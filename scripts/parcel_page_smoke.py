"""Bounded Parcel Switchyard public-page acceptance on an isolated local build."""
import argparse
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
import subprocess
from pathlib import Path
import threading
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect


def select_parcel_filters(page):
    # These controls live inside the gallery's initially closed native details.
    disclosure = page.locator('#filter-disclosure')
    disclosure.locator('summary').click()
    expect(disclosure).to_have_attribute('open', '')
    for group, value in [('software', 'Godot'), ('capability', '交互')]:
        button = page.locator('[data-filter="%s"] [data-value="%s"]' % (group, value))
        button.click()
        expect(button).to_have_attribute('aria-pressed', 'true')


p = argparse.ArgumentParser()
p.add_argument('--site', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(a.site)))
threading.Thread(target=server.serve_forever, daemon=True).start()
origin = 'http://127.0.0.1:' + str(server.server_port)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert head == os.environ['EXPECTED_HEAD_SHA'], 'Exact candidate head mismatch'
report = {'head_sha': head, 'layouts': []}
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        report['browser_version'] = browser.version
        for layout, size in [('desktop', {'width':1440,'height':1080}), ('mobile', {'width':390,'height':844})]:
            for locale, prefix in [('en', ''), ('zh', 'zh/')]:
                context = browser.new_context(viewport=size, accept_downloads=True, reduced_motion='reduce', service_workers='block')
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
                page = context.new_page()
                page.goto(origin + '/' + prefix, wait_until='networkidle')
                page.locator('#search').fill('Parcel Switchyard')
                expect(page.locator('.case-card:visible')).to_have_count(1)
                select_parcel_filters(page)
                expect(page.locator('.case-card:visible')).to_have_count(1)
                page.locator('.case-card:visible a').first.click()
                expect(page.locator('h1')).to_contain_text('Parcel Switchyard')
                page.evaluate('document.fonts.ready')
                page.screenshot(path=str(a.output / (layout + '-' + locale + '-parcel-top.png')))
                video = page.locator('video').first
                video.scroll_into_view_if_needed()
                assert video.evaluate('(v)=>v.played.length') == 0
                video.press('Space')
                page.wait_for_function('document.querySelector("video").readyState >= 2 && !document.querySelector("video").paused')
                assert video.evaluate('(v) => v.videoWidth === 1280 && v.videoHeight === 720 && Math.abs(v.duration - 8) < .1 && !v.autoplay')
                video.focus()
                page.wait_for_function('!document.querySelector("video").paused && document.querySelector("video").currentTime > 0.4 && document.querySelector("video").readyState >= 3')
                page.keyboard.press('Space')
                page.wait_for_function('document.querySelector("video").paused && document.querySelector("video").readyState >= 3')
                played = video.evaluate('(v)=>v.currentTime')
                page.wait_for_timeout(300)
                video.locator('..').screenshot(path=str(a.output / (layout + '-' + locale + '-parcel-film.png')))
                source = page.locator('a[download="Parcel-Switchyard-Source.zip"]')
                with page.expect_download() as event:
                    source.click()
                download = event.value
                assert download.failure() is None
                original = a.site / 'docs/showcase/parcel-switchyard/Parcel-Switchyard-Source.zip'
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
                page.locator('#search').fill('no-parcel-matches-this-query')
                expect(page.locator('.case-card:visible')).to_have_count(0)
                page.locator('#reset-filters').click()
                expect(page.locator('.case-card:visible')).not_to_have_count(0)
                report['layouts'].append({'layout':layout,'locale':locale,'search_filters_reset_empty_back':True,'native_video_keyboard_play_pause':True,'video_advanced_seconds':played,'source_download_hash_match':True,'public_links_checked':len(checked),'horizontal_overflow':False})
                context.close()
        browser.close()
    report['passed'] = True
finally:
    server.shutdown()
    (a.output / 'parcel-page-report.json').write_text(json.dumps(report, indent=2) + '\n')
