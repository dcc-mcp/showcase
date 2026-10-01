"""Read-only gallery projection of the producer's authoritative brand snapshot.

The gallery keeps a manifest pointer, not a second hand-maintained asset list.
Supports the corrected core wordmarks and explicitly reviewed software-family
batches. New families require their own production, file and rights evidence.
"""
from __future__ import annotations

from datetime import datetime
import copy
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
SOFTWARE_FAMILIES = {"maya", "3dsmax", "blender", "houdini", "zbrush", "photoshop"}
MOTIFS = {"maya": ("triangular-wireframe-mesh", "三角线框网格"),
          "3dsmax": ("mesh-and-modifier-stack", "网格与修改器堆栈"),
          "blender": ("camera-rays-and-mesh", "相机射线与网格"),
          "houdini": ("procedural-node-network", "程序化节点网络"),
          "zbrush": ("sculpt-brush-and-wire-surface", "雕刻笔刷与线框表面"),
          "photoshop": ("raster-layers-and-brush", "栅格图层与笔刷")}


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


def _family_evidence(root, base, publication, actual, matrices):
    """Check the actual batch's file QA and its separate reference/rights plan."""
    if not actual:
        return {}
    qa_path = _file(base, publication.get("family_qa"), root)
    policy_path = _file(base, publication.get("family_policy"), root)
    qa, policy = _json(qa_path), _json(policy_path)
    _require(qa.get("pass") is True and qa.get("missing") == [] and _string(qa.get("scope")),
             "successful scoped family file QA required")
    reviews = _indexed(_rows(qa.get("families"), "family QA"), "family", "family QA")
    _require(set(reviews) == set(actual), "family QA group scope mismatch")
    policies = _indexed(_rows(policy.get("families"), "family policies"), "family_id", "family policy")
    owners = policy.get("vendor_policy_groups", {})
    _require(isinstance(owners, dict), "vendor ownership records required")
    sources = {}
    def c_paths(asset):
        return {node.get("id"): node.get("d") for node in ET.parse(_file(base, asset["path"], root)).getroot().iter()
                if node.get("id") in ("dcc-c1", "dcc-c2")}
    core_paths = c_paths(matrices["core"][("light", "svg", "editable")])
    _require(set(core_paths) == {"dcc-c1", "dcc-c2"} and all(_string(value) for value in core_paths.values()),
             "shared corrected C paths required")
    for family in actual:
        review = reviews[family]
        _require(review.get("pass") is True, "family file QA failed")
        checks = _indexed(_rows(review.get("checks"), "family QA checks"), "path", "family QA check")
        assets = list(matrices[family].values())
        _require(set(checks) == {asset["path"] for asset in assets}, "family QA asset inventory mismatch")
        for asset in assets:
            check = checks[asset["path"]]
            _require(check.get("pass") is True and check.get("failures") == []
                     and check.get("sha256") == asset["sha256"] and check.get("bytes") == asset["bytes"]
                     and check.get("format") == asset["kind"], "family QA asset proof mismatch")
            if asset["kind"] == "png":
                _require(check.get("size") == asset["size"] and check.get("mode") == "RGBA"
                         and check.get("alpha_extrema") == [0, 255], "family PNG bitmap QA mismatch")
            else:
                expected_mode = "release" if asset["role"] == "release" else "native_optical" if asset["optical"] else "native"
                _require(check.get("mode") == expected_mode and _integer(check.get("text_count"))
                         and (check["text_count"] > 0) == asset["live_text"], "family SVG role QA mismatch")
                _require(c_paths(asset) == core_paths, "family corrected C geometry differs from shared master")
        _require(family in policies, "family source and rights record required")
        row = policies[family]
        source, rights = row.get("original_reference", {}), row.get("rights", {})
        _require(_commit(source.get("source_commit")) and _sha(source.get("sha256"))
                 and not common.link_problems(source.get("source_url"), root, "family source")
                 and source["source_commit"] in source["source_url"], "fixed family reference source required")
        _require(source.get("native_editable_source_established") is False,
                 "reference reconstruction boundary required")
        _require(rights.get("third_party_mark_in_final_plan") is False
                 and rights.get("vendor_mark_permission_inferred_from_repo_mit") is False
                 and rights.get("affiliation_claimed") is False and _string(rights.get("trademark_notice_plan")),
                 "independent geometry and separate trademark rights required")
        _require(actual[family].get("rights") == rights, "family rights snapshot mismatch")
        ids = row.get("policy_ids")
        _require(isinstance(ids, list) and ids and all(identity in owners and _string(owners[identity].get("owner")) for identity in ids),
                 "actual vendor rights holders required")
        source_path = _file(base, "assets/families/" + family + "/source-and-rights.json", root)
        metadata = _json(source_path)
        _require(metadata.get("family") == family and metadata.get("motif_semantics") == MOTIFS[family][0]
                 and metadata.get("third_party_glyphs_embedded") is False and metadata.get("rights") == rights
                 and metadata.get("compatibility_phrase") == actual[family].get("compatibility_phrase")
                 and _string(metadata.get("artwork_author")), "actual family motif and rights metadata required")
        reference = metadata.get("reference", {})
        _require(all(reference.get(key) == source.get(key) for key in ("source_url", "source_commit", "sha256"))
                 and reference.get("byte_hash_verified") is True, "actual family reference identity mismatch")
        palette = metadata.get("palette", {})
        _require(palette.get("vendor_official_palette_claimed") is False and palette.get("master_palette_changes") is False,
                 "palette reference boundary required")
        sources[family] = {"path": source_path, "metadata": metadata}
    composites = qa.get("composites", [])
    _require(isinstance(composites, list) and all(isinstance(row, dict) for row in composites),
             "QA composite records must be an object array")
    composite_files, seen = [], set()
    for row in composites:
        rel = row.get("path")
        _require(rel in {"evidence/family-first-six-light-qa.png", "evidence/family-first-six-dark-qa.png"}
                 and rel not in seen and _sha(row.get("sha256")) and _integer(row.get("bytes")),
                 "reviewed QA composite identity required")
        image = _file(base, rel, root)
        data = image.read_bytes()
        _require(data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) == row["bytes"]
                 and hashlib.sha256(data).hexdigest() == row["sha256"], "QA composite integrity mismatch")
        seen.add(rel)
        composite_files.append({"path": image, "sha256": row["sha256"],
                                "theme": "light" if "-light-" in rel else "dark"})
    return {"qa_path": qa_path, "policy_path": policy_path, "policies": policies, "owners": owners,
            "sources": sources, "composites": composite_files}


def _snapshot(root, manifest_rel):
    manifest_path = _file(root, manifest_rel, root)
    _require(manifest_path.suffix.lower() == ".json", "local JSON manifest required")
    base = manifest_path.parent
    manifest = _json(manifest_path)
    _require(type(manifest.get("schema_version")) is int and manifest["schema_version"] == 2,
             "producer schema 2 required")
    _require(manifest.get("authoritative_asset_map") is True and manifest.get("status") in ("partial_actual_core", "partial_actual_core_and_first_six"),
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
    actual = {}
    for key, row in families.items():
        if key in SOFTWARE_FAMILIES and row.get("production_status") == "partial_actual_verified":
            _require(row.get("currentcolor_release_status") == "pending_software_outlined_export",
                     "currentColor outlined release must remain pending")
            actual[key] = row
        elif key != "core":
            _require(row.get("production_status") == "planned_not_executed" and row.get("actual_asset_ids") == [],
                     "unsupported or unexecuted family cannot publish")
    _require((bool(actual) and manifest["status"] == "partial_actual_core_and_first_six")
             or (not actual and manifest["status"] == "partial_actual_core"), "snapshot status and actual family scope mismatch")
    assets = _rows(manifest.get("assets"), "assets")
    indexed_assets = _indexed(assets, "asset_id", "asset")
    _require(len(assets) == 8 + 16 * len(actual) and type(manifest.get("actual_asset_count")) is int
             and manifest["actual_asset_count"] == len(assets), "declared actual asset count mismatch")
    _require(type(manifest.get("actual_family_count")) is int and manifest["actual_family_count"] == 1 + len(actual),
             "declared actual family count mismatch")
    for family in {"core", *actual}:
        ids = families[family].get("actual_asset_ids")
        expected_ids = {key for key, asset in indexed_assets.items() if asset.get("family") == family}
        _require(isinstance(ids, list) and len(ids) == len(expected_ids) and set(ids) == expected_ids,
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
             and acceptance.get("family_production") in ("in_progress", "paused_pending_native_birth_race_repair"),
             "acceptance scope mismatch")
    if actual:
        _require(acceptance.get("family_first_six_file_and_bitmap_qa") == "verified",
                 "family file and bitmap acceptance required")
        _utc(manifest.get("generated_utc"))
    matrices, paths, receipt_keys = {family: {} for family in {"core", *actual}}, set(), set()
    from validate_brand_gallery import png_check, svg_check
    for asset in assets:
        family = asset.get("family")
        _require(family in matrices and asset.get("status") == "actual"
                 and asset.get("qa_status") == "verified" and asset.get("license") == "MIT",
                 "only verified actual artwork can publish")
        matrix, is_core = matrices[family], family == "core"
        path = _file(base, asset.get("path"), root)
        _require(path not in paths, "duplicate asset path")
        paths.add(path)
        data = _integrity(asset, path)
        theme, kind, role = asset.get("theme"), asset.get("kind"), asset.get("role")
        _require(theme in (("light", "dark") if is_core else ("light", "dark", "currentcolor"))
                 and kind in ("svg", "png") and role in ("editable", "release")
                 and path.suffix == "." + kind, "supported asset role and format required")
        optical = asset.get("optical", False)
        _require(type(optical) is bool and (not is_core or not optical), "valid optical variant declaration required")
        if kind == "png":
            dims, problems = png_check(data, "brand manifest PNG")
            _require(not problems and isinstance(asset.get("size"), list) and list(dims or ()) == asset["size"]
                     and asset["size"] in (([1024, 455], [128, 57]) if is_core else ([1024, 478], [512, 239], [256, 119], [128, 60])) and role == "release",
                     "actual PNG dimensions mismatch")
            _require(asset.get("transparent") is True and asset.get("corner_alpha") == [0, 0, 0, 0],
                     "transparent raster evidence required")
            if not is_core:
                _require(optical == (asset["size"][0] == 128)
                         and (theme != "currentcolor" or (asset["size"] == [512, 239] and asset.get("currentcolor_default") == "black")),
                         "actual optical or black-default currentColor raster required")
            matrix_key = (theme, kind, asset["size"][0]) if is_core else (theme, kind, asset["size"][0], optical)
        else:
            viewbox, problems = svg_check(data, "brand manifest SVG")
            _require(not problems and viewbox == asset.get("viewbox") == ([0, 0, 900, 400] if is_core else [0, 0, 1200, 560]),
                     "safe actual SVG viewBox required")
            live = any(node.tag == "{http://www.w3.org/2000/svg}text" for node in ET.fromstring(data).iter())
            _require(type(asset.get("live_text")) is bool and asset["live_text"] == live
                     and live == (role == "editable"), "actual SVG text role mismatch")
            matrix_key = (theme, kind, role) if is_core else (theme, kind, role, optical)
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
    _require(set(matrices["core"]) == expected and receipt_keys == set(calls) == set(receipts), "complete two-theme output matrix required")
    family_expected = {(theme, "svg", "editable", optical) for theme in ("light", "dark") for optical in (False, True)}
    family_expected |= {(theme, "svg", "release", False) for theme in ("light", "dark")}
    family_expected |= {(theme, "png", width, width == 128) for theme in ("light", "dark") for width in (128, 256, 512, 1024)}
    family_expected |= {("currentcolor", "svg", "editable", False), ("currentcolor", "png", 512, False)}
    for family in actual:
        _require(set(matrices[family]) == family_expected, "complete partial-family output matrix required")
        for asset in matrices[family].values():
            if asset["role"] != "release":
                continue
            source = matrices[family][(asset["theme"], "svg", "editable", asset["optical"])]
            source_file = calls[asset["producer"]["receipt_key"]]["arguments"].get("source_file")
            _require(isinstance(source_file, str) and (source_file == source["path"] or source_file.endswith("/" + source["path"])),
                     "actual export source or optical document mismatch")
    _visual_check(visual, [asset for asset in assets if asset["family"] == "core"])
    extra = _family_evidence(root, base, publication, actual, matrices)
    extra.update(actual=actual, matrices=matrices)
    if publication.get("ui_evidence"):
        ui_path = _file(base, publication["ui_evidence"], root)
        ui = _json(ui_path)
        _require(ui.get("status") == "verified_partial_canvas" and ui.get("native_software_reopened_observed") is True
                 and ui.get("full_page_visible") is False and ui.get("brand_design_acceptance") == "awaiting_user_review",
                 "partial-canvas GUI evidence scope required")
        core_native = matrices["core"][("light", "svg", "editable")]
        _require(ui.get("native_document", {}).get("sha256") == core_native["sha256"], "GUI native document hash mismatch")
        extra.update(ui_path=ui_path, ui=ui)
    if acceptance.get("new_core_gui") == "verified_partial_canvas":
        _require("ui" in extra and acceptance.get("full_page_gui_acceptance") == "incomplete", "partial GUI record required")
    else:
        _require(acceptance.get("new_core_gui") in (None, "launch_observed_only_not_visual_acceptance"), "unsupported GUI acceptance claim")
    return manifest_path, manifest, matrices["core"], ledger_path, visual_path, font_notice_path, license_path, trademark_path, visual, extra


def _family_item(root, base, manifest, family, row, extra, core, production_source):
    """Build a page from successful files, not from the old unexecuted brief."""
    item = copy.deepcopy(core)
    matrix = extra["matrices"][family]
    def url(path):
        return path.relative_to(root).as_posix()
    def asset_url(asset):
        return url(_file(base, asset["path"], root))
    title, motif = row["display_product"], MOTIFS[family][1]
    def preview(theme, width):
        asset = matrix[(theme, "png", width, width == 128)]
        return {"src": asset_url(asset), "alt": "DCC-MCP · " + title + " 家族标识 · " + ("浅色" if theme == "light" else "深色") + "背景 · 实际 " + str(width) + (" 像素 optical 导出" if width == 128 else " 像素导出"),
                "width": asset["size"][0], "height": asset["size"][1]}
    variants = []
    for asset in [a for a in manifest["assets"] if a["family"] == family]:
        theme = {"light": "浅色", "dark": "深色", "currentcolor": "currentColor 单色（原生可编辑）" if asset["kind"] == "svg" else "固定黑色单色光栅"}[asset["theme"]]
        optical = " · 小尺寸 optical" if asset["optical"] else ""
        if asset["kind"] == "svg":
            label = "可编辑原生 SVG · 文字保留" if asset["role"] == "editable" else "轮廓化发布 SVG · 文字转路径"
            note = ("可编辑文字依赖 Montserrat，字体文件未随作品分发。" if asset["role"] == "editable" else "文字已由实际软件转路径，显示无需安装字体。")
            if asset["theme"] == "currentcolor":
                note += "这是保留文字的原生单色版本；轮廓化 currentColor 发布 SVG 尚未完成。"
            if asset["optical"]:
                note += "使用独立 optical 计划简化小尺寸细节。"
            dimensions = {"viewBox": list(asset["viewbox"])}
        else:
            label = "PNG · %d × %d" % tuple(asset["size"])
            note = ("实际 Inkscape 导出的 optical 小尺寸 PNG，来自独立原生文档，并非大图缩小。" if asset["optical"] else "实际 Inkscape 透明 PNG 导出。")
            if asset["theme"] == "currentcolor":
                note += "这是黑色默认光栅结果，PNG 不会继承网页文字颜色。"
            dimensions = {"width": asset["size"][0], "height": asset["size"][1]}
        variants.append({"label": theme + " · " + label + optical, "note": note, "url": asset_url(asset), "format": asset["kind"], "bytes": asset["bytes"], "sha256": asset["sha256"],
                         "rights_ids": ["artwork", "font", "trademark"], "source_id": "production", **dimensions})
    source_info = extra["sources"][family]
    metadata, policy = source_info["metadata"], extra["policies"][family]
    reference = metadata["reference"]
    vendor_owners = "、".join(extra["owners"][identity]["owner"] for identity in policy["policy_ids"])
    item.update(slug="dcc-mcp-" + family + "-v2", title="DCC-MCP · " + title, family=title,
                version="v2 · 软件家族首款", summary="在修正核心母版下加入独立绘制的" + motif + "，以分离的兼容性文字说明 " + title + " 工作流；提供深浅主题与独立小尺寸版本。",
                verified_at=manifest["generated_utc"], previews={theme: preview(theme, 1024) for theme in ("light", "dark")},
                small_previews={theme: preview(theme, 128) for theme in ("light", "dark")}, variants=variants)
    item["prompt"] = {"kind": "reusable", "text": "通过 DCC-MCP 的 Inkscape 原生矢量工具创建 " + title + " 家族标识。复用修正后的 DCC-MCP 母版和两处 C 路径；在 1200 × 560 画布的独立配件区绘制" + motif + "，不描摹厂商 Logo。保持项目标识更突出，用普通 Montserrat 文字单独标明“" + metadata["compatibility_phrase"] + "”。分别构建深浅、currentColor 单色和独立 optical 小尺寸原生 SVG。实际软件导出深浅轮廓 SVG 与透明 1024 × 478、512 × 239、256 × 119 PNG；128 × 60 PNG 来自 optical 文档。保留真实输出收据、请求响应、文件哈希与位图检查。currentColor 轮廓化发布 SVG 尚未完成时只说明状态，不生成该下载链接。",
                      "note": "根据真实素材语义和本轮目标整理的可复用提示词，并非逐字原始提示。完整实际构建计划与导出参数以 MCP 记录为准；来源说明中的 prepared plan 状态本身不证明执行。"}
    item["steps"] = [{"title": "复用核心母版，绘制工作流配件", "description": "实际构建请求复用两个修正 C 的路径，并在独立区域绘制" + motif + "。原生与轮廓 SVG 均核对母版路径，兼容性文字与品牌主体分开。"},
                     {"title": "导出深浅主题", "description": "使用真实 Inkscape 导出两份轮廓化 SVG 及 1024、512、256 像素宽 PNG。下图为最终浅色成品，未冒充过程中的临时画面。", "image": preview("light", 1024)},
                     {"title": "独立小尺寸 optical 版本", "description": "分别构建深浅 optical 原生文档，调整小尺寸信息层级，再由软件导出真正的 128 × 60 PNG。这里显示真实小尺寸结果，未从大图缩放生成。", "image": preview("dark", 128)},
                     {"title": "记录单色版本与未完成项", "description": "currentColor 原生 SVG 与黑色默认 512 × 239 PNG 已有成功输出。原生 SVG 保留字体依赖；尚无轮廓化 currentColor 发布 SVG，因此该版本没有下载入口。"}]
    item["checks"] = [{"name": "实际文件与 MCP 输出", "result": "pass", "observed": "本家族 16 个输出的字节数和 SHA-256 与成功 Gateway 响应、manifest 及独立文件 QA 一致。"},
                      {"name": "共享核心几何", "result": "pass", "observed": "本家族七份 SVG 的两个 C 路径与修正核心母版一致；不把相同路径的复用说成新的 G2 或等厚设计。"},
                      {"name": "原生与轮廓角色", "result": "pass", "observed": "五份原生 SVG 保留可编辑文字；两份深浅发布 SVG 文字已转路径。Montserrat 的字体来源与许可另列。"},
                      {"name": "位图尺寸与透明", "result": "pass", "observed": "九份实际 PNG 的尺寸、RGBA 非空像素和透明角点通过文件检查；128 × 60 来自 optical 原生计划。"},
                      {"name": "来源与权利范围", "result": "pass", "observed": "独立新几何、字体依赖及厂商名称的权利分别记录；未嵌入厂商 glyph，未从仓库软件许可推定商标授权。"},
                      {"name": "currentColor 轮廓化发布 SVG", "result": "not_run", "observed": "该发布版本仍待实际软件导出；当前只提供已验证的可编辑单色 SVG 与黑色默认 PNG。"},
                      {"name": "家族原生 GUI 完整验收", "result": "not_run", "observed": "本家族记录覆盖构建、导出及文件/位图 QA；未纳入逐家族 GUI 完整页面验收记录。"},
                      {"name": "用户设计评价", "result": "not_run", "observed": "设计接受度等待用户审阅。"}]
    item["evidence_scope"] = "本家族 16 次实际成功矢量构建/导出、对应文件和位图 QA；记录检查时间采用清单打包快照时间。没有站点集成重跑、逐家族完整 GUI 验收或用户设计通过的声明。"
    item["evidence"] = [{"label": "单一制作清单 · 实际状态与文件哈希", "url": production_source["url"]},
                        {"label": "实际 MCP 构建与导出记录", "url": url(_file(base, manifest["publication"]["mcp_evidence"], root))},
                        {"label": "六家族文件与位图 QA", "url": url(extra["qa_path"])},
                        {"label": "本家族素材语义、来源与权利说明", "url": url(source_info["path"])}]
    item["sources"].append({"id": "reference", "label": "原家族历史参考 · 固定来源，未作为作品下载分发", "url": reference["source_url"], "commit": reference["source_commit"], "sha256": reference["sha256"], "author": "原仓库素材贡献者；厂商标识权利另列"})
    item["sources"].append({"id": "policy", "label": "家族来源与权利分析快照", "url": url(extra["policy_path"]), "sha256": hashlib.sha256(extra["policy_path"].read_bytes()).hexdigest(), "author": "DCC-MCP contributors"})
    for composite in extra["composites"]:
        label = "六家族实际成品 QA 总览 · " + ("浅色背景" if composite["theme"] == "light" else "深色背景")
        item["evidence"].append({"label": label, "url": url(composite["path"])})
        item["sources"].append({"id": "qa-" + composite["theme"], "label": label,
                                "url": url(composite["path"]), "sha256": composite["sha256"],
                                "author": "DCC-MCP contributors"})
    item["rights"][0]["scope"] = "独立制作的 DCC-MCP 几何与" + motif + "、计划及元数据；原参考和厂商图形未在本作品中重新授权。"
    item["rights"][2].update(holder="DCC-MCP 品牌权利人；" + vendor_owners, scope=title + " 的名称用于独立兼容性说明；当前家族作品不含厂商 Logo 或 glyph。",
                             notice=metadata["rights"]["trademark_notice_plan"])
    item["contributors"] = [metadata["artwork_author"]]
    item["limitations"] = ["本家族首款已交付 16 个文件；轮廓化 currentColor 发布 SVG 尚未制作完成。", "软件家族名称说明集成目标；本作品实际生产软件为 Inkscape，不声称在对应目标软件中制作。", "来源说明是事前计划元数据，实际执行仅由成功 MCP 调用与输出哈希证明。", "文件和位图 QA 与界面视觉验收分别记录，未声称本家族完整 GUI 验收通过。", "128 像素 optical 版本保留更少细节；位图检查不等同于所有小字均可读或用户已接受设计。", "currentColor PNG 是黑色默认光栅，不能随网页文字颜色变化；原生 currentColor SVG 保留 Montserrat 字体依赖。", "依据历史参考语义重新绘制，并非找回原始可编辑源文件或像素完全一致。", "公开记录移除私人连接和实例标识；站点集成未重新执行 DCC 生产。", "其余家族仍按清单状态分批制作；当前生产暂停等待原生路由修复，不影响已完成文件的存在与验证。"]
    return item


def _project(root, manifest_rel):
    """Return a standard enabled catalog without writing or discovering files."""
    root = Path(root).resolve()
    path, manifest, matrix, ledger, visual_path, font_notice, license_path, trademark_path, visual, extra = _snapshot(root, manifest_rel)
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
    for asset in [row for row in manifest["assets"] if row["family"] == "core"]:
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
                   {"name": "本轮站点集成重跑 DCC", "result": "not_run", "observed": "制作任务另有原生 inspect 记录；本站集成读取并核验已有成品，公共记录保留对应输出调用，不宣称本站重新执行过软件生产。"},
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
    if "ui" in extra:
        gui_check = next(row for row in item["checks"] if row["name"] == "GUI 视觉验收")
        gui_check.update(result="unknown", observed="制作记录证明核心原生文件已重新打开并观察局部画布；162% 缩放下右侧六边形被裁切，完整页面 GUI 验收仍未完成。")
        item["limitations"][3] = "核心原生 GUI 已观察局部画布；完整页面未成功适配，不声称完整 GUI 验收通过。"
        item["evidence"].append({"label": "核心原生 GUI · 仅局部画布观察", "url": url(extra["ui_path"])})
    items = [item]
    if extra["actual"]:
        item["limitations"][0] = "核心字标首款及 %d 个软件家族已有交付；Core 其他变体、家族 currentColor 轮廓 SVG 与其余组尚未完成。" % len(extra["actual"])
        item["rights"][2]["notice"] = "本核心作品的软件名称用于说明制作环境；已交付软件家族各自记录兼容性与权利范围。未制作家族仍是计划，不推定商标许可或作品完成。"
        for family, row in extra["actual"].items():
            items.append(_family_item(root, base, manifest, family, row, extra, item, production_source))
    completed = len(items)
    planned = [{"id": row["family_id"], "title": row["display_product"], "status": row["production_status"]} for row in manifest["families"]]
    description = ("核心字标及 %d 个软件家族已交付；部分变体尚缺，另外 %d 组待制作。" % (completed - 1, manifest["family_count"] - completed)
                   if completed > 1 else "核心字标已交付，Core 其他变体及其余 %d 组待制作。" % (manifest["family_count"] - 1))
    return {"schema_version": 1, "enabled": True, "title": "DCC-MCP 品牌画廊", "description": "从核心字标开始整理品牌家族。展示实际修正成品、深浅与小尺寸预览，并记录工具、来源和制作证据。", "updated_at": (manifest["generated_utc"] if extra["actual"] else visual["visual_reviewed_utc"]).split("T")[0],
            "progress": {"completed": completed, "total": manifest["family_count"], "assets": len(manifest["assets"]), "description": description, "planned": planned}, "items": items}


def project(root, manifest_rel):
    """Fail closed on malformed snapshots, without returning record values."""
    try:
        return _project(root, manifest_rel)
    except (OSError, UnicodeError, TypeError, KeyError, AttributeError, ET.ParseError, RecursionError, OverflowError):
        raise ValueError("brand manifest: malformed or unreadable production snapshot") from None
