"""Bounded Prism Tide public-page acceptance on an isolated local build."""
import argparse
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect
from browser_preview import QuietHandler

p = argparse.ArgumentParser()
p.add_argument('--site', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(a.site)))
threading.Thread(target=server.serve_forever, daemon=True).start()
origin = 'http://127.0.0.1:' + str(server.server_port)
report = {'head_sha': os.environ.get('EXPECTED_HEAD_SHA'), 'layouts': []}
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        report['browser_version'] = browser.version
        for layout, size in [('desktop', {'width':1440,'height':1080}), ('mobile', {'width':390,'height':844})]:
            context = browser.new_context(viewport=size, accept_downloads=True, reduced_motion='reduce', service_workers='block')
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
            page = context.new_page()
            page.goto(origin + '/', wait_until='networkidle')
            page.locator('#search').fill('Prism Tide')
            expect(page.locator('.case-card:visible')).to_have_count(1)
            if page.locator('.filter-disclosure').get_attribute('open') is None:
                page.locator('.filter-disclosure summary').click()
            page.locator('[data-filter="software"] [data-value="Godot"]').click()
            page.locator('[data-filter="capability"] [data-value="交互"]').click()
            expect(page.locator('.case-card:visible')).to_have_count(1)
            page.locator('.case-card:visible a').first.click()
            expect(page.locator('h1')).to_contain_text('Prism Tide')
            page.evaluate('document.fonts.ready')
            page.screenshot(path=str(a.output / (layout + '-prism-tide-top.png')))
            video = page.locator('video').first
            video.scroll_into_view_if_needed()
            expect(video).to_have_js_property('controls', True)
            expect(video).to_have_js_property('paused', True)
            assert video.evaluate('(v) => !v.autoplay && v.played.length === 0')
            # Explicit native keyboard playback also loads preload=none media.
            video.focus()
            page.keyboard.press('Space')
            page.wait_for_function('document.querySelector("video").readyState >= 2')
            assert video.evaluate('(v) => v.videoWidth === 1280 && v.videoHeight === 800 && Math.abs(v.duration - 15) < .1 && !v.autoplay')
            page.wait_for_function('!document.querySelector("video").paused && document.querySelector("video").currentTime > 0.4 && document.querySelector("video").readyState >= 3')
            page.keyboard.press('Space')
            page.wait_for_function('document.querySelector("video").paused && document.querySelector("video").readyState >= 3')
            played = video.evaluate('(v)=>v.currentTime')
            page.wait_for_timeout(300)
            video.locator('..').screenshot(path=str(a.output / (layout + '-prism-tide-film.png')))
            source = page.locator('a[download="Prism-Tide-Source.zip"]')
            with page.expect_download() as event:
                source.click()
            download = event.value
            assert download.failure() is None
            original = a.site / 'docs/showcase/prism-tide/Prism-Tide-Source.zip'
            assert hashlib.sha256(Path(download.path()).read_bytes()).digest() == hashlib.sha256(original.read_bytes()).digest()
            checked = set()
            for href in page.locator('a[href]').evaluate_all('(links)=>links.map(a=>a.href)'):
                if href.startswith(origin + '/'):
                    href = href.split('#')[0]
                    if href not in checked:
                        assert context.request.get(href).ok
                        checked.add(href)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.go_back(wait_until='networkidle')
            page.locator('#reset-filters').click()
            page.locator('#search').fill('no-prism-tide-matches-this-query')
            expect(page.locator('.case-card:visible')).to_have_count(0)
            page.locator('#reset-filters').click()
            expect(page.locator('.case-card:visible')).not_to_have_count(0)
            report['layouts'].append({'layout':layout,'search_filters_reset_empty_back':True,'native_video_keyboard_play_pause':True,'video_advanced_seconds':played,'source_download_hash_match':True,'public_links_checked':len(checked),'horizontal_overflow':False})
            context.close()
        browser.close()
    report['passed'] = True
finally:
    server.shutdown()
    (a.output / 'prism-tide-page-report.json').write_text(json.dumps(report, indent=2) + '\n')
