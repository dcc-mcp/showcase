"""Publication and progressive-enhancement contracts for the artwork gallery."""
import json
from pathlib import Path
import tempfile
import unittest

import build_site as site
import localization as i18n
from test_build_site import fixture_case, make_png


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        folder = self.root / 'docs/showcase/sample-case'
        folder.mkdir(parents=True)
        (folder / 'cover.png').write_bytes(make_png(120, 80))
        self.case = fixture_case()

    def tearDown(self):
        self.tmp.cleanup()

    def test_godot_name_does_not_invent_a_demo(self):
        self.case['software'] = ['Godot']
        self.assertEqual(site.media_kinds(self.case), ['image'])
        self.assertEqual(site.media_kinds(self.case, True), ['interactive'])

    def test_existing_video_is_on_demand_and_stays_muted(self):
        self.case['results'].append({'src': 'docs/showcase/sample-case/real.mp4', 'alt': 'Real video'})
        markup = site.cards_markup([self.case], str(self.root))
        self.assertIn('data-preview-src="docs/showcase/sample-case/real.mp4"', markup)
        self.assertIn('muted playsinline preload="none"', markup)
        self.assertNotIn('<source', markup)
        self.assertNotIn('autoplay', markup)
        self.assertNotIn('<iframe', markup)
        self.assertIn('class="preview-toggle"', markup)
        self.assertIn('data-loading-label="正在加载预览…"', markup)
        self.assertIn('data-playing-label="静音预览中"', markup)
        self.assertIn('class="preview-hint" aria-hidden="true">悬停即预览</span>', markup)
        self.assertIn(' hidden', markup)
        self.assertIn('href="cases/sample-case/"', markup)

    def test_static_work_has_no_preview_control(self):
        markup = site.cards_markup([self.case], str(self.root))
        self.assertNotIn('card-preview', markup)
        self.assertNotIn('preview-toggle', markup)
        self.assertIn('data-media="[&quot;image&quot;]"', markup)

    def test_data_and_titles_are_escaped(self):
        markup = site.cards_markup([self.case], str(self.root))
        self.assertNotIn('<script>', markup)
        self.assertIn('&lt;script&gt;', markup)

    def test_preview_path_uses_existing_resource_safety(self):
        self.case['results'].append({'src': '../private/secret.mp4'})
        with self.assertRaises(ValueError):
            site.cards_markup([self.case], str(self.root))

    def test_first_media_and_audio_are_not_synthetic(self):
        self.case['results'].append({'src': 'docs/showcase/sample-case/sound.mp3'})
        self.assertEqual(site.media_kinds(self.case), ['audio'])
        self.assertIsNone(site.preview_media(self.case))
        self.case['results'].append({'src': 'docs/showcase/sample-case/clip.webm'})
        self.assertEqual(site.media_kinds(self.case, True), ['video', 'interactive', 'audio'])
        self.assertEqual(site.preview_media(self.case)['src'], 'docs/showcase/sample-case/clip.webm')

    def test_source_evidence_is_visible_outside_the_media_and_escaped(self):
        self.case['evidence_label'] = '<b>Partial excerpt</b> · Not final acceptance'
        self.case['results'].insert(0, {'src': 'docs/showcase/sample-case/partial.mp4', 'alt': 'Partial test video'})
        markup = site.cards_markup([self.case], str(self.root))
        self.assertIn('<p class="card-evidence">&lt;b&gt;Partial excerpt&lt;/b&gt; · Not final acceptance</p>', markup)
        # The evidence is ordinary card text, outside the preview/video layer.
        self.assertGreater(markup.index('class="card-evidence"'), markup.index('class="card-title"'))
        self.assertNotIn('card-evidence" hidden', markup)
        self.assertNotIn('class="sr-only card-evidence"', markup)

    def test_partial_fixture_retains_exact_source_evidence_in_both_locales(self):
        source = '历史成果 · 新镜头仅为未完成阶段证据'
        target = 'Historical artwork · New camera attempt is partial stage evidence'
        self.case['evidence_label'] = source
        self.case['results'].insert(0, {'src': 'docs/showcase/sample-case/partial.mp4', 'alt': 'Partial test video'})
        markup = site.cards_markup([self.case], str(self.root))
        root = str(Path(__file__).resolve().parents[1])
        for locale, expected in [('en', target), ('zh', source)]:
            translations = i18n.catalog(root, locale=locale)
            if locale == 'en':
                translations[source] = target
            parser = i18n.LocalizedHTML('index.html', locale, {'index.html'}, translations)
            parser.feed(markup)
            parser.close()
            self.assertFalse(parser.missing)
            self.assertIn('<p class="card-evidence">' + expected + '</p>', ''.join(parser.output))

    def test_evidence_is_not_inferred_from_video_name_or_duration(self):
        self.case['evidence_label'] = 'Published evidence'
        self.case['results'].insert(0, {'src': 'docs/showcase/sample-case/partial-short.mp4', 'alt': 'A short clip', 'duration': 2.083})
        markup = site.cards_markup([self.case], str(self.root))
        self.assertIn('<p class="card-evidence">Published evidence</p>', markup)
        self.assertNotIn('>Partial excerpt<', markup)

    def test_current_main_assets_are_not_changed_by_rendering(self):
        root = Path(__file__).resolve().parents[1]
        cases = json.loads((root / 'collection.json').read_text())['cases']
        before = json.dumps(cases, sort_keys=True)
        site.cards_markup(cases, str(root), {'sonic-loom': {}})
        self.assertEqual(before, json.dumps(cases, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
