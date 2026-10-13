"""Artwork-first, opt-in game discovery and dedicated play stages.

The validated play manifest is the only game inventory. Collection evidence,
source attribution and originals stay authoritative on their case pages.
"""


def game_card(case, demo, root, prefix="", compact=False):
    import build_site as site
    slug = case['slug']
    return '''<article class="game-card%s" data-game-case="%s">
<a class="game-cover" href="%sgames/%s/" aria-label="%s">%s<span class="game-engine">Godot Web</span></a>
<a class="game-launch" href="%sgames/%s/" data-game-launch="%s"><span aria-hidden="true">▶</span> 开始游戏</a>
<h3><a href="%sgames/%s/">%s</a></h3><p>%s</p></article>''' % (
        ' game-card-compact' if compact else '', site.esc(slug), prefix, site.esc(slug),
        site.esc(case['title']), site.media_markup(case['cover'], root, prefix),
        prefix, site.esc(slug), site.esc(slug), prefix, site.esc(slug), site.esc(case['title']),
        site.esc(case['subtitle']))


def shelf(cases, demos, root):
    if not demos:
        return ''
    return '''<section class="games-shelf" id="games" aria-labelledby="games-title">
<div class="games-heading"><div><p class="eyebrow">PLAY / GODOT</p><h2 id="games-title">即点即玩</h2></div>
<p>小小的游戏，大大的想象。无需安装，点击开始。</p></div>
<div class="games-rail">%s</div></section>''' % '\n'.join(
        game_card(case, demos[case['slug']], root) for case in cases if case['slug'] in demos)


def pages(cases, demos, root):
    import build_site as site
    selected = [case for case in cases if case['slug'] in demos]
    result = {}
    for case in selected:
        slug = case['slug']
        demo = demos[slug]
        title = site.esc(case['title'])
        metadata = site.seo_tags(case['title'], case['summary'], 'games/%s/' % slug,
                                 case['cover'], root, {
            '@context': 'https://schema.org', '@type': 'VideoGame', 'name': case['title'],
            'url': site.public_url('games/%s/' % slug), 'gamePlatform': 'Web browser',
            'inLanguage': 'zh-CN', 'isBasedOn': site.public_url('cases/%s/' % slug)})
        others = '\n'.join(game_card(other, demos[other['slug']], root, '../../', True)
                           for other in selected if other['slug'] != slug)
        result['games/%s/index.html' % slug] = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
%s<link rel="stylesheet" href="../../assets/site.css"><link rel="stylesheet" href="../../assets/games.css">
<script src="../../assets/games.js" defer></script></head><body>
<a class="skip-link" href="#game-stage">跳到游戏</a>
<header class="site-header wrap"><a class="brand" href="../../"><strong>DCC-MCP</strong><span>Showcase</span></a>
<nav aria-label="主导航"><a href="../../#games">游戏</a><a href="../../#works">作品合集</a><a href="../../agents/">Agent / Data</a></nav></header>
<main class="wrap games-main"><a class="detail-back" href="../../#games">← 返回游戏合集</a>
<div class="game-layout"><section class="game-primary" aria-labelledby="game-title">
<div class="game-stage" id="game-stage" data-game-stage data-game-slug="%s" data-game-url="%s" data-state="idle">
<div class="game-poster" data-game-poster>%s<div class="game-poster-caption"><span class="game-engine">Godot Web</span><h2>%s</h2><button class="primary-button" data-game-start type="button" hidden>开始游戏</button><p>点击后才下载游戏。共享引擎约 36 MiB，首次启动可能需要片刻。</p></div></div>
<div class="game-frame" data-game-frame></div></div>
<div class="game-toolbar"><p data-game-status role="status" aria-live="polite">准备就绪，尚未加载游戏。</p>
<div class="game-actions"><button type="button" data-game-sound hidden>点击开声</button><button type="button" data-game-reset hidden>重新开始</button><button type="button" data-game-fullscreen hidden>全屏</button><button type="button" data-game-exit hidden>退出游戏</button></div></div>
<div class="game-title-row"><div><p class="eyebrow">PLAY / GODOT</p><h1 id="game-title">%s</h1><p class="game-subtitle">%s</p></div><a class="text-link" href="../../cases/%s/">制作过程与源码 ↗</a></div>
<section class="game-instructions"><h2>怎么玩</h2><p>%s</p><p>电脑支持键盘，手机可直接轻触。点击游戏画面后开始操作；退出会丢弃未保存的进度。</p>
<details><summary>运行说明与验证范围</summary><p>%s</p><p>%s · WebGL 2 · <a href="%s?lang=zh">在独立页面打开 ↗</a></p></details></section>
<noscript><p class="notice">启用 JavaScript 后即可在此试玩，也可使用上方独立页面链接。</p></noscript>
</section><aside class="more-games" aria-labelledby="more-games-title"><div class="games-heading"><h2 id="more-games-title">更多游戏</h2><a href="../../#games">查看全部</a></div><div class="more-games-grid">%s</div></aside></div></main>
<footer class="site-footer wrap"><p>DCC-MCP Showcase</p><a href="../../cases/%s/">查看本作的创作过程、来源与许可</a></footer></body></html>''' % (
            metadata, site.esc(slug), site.esc('../../' + demo['url']),
            site.media_markup(case['cover'], root, '../../', eager=True), title, title,
            site.esc(case['subtitle']), site.esc(slug), site.esc(demo['controls']['zh']),
            site.esc(demo['notes']['zh']), site.esc(demo['engine']), site.esc('../../' + demo['url']),
            others, site.esc(slug))
    return result
