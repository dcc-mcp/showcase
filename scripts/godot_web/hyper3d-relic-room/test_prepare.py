import json
from pathlib import Path
import unittest
import importlib.util

spec = importlib.util.spec_from_file_location('relic_prepare', Path(__file__).with_name('prepare.py'))
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class ExportShell(unittest.TestCase):
    def test_optional_default_images_do_not_make_missing_requests(self):
        html = ('<link id="-gd-engine-icon" rel="icon" type="image/png" href="index.icon.png" />\n'
                '<link rel="apple-touch-icon" href="index.apple-touch-icon.png"/>\n'
                '<img id="status-splash" class="show-image--true" src="index.png" alt="">\n'
                '<progress id="status-progress"></progress>\n')
        cleaned = prepare.without_unused_template_images(html)
        self.assertNotIn('index.png', cleaned)
        self.assertNotIn('index.icon.png', cleaned)
        self.assertNotIn('index.apple-touch-icon.png', cleaned)
        self.assertIn('<progress id="status-progress">', cleaned)
        self.assertEqual(cleaned, prepare.without_unused_template_images(cleaned))

    def test_real_engine_and_immutable_pack_hooks_are_retained(self):
        config = {'ensureCrossOriginIsolationHeaders': False, 'emscriptenPoolSize': 0,
                  'godotPoolSize': 0, 'fileSizes': {'index.wasm': 100, 'index.pck': 20}}
        html = ('<script src="index.js"></script>\nconst GODOT_CONFIG = ' + json.dumps(config)
                + ';\nconst engine = new Engine(GODOT_CONFIG);\nfunction displayFailureNotice(err) {\n}')
        result, published = prepare.public_html(html, 'relic-abc.pck', 'abc', 'v1')
        self.assertEqual(published['mainPack'], 'relic-abc.pck')
        self.assertIn('../runtime/godot-4.6.3.js', result)
        self.assertIn('engine.requestQuit()', result)
        self.assertIn('relicPublication.failed()', result)


if __name__ == '__main__':
    unittest.main()
