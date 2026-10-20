"""Fast tests of isolation/failure guards. These do not claim native/browser acceptance."""
import tempfile
import json
import struct
import zlib
import unittest
import signal
from unittest.mock import Mock, patch
from pathlib import Path
from author_native import envelope, script_authoring_plan, script_request_size, SCRIPT_REQUEST_BUDGET
from common import ASSET_NOTICE_FILES, GAME_FILES, RAW_IMAGE_FILES, TROPICAL_FILES, TROPICAL_NOTICES, check_engine_log, copy_game, isolated_env, isolated_output
from capture_native import import_native_resources, collect_composition_studies, stop_input_runtime, wait_for
from observers import CHINESE_LABELS, observer_receipts, validate_language_frame, validate_touch_release
from export_web import copy_asset_notices, raw_include_filter, copy_web_audio, WEB_AUDIO_FILES, prepare_audio_before_game


class BoundedScriptAuthoringTests(unittest.TestCase):
    @staticmethod
    def restore(plan):
        assert plan[0][0] == "create_script"
        source = plan[0][1]["source"]
        for action, arguments in plan[1:]:
            assert action == "edit_script"
            assert arguments["replace_all"] is False
            assert source.count(arguments["search"]) == 1
            source = source.replace(arguments["search"], arguments["replace"], 1)
        return source

    def test_small_source_uses_one_typed_create(self):
        source = "extends Node\nfunc sample() -> void:\n pass\n"
        plan = script_authoring_plan("res://sample.gd", source)
        self.assertEqual(len(plan), 1)
        self.assertEqual(self.restore(plan), source)

    def test_current_main_is_bounded_and_restores_exact_utf8_bytes(self):
        source = (Path(__file__).resolve().parent.parent / "game/main.gd").read_text()
        self.assertGreater(script_request_size("create_script", {"path":"res://main.gd", "source":source, "overwrite":True}), 65535)
        plan = script_authoring_plan("res://main.gd", source)
        self.assertGreater(len(plan), 1)
        for action, arguments in plan:
            self.assertLessEqual(script_request_size(action, arguments), SCRIPT_REQUEST_BUDGET)
        self.assertEqual(self.restore(plan).encode(), source.encode())

    def test_encoded_budget_counts_unicode_quotes_and_backslashes(self):
        source = 'extends Node\n'
        for index in range(12):
            source += f'func sample_{index}() -> void:\n var label = ' + json.dumps('海岛路径\\"' * 200, ensure_ascii=False) + '\n\n'
        self.assertLess(len(source.encode()), SCRIPT_REQUEST_BUDGET)
        plan = script_authoring_plan("res://sample.gd", source)
        self.assertGreater(len(plan), 1)
        for action, arguments in plan:
            self.assertLessEqual(script_request_size(action, arguments), SCRIPT_REQUEST_BUDGET)
        self.assertEqual(self.restore(plan), source)

    def test_oversized_individual_function_fails_before_mutation(self):
        source = 'extends Node\nfunc huge() -> void:\n #' + 'x' * 65536 + '\n'
        with self.assertRaisesRegex(ValueError, "complete void function"):
            script_authoring_plan("res://sample.gd", source)

    def test_no_safe_void_body_fails_before_mutation(self):
        source = 'extends Node\nconst VALUE = "' + 'x' * 65536 + '"\n'
        with self.assertRaisesRegex(ValueError, "cannot be authored"):
            script_authoring_plan("res://sample.gd", source)

    def test_intervening_global_or_annotation_is_not_silently_removed(self):
        for declaration in ('var sentinel: int = 42', '@warning_ignore("unused_variable")', 'static func other() -> void:'):
            source = 'extends Node\nfunc huge() -> void:\n #' + 'x' * 40000 + '\n' + declaration + '\nfunc second() -> void:\n #' + 'y' * 20000 + '\n'
            with self.subTest(declaration=declaration), self.assertRaisesRegex(ValueError, "unsupported top-level"):
                script_authoring_plan("res://sample.gd", source)

    def test_multiline_string_is_refused_in_staged_subset(self):
        source = 'extends Node\nfunc huge() -> void:\n var text = """' + 'x' * 40000 + '"""\nfunc second() -> void:\n #' + 'y' * 20000 + '\n'
        with self.assertRaisesRegex(ValueError, "multiline syntax"):
            script_authoring_plan("res://sample.gd", source)

    def test_invalid_paths_and_empty_sources_fail_closed(self):
        for path in ('main.gd', 'res://../main.gd', 'res://main.txt', None):
            with self.subTest(path=path), self.assertRaises(ValueError):
                script_authoring_plan(path, "extends Node")
        for source in ('', ' \n', None):
            with self.subTest(source=source), self.assertRaises(ValueError):
                script_authoring_plan("res://main.gd", source)


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

    def test_explicit_three_dimensional_physics_backends(self):
        project = (Path(__file__).resolve().parent.parent / "game/project.godot").read_text()
        self.assertIn('3d/physics_engine="Jolt Physics"', project)
        self.assertIn('2d/physics_engine="Dummy"', project)

    def test_runtime_errors_fail(self):
        for message in ("SCRIPT ERROR: Invalid call", "ERROR: Cannot load font", "ERROR: Pages in use exist at exit in PagedAllocator: N16WorkerThreadPool5GroupE", "ERROR: Required extension VK_KHR_surface not found.", "Parse Error: Unexpected token", "Shader compilation failed"):
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

    def test_input_regression_is_copied_and_run(self):
        self.assertIn("verify_input.gd", GAME_FILES)
        runner = Path(__file__).with_name("capture_native.py").read_text()
        self.assertIn('("verify_input.gd", "TIDAL_INPUT_CHECK")', runner)
        self.assertIn('"verify_input.gd.log"', runner)

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
                "labels": {**CHINESE_LABELS, "prompt": "靠近后即可互动"}, "missing_codepoints": []}

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
        self.assertEqual(labels["prompt"], "靠近后即可互动")

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

    def test_fresh_spawn_language_rejects_empty_or_reachable_prompt(self):
        for prompt in ("", "E · 阅读海图", "Move closer to interact", None):
            receipt = self.language_receipt()
            receipt["labels"]["prompt"] = prompt
            with self.subTest(prompt=prompt), self.assertRaisesRegex(ValueError, "prompt"):
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

    def write_study_fixture(self, directory, name, width=1280, height=720):
        # Unit fixture only, never production visual evidence.
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        data += chunk(b"IDAT", zlib.compress((b"\0" + bytes(width * 3)) * height)) + chunk(b"IEND", b"")
        (directory / name).write_bytes(data)

    def study_log(self):
        return "TIDAL_CAPTURE /temporary/tidal-05.png 0\n" + "\n".join(
            "TIDAL_HERO_CAPTURE " + json.dumps({"file": name, "error": 0, "kind": "fixed-camera-study"})
            for name in ("hero-composition.png", "hero-wide.png"))

    def test_composition_studies_stay_separate_with_actual_save_receipts(self):
        with tempfile.TemporaryDirectory() as root:
            frames = Path(root)
            for name in ("hero-composition.png", "hero-wide.png"):
                self.write_study_fixture(frames, name)
            records = collect_composition_studies(frames, self.study_log())
            self.assertEqual([item["name"] for item in records], ["hero-composition.png", "hero-wide.png"])
            self.assertTrue(all(item["kind"] == "fixed-camera-study" for item in records))
            self.assertTrue(all(len(item["sha256"]) == 64 for item in records))

    def test_composition_studies_require_fifth_frame_and_both_successful_receipts(self):
        with tempfile.TemporaryDirectory() as root:
            frames = Path(root)
            for name in ("hero-composition.png", "hero-wide.png"):
                self.write_study_fixture(frames, name)
            log = self.study_log()
            cases = [log.replace("tidal-05.png 0", "tidal-05.png 1"),
                     log.replace('"error": 0', '"error": 1'),
                     log.replace('"error": 0', '"error": false'),
                     log.replace('"fixed-camera-study"', '"physical-input"'),
                     "\n".join(log.splitlines()[:-1]),
                     "\n".join(log.splitlines()[1:] + log.splitlines()[:1]),
                     log + "\n" + log.splitlines()[-1]]
            for bad_log in cases:
                with self.subTest(log=bad_log), self.assertRaises(RuntimeError):
                    collect_composition_studies(frames, bad_log)

    def test_composition_studies_reject_missing_corrupt_or_wrong_size_png(self):
        with tempfile.TemporaryDirectory() as root:
            frames = Path(root)
            self.write_study_fixture(frames, "hero-composition.png")
            with self.assertRaisesRegex(RuntimeError, "missing"):
                collect_composition_studies(frames, self.study_log())
            (frames / "hero-wide.png").write_bytes(b"not a png")
            with self.assertRaisesRegex(RuntimeError, "not a PNG"):
                collect_composition_studies(frames, self.study_log())
            self.write_study_fixture(frames, "hero-wide.png", width=640, height=360)
            with self.assertRaisesRegex(RuntimeError, "viewport"):
                collect_composition_studies(frames, self.study_log())

    def test_polyhaven_manifest_and_exact_raw_export_paths(self):
        expected_buffers = {
            "assets/polyhaven/fern-albedo.png.bin", "assets/polyhaven/fern-normal.jpg.bin",
            "assets/polyhaven/stone-diff.jpg.bin", "assets/polyhaven/stone-normal.png.bin",
            "assets/polyhaven/stone-rough.jpg.bin",
        }
        self.assertEqual(set(RAW_IMAGE_FILES), expected_buffers)
        self.assertEqual(set(raw_include_filter().split(",")), {"*.otf", "assets/story/story.en-zh.json", *expected_buffers})
        self.assertNotIn("*.bin", raw_include_filter())
        expected = expected_buffers | {f"assets/polyhaven/fern-{index}.res" for index in range(4)}
        expected |= {"assets/POLYHAVEN-LICENSE.txt", "assets/POLYHAVEN-SOURCE.json"}
        self.assertTrue(expected.issubset(GAME_FILES))
        self.assertEqual(len(GAME_FILES), len(set(GAME_FILES)))

    def test_fresh_native_import_is_bounded_and_checks_every_scene(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); project = root / "game"; out = root / "out"; out.mkdir()
            for name in TROPICAL_FILES:
                path = project / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"unit fixture, not a real model")
                Path(str(path) + ".import").write_text('importer="scene"\ntype="PackedScene"\n')
            result = Mock(returncode=0, stdout="Import complete", stderr="")
            with patch("capture_native.subprocess.run", return_value=result) as run:
                receipt = import_native_resources("godot", project, out)
            self.assertEqual(run.call_args.args[0], ["godot", "--headless", "--path", str(project), "--editor", "--import", "--quit"])
            self.assertEqual(run.call_args.kwargs["timeout"], 240)
            self.assertEqual(len(receipt["source_imports"]), 8)
            self.assertTrue(receipt["passed"])
            self.assertEqual((out / "native-import.log").read_text(), "Import complete")

    def test_fresh_native_import_refuses_error_nonzero_and_missing_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); out = root / "out"; out.mkdir()
            for result in [Mock(returncode=1, stdout="", stderr=""),
                           Mock(returncode=0, stdout="", stderr="ERROR: import failed"),
                           Mock(returncode=0, stdout="Import complete", stderr="")]:
                with self.subTest(result=result), patch("capture_native.subprocess.run", return_value=result), self.assertRaises(RuntimeError):
                    import_native_resources("godot", root / "game", out)

    def test_tropical_manifest_has_exact_scene_and_notice_paths(self):
        names = {"palm-a", "palm-b", "understory-a", "understory-b", "bush-a",
                 "shore-stone-a", "shore-stone-b", "explorer"}
        self.assertEqual(set(TROPICAL_FILES), {f"assets/tropical/{name}.glb" for name in names})
        self.assertEqual(set(TROPICAL_NOTICES), {"assets/tropical/FOREST-LICENSE.txt",
            "assets/tropical/ADVENTURERS-LICENSE.txt", "assets/tropical/SOURCE.json"})
        self.assertTrue(set(TROPICAL_FILES + TROPICAL_NOTICES).issubset(GAME_FILES))
        self.assertTrue(set(TROPICAL_NOTICES).issubset(ASSET_NOTICE_FILES))

    def test_tropical_glbs_match_source_manifest_and_are_embedded(self):
        import hashlib
        import json
        source = Path(__file__).resolve().parent.parent / "game/assets/tropical"
        records = json.loads((source / "SOURCE.json").read_text())["game_assets"]
        self.assertEqual(set(records), {Path(name).name for name in TROPICAL_FILES})
        for filename, record in records.items():
            with self.subTest(filename=filename):
                raw = (source / filename).read_bytes()
                self.assertEqual(len(raw), record["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), record["sha256"])
                self.assertEqual(struct.unpack_from("<4sII", raw), (b"glTF", 2, len(raw)))
                size, kind = struct.unpack_from("<I4s", raw, 12)
                self.assertEqual(kind, b"JSON")
                content = json.loads(raw[20:20+size])
                self.assertFalse([row for field in ("buffers", "images")
                                  for row in content.get(field, []) if "uri" in row])
                if filename == "explorer.glb":
                    self.assertEqual({clip["name"] for clip in content["animations"]}, {"Idle", "Walk", "Swim"})
                    self.assertEqual(len(content["skins"][0]["joints"]), 23)

    def test_export_copies_original_web_audio_and_public_helper_byte_for_byte(self):
        native = Path(__file__).parent.parent / "game"
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            copy_web_audio(native, site)
            self.assertEqual({p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()},
                             {"web_audio.js", *WEB_AUDIO_FILES})
            for name in ("web_audio.js", *WEB_AUDIO_FILES):
                self.assertEqual((site / name).read_bytes(), (native / name).read_bytes())
        project = (native / "project.godot").read_text()
        self.assertIn('driver/driver.web="Dummy"', project)
        self.assertIn('driver/mix_rate.web=44100', project)
        self.assertNotIn('driver/driver="Dummy"', project)

    def test_official_boot_predecodes_before_engine_start_without_audio_activation(self):
        shell = "(function () {\nengine.startGame({onProgress: report}).then(done, failed);\n}());"
        patched = prepare_audio_before_game(shell)
        self.assertIn("(async function () {", patched)
        self.assertLess(patched.index("await window.TidalWebAudio.initialize("), patched.index("engine.startGame({"))
        self.assertIn("engine.startGame({onProgress: report}).then(done, failed);", patched)
        self.assertNotIn(".resume(", patched)
        self.assertNotIn("TidalWebAudio.start(", patched)
        for name in WEB_AUDIO_FILES:
            self.assertIn(name, patched)
        for changed in (shell.replace("(function () {", "(() => {"), shell + shell,
                        shell.replace("engine.startGame({", "engine.start({")):
            with self.assertRaisesRegex(RuntimeError, "boot scope changed"):
                prepare_audio_before_game(changed)

    def test_export_preserves_all_asset_notices_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as root:
            native, site = Path(root) / "native", Path(root) / "site"
            for name in ASSET_NOTICE_FILES:
                source = native / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(("original source/license: " + name).encode())
            copy_asset_notices(native, site)
            for name in ASSET_NOTICE_FILES:
                self.assertEqual((site / name).read_bytes(), (native / name).read_bytes())
            self.assertEqual(len(list(site.rglob("*.txt"))) + len(list(site.rglob("*.json"))), len(ASSET_NOTICE_FILES))


if __name__ == "__main__":
    unittest.main()
