"""Fast tests of isolation/failure guards. These do not claim native/browser acceptance."""
import tempfile
import json
import unittest
import signal
from unittest.mock import Mock, patch
from pathlib import Path
from author_native import envelope
from common import GAME_FILES, check_engine_log, copy_game, isolated_env, isolated_output
from capture_native import stop_input_runtime, wait_for
from observers import CHINESE_LABELS, observer_receipts, validate_language_frame, validate_touch_release


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

    def test_manifest_copies_nested_assets_byte_for_byte(self):
        expected_assets = {"assets/shore-rock-a.tscn", "assets/shore-rock-d.tscn",
                           "assets/coastal-tree.tscn", "assets/needle-pine.tscn",
                           "assets/KENNEY-LICENSE.txt", "assets/SOURCE.json"}
        self.assertTrue(expected_assets.issubset(GAME_FILES))
        with tempfile.TemporaryDirectory() as root:
            source, destination = Path(root) / "source", Path(root) / "copy"
            for name in GAME_FILES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("original bytes: " + name).encode())
            copy_game(source, destination)
            for name in GAME_FILES:
                self.assertEqual((destination / name).read_bytes(), (source / name).read_bytes())

    def test_manifest_missing_asset_cannot_silently_pass(self):
        with tempfile.TemporaryDirectory() as root:
            source, destination = Path(root) / "source", Path(root) / "copy"
            source.mkdir()
            for name in GAME_FILES[:-1]:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            with self.assertRaises(FileNotFoundError):
                copy_game(source, destination)

    def touch_receipt(self):
        return {"schema": 1, "gesture_id": 1, "touch_index": 0,
                "before": [1.3, 1.7, 10], "after": [1.6, 1.7, 9.6],
                "physics_frames_elapsed": 60, "drag_events": 1,
                "canceled": False, "demo": False, "active_after": False, "move_after": [0, 0]}

    def language_receipt(self):
        return {"schema": 1, "change_id": 1, "previous": "en", "language": "zh", "trigger": "key_L",
                "labels": {**CHINESE_LABELS, "prompt": "海的记忆正在苏醒"}, "missing_codepoints": []}

    def test_touch_validation_computes_actual_horizontal_distance(self):
        self.assertAlmostEqual(validate_touch_release(self.touch_receipt()), .5)

    def test_touch_validation_rejects_vertical_only_and_threshold_motion(self):
        for after in ([1.3, 20, 10], [1.55, 1.7, 10]):
            receipt = self.touch_receipt()
            receipt["after"] = after
            with self.assertRaises(ValueError):
                validate_touch_release(receipt)

    def test_touch_validation_rejects_missing_or_false_positive_evidence(self):
        cases = [("physics_frames_elapsed", 0), ("drag_events", 0), ("canceled", True),
                 ("demo", True), ("active_after", True), ("move_after", [0, .1]),
                 ("touch_index", 1), ("gesture_id", True), ("schema", True),
                 ("after", [float("nan"), 1, 2]), ("after", [1, float("inf"), 2]),
                 ("after", [True, 1, 2]), ("before", "(1.3, 1.7, 10)")]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                receipt = self.touch_receipt()
                receipt[field] = value
                with self.assertRaises(ValueError):
                    validate_touch_release(receipt)
        for field in self.touch_receipt():
            receipt = self.touch_receipt()
            del receipt[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_touch_release(receipt)
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_touch_release(self.touch_receipt(), previous_gesture_id=1)

    def test_language_validation_requires_actual_rendered_chinese_labels(self):
        labels = validate_language_frame(self.language_receipt())
        self.assertEqual(labels["title"], "潮 汐 圣 所")
        self.assertEqual(labels["prompt"], "海的记忆正在苏醒")

    def test_language_validation_rejects_untranslated_prompt_and_missing_glyph(self):
        receipt = self.language_receipt()
        receipt["labels"]["prompt"] = "A memory returns to the sea"
        with self.assertRaisesRegex(ValueError, "prompt"):
            validate_language_frame(receipt)
        receipt = self.language_receipt()
        receipt["missing_codepoints"] = [ord("潮")]
        with self.assertRaisesRegex(ValueError, "codepoints"):
            validate_language_frame(receipt)
        receipt = self.language_receipt()
        receipt["labels"]["title"] = "TIDAL SANCTUARY"
        with self.assertRaisesRegex(ValueError, "title"):
            validate_language_frame(receipt)

    def test_language_validation_rejects_stale_or_non_keyboard_transition(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_language_frame(self.language_receipt(), previous_change_id=1)
        for field, value in (("trigger", "injected"), ("language", "en"), ("previous", "zh"),
                             ("change_id", 0), ("schema", True), ("missing_codepoints", None)):
            receipt = self.language_receipt()
            receipt[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_language_frame(receipt)

    def test_observer_parser_only_accepts_fresh_exact_event_lines(self):
        marker = "TIDAL_TOUCH_RELEASE"
        console = [{"text": marker + " " + json.dumps(self.touch_receipt())},
                   {"text": "description of " + marker + " {}"},
                   {"text": marker + " " + json.dumps({**self.touch_receipt(), "gesture_id": 2})}]
        records = observer_receipts(console, marker, start=1)
        self.assertEqual([record["gesture_id"] for record in records], [2])
        for suffix in ("invalid", "[]"):
            with self.assertRaises(ValueError):
                observer_receipts([{"text": marker + " " + suffix}], marker)


if __name__ == "__main__":
    unittest.main()
