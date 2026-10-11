#!/usr/bin/env python3
"""Build the curated collection as a static GitHub Pages website.

Only the selected case manifests, explicitly linked resources and local UI
assets enter the publication directory. No unselected archive is crawled.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
from urllib.parse import unquote, urlsplit

MAX_STILL_WIDTH = 1600
MAX_GIF_WIDTH = 900
MAX_GIF_BYTES = 8 * 1024 * 1024
MAX_GIF_FPS = 12
ATTR_REF = re.compile(r'(?:src|href|poster)="([^"]+)"')
MD_LINK = re.compile(r'\]\(([^)\s]+)\)')
EXTERNAL = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|//|#)')
FOLLOW = (".html", ".htm", ".md")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
FORBIDDEN = {".git", ".agents", ".codex", ".aws", "node_modules"}
AUDIO_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg"}

def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def as_posix(path: str) -> str:
    return path.replace("\\", "/")

def safe_rel(raw: str) -> str:
    """A manifest path is a repository-relative public path, never a URL."""
    raw = unquote(str(raw))
    if not raw or "\\" in raw or raw.startswith("/") or re.search(r"[:\x00-\x1f]", raw):
        raise ValueError("unsafe public path")
    parts = raw.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") or p in FORBIDDEN for p in parts):
        raise ValueError("unsafe public path")
    return "/".join(parts)

def resolve_public(root: str, rel: str) -> str:
    rel = safe_rel(rel)
    root_abs = os.path.realpath(root)
    src = os.path.realpath(os.path.join(root_abs, *rel.split("/")))
    try:
        inside = os.path.commonpath([root_abs, src]) == root_abs
    except ValueError:
        inside = False
    if not inside:
        raise ValueError("public path resolves outside repository")
    if not os.path.isfile(src):
        raise ValueError("%s: referenced but missing" % rel)
    return src

def refs_of(text: str, base_rel: str) -> list[str]:
    found = []
    for pattern in (ATTR_REF, MD_LINK):
        found.extend(pattern.findall(text))
    resolved = []
    for raw in found:
        raw = html.unescape(raw)
        ref = raw.split("#")[0].split("?")[0]
        if not ref or EXTERNAL.match(ref):
            continue
        ref = unquote(ref)
        if "\\" in ref:
            raise ValueError("backslash in public reference")
        if ref.startswith("/"):
            rel = ref.lstrip("/")
        else:
            rel = as_posix(os.path.normpath(os.path.join(os.path.dirname(base_rel), ref)))
        if rel in (".", ""):
            rel = "index.html"
        elif raw.split("#")[0].split("?")[0].endswith("/"):
            rel = rel.rstrip("/") + "/index.html"
        rel = safe_rel(rel)
        if rel != base_rel:
            resolved.append(rel)
    return resolved

def png_size(path: str):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def jpeg_size(path: str):
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            i += 2
            continue
        if marker == 0xFF:
            i += 1
            continue
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height = int.from_bytes(data[i + 5:i + 7], "big")
            width = int.from_bytes(data[i + 7:i + 9], "big")
            return width, height
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None


def gif_info(path: str):
    """Width, height, frame count and the shortest frame delay in 1/100 s."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 13 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    flags = data[10]
    i = 13
    if flags & 0x80:
        i += 3 * (2 ** ((flags & 0x07) + 1))
    frames = 0
    min_delay = None
    while i < len(data):
        block = data[i]
        if block == 0x21:
            if data[i + 1:i + 2] == b"\xf9" and data[i + 2:i + 3] == b"\x04":
                delay = int.from_bytes(data[i + 4:i + 6], "little")
                if delay:
                    min_delay = delay if min_delay is None else min(min_delay, delay)
                frames += 1
            i += 3
            while i < len(data) and data[i] != 0:
                i += 1 + data[i]
            i += 1
        elif block == 0x2C:
            local = data[i + 9] if i + 9 < len(data) else 0
            i += 10
            if local & 0x80:
                i += 3 * (2 ** ((local & 0x07) + 1))
            i += 1
            while i < len(data) and data[i] != 0:
                i += 1 + data[i]
            i += 1
        elif block == 0x3B:
            break
        else:
            i += 1
    return width, height, frames, min_delay


def check_media(rel: str, src: str) -> list[str]:
    """Gallery media contract, enforced on the files the page actually loads."""
    ext = os.path.splitext(rel)[1].lower()
    size = os.path.getsize(src)
    if ext == ".gif":
        info = gif_info(src)
        if info is None:
            return ["%s: not a readable GIF" % rel]
        width, height, frames, min_delay = info
        problems = []
        if width > MAX_GIF_WIDTH:
            problems.append("%s: %dpx wide (gif max %d)" % (rel, width, MAX_GIF_WIDTH))
        if size > MAX_GIF_BYTES:
            problems.append("%s: %d bytes (gif max %d)" % (rel, size, MAX_GIF_BYTES))
        if min_delay:
            fps = 100.0 / min_delay
            if fps > MAX_GIF_FPS + 0.01:
                problems.append("%s: %.1f fps (max %d)" % (rel, fps, MAX_GIF_FPS))
        return problems
    if ext in (".png", ".jpg", ".jpeg"):
        dims = png_size(src) if ext == ".png" else jpeg_size(src)
        if dims is None:
            return ["%s: not a readable image" % rel]
        width, height = dims
        if width > MAX_STILL_WIDTH:
            return ["%s: %dpx wide (still max %d)" % (rel, width, MAX_STILL_WIDTH)]
        return []
    return []



def esc(value) -> str:
    return html.escape(str(value), quote=True)

def text_value(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)

def resource_url(raw: str, prefix: str = "") -> str:
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("resources require an HTTPS URL or safe local path")
        return raw
    return prefix + safe_rel(raw)

def dimensions(root: str, rel: str) -> str:
    src = resolve_public(root, rel)
    ext = os.path.splitext(rel)[1].lower()
    dims = png_size(src) if ext == ".png" else jpeg_size(src) if ext in (".jpg", ".jpeg") else None
    if dims:
        return ' width="%d" height="%d"' % dims
    return ""

def media_markup(media: dict, root: str, prefix: str = "", eager: bool = False) -> str:
    rel = safe_rel(media["src"])
    url = esc(prefix + rel)
    alt = esc(media["alt"])
    extension = os.path.splitext(rel)[1].lower()
    if extension in AUDIO_TYPES:
        return ('<div class="audio-player"><audio controls preload="metadata" aria-label="%s" tabindex="0">'
                '<source src="%s" type="%s">你的浏览器不支持此音频，可使用下方链接下载。'
                '</audio><div class="audio-actions"><div class="audio-seek" role="group" aria-label="音频快进与后退">'
                '<button type="button" data-audio-seek="-5" aria-label="后退 5 秒" disabled>−5 秒</button>'
                '<button type="button" data-audio-seek="5" aria-label="快进 5 秒" disabled>+5 秒</button>'
                '</div><p class="audio-download">无法播放？'
                '<a href="%s" download="%s">下载音频（%s）</a></p></div></div>') % (
                    alt, url, AUDIO_TYPES[extension], url, esc(os.path.basename(rel)), extension[1:].upper())
    if os.path.splitext(rel)[1].lower() in (".mp4", ".webm"):
        poster = (' poster="%s"' % esc(resource_url(media["poster"], prefix))) if media.get("poster") else ""
        return '<video controls playsinline preload="metadata"%s aria-label="%s"><source src="%s"><p>你的浏览器不支持此视频。<a href="%s">下载视频</a></p></video>' % (poster, alt, url, url)
    load = ' loading="eager" fetchpriority="high"' if eager else ' loading="lazy"'
    return '<img src="%s" alt="%s"%s%s decoding="async">' % (url, alt, dimensions(root, rel), load)

def figure(media: dict, root: str, prefix: str) -> str:
    visual = media_markup(media, root, prefix)
    if os.path.splitext(media["src"])[1].lower() not in {".mp4", ".webm", *AUDIO_TYPES}:
        visual = '<a href="%s" aria-label="%s">%s</a>' % (esc(prefix + media["src"]), esc("查看原尺寸：" + media["alt"]), visual)
    caption = media.get("caption", media["alt"])
    return '<figure class="artifact">%s<figcaption>%s</figcaption></figure>' % (visual, esc(caption))

def filters(values: list[str]) -> str:
    return "".join('<button class="filter-button" type="button" data-value="%s" aria-pressed="%s">%s</button>' %
                   (esc(value), "true" if value == "all" else "false", "全部" if value == "all" else esc(value))
                   for value in ["all"] + values)

def cards_markup(cases: list[dict], root: str) -> str:
    cards = []
    for index, case in enumerate(cases):
        href = "cases/%s/" % case["slug"]
        software = esc(json.dumps(case["software"], ensure_ascii=False))
        capabilities = esc(json.dumps(case["capabilities"], ensure_ascii=False))
        search = esc(" ".join([case["title"], case["subtitle"], case["summary"]] + case["software"] + case["capabilities"]))
        tags = "".join("<span>%s</span>" % esc(tag) for tag in case["capabilities"])
        cards.append("""<article class="case-card" data-software="%s" data-capabilities="%s" data-search="%s">
<a class="card-visual" href="%s" aria-label="%s">%s</a>
<div class="card-meta"><span>%s</span><span class="evidence-label">%s</span></div>
<h3 class="card-title"><a href="%s">%s</a></h3><p class="card-summary">%s</p>
<div class="card-bottom"><div class="capability-list">%s</div><a class="card-link" href="%s">查看过程 <span aria-hidden="true">↗</span></a></div></article>""" %
            (software, capabilities, search, href, esc("查看案例：" + case["title"]), media_markup(case["cover"], root, eager=index == 0),
             esc(" / ".join(case["software"])), esc(case["evidence_label"]), href, esc(case["title"]),
             esc(case["summary"]), tags, href))
    return "\n".join(cards)

# Verified public endpoints. Keep the project-site slash: the organization site
# also contains a VitePress route and must not capture collection navigation.
SITE_URL = "https://dcc-mcp.github.io/showcase/"
OFFICIAL_URL = "https://dcc-mcp.github.io/"
GUIDE_URL = "https://dcc-mcp.github.io/zh/agents"
CORE_URL = "https://github.com/dcc-mcp/dcc-mcp-core"
ADAPTER_PROJECTS = {
    "Blender": "https://github.com/dcc-mcp/dcc-mcp-blender",
    "Houdini": "https://github.com/dcc-mcp/dcc-mcp-houdini",
    "Substance 3D Designer": "https://github.com/dcc-mcp/dcc-mcp-substance3d-designer",
}
ENGINEERING_EXTENSIONS = {
    ".blend", ".sbs", ".sbsar", ".hip", ".hiplc", ".hipnc", ".ma", ".mb",
    ".max", ".c4d", ".nk", ".psd", ".spp", ".ztl", ".unitypackage", ".zip",
    ".obj", ".mtl", ".fbx", ".gltf", ".glb", ".usd", ".usda", ".usdc",
    ".abc", ".stl", ".step", ".iges", ".3mf",
}

def public_url(path: str = "") -> str:
    if not path:
        return SITE_URL
    has_slash = path.endswith("/")
    return SITE_URL + safe_rel(path.rstrip("/")) + ("/" if has_slash else "")

def structured_json(value: dict) -> str:
    # JSON-LD remains data even when a user-supplied title contains </script>.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

def seo_tags(title: str, description: str, path: str, cover: dict,
             root: str, structured: dict) -> str:
    canonical = public_url(path)
    rows = [
        "<title>%s</title>" % esc(title),
        '<meta name="description" content="%s">' % esc(description),
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        '<link rel="canonical" href="%s">' % esc(canonical),
        '<link rel="sitemap" type="application/xml" href="%s">' % esc(public_url("sitemap.xml")),
        '<meta property="og:type" content="%s">' % ("article" if path else "website"),
        '<meta property="og:site_name" content="DCC-MCP Showcase">',
        '<meta property="og:locale" content="zh_CN">',
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(description),
        '<meta property="og:url" content="%s">' % esc(canonical),
        '<meta name="twitter:title" content="%s">' % esc(title),
        '<meta name="twitter:description" content="%s">' % esc(description),
    ]
    image = cover.get("poster", cover["src"])
    if os.path.splitext(image)[1].lower() in (".jpg", ".jpeg", ".png", ".webp"):
        image_url = public_url(image)
        rows.extend([
            '<meta property="og:image" content="%s">' % esc(image_url),
            '<meta property="og:image:alt" content="%s">' % esc(cover["alt"]),
            '<meta name="twitter:card" content="summary_large_image">',
            '<meta name="twitter:image" content="%s">' % esc(image_url),
            '<meta name="twitter:image:alt" content="%s">' % esc(cover["alt"]),
        ])
        src = resolve_public(root, image)
        ext = os.path.splitext(image)[1].lower()
        dims = png_size(src) if ext == ".png" else jpeg_size(src) if ext in (".jpg", ".jpeg") else None
        if dims:
            rows.extend(['<meta property="og:image:width" content="%d">' % dims[0],
                         '<meta property="og:image:height" content="%d">' % dims[1]])
    else:
        rows.append('<meta name="twitter:card" content="summary">')
    rows.append('<script type="application/ld+json">%s</script>' % structured_json(structured))
    return "\n".join(rows)

def collection_metadata(cases: list[dict]) -> dict:
    return {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "DCC-MCP Showcase · 真实 DCC 作品与可复用流程",
        "url": SITE_URL, "inLanguage": "zh-CN",
        "isPartOf": {"@type": "WebSite", "name": "DCC-MCP", "url": OFFICIAL_URL},
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(cases),
            "itemListElement": [
                {"@type": "ListItem", "position": index + 1,
                 "name": case["title"], "url": public_url("cases/%s/" % case["slug"])}
                for index, case in enumerate(cases)
            ],
        },
    }

def case_metadata(case: dict) -> dict:
    return {
        "@context": "https://schema.org", "@type": "CreativeWork",
        "name": case["title"], "description": case["summary"],
        "url": public_url("cases/%s/" % case["slug"]), "inLanguage": "zh-CN",
        "image": public_url(case["cover"].get("poster", case["cover"]["src"])),
        "creditText": case["credits"]["author"], "isBasedOn": case["source"]["url"],
        "isPartOf": {"@type": "CollectionPage", "name": "DCC-MCP Showcase", "url": SITE_URL},
        "keywords": case["software"] + case["capabilities"],
    }

def sitemap_text(cases: list[dict], brand_slugs: list[str] | None = None) -> str:
    urls = [SITE_URL] + [public_url("cases/%s/" % case["slug"]) for case in cases]
    if brand_slugs:
        urls += [public_url("brands/")] + [public_url("brands/%s/" % slug) for slug in brand_slugs]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
            "".join("  <url><loc>%s</loc></url>\n" % esc(url) for url in urls) + "</urlset>\n")

def related_projects(case: dict) -> str:
    projects = [(name + " 适配器", ADAPTER_PROJECTS[name]) for name in case["software"] if name in ADAPTER_PROJECTS]
    parsed = urlsplit(case["source"]["url"])
    source_parts = parsed.path.strip("/").split("/")
    if parsed.netloc == "github.com" and len(source_parts) >= 2 and source_parts[0] == "dcc-mcp":
        source_repo = "https://github.com/" + "/".join(source_parts[:2])
        if source_repo not in [url for _, url in projects]:
            projects.append(("案例源项目", source_repo))
    projects.extend([("DCC-MCP Core", CORE_URL), ("安装与连接指南", GUIDE_URL)])
    return "".join('<li><a href="%s">%s <span aria-hidden="true">↗</span></a></li>' %
                   (esc(resource_url(url)), esc(label)) for label, url in projects)

def engineering_resource(item: dict) -> bool:
    return os.path.splitext(urlsplit(item["url"]).path)[1].lower() in ENGINEERING_EXTENSIONS

def engineering_section(case: dict, root: str, prefix: str) -> tuple[str, list[dict]]:
    all_engineering = [item for item in case["resources"] if engineering_resource(item)]
    local = [item for item in all_engineering if not urlsplit(item["url"]).scheme]
    chosen = local if local else all_engineering
    remaining = [item for item in case["resources"] if item not in chosen]
    if not chosen:
        return "", remaining
    rows = []
    for item in chosen:
        parsed = urlsplit(item["url"])
        ext = os.path.splitext(parsed.path)[1].lstrip(".").upper()
        filename = os.path.basename(parsed.path)
        url = resource_url(item["url"], prefix)
        if not parsed.scheme:
            size = os.path.getsize(resolve_public(root, item["url"]))
            display_size = "%.1f MiB" % (size / 1048576) if size >= 1048576 else "%.1f KiB" % (size / 1024)
            meta = ext + " · " + display_size
            action = "下载工程"
            download = ' download="%s"' % esc(filename)
        else:
            release_asset = parsed.netloc == "github.com" and "/releases/download/" in parsed.path
            meta = ext + (" · GitHub Release" if release_asset else " · 外部源项目")
            action = "下载工程包" if release_asset else "查看源工程"
            download = ""
        rows.append('<li class="engineering-file"><div><strong>%s</strong><span>%s</span></div><a href="%s"%s>%s <span aria-hidden="true">↗</span></a></li>' %
                    (esc(item["label"]), esc(meta), esc(url), download, action))
    return ('<section class="detail-section" id="downloads"><h2>工程文件</h2>'
            '<p>选择工程、复现包或导出资源。使用前请查看本案例的软件版本、依赖、格式边界与许可。</p>'
            '<ul class="engineering-files">%s</ul></section>' % "".join(rows)), remaining

def model_attribution_section(case: dict) -> str:
    """Render role-scoped model configuration without rewriting making history."""
    models = case.get("model_attribution", [])
    revisions = case.get("revision_notes", [])
    if not models and not revisions:
        return ""
    rows = "".join(
        '<div><dt>%s</dt><dd><strong>%s</strong> · 推理强度：<strong>%s</strong>'
        '<p class="prompt-note">%s<br>%s</p></dd></div>' %
        (esc(row["stage"]), esc(row["model"]), esc(row["reasoning_effort"]),
         esc(row["basis"]), esc(row["scope"])) for row in models)
    history = "".join('<li><strong>%s</strong> · <time datetime="%s">%s</time><p>%s</p></li>' %
                      (esc(row["version"]), esc(row["date"]), esc(row["date"]), esc(row["change"]))
                      for row in revisions)
    return ('<section class="detail-section" id="models"><h2>模型与版本</h2>'
            '<p>制作、后期与审阅分别归属。未知表示没有足够记录，不代表由当前模型制作。</p>'
            '<dl class="environment">%s</dl><h3>版本记录</h3><ul>%s</ul></section>' % (rows, history))

def detail_page(case: dict, root: str, next_case: dict | None = None) -> str:
    prefix = "../../"
    nav_sections = [("goal", "创作目标"), ("prompt", "提示词"), ("environment", "软件与工具"),
                    ("process", "分步过程"), ("results", "成果"), ("evidence", "验证与边界"), ("downloads", "工程文件"), ("resources", "资源与许可")]
    models = model_attribution_section(case)
    if models:
        nav_sections.insert(1, ("models", "模型与版本"))
    downloads, general_resources = engineering_section(case, root, prefix)
    if not downloads:
        nav_sections = [item for item in nav_sections if item[0] != "downloads"]
    nav = "".join('<a href="#%s">%s</a>' % item for item in nav_sections)
    metadata = "".join("<span>%s</span>" % esc(value) for value in case["software"] + case["capabilities"])
    environment = "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (esc(item["label"]), esc(item["value"])) for item in case["environment"])
    tools = "".join("<li><code>%s</code><p>%s</p></li>" % (esc(item["name"]), esc(item["description"])) for item in case["tools"])
    steps = []
    for item in case["steps"]:
        visual = figure(item["image"], root, prefix) if item.get("image") else ""
        steps.append('<li class="process-step"><div class="step-heading"><h3>%s</h3></div><p>%s</p>%s</li>' %
                     (esc(item["title"]), esc(item["description"]), visual))
    checks = []
    result_labels = {"pass": "通过", "fail": "未通过", "unverified": "未验证", "not-run": "未运行"}
    for item in case["checks"]:
        result = item["result"]
        css = "check-pass" if result == "pass" else "check-fail" if result == "fail" else ""
        checks.append('<tr><td>%s</td><td><span class="check-result %s">%s</span></td><td>%s</td></tr>' %
                      (esc(item["name"]), css, esc(result_labels.get(result, result)), esc(text_value(item["observed"]))))
    resources = "".join('<li><a href="%s">%s <span aria-hidden="true">↗</span></a></li>' %
                        (esc(resource_url(item["url"], prefix)), esc(item["label"])) for item in general_resources)
    limitations = "".join("<li>%s</li>" % esc(value) for value in case["limitations"])
    prompt_label = "原始提示词" if case["prompt"]["kind"] == "original" else "可复用提示词模板"
    next_link = ('<a href="../%s/">下一个案例：%s <span aria-hidden="true">→</span></a>' % (next_case["slug"], esc(next_case["title"]))) if next_case else ""
    title = esc(case["title"])
    head = seo_tags(case["title"] + " · " + case["subtitle"] + " | DCC-MCP Showcase",
                    case["summary"][:220], "cases/%s/" % case["slug"], case["cover"], root, case_metadata(case))
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
%s<meta name="theme-color" content="#101311">
<link rel="stylesheet" href="../../assets/site.css"><script src="../../assets/detail.js" defer></script></head>
<body><a class="skip-link" href="#goal">跳到案例内容</a>
<header class="site-header wrap"><a class="brand" href="../../" aria-label="DCC-MCP Showcase 首页"><strong>DCC-MCP</strong><span>Showcase</span></a><nav aria-label="主导航"><a href="../../#works">作品合集</a><a href="https://dcc-mcp.github.io/">DCC-MCP 官网 ↗</a><a href="https://dcc-mcp.github.io/zh/agents">开始使用 ↗</a></nav></header>
<main class="wrap"><a class="detail-back" href="../../#works"><span aria-hidden="true">←</span> 返回作品合集</a>
<div class="detail-heading"><div class="detail-meta">%s</div><h1>%s</h1><p class="subtitle">%s</p></div>
<figure class="detail-cover">%s<figcaption>%s</figcaption></figure>
<aside class="evidence-note" aria-label="证据范围"><strong>%s</strong><p>%s</p></aside>
<div class="detail-layout"><nav class="detail-nav" aria-label="案例目录">%s</nav><div class="detail-content">
<section class="detail-section" id="goal"><h2>创作目标</h2><p>%s</p><p>%s</p></section>
%s
<section class="detail-section" id="prompt"><h2>提示词</h2><div class="prompt-label"><strong>%s</strong><button class="copy-button" id="copy-prompt" type="button" hidden>复制提示词</button></div><pre class="prompt" id="reusable-prompt">%s</pre><div class="copy-status" id="copy-status" role="status" aria-live="polite"></div><p class="prompt-note">%s</p></section>
<section class="detail-section" id="environment"><h2>软件与工具</h2><dl class="environment">%s</dl><ul class="tool-list">%s</ul><h3 class="related-heading">适配器与相关项目</h3><p class="prompt-note">安装、兼容性和当前工具能力以项目文档为准；案例的实际环境与执行证据见上述记录。</p><ul class="related-projects">%s</ul></section>
<section class="detail-section" id="process"><h2>分步过程</h2><ol class="process-list">%s</ol></section>
<section class="detail-section" id="results"><h2>成果</h2>%s</section>
<section class="detail-section" id="evidence"><h2>验证与边界</h2><table class="checks"><caption class="notice">检查记录；历史测量与本轮审阅以各行文字为准。</caption><thead><tr><th scope="col">检查</th><th scope="col">结果</th><th scope="col">观测与依据</th></tr></thead><tbody>%s</tbody></table><h3 style="margin-top:26px">证据边界</h3><ul class="limitations">%s</ul><p class="source-line">最近审阅：%s</p></section>
%s
<section class="detail-section" id="resources"><h2>资源与许可</h2><ul class="resource-links">%s</ul><p class="source-line">来源：<a class="text-link" href="%s">来源与代码</a><br>来源提交：<code>%s</code></p><div class="credit-block"><strong>作者</strong>：%s<br><strong>许可范围</strong>：%s<br>%s</div></section>
</div></div><div class="detail-footer"><a href="../../#works">← 返回作品合集</a>%s</div></main>
<footer class="site-footer wrap"><p>DCC-MCP Showcase</p><nav aria-label="页脚导航"><a href="https://dcc-mcp.github.io/">DCC-MCP 官网 ↗</a><a href="https://github.com/dcc-mcp/dcc-mcp-core">核心项目 ↗</a><a href="https://github.com/dcc-mcp/showcase">合集源码 ↗</a></nav></footer></body></html>
""" % (head, metadata, title, esc(case["subtitle"]),
       media_markup(case["cover"], root, prefix, eager=True), esc(case["cover"]["alt"]),
       esc(case["evidence_label"]), esc(case["evidence_scope"]), nav, esc(case["goal"]), esc(case["summary"]),
       models, prompt_label, esc(case["prompt"]["text"]), esc(case["prompt"]["note"]), environment, tools, related_projects(case),
       "".join(steps), "".join(figure(item, root, prefix) for item in case["results"]), "".join(checks),
       limitations, esc(case["verified_at"]), downloads, resources, esc(resource_url(case["source"]["url"])),
       esc(case["source"]["commit"]), esc(case["credits"]["author"]), esc(case["credits"]["license"]),
       esc(case["credits"]["note"]), next_link)

def compatibility_pages() -> dict[str, str]:
    """Only the published Wwise legacy routes are bridged across the Pages mount."""
    target = "https://dcc-mcp.github.io/examples/wwise"
    page = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wwise 案例已迁移 · DCC-MCP</title><meta name="robots" content="noindex, follow">
<link rel="canonical" href="%s"><meta http-equiv="refresh" content="0;url=%s"></head>
<body><main><h1>Wwise 案例已迁移</h1><p><a href="%s">前往 DCC-MCP 官网的 Wwise 案例</a></p>
<p><a href="%s">返回 DCC-MCP Showcase 作品合集</a></p></main></body></html>
""" % (esc(target), esc(target), esc(target), esc(SITE_URL))
    return {"wwise/index.html": page, "wwise.html": page}

def output_path(root: str, out_dir: str) -> str:
    # Prevent --out . or --out docs from deleting source data.
    if not re.fullmatch(r"_site(?:-[A-Za-z0-9_-]+)?", out_dir):
        raise ValueError("output must be a top-level _site or _site-* directory")
    root_abs = os.path.realpath(root)
    out_abs = os.path.join(root_abs, out_dir)
    if os.path.islink(out_abs) or getattr(os.path, "isjunction", lambda p: False)(out_abs):
        raise ValueError("output directory must not be a symbolic link or junction")
    resolved = os.path.realpath(out_abs)
    if os.path.commonpath([root_abs, resolved]) != root_abs or resolved == root_abs:
        raise ValueError("output directory must stay inside repository")
    return out_abs

def build(root: str, out_dir: str, brand_preview: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Return published paths, problems, and notes; validate before deleting."""
    published: list[str] = []
    notes: list[str] = []
    try:
        out_abs = output_path(root, out_dir)
        if brand_preview and out_dir != "_site-brand-preview":
            raise ValueError("brand development previews require --out _site-brand-preview")
        collection_path = resolve_public(root, "collection.json")
        import validate_collection
        problems = validate_collection.validate(collection_path, root=root)
        if problems:
            return [], problems, []
        import validate_brand_gallery
        brand_catalog, brand_assets, problems = validate_brand_gallery.read_and_validate(root)
        if problems:
            return [], problems, []
        brands_visible = bool(brand_catalog.get("enabled")) or brand_preview
        brand_pages = {}
        if brands_visible:
            import brand_pages as brand_renderer
            brand_pages = brand_renderer.generate(brand_catalog, root, preview=brand_preview)
        brand_nav = '<a href="brands/">品牌画廊</a>' if brands_visible else ""
        brand_portal = ('<section class="project-portal" aria-label="品牌画廊"><p>标识、组合与矢量资源。'
                        '逐项记录制作过程、版本、来源及使用许可。</p><div class="project-links">'
                        '<a href="brands/">浏览品牌画廊 →</a></div></section>') if brands_visible else ""
        if brand_preview:
            notes.append("LOCAL DEVELOPMENT PREVIEW: pending brand assets are not approved for publication")
            brand_portal = '<aside class="evidence-note"><strong>品牌画廊开发预览</strong><p>等待修正版资产与验证记录；占位内容仅用于本地开发。</p></aside>' + brand_portal
        with open(collection_path, encoding="utf-8-sig") as fh:
            cases = json.load(fh)["cases"]
        with open(resolve_public(root, "index.html"), encoding="utf-8-sig") as fh:
            template = fh.read()
        software = sorted({value for case in cases for value in case["software"]})
        capabilities = sorted({value for case in cases for value in case["capabilities"]})
        substitutions = {"CASE_COUNT": str(len(cases)), "SOFTWARE_COUNT": str(len(software)),
                         "SOFTWARE_FILTERS": filters(software), "CAPABILITY_FILTERS": filters(capabilities),
                         "BRAND_NAV": brand_nav, "BRAND_PORTAL": brand_portal,
                          "CASE_CARDS": cards_markup(cases, root),
                         "SEO_HEAD": seo_tags(
                             "DCC-MCP Showcase · 真实 DCC 作品与可复用流程",
                             "DCC-MCP 官方作品合集：真实 DCC 软件中的建模、程序化材质与跨软件创作，附提示词、步骤、工程资源及验证证据。",
                             "", cases[0]["cover"], root, collection_metadata(cases))}
        for key, value in substitutions.items():
            template = template.replace("{{%s}}" % key, value)
        if re.search(r"\{\{[A-Z_]+\}\}", template):
            raise ValueError("unresolved homepage template token")
        pages = {"index.html": template,
                 "sitemap.xml": sitemap_text(cases, [item["slug"] for item in brand_catalog.get("items", [])] if brands_visible and not brand_preview else None),
                 "robots.txt": "User-agent: *\nAllow: /showcase/\nSitemap: " + public_url("sitemap.xml") + "\n"}
        pages.update(brand_pages)
        if brand_preview:
            pages["robots.txt"] = "User-agent: *\nDisallow: /\n"
            pages["index.html"] = pages["index.html"].replace("index, follow, max-image-preview:large", "noindex, nofollow")
        pages.update(compatibility_pages())
        assets = {"assets/site.css", "assets/gallery.js", "assets/detail.js"}
        if brands_visible:
            assets.update({"assets/brand.css", "assets/brand.js"})
            assets.update(brand_assets)
        for index, case in enumerate(cases):
            if not SLUG.fullmatch(case["slug"]):
                raise ValueError("invalid case slug")
            pages["cases/%s/index.html" % case["slug"]] = detail_page(
                case, root, cases[(index + 1) % len(cases)] if len(cases) > 1 else None)
            if brands_visible:
                case_path = "cases/%s/index.html" % case["slug"]
                pages[case_path] = pages[case_path].replace('<a href="https://dcc-mcp.github.io/">DCC-MCP 官网', '<a href="../../brands/">品牌画廊</a><a href="https://dcc-mcp.github.io/">DCC-MCP 官网')
                if brand_preview:
                    pages[case_path] = pages[case_path].replace("index, follow, max-image-preview:large", "noindex, nofollow")
            base = "docs/showcase/%s" % case["slug"]
            for required in ("README.md", "manifest.json", "validation.json"):
                assets.add(base + "/" + required)
            with open(resolve_public(root, base + "/manifest.json"), encoding="utf-8-sig") as fh:
                manifest = json.load(fh)
            for item in manifest["files"]:
                assets.add(base + "/" + safe_rel(item["path"]))
            media = [case["cover"]] + case["results"] + [step["image"] for step in case["steps"] if step.get("image")]
            for item in media:
                assets.add(safe_rel(item["src"]))
                if item.get("poster"):
                    assets.add(safe_rel(item["poster"]))
            for item in case["resources"]:
                resource_url(item["url"])
                if not urlsplit(item["url"]).scheme:
                    assets.add(safe_rel(item["url"]))
        # Every file is selected explicitly, rather than discovered by crawling.
        sources = {rel: resolve_public(root, rel) for rel in sorted(assets)}
        problems = []
        for rel, src in sources.items():
            # Brand download sizes, SVG safety and hashes have their own contract.
            # The case display-width ceiling must not reject a verified large PNG download.
            if rel not in brand_assets:
                problems.extend(check_media(rel, src))
        for rel, text in pages.items():
            for child in refs_of(text, rel):
                if child not in pages and child not in sources:
                    problems.append("%s: references an unpublished file %s" % (rel, child))
        for rel, src in sources.items():
            if os.path.splitext(rel)[1].lower() in FOLLOW:
                with open(src, encoding="utf-8-sig") as fh:
                    for child in refs_of(fh.read(), rel):
                        if child not in pages and child not in sources:
                            problems.append("%s: references an unpublished file %s" % (rel, child))
        if problems:
            return [], problems, notes
        if os.path.isdir(out_abs):
            shutil.rmtree(out_abs)
        os.makedirs(out_abs)
        for rel, text in pages.items():
            dst = os.path.join(out_abs, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text.rstrip() + "\n")
            published.append(rel)
        for rel, src in sources.items():
            dst = os.path.join(out_abs, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            published.append(rel)
        with open(os.path.join(out_abs, ".nojekyll"), "w", encoding="utf-8"):
            pass
        return sorted(published), [], notes
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        return [], [str(exc)], notes

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="_site", help="top-level output directory (_site or _site-*)")
    parser.add_argument("--preview-brands", action="store_true", help="local unpublished brand development preview (requires --out _site-brand-preview)")
    args = parser.parse_args(argv[1:])
    root = repo_root()
    published, problems, notes = build(root, args.out, brand_preview=args.preview_brands)
    if not problems:
        total = sum(os.path.getsize(os.path.join(root, args.out, rel)) for rel in published)
        print("built %d files into %s/ (%.1f MiB)" % (len(published), args.out, total / 1048576.0))
    for note in notes:
        print("NOTE %s" % note)
    for problem in problems:
        print("FAIL %s" % problem)
    if problems:
        print("%d problem(s); site not published" % len(problems))
        return 1
    print("OK all selected cases, references and media satisfy the publication contract")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
