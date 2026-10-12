"""Static locale routing, escaping and fail-closed translation guards."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import localization as i18n


class LocaleGuards(unittest.TestCase):
    def render(self, markup, path='cases/sample/index.html', locale='en', translations=None):
        pages = {'index.html', 'cases/sample/index.html', 'brands/index.html'}
        parser = i18n.LocalizedHTML(path, locale, pages, translations or {'标题': 'Title', '说明': 'Description'})
        parser.feed(markup)
        parser.close()
        return ''.join(parser.output), parser.missing

    def test_translates_content_attributes_and_structured_data(self):
        markup = '<html lang="zh-CN"><head><meta property="og:locale" content="zh_CN"><script type="application/ld+json">{"name":"标题","inLanguage":"zh-CN","url":"https://dcc-mcp.github.io/showcase/cases/sample/"}</script></head><body><h1>标题</h1><img alt="说明" src="../../docs/hero.png"></body></html>'
        result, missing = self.render(markup)
        self.assertFalse(missing)
        self.assertIn('<html lang="en">', result)
        self.assertIn('content="en_US"', result)
        self.assertIn('"name":"Title"', result)
        self.assertIn('alt="Description"', result)
        self.assertIn('hreflang="zh-CN"', result)
        self.assertIn('hreflang="x-default"', result)

    def test_locale_routes_and_shared_assets_are_not_confused(self):
        markup = '<html><head></head><header><a href="../../#works">说明</a><a href="../../brands/">说明</a></header><img src="../../docs/hero.png" alt="说明"><a href="../../docs/source.zip">说明</a><a href="https://dcc-mcp.github.io/zh/agents">说明</a></html>'
        result, missing = self.render(markup, locale='zh')
        self.assertFalse(missing)
        self.assertIn('href="../../#works"', result)
        self.assertIn('href="../../brands/"', result)
        self.assertIn('src="../../../docs/hero.png"', result)
        self.assertIn('href="../../../docs/source.zip"', result)
        self.assertIn('href="../../../cases/sample/" data-locale-link="en"', result)
        self.assertIn('href="https://dcc-mcp.github.io/zh/agents"', result)
        english, _ = self.render(markup)
        self.assertIn('href="https://dcc-mcp.github.io/agents"', english)

    def test_machine_identifiers_remain_stable(self):
        result, missing = self.render('<button data-value="标题">标题</button><article data-search="说明" data-capabilities="[&quot;标题&quot;]"></article><code>typed_render.render</code>')
        self.assertFalse(missing)
        self.assertIn('data-value="标题"', result)
        self.assertIn('data-capabilities="[&quot;标题&quot;]"', result)
        self.assertIn('typed_render.render', result)

    def test_encoded_asset_names_and_pages_mount(self):
        result, _ = self.render('<img src="../../docs/a%23b%3Fc.svg"><link href="/showcase/assets/site.css"><a href="/showcase/brands/">说明</a>', locale='zh')
        self.assertIn('src="../../../docs/a%23b%3Fc.svg"', result)
        self.assertIn('href="../../../assets/site.css"', result)
        self.assertIn('href="../../brands/"', result)

    def test_raw_text_css_is_preserved(self):
        source = '<style>.a>b{content:"a&b"}</style>'
        result, _ = self.render(source)
        self.assertEqual(result, source)

    def test_entities_form_one_source_text_and_output_is_escaped(self):
        result, missing = self.render('<h1>标题 &amp; 说明</h1>', translations={'标题 & 说明': '<Title> & description'})
        self.assertFalse(missing)
        self.assertEqual(result, '<h1>&lt;Title&gt; &amp; description</h1>')

    def test_script_closing_text_cannot_escape_json_ld(self):
        raw = json.dumps({'name': '标题'})
        result, _ = self.render('<script type="application/ld+json">' + raw + '</script>', translations={'标题': '</script><img src=x>'})
        self.assertEqual(result.count('</script>'), 1)
        self.assertIn('\\u003c/script\\u003e', result)

    def test_changed_copy_is_not_silently_partially_translated(self):
        result, missing = self.render('<p>新标题说明</p>')
        self.assertEqual(missing, {'新标题说明'})

    def test_registered_compositions_require_translated_content(self):
        result, missing = self.render('<a aria-label="查看原尺寸：标题">下一个案例：标题</a>')
        self.assertFalse(missing)
        self.assertIn('View full size: Title', result)
        self.assertIn('Next case: Title', result)
        _, missing = self.render('<a>下一个案例：新标题</a>')
        self.assertIn('新标题', missing)

    def test_bilingual_search_aliases_exist_in_both_languages(self):
        for locale in ('en', 'zh'):
            result, _ = self.render('<article data-search="标题 说明">标题</article>', locale=locale)
            self.assertIn('data-search="标题 说明 Title Description"', result)

    def test_missing_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                i18n.localize_pages(tmp, {'index.html': '<p>Content</p>'})

    def test_english_source_prose_has_chinese_presentation(self):
        source = 'Listening has not been performed.'
        target = '尚未进行主观听评。'
        result, missing = self.render('<p>' + source + '</p><p>：' + source + '</p>', locale='zh', translations={source: target})
        self.assertFalse(missing)
        self.assertEqual(result, '<p>' + target + '</p><p>：' + target + '</p>')

    def test_measurement_json_preserves_keys_numbers_and_hashes(self):
        source = {'name': 'step toggles on', 'pass': True, 'samples': 21168, 'sha256': 'a' * 64}
        markup = '<td>' + json.dumps(source) + '</td>'
        result, _ = self.render(markup, locale='zh', translations={'step toggles on': '步进开启'})
        rendered = json.loads(result.removeprefix('<td>').removesuffix('</td>'))
        self.assertEqual(rendered, dict(source, name='步进开启'))

    def test_chinese_gate_distinguishes_prose_and_technical_keys(self):
        cases = [{'software': ['Godot'], 'limitations': ['Not tested on physical phones.'],
                  'credits': {'license': 'MIT'}, 'environment': [{'label': 'Godot'}],
                  'checks': [{'name': 'web_playable_acceptance', 'observed': json.dumps({'name': 'step toggles on', 'source': 'https://example.com', 'count': 9})}]}]
        self.assertEqual(i18n.required_chinese_sources(cases), {'Not tested on physical phones.', 'step toggles on'})

    def test_unknown_hints_fall_back_to_english(self):
        for value in (None, '', 'de', '../../zh', '<script>', 'EN'):
            self.assertEqual(i18n.normalize_locale(value), 'en')
        for value in ('zh', 'zh-CN', 'ZH-hans'):
            self.assertEqual(i18n.normalize_locale(value), 'zh')

    def test_missing_translation_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'locales'
            folder.mkdir()
            (folder / 'config.json').write_text('{}')
            with patch('localization.catalog', return_value={}):
                with self.assertRaisesRegex(ValueError, 'publication blocked'):
                    i18n.localize_pages(tmp, {'index.html': '<p>漏译</p>'})

    def test_sitemap_has_reciprocal_locales_and_no_redirects(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'locales'
            folder.mkdir()
            (folder / 'config.json').write_text('{}')
            with patch('localization.catalog', return_value={}):
                result = i18n.localize_pages(tmp, {'index.html': '<html><head></head></html>', 'wwise.html': '<p>Moved</p>'})
            self.assertIn('zh/index.html', result)
            self.assertEqual(result['sitemap.xml'].count('<url>'), 2)
            self.assertNotIn('wwise', result['sitemap.xml'])
            self.assertEqual(result['sitemap.xml'].count('hreflang="x-default"'), 2)


if __name__ == '__main__':
    unittest.main()
