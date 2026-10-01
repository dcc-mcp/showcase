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
                data = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 400">' + live + b'</svg>'
                self.add_asset(theme, "svg", role, "%s-%s.svg" % (theme, role), data, viewbox=[0, 0, 900, 400], live_text=role == "editable")
            for width, height in ((1024, 455), (128, 57)):
                self.add_asset(theme, "png", "release", "%s-%d.png" % (theme, width), png(width, height), size=[width, height], transparent=True, corner_alpha=[0, 0, 0, 0])
        for rel in ("fonts/OFL.txt", "LICENSE", "THIRD_PARTY_NOTICES.md"):
            target = self.base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("Original geometry is MIT; Montserrat is OFL; trademark rights reserved.", encoding="utf-8")

    def add_asset(self, theme, kind, role, filename, data, **details):
        key = "core-" + filename.replace(".", "-")
        rel = "assets/" + filename
        target = self.base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        operation = "document_build" if role == "editable" else "document_export"
        asset = {"asset_id": key, "path": rel, "family": "core", "theme": theme, "kind": kind, "role": role, "status": "actual", "qa_status": "verified", "license": "MIT", "bytes": len(data), "sha256": digest,
                 "producer": {"application": "Inkscape 1.4.4", "source_commit": self.runtime, "receipt_key": key}, **details}
        self.manifest["assets"].append(asset)
        self.manifest["families"][0]["actual_asset_ids"].append(key)
        self.manifest["mcp_receipts"].append({"key": key, "operation": operation, "recorded_utc": self.stamp, "source_commit": self.runtime, "control_route": "gateway", "output_sha256": digest})
        self.ledger["calls"].append({"key": key, "tool": brand_manifest.TOOLS[operation], "arguments": {"plan": {"canvas": {"width": 900, "height": 400}}}, "response": {"success": True, "context": {"sha256": digest, "bytes": len(data)}}, "recorded_utc": self.stamp, "source_commit": self.runtime, "control_route": "gateway", "gateway_stats_recorded": True, "artifact_sha256": digest, "original_completed_record_sha256": "b" * 64})
        if kind == "png" or role == "editable":
            self.visual["raster_sources" if kind == "png" else "native_sources"].append({"path": "snapshot/" + rel, "sha256": digest, "bytes": len(data), **({"size": details["size"]} if kind == "png" else {})})

    def tearDown(self):
        self.temp.cleanup()

    def project(self):
        for rel, data in (("manifest.json", self.manifest), ("evidence/calls.json", self.ledger), ("evidence/visual.json", self.visual)):
            target = self.base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data), encoding="utf-8")
        return brand_manifest.project(self.root, "docs/brands/snapshot/manifest.json")

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


if __name__ == "__main__":
    unittest.main()
