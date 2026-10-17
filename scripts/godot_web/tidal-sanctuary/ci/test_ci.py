"""Fast tests of isolation/failure guards. These do not claim native/browser acceptance."""
import tempfile
import unittest
import signal
from unittest.mock import Mock, patch
from pathlib import Path
from author_native import envelope
from common import check_engine_log, isolated_env, isolated_output
from capture_native import stop_input_runtime, wait_for


class HarnessTests(unittest.TestCase):
    def test_structured_mcp_result_is_preserved(self):
        result = {"success": True, "context": {"valid": True}}
        self.assertEqual(envelope({"structuredContent": result}), result)

    def test_text_mcp_result_is_parsed(self):
        self.assertEqual(envelope({"content": [{"type": "text", "text": '{"success":false}'}]}), {"success": False})

    def test_nested_source_output_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source"
            source.mkdir()
            for output in (source, source / "generated", Path(root)):
                with self.assertRaises(ValueError):
                    isolated_output(output, source)

    def test_existing_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "out"
            path.mkdir()
            (path / "receipt.json").write_text("{}")
            with self.assertRaises(ValueError):
                isolated_output(path)
            self.assertEqual((path / "receipt.json").read_text(), "{}")

    def test_task_session_isolated(self):
        with tempfile.TemporaryDirectory() as root:
            env = isolated_env(Path(root))
            for key in ("HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
                self.assertTrue(Path(env[key]).is_relative_to(root))
                self.assertTrue(Path(env[key]).is_dir())

    def test_runtime_errors_fail(self):
        for message in ("SCRIPT ERROR: Invalid call", "ERROR: Cannot load font", "ERROR: Required extension VK_KHR_surface not found.", "Parse Error: Unexpected token", "Shader compilation failed"):
            with self.assertRaises(RuntimeError):
                check_engine_log(message)
        check_engine_log("TIDAL_READY {}")

    def test_crash_diagnostic_fails_without_error_prefix(self):
        with self.assertRaisesRegex(RuntimeError, "crashed with signal 11"):
            check_engine_log("handle_crash: Program crashed with signal 11")

    def test_wait_refuses_stale_evidence_from_exited_runtime(self):
        for status in (0, 1, -signal.SIGSEGV):
            with self.subTest(status=status):
                process = Mock()
                process.poll.return_value = status
                predicate = Mock(return_value=True)
                with self.assertRaisesRegex(RuntimeError, "exited with status"):
                    wait_for(process, predicate, 1, "ready evidence")
                predicate.assert_not_called()

    def test_wait_checks_exit_again_after_predicate(self):
        process = Mock()
        process.poll.side_effect = [None, -signal.SIGSEGV]
        with self.assertRaisesRegex(RuntimeError, "exited with status"):
            wait_for(process, lambda: True, 1, "ready evidence")

    def test_wait_accepts_live_runtime_evidence(self):
        process = Mock()
        process.poll.return_value = None
        wait_for(process, lambda: True, 1, "ready evidence")
        self.assertEqual(process.poll.call_count, 2)

    def test_deliberate_stop_refuses_already_exited_runtime(self):
        process = Mock()
        process.poll.return_value = -signal.SIGSEGV
        with patch("capture_native.stop_process") as stop:
            with self.assertRaisesRegex(RuntimeError, "deliberate input-test shutdown"):
                stop_input_runtime(process)
            stop.assert_not_called()

    def test_deliberate_stop_rejects_racing_crash(self):
        process = Mock()
        process.poll.return_value = None
        process.returncode = -signal.SIGSEGV
        with patch("capture_native.stop_process") as stop:
            with self.assertRaisesRegex(RuntimeError, "unexpected status"):
                stop_input_runtime(process)
            stop.assert_called_once_with(process)

    def test_deliberate_stop_accepts_only_normal_or_requested_sigterm(self):
        for status in (0, -signal.SIGTERM, -signal.SIGKILL, 1):
            with self.subTest(status=status):
                process = Mock()
                process.poll.return_value = None
                process.returncode = status
                with patch("capture_native.stop_process"):
                    if status in (0, -signal.SIGTERM):
                        stop_input_runtime(process)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "unexpected status"):
                            stop_input_runtime(process)


if __name__ == "__main__":
    unittest.main()
