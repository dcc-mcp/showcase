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
import math
from pathlib import Path
import threading

from localization_browser_smoke import MountHandler


def _finite_time(value):
    assert isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0, \
        'Missing or invalid browser request/event time: ' + repr(value)
    return value


def media_request_started(event):
    """CDP wallTime is request initiation, not Python callback delivery time.

    Unlike completed ResourceTiming entries, this also observes aborted and
    unfinished requests. No media methods, network policy or response changes.
    """
    request = event['request']
    if not request['url'].split('?')[0].endswith(('.mp4', '.webm')):
        return None
    started_at_ms = _finite_time(event.get('wallTime')) * 1000
    assert started_at_ms > 0, 'Missing positive request epoch'
    return {'url': request['url'], 'request_id': event['requestId'],
            'range': next((v for k, v in request.get('headers', {}).items() if k.lower() == 'range'), None),
            'started_at_ms': started_at_ms}


def media_release_observation(requests, before, snapshot):
    """Keep pre-click activity separate, but reject any request at/after stop.

    The trusted intent is captured before the product stop handler. Its native
    emptied event confirms a paused, source-detached player. Requests between
    these boundaries are forbidden too: stop-triggered refetches cannot hide
    inside asynchronous media cleanup.
    """
    origin = _finite_time(snapshot['timeOrigin'])
    armed = _finite_time(before['armed_at_ms'])
    assert origin > 0 and armed >= origin, 'Invalid document/guard epoch'
    assert origin == before['timeOrigin'], 'Document changed during media release'
    events = snapshot['events'][before['event_count']:]
    intents = [e for e in events if e['event'] == before['event'] and e['target'] == before['target']
               and e['video_index'] == before['video_index'] and e['trusted'] is True]
    assert len(intents) == 1, 'Missing or ambiguous trusted stop intent: ' + repr(intents)
    intent = intents[0]
    intent_at = origin + _finite_time(intent['time'])
    assert intent_at >= armed, 'Stop intent predates its guard'
    assert intent['state'] in {'preview', 'watching'}, 'Stop intent did not target an active player'
    detached = [e for e in events[events.index(intent) + 1:] if e['event'] == 'emptied' and e['target'] == 'video'
                and e['video_index'] == before['video_index'] and e['trusted'] is True
                and e['src'] is None and e['live_sources'] == 0 and e['paused'] is True and e['state'] == 'idle']
    assert detached, 'Missing native source-detached release receipt'
    detached_at = origin + _finite_time(detached[0]['time'])
    observed_at = origin + _finite_time(snapshot['time'])
    assert armed <= intent_at <= detached_at <= observed_at, 'Invalid release event ordering'
    assert requests, 'No CDP media initiation evidence for decoded playback'
    phases = {'before_guard': [], 'guard_to_stop': [], 'during_release': [], 'after_release': []}
    for request in requests:
        started = _finite_time(request['started_at_ms'])
        assert started > 0, 'Missing positive request epoch'
        phase = ('before_guard' if started < armed else 'guard_to_stop' if started < intent_at
                 else 'during_release' if started < detached_at else 'after_release')
        phases[phase].append(request)
    return {'guard_armed_at_ms': armed, 'trusted_stop_at_ms': intent_at,
            'source_detached_at_ms': detached_at, 'observed_at_ms': observed_at,
            'intent': intent, 'detached': detached[0], 'phases': phases}


def assert_no_media_requests_after_stop(observation):
    phases = observation['phases']
    unexpected = phases['during_release'] + phases['after_release']
    assert not unexpected, 'Media refetched after stop: ' + repr(unexpected)


def arm_release_guard(video, event='click'):
    return video.evaluate("""(v, event) => ({timeOrigin: performance.timeOrigin,
      armed_at_ms: performance.timeOrigin + performance.now(),
      event_count: (window.__mediaDiagnosticEvents || []).length,
      video_index: Array.from(document.querySelectorAll('video')).indexOf(v), event,
      target: event === 'pointerleave' ? 'detail-host' : 'video-watch'})""", event)


# Observers only: no media methods or browser policies are replaced.
MEDIA_DIAGNOSTICS = """(() => {
  window.__mediaDiagnosticEvents = [];
  for (const event of ['loadstart', 'emptied', 'loadedmetadata', 'loadeddata', 'suspend', 'progress', 'abort', 'error', 'play', 'playing', 'pause', 'waiting', 'pointerenter', 'pointerleave', 'pointerdown', 'click']) {
    document.addEventListener(event, e => {
      const target = e.target instanceof HTMLVideoElement ? 'video' :
        e.target.matches?.('.video-watch') ? 'video-watch' : e.target.matches?.('.detail-video') ? 'detail-host' : null;
      const v = target === 'video' ? e.target : target ? e.target.closest('.detail-video')?.querySelector('video') : null;
      if (!v || window.__mediaDiagnosticEvents.length >= 500) return;
      window.__mediaDiagnosticEvents.push({event, target, video_index: Array.from(document.querySelectorAll('video')).indexOf(v),
        time: performance.now(), src: v.getAttribute('src'), live_sources: v.querySelectorAll('source[src]').length, currentSrc: v.currentSrc,
        paused: v.paused, readyState: v.readyState, networkState: v.networkState, trusted: e.isTrusted,
        state: v.closest('.detail-video')?.dataset.videoState || v.closest('.case-card')?.dataset.previewState});
    }, true);
  }
})();"""


def media_snapshot(page):
    return page.evaluate(r"""() => ({url: location.href, timeOrigin: performance.timeOrigin, time: performance.now(), hidden: document.hidden,
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
              'detail_videos': sum(map(len, films.values())), 'release_observations': [],
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
                    started_requests = []
                    network = context.new_cdp_session(page)
                    def observe_request(event):
                        record = media_request_started(event)
                        if record is not None:
                            started_requests.append(record)
                    network.on('Network.requestWillBeSent', observe_request)
                    network.send('Network.enable')
                    page.set_default_timeout(20000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    def assert_released(video, before, label):
                        # Observe beyond the stop event: a decoder reset must not
                        # silently reopen a retained SOURCE in the next event loop.
                        page.wait_for_timeout(500)
                        observation = media_release_observation(started_requests, before, media_snapshot(page))
                        report['release_observations'].append({'label': label, **observation})
                        if observation['phases']['during_release'] or observation['phases']['after_release']:
                            diagnose_unexpected_media(browser, page, output, report, request_details, mobile, label)
                        assert_no_media_requests_after_stop(observation)
                        assert video.evaluate('(v)=>v.paused && v.muted && !v.hasAttribute("src") && !v.querySelector("source[src]")')
                    for prefix, locale in [('', 'en'), ('zh/', 'zh')]:
                        stage = f'{locale}/{kind}: gallery initial'
                        requests.clear()
                        request_details.clear()
                        started_requests.clear()
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
                            started_requests.clear()
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
                                    before_stop = arm_release_guard(video, 'pointerleave')
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
                                # currentTime changes before its asynchronous seek.
                                # Observe seek completion; any later Range is still
                                # attributed by its actual start vs. the stop event.
                                expect(video).to_have_js_property('seeking', False)
                                expect(host).to_have_attribute('data-video-state', 'watching')
                                await_time = video.evaluate('(v)=>v.currentTime')
                                assert await_time > 0
                                if slug == 'sonic-loom':
                                    capture(page, f'{locale}-{kind}-detail-controls.png')
                                before_stop = arm_release_guard(video)
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
                                before_stop = arm_release_guard(video)
                                host.locator('.video-watch').click()
                                expect(host).to_have_attribute('data-video-state', 'idle')
                                assert_released(video, before_stop, f'{locale}-{kind}-{slug}-{index}-native-stop')
                                if not mobile:
                                    stage = f'{locale}/{kind}: released poster single click {slug}/{index}'
                                    # Keep the same lower-left single-click target.
                                    # Fully released players show a clickable poster,
                                    # not a disabled native control that eats input.
                                    assert video.evaluate('(v)=>!v.controls')
                                    box = video.bounding_box()
                                    assert box is not None
                                    video.click(position={'x': 30, 'y': box['height'] - 25})
                                    expect(host).to_have_attribute('data-video-state', 'watching')
                                    assert video.evaluate('(v)=>!v.paused && v.controls')
                                    before_stop = arm_release_guard(video)
                                    host.locator('.video-watch').click()
                                    expect(host).to_have_attribute('data-video-state', 'idle')
                                    assert_released(video, before_stop, f'{locale}-{kind}-{slug}-{index}-poster-stop')
                                pointer_scope = ' and poster single click' if not mobile else ''
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
