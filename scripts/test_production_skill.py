#!/usr/bin/env python3
"""Behavioral checks: isolated records plus real, read-only repository examples."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "dcc-showcase-production"
spec = importlib.util.spec_from_file_location("check_showcase", SKILL / "scripts" / "check_showcase.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entry = self.root / "docs/showcase/sample"
        self.entry.mkdir(parents=True)
        for name, value in (("README.md", "Synthetic fixture, not host evidence.\n"),
                            ("observations.txt", "Synthetic fixture, not a real production run.\n"),
                            ("recipe.txt", "Synthetic recipe fixture.\n")):
            (self.entry / name).write_text(value)
        self.write(self.entry / "validation.json", {"schema_version": 1, "environment": {}, "checks": [{"name": "legacy", "result": "pass"}]})
        self.ref = self.reference("observations.txt")
        self.case = {"slug": "sample", "software": ["Blender"], "results": [], "model_attribution": [
            {"stage_id": "creation", "model": "Unknown", "reasoning_effort": "Unknown", "record_status": "unknown", "basis": "No record", "scope": "Original production"},
            {"stage_id": "review_visual", "model": "Unknown", "reasoning_effort": "Unknown", "record_status": "unknown", "basis": "No record", "scope": "Separate review"}]}
        self.record = {"schema": checker.SCHEMA, "case_slug": "sample", "recorded_at": "2026-10-12T00:00:00Z",
                       "environment": [{"role": role, "component": role, "version": "fixture-version", "evidence": self.ref} for role in ["host", "adapter", "core"]],
                       "recipe": self.reference("recipe.txt"), "sources": [self.ref],
                       "task": {"goal": "Validate synthetic record boundaries", "inputs": [], "capabilities": ["fixture"], "reproduction_budget": {"estimated_seconds": None, "measured_seconds": None, "cost_ceiling": None}},
                       "outputs": [self.ref], "usage_rights": dict(checker.default_usage_rights(), display={"status": "granted", "evidence": [self.ref]}),
                       "checks": {stage: {"status": "passed", "evidence_origin": "historical", "scope": "Synthetic fixture, never host acceptance", "summary": "Synthetic structural fixture, not measured acceptance.", "evidence": [self.ref]} for stage in checker.STAGES}}
        self.refresh()

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def reference(self, name):
        path = self.entry / name
        return {"path": path.relative_to(self.root).as_posix(), "sha256": checker.digest(path)}

    def refresh(self):
        self.write(self.entry / "production-evidence.json", self.record)
        files = [{"path": p.name, "sha256": checker.digest(p), "bytes": p.stat().st_size}
                 for p in self.entry.iterdir() if p.name not in {"README.md", "validation.json", "manifest.json"}]
        self.write(self.entry / "manifest.json", {"schema_version": 1, "files": files})
        self.write(self.root / "collection.json", {"schema_version": 1, "cases": [self.case]})

    def test_valid_record_is_only_a_record(self):
        errors, missing = checker.validate_record(self.root, self.record, "sample", False)
        self.assertEqual((errors, missing), ([], []))
        result = checker.inspect_case(self.root, self.case)
        self.assertFalse(result["ready_for_human_decision"])
        self.assertIn("missing_video", result["unresolved_stages"])
        self.assertEqual(result["quality_approval"], "not-assessed-by-this-tool")

    def test_unexecuted_stage_cannot_be_ready(self):
        for status in ("failed", "not-tested", "blocked"):
            with self.subTest(status=status):
                self.record["checks"]["save_reopen"]["status"] = status
                errors, missing = checker.validate_record(self.root, self.record, "sample", False)
                self.assertEqual(errors, [])
                self.assertIn("save_reopen", missing)

    def test_pass_needs_evidence_and_hash_matches(self):
        self.record["checks"]["real_mcp"]["evidence"] = []
        self.assertTrue(checker.validate_record(self.root, self.record, "sample", False)[0])
        self.record["checks"]["real_mcp"]["evidence"] = [dict(self.ref, sha256="0" * 64)]
        self.assertTrue(checker.validate_record(self.root, self.record, "sample", False)[0])

    def test_unknown_environment_stays_unresolved(self):
        self.record["environment"][0].update(version="unknown", reason="Not available")
        errors, missing = checker.validate_record(self.root, self.record, "sample", False)
        self.assertEqual(errors, [])
        self.assertIn("environment:host", missing)

    def test_godot_requires_real_interaction_and_web(self):
        self.case["software"] = ["Godot"]
        result = checker.inspect_case(self.root, self.case)
        self.assertIn("native_interaction", result["unresolved_stages"])
        self.assertIn("web_playable", result["unresolved_stages"])

    def test_non_godot_interactive_flag(self):
        self.record["interactive"] = True
        self.refresh()
        self.assertIn("native_interaction", checker.inspect_case(self.root, self.case)["unresolved_stages"])

    def test_model_unknown_is_not_replaced_by_current_reviewer(self):
        before = deepcopy(self.case["model_attribution"])
        result = checker.inspect_case(self.root, self.case)
        self.assertEqual(result["model_attribution"], before)
        self.assertFalse(result["model_identity_verified"])
        self.assertEqual(self.case["model_attribution"], before)

    def test_tampered_manifest_blocks_readiness(self):
        (self.entry / "observations.txt").write_text("Changed bytes")
        result = checker.inspect_case(self.root, self.case)
        self.assertTrue(result["manifest_errors"])
        self.assertTrue(result["record_errors"])
        self.assertFalse(result["ready_for_human_decision"])

    def test_invalid_status_and_timestamp_rejected(self):
        self.record["checks"]["visual_review"]["status"] = "pass"
        self.record["recorded_at"] = "yesterday"
        self.assertGreaterEqual(len(checker.validate_record(self.root, self.record, "sample", False)[0]), 2)

    def test_paths_cannot_escape(self):
        for path in ("../secret", "/etc/passwd", "https://example.com/file", "docs\\secret"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                checker.local_path(self.root, path)
        (self.entry / "escape").symlink_to("/etc/passwd")
        with self.assertRaises(ValueError):
            checker.local_path(self.root, "docs/showcase/sample/escape")

    def test_declared_video_with_fake_bytes_does_not_pass_decode(self):
        (self.entry / "fake.mp4").write_bytes(b"a JSON claim is not a movie")
        self.refresh()
        result = checker.inspect_case(self.root, self.case, decode=True)
        self.assertNotEqual(result["video_decode"][0]["status"], "passed")
        self.assertFalse(result["ready_for_human_decision"])

    def test_missing_decoder_and_external_media_are_blocked(self):
        (self.entry / "probe.mp4").write_bytes(b"unavailable decoder fixture")
        with patch.object(checker.shutil, "which", return_value=None):
            self.assertEqual(checker.decode_video(self.root, "docs/showcase/sample/probe.mp4")["status"], "blocked")
        result = checker.decode_video(self.root, "https://example.com/movie.mp4")
        self.assertEqual(result["status"], "blocked")
        (self.entry / "pointer.mp4").write_text("version https://git-lfs.github.com/spec/v1\noid sha256:abc\n")
        self.assertEqual(checker.decode_video(self.root, "docs/showcase/sample/pointer.mp4")["status"], "blocked")

    @unittest.skipUnless(shutil.which("ffprobe") and shutil.which("ffmpeg"), "real video decode tools unavailable")
    def test_complete_claims_and_real_bytes_still_need_human_decision(self):
        shutil.copyfile(ROOT / "docs/showcase/prism-tide/demo.mp4", self.entry / "video.mp4")
        self.refresh()
        result = checker.inspect_case(self.root, self.case, decode=True)
        self.assertTrue(result["ready_for_human_decision"])
        self.assertEqual(result["quality_approval"], "not-assessed-by-this-tool")
        self.assertFalse(result["model_identity_verified"])
        self.assertEqual(result["unknown_model_stages"], ["creation", "review_visual"])

    def test_usage_rights_are_independent_and_never_inferred_from_mit(self):
        del self.record["usage_rights"]
        (self.root / "LICENSE").write_text("MIT")
        self.refresh()
        result = checker.inspect_case(self.root, self.case)
        self.assertEqual(result["usage_rights"]["display"]["status"], "unknown")
        self.assertEqual(result["usage_rights"]["training"]["status"], "not-granted")
        self.assertEqual(result["usage_rights"]["evaluation"]["status"], "not-granted")
        self.assertIn("display_rights", result["unresolved_stages"])
        self.record["usage_rights"] = checker.default_usage_rights()
        self.record["usage_rights"]["training"] = {"status": "granted", "evidence": []}
        self.assertTrue(checker.validate_record(self.root, self.record, "sample", False)[0])

    def test_outputs_must_belong_to_case_inventory(self):
        (self.root / "LICENSE").write_text("MIT")
        self.record["outputs"] = [{"path": "LICENSE", "sha256": checker.digest(self.root / "LICENSE")}]
        self.assertTrue(checker.validate_record(self.root, self.record, "sample", False)[0])
        (self.entry / "not-selected.txt").write_text("not in the artifact manifest")
        self.record["outputs"] = [self.reference("not-selected.txt")]
        self.assertTrue(checker.validate_record(self.root, self.record, "sample", False)[0])

    def test_inputs_may_reuse_assets_outside_case_inventory(self):
        shared = self.root / "shared-licensed-input.dat"
        shared.write_bytes(b"authorized synthetic cross-case input")
        self.record["task"]["inputs"] = [{"path": shared.name, "sha256": checker.digest(shared), "origin_url": "https://example.org/authorized-source"}]
        self.assertEqual(checker.validate_record(self.root, self.record, "sample", False)[0], [])

    def test_declared_rights_are_never_verified_by_checker(self):
        self.record["usage_rights"] = {"display": {"status": "granted", "evidence": [self.ref]}}
        self.refresh()
        result = checker.inspect_case(self.root, self.case)
        self.assertEqual(result["usage_rights"]["display"]["status"], "granted")
        self.assertEqual(result["usage_rights"]["training"]["status"], "not-granted")
        self.assertEqual(result["usage_rights"]["evaluation"]["status"], "not-granted")
        self.assertFalse(result["rights_verified"])

    def test_measured_budget_and_recovery_need_evidence(self):
        self.record["task"]["reproduction_budget"]["measured_seconds"] = 12
        self.record["failure_recovery"] = [{"stage": "real_mcp", "status": "passed", "minimal_reproducer": self.ref}]
        errors, _ = checker.validate_record(self.root, self.record, "sample", False)
        self.assertGreaterEqual(len(errors), 2)
        self.record["task"]["reproduction_budget"]["evidence"] = self.ref
        self.record["failure_recovery"][0]["real_regression"] = self.ref
        self.assertEqual(checker.validate_record(self.root, self.record, "sample", False)[0], [])

    def test_unrun_stage_cannot_be_declared_passed(self):
        self.record["checks"]["visual_review"]["evidence_origin"] = "not-run"
        self.assertTrue(checker.validate_record(self.root, self.record, "sample", False)[0])

    @unittest.skipUnless(shutil.which("ffprobe") and shutil.which("ffmpeg"), "real video decode tools unavailable")
    def test_decoder_threads_are_bounded_and_explicit(self):
        path = "docs/showcase/prism-tide/demo.mp4"
        with patch.object(checker.subprocess, "run", wraps=checker.subprocess.run) as run:
            result = checker.decode_video(ROOT, path, threads=1)
        self.assertEqual(result["status"], "passed")
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[command.index("-threads") + 1], "1")
        for threads in (0, 9, True):
            with self.assertRaises(ValueError):
                checker.decode_video(ROOT, path, threads=threads)

    def test_cli_readiness_exit_and_malformed_input(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main(["--repo", str(self.root), "--case", "sample"]), 0)
            self.assertEqual(checker.main(["--repo", str(self.root), "--case", "sample", "--require-ready"]), 1)
            self.assertEqual(checker.main(["--repo", str(self.root), "--case", "absent"]), 2)
            self.write(self.root / "collection.json", {"cases": "not an array"})
            self.assertEqual(checker.main(["--repo", str(self.root)]), 2)


class RealRepositoryCases(unittest.TestCase):
    def get_case(self, slug):
        return next(c for c in checker.read_json(ROOT / "collection.json")["cases"] if c["slug"] == slug)

    @unittest.skipUnless(shutil.which("ffprobe") and shutil.which("ffmpeg"), "real video decode tools unavailable")
    def test_prism_tide_current_video_bytes_decode_without_mutation(self):
        case = self.get_case("prism-tide")
        paths = [ROOT / "collection.json", ROOT / "docs/showcase/prism-tide/validation.json", ROOT / "docs/showcase/prism-tide/demo.mp4"]
        before = [checker.digest(p) for p in paths]
        result = checker.inspect_case(ROOT, case, decode=True)
        self.assertEqual(result["manifest_errors"], [])
        self.assertFalse(result["optional_record_present"])
        self.assertEqual(result["declared_playables"][0]["url"], "play/prism-tide/index.html")
        pointers = {r["path"] for r in result["existing_evidence_pointers"]}
        self.assertIn("play/manifest.json", pointers)
        self.assertIn("play/verification-portrait.json", pointers)
        self.assertTrue(all(r["status_this_run"] == "not-tested" for r in result["existing_evidence_pointers"]))
        self.assertTrue(result["video_decode"])
        self.assertTrue(all(r["status"] == "passed" for r in result["video_decode"]))
        self.assertTrue(all(r["duration_seconds"] > 0 and r["decoded_frames"] > 1 for r in result["video_decode"]))
        self.assertFalse(result["ready_for_human_decision"])
        self.assertEqual(result["quality_approval"], "not-assessed-by-this-tool")
        self.assertEqual(before, [checker.digest(p) for p in paths])

    def test_case_output_inventory_rejects_other_case_and_shared_engine(self):
        selected = checker.selected_output_refs(ROOT, "prism-tide")
        self.assertIn("docs/showcase/prism-tide/demo.mp4", selected)
        self.assertIn("play/prism-tide/game.pck", selected)
        self.assertNotIn("docs/showcase/crate-lookdev/hero.jpg", selected)
        self.assertNotIn("LICENSE", selected)
        self.assertNotIn("play/runtime/godot-4.6.3.wasm", selected)

    def test_crate_current_inventory_preserves_historical_unknowns(self):
        case = self.get_case("crate-lookdev")
        before = checker.digest(ROOT / "collection.json")
        result = checker.inspect_case(ROOT, case)
        self.assertEqual(result["manifest_errors"], [])
        # The historical baseline has no video; later partial supplements may
        # add one without changing original attribution or accepting the film.
        manifest = checker.read_json(ROOT / "docs/showcase/crate-lookdev/manifest.json")
        expected_videos = sorted({"docs/showcase/crate-lookdev/" + item["path"]
                                  for item in manifest["files"]
                                  if Path(item["path"]).suffix.lower() in checker.VIDEO_EXTENSIONS})
        self.assertEqual(result["video_paths"], expected_videos)
        self.assertEqual("missing_video" in result["unresolved_stages"], not expected_videos)
        expected_attribution = [{key: row[key] for key in
                                 ("stage_id", "model", "reasoning_effort", "record_status", "basis", "scope")}
                                for row in case["model_attribution"]]
        self.assertEqual(result["model_attribution"], expected_attribution)
        self.assertFalse(result["optional_record_present"])
        self.assertIn("continuous_frames", result["unresolved_stages"])
        self.assertEqual(result["quality_approval"], "not-assessed-by-this-tool")
        self.assertIn("creation", result["unknown_model_stages"])
        self.assertIn("review_visual", result["unknown_model_stages"])
        self.assertFalse(result["ready_for_human_decision"])
        self.assertFalse(result["model_identity_verified"])
        self.assertEqual(before, checker.digest(ROOT / "collection.json"))


if __name__ == "__main__":
    unittest.main()
