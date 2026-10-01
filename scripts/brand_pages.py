"""Static pages for verified DCC-MCP brand assets.

The parent builder validates the catalog and selects publication files. Draft
rendering is local preview only and never uses unverified images.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit


def _helpers():
    import build_site
    return build_site


def _url(raw, root, prefix):
    site = _helpers()
    value = site.resource_url(raw, prefix)
    if not urlsplit(raw).scheme:
        site.resolve_public(root, raw)
    return site.esc(value)


def _links(rows, root, prefix):
    site = _helpers()
    output = []
    for row in rows:
        pin = ('<code class="brand-pin">%s</code>' % site.esc(row['commit'])) if row.get('commit') else ''
        output.append('<li><a href="%s">%s <span aria-hidden="true">↗</span></a>%s</li>' %
                      (_url(row['url'], root, prefix), site.esc(row['label']), pin))
    return '<ul class="resource-links brand-source-links">%s</ul>' % ''.join(output)


def _preview_image(item, root, prefix, eager=False):
    site = _helpers()
    dark, light = item['previews']['dark'], item['previews']['light']
    dark_url = _url(dark['src'], root, prefix)
    light_url = _url(light['src'], root, prefix)
    dark_dimensions = site.dimensions(root, dark['src'])
    light_dimensions = site.dimensions(root, light['src'])
    load = ' loading="eager" fetchpriority="high"' if eager else ' loading="lazy"'
    return ('<img class="brand-artwork" src="%s" alt="%s"%s%s decoding="async" '
            'data-brand-image data-dark-src="%s" data-light-src="%s" '
            'data-dark-alt="%s" data-light-alt="%s" data-dark-dimensions="%s" data-light-dimensions="%s">'
            '<noscript><figure class="brand-noscript-light" data-background="light">'
            '<img src="%s" alt="%s"%s loading="lazy" decoding="async"><figcaption>浅色背景 · 实际资源</figcaption>'
            '</figure></noscript>') % (
                dark_url, site.esc(dark['alt']), dark_dimensions, load,
                dark_url, light_url, site.esc(dark['alt']), site.esc(light['alt']),
                site.esc(dark_dimensions), site.esc(light_dimensions), light_url, site.esc(light['alt']), light_dimensions)


def _stage(item, root, prefix, eager=False):
    if item.get('status') != 'verified':
        return ('<div class="brand-stage brand-stage-pending" aria-label="品牌资产待完成">'
                '<div><span class="brand-pending-marker">待新资产</span><p>验证完成后展示实际品牌文件</p>'
                '<span>当前预览不包含 Logo 图像</span></div></div>')
    return '<div class="brand-stage" data-background="dark">%s</div>' % _preview_image(item, root, prefix, eager)


def _theme_controls():
    return ('<div class="brand-theme-controls" role="group" aria-label="预览背景" hidden data-brand-themes>'
            '<span>预览背景</span><div><button type="button" data-brand-theme="dark" aria-pressed="true">深色</button>'
            '<button type="button" data-brand-theme="light" aria-pressed="false">浅色</button></div></div>')


def _head(title, description, path, root, items, preview, detail=None):
    site = _helpers()
    verified = [item for item in items if item.get('status') == 'verified']
    structured = {'@context': 'https://schema.org', '@type': 'CreativeWork' if detail else 'CollectionPage',
                  'name': title, 'description': description, 'url': site.public_url(path),
                  'inLanguage': 'zh-CN', 'isPartOf': {'@type': 'WebSite', 'name': 'DCC-MCP Showcase', 'url': site.SITE_URL}}
    if detail:
        structured['keywords'] = detail.get('software', []) + [detail.get('family', '')]
    else:
        structured['mainEntity'] = {'@type': 'ItemList', 'numberOfItems': len(verified), 'itemListElement': [
            {'@type': 'ListItem', 'position': index + 1, 'name': item['title'],
             'url': site.public_url('brands/%s/' % item['slug'])} for index, item in enumerate(verified)]}
    if verified:
        cover = verified[0]['previews']['dark']
        if urlsplit(cover['src']).path.lower().endswith('.svg'):
            for variant in verified[0].get('variants', []):
                parsed = urlsplit(variant['url'])
                if not parsed.scheme and parsed.path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    cover = {'src': variant['url'], 'alt': cover['alt']}
                    break
        head = site.seo_tags(title, description[:220], path, cover, root, structured)
        if preview:
            head = head.replace('index, follow, max-image-preview:large', 'noindex, nofollow')
        return head
    return ('<title>%s</title><meta name="description" content="%s">'
            '<meta name="robots" content="noindex, nofollow"><link rel="canonical" href="%s">'
            '<script type="application/ld+json">%s</script>') % (
                site.esc(title), site.esc(description), site.esc(site.public_url(path)), site.structured_json(structured))


def _shell(content, head, prefix):
    return '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
%s<meta name="theme-color" content="#101311"><link rel="stylesheet" href="%sassets/site.css">
<link rel="stylesheet" href="%sassets/brand.css"><script src="%sassets/brand.js" defer></script></head>
<body class="brand-page"><a class="skip-link" href="#brand-content">跳到品牌内容</a>
<header class="site-header wrap"><a class="brand" href="%s" aria-label="DCC-MCP Showcase 首页"><strong>DCC-MCP</strong><span>Showcase</span></a>
<nav aria-label="主导航"><a href="%s#works">作品合集</a><a href="%sbrands/" aria-current="page">品牌画廊</a><a href="https://dcc-mcp.github.io/">DCC-MCP 官网 ↗</a></nav></header>
<main class="wrap" id="brand-content">%s</main>
<footer class="site-footer wrap"><p>DCC-MCP Showcase</p><nav aria-label="页脚导航"><a href="https://dcc-mcp.github.io/">DCC-MCP 官网 ↗</a><a href="https://github.com/dcc-mcp/showcase">合集源码 ↗</a></nav></footer></body></html>
''' % (head, prefix, prefix, prefix, prefix, prefix, prefix, content)


def _option(values):
    site = _helpers()
    return '<option value="all">全部</option>' + ''.join('<option value="%s">%s</option>' % (site.esc(value), site.esc(value)) for value in values)


def _card(item, root):
    site = _helpers()
    search = ' '.join([item['title'], item.get('summary', ''), item.get('family', '')] + item.get('software', []))
    href = '%s/' % item['slug']
    status = '已验证资产' if item.get('status') == 'verified' else '待完成 · 本地预览'
    return '''<article class="brand-card" data-brand-card data-family="%s" data-software="%s" data-search="%s">
<a class="brand-card-visual brand-detail-link" href="%s" aria-label="查看品牌：%s">%s</a>
<div class="brand-card-meta"><span>%s</span><span>%s</span></div><h3><a class="brand-detail-link" href="%s">%s</a></h3>
<p>%s</p><div class="brand-card-bottom"><span>%s</span><a class="brand-detail-link" href="%s">资源与制作记录 <span aria-hidden="true">↗</span></a></div></article>''' % (
        site.esc(item.get('family', '')), site.esc(json.dumps(item.get('software', []), ensure_ascii=False)),
        site.esc(search), href, site.esc(item['title']), _stage(item, root, '../'), site.esc(item.get('family', '品牌系统')),
        status, href, site.esc(item['title']), site.esc(item.get('summary', '新品牌资产正在准备；完成工具、来源和许可验证后展示。')),
        site.esc(' / '.join(item.get('software', [])) or '制作环境待确认'), href)


def _gallery(catalog, items, root, preview):
    site = _helpers()
    families = sorted({item['family'] for item in items if item.get('family')})
    software = sorted({name for item in items for name in item.get('software', [])})
    notice = ('<aside class="brand-draft-notice"><strong>仅本地预览</strong><p>此页面用于审阅画廊结构。待完成条目没有 Logo 图像或下载；正式发布只接收验证通过的新资产。</p></aside>') if preview else ''
    title = catalog.get('title', 'DCC-MCP 品牌画廊')
    description = catalog.get('description', '统一品牌语言，保留每件资产的实际制作步骤、工具、来源与许可。')
    empty = len(items) == 0
    content = '''<section class="brand-hero"><p class="eyebrow">DCC-MCP · BRAND LIBRARY</p><h1>%s</h1><p>%s</p>
<div class="brand-hero-meta"><span>实际资源 · 深浅背景</span><span>制作过程 · 可核验下载</span></div></section>%s
<section class="brand-collection" aria-labelledby="brand-wall-title"><div class="brand-collection-heading"><h2 id="brand-wall-title">品牌家族</h2><p>从品牌标识到适配器视觉</p></div>
<div class="brand-controls" id="brand-controls" hidden><label class="brand-search"><span>搜索品牌</span><input id="brand-search" type="search" maxlength="200" placeholder="品牌、软件或关键词" autocomplete="off"></label>
<div class="brand-filter-row"><label>家族<select id="brand-family">%s</select></label><label>软件<select id="brand-software">%s</select></label><button type="button" class="reset-button" id="brand-reset">重置筛选</button></div>%s</div>
<noscript><p class="notice">当前显示全部条目。已验证资产同时提供深浅背景实图；详情、下载与许可无需 JavaScript 即可查看。</p></noscript>
<p class="result-count" id="brand-count" role="status" aria-live="polite">全部 %d 个品牌条目</p>
<div class="brand-wall" id="brand-wall">%s</div><div class="empty-state" id="brand-empty"%s><h3>没有匹配的品牌</h3><p>试试其他软件、家族或关键词。</p><button class="primary-button" id="brand-empty-reset" type="button" hidden>显示全部</button></div></section>''' % (
        site.esc(title), site.esc(description), notice, _option(families), _option(software), _theme_controls(), len(items),
        ''.join(_card(item, root) for item in items), '' if empty else ' hidden')
    return _shell(content, _head(title + ' | DCC-MCP Showcase', description, 'brands/', root, items, preview), '../')


def _bytes(value):
    if value >= 1048576:
        return '%.2f MiB' % (value / 1048576)
    if value >= 1024:
        return '%.1f KiB' % (value / 1024)
    return '%d B' % value


def _downloads(item, root, prefix):
    site = _helpers()
    rights = {row['id']: row for row in item.get('rights', [])}
    rows = []
    for variant in item.get('variants', []):
        rights_ids = variant.get('rights_ids') or [variant['rights_id']]
        right_links = []
        for rights_id in rights_ids:
            right = rights[rights_id]
            right_links.append('<a href="#rights-%s">%s · %s</a>' % (
                site.esc(right['id']), site.esc(right['holder']), site.esc(right['license'])))
        label = site.esc(variant['label'])
        size = '%s × %s' % (variant.get('width', '—'), variant.get('height', '—'))
        download = ' download' if not urlsplit(variant['url']).scheme else ''
        rows.append('''<li class="brand-download"><div class="brand-download-heading"><h3>%s</h3><a href="%s"%s>下载 <span aria-hidden="true">↓</span></a></div>
<p class="brand-file-meta">%s · %s · %s</p><p class="brand-file-rights">%s</p><div class="brand-checksum"><span>SHA-256</span><code>%s</code></div></li>''' % (
            label, _url(variant['url'], root, prefix), download, site.esc(variant['format'].upper()), site.esc(size),
            _bytes(variant['bytes']), ' / '.join(right_links), site.esc(variant['sha256'])))
    return '<ul class="brand-downloads">%s</ul>' % ''.join(rows)


def _detail(item, catalog, root, preview):
    site = _helpers()
    prefix = '../../'
    verified = item.get('status') == 'verified'
    pending = '<p class="brand-pending-copy">待新资产及对应实际记录验证完成后补齐。</p>'
    metadata = ''.join('<span>%s</span>' % site.esc(value) for value in [item.get('family', '品牌系统')] + item.get('software', []))
    version = '<p class="brand-version">资产版本：%s</p>' % site.esc(item['version']) if item.get('version') and verified else ''
    environment = ''.join('<div><dt>%s</dt><dd>%s</dd></div>' % (site.esc(row['label']), site.esc(row['value'])) for row in item.get('environment', [])) if verified else ''
    tools = ''.join('<li><code>%s</code><p>%s</p></li>' % (site.esc(row['name']), site.esc(row['description'])) for row in item.get('tools', [])) if verified else ''
    steps = []
    if verified:
        for row in item.get('steps', []):
            image = site.figure(row['image'], root, prefix) if row.get('image') else ''
            steps.append('<li class="process-step"><div class="step-heading"><h3>%s</h3></div><p>%s</p>%s</li>' % (site.esc(row['title']), site.esc(row['description']), image))
    checks = []
    labels = {'pass': '通过', 'fail': '未通过', 'unknown': '未验证', 'not_run': '未运行',
              'unverified': '未验证', 'not-run': '未运行'}
    if verified:
        for row in item.get('checks', []):
            result = row['result']
            checks.append('<tr><td>%s</td><td><span class="check-result %s">%s</span></td><td>%s</td></tr>' % (site.esc(row['name']), 'check-pass' if result == 'pass' else 'check-fail' if result == 'fail' else '', site.esc(labels.get(result, result)), site.esc(site.text_value(row['observed']))))
    prompt = item.get('prompt', {}) if verified else {}
    prompt_html = '<div class="prompt-label"><strong>%s</strong><button type="button" class="copy-button" data-brand-copy hidden>复制提示词</button></div><pre class="prompt" id="brand-prompt">%s</pre><p class="prompt-note">%s</p><p class="brand-copy-status" role="status" aria-live="polite"></p>' % ('原始提示词' if prompt.get('kind') == 'original' else '可复用提示词', site.esc(prompt.get('text', '')), site.esc(prompt.get('note', ''))) if prompt else pending
    rights = []
    if verified:
        for right in item.get('rights', []):
            rights.append('<article class="brand-right" id="rights-%s"><h3>%s · %s</h3><p><strong>权利人</strong>：%s<br><strong>适用范围</strong>：%s</p><p>%s</p><a class="text-link" href="%s">查看许可或来源 ↗</a></article>' % (site.esc(right['id']), site.esc(right['id']), site.esc(right['license']), site.esc(right['holder']), site.esc(right['scope']), site.esc(right.get('notice', '')), _url(right['url'], root, prefix)))
    contributors = []
    if verified:
        for person in item.get('contributors', []):
            if isinstance(person, str):
                contributors.append(site.esc(person))
            elif isinstance(person, dict):
                name = site.esc(person.get('name', person.get('label', '')))
                contributors.append('<a href="%s">%s</a>' % (_url(person['url'], root, prefix), name) if person.get('url') else name)
    credit = '<p class="brand-contributors">贡献者：%s</p>' % ' / '.join(contributors) if contributors else ''
    limitations = '<ul class="limitations">%s</ul>' % ''.join('<li>%s</li>' % site.esc(value) for value in item.get('limitations', [])) if verified else pending
    checks_html = '<table class="checks"><caption class="brand-table-caption">实际验证记录；证据范围以各项观测为准。</caption><thead><tr><th scope="col">检查</th><th scope="col">结果</th><th scope="col">观测与依据</th></tr></thead><tbody>%s</tbody></table>' % ''.join(checks) if checks else pending
    status = '已验证资源 · 可核验文件' if verified else '待完成 · 仅本地预览'
    notice = '<aside class="brand-draft-notice"><strong>此详情尚未发布</strong><p>预览结构不代表作品已完成；不引用旧缺陷图，也不提供待验证资产下载。</p></aside>' if not verified else ''
    nav = ''.join('<a href="#%s">%s</a>' % row for row in [('downloads', '资源下载'), ('prompt', '提示词'), ('environment', '制作工具'), ('process', '分步过程'), ('evidence', '验证记录'), ('rights', '来源与许可')])
    content = '''<a class="detail-back" data-brand-back href="../"><span aria-hidden="true">←</span> 返回品牌画廊</a><div class="detail-heading"><div class="detail-meta">%s</div><h1>%s</h1><p class="subtitle">%s</p>%s</div>%s
<div class="brand-detail-stage">%s%s<p class="brand-stage-caption">%s</p></div>
<div class="detail-layout"><nav class="detail-nav" aria-label="品牌详情目录">%s</nav><div class="detail-content">
<section class="detail-section" id="downloads"><h2>资源下载</h2><p>每个变体单独保留尺寸、文件哈希与适用许可。查看页面不会自动下载源文件。</p>%s</section>
<section class="detail-section" id="prompt"><h2>提示词</h2>%s</section>
<section class="detail-section" id="environment"><h2>制作工具与版本</h2><dl class="environment">%s</dl><ul class="tool-list">%s</ul>%s</section>
<section class="detail-section" id="process"><h2>分步过程</h2><ol class="process-list">%s</ol>%s</section>
<section class="detail-section" id="evidence"><h2>验证与证据边界</h2>%s%s<h3 class="brand-limitations-heading">证据边界</h3>%s</section>
<section class="detail-section" id="rights"><h2>来源与许可</h2>%s%s%s</section></div></div>
<div class="detail-footer"><a data-brand-back href="../">← 返回品牌画廊</a><a href="../../#works">查看 DCC-MCP 作品合集 ↗</a></div>''' % (
        metadata, site.esc(item['title']), site.esc(item.get('summary', '新品牌资源与实际制作证据正在准备。')), version, notice,
        _stage(item, root, prefix, eager=True), _theme_controls() if verified else '', status, nav,
        _downloads(item, root, prefix) if verified else pending, prompt_html, environment, tools, '' if verified else pending,
        ''.join(steps), '' if steps else pending, checks_html, _links(item.get('evidence', []), root, prefix) if verified else '',
        limitations, _links(item.get('sources', []), root, prefix) if verified else pending, ''.join(rights), credit)
    title = item['title'] + ' · 品牌资源 | DCC-MCP Showcase'
    return _shell(content, _head(title, item.get('summary', ''), 'brands/%s/' % item['slug'], root, [item], preview, detail=item), prefix)


def generate(catalog, root, preview=False):
    """Return full HTML keyed by safe publication-relative paths.

    Production requires an enabled catalog with verified assets. Local previews
    expose pending text scaffolding, never its unverified media or downloads.
    """
    site = _helpers()
    if not isinstance(catalog, dict) or catalog.get('schema_version') != 1:
        raise ValueError('brand catalog schema_version must be 1')
    items = catalog.get('items', [])
    if not isinstance(items, list):
        raise ValueError('brand catalog items must be a list')
    if not preview and (catalog.get('enabled') is not True or not items or any(item.get('status') != 'verified' for item in items)):
        raise ValueError('brand publication requires an enabled verified catalog with verified assets')
    if preview and not items:
        items = [{'slug': 'dcc-mcp', 'title': 'DCC-MCP', 'family': '品牌系统', 'software': [], 'status': 'pending',
                  'summary': '待验证的新品牌资产将出现在这里；当前仅为本地页面结构预览。'}]
    elif preview:
        # This flag previews the unpublished page structure, not asset approval.
        items = [dict(item, status='pending') for item in items]
    seen = set()
    for item in items:
        slug = item.get('slug', '')
        if not site.SLUG.fullmatch(slug) or slug in seen:
            raise ValueError('brand slugs must be unique safe paths')
        seen.add(slug)
    pages = {'brands/index.html': _gallery(catalog, items, root, preview)}
    for item in items:
        pages['brands/%s/index.html' % item['slug']] = _detail(item, catalog, root, preview)
    return pages
