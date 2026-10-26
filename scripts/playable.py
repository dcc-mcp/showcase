"""Optional, explicitly inventoried Godot Web demos; never publish by crawling."""
from __future__ import annotations

import hashlib
import json
import os
import re


def read_and_validate(root, cases):
    import build_site as site
    name = 'play/manifest.json'
    if not os.path.lexists(os.path.join(root, name)):
        return {}, set()
    manifest_path = site.resolve_public(root, name)
    with open(manifest_path, encoding='utf-8') as handle:
        manifest = json.load(handle)
    if manifest.get('schema_version') != 1:
        raise ValueError('play manifest schema_version must be 1')
    files = manifest.get('files')
    demos = manifest.get('demos')
    if not isinstance(files, list) or not files or not isinstance(demos, list) or not demos:
        raise ValueError('play manifest requires nonempty files and demos')
    assets = {name}
    allowed = {'.html', '.js', '.wasm', '.pck', '.css', '.txt', '.json', '.md', '.svg', '.png', '.woff2'}
    for item in files:
        path = site.safe_rel(item['path'])
        if not path.startswith('play/') or path in assets or os.path.splitext(path)[1] not in allowed:
            raise ValueError('invalid or duplicate play asset: ' + path)
        source = site.resolve_public(root, path)
        if type(item.get('bytes')) is not int or item['bytes'] <= 0:
            raise ValueError('play asset requires a positive byte count: ' + path)
        digest = item.get('sha256', '')
        if not re.fullmatch('[a-f0-9]{64}', digest):
            raise ValueError('play asset requires SHA-256: ' + path)
        if os.path.getsize(source) != item['bytes']:
            raise ValueError('play asset byte count mismatch: ' + path)
        with open(source, 'rb') as handle:
            actual = hashlib.file_digest(handle, 'sha256').hexdigest()
        if actual != digest:
            raise ValueError('play asset SHA-256 mismatch: ' + path)
        assets.add(path)
    slugs = {case['slug'] for case in cases}
    selected = {}
    for demo in demos:
        slug = demo.get('case_slug')
        if slug not in slugs or slug in selected:
            raise ValueError('play demo must identify a unique selected case')
        path = site.safe_rel(demo['url'])
        if path not in assets or not path.endswith('/index.html'):
            raise ValueError('play demo entry must be an inventoried index.html')
        if demo.get('threads') is not False or demo.get('renderer') != 'gl_compatibility':
            raise ValueError('play demos require single-thread Compatibility exports')
        if demo.get('localeSupport') != ['en', 'zh']:
            raise ValueError('play shell must support en/zh')
        # This is a closed publication declaration, not a locale fallback:
        # existing English-only native art stays "en"; "en-zh" explicitly
        # declares native English/Chinese text, independently of the shell.
        if demo.get('nativeTextLanguage') not in ('en', 'en-zh'):
            raise ValueError('play nativeTextLanguage must be en or en-zh')
        for key in ('title', 'engine'):
            if not isinstance(demo.get(key), str) or not demo[key].strip():
                raise ValueError('play demo requires ' + key)
        for key in ('controls', 'notes'):
            if not isinstance(demo.get(key), dict) or set(demo[key]) != {'en', 'zh'}:
                raise ValueError('play demo requires bilingual ' + key)
            if any(not isinstance(value, str) or not value.strip() for value in demo[key].values()):
                raise ValueError('play demo has empty ' + key)
        selected[slug] = demo
    return selected, assets


def section(demo, prefix='../../'):
    import build_site as site
    return '''<section class="detail-section playable-section" id="play" data-playable data-play-case="%s">
<h2>在浏览器中体验</h2><p>%s</p><p class="prompt-note">%s</p>
<p class="prompt-note">WebGL 2 · %s · 点击后才加载。关闭体验会丢弃未保存的状态。</p>
<div class="playable-actions"><button class="primary-button" type="button" data-play-start data-play-url="%s" hidden>打开交互体验</button>
<button class="copy-button" type="button" data-play-exit hidden>关闭体验</button>
<a class="text-link" data-play-link href="%s?lang=zh">在独立页面打开 ↗</a></div>
<div class="playable-frame" data-play-frame></div><p role="status" aria-live="polite" data-play-status></p>
</section>''' % (site.esc(demo['case_slug']), site.esc(demo['controls']['zh']), site.esc(demo['notes']['zh']), site.esc(demo['engine']),
                site.esc(prefix + demo['url']), site.esc(prefix + demo['url']))
