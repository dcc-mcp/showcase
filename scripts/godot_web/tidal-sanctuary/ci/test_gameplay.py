"""Fail-closed unit fixtures, not claims that real input or rendering has passed."""
import copy
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from common import GAME_FILES
from author_native import DEFERRED_TEST_FILES, EDITOR_PROBE_PATH, editor_idle_sample, initial_copy_files
from capture_browser import capture_png, completed_route_save, secondary_touch_tap, validate_web_exit
from capture_native import validate_input_movie_span
from gameplay import (ROUTE, RouteDriver, complete, direction_to, keyboard_direction,
                      validate_progress, validate_restored, validate_state, validate_water_crossing)


class GameplayObserverTests(unittest.TestCase):
    def state(self, **changes):
        result = {"schema": 1, "sample_id": 1, "physics_frame": 60, "demo": False,
                  "position": [1.3, 1, 10], "locomotion": "walk", "water_depth": 0.0,
                  "camera_right": [1, 0], "camera_forward": [0, -1],
                  "action_rect": [1100, 620, 100, 40], "quest_stage": 0,
                  "treasures": [False, False], "completed": False, "language": "en",
                  "movement_input": [0, 0], "velocity": [0, 0, 0]}
        result.update(changes)
        return result

    def finished(self, **changes):
        return self.state(**{"quest_stage": 4, "treasures": [True, True], "completed": True, **changes})

    def at_stage(self, stage, **changes):
        return self.state(**{"quest_stage": stage,
                             "treasures": [[False, False], [False, False], [True, False], [True, True], [True, True]][stage],
                             "completed": stage == 4, **changes})

    def driver(self, samples, interact=None):
        return RouteDriver(lambda: samples, Mock(), interact or Mock(), Mock(), Mock())

    def settle(self, driver, samples, initial, point):
        driver.stop_for_action(initial, point)
        settled = {**initial, "sample_id": initial["sample_id"] + 1,
                   "physics_frame": initial["physics_frame"] + 12,
                   "movement_input": [0, 0], "velocity": [0, 0, 0]}
        samples.append(settled)
        driver.observe()
        return settled

    def crossing(self):
        return [self.state(sample_id=i + 1, physics_frame=60 + i * 30, locomotion=mode, water_depth=1.2 if mode == "swim" else 0.2)
                for i, mode in enumerate(["walk", "wade", "swim", "swim", "swim", "wade", "walk"])]

    def test_route_and_source_files_are_explicit(self):
        self.assertEqual([point.get("stage") for point in ROUTE if point.get("stage")], [1, 2, 3, 4])
        self.assertTrue({"swim_controller.gd", "verify_swimming.gd", "verify_treasure.gd"}.issubset(GAME_FILES))
        self.assertEqual(ROUTE[3]["target"], [8.2, 5.5])

    def test_valid_passive_state(self):
        self.assertEqual(validate_state(self.state()), self.state())
        validate_state(self.state(sample_id=2, physics_frame=72, position=[1.7, .5, 9.8]), self.state())
        validate_state(self.state(demo=True), expected_demo=True)

    def test_observer_rejects_missing_fields_wrong_types_and_invalid_values(self):
        cases = [("schema", True), ("sample_id", 0), ("physics_frame", -1), ("demo", True),
                 ("position", [1, float("nan"), 2]), ("position", [1, 2]), ("locomotion", "flying"),
                 ("camera_right", [0, 0]), ("camera_forward", [1, 0]), ("action_rect", [1, 2, 0, 4]),
                 ("quest_stage", True), ("quest_stage", 5), ("treasures", [1, 1]), ("treasures", [True]),
                 ("completed", 1), ("water_depth", float("nan")), ("water_depth", -1), ("language", "xx"),
                 ("movement_input", [float("nan"), 0]), ("movement_input", [0]),
                 ("velocity", [0, float("inf"), 0]), ("velocity", [0, 0])]
        for field, value in cases:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_state(self.state(**{field: value}))
        for field in ("schema", "sample_id", "physics_frame", "demo", "position", "locomotion", "camera_right",
                      "camera_forward", "action_rect", "quest_stage", "treasures", "completed", "water_depth", "language", "movement_input", "velocity"):
            value = self.state()
            del value[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_state(value)

    def test_stale_frames_teleport_and_regression_are_rejected(self):
        for state in (self.state(), self.state(sample_id=2),
                      self.state(sample_id=2, physics_frame=72, position=[30, 1, 10])):
            with self.assertRaises(ValueError):
                validate_state(state, self.state())
        with self.assertRaisesRegex(ValueError, "regressed"):
            validate_state(self.state(sample_id=2, physics_frame=72), self.state(quest_stage=1))

    def test_real_input_direction_uses_observed_camera_axes(self):
        self.assertEqual(direction_to(self.state(), [1.3, 8]), (0, -1))
        self.assertEqual(keyboard_direction((0, -1)), {"w"})
        self.assertEqual(keyboard_direction((.7, .7)), {"d", "s"})
        self.assertEqual(keyboard_direction((0, 0)), set())
        self.assertEqual(direction_to(self.state(), [1.3, 10]), (0, 0))

    def test_water_crossing_requires_return_and_sustained_swimming(self):
        report = validate_water_crossing(self.crossing())
        self.assertEqual(report["longest_continuous_swim_physics_frames"], 60)
        for samples in (self.crossing()[:-1], self.crossing()[1:],
                        [state for state in self.crossing() if state["locomotion"] != "wade"],
                        self.crossing()[:3] + self.crossing()[5:]):
            with self.assertRaises(ValueError):
                validate_water_crossing(samples)
        samples = self.crossing()
        samples[3]["locomotion"] = "wade"
        with self.assertRaisesRegex(ValueError, "sustain"):
            validate_water_crossing(samples)

    def test_completion_requires_every_treasure_and_return_stage(self):
        self.assertTrue(complete(self.finished()))
        for stage in range(4):
            self.assertFalse(complete(self.at_stage(stage)))
        for changes in ({"quest_stage": 3}, {"treasures": [True, False]}, {"completed": False}):
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                complete(self.finished(**changes))

    def test_exact_stage_to_flags_consistency(self):
        for stage in range(5):
            for treasures in ([False, False], [True, False], [False, True], [True, True]):
                for completed in (False, True):
                    state = self.state(quest_stage=stage, treasures=treasures, completed=completed)
                    expected = self.at_stage(stage)
                    with self.subTest(stage=stage, treasures=treasures, completed=completed):
                        if treasures == expected["treasures"] and completed == expected["completed"]:
                            validate_progress(state)
                        else:
                            with self.assertRaisesRegex(ValueError, "inconsistent"):
                                validate_progress(state)

    def test_consistent_flags_cannot_hide_skipped_quest_stages(self):
        for before in range(3):
            for after in range(before + 2, 5):
                with self.subTest(before=before, after=after), self.assertRaisesRegex(ValueError, "skipped"):
                    validate_state(self.at_stage(after, sample_id=2, physics_frame=72), self.at_stage(before))
        for before in range(4):
            validate_state(self.at_stage(before + 1, sample_id=2, physics_frame=72), self.at_stage(before))

    def test_progress_requires_real_callback_request_and_matching_location(self):
        at_map = self.at_stage(0, position=[1.3, 1, 7.8])
        samples = [at_map]
        callback = Mock()
        driver = self.driver(samples, callback)
        driver.observe()
        at_map = self.settle(driver, samples, at_map, ROUTE[0])
        driver.request_action(at_map, ROUTE[0])
        callback.assert_called_once_with(at_map)
        samples.append(self.at_stage(1, sample_id=3, physics_frame=84, position=[1.3, 1, 7.8]))
        driver.observe()
        self.assertEqual(driver.accepted_stage, 1)
        self.assertIsNone(driver.pending_action)
        self.assertEqual(driver.actions[0]["accepted_sample_id"], 3)
        # The same action cannot authorize a second, unrequested stage transition.
        samples.append(self.at_stage(2, sample_id=4, physics_frame=96, position=[1.3, 1, 7.8]))
        with self.assertRaisesRegex(ValueError, "without.*callback"):
            driver.observe()

    def test_unsolicited_chart_and_early_completion_are_rejected(self):
        for stage in (0, 3):
            samples = [self.at_stage(stage)]
            driver = self.driver(samples)
            # Simulate already accepted earlier checkpoints only for this unit fixture.
            if stage:
                driver.samples = list(samples)
                driver.accepted_stage = stage
            else:
                driver.observe()
            samples.append(self.at_stage(stage + 1, sample_id=2, physics_frame=72))
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, "without.*callback"):
                driver.observe()
        for stage in (1, 4):
            with self.subTest(initial_stage=stage), self.assertRaisesRegex(ValueError, "fresh quest stage"):
                self.driver([self.at_stage(stage)]).observe()

    def test_action_cannot_authorize_a_distant_or_earlier_receipt(self):
        initial = self.at_stage(0, position=[1.3, 1, 7.8])
        samples = [initial]
        driver = self.driver(samples)
        driver.observe()
        with self.assertRaisesRegex(ValueError, "outside the authored interaction range"):
            driver.request_action(initial, {**ROUTE[0], "target": [20, 20]})
        initial = self.settle(driver, samples, initial, ROUTE[0])
        driver.request_action(initial, ROUTE[0])
        with self.assertRaisesRegex(ValueError, "predates"):
            driver.accept_progress(self.at_stage(1, position=[1.3, 1, 7.8]), initial)
        distant = self.at_stage(1, sample_id=3, physics_frame=180, position=[5, 1, 7.8])
        with self.assertRaisesRegex(ValueError, "interaction location"):
            driver.accept_progress(distant, initial)

    def test_failed_physical_callback_cannot_authorize_progress(self):
        initial = self.at_stage(0, position=[1.3, 1, 7.8])
        samples = [initial]
        driver = self.driver(samples, Mock(side_effect=RuntimeError("OS input failed")))
        driver.observe()
        initial = self.settle(driver, samples, initial, ROUTE[0])
        with self.assertRaisesRegex(RuntimeError, "OS input failed"):
            driver.request_action(initial, ROUTE[0])
        samples.append(self.at_stage(1, sample_id=3, physics_frame=84, position=[1.3, 1, 7.8]))
        with self.assertRaisesRegex(ValueError, "without.*callback"):
            driver.observe()

    def test_action_cannot_skip_current_authored_milestone(self):
        initial = self.at_stage(0, position=[1.3, 1, 7.8])
        driver = self.driver([initial])
        driver.observe()
        for target_stage in (0, 2, 3, 4):
            with self.subTest(stage=target_stage), self.assertRaisesRegex(ValueError, "next exact quest milestone"):
                driver.request_action(initial, {**ROUTE[0], "stage": target_stage})
        # A route definition itself cannot jump directly to the final milestone.
        with patch("gameplay.ROUTE", [{**ROUTE[0], "stage": 4}]):
            with self.assertRaisesRegex(ValueError, "skips a required quest milestone"):
                driver.run()

    def test_callback_drift_outside_navigation_radius_does_not_undo_valid_action(self):
        initial = self.at_stage(0, position=[1.3, 1, 7.8])
        samples = [initial]
        driver = self.driver(samples)
        driver.observe()
        initial = self.settle(driver, samples, initial, ROUTE[0])
        driver.request_action(initial, ROUTE[0])
        acknowledged = self.at_stage(1, sample_id=3, physics_frame=84,
                                     position=[1.3135, .4668, 6.8344])
        samples.append(acknowledged)
        driver.observe()
        self.assertTrue(driver.milestone_reached(acknowledged, ROUTE[0]))
        self.assertFalse(driver.milestone_reached(initial, ROUTE[0]))
        driver.actions.clear()
        with self.assertRaisesRegex(ValueError, "matching accepted physical action"):
            driver.milestone_reached(acknowledged, ROUTE[0])

    def test_navigation_waypoint_preserves_held_input_until_next_direction(self):
        driver = self.driver([self.state()])
        driver.snapshot.side_effect = [None, RuntimeError("waypoint captured")]
        point = {"name": "through point", "target": [1.3, 10], "screenshot": "marker.png"}
        with patch("gameplay.ROUTE", [point]), self.assertRaisesRegex(RuntimeError, "waypoint captured"):
            driver.run()
        # Only finally releases input; reaching a path turn must not create a
        # zero-duration release/repress of a key shared by both directions.
        driver.move.assert_called_once_with((0, 0))
        driver.interact.assert_not_called()

    def test_pending_action_does_not_resteer_or_double_tap(self):
        initial = self.at_stage(0, position=[1.3, 1, 7.8])
        samples, clock = [initial], [1.0]
        callback = Mock(side_effect=lambda _: samples.append(
            self.at_stage(0, sample_id=3, physics_frame=84, position=[1.3, 1, 6.84])))
        driver = self.driver(samples, callback)
        driver.timeout = .5
        def pause(seconds):
            clock[0] += seconds
            if len(samples) == 1:
                samples.append({**initial, "sample_id": 2, "physics_frame": 72})
        driver.pause = pause
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [ROUTE[0]]):
            with self.assertRaisesRegex(RuntimeError, "could not reach/complete"):
                driver.run()
        callback.assert_called_once_with(samples[1])
        self.assertEqual(len(driver.actions), 1)
        self.assertTrue(all(call.args == ((0, 0),) for call in driver.move.call_args_list))

    def test_action_waits_for_new_settled_physics_after_stop_callback_return(self):
        initial = self.at_stage(0, position=[1.3, 1, 7.8], movement_input=[0, -1], velocity=[0, 0, -4])
        buffered_neutral = self.at_stage(0, sample_id=2, physics_frame=72, position=[1.3, 1, 7.8])
        samples = [initial]
        driver = self.driver(samples)
        driver.observe()
        # A long physical callback delivered this neutral sample before return.
        # Its existence must not authorize an immediate stale-position action.
        driver.move.side_effect = lambda _: samples.append(buffered_neutral)
        boundary = driver.stop_for_action(initial, ROUTE[0])
        self.assertEqual(boundary, buffered_neutral)
        self.assertEqual(driver.stop_boundary["after_sample_id"], 2)
        for changes in ({}, {"sample_id": 3}, {"physics_frame": 84},
                        {"sample_id": 3, "physics_frame": 84, "movement_input": [.00001, 0]},
                        {"sample_id": 3, "physics_frame": 84, "velocity": [.081, 0, 0]},
                        {"sample_id": 3, "physics_frame": 84, "velocity": [.06, 0, .06]}):
            stale_or_moving = {**buffered_neutral, **changes}
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "fresh neutral and settled"):
                driver.request_action(stale_or_moving, ROUTE[0])
        driver.interact.assert_not_called()
        fresh = {**buffered_neutral, "sample_id": 3, "physics_frame": 84}
        samples.append(fresh)
        driver.observe()
        driver.request_action(fresh, ROUTE[0])
        driver.interact.assert_called_once_with(fresh)
        self.assertEqual(driver.actions[0]["stop"]["settled_sample_id"], 3)
        with self.assertRaisesRegex(ValueError, "already pending"):
            driver.request_action(fresh, ROUTE[0])
        with self.assertRaisesRegex(ValueError, "pending"):
            driver.stop_for_action(fresh, ROUTE[0])

    def test_hosted_touch_stop_drift_reapproaches_before_any_action(self):
        # Retained failed head 0e5ad284: sample 30 was moving near the chart,
        # neutral arrived at 32, and settled sample 35 was outside real reach.
        initial = self.state(sample_id=30, physics_frame=390,
            position=[1.30216014, .49920744, 7.47378206],
            movement_input=[-.00044332, -.92857087], velocity=[-.00400176, 0, -3.06396008])
        buffered = self.state(sample_id=32, physics_frame=416,
            position=[1.30944026, .451, 6.18772173], velocity=[-.00097713, 0, -1.85857749])
        settled = self.state(sample_id=35, physics_frame=455,
            position=[1.31959140, .45105976, 6.01897573])
        samples, clock = [initial], [1.0]
        driver = self.driver(samples)
        def move(direction):
            if direction != (0, 0):
                self.assertEqual(direction, direction_to(settled, ROUTE[0]["target"]))
                self.assertEqual(samples[-1], settled)
                raise RuntimeError("physical reapproach requested")
            if len(samples) == 1:
                samples.append(buffered)
        def pause(seconds):
            clock[0] += seconds
            if len(samples) == 2:
                samples.append(settled)
        driver.move.side_effect, driver.pause = move, pause
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), \
                patch("gameplay.ROUTE", [ROUTE[0]]), \
                self.assertRaisesRegex(RuntimeError, "physical reapproach requested"):
            driver.run()
        driver.interact.assert_not_called()
        self.assertEqual(driver.actions, [])
        self.assertEqual(driver.stops[0]["after_sample_id"], 32)
        self.assertEqual(driver.stops[0]["drifted_sample_id"], 35)

    def test_stop_drift_then_reapproach_sends_one_action_after_second_stop(self):
        point = {**ROUTE[0], "screenshot": "checkpoint.png"}
        initial = self.state(position=[1.3, 1, 7.47], movement_input=[0, -1], velocity=[0, 0, -3])
        outside = self.state(sample_id=2, physics_frame=72, position=[1.3, 1, 6.02])
        samples, clock = [initial], [1.0]
        driver = self.driver(samples)
        driver.snapshot.side_effect = [None, RuntimeError("accepted checkpoint captured")]
        def move(direction):
            if direction == (0, 0):
                if len(samples) == 1:
                    samples.append(outside)
                elif len(samples) == 4:
                    samples.append(self.state(sample_id=5, physics_frame=108, position=[1.3, 1, 7.0]))
            else:
                self.assertEqual(samples[-1]["sample_id"], 3)
                driver.interact.assert_not_called()
                samples.append(self.state(sample_id=4, physics_frame=96,
                    position=[1.3, 1, 6.8], movement_input=[0, 1], velocity=[0, 0, 2]))
        def pause(seconds):
            clock[0] += seconds
            if len(samples) in (2, 5):
                sample = samples[-1]
                samples.append({**sample, "sample_id": sample["sample_id"] + 1,
                                "physics_frame": sample["physics_frame"] + 12})
        driver.move.side_effect, driver.pause = move, pause
        driver.interact.side_effect = lambda state: samples.append(
            {**state, "sample_id": 7, "physics_frame": 132, "quest_stage": 1})
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), \
                patch("gameplay.ROUTE", [point]), \
                self.assertRaisesRegex(RuntimeError, "accepted checkpoint captured"):
            driver.run()
        driver.interact.assert_called_once_with(samples[5])
        self.assertEqual(len(driver.stops), 2)
        self.assertEqual(driver.stops[0]["drifted_sample_id"], 3)
        self.assertEqual(driver.actions[0]["stop"]["after_sample_id"], 5)
        self.assertEqual(driver.actions[0]["stop"]["settled_sample_id"], 6)
        self.assertEqual(driver.actions[0]["accepted_sample_id"], 7)

    def test_settled_action_uses_real_range_without_expanding_it(self):
        point = {**ROUTE[0], "target": [0, 0]}
        initial = self.state(position=[0, 1, 1.2])
        samples = [initial]
        driver = self.driver(samples)
        driver.observe()
        settled = self.settle(driver, samples, initial, point)
        settled["velocity"] = [0, .5, 0]  # Vertical wave buoyancy does not move out of reach.
        # The .8 m navigation aiming disk is not a restriction in the game.
        # A neutral, stationary player at 1.2 m is still genuinely in reach.
        for distance in (1.55, 1.550001, 2):
            with self.subTest(distance=distance), self.assertRaisesRegex(ValueError, "outside the authored interaction range"):
                driver.request_action({**settled, "position": [0, 1, distance]}, point)
        driver.interact.assert_not_called()
        driver.request_action(settled, point)
        driver.interact.assert_called_once_with(settled)
        self.assertEqual(driver.actions[0]["stop"]["settled_sample_id"], 2)

    def test_slow_snapshot_requires_fresh_real_observation_after_capture(self):
        for advances in (True, False):
            clock = [1.0]
            samples = [self.state(), self.state(sample_id=2, physics_frame=72, locomotion="wade", water_depth=.2)]
            driver = self.driver(samples)
            def capture(*_):
                clock[0] += 12
                if advances:
                    samples.append(self.state(sample_id=3, physics_frame=84, locomotion="wade", water_depth=.2))
            driver.snapshot.side_effect = capture
            with self.subTest(advances=advances), patch("gameplay.time.monotonic", side_effect=lambda: clock[0]):
                if advances:
                    self.assertEqual(driver.observe()["sample_id"], 3)
                    self.assertEqual(driver.capture_seconds, 12)
                else:
                    with self.assertRaisesRegex(RuntimeError, "stopped advancing"):
                        driver.observe()

    def test_fresh_process_restoration_requires_existing_matching_complete_save(self):
        expected = self.finished()
        receipt = {**expected, "found": True}
        self.assertEqual(validate_restored(receipt, expected), receipt)
        for field, value in (("found", False), ("found", 1), ("schema", 2), ("quest_stage", 3),
                             ("treasures", [False, True]), ("completed", False), ("language", "zh"),
                             ("position", [100, 1, 10])):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_restored({**receipt, field: value}, expected)
        missing = copy.deepcopy(expected)
        del missing["language"]
        with self.assertRaises(ValueError):
            validate_restored(receipt, missing)


class AuthoringBoundaryTests(unittest.TestCase):
    def response(self, **changes):
        sample = {"schema": 1, "scanning": False, "process_frame": 42,
                  "types": {"res://swim_controller.gd": "GDScript"}}
        sample.update(changes)
        return {"success": True, "context": {"executed": True, "result": sample}}

    def test_initial_editor_scan_excludes_uncreated_dependencies_and_regression_fixtures(self):
        initial = set(initial_copy_files())
        self.assertFalse(initial & {"main.gd", "swim_controller.gd", "start.tscn", "project.godot", *DEFERRED_TEST_FILES})
        self.assertEqual(set(DEFERRED_TEST_FILES), {"verify_swimming.gd", "verify_treasure.gd"})
        self.assertTrue(set(DEFERRED_TEST_FILES).issubset(GAME_FILES))
        self.assertEqual(initial | {"main.gd", "swim_controller.gd", "start.tscn", "project.godot", *DEFERRED_TEST_FILES}, set(GAME_FILES))
        self.assertNotIn(EDITOR_PROBE_PATH.removeprefix("res://"), GAME_FILES)

    def test_editor_idle_requires_not_scanning_and_exact_filesystem_types(self):
        expected = {"res://swim_controller.gd": "GDScript"}
        sample, idle = editor_idle_sample(self.response(), expected)
        self.assertTrue(idle)
        self.assertEqual(sample["process_frame"], 42)
        for changes in ({"scanning": True}, {"types": {}}, {"types": {"res://swim_controller.gd": "Resource"}}):
            with self.subTest(changes=changes):
                self.assertFalse(editor_idle_sample(self.response(**changes), expected)[1])

    def test_editor_probe_rejects_unexecuted_malformed_or_unobserved_state(self):
        expected = {"res://swim_controller.gd": "GDScript"}
        for changes in ({"schema": True}, {"scanning": 0}, {"process_frame": 0},
                        {"process_frame": True}, {"types": []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                editor_idle_sample(self.response(**changes), expected)
        for response in (None, {}, {"context": None}, {"executed": False},
                         {"executed": True, "result": None}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                editor_idle_sample(response, expected)


class BrowserInputTests(unittest.TestCase):
    def test_second_finger_sends_only_changed_id_and_can_be_repeated(self):
        primary = [{"id": 0, "x": 80, "y": 600}]
        action = {"id": 1, "x": 304, "y": 787}
        send, pause = Mock(), Mock()
        secondary_touch_tap(send, primary, action, pause)
        self.assertEqual([(call.args[0], [point["id"] for point in call.args[1]])
                          for call in send.call_args_list], [("touchStart", [1]), ("touchEnd", [1])])
        self.assertEqual(primary, [{"id": 0, "x": 80, "y": 600}])
        pause.assert_called_once_with(.09)
        secondary_touch_tap(send, primary, action, pause)
        self.assertEqual([call.args[0] for call in send.call_args_list],
                         ["touchStart", "touchEnd", "touchStart", "touchEnd"])
        for invalid in ([], [{"id": 1}], primary + [action]):
            with self.assertRaises(ValueError):
                secondary_touch_tap(send, invalid, action, pause)

    def test_completion_save_survives_slow_capture_without_accepting_old_or_fake_save(self):
        saved = {"schema": 1, "quest_stage": 4, "treasures": [True, True],
                 "completed": True, "position": [0, 4, -11.7], "language": "en"}
        def line(prefix, value):
            return {"text": prefix + " " + json.dumps(value)}
        complete_line = line("TIDAL_COMPLETE", {"demo": False, "stage": 4})
        save_line = line("TIDAL_SAVE", saved)
        console = [save_line, complete_line, save_line]
        self.assertEqual(completed_route_save(console, 1, saved), saved)
        self.assertIsNone(completed_route_save(console, 2, saved))
        self.assertIsNone(completed_route_save([save_line], 0, saved))
        self.assertIsNone(completed_route_save([complete_line], 0, saved))
        for changes in ({"schema": True}, {"completed": False}, {"treasures": [False, False]},
                        {"position": [float("nan"), 4, 0]}, {"position": [20, 4, 0]}, {"language": "zh"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                completed_route_save([complete_line, line("TIDAL_SAVE", {**saved, **changes})], 0, saved)
        with self.assertRaises(ValueError):
            completed_route_save([line("TIDAL_COMPLETE", {"demo": True, "stage": 4}), save_line], 0, saved)

    def test_real_save_return_requires_final_persistent_save_and_clean_exit(self):
        saved = {"schema": 1, "quest_stage": 4, "treasures": [True, True],
                 "completed": True, "position": [0, 4, -12], "language": "en", "persistent": True, "reason": "exit"}
        receipt = {"schema": 1, "code": 0, "requested": True, "trusted": True,
                   "ok": True, "save_after_request": True, "saved": saved}
        self.assertEqual(validate_web_exit(receipt, saved), saved)
        for changes in ({"code": True}, {"code": 1}, {"ok": False}, {"trusted": False},
                        {"requested": False}, {"save_after_request": False}, {"saved": None},
                        {"saved": {**saved, "persistent": False}},
                        {"saved": {**saved, "reason": "auto"}},
                        {"saved": {**saved, "quest_stage": 3}},
                        {"saved": {**saved, "position": [10, 4, 0]}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_web_exit({**receipt, **changes}, saved)

    def test_public_web_exit_callbacks_fail_closed(self):
        subprocess.run(["node", str(Path(__file__).with_name("test_web_exit.js"))], check=True,
                       capture_output=True, text=True, timeout=10)

    def test_required_screenshot_timeout_is_finite_and_errors_are_not_masked(self):
        page = Mock()
        receipt = capture_png(page, Path("actual.png"))
        page.screenshot.assert_called_once_with(path="actual.png", timeout=120000)
        self.assertEqual(receipt["timeout_seconds"], 120)
        self.assertFalse(receipt["diagnostic"])
        capture_png(page, Path("diagnostic.png"), diagnostic=True)
        page.screenshot.assert_called_with(path="diagnostic.png", timeout=30000)
        page.screenshot.side_effect = TimeoutError("capture failed")
        with self.assertRaisesRegex(TimeoutError, "capture failed"):
            capture_png(page, Path("required.png"))

    def test_input_movie_must_cover_observed_route_not_merely_decode(self):
        video = {"width": 1280, "height": 720}
        validate_input_movie_span(video, 100.25, 100)
        with self.assertRaisesRegex(RuntimeError, "shorter than"):
            validate_input_movie_span(video, 3, 100)
        for duration, wall in ((0, 100), (602, 100), (100, 0), (100, float("nan")), (float("nan"), 100)):
            with self.subTest(duration=duration, wall=wall), self.assertRaises(RuntimeError):
                validate_input_movie_span(video, duration, wall)
        with self.assertRaises(RuntimeError):
            validate_input_movie_span({"width": 640, "height": 360}, 100, 100)


if __name__ == "__main__":
    unittest.main()
