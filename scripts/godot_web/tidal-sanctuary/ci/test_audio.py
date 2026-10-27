"""Fail-closed audio acceptance fixtures; never launches a browser/renderer."""
import array
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import tempfile
from test_audio_thread import meter_fixture, timed_fixture
from capture_browser import (AUDIO_CUES, BROWSER_ARGS, IGNORED_DEFAULT_ARGS, audio_graph, audio_window, audio_prepared,
                             first_loop_cutoff_ready, real_button, native_save_return_touch, configure_native_viewport, verify_native_viewport, validate_audio_baseline, validate_audio_sources,
                             validate_journey, validate_recorded_pcm, validate_muted_restore_audio,
                             browser_executable, validate_browser_arguments, validate_audio_closed, validate_focus_suspension)


def snapshot(rms=0, state="suspended", seconds=2.5):
    result = {"schema": 1, "errors": [], "wall_ms": seconds * 1000,
            "starts": [], "gestures": [], "marks": [{"name": "baseline", "wall_ms": 0, "context_times": [{"id": 1, "time": 0}]}], "user_activation": {"has_been_active": False},
            "contexts": [{"id": 1, "destination": 1, "state": state, "context_time": seconds if state == "running" else 0,
                          "terminals": [{"active": True, "kind": "GainNode", "source": 2, "key": "2:0:0", "mirror_count": 1, "connected_ms": 0}],
                          "samples": [{"wall_ms": index * 100, "context_time": index / 10 if state == "running" else 0,
                                       "state": state, "rms": rms, "peak": rms * 2, "clipped_fraction": 0, "active_music": 0, "active_cues": []}
                                      for index in range(int(seconds * 10) + 1)]}]}
    context = result["contexts"][0]
    context["sample_rate"] = 8000
    context["audio_thread"] = meter_fixture(seconds if state == "running" else 0, rms)
    timing = timed_fixture(seconds)
    result.update({key:value for key,value in timing.items() if key.startswith("pcm_")})
    return result


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
    value["marks"].append({"name": "after-begin", "wall_ms": 3000, "context_times": [{"id": 1, "time": 3}]})
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
    refresh_route_graph(value)
    return value, receipts, actions


def refresh_route_graph(value):
    from test_audio_source_contract import graph_event, gain_event
    context = value["contexts"][0]
    seconds = context["context_time"]
    value.update(history_overflow=False, graph_events=[], gain_events=[], edges=[])
    value["nodes"] = [{"id":1,"kind":"AudioDestinationNode"},
                      *[{"id":node,"kind":"GainNode"} for node in (2,100,101)],
                      *[{"id":item["id"],"kind":"AudioBufferSourceNode"} for item in value["starts"]]]
    for bus in (100,101):graph_event(value,"connect",bus,2,0)
    graph_event(value,"connect",2,1,0)
    for gain in (2,100,101):gain_event(value,gain,"initial",[],1,0)
    for meter in (context["audio_thread"],):meter.update(ready_context_time=0,ready_wall_ms=0)
    buses=[]
    for bus in (100,101):
        meter=meter_fixture(seconds,.01,source=bus);meter.update(ready_context_time=0,ready_wall_ms=0);buses.append(meter)
    context["audio_thread"]["streams"]=buses
    for item in value["starts"]:
        bus=100 if item["name"]=="music" else 101
        item.update(path_at_start=[item["id"],bus,2,1],nonzero_gain_path_at_start=[item["id"],bus,2,1])
        for key,default in {"detune":0,"mutations":[],"parameter_automation":[],"requested_duration":None}.items():item.setdefault(key,default)
        item["meter_taps"]=[{"tap_id":"mix:1","source":None,"role":"mix"},
                            {"tap_id":"node:"+str(bus),"source":bus,"role":"bus"}]
        graph_event(value,"connect",item["id"],bus,item["scheduled_start"])
        if item.get("planned_end") is not None and item["planned_end"] <= seconds:
            graph_event(value,"disconnect",item["id"],bus,item["planned_end"])


def silence_pcm_window(item):
    for key in ("square_sum", "rms", "peak", "clipped_samples", "clipped_fraction"):item[key]=0
    for key in ("channel_square_sum", "channel_rms", "channel_peak", "channel_clipped_samples"):
        item[key]=[0]*item["channels"]


class AudioAcceptanceFixtures(unittest.TestCase):
    def test_preparation_error_preserves_actual_reason_instead_of_opaque_timeout(self):
        self.assertFalse(audio_prepared({"audio_ready": False, "audio_status": "loading"}))
        self.assertTrue(audio_prepared({"audio_ready": True, "audio_status": "ready"}))
        with self.assertRaisesRegex(RuntimeError, "Audio initialization timed out"):
            audio_prepared({"audio_ready": False, "audio_status": "error", "audio_error": "Audio initialization timed out"})

    def test_owned_context_close_requires_no_live_edges_or_new_sources(self):
        before = snapshot(.01, "running")
        before["starts"] = [{"id": 3}]
        after = copy.deepcopy(before)
        context = after["contexts"][0]
        context["state"] = "closed"
        context["terminals"][0]["active"] = False
        validate_audio_closed(before, after)
        for change in ("open", "edge", "voice", "source", "extra-context", "probe-error"):
            bad = copy.deepcopy(after)
            if change == "open": bad["contexts"][0]["state"] = "running"
            if change == "edge": bad["contexts"][0]["terminals"][0]["active"] = True
            if change == "voice": bad["contexts"][0]["samples"][-1]["active_music"] = 1
            if change == "source": bad["starts"].append({"id": 4})
            if change == "extra-context": bad["contexts"].append({"id": 2, "state": "closed"})
            if change == "probe-error": bad["errors"] = ["unknown graph"]
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_audio_closed(before, bad)

    def test_focus_requires_real_silence_frozen_clock_and_same_voices(self):
        before = snapshot(.01, "running")
        before["starts"] = [{"id": 3}]
        away = snapshot(0, "suspended")
        away["starts"] = [{"id": 3}]
        away["contexts"][0]["context_time"] = 2.5
        for item in away["contexts"][0]["samples"]:
            item.update(context_time=2.5, rms=.02, peak=.04, active_music=1,
                        terminal_gain_values=[{"source": 2, "value": 0}])
        returned = snapshot(.01, "running", 4)
        returned["starts"] = [{"id": 3}]
        validate_focus_suspension(before, away, returned, 0, 2500)
        for change in ("unmuted-terminal", "missing-terminal", "advancing", "running", "sparse", "restart", "replacement", "not-resumed"):
            bad, back = copy.deepcopy(away), copy.deepcopy(returned)
            if change == "unmuted-terminal": bad["contexts"][0]["samples"][5]["terminal_gain_values"][0]["value"] = .1
            if change == "missing-terminal": bad["contexts"][0]["samples"][5]["terminal_gain_values"] = []
            if change == "advancing": bad["contexts"][0]["samples"][5]["context_time"] += .1
            if change == "running": bad["contexts"][0]["samples"][5]["state"] = "running"
            if change == "sparse": bad["contexts"][0]["samples"] = bad["contexts"][0]["samples"][:2]
            if change == "restart": back["starts"].append({"id": 4})
            if change == "replacement": back["contexts"][0]["id"] = 2
            if change == "not-resumed": back["contexts"][0]["state"] = "suspended"
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_focus_suspension(before, bad, back, 0, 2500)

    def test_visible_desktop_sparse_suspension_remains_rejected(self):
        # Actual 00ec229 hosted desktop timestamps. A frozen clock at these
        # sparse endpoints is not a substitute for sustained fresh evidence.
        before = snapshot(.01, "running")
        away = snapshot(0, "suspended")
        returned = snapshot(.01, "running", 540)
        for value in (before, away, returned):
            value["starts"] = [{"id": 3}]
        template = away["contexts"][0]["samples"][0]
        away["contexts"][0]["samples"] = [dict(template, wall_ms=wall,
            context_time=536.5202721088435, active_music=1,
            terminal_gain_values=[{"source": 2, "value": 0}])
            for wall in (605184., 608555., 611872.8, 611873.3, 611927.4, 614406.4)]
        with self.assertRaisesRegex(ValueError, "sustained fresh wall-time"):
            validate_focus_suspension(before, away, returned, 608555.7, 611873.2)
        # Even retaining every sparse endpoint cannot waive the maximum gap.
        with self.assertRaisesRegex(ValueError, "sustained fresh wall-time"):
            validate_focus_suspension(before, away, returned, 605000, 615000)

    def test_headed_lane_and_failure_focus_snapshots_are_explicit(self):
        source = Path(__file__).with_name("capture_browser.py").read_text()
        self.assertIn('parser.add_argument("--headed", action="store_true"', source)
        self.assertIn('launch_options = {"headless": not args.headed', source)
        self.assertEqual(source.count('require_hidden=hidden_required'), 3)
        self.assertIn('hidden_required = args.headed or args.standard_headless', source)
        self.assertIn('profile=profile, timeout=15, headed=args.headed)', source)
        self.assertIn('args.standard_headless and (args.headed or not args.no_defaults)', source)
        evidence = source.index('write_json(out / (label + "-audio-focus.json")')
        validation = source.index('result["audio"]["focus"] = validate_focus_suspension')
        self.assertLess(evidence, validation)

    def test_native_loop_cannot_change_bounds_pitch_or_automation(self):
        value, receipts, actions = route_audio()
        value["starts"] = [item for item in value["starts"] if item["name"] != "music" or item["id"] == 3]
        source = value["starts"][0]
        source.update(looping=True, planned_end=None, detune=0, loop_start=0, loop_end=32,
                      requested_duration=None, mutations=[], parameter_automation=[])
        refresh_route_graph(value)
        validate_audio_sources(value, receipts, actions)
        for change in ({"loop_start": 1}, {"loop_end": 31}, {"detune": 1}, {"requested_duration": 32},
                       {"mutations": [{}]}, {"parameter_automation": [{}]}):
            bad = copy.deepcopy(value);bad["starts"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_audio_sources(bad, receipts, actions)

    def test_rejected_window_preserves_its_exact_observation_before_diagnostics(self):
        value = snapshot(.02, "running")
        value["contexts"][0]["audio_thread"]["windows"] = value["contexts"][0]["audio_thread"]["windows"][:2]
        original = copy.deepcopy(value)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rejected-window.json"
            with self.assertRaisesRegex(ValueError, "sustained contiguous real PCM"):
                audio_window(value, 0, 2500, 1.2, audible=True, evidence_path=path)
            self.assertEqual(json.loads(path.read_text()), {"begin_ms": 0, "end_ms": 2500,
                "minimum_seconds": 1.2, "audible": True, "snapshot": original})
        self.assertEqual(value, original)

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
        self.assertEqual(BROWSER_ARGS, ["--disable-dev-shm-usage", "--enable-automation"])
        self.assertFalse(any("autoplay" in item or "audio" in item for item in BROWSER_ARGS))
        validate_browser_arguments(["chrome", *BROWSER_ARGS])
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
        stalled["contexts"][0]["context_time"] = 0
        with self.assertRaises(ValueError): audio_window(stalled, 0, 2500, 2, audible=True)

    def test_quiet_window_rejects_mute_that_does_not_mute(self):
        audio_window(snapshot(0, "running"), 0, 2500, 1)
        with self.assertRaises(ValueError): audio_window(snapshot(.001, "running"), 0, 2500, 1)

    def test_missing_meter_span_stale_gaps_and_invalid_rms_fail(self):
        for change in ("missing", "gap", "nan", "duplicate-voice", "clip"):
            value = snapshot(.01, "running")
            samples = value["contexts"][0]["samples"]
            if change == "missing": value["contexts"][0]["audio_thread"]["windows"].clear()
            if change == "gap": del value["contexts"][0]["audio_thread"]["windows"][4:20]
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
        value["starts"][0].update({"looping": True, "planned_end": None, "detune": 0, "loop_start": 0, "loop_end": 32, "requested_duration": None, "mutations": [], "parameter_automation": []})
        refresh_route_graph(value)
        result = validate_audio_sources(value, receipts, actions)
        self.assertEqual(result["first_loop_boundary"]["continuing_source_id"], 3)
        value["starts"][0]["stopped_context_time"] = 32.3
        with self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)

    def test_loop_boundary_silent_gapped_sparse_or_muted_evidence_fails(self):
        for change in ("silent", "gap", "sparse", "early-stop", "muted"):
            value, receipts, actions = route_audio()
            samples = value["contexts"][0]["audio_thread"]["streams"][0]["windows"]
            if change == "silent":
                for item in samples:
                    if 32 <= item["start_frame"] / 8000 <= 32.4: silence_pcm_window(item)
            if change == "gap": samples[:] = [item for item in samples if not 32 <= item["start_frame"] / 8000 <= 32.5]
            if change == "sparse": samples[:] = samples[::4]
            if change == "early-stop": value["starts"][0]["stopped_context_time"] = 10
            if change == "muted": receipts.append({"schema": 1, "event": "mute", "muted": True})
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)

    def test_first_seam_is_proved_before_late_mute_cycle_without_using_later_seam(self):
        value, receipts, actions = route_audio()
        # Slow actual input can put unmute after the first seam. The first seam
        # is independently required to be genuinely audible before any mute.
        next(item for item in value["marks"] if item["name"] == "unmuted")["context_times"][0]["time"] = 45
        result = validate_audio_sources(value, receipts, actions)
        self.assertEqual(result["first_loop_boundary"]["boundary_context_time"], 32.2)
        from test_audio_source_contract import gain_event
        gain_event(value, 2, "setValueAtTime", [0, 30], 0, 30)
        gain_event(value, 2, "setValueAtTime", [1, 45], 1, 45)
        with self.assertRaises(ValueError):
            validate_audio_sources(value, receipts, actions)

    def test_first_seam_missing_late_or_nonfinite_begin_mark_cannot_pass(self):
        for clock in (None, float("nan"), True, -1, 32):
            value, receipts, actions = route_audio()
            mark = next(item for item in value["marks"] if item["name"] == "after-begin")
            mark["context_times"][0]["time"] = clock
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                validate_audio_sources(value, receipts, actions)

    def test_first_loop_wait_uses_frozen_cutoff_not_late_delivery_clock(self):
        value = snapshot(.01,"running",36.591746031746034)
        music = [{"scheduled_start":2.4700226757369617}]
        value["pcm_cutoff"]={"context_times":[{"id":1,"time":31.71265306122449}]}
        self.assertFalse(first_loop_cutoff_ready(value,music))
        value["pcm_cutoff"]["context_times"][0]["time"]=35.8
        self.assertTrue(first_loop_cutoff_ready(value,music))
        for clock in (None, True, float("nan"), -1, 40):
            value["pcm_cutoff"]["context_times"][0]["time"]=clock
            with self.subTest(clock=clock),self.assertRaises(ValueError):
                first_loop_cutoff_ready(value,music)
        source=Path(__file__).with_name("capture_browser.py").read_text()
        self.assertIn('first_loop_deadline = time.monotonic() + 45',source)
        self.assertIn('if first_loop_cutoff_ready(first_loop_audio, first_music):',source)

    def test_harness_checks_original_seam_before_first_mute_input(self):
        source = Path(__file__).with_name("capture_browser.py").read_text()
        before_mute = source.index('result["audio"]["first_loop_before_mute"]')
        mute = source.index('mute_input = real_button(page, mute_state')
        self.assertLess(before_mute, mute)
        self.assertIn('label + "-audio-first-loop.json"', source[:before_mute])

    def test_cue_near_end_offset_early_stop_and_missing_pcm_lifetime_fail(self):
        for change in ("offset", "stop", "ended", "planned-short", "silent-bus", "muted-middle", "sparse", "missing-end", "nan-rms", "negative-peak", "nan-frame"):
            value, receipts, actions = route_audio()
            cue = next(item for item in value["starts"] if item["name"] == "chart_read")
            samples = value["contexts"][0]["audio_thread"]["streams"][1]["windows"]
            if change == "offset": cue["offset"] = cue["duration"] - .001
            if change == "stop": cue["stopped_context_time"] = cue["scheduled_start"] + .001
            if change == "ended": cue["ended_context_time"] = cue["scheduled_start"] + .001
            if change == "planned-short": cue["planned_end"] = cue["scheduled_start"] + .1
            if change == "silent-bus":
                for item in samples:silence_pcm_window(item)
            if change == "muted-middle":
                for item in samples:
                    if abs(item["start_frame"] / 8000 - 10.3) < .01:silence_pcm_window(item)
            if change == "sparse": samples[:] = [item for item in samples if not 10.2 <= item["start_frame"] / 8000 <= 10.5]
            if change == "missing-end": samples[:] = [item for item in samples if not 10.4 <= item["start_frame"] / 8000 <= 10.8]
            if change == "nan-rms": samples[101]["rms"] = float("nan")
            if change == "negative-peak": samples[101]["peak"] = -.1
            if change == "nan-frame": samples[101]["start_frame"] = float("nan")
            with self.subTest(change=change), self.assertRaises(ValueError): validate_audio_sources(value, receipts, actions)

    def test_native_seam_uses_real_effective_buffer_end_without_padding(self):
        value, receipts, actions = route_audio()
        value["starts"] = [item for item in value["starts"] if item["name"] != "music" or item["id"] == 3]
        music=value["starts"][0]
        music.update(looping=True,planned_end=None,detune=0,loop_start=0,loop_end=32,
                     duration=1411199/44100,requested_duration=None,mutations=[],parameter_automation=[])
        refresh_route_graph(value)
        result=validate_audio_sources(value,receipts,actions)
        self.assertEqual(result["first_loop_boundary"]["boundary_context_time"],.2+1411199/44100)

    def test_audio_thread_proof_does_not_backfill_sparse_main_thread_metadata(self):
        value, receipts, actions = route_audio()
        context=value["contexts"][0];context["samples"]=[context["samples"][0],context["samples"][-1]]
        result=validate_audio_sources(value,receipts,actions)
        self.assertEqual(len(result["cue_pairs"]),4)
        self.assertEqual(len(context["samples"]),2)

    def test_actual_input_uses_mouse_or_touch_only_at_observed_rect(self):
        page = Mock()
        real_button(page, {"begin_rect": [20, 30, 100, 40]}, "begin_rect", False, 400, 800)
        page.mouse.click.assert_called_once_with(70, 50)
        real_button(page, {"begin_rect": [20, 30, 100, 40]}, "begin_rect", True, 400, 800)
        page.touchscreen.tap.assert_called_once_with(70, 50)
        page.evaluate.assert_not_called()
        with self.assertRaises(ValueError): real_button(page, {"begin_rect": [-1, 0, 20, 20]}, "begin_rect", True, 400, 800)

    def test_no_defaults_buttons_use_real_native_touch_protocol(self):
        page = Mock()
        with patch("capture_browser.bounded_cdp") as call, patch("capture_browser.detach_cdp") as detach:
            receipt = real_button(page, {"begin_rect": [20,30,100,40]}, "begin_rect", True, 400,800,native_touch=True)
        self.assertEqual(receipt["kind"], "CDP native touch")
        self.assertEqual([x.args[1] for x in call.call_args_list], ["Input.dispatchTouchEvent"]*2)
        self.assertEqual(call.call_args_list[0].args[2], {"type":"touchStart","touchPoints":[{"id":0,"x":70,"y":50}]})
        self.assertEqual(call.call_args_list[1].args[2], {"type":"touchEnd","touchPoints":[]})
        page.touchscreen.tap.assert_not_called()
        page.evaluate.assert_not_called()
        detach.assert_called_once()

    def test_save_return_uses_observed_shipped_control_and_native_touch(self):
        page = Mock()
        with patch("capture_browser.passive_evaluate", return_value=[20,30,100,40]) as observe, \
                patch("capture_browser.bounded_cdp") as call, patch("capture_browser.detach_cdp"):
            receipt = native_save_return_touch(page,390,844)
        self.assertEqual(receipt["kind"], "CDP native touch")
        self.assertEqual(receipt["field"], "save_return_rect")
        self.assertEqual(call.call_args_list[0].args[2], {"type":"touchStart","touchPoints":[{"id":0,"x":70,"y":50}]})
        self.assertEqual(call.call_args_list[1].args[2], {"type":"touchEnd","touchPoints":[]})
        script = observe.call_args.args[1]
        self.assertIn("querySelectorAll('#tidal-save-return')",script)
        self.assertIn("document.elementFromPoint",script)
        self.assertNotIn(".click(",script)
        self.assertNotIn("dispatchEvent",script)
        page.locator.assert_not_called()
        page.touchscreen.tap.assert_not_called()
        source=Path(__file__).with_name("capture_browser.py").read_text()
        self.assertIn("if mobile and args.no_defaults:\n                        exit_input = native_save_return_touch(page, width, height)",source)

    def test_save_return_missing_obscured_or_invalid_rect_never_sends_input(self):
        for rect in (None, [], [0,0,0,40], [-1,0,20,20], [380,0,20,20]):
            with self.subTest(rect=rect), patch("capture_browser.passive_evaluate",return_value=rect), \
                    patch("capture_browser.bounded_cdp") as call, self.assertRaises(ValueError):
                native_save_return_touch(Mock(),390,844)
            call.assert_not_called()

    def test_native_viewport_keeps_exact_dimensions_dpr_and_touch(self):
        for width,height,mobile in ((1280,720,False),(390,844,True)):
            page = Mock()
            with patch("capture_browser.bounded_cdp") as call:
                configure_native_viewport(page,width,height,mobile)
            metrics = call.call_args_list[0].args[2]
            self.assertEqual((metrics["width"],metrics["height"],metrics["deviceScaleFactor"],metrics["mobile"]), (width,height,1,mobile))
            good={"width":width,"height":height,"dpr":1,"touch_points":5 if mobile else 0}
            with patch("capture_browser.passive_evaluate",return_value=good):
                self.assertEqual(verify_native_viewport(page,width,height,mobile),good)
            for key in good:
                with self.subTest(mobile=mobile,key=key), patch("capture_browser.passive_evaluate",return_value={**good,key:-1}), self.assertRaises(ValueError):
                    verify_native_viewport(page,width,height,mobile)

    def test_recorded_bytes_must_have_mute_and_nonzero_signal(self):
        valid = array.array("f", [0] * 100 + [.01] * 3300)
        result = validate_recorded_pcm(valid, 100)
        self.assertEqual(result["longest_quiet_seconds"], 1)
        self.assertEqual(result["nonzero_seconds"], 33)
        for value in (array.array("f", [0] * 4000), array.array("f", [.01] * 4000), array.array("f", [0] * 100 + [.01] * 3100)):
            with self.assertRaises(ValueError): validate_recorded_pcm(value, 100)


if __name__ == "__main__":
    unittest.main()
