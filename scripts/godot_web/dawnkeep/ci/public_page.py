#!/usr/bin/env python3
"""Bounded Dawnkeep publication acceptance, using only actual browser inputs.

A local isolated build and the allowlisted deployed Pages origin use the same
checks. The frozen eight-wave runtime is not re-exported or replayed here.
"""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import unquote, urljoin, urlsplit

from capture_browser import (BROWSER_ARGS, BROWSER_IGNORED_DEFAULT_ARGS,
                             RequiredPayloadOutage, browser_executable, canvas_point)
from common import check_engine_log, isolated_output, receipts, sha256, write_json
from interaction import InputPlan
from media import inspect_video

SLUG = 'dawnkeep-defense'
OFFICIAL_BASE = 'https://dcc-mcp.github.io/showcase/'
CHROME = '/opt/google/chrome/chrome'
PCK_NAME = 'dawnkeep-649ccf7ed6a7.pck'
PCK_SHA256 = '649ccf7ed6a762fb00315c07fe6253d35a626fe907f0cb23a238537bb0c3b29b'
CASE_ROOT = f'docs/showcase/{SLUG}/'
PLAY_ROOT = f'play/{SLUG}/'
ROOT = Path(__file__).resolve().parents[4]
# Reuse the site's existing, independently tested HTTP Range implementation.
# The exported-runtime preview handler intentionally has no media range logic.
sys.path.append(str(ROOT / 'scripts'))
from browser_preview import QuietHandler as RangeHTTPHandler
from tracked_file_bytes import MAX_LFS_POINTER_BYTES, matches_lfs_content


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def selected_pairs(locale='all', viewport='all'):
    if locale not in ('all', 'en', 'zh') or viewport not in ('all', 'desktop', 'portrait'):
        raise ValueError('Unsupported publication locale/viewport selector')
    return [(language, layout == 'portrait') for language in ('en', 'zh')
            for layout in ('desktop', 'portrait')
            if locale in ('all', language) and viewport in ('all', layout)]


def progress_event(stage, status, **details):
    row = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'stage': stage, 'status': status, **details}
    print('DAWNKEEP_PUBLIC_PROGRESS ' + json.dumps(row, ensure_ascii=False), flush=True)
    return row


def native_media_point(box, control):
    """CSS coordinates for the reviewed stable-Chrome native control strip.

    Run 39351546034's actual desktop and 390px portrait failure captures show
    the native timeline centered 22 CSS px above the video bottom, and the
    play/pause control 24 px from its left and 50 px above its bottom. Read the
    current rendered video rectangle each time; never write media state.
    """
    values = [box.get(key) for key in ('x', 'y', 'width', 'height')]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError('Native media controls require finite actual video geometry')
    x, y, width, height = values
    if width < 200 or height < 100:
        raise ValueError('Actual video is too small for the reviewed native controls')
    if control == 'timeline':
        return x + width / 2, y + height - 22
    if control == 'play-pause':
        return x + 24, y + height - 50
    raise ValueError('Unknown native media control')


def deployed_base(value):
    # This is an acceptance gate for one official publication, not a URL runner.
    if value != OFFICIAL_BASE:
        raise ValueError('Deployed acceptance requires exactly ' + OFFICIAL_BASE)
    return value


def public_path(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Invalid public artifact path')
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in ('.', '..') for p in path.parts):
        raise ValueError('Public artifact path must be canonical and relative')
    if urlsplit(value).scheme or urlsplit(value).query or urlsplit(value).fragment or unquote(value) != value:
        raise ValueError('Public artifact path cannot contain URL escaping or parameters')
    return value


def in_site(url, base):
    parsed, allowed = urlsplit(url), urlsplit(base)
    path = unquote(parsed.path)
    return ((parsed.scheme, parsed.netloc) == (allowed.scheme, allowed.netloc)
            and path.startswith(allowed.path) and '\\' not in path
            and not any(part in ('.', '..') for part in path.split('/')))


def engine_request(url):
    path = urlsplit(url).path
    return path.endswith(('.pck', '.wasm')) or '/runtime/godot-' in path


def verify_bytes(data, entry, label):
    observed = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    if observed != {key: entry.get(key) for key in ('sha256', 'bytes')}:
        raise ValueError('Public byte/hash mismatch: ' + label)
    return observed


def installed_chrome():
    path = Path(CHROME)
    if not path.is_file() or not os.access(path, os.X_OK) or path.resolve() != path:
        raise ValueError('Required canonical preinstalled stable Chrome is unavailable: ' + CHROME)
    selected = browser_executable(CHROME)
    if not re.fullmatch(r'Google Chrome [0-9]+(?:\.[0-9]+){3}(?: .*)?', selected['executable_version']):
        raise ValueError('Preinstalled stable Google Chrome is required')
    return selected


def verify_tracked_bytes(repo):
    """Match raw HEAD blobs or hydrated LFS content and modes, without filters.

    Legacy media blobs in this repository inherit filter=lfs despite being
    committed as ordinary binary blobs. A runner with LFS installed therefore
    reports synthetic pointer conversions in a normal worktree diff. Never
    waive those paths: ordinary blobs must match raw bytes, while hydrated LFS
    files must match the committed pointer size and SHA-256.
    """
    repo = Path(repo).resolve()
    tree = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-r', '-z', '--full-tree', 'HEAD'])
    mismatches = []
    count = 0
    for record in tree.split(b'\0'):
        if not record:
            continue
        metadata, raw_name = record.split(b'\t', 1)
        mode, kind, expected = metadata.decode('ascii').split()
        name = os.fsdecode(raw_name)
        path = repo / name
        count += 1
        if kind != 'blob' or mode not in ('100644', '100755', '120000'):
            mismatches.append(name + ': unsupported tracked object/mode')
            continue
        if any(parent.is_symlink() for parent in path.parents if parent != repo and repo in parent.parents):
            mismatches.append(name + ': symlink ancestor')
            continue
        try:
            before = path.lstat()
            digest = hashlib.sha1()
            if mode == '120000':
                if not stat.S_ISLNK(before.st_mode):
                    raise ValueError('expected tracked symlink')
                data = os.fsencode(os.readlink(path))
                digest.update(b'blob ' + str(len(data)).encode() + b'\0' + data)
            else:
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError('expected regular tracked file')
                executable = bool(before.st_mode & stat.S_IXUSR)
                if executable != (mode == '100755'):
                    raise ValueError('tracked executable mode differs')
                digest.update(b'blob ' + str(before.st_size).encode() + b'\0')
                content_digest = hashlib.sha256()
                content_size = 0
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                        content_digest.update(chunk)
                        content_size += len(chunk)
            if digest.hexdigest() != expected:
                pointer = b''
                if mode in ('100644', '100755') and int(subprocess.check_output(
                        ['git', '-C', str(repo), 'cat-file', '-s', expected])) <= MAX_LFS_POINTER_BYTES:
                    pointer = subprocess.check_output(
                        ['git', '-C', str(repo), 'cat-file', 'blob', expected])
                if not pointer or not matches_lfs_content(
                        pointer, content_size, content_digest.hexdigest()):
                    raise ValueError('raw tracked bytes differ from HEAD blob')
            after = path.lstat()
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode):
                raise ValueError('tracked file changed while hashing')
        except (OSError, ValueError) as error:
            mismatches.append(name + ': ' + str(error))
    require(count > 0, 'Expected source tree has no tracked blobs')
    require(not mismatches, 'Tracked source differs from exact HEAD: ' + '; '.join(mismatches))
    return {'method': 'Raw Git blobs or exact LFS pointer content and executable/symlink modes; no clean/smudge filters',
            'tracked_blobs_checked': count, 'tree_listing_sha256': hashlib.sha256(tree).hexdigest()}


def source_receipt(repo, expected):
    if not re.fullmatch('[a-f0-9]{40}', expected or ''):
        raise ValueError('Expected source head must be a full lowercase Git SHA')
    head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if head != expected:
        raise ValueError('Checkout does not match the expected source head')
    # Index changes remain fatal. Unlike a worktree diff, this compares stored
    # objects and does not run a clean filter over the checked-out media.
    try:
        subprocess.run(['git', '-C', str(repo), 'diff', '--cached', '--name-status',
                        '--no-ext-diff', '--no-textconv', '--exit-code', 'HEAD', '--'],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError('Tracked index differs from expected HEAD: ' +
                           (error.stdout or error.stderr or str(error)).strip()) from error
    tracked = verify_tracked_bytes(repo)
    files = [Path(__file__), Path(__file__).with_name('interaction.py'),
             Path(__file__).with_name('capture_browser.py'), Path(__file__).with_name('common.py'),
             Path(__file__).with_name('media.py'), ROOT / 'scripts/browser_preview.py']
    return {'expected_head_sha': expected, 'checkout_head_sha': head,
            'tracked_checkout_matches_head_bytes_and_modes': True, 'tracked_source': tracked,
            'acceptance_scripts': [{'name': f.name, 'sha256': sha256(f)} for f in files]}


def artifact_inventory(repo):
    play = json.loads((repo / 'play/manifest.json').read_text())
    case = json.loads((repo / CASE_ROOT / 'manifest.json').read_text())
    require(play.get('schema_version') == 1 and case.get('schema_version') == 1, 'Manifest schema changed')
    entries = {public_path(e['path']): e for e in play['files']}
    expected_pck = PLAY_ROOT + PCK_NAME
    require(entries.get(expected_pck, {}).get('sha256') == PCK_SHA256,
            'Published Dawnkeep must retain the verified frozen PCK bytes')
    selected = {e['case_slug']: e for e in play['demos']}
    require(selected.get(SLUG, {}).get('url') == PLAY_ROOT + 'index.html', 'Dawnkeep playable declaration is missing')
    case_entries = {CASE_ROOT + public_path(e['path']): e for e in case['files']}
    zips = [name for name in case_entries if name.endswith('.zip')]
    films = [name for name in case_entries if name.endswith(('.mp4', '.webm'))]
    require(len(zips) == 1, 'Exactly one inventoried native source ZIP is required')
    require(bool(films), 'At least one inventoried delivered film is required')
    assets = {name: item for name, item in entries.items()
              if name.startswith(PLAY_ROOT) or name.startswith('play/runtime/godot-4.6.3.')}
    for name in ('play/manifest.json', CASE_ROOT + 'manifest.json', 'assets/games.js',
                 'assets/playable.js', 'assets/preview.js', 'assets/games.css', 'assets/site.css'):
        path = repo / name
        assets[name] = {'sha256': sha256(path), 'bytes': path.stat().st_size}
    assets.update({name: item for name, item in case_entries.items()
                   if name.endswith(('.png', '.jpg', '.jpeg', '.mp4', '.webm', '.zip'))})
    return {'assets': assets, 'source_zip': zips[0], 'films': films, 'pck': expected_pck}


def verify_media_range(request, base, name, data):
    """Require an actual bounded partial response from local AND deployed hosts."""
    require(len(data) >= 2048, 'Delivered film is too small for a meaningful range probe')
    start = len(data) // 2
    end = min(start + 1023, len(data) - 1)
    response = request.get(urljoin(base, name),
                           headers={'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'},
                           timeout=30000, max_redirects=0)
    result = {'url': response.url, 'status': response.status,
              'requested_range': f'bytes={start}-{end}',
              'content_range': response.headers.get('content-range'),
              'content_length': response.headers.get('content-length'),
              'accept_ranges': response.headers.get('accept-ranges')}
    try:
        require(response.status == 206 and in_site(response.url, base),
                'Native media requires a same-origin HTTP 206 Range response: ' + json.dumps(result))
        require(result['content_range'] == f'bytes {start}-{end}/{len(data)}'
                and result['content_length'] == str(end - start + 1),
                'Media Range headers do not match the requested interval: ' + json.dumps(result))
        partial_data = response.body()
        require(partial_data == data[start:end + 1],
                'Media Range bytes differ from the verified complete film: ' + name)
        result.update({'bytes': len(partial_data), 'sha256': hashlib.sha256(partial_data).hexdigest(),
                       'matches_verified_film_slice': True})
        return result
    finally:
        response.dispose()


def midpoint_seekable(state):
    duration = state.get('duration')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        return False
    target = duration / 2
    return any(isinstance(span, list) and len(span) == 2
               and all(type(value) in (int, float) and math.isfinite(value) for value in span)
               and span[0] <= target <= span[1] for span in state.get('seekable', []))


def fetch_artifacts(request, base, inventory, output, report):
    """Check actual public bytes against the exact checkout, without rebuilding live."""
    result = {}
    report['public_artifacts'] = result
    for name, expected in inventory['assets'].items():
        response = request.get(urljoin(base, name), timeout=180000, max_redirects=0)
        result[name] = {'url': response.url, 'status': response.status,
                        'content_type': response.headers.get('content-type'), 'expected': expected}
        require(response.status == 200 and in_site(response.url, base), 'Public artifact unavailable: ' + name)
        data = response.body()
        result[name].update({'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        verify_bytes(data, expected, name)
        if name in inventory['films']:
            result[name]['http_range'] = verify_media_range(request, base, name, data)
            path = output / Path(name).name
            path.write_bytes(data)
            result[name]['decode'] = inspect_video(path)
        response.dispose()
    report['public_artifacts'] = result
    report['frozen_pck_sha256'] = result[inventory['pck']]['sha256']


class Session:
    """One locale/viewport, with passive observations and physical input receipts."""
    def __init__(self, browser, base, output, locale, mobile, inventory):
        self.base, self.output, self.locale, self.mobile = base, output, locale, mobile
        self.inventory = inventory
        self.started_at = time.monotonic()
        self.console, self.errors, self.requests, self.responses, self.network_failures = [], [], [], [], []
        self.result = {'locale': locale, 'touch_emulation': mobile, 'passed': False, 'checks': [], 'events': []}
        self.context = browser.new_context(viewport={'width': 390 if mobile else 1440,
                                                    'height': 844 if mobile else 1080},
                                           device_scale_factor=1, is_mobile=mobile, has_touch=mobile,
                                           accept_downloads=True, reduced_motion='reduce', service_workers='block')
        self.context.route('**/*', self.guard_origin)
        self.page = self.context.new_page()
        self.page.on('console', lambda message: self.console.append(message.text))
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('request', lambda request: self.requests.append(request.url))
        self.page.on('response', lambda response: self.responses.append(
            {'url': response.url, 'status': response.status, 'content_type': response.headers.get('content-type')}))
        self.page.on('requestfailed', lambda request: self.network_failures.append(
            {'url': request.url, 'failure': request.failure}))
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(120000)
        output.mkdir()

    def progress(self, stage, status, **details):
        row = progress_event(stage, status, locale=self.locale,
                             viewport='portrait' if self.mobile else 'desktop',
                             elapsed_seconds=round(time.monotonic() - self.started_at, 2), **details)
        self.result.setdefault('progress', []).append(row)

    def media_control(self, video, control):
        video.scroll_into_view_if_needed()
        box = video.bounding_box()
        require(box is not None, 'Actual video control geometry is missing')
        x, y = native_media_point(box, control)
        viewport = self.page.viewport_size
        require(0 <= x < viewport['width'] and 0 <= y < viewport['height'],
                'Native media gesture is outside the browser viewport')
        require(video.evaluate('v=>v.controls'), 'Native video controls are not enabled')
        require(self.page.evaluate('p=>document.elementFromPoint(p.x,p.y)===document.querySelector("video")',
                                   {'x': x, 'y': y}), 'Native video control is occluded')
        if not self.mobile:
            self.page.mouse.move(x, y)
            self.page.wait_for_timeout(150)
        (self.page.touchscreen.tap if self.mobile else self.page.mouse.click)(x, y)
        event = {'type': 'touchscreen.tap' if self.mobile else 'mouse.click',
                 'target': 'Chrome native video ' + control, 'x': x, 'y': y, 'video_geometry': box}
        self.result['events'].append(event)
        return event

    def media_state(self, video):
        return video.evaluate('''v => ({time:v.currentTime,duration:v.duration,paused:v.paused,
            seeking:v.seeking,readyState:v.readyState,controls:v.controls,
            seekable:Array.from({length:v.seekable.length},(_,i)=>[v.seekable.start(i),v.seekable.end(i)]),
            totalVideoFrames:v.getVideoPlaybackQuality().totalVideoFrames,
            error:v.error ? {code:v.error.code,message:v.error.message} : null})''')

    def guard_origin(self, route):
        url = route.request.url
        if in_site(url, self.base) or url.startswith(('blob:', 'data:')):
            route.continue_()
        else:
            self.errors.append('Unexpected cross-origin browser request: ' + url)
            route.abort()

    def healthy(self):
        require(not self.errors, 'Browser JavaScript/origin error: ' + repr(self.errors))
        check_engine_log('\n'.join(self.console))
        bad = [r for r in self.responses if r['status'] >= 400 and
               (engine_request(r['url']) or urlsplit(r['url']).path.endswith(('.js', '.css')) or
                CASE_ROOT in r['url'] or PLAY_ROOT in r['url'])]
        require(not bad, 'Failed public resource responses: ' + repr(bad))

    def wait(self, predicate, label, seconds=120):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.healthy()
            if predicate():
                return
            self.page.wait_for_timeout(100)
        raise TimeoutError(label)

    def line(self, prefix, boundary=0, seconds=120):
        self.wait(lambda: bool(receipts('\n'.join(self.console[boundary:]), prefix)),
                  'Missing actual ' + prefix, seconds)
        return receipts('\n'.join(self.console[boundary:]), prefix)[-1]

    def shot(self, name, state=None):
        path = self.output / (name + '.png')
        self.page.screenshot(path=str(path), timeout=45000)
        row = {'path': path.name, 'sha256': sha256(path)}
        if state is not None:
            row['state'] = state
        self.result.setdefault('screenshots', []).append(row)

    def click(self, selector, scope=None):
        target = (scope or self.page).locator(selector)
        (target.tap if self.mobile else target.click)()
        self.result['events'].append({'type': 'touchscreen.tap' if self.mobile else 'mouse.click',
                                      'selector': selector})

    def key(self, name, down):
        (self.page.keyboard.down if down else self.page.keyboard.up)(name)
        self.result['events'].append({'type': 'keyboard.down' if down else 'keyboard.up', 'key': name})

    def keyboard_press(self, name):
        self.page.keyboard.press(name)
        self.result['events'].append({'type': 'keyboard.press', 'key': name})

    def navigate(self, relative):
        response = self.page.goto(urljoin(self.base, relative), wait_until='domcontentloaded')
        require(response and response.status == 200 and in_site(self.page.url, self.base),
                'Public page did not load: ' + relative)
        self.wait(lambda: self.page.evaluate('document.readyState === "complete"'), 'Page load did not settle')
        self.layout(relative)

    def layout(self, label):
        observed = self.page.evaluate('''() => ({lang:document.documentElement.lang,
            width:innerWidth, scrollWidth:document.documentElement.scrollWidth})''')
        require(observed['scrollWidth'] <= observed['width'] + 1, 'Horizontal overflow: ' + label)
        require(observed['lang'].lower().startswith(self.locale), 'Wrong public page locale: ' + label)
        self.result['checks'].append({'name': label + ' locale/layout', 'observed': observed})

    def prefix(self):
        return 'zh/' if self.locale == 'zh' else ''

    def no_engine_since(self, index, label):
        loaded = [url for url in self.requests[index:] if engine_request(url)]
        require(not loaded and self.page.locator('iframe').count() == 0,
                'Engine loaded before user Start: ' + label + repr(loaded))
        self.result['checks'].append({'name': label + ' on-demand engine', 'passed': True})

    def decoded_frames(self, video):
        # Observation only: requestVideoFrameCallback reads actual presented frames.
        sample = video.evaluate('''v => new Promise((resolve,reject) => {
            const timer=setTimeout(()=>reject(new Error('No two decoded video frames')),15000);
            v.requestVideoFrameCallback((_,a)=>v.requestVideoFrameCallback((__,b)=>{
                clearTimeout(timer);resolve({first:a.mediaTime,last:b.mediaTime,
                    firstPresented:a.presentedFrames,lastPresented:b.presentedFrames,
                    width:v.videoWidth,height:v.videoHeight,total:v.getVideoPlaybackQuality().totalVideoFrames});
            }));
        })''')
        require(sample['last'] > sample['first'] and sample['lastPresented'] > sample['firstPresented']
                and sample['total'] > 1 and sample['width'] > 200, 'Video did not present advancing decoded frames')
        return sample

    def gallery(self):
        from playwright.sync_api import expect
        boundary = len(self.requests)
        self.navigate(self.prefix())
        search = self.page.locator('#search')
        card = self.page.locator(f'.case-card[data-case="{SLUG}"]')
        expect(card).to_have_count(1)
        title = card.locator('.card-title').inner_text()
        search.fill(title)
        expect(self.page.locator('.case-card:visible')).to_have_count(1)
        disclosure = self.page.locator('.filter-disclosure')
        if disclosure.get_attribute('open') is None:
            self.click('.filter-disclosure summary')
        self.click('[data-filter="software"] [data-value="Godot"]')
        expect(card).to_be_visible()
        shelf = self.page.locator(f'[data-game-case="{SLUG}"]')
        expect(shelf).to_be_visible()
        require(shelf.locator('.game-cover').evaluate('a=>a.href').endswith(f'/games/{SLUG}/'),
                'Dawnkeep game shelf card points to the wrong game')
        self.no_engine_since(boundary, 'gallery/card')
        card.scroll_into_view_if_needed()
        image = card.locator('img').first
        self.wait(lambda: image.evaluate('i=>i.complete && i.naturalWidth>0'), 'Gallery poster is not decoded')
        self.click(f'[data-case="{SLUG}"] .preview-toggle')
        self.wait(lambda: card.get_attribute('data-preview-state') == 'playing', 'Card preview did not play')
        frames = self.decoded_frames(card.locator('video'))
        self.shot('gallery-preview')
        self.click(f'[data-case="{SLUG}"] .preview-toggle')
        require(card.locator('video').evaluate('v=>v.paused && !v.hasAttribute("src")'), 'Card preview did not release media')
        self.no_engine_since(boundary, 'card film preview')
        self.result['checks'].append({'name': 'gallery actual preview play/stop', 'frames': frames})
        self.click(f'[data-case="{SLUG}"] .card-title a')
        self.wait(lambda: urlsplit(self.page.url).path.endswith(f'/cases/{SLUG}/'), 'Card did not open case')
        self.page.go_back(wait_until='domcontentloaded')
        expect(card).to_be_visible()
        self.page.go_forward(wait_until='domcontentloaded')
        require(urlsplit(self.page.url).path.endswith(f'/cases/{SLUG}/'), 'Forward did not restore case')
        self.page.go_back(wait_until='domcontentloaded')
        self.click('#reset-filters')
        search.fill('no-dawnkeep-match-acceptance-93e1')
        expect(self.page.locator('.case-card:visible')).to_have_count(0)
        self.click('#reset-filters')
        expect(card).to_be_visible()
        self.result['checks'].append({'name': 'search/filter/empty/reset/back/forward', 'passed': True})

    def reveal_native_point(self, geometry, x, y, label):
        """Scroll the parent using a real wheel over a verified parent surface.

        In portrait the running iframe can cover (1,1), so wheeling there is
        delivered to Godot and consumed. Never target a fixed browser corner.
        """
        viewport = self.page.viewport_size
        for attempt in range(3):
            geo = geometry()
            px, py = canvas_point(geo, x, y)
            if 8 <= py <= viewport['height'] - 8:
                return geo, px, py
            surface = self.page.evaluate('''() => {
                const ys=[innerHeight-16,16,innerHeight/2];
                for(let y=32;y<innerHeight-16;y+=32) ys.push(y);
                for(const y of ys) for(const x of [innerWidth/2,8,innerWidth-8]) {
                    const node=document.elementFromPoint(x,y);
                    if(!node || node.closest('iframe,video,audio,canvas,input,textarea,select,[contenteditable=true]')) continue;
                    let nested=false;
                    for(let p=node;p && p!==document.body && p!==document.documentElement;p=p.parentElement) {
                        if(/auto|scroll/.test(getComputedStyle(p).overflowY) && p.scrollHeight>p.clientHeight+1) {nested=true;break;}
                    }
                    if(!nested) return {x,y,tag:node.tagName,scrollY};
                }
                return null;
            }''')
            require(surface is not None, 'No unobscured parent-page surface for physical scrolling')
            delta = py - viewport['height'] / 2
            self.page.mouse.move(surface['x'], surface['y'])
            self.page.mouse.wheel(0, delta)
            self.wait(lambda: abs(geometry()['y'] - geo['y']) > .5,
                      'Physical wheel did not scroll the parent page', 5)
            self.page.wait_for_timeout(200)
            after = geometry()
            self.result['events'].append({'type': 'mouse.wheel', 'stage': label,
                'target': 'observed non-embedded parent surface', 'surface': surface,
                'delta_y': delta, 'canvas_before': geo, 'canvas_after': after,
                'attempt': attempt + 1})
        geo = geometry()
        px, py = canvas_point(geo, x, y)
        require(8 <= py <= viewport['height'] - 8,
                'Native control remains outside viewport after physical parent scrolling')
        return geo, px, py

    def native_plan(self, frame, boundary, label):
        self.progress(label + '-engine', 'waiting-for-rendered-frame')
        self.line('DAWNKEEP_FRAME_READY', boundary)
        self.line('DAWNKEEP_STATE', boundary)
        self.progress(label + '-engine', 'rendered-native-state-observed')
        canvas = frame.locator('#canvas')

        def observe():
            self.healthy()
            values = receipts('\n'.join(self.console[boundary:]))
            require(bool(values), 'No actual Godot state after this launch')
            return values[-1]

        def geometry():
            box = canvas.bounding_box()
            require(box is not None, 'Actual engine canvas is unavailable')
            local = canvas.evaluate('''c => {const r=c.getBoundingClientRect(),t=document.querySelector('#dawnkeep-web-tools').getBoundingClientRect();
                return {pixel_width:c.width,pixel_height:c.height,left:r.left,top:r.top,
                    bottom:r.bottom,toolbar_bottom:t.bottom,viewport_height:innerHeight};}''')
            require(local['toolbar_bottom'] <= local['top'] + 1 and local['bottom'] <= local['viewport_height'] + 1,
                    'Web shell overlaps/clips actual canvas')
            return {**box, **local}

        def click(x, y):
            geo, px, py = self.reveal_native_point(geometry, x, y, label)
            viewport = self.page.viewport_size
            require(0 <= px < viewport['width'] and 0 <= py < viewport['height'], 'Actual native input is outside browser viewport')
            local = {'x': geo['left'] + x * geo['width'] / geo['pixel_width'],
                     'y': geo['top'] + y * geo['height'] / geo['pixel_height']}
            require(frame.evaluate('p=>document.elementFromPoint(p.x,p.y)===document.querySelector("#canvas")', local),
                    'Web wrapper occludes actual native control')
            top_selector = '#canvas' if frame == self.page.main_frame else 'iframe'
            require(self.page.evaluate('p=>document.elementFromPoint(p.x,p.y)?.matches(p.selector)',
                                       {'x': px, 'y': py, 'selector': top_selector}), 'Parent page occludes engine pointer')
            (self.page.touchscreen.tap if self.mobile else self.page.mouse.click)(px, py)
            self.result['events'].append({'type': 'touchscreen.tap' if self.mobile else 'mouse.click',
                                          'engine_x': x, 'engine_y': y, 'x': px, 'y': py, 'stage': label})

        geo = geometry()
        self.result['checks'].append({'name': label + ' actual canvas geometry', 'observed': geo})
        return InputPlan(observe, click, self.key, lambda seconds: self.page.wait_for_timeout(seconds * 1000),
                         (geo['pixel_width'], geo['pixel_height']),
                         lambda name: self.shot(label + '-' + name, observe()), self.result)

    def embedded_frame(self, selector):
        self.wait(lambda: self.page.locator(selector).count() == 1, 'Expected one engine iframe')
        def loaded_frame():
            candidate = self.page.locator(selector).element_handle().content_frame()
            return candidate if candidate is not None and in_site(candidate.url, self.base) else None
        self.wait(lambda: loaded_frame() is not None, 'Missing same-origin engine frame')
        return loaded_frame()

    def shell_language(self, frame, language, label):
        from playwright.sync_api import expect
        expected = ({'quit': '退出游戏', 'fullscreen': '全屏', 'restart': '重新打开', 'retry': '重新载入'}
                    if language == 'zh' else
                    {'quit': 'Quit game', 'fullscreen': 'Fullscreen', 'restart': 'Open again', 'retry': 'Retry loading'})
        observed = {}
        for name, text in expected.items():
            control = frame.locator('#dawnkeep-web-' + name)
            expect(control).to_have_text(text)
            observed[name] = control.text_content()
        self.result['checks'].append({'name': label + ' shell language', 'language': language, 'observed': observed})

    def game_page(self):
        from playwright.sync_api import expect
        boundary = len(self.requests)
        self.navigate(self.prefix() + f'games/{SLUG}/')
        self.page.wait_for_timeout(400)
        expect(self.page.locator('[data-game-poster]')).to_be_visible()
        self.wait(lambda: self.page.locator('[data-game-poster] img').evaluate('i=>i.complete && i.naturalWidth>0'),
                  'Dedicated game poster is not decoded')
        self.no_engine_since(boundary, 'dedicated game poster')
        self.shot('game-poster')
        boundary = len(self.console)
        self.click('[data-game-start]')
        frame = self.embedded_frame('[data-game-frame] iframe')
        plan = self.native_plan(frame, boundary, 'game')
        self.shell_language(frame, plan.current()['language'], 'game intro')
        require(any(urlsplit(url).path.endswith('/' + PCK_NAME) for url in self.requests),
                'Actual browser did not request the frozen public PCK')
        require(any(urlsplit(url).path.endswith('/runtime/godot-4.6.3.wasm') for url in self.requests),
                'Actual browser did not request the common official Godot WASM')
        expect(self.page.locator('[data-game-stage]')).to_have_attribute('data-state', 'running', timeout=120000)
        expect(self.page.locator('[data-game-sound]')).to_be_hidden()
        plan.gate(touch=self.mobile)
        self.shell_language(frame, plan.current()['language'], 'game after native language input')
        self.progress('native-input-gate', 'passed')
        before = plan.tap('start_wave')
        plan.wait(lambda state: state.get('wave', 0) > before['wave'], 'native next-wave through visible UI', before['sample_id'])
        plan.restart_game('native restart after actual wave start')
        self.shot('native-reset', plan.current())
        self.progress('native-wave-and-reset', 'passed')
        # The outer reset must really navigate the engine document, not merely
        # reset a shell label or send an ignored game command.
        boundary = len(self.console)
        with frame.expect_navigation(wait_until='domcontentloaded'):
            self.click('[data-game-reset]')
        fresh = self.native_plan(frame, boundary, 'outer-reset').current()
        require('start' in fresh['ui']['controls'] and fresh['wave'] == 0, 'Outer reset did not create fresh native intro')
        self.result['checks'].append({'name': 'outer reset performed real iframe reload', 'state': fresh})
        self.click('[data-game-fullscreen]')
        self.wait(lambda: self.page.evaluate('document.fullscreenElement?.matches("[data-game-stage]") === true'),
                  'Outer fullscreen did not engage', 15)
        self.shot('outer-fullscreen')
        self.click('[data-game-leave-full]')
        self.wait(lambda: self.page.evaluate('!document.fullscreenElement'), 'Outer fullscreen did not exit', 15)
        self.click('[data-game-exit]')
        expect(self.page.locator('[data-game-frame] iframe')).to_have_count(0)
        expect(self.page.locator('[data-game-poster]')).to_be_visible()
        self.page.wait_for_timeout(300)
        stopped = len(receipts('\n'.join(self.console)))
        self.page.wait_for_timeout(500)
        require(len(receipts('\n'.join(self.console))) == stopped, 'Exited iframe still emits engine state')
        boundary = len(self.console)
        self.click('[data-game-start]')
        frame = self.embedded_frame('[data-game-frame] iframe')
        fresh = self.native_plan(frame, boundary, 'reopened-game').current()
        require('start' in fresh['ui']['controls'] and fresh['wave'] == 0, 'Reopened game retained old runtime')
        self.click('[data-game-exit]')
        self.layout('game after lifecycle')
        self.result['checks'].append({'name': 'outer fullscreen/exit/reopen', 'passed': True})
        if self.locale == 'en' and not self.mobile:
            self.progress('required-pck-outage', 'started')
            outage = RequiredPayloadOutage()
            pattern = '**/' + PCK_NAME + '*'
            self.page.route(pattern, outage)
            boundary = len(self.console)
            try:
                self.click('[data-game-start]')
                # The publication bridge can notify the parent before the
                # original shell logs its load-error receipt. Removing that
                # iframe may lose its last console message. Assert the visible
                # parent failure and real failed request, not teardown timing.
                self.wait(lambda: self.page.locator('[data-game-stage]').get_attribute('data-state') == 'error',
                          'Required-PCK outage did not reach the outer error UI')
                expect(self.page.locator('[data-game-stage]')).to_have_attribute('data-state', 'error')
                expect(self.page.locator('[data-game-frame] iframe')).to_have_count(0)
                require(outage.attempts > 0, 'Actual required-PCK outage was not exercised')
                self.healthy()
                load_error_logs = receipts('\n'.join(self.console[boundary:]), 'DAWNKEEP_WEB_LOAD_ERROR')
                self.shot('outer-load-error')
            finally:
                self.page.unroute(pattern, outage)
            boundary = len(self.console)
            self.click('[data-game-start]')
            frame = self.embedded_frame('[data-game-frame] iframe')
            self.native_plan(frame, boundary, 'outer-load-retry')
            expect(self.page.locator('[data-game-stage]')).to_have_attribute('data-state', 'running')
            self.click('[data-game-exit]')
            self.progress('required-pck-outage', 'passed', aborted_requests=outage.attempts)
            self.result['checks'].append({'name': 'actual PCK outage, outer error and visible retry',
                                          'aborted_requests': outage.attempts, 'load_error_receipts': load_error_logs,
                                          'parent_error_observed': True, 'failed_iframe_removed': True,
                                          'fresh_retry_rendered': True, 'passed': True})
        # The gallery launch button is a separate real user gesture that the
        # existing site carries across navigation, without test-written storage.
        self.navigate(self.prefix())
        boundary = len(self.console)
        self.click(f'[data-game-launch="{SLUG}"]')
        self.wait(lambda: urlsplit(self.page.url).path.endswith(f'/games/{SLUG}/'), 'Gallery Start did not navigate')
        frame = self.embedded_frame('[data-game-frame] iframe')
        self.native_plan(frame, boundary, 'gallery-launch')
        self.click('[data-game-exit]')
        self.result['checks'].append({'name': 'actual gallery Start gesture opened native game', 'passed': True})

    def case_viewport_fit(self, frame):
        observed = self.page.evaluate('''() => {
            const section=document.querySelector('[data-playable]');
            const rect=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};};
            return {width:innerWidth,height:innerHeight,open:section.dataset.playOpen,
                actions:rect(section.querySelector('.playable-actions')),
                exit:rect(section.querySelector('[data-play-exit]')),
                frame:rect(section.querySelector('iframe'))};
        }''')
        require(observed['open'] == 'true', 'Dawnkeep case did not enable viewport-fit controls')
        for key in ('actions', 'exit', 'frame'):
            rect = observed[key]
            require(rect['x'] >= -1 and rect['y'] >= -1
                    and rect['right'] <= observed['width'] + 1 and rect['bottom'] <= observed['height'] + 1,
                    'Case ' + key + ' is not wholly reachable in the actual viewport: ' + json.dumps(observed))
        require(observed['exit']['height'] >= 44 and observed['exit']['width'] >= 44,
                'Case Exit lacks a 44px touch target')
        require(observed['actions']['bottom'] <= observed['frame']['y'] + 1,
                'Case toolbar overlaps the native iframe')
        box = frame.locator('#canvas').bounding_box()
        require(box is not None and box['y'] >= observed['actions']['bottom']
                and box['y'] + box['height'] <= observed['height'] + 1,
                'Case native canvas is clipped outside its reachable toolbar')
        self.result['checks'].append({'name': 'case viewport-fit native canvas and 44px Exit', 'observed': observed})

    def case_page(self):
        from playwright.sync_api import expect
        boundary = len(self.requests)
        self.navigate(self.prefix() + f'cases/{SLUG}/')
        self.no_engine_since(boundary, 'case page')
        video = self.page.locator('video').first
        video.scroll_into_view_if_needed()
        expect(video).to_have_js_property('controls', True)
        require(video.evaluate('v=>!v.autoplay && v.paused && v.played.length===0'), 'Case film unexpectedly autoplayed')
        video.focus()
        self.keyboard_press('Space')
        self.wait(lambda: video.evaluate('v=>!v.paused && v.readyState>=3 && v.currentTime>.2'), 'Native video playback did not begin')
        frames = self.decoded_frames(video)
        self.keyboard_press('Space')
        self.wait(lambda: video.evaluate('v=>v.paused'), 'Native video pause failed')
        self.progress('native-film-seekability', 'waiting', state=self.media_state(video))
        self.wait(lambda: midpoint_seekable(self.media_state(video)),
                  'Browser did not expose a native seekable range covering the film midpoint')
        before = self.media_state(video)
        self.progress('native-film-seekability', 'passed', state=before)
        self.page.wait_for_timeout(300)
        require(abs(self.media_state(video)['time'] - before['time']) < .1, 'Paused video continues advancing')
        require(math.isfinite(before['duration']) and before['duration'] > before['time'] + 3,
                'Native film has no finite forward-seek interval')
        self.shot('case-film-before-seek')
        self.progress('native-film-seek', 'started', before=before)
        gesture = self.media_control(video, 'timeline')
        self.wait(lambda: self.media_state(video)['time'] > before['time'] + 1,
                  'Physical native timeline seek did not advance')
        self.wait(lambda: video.evaluate('v=>!v.seeking && v.readyState>=2 && v.paused'),
                  'Native timeline seek did not settle while paused')
        after = self.media_state(video)
        require(after['time'] < after['duration'] - 1, 'Native timeline seek landed at the end instead of the middle')
        self.shot('case-film-after-seek')
        self.progress('native-film-seek', 'passed', before=before, after=after, gesture=gesture)
        self.media_control(video, 'play-pause')
        self.wait(lambda: video.evaluate('v=>!v.paused'), 'Native video resume failed')
        resumed = self.decoded_frames(video)
        require(resumed['first'] >= after['time'] - .1 and resumed['last'] > after['time'],
                'Resumed decoded frames did not advance from the actual seek position')
        self.media_control(video, 'play-pause')
        self.wait(lambda: video.evaluate('v=>v.paused'), 'Native film final pause failed')
        self.shot('case-film')
        media_url = video.evaluate('v=>v.currentSrc')
        require(any(urlsplit(media_url).path == urlsplit(urljoin(self.base, f)).path for f in self.inventory['films']),
                'Page film is not the accepted inventoried media')
        self.result['checks'].append({'name': 'native film play/pause/seek/resume', 'url': media_url,
                                      'frames': frames, 'resumed_frames': resumed, 'seeked_seconds': after['time'],
                                      'seek_before': before, 'seek_after': after, 'seek_gesture': gesture})
        self.progress('native-film-playback', 'passed')
        name = Path(self.inventory['source_zip']).name
        download_link = self.page.locator(f'a[download="{name}"]').first
        expect(download_link).to_have_count(1)
        with self.page.expect_download() as event:
            (download_link.tap if self.mobile else download_link.click)()
        download = event.value
        require(download.failure() is None, 'Actual native source download failed')
        data = Path(download.path()).read_bytes()
        observed = verify_bytes(data, self.inventory['assets'][self.inventory['source_zip']], name)
        self.result['checks'].append({'name': 'actual native ZIP download', **observed})
        self.progress('native-zip-download', 'passed', **observed)
        boundary = len(self.console)
        self.click('[data-play-start]')
        frame = self.embedded_frame('[data-play-frame] iframe')
        plan = self.native_plan(frame, boundary, 'case-embed')
        self.case_viewport_fit(frame)
        input_boundary = len(self.result['events'])
        state = plan.current()
        require('start' in state['ui']['controls'], 'Case embed did not expose native start')
        self.shell_language(frame, state['language'], 'case intro')
        plan.tap('start')
        plan.wait(lambda s: 'start' not in s['ui']['controls'], 'case embed native start', state['sample_id'])
        before = plan.tap('language')
        switched = plan.wait(lambda s: s['language'] != before['language'], 'case embed native language', before['sample_id'])
        self.shell_language(frame, switched['language'], 'case switched native language')
        self.case_viewport_fit(frame)
        require(not any(event['type'] == 'mouse.wheel' for event in self.result['events'][input_boundary:]),
                'Viewport-fit case input unexpectedly required an outside scrolling escape')
        self.shot('case-native', plan.current())
        boundary = len(self.console)
        self.click('#dawnkeep-web-fullscreen', frame)
        fullscreen = self.line('DAWNKEEP_WEB_FULLSCREEN', boundary, 15)
        require(fullscreen.get('active') is True and fullscreen.get('trusted') is True,
                'Case native fullscreen did not engage through a real control')
        self.shell_language(frame, plan.current()['language'], 'case fullscreen')
        self.click('#dawnkeep-web-fullscreen', frame)
        self.wait(lambda: self.page.evaluate('!document.fullscreenElement'), 'Case native fullscreen did not exit', 15)
        self.case_viewport_fit(frame)
        self.result['checks'].append({'name': 'case reachable native fullscreen and exit', 'passed': True})
        self.click('[data-play-exit]')
        expect(self.page.locator('[data-play-frame] iframe')).to_have_count(0)
        self.layout('case after embed')
        self.result['checks'].append({'name': 'case embedded native start/language/exit', 'passed': True})

    def standalone_page(self):
        from playwright.sync_api import expect
        # A real required-asset outage exercises the pre-engine locale fallback.
        # No synthetic engine state, DOM labels or media state are assigned.
        outage = RequiredPayloadOutage()
        pattern = '**/' + PCK_NAME + '*'
        self.page.route(pattern, outage)
        boundary = len(self.console)
        try:
            response = self.page.goto(urljoin(self.base, PLAY_ROOT + 'index.html?lang=' + self.locale),
                                      wait_until='domcontentloaded')
            require(response and response.status == 200, 'Standalone shell did not load')
            self.line('DAWNKEEP_WEB_LOAD_ERROR', boundary)
            require(outage.attempts > 0 and not receipts('\n'.join(self.console[boundary:])),
                    'Pre-engine language fallback did not precede native state')
            self.shell_language(self.page.main_frame, self.locale, 'pre-engine page locale fallback')
            expect(self.page.locator('#dawnkeep-web-panel [role="status"]')).to_have_text(
                '载入失败。请重试。' if self.locale == 'zh' else 'Loading failed. Please retry.')
            self.shot('standalone-localized-load-error')
        finally:
            self.page.unroute(pattern, outage)
        boundary = len(self.console)
        self.click('#dawnkeep-web-retry')
        plan = self.native_plan(self.page.main_frame, boundary, 'standalone')
        state = plan.current()
        require(state['language'] == 'zh' and 'start' in state['ui']['controls'], 'Frozen native intro default changed')
        self.shell_language(self.page.main_frame, state['language'], 'standalone actual retry native intro')
        self.shot('standalone-intro', state)
        boundary = len(self.console)
        self.click('#dawnkeep-web-fullscreen')
        event = self.line('DAWNKEEP_WEB_FULLSCREEN', boundary, 15)
        require(event.get('active') is True and event.get('trusted') is True, 'Native shell fullscreen did not engage')
        self.click('#dawnkeep-web-fullscreen')
        self.wait(lambda: self.page.evaluate('!document.fullscreenElement'), 'Standalone fullscreen did not exit', 15)
        boundary = len(self.console)
        self.click('#dawnkeep-web-quit')
        event = self.line('DAWNKEEP_WEB_EXIT', boundary, 30)
        require(event.get('ok') is True and event.get('code') == 0, 'Actual Engine.requestQuit/onExit failed')
        self.shell_language(self.page.main_frame, state['language'], 'standalone closed')
        expect(self.page.locator('#dawnkeep-web-panel [role="status"]')).to_have_text('游戏已退出')
        self.shot('standalone-engine-exited')
        boundary = len(self.console)
        self.click('#dawnkeep-web-restart')
        state = self.native_plan(self.page.main_frame, boundary, 'standalone-reopen').current()
        require('start' in state['ui']['controls'], 'Standalone reopen did not create native intro')
        self.shell_language(self.page.main_frame, state['language'], 'standalone reopened')
        self.result['checks'].append({'name': 'standalone fullscreen/official engine quit/reopen', 'passed': True})
        self.healthy()

    def run(self):
        self.progress('viewport', 'started')
        stage = 'setup'
        try:
            # Exercise media before the more expensive engine lifecycle route.
            # All four stages remain mandatory for every locale/viewport.
            for stage, action in (('gallery', self.gallery), ('case-media-and-embed', self.case_page),
                                  ('game-lifecycle', self.game_page), ('standalone', self.standalone_page)):
                self.progress(stage, 'started')
                action()
                self.progress(stage, 'passed')
            self.healthy()
            self.result['passed'] = True
            self.progress('viewport', 'passed')
        except Exception as error:
            self.result['blocker'] = str(error)
            self.progress(stage, 'failed', blocker=str(error))
            try:
                self.shot('failure')
            except Exception:
                pass
        finally:
            self.context.close()
            (self.output / 'console.log').write_text('\n'.join(self.console) + '\n')
            write_json(self.output / 'network.json', {'requests': self.requests, 'responses': self.responses,
                                                      'failures': self.network_failures, 'page_errors': self.errors})
            write_json(self.output / 'result.json', self.result)
        return self.result


def main():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--site', type=Path, help='Already-built isolated _site directory')
    mode.add_argument('--base-url', type=deployed_base, help='Official deployed Pages URL only')
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-head', default=os.environ.get('EXPECTED_HEAD_SHA'))
    parser.add_argument('--locale', choices=('all', 'en', 'zh'), default='all')
    parser.add_argument('--viewport', choices=('all', 'desktop', 'portrait'), default='all')
    args = parser.parse_args()
    pairs = selected_pairs(args.locale, args.viewport)
    out = isolated_output(args.output, args.site)
    report = {'schema': 1, 'passed': False, 'expected_head_sha': args.expected_head,
              'mode': 'deployed' if args.base_url else 'isolated-build',
              'selection': {'locale': args.locale, 'viewport': args.viewport,
                            'required_pairs': [{'locale': locale, 'viewport': 'portrait' if mobile else 'desktop'}
                                               for locale, mobile in pairs],
                            'complete_four_pair_matrix': len(pairs) == 4},
              'viewports': [], 'browser_launch': {'args': BROWSER_ARGS, 'chromium_sandbox': True,
                                                'ignore_default_args': BROWSER_IGNORED_DEFAULT_ARGS},
              'scope': 'Promotion, public media and bounded shell/embedded integration of frozen verified runtime',
              'limitations': ['No new eight-wave campaign or gameplay-balance claim.',
                             'Portrait is Chromium emulated touch, not a physical phone.',
                             'Video decode and presented-frame checks do not establish soundtrack listening or subjective quality.',
                             'Expected source SHA is bound to checked public bytes; global deployment identity needs the Pages run receipt.',
                             'This result covers only selection.required_pairs; publication needs all four workflow matrix jobs.']}
    server = None
    try:
        report['source'] = source_receipt(args.repo, args.expected_head)
        selected = installed_chrome()
        report['browser_launch'].update(selected)
        inventory = artifact_inventory(args.repo)
        if args.site:
            require(args.site.is_dir() and (args.site / 'index.html').is_file(), 'Isolated built site is missing')
            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(RangeHTTPHandler, directory=str(args.site.resolve())))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{server.server_port}/'
            report['limitations'].append('Isolated-build acceptance does not prove deployed-site behavior.')
        else:
            base = args.base_url
        report['base_url'] = base
        with sync_playwright() as pw:
            request = pw.request.new_context()
            try:
                progress_event('public-artifacts', 'started', count=len(inventory['assets']))
                fetch_artifacts(request, base, inventory, out, report)
                progress_event('public-artifacts', 'passed', count=len(inventory['assets']))
            finally:
                request.dispose()
            browser = pw.chromium.launch(headless=True, executable_path=selected['executable_path'],
                                         args=BROWSER_ARGS, chromium_sandbox=True,
                                         ignore_default_args=BROWSER_IGNORED_DEFAULT_ARGS)
            report['browser_version'] = browser.version
            try:
                for locale, mobile in pairs:
                    name = locale + ('-portrait' if mobile else '-desktop')
                    result = Session(browser, base, out / name, locale, mobile, inventory).run()
                    report['viewports'].append(result)
                    write_json(out / 'public-page.json', report)
            finally:
                browser.close()
        report['passed'] = len(report['viewports']) == len(pairs) and all(r['passed'] for r in report['viewports'])
        require(report['passed'], 'At least one public locale/viewport acceptance failed')
    except Exception as error:
        report['blocker'] = str(error)
        raise
    finally:
        if server:
            server.shutdown()
            server.server_close()
        write_json(out / 'public-page.json', report)


if __name__ == '__main__':
    main()
