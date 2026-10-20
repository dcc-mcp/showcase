import importlib.util,json,sys,unittest
from pathlib import Path
PATH=Path(__file__).resolve().parents[1]/'promote.py'
spec=importlib.util.spec_from_file_location('dawnkeep_promote',PATH);promote=importlib.util.module_from_spec(spec);spec.loader.exec_module(promote)
class Promotion(unittest.TestCase):
    def page(self):
        config={'ensureCrossOriginIsolationHeaders':False,'emscriptenPoolSize':0,'godotPoolSize':0,'executable':'index','fileSizes':{'index.wasm':37700666,'index.pck':5325512}}
        return '<script src="index.js"></script>\nconst GODOT_CONFIG = '+json.dumps(config)+';\nconst dawnkeepShell = window.DawnkeepShell.attach(GODOT_CONFIG,()=>engine.requestQuit());\n dawnkeepShell.failed(err);'
    def test_only_explicit_shared_engine_and_hash_named_pack(self):
        text,config=promote.public_html(self.page())
        self.assertEqual(config['mainPack'],'dawnkeep-649ccf7ed6a7.pck')
        self.assertEqual(config['executable'],'../runtime/godot-4.6.3')
        self.assertEqual(config['fileSizes']['../runtime/godot-4.6.3.wasm'],37700666)
        self.assertIn('DawnkeepPublication.attach(GODOT_CONFIG)',text)
        self.assertIn('dawnkeepPublication.failed()',text)
        self.assertNotIn('src="index.js"',text)
    def test_changed_official_shell_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'marker changed'):promote.public_html(self.page().replace(' dawnkeepShell.failed(err);',''))
    def test_thread_configuration_cannot_be_promoted(self):
        with self.assertRaisesRegex(ValueError,'single-thread'):promote.public_html(self.page().replace('"emscriptenPoolSize": 0','"emscriptenPoolSize": 1'))
if __name__=='__main__':unittest.main()
