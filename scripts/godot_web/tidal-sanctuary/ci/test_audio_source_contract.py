"""Deterministic contract negatives, not browser or audible-output acceptance."""
import copy
import math
import unittest

from audio_source_contract import validate_cue_pcm, validate_source_bus


def fixture():
    rate = 8000

    def stream(source, rms):
        windows = []
        for index, start in enumerate(range(78400, 88000, 800), 1):
            windows.append({"sequence": index, "start_frame": start, "end_frame": start + 800,
                            "frames": 800, "channels": 1, "samples": 800, "complete": True,
                            "channel_samples": [800], "channel_square_sum": [rms * rms * 800],
                            "channel_rms": [rms], "channel_peak": [rms * 2], "channel_clipped_samples": [0],
                            "square_sum": rms * rms * 800, "rms": rms, "peak": rms * 2,
                            "clipped_samples": 0, "clipped_fraction": 0})
        return {"schema": 1, "tap_id": "mix:1" if source is None else "node:" + str(source),
                "source": source, "role": "mix" if source is None else "bus", "status": "ready",
                "overflow": False, "errors": [], "sample_rate": rate, "window_frames": 800,
                "ready_context_time": 0, "ready_wall_ms": 0, "windows": windows, "gaps": []}

    context = {"id": 1, "destination": 1, "sample_rate": rate, "state": "running", "context_time": 14,
               "audio_thread": stream(None, .04)}
    context["audio_thread"]["streams"] = [stream(3, .03), stream(4, .01)]
    cue = {"id": 6, "context": 1, "name": "chart_read", "duration": .72,
           "context_time": 10, "wall_ms": 10000, "scheduled_start": 10, "planned_end": 10.72,
           "offset": 0, "rate": 1, "detune": 0, "looping": False, "mutations": [], "parameter_automation": [],
           "path_at_start": [6, 4, 2, 1], "meter_taps": [
               {"tap_id": "mix:1", "source": None, "role": "mix"},
               {"tap_id": "node:4", "source": 4, "role": "bus"}]}
    music = {"id": 5, "context": 1, "name": "music", "scheduled_start": 1,
             "path_at_start": [5, 3, 2, 1], "planned_end": None}
    snapshot = {"schema": 1, "errors": [], "history_overflow": False, "wall_ms": 14000,
                "contexts": [context], "starts": [music, cue],
                "nodes": [{"id": i, "kind": kind} for i, kind in enumerate(
                    ["AudioDestinationNode", "GainNode", "GainNode", "GainNode",
                     "AudioBufferSourceNode", "AudioBufferSourceNode"], 1)],
                "edges": [], "graph_events": [], "gain_events": []}
    for left, right, at in ((3, 2, 0), (4, 2, 0), (2, 1, 0), (5, 3, 1), (6, 4, 10)):
        graph_event(snapshot, "connect", left, right, at)
    for node in (2, 3, 4):
        gain_event(snapshot, node, "initial", [], 1, 0)
    gain_event(snapshot, 4, "setValueAtTime", [math.pow(10, -3 / 20), 0], 1, 0)
    gain_event(snapshot, 2, "value", [1], 1, 0)
    # Unrelated music automation must not be used as cue-bus evidence or cause
    # a false rejection of this separately observed static cue path.
    gain_event(snapshot, 3, "exponentialRampToValueAtTime", [.56, 2.5], .01, 1)
    gain_event(snapshot, 2, "value", [0], 0, 2)
    gain_event(snapshot, 2, "value", [1], 1, 3)
    return snapshot, cue, context


def graph_event(snapshot, event, left, right, at):
    record = {"event": event, "from": left, "to": right, "output": 0, "input": 0,
              "context": 1, "context_time": at, "wall_ms": at * 1000}
    snapshot["graph_events"].append(record)
    snapshot["graph_events"].sort(key=lambda item: item["context_time"])
    for index, item in enumerate(snapshot["graph_events"], 1):
        item["sequence"] = index
    if event == "connect":
        snapshot["edges"].append({"from": left, "to": right, "output": 0, "input": 0, "active": True})
    elif event == "disconnect":
        for item in snapshot["edges"]:
            if item["from"] == left and item["to"] == right:
                item["active"] = False


def gain_event(snapshot, node, method, args, value, at):
    snapshot["gain_events"].append({"node": node, "context": 1, "method": method, "args": args,
                                    "value": value, "context_time": at, "wall_ms": at * 1000})
    snapshot["gain_events"].sort(key=lambda item: item["context_time"])
    for index, item in enumerate(snapshot["gain_events"], 1):
        item["sequence"] = index


def silence(stream):
    for item in stream["windows"]:
        for key in ("square_sum", "rms", "peak"):
            item[key] = 0
        for key in ("channel_square_sum", "channel_rms", "channel_peak"):
            item[key] = [0]


class SourceContractTests(unittest.TestCase):
    def test_actual_bus_and_mix_receipts_pass_without_mutating_evidence(self):
        snapshot, cue, context = fixture()
        original = copy.deepcopy(snapshot)
        proof = validate_cue_pcm(snapshot, cue, context)
        self.assertEqual(proof["bus_id"], 4)
        self.assertEqual(proof["master_id"], 2)
        self.assertEqual(proof["active_meter_samples"], 7)
        self.assertAlmostEqual(proof["bus_gain"], math.pow(10, -3 / 20))
        self.assertEqual(proof["master_gain"], 1)
        self.assertEqual(snapshot, original)

    def test_silent_cue_cannot_borrow_audible_background_music(self):
        snapshot, cue, context = fixture()
        silence(context["audio_thread"]["streams"][1])
        self.assertGreater(context["audio_thread"]["windows"][0]["rms"], 0)
        with self.assertRaisesRegex(ValueError, "silent"):
            validate_cue_pcm(snapshot, cue, context)

    def test_audible_cue_bus_cannot_borrow_muted_final_mix(self):
        snapshot, cue, context = fixture()
        silence(context["audio_thread"])
        with self.assertRaisesRegex(ValueError, "silent"):
            validate_cue_pcm(snapshot, cue, context)

    def test_detached_source_bus_or_terminal_fail(self):
        for left, right in ((6, 4), (4, 2), (2, 1)):
            with self.subTest(edge=(left, right)):
                snapshot, cue, context = fixture()
                graph_event(snapshot, "disconnect", left, right, 10.3)
                with self.assertRaisesRegex(ValueError, "graph changed"):
                    validate_cue_pcm(snapshot, cue, context)

    def test_disconnect_reconnect_same_clock_is_not_erased(self):
        snapshot, cue, context = fixture()
        graph_event(snapshot, "disconnect", 4, 2, 10.3)
        graph_event(snapshot, "connect", 4, 2, 10.3)
        with self.assertRaisesRegex(ValueError, "graph changed"):
            validate_cue_pcm(snapshot, cue, context)

    def test_rewiring_to_another_audible_bus_fails(self):
        snapshot, cue, context = fixture()
        graph_event(snapshot, "connect", 6, 3, 10.3)
        with self.assertRaises(ValueError):
            validate_cue_pcm(snapshot, cue, context)

    def test_current_graph_after_natural_end_does_not_replace_history(self):
        snapshot, cue, context = fixture()
        graph_event(snapshot, "disconnect", 6, 4, 11)
        gain_event(snapshot, 2, "value", [0], 0, 12)
        self.assertEqual(validate_cue_pcm(snapshot, cue, context)["master_gain"], 1)

    def test_missing_connect_history_cannot_be_filled_by_snapshot(self):
        snapshot, cue, context = fixture()
        snapshot["graph_events"].pop()
        with self.assertRaisesRegex(ValueError, "history"):
            validate_cue_pcm(snapshot, cue, context)

    def test_transient_master_mute_even_at_one_clock_fails(self):
        snapshot, cue, context = fixture()
        gain_event(snapshot, 2, "value", [0], 0, 10.3)
        gain_event(snapshot, 2, "value", [1], 1, 10.3)
        with self.assertRaisesRegex(ValueError, "Gain changed"):
            validate_cue_pcm(snapshot, cue, context)

    def test_nonzero_parameter_restored_before_cue_is_allowed(self):
        snapshot, cue, context = fixture()
        gain_event(snapshot, 2, "value", [0], 0, 9)
        gain_event(snapshot, 2, "value", [1], 1, 9)
        self.assertEqual(validate_cue_pcm(snapshot, cue, context)["master_gain"], 1)

    def test_nonzero_cue_pcm_does_not_override_observed_master_mute(self):
        snapshot, cue, context = fixture()
        gain_event(snapshot, 2, "value", [0], 0, 9)
        with self.assertRaisesRegex(ValueError, "nonzero gain"):
            validate_cue_pcm(snapshot, cue, context)

    def test_unknown_or_cancelled_automation_is_not_inferred(self):
        for method, args in (("linearRampToValueAtTime", [1, 11]),
                             ("cancelScheduledValues", [10]),
                             ("cancelAndHoldAtTime", [10]), ("audio_input", []),
                             ("unrecognized", [])):
            with self.subTest(method=method):
                snapshot, cue, context = fixture()
                gain_event(snapshot, 2, method, args, 1, 9)
                with self.assertRaisesRegex(ValueError, "Unsupported gain"):
                    validate_cue_pcm(snapshot, cue, context)

    def test_future_set_value_is_not_assumed_to_be_current(self):
        snapshot, cue, context = fixture()
        gain_event(snapshot, 2, "setValueAtTime", [0, 10.4], 1, 9)
        with self.assertRaisesRegex(ValueError, "Future gain"):
            validate_cue_pcm(snapshot, cue, context)

    def test_queued_value_uses_actual_arguments_not_old_intrinsic_value(self):
        snapshot, cue, context = fixture()
        gain_event(snapshot, 2, "setValueAtTime", [0, 9], 1, 9)
        with self.assertRaisesRegex(ValueError, "nonzero gain"):
            validate_cue_pcm(snapshot, cue, context)

    def test_early_stop_or_shortened_planned_lifetime_fails(self):
        for field in ("stopped_context_time", "ended_context_time", "planned_end"):
            snapshot, cue, context = fixture()
            cue[field] = 10.4
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "authored lifetime"):
                validate_cue_pcm(snapshot, cue, context)

    def test_competing_source_into_cue_bus_fails(self):
        snapshot, cue, context = fixture()
        snapshot["nodes"].append({"id": 7, "kind": "AudioBufferSourceNode"})
        snapshot["starts"].append({"id": 7, "context": 1, "scheduled_start": 9.9,
                                    "planned_end": 11, "path_at_start": [7, 4, 2, 1]})
        graph_event(snapshot, "connect", 7, 4, 9.9)
        with self.assertRaisesRegex(ValueError, "competing"):
            validate_cue_pcm(snapshot, cue, context)

    def test_source_lifecycle_overlap_fails_even_with_inconsistent_graph_snapshot(self):
        snapshot, cue, context = fixture()
        snapshot["nodes"].append({"id": 7, "kind": "AudioBufferSourceNode"})
        snapshot["starts"].append({"id": 7, "context": 1, "scheduled_start": 10.2,
                                    "planned_end": 11, "path_at_start": [7, 4, 2, 1]})
        with self.assertRaisesRegex(ValueError, "Competing source"):
            validate_cue_pcm(snapshot, cue, context)

    def test_missing_silent_gapped_or_dropped_bus_pcm_fails(self):
        for defect in ("missing", "no_windows", "dropped", "silent_window", "wrong_frames"):
            snapshot, cue, context = fixture()
            bus = context["audio_thread"]["streams"][1]
            if defect == "missing":
                context["audio_thread"]["streams"].pop()
            elif defect == "no_windows":
                bus["windows"] = []
            elif defect == "dropped":
                bus["windows"].pop(4)
            elif defect == "silent_window":
                silence({"windows": [bus["windows"][4]]})
            else:
                bus["windows"][4]["frames"] -= 1
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                validate_cue_pcm(snapshot, cue, context)

    def test_late_duplicate_or_misidentified_tap_fails(self):
        for defect in ("late", "duplicate", "wrong_id", "wrong_source", "no_original_binding"):
            snapshot, cue, context = fixture()
            bus = context["audio_thread"]["streams"][1]
            if defect == "late":
                bus["ready_context_time"] = 10.1
            elif defect == "duplicate":
                context["audio_thread"]["streams"].append(copy.deepcopy(bus))
            elif defect == "wrong_id":
                bus["tap_id"] = "invented"
            elif defect == "wrong_source":
                cue["meter_taps"][1]["source"] = 3
            else:
                cue["meter_taps"] = []
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                validate_cue_pcm(snapshot, cue, context)

    def test_unknown_history_or_lost_sequence_fails(self):
        for defect in ("overflow", "missing_gain", "gain_sequence", "graph_sequence", "cross_context", "nonfinite"):
            snapshot, cue, context = fixture()
            if defect == "overflow":
                snapshot["history_overflow"] = True
            elif defect == "missing_gain":
                snapshot["gain_events"] = []
            elif defect == "gain_sequence":
                snapshot["gain_events"][2]["sequence"] += 1
            elif defect == "graph_sequence":
                snapshot["graph_events"][2]["sequence"] += 1
            elif defect == "cross_context":
                snapshot["graph_events"][2]["context"] = 2
            else:
                snapshot["gain_events"][2]["value"] = math.nan
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                validate_cue_pcm(snapshot, cue, context)

    def test_source_metadata_and_topology_are_not_backfilled(self):
        for field, value in (("rate", 2), ("detune", 1), ("looping", True),
                             ("mutations", [{"field": "rate"}]), ("parameter_automation", [{}]),
                             ("path_at_start", [6, 2, 1])):
            snapshot, cue, context = fixture()
            cue[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_cue_pcm(snapshot, cue, context)

    def test_exported_bus_helper_is_independent_of_pcm_amplitude(self):
        snapshot, cue, context = fixture()
        silence(context["audio_thread"]["streams"][1])
        proof = validate_source_bus(snapshot, cue, context, 10, 10.72)
        self.assertEqual(proof["bus_tap_id"], "node:4")
        self.assertNotIn("rms", proof)

    def test_only_music_may_use_measured_post_bus_pcm_instead_of_fade_reconstruction(self):
        snapshot, cue, context = fixture()
        with self.assertRaisesRegex(ValueError, "Only measured music"):
            validate_source_bus(snapshot, cue, context, 10, 10.72, check_bus_gain=False)
        music = snapshot["starts"][0]
        music.update({"context_time": 1, "wall_ms": 1000, "meter_taps": [
            {"tap_id": "mix:1", "source": None, "role": "mix"},
            {"tap_id": "node:3", "source": 3, "role": "bus"}]})
        with self.assertRaisesRegex(ValueError, "Unsupported gain"):
            validate_source_bus(snapshot, music, context, 10, 10.72)
        proof = validate_source_bus(snapshot, music, context, 10, 10.72, check_bus_gain=False)
        self.assertIsNone(proof["bus_gain"])
        self.assertFalse(proof["bus_gain_checked"])
        self.assertEqual(proof["master_gain"], 1)
        gain_event(snapshot, 2, "value", [0], 0, 10.3)
        with self.assertRaisesRegex(ValueError, "Gain changed"):
            validate_source_bus(snapshot, music, context, 10, 10.72, check_bus_gain=False)

    def test_boolean_or_missing_source_clocks_and_parameters_fail(self):
        for field, value in (("rate", True), ("offset", False), ("detune", False),
                             ("context_time", None), ("wall_ms", math.nan)):
            snapshot, cue, context = fixture()
            cue[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_cue_pcm(snapshot, cue, context)

    def test_source_observation_may_cross_one_real_render_quantum(self):
        snapshot, cue, context = fixture()
        cue["context_time"] += 128 / 44100
        validate_cue_pcm(snapshot, cue, context)
        # This allowance cannot be reused to arm a tap after the scheduled start.
        context["audio_thread"]["streams"][1]["ready_context_time"] = 10.001
        with self.assertRaisesRegex(ValueError, "armed after"):
            validate_cue_pcm(snapshot, cue, context)

    def test_bus_helper_alone_rejects_early_source_termination(self):
        snapshot, cue, context = fixture()
        cue["stopped_context_time"] = 10.3
        with self.assertRaisesRegex(ValueError, "required lifetime"):
            validate_source_bus(snapshot, cue, context, 10, 10.72)

    def test_duplicate_or_cross_context_source_history_fails(self):
        for duplicate in (True, False):
            snapshot, cue, context = fixture()
            if duplicate:
                snapshot["starts"].append(copy.deepcopy(snapshot["starts"][0]))
            else:
                snapshot["starts"][0]["context"] = 2
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(ValueError, "source history"):
                validate_cue_pcm(snapshot, cue, context)


if __name__ == "__main__":
    unittest.main()
