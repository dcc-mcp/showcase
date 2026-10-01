#!/usr/bin/env python3
"""Exercise brand publication boundaries with real SVG/PNG fixture files."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest.mock import patch
import zlib

import validate_brand_gallery as gallery


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)


def png(metadata=b"", width=2, height=1):
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + metadata + chunk(b"IDAT", zlib.compress((b"\x00" + b"\xff\x00\x00\xff" * width) * height)) + chunk(b"IEND", b""))


SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10"><defs><linearGradient id="paint"><stop offset="0" stop-color="#f00"/></linearGradient></defs><path d="M0 0H20V10H0Z" fill="url(#paint)"/></svg>'


class BrandGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.assets = self.root / "brand"
        self.assets.mkdir()
        (self.assets / "mark.svg").write_bytes(SVG)
        (self.assets / "mark.png").write_bytes(png())
        (self.assets / "LICENSE.txt").write_text("Brand artwork: permitted redistribution with attribution. Trademark rights reserved.", encoding="utf-8")
        (self.assets / "calls.json").write_text(json.dumps({"evidence_scope": "Recorded vector construction and export responses.", "calls": [
            {"tool": "inkscape_documents__create_document", "arguments": {}, "response": {"success": True, "document_created": True}}
        ]}), encoding="utf-8")
        source = {"id": "original", "label": "Original user-contributed brand artwork", "url": "https://example.com/original.svg", "sha256": "1" * 64}
        self.catalog = {"schema_version": 1, "enabled": True, "title": "Brand gallery", "description": "Verified vector studies", "updated_at": "2026-10-01", "items": [{
            "slug": "dcc-mcp-mark", "title": "DCC-MCP", "family": "DCC-MCP", "software": ["Inkscape"], "summary": "Rounded mark reconstruction",
            "status": "verified", "verified_at": "2026-10-01T10:00:00Z",
            "previews": {"light": {"src": "brand/mark.svg", "alt": "Brand mark on a light background"}, "dark": {"src": "brand/mark.png", "alt": "Raster brand mark on a dark background"}},
            "variants": [self.asset("mark.svg", "svg", viewBox=[0, 0, 20, 10]), self.asset("mark.png", "png", width=2, height=1)],
            "prompt": {"kind": "original", "text": "Reconstruct the rounded mark.", "note": "Original production request"},
            "environment": [{"label": "Inkscape", "value": "1.4"}, {"label": "DCC-MCP adapter", "value": "0.1.0"}, {"label": "DCC-MCP Core", "value": "0.20.39"}],
            "tools": [{"name": "inkscape_documents__create_document", "description": "Create a vector document"}],
            "steps": [{"title": "Construction", "description": "Create rounded paths"}],
            "checks": [{"name": "Geometry", "result": "pass", "observed": "Closed curve contour verified"}],
            "evidence": [{"label": "MCP calls", "url": "brand/calls.json"}], "sources": [source],
            "rights": [{"id": "artwork", "holder": "DCC-MCP contributors", "license": "LicenseRef-Brand", "scope": "Original artwork", "url": "brand/LICENSE.txt", "notice": "Credit the contributors; trademark rights reserved."}],
            "contributors": ["DCC-MCP contributors"], "limitations": ["Visual matching is independently reviewed"]
        }]}

    def tearDown(self):
        self.temp.cleanup()

    def asset(self, filename, fmt, **extra):
        data = (self.assets / filename).read_bytes()
        return {"label": filename, "url": "brand/" + filename, "format": fmt, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "rights_ids": ["artwork"], "source_id": "original", **extra}

    @property
    def item(self):
        return self.catalog["items"][0]

    def check(self, expected=None):
        path = self.root / "brand-gallery.json"
        path.write_text(json.dumps(self.catalog), encoding="utf-8")
        catalog, selected, problems = gallery.read_and_validate(self.root)
        if expected:
            self.assertTrue(any(expected in issue for issue in problems), problems)
        else:
            self.assertEqual([], problems)
        return catalog, selected, problems

    def change_svg(self, data):
        (self.assets / "mark.svg").write_bytes(data)
        self.item["variants"][0] = self.asset("mark.svg", "svg", viewBox=[0, 0, 20, 10])

    def test_verified_files_selected(self):
        _, selected, _ = self.check()
        self.assertEqual({"brand/mark.svg", "brand/mark.png", "brand/LICENSE.txt", "brand/calls.json"}, selected)

    def test_missing_catalog_disabled(self):
        catalog, selected, issues = gallery.read_and_validate(self.root)
        self.assertFalse(catalog["enabled"])
        self.assertEqual((set(), []), (selected, issues))

    def test_disabled_does_not_select_unverified_or_private_files(self):
        self.catalog["enabled"] = False
        self.item["status"] = "pending"
        self.item["summary"] = "C:\\Users\\private\\secret"
        _, selected, _ = self.check()
        self.assertEqual(set(), selected)

    def test_string_enabled_cannot_publish(self):
        self.catalog["enabled"] = "false"
        self.check("boolean")

    def test_boolean_schema_not_integer_one(self):
        self.catalog["schema_version"] = True
        self.check("integer 1")

    def test_enabled_empty_inventory_fails(self):
        self.catalog["items"] = []
        self.check("nonempty array")

    def test_pending_and_bad_verified_date_fail(self):
        self.item["status"] = "pending"
        self.item["verified_at"] = "yesterday"
        self.check("only verified")
        self.check("ISO date")

    def test_replaced_asset_fails_integrity(self):
        (self.assets / "mark.svg").write_bytes(SVG.replace(b"#f00", b"#0f0"))
        self.check("SHA-256 mismatch")

    def test_wrong_dimensions_fail(self):
        self.item["variants"][1]["width"] = 3
        self.check("PNG dimensions mismatch")
        self.item["variants"][0]["viewBox"] = [0, 0, 30, 10]
        self.check("viewBox must match")

    def test_missing_source_hash_fails(self):
        del self.item["sources"][0]["sha256"]
        self.check("original source SHA-256")

    def test_unpinned_source_commit_fails(self):
        self.item["sources"][0]["commit"] = "a" * 40
        self.check("must pin recorded commit")

    def test_missing_rights_for_asset_fails(self):
        self.item["variants"][0]["rights_ids"] = ["software-logo"]
        self.check("known rights_ids")

    def test_composite_rights_selects_both_license_sources(self):
        (self.assets / "TRADEMARK.txt").write_text("Software vendor retains its trademark rights.", encoding="utf-8")
        self.item["rights"].append({"id": "trademark", "holder": "Software vendor", "license": "Trademark notice", "scope": "Software logo only", "url": "brand/TRADEMARK.txt", "notice": "No endorsement implied"})
        self.item["variants"][0]["rights_ids"].append("trademark")
        _, selected, _ = self.check()
        self.assertIn("brand/TRADEMARK.txt", selected)

    def test_unverified_preview_rejected(self):
        (self.assets / "old.svg").write_bytes(SVG)
        self.item["previews"]["light"]["src"] = "brand/old.svg"
        self.check("validated variant asset")

    def test_no_local_evidence_not_verified(self):
        self.item["evidence"][0]["url"] = "https://example.com/calls.json"
        self.check("local successful MCP")

    def test_tool_name_only_is_not_response_proof(self):
        (self.assets / "calls.json").write_text(json.dumps({"evidence_scope": "Vector creation", "tool": "inkscape_documents__create_document"}), encoding="utf-8")
        self.check("matching all tools")

    def test_failed_response_cannot_verify_tool(self):
        (self.assets / "calls.json").write_text(json.dumps({"evidence_scope": "Vector creation", "calls": [{"tool": "inkscape_documents__create_document", "arguments": {}, "response": {"success": False, "error": "failed"}}]}), encoding="utf-8")
        self.check("matching all tools")

    def test_private_evidence_text_diagnostics_do_not_echo_secret(self):
        self.item["summary"] = "C:\\Users\\private-user\\asset.svg"
        _, _, problems = self.check("private filesystem path")
        self.assertNotIn("private-user", " ".join(problems))

    def test_path_traversal_rejected(self):
        self.item["variants"][0]["url"] = "%2e%2e/outside.svg"
        self.check("path is unsafe")

    def test_svg_active_and_external_features_fail(self):
        payloads = [b'<script>alert(1)</script>', b'<foreignObject/>', b'<path onload="alert(1)"/>',
                    b'<use href="https://example.com/other.svg#x"/>', b'<path fill="url(https://example.com/paint)"/>',
                    b'<style>@import "https://example.com/paint.css";</style>']
        for payload in payloads:
            with self.subTest(payload=payload):
                self.change_svg(SVG.replace(b"</svg>", payload + b"</svg>"))
                self.assertTrue(self.check("SVG")[2])

    def test_svg_dtd_and_missing_fragment_fail(self):
        self.change_svg(b'<!DOCTYPE svg [<!ENTITY x "bad">]>' + SVG)
        self.check("DTD")
        self.change_svg(SVG.replace(b"url(#paint)", b"url(#missing)"))
        self.check("resolve to an internal id")

    def test_svg_metadata_private_path_fails(self):
        self.change_svg(SVG.replace(b"</svg>", b'<desc>C:\\Users\\private\\original.svg</desc></svg>'))
        self.check("private filesystem path")

    def test_png_text_and_compressed_metadata_private_path_fail(self):
        for tag, payload in ((b"tEXt", b"Source\0C:\\Users\\private\\mark.svg"),
                             (b"zTXt", b"Source\0\0" + zlib.compress(b"C:\\Users\\private\\mark.svg")),
                             (b"iTXt", b"Source\0\1\0\0\0" + zlib.compress(b"C:\\Users\\private\\mark.svg"))):
            with self.subTest(tag=tag):
                (self.assets / "mark.png").write_bytes(png(chunk(tag, payload)))
                self.item["variants"][1] = self.asset("mark.png", "png", width=2, height=1)
                self.check("private filesystem path")

    def test_png_crc_corruption_rejected_even_with_matching_file_hash(self):
        data = bytearray(png())
        data[-1] ^= 1
        (self.assets / "mark.png").write_bytes(data)
        self.item["variants"][1] = self.asset("mark.png", "png", width=2, height=1)
        self.check("malformed PNG")

    def test_svg_xml_base_cannot_redirect_internal_fragment(self):
        self.change_svg(SVG.replace(b'viewBox="0 0 20 10"', b'viewBox="0 0 20 10" xml:base="other.svg"'))
        self.check("xml:base forbidden")

    def test_png_exif_gps_rejected(self):
        # A minimal valid little-endian TIFF with the GPS IFD pointer tag.
        exif = b"II" + struct.pack("<HIH", 42, 8, 1) + struct.pack("<HHII", 0x8825, 4, 1, 26) + b"\0" * 4
        (self.assets / "mark.png").write_bytes(png(chunk(b"eXIf", exif)))
        self.item["variants"][1] = self.asset("mark.png", "png", width=2, height=1)
        self.check("EXIF GPS metadata forbidden")

    def test_png_exif_utf16_private_description_rejected(self):
        exif = b"II" + struct.pack("<HIH", 42, 8, 0) + b"\0" * 4 + "C:\\Users\\private\\mark.svg".encode("utf-16-le")
        (self.assets / "mark.png").write_bytes(png(chunk(b"eXIf", exif)))
        self.item["variants"][1] = self.asset("mark.png", "png", width=2, height=1)
        self.check("private filesystem path")

    def test_png_malformed_compressed_metadata_rejected(self):
        (self.assets / "mark.png").write_bytes(png(chunk(b"zTXt", b"Source\0\0not-zlib")))
        self.item["variants"][1] = self.asset("mark.png", "png", width=2, height=1)
        self.check("malformed PNG")

    def test_actual_versions_required(self):
        for index in range(3):
            with self.subTest(index=index):
                original = self.item["environment"][index]["value"]
                self.item["environment"][index]["value"] = "unrecorded"
                self.check("version")
                self.item["environment"][index]["value"] = original

    def test_malformed_fields_fail_without_exception_or_selected_files(self):
        mutations = [lambda item: item.update(rights=[{"id": []}]),
                     lambda item: item["variants"][0].update(source_id=[]),
                     lambda item: item.update(software="Inkscape"),
                     lambda item: item.update(verified_at=[]),
                     lambda item: item.update(variants=[False]),
                     lambda item: item.update(previews=False)]
        initial = copy.deepcopy(self.catalog)
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.catalog = copy.deepcopy(initial)
                mutate(self.item)
                path = self.root / "brand-gallery.json"
                path.write_text(json.dumps(self.catalog), encoding="utf-8")
                self.assertTrue(gallery.validate(path))

    def test_duplicate_source_id_is_ambiguous(self):
        self.item["sources"].append(copy.deepcopy(self.item["sources"][0]))
        self.check("duplicate id")

    def test_steps_require_image_object_with_alt(self):
        self.item["steps"][0]["image"] = "brand/mark.png"
        self.check("image object")
        self.item["steps"][0]["image"] = {"src": "brand/mark.png"}
        self.check("alt: nonempty string")
        self.item["steps"][0]["image"]["alt"] = "Construction image"
        self.check()

    def test_rights_id_must_be_safe_fragment_slug(self):
        for bad in ("Adobe CC", "artwork#other", "../license", "", "UPPERCASE"):
            with self.subTest(rights_id=bad):
                self.item["rights"][0]["id"] = bad
                self.item["variants"][0]["rights_ids"] = [bad]
                self.check("safe lowercase slug")

    def test_original_source_svg_with_correct_hash_cannot_bypass_activity_scan(self):
        raw = SVG.replace(b"</svg>", b"<script>alert(1)</script></svg>")
        (self.assets / "original.svg").write_bytes(raw)
        source = self.item["sources"][0]
        source["url"] = "brand/original.svg"
        source["sha256"] = hashlib.sha256(raw).hexdigest()
        self.check("unsupported or active element")

    def test_original_source_png_with_correct_hash_cannot_bypass_private_metadata(self):
        raw = png(chunk(b"tEXt", b"Source\0C:\\Users\\private\\original.svg"))
        (self.assets / "original.png").write_bytes(raw)
        source = self.item["sources"][0]
        source["url"] = "brand/original.png"
        source["sha256"] = hashlib.sha256(raw).hexdigest()
        self.check("private filesystem path")

    def test_all_selection_routes_audit_svg_and_png(self):
        routes = ("steps", "rights", "evidence")
        for fmt in ("svg", "png"):
            raw = (SVG.replace(b"</svg>", b'<use href="https://example.com/a.svg#x"/></svg>')
                   if fmt == "svg" else png(chunk(b"zTXt", b"Source\0\0" + zlib.compress(b"C:\\Users\\private\\original.svg"))))
            (self.assets / ("unsafe." + fmt)).write_bytes(raw)
            initial = copy.deepcopy(self.catalog)
            for route in routes:
                with self.subTest(format=fmt, route=route):
                    self.catalog = copy.deepcopy(initial)
                    url = "brand/unsafe." + fmt
                    if route == "steps":
                        self.item["steps"][0]["image"] = {"src": url, "alt": "Production step"}
                    elif route == "rights":
                        self.item["rights"][0]["url"] = url
                    else:
                        self.item["evidence"].append({"label": "Additional evidence", "url": url})
                    self.check("private filesystem path" if fmt == "png" else "internal id")
            self.catalog = initial

    def test_safe_local_source_is_selected_and_remote_source_is_not(self):
        source = self.item["sources"][0]
        source["url"] = "brand/mark.svg"
        source["sha256"] = hashlib.sha256(SVG).hexdigest()
        _, selected, _ = self.check()
        self.assertIn("brand/mark.svg", selected)
        source["url"] = "https://example.com/original.svg"
        _, selected, _ = self.check()
        self.assertNotIn("original.svg", selected)

    def test_native_live_text_and_precise_passive_namedview_are_supported(self):
        native = (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                  b'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" viewBox="0 0 20 10">'
                  b'<sodipodi:namedview id="view" pagecolor="#ffffff" borderopacity="0.25" inkscape:deskcolor="#ddd" '
                  b'inkscape:showpageshadow="2" inkscape:pageopacity="0" inkscape:pagecheckerboard="0" inkscape:document-units="mm"/>'
                  b'<g inkscape:label="Editable text" inkscape:groupmode="layer"><text x="1" y="8" '
                  b'style="fill:#111;font-family:Montserrat;font-size:6;font-weight:800"><tspan>MCP</tspan></text></g></svg>')
        self.change_svg(native)
        self.check()

    def test_native_editor_namespaces_cannot_admit_active_or_unknown_content(self):
        start = (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
                 b'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" viewBox="0 0 20 10">')
        for bad in (b'<sodipodi:namedview><script>alert(1)</script></sodipodi:namedview>',
                    b'<sodipodi:namedview onload="alert(1)"/>',
                    b'<sodipodi:namedview inkscape:export-filename="x.svg"/>',
                    b'<inkscape:path/>', b'<path inkscape:unknown="static"/>',
                    b'<text><foreignObject/></text>', b'<style>text{fill:red}</style>',
                    b'<text style="font-family:url(https://example.com/font)">MCP</text>'):
            with self.subTest(payload=bad):
                self.change_svg(start + bad + b'</svg>')
                self.assertTrue(self.check("SVG")[2])

    def test_unknown_namespace_declarations_and_attributes_rejected(self):
        for bad in (SVG.replace(b'viewBox=', b'xmlns:other="https://example.com/namespace" viewBox='),
                    SVG.replace(b'<path d=', b'<path xmlns:other="https://example.com/namespace" other:property="value" d=')):
            with self.subTest(svg=bad):
                self.change_svg(bad)
                self.check("namespace")

    def test_adapter_fixed_commit_is_valid_without_invented_semver(self):
        self.item["environment"][1]["value"] = "unreleased source commit 7657bafe78dad0c59c833e25da6f330067c2e64b"
        self.check()
        self.item["environment"][1]["value"] = "unreleased source commit 7657baf"
        self.check("fixed commit")

    def test_manifest_pointer_uses_projection_and_selects_single_authoritative_manifest(self):
        original = copy.deepcopy(self.catalog)
        manifest = self.assets / "manifest.json"
        manifest.write_text(json.dumps({"schema_version": 2, "scope": "Only actual assets"}), encoding="utf-8")
        self.catalog = {"schema_version": 1, "enabled": True, "manifest": "brand/manifest.json"}
        module = types.SimpleNamespace(project=lambda root, path: original)
        with patch.dict("sys.modules", {"brand_manifest": module}):
            catalog, selected, _ = self.check()
        self.assertEqual(original, catalog)
        self.assertIn("brand/manifest.json", selected)
        self.assertFalse((self.assets / "items.json").exists())

    def test_manifest_pointer_rejects_private_authoritative_metadata(self):
        original = copy.deepcopy(self.catalog)
        (self.assets / "manifest.json").write_text(json.dumps({"schema_version": 2, "path": "C:\\Users\\private\\original.svg"}), encoding="utf-8")
        self.catalog = {"schema_version": 1, "enabled": True, "manifest": "brand/manifest.json"}
        with patch.dict("sys.modules", {"brand_manifest": types.SimpleNamespace(project=lambda root, path: original)}):
            self.check("private filesystem path")

    def test_manifest_pointer_does_not_project_when_disabled(self):
        self.catalog = {"schema_version": 1, "enabled": False, "manifest": "missing.json"}
        with patch.dict("sys.modules", {"brand_manifest": types.SimpleNamespace(project=lambda root, path: self.fail("disabled projection must not run"))}):
            _, selected, _ = self.check()
        self.assertEqual(set(), selected)

    def test_manifest_pointer_rejects_non_json_or_invalid_projection(self):
        self.catalog = {"schema_version": 1, "enabled": True, "manifest": "brand/LICENSE.txt"}
        self.check("safe local JSON")
        (self.assets / "manifest.json").write_text("{}", encoding="utf-8")
        self.catalog["manifest"] = "brand/manifest.json"
        for projected in ({"schema_version": True, "enabled": True}, {"schema_version": 1, "enabled": False}, []):
            with self.subTest(projected=projected), patch.dict("sys.modules", {"brand_manifest": types.SimpleNamespace(project=lambda root, path: projected)}):
                self.check("projection must return")

    def test_manifest_pointer_digest_pins_actual_snapshot_before_projection(self):
        original = copy.deepcopy(self.catalog)
        path = self.assets / "manifest.json"
        path.write_text('{"schema_version":2}', encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.catalog = {"schema_version": 1, "enabled": True, "manifest": "brand/manifest.json", "manifest_sha256": digest}
        with patch.dict("sys.modules", {"brand_manifest": types.SimpleNamespace(project=lambda root, rel: original)}):
            self.check()
        path.write_text('{"schema_version":2,"replaced":true}', encoding="utf-8")
        with patch.dict("sys.modules", {"brand_manifest": types.SimpleNamespace(project=lambda root, rel: self.fail("hash mismatch must stop projection"))}):
            self.check("actual manifest SHA-256 mismatch")

    def test_manifest_pointer_digest_requires_complete_hash(self):
        (self.assets / "manifest.json").write_text("{}", encoding="utf-8")
        for bad in (True, "short", "g" * 64, None):
            self.catalog = {"schema_version": 1, "enabled": True, "manifest": "brand/manifest.json", "manifest_sha256": bad}
            with self.subTest(digest=bad):
                self.check("full 64-digit")

    def install_small_previews(self):
        (self.assets / "small.png").write_bytes(png(width=128, height=57))
        self.item["variants"].append(self.asset("small.png", "png", width=128, height=57))
        self.item["small_previews"] = {theme: {"src": "brand/small.png", "alt": theme + " native 128px output", "width": 128, "height": 57} for theme in ("light", "dark")}

    def test_small_previews_use_actual_128px_variant(self):
        self.install_small_previews()
        self.check()

    def test_small_preview_nonvariant_or_remote_asset_rejected(self):
        self.install_small_previews()
        (self.assets / "unverified-small.png").write_bytes(png(width=128, height=57))
        self.item["small_previews"]["light"]["src"] = "brand/unverified-small.png"
        self.check("validated variant asset")
        self.item["small_previews"]["light"]["src"] = "https://example.com/small.png"
        self.check("only public HTTPS or safe local")

    def test_small_preview_css_dimensions_cannot_claim_actual_128px_export(self):
        self.install_small_previews()
        self.item["small_previews"]["light"]["src"] = "brand/mark.png"
        self.check("actual PNG dimensions must match")
        self.item["small_previews"]["light"]["src"] = "brand/mark.svg"
        self.check("actual 128px PNG required")

    def test_small_preview_missing_alt_wrong_height_or_extra_theme_rejected(self):
        self.install_small_previews()
        del self.item["small_previews"]["light"]["alt"]
        self.check("alt: nonempty string")
        self.item["small_previews"]["light"]["alt"] = "Small export"
        self.item["small_previews"]["light"]["height"] = 56
        self.check("actual PNG dimensions must match")
        self.item["small_previews"]["other"] = {"src": "unverified.png"}
        self.check("exactly light and dark")


if __name__ == "__main__":
    unittest.main(verbosity=2)
