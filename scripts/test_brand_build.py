#!/usr/bin/env python3
"""Verify brand publication remains separate from local development previews.

Synthetic rectangle assets are temporary test fixtures, never logo deliverables.
"""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import build_site
from test_build_site import fixture_case, make_png
import test_validate_brand_gallery as brand_fixture


class BrandBuildGuards(unittest.TestCase):
    def setUp(self):
        self.assets = brand_fixture.BrandGuards(methodName="runTest")
        self.assets.setUp()
        self.root = self.assets.root
        self.catalog = self.assets.catalog
        case = fixture_case()
        folder = self.root / "docs/showcase/sample-case"
        folder.mkdir(parents=True)
        (folder / "cover.png").write_bytes(make_png(120, 80))
        (folder / "README.md").write_text("# Fixture", encoding="utf-8")
        (folder / "validation.json").write_text("{}", encoding="utf-8")
        (folder / "manifest.json").write_text(json.dumps({"files": [{"path": "cover.png"}]}), encoding="utf-8")
        (self.root / "collection.json").write_text(json.dumps({"schema_version": 1, "cases": [case]}), encoding="utf-8")
        ui = self.root / "assets"
        ui.mkdir()
        for name in ("site.css", "gallery.js", "detail.js", "brand.css", "brand.js"):
            (ui / name).write_text("/* Fixture UI */", encoding="utf-8")
        (self.root / "index.html").write_text('<html><head>{{SEO_HEAD}}</head>{{BRAND_NAV}}{{BRAND_PORTAL}}{{CASE_CARDS}}</html>', encoding="utf-8")
        (self.root / "unselected-secret.txt").write_text("never selected", encoding="utf-8")

    def tearDown(self):
        self.assets.tearDown()

    def save(self):
        (self.root / "brand-gallery.json").write_text(json.dumps(self.catalog), encoding="utf-8")

    def build(self, out="_site", preview=False):
        # The independent collection validator has its own contract tests.
        with patch("validate_collection.validate", return_value=[]):
            return build_site.build(str(self.root), out, brand_preview=preview)

    def page(self, rel, out="_site"):
        return (self.root / out / rel).read_text(encoding="utf-8")

    def test_missing_catalog_preserves_original_collection(self):
        published, problems, _ = self.build()
        self.assertEqual([], problems)
        self.assertIn("cases/sample-case/index.html", published)
        self.assertFalse(any(path.startswith(("brands/", "brand/", "assets/brand")) for path in published))

    def test_disabled_catalog_publishes_no_brand_content(self):
        self.catalog["enabled"] = False
        self.catalog["items"][0]["status"] = "pending"
        self.save()
        published, problems, _ = self.build()
        self.assertEqual([], problems)
        self.assertFalse(any(path.startswith(("brands/", "brand/", "assets/brand")) for path in published))
        self.assertNotIn("brands/", self.page("index.html"))

    def test_verified_inventory_publishes_only_selected_assets(self):
        self.save()
        published, problems, _ = self.build()
        self.assertEqual([], problems)
        for rel in ("brands/index.html", "brands/dcc-mcp-mark/index.html", "brand/mark.svg", "brand/mark.png", "brand/calls.json", "brand/LICENSE.txt"):
            self.assertIn(rel, published)
        self.assertNotIn("brand-gallery.json", published)
        self.assertNotIn("unselected-secret.txt", published)
        self.assertIn("brands/", self.page("index.html"))
        self.assertIn("../../brands/", self.page("cases/sample-case/index.html"))
        self.assertIn("/showcase/brands/dcc-mcp-mark/", self.page("sitemap.xml"))
        self.assertIn(self.catalog["items"][0]["variants"][0]["sha256"], self.page("brands/dcc-mcp-mark/index.html"))

    def test_invalid_brand_catalog_preserves_previous_output(self):
        output = self.root / "_site"
        output.mkdir()
        (output / "sentinel.txt").write_text("previous deployment", encoding="utf-8")
        self.catalog["items"][0]["variants"][0]["sha256"] = "0" * 64
        self.save()
        published, problems, _ = self.build()
        self.assertEqual([], published)
        self.assertTrue(any("SHA-256 mismatch" in problem for problem in problems))
        self.assertEqual("previous deployment", (output / "sentinel.txt").read_text(encoding="utf-8"))

    def test_local_preview_cannot_target_production_directory(self):
        published, problems, _ = self.build(preview=True)
        self.assertEqual([], published)
        self.assertTrue(any("_site-brand-preview" in problem for problem in problems))
        self.assertFalse((self.root / "_site").exists())

    def test_empty_preview_has_no_unverified_images_or_downloads(self):
        self.catalog.update(enabled=False, items=[])
        self.save()
        published, problems, notes = self.build("_site-brand-preview", preview=True)
        self.assertEqual([], problems)
        self.assertTrue(notes)
        self.assertIn("brands/dcc-mcp/index.html", published)
        for rel in ("brands/index.html", "brands/dcc-mcp/index.html"):
            page = self.page(rel, "_site-brand-preview")
            self.assertIn("noindex, nofollow", page)
            self.assertNotIn("<img", page)
            self.assertNotIn(" download=", page)
        self.assertNotIn("brands/", self.page("sitemap.xml", "_site-brand-preview"))
        self.assertEqual("User-agent: *\nDisallow: /\n", self.page("robots.txt", "_site-brand-preview"))
        self.assertNotIn("brand/mark.svg", published)

    def test_verified_large_png_download_is_not_case_display_media(self):
        (self.root / "brand/mark.png").write_bytes(make_png(2048, 1))
        self.catalog["items"][0]["variants"][1] = self.assets.asset("mark.png", "png", width=2048, height=1)
        self.save()
        published, problems, _ = self.build()
        self.assertEqual([], problems)
        self.assertIn("brand/mark.png", published)

    def test_nonverified_item_cannot_generate_production_pages(self):
        import brand_pages
        self.catalog["items"][0]["status"] = "pending"
        with self.assertRaises(ValueError):
            brand_pages.generate(self.catalog, str(self.root))


if __name__ == "__main__":
    unittest.main()
