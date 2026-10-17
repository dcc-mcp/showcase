"""Game discovery, routing and hash-bound audio evidence contracts."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import games
import localization
import preview_audio
from test_build_site import fixture_case, make_png


class GamePages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        folder = self.root / 'docs/showcase/sample-case'
        folder.mkdir(parents=True)
        (folder / 'cover.png').write_bytes(make_png(120, 80))
        self.case = fixture_case()
        self.demo = {'url':'play/sample-case/index.html', 'engine':'Godot 4.6.3',
                     'controls':{'zh':'Tap controls'}, 'notes':{'zh':'No tracking'}}

    def test_only_manifest_selected_cases_get_games(self):
        self.assertEqual('', games.shelf([self.case], {}, str(self.root)))
        self.assertEqual({}, games.pages([self.case], {}, str(self.root)))
        shelf = games.shelf([self.case], {'sample-case':self.demo}, str(self.root))
        self.assertIn('data-game-launch="sample-case"', shelf)
        self.assertIn('href="games/sample-case/"', shelf)
        self.assertNotIn('<iframe', shelf)
        self.assertNotIn('.wasm', shelf)

    def test_game_page_is_static_until_explicit_intent(self):
        page = games.pages([self.case], {'sample-case':self.demo}, str(self.root))['games/sample-case/index.html']
        self.assertNotIn('<iframe', page)
        self.assertNotIn('autoplay', page)
        self.assertIn('data-game-url="../../play/sample-case/index.html"', page)
        self.assertIn('data-game-exit', page)
        self.assertIn('data-game-reset', page)
        self.assertIn('more-games', page)
        self.assertIn('cases/sample-case/', page)
        self.assertNotIn('<script>alert', page)

    def test_game_runtime_path_is_shared_and_language_link_keeps_page(self):
        parser = localization.LocalizedHTML('games/sample-case/index.html','zh',
            {'games/sample-case/index.html','index.html'}, {})
        self.assertEqual('../../../play/sample-case/index.html', parser.url('../../play/sample-case/index.html'))
        self.assertEqual('../../#games', parser.url('../../#games'))

    def test_native_language_notes_are_accurate_in_both_page_locales(self):
        notes = {
            'en': ('原作画面与游戏内文字保留英文，页面和操作说明提供中英文。',
                   'The original artwork and in-game text remain in English. This page and the instructions are available in English and Chinese.'),
            'en-zh': ('游戏内文字提供英文与简体中文。',
                      'In-game text is available in English and Simplified Chinese.'),
        }
        root = Path(__file__).resolve().parents[1]
        path = 'games/sample-case/index.html'
        page_paths = {'index.html', path, 'cases/sample-case/index.html'}
        for language, (chinese, english) in notes.items():
            self.demo['nativeTextLanguage'] = language
            page = games.pages([self.case], {'sample-case': self.demo}, str(self.root))[path]
            self.assertEqual(page.count('class="game-language-note"'), 1)
            self.assertIn(chinese, page)
            for locale, expected in (('en', english), ('zh', chinese)):
                with self.subTest(native_language=language, page_locale=locale):
                    parser = localization.LocalizedHTML(
                        path, locale, page_paths, localization.catalog(root, locale=locale))
                    parser.feed(page)
                    parser.close()
                    self.assertFalse(parser.missing)
                    rendered = ''.join(parser.output)
                    self.assertIn('<p class="game-language-note">' + expected + '</p>', rendered)
                    other = notes['en-zh' if language == 'en' else 'en']
                    self.assertNotIn(other[0], rendered)
                    self.assertNotIn(other[1], rendered)
                    self.assertNotIn('<iframe', rendered)
                    self.assertNotIn('autoplay', rendered)

    def test_bilingual_language_note_requires_its_exact_translation(self):
        self.demo['nativeTextLanguage'] = 'en-zh'
        path = 'games/sample-case/index.html'
        page = games.pages([self.case], {'sample-case': self.demo}, str(self.root))[path]
        translations = localization.catalog(Path(__file__).resolve().parents[1])
        del translations['游戏内文字提供英文与简体中文。']
        parser = localization.LocalizedHTML(path, 'en', {path, 'index.html'}, translations)
        parser.feed(page)
        parser.close()
        self.assertEqual(parser.missing, {'游戏内文字提供英文与简体中文。'})

    def test_audio_unknown_is_not_silent_and_hash_mismatch_blocks(self):
        self.assertEqual({}, preview_audio.read(self.root))
        source=self.root / 'test.mp4';source.write_bytes(b'fixture')
        catalog=self.root / 'assets/preview-audio.json';catalog.parent.mkdir()
        data={'schema_version':1,'files':[{'src':'test.mp4','sha256':hashlib.sha256(b'fixture').hexdigest(),'has_audio':None}]}
        catalog.write_text(json.dumps(data));self.assertEqual({'test.mp4':'unknown'},preview_audio.read(self.root))
        data['files'][0]['has_audio']=False;catalog.write_text(json.dumps(data));self.assertEqual({'test.mp4':'false'},preview_audio.read(self.root))
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'stale'):
            preview_audio.read(self.root)


if __name__ == '__main__':
    unittest.main()
