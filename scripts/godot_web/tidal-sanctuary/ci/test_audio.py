"""Fail-closed audio acceptance fixtures; never launches a browser/renderer."""
import array
import copy
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import tempfile
from capture_browser import (AUDIO_CUES, BROWSER_ARGS, IGNORED_DEFAULT_ARGS, audio_graph, audio_window,
                             real_button, validate_audio_baseline, validate_audio_sources,
                             validate_journey, validate_recorded_pcm, validate_muted_restore_audio,
                             browser_executable, validate_browser_arguments)


def snapshot(rms=0, state="suspended", seconds=2.5):
    return {"schema": 1, "errors": [], "wall_ms": seconds * 1000,
            "starts": [], "gestures": [], "marks": [{"name": "baseline", "wall_ms": 0, "context_times": [{"id": 1, "time": 0}]}], "user_activation": {"has_been_active": False},
            "contexts": [{"id": 1, "destination": 1, "state": state, "context_time": seconds if state == "running" else 0,
                          "terminals": [{"active": True, "kind": "GainNode", "key": "2:0:0", "mirror_count": 1, "connected_ms": 0}],
                          "samples": [{"wall_ms": index * 100, "context_time": index / 10 if state == "running" else 0,
                                       "state": state, "rms": rms, "peak": rms * 2, "clipped_fraction": 0, "active_music": 0, "active_cues": []}
                                      for index in range(int(seconds * 10) + 1)]}]}


def route_audio():
    value = snapshot(.01, "running", 70)
    value["gestures"] = [{"trusted": True, "wall_ms": 100}]
    value["user_activation"]["has_been_active"] = True
    def source(name, duration, at, wall, fingerprint, identifier):
        return {"id": identifier, "context": 1, "name": name, "duration": duration, "wall_ms": wall,
                "context_time": at, "scheduled_start": at, "planned_end": at + duration, "offset": 0, "rate": 1, "looping": False,
                "pcm_peak": .1, "pcm_fingerprint": fingerprint, "path_at_start": [identifier, 2, 1],
                "nonzero_gain_path_at_start": [identifier, 2, 1]}
    value["starts"] = [source("music", 32, .2, 200, "music", 3), source("music", 32, 32.2, 32200, "music", 4),
                       source("music", 32, 64.2, 64200, "music", 5)]
    receipts = [{"schema": 1, "event": "start", "start_count": 1, "started": True, "muted": False},
                {"schema": 1, "event": "mute", "muted": True}, {"schema": 1, "event": "mute", "muted": False}]
    value["marks"].append({"name": "unmuted", "wall_ms": 6000, "context_times": [{"id": 1, "time": 6}]})
    actions = []
    for stage, (name, duration) in enumerate(AUDIO_CUES):
        wall = (stage + 1) * 10000
        value["marks"].append({"name": "action-" + str(stage), "wall_ms": wall - 200})
        value["starts"].append(source(name, duration, wall / 1000, wall, name, stage + 10))
        receipts.append({"schema": 1, "event": "cue", "name": name, "duration": duration, "stage": stage,
                         "count": 1, "started": True, "muted": False})
        actions.append({"from_stage": stage, "target_stage": stage + 1, "accepted_sample_id": stage + 100})
    value["starts"].sort(key=lambda item: item["wall_ms"])
    for sample in value["contexts"][0]["samples"]:
        sample["active_music"] = 1 if sample["context_time"] >= .2 else 0
        sample["active_cues"] = [item["id"] for item in value["starts"] if item["name"] != "music"
            and item["scheduled_start"] <= sample["context_time"] < item["planned_end"]]
    return value, receipts, actions


class AudioAcceptanceFixtures(unittest.TestCase):
    def test_bus_growth_and_observers_do_not_reintroduce_known_failures(self):
        audio = Path(__file__).parent.parent / "game/tide_audio.gd"
        source = audio.read_text()
        self.assertIn("AudioServer.bus_count = bus_index + 1", source)
        self.assertNotIn("AudioServer.add_bus(", source)
        source = Path(__file__).with_name("capture_browser.py").read_text()
        self.assertNotIn("page.evaluate(", source)
        self.assertNotIn("page.screenshot(", source)
        self.assertNotIn("canvas.bounding_box(", source)
        self.assertIn('result["audio"]["before_begin"] = validate_audio_baseline', source)
        self.assertIn('result["audio"]["restored_before_begin"] = validate_audio_baseline', source)

    def test_restored_muted_begin_unmutes_without_restart_or_cues(self):
        source = {"id": 1, "name": "music", "scheduled_start": 2., "rate": 1, "offset": 0}
        before = {"starts": [source]}
        after = {"starts": [source, {**source, "id": 2, "scheduled_start": 34.}]}
        receipts = [{"event": "start", "start_count": 1, "started": True, "muted": True}]
        validate_muted_restore_audio(before, before, receipts)
        validate_muted_restore_audio(before, after, receipts)
        for bad in ([], receipts * 2, [{**receipts[0], "muted": False}],
                    [{**receipts[0], "start_count": True}], receipts + [{"event": "cue"}]):
            with self.subTest(receipts=bad), self.assertRaises(ValueError):
                validate_muted_restore_audio(before, after, bad)
        for change in ({"scheduled_start": 5.}, {"scheduled_start": float("nan")},
                       {"name": "chart_read"}, {"rate": 2}, {"offset": 1}):
            bad = {"starts": [source, {**after["starts"][1], **change}]}
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_muted_restore_audio(before, bad, receipts)
        with self.assertRaises(ValueError):
            validate_muted_restore_audio(before, {"starts": [{**source, "id": 3}]}, receipts)

    def test_safe_browser_defaults_and_real_audio_are_required(self):
        self.assertEqual(IGNORED_DEFAULT_ARGS, ["--mute-audio", "--enable-unsafe-swiftshader"])
        self.assertEqual(BROWSER_ARGS, ["--disable-dev-shm-usage"])
        self.assertFalse(any("autoplay" in item or "audio" in item for item in BROWSER_ARGS))
        validate_browser_arguments(["chrome", "--enable-automation", *BROWSER_ARGS])
        for option in ("--mute-audio", "--no-sandbox", "--disable-setuid-sandbox", "--disable-web-security",
                       "--enable-unsafe-swiftshader", "--ignore-certificate-errors", "--autoplay-policy=no-user-gesture-required"):
            with self.subTest(option=option), self.assertRaises(RuntimeError):
                validate_browser_arguments(["chrome", option])
        source = Path(__file__).with_name("capture_browser.py").read_text()
        self.assertIn('"chromium_sandbox": True', source)
        self.assertIn('verify_passive_protocol(pw, out, launch_options)', source)

    def test_explicit_browser_is_verified_without_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "chrome"
            with self.assertRaises(FileNotFoundError):
                browser_executable(path)
            path.write_text("fixture")
            with self.assertRaises(ValueError):
                browser_executable(path)
            path.chmod(0o700)
            with patch("capture_browser.subprocess.run", return_value=Mock(stdout="Google Chrome 155.0.8059.39\n")):
                self.assertEqual(browser_executable(path), {"executable_path": str(path), "executable_version": "Google Chrome 155.0.8059.39"})
            with patch("capture_browser.subprocess.run", return_value=Mock(stdout="unknown browser\n")):
                with self.assertRaises(ValueError):
                    browser_executable(path)

    def test_real_begin_receipt_requires_exact_trigger_and_not_demo(self):
        receipt = {"schema": 1, "started": True, "trigger": "touch_begin", "demo": False}
        validate_journey(receipt, "touch_begin")
        for mutation in ({"trigger": "fixture"}, {"demo": True}, {"started": False}, {"schema": True}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_journey({**receipt, **mutation}, "touch_begin")

    def test_baseline_requires_two_seconds_quiet_and_no_input(self):
        validate_audio_baseline(snapshot(), 0)
        for mutation in ({"gestures": [{"trusted": True}]}, {"starts": [{}]}, {"user_activation": {"has_been_active": True}}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_audio_baseline({**snapshot(), **mutation}, 0)
        with self.assertRaises(ValueError):
            validate_audio_baseline(snapshot(seconds=1.9), 0)
        with self.assertRaises(ValueError):
            validate_audio_baseline(snapshot(.002), 0)

    def test_suspended_baseline_proves_no_audio_despite_sparse_main_thread_timer(self):
        value = snapshot(seconds=8)
        value["contexts"][0]["samples"] = [value["contexts"][0]["samples"][0], value["contexts"][0]["samples"][-1]]
        validate_audio_baseline(value, 0)
        for change in ({"state": "running"}, {"context_time": .001}, {"context_time": False}):
            bad = copy.deepcopy(value);bad["contexts"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_baseline(bad, 0)
        for change in ({"state": "running"}, {"context_time": .001}, {"rms": .00001}, {"peak": .00001}, {"active_music": 1}):
            bad = copy.deepcopy(value);bad["contexts"][0]["samples"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_baseline(bad, 0)
        for change in ({"marks": []}, {"wall_ms": 1999}, {"wall_ms": float("nan")},
                       {"marks": [{"name": "baseline", "wall_ms": 0, "context_times": [{"id": 2, "time": 0}]}]},
                       {"marks": [{"name": "baseline", "wall_ms": 0, "context_times": [{"id": 1, "time": .001}]}]}):
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_baseline({**value, **change}, 0)
        for change in ({"connected_ms": 1}, {"disconnected_ms": 1}):
            bad = copy.deepcopy(value);bad["contexts"][0]["terminals"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_baseline(bad, 0)
        with self.assertRaises(ValueError): audio_window(value, 0, 8000, 2, audible=True)

    def test_missing_unknown_and_duplicate_taps_fail(self):
        for mutation in ({"contexts": []}, {"errors": ["unknown node"]}, {"schema": True}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audio_graph({**snapshot(), **mutation})
        for change in ("duplicate", "not-gain", "double-mirror", "inactive"):
            value = snapshot()
            terminals = value["contexts"][0]["terminals"]
            if change == "duplicate": terminals.append(copy.deepcopy(terminals[0]))
            if change == "not-gain": terminals[0]["kind"] = "Unknown"
            if change == "double-mirror": terminals[0]["mirror_count"] = 2
            if change == "inactive": terminals[0]["active"] = False
            with self.subTest(change=change), self.assertRaises(ValueError): audio_graph(value)

    def test_running_must_really_be_nonzero_and_advance(self):
        audio_window(snapshot(.01, "running"), 0, 2500, 2, audible=True)
        for value in (snapshot(0, "running"), snapshot(.01, "suspended")):
            with self.assertRaises(ValueError): audio_window(value, 0, 2500, 2, audible=True)
        stalled = snapshot(.01, "running")
        for item in stalled["contexts"][0]["samples"]: item["context_time"] = 0
        with self.assertRaises(ValueError): audio_window(stalled, 0, 2500, 2, audible=True)

    def test_quiet_window_rejects_mute_that_does_not_mute(self):
        audio_window(snapshot(), 0, 2500, 1)
        with self.assertRaises(ValueError): audio_window(snapshot(.001, "running"), 0, 2500, 1)

    def test_missing_meter_span_stale_gaps_and_invalid_rms_fail(self):
        for change in ("missing", "gap", "nan", "duplicate-voice", "clip"):
            value = snapshot(.01, "running")
            samples = value["contexts"][0]["samples"]
            if change == "missing": samples.clear()
            if change == "gap": del samples[4:20]
            if change == "nan": samples[0]["rms"] = float("nan")
            if change == "duplicate-voice": samples[0]["active_music"] = 2
            if change == "clip": samples[0]["clipped_fraction"] = .1
            with self.subTest(change=change), self.assertRaises(ValueError): audio_window(value, 0, 2500, 2, audible=True)

    def test_recreated_loop_and_four_real_source_pairs_pass(self):
        result = validate_audio_sources(*route_audio())
        self.assertEqual(result["music_source_count"], 3)
        self.assertEqual([item["name"] for item in result["cue_pairs"]], [name for name, duration in AUDIO_CUES])

    def test_no_gesture_silent_pcm_missing_graph_and_zero_gain_path_fail(self):
        for change in ("gesture", "silent", "path", "gain", "before-gesture"):
            value, receipts, actions = route_audio()
            if change == "gesture": value["gestures"] = []
            if change == "silent": value["starts"][0]["pcm_peak"] = 0
            if change == "path": value["starts"][0]["path_at_start"] = None
            if change == "gain": value["starts"][0]["nonzero_gain_path_at_start"] = None
            if change == "before-gesture": value["starts"][0]["wall_ms"] = 50
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)

    def test_duplicate_cue_and_overlapping_music_fail(self):
        for change in ("extra-cue", "overlap", "active-overlap", "fingerprint", "unknown"):
            value, receipts, actions = route_audio()
            if change == "extra-cue": value["starts"].append(copy.deepcopy(value["starts"][1]))
            if change == "overlap": value["starts"].append({**value["starts"][0], "scheduled_start": 1, "wall_ms": 1000})
            if change == "active-overlap": value["contexts"][0]["samples"][0]["active_music"] = 2
            if change == "fingerprint": next(item for item in value["starts"] if item["name"] == "music" and item["id"] == 4)["pcm_fingerprint"] = "changed"
            if change == "unknown": value["errors"].append("Unknown source duration")
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)

    def test_receipts_cannot_replace_source_and_physical_action_evidence(self):
        for change in ("receipt-stage", "receipt-count", "receipt-nan", "missing-action", "before-action", "no-accepted-action", "short-loop"):
            value, receipts, actions = route_audio()
            if change == "receipt-stage": receipts[4]["stage"] = True
            if change == "receipt-count": receipts[3]["count"] = 2
            if change == "receipt-nan": receipts[3]["duration"] = float("nan")
            if change == "missing-action": value["marks"].clear()
            if change == "before-action": next(item for item in value["starts"] if item["name"] == "chart_read")["wall_ms"] = 9700
            if change == "no-accepted-action": actions[0].pop("accepted_sample_id")
            if change == "short-loop": value["contexts"][0]["context_time"] = 10
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)


    def test_single_nonlooping_source_with_later_clock_does_not_prove_loop(self):
        value, receipts, actions = route_audio()
        value["starts"] = [item for item in value["starts"] if item["name"] != "music" or item["id"] == 3]
        # Even misleading positive meters and a 70s context clock cannot replace
        # a real continuing voice after the first non-looping 32s source ends.
        with self.assertRaisesRegex(ValueError, "genuinely continue"):
            validate_audio_sources(value, receipts, actions)

    def test_true_native_loop_still_requires_audible_boundary(self):
        value, receipts, actions = route_audio()
        value["starts"] = [item for item in value["starts"] if item["name"] != "music" or item["id"] == 3]
        value["starts"][0].update({"looping": True, "planned_end": None})
        result = validate_audio_sources(value, receipts, actions)
        self.assertEqual(result["first_loop_boundary"]["continuing_source_id"], 3)
        value["starts"][0]["stopped_context_time"] = 32.3
        with self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)

    def test_loop_boundary_silent_gapped_sparse_or_muted_evidence_fails(self):
        for change in ("silent", "gap", "sparse", "early-stop", "muted"):
            value, receipts, actions = route_audio()
            samples = value["contexts"][0]["samples"]
            if change == "silent":
                for item in samples:
                    if 32 <= item["context_time"] <= 32.4: item["rms"] = 0
            if change == "gap": samples[:] = [item for item in samples if not 32 <= item["context_time"] <= 32.5]
            if change == "sparse": samples[:] = samples[::4]
            if change == "early-stop": value["starts"][0]["stopped_context_time"] = 10
            if change == "muted": receipts.append({"schema": 1, "event": "mute", "muted": True})
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)

    def test_cue_near_end_offset_early_stop_and_missing_active_lifetime_fail(self):
        for change in ("offset", "stop", "ended", "planned-short", "missing-active", "muted-middle", "sparse", "missing-end", "nan-rms", "negative-peak", "nan-clock"):
            value, receipts, actions = route_audio()
            cue = next(item for item in value["starts"] if item["name"] == "chart_read")
            samples = value["contexts"][0]["samples"]
            if change == "offset": cue["offset"] = cue["duration"] - .001
            if change == "stop": cue["stopped_context_time"] = cue["scheduled_start"] + .001
            if change == "ended": cue["ended_context_time"] = cue["scheduled_start"] + .001
            if change == "planned-short": cue["planned_end"] = cue["scheduled_start"] + .1
            if change == "missing-active":
                for item in samples: item["active_cues"] = []
            if change == "muted-middle":
                for item in samples:
                    if abs(item["context_time"] - 10.3) < .01: item["active_cues"] = []
            if change == "sparse": samples[:] = [item for item in samples if not 10.2 <= item["context_time"] <= 10.5]
            if change == "missing-end": samples[:] = [item for item in samples if not 10.4 <= item["context_time"] <= 10.8]
            if change == "nan-rms": samples[101]["rms"] = float("nan")
            if change == "negative-peak": samples[101]["peak"] = -.1
            if change == "nan-clock": samples[101]["context_time"] = float("nan")
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)

    def test_actual_input_uses_mouse_or_touch_only_at_observed_rect(self):
        page = Mock()
        real_button(page, {"begin_rect": [20, 30, 100, 40]}, "begin_rect", False, 400, 800)
        page.mouse.click.assert_called_once_with(70, 50)
        real_button(page, {"begin_rect": [20, 30, 100, 40]}, "begin_rect", True, 400, 800)
        page.touchscreen.tap.assert_called_once_with(70, 50)
        page.evaluate.assert_not_called()
        with self.assertRaises(ValueError): real_button(page, {"begin_rect": [-1, 0, 20, 20]}, "begin_rect", True, 400, 800)

    def test_recorded_bytes_must_have_mute_and_nonzero_signal(self):
        valid = array.array("f", [0] * 100 + [.01] * 3300)
        result = validate_recorded_pcm(valid, 100)
        self.assertEqual(result["longest_quiet_seconds"], 1)
        self.assertEqual(result["nonzero_seconds"], 33)
        for value in (array.array("f", [0] * 4000), array.array("f", [.01] * 4000), array.array("f", [0] * 100 + [.01] * 3100)):
            with self.assertRaises(ValueError): validate_recorded_pcm(value, 100)


if __name__ == "__main__":
    unittest.main()
