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
            "model_attribution": self.complete_attribution(),
            "revision_notes": [{"version": "Imported historical baseline", "date": "2026-10-01",
                                "change": "Historical artifact; making model unrecorded"}],
        }

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def problems(self, cases=None):
        path = self.root / "collection.json"
        self.write_json(path, {"schema_version": 1, "cases": cases or [self.case]})
        return validate_collection.validate(path)

    def attribution(self):
        return {"stage_id": "creation", "stage": "Creation", "model": "Unknown", "reasoning_effort": "Unknown",
                "record_status": "unknown", "basis": "Historical model unrecorded",
                "scope": "Original artwork, not current review"}

    def complete_attribution(self, creation=None):
        rows = [dict(self.attribution(), stage_id=stage, stage=stage)
                for stage in ("planning", "creation", "code", "reference", "post_production", "review")]
        if creation is not None:
            rows[1] = creation
        return rows

    def test_incomplete_stage_categories_fail_closed(self):
        self.case["model_attribution"] = [self.attribution()]
        self.assertTrue(any("missing required stage categories" in p for p in self.problems()))
        for stage in ("planning", "creation", "code", "reference", "post_production", "review"):
            with self.subTest(stage=stage):
                self.case["model_attribution"] = [r for r in self.complete_attribution() if r["stage_id"] != stage]
                self.assertTrue(any("missing required stage categories" in p for p in self.problems()))

    def test_invalid_and_duplicate_stage_ids_rejected(self):
        for bad in ("creation", "unrecognized", ["creation"]):
            with self.subTest(stage_id=bad):
                self.case["model_attribution"] = self.complete_attribution()
                self.case["model_attribution"][0]["stage_id"] = bad
                self.assertTrue(any("stage_id" in p for p in self.problems()))

    def test_split_visual_and_technical_review_allowed(self):
        rows = self.complete_attribution()[:-1]
        rows += [dict(self.attribution(), stage_id=s, stage=s) for s in ("review_visual", "review_technical")]
        self.case["model_attribution"] = rows
        self.assertEqual(self.problems(), [])

    def test_unknown_cannot_contain_a_model_or_effort_claim(self):
        for field, value in (("model", "GPT-6 Astra (configuration unknown)"),
                             ("reasoning_effort", "ultra (unknown record)")):
            with self.subTest(field=field):
                self.case["model_attribution"] = self.complete_attribution(dict(self.attribution(), **{field: value}))
                self.assertTrue(any("unknown record" in p for p in self.problems()))

    def test_additional_execution_roots_rejected_without_echo(self):
        for path in ("/var/tmp/private-task.json", "/private/tmp/task.json", "/mnt/data/task.json",
                     "/run/user/task.json", "/opt/project/task.json", "/srv/project/task.json"):
            for prefix in ("Saved ", "path:"):
                with self.subTest(path=path, prefix=prefix):
                    self.case["model_attribution"] = self.complete_attribution(dict(self.attribution(), basis=prefix+path))
                    problems = self.problems()
                    self.assertTrue(any("private execution path" in p for p in problems))
                    self.assertNotIn(path, "\n".join(problems))

    def test_missing_model_attribution_fails_closed(self):
        del self.case["model_attribution"]
        self.assertTrue(any("missing required field model_attribution" in p for p in self.problems()))

    def test_missing_revision_notes_fails_closed(self):
        del self.case["revision_notes"]
        self.assertTrue(any("missing required field revision_notes" in p for p in self.problems()))

    def test_empty_required_attribution_and_revisions_are_rejected(self):
        for field in ("model_attribution", "revision_notes"):
            with self.subTest(field=field):
                previous = self.case[field]
                self.case[field] = []
                self.assertTrue(any(field + ": must be a nonempty array" in p for p in self.problems()))
                self.case[field] = previous

    def test_receipt_bound_without_receipt_is_not_supported(self):
        self.case["model_attribution"] = [dict(self.attribution(), model="gpt-6-astra",
            reasoning_effort="ultra", record_status="receipt_bound", basis="Some receipt")]
        self.assertTrue(any("invalid record_status" in p for p in self.problems()))

    def test_receipt_bound_cannot_pass_with_unchecked_receipt_text(self):
        self.case["model_attribution"] = [dict(self.attribution(), model="gpt-6-astra",
            reasoning_effort="ultra", record_status="receipt_bound", receipt="pretend proof")]
        self.assertTrue(any("invalid record_status" in p for p in self.problems()))

    def test_execution_paths_in_attribution_are_rejected_without_echo(self):
        for path in ("/workspace/shared/private-project/task.json", "/tmp/private-task.json",
                     "/root/private-task.json"):
            for field in ("basis", "scope"):
                with self.subTest(path=path, field=field):
                    self.case["model_attribution"] = [dict(self.attribution(), **{field: "Saved " + path})]
                    problems = self.problems()
                    self.assertTrue(any("private execution path" in p for p in problems))
                    self.assertNotIn(path, "\n".join(problems))

    def test_relative_and_public_paths_are_not_execution_paths(self):
        for text in ("docs/showcase/workspace/public-config.json", "docs/showcase/tmp/public-config.json",
                     "docs/showcase/root/public-config.json", "https://example.org/tmp/public-config.json", "https://example.org/var/tmp/public.json",
                     "docs/showcase/opt/public.json"):
            with self.subTest(text=text):
                self.case["model_attribution"] = self.complete_attribution(dict(self.attribution(), basis=text))
                self.assertEqual(self.problems(), [])

    def test_execution_paths_after_colon_are_rejected_without_echo(self):
        for path in ("/workspace/shared/private-task.json", "/tmp/private.json", "/root/private.json"):
            with self.subTest(path=path):
                self.case["model_attribution"] = [dict(self.attribution(), basis="path:" + path)]
                problems = self.problems()
                self.assertTrue(any("private execution path" in p for p in problems))
                self.assertNotIn(path, "\n".join(problems))

    def test_model_unknown_and_current_config_stay_separate(self):
        review = dict(self.attribution(), stage_id="review", stage="Independent review", model="GPT-6 Astra",
                      reasoning_effort="ultra", record_status="configured",
                      basis="Accepted task configuration, not backend attestation")
        self.case["model_attribution"] = self.complete_attribution()[:-1] + [review]
        self.case["revision_notes"] = [{"version": "Documentation 2026-10-07", "date": "2026-10-07",
                                        "change": "Attribution only; artwork bytes unchanged"}]
        self.assertEqual(self.problems(), [])

    def test_unknown_attribution_cannot_claim_known_model(self):
        self.case["model_attribution"] = [dict(self.attribution(), model="GPT-6 Astra")]
        self.assertTrue(any("unknown record" in p for p in self.problems()))

    def test_configured_attribution_requires_effort(self):
        self.case["model_attribution"] = [dict(self.attribution(), model="GPT-6 Astra", record_status="configured")]
        self.assertTrue(any("explicit model and effort" in p for p in self.problems()))

    def test_duplicate_model_stage_is_rejected(self):
        self.case["model_attribution"] = [self.attribution(), self.attribution()]
        self.assertTrue(any("duplicate stage" in p for p in self.problems()))

    def test_invalid_attribution_status_is_rejected(self):
        self.case["model_attribution"] = [dict(self.attribution(), record_status="guessed")]
        self.assertTrue(any("invalid record_status" in p for p in self.problems()))

    def test_invalid_revision_date_is_rejected(self):
        self.case["revision_notes"] = [{"version": "v1", "date": "2026-02-30", "change": "Review only"}]
        self.assertTrue(any("invalid date" in p for p in self.problems()))

    def test_model_basis_is_privacy_scanned(self):
        self.case["model_attribution"] = [dict(self.attribution(), basis="Private path /home/example/private.json")]
        self.assertTrue(any("private filesystem path" in p for p in self.problems()))

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

    def test_published_reproduction_scripts_are_privacy_scanned(self):
        for extension in (".py", ".ps1", ".sh"):
            with self.subTest(extension=extension):
                report = self.root / ("replay" + extension)
                report.write_text("private = 'C:/private/scene.hip'\n", encoding="utf-8")
                self.case["resources"] = [{"label": "Replay", "url": report.name}]
                self.assertTrue(any("private filesystem" in p for p in self.problems()))

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
