#!/usr/bin/env python3
"""Test an explicitly generated local-only pilot; never invokes a DCC host."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import subprocess
import os
import hashlib
from playwright.sync_api import sync_playwright


def run(site, output, executable=None):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:' + str(server.server_port)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    expected = os.environ.get('EXPECTED_HEAD_SHA')
    if expected and head != expected:
        raise ValueError('viewer QA head mismatch')
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=executable, channel=None if executable else 'chrome', chromium_sandbox=True)
            for lang in ('en', 'zh'):
                for mobile in (False, True):
                    context = browser.new_context(viewport={'width': 390 if mobile else 1280, 'height': 844 if mobile else 900}, is_mobile=mobile, has_touch=mobile)
                    page = context.new_page(); requests = []; errors = []
                    page.on('request', lambda r: requests.append(r.url))
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(base + '/' + lang + '.html'); page.wait_for_timeout(300)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    assert not any(url.endswith('.glb') or 'model-viewer.min.js' in url for url in requests), requests
                    start = page.locator('[data-model-start]'); start.click()
                    page.wait_for_function("document.querySelector('model-viewer')?.loaded === true", timeout=30000)
                    viewer = page.locator('model-viewer'); before = viewer.evaluate('(v) => v.getCameraOrbit().theta')
                    button = page.locator('[data-model-action="right"]'); button.focus(); page.keyboard.press('Enter')
                    page.wait_for_function('(before) => document.querySelector("model-viewer").getCameraOrbit().theta !== before', arg=before)
                    radius = viewer.evaluate('(v) => v.getCameraOrbit().radius')
                    page.locator('[data-model-action="in"]').click()
                    page.wait_for_function('(r) => document.querySelector("model-viewer").getCameraOrbit().radius < r', arg=radius)
                    page.locator('[data-model-action="reset"]').click()
                    page.wait_for_function('Math.abs(document.querySelector("model-viewer").getCameraOrbit().theta) < 0.01')
                    if mobile:
                        # Actual browser touch events: rotate using a horizontal gesture.
                        cdp = context.new_cdp_session(page); box = viewer.bounding_box()
                        x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
                        for event, dx in [('touchStart', 0), ('touchMove', 70), ('touchEnd', 70)]:
                            cdp.send('Input.dispatchTouchEvent', {'type': event, 'touchPoints': [] if event == 'touchEnd' else [{'x': x + dx, 'y': y}]})
                        page.wait_for_function('Math.abs(document.querySelector("model-viewer").getCameraOrbit().theta) > 0.01')
                        radius = viewer.evaluate('(v) => v.getCameraOrbit().radius')
                        for event, spread in [('touchStart', 25), ('touchMove', 65), ('touchEnd', 65)]:
                            cdp.send('Input.dispatchTouchEvent', {'type': event, 'touchPoints': [] if event == 'touchEnd' else [{'x': x - spread, 'y': y}, {'x': x + spread, 'y': y}]})
                        page.wait_for_function('(r) => Math.abs(document.querySelector("model-viewer").getCameraOrbit().radius - r) > 0.001', arg=radius)

                    assert viewer.evaluate('(v) => v.constructor.modelCacheSize') == 0
                    assert not viewer.evaluate('(v) => v.autoplay || v.autoRotate')
                    assert not any(not url.startswith(base) for url in requests), requests
                    # Capture the reset view, not the deliberately zoomed gesture state.
                    page.locator('[data-model-action="reset"]').click()
                    page.wait_for_function('(r) => Math.abs(document.querySelector("model-viewer").getCameraOrbit().radius - r) < 0.001', arg=radius)
                    page.screenshot(path=str(output / (lang + ('-mobile' if mobile else '-desktop') + '.png')), full_page=True)
                    page.locator('[data-model-stop]').click(); assert page.locator('model-viewer').count() == 0
                    assert start.is_enabled(); start.click()
                    page.wait_for_function("document.querySelector('model-viewer')?.loaded === true")
                    page.locator('[data-model-stop]').click()
                    assert not errors, errors
                    results.append({'locale': lang, 'mobile': mobile, 'lazy_load': True, 'keyboard_orbit': True, 'zoom_reset': True, 'touch_orbit': mobile, 'touch_pinch': mobile, 'disconnected_model_cache': 0, 'close_reopen': True, 'external_requests': False})
                    context.close()
            # Failed asset and Close during activation must not resurrect a viewer.
            context = browser.new_context(); page = context.new_page(); page.goto(base + '/en.html')
            page.route('**/asset.glb', lambda route: route.abort())
            page.locator('[data-model-start]').click()
            page.wait_for_function('document.querySelector("[role=status]").textContent.includes("unavailable")')
            assert page.locator('model-viewer').count() == 0 and page.locator('[data-model-start]').is_enabled()
            results.append({'failed_asset_fallback': True})
            context.close()
            # Hold the module response in a fresh context: immediate error recovery
            # can hide Close before a test can click it and is not an in-flight load.
            context = browser.new_context(); page = context.new_page(); held = []
            page.route('**/model-viewer.min.js', lambda route: held.append(route))
            page.goto(base + '/en.html')
            page.locator('[data-model-start]').click(); page.locator('[data-model-stop]').click()
            for route in held: route.continue_()
            page.wait_for_timeout(500); assert page.locator('model-viewer').count() == 0
            assert page.locator('[data-model-start]').is_enabled()
            results.append({'close_during_module_load': True})
            browser.close()
    finally:
        server.shutdown()
    report = {'head_sha': head, 'asset_sha256': hashlib.sha256((Path(site) / 'asset.glb').read_bytes()).hexdigest(), 'scope': 'Viewer controls only; not production or benchmark acceptance', 'results': results}
    (output / 'result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--site', default='_model-preview-pilot')
    parser.add_argument('--output', required=True); parser.add_argument('--executable')
    parser.add_argument('--test-fixture', action='store_true', help='Create an isolated synthetic test triangle, not production evidence')
    a = parser.parse_args()
    if a.test_fixture:
        import tempfile, hashlib
        from test_model_previews import fixture_glb
        from model_preview_pilot import generate
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'fixture.glb'; source.write_bytes(fixture_glb())
            license_file = Path(temp) / 'LICENSE.txt'; license_file.write_text('Synthetic software test fixture only. Not a Showcase asset or production receipt.')
            a.site = generate(source, hashlib.sha256(source.read_bytes()).hexdigest(), license_file, '_model-preview-pilot')
    run(a.site, a.output, a.executable)
