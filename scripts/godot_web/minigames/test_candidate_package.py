"""The downloadable review candidate must launch without a separate checkout."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from verify_candidate import verify_candidate


class CandidatePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name)
        self.required = ['README.txt', 'play/minigame-shell.js', 'play/minigame-shell.css',
                         'play/runtime/LICENSE.txt', 'play/runtime/COPYRIGHT.txt',
                         'play/signal-garden/FONT-LICENSE.txt', 'play/signal-garden/game.pck']
        self.required += ['play/runtime/godot-4.6.3' + suffix for suffix in
                          ['.js', '.wasm', '.audio.worklet.js', '.audio.position.worklet.js']]
        for name in self.required:
            path = self.site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        self.config = {'export': {'executable': '../runtime/godot-4.6.3',
                                 'fileSizes': {'../runtime/godot-4.6.3.wasm': 7, 'game.pck': 7}}}
        (self.site / 'export.json').write_text(json.dumps({'pack_sha256': hashlib.sha256(b'fixture').hexdigest()}))
        self.write_page()

    def write_page(self):
        (self.site / 'play/signal-garden/index.html').write_text(
            '<link href="../minigame-shell.css"><script src="../minigame-shell.js"></script>'
            '<script type="application/json" id="game-config">' + json.dumps(self.config) + '</script>')

    def test_complete_package_passes(self):
        self.assertIn('play/runtime/godot-4.6.3.wasm', verify_candidate(self.site))

    def test_each_missing_dependency_fails(self):
        for name in self.required:
            with self.subTest(name=name):
                path = self.site / name
                path.unlink()
                with self.assertRaisesRegex(ValueError, 'Missing candidate dependency'):
                    verify_candidate(self.site)
                path.write_bytes(b'fixture')

    def test_wrong_size_and_pack_hash_fail(self):
        pack = self.site / 'play/signal-garden/game.pck'
        for data, error in [(b'bad', 'size mismatch'), (b'changed', 'hash mismatch')]:
            pack.write_bytes(data)
            with self.assertRaisesRegex(ValueError, error):
                verify_candidate(self.site)

    def test_external_dependency_fails(self):
        self.config['export']['executable'] = '../../../outside'
        self.write_page()
        with self.assertRaisesRegex(ValueError, 'escapes its artifact'):
            verify_candidate(self.site)

    def test_workflow_preserves_the_complete_play_directory(self):
        workflow = Path(__file__).resolve().parents[3] / '.github/workflows/minigames-preview.yml'
        lines = workflow.read_text().splitlines()
        self.assertIn('            ${{ runner.temp }}/minigame-site/play', lines)
        self.assertIn('            ${{ runner.temp }}/minigame-site/README.txt', lines)


if __name__ == '__main__':
    unittest.main()
