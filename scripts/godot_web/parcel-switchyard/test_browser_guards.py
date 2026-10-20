"""Host-free regressions for passive fresh-frame and native-language gates."""
import ast
import math
import re
import sys
import struct
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from localization import LOCALES


def helper(name, source_path=None, **namespace):
    source=source_path or Path(__file__).with_name('browser_test.py')
    node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
    return namespace[name]


def pixel_capture():
    return helper('capture_canvas_png', struct=struct, enclosing_pixel_rect=helper('enclosing_pixel_rect', math=math))


class ObserverGuards(unittest.TestCase):
    def test_pixel_bounds_include_fractional_origin_and_document_scroll(self):
        enclose = helper('enclosing_pixel_rect', math=math)
        box = {'x': 12, 'y': 25.5, 'width': 296, 'height': 542.65625}
        self.assertEqual(enclose(box, {'x': 0, 'y': 334, 'dpr': 1}), {'x': 12, 'y': 359, 'width': 296, 'height': 544})
        self.assertEqual(enclose(box, {'x': 0, 'y': 334.5, 'dpr': 1}), {'x': 12, 'y': 360, 'width': 296, 'height': 543})
        self.assertEqual(enclose({'x': 1.0001, 'y': -100.0001, 'width': 300, 'height': 550}, {'x': 0, 'y': 1000, 'dpr': 1}),
                         {'x': 1, 'y': 900, 'width': 300, 'height': 550})
        for changes in [{'width': 0}, {'height': 8192}, {'x': float('nan')}, {'y': float('inf')}]:
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                enclose(dict(box, **changes), {'x': 0, 'y': 334, 'dpr': 1})
        with self.assertRaises(AssertionError): enclose(box, {'x': 0, 'y': 334, 'dpr': 2})

    def test_png_capture_allows_scroll_but_not_document_movement_or_wrong_pixels(self):
        page, canvas = Mock(), Mock()
        before = {'x': 12, 'y': 25.5, 'width': 296, 'height': 542.65625}
        after = dict(before, y=15.5)
        canvas.bounding_box.return_value = after
        valid_png = b'\x89PNG\r\n\x1a\n' + bytes(8) + struct.pack('>II', 296, 544)
        canvas.screenshot.return_value = valid_png
        capture = pixel_capture()
        def scrolls(): page.evaluate.side_effect = [{'x': 0, 'y': 334, 'dpr': 1}, {'x': 0, 'y': 344, 'dpr': 1}]
        scrolls()
        result = capture(page, canvas, Path('/evidence/canvas.png'), before)
        self.assertEqual(result['png_dimensions'], [296, 544])
        self.assertEqual(result['document_pixel_rect']['y'], 359)
        for size in [(296, 543), (297, 544), (296, 8192)]:
            scrolls();canvas.screenshot.return_value = valid_png[:16] + struct.pack('>II', *size)
            with self.subTest(size=size), self.assertRaises(AssertionError): capture(page, canvas, Path('/evidence/canvas.png'), before)
        canvas.screenshot.return_value = valid_png
        for changes in [{'y': 16.5}, {'width': 296.5}]:
            scrolls();canvas.bounding_box.return_value = dict(after, **changes)
            with self.subTest(changes=changes), self.assertRaises(AssertionError): capture(page, canvas, Path('/evidence/canvas.png'), before)

    def test_embedded_capture_uses_fresh_draw_and_bounded_actual_canvas(self):
        events = []
        page, frame, canvas = Mock(), Mock(), Mock()
        page.evaluate.return_value = {'x': 0, 'y': 0, 'dpr': 1}
        frame.locator.return_value = canvas
        canvas.scroll_into_view_if_needed.side_effect = lambda: events.append('scroll')
        receipt = {'draw_id': 5, 'draw_frame': 10}
        fresh = Mock(side_effect=lambda *args: events.append('draw') or receipt)
        canvas.bounding_box.return_value = {'x': 0, 'y': 40, 'width': 300, 'height': 550}
        canvas.screenshot.side_effect = lambda **kwargs: events.append('canvas') or b'\x89PNG\r\n\x1a\n' + bytes(8) + struct.pack('>II', 300, 550)
        page.screenshot.side_effect = lambda **kwargs: events.append('viewport')
        snapshot = {'delivered': 1, 'missed': 0, 'sent': 1, 'active': 0, 'streak': 1, 'selected': 1, 'auto': False, 'paused': False}
        capture = helper('capture_embedded_delivery', assert_native_language=fresh, state=Mock(return_value=snapshot), capture_canvas_png=pixel_capture())
        result = capture(page, frame, Path('/evidence'), 'case', 'zh')
        self.assertEqual(events, ['scroll', 'draw', 'canvas', 'viewport'])
        canvas.screenshot.assert_called_once_with(path='/evidence/case-delivered.png')
        page.screenshot.assert_called_once_with(path='/evidence/case-delivered-context.png', full_page=False)
        self.assertEqual(result['png_dimensions'], [300, 550])
        self.assertEqual(result['observed_state'], snapshot)
        fresh.assert_called_once_with(frame, 'zh')
        for dimensions in [(300, 8192), (320, 550)]:
            canvas.screenshot.side_effect = None
            canvas.screenshot.return_value = b'\x89PNG\r\n\x1a\n' + bytes(8) + struct.pack('>II', *dimensions)
            with self.subTest(dimensions=dimensions), self.assertRaises(AssertionError):
                capture(page, frame, Path('/evidence'), 'case', 'zh')

    def test_reflow_geometry_rejects_stage_growth_and_control_overlap(self):
        check = helper('assert_reflow_geometry')
        boxes = {'#stage': {'x': 10, 'y': 0, 'width': 300, 'height': 550},
                 '#canvas': {'x': 10, 'y': 0, 'width': 300, 'height': 550},
                 '#alternate': {'x': 0, 'y': 562, 'width': 320, 'height': 44},
                 '#note': {'x': 0, 'y': 618, 'width': 320, 'height': 60},
                 '#rights': {'x': 0, 'y': 690, 'width': 320, 'height': 80}}
        check(boxes)
        for selector, changes in [('#stage', {'height': 700}), ('#canvas', {'width': 0}),
                                  ('#alternate', {'y': 540}), ('#note', {'y': 580}), ('#rights', {'y': 660})]:
            altered = {name: dict(box) for name, box in boxes.items()}
            altered[selector].update(changes)
            with self.subTest(selector=selector, changes=changes), self.assertRaises(AssertionError):
                check(altered)

    def test_reflow_capture_waits_for_draw_and_exposes_real_controls(self):
        events = []
        page = Mock();page.viewport_size = {'width': 320, 'height': 568}
        page.evaluate.return_value = {'x': 0, 'y': 0, 'dpr': 1}
        locators = {name: Mock() for name in ['#canvas', '#stage', '#alternate', '#alternate-label', '#note', '#rights']}
        page.locator.side_effect = lambda selector: locators[selector]
        box = {'x': 10, 'y': 0, 'width': 300, 'height': 550}
        locators['#canvas'].bounding_box.return_value = box
        locators['#stage'].bounding_box.return_value = dict(box)
        locators['#alternate'].bounding_box.return_value = {'x': 0, 'y': 562, 'width': 320, 'height': 44}
        locators['#alternate-label'].bounding_box.return_value = {'x': 0, 'y': 300, 'width': 320, 'height': 44}
        locators['#note'].bounding_box.side_effect = [{'x': 0, 'y': 618, 'width': 320, 'height': 60}, {'x': 0, 'y': 356, 'width': 320, 'height': 40}]
        locators['#rights'].bounding_box.side_effect = [{'x': 0, 'y': 690, 'width': 320, 'height': 80}, {'x': 0, 'y': 408, 'width': 320, 'height': 80}]
        locators['#canvas'].scroll_into_view_if_needed.side_effect = lambda: events.append('canvas-scroll')
        locators['#rights'].scroll_into_view_if_needed.side_effect = lambda: events.append('rights-scroll')
        locators['#canvas'].screenshot.side_effect = lambda **kwargs: events.append('canvas') or b'\x89PNG\r\n\x1a\n' + bytes(8) + struct.pack('>II', 300, 550)
        page.screenshot.side_effect = lambda **kwargs: events.append('viewport')
        snapshot = {'selected': 1, 'sent': 1, 'delivered': 0, 'missed': 0, 'active': 1, 'auto': False, 'paused': True, 'elapsed': 1.5,
                    'mobile_layout': True, 'draw_receipt': {'draw_id': 7}, 'publication_id': 10, 'process_frame': 20}
        before_resize = dict(snapshot, mobile_layout=False, draw_receipt={'draw_id': 6})
        fresh = Mock(side_effect=lambda *args, **kwargs: events.append('draw') or {'draw_id': 7})
        presentation = Mock(side_effect=lambda *args: events.append('presentation') or {'first': 1, 'second': 2, 'visibility': 'visible'})
        publication = Mock(side_effect=lambda *args: events.append('publication') or snapshot)
        capture = helper('capture_reflow', assert_native_language=fresh, state=Mock(return_value=snapshot), struct=struct,
                         assert_reflow_geometry=helper('assert_reflow_geometry'), wait_presentation=presentation, wait_fresh=publication, capture_canvas_png=pixel_capture())
        result = capture(page, Path('/evidence'), 'reflow', 'en', before_resize)
        self.assertEqual(events, ['canvas-scroll', 'draw', 'presentation', 'canvas', 'rights-scroll', 'publication', 'presentation', 'viewport'])
        self.assertEqual(result['observed_state'], {key: snapshot[key] for key in result['observed_state']})
        self.assertEqual(result['png_dimensions'], [300, 550])
        self.assertTrue(result['native_draw_required'])
        fresh.assert_called_once_with(page, 'en', previous=6, require_new_draw=True)
        page.screenshot.assert_called_once_with(path='/evidence/reflow-context.png', full_page=False)
        self.assertEqual(page.evaluate.call_count, 2)
        self.assertTrue(all(call.args == ('() => ({x: window.scrollX, y: window.scrollY, dpr: window.devicePixelRatio})',) for call in page.evaluate.call_args_list))
        # A scrolled-out control or changed paused game must not become evidence.
        locators['#note'].bounding_box.side_effect = None
        locators['#note'].bounding_box.return_value = {'x': 0, 'y': 356, 'width': 320, 'height': 40}
        locators['#rights'].bounding_box.side_effect = None
        locators['#rights'].bounding_box.return_value = {'x': 0, 'y': 408, 'width': 320, 'height': 80}
        # Geometry has its own negatives above; isolate the viewport/state guards.
        capture = helper('capture_reflow', assert_native_language=fresh, state=Mock(return_value=snapshot), struct=struct,
                         assert_reflow_geometry=Mock(), wait_presentation=presentation, wait_fresh=publication, capture_canvas_png=pixel_capture())
        locators['#alternate-label'].bounding_box.return_value['y'] = -30
        with self.assertRaises(AssertionError):
            capture(page, Path('/evidence'), 'reflow', 'en', before_resize)
        locators['#alternate-label'].bounding_box.return_value['y'] = 300
        result = capture(page, Path('/evidence'), 'reflow', 'en', snapshot)
        self.assertFalse(result['native_draw_required'])
        fresh.assert_called_with(page, 'en', previous=7, require_new_draw=False)
        changed = dict(snapshot, active=0)
        capture = helper('capture_reflow', assert_native_language=fresh, state=Mock(side_effect=[snapshot, snapshot, changed]), struct=struct,
                         assert_reflow_geometry=Mock(), wait_presentation=presentation, wait_fresh=publication, capture_canvas_png=pixel_capture())
        with self.assertRaisesRegex(AssertionError, 'changed the paused shift'):
            capture(page, Path('/evidence'), 'reflow', 'en', before_resize)

    def test_presentation_requires_two_visible_browser_frames(self):
        page = Mock()
        observe = helper('wait_presentation')
        valid = {'first': 10, 'second': 20, 'visibility': 'visible'}
        page.evaluate.return_value = valid
        self.assertEqual(observe(page), valid)
        source = page.evaluate.call_args.args[0]
        self.assertEqual(source.count('requestAnimationFrame('), 2)
        self.assertIn('setTimeout(', source)
        self.assertIn('15000', source)
        self.assertNotIn('showcaseCommand', source)
        for changed in [dict(first=20), dict(second=10), dict(visibility='hidden')]:
            page.evaluate.return_value = dict(valid, **changed)
            with self.subTest(changed=changed), self.assertRaises(AssertionError): observe(page)

    def test_every_reflow_gets_fresh_publication_and_bounded_capture(self):
        source = Path(__file__).with_name('browser_test.py').read_text()
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'run_input')
        loop = next(n for n in ast.walk(node) if isinstance(n, ast.For) and ast.unparse(n.target) == '(new_width, new_height)')
        statements = [ast.unparse(n) for n in loop.body]
        fresh = next(i for i, statement in enumerate(statements) if 'after = wait_fresh(page, before)' in statement)
        capture = next(i for i, statement in enumerate(statements) if 'capture_reflow(' in statement)
        self.assertLess(fresh, capture)
        self.assertIn('capture_reflow(page, output, capture_name, lang, before)', statements[capture])
        self.assertEqual(statements[-1], 'before = state(page)')
        self.assertFalse(any('screenshot(' in statement for statement in statements))

    def test_page_filters_require_real_disclosure_click_before_filter_clicks(self):
        events = []

        class Locator:
            def __init__(self, selector): self.selector = selector
            def locator(self, selector): return Locator(self.selector + ' ' + selector)
            def click(self): events.append(('click', self.selector))
            def to_have_attribute(self, name, value): events.append(('assert', self.selector, name, value))

        page = Mock()
        page.locator.side_effect = Locator
        source = Path(__file__).resolve().parents[2] / 'parcel_page_smoke.py'
        helper('select_parcel_filters', source_path=source, expect=lambda locator: locator)(page)
        self.assertEqual(events, [
            ('click', '#filter-disclosure summary'),
            ('assert', '#filter-disclosure', 'open', ''),
            ('click', '[data-filter="software"] [data-value="Godot"]'),
            ('assert', '[data-filter="software"] [data-value="Godot"]', 'aria-pressed', 'true'),
            ('click', '[data-filter="capability"] [data-value="交互"]'),
            ('assert', '[data-filter="capability"] [data-value="交互"]', 'aria-pressed', 'true'),
        ])
        page.evaluate.assert_not_called()

    def test_generated_pages_use_the_canonical_html_locale(self):
        check = helper('assert_generated_page_language', LOCALES=LOCALES)
        for lang, actual in [('en', 'en'), ('zh', 'zh-CN')]:
            with self.subTest(lang=lang):
                page = Mock(url='http://localhost/cases/parcel-switchyard/')
                page.locator.return_value.get_attribute.return_value = actual
                check(page, Mock(ok=True, status=200), lang)

    def test_wrong_generated_locale_and_http_failure_keep_diagnostics(self):
        check = helper('assert_generated_page_language', LOCALES=LOCALES)
        for actual, response in [('zh', Mock(ok=True, status=200)), ('en', Mock(ok=True, status=200)),
                                 ('zh-CN', Mock(ok=False, status=404)), ('zh-CN', None)]:
            with self.subTest(actual=actual, response=response):
                page = Mock(url='http://localhost/zh/cases/parcel-switchyard/')
                page.locator.return_value.get_attribute.return_value = actual
                with self.assertRaises(AssertionError) as caught:
                    check(page, response, 'zh')
                detail = caught.exception.args[0]
                self.assertEqual(detail['url'], page.url)
                self.assertEqual(detail['actual_lang'], actual)
                self.assertEqual(detail['expected_lang'], 'zh-CN')
                self.assertEqual(detail['http_status'], response.status if response is not None else None)

    def test_empty_failure_messages_still_produce_a_report_reason(self):
        reason = helper('failure_reason')
        for error in [AssertionError(), AssertionError(''), AssertionError('\n  \n')]:
            self.assertEqual(reason(error), 'AssertionError')
        self.assertEqual(reason(ValueError('')), 'ValueError')
        self.assertEqual(reason(AssertionError('\n  actual failed gate\nprivate detail')), 'actual failed gate')
        self.assertEqual(reason(AssertionError('x' * 700)), 'x' * 500)
        self.assertEqual(reason(RuntimeError('socket() failed: Operation not permitted\nprivate detail')),
                         'Chromium process singleton socket is denied by the execution sandbox.')

    def test_observed_engine_group_leak_stays_fatal(self):
        errors = []
        callback = helper('record_console_error', re=re)
        callback(Mock(type='log', text='ERROR: Pages in use exist at exit in PagedAllocator: N16WorkerThreadPool5GroupE'), errors)
        self.assertEqual(len(errors), 1)
        self.assertIn('WorkerThreadPool5GroupE', errors[0])
        callback(Mock(type='log', text='Godot Engine v4.6.3'), errors)
        self.assertEqual(len(errors), 1)
        callback(Mock(type='error', text='Any unexpected browser error'), errors)
        self.assertEqual(len(errors), 2)

    def test_capacity_burst_uses_eight_real_inputs_before_one_fresh_wait(self):
        snapshot = {'targets': {'send': [100, 100, 80, 50]}, 'layout_size': [1280, 720]}
        for touch in [False, True]:
            page = Mock();page.viewport_size = {'height': 900}
            page.locator.return_value.bounding_box.return_value = {'x': 0, 'y': 0, 'width': 1280, 'height': 720}
            events = []
            page.touchscreen.tap.side_effect = lambda *args: events.append(('tap', args))
            page.mouse.click.side_effect = lambda *args: events.append(('click', args))
            fresh = Mock(side_effect=lambda *args: events.append(('fresh', args)))
            settle = Mock()
            helper('target', state=Mock(return_value=snapshot), wait_fresh=fresh, settle_input_geometry=settle)(page, 'send', touch, repetitions=8)
            self.assertEqual([event[0] for event in events], [('tap' if touch else 'click')] * 8 + ['fresh'])
            self.assertTrue(all(event[1] == (140, 125) for event in events[:8]))
            fresh.assert_called_once_with(page, snapshot)
            settle.assert_called_once_with(page)
            page.evaluate.assert_called_once_with('() => window.scrollTo({left: scrollX, top: scrollY, behavior: "instant"})')

    def test_scrolled_target_uses_instant_presentation_and_remeasures(self):
        snapshot = {'targets': {'send': [100, 600, 800, 80]}, 'layout_size': [1000, 720]}
        for touch in [False, True]:
            with self.subTest(touch=touch):
                page = Mock();page.viewport_size = {'height': 900}
                page.locator.return_value.bounding_box.side_effect = [
                    {'x': 40, 'y': 1200, 'width': 1000, 'height': 720},
                    {'x': 40, 'y': -190, 'width': 1000, 'height': 720}]
                events = []
                page.evaluate.side_effect = lambda *args: events.append(('scroll', args))
                page.touchscreen.tap.side_effect = lambda *args: events.append(('tap', args))
                page.mouse.click.side_effect = lambda *args: events.append(('click', args))
                fresh = Mock(side_effect=lambda *args: events.append(('fresh', args)))
                settle = Mock(side_effect=lambda *args: events.append(('settle', args)))
                helper('target', state=Mock(return_value=snapshot), wait_fresh=fresh, settle_input_geometry=settle)(page, 'send', touch)
                self.assertEqual(events[0], ('scroll', ('() => window.scrollTo({left: scrollX, top: scrollY, behavior: "instant"})',)))
                self.assertEqual(events[1][0], 'settle')
                self.assertEqual(events[2], ('scroll', ('(delta) => window.scrollBy({top: delta, behavior: "instant"})', 1390)))
                self.assertEqual(events[3][0], 'settle')
                self.assertEqual(events[4], ('tap' if touch else 'click', (540, 450)))
                self.assertEqual(events[5][0], 'fresh')
                self.assertEqual(page.locator.return_value.bounding_box.call_count, 2)
                fresh.assert_called_once_with(page, snapshot)

    def test_failed_wait_reports_the_actual_condition(self):
        page = Mock();page.wait_for_function.side_effect = TimeoutError()
        with self.assertRaisesRegex(AssertionError, 'sent===6.*TimeoutError'):
            helper('wait', state=Mock())(page, 'window.__parcelState.sent===6')

    def test_fresh_gate_requires_new_publication_and_elapsed_process_frames(self):
        wait=Mock();view=Mock()
        helper('wait_fresh',wait=wait)(view,{'publication_id':7,'process_frame':20},frames=6)
        self.assertEqual(wait.call_args.args,(view,'window.__parcelState.publication_id>7 && window.__parcelState.process_frame>=26'))

    def receipt(self, **changes):
        result={'draw_id':3,'draw_frame':8,'language':'zh','labels':['包裹转辙场','下一件包裹','港口','花园','市场'],'missing_translations':[],'missing_glyphs':[]};result.update(changes);return result

    def verify(self, receipt):
        state=Mock(side_effect=[{'draw_receipt':{'draw_id':2}}, {'language':'zh','draw_receipt':receipt}]);wait=Mock()
        result=helper('assert_native_language',state=state,wait=wait)(Mock(),'zh')
        self.assertEqual(wait.call_args.args[1],'window.__parcelState.draw_receipt.draw_id>2')
        return result

    def test_success_requires_actual_new_draw_and_complete_chinese_labels(self):
        self.assertEqual(self.verify(self.receipt()),self.receipt())

    def test_reflow_accepts_completed_draw_against_pre_resize_baseline(self):
        snapshot = {'language': 'zh', 'draw_receipt': self.receipt(draw_id=5)}
        wait = Mock()
        check = helper('assert_native_language', state=Mock(return_value=snapshot), wait=wait)
        self.assertEqual(check(Mock(), 'zh', previous=4), snapshot['draw_receipt'])
        self.assertEqual(wait.call_args.args[1], 'window.__parcelState.draw_receipt.draw_id>4')
        with self.assertRaises(AssertionError): check(Mock(), 'zh', previous=5)

    def test_css_only_reflow_keeps_receipt_validation_without_impossible_draw(self):
        snapshot = {'language': 'zh', 'draw_receipt': self.receipt(draw_id=5)}
        wait = Mock()
        check = helper('assert_native_language', state=Mock(return_value=snapshot), wait=wait)
        self.assertEqual(check(Mock(), 'zh', previous=5, require_new_draw=False), snapshot['draw_receipt'])
        wait.assert_not_called()
        for receipt in [self.receipt(draw_id=4), self.receipt(draw_id=0), self.receipt(draw_id=5, missing_glyphs=[20013]), self.receipt(draw_id=5, language='en')]:
            check = helper('assert_native_language', state=Mock(return_value={'language':'zh','draw_receipt':receipt}), wait=wait)
            with self.subTest(receipt=receipt), self.assertRaises(AssertionError):
                check(Mock(), 'zh', previous=5, require_new_draw=False)

    def test_wrong_language_unrendered_missing_glyph_and_english_fallback_reject(self):
        for changes in [{'language':'en'},{'draw_frame':0},{'missing_glyphs':[12345]},{'missing_translations':['NEXT PARCEL']},{'labels':['Parcel Switchyard']}]:
            with self.subTest(changes=changes),self.assertRaises(AssertionError):self.verify(self.receipt(**changes))

    def _run_geometry_script(self, mode):
        import json
        import subprocess
        view = Mock()
        helper('settle_input_geometry')(view)
        view.locator.assert_called_once_with('#canvas')
        script = view.locator.return_value.evaluate.call_args.args[0]
        runner = r'''
const fs = require('fs'), vm = require('vm');
const {script, mode} = JSON.parse(fs.readFileSync(0, 'utf8'));
(async () => {
  let now = 0, frames = 0, serial = 0, outcome = null;
  const tasks = new Map();
  const schedule = (fn, delay, frame = false) => {
    const id = ++serial; tasks.set(id, {fn, due: now + delay, frame}); return id;
  };
  const parent = {scrollX:0, frameElement:null};
  Object.defineProperty(parent, 'scrollY', {get: () => mode === 'parent-scroll' ? Math.min(frames, 5) * 12 : 0});
  const child = {scrollX:0, scrollY:0};
  const frameElement = {
    ownerDocument:{defaultView:parent},
    getBoundingClientRect:() => ({x:10, y:mode === 'ancestor-moves' ? Math.min(frames, 5) * 20 : 20, width:300, height:600})
  };
  child.frameElement = frameElement;
  const canvas = {
    ownerDocument:{defaultView:child},
    getBoundingClientRect:() => ({
      x:0, y:mode === 'continuous' ? frames * 2 : mode === 'slow-drift' ? frames * 0.2 : 0,
      width:mode === 'zero-canvas' ? 0 : mode === 'nonfinite-canvas' ? NaN : 296, height:542
    })
  };
  const sandbox = {
    performance:{now:() => now},
    requestAnimationFrame:fn => mode === 'stopped-raf' ? ++serial : schedule(fn, 16, true),
    cancelAnimationFrame:id => tasks.delete(id),
    setTimeout:(fn, delay) => schedule(fn, delay),
    clearTimeout:id => tasks.delete(id)
  };
  vm.runInNewContext('(' + script + ')', sandbox)(canvas).then(
    () => {outcome = {status:'resolved'};},
    error => {outcome = {status:'rejected', message:String(error.message)};}
  );
  for (let step = 0; step < 1000 && !outcome; step++) {
    await Promise.resolve();
    if (outcome) break;
    if (!tasks.size) break;
    const [id, task] = [...tasks].sort((a,b) => a[1].due-b[1].due || a[0]-b[0])[0];
    tasks.delete(id); now = task.due;
    if (task.frame) frames++;
    task.fn(now);
  }
  await Promise.resolve();
  process.stdout.write(JSON.stringify({...outcome, status:outcome?.status || 'pending', now, frames}));
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
        result = subprocess.run(['node', '-e', runner], input=json.dumps({'script':script, 'mode':mode}),
                                text=True, capture_output=True, timeout=10, check=True)
        return json.loads(result.stdout)

    def test_geometry_constant_resolves_after_frame_observations(self):
        result = self._run_geometry_script('constant')
        self.assertEqual(result['status'], 'resolved', result)
        self.assertGreaterEqual(result['frames'], 3)
        self.assertLess(result['now'], 5000)

    def test_geometry_ancestor_motion_and_parent_scroll_reset_stability(self):
        for mode in ['ancestor-moves', 'parent-scroll']:
            with self.subTest(mode=mode):
                result = self._run_geometry_script(mode)
                self.assertEqual(result['status'], 'resolved', result)
                self.assertGreaterEqual(result['frames'], 7, result)
                self.assertLess(result['now'], 5000)

    def test_geometry_cumulative_subpixel_drift_cannot_pass(self):
        result = self._run_geometry_script('slow-drift')
        self.assertEqual(result['status'], 'rejected', result)
        self.assertIn('did not settle', result['message'])
        self.assertGreaterEqual(result['now'], 5000)
        self.assertLessEqual(result['now'], 5020)

    def test_geometry_continuous_motion_times_out(self):
        result = self._run_geometry_script('continuous')
        self.assertEqual(result['status'], 'rejected', result)
        self.assertIn('did not settle', result['message'])
        self.assertGreaterEqual(result['now'], 5000)
        self.assertLessEqual(result['now'], 5020)

    def test_geometry_watchdog_rejects_when_animation_frames_stop(self):
        result = self._run_geometry_script('stopped-raf')
        self.assertEqual(result['status'], 'rejected', result)
        self.assertIn('did not settle', result['message'])
        self.assertEqual(result['frames'], 0)
        self.assertEqual(result['now'], 5000)

    def test_geometry_invalid_canvas_is_rejected(self):
        for mode in ['zero-canvas', 'nonfinite-canvas']:
            with self.subTest(mode=mode):
                result = self._run_geometry_script(mode)
                self.assertEqual(result['status'], 'rejected', result)
                self.assertIn('Invalid input geometry', result['message'])


if __name__=='__main__':unittest.main()
