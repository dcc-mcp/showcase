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
from pathlib import Path
import re
import subprocess
import threading

from browser_preview import safe_error_text
from localization_browser_smoke import MountHandler

ENTRY = 'docs/showcase/brass-pendulum-denoise/'


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
    return spec


def run(site: Path, output: Path, expected_head: str):
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    actual_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    report = {'passed': False, 'head_sha': actual_head, 'checks': [], 'screenshots': [],
        'scope': 'Exact candidate; Chromium English/Chinese desktop and touch-viewport emulation.',
        'limitations': ['Touch emulation is not a physical-device test.',
            'Same-delivery pixel matching does not certify source-render fidelity or subjective motion quality.',
            'No merge, deployment or final user artistic acceptance is implied.']}
    server = None
    base = ''
    page = None
    label = 'setup'
    try:
        assert expected_head and actual_head == expected_head, 'Exact candidate head mismatch'
        assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], text=True).strip(), \
            'Tracked worktree changes cannot be reported as exact-head acceptance'
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
                    page.evaluate('(url) => window.__pendulumPlayback.compareDisplayedEnd(url)',
                        'data:image/png;base64,' + base64.b64encode(screenshot).decode())
                    evidence = page.evaluate('''() => ({receipt: window.__pendulumPlayback.receipt,
                        pictures: window.__pendulumPlayback.pictures,
                        verdict: PendulumPlayback.validate(window.__pendulumPlayback.receipt)})''')
                    for name, data_url in evidence.pop('pictures').items():
                        filename = label + '-' + name + '.png'
                        (output / filename).write_bytes(base64.b64decode(data_url.split(',', 1)[1]))
                        report['screenshots'].append(filename)
                    evidence.update(locale=locale, viewport=layout, page_errors=errors,
                        no_media_before_intent=True, touch_emulation=mobile)
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
