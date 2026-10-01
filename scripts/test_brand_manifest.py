"""Exercise projection using independently generated minimal production records."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

import brand_manifest


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)


def png(width, height):
    pixels = (b"\0" + b"\0\0\0\0" * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


class BrandProjection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "docs" / "brands" / "snapshot"
        self.base.mkdir(parents=True)
        self.stamp = "2026-10-01T11:46:00+00:00"
        self.runtime = "7" * 40
        self.ledger = {"schema_version": 1, "evidence_scope": "Actual vector construction and export records; no integration rerun.", "redactions": ["private locations removed"], "calls": []}
        self.manifest = {"schema_version": 2, "authoritative_asset_map": True, "status": "partial_actual_core", "family_count": 3, "actual_family_count": 1, "actual_asset_count": 8,
            "publication": {"source_manifest_sha256": "a" * 64, "mcp_evidence": "evidence/calls.json", "visual_evidence": "evidence/visual.json", "font_notice": "fonts/OFL.txt", "scope": "Only actual corrected core assets; all other families remain planned.", "metadata_redactions": ["private locations removed"], "comparison_published": False},
            "families": [{"family_id": "core", "display_product": "Core", "production_status": "partial_actual_core_wordmarks", "actual_asset_ids": []},
                         {"family_id": "blender", "display_product": "Blender", "production_status": "planned_not_executed", "actual_asset_ids": []},
                         {"family_id": "houdini", "display_product": "SideFX Houdini", "production_status": "planned_not_executed", "actual_asset_ids": []}],
            "assets": [], "mcp_receipts": [],
            "toolchain": {"runtime_source_commit": self.runtime, "public_head_commit": "0" * 40, "public_repository": "https://github.com/dcc-mcp/dcc-mcp-inkscape", "application_version": "Inkscape 1.4.4", "core_version": "0.20.36", "gateway_cli_version": "0.20.38"},
            "acceptance": {"geometry_and_raster_visual_review": "verified", "brand_design_acceptance": "awaiting_user_review", "family_production": "in_progress"}}
        self.visual = {"qa_status": "verified", "visual_review_complete": True, "brand_design_acceptance": "awaiting_user_review", "visual_reviewed_utc": self.stamp,
            "actual_native_paths_match_proposed": {"dcc-c1": True, "dcc-c2": True}, "dark_native_paths_match_proposed": {"dcc-c1": True, "dcc-c2": True},
            "changed_native_ids_light": ["dcc-c1", "dcc-c2"], "changed_native_ids_dark": ["dcc-c1", "dcc-c2"], "non_cc_native_attribute_changes": [],
            "c1": {"max_internal_curve_tangent_turn_degrees": 0.0000019, "continuity_claim": "G1 within numeric rounding, not G2 or uniform-thickness claim"},
            "c2": {"center_separation_design_px": 0.0000011, "radii_design_px": [100, 63], "nominal_radial_thickness_design_px": 37},
            "native_sources": [], "raster_sources": [], "caption_font": {"sha256": "f" * 64, "family": "Montserrat", "license": "SIL Open Font License 1.1"}}
        for theme in ("light", "dark"):
            for role in ("editable", "release"):
                live = b'<text x="2" y="12">MCP</text>' if role == "editable" else b'<path d="M0 0H20V10H0Z"/>'
                shared = b'<path id="dcc-c1" d="M1 1H4"/><path id="dcc-c2" d="M7 1H10"/>'
                data = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 400">' + shared + live + b'</svg>'
                self.add_asset(theme, "svg", role, "%s-%s.svg" % (theme, role), data, viewbox=[0, 0, 900, 400], live_text=role == "editable")
            for width, height in ((1024, 455), (128, 57)):
                self.add_asset(theme, "png", "release", "%s-%d.png" % (theme, width), png(width, height), size=[width, height], transparent=True, corner_alpha=[0, 0, 0, 0])
        for rel in ("fonts/OFL.txt", "LICENSE", "THIRD_PARTY_NOTICES.md"):
            target = self.base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("Original geometry is MIT; Montserrat is OFL; trademark rights reserved.", encoding="utf-8")

    def add_asset(self, theme, kind, role, filename, data, family="core", **details):
        key = family + "-" + filename.replace(".", "-")
        rel = "assets/" + ("families/" + family + "/" if family != "core" else "") + filename
        target = self.base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        operation = "document_build" if role in ("editable", "editable_outlined") else "document_export"
        asset = {"asset_id": key, "path": rel, "family": family, "theme": theme, "kind": kind, "role": role, "status": "actual", "qa_status": "verified", "license": "MIT", "bytes": len(data), "sha256": digest,
                 "producer": {"application": "Inkscape 1.4.4", "source_commit": self.runtime, "receipt_key": key}, **details}
        self.manifest["assets"].append(asset)
        next(row for row in self.manifest["families"] if row["family_id"] == family)["actual_asset_ids"].append(key)
        self.manifest["mcp_receipts"].append({"key": key, "operation": operation, "recorded_utc": self.stamp, "source_commit": self.runtime, "control_route": "gateway", "output_sha256": digest})
        self.ledger["calls"].append({"key": key, "tool": brand_manifest.TOOLS[operation], "arguments": {"plan": {"canvas": {"width": 900, "height": 400}}}, "response": {"success": True, "context": {"sha256": digest, "bytes": len(data)}}, "recorded_utc": self.stamp, "source_commit": self.runtime, "control_route": "gateway", "gateway_stats_recorded": True, "artifact_sha256": digest, "original_completed_record_sha256": "b" * 64})
        if family != "core" and role == "release":
            self.ledger["calls"][-1]["arguments"] = {"source_file": "snapshot/assets/families/" + family + "/" + theme + "-editable" + ("-optical" if details.get("optical") else "") + ".svg", "format": kind}
        if family == "core" and (kind == "png" or role == "editable"):
            self.visual["raster_sources" if kind == "png" else "native_sources"].append({"path": "snapshot/" + rel, "sha256": digest, "bytes": len(data), **({"size": details["size"]} if kind == "png" else {})})

    def tearDown(self):
        self.temp.cleanup()

    def project(self):
        files = [("manifest.json", self.manifest), ("evidence/calls.json", self.ledger), ("evidence/visual.json", self.visual)]
        if hasattr(self, "family_qa"):
            files += [("evidence/family-qa.json", self.family_qa), ("evidence/policy.json", self.policy)]
            files += [("assets/families/" + family + "/source-and-rights.json", data) for family, data in self.source_metadata.items()]
        if hasattr(self, "ui"):
            files += [("evidence/ui.json", self.ui)]
        if hasattr(self, "core_current_qa"):
            files += [("evidence/core-current-qa.json", self.core_current_qa)]
        if hasattr(self, "historical_qa"):
            files += [("evidence/historical-six-qa.json", self.historical_qa)]
        if hasattr(self, "family_visual"):
            files += [("evidence/family-visual.json", self.family_visual)]
        for rel, data in files:
            target = self.base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data), encoding="utf-8")
        return brand_manifest.project(self.root, "docs/brands/snapshot/manifest.json")

    def with_six(self, families=None):
        """Independent fixture encodes the expected shapes, never real files."""
        families = families or ("maya", "3dsmax", "blender", "houdini", "zbrush", "photoshop")
        self.manifest.update(status="partial_actual_core_and_first_six", generated_utc=self.stamp, family_count=37, actual_family_count=1 + len(families), actual_asset_count=8 + 16 * len(families))
        self.manifest["acceptance"].update(family_first_six_file_and_bitmap_qa="verified", family_production="paused_pending_native_birth_race_repair")
        self.manifest["publication"].update(family_qa="evidence/family-qa.json", family_policy="evidence/policy.json")
        core = self.manifest["families"][0]
        self.manifest["families"] = [core]
        self.family_qa = {"scope": "Actual file and bitmap checks; separate GUI scope.", "pass": True, "missing": [], "families": []}
        self.policy = {"families": [], "vendor_policy_groups": {"vendor": {"owner": "Original software rights holder"}}}
        self.source_metadata = {}
        source_commit = "c" * 40
        for family in families:
            rights = {"third_party_mark_in_final_plan": False, "vendor_mark_permission_inferred_from_repo_mit": False, "affiliation_claimed": False,
                      "trademark_notice_plan": "Software name is referential; no endorsement."}
            phrase = "for use with " + family + " software"
            self.manifest["families"].append({"family_id": family, "display_product": family.title(), "production_status": "partial_actual_verified", "actual_asset_ids": [],
                                            "currentcolor_release_status": "pending_software_outlined_export", "rights": rights, "compatibility_phrase": phrase,
                                            "drawing_brief": "Old unrelated prepared brief must not become actual description"})
            reference = {"source_url": "https://raw.githubusercontent.com/example/brand/" + source_commit + "/" + family + ".svg", "source_commit": source_commit, "sha256": "d" * 64,
                         "native_editable_source_established": False}
            self.policy["families"].append({"family_id": family, "original_reference": reference, "rights": rights, "policy_ids": ["vendor"]})
            self.source_metadata[family] = {"family": family, "display_name": family, "reference": {**reference, "byte_hash_verified": True},
                                           "motif_semantics": brand_manifest.MOTIFS[family][0], "rights": rights, "compatibility_phrase": phrase, "artwork_author": "DCC-MCP contributors",
                                           "third_party_glyphs_embedded": False, "palette": {"vendor_official_palette_claimed": False, "master_palette_changes": False},
                                           "production_status": "Prepared plan only; actual execution tracked in the shared MCP ledger."}
            for theme in ("light", "dark", "currentcolor"):
                if family in ("nuke", "openusd") or (family == "mobu" and theme == "currentcolor"):
                    self.runtime = "f" * 40
                roles = (("editable", False),) if theme == "currentcolor" else (("editable", False), ("release", False), ("editable", True))
                for role, optical in roles:
                    label = theme + "-" + role + ("-optical" if optical else "") + ".svg"
                    live = b'<text>MCP</text>' if role == "editable" else b'<path d="M3 3H5"/>'
                    data = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 560"><path id="dcc-c1" d="M1 1H4"/><path id="dcc-c2" d="M7 1H10"/>' + live + b'</svg>'
                    self.add_asset(theme, "svg", role, label, data, family=family, optical=optical, live_text=role == "editable", viewbox=[0, 0, 1200, 560])
                sizes = ((512, 239),) if theme == "currentcolor" else ((1024, 478), (512, 239), (256, 119), (128, 60))
                for width, height in sizes:
                    self.add_asset(theme, "png", "release", theme + "-" + str(width) + ".png", png(width, height), family=family, optical=width == 128,
                                   size=[width, height], transparent=True, corner_alpha=[0, 0, 0, 0], currentcolor_default="black" if theme == "currentcolor" else None)
            checks = []
            for asset in self.manifest["assets"]:
                if asset["family"] != family:
                    continue
                check = {"path": asset["path"], "bytes": asset["bytes"], "sha256": asset["sha256"], "format": asset["kind"], "pass": True, "failures": []}
                if asset["kind"] == "png":
                    check.update(size=asset["size"], mode="RGBA", alpha_extrema=[0, 255])
                else:
                    check.update(text_count=1 if asset["live_text"] else 0, mode="release" if asset["role"] == "release" else "native_optical" if asset["optical"] else "native")
                checks.append(check)
            self.family_qa["families"].append({"family": family, "checks": checks, "pass": True})
        self.manifest["families"] += [{"family_id": "planned-" + str(index), "display_product": "Planned " + str(index), "production_status": "planned_not_executed", "actual_asset_ids": []} for index in range(36 - len(families))]

    def with_nine(self):
        self.with_six(("maya", "3dsmax", "blender", "houdini", "zbrush", "photoshop", "mobu", "nuke", "openusd"))
        self.manifest.update(status="partial_actual_verified_in_progress", actual_asset_count=155)
        self.manifest["acceptance"].update(family_first_nine_file_and_bitmap_qa="verified", family_production="resumed_after_native_birth_repair")
        self.manifest["toolchain"].update(runtime_source_commit="f" * 40, public_head_commit="f" * 40)
        self.manifest["publication"]["core_current_qa"] = "evidence/core-current-qa.json"
        self.manifest["families"][0].update(production_status="actual_verified_published_themes", currentcolor_release_status="actual_verified")
        self.core_current_qa = {"scope": "Actual core currentColor file checks; GUI is separate.", "generated_utc": self.stamp, "pass": True, "artwork_written_or_rendered": False, "checks": []}
        for role in ("editable", "editable_outlined", "release"):
            text = b'<text>MCP</text>' if role == "editable" else b'<path d="M3 3H5"/>'
            data = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 400"><path id="dcc-c1" d="M1 1H4"/><path id="dcc-c2" d="M7 1H10"/>' + text + b'</svg>'
            self.add_asset("currentcolor", "svg", role, "currentcolor-" + role + ".svg", data, optical=False, live_text=role == "editable", viewbox=[0, 0, 900, 400])
            asset = self.manifest["assets"][-1]
            self.core_current_qa["checks"].append({"path": asset["path"], "bytes": asset["bytes"], "sha256": asset["sha256"], "format": "svg", "text_count": 1 if role == "editable" else 0, "pass": True, "failures": []})

    def with_nine_composites_and_history(self):
        self.with_nine()
        self.manifest["publication"].update(historical_family_qa="evidence/historical-six-qa.json", family_visual_evidence="evidence/family-visual.json")
        self.historical_qa = copy.deepcopy(self.family_qa)
        self.historical_qa["families"] = self.historical_qa["families"][:6]
        for label, qa in (("six", self.historical_qa), ("nine", self.family_qa)):
            qa["composites"] = []
            for theme in ("light", "dark"):
                rel = "evidence/family-first-" + label + "-" + theme + "-qa.png"
                data = png(640, 180 if label == "six" else 240)
                (self.base / rel).parent.mkdir(exist_ok=True)
                (self.base / rel).write_bytes(data)
                qa["composites"].append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.family_visual = {"status": "verified_for_current_completed_outputs", "reviewed_utc": self.stamp, "brand_design_acceptance": "awaiting_user_review",
                              "families": [row["family"] for row in self.family_qa["families"]], "evidence": [{"path": row["path"], "sha256": row["sha256"]} for row in self.family_qa["composites"]]}

    def with_partial_gui(self):
        self.manifest["publication"]["ui_evidence"] = "evidence/ui.json"
        self.manifest["acceptance"].update(new_core_gui="verified_partial_canvas", full_page_gui_acceptance="incomplete")
        self.ui = {"status": "verified_partial_canvas", "native_software_reopened_observed": True, "full_page_visible": False, "brand_design_acceptance": "awaiting_user_review",
                   "native_document": {"sha256": self.manifest["assets"][0]["sha256"]}}

    def reject(self, phrase):
        with self.assertRaisesRegex(ValueError, phrase):
            self.project()

    def test_projects_only_actual_core_and_retains_partial_plans(self):
        catalog = self.project()
        self.assertEqual((1, 3, 8), tuple(catalog["progress"][key] for key in ("completed", "total", "assets")))
        self.assertEqual("partial_actual_core_wordmarks", catalog["progress"]["planned"][0]["status"])
        item = catalog["items"][0]
        self.assertEqual("dcc-mcp-core-v2", item["slug"])
        self.assertEqual(8, len(item["variants"]))
        self.assertEqual((128, 57), (item["small_previews"]["light"]["width"], item["small_previews"]["light"]["height"]))
        self.assertEqual("reusable", item["prompt"]["kind"])
        self.assertEqual("not_run", next(v for v in item["checks"] if v["name"] == "用户设计评价")["result"])
        self.assertTrue(all(v["rights_ids"] == ["artwork", "font", "trademark"] for v in item["variants"]))
        editable = [v for v in item["variants"] if "可编辑" in v["label"]]
        self.assertEqual(2, len(editable))
        self.assertTrue(all("安装对应字体" in v["note"] for v in editable))

    def test_projection_does_not_write_second_inventory_or_discover_files(self):
        extra = self.base / "assets" / "unlisted.svg"
        extra.write_text("unverified old geometry", encoding="utf-8")
        catalog = self.project()
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        again = brand_manifest.project(self.root, "docs/brands/snapshot/manifest.json")
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(catalog, again)
        self.assertFalse(any("unlisted" in v["url"] for v in again["items"][0]["variants"]))

    def test_mismatched_actual_counts_rejected(self):
        self.manifest["actual_asset_count"] = 9
        self.reject("actual asset count")

    def test_boolean_count_rejected(self):
        self.manifest["actual_family_count"] = True
        self.reject("actual family count")

    def test_planned_family_cannot_claim_actual_asset(self):
        self.manifest["families"][1]["actual_asset_ids"] = [self.manifest["assets"][0]["asset_id"]]
        self.reject("unexecuted family")

    def test_core_cannot_claim_whole_family_complete(self):
        self.manifest["families"][0]["production_status"] = "completed"
        self.reject("partially delivered")

    def test_unverified_actual_asset_rejected(self):
        self.manifest["assets"][0]["qa_status"] = "planned"
        self.reject("verified actual")

    def test_replaced_asset_rejected(self):
        (self.base / self.manifest["assets"][0]["path"]).write_bytes(b"replacement")
        self.reject("byte count mismatch")

    def test_equal_bytes_different_hash_rejected(self):
        asset = self.manifest["assets"][0]
        target = self.base / asset["path"]
        target.write_bytes(target.read_bytes().replace(b"MCP", b"ABC"))
        self.reject("SHA-256 mismatch")

    def test_wrong_receipt_hash_rejected(self):
        self.manifest["mcp_receipts"][0]["output_sha256"] = "e" * 64
        self.reject("receipt output SHA-256")

    def test_failed_response_rejected(self):
        self.ledger["calls"][0]["response"]["success"] = False
        self.reject("successful MCP response")

    def test_wrong_response_hash_rejected(self):
        self.ledger["calls"][0]["response"]["context"]["sha256"] = "e" * 64
        self.reject("response context SHA-256")

    def test_wrong_context_bytes_rejected(self):
        self.ledger["calls"][0]["response"]["context"]["bytes"] += 1
        self.reject("response context SHA-256")

    def test_mismatched_tool_rejected(self):
        self.ledger["calls"][0]["tool"] = "inkscape_vector__document_export"
        self.reject("tool and operation")

    def test_unrecorded_gateway_rejected(self):
        self.ledger["calls"][0]["gateway_stats_recorded"] = False
        self.reject("recorded gateway")

    def test_wrong_runtime_source_rejected(self):
        self.ledger["calls"][0]["source_commit"] = "e" * 40
        self.reject("production source revision")

    def test_unsafe_asset_path_rejected(self):
        self.manifest["assets"][0]["path"] = "../outside.svg"
        self.reject("safe existing")

    def test_private_path_rejected_without_echo(self):
        self.manifest["scope"] = "C:\\Users\\private\\case"
        with self.assertRaises(ValueError) as caught:
            self.project()
        self.assertNotIn("Users", str(caught.exception))
        self.assertIn("private metadata", str(caught.exception))

    def test_private_device_path_rejected(self):
        self.ledger["calls"][0]["response"]["device"] = "\\Device\\HarddiskVolume3\\private"
        self.reject("private device path")

    def test_private_runtime_ids_rejected(self):
        self.ledger["calls"][0]["response"]["requested_pid"] = 1234
        self.reject("private runtime identifiers")

    def test_library_identity_remains_private(self):
        self.manifest["preview"] = {"library_file_id": "libfile_0123abcd"}
        self.reject("private Library identity")

    def test_malformed_record_fails_closed(self):
        self.manifest["acceptance"] = ["verified"]
        self.reject("malformed or unreadable")

    def test_visual_hash_mismatch_rejected(self):
        self.visual["native_sources"][0]["sha256"] = "e" * 64
        self.reject("visual review asset hash")

    def test_invalid_concentricity_rejected(self):
        self.visual["c2"]["center_separation_design_px"] = 0.49
        self.reject("concentricity")

    def test_false_user_design_acceptance_rejected(self):
        self.manifest["acceptance"]["brand_design_acceptance"] = "verified"
        self.reject("acceptance scope")

    def test_forged_g2_claim_rejected(self):
        self.visual["c1"]["continuity_claim"] = "G2 verified"
        self.reject("G1-only evidence")

    def test_ledger_scope_requires_exact_output_records(self):
        self.ledger["calls"].append(copy.deepcopy(self.ledger["calls"][0]))
        self.ledger["calls"][-1]["key"] = "unrelated"
        self.reject("exact output receipt")

    def test_real_preview_dimensions_required(self):
        self.manifest["assets"][3]["size"] = [128, 58]
        self.reject("actual PNG dimensions")

    def test_release_svg_cannot_be_live_font_text(self):
        self.manifest["assets"][1]["live_text"] = True
        self.reject("text role mismatch")

    def test_timestamps_compare_instants_across_offsets(self):
        self.ledger["calls"][0]["recorded_utc"] = "2026-10-01T19:46:00+08:00"
        self.project()
        self.ledger["calls"][0]["recorded_utc"] = "2026-10-01T19:46:01+08:00"
        self.reject("timestamp mismatch")

    def test_six_family_snapshot_projects_104_actual_files_not_37_complete(self):
        self.with_six()
        self.with_partial_gui()
        catalog = self.project()
        self.assertEqual((7, 37, 104), tuple(catalog["progress"][key] for key in ("completed", "total", "assets")))
        self.assertEqual([8, 16, 16, 16, 16, 16, 16], [len(item["variants"]) for item in catalog["items"]])
        self.assertEqual(30, sum(row["status"] == "planned_not_executed" for row in catalog["progress"]["planned"]))
        for item in catalog["items"][1:]:
            self.assertEqual((128, 60), (item["small_previews"]["light"]["width"], item["small_previews"]["light"]["height"]))
            self.assertEqual(["Inkscape"], item["software"])
            self.assertFalse(any("Old unrelated" in item[field] for field in ("summary", "title")))
            svg = [v for v in item["variants"] if v["format"] == "svg"]
            self.assertEqual((5, 2), (sum("可编辑" in v["label"] for v in svg), sum("轮廓化发布" in v["label"] for v in svg)))

    def with_qa_composites(self):
        self.with_six()
        self.family_qa["composites"] = []
        for theme in ("light", "dark"):
            rel = "evidence/family-first-six-" + theme + "-qa.png"
            image = self.base / rel
            image.parent.mkdir(parents=True, exist_ok=True)
            data = png(640, 180)
            image.write_bytes(data)
            self.family_qa["composites"].append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    def test_qa_composites_are_selected_as_hashed_public_evidence(self):
        self.with_qa_composites()
        for item in self.project()["items"][1:]:
            evidence_urls = {row["url"] for row in item["evidence"]}
            for row in item["sources"]:
                if row["id"].startswith("qa-"):
                    self.assertIn(row["url"], evidence_urls)
                    self.assertEqual(hashlib.sha256((self.root / row["url"]).read_bytes()).hexdigest(), row["sha256"])
            self.assertEqual(2, sum(row["id"].startswith("qa-") for row in item["sources"]))

    def test_referenced_qa_composite_cannot_be_missing(self):
        self.with_qa_composites()
        (self.base / self.family_qa["composites"][0]["path"]).unlink()
        with self.assertRaises(ValueError):
            self.project()

    def test_referenced_qa_composite_cannot_be_modified(self):
        self.with_qa_composites()
        (self.base / self.family_qa["composites"][0]["path"]).write_bytes(png(641, 180))
        with self.assertRaises(ValueError):
            self.project()

    def test_qa_composite_cannot_admit_an_unreviewed_file(self):
        self.with_qa_composites()
        self.family_qa["composites"][0]["path"] = "evidence/private-reference.png"
        with self.assertRaises(ValueError):
            self.project()

    def test_currentcolor_pending_release_never_gets_href(self):
        self.with_six()
        item = self.project()["items"][1]
        current = [v for v in item["variants"] if "currentcolor" in v["url"]]
        self.assertEqual(2, len(current))
        svg, raster = next(v for v in current if v["format"] == "svg"), next(v for v in current if v["format"] == "png")
        self.assertIn("原生可编辑", svg["label"])
        self.assertIn("轮廓化", svg["note"])
        self.assertIn("固定黑色", raster["label"])
        self.assertIn("不会继承", raster["note"])
        pending = next(v for v in item["checks"] if v["name"] == "currentColor 轮廓化发布 SVG")
        self.assertEqual("not_run", pending["result"])
        self.assertNotIn("url", pending)

    def test_wrong_family_count_cannot_publish(self):
        self.with_six()
        self.manifest["actual_family_count"] = 37
        self.reject("actual family count")

    def test_currentcolor_cannot_be_marked_complete(self):
        self.with_six()
        self.manifest["families"][1]["currentcolor_release_status"] = "completed"
        self.reject("outlined release must remain pending")

    def test_family_optical_flag_must_match_actual_128_size(self):
        self.with_six()
        asset = next(v for v in self.manifest["assets"] if v["family"] == "maya" and v["kind"] == "png" and v["size"][0] == 128)
        asset["optical"] = False
        self.reject("actual optical")

    def test_small_export_must_reference_optical_native_document(self):
        self.with_six()
        asset = next(v for v in self.manifest["assets"] if v["family"] == "maya" and v["kind"] == "png" and v["size"][0] == 128)
        call = next(v for v in self.ledger["calls"] if v["key"] == asset["producer"]["receipt_key"])
        call["arguments"]["source_file"] = call["arguments"]["source_file"].replace("-optical", "")
        self.reject("optical document mismatch")

    def test_currentcolor_png_default_is_fixed_black(self):
        self.with_six()
        asset = next(v for v in self.manifest["assets"] if v["family"] == "maya" and v["theme"] == "currentcolor" and v["kind"] == "png")
        asset["currentcolor_default"] = "dynamic_css"
        self.reject("black-default currentColor")

    def test_family_bitmap_qa_failure_is_not_verified(self):
        self.with_six()
        self.family_qa["families"][0]["checks"][0]["pass"] = False
        self.reject("QA asset proof")

    def test_family_qa_hash_must_match_manifest(self):
        self.with_six()
        self.family_qa["families"][0]["checks"][0]["sha256"] = "e" * 64
        self.reject("QA asset proof")

    def test_family_qa_missing_file_cannot_publish(self):
        self.with_six()
        self.family_qa["missing"] = ["planned artifact"]
        self.reject("scoped family file QA")

    def test_family_qa_cannot_omit_a_manifest_asset(self):
        self.with_six()
        self.family_qa["families"][0]["checks"].pop()
        self.reject("QA asset inventory")

    def test_actual_motif_comes_from_source_and_rights(self):
        self.with_six()
        blender = next(v for v in self.project()["items"] if v["slug"] == "dcc-mcp-blender-v2")
        self.assertIn("相机射线与网格", blender["summary"])
        self.source_metadata["blender"]["motif_semantics"] = "old-proposed-glyph"
        self.reject("motif and rights metadata")

    def test_vendor_glyph_inclusion_cannot_use_independent_geometry_scope(self):
        self.with_six()
        self.source_metadata["maya"]["third_party_glyphs_embedded"] = True
        self.reject("motif and rights metadata")

    def test_vendor_mark_permission_is_not_inferred_from_repository_license(self):
        self.with_six()
        self.policy["families"][0]["rights"]["vendor_mark_permission_inferred_from_repo_mit"] = True
        self.reject("independent geometry")

    def test_family_reference_hash_must_match_rights_record(self):
        self.with_six()
        self.source_metadata["maya"]["reference"]["sha256"] = "e" * 64
        self.reject("reference identity mismatch")

    def test_reference_palette_is_not_official_vendor_palette(self):
        self.with_six()
        self.source_metadata["maya"]["palette"]["vendor_official_palette_claimed"] = True
        self.reject("palette reference boundary")

    def test_family_source_metadata_cannot_leak_private_runtime_ids(self):
        self.with_six()
        self.source_metadata["maya"]["instance_id"] = "private-session"
        self.reject("private runtime identifiers")

    def test_core_gui_partial_canvas_is_not_complete_acceptance(self):
        self.with_six()
        self.with_partial_gui()
        item = self.project()["items"][0]
        check = next(v for v in item["checks"] if v["name"] == "GUI 视觉验收")
        self.assertEqual("unknown", check["result"])
        self.assertIn("局部画布", check["observed"])
        self.assertTrue(any("局部画布" in v["label"] for v in item["evidence"]))
        self.ui["full_page_visible"] = True
        self.reject("partial-canvas GUI")

    def test_partial_gui_requires_actual_bound_native_file(self):
        self.with_partial_gui()
        self.ui["native_document"]["sha256"] = "e" * 64
        self.reject("GUI native document hash")

    def test_changed_shared_c_geometry_fails_even_if_other_records_agree(self):
        self.with_six()
        asset = next(v for v in self.manifest["assets"] if v["family"] == "maya" and v["kind"] == "svg")
        target = self.base / asset["path"]
        data = target.read_bytes().replace(b'M1 1H4', b'M1 1H5')
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        asset["sha256"] = digest
        key = asset["producer"]["receipt_key"]
        next(v for v in self.manifest["mcp_receipts"] if v["key"] == key)["output_sha256"] = digest
        call = next(v for v in self.ledger["calls"] if v["key"] == key)
        call["artifact_sha256"] = call["response"]["context"]["sha256"] = digest
        next(v for v in self.family_qa["families"][0]["checks"] if v["path"] == asset["path"])["sha256"] = digest
        self.reject("corrected C geometry differs")

    def test_nine_families_and_core_currentcolor_project_155_files(self):
        self.with_nine()
        catalog = self.project()
        self.assertEqual((10, 37, 155), tuple(catalog["progress"][key] for key in ("completed", "total", "assets")))
        self.assertEqual([11] + [16] * 9, [len(item["variants"]) for item in catalog["items"]])
        self.assertEqual(27, sum(row["status"] == "planned_not_executed" for row in catalog["progress"]["planned"]))
        self.assertEqual({"dcc-mcp-mobu-v2", "dcc-mcp-nuke-v2", "dcc-mcp-openusd-v2"}, {item["slug"] for item in catalog["items"][-3:]})
        self.assertIn("动画骨架与运动轨迹", catalog["items"][-3]["summary"])
        self.assertIn("合成合并节点图", catalog["items"][-2]["summary"])
        self.assertIn("场景图层堆栈与基元", catalog["items"][-1]["summary"])
        core_current = [v for v in catalog["items"][0]["variants"] if "currentcolor" in v["url"]]
        self.assertEqual(3, len(core_current))
        self.assertEqual(1, sum("可编辑原生" in v["label"] for v in core_current))
        self.assertEqual(1, sum("轮廓化原生" in v["label"] for v in core_current))

    def test_item_environment_preserves_each_actual_source_revision(self):
        self.with_nine()
        catalog = self.project()
        core, maya, mobu, nuke = catalog["items"][0], catalog["items"][1], catalog["items"][-3], catalog["items"][-2]
        env = lambda item: next(row["value"] for row in item["environment"] if "适配器" in row["label"])
        self.assertIn("7" * 40, env(core))
        self.assertIn("f" * 40, env(core))
        self.assertIn("7" * 40, env(maya))
        self.assertNotIn("f" * 40, env(maya))
        self.assertIn("7" * 40, env(mobu))
        self.assertIn("f" * 40, env(mobu))
        self.assertNotIn("7" * 40, env(nuke))
        self.assertIn("f" * 40, env(nuke))
        self.assertTrue(all("制作已恢复" in item["limitations"][-1] for item in catalog["items"][1:]))

    def test_core_currentcolor_file_qa_hash_is_required(self):
        self.with_nine()
        self.core_current_qa["checks"][0]["sha256"] = "e" * 64
        self.reject("core currentColor QA proof")

    def test_core_currentcolor_file_qa_scope_cannot_omit_asset(self):
        self.with_nine()
        self.core_current_qa["checks"].pop()
        self.reject("core currentColor QA inventory")

    def test_native_outlined_is_real_build_not_live_text_export(self):
        self.with_nine()
        asset = next(v for v in self.manifest["assets"] if v["role"] == "editable_outlined")
        receipt = next(v for v in self.manifest["mcp_receipts"] if v["key"] == asset["producer"]["receipt_key"])
        receipt["operation"] = "document_export"
        self.reject("tool and operation mismatch")

    def test_nine_qa_and_historical_six_resources_both_remain_selected(self):
        self.with_nine_composites_and_history()
        catalog = self.project()
        old, new = catalog["items"][1], catalog["items"][-1]
        old_links = {e["url"] for e in old["evidence"]}
        new_links = {e["url"] for e in new["evidence"]}
        self.assertTrue(any("historical-six-qa.json" in url for url in old_links))
        self.assertTrue(any("family-first-six-light-qa.png" in url for url in old_links))
        self.assertTrue(any("family-first-nine-light-qa.png" in url for url in old_links))
        self.assertFalse(any("family-first-six" in url for url in new_links))
        self.assertTrue(any("family-first-nine" in url for url in new_links))
        self.assertTrue(any("family-visual.json" in url for url in new_links))

    def test_historical_six_composite_cannot_disappear_when_nine_is_current(self):
        self.with_nine_composites_and_history()
        self.project()
        (self.base / self.historical_qa["composites"][0]["path"]).unlink()
        self.reject("safe existing local file")

    def test_historical_six_composite_replacement_fails_integrity(self):
        self.with_nine_composites_and_history()
        (self.base / self.historical_qa["composites"][0]["path"]).write_bytes(png(641, 180))
        self.reject("composite integrity mismatch")

    def test_nine_visual_review_cannot_refer_to_unrelated_composite(self):
        self.with_nine_composites_and_history()
        self.family_visual["evidence"][0]["sha256"] = "e" * 64
        self.reject("visual composite hash mismatch")

    def test_nine_visual_review_is_not_user_design_approval(self):
        self.with_nine_composites_and_history()
        self.family_visual["brand_design_acceptance"] = "verified"
        self.reject("visual review scope mismatch")

    def test_actual_family_currentcolor_release_is_derived_from_its_matrix(self):
        self.with_nine()
        row = next(v for v in self.manifest["families"] if v["family_id"] == "nuke")
        row.update(currentcolor_release_status="actual_verified", production_status="actual_verified_published_themes")
        data = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 560"><path id="dcc-c1" d="M1 1H4"/><path id="dcc-c2" d="M7 1H10"/></svg>'
        self.add_asset("currentcolor", "svg", "release", "currentcolor-release.svg", data, family="nuke", optical=False, live_text=False, viewbox=[0, 0, 1200, 560])
        asset = self.manifest["assets"][-1]
        qa = next(v for v in self.family_qa["families"] if v["family"] == "nuke")
        qa["checks"].append({"path": asset["path"], "bytes": asset["bytes"], "sha256": asset["sha256"], "format": "svg", "pass": True, "failures": [], "mode": "release", "text_count": 0})
        self.manifest["actual_asset_count"] = 156
        catalog = self.project()
        item = next(v for v in catalog["items"] if v["slug"] == "dcc-mcp-nuke-v2")
        self.assertEqual(17, len(item["variants"]))
        self.assertEqual(156, catalog["progress"]["assets"])
        self.assertEqual("pass", next(v for v in item["checks"] if v["name"] == "currentColor 轮廓化发布 SVG")["result"])


if __name__ == "__main__":
    unittest.main()
