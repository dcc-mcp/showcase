"""Read-only gallery projection of the producer's authoritative brand snapshot.

The gallery keeps a manifest pointer, not a second hand-maintained asset list.
This initial projection supports the corrected core wordmarks. New families
require an explicit mapping and their own reviewed production evidence.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import validate_collection as common


SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
TOOLS = {"document_build": "inkscape_vector__document_build",
         "document_export": "inkscape_vector__document_export"}


def _require(condition, message):
    if not condition:
        # Never include record values in diagnostics: malformed input may be
        # private. The caller converts failure to a publication contract error.
        raise ValueError("brand manifest: " + message)


def _string(value):
    return isinstance(value, str) and bool(value.strip())


def _sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _commit(value):
    return isinstance(value, str) and COMMIT.fullmatch(value) is not None


def _integer(value):
    return type(value) is int and value >= 0


def _utc(value):
    _require(_string(value), "recorded timestamp required")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("brand manifest: ISO timestamp required") from None
    _require(stamp.tzinfo is not None, "timestamp timezone required")
    return stamp


def _file(base, rel, root):
    target = common.local_file(rel, base)
    _require(target is not None and target.is_relative_to(root), "safe existing local file required")
    return target


def _json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("brand manifest: readable JSON required") from None
    _require(isinstance(value, dict), "JSON object required")
    _require(not common.scan_values(value, "brand manifest"), "private metadata forbidden")
    _require(not re.search(r"\\(?:Device|GLOBALROOT)\\", json.dumps(value)), "private device path forbidden")
    _require(not re.search(r"\blibfile_[a-zA-Z0-9]+", json.dumps(value)), "private Library identity forbidden")
    def private_keys(obj):
        if isinstance(obj, dict):
            return any(re.search(r"(?:^|_)pid$", str(key)) or key in ("backend_port", "service_session", "instance_id", "nonce")
                       or private_keys(child) for key, child in obj.items())
        return isinstance(obj, list) and any(private_keys(child) for child in obj)
    _require(not private_keys(value), "private runtime identifiers forbidden")
    return value


def _rows(value, label):
    _require(isinstance(value, list) and value and all(isinstance(v, dict) for v in value),
             label + " must be a nonempty object array")
    return value


def _indexed(rows, key, label):
    result = {}
    for row in rows:
        identity = row.get(key)
        _require(_string(identity) and identity not in result, label + " identifiers must be unique")
        result[identity] = row
    return result


def _integrity(asset, path):
    data = path.read_bytes()
    _require(_integer(asset.get("bytes")) and asset["bytes"] == len(data), "asset byte count mismatch")
    _require(_sha(asset.get("sha256")) and hashlib.sha256(data).hexdigest() == asset["sha256"],
             "asset SHA-256 mismatch")
    return data


def _visual_check(visual, assets):
    _require(visual.get("qa_status") == "verified" and visual.get("visual_review_complete") is True,
             "completed visual review required")
    _require(visual.get("brand_design_acceptance") == "awaiting_user_review",
             "user design acceptance must remain pending")
    _utc(visual.get("visual_reviewed_utc"))
    for field in ("actual_native_paths_match_proposed", "dark_native_paths_match_proposed"):
        _require(visual.get(field) == {"dcc-c1": True, "dcc-c2": True}, "both C path checks required")
    for field in ("changed_native_ids_light", "changed_native_ids_dark"):
        _require(isinstance(visual.get(field), list) and set(visual[field]) == {"dcc-c1", "dcc-c2"},
                 "C-only geometry change scope required")
    _require(visual.get("non_cc_native_attribute_changes") == [], "unexpected non-C geometry change")
    c1, c2 = visual.get("c1", {}), visual.get("c2", {})
    turn = c1.get("max_internal_curve_tangent_turn_degrees")
    _require(type(turn) in (int, float) and math.isfinite(turn) and 0 <= turn <= 0.0001,
             "C1 tangent continuity check mismatch")
    claim = c1.get("continuity_claim", "")
    _require("G1" in claim and "not G2" in claim, "C1 G1-only evidence boundary required")
    separation = c2.get("center_separation_design_px")
    _require(type(separation) in (int, float) and math.isfinite(separation) and 0 <= separation <= 0.000002,
             "C2 concentricity check mismatch")
    _require(c2.get("radii_design_px") == [100, 63] and c2.get("nominal_radial_thickness_design_px") == 37,
             "C2 radius and thickness checks required")
    reviewed = _rows(visual.get("native_sources"), "visual native sources") + _rows(visual.get("raster_sources"), "visual raster sources")
    for asset in assets:
        if asset["kind"] == "svg" and asset["role"] == "release":
            continue  # outlined exports are linked by their real MCP receipts
        matches = [v for v in reviewed if isinstance(v.get("path"), str)
                   and (v["path"] == asset["path"] or v["path"].endswith("/" + asset["path"]))]
        _require(len(matches) == 1 and matches[0].get("sha256") == asset["sha256"]
                 and matches[0].get("bytes") == asset["bytes"], "visual review asset hash mismatch")
        if asset["kind"] == "png":
            _require(matches[0].get("size") == asset["size"], "visual review raster size mismatch")


def _snapshot(root, manifest_rel):
    manifest_path = _file(root, manifest_rel, root)
    _require(manifest_path.suffix.lower() == ".json", "local JSON manifest required")
    base = manifest_path.parent
    manifest = _json(manifest_path)
    _require(type(manifest.get("schema_version")) is int and manifest["schema_version"] == 2,
             "producer schema 2 required")
    _require(manifest.get("authoritative_asset_map") is True and manifest.get("status") == "partial_actual_core",
             "reviewed partial-core snapshot required")
    publication = manifest.get("publication", {})
    _require(isinstance(publication, dict) and _sha(publication.get("source_manifest_sha256")),
             "source snapshot identity required")
    _require(publication.get("comparison_published") is False and _string(publication.get("scope")),
             "public evidence scope required")
    _require(isinstance(publication.get("metadata_redactions"), list) and publication["metadata_redactions"],
             "public evidence redactions required")
    ledger_path = _file(base, publication.get("mcp_evidence"), root)
    visual_path = _file(base, publication.get("visual_evidence"), root)
    font_notice_path = _file(base, publication.get("font_notice"), root)
    license_path = _file(base, "LICENSE", root)
    trademark_path = _file(base, "THIRD_PARTY_NOTICES.md", root)
    for notice in (font_notice_path, license_path, trademark_path):
        _require(not common.scan_text_file(notice, root), "private license metadata forbidden")
    ledger, visual = _json(ledger_path), _json(visual_path)
    _require(type(ledger.get("schema_version")) is int and ledger["schema_version"] == 1
             and _string(ledger.get("evidence_scope")), "scoped public MCP ledger required")
    families = _indexed(_rows(manifest.get("families"), "families"), "family_id", "family")
    _require(all(common.SLUG.fullmatch(key) and _string(row.get("display_product")) for key, row in families.items()),
             "safe family identity required")
    _require(type(manifest.get("family_count")) is int and manifest["family_count"] == len(families),
             "declared family count mismatch")
    _require("core" in families and families["core"].get("production_status") == "partial_actual_core_wordmarks",
             "core must remain partially delivered")
    for key, row in families.items():
        if key != "core":
            _require(row.get("production_status") == "planned_not_executed" and row.get("actual_asset_ids") == [],
                     "unsupported or unexecuted family cannot publish")
    assets = _rows(manifest.get("assets"), "assets")
    indexed_assets = _indexed(assets, "asset_id", "asset")
    _require(len(assets) == 8 and type(manifest.get("actual_asset_count")) is int
             and manifest["actual_asset_count"] == len(assets), "declared actual asset count mismatch")
    _require(type(manifest.get("actual_family_count")) is int and manifest["actual_family_count"] == 1,
             "declared actual family count mismatch")
    ids = families["core"].get("actual_asset_ids")
    _require(isinstance(ids, list) and len(ids) == len(indexed_assets) and set(ids) == set(indexed_assets),
             "family actual asset inventory mismatch")
    calls = _indexed(_rows(ledger.get("calls"), "MCP calls"), "key", "MCP call")
    receipts = _indexed(_rows(manifest.get("mcp_receipts"), "MCP receipts"), "key", "MCP receipt")
    _require(len(calls) == len(receipts) == len(assets), "exact output receipt scope required")
    toolchain = manifest.get("toolchain", {})
    _require(isinstance(toolchain, dict) and _commit(toolchain.get("runtime_source_commit"))
             and _commit(toolchain.get("public_head_commit")), "fixed adapter source revisions required")
    _require(not common.link_problems(toolchain.get("public_repository"), root, "adapter"),
             "public adapter repository required")
    _require(toolchain.get("application_version") == "Inkscape 1.4.4"
             and toolchain.get("core_version") == "0.20.36" and toolchain.get("gateway_cli_version") == "0.20.38",
             "reviewed production environment mismatch")
    acceptance = manifest.get("acceptance", {})
    _require(acceptance.get("geometry_and_raster_visual_review") == "verified"
             and acceptance.get("brand_design_acceptance") == "awaiting_user_review"
             and acceptance.get("family_production") == "in_progress",
             "acceptance scope mismatch")
    matrix, paths, receipt_keys = {}, set(), set()
    from validate_brand_gallery import png_check, svg_check
    for asset in assets:
        _require(asset.get("family") == "core" and asset.get("status") == "actual"
                 and asset.get("qa_status") == "verified" and asset.get("license") == "MIT",
                 "only verified actual core artwork can publish")
        path = _file(base, asset.get("path"), root)
        _require(path not in paths, "duplicate asset path")
        paths.add(path)
        data = _integrity(asset, path)
        theme, kind, role = asset.get("theme"), asset.get("kind"), asset.get("role")
        _require(theme in ("light", "dark") and kind in ("svg", "png") and role in ("editable", "release")
                 and path.suffix == "." + kind, "supported asset role and format required")
        if kind == "png":
            dims, problems = png_check(data, "brand manifest PNG")
            _require(not problems and isinstance(asset.get("size"), list) and list(dims or ()) == asset["size"]
                     and asset["size"] in ([1024, 455], [128, 57]) and role == "release",
                     "actual PNG dimensions mismatch")
            _require(asset.get("transparent") is True and asset.get("corner_alpha") == [0, 0, 0, 0],
                     "transparent raster evidence required")
            matrix_key = (theme, kind, asset["size"][0])
        else:
            viewbox, problems = svg_check(data, "brand manifest SVG")
            _require(not problems and viewbox == asset.get("viewbox") == [0, 0, 900, 400],
                     "safe actual SVG viewBox required")
            live = any(node.tag == "{http://www.w3.org/2000/svg}text" for node in ET.fromstring(data).iter())
            _require(type(asset.get("live_text")) is bool and asset["live_text"] == live
                     and live == (role == "editable"), "actual SVG text role mismatch")
            matrix_key = (theme, kind, role)
        _require(matrix_key not in matrix, "duplicate preview or release variant")
        matrix[matrix_key] = asset
        producer = asset.get("producer", {})
        key = producer.get("receipt_key")
        _require(_string(key) and key in receipts and key in calls and key not in receipt_keys,
                 "unique actual output receipt required")
        receipt_keys.add(key)
        receipt, call = receipts[key], calls[key]
        operation = "document_build" if role == "editable" else "document_export"
        _require(receipt.get("operation") == operation and call.get("tool") == TOOLS[operation],
                 "actual MCP tool and operation mismatch")
        digest = asset["sha256"]
        _require(receipt.get("output_sha256") == call.get("artifact_sha256") == digest,
                 "receipt output SHA-256 mismatch")
        response = call.get("response", {})
        _require(isinstance(response, dict) and response.get("success") is True
                 and isinstance(response.get("context"), dict) and response["context"].get("sha256") == digest
                 and response["context"].get("bytes") == asset["bytes"],
                 "successful MCP response context SHA-256 mismatch")
        _require(isinstance(call.get("arguments"), dict) and call["arguments"]
                 and call.get("gateway_stats_recorded") is True and _sha(call.get("original_completed_record_sha256")),
                 "actual request and recorded gateway response required")
        _require(producer.get("source_commit") == receipt.get("source_commit") == call.get("source_commit")
                 == toolchain["runtime_source_commit"] and producer.get("application") == toolchain["application_version"],
                 "production source revision mismatch")
        _require(receipt.get("control_route") == call.get("control_route") == "gateway", "gateway route required")
        _require(_utc(call.get("recorded_utc")) == _utc(receipt.get("recorded_utc")), "receipt timestamp mismatch")
    expected = {(theme, "svg", role) for theme in ("light", "dark") for role in ("editable", "release")}
    expected |= {(theme, "png", width) for theme in ("light", "dark") for width in (128, 1024)}
    _require(set(matrix) == expected and receipt_keys == set(calls) == set(receipts), "complete two-theme output matrix required")
    _visual_check(visual, assets)
    return manifest_path, manifest, matrix, ledger_path, visual_path, font_notice_path, license_path, trademark_path, visual


def _project(root, manifest_rel):
    """Return a standard enabled catalog without writing or discovering files."""
    root = Path(root).resolve()
    path, manifest, matrix, ledger, visual_path, font_notice, license_path, trademark_path, visual = _snapshot(root, manifest_rel)
    base = path.parent
    def url(target):
        return target.relative_to(root).as_posix()
    def asset_url(asset):
        return url(_file(base, asset["path"], root))
    def preview(theme, width):
        asset = matrix[(theme, "png", width)]
        return {"src": asset_url(asset), "alt": "修正后的 DCC-MCP 核心字标 · " + ("浅色" if theme == "light" else "深色") + "背景 · 实际 " + str(width) + " 像素导出",
                "width": asset["size"][0], "height": asset["size"][1]}
    variants = []
    for asset in manifest["assets"]:
        theme = "浅色" if asset["theme"] == "light" else "深色"
        label = ("可编辑原生 SVG · MCP 文字保留" if asset["role"] == "editable" else "轮廓化 SVG · MCP 文字转路径") if asset["kind"] == "svg" else "PNG · %d × %d" % tuple(asset["size"])
        variant = {"label": theme + " · " + label, "url": asset_url(asset), "format": asset["kind"], "bytes": asset["bytes"], "sha256": asset["sha256"],
                   "rights_ids": ["artwork", "font", "trademark"], "source_id": "production"}
        if asset["kind"] == "svg":
            variant["viewBox"] = list(asset["viewbox"])
            variant["note"] = ("保留可编辑 Montserrat 文字；编辑需安装对应字体。字体许可独立，字体文件未随作品分发。"
                               if asset["role"] == "editable" else "MCP 文字已转路径，无需安装字体即可显示。")
        else:
            variant.update(width=asset["size"][0], height=asset["size"][1])
        variants.append(variant)
    toolchain = manifest["toolchain"]
    caption_font = visual.get("caption_font", {})
    _require(_sha(caption_font.get("sha256")) and caption_font.get("family") == "Montserrat"
             and caption_font.get("license") == "SIL Open Font License 1.1", "recorded font identity required")
    production_source = {"id": "production", "label": "制作任务原始 manifest 的公开快照", "url": url(path),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "author": "DCC-MCP contributors"}
    item = {
        "slug": "dcc-mcp-core-v2", "title": "DCC-MCP 核心字标 · C 曲线修正", "family": "DCC-MCP", "software": ["Inkscape"],
        "version": "v2 · 核心字标", "summary": "保留交织字母、像素起点和协议连线，修正两处 C 的曲线接合；提供经过核验的深浅主题矢量与真实尺寸导出。",
        "status": "verified", "verified_at": visual["visual_reviewed_utc"], "previews": {theme: preview(theme, 1024) for theme in ("light", "dark")},
        "small_previews": {theme: preview(theme, 128) for theme in ("light", "dark")}, "variants": variants,
        "prompt": {"kind": "reusable", "text": "使用 DCC-MCP 的 Inkscape 原生矢量工具修正 DCC-MCP 核心字标的两个 C。保留 900 × 400 画布、D 的交织尾部、像素起点、协议连线与 MCP 排版。C1 曲线接合达到 G1 连续，保留非等厚轮廓和平斜端面；C2 使用同心圆弧，外半径 100、内半径 63、径向厚度 37，保留平直径向端面。分别构建深浅主题可编辑 SVG，通过实际软件导出文字轮廓化 SVG，以及透明 1024 × 455 和 128 × 57 PNG。记录每次 MCP 请求响应、输出哈希、几何和实际像素检查；不把尚未制作的其他家族标为完成。",
                   "note": "根据本轮制作目标整理的可复用提示词，并非逐字原始用户提示。真实构建计划和导出参数保留在公开 MCP 记录中。"},
        "environment": [{"label": "Inkscape", "value": toolchain["application_version"]},
                        {"label": "DCC-MCP 适配器", "value": "commit " + toolchain["runtime_source_commit"] + "；未发布开发版本。公开 draft PR 固定提交另列于来源。"},
                        {"label": "DCC-MCP Core", "value": toolchain["core_version"]},
                        {"label": "DCC-MCP Gateway / CLI", "value": toolchain["gateway_cli_version"]}],
        "tools": [{"name": TOOLS["document_build"], "description": "通过原生矢量计划构建可编辑文档、曲线与图层。"},
                  {"name": TOOLS["document_export"], "description": "由实际 Inkscape 导出透明 PNG 和文字轮廓化 SVG。"}],
        "steps": [{"title": "保留布局，修正两个 C", "description": "使用实际矢量构建计划保存深浅主题原生 SVG。视觉记录核对仅 dcc-c1 与 dcc-c2 的属性发生变化，其余图形布局保留。"},
                  {"title": "导出两主题 PNG", "description": "在实际 Inkscape 中导出 1024 × 455 与 128 × 57 透明 PNG。下图是最终浅色成品，不作为中间状态证明。", "image": preview("light", 1024)},
                  {"title": "保留可编辑与轮廓版本", "description": "原生 SVG 保留 Montserrat 可编辑文字；实际软件另导出文字转路径的发布 SVG。字体文件未随作品分发，提供独立 OFL 说明。"},
                  {"title": "核验几何与真实小尺寸", "description": "读取保存后的路径及实际 PNG，核对曲线接合、同心圆与端面；检查真正 128 像素导出的深浅背景可读性。视觉质量检查已完成，整体设计仍等待用户评价。", "image": preview("dark", 1024)}],
        "checks": [{"name": "实际成品与制作收据", "result": "pass", "observed": "8 个文件的字节数和 SHA-256 与原始 manifest、Gateway 成功响应及导出收据一致。"},
                   {"name": "C1 曲线接合", "result": "pass", "observed": "内部接合最大切线转角 %.9g°，在数值舍入内满足 G1；不声称 G2 或 C1 等厚。" % visual["c1"]["max_internal_curve_tangent_turn_degrees"]},
                   {"name": "C2 同心圆与厚度", "result": "pass", "observed": "外/内半径 100 / 63，径向厚度 37；恢复圆心偏差 %.9g 设计像素。" % visual["c2"]["center_separation_design_px"]},
                   {"name": "改动范围", "result": "pass", "observed": "深浅原生文档仅两个 C 的属性改变，其他原生图形属性保持。"},
                   {"name": "真实 128 像素导出", "result": "pass", "observed": "两张实际 128 × 57 PNG 已在对应背景查看；字母可辨，细协议线和节点在此尺寸的分离度降低。"},
                   {"name": "透明 PNG 与 SVG 角色", "result": "pass", "observed": "四张 PNG 为透明角点；两份原生 SVG 保留文字，两份发布 SVG 已轮廓化。"},
                   {"name": "本轮站点集成重跑 DCC", "result": "not_run", "observed": "制作任务另有原生 inspect 记录；本站集成读取并核验已有成品，此公开证据包仅纳入八次输出调用，不宣称本站重新执行过软件生产。"},
                   {"name": "GUI 视觉验收", "result": "not_run", "observed": "此核心快照仅记录 GUI 启动观察，不作为原生界面视觉验收证明。"},
                   {"name": "用户设计评价", "result": "not_run", "observed": "几何与像素检查完成；设计接受度等待用户审阅。"}],
        "evidence_scope": manifest["publication"]["scope"],
        "evidence": [{"label": "单一制作清单 · 状态、资产与哈希", "url": url(path)},
                     {"label": "实际 MCP 构建 / 导出请求与成功响应", "url": url(ledger)},
                     {"label": "保存路径与真实像素的视觉检查", "url": url(visual_path)}],
        "sources": [production_source,
                    {"id": "adapter", "label": "Inkscape 适配器制作源码 · 固定公开提交", "url": toolchain["public_repository"].rstrip("/") + "/tree/" + toolchain["public_head_commit"], "commit": toolchain["public_head_commit"], "author": "DCC-MCP contributors"},
                    {"id": "font-source", "label": "Montserrat 原字体来源 · 本作品未分发字体文件", "url": "https://github.com/google/fonts/blob/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf", "sha256": caption_font["sha256"], "author": "The Montserrat.Git Project Authors"}],
        "rights": [{"id": "artwork", "holder": "DCC-MCP contributors", "license": "MIT", "scope": "独立制作的新矢量几何、计划及元数据；不改变参考素材、字体或商标的权利。", "url": url(license_path), "notice": "保留贡献者与 MIT 许可；原始参考素材未作为下载分发。"},
                   {"id": "font", "holder": "The Montserrat.Git Project Authors", "license": "SIL Open Font License 1.1", "scope": "Montserrat 是文字构建与原生可编辑 SVG 的字体依赖；字体文件未分发，轮廓文字保留来源说明。", "url": url(font_notice), "notice": "字体许可与新矢量几何许可分别列明；使用可编辑文字版本需自行安装 Montserrat。"},
                   {"id": "trademark", "holder": "DCC-MCP 品牌权利人及各软件名称权利人", "license": "商标权利保留", "scope": "版权许可不授予品牌、厂商标识或背书权利；本首款不包含厂商 Logo。", "url": url(trademark_path), "notice": "软件名称用于说明制作环境。未来家族仅列制作计划，未获商标许可或完成作品的推定。"}],
        "contributors": ["DCC-MCP contributors"],
        "limitations": ["当前仅核心字标首款交付；Core 其他变体及其余家族尚未制作完成。", "网站集成检查已有成品及记录，未重新执行 Inkscape 生产。", "公开请求保留矢量计划与哈希，移除私人路径、主机、实例标识和服务连接参数。", "核心 GUI 记录仅证明启动观察；本证据范围不声称原生界面的完整验收。", "几何和像素验证与用户的设计接受度分别记录，用户评价仍待完成。", "这是依据参考布局重新构建并修正的矢量，不声称找回原始 Logo 源文件或像素完全一致。", "C1 采用 G1 接合并保留非等厚设计，不声称 G2 连续。", "前后对照图包含未确认公开许可的参考图，未纳入公开下载。"]}
    planned = [{"id": row["family_id"], "title": row["display_product"], "status": row["production_status"]} for row in manifest["families"]]
    return {"schema_version": 1, "enabled": True, "title": "DCC-MCP 品牌画廊", "description": "从核心字标开始整理品牌家族。展示实际修正成品、深浅与小尺寸预览，并记录工具、来源和制作证据。", "updated_at": visual["visual_reviewed_utc"].split("T")[0], "items": [item],
            "progress": {"completed": 1, "total": manifest["family_count"], "assets": len(variants), "description": "核心字标已交付，Core 其他变体及其余 %d 组待制作。" % (manifest["family_count"] - 1), "planned": planned}}


def project(root, manifest_rel):
    """Fail closed on malformed snapshots, without returning record values."""
    try:
        return _project(root, manifest_rel)
    except (OSError, UnicodeError, TypeError, KeyError, AttributeError, ET.ParseError, RecursionError, OverflowError):
        raise ValueError("brand manifest: malformed or unreadable production snapshot") from None
