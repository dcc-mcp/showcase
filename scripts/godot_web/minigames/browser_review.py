#!/usr/bin/env python3
"""Exercise the artifact-only review desk and its real exported game, not a mock."""
import argparse
import hashlib
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    expected = json.loads((args.site / 'review/evidence.json').read_text())
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(args.site.resolve())))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    report = {'checks': [], 'passed': False, 'pack_sha256': expected['pack_sha256'],
              'source_commit': expected['source_commit'], 'limitations': [
                  'Chromium only; mobile is viewport/touch emulation, not a physical phone.',
                  'Audio player progression is not subjective listening approval.',
                  'Artifact-only preview; public collection and playable manifest are unchanged.']}
    def check(name, **data):
        report['checks'].append({'name': name, 'passed': True, **data})
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--use-gl=angle', '--use-angle=swiftshader',
                '--enable-unsafe-swiftshader', '--disable-dev-shm-usage'])
            for lang in ('en', 'zh'):
                for mobile in (False, True):
                    label = lang + ('-mobile' if mobile else '-desktop')
                    context = browser.new_context(viewport={'width': 320 if mobile else 1280, 'height': 900},
                                                  is_mobile=mobile, has_touch=mobile, accept_downloads=True)
                    page = context.new_page()
                    requested = []
                    page.on('request', lambda r: requested.append(r.url))
                    url = origin + ('/zh/index.html' if lang == 'zh' else '/index.html')
                    response = page.goto(url)
                    assert response.status == 200
                    assert page.locator('html').get_attribute('lang') == ('zh-CN' if lang == 'zh' else 'en')
                    assert page.locator('#review-boundary').is_visible()
                    assert not any(u.endswith(('.wasm', '.pck')) for u in requested)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    for media_id in ('original-video', 'original-audio'):
                        page.locator('#' + media_id).wait_for(state='visible')
                        assert page.locator('#' + media_id).evaluate('(e) => e.paused && e.playbackRate === 1')
                    check(label + ': truthful localized boundaries, original speed and no autoplay/deferred engine')
                    page.screenshot(path=str(args.output / (label + '-portal.png')), full_page=True)
                    # Verify every local page/resource link, including the actual source-download click.
                    links = page.locator('[href], [src]').evaluate_all("els => els.map(e => e.getAttribute('href') || e.getAttribute('src'))")
                    for link in links:
                        from urllib.parse import urljoin
                        assert context.request.get(urljoin(url, link)).status == 200, link
                    with page.expect_download() as download:
                        page.locator('#source-download').click()
                    source = Path(download.value.path())
                    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected['files']['native-source.zip']['sha256']
                    check(label + ': all local resources and source download hash')
                    page.locator('#language').click()
                    assert page.locator('html').get_attribute('lang') != ('zh-CN' if lang == 'zh' else 'en')
                    page.go_back()
                    assert page.url == url
                    check(label + ': language switch and browser Back')
                    for media_id in ('original-video', 'original-audio'):
                        player = page.locator('#' + media_id)
                        player.scroll_into_view_if_needed()
                        player.focus()
                        player.press('Space')
                        page.wait_for_function("id => {const m=document.getElementById(id); return !m.paused && m.currentTime > .35}", arg=media_id)
                        player.press('Space')
                        page.wait_for_function("id => document.getElementById(id).paused", arg=media_id)
                        check(label + ': ' + media_id + ' actual keyboard playback and pause',
                              seconds=player.evaluate('(e) => e.currentTime'))
                    page.locator('#play-candidate').focus()
                    page.keyboard.press('Enter')
                    page.wait_for_url('**/play/signal-garden/index.html?lang=' + lang)
                    page.locator('#start').click()
                    page.wait_for_function("lang => window.__showcaseState && document.body.dataset.state === 'running' && window.__showcaseState.language === lang", arg=lang)
                    if mobile:
                        state = page.evaluate('window.__showcaseState')
                        board = state['board']
                        canvas = page.locator('#canvas')
                        canvas.scroll_into_view_if_needed()
                        rect = canvas.bounding_box()
                        page.touchscreen.tap(rect['x'] + (board['x'] + board['cell'] / 2) * rect['width'] / state['layout_width'],
                                             rect['y'] + (board['y'] + board['cell'] / 2) * rect['height'] / state['layout_height'])
                    else:
                        page.locator('#canvas').focus()
                        page.keyboard.press('Space')
                    page.wait_for_function('window.__showcaseState.moves === 1')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    page.screenshot(path=str(args.output / (label + '-actual-game.png')), full_page=True)
                    check(label + ': entry launches real localized Godot and accepts actual input')
                    context.close()
            browser.close()
        report['passed'] = True
    finally:
        server.shutdown()
        (args.output / 'portal-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
