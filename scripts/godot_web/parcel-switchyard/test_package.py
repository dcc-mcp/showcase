#!/usr/bin/env python3
"""Structural integrity tests only; these are not browser or visual acceptance."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / 'scripts/godot_web/projects/parcel-switchyard'
PLAY = ROOT / 'play/parcel-switchyard'


class PackageTests(unittest.TestCase):
    def test_original_source_is_identical(self):
        self.assertEqual((PROJECT / 'parcel_game.gd').read_bytes(), (ROOT / 'docs/showcase/parcel-switchyard/native/parcel_game.gd').read_bytes())

    def test_provenance_hashes(self):
        provenance = json.loads((PLAY / 'export-provenance.json').read_text())
        for entry in provenance['source_files'] + provenance['export_files'] + provenance['runtime_files'] + [provenance['original_native_source'], provenance['original_source_archive']]:
            with self.subTest(path=entry['path']):
                path = ROOT / entry['path']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
                self.assertEqual(path.stat().st_size, entry['bytes'])
        self.assertTrue(provenance['native_tests']['passed'])
        self.assertTrue(provenance['exported_pack_reopened_tests']['passed'])
        self.assertGreaterEqual(len(provenance['exported_pack_reopened_tests']['checks']), 118)
        checks = {item['name']: item for item in provenance['exported_pack_reopened_tests']['checks']}
        self.assertTrue(checks['english_full_catalog_glyph_coverage']['pass'])
        self.assertTrue(checks['english_original_latin_metrics_retained']['pass'])
        self.assertEqual(provenance['browser_acceptance']['status'], 'not-tested')
        self.assertFalse(provenance['threads'])
        self.assertFalse(provenance['pwa'])

    def test_official_pack_config(self):
        html = (PLAY / 'index.html').read_text()
        raw = re.search(r'<script id="game-config" type="application/json">(.*?)</script>', html).group(1)
        config = json.loads(raw)
        self.assertEqual(config['showcasePackSha256'], hashlib.sha256((PLAY / 'game.pck').read_bytes()).hexdigest())
        self.assertEqual(config['fileSizes']['game.pck'], (PLAY / 'game.pck').stat().st_size)
        self.assertFalse(config['ensureCrossOriginIsolationHeaders'])
        self.assertEqual(config['godotPoolSize'], 0)
        self.assertEqual(config['emscriptenPoolSize'], 0)
        self.assertEqual((PLAY / 'game.pck').read_bytes()[:4], b'GDPC')

    def test_no_state_injection_in_acceptance(self):
        tests = (ROOT / 'scripts/godot_web/parcel-switchyard/browser_test.py').read_text()
        self.assertNotIn('showcaseCommand', tests)
        self.assertNotRegex(tests, r'__parcelState\s*=(?!=)')
        self.assertIn('page.touchscreen.tap', tests)
        self.assertIn('page.keyboard.press', tests)
        self.assertIn('page.mouse.click', tests)

    def test_shell_uses_engine_before_user_args(self):
        shell = (PLAY / 'shell.js').read_text()
        self.assertIn("args:['--main-pack','game.pck',...options.args]", shell)
        self.assertIn("'game.pck?v='+config.showcasePackSha256", shell)
        self.assertIn('event.source!==parent', shell)
        self.assertIn('event.origin!==location.origin', shell)
        self.assertNotIn('SharedArrayBuffer', shell)
        self.assertNotIn('serviceWorker', shell)

    def test_language_reaches_actual_godot_and_export_contains_catalog(self):
        shell = (PLAY / 'shell.js').read_text()
        self.assertIn("'--lang='+lang", shell)
        preset = (PROJECT / 'export_presets.cfg').read_text()
        self.assertIn('include_filter="translations.json,font-provenance.json,FONT-LICENSE.txt"', preset)
        catalog = json.loads((PROJECT / 'translations.json').read_text())
        self.assertEqual(catalog['Parcel Switchyard'], '包裹转辙场')
        for key in ['HARBOR', 'GARDEN', 'MARKET', 'SEND PARCEL', 'RESUME', 'PAUSE', 'RESET']:
            self.assertRegex(catalog[key], r'[\u3400-\u9fff]')
        font = json.loads((PROJECT / 'font-provenance.json').read_text())
        self.assertEqual(hashlib.sha256((PROJECT / 'parcel-interface.otf').read_bytes()).hexdigest(), font['subset_sha256'])
        self.assertEqual((PROJECT / 'FONT-LICENSE.txt').read_bytes(), (PLAY / 'FONT-LICENSE.txt').read_bytes())


if __name__ == '__main__':
    unittest.main()
