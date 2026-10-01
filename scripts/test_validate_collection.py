#!/usr/bin/env python3
"""Exercise meaningful publication risks with isolated standard-library fixtures."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import validate_collection


class CollectionContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="showcase-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.entry = self.root / "docs" / "showcase" / "sample"
        self.entry.mkdir(parents=True)
        image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQ2kAAAAASUVORK5CYII=")
        (self.entry / "hero.png").write_bytes(image)
        (self.entry / "README.md").write_text("# Sample\nHistorical evidence; no new DCC execution.\n", encoding="utf-8")
        self.write_json(self.entry / "manifest.json", {
            "schema_version": 1,
            "files": [{"path": "hero.png", "bytes": len(image),
                       "sha256": hashlib.sha256(image).hexdigest(), "width": 1}],
        })
        self.write_json(self.entry / "validation.json", {
            "schema_version": 1, "environment": {"Blender": "5.2.0"},
            "checks": [{"name": "hash", "result": "pass", "observed": "published bytes"}],
            "not_claimed": ["No DCC execution in this publication run."],
        })
        self.asset = "docs/showcase/sample/hero.png"
        self.case = {
            "slug": "sample", "title": "Sample", "subtitle": "Measured artifact",
            "software": ["Blender"], "capabilities": ["Rendering"],
            "cover": {"src": self.asset, "alt": "A render"},
            "evidence_label": "Historical public case; not rerun",
            "evidence_scope": "Only published artifact hashes checked; no DCC execution in this run.",
            "summary": "A real historical rendered artifact.", "goal": "Render a scene.",
            "prompt": {"kind": "reusable", "text": "Use DCC-MCP to render a scene.",
                       "note": "Reusable adapted prompt, never executed in this publication run."},
            "environment": [{"label": "Software", "value": "Blender 5.2.0"},
                            {"label": "Adapter / Core", "value": "Unknown; unrecorded"}],
            "tools": [{"name": "DCC-MCP historical report", "description": "Actual call log unrecorded."}],
            "steps": [{"title": "Render", "description": "Historical report says the host rendered."}],
            "results": [{"src": self.asset, "alt": "A render", "caption": "Historical render."}],
            "checks": [{"name": "hash", "result": "pass", "observed": "published bytes"}],
            "limitations": ["No current DCC reproduction."],
            "resources": [{"label": "Report", "url": "docs/showcase/sample/README.md"}],
            "credits": {"author": "Public author", "license": "MIT", "note": "Attribution retained."},
            "source": {"url": "https://example.org/commit/" + "a" * 40, "commit": "a" * 40},
            "verified_at": "2026-10-01",
        }

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self, cases=None):
        path = self.root / "collection.json"
        self.write_json(path, {"schema_version": 1, "cases": cases or [self.case]})
        return validate_collection.validate(path)

    def test_valid_historical_case_preserves_unknown_boundaries(self):
        self.assertEqual(self.problems(), [])

    def test_unselected_private_case_is_not_scanned(self):
        unused = self.root / "docs" / "showcase" / "unused"
        unused.mkdir()
        (unused / "manifest.json").write_text('{"host":"localhost"}', encoding="utf-8")
        self.assertEqual(self.problems(), [])

    def test_missing_evidence_scope_is_rejected(self):
        del self.case["evidence_scope"]
        self.assertTrue(any("evidence_scope" in p for p in self.problems()))

    def test_duplicate_slug_is_rejected(self):
        self.assertTrue(any("duplicate slug" in p for p in self.problems([self.case, deepcopy(self.case)])))

    def test_short_commit_and_mutable_source_are_rejected(self):
        self.case["source"]["commit"] = "abcdef1"
        self.assertTrue(any("40-digit" in p for p in self.problems()))
        self.case["source"]["commit"] = "a" * 40
        self.case["source"]["url"] = "https://example.org/tree/main"
        self.assertTrue(any("pin the recorded commit" in p for p in self.problems()))

    def test_traversal_absolute_and_encoded_escape_are_rejected(self):
        for unsafe in ("../hero.png", "/hero.png", "C:/private/hero.png",
                       "docs/%2e%2e/hero.png", "docs/%252e%252e/hero.png",
                       "docs\\showcase\\sample\\hero.png", "//private/hero.png",
                       "https://[malformed"):
            with self.subTest(path=unsafe):
                self.case["cover"]["src"] = unsafe
                self.assertTrue(self.problems())

    def test_manifest_traversal_is_rejected_before_legacy_validation(self):
        self.write_json(self.entry / "manifest.json", {"files": [{"path": "../../../secret.txt"}]})
        self.assertTrue(any("unsafe artifact path" in p for p in self.problems()))

    def test_hidden_workspace_metadata_cannot_be_a_public_resource(self):
        private = self.root / ".git"
        private.mkdir()
        (private / "config").write_text("Private repository metadata", encoding="utf-8")
        self.case["resources"][0]["url"] = ".git/config"
        self.assertTrue(any("unsafe" in p for p in self.problems()))

    def test_missing_or_noninventoried_result_is_rejected(self):
        self.case["results"][0]["src"] = "docs/showcase/sample/missing.png"
        self.assertTrue(any("missing" in p for p in self.problems()))
        other = self.root / "other.png"
        other.write_bytes((self.entry / "hero.png").read_bytes())
        self.case["results"][0]["src"] = "other.png"
        self.assertTrue(any("absent from selected" in p for p in self.problems()))

    def test_modified_artifact_hash_is_rejected(self):
        (self.entry / "hero.png").write_bytes(b"changed bytes")
        self.assertTrue(any("sha256 mismatch" in p for p in self.problems()))

    def test_token_is_rejected_without_echoing_credential(self):
        token = "ghp_" + "Q" * 36
        self.case["prompt"]["text"] += " " + token
        problems = self.problems()
        self.assertTrue(any("credential token" in p for p in problems))
        self.assertNotIn(token, "\n".join(problems))

    def test_private_path_and_host_are_rejected(self):
        self.case["summary"] = "Saved to " + "C:" + "\\Users\\private\\scene.blend"
        self.case["goal"] = "Connect to localhost."
        problems = self.problems()
        self.assertTrue(any("private filesystem" in p for p in problems))
        self.assertTrue(any("private host" in p for p in problems))

    def test_bare_private_ip_is_rejected(self):
        self.case["summary"] = "The source machine address was 192.168.50.8."
        self.assertTrue(any("private network" in p for p in self.problems()))

    def test_unsafe_resource_schemes_and_private_https_are_rejected(self):
        for link in ("javascript:alert(1)", "http://example.org/report", "//example.org/report",
                     "https://127.0.0.1/report", "https://10.1.2.3/report", "https://user:password@example.org/report"):
            with self.subTest(link=link):
                self.case["resources"][0]["url"] = link
                self.assertTrue(self.problems())

    def test_prompt_and_unknown_versions_must_be_explicit(self):
        self.case["prompt"]["note"] = "Some words with no prompt classification."
        self.assertTrue(any("label the prompt kind" in p for p in self.problems()))
        self.case["prompt"]["note"] = "Reusable adapted prompt."
        self.case["environment"][1]["value"] = ""
        self.assertTrue(any("versions require" in p for p in self.problems()))

    def test_selected_public_report_is_privacy_scanned(self):
        (self.entry / "README.md").write_text("Connect to https://10.0.0.1/api", encoding="utf-8")
        self.assertTrue(any("private network" in p for p in self.problems()))

    def test_report_links_cannot_use_unsafe_schemes(self):
        (self.entry / "README.md").write_text("[link](javascript:alert)\n", encoding="utf-8")
        self.assertTrue(any("only public HTTPS" in p for p in self.problems()))

    def test_document_sibling_links_are_allowed_inside_public_root(self):
        (self.root / "report.txt").write_text("Public text", encoding="utf-8")
        (self.entry / "README.md").write_text("[link](../../../report.txt)\n", encoding="utf-8")
        self.assertEqual(self.problems(), [])

    def test_generated_site_private_text_and_broken_link_are_rejected(self):
        site = self.root / "_site"
        site.mkdir()
        (site / "index.html").write_text('<a href="missing.md">report</a><p>localhost</p>', encoding="utf-8")
        problems = validate_collection.validate_site(site)
        self.assertTrue(any("missing" in p for p in problems))
        self.assertTrue(any("private host" in p for p in problems))

    def test_generated_site_directory_routes_and_back_link_are_allowed(self):
        site = self.root / "_site"
        detail = site / "cases" / "sample"
        detail.mkdir(parents=True)
        (site / "index.html").write_text('<a href="cases/sample/">case</a>', encoding="utf-8")
        (detail / "index.html").write_text('<a href="../../#works">back</a>', encoding="utf-8")
        self.assertEqual(validate_collection.validate_site(site), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
