"""Secondary, read-only views of the already selected public case records.

The parent builder validates collection and playable manifests before calling
generate(). The catalog never discovers files, reads artifact contents, infers
licenses, or converts a workflow record into an accepted benchmark case. The
page reuses the site's ordinary share-image metadata helper.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


# Exact source-text pairs for the existing fail-closed localization pipeline.
# The machine index intentionally retains original record text in both locales.
AGENT_TRANSLATIONS = {
    "Agent 与数据": "Agent & Data",
    "Agent 与数据 | DCC-MCP Showcase": "Agent & Data | DCC-MCP Showcase",
    "公开制作记录的结构化入口；保留来源、模型分工、验证边界与逐项权利说明。": "A structured entry point to public production records, preserving sources, model roles, verification limits and scoped rights notices.",
    "跳到数据说明": "Skip to data notes",
    "制作记录，供进一步核对。": "Production records, ready for closer inspection.",
    "这里汇集画廊已选作品的公开元数据，方便查找提示词、软件环境、工具、检查与原始文件清单。": "Explore metadata for works already selected in the gallery, with prompts, software environments, tools, checks and original file inventories.",
    "读取 JSON 索引": "Read the JSON index",
    "展示范围与使用权利": "Publication scope and usage rights",
    "公开展示只描述当前选录状态，不构成训练、评测或再分发的许可。": "Public display describes the current selection only. It does not grant permission for training, evaluation or redistribution.",
    "本索引不授予训练或评测权利。未知或未核实的权利保持未授予；现有逐项许可原文保留，不自动解释或扩大其范围。": "This index grants no training or evaluation rights. Unknown or unverified rights remain not granted here; existing item-specific license text is retained without automatic interpretation or expansion.",
    "站点代码的 MIT 许可不会自动覆盖作品、原生工程、音频或第三方素材；请核对各案例及具体文件的权利说明。": "The site-code MIT license does not automatically cover artwork, native projects, audio or third-party materials. Check each case and file's scoped rights notices.",
    "读取记录": "Reading the records",
    "模型归属按策划、制作、代码、参考、后期与审阅阶段保留。未知值不补写；模型名称不代表作品质量。": "Model attribution is preserved by planning, creation, code, reference, post-production and review stage. Unknown values remain unknown; model names are not quality ratings.",
    "提示词保留原始或复用模板标记；检查结果连同失败、未运行项目和已知限制一起记录。": "Prompts retain their original or reusable-template labels. Checks retain failures, unrun steps and known limitations.",
    "JSON 保留源记录的原文与标题，可能混合中文和英文；网页翻译不改写来源、哈希或许可文本。": "The JSON preserves source titles and text, which may mix Chinese and English. Page translations do not rewrite source records, hashes or license text.",
    "文件 SHA-256 来自已发布清单；清单本身另有字节哈希。外部链接与未列入清单的必需记录不会获得推测的文件哈希。": "File SHA-256 values come from the published inventories; each manifest also has its own byte hash. External links and required records absent from an inventory receive no inferred file hashes.",
    "未来训练与评测": "Future training and evaluation",
    "这些条目是任务与流程记录，尚未被接纳为评测案例；这里不发布模型排名、分数或内部基准。": "These are task and workflow records, not accepted benchmark cases. This page publishes no model rankings, scores or internal benchmarks.",
    "未来如需构建训练或评测集合，应先分别核实用途、文件范围、权利人及明确授权，再进行独立的案例接纳与验证。": "A future training or evaluation collection would first need separate verification of purpose, file scope, rights holders and explicit permission, followed by independent case acceptance and validation.",
    "筛选条件应按用途分别要求已核实授权；未知、未授予或范围不符的记录均不纳入。当前索引不是可用数据集的声明。": "Future filters should require verified permission for each intended use and exclude unknown, not-granted or out-of-scope records. This index does not claim an available dataset.",
    "已选公开记录": "Selected public records",
    "每项链接回到作品本身、制作过程和原始清单。": "Each entry links back to the work, its production record and original inventory.",
    "查看作品": "View work",
    "制作与模型记录": "Production and model record",
    "来源与哈希": "Sources and hashes",
    "当前没有选录记录。": "No records are currently selected.",
}

TITLE = "Agent 与数据 | DCC-MCP Showcase"
DESCRIPTION = "公开制作记录的结构化入口；保留来源、模型分工、验证边界与逐项权利说明。"
SOURCE_FIELDS = (
    "slug", "title", "subtitle", "software", "capabilities", "summary", "goal",
    "prompt", "environment", "tools", "steps", "checks", "limitations",
    "resources", "credits", "source", "verified_at", "model_attribution",
    "revision_notes", "evidence_label", "evidence_scope",
)


def _site():
    # Delayed import avoids a cycle when called by the builder.
    import build_site
    return build_site


def _usage_rights():
    return {
        "display": {"status": "unknown", "evidence": []},
        "training": {"status": "not-granted", "evidence": []},
        "evaluation": {"status": "not-granted", "evidence": []},
    }


def _manifest(root, path, base):
    """Read an explicit inventory; project only file paths, sizes and hashes."""
    site = _site()
    raw = Path(site.resolve_public(root, path)).read_bytes()
    manifest = json.loads(raw.decode("utf-8-sig"))
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        raise ValueError("agent index: unsupported public inventory")
    binding = {"path": path, "url": site.public_url(path),
               "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
               "hash_source": "manifest-bytes"}
    files = {}
    for item in manifest["files"]:
        rel = site.safe_rel(item["path"])
        path = base + rel
        # Resolve only listed paths, including symlink containment checks.
        site.resolve_public(root, path)
        if path in files:
            raise ValueError("agent index: duplicate inventoried file")
        if (not isinstance(item.get("sha256"), str)
                or not re.fullmatch(r"[a-fA-F0-9]{64}", item["sha256"])
                or type(item.get("bytes")) is not int or item["bytes"] < 0):
            raise ValueError("agent index: inventoried file requires bytes and SHA-256")
        files[path] = {"path": path, "manifest_path": item["path"],
                       "url": site.public_url(path), "sha256": item["sha256"],
                       "bytes": item["bytes"], "hash_source": "manifest",
                       "manifest_url": binding["url"]}
    return binding, files


def _reference(root, raw, files, required):
    site = _site()
    import validate_collection
    if validate_collection.link_problems(raw, Path(root), "agent index reference"):
        raise ValueError("agent index: unsafe public reference")
    if urlsplit(raw).scheme:
        return {"source_url": raw, "url": raw, "integrity": "external-reference-only"}
    path = site.safe_rel(raw)
    if path in files:
        return {"source_url": raw, **files[path]}
    if path in required:
        return {"source_url": raw, "path": path, "url": site.public_url(path),
                "integrity": "selected-required-record-not-in-file-inventory"}
    raise ValueError("agent index: local reference is outside selected public inventories")


def _catalog(root, cases, demos):
    site = _site()
    import validate_collection
    manifests, inventory, required, slugs = {}, {}, set(), set()
    for case in cases:
        slug = case["slug"]
        if not isinstance(slug, str) or not site.SLUG.fullmatch(slug) or slug in slugs:
            raise ValueError("agent index: invalid or duplicate selected case")
        slugs.add(slug)
        base = "docs/showcase/%s/" % slug
        manifests[slug] = _manifest(root, base + "manifest.json", base)
        inventory.update(manifests[slug][1])
        required.update(base + name for name in ("README.md", "manifest.json", "validation.json"))
    selected_demos = {slug: demos[slug] for slug in slugs if slug in demos}
    play_manifest = None
    if selected_demos:
        play_manifest, play_files = _manifest(root, "play/manifest.json", "")
        if any(not path.startswith("play/") for path in play_files):
            raise ValueError("agent index: playable reference is outside public play inventory")
        inventory.update(play_files)
    records = []
    for case in cases:
        # New source fields, including any future permission claim, cannot
        # silently enter this projection or change its conservative policy.
        record = {key: copy.deepcopy(case[key]) for key in SOURCE_FIELDS if key in case}
        slug = record["slug"]
        manifest, files = manifests[slug]
        base = "docs/showcase/%s/" % slug
        record["record_kind"] = "task-and-workflow-metadata"
        record["publication_status"] = "selected-public-record"
        record["usage_rights"] = _usage_rights()
        record["rights_verified"] = False
        record["benchmark"] = {"status": "not-an-accepted-benchmark"}
        record["public_references"] = {
            "case_url": site.public_url("cases/%s/" % slug),
            "report": _reference(root, base + "README.md", inventory, required),
            "validation": _reference(root, base + "validation.json", inventory, required),
            "manifest": manifest,
            "files": list(files.values()),
            "resources": [_reference(root, item["url"], inventory, required)
                          for item in case.get("resources", [])],
        }
        # Validate embedded workflow image references, but do not duplicate
        # image bytes or create any newly selected download.
        for step in record.get("steps", []):
            for key in ("src", "poster"):
                if key in step.get("image", {}):
                    _reference(root, step["image"][key], inventory, required)
        if slug in selected_demos:
            demo = selected_demos[slug]
            entry = _reference(root, demo["url"], inventory, set())
            if entry.get("hash_source") != "manifest":
                raise ValueError("agent index: playable entry must be inventoried")
            record["playable"] = {
                key: copy.deepcopy(demo[key]) for key in
                ("engine", "renderer", "threads", "controls", "notes", "localeSupport", "nativeTextLanguage")
                if key in demo
            }
            record["playable"].update({"entry": entry, "manifest": play_manifest})
        if validate_collection.scan_values(record, "agent index record"):
            raise ValueError("agent index: selected record contains unsafe public metadata")
        records.append(record)
    return {
        "schema_version": 1,
        "schema_id": "dcc-showcase-catalog/v1",
        "kind": "selected-public-workflow-index",
        "title": "DCC-MCP Showcase: selected public production records",
        "scope": "selected-public-records-only",
        "source_text": {"mode": "original-untranslated", "languages": ["zh-CN", "en"],
                        "note": "Titles and source prose retain the selected collection record's original text. Website translations are presentation only."},
        "publication_status": "selected-public-records",
        "usage_rights": _usage_rights(),
        "rights_verified": False,
        "rights_note": "Credits and asset-specific license text are retained separately in each record. Repository MIT does not automatically relicense artwork or other case assets. This index makes no additional license grant.",
        "benchmark": {"status": "not-an-accepted-benchmark", "model_quality_inferred": False,
                      "note": "No accepted benchmark, competitive model ranking, score or internal benchmark is published here."},
        "future_use": {"available_dataset": False,
                       "required_before_inclusion": ["Verify explicit permission separately for training and evaluation, for the exact files and purpose.",
                                                     "Exclude unknown, not-granted and out-of-scope rights; do not infer permission from a license label.",
                                                     "Apply independent case acceptance, versioning and validation after the rights review."]},
        "record_count": len(records), "records": records,
    }


def _page(root, cases):
    site = _site()
    structured = {"@context": "https://schema.org", "@type": "CollectionPage",
                  "name": TITLE, "description": DESCRIPTION,
                  "url": site.public_url("agents/"), "inLanguage": "zh-CN",
                  "isPartOf": {"@type": "WebSite", "name": "DCC-MCP Showcase", "url": site.SITE_URL}}
    cover = cases[0]["cover"] if cases else {"src": "", "alt": ""}
    head = site.seo_tags(TITLE, DESCRIPTION, "agents/", cover, root, structured)
    rows = []
    for case in cases:
        path = "../cases/%s/" % case["slug"]
        rows.append('<li class="agent-record"><h3><a href="%s">%s</a></h3>'
                    '<p>%s</p><div class="project-actions">'
                    '<a class="text-link" href="%s">查看作品</a>'
                    '<a class="text-link" href="%s#models">制作与模型记录</a>'
                    '<a class="text-link" href="../docs/showcase/%s/manifest.json">来源与哈希</a>'
                    '</div></li>' % (site.esc(path), site.esc(case["title"]), site.esc(case["subtitle"]),
                                    site.esc(path), site.esc(path), site.esc(case["slug"])))
    records = '<ul class="tool-list agent-records">%s</ul>' % ''.join(rows) if rows else '<p>当前没有选录记录。</p>'
    return '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
%s<meta name="theme-color" content="#101311"><link rel="stylesheet" href="../assets/site.css"></head>
<body class="agent-page"><a class="skip-link" href="#agent-content">跳到数据说明</a>
<header class="site-header wrap"><a class="brand" href="../" aria-label="DCC-MCP Showcase 首页"><strong>DCC-MCP</strong><span>Showcase</span></a>
<nav aria-label="主导航"><a href="../#works">作品合集</a><a href="./" aria-current="page">Agent 与数据</a><a href="https://dcc-mcp.github.io/">DCC-MCP 官网 ↗</a></nav></header>
<main class="wrap" id="agent-content"><section class="hero"><p class="eyebrow">DCC-MCP · AGENT &amp; DATA</p><h1>制作记录，供进一步核对。</h1>
<p class="hero-intro">这里汇集画廊已选作品的公开元数据，方便查找提示词、软件环境、工具、检查与原始文件清单。</p>
<a class="text-link" href="../data/catalog.json" type="application/json">读取 JSON 索引 <span aria-hidden="true">↗</span></a></section>
<aside class="evidence-note" aria-labelledby="agent-rights-title"><strong id="agent-rights-title">展示范围与使用权利</strong><div>
<p>公开展示只描述当前选录状态，不构成训练、评测或再分发的许可。</p>
<p>本索引不授予训练或评测权利。未知或未核实的权利保持未授予；现有逐项许可原文保留，不自动解释或扩大其范围。</p>
<p>站点代码的 MIT 许可不会自动覆盖作品、原生工程、音频或第三方素材；请核对各案例及具体文件的权利说明。</p></div></aside>
<div class="detail-layout"><nav class="detail-nav" aria-label="案例目录"><a href="#reading">读取记录</a><a href="#future-use">未来训练与评测</a><a href="#records">已选公开记录</a></nav>
<div class="detail-content"><section class="detail-section" id="reading"><h2>读取记录</h2>
<p>模型归属按策划、制作、代码、参考、后期与审阅阶段保留。未知值不补写；模型名称不代表作品质量。</p>
<p>提示词保留原始或复用模板标记；检查结果连同失败、未运行项目和已知限制一起记录。</p>
<p>JSON 保留源记录的原文与标题，可能混合中文和英文；网页翻译不改写来源、哈希或许可文本。</p>
<p>文件 SHA-256 来自已发布清单；清单本身另有字节哈希。外部链接与未列入清单的必需记录不会获得推测的文件哈希。</p></section>
<section class="detail-section" id="future-use"><h2>未来训练与评测</h2>
<p>这些条目是任务与流程记录，尚未被接纳为评测案例；这里不发布模型排名、分数或内部基准。</p>
<p>未来如需构建训练或评测集合，应先分别核实用途、文件范围、权利人及明确授权，再进行独立的案例接纳与验证。</p>
<p>筛选条件应按用途分别要求已核实授权；未知、未授予或范围不符的记录均不纳入。当前索引不是可用数据集的声明。</p></section>
<section class="detail-section" id="records"><h2>已选公开记录</h2><p>每项链接回到作品本身、制作过程和原始清单。</p>%s</section></div></div>
<div class="detail-footer"><a href="../#works">← 返回作品合集</a><a href="../data/catalog.json">读取 JSON 索引</a></div></main>
<footer class="site-footer wrap"><p>DCC-MCP Showcase</p><nav aria-label="页脚导航"><a href="https://dcc-mcp.github.io/">DCC-MCP 官网 ↗</a><a href="https://github.com/dcc-mcp/showcase">合集源码 ↗</a></nav></footer></body></html>
''' % (head, records)


def generate(root, cases, demos):
    """Return localized-page inputs and a single untranslated JSON projection.

    Inputs must already have passed collection/playable publication validation.
    The returned data is generated text, never an additional source-file list.
    """
    cases = list(cases)
    catalog = _catalog(root, cases, demos or {})
    return ({"agents/index.html": _page(root, cases)},
            {"data/catalog.json": json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"})
