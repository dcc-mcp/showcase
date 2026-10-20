#!/usr/bin/env python3
"""Real Chromium WASM input acceptance; never sets game state or calls its bridge."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import re
import subprocess
import struct
import sys
from pathlib import Path
import threading
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from localization import LOCALES


def assert_generated_page_language(page, response, lang):
    expected = LOCALES[lang]['lang']
    actual = page.locator('html').get_attribute('lang')
    detail = {'url': page.url, 'http_status': response.status if response is not None else None,
              'expected_lang': expected, 'actual_lang': actual}
    assert response is not None and response.ok, detail
    assert actual == expected, detail


def failure_reason(error):
    message = str(error)
    if 'socket() failed: Operation not permitted' in message:
        return 'Chromium process singleton socket is denied by the execution sandbox.'
    return next((line.strip()[:500] for line in message.splitlines() if line.strip()), type(error).__name__)


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


def record_console_error(message, errors):
    if message.type == 'error' or re.search(r'SCRIPT ERROR|Parse Error|(?:^|\s)ERROR:', message.text):
        errors.append(message.text)


def state(page):
    return page.evaluate('window.__parcelState')


def wait(page, expression):
    try:
        page.wait_for_function('window.__parcelState && (' + expression + ')', timeout=15000)
    except Exception as error:
        raise AssertionError('Browser state wait failed: ' + expression + ' (' + type(error).__name__ + ')') from error
    return state(page)


def wait_fresh(view, before, frames=2):
    return wait(view, 'window.__parcelState.publication_id>%d && window.__parcelState.process_frame>=%d' % (before['publication_id'], before['process_frame'] + frames))


def install_input_trace(context):
    # Observation only: no preventDefault, event dispatch, command bridge or engine writes.
    context.add_init_script("""(() => {
      window.__parcelInputTrace = [];
      document.addEventListener('DOMContentLoaded', () => {
        const record = event => {
          if (event.target?.id !== 'canvas') return;
          const canvas = event.target, box = canvas.getBoundingClientRect();
          const point = event.changedTouches?.[0] || event.touches?.[0] || event;
          const state = window.__parcelState;
          const entry = {type: event.type, trusted: event.isTrusted, time: performance.now(),
            client: [point.clientX, point.clientY], page: [point.pageX, point.pageY],
            box: {x:box.x,y:box.y,width:box.width,height:box.height},
            buffer: [canvas.width,canvas.height], scroll: [scrollX,scrollY],
            viewport: {width:innerWidth,height:innerHeight,scale:visualViewport?.scale},
            state: state ? {publication_id:state.publication_id,process_frame:state.process_frame,
              layout_size:state.layout_size,targets:state.targets,selected:state.selected,
              sent:state.sent,active:state.active,auto:state.auto,paused:state.paused} : null};
          if (state) entry.logical = [(point.clientX-box.x)*state.layout_size[0]/box.width,
                                      (point.clientY-box.y)*state.layout_size[1]/box.height];
          window.__parcelInputTrace.push(entry);
          if (window.__parcelInputTrace.length>128) window.__parcelInputTrace.shift();
        };
        for (const type of ['pointerdown','pointerup','touchstart','touchend','mousedown','mouseup'])
          document.addEventListener(type, record, {capture:true,passive:true});
      }, {once:true});
    })();""")


def target(page, command, touch=False, view=None, repetitions=1):
    view = view or page
    snapshot = state(view)
    x, y, width, height = snapshot['targets'][command]
    logical_width, logical_height = snapshot['layout_size']
    box = view.locator('#canvas').bounding_box()
    cx = box['x'] + (x + width / 2) * box['width'] / logical_width
    cy = box['y'] + (y + height / 2) * box['height'] / logical_height
    # Scroll presentation only. The parent site has CSS smooth scrolling, so
    # request an instant move before measuring coordinates for real input.
    # This never changes engine state or dispatches synthetic game input.
    screen_height = page.viewport_size['height']
    if cy < 60 or cy > screen_height - 60:
        page.evaluate('(delta) => window.scrollBy({top: delta, behavior: "instant"})', cy - screen_height / 2)
        box = view.locator('#canvas').bounding_box()
        cx = box['x'] + (x + width / 2) * box['width'] / logical_width
        cy = box['y'] + (y + height / 2) * box['height'] / logical_height
    if getattr(page, '_parcel_input_trace', False) is True:
        view.evaluate("""entry => {
          window.__parcelInputTrace.push(entry);
          if (window.__parcelInputTrace.length>128) window.__parcelInputTrace.shift();
        }""", {'type':'intent','command':command,'top_page_point':[cx,cy],
                 'top_page_canvas':box,'touch':touch,'repetitions':repetitions,
                 'layout_size':snapshot['layout_size'],'target':snapshot['targets'][command]})
    for _ in range(repetitions):
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


def assert_native_language(view, lang, previous=None, require_new_draw=True):
    snapshot = state(view)
    if previous is None:
        previous = snapshot.get('draw_receipt', {}).get('draw_id', 0)
    if require_new_draw:
        wait(view, 'window.__parcelState.draw_receipt.draw_id>%d' % previous)
    snapshot = state(view)
    receipt = snapshot['draw_receipt']
    assert receipt['draw_id'] > 0
    assert receipt['draw_id'] > previous if require_new_draw else receipt['draw_id'] >= previous
    assert snapshot['language'] == receipt['language'] == lang
    assert receipt['draw_frame'] > 0, {'gate': 'actual draw', 'draw_frame': receipt['draw_frame']}
    assert not receipt['missing_translations'], {'gate': 'translation coverage', 'missing': receipt['missing_translations']}
    assert not receipt['missing_glyphs'], {'gate': 'font coverage', 'missing_codepoints': receipt['missing_glyphs']}
    required = ['包裹转辙场', '下一件包裹', '港口', '花园', '市场'] if lang == 'zh' else ['Parcel Switchyard', 'Harbor', 'Garden', 'Market']
    assert all(label in receipt['labels'] for label in required), {'gate': 'required labels', 'missing': [label for label in required if label not in receipt['labels']]}
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


def enclosing_pixel_rect(box, scroll):
    assert scroll['dpr'] == 1, scroll
    assert all(math.isfinite(box[key]) for key in ['x', 'y', 'width', 'height']), box
    assert all(math.isfinite(scroll[key]) for key in ['x', 'y']), scroll
    assert 0 < box['width'] <= 2048 and 0 < box['height'] <= 2048, box
    # Match pinned Playwright 1.63 screenshotElement -> enclosingIntRect:
    # https://github.com/microsoft/playwright/blob/v1.63.0/packages/playwright-core/src/server/helper.ts
    left, top = box['x'] + scroll['x'], box['y'] + scroll['y']
    x, y = math.floor(left + 0.001), math.floor(top + 0.001)
    return {'x': x, 'y': y, 'width': math.ceil(left + box['width'] - 0.001) - x,
            'height': math.ceil(top + box['height'] - 0.001) - y}


def capture_canvas_png(page, canvas, path, before_box):
    # Element screenshots may scroll automatically. Re-read main-frame geometry
    # afterwards, including its document offset; fractional origins can add two
    # outward edge pixels even though the CSS dimensions are unchanged.
    observe_scroll = '() => ({x: window.scrollX, y: window.scrollY, dpr: window.devicePixelRatio})'
    before_scroll = page.evaluate(observe_scroll)
    before_rect = enclosing_pixel_rect(before_box, before_scroll)
    png = canvas.screenshot(path=str(path))
    box = canvas.bounding_box()
    assert box and all(abs(box[key] - before_box[key]) < 0.001 for key in ['width', 'height']), (before_box, box)
    scroll = page.evaluate(observe_scroll)
    rect = enclosing_pixel_rect(box, scroll)
    assert all(abs(box[key] + scroll[key] - before_box[key] - before_scroll[key]) < 0.001 for key in ['x', 'y']), (before_box, before_scroll, box, scroll)
    assert rect == before_rect, (before_rect, rect)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'
    dimensions = struct.unpack('>II', png[16:24])
    assert dimensions == (rect['width'], rect['height']), (dimensions, rect, box, scroll)
    return {'png_dimensions': list(dimensions), 'pre_capture_css_box': before_box, 'post_capture_css_box': box,
            'pre_capture_scroll': before_scroll, 'post_capture_scroll': scroll, 'document_pixel_rect': rect}


def capture_embedded_delivery(page, frame, output, name, lang):
    # Full-page captures of very tall case pages can repeat compositor tiles.
    # Capture the real bounded canvas, plus the current viewport for context.
    canvas = frame.locator('#canvas')
    canvas.scroll_into_view_if_needed()
    receipt = assert_native_language(frame, lang)
    box = canvas.bounding_box()
    assert box and 0 < box['width'] <= 2048 and 0 < box['height'] <= 2048, box
    keys = ['delivered', 'missed', 'sent', 'active', 'streak', 'selected', 'auto', 'paused']
    snapshot = state(frame)
    before = {key: snapshot[key] for key in keys}
    assert before['delivered'] == before['sent'] == before['streak'] == 1
    assert before['missed'] == before['active'] == 0 and not before['auto']
    pixels = capture_canvas_png(page, canvas, output / (name + '-delivered.png'), box)
    page.screenshot(path=str(output / (name + '-delivered-context.png')), full_page=False)
    after = state(frame)
    assert {key: after[key] for key in keys} == before, 'Capture changed the completed game state'
    return {'draw_receipt': receipt, 'observed_state': before, 'css_box': box, 'png_dimensions': pixels['png_dimensions'], 'pixel_geometry': pixels,
            'scope': 'Actual canvas element pixels and separate viewport context; not a full-page image.'}


def assert_reflow_geometry(boxes):
    for name, box in boxes.items():
        assert box and box['width'] > 0 and box['height'] > 0, (name, box)
    stage, canvas = boxes['#stage'], boxes['#canvas']
    assert all(abs(stage[key] - canvas[key]) <= 1 for key in ['x', 'y', 'width', 'height']), boxes
    for upper, lower in [('#stage', '#alternate'), ('#alternate', '#note'), ('#note', '#rights')]:
        assert boxes[lower]['y'] >= boxes[upper]['y'] + boxes[upper]['height'] - 1, boxes


def wait_presentation(page):
    # Passive browser paint observation, with a bounded wait. No engine command
    # or game state is set; CSS-only resizes need no native CanvasItem redraw.
    frames = page.evaluate('''() => new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Browser presentation timeout')), 15000);
      requestAnimationFrame(first => requestAnimationFrame(second => {
        clearTimeout(timeout);
        resolve({first, second, visibility: document.visibilityState});
      }));
    })''')
    assert frames['visibility'] == 'visible' and 0 <= frames['first'] < frames['second'], frames
    return frames


def capture_reflow(page, output, name, lang, before_resize):
    # Every resize needs fresh browser presentation. Full-page screenshot
    # viewport expansion can race Chromium's WebGL composition; keep the actual
    # bounded canvas and separately expose the real controls/rights viewport.
    canvas = page.locator('#canvas')
    canvas.scroll_into_view_if_needed()
    keys = ['selected', 'sent', 'delivered', 'missed', 'active', 'auto', 'paused', 'elapsed']
    snapshot = state(page)
    before = {key: snapshot[key] for key in keys}
    assert before['paused'], 'Reflow capture requires the actual paused shift'
    # A paused shift deliberately does not redraw every process frame. A layout
    # switch must draw after the pre-resize baseline, possibly before this helper
    # starts. A same-layout resize only scales the existing canvas through CSS.
    layout_changed = snapshot['mobile_layout'] != before_resize['mobile_layout']
    previous_draw = before_resize['draw_receipt']['draw_id']
    receipt = assert_native_language(page, lang, previous=previous_draw, require_new_draw=layout_changed)
    canvas_presentation = wait_presentation(page)
    boxes = {selector: page.locator(selector).bounding_box() for selector in ['#stage', '#canvas', '#alternate', '#note', '#rights']}
    assert_reflow_geometry(boxes)
    box = boxes['#canvas']
    assert box['width'] <= 2048 and box['height'] <= 2048, box
    pixels = capture_canvas_png(page, canvas, output / (name + '.png'), box)
    page.locator('#rights').scroll_into_view_if_needed()
    # The context contains ordinary DOM controls. Scrolling must not force the
    # unchanged paused canvas to redraw; require a fresh live state publication.
    context_state = wait_fresh(page, state(page))
    context_presentation = wait_presentation(page)
    controls = {selector: page.locator(selector).bounding_box() for selector in ['#alternate-label', '#note', '#rights']}
    viewport = page.viewport_size
    for selector, rect in controls.items():
        assert rect and rect['width'] > 0 and rect['height'] > 0, (selector, rect)
        assert rect['x'] >= -1 and rect['y'] >= -1, (selector, rect)
        assert rect['x'] + rect['width'] <= viewport['width'] + 1 and rect['y'] + rect['height'] <= viewport['height'] + 1, (selector, rect, viewport)
    page.screenshot(path=str(output / (name + '-context.png')), full_page=False)
    after = state(page)
    assert {key: after[key] for key in keys} == before, 'Reflow capture changed the paused shift'
    return {'draw_receipt': receipt, 'native_draw_required': layout_changed, 'previous_draw_id': previous_draw,
            'canvas_presentation': canvas_presentation, 'context_presentation': context_presentation,
            'context_publication': {key: context_state[key] for key in ['publication_id', 'process_frame']},
            'observed_state': before, 'geometry': boxes, 'png_dimensions': pixels['png_dimensions'], 'pixel_geometry': pixels,
            'controls_viewport_boxes': controls, 'viewport': viewport,
            'scope': 'Actual bounded canvas and real scrolled controls/rights viewport. Cross-layout resize requires a new native draw; same-layout resize observes CSS presentation of the retained paused canvas.'}


def run_input(browser, base, output, width, height, lang, phone):
    name = '%s-%s-%dx%d' % ('touch' if phone else 'desktop', lang, width, height)
    context = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=phone, has_touch=phone,
                                  device_scale_factor=1, record_video_dir=str(output / 'videos'), record_video_size={'width': width, 'height': height})
    try:
        page = context.new_page()
        errors, requests, console_errors, failed_requests, packs = [], [], [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url))
        page.on('console', lambda message: record_console_error(message, console_errors))
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
        # A real rapid burst fills the queue. Waiting for two rendered frames
        # after every click can let earlier parcels finish on software rendering.
        target(page, 'send', phone, repetitions=8)
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
        reflow_captures = []
        for new_width, new_height in ([(844, 390), (width, height)] if phone else [(320, 568), (768, 1024), (2048, 1152), (width, height)]):
            page.set_viewport_size({'width': new_width, 'height': new_height})
            expected_mobile = phone or new_width < 1100
            wait(page, 'window.__parcelState.mobile_layout===' + str(expected_mobile).lower())
            after = wait_fresh(page, before)
            assert all(after[key] == before[key] for key in ['selected', 'sent', 'delivered', 'missed', 'active', 'auto', 'paused', 'elapsed'])
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert_phone_size(page)
            capture_name = name + '-reflow-%dx%d' % (new_width, new_height)
            reflow_captures.append({'name': capture_name, **capture_reflow(page, output, capture_name, lang, before)})
            before = state(page)
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
            page.wait_for_function('document.fullscreenElement === document.getElementById("stage")')
            page.keyboard.press('Escape')
            page.wait_for_function('document.fullscreenElement === null')
            # The visible in-fullscreen control must independently work too.
            page.locator('#fullscreen').click()
            page.wait_for_function('document.fullscreenElement === document.getElementById("stage")')
            leave = page.locator('#leave-fullscreen')
            assert leave.is_visible() and leave.inner_text() == ('退出全屏' if lang == 'zh' else 'Exit fullscreen')
            assert leave.bounding_box()['height'] >= 44
            page.screenshot(path=str(output / (name + '-fullscreen.png')), full_page=True)
            leave.click()
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
                  'reflow_captures': reflow_captures, 'native_language_receipts': language_receipts, 'page_errors': errors, 'console_errors': console_errors, 'failed_requests': failed_requests, 'served_pack_sha256': served_pack}
        return result
    except Exception:
        if not page.is_closed():
            page.screenshot(path=str(output / (name + '-failure.png')), full_page=True)
            (output / (name + '-failure-state.json')).write_text(json.dumps(state(page), ensure_ascii=False, indent=2) + '\n')
        raise
    finally:
        context.close()


def run_embedding(browser, base, output, width, height, lang, phone, kind):
    name = 'embedded-%s-%s-%dx%d' % (kind, lang, width, height)
    context = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=phone, has_touch=phone,
                                  device_scale_factor=1, record_video_dir=str(output / 'videos'), record_video_size={'width': width, 'height': height})
    install_input_trace(context)
    page = context.new_page()
    page._parcel_input_trace = True
    frame = None
    errors, console_errors, packs = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: record_console_error(message, console_errors))
    page.on('response', lambda response: packs.append(response) if urlparse(response.url).path.endswith('/game.pck') else None)
    try:
        prefix = '/zh' if lang == 'zh' else ''
        response = page.goto(base + prefix + '/' + kind + '/parcel-switchyard/', wait_until='domcontentloaded')
        assert_generated_page_language(page, response, lang)
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
        delivery_capture = capture_embedded_delivery(page, frame, output, name, lang)
        if kind == 'games':
            page.locator('[data-game-reset]').click()
            wait(frame, 'window.__parcelState.sent===0 && window.__parcelState.best===0')
            assert_fresh(frame)
        input_trace = frame.evaluate('window.__parcelInputTrace || []')
        exit_selector = '[data-play-exit]' if kind == 'cases' else '[data-game-exit]'
        page.locator(exit_selector).click()
        page.wait_for_selector('iframe', state='detached')
        assert not errors and not console_errors, (errors, console_errors)
        return {'name': name, 'status': 'passed', 'lang': lang, 'native_language_receipt': language_receipt, 'delivery_capture': delivery_capture, 'viewport': [width, height], 'served_pack_sha256': served_hash,
                'input_trace': input_trace,
                'checks': ['explicit launch', 'actual WASM', 'non-default route', 'misroute', 'reset', 'delivery', 'minimum phone targets/text', 'parent exit'], 'page_errors': errors, 'console_errors': console_errors}
    except Exception:
        try:
            diagnostics = {'name':name,'input_trace':frame.evaluate('window.__parcelInputTrace || []') if frame else [],
                           'native_state':state(frame) if frame else None,
                           'parent':page.evaluate('({scroll:[scrollX,scrollY],viewport:[innerWidth,innerHeight]})')}
            (output / (name + '-input-diagnostics.json')).write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2)+'\n')
        except Exception as diagnostic_error:
            (output / (name + '-diagnostic-error.txt')).write_text(type(diagnostic_error).__name__+'\n')
        if not page.is_closed():
            page.screenshot(path=str(output / (name + '-failure.png')), full_page=False)
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
        report['reason'] = failure_reason(error)
    report['evidence_files'] = [{'path': path.relative_to(args.output).as_posix(), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(args.output.rglob('*')) if path.is_file() and path.name != 'report.json']
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
