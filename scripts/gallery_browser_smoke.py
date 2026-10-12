#!/usr/bin/env python3
"""Exact-head Chromium acceptance for the artwork gallery (CI preview, not production)."""
from __future__ import annotations

import argparse
import copy
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import threading

from browser_preview import safe_error_text
from localization_browser_smoke import MountHandler


def run(site: Path, output: Path, expected_head: str):
    from playwright.sync_api import sync_playwright, expect
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if expected_head and head != expected_head:
        raise ValueError('Gallery browser candidate does not match expected head')
    output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'running', 'head_sha': head, 'scope': 'isolated-exact-head-ci-preview',
              'mobile_scope': 'Chromium touch viewport emulation, not a physical device', 'checks': [], 'screenshots': []}
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(MountHandler, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    base = origin + '/showcase/'
    source_cases = json.loads(Path('collection.json').read_text(encoding='utf-8'))['cases']
    case_count = len(source_cases)
    errors, requests = [], []
    page = None
    stage = 'launch'
    def checked(name):
        report['checks'].append(name)
        print('PASS ' + name, flush=True)
    def capture(page, filename):
        page.screenshot(path=str(output / filename), animations='disabled')
        report['screenshots'].append(filename)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            report['browser'] = browser.version
            def context(**kwargs):
                ctx = browser.new_context(service_workers='block', **kwargs)
                def guard(route):
                    if route.request.url.startswith(base):
                        requests.append(route.request.url.removeprefix(base))
                        route.continue_()
                    elif route.request.url == origin + '/favicon.ico':
                        route.fulfill(status=204, body='')
                    else:
                        errors.append('Unexpected outside request')
                        route.abort()
                ctx.route('**/*', guard)
                ctx.on('page', lambda pg: pg.on('pageerror', lambda _: errors.append('JavaScript error')))
                return ctx
            ctx = context(viewport={'width': 1486, 'height': 1059})
            page = ctx.new_page()
            page.set_default_timeout(20000)
            def home(prefix=''):
                page.goto(base + prefix, wait_until='networkidle')
                page.evaluate('document.fonts.ready')
                expect(page.locator('.case-card')).to_have_count(case_count)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            for prefix, locale in [('', 'en'), ('zh/', 'zh')]:
                stage = locale + ' initial'
                home(prefix)
                assert page.locator('.card-preview').evaluate_all('(videos)=>videos.every(v=>!v.hasAttribute("src") && v.paused && v.muted && !v.autoplay && v.preload==="none")')
                assert not any(path.endswith(('.mp4', '.webm', '.wasm', '.pck')) for path in requests)
                assert page.locator('iframe').count() == 0
                expect(page.locator('.card-evidence')).to_have_count(case_count)
                assert page.locator('.card-evidence').evaluate_all('(items)=>items.every(item=>item.textContent.trim() && getComputedStyle(item).display!=="none")')
                capture(page, locale + '-desktop-gallery.png')
                checked(locale + ': static artwork before intent; no video or engine request')
                stage = locale + ' hover'
                sonic = page.locator('[data-case="sonic-loom"]')
                video = sonic.locator('video')
                sonic.locator('.card-visual').hover()
                expect(sonic).to_have_attribute('data-preview-state', 'playing')
                page.wait_for_function('document.querySelector("[data-case=sonic-loom] video").currentTime > 0.2')
                assert video.evaluate('(v)=>v.muted && v.videoWidth > 0 && v.readyState >= 2')
                assert page.locator('.card-preview').evaluate_all('(vs)=>vs.filter(v=>!v.paused).length===1')
                capture(page, locale + '-desktop-hover.png')
                page.locator('h1').hover()
                expect(sonic).to_have_attribute('data-preview-state', 'idle')
                assert video.get_attribute('src') is None
                checked(locale + ': decoded muted hover, one active, leave releases source')
                stage = locale + ' controls'
                sonic.locator('.preview-toggle').focus()
                page.keyboard.press('Enter')
                expect(sonic).to_have_attribute('data-preview-state', 'playing')
                page.locator('#search').fill('no-matching-gallery-item')
                expect(page.locator('#empty-state')).to_be_visible()
                assert video.get_attribute('src') is None
                page.locator('#empty-reset').click()
                expect(page.locator('.case-card:visible')).to_have_count(case_count)
                page.locator('[data-filter="media"] [data-value="interactive"]').click()
                expect(page.locator('.case-card:visible')).to_have_count(2)
                opposite = 'zh' if locale == 'en' else 'en'
                page.locator('[data-locale-link="' + opposite + '"]').click()
                expect(page.locator('.case-card:visible')).to_have_count(2)
                assert 'media=interactive' in page.url
                checked(locale + ': keyboard start, filter cleanup, empty/reset, locale query preservation')
                requests.clear()
            stage = 'offscreen and preference gates'
            home()
            sonic = page.locator('[data-case="sonic-loom"]')
            sonic.locator('.card-visual').hover()
            expect(sonic).to_have_attribute('data-preview-state', 'playing')
            page.locator('.site-footer').scroll_into_view_if_needed()
            expect(sonic).to_have_attribute('data-preview-state', 'idle')
            checked('offscreen stops and releases preview')
            ctx.close()
            for preference in ['reduced-motion', 'save-data']:
                ctx = context(viewport={'width': 1486, 'height': 1059}, reduced_motion='reduce' if preference == 'reduced-motion' else 'no-preference')
                if preference == 'save-data':
                    # Explicit browser-test fixture, never used by the production page.
                    ctx.add_init_script('Object.defineProperty(navigator,"connection",{value:{saveData:true,addEventListener(){},removeEventListener(){}}})')
                page = ctx.new_page()
                page.goto(base, wait_until='networkidle')
                sonic = page.locator('[data-case="sonic-loom"]')
                sonic.locator('.card-visual').hover()
                page.wait_for_timeout(400)  # Intent threshold is a timing acceptance criterion.
                assert sonic.locator('video').get_attribute('src') is None
                sonic.locator('.preview-toggle').click()
                expect(sonic).to_have_attribute('data-preview-state', 'playing')
                sonic.locator('.preview-toggle').click()
                expect(sonic).to_have_attribute('data-preview-state', 'idle')
                checked(preference + ': no automatic preview, explicit control works')
                ctx.close()
            stage = 'mobile explicit controls and detail'
            ctx = context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=1)
            page = ctx.new_page()
            for prefix, locale in [('', 'en'), ('zh/', 'zh')]:
                home(prefix)
                assert page.locator('.media-tabs button').evaluate_all('(items)=>items.every(item=>Math.abs(item.getBoundingClientRect().top-items[0].getBoundingClientRect().top)<2)')
                capture(page, locale + '-mobile-gallery.png')
                sonic = page.locator('[data-case="sonic-loom"]')
                sonic.locator('.preview-toggle').scroll_into_view_if_needed()
                assert sonic.locator('video').get_attribute('src') is None
                sonic.locator('.preview-toggle').tap()
                expect(sonic).to_have_attribute('data-preview-state', 'playing')
                page.wait_for_function('document.querySelector("[data-case=sonic-loom] video").currentTime > 0.2')
                capture(page, locale + '-mobile-explicit-preview.png')
                sonic.locator('.preview-toggle').tap()
                expect(sonic).to_have_attribute('data-preview-state', 'idle')
                page.goto(base + prefix + 'cases/sonic-loom/', wait_until='domcontentloaded')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                assert page.locator('iframe').count() == 0
                assert page.locator('.detail-actions a[href="#play"]').count() == 1
                capture(page, locale + '-mobile-detail.png')
                page.locator('a[href="#play"]').first.click()
                page.locator('#play').scroll_into_view_if_needed()
                expect(page.locator('#play')).to_be_in_viewport()
                # The engine remains user-started; fallback/source links stay available.
                assert page.locator('iframe').count() == 0
                capture(page, locale + '-mobile-playable-idle.png')
                page.goto(base + prefix + 'agents/', wait_until='domcontentloaded')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                capture(page, locale + '-mobile-agent-data.png')
                checked(locale + ': touch start/stop, detail actions, idle Godot fallback, Agent/Data layout')
            data = page.request.get(base + 'data/catalog.json').json()
            assert data['record_count'] == case_count and not data['future_use']['available_dataset']
            assert data['usage_rights']['training']['status'] == 'not-granted'
            assert data['usage_rights']['evaluation']['status'] == 'not-granted'
            checked('catalog preserves separate conservative usage rights')
            ctx.close()
            # Isolated markup fixture, never written into _site or the catalog.
            # Its video bytes are an existing selected public asset; the changed
            # evidence/title below are TEST DATA, not a new production claim.
            import build_site as renderer
            import localization as i18n
            partial_case = copy.deepcopy(next(case for case in source_cases if renderer.preview_media(case)))
            partial_case['slug'] = 'partial-preview-contract-fixture'
            partial_case['title'] = 'TEST FIXTURE — not a published showcase'
            source_label = '历史成果 · 新镜头仅为未完成阶段证据'
            english_label = 'Historical artwork · New camera attempt is partial stage evidence'
            partial_case['evidence_label'] = source_label
            root = str(Path.cwd())
            for touch in [False, True]:
                stage = 'partial evidence fixture ' + ('touch' if touch else 'desktop')
                ctx = context(viewport={'width': 390 if touch else 1486, 'height': 844 if touch else 1059}, is_mobile=touch, has_touch=touch)
                page = ctx.new_page()
                for prefix, locale in [('', 'en'), ('zh/', 'zh')]:
                    translations = i18n.catalog(root, locale=locale)
                    if locale == 'en':
                        translations[source_label] = english_label
                    parser = i18n.LocalizedHTML('index.html', locale, {'index.html'}, translations)
                    parser.feed(renderer.cards_markup([partial_case], root))
                    parser.close()
                    assert not parser.missing
                    fixture_url = base + prefix + '__partial_contract_fixture.html'
                    fixture_html = ('<!doctype html><html lang="' + ('en' if locale == 'en' else 'zh-CN') + '"><head><base href="' + base + prefix + '"><link rel="stylesheet" href="' + base + 'assets/site.css"><script src="' + base + 'assets/preview.js" defer></script></head><body><main class="gallery-main"><h1>TEST FIXTURE</h1><div class="work-wall">' + ''.join(parser.output) + '</div></main></body></html>')
                    # A fresh served document avoids document.write inheriting
                    # timers/listeners from the previous live gallery document.
                    page.route(fixture_url, lambda route: route.fulfill(status=200, content_type='text/html', body=fixture_html))
                    page.mouse.move(0, 0)
                    page.goto(fixture_url, wait_until='networkidle')
                    card = page.locator('.case-card')
                    label = card.locator('.card-evidence')
                    expected = english_label if locale == 'en' else source_label
                    expect(label).to_have_text(expected)
                    expect(label).to_be_visible()
                    if touch:
                        card.locator('.preview-toggle').tap()
                    else:
                        card.locator('.card-visual').hover()
                    expect(card).to_have_attribute('data-preview-state', 'playing')
                    expect(label).to_have_text(expected)
                    expect(label).to_be_visible()
                    assert label.bounding_box()['y'] >= card.locator('.card-media').bounding_box()['y'] + card.locator('.card-media').bounding_box()['height']
                    card.locator('.preview-toggle').click()
                    expect(card).to_have_attribute('data-preview-state', 'idle')
                    expect(label).to_have_text(expected)
                    expect(label).to_be_visible()
                    checked(locale + ': partial TEST FIXTURE evidence survives ' + ('touch' if touch else 'hover') + ' preview start/stop outside the media layer')
                ctx.close()
            browser.close()
            if errors:
                raise AssertionError('; '.join(errors))
            report['status'] = 'passed'
            return 0
    except Exception as exc:
        report.update(status='failed', stage=stage, error=safe_error_text(exc, origin))
        if page:
            try:
                capture(page, 'failure.png')
            except Exception:
                pass
        raise
    finally:
        server.shutdown()
        server.server_close()
        (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path('_site'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-head', default='')
    args = parser.parse_args()
    raise SystemExit(run(args.site.resolve(), args.output.resolve(), args.expected_head))
