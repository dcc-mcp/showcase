"""Host-free regressions for passive fresh-frame and native-language gates."""
import ast
import re
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from localization import LOCALES


def helper(name, **namespace):
    source=Path(__file__).with_name('browser_test.py')
    node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
    return namespace[name]


class ObserverGuards(unittest.TestCase):
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
            helper('target', state=Mock(return_value=snapshot), wait_fresh=fresh)(page, 'send', touch, repetitions=8)
            self.assertEqual([event[0] for event in events], [('tap' if touch else 'click')] * 8 + ['fresh'])
            self.assertTrue(all(event[1] == (140, 125) for event in events[:8]))
            fresh.assert_called_once_with(page, snapshot)
            page.evaluate.assert_not_called()

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

    def test_wrong_language_unrendered_missing_glyph_and_english_fallback_reject(self):
        for changes in [{'language':'en'},{'draw_frame':0},{'missing_glyphs':[12345]},{'missing_translations':['NEXT PARCEL']},{'labels':['Parcel Switchyard']}]:
            with self.subTest(changes=changes),self.assertRaises(AssertionError):self.verify(self.receipt(**changes))


if __name__=='__main__':unittest.main()
