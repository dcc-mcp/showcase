#!/usr/bin/env python3
"""Real Chromium WASM input acceptance; never sets game state or calls its bridge."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import subprocess
from pathlib import Path
import threading
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]


@contextmanager
def serve(directory):
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(directory)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:%d' % server.server_port
    finally:
        server.shutdown()
        server.server_close()


def state(page):
    return page.evaluate('window.__parcelState')


def wait(page, expression):
    page.wait_for_function('window.__parcelState && (' + expression + ')', timeout=15000)
    return state(page)


def wait_fresh(view, before, frames=2):
    return wait(view, 'window.__parcelState.publication_id>%d && window.__parcelState.process_frame>=%d' % (before['publication_id'], before['process_frame'] + frames))


def target(page, command, touch=False, view=None):
    view = view or page
    snapshot = state(view)
    x, y, width, height = snapshot['targets'][command]
    logical_width, logical_height = snapshot['layout_size']
    box = view.locator('#canvas').bounding_box()
    cx = box['x'] + (x + width / 2) * box['width'] / logical_width
    cy = box['y'] + (y + height / 2) * box['height'] / logical_height
    # Scroll presentation only. This never changes engine state or dispatches input.
    screen_height = page.viewport_size['height']
    if cy < 60 or cy > screen_height - 60:
        page.evaluate('(delta) => window.scrollBy(0, delta)', cy - screen_height / 2)
        box = view.locator('#canvas').bounding_box()
        cx = box['x'] + (x + width / 2) * box['width'] / logical_width
        cy = box['y'] + (y + height / 2) * box['height'] / logical_height
    if touch:
        page.touchscreen.tap(cx, cy)
    else:
        page.mouse.click(cx, cy)
    wait_fresh(view, snapshot)


def reset(page, touch=False):
    target(page, 'reset', touch)
    wait(page, 's.sent===0 && s.delivered===0 && s.missed===0 && s.active===0 && s.selected===1 && s.streak===0 && s.best===0 && !s.auto && !s.paused'.replace('s.', 'window.__parcelState.'))


def start(page):
    page.locator('#start').click()
    page.wait_for_selector('body[data-state="running"]', timeout=90000)
    wait(page, 'window.__parcelState.case==="parcel-switchyard"')
    if state(page)['paused']:
        target(page, 'pause')
        wait(page, '!window.__parcelState.paused')


def assert_fresh(page):
    snapshot = state(page)
    assert snapshot['sent'] == snapshot['delivered'] == snapshot['missed'] == snapshot['active'] == 0
    assert snapshot['selected'] == 1 and snapshot['streak'] == snapshot['best'] == 0 and not snapshot['auto'] and not snapshot['paused']


def assert_localized(view, lang):
    expected = {'en': {'instructions': 'Choose a route, then send.', 'note': 'game and browser controls support English and Chinese', 'rights': 'no additional license is granted', 'start': 'Start game'},
                'zh': {'instructions': '选择线路后发送', 'note': '游戏画面与浏览器控件均支持中英文', 'rights': '没有新增授权', 'start': '开始游戏'}}[lang]
    for selector, text in expected.items():
        assert text in view.locator('#' + selector).inner_text(), (selector, lang)


def assert_native_language(view, lang):
    snapshot = state(view)
    previous = snapshot.get('draw_receipt', {}).get('draw_id', 0)
    wait(view, 'window.__parcelState.draw_receipt.draw_id>%d' % previous)
    snapshot = state(view)
    receipt = snapshot['draw_receipt']
    assert snapshot['language'] == receipt['language'] == lang
    assert receipt['draw_frame'] > 0 and not receipt['missing_translations'] and not receipt['missing_glyphs'], receipt
    required = ['包裹转辙场', '下一件包裹', '港口', '花园', '市场'] if lang == 'zh' else ['Parcel Switchyard', 'Harbor', 'Garden', 'Market']
    assert all(label in receipt['labels'] for label in required), receipt
    return receipt


def assert_phone_size(page, view=None):
    view = view or page
    snapshot = state(view)
    if not snapshot['mobile_layout']:
        return
    box = view.locator('#canvas').bounding_box()
    scale = box['width'] / snapshot['layout_size'][0]
    assert min(min(rect[2], rect[3]) * scale for rect in snapshot['targets'].values()) >= 44
    assert snapshot['minimum_mobile_text_units'] * scale >= 14


def run_input(browser, base, output, width, height, lang, phone):
    name = '%s-%s-%dx%d' % ('touch' if phone else 'desktop', lang, width, height)
    context = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=phone, has_touch=phone,
                                  device_scale_factor=1, record_video_dir=str(output / 'videos'), record_video_size={'width': width, 'height': height})
    try:
        page = context.new_page()
        errors, requests, console_errors, failed_requests, packs = [], [], [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url))
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' or re.search(r'SCRIPT ERROR|Parse Error|(?:^|\s)ERROR:', message.text) else None)
        page.on('requestfailed', lambda request: failed_requests.append({'url': request.url, 'failure': request.failure}))
        page.on('response', lambda response: packs.append(response) if urlparse(response.url).path.endswith('/game.pck') else None)
        page.goto(base + '/play/parcel-switchyard/?lang=' + lang)
        assert page.locator('html').get_attribute('lang') == lang
        assert_localized(page, lang)
        assert not any('.wasm' in url or '.pck' in url for url in requests), 'Game must not download before Start'
        start(page)
        assert_fresh(page)
        language_receipts = [assert_native_language(page, lang)]
        page.screenshot(path=str(output / (name + '-localized-start.png')), full_page=True)
        assert packs, 'No actual PCK response'
        expected_pack = page.evaluate('JSON.parse(document.getElementById("game-config").textContent).showcasePackSha256')
        served_pack = hashlib.sha256(packs[-1].body()).hexdigest()
        assert packs[-1].ok and served_pack == expected_pack
        assert state(page)['mobile_layout'] == phone
        if phone:
            box = page.locator('#canvas').bounding_box()
            snapshot = state(page)
            scale = box['width'] / snapshot['layout_size'][0]
            minimum_target = min(min(rect[2], rect[3]) * scale for rect in snapshot['targets'].values())
            primary_text = snapshot['minimum_mobile_text_units'] * scale
            assert minimum_target >= 44 and primary_text >= 14, (minimum_target, primary_text)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'
        else:
            minimum_target = primary_text = None
        # A correct Garden delivery, a deliberately wrong route, then all route labels.
        if phone:
            target(page, 'route:1', True);target(page, 'send', True)
        else:
            page.locator('#canvas').focus()
            # Start from the default Garden selection, so each non-default key must
            # demonstrably change the actual engine state before returning to 2.
            for key, selected in [('1', 0), ('3', 2), ('2', 1)]:
                page.keyboard.press(key)
                wait(page, 'window.__parcelState.selected===%d' % selected)
            page.keyboard.press('Space')
        wait(page, 'window.__parcelState.delivered===1 && window.__parcelState.active===0')
        target(page, 'route:2', phone);target(page, 'send', phone)
        wait(page, 'window.__parcelState.missed===1 && window.__parcelState.streak===0')
        language_receipts.append(assert_native_language(page, lang))
        reset(page, phone)
        for route in [1, 0, 2]:
            expected = state(page)['delivered'] + 1
            target(page, 'route:' + str(route), phone);target(page, 'send', phone)
            wait(page, 'window.__parcelState.delivered===%d && window.__parcelState.active===0' % expected)
        assert state(page)['streak'] == 3
        language_receipts.append(assert_native_language(page, lang))
        page.screenshot(path=str(output / (name + '-three-destinations.png')), full_page=True)
        if not phone:
            page.locator('#canvas').focus()
            for key, expression in [('a', 'window.__parcelState.auto'), ('a', '!window.__parcelState.auto'), ('p', 'window.__parcelState.paused'), ('p', '!window.__parcelState.paused')]:
                before_key = state(page)
                page.keyboard.press(key)
                wait_fresh(page, before_key)
                wait(page, expression)
            page.keyboard.press('r')
            wait(page, 'window.__parcelState.sent===0 && window.__parcelState.best===0')
            assert_fresh(page)
        # Busy route capacity, repeated actions, frozen motion and safe reset.
        reset(page, phone)
        for _ in range(8):
            target(page, 'send', phone)
        wait(page, 'window.__parcelState.sent===6 && window.__parcelState.active===6')
        # Capacity and pause are separate scenarios: a full queue would hide a
        # broken pause-dispatch guard. Keep exactly one correctly routed parcel.
        reset(page, phone)
        target(page, 'send', phone)
        wait(page, 'window.__parcelState.sent===1 && window.__parcelState.active===1')
        target(page, 'pause', phone);wait(page, 'window.__parcelState.paused')
        paused = state(page)
        assert paused['active'] == 1 and paused['sent'] == 1 and paused['delivered'] == 0
        wait_fresh(page, paused, frames=6)
        target(page, 'send', phone)
        after = wait_fresh(page, state(page), frames=6)
        assert all(after[key] == paused[key] for key in ['sent', 'delivered', 'missed', 'active'])
        assert abs(after['elapsed'] - paused['elapsed']) < 0.001
        target(page, 'pause', phone);wait(page, '!window.__parcelState.paused')
        # No further sends: delivery must belong to the parcel present at pause.
        resumed = wait(page, 'window.__parcelState.delivered===1 && window.__parcelState.active===0')
        assert resumed['sent'] == 1 and resumed['missed'] == 0 and resumed['elapsed'] > paused['elapsed']
        for _ in range(3):
            reset(page, phone)
        target(page, 'auto', phone)
        wait(page, 'window.__parcelState.auto && window.__parcelState.sent>=1')
        target(page, 'auto', phone);wait(page, '!window.__parcelState.auto')
        target(page, 'pause', phone);wait(page, 'window.__parcelState.paused')
        before = state(page)
        # Reflow and orientation changes must preserve a live, paused shift.
        for new_width, new_height in ([(844, 390), (width, height)] if phone else [(320, 568), (768, 1024), (2048, 1152), (width, height)]):
            page.set_viewport_size({'width': new_width, 'height': new_height})
            expected_mobile = phone or new_width < 1100
            wait(page, 'window.__parcelState.mobile_layout===' + str(expected_mobile).lower())
            after = state(page)
            assert all(after[key] == before[key] for key in ['selected', 'sent', 'delivered', 'missed', 'active', 'auto', 'paused'])
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert_phone_size(page)
            page.screenshot(path=str(output / (name + '-reflow-%dx%d.png' % (new_width, new_height))), full_page=True)
        reset(page, phone)
        if phone:
            # Real finger drag over the native canvas must pan without dispatching.
            page.evaluate('window.scrollTo(0, 0)')
            box = page.locator('#canvas').bounding_box()
            start_y = min(height - 60, max(150, box['y'] + 200))
            start_x = width / 2
            session = context.new_cdp_session(page)
            before_scroll = page.evaluate('scrollY')
            session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': start_x, 'y': start_y}]})
            for offset in [25, 50, 75, 100]:
                session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': start_x, 'y': start_y - offset}]})
                time.sleep(.04)
            session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            page.wait_for_timeout(250)
            assert page.evaluate('scrollY') > before_scroll + 20, 'Finger swipe did not scroll'
            assert_fresh(page)
            session.detach()
        else:
            page.locator('#fullscreen').click()
            page.wait_for_function('document.fullscreenElement !== null')
            page.keyboard.press('Escape')
            page.wait_for_function('document.fullscreenElement === null')
        reset(page, phone)
        page.screenshot(path=str(output / (name + '-reset.png')), full_page=True)
        # Accessible, localized controls remain real UI actions, not test injections.
        page.locator('#alternate-label').click()
        page.locator('[data-command="route:1"]').click()
        page.locator('[data-command="send"]').click()
        wait(page, 'window.__parcelState.delivered===1')
        page.locator('[data-command="reset"]').click();wait(page, 'window.__parcelState.sent===0')
        # Exiting/restarting creates a new shift; this game never promises persistence.
        page.locator('#exit').click();page.wait_for_selector('body[data-state="ready"]', timeout=30000)
        start(page);assert_fresh(page)
        page.locator('#language').click()
        other = 'en' if lang == 'zh' else 'zh'
        page.wait_for_url('**/*lang=' + other)
        assert page.locator('html').get_attribute('lang') == other
        page.go_back();page.wait_for_selector('body[data-state="ready"]')
        page.go_forward();page.wait_for_selector('body[data-state="ready"]')
        assert not errors, errors
        assert not console_errors, console_errors
        assert not failed_requests, failed_requests
        result = {'name': name, 'status': 'passed', 'input': 'Playwright touchscreen tap → shell tap/pan normalization → Godot canvas mouse events' if phone else 'Real browser keyboard and mouse events',
                  'viewport': [width, height], 'lang': lang, 'minimum_target_css_px': minimum_target, 'minimum_primary_text_css_px': primary_text,
                  'checks': ['deferred loading', 'actual WASM startup', 'three destinations', 'misroute', 'capacity', 'pause/resume', 'auto on/off', 'repeated reset', 'live resize/orientation', 'touch pan' if phone else 'fullscreen/exit', 'localized alternate controls', 'exit/restart', 'language Back/Forward'],
                  'native_language_receipts': language_receipts, 'page_errors': errors, 'console_errors': console_errors, 'failed_requests': failed_requests, 'served_pack_sha256': served_pack}
        return result
    except Exception:
        if not page.is_closed():
            page.screenshot(path=str(output / (name + '-failure.png')), full_page=True)
        raise
    finally:
        context.close()


def run_embedding(browser, base, output, width, height, lang, phone, kind):
    name = 'embedded-%s-%s-%dx%d' % (kind, lang, width, height)
    context = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=phone, has_touch=phone,
                                  device_scale_factor=1, record_video_dir=str(output / 'videos'), record_video_size={'width': width, 'height': height})
    page = context.new_page()
    errors, console_errors, packs = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' or re.search(r'SCRIPT ERROR|Parse Error|(?:^|\s)ERROR:', message.text) else None)
    page.on('response', lambda response: packs.append(response) if urlparse(response.url).path.endswith('/game.pck') else None)
    try:
        prefix = '/zh' if lang == 'zh' else ''
        response = page.goto(base + prefix + '/' + kind + '/parcel-switchyard/', wait_until='domcontentloaded')
        assert response.ok and page.locator('html').get_attribute('lang') == lang
        assert page.locator('iframe').count() == 0, 'Embedded game must await explicit start'
        start_selector = '[data-play-start]' if kind == 'cases' else '[data-game-start]'
        page.locator(start_selector).click()
        page.wait_for_selector('iframe')
        frame = page.locator('iframe').element_handle().content_frame()
        frame.wait_for_selector('body')
        if kind == 'cases':
            assert_localized(frame, lang)
            frame.locator('#start').click()
        frame.wait_for_selector('body[data-state="running"]', timeout=90000)
        wait(frame, 'window.__parcelState.case==="parcel-switchyard"')
        if state(frame)['paused']:
            target(page, 'pause', phone, frame)
        assert_fresh(frame)
        language_receipt = assert_native_language(frame, lang)
        assert_phone_size(page, frame)
        assert packs and packs[-1].ok
        expected_hash = frame.evaluate('JSON.parse(document.getElementById("game-config").textContent).showcasePackSha256')
        served_hash = hashlib.sha256(packs[-1].body()).hexdigest()
        assert served_hash == expected_hash
        target(page, 'route:0', phone, frame)
        wait(frame, 'window.__parcelState.selected===0')
        target(page, 'send', phone, frame)
        wait(frame, 'window.__parcelState.missed===1 && window.__parcelState.active===0')
        target(page, 'reset', phone, frame)
        assert_fresh(frame)
        target(page, 'send', phone, frame)
        wait(frame, 'window.__parcelState.delivered===1 && window.__parcelState.active===0')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(output / (name + '-delivered.png')), full_page=True)
        if kind == 'games':
            page.locator('[data-game-reset]').click()
            wait(frame, 'window.__parcelState.sent===0 && window.__parcelState.best===0')
            assert_fresh(frame)
        exit_selector = '[data-play-exit]' if kind == 'cases' else '[data-game-exit]'
        page.locator(exit_selector).click()
        page.wait_for_selector('iframe', state='detached')
        assert not errors and not console_errors, (errors, console_errors)
        return {'name': name, 'status': 'passed', 'lang': lang, 'native_language_receipt': language_receipt, 'viewport': [width, height], 'served_pack_sha256': served_hash,
                'checks': ['explicit launch', 'actual WASM', 'non-default route', 'misroute', 'reset', 'delivery', 'minimum phone targets/text', 'parent exit'], 'page_errors': errors, 'console_errors': console_errors}
    except Exception:
        if not page.is_closed():
            page.screenshot(path=str(output / (name + '-failure.png')), full_page=True)
        raise
    finally:
        context.close()


def run_loading(browser, base, lang):
    context = browser.new_context()
    page = context.new_page()
    page.route('**/*.wasm*', lambda route: route.abort())
    page.goto(base + '/play/parcel-switchyard/?lang=' + lang)
    page.locator('#start').click();page.wait_for_selector('body[data-state="error"]', timeout=90000)
    assert page.locator('#start').inner_text() == ('重试' if lang == 'zh' else 'Retry')
    assert ('无法加载游戏' if lang == 'zh' else 'Could not load') in page.locator('#status').inner_text()
    page.unroute('**/*.wasm*');page.locator('#start').click()
    page.wait_for_selector('body[data-state="ready"]');start(page);assert_fresh(page)
    context.close()
    context = browser.new_context();page = context.new_page()
    held_routes = []
    page.route('**/*.wasm*', lambda route: held_routes.append(route))
    page.goto(base + '/play/parcel-switchyard/?lang=' + lang)
    page.locator('#start').click();page.locator('#cancel').click()
    page.wait_for_selector('body[data-state="ready"]')
    assert not page.locator('#stage').is_visible()
    context.close()
    return {'name': 'loading-retry-cancel-' + lang, 'status': 'passed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--browser-executable')
    parser.add_argument('--expected-head', default=os.environ.get('EXPECTED_HEAD_SHA'))
    parser.add_argument('--require-integration', action='store_true')
    args = parser.parse_args();args.output.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((args.site / 'play/parcel-switchyard/export-provenance.json').read_text())
    source_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.expected_head and source_head != args.expected_head:
        raise SystemExit('Exact candidate head mismatch')
    pack = args.site / 'play/parcel-switchyard/game.pck'
    pack_hash = hashlib.sha256(pack.read_bytes()).hexdigest()
    assert provenance['export_files'][0]['sha256'] == pack_hash
    report = {'source_head': source_head, 'case': 'parcel-switchyard', 'recorded_at': datetime.now(timezone.utc).isoformat(), 'status': 'not-tested',
              'pack_sha256': pack_hash, 'scenarios': [],
              'not_claimed': ['Physical phone', 'Safari/Firefox', 'Production deployment', 'Subjective visual acceptance', 'MCP authorship', 'Native GUI touch']}
    phase = 'browser launch'
    try:
        with sync_playwright() as playwright:
            options = {'headless': True, 'args': ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
            if args.browser_executable:
                options['executable_path'] = args.browser_executable
            browser = playwright.chromium.launch(**options)
            report['browser'] = 'Chromium ' + browser.version
            phase = 'localhost server'
            with serve(args.site) as base:
                phase = 'real browser input'
                for width, height, phone in [(1280, 900, False), (320, 568, True), (390, 844, True)]:
                    for lang in ['en', 'zh']:
                        report['scenarios'].append(run_input(browser, base, args.output, width, height, lang, phone))
                for lang in ['en', 'zh']:
                    report['scenarios'].append(run_loading(browser, base, lang))
                integrated = all((args.site / kind / 'parcel-switchyard/index.html').is_file() for kind in ['cases', 'games'])
                if args.require_integration and not integrated:
                    raise AssertionError('Generated case/game integration pages are required')
                if integrated:
                    for width, height, phone in [(1280, 900, False), (320, 568, True), (390, 844, True)]:
                        for lang in ['en', 'zh']:
                            for kind in ['cases', 'games']:
                                report['scenarios'].append(run_embedding(browser, base, args.output, width, height, lang, phone, kind))
                report['integration_tested'] = integrated
            browser.close()
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'blocked' if phase in ['browser launch', 'localhost server'] else 'failed'
        report['stage'] = phase
        report['error_type'] = type(error).__name__
        # Preserve useful failure detail without publishing machine paths/crash logs.
        message = str(error)
        report['reason'] = 'Chromium process singleton socket is denied by the execution sandbox.' if 'socket() failed: Operation not permitted' in message else message.splitlines()[0][:500]
    report['evidence_files'] = [{'path': path.relative_to(args.output).as_posix(), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(args.output.rglob('*')) if path.is_file() and path.name != 'report.json']
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
