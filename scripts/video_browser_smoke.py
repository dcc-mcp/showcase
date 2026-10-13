#!/usr/bin/env python3
"""Decode every published video on Chromium; verify hover and native controls.

Uses only locally served public outputs. Mobile coverage is touch-viewport
emulation, not a physical-device or subjective audio acceptance claim.
"""
from __future__ import annotations

import argparse
import html
import time
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from localization_browser_smoke import MountHandler



# Observers only: no media methods or browser policies are replaced.
MEDIA_DIAGNOSTICS = """(() => {
  window.__mediaDiagnosticEvents = [];
  for (const event of ['loadstart', 'emptied', 'loadedmetadata', 'loadeddata', 'suspend', 'progress', 'abort', 'error', 'play', 'playing', 'pause', 'waiting', 'pointerenter', 'pointerdown']) {
    document.addEventListener(event, e => {
      const v = e.target;
      if (!(v instanceof HTMLVideoElement) || window.__mediaDiagnosticEvents.length >= 500) return;
      window.__mediaDiagnosticEvents.push({event, time: performance.now(), src: v.getAttribute('src'), currentSrc: v.currentSrc,
        paused: v.paused, readyState: v.readyState, networkState: v.networkState, trusted: e.isTrusted,
        state: v.closest('.detail-video')?.dataset.videoState || v.closest('.case-card')?.dataset.previewState});
    }, true);
  }
})();"""


def media_snapshot(page):
    return page.evaluate(r"""() => ({url: location.href, time: performance.now(), hidden: document.hidden,
      userActivation: {active: navigator.userActivation?.isActive, sticky: navigator.userActivation?.hasBeenActive},
      videos: Array.from(document.querySelectorAll('video')).map(v => ({
        html: v.outerHTML, src: v.getAttribute('src'), currentSrc: v.currentSrc, preload: v.preload,
        paused: v.paused, muted: v.muted, autoplay: v.autoplay, controls: v.controls,
        readyState: v.readyState, networkState: v.networkState, currentTime: v.currentTime,
        videoWidth: v.videoWidth, videoHeight: v.videoHeight,
        state: v.closest('.detail-video')?.dataset.videoState || v.closest('.case-card')?.dataset.previewState,
        hovered: v.matches(':hover'), hostHovered: v.parentElement.matches(':hover'),
        rect: v.getBoundingClientRect().toJSON()})),
      resources: performance.getEntriesByType('resource').filter(r => /\.(mp4|webm)(\?|$)/.test(r.name)).map(r => r.toJSON()),
      events: window.__mediaDiagnosticEvents || []})""")


def request_diagnostic(request):
    try:
        frame_url = request.frame.url
    except Exception:
        frame_url = None
    return {'url': request.url, 'frame_url': frame_url, 'referer': request.headers.get('referer'),
            'range': request.headers.get('range'), 'resource_type': request.resource_type,
            'observed_at': time.monotonic()}


def diagnose_unexpected_media(browser, page, output, report, request_details, mobile, label):
    """Keep the original failure and use isolated local probes to explain it."""
    diagnostic = {'label': label, 'original_requests': list(request_details), 'original_page': media_snapshot(page), 'probes': []}
    image = label + '-unexpected-media.png'
    page.screenshot(path=str(output / image))
    report['screenshots'].append(image)
    url = page.url
    source = page.locator('video source').first.get_attribute('src') if page.locator('video source').count() else None
    poster = page.locator('video').first.evaluate('(v)=>v.poster') if page.locator('video').count() else ''
    options = {'viewport': {'width': 390 if mobile else 1486, 'height': 844 if mobile else 1059},
               'is_mobile': mobile, 'has_touch': mobile, 'service_workers': 'block'}
    # Fresh context eliminates both prior gallery traffic and sticky activation.
    isolated = browser.new_context(**options)
    isolated.add_init_script(MEDIA_DIAGNOSTICS)
    records = []
    isolated.on('request', lambda request: records.append(request_diagnostic(request)))
    probe = isolated.new_page()
    try:
        probe.goto(url, wait_until='networkidle')
        diagnostic['probes'].append({'label': 'fresh-context-same-page', 'requests': list(records), 'page': media_snapshot(probe)})
        if source:
            from urllib.parse import urljoin
            source = urljoin(url, source)
            probe.goto('about:blank')
            records.clear()
            # Local public media only. This fixture diagnoses individual DOM
            # operations; its results are never reported as product acceptance.
            probe.set_content('<video controls playsinline preload="none" poster="' + html.escape(poster, quote=True) + '"><source src="' + html.escape(source, quote=True) + '"></video>')
            operations = [('static-preload-none', None),
                          ('pause-muted-controls', '(v)=>{v.pause();v.muted=v.defaultMuted=true;v.autoplay=false;v.preload="none";v.playsInline=true;v.controls=true;v.loop=false}'),
                          ('current-time-zero', '(v)=>{v.currentTime=0}'),
                          ('remove-video-src', '(v)=>v.removeAttribute("src")'),
                          ('explicit-load', '(v)=>v.load()')]
            for name, action in operations:
                if action:
                    probe.locator('video').evaluate(action)
                probe.wait_for_timeout(300)
                diagnostic['probes'].append({'label': name, 'requests': list(records), 'page': media_snapshot(probe)})
                records.clear()
    except Exception as error:
        diagnostic['probe_error'] = str(error)
    finally:
        isolated.close()
    name = label + '-media-diagnostic.json'
    (output / name).write_text(json.dumps(diagnostic, indent=2) + '\n', encoding='utf-8')
    report.setdefault('diagnostics', []).append(name)
    print('MEDIA DIAGNOSTIC ' + json.dumps(diagnostic), flush=True)


def run(site: Path, output: Path):
    from playwright.sync_api import sync_playwright, expect
    cases = json.loads(Path('collection.json').read_text(encoding='utf-8'))['cases']
    films = {case['slug']: [item for item in case['results'] if Path(item['src']).suffix.lower() in {'.mp4', '.webm'}]
             for case in cases}
    films = {slug: items for slug, items in films.items() if items}
    output.mkdir(parents=True, exist_ok=True)
    report = {'passed': False, 'checks': [], 'screenshots': [], 'gallery_videos': len(films),
              'detail_videos': sum(map(len, films.values())),
              'scope': 'Real decoded local media; Chromium desktop and touch-viewport emulation. No subjective listening.'}
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(MountHandler, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/showcase/'
    errors = []
    page = None
    request_details = []
    stage = "launch"
    def check(text):
        report['checks'].append(text)
        print('PASS ' + text, flush=True)
    def capture(page, filename):
        page.screenshot(path=str(output / filename))
        report['screenshots'].append(filename)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                report['browser'] = browser.version
                for mobile in [False, True]:
                    kind = 'mobile' if mobile else 'desktop'
                    context = browser.new_context(viewport={'width': 390 if mobile else 1486, 'height': 844 if mobile else 1059},
                                                  is_mobile=mobile, has_touch=mobile, service_workers='block')
                    requests = []
                    request_details = []
                    context.add_init_script(MEDIA_DIAGNOSTICS)
                    context.on('request', lambda request: request_details.append(request_diagnostic(request)))
                    def guard(route):
                        if route.request.url.startswith(base):
                            requests.append(route.request.url)
                            route.continue_()
                        else:
                            route.abort()
                    context.route('**/*', guard)
                    page = context.new_page()
                    page.set_default_timeout(20000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    def media_requests():
                        return [url for url in requests if url.split('?')[0].endswith(('.mp4', '.webm'))]
                    def assert_released(video, before, label):
                        # Observe beyond the stop event: a decoder reset must not
                        # silently reopen a retained SOURCE in the next event loop.
                        page.wait_for_timeout(500)
                        unexpected = media_requests()[before:]
                        if unexpected:
                            diagnose_unexpected_media(browser, page, output, report, request_details, mobile, label)
                        assert not unexpected, 'Media refetched after stop: ' + repr(unexpected)
                        assert video.evaluate('(v)=>v.paused && v.muted && !v.hasAttribute("src") && !v.querySelector("source[src]")')
                    for prefix, locale in [('', 'en'), ('zh/', 'zh')]:
                        stage = f'{locale}/{kind}: gallery initial'
                        requests.clear()
                        request_details.clear()
                        page.mouse.move(1, 1)
                        page.goto(base + prefix, wait_until='networkidle')
                        expect(page.locator('.case-card[data-preview-src]')).to_have_count(len(films))
                        assert not any(url.split('?')[0].endswith(('.mp4', '.webm', '.wasm', '.pck')) for url in requests)
                        for slug in films:
                            stage = f'{locale}/{kind}: gallery {slug}'
                            card = page.locator(f'.case-card[data-case="{slug}"]')
                            card.scroll_into_view_if_needed()
                            video = card.locator('video')
                            if mobile:
                                card.locator('.preview-toggle').tap()
                            else:
                                card.locator('.card-title').hover()
                            expect(card).to_have_attribute('data-preview-state', 'playing')
                            page.wait_for_function("(v)=>v.currentTime>0.05", arg=video.element_handle())
                            assert video.evaluate('(v)=>v.muted && v.videoWidth>0 && !v.paused')
                            if slug == 'sonic-loom':
                                capture(page, f'{locale}-{kind}-gallery-hover.png')
                            if mobile:
                                card.locator('.preview-toggle').tap()
                            else:
                                page.mouse.move(1, 1)
                            expect(card).to_have_attribute('data-preview-state', 'idle')
                            assert video.evaluate('(v)=>v.paused && v.muted && !v.hasAttribute("src")')
                        assert not any(url.split('?')[0].endswith(('.wasm', '.pck')) for url in requests)
                        check(f'{locale}/{kind}: all {len(films)} real video cards decode muted, stop and release; no engine request')
                        for slug, items in films.items():
                            stage = f'{locale}/{kind}: detail initial {slug}'
                            requests.clear()
                            request_details.clear()
                            page.mouse.move(1, 1)
                            page.goto(base + prefix + f'cases/{slug}/', wait_until='networkidle')
                            expect(page.locator('.detail-video')).to_have_count(len(items))
                            unexpected = [url for url in requests if url.split('?')[0].endswith(('.mp4', '.webm'))]
                            if unexpected:
                                diagnose_unexpected_media(browser, page, output, report, request_details, mobile, f'{locale}-{kind}-{slug}')
                            assert not unexpected, 'Media requested before detail intent: ' + repr(unexpected)
                            for index, item in enumerate(items):
                                stage = f'{locale}/{kind}: detail hover {slug}/{index}'
                                host = page.locator('.detail-video').nth(index)
                                video = host.locator('video')
                                host.scroll_into_view_if_needed()
                                if not mobile:
                                    video.hover()
                                    expect(host).to_have_attribute('data-video-state', 'preview')
                                    assert video.evaluate('(v)=>v.muted && v.videoWidth>0 && v.loop && v.controls')
                                    before_stop = len(media_requests())
                                    page.mouse.move(1, 1)
                                    expect(host).to_have_attribute('data-video-state', 'idle')
                                    assert_released(video, before_stop, f'{locale}-{kind}-{slug}-{index}-hover-stop')
                                stage = f'{locale}/{kind}: detail watch {slug}/{index}'
                                # The visible explicit control works for touch and
                                # keyboard without depending on autoplay permission.
                                if mobile:
                                    host.locator('.video-watch').tap()
                                else:
                                    host.locator('.video-watch').focus()
                                    page.keyboard.press('Enter')
                                expect(host).to_have_attribute('data-video-state', 'watching')
                                assert video.evaluate('(v)=>v.videoWidth>0 && v.controls && !v.loop && !v.paused')
                                audio = video.get_attribute('data-preview-audio')
                                assert video.evaluate('(v)=>v.muted') == (audio == 'false')
                                page.mouse.move(1, 1)
                                expect(host).to_have_attribute('data-video-state', 'watching')
                                # Native pause/seek/play remains owned by the viewer;
                                # no hover handler is allowed to restart or clear it.
                                video.evaluate('(v)=>{v.pause();v.currentTime=Math.min(1,v.duration/2)}')
                                expect(host).to_have_attribute('data-video-state', 'watching')
                                await_time = video.evaluate('(v)=>v.currentTime')
                                assert await_time > 0
                                if slug == 'sonic-loom':
                                    capture(page, f'{locale}-{kind}-detail-controls.png')
                                before_stop = len(media_requests())
                                host.locator('.video-watch').click()
                                expect(host).to_have_attribute('data-video-state', 'idle')
                                assert_released(video, before_stop, f'{locale}-{kind}-{slug}-{index}-watch-stop')
                                stage = f'{locale}/{kind}: released keyboard {slug}/{index}'
                                # Exercise the focusable released-player keyboard
                                # path, without calling HTMLMediaElement.play here.
                                video.focus()
                                page.keyboard.press('Space')
                                expect(host).to_have_attribute('data-video-state', 'watching')
                                assert video.evaluate('(v)=>!v.paused && v.controls')
                                before_stop = len(media_requests())
                                host.locator('.video-watch').click()
                                expect(host).to_have_attribute('data-video-state', 'idle')
                                assert_released(video, before_stop, f'{locale}-{kind}-{slug}-{index}-native-stop')
                                if not mobile:
                                    stage = f'{locale}/{kind}: released native pointer {slug}/{index}'
                                    # One click on Chromium's native lower-left play
                                    # button must be enough after full source release.
                                    # Moving within this host does not re-enter hover.
                                    box = video.bounding_box()
                                    assert box is not None
                                    video.click(position={'x': 30, 'y': box['height'] - 25})
                                    expect(host).to_have_attribute('data-video-state', 'watching')
                                    assert video.evaluate('(v)=>!v.paused && v.controls')
                                    before_stop = len(media_requests())
                                    host.locator('.video-watch').click()
                                    expect(host).to_have_attribute('data-video-state', 'idle')
                                    assert_released(video, before_stop, f'{locale}-{kind}-{slug}-{index}-pointer-stop')
                                pointer_scope = ' and native pointer' if not mobile else ''
                                check(f'{locale}/{kind}: {item["src"]} decoded; hover/manual/released keyboard{pointer_scope}; cleanup without refetch')
                            assert not any(url.split('?')[0].endswith(('.wasm', '.pck')) for url in requests)
                            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    assert not errors, errors
                    context.close()
                # Policy gates keep the native/manual alternative working.
                for policy in ['reduced-motion', 'save-data']:
                    stage = 'detail policy: ' + policy
                    request_details = []
                    context = browser.new_context(reduced_motion='reduce' if policy == 'reduced-motion' else 'no-preference')
                    context.add_init_script(MEDIA_DIAGNOSTICS)
                    context.on('request', lambda request: request_details.append(request_diagnostic(request)))
                    if policy == 'save-data':
                        context.add_init_script('Object.defineProperty(navigator,"connection",{value:{saveData:true,addEventListener(){},removeEventListener(){}}})')
                    page = context.new_page()
                    page.goto(base + 'cases/sonic-loom/', wait_until='networkidle')
                    host = page.locator('.detail-video').first
                    host.locator('video').hover()
                    expect(host).to_have_attribute('data-video-state', 'idle')
                    assert host.locator('video').get_attribute('src') is None
                    host.locator('.video-watch').click()
                    expect(host).to_have_attribute('data-video-state', 'watching')
                    page.keyboard.press('Escape')
                    expect(host).to_have_attribute('data-video-state', 'idle')
                    check(policy + ': detail hover suppressed; explicit watching and Escape work')
                    assert not errors, errors
                    context.close()
                browser.close()
            except Exception:
                diagnostic = {'stage': stage, 'requests': list(request_details)}
                if page is not None and not page.is_closed():
                    try:
                        diagnostic['page'] = media_snapshot(page)
                    except Exception as error:
                        diagnostic['snapshot_error'] = str(error)
                    try:
                        capture(page, 'failure-state.png')
                    except Exception as error:
                        diagnostic['screenshot_error'] = str(error)
                (output / 'failure-state.json').write_text(json.dumps(diagnostic, indent=2) + '\n', encoding='utf-8')
                report['failure_diagnostic'] = 'failure-state.json'
                print('VIDEO FAILURE ' + json.dumps(diagnostic), flush=True)
                raise
        assert not errors, errors
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        report['page_errors'] = errors
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        server.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.site, args.output)
