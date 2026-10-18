#!/usr/bin/env python3
"""Read-only catalog and rights regression tests. Standard library only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import agent_pages
import build_site
import localization


def fixture_case():
    return {
        "slug": "selected-work", "title": 'A <script>alert("x")</script> & work',
        "subtitle": "An original production record", "software": ["Test Host"],
        "capabilities": ["Render"], "summary": "An existing public work",
        "goal": "Inspect the actual output", "evidence_label": "Public record",
        "evidence_scope": "Historical execution; not rerun",
        "cover": {"src": "docs/showcase/selected-work/cover.svg", "alt": "A work"},
        "prompt": {"kind": "reusable", "text": "Create <one> object.", "note": "Not the original prompt"},
        "environment": [{"label": "Host", "value": "1.0; adapter unknown"}],
        "tools": [{"name": "host.render", "description": "Published call name"}],
        "steps": [{"title": "Render", "description": "Run the host", "image": {
            "src": "docs/showcase/selected-work/cover.svg", "alt": "Output"}}],
        "checks": [{"name": "Reopen", "result": "fail", "observed": "No clean reopen"},
                   {"name": "Cross-host", "result": "not-run", "observed": "Not attempted"}],
        "limitations": ["Original host unavailable"],
        "resources": [{"label": "Report", "url": "docs/showcase/selected-work/README.md"},
                      {"label": "Source", "url": "https://example.com/public-source"}],
        "credits": {"author": "Original artist", "license": "MIT", "note": "Original scope retained"},
        "source": {"url": "https://example.com/public-source", "commit": "a" * 40},
        "verified_at": "2026-10-01",
        "model_attribution": [
            {"stage_id": "creation", "stage": "Creation", "model": "Unknown",
             "reasoning_effort": "Unknown", "record_status": "unknown",
             "basis": "Historical configuration unrecorded", "scope": "Original artwork"},
            {"stage_id": "review", "stage": "Review", "model": "Recorded reviewer",
             "reasoning_effort": "high", "record_status": "recorded",
             "basis": "Actual review record", "scope": "Later review only"}],
        "revision_notes": [{"version": "Imported baseline", "date": "2026-10-01",
                            "change": "No new execution"}],
    }


class AgentPagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = fixture_case()
        self.base = self.root / "docs/showcase/selected-work"
        self.base.mkdir(parents=True)
        for name, payload in (("cover.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
                              ("README.md", b"Public report\n"),
                              ("validation.json", b'{"result":"fail"}\n')):
            (self.base / name).write_bytes(payload)
        self.manifest = {"schema_version": 1, "files": [
            {"path": name, "sha256": hashlib.sha256((self.base / name).read_bytes()).hexdigest(),
             "bytes": (self.base / name).stat().st_size}
            for name in ("cover.svg", "README.md", "validation.json")]}
        self.save_manifest()

    def save_manifest(self):
        (self.base / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def generate(self, cases=None, demos=None):
        pages, data = agent_pages.generate(self.root, [self.case] if cases is None else cases, demos or {})
        return pages, data, json.loads(data["data/catalog.json"])

    def test_only_selected_records_and_inventoried_files(self):
        private = self.root / "docs/showcase/unselected-work"
        private.mkdir()
        (private / "manifest.json").write_text("not a valid manifest")
        (self.base / "unlisted-private.txt").write_text("PRIVATE-SENTINEL")
        self.case["private_working_notes"] = "PRIVATE-SENTINEL /home/owner/not-published"
        with patch.object(Path, "rglob", side_effect=AssertionError("must not crawl")), \
             patch("os.walk", side_effect=AssertionError("must not crawl")):
            pages, data, catalog = self.generate()
        self.assertEqual(set(pages), {"agents/index.html"})
        self.assertEqual(set(data), {"data/catalog.json"})
        self.assertEqual(catalog["record_count"], 1)
        self.assertEqual([row["slug"] for row in catalog["records"]], ["selected-work"])
        self.assertNotIn("unselected-work", data["data/catalog.json"])
        self.assertNotIn("PRIVATE-SENTINEL", data["data/catalog.json"])
        self.assertNotIn("unlisted-private", data["data/catalog.json"])
        self.assertNotIn(str(self.root), data["data/catalog.json"])

    def test_publication_is_separate_from_unverified_rights(self):
        for license_text in ("MIT", "CC0-1.0", "Unknown", "Rights reserved"):
            with self.subTest(license=license_text):
                self.case["credits"]["license"] = license_text
                self.case["usage_rights"] = {"training": {"status": "granted", "evidence": ["unverified assertion"]}}
                _, _, catalog = self.generate()
                record = catalog["records"][0]
                self.assertEqual(record["credits"], self.case["credits"])
                self.assertEqual(record["publication_status"], "selected-public-record")
                for row in (catalog, record):
                    self.assertFalse(row["rights_verified"])
                    self.assertEqual(row["usage_rights"], {
                        "display": {"status": "unknown", "evidence": []},
                        "training": {"status": "not-granted", "evidence": []},
                        "evaluation": {"status": "not-granted", "evidence": []}})
                    self.assertEqual(row["benchmark"]["status"], "not-an-accepted-benchmark")
                self.assertFalse(catalog["future_use"]["available_dataset"])
                self.assertFalse(catalog["benchmark"]["model_quality_inferred"])
                self.assertEqual(catalog["schema_id"], "dcc-showcase-catalog/v1")

    def test_original_provenance_and_unknown_attribution_are_unchanged(self):
        before = copy.deepcopy(self.case)
        _, _, catalog = self.generate()
        record = catalog["records"][0]
        for key in agent_pages.SOURCE_FIELDS:
            self.assertEqual(record[key], before[key], key)
        self.assertEqual(record["model_attribution"][0]["model"], "Unknown")
        self.assertEqual(record["checks"][0]["result"], "fail")
        self.assertEqual(record["checks"][1]["result"], "not-run")
        self.assertEqual(self.case, before)
        self.assertEqual(catalog["source_text"]["mode"], "original-untranslated")

    def test_exact_manifest_hash_and_stable_file_bindings(self):
        _, data, catalog = self.generate()
        refs = catalog["records"][0]["public_references"]
        raw = (self.base / "manifest.json").read_bytes()
        self.assertEqual(refs["manifest"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(refs["manifest"]["bytes"], len(raw))
        self.assertEqual(refs["manifest"]["url"], build_site.SITE_URL + "docs/showcase/selected-work/manifest.json")
        for record, source in zip(refs["files"], self.manifest["files"]):
            self.assertEqual(record["manifest_path"], source["path"])
            self.assertEqual(record["sha256"], source["sha256"])
            self.assertEqual(record["bytes"], source["bytes"])
            self.assertEqual(record["hash_source"], "manifest")
        self.assertEqual(data, self.generate()[1])
        self.assertEqual(refs["resources"][1]["integrity"], "external-reference-only")
        self.assertNotIn("sha256", refs["resources"][1])

    def test_required_record_outside_inventory_gets_no_inferred_hash(self):
        self.manifest["files"] = self.manifest["files"][:1]
        self.save_manifest()
        _, _, catalog = self.generate()
        report = catalog["records"][0]["public_references"]["report"]
        self.assertEqual(report["integrity"], "selected-required-record-not-in-file-inventory")
        self.assertNotIn("sha256", report)

    def test_invalid_manifest_hash_is_rejected(self):
        self.manifest["files"][0]["sha256"] = "not-a-hash"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "requires bytes and SHA-256"):
            self.generate()

    def test_local_resources_must_be_selected_and_inventoried(self):
        path = "docs/showcase/selected-work/unlisted.txt"
        (self.root / path).write_text("Not a published artifact")
        self.case["resources"].append({"label": "Not inventoried", "url": path})
        with self.assertRaisesRegex(ValueError, "outside selected public inventories"):
            self.generate()

    def test_private_metadata_is_rejected_without_echoing_it(self):
        self.case["environment"][0]["value"] = "/home/private-owner/secret-project"
        with self.assertRaises(ValueError) as caught:
            self.generate()
        self.assertNotIn("private-owner", str(caught.exception))
        self.assertIn("unsafe public metadata", str(caught.exception))

    def test_manifest_cannot_expose_hidden_or_escaping_paths(self):
        for path in ("../private.txt", "/home/owner/private.txt", ".private/file.txt", "%2e%2e/private.txt"):
            with self.subTest(path=path):
                self.manifest["files"][0]["path"] = path
                self.save_manifest()
                with self.assertRaises(ValueError):
                    self.generate()

    def test_manifest_cannot_follow_symlink_outside_repository(self):
        with tempfile.TemporaryDirectory() as outside:
            source = Path(outside) / "private.txt"
            source.write_text("Not public")
            link = self.base / "linked.txt"
            link.symlink_to(source)
            self.manifest["files"][0]["path"] = link.name
            self.save_manifest()
            with self.assertRaisesRegex(ValueError, "outside repository"):
                self.generate()

    def test_title_is_escaped_and_no_optional_production_record_is_needed(self):
        pages, data, catalog = self.generate()
        page = pages["agents/index.html"]
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertIn("&lt;script&gt;", page)
        self.assertEqual(catalog["records"][0]["title"], self.case["title"])
        self.assertNotIn("dcc-showcase-production/v1", data["data/catalog.json"])
        self.assertNotIn("skills/", data["data/catalog.json"])
        self.assertIn('aria-current="page">Agent 与数据', page)

    def test_empty_selection_does_not_read_any_manifest(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("must not read")):
            _, _, catalog = self.generate(cases=[])
        self.assertEqual(catalog["records"], [])

    def test_unselected_demo_is_not_read_or_exposed(self):
        _, data, _ = self.generate(demos={"not-selected": {"url": "/home/owner/private"}})
        self.assertNotIn("not-selected", data["data/catalog.json"])
        self.assertNotIn("playable", data["data/catalog.json"])

    def test_selected_demo_uses_only_explicit_play_inventory(self):
        play = self.root / "play"
        play.mkdir()
        payload = b"<!doctype html><title>Selected demo</title>"
        (play / "index.html").write_bytes(payload)
        (play / "manifest.json").write_text(json.dumps({"schema_version": 1, "files": [
            {"path": "play/index.html", "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}]}))
        demos = {"selected-work": {"url": "play/index.html", "engine": "Godot", "threads": False,
                                   "private_notes": "/home/private-owner/unpublished"}}
        _, data, catalog = self.generate(demos=demos)
        demo = catalog["records"][0]["playable"]
        self.assertEqual(demo["entry"]["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(demo["manifest"]["url"], build_site.SITE_URL + "play/manifest.json")
        self.assertNotIn("private_notes", data["data/catalog.json"])

    def test_page_localizes_without_localizing_the_machine_index(self):
        pages, data, _ = self.generate()
        translations = localization.catalog(Path(__file__).resolve().parents[1])
        translations.update(agent_pages.AGENT_TRANSLATIONS)
        source_pages = {"index.html", "agents/index.html", "cases/selected-work/index.html"}
        for locale in ("en", "zh"):
            parser = localization.LocalizedHTML("agents/index.html", locale, source_pages,
                                                translations if locale == "en" else {})
            parser.feed(pages["agents/index.html"])
            parser.close()
            self.assertFalse(parser.missing)
            page = ''.join(parser.output)
            prefix = "zh/" if locale == "zh" else ""
            self.assertIn('rel="canonical" href="' + build_site.SITE_URL + prefix + 'agents/"', page)
            self.assertIn('href="../../data/catalog.json"' if locale == "zh" else 'href="../data/catalog.json"', page)
        self.assertEqual(set(data), {"data/catalog.json"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
