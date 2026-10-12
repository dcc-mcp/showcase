"""Static English/Chinese pages with exact, fail-closed source-text catalogs.

The original collection and producer evidence stay authoritative and unchanged.
Only presentation text and known page URLs are localized; technical identifiers,
filter values, media bytes, hashes and downloadable sources are not translated.
"""
from __future__ import annotations

import html
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import re
from urllib.parse import urlsplit, urlunsplit, unquote, quote

SITE = 'https://dcc-mcp.github.io/showcase/'
OFFICIAL = 'https://dcc-mcp.github.io'
LOCALES = {'en': {'lang': 'en', 'label': 'English', 'og': 'en_US', 'prefix': ''},
           'zh': {'lang': 'zh-CN', 'label': '简体中文', 'og': 'zh_CN', 'prefix': 'zh/'}}
CJK = re.compile('[\u3400-\u9fff]')
TEXT_ATTRS = {'alt', 'aria-label', 'title', 'placeholder', 'data-dark-alt', 'data-light-alt'}
URL_ATTRS = {'href', 'src', 'poster', 'data-dark-src', 'data-light-src', 'data-play-url'}


def normalize_locale(value):
    """Unsupported language hints deterministically fall back to English."""
    return 'zh' if str(value).lower() in ('zh', 'zh-cn', 'zh-hans') else 'en'


def localized_path(path, locale):
    return LOCALES[locale]['prefix'] + path


def route(path):
    return path[:-10] if path.endswith('index.html') else path


def required_chinese_sources(cases):
    """Natural-language source fields must have Chinese presentation entries.

    This schema-aware gate handles the collection's mixed Chinese/English
    source records without guessing that software/API identifiers are prose.
    """
    technical_labels = {software for case in cases for software in case['software']}
    technical_labels.update({'Core / CLI / Gateway', 'Core / Server / CLI', 'Core / SDK',
                             'Kdenlive / MLT', 'OpenSCAD', 'FreeCAD', 'ParaView', 'GIMP',
                             'DCC-MCP Core', 'DCC-MCP Gateway / CLI'})
    fields = {'subtitle', 'summary', 'goal', 'evidence_scope', 'evidence_label',
              'description', 'note', 'notice', 'basis', 'scope', 'change', 'license', 'text', 'stage'}
    required = set()
    def walk(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, path + (key,))
        elif isinstance(value, list):
            for child in value:
                walk(child, path + ('[]',))
        elif isinstance(value, str) and value.strip() and not CJK.search(value):
            key = path[-1]
            if value.startswith(('https://', 'http://', 'docs/', 'play/')) or re.fullmatch('[a-fA-F0-9]{7,64}', value):
                return
            if key == 'license' and (re.fullmatch('[A-Za-z0-9.+-]+', value) or value == 'SIL Open Font License 1.1'):
                return  # SPDX identifiers are not prose.
            if key == 'name' and re.fullmatch('[a-z0-9]+(?:_[a-z0-9]+)+', value):
                return  # Machine-readable check identifiers stay stable.
            prose = key in fields or 'limitations' in path or key == 'observed'
            prose = prose or (key in ('name', 'source') and 'checks' in path)
            if key == 'label' and value not in technical_labels and not re.fullmatch('[A-Z0-9 /._-]+', value):
                prose = True
            if not prose or not re.search('[A-Za-z]', value):
                return
            if value.lstrip().startswith(('{', '[', '"')):
                try:
                    parsed = json.loads(value)
                except (ValueError, TypeError):
                    pass
                else:
                    if isinstance(parsed, str):
                        walk(parsed, path)
                    else:
                        walk(parsed, path + ('json',))
                    return
            required.add(value)
    for case in cases:
        walk(case, ())
    return required


def catalog(root, demos=None, locale="en"):
    folder = Path(root) / 'locales'
    config = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
    if config != {'schema_version': 1, 'default_locale': 'en', 'locales': ['en', 'zh'], 'source_locale': 'zh'}:
        raise ValueError('unsupported localization configuration')
    result = {}
    # Exact source text acts as the key. New or changed copy needs a new review.
    for path in sorted((folder / locale).rglob('*.json')):
        rows = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(rows, dict):
            raise ValueError('translation catalogs must be source-text dictionaries')
        for source, target in rows.items():
            if not isinstance(target, str) or not source.strip() or not target.strip() or (locale == 'en' and CJK.search(target)):
                raise ValueError('invalid translation in ' + path.name)
            if source in result and result[source] != target:
                raise ValueError('conflicting translation for ' + repr(source))
            result[source] = target
    collection = json.loads((Path(root) / 'collection.json').read_text(encoding='utf-8'))
    for case in collection['cases']:
        title, subtitle, summary = case['title'], case['subtitle'], case['summary']
        if locale == 'en' and title in result and subtitle in result:
            result[title + ' · ' + subtitle + ' | DCC-MCP Showcase'] = result[title] + ' · ' + result[subtitle] + ' | DCC-MCP Showcase'
        if locale == 'en' and summary in result:
            result[summary[:220]] = result[summary]
    if locale == 'zh':
        missing = required_chinese_sources(collection['cases']) - result.keys()
        if missing:
            raise ValueError('Missing Chinese source translations (publication blocked):\n' + '\n'.join(sorted(missing)))
    for demo in (demos or {}).values():
        for key in ('controls', 'notes'):
            result[demo[key]['zh' if locale == 'en' else 'en']] = demo[key][locale]
    return result


class LocalizedHTML(HTMLParser):
    def __init__(self, path, locale, pages, translations):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.locale = locale
        self.destination = localized_path(path, locale)
        self.pages = pages
        self.translations = translations
        self.output = []
        self.missing = set()
        self.script = None
        self.script_data = []

    def text(self, value):
        stripped = value.strip()
        start = len(value) - len(value.lstrip())
        end = len(value.rstrip())
        if stripped in self.translations:
            return value[:start] + self.translations[stripped] + value[end:]
        if self.locale == 'zh':
            # A subset of the original case records is English. Localize that
            # prose too, while preserving measurement JSON keys and numbers.
            if stripped.startswith(('{', '[', '"')):
                try:
                    parsed = json.loads(stripped)
                except (ValueError, TypeError):
                    pass
                else:
                    def translate_json(item):
                        if isinstance(item, dict):
                            return {key: translate_json(child) for key, child in item.items()}
                        if isinstance(item, list):
                            return [translate_json(child) for child in item]
                        return self.text(item) if isinstance(item, str) else item
                    translated = translate_json(parsed)
                    if translated != parsed:
                        return value[:start] + json.dumps(translated, ensure_ascii=False) + value[end:]
            if stripped.startswith('：'):
                return value[:start] + '：' + self.text(stripped[1:]) + value[end:]
            return value
        if not CJK.search(value):
            return value
        prefixes = {'查看原尺寸：': 'View full size: ', '查看案例：': 'View case: ',
                    '下一个案例：': 'Next case: ', '：': ': '}
        for source, target in prefixes.items():
            if stripped.startswith(source):
                rest = stripped[len(source):]
                translated = self.text(rest)
                if not CJK.search(translated):
                    return value[:start] + target + translated + value[end:]
        formats = [(r'(\d+) 个案例', '{} cases'), (r'(\d+) 种软件', '{} applications'),
                   (r'显示全部 (\d+) 个案例', 'Showing all {} cases'),
                   (r'最近审阅：([0-9TZ:.+\-]+)', 'Last reviewed: {}')]
        for pattern, template in formats:
            match = re.fullmatch(pattern, stripped)
            if match:
                return template.format(*match.groups())
        self.missing.add(stripped)
        return value

    def url(self, value):
        parsed = urlsplit(value)
        if value.startswith(SITE):
            suffix = value[len(SITE):]
            p = urlsplit(suffix)
            key = p.path + 'index.html' if not p.path or p.path.endswith('/') else p.path
            if key in self.pages:
                return SITE + route(localized_path(key, self.locale)) + ('?' + p.query if p.query else '') + ('#' + p.fragment if p.fragment else '')
            return value
        if parsed.scheme or parsed.netloc:
            if parsed.scheme == 'https' and parsed.netloc == 'dcc-mcp.github.io':
                path = parsed.path
                if path.startswith('/zh/'):
                    path = path[3:]
                # These are the verified bilingual official routes linked here.
                if path in ('/', '/agents', '/why-dcc-mcp', '/examples', '/examples/wwise'):
                    if self.locale == 'zh':
                        path = '/zh' + path
                    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
            return value
        if not parsed.path:
            return value
        if parsed.path.startswith('/showcase/'):
            resolved = posixpath.normpath(unquote(parsed.path[len('/showcase/'):]))
        elif parsed.path.startswith('/'):
            return value
        else:
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(self.path), unquote(parsed.path)))
        if parsed.path.endswith('/') or resolved == '.':
            resolved = (resolved.rstrip('/') + '/' if resolved != '.' else '') + 'index.html'
        target = localized_path(resolved, self.locale) if resolved in self.pages else resolved
        rel = posixpath.relpath(target, posixpath.dirname(self.destination) or '.')
        if parsed.path.endswith('/') or resolved == 'index.html':
            rel = route(rel)
            if not rel:
                rel = './'
        query = parsed.query
        if resolved.startswith('play/') and resolved.endswith('/index.html') and query:
            query = re.sub(r'(^|&)lang=(?:en|zh)(&|$)', lambda m: m[1] + 'lang=' + self.locale + m[2], query)
        return urlunsplit(('', '', quote(rel, safe='/'), query, parsed.fragment))

    def json_value(self, value, key=''):
        if isinstance(value, dict):
            return {k: self.json_value(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [self.json_value(v, key) for v in value]
        if isinstance(value, str):
            if key == 'inLanguage':
                return LOCALES[self.locale]['lang']
            return self.url(value) if value.startswith('https://') else self.text(value)
        return value

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        transformed = []
        for key, value in attributes:
            if value is not None:
                if tag == 'html' and key == 'lang':
                    value = LOCALES[self.locale]['lang']
                elif key in URL_ATTRS:
                    value = self.url(value)
                elif key == 'data-search':
                    # Both locales expose the same bilingual aliases. A query
                    # stays useful after switching language; filter IDs stay raw.
                    aliases = [target for source, target in getattr(self, 'search_translations', self.translations).items() if source in value]
                    value = ' '.join([value] + list(dict.fromkeys(aliases)))
                elif key in TEXT_ATTRS:
                    value = self.text(value)
                elif tag == 'meta' and key == 'content':
                    if attrs.get('property') == 'og:locale':
                        value = LOCALES[self.locale]['og']
                    elif attrs.get('property') in ('og:url', 'og:image') or attrs.get('name') == 'twitter:image':
                        value = self.url(value)
                    elif attrs.get('http-equiv') == 'refresh' and ';url=' in value:
                        delay, url = value.split(';url=', 1)
                        value = delay + ';url=' + self.url(url)
                    else:
                        value = self.text(value)
            transformed.append(key if value is None else '%s="%s"' % (key, html.escape(value, quote=True)))
        self.output.append('<' + tag + (' ' + ' '.join(transformed) if transformed else '') + '>')
        if tag in ('script', 'style'):
            self.script = attrs.get('type', '') if tag == 'script' else '__style__'
            self.script_data = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.output[-1] = self.output[-1][:-1] + ' />'

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.script is not None:
            content = ''.join(self.script_data)
            if self.script == 'application/ld+json':
                value = self.json_value(json.loads(content))
                content = json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            self.output.append(content)
            self.script = None
        if tag == 'head':
            for locale, settings in LOCALES.items():
                href = SITE + route(localized_path(self.path, locale))
                self.output.append('<link rel="alternate" hreflang="%s" href="%s">' % (settings['lang'], href))
            self.output.append('<link rel="alternate" hreflang="x-default" href="%s">' % (SITE + route(self.path)))
            self.output.append('<script src="%s" defer></script>' % self.url(posixpath.relpath('assets/locale.js', posixpath.dirname(self.path) or '.')))
        if tag == 'header':
            label = 'Language' if self.locale == 'en' else '语言'
            self.output.append('<nav class="language-switcher" aria-label="%s">' % label)
            for locale, settings in LOCALES.items():
                href = posixpath.relpath(localized_path(self.path, locale), posixpath.dirname(self.destination) or '.')
                href = route(href) or './'
                current = ' aria-current="true"' if locale == self.locale else ''
                self.output.append('<a href="%s" data-locale-link="%s" lang="%s" hreflang="%s"%s>%s</a>' % (href, locale, settings['lang'], settings['lang'], current, settings['label']))
            self.output.append('</nav>')
        self.output.append('</' + tag + '>')

    def handle_data(self, value):
        if self.script is not None:
            self.script_data.append(value)
        else:
            self.output.append(html.escape(self.text(value), quote=False))

    def handle_entityref(self, name):
        # Keep entities byte-for-byte unless part of script data.
        value = '&' + name + ';'
        (self.script_data if self.script is not None else self.output).append(value)

    def handle_charref(self, name):
        value = '&#' + name + ';'
        (self.script_data if self.script is not None else self.output).append(value)

    def handle_comment(self, value):
        self.output.append('<!--' + value + '-->')

    def handle_decl(self, value):
        self.output.append('<!' + value + '>')


def localize_pages(root, original_pages, demos=None, brands=None):
    translations = {locale: catalog(root, demos, locale) for locale in LOCALES}
    missing_brands = required_chinese_sources((brands or {}).get('items', [])) - translations['zh'].keys()
    if missing_brands:
        raise ValueError('Missing Chinese brand translations (publication blocked):\n' + '\n'.join(sorted(missing_brands)))
    source_pages = {path for path in original_pages if path.endswith('.html')}
    result = {path: content for path, content in original_pages.items() if path not in source_pages}
    missing = {}
    for path in sorted(source_pages):
        for locale in LOCALES:
            parser = LocalizedHTML(path, locale, source_pages, translations[locale])
            parser.search_translations = translations['en']
            parser.feed(original_pages[path])
            parser.close()
            content = ''.join(parser.output)
            if parser.missing:
                missing[path] = sorted(parser.missing)
            if locale == 'en' and path.startswith(('cases/', 'brands/')):
                source_link = posixpath.relpath('zh/' + path, posixpath.dirname(path) or '.')
                source_link = route(source_link) + '#prompt'
                notice = ('<p class="translation-note">English translation. '
                          '<a href="%s" lang="zh-CN">Read the original Chinese text</a>. '
                          'Source evidence, downloads and native artwork retain their original language.</p>') % source_link
                content = content.replace('<section class="detail-section" id="prompt">', notice + '<section class="detail-section" id="prompt">')
            result[localized_path(path, locale)] = content
    if missing:
        details = '\n'.join(path + ': ' + repr(value) for path, values in missing.items() for value in values)
        raise ValueError('Missing English translations (publication blocked):\n' + details)
    indexed = [p for p in sorted(source_pages) if p not in ('wwise/index.html', 'wwise.html')]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for path in indexed:
        for locale in LOCALES:
            xml.append('<url><loc>%s</loc>' % (SITE + route(localized_path(path, locale))))
            for alternate, settings in LOCALES.items():
                xml.append('<xhtml:link rel="alternate" hreflang="%s" href="%s" />' % (settings['lang'], SITE + route(localized_path(path, alternate))))
            xml.append('<xhtml:link rel="alternate" hreflang="x-default" href="%s" /></url>' % (SITE + route(path)))
    xml.append('</urlset>')
    result['sitemap.xml'] = '\n'.join(xml)
    return result
