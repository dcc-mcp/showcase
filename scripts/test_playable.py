"""Publication and on-demand loading guards for optional Web exports."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import playable


class PlayableGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cases = [{'slug': 'sample'}]
        path = self.root / 'play/sample/index.html'
        path.parent.mkdir(parents=True)
        path.write_text('<!doctype html><title>Demo</title>')
        data = path.read_bytes()
        self.manifest = {'schema_version': 1, 'files': [{'path': 'play/sample/index.html', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}], 'demos': [{'case_slug': 'sample', 'url': 'play/sample/index.html', 'title': 'Sample', 'engine': 'Godot 4.6.3', 'renderer': 'gl_compatibility', 'threads': False, 'localeSupport': ['en', 'zh'], 'nativeTextLanguage': 'en', 'controls': {'en': 'Click', 'zh': '点击'}, 'notes': {'en': 'No autoplay', 'zh': '不自动播放'}}]}

    def write(self):
        (self.root / 'play/manifest.json').write_text(json.dumps(self.manifest))

    def test_absent_manifest_publishes_nothing(self):
        self.assertEqual(playable.read_and_validate(str(self.root), self.cases), ({}, set()))

    def test_only_verified_inventory_is_selected(self):
        self.write()
        (self.root / 'play/private.txt').write_text('unselected')
        demos, assets = playable.read_and_validate(str(self.root), self.cases)
        self.assertEqual(assets, {'play/manifest.json', 'play/sample/index.html'})
        markup = playable.section(demos['sample'])
        self.assertNotIn('<iframe', markup)
        self.assertNotIn('autoplay', markup)
        self.assertIn('data-play-url="../../play/sample/index.html"', markup)

    def test_invalid_manifests_fail_closed(self):
        mutations = [lambda m: m['files'][0].update(sha256='0' * 64),
                     lambda m: m['files'][0].update(bytes=1),
                     lambda m: m['files'][0].update(path='../secret.txt'),
                     lambda m: m['demos'][0].update(case_slug='unselected'),
                     lambda m: m['demos'][0].update(url='play/unselected/index.html'),
                     lambda m: m['demos'][0].update(threads=True),
                     lambda m: m['demos'][0].update(controls={'en': 'Click'})]
        original = json.dumps(self.manifest)
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.manifest = json.loads(original)
                mutate(self.manifest)
                self.write()
                with self.assertRaises((ValueError, OSError)):
                    playable.read_and_validate(str(self.root), self.cases)


if __name__ == '__main__':
    unittest.main()
