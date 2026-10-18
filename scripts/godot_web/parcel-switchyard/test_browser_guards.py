"""Host-free regressions for passive fresh-frame and native-language gates."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock


def helper(name, **namespace):
    source=Path(__file__).with_name('browser_test.py')
    node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
    return namespace[name]


class ObserverGuards(unittest.TestCase):
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
