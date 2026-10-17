"""Unit guards are isolated; only hosted browser runs establish real playability."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import prepare_review as review


class ReviewInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site, self.native, self.evidence = [self.root / n for n in ('site', 'native', 'evidence')]
        self.project = self.native / 'native/signal-garden'
        for path in (self.site / 'play/signal-garden', self.project, self.evidence):
            path.mkdir(parents=True)
        self.sha = 'a' * 40
        (self.site / 'play/signal-garden/game.pck').write_bytes(b'test-pack-not-real-game')
        files = {}
        for name in review.SOURCE_FILES:
            recipe = {'game.gd': 'signal-garden.gd', 'garden-font.otf': 'garden-font.otf', 'FONT-LICENSE.txt': 'FONT-LICENSE.txt'}.get(name)
            (self.project / name).write_bytes(Path(review.__file__).with_name(recipe).read_bytes() if recipe else ('isolated test fixture ' + name).encode())
            files[name] = review.digest(self.project / name)
        self.author = {'editor_restarted': True, 'native_files': files}
        self.browser = {'passed': True, 'checks': [{'name': n, 'passed': True} for n in sorted(review.REQUIRED_CHECKS)],
                        'pack_sha256': review.digest(self.site / 'play/signal-garden/game.pck')}
        self.write(self.native / 'authoring.json', self.author)
        self.write(self.native / 'native-input.json', {'passed': True})
        self.write(self.site / 'export.json', {'source_files': files})
        self.write(self.evidence / 'verification.json', self.browser)
        self.media = []
        for lang in review.LANGUAGES:
            name = lang + '-native-gameplay-with-audio.mp4'
            (self.evidence / name).write_bytes(b'isolated-video-fixture')
            self.media.append({'file': name, 'sha256': review.digest(self.evidence / name),
                               'full_decode': 'passed', 'playback_speed': 3,
                               'original_complete_recording': lang + '-native-gameplay-with-audio.webm'})
        self.write(self.evidence / 'media-verification.json', self.media)
        self.guard = patch.object(review, 'verify_candidate', return_value=[])
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def write(self, path, data):
        path.write_text(json.dumps(data))

    def validate(self):
        return review.validate_inputs(self.site, self.native, self.evidence, self.sha)

    def test_valid_inputs_check_commit_format_and_bound_bytes(self):
        self.assertEqual(self.validate()[0], self.author)
        for bad in ('main', 'a' * 39, 'a' * 41, 'z' * 40):
            with self.subTest(commit=bad), self.assertRaises(ValueError):
                review.validate_inputs(self.site, self.native, self.evidence, bad)

    def test_changed_native_source_rejected(self):
        (self.project / 'game.gd').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Native source hash mismatch'):
            self.validate()

    def test_wrong_pack_and_failed_browser_rejected(self):
        self.browser['pack_sha256'] = '0' * 64
        self.write(self.evidence / 'verification.json', self.browser)
        with self.assertRaisesRegex(ValueError, 'another pack'):
            self.validate()
        self.browser['checks'][0]['passed'] = False
        self.write(self.evidence / 'verification.json', self.browser)
        with self.assertRaisesRegex(ValueError, 'Browser verification failed'):
            self.validate()

    def test_missing_native_reopen_or_input_rejected(self):
        self.author['editor_restarted'] = False
        self.write(self.native / 'authoring.json', self.author)
        with self.assertRaisesRegex(ValueError, 'restart/reopen'):
            self.validate()
        self.author['editor_restarted'] = True
        self.write(self.native / 'authoring.json', self.author)
        self.write(self.native / 'native-input.json', {'passed': False})
        with self.assertRaisesRegex(ValueError, 'Native input'):
            self.validate()

    def test_self_consistent_stale_recipe_is_rejected(self):
        (self.project / 'game.gd').write_text('another recipe')
        self.author['native_files']['game.gd'] = review.digest(self.project / 'game.gd')
        self.write(self.native / 'authoring.json', self.author)
        self.write(self.site / 'export.json', {'source_files': self.author['native_files']})
        with self.assertRaisesRegex(ValueError, 'checked-out recipe'):
            self.validate()

    def test_each_required_startup_and_garden_check_is_mandatory(self):
        complete = self.browser['checks']
        for missing in sorted(review.REQUIRED_CHECKS):
            with self.subTest(missing=missing):
                self.browser['checks'] = [c for c in complete if c['name'] != missing]
                self.write(self.evidence / 'verification.json', self.browser)
                with self.assertRaisesRegex(ValueError, 'Incomplete real game'):
                    self.validate()

    def test_media_hash_and_traversal_rejected(self):
        self.media[0]['original_complete_recording'] = '../private.webm'
        self.write(self.evidence / 'media-verification.json', self.media)
        with self.assertRaisesRegex(ValueError, 'recording path'):
            self.validate()
        self.media[0]['sha256'] = '0' * 64
        self.write(self.evidence / 'media-verification.json', self.media)
        with self.assertRaisesRegex(ValueError, 'Media verification mismatch'):
            self.validate()

    def test_remux_packet_identity_rejects_content_and_timing_changes(self):
        before = [{'data_hash': 'SHA256:a', 'pts_time': '0.095000', 'dts_time': '0.095000'},
                  {'data_hash': 'SHA256:b', 'pts_time': '0.195000', 'dts_time': '0.195000', 'duration_time': '0.060000'}]
        self.assertEqual(review.verify_packet_identity(before, before)['packets'], 2)
        populated = [dict(p) for p in before]
        populated[0]['duration_time'] = '0.001000'
        self.assertEqual(review.verify_packet_identity(before, populated)['packets'], 2)
        for bad in ([before[0]], list(reversed(before)),
                    [dict(before[0], data_hash='SHA256:c'), before[1]],
                    [dict(before[0], pts_time='0.196000'), before[1]],
                    [dict(before[0], dts_time='0.000000'), before[1]],
                    [before[0], dict(before[1], duration_time='0.061000')]):
            with self.subTest(changed=bad), self.assertRaises(ValueError):
                review.verify_packet_identity(before, bad)

    def test_pages_keep_review_and_listening_boundaries(self):
        for lang in review.LANGUAGES:
            text = review.page(lang)
            self.assertIn('noindex,nofollow', text)
            self.assertIn('?lang=' + lang, text)
            self.assertIn('id="listening-boundary"', text)
            self.assertIn('id="remaining"', text)
            self.assertNotIn('autoplay', text)
            self.assertIn(lang + '-listening.wav', text)
            self.assertIn('not tested' if lang == 'en' else '未验收', text)
        self.assertIn('href="../play/', review.page('zh'))
        self.assertIn('href="zh/index.html"', review.page('en'))

    def test_download_instructions_require_byte_range_media_host(self):
        text = review.review_instructions()
        for required in ('206 responses', 'QuietHandler', '127.0.0.1',
                         '/path/to/minigame-site', 'does not provide them',
                         'No subjective listening or public release approval'):
            self.assertIn(required, text)


if __name__ == '__main__':
    unittest.main()
