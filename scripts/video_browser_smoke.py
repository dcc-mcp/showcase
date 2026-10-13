#!/usr/bin/env python3
"""Decode every published video on Chromium; verify hover and native controls.

Uses only locally served public outputs. Mobile coverage is touch-viewport
emulation, not a physical-device or subjective audio acceptance claim.
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from localization_browser_smoke import MountHandler


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
    def check(text):
        report['checks'].append(text)
        print('PASS ' + text, flush=True)
    def capture(page, filename):
        page.screenshot(path=str(output / filename))
        report['screenshots'].append(filename)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            report['browser'] = browser.version
            for mobile in [False, True]:
                kind = 'mobile' if mobile else 'desktop'
                context = browser.new_context(viewport={'width': 390 if mobile else 1486, 'height': 844 if mobile else 1059},
                                              is_mobile=mobile, has_touch=mobile, service_workers='block')
                requests = []
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
                for prefix, locale in [('', 'en'), ('zh/', 'zh')]:
                    requests.clear()
                    page.mouse.move(1, 1)
                    page.goto(base + prefix, wait_until='networkidle')
                    expect(page.locator('.case-card[data-preview-src]')).to_have_count(len(films))
                    assert not any(url.split('?')[0].endswith(('.mp4', '.webm', '.wasm', '.pck')) for url in requests)
                    for slug in films:
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
                        requests.clear()
                        page.mouse.move(1, 1)
                        page.goto(base + prefix + f'cases/{slug}/', wait_until='networkidle')
                        expect(page.locator('.detail-video')).to_have_count(len(items))
                        assert not any(url.split('?')[0].endswith(('.mp4', '.webm')) for url in requests)
                        for index, item in enumerate(items):
                            host = page.locator('.detail-video').nth(index)
                            video = host.locator('video')
                            host.scroll_into_view_if_needed()
                            if not mobile:
                                video.hover()
                                expect(host).to_have_attribute('data-video-state', 'preview')
                                assert video.evaluate('(v)=>v.muted && v.videoWidth>0 && v.loop && v.controls')
                                page.mouse.move(1, 1)
                                expect(host).to_have_attribute('data-video-state', 'idle')
                                assert video.evaluate('(v)=>v.paused && v.muted && !v.hasAttribute("src")')
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
                            host.locator('.video-watch').click()
                            expect(host).to_have_attribute('data-video-state', 'idle')
                            assert video.evaluate('(v)=>v.paused && v.muted && !v.hasAttribute("src")')
                            # Exercise native keyboard play from idle, rather
                            # than calling HTMLMediaElement.play in the test.
                            video.focus()
                            page.keyboard.press('Space')
                            expect(host).to_have_attribute('data-video-state', 'watching')
                            assert video.evaluate('(v)=>!v.paused && v.controls')
                            host.locator('.video-watch').click()
                            expect(host).to_have_attribute('data-video-state', 'idle')
                            check(f'{locale}/{kind}: {item["src"]} decoded; hover/manual/native keyboard and cleanup')
                        assert not any(url.split('?')[0].endswith(('.wasm', '.pck')) for url in requests)
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                context.close()
            # Policy gates keep the native/manual alternative working.
            for policy in ['reduced-motion', 'save-data']:
                context = browser.new_context(reduced_motion='reduce' if policy == 'reduced-motion' else 'no-preference')
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
                context.close()
            browser.close()
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
