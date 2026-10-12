"""Real desktop/mobile acceptance of every localized public content page.

Serves the Pages /showcase/ mount, blocks outside requests, checks every local
link, renders all media images, and exercises language/filter/theme/copy flows.
"""
from __future__ import annotations

import argparse
from functools import partial
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
from urllib.parse import unquote, urljoin, urlsplit

from browser_preview import QuietHandler, safe_error_text
from localization import LOCALES, SITE, catalog
from validate_brand_gallery import read_and_validate


class MountHandler(QuietHandler):
    def translate_path(self, path):
        if path.startswith('/showcase/'):
            path = path[len('/showcase'):]
        return super().translate_path(path)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.add(values['id'])
        for key in ('href', 'src', 'poster', 'data-dark-src', 'data-light-src'):
            if values.get(key):
                self.links.append(values[key])


def check_links(site, paths):
    parsed = {}
    for path in site.rglob('*.html'):
        item = Links()
        item.feed(path.read_text(encoding='utf-8'))
        parsed[path.relative_to(site).as_posix()] = item
    checked = set()
    for path in paths:
        for link in parsed[path].links:
            url = urljoin(SITE + path, link)
            if not url.startswith(SITE):
                continue
            parts = urlsplit(url)
            relative = unquote(parts.path[len('/showcase/'):])
            if not relative or relative.endswith('/'):
                relative += 'index.html'
            target = site / relative
            if not target.is_file():
                raise AssertionError('Broken local link: ' + path + ' -> ' + relative)
            if parts.fragment and relative in parsed and unquote(parts.fragment) not in parsed[relative].ids:
                raise AssertionError('Broken page anchor: ' + path + ' -> ' + relative + '#' + parts.fragment)
            checked.add(relative)
    return len(checked)


def run(site, output):
    from playwright.sync_api import sync_playwright, expect

    output.mkdir(parents=True, exist_ok=True)
    cases = json.loads(Path('collection.json').read_text(encoding='utf-8'))['cases']
    cases_by_slug = {case['slug']: case for case in cases}
    chinese_copy = catalog(str(Path.cwd()), locale='zh')
    brands, _, problems = read_and_validate(str(Path.cwd()))
    if problems:
        raise ValueError('Invalid brand source catalog')
    brands_by_slug = {item['slug']: item for item in brands.get('items', [])}
    base_paths = ['index.html'] + ['cases/' + case['slug'] + '/index.html' for case in cases]
    if brands.get('enabled'):
        base_paths += ['brands/index.html'] + ['brands/' + item['slug'] + '/index.html' for item in brands['items']]
    all_paths = [settings['prefix'] + path for settings in LOCALES.values() for path in base_paths]
    report = {'status': 'running', 'case_count': len(cases), 'content_pages_per_language': len(base_paths), 'pages': [], 'flows': []}
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(MountHandler, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    base = origin + '/showcase/'
    page = None
    active = 'link audit'
    try:
        report['local_link_targets_checked'] = check_links(site, all_paths)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            report['browser'] = browser.version
            for layout, viewport in (('desktop', {'width': 1440, 'height': 1000}), ('mobile', {'width': 390, 'height': 844})):
                context = browser.new_context(viewport=viewport, reduced_motion='reduce', service_workers='block', accept_downloads=True, permissions=['clipboard-read', 'clipboard-write'])
                errors = []
                def guard(route):
                    if route.request.url.startswith(base):
                        route.continue_()
                    elif route.request.url == origin + '/favicon.ico':
                        route.fulfill(status=204, body='')
                    else:
                        errors.append('Unexpected outside request')
                        route.abort()
                context.route('**/*', guard)
                page = context.new_page()
                page.set_default_timeout(20000)
                page.on('pageerror', lambda _: errors.append('JavaScript error'))
                page.on('response', lambda response: errors.append('HTTP ' + str(response.status)) if response.status >= 400 else None)
                for locale, settings in LOCALES.items():
                    for path in base_paths:
                        active = layout + ' ' + locale + ' ' + path
                        print(active, flush=True)
                        relative = settings['prefix'] + path
                        route_path = relative[:-10]
                        page.goto(base + route_path, wait_until='domcontentloaded')
                        page.evaluate('document.fonts.ready')
                        expect(page.locator('html')).to_have_attribute('lang', settings['lang'])
                        expect(page.locator('.language-switcher a')).to_have_count(2)
                        expect(page.locator('[data-locale-link="' + locale + '"]')).to_have_attribute('aria-current', 'true')
                        expect(page.locator('link[rel="canonical"]')).to_have_attribute('href', SITE + route_path)
                        expect(page.locator('link[hreflang="en"]')).to_have_count(1)
                        expect(page.locator('link[hreflang="zh-CN"]')).to_have_count(1)
                        expect(page.locator('link[hreflang="x-default"]')).to_have_count(1)
                        for other, other_settings in LOCALES.items():
                            expect(page.locator('link[hreflang="' + other_settings['lang'] + '"]')).to_have_attribute('href', SITE + other_settings['prefix'] + path[:-10])
                        expect(page.locator('link[hreflang="x-default"]')).to_have_attribute('href', SITE + path[:-10])
                        structured = json.loads(page.locator('script[type="application/ld+json"]').text_content())
                        assert structured['inLanguage'] == settings['lang'] and structured['url'] == SITE + route_path
                        expect(page.locator('meta[property="og:url"]')).to_have_attribute('content', SITE + route_path)
                        # Force all lazy images to load: every case's intermediate
                        # images and both brand preview themes are real resources.
                        page.evaluate('''async () => { await Promise.all([...document.images].map(async image => {
                            image.loading = 'eager'; await image.decode();
                            if (!image.naturalWidth || !image.alt.trim()) throw new Error('Invalid image or alt');
                        })); }''')
                        if not page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'):
                            raise AssertionError('Horizontal overflow: ' + active)
                        if locale == 'en':
                            untranslated = page.evaluate('''() => {
                                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                                const found=[]; while (walker.nextNode()) {
                                    const node=walker.currentNode, parent=node.parentElement;
                                    if (parent && !parent.closest('script,style,[lang="zh-CN"]') && /[\\u3400-\\u9fff]/.test(node.textContent)) found.push(node.textContent.trim());
                                }
                                for (const el of document.querySelectorAll('[alt],[aria-label],[placeholder]')) {
                                    if (el.closest('[lang="zh-CN"]')) continue;
                                    for (const key of ['alt','aria-label','placeholder']) if (/[\\u3400-\\u9fff]/.test(el.getAttribute(key)||'')) found.push(el.getAttribute(key));
                                }
                                return found;
                            }''')
                            if untranslated:
                                raise AssertionError('Untranslated public text: ' + repr(untranslated))
                        if page.locator('audio,video').count():
                            assert page.locator('audio,video').evaluate_all('(items)=>items.every(x=>x.controls && !x.autoplay && x.paused)')
                        screenshot = locale + '-' + layout + '-' + path.replace('/index.html', '').replace('index.html', 'home').replace('/', '-') + '.png'
                        page.screenshot(path=str(output / screenshot), full_page=path in ('index.html', 'brands/index.html'), animations='disabled')
                        if path.startswith('cases/'):
                            expect(page.locator('#reusable-prompt')).not_to_be_empty()
                            expect(page.locator('.detail-cover img')).to_have_count(1)
                            if locale == 'zh':
                                case = cases_by_slug[path.split('/')[1]]
                                for limitation in case['limitations']:
                                    expect(page.locator('.limitations')).to_contain_text(chinese_copy.get(limitation, limitation))
                                expect(page.locator('.credit-block')).to_contain_text(chinese_copy.get(case['credits']['license'], case['credits']['license']))
                            if locale == 'en':
                                expect(page.locator('.translation-note a')).to_have_attribute('href', re.compile('zh/cases/.*#prompt'))
                        if locale == 'zh' and path.startswith('brands/') and path != 'brands/index.html':
                            for rights in brands_by_slug[path.split('/')[1]]['rights']:
                                expect(page.locator('body')).to_contain_text(chinese_copy.get(rights['notice'], rights['notice']))
                        # Review representative long translated copy beyond the hero.
                        if path in ('cases/prism-tide/index.html', 'brands/dcc-mcp-maya-v2/index.html'):
                            section = '#prompt' if path.startswith('cases/') else '#rights'
                            page.locator(section).evaluate("node => node.scrollIntoView({block: 'start'})")
                            # Capture the actual viewport. Oversized element
                            # screenshots can include fixed, offscreen skip links
                            # outside the viewport and misrepresent visible UI.
                            assert page.locator('.skip-link').evaluate('node => node.getBoundingClientRect().bottom <= 0')
                            page.screenshot(path=str(output / (screenshot[:-4] + '-copy.png')), animations='disabled')
                            if section == '#rights':
                                page.locator('#rights-trademark').evaluate("node => node.scrollIntoView({block: 'start'})")
                                page.screenshot(path=str(output / (screenshot[:-4] + '-trademark.png')), animations='disabled')
                        report['pages'].append({'locale': locale, 'layout': layout, 'path': relative, 'screenshot': screenshot, 'overflow': False, 'images_loaded': page.locator('img').count()})

                    # Search and stable filter values survive a same-page language switch.
                    active = layout + ' ' + locale + ' gallery interactions'
                    home = base + settings['prefix']
                    page.goto(home, wait_until='networkidle')
                    expect(page.locator('.case-card:visible')).to_have_count(len(cases))
                    page.locator('#search').fill('Prism Tide')
                    page.locator('[data-filter="software"] [data-value="Godot"]').click()
                    page.locator('[data-filter="capability"] [data-value="交互"]').click()
                    expect(page.locator('.case-card:visible')).to_have_count(1)
                    page.locator('.skip-link').focus()
                    page.keyboard.press('Enter')
                    opposite = 'zh' if locale == 'en' else 'en'
                    switch = page.locator('[data-locale-link="' + opposite + '"]')
                    switch.focus()
                    page.keyboard.press('Enter')
                    expect(page.locator('html')).to_have_attribute('lang', LOCALES[opposite]['lang'])
                    expect(page.locator('.case-card:visible')).to_have_count(1)
                    assert urlsplit(page.url).fragment == 'works'
                    assert 'q=Prism+Tide' in page.url
                    page.go_back(wait_until='networkidle')
                    expect(page.locator('html')).to_have_attribute('lang', settings['lang'])
                    expect(page.locator('.case-card:visible')).to_have_count(1)
                    page.locator('#reset-filters').click()
                    page.locator('#search').fill('no-result-for-this-query-1234')
                    expect(page.locator('#empty-state')).to_be_visible()
                    page.locator('#empty-reset').click()
                    expect(page.locator('.case-card:visible')).to_have_count(len(cases))
                    if locale == 'en':
                        expect(page.locator('#result-count')).to_have_text('Showing all ' + str(len(cases)) + ' cases')
                        page.locator('#search').fill('optical console')
                        expect(page.locator('.case-card:visible')).to_have_count(1)
                        page.locator('[data-locale-link="zh"]').click()
                        expect(page.locator('.case-card:visible')).to_have_count(1)
                        expect(page.locator('#search')).to_have_value('optical console')
                    active = layout + ' ' + locale + ' clipboard success and refusal'
                    page.goto(home + 'cases/prism-tide/#prompt', wait_until='domcontentloaded')
                    page.locator('#copy-prompt').click()
                    expect(page.locator('#copy-status')).to_have_text('Prompt copied.' if locale == 'en' else '提示词已复制。')
                    assert page.evaluate('navigator.clipboard.readText()') == page.locator('#reusable-prompt').text_content()
                    # Interrupted copy uses a localized, selectable fallback.
                    page.evaluate('() => { navigator.clipboard.writeText = async () => { throw new Error("Test denied"); }; }')
                    page.locator('#copy-prompt').click()
                    expect(page.locator('#copy-status')).to_have_text('Prompt selected. Use your copy shortcut.' if locale == 'en' else '已选中提示词，请使用复制快捷键。')
                    assert page.evaluate('getSelection().toString()') == page.locator('#reusable-prompt').text_content()
                    active = layout + ' ' + locale + ' brand theme and Back'
                    page.goto(home + 'brands/', wait_until='networkidle')
                    page.locator('[data-brand-theme="light"]').click()
                    expect(page.locator('[data-brand-theme="light"]')).to_have_attribute('aria-pressed', 'true')
                    page.locator('#brand-search').fill('Blender')
                    expect(page.locator('[data-brand-card]:visible')).to_have_count(1)
                    page.locator('[data-brand-card]:visible .brand-detail-link').first.click()
                    assert 'theme=light' in page.url
                    page.locator('[data-brand-back]').first.click()
                    expect(page.locator('#brand-search')).to_have_value('Blender')
                    page.locator('#brand-reset').click()
                    report['flows'].append({'locale': locale, 'layout': layout, 'search_filter_empty_reset': True, 'keyboard_language_switch_query_hash_back': True, 'copy_success_and_denied_fallback': True, 'brand_theme_and_back': True})
                if errors:
                    raise AssertionError(repr(errors))
                context.close()
            # The content, alternate language links and source downloads also
            # remain navigable without JavaScript.
            active = 'no-JavaScript navigation'
            context = browser.new_context(java_script_enabled=False, viewport={'width': 390, 'height': 844})
            page = context.new_page()
            for prefix, language in (('', 'en'), ('zh/', 'zh-CN')):
                page.goto(base + prefix, wait_until='load')
                expect(page.locator('.case-card')).to_have_count(len(cases))
                page.locator('.case-card a').first.click()
                expect(page.locator('html')).to_have_attribute('lang', language)
                expect(page.locator('#reusable-prompt')).to_be_visible()
                expect(page.locator('.language-switcher')).to_be_visible()
                expect(page.locator('.engineering-file a').first).to_have_attribute('href', re.compile('.+'))
            context.close()
            browser.close()
        report['status'] = 'passed'
        return 0
    except Exception as error:
        report.update(status='failed', stage=active, error=safe_error_text(error, origin))
        if page:
            try:
                page.screenshot(path=str(output / 'failure.png'), full_page=True)
            except Exception:
                pass
        raise
    finally:
        server.shutdown()
        (output / 'localization-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.site, args.output))
