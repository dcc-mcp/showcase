"""Pure smoke packaging/deadline fixtures. They never launch Chrome or render PCM."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import check_audio_observer_browser as smoke


class AudioObserverSmokeFixtures(unittest.TestCase):
    def source(self, root):
        source = root / "source"
        (source / "assets/audio").mkdir(parents=True)
        (source / "web_audio.js").write_bytes(b"// original backend fixture\n")
        for name in smoke.AUDIO_FILES.values():
            (source / "assets/audio" / name).write_bytes(("original bytes: " + name).encode())
        return source

    def test_served_backend_and_all_five_assets_keep_exact_original_bytes_and_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.source(Path(temporary))
            resources, hashes = smoke.fixture_resources(source)
            self.assertEqual(len(resources), 7)
            for url, (body, _) in resources.items():
                if url == "/":
                    continue
                self.assertEqual(body, (source / url.lstrip("/")).read_bytes())
                self.assertEqual(hashes[url.lstrip("/")]["sha256"], hashlib.sha256(body).hexdigest())
            html = resources["/"][0].decode()
            self.assertIn("TidalWebAudio.initialize(", html)
            self.assertIn("onclick=\"TidalWebAudio.start('observer_fixture_button')\"", html)
            self.assertNotIn("AudioContext", html)
            self.assertNotIn("createBuffer", html)
            self.assertNotIn("resume(", html)
            self.assertEqual(html.count("<button "), 4)

    def test_missing_lfs_empty_and_escaped_sources_fail_without_fallback(self):
        for failure in ("missing", "lfs", "empty", "escape"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source = self.source(root)
                target = source / "assets/audio/chart_read.wav"
                if failure == "missing": target.unlink()
                if failure == "empty": target.write_bytes(b"")
                if failure == "lfs": target.write_text("version https://git-lfs.github.com/spec/v1\n")
                if failure == "escape":
                    outside = root / "unrelated.wav"; outside.write_bytes(b"not original")
                    target.unlink(); target.symlink_to(outside)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    smoke.fixture_resources(source)

    def test_report_write_is_complete_and_does_not_leave_a_partial_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            value = {"passed": False, "error": "original failure", "stage": "cue"}
            smoke.save_report(output, value)
            self.assertEqual(json.loads((output / "receipt.json").read_text()), value)
            self.assertFalse((output / ".receipt.json.tmp").exists())

    def supervised(self, output, process, result=None):
        def finish(*args, **kwargs):
            smoke.save_report(output, result or {"passed": True, "status": "passed", "scope": smoke.SCOPE})
            return 0 if result is None or result["passed"] else 1
        process.wait.side_effect = finish
        with patch.object(smoke.subprocess, "Popen", return_value=process) as launch, contextlib.redirect_stdout(io.StringIO()):
            code = smoke.supervise(Path("/verified/chrome"), Path("/selected/source"), output)
        return code, launch

    def test_success_requires_real_worker_success_and_preserves_explicit_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); process = Mock(pid=1234)
            code, launch = self.supervised(output, process)
            self.assertEqual(code, 0)
            command = launch.call_args.args[0]
            self.assertIn("--observer-worker", command)
            self.assertEqual(command[command.index("--chromium") + 1], "/verified/chrome")
            self.assertEqual(command[command.index("--source") + 1], "/selected/source")
            self.assertTrue(launch.call_args.kwargs["start_new_session"])
            report = json.loads((output / "receipt.json").read_text())
            self.assertTrue(report["passed"])
            self.assertEqual(report["maximum_seconds"], 30)
            self.assertIn("no Godot gameplay", report["scope"])

    def test_worker_validation_failure_retains_exact_stage_and_reason(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); process = Mock(pid=1234)
            result = {"passed": False, "status": "failed", "stage": "real-cue-and-source-bound-pcm", "error": "missing actual channel"}
            code, _ = self.supervised(output, process, result)
            report = json.loads((output / "receipt.json").read_text())
            self.assertEqual(code, 1); self.assertEqual(report["error"], result["error"])
            self.assertEqual(report["stage"], result["stage"]); self.assertEqual(report["worker_exit_code"], 1)

    def test_global_deadline_kills_only_owned_group_and_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            process = Mock(pid=4321)
            process.wait.side_effect = [subprocess.TimeoutExpired("owned fixture", 27), -9]
            with patch.object(smoke.subprocess, "Popen", return_value=process), patch.object(smoke.os, "killpg") as kill, contextlib.redirect_stdout(io.StringIO()):
                code = smoke.supervise(Path("/verified/chrome"), Path("/source"), output)
            kill.assert_called_once_with(4321, signal.SIGKILL)
            self.assertLessEqual(process.wait.call_args_list[0].kwargs["timeout"], 27)
            self.assertEqual(process.wait.call_args_list[1].kwargs["timeout"], 2)
            report = json.loads((output / "receipt.json").read_text())
            self.assertEqual(code, 1); self.assertFalse(report["passed"])
            self.assertIn("work budget", report["deadline_error"])

    def test_launcher_failure_is_a_saved_failure_not_an_unfinished_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with patch.object(smoke.subprocess, "Popen", side_effect=OSError("driver unavailable")), contextlib.redirect_stdout(io.StringIO()):
                code = smoke.supervise(Path("/verified/chrome"), Path("/source"), output)
            report = json.loads((output / "receipt.json").read_text())
            self.assertEqual(code, 1); self.assertEqual(report["status"], "failed")
            self.assertIn("driver unavailable", report["launcher_error"])

    def test_late_success_cannot_exceed_total_time_ceiling(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); process = Mock(pid=1234)
            with patch.object(smoke.time, "monotonic", side_effect=[0, 0, 31]):
                code, _ = self.supervised(output, process)
            report = json.loads((output / "receipt.json").read_text())
            self.assertEqual(code, 1); self.assertFalse(report["passed"])
            self.assertIn("total 30-second", report["deadline_error"])


if __name__ == "__main__":
    unittest.main()
