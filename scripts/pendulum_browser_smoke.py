#!/usr/bin/env python3
"""Observe the entire Brass Pendulum film in the standard CI Chromium.

The actual page and its real controls drive playback. The observer never seeks,
changes speed, replaces events or patches media methods. A same-delivery reference
atlas tests display identity, not native-render fidelity or subjective art quality.
"""
from __future__ import annotations

import argparse
import base64
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import threading
import zlib

from browser_preview import safe_error_text
from localization_browser_smoke import MountHandler

ENTRY = 'docs/showcase/brass-pendulum-denoise/'
PNG_COLOR_CHUNKS = {b'cICP', b'gAMA', b'cHRM', b'sRGB', b'iCCP'}


def native_fullscreen_ax_node(nodes: list, video_dom: dict, mode: str = 'enter') -> dict:
    """Select one visible native button inside this video's user-agent shadow."""
    assert mode in ('enter', 'exit'), 'Invalid native fullscreen action'
    assert video_dom.get('localName') == 'video', 'Fullscreen target is not the actual video'
    attributes = video_dom.get('attributes', [])
    attrs = dict(zip(attributes[::2], attributes[1::2]))
    assert attrs.get('src', '').split('?')[0].endswith('/pendulum-oidn.mp4'), 'Wrong fullscreen video source'
    native_ids = set()

    def collect(node):
        native_ids.add(node.get('backendNodeId'))
        for child in node.get('children', []) + node.get('shadowRoots', []):
            collect(child)

    for shadow in video_dom.get('shadowRoots', []):
        if shadow.get('shadowRootType') == 'user-agent':
            collect(shadow)
    native_ids.discard(None)
    matches = []
    for node in nodes:
        name = node.get('name', {}).get('value', '').strip()
        matches_action = (re.fullmatch(r'(?:enter )?full[ -]?screen', name, re.I) or name in ('进入全屏', '全屏')) \
            if mode == 'enter' else name.lower() == 'exit full screen' or name == '退出全屏'
        if (not node.get('ignored', True) and node.get('role', {}).get('value') == 'button'
                and matches_action and node.get('backendDOMNodeId') in native_ids):
            assert not any(p.get('name') == 'disabled' and p.get('value', {}).get('value')
                for p in node.get('properties', [])), 'Native fullscreen button is disabled'
            matches.append(node)
    assert len(matches) == 1, 'Native fullscreen button is missing or ambiguous within target video'
    return matches[0]


def native_control_center(quad: list, box: dict, viewport: dict) -> dict:
    assert len(quad) == 8 and all(isinstance(n, (int, float)) and math.isfinite(n) for n in quad), 'Invalid native control bounds'
    left, right = min(quad[::2]), max(quad[::2])
    top, bottom = min(quad[1::2]), max(quad[1::2])
    assert right > left and bottom > top, 'Native control has no visible size'
    assert (box['x'] - 1 <= left < right <= box['x'] + box['width'] + 1 and
            box['y'] - 1 <= top < bottom <= box['y'] + box['height'] + 1), 'Native control is outside target video'
    assert 0 <= left < right <= viewport['width'] and 0 <= top < bottom <= viewport['height'], 'Native control is outside viewport'
    return {'x': (left + right) / 2, 'y': (top + bottom) / 2}


def locate_native_fullscreen(page, context, video, index: int, mode: str = 'enter') -> dict:
    # CDP only observes the real browser's UA accessibility/DOM geometry.
    # The action below is a trusted touchscreen tap, never a DOM/script click.
    session = context.new_cdp_session(page)
    try:
        root = session.send('DOM.getDocument', {'depth': 0})['root']['nodeId']
        videos = session.send('DOM.querySelectorAll', {'nodeId': root, 'selector': 'video'})['nodeIds']
        assert index < len(videos), 'Actual video disappeared before fullscreen'
        dom = session.send('DOM.describeNode', {'nodeId': videos[index], 'depth': -1, 'pierce': True})['node']
        node = native_fullscreen_ax_node(session.send('Accessibility.getFullAXTree')['nodes'], dom, mode)
        quad = session.send('DOM.getBoxModel', {'backendNodeId': node['backendDOMNodeId']})['model']['border']
        point = native_control_center(quad, video.bounding_box(), page.viewport_size)
        return {'action': mode, 'accessible_name': node['name']['value'], 'role': 'button', 'within_target_native_controls': True, **point}
    finally:
        session.detach()


def ended_media_state(video) -> dict:
    return video.evaluate('''v => {
        const r = window.__pendulumPlayback.receipt, q = v.getVideoPlaybackQuality();
        return {ended:v.ended, paused:v.paused, controls:v.controls, muted:v.muted, loop:v.loop,
            currentTime:v.currentTime, duration:v.duration, rate:v.playbackRate,
            sourceName:v.currentSrc.split('/').pop(), objectFit:getComputedStyle(v).objectFit,
            fullscreen:document.fullscreenElement === v,
            playEvents:r.playEvents, seeks:r.seeks, endedEvents:r.ended,
            quality:{totalVideoFrames:q.totalVideoFrames, droppedVideoFrames:q.droppedVideoFrames,
                corruptedVideoFrames:q.corruptedVideoFrames}};
    }''')


def verify_ended_ui_transition(before: dict, after: dict, fullscreen: bool):
    for state in (before, after):
        assert state['ended'] and state['paused'] and state['controls'] and state['muted'] and not state['loop'], 'Native view changed ended media or controls'
        assert state['rate'] == 1 and state['playEvents'] == state['endedEvents'] == 1 and state['seeks'] == 0, 'Native view replayed, sought or retimed media'
        assert state['quality']['totalVideoFrames'] == 144 and state['quality']['corruptedVideoFrames'] == 0, 'Native view changed complete decode'
        assert state['objectFit'] == 'contain' and state['sourceName'] == 'pendulum-oidn.mp4', 'Native view changed picture presentation'
    assert after['fullscreen'] is fullscreen, 'Native fullscreen transition did not complete'
    assert {k: v for k, v in before.items() if k != 'fullscreen'} == {k: v for k, v in after.items() if k != 'fullscreen'}, 'Native view changed end-frame time or decode state'


def inspect_touch_fullscreen(page, context, video, index: int, output: Path, image: str, observation: dict):
    """Use the actual native enter/exit buttons without changing the ended media."""
    before = ended_media_state(video)
    verify_ended_ui_transition(before, before, False)
    observation['before_entry'] = before
    control = locate_native_fullscreen(page, context, video, index)
    observation['native_button'] = control
    page.touchscreen.tap(control['x'], control['y'])
    page.wait_for_function('(index) => document.fullscreenElement === document.querySelectorAll("video")[index]',
                           arg=index, timeout=5000)
    entered = ended_media_state(video)
    observation['after_entry'] = entered
    verify_ended_ui_transition(before, entered, True)
    screenshot = video.screenshot(path=str(output / image))
    observation['screenshot'] = image
    observation['comparison'] = page.evaluate('(url) => window.__pendulumPlayback.compareDisplayedEnd(url)',
        'data:image/png;base64,' + base64.b64encode(screenshot).decode())
    # Resolve the now-changed native exit label and geometry again. Touch
    # emulation does not necessarily exit media fullscreen on an Escape key.
    exit_control = locate_native_fullscreen(page, context, video, index, 'exit')
    observation['native_exit_button'] = exit_control
    page.touchscreen.tap(exit_control['x'], exit_control['y'])
    page.wait_for_function('document.fullscreenElement === null', timeout=5000)
    exited = ended_media_state(video)
    observation['after_exit'] = exited
    verify_ended_ui_transition(before, exited, False)
    observation['inspected'] = True


def validate_unprofiled_png(data: bytes):
    """References are decoded RGB samples, with no extra image color transform."""
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'Invalid reference PNG signature'
    offset, kinds = 8, []
    while offset < len(data):
        assert offset + 12 <= len(data), 'Truncated reference PNG chunk'
        size = int.from_bytes(data[offset:offset + 4], 'big')
        end = offset + 12 + size
        assert end <= len(data), 'Truncated reference PNG payload'
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:end - 4]
        assert zlib.crc32(kind + payload) & 0xffffffff == int.from_bytes(data[end - 4:end], 'big'), 'Reference PNG CRC differs'
        assert kind not in PNG_COLOR_CHUNKS, 'Reference PNG must contain unprofiled RGB samples; unexpected ' + kind.decode('ascii')
        kinds.append(kind)
        if kind == b'IEND':
            assert size == 0 and end == len(data), 'Invalid reference PNG end'
        offset = end
    assert kinds and kinds[0] == b'IHDR' and b'IDAT' in kinds and kinds[-1] == b'IEND', 'Incomplete reference PNG'


def tracked_bytes_receipt(repo: Path) -> dict:
    """Bind all tracked bytes to HEAD without Git clean/smudge filters.

    Old media blobs can be ordinary binary Git objects despite their LFS
    attributes. A clean filter then reports them dirty even when checkout bytes
    match HEAD. Do not whitelist those paths or trust a filtered status result.
    """
    repo = repo.resolve()

    def git(*args):
        return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=repo)

    status = subprocess.run(['git', '--no-optional-locks', 'status', '--porcelain',
        '--untracked-files=no'], cwd=repo, capture_output=True, check=True)
    head = git('rev-parse', 'HEAD').decode().strip()
    algorithm = git('rev-parse', '--show-object-format').decode().strip()
    assert algorithm in ('sha1', 'sha256'), 'Unsupported Git object format'
    expected = {}
    for entry in git('ls-tree', '-rz', '--full-tree', 'HEAD').split(b'\0'):
        if entry:
            metadata, path = entry.split(b'\t', 1)
            mode, kind, digest = metadata.split()
            expected[path] = (mode, kind, digest)
    expected_index = {path: [(mode, digest, b'0')]
        for path, (mode, _kind, digest) in expected.items()}

    def index_entries():
        records = {}
        for entry in git('ls-files', '--stage', '-z').split(b'\0'):
            if entry:
                metadata, path = entry.split(b'\t', 1)
                records.setdefault(path, []).append(tuple(metadata.split()))
        return records

    index = index_entries()
    changes = []
    for path in sorted(set(index) | set(expected_index)):
        if index.get(path) != expected_index.get(path):
            changes.append({'path': os.fsdecode(path), 'reason': 'index differs from HEAD'})
    checked = 0
    for name, (mode, kind, expected_digest) in expected.items():
        path = repo / os.fsdecode(name)
        reason = None
        try:
            # Reject parent-directory symlinks rather than read outside checkout.
            if any(parent.is_symlink() for parent in path.parents if parent != repo and repo in parent.parents):
                raise ValueError('tracked parent directory is a symlink')
            info = path.lstat()
            if kind != b'blob':
                raise ValueError('unsupported non-blob tracked entry')
            if mode == b'120000':
                if not stat.S_ISLNK(info.st_mode):
                    raise ValueError('tracked symlink type differs')
                data = os.fsencode(os.readlink(path))
                digest = hashlib.new(algorithm, b'blob ' + str(len(data)).encode() + b'\0' + data)
            else:
                if mode not in (b'100644', b'100755') or not stat.S_ISREG(info.st_mode):
                    raise ValueError('tracked regular-file type differs')
                if bool(info.st_mode & 0o111) != (mode == b'100755'):
                    raise ValueError('tracked executable mode differs')
                digest = hashlib.new(algorithm, b'blob ' + str(info.st_size).encode() + b'\0')
                with path.open('rb') as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(chunk)
            if digest.hexdigest().encode() != expected_digest:
                raise ValueError('raw Git blob hash differs from HEAD')
            checked += 1
        except (OSError, ValueError) as error:
            reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        if reason:
            changes.append({'path': os.fsdecode(name), 'reason': reason})
    if git('rev-parse', 'HEAD').decode().strip() != head or index_entries() != index:
        changes.append({'path': '', 'reason': 'HEAD or index changed during verification'})
    return {'passed': not changes, 'head_sha': head, 'method': 'unfiltered Git blob hashes, file modes/types, and exact HEAD/index entries',
        'tracked_entries': len(expected), 'raw_hashes_matched': checked,
        'git_status_porcelain': status.stdout.decode('utf-8', errors='replace'),
        'git_status_stderr': status.stderr.decode('utf-8', errors='replace'), 'changes': changes}


def load_references(site: Path) -> dict:
    folder = site / ENTRY
    spec = json.loads((folder / 'playback-reference.json').read_text(encoding='utf-8'))
    assert spec['schema_version'] == 1
    assert spec['frame_count'] == 144 and spec['frame_rate'] == '24000/1001'
    assert spec['width'] == 960 and spec['height'] == 720
    assert spec['video']['path'] == 'pendulum-oidn.mp4'
    assert spec['atlas']['columns'] == 8 and spec['atlas']['rows'] == 18
    assert spec['atlas']['tile_width'] == 160 and spec['atlas']['tile_height'] == 120
    assert [item['frame'] for item in spec['keyframes']] == [1, 73, 144]
    assert spec['reference_basis'] == 'Independent decode of the exact final H.264 delivery; not a source-render quality reference.'
    for record in [spec['video'], spec['atlas'], *spec['keyframes']]:
        path = Path(record['path'])
        assert len(path.parts) == 1 and not path.is_absolute() and path.name not in ('.', '..'), 'Unsafe reference path'
        assert re.fullmatch('[0-9a-f]{64}', record['sha256']), 'Missing reference digest'
        data = (folder / path).read_bytes()
        assert len(data) == record['bytes'], 'Reference byte count differs'
        assert hashlib.sha256(data).hexdigest() == record['sha256'], 'Reference digest differs'
        if path.suffix.lower() == '.png':
            validate_unprofiled_png(data)
    return spec


def run(site: Path, output: Path, expected_head: str):
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    actual_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    report = {'passed': False, 'head_sha': actual_head, 'checks': [], 'screenshots': [], 'displayed_views': [],
        'scope': 'Exact candidate; Chromium English/Chinese desktop and touch-viewport emulation.',
        'limitations': ['Touch emulation is not a physical-device test.',
            'Touch playback remains inline; final displayed pixels are checked in native fullscreen after ended. Inline native-controls occlusion is separately retained, not claimed unobstructed.',
            'Same-delivery pixel matching does not certify source-render fidelity or subjective motion quality.',
            'No merge, deployment or final user artistic acceptance is implied.']}
    server = None
    base = ''
    page = None
    label = 'setup'
    try:
        assert expected_head and actual_head == expected_head, 'Exact candidate head mismatch'
        report['tracked_source'] = tracked_bytes_receipt(Path.cwd())
        assert report['tracked_source']['head_sha'] == expected_head, 'Tracked source head mismatch'
        assert report['tracked_source']['passed'], \
            'Tracked source bytes or index differ from exact HEAD: ' + str(report['tracked_source']['changes'])
        spec = load_references(site)
        report['reference'] = spec
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(MountHandler, directory=str(site)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}/showcase/'
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            report['browser'] = browser.version
            for locale, prefix in [('en', ''), ('zh', 'zh/')]:
                for layout, mobile in [('desktop', False), ('touch', True)]:
                    label = f'{locale}-{layout}'
                    context = browser.new_context(viewport={'width': 390 if mobile else 1440,
                        'height': 844 if mobile else 1000}, is_mobile=mobile, has_touch=mobile,
                        device_scale_factor=1, reduced_motion='reduce', service_workers='block')
                    errors, media_requests = [], []
                    context.route('**/*', lambda route: route.continue_()
                                  if route.request.url.startswith(base) else route.abort())
                    context.on('request', lambda request: media_requests.append(request.url)
                               if request.url.split('?')[0].endswith(('.mp4', '.webm')) else None)
                    page = context.new_page()
                    page.set_default_timeout(30000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(base + prefix + 'cases/brass-pendulum-denoise/', wait_until='domcontentloaded')
                    expect(page.locator('html')).to_have_attribute('lang', 'zh-CN' if locale == 'zh' else 'en')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    video = page.locator('video').filter(has=page.locator('source[src*="pendulum-oidn.mp4"]'))
                    expect(video).to_have_count(1)
                    index = video.evaluate('(v) => Array.from(document.querySelectorAll("video")).indexOf(v)')
                    video = page.locator('video').nth(index)  # Stable after stop removes live sources.
                    video.scroll_into_view_if_needed()
                    host = video.locator('..')
                    expect(video).to_have_js_property('paused', True)
                    expect(video).to_have_js_property('autoplay', False)
                    expect(video).to_have_attribute('data-preview-audio', 'false')
                    expect(host.locator('.video-audio-note')).to_have_text('无音轨' if locale == 'zh' else 'No audio track')
                    assert not media_requests, 'Media requested before explicit activation'
                    await_spec = json.loads(json.dumps(spec))
                    for record in [await_spec['atlas'], *await_spec['keyframes']]:
                        record['url'] = base + ENTRY + record['path']
                    page.add_script_tag(path=str(Path(__file__).with_name('pendulum_playback.js')))
                    video.evaluate('(video, spec) => PendulumPlayback.install(video, spec)', await_spec)
                    if mobile:
                        host.locator('.video-watch').tap()
                    else:
                        host.locator('.video-watch').focus()
                        page.keyboard.press('Enter')
                    page.mouse.move(1, 1)
                    try:
                        page.wait_for_function('window.__pendulumPlayback.receipt.done', timeout=30000)
                    except Exception:
                        # Retain actual observations before Playwright's context
                        # manager tears down the browser after an exception.
                        report['failure_receipt'] = page.evaluate('window.__pendulumPlayback.receipt')
                        page.screenshot(path=str(output / (label + '-failure.png')))
                        raise
                    observed = page.evaluate('window.__pendulumPlayback.receipt')
                    if observed['errors']:
                        report['failure_receipt'] = observed
                        raise AssertionError(observed['errors'])
                    expect(video).to_have_js_property('ended', True)
                    assert video.evaluate('(v) => v.playbackRate === 1 && !v.loop && v.muted')
                    image = label + '-last-displayed.png'
                    screenshot = video.screenshot(path=str(output / image))
                    report['screenshots'].append(image)
                    inline = page.evaluate('(url) => window.__pendulumPlayback.compareDisplayedEnd(url)',
                        'data:image/png;base64,' + base64.b64encode(screenshot).decode())
                    # The paused native touch controls remain opaque by design.
                    # Keep that actual inline screenshot and its error, even when
                    # inspecting the same ended picture through native fullscreen.
                    views = {'locale': locale, 'viewport': layout,
                        'inline': {'screenshot': image, 'comparison': inline,
                            'motion_region_pixel_match': inline['passed']}}
                    report['displayed_views'].append(views)
                    page.evaluate('''() => {
                        const r = window.__pendulumPlayback.receipt;
                        r.inlineDisplayedEnd = {...r.displayedEnd}; r.displayedEndMode = 'inline';
                    }''')
                    if mobile:
                        views['inline']['native_controls_retained'] = video.evaluate('(v) => v.controls')
                        views['fullscreen'] = {'inspected': False}
                        image = label + '-last-displayed-fullscreen.png'
                        inspect_touch_fullscreen(page, context, video, index, output, image, views['fullscreen'])
                        report['screenshots'].append(image)
                        page.evaluate('window.__pendulumPlayback.receipt.displayedEndMode = "native_fullscreen_after_natural_ended"')
                    evidence = page.evaluate('''() => ({receipt: window.__pendulumPlayback.receipt,
                        pictures: window.__pendulumPlayback.pictures,
                        verdict: PendulumPlayback.validate(window.__pendulumPlayback.receipt)})''')
                    for name, data_url in evidence.pop('pictures').items():
                        filename = label + '-' + name + '.png'
                        (output / filename).write_bytes(base64.b64decode(data_url.split(',', 1)[1]))
                        report['screenshots'].append(filename)
                    evidence.update(locale=locale, viewport=layout, page_errors=errors,
                        no_media_before_intent=True, touch_emulation=mobile, displayed_views=views)
                    report['checks'].append(evidence)
                    assert evidence['verdict']['passed'], evidence['verdict']['errors']
                    assert not errors, errors
                    # Preserve the stop/release gate after the added full-play run.
                    before_stop = len(media_requests)
                    host.locator('.video-watch').click()
                    expect(host).to_have_attribute('data-video-state', 'idle')
                    page.wait_for_timeout(500)
                    assert len(media_requests) == before_stop, 'Stop refetched media'
                    assert video.evaluate('(v) => v.paused && v.muted && !v.hasAttribute("src") && !v.querySelector("source[src]")')
                    evidence['stop_releases_without_refetch'] = True
                    context.close()
            browser.close()
        report['passed'] = len(report['checks']) == 4
    except Exception as error:
        report['failed_stage'] = label
        report['error'] = safe_error_text(error, base)
        if page and not page.is_closed():
            try:
                report['failure_receipt'] = page.evaluate('window.__pendulumPlayback?.receipt || null')
                page.screenshot(path=str(output / (label + '-failure.png')))
            except Exception:
                pass
        raise
    finally:
        if server:
            server.shutdown()
        (output / 'browser-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-head', required=True)
    args = parser.parse_args()
    run(args.site.resolve(), args.output.resolve(), args.expected_head)
