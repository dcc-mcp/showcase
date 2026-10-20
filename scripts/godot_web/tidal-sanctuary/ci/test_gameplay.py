"""Fail-closed unit fixtures, not claims that real input or rendering has passed."""
import copy
import base64
import tempfile
import asyncio
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from common import GAME_FILES
from author_native import DEFERRED_TEST_FILES, EDITOR_PROBE_PATH, editor_idle_sample, initial_copy_files
from capture_browser import capture_png, passive_evaluate, bounded_cdp, completed_route_save, route_diagnostics, secondary_touch_tap, validate_web_exit
from capture_native import apply_movement_keys, validate_input_movie_span, wait_for_neutral_movement, wait_for_presented_state, story_objectives
from gameplay import (ROUTE, RouteDriver, complete, direction_to, inside_approach,
                      inside_interaction_region, keyboard_direction,
                      validate_progress, validate_restored, validate_state, validate_water_crossing)


class GameplayObserverTests(unittest.TestCase):
    def state(self, **changes):
        result = {"schema": 1, "sample_id": 1, "physics_frame": 60, "demo": False,
                  "position": [1.3, 1, 10], "locomotion": "walk", "water_depth": 0.0,
                  "camera_right": [1, 0], "camera_forward": [0, -1],
                  "action_rect": [1100, 620, 100, 40], "quest_stage": 0,
                  "treasures": [False, False], "completed": False, "language": "en", "audio_muted": False,
                  "movement_input": [0, 0], "velocity": [0, 0, 0],
                  "interaction_available": True, "interaction_reason": "available"}
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
        self.assertTrue({"swim_controller.gd", "verify_swimming.gd", "verify_treasure.gd", "verify_collision.gd"}.issubset(GAME_FILES))
        self.assertEqual(next(p for p in ROUTE if p["name"] == "recover the sea treasure")["target"], [8.2, 5.5])
        self.assertEqual(ROUTE[-1]["target"], [0, -11.7])
        self.assertEqual(ROUTE[-1]["approach"], [0, -10.25])
        self.assertEqual(ROUTE[-1]["radius"], .25)

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
                 ("velocity", [0, float("inf"), 0]), ("velocity", [0, 0]),
                 ("interaction_available", 1), ("interaction_reason", False)]
        for field, value in cases:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_state(self.state(**{field: value}))
        for field in ("schema", "sample_id", "physics_frame", "demo", "position", "locomotion", "camera_right",
                      "camera_forward", "action_rect", "quest_stage", "treasures", "completed", "water_depth", "language",
                      "movement_input", "velocity", "interaction_available"):
            value = self.state()
            del value[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_state(value)

    def test_chart_plinth_detour_retains_physical_milestones(self):
        self.assertEqual([p['stage'] for p in ROUTE if 'stage' in p], [1, 2, 3, 4])
        east, north = ROUTE[1:3]
        self.assertEqual(east['target'], [2.6, 8.7])
        self.assertEqual(north['target'], [2.6, 6.4])
        self.assertEqual(east['corridor_region'], 'southeast')
        self.assertEqual(north['corridor_region'], 'northeast')
        self.assertNotIn('radius', east)
        self.assertNotIn('radius', north)
        self.assertEqual(ROUTE[3]['name'], 'open the inland cache')

    def test_stale_frames_teleport_and_regression_are_rejected(self):
        for state in (self.state(), self.state(sample_id=2),
                      self.state(sample_id=2, physics_frame=72, position=[30, 1, 10])):
            with self.assertRaises(ValueError):
                validate_state(state, self.state())
        with self.assertRaisesRegex(ValueError, "regressed"):
            validate_state(self.state(sample_id=2, physics_frame=72), self.state(quest_stage=1))

    def test_native_release_waits_for_new_neutral_physics_after_keyup(self):
        baseline = self.state(movement_input=[0, 0])
        fresh = self.state(sample_id=4, physics_frame=90, movement_input=[0, 0])
        read = Mock(side_effect=[[baseline],
            [self.state(sample_id=2, movement_input=[0, 0])],
            [self.state(sample_id=3, physics_frame=80, movement_input=[1, 0])], [fresh]])
        with patch("capture_native.time.sleep"):
            receipt = wait_for_neutral_movement(Mock(poll=Mock(return_value=None)), read, baseline)
        self.assertEqual(read.call_count, 4)
        self.assertEqual(receipt["observed"], fresh)
        self.assertEqual(receipt["after_physics_frame"], baseline["physics_frame"])
        self.assertEqual(receipt["after_sample_id"], baseline["sample_id"])

    def test_native_release_refuses_stale_partial_or_absent_input_until_timeout(self):
        baseline = self.state(movement_input=[0, 0])
        for states in [[], [baseline], [self.state(sample_id=2, movement_input=[0, 0])],
                       [self.state(sample_id=2, physics_frame=80, movement_input=[.1, 0])]]:
            clock = [0.0]
            with self.subTest(states=states), patch("capture_native.time.monotonic", side_effect=lambda: clock[0]), \
                    patch("capture_native.time.sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                    self.assertRaisesRegex(TimeoutError, "fresh neutral"):
                wait_for_neutral_movement(Mock(poll=Mock(return_value=None)), lambda: states, baseline, timeout=.2)

    def test_native_release_rejects_invalid_input_and_wrong_route(self):
        baseline = self.state(movement_input=[0, 0])
        for movement in (None, [float("nan"), 0], [0, float("inf")], [True, 0], [0]):
            fresh = self.state(sample_id=2, physics_frame=80, movement_input=movement)
            with self.subTest(movement=movement), self.assertRaises(ValueError):
                wait_for_neutral_movement(Mock(poll=Mock(return_value=None)), lambda: [fresh], baseline)
        with self.assertRaisesRegex(ValueError, "wrong input route"):
            wait_for_neutral_movement(Mock(poll=Mock(return_value=None)),
                lambda: [self.state(sample_id=2, physics_frame=80, movement_input=[0, 0], demo=True)], baseline)

    def test_native_release_requires_live_runtime_before_and_after_receipt(self):
        baseline = self.state(movement_input=[0, 0])
        fresh = self.state(sample_id=2, physics_frame=80, movement_input=[0, 0])
        for polls in ([0], [None, 0]):
            with self.subTest(polls=polls), self.assertRaisesRegex(RuntimeError, "exited"):
                wait_for_neutral_movement(Mock(poll=Mock(side_effect=polls)), lambda: [fresh], baseline)

    def test_native_release_barrier_only_follows_actual_all_keyup(self):
        pressed, calls = {"d", "w"}, []
        def key(name, down):
            calls.append((name, down))
            pressed.add(name) if down else pressed.discard(name)
        barrier = Mock(side_effect=lambda: self.assertEqual(pressed, set()))
        apply_movement_keys((1, 0), pressed, key, barrier)
        self.assertEqual(calls, [("w", False)])
        barrier.assert_not_called()
        apply_movement_keys((1, 0), pressed, key, barrier)
        self.assertEqual(calls, [("w", False)])
        apply_movement_keys((0, 0), pressed, key, barrier)
        self.assertEqual(calls, [("w", False), ("d", False)])
        barrier.assert_called_once()
        apply_movement_keys((0, 0), pressed, key, barrier)
        barrier.assert_called_once()
        apply_movement_keys((1, 0), pressed, key, barrier)
        self.assertEqual(calls[-1], ("d", True))
        barrier.assert_called_once()

    def presentation(self, state=None, **changes):
        state = state or self.state()
        receipt = {"schema": 1, "presentation_id": 2, "first_draw_frame": 50,
                   "draw_frame": 51, "post_draw_count": 2, "state": state,
                   "labels": {"objective": story_objectives()[state["language"]][state["quest_stage"]],
                              "progress": "%d / 4" % state["quest_stage"],
                              "compass": "↑  1m  ·  " + (state["locomotion"].upper() if state["language"] == "en"
                                  else {"walk": "行走", "wade": "涉水", "swim": "游泳"}[state["locomotion"]])}}
        receipt.update(changes)
        return receipt

    def test_native_screenshot_waits_for_new_matching_post_draw_not_physics_alone(self):
        baseline = self.finished(sample_id=4, physics_frame=100)
        old = self.presentation(self.state(), presentation_id=1)
        wrong_stage = self.presentation(self.state(sample_id=4, physics_frame=100))
        fresh = self.presentation(baseline, presentation_id=3)
        read = Mock(side_effect=[[old], [old], [wrong_stage], [fresh]])
        with patch("capture_native.time.sleep"):
            evidence = wait_for_presented_state(Mock(poll=Mock(return_value=None)), read, baseline)
        self.assertEqual(read.call_count, 4)
        self.assertEqual(evidence, {"after_presentation_id": 1, "receipt": fresh})

    def test_native_screenshot_refuses_absent_stale_physics_wrong_mode_or_stage(self):
        baseline = self.state(sample_id=4, physics_frame=100)
        for candidate in [None, self.presentation(baseline, presentation_id=1),
                          self.presentation(self.state(sample_id=3, physics_frame=100)),
                          self.presentation(self.state(sample_id=4, physics_frame=99)),
                          self.presentation(self.state(sample_id=4, physics_frame=100, locomotion="wade")),
                          self.presentation(self.finished(sample_id=4, physics_frame=100))]:
            old = self.presentation(baseline, presentation_id=1)
            read = Mock(side_effect=lambda: [candidate] if candidate else [])
            clock = [0.0]
            # The initial read defines the boundary; every later receipt stays
            # stale, missing, or mismatched. None may manufacture a screenshot.
            sequence = iter([[old]])
            def receipts():
                return next(sequence, read())
            with self.subTest(candidate=candidate), patch("capture_native.time.monotonic", side_effect=lambda: clock[0]), \
                    patch("capture_native.time.sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                    self.assertRaisesRegex(TimeoutError, "frame_post_draw"):
                wait_for_presented_state(Mock(poll=Mock(return_value=None)), receipts, baseline, timeout=.2)

    def test_native_screenshot_rejects_forged_frame_shape_and_wrong_labels(self):
        for patch_fields in [{"schema": True}, {"presentation_id": True}, {"post_draw_count": True},
                             {"post_draw_count": 1}, {"draw_frame": 50}, {"first_draw_frame": -1},
                             {"state": None}, {"state": self.state(demo=True)},
                             {"labels": {"objective": "Treasure recovered", "compass": "↑  1m  ·  WALK"}},
                             {"labels": {"objective": "Find the mariner's chart", "compass": "↑  1m  ·  SWIM"}}]:
            receipt = self.presentation()
            receipt.update(patch_fields)
            read = Mock(side_effect=[[], [receipt]])
            with self.subTest(fields=patch_fields), self.assertRaises(ValueError):
                wait_for_presented_state(Mock(poll=Mock(return_value=None)), read, self.state())

    def test_native_screenshot_checks_both_story_languages_and_progress(self):
        self.assertEqual(story_objectives()["en"][0], "Read the shore chart")
        self.assertEqual(story_objectives()["en"][4], "The promise is kept")
        for language in ("en", "zh"):
            for stage in range(5):
                state = self.at_stage(stage, language=language)
                receipt = self.presentation(state)
                read = Mock(side_effect=[[], [receipt]])
                self.assertEqual(wait_for_presented_state(Mock(poll=Mock(return_value=None)), read, state)["receipt"], receipt)
                for key, bad in (("objective", "Find the mariner's chart"),
                                 ("progress", "%d / 4" % ((stage + 1) % 5)), ("progress", None),
                                 ("compass", "↑ 1m · SWIM"), ("compass", "↑ 1米 · 游泳")):
                    bad_receipt = {**receipt, "labels": {**receipt["labels"], key: bad}}
                    with self.subTest(language=language, key=key, bad=bad), self.assertRaises(ValueError):
                        wait_for_presented_state(Mock(poll=Mock(return_value=None)), Mock(side_effect=[[], [bad_receipt]]), state)

    def test_native_screenshot_requires_runtime_liveness_around_draw_receipt(self):
        for polls in ([0], [None, 0]):
            read = Mock(side_effect=[[], [self.presentation()]])
            with self.subTest(polls=polls), self.assertRaisesRegex(RuntimeError, "exited"):
                wait_for_presented_state(Mock(poll=Mock(side_effect=polls)), read, self.state())

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
        self.assertIs(driver.map_entry, samples[-1])
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
        for available in (False, None, 1):
            with self.subTest(available=available), self.assertRaisesRegex(ValueError, "unavailable"):
                driver.request_action({**fresh, "interaction_available": available}, ROUTE[0])
        samples.append(fresh)
        driver.observe()
        driver.request_action(fresh, ROUTE[0])
        driver.interact.assert_called_once_with(fresh)
        self.assertEqual(driver.actions[0]["stop"]["settled_sample_id"], 3)
        with self.assertRaisesRegex(ValueError, "already pending"):
            driver.request_action(fresh, ROUTE[0])
        with self.assertRaisesRegex(ValueError, "pending"):
            driver.stop_for_action(fresh, ROUTE[0])

    def test_actual_interaction_region_is_independent_of_steering_approach_radius(self):
        point = {**ROUTE[-1], "stage": 1}
        # Hosted desktop sample 166 was physically ready and settled here, but
        # was wrongly re-steered because it lay outside the .25 m aiming disk.
        initial = self.state(position=[-.5133, 3.9459, -10.3726], velocity=[-.0411, 0, -.011])
        samples = [initial]
        driver = self.driver(samples)
        driver.observe()
        settled = self.settle(driver, samples, initial, point)
        self.assertFalse(inside_approach(settled, point))
        self.assertTrue(inside_interaction_region(settled, point))
        # Inside the approach disk but still outside the genuine 1.55 m target
        # radius: never substitute the approach point for the quest target.
        with self.assertRaisesRegex(ValueError, "outside the authored interaction range"):
            driver.request_action({**settled, "position": [0, 1, -10.03]}, point)
        for distance in (1.55, 1.550001, 2):
            outside = {**settled, "position": [0, 1, distance]}
            distant_point = {**point, "target": [0, 0], "approach": [0, 1.45]}
            self.assertFalse(inside_interaction_region(outside, distant_point))
            with self.subTest(distance=distance), self.assertRaisesRegex(ValueError, "outside the authored interaction range"):
                driver.request_action(outside, distant_point)
        driver.interact.assert_not_called()
        driver.request_action(settled, point)
        self.assertEqual(driver.actions[0]["target"], [0, -11.7])
        self.assertEqual(driver.actions[0]["stop"]["approach"], [0, -10.25])
        driver.interact.assert_called_once_with(settled)
        with self.assertRaisesRegex(ValueError, "already pending"):
            driver.request_action(settled, point)

    def test_ready_outside_aiming_disk_stops_then_uses_one_fresh_settled_action(self):
        point = {**ROUTE[-1], "stage": 1, "screenshot": "checkpoint.png"}
        initial = self.state(position=[-.4842, 3.9459, -10.3648],
                             movement_input=[-1, 0], velocity=[-.3584, 0, -.0963])
        buffered = {**initial, "sample_id": 2, "physics_frame": 72,
                    "position": [-.5133, 3.9459, -10.3726],
                    "movement_input": [0, 0], "velocity": [-.0411, 0, -.011]}
        samples, clock = [initial], [1.0]
        driver = self.driver(samples)
        driver.snapshot.side_effect = [None, RuntimeError("accepted checkpoint captured")]
        def move(direction):
            self.assertEqual(direction, (0, 0))
            if len(samples) == 1:
                samples.append(buffered)
        def pause(seconds):
            clock[0] += seconds
            if len(samples) == 2:
                driver.interact.assert_not_called()
                samples.append({**buffered, "sample_id": 3, "physics_frame": 84})
        driver.move.side_effect, driver.pause = move, pause
        driver.interact.side_effect = lambda state: samples.append(
            {**state, "sample_id": 4, "physics_frame": 96, "quest_stage": 1})
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [point]), \
                self.assertRaisesRegex(RuntimeError, "accepted checkpoint captured"):
            driver.run()
        self.assertFalse(inside_approach(initial, point))
        self.assertFalse(inside_approach(samples[2], point))
        driver.interact.assert_called_once_with(samples[2])
        self.assertEqual(len(driver.stops), 1)
        self.assertEqual(driver.actions[0]["stop"]["after_sample_id"], 2)
        self.assertEqual(driver.actions[0]["stop"]["settled_sample_id"], 3)
        self.assertEqual(driver.actions[0]["accepted_sample_id"], 4)
        self.assertNotIn("drifted_sample_id", driver.stops[0])

    def test_ready_region_still_rejects_stale_moving_and_unavailable_actions(self):
        point = {**ROUTE[-1], "stage": 1}
        initial = self.state(position=[-.6732, 3.9459, -10.4254])
        samples = [initial]
        driver = self.driver(samples)
        driver.observe()
        driver.stop_for_action(initial, point)
        fresh = {**initial, "sample_id": 2, "physics_frame": 72}
        for state in (initial, {**fresh, "physics_frame": 60}, {**fresh, "sample_id": 1},
                      {**fresh, "movement_input": [.00001, 0]}, {**fresh, "velocity": [.081, 0, 0]}):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "fresh neutral and settled"):
                driver.request_action(state, point)
        for reason in ("too_far", "too_high", "blocked"):
            unavailable = {**fresh, "interaction_available": False, "interaction_reason": reason}
            self.assertFalse(inside_interaction_region(unavailable, point))
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, "unavailable"):
                driver.request_action(unavailable, point)
        driver.interact.assert_not_called()
        self.assertEqual(driver.actions, [])

    def test_lost_actual_availability_after_stop_reapproaches_without_action(self):
        point = {**ROUTE[-1], "stage": 1}
        for reason in ("too_high", "blocked"):
            initial = self.state(position=[-.5133, 3.9459, -10.3726])
            buffered = {**initial, "sample_id": 2, "physics_frame": 72,
                        "interaction_available": False, "interaction_reason": reason}
            samples, clock = [initial], [1.0]
            driver = self.driver(samples)
            def move(direction):
                if direction != (0, 0):
                    self.assertEqual(direction, direction_to(samples[-1], point["approach"]))
                    self.assertEqual(samples[-1]["sample_id"], 3)
                    raise RuntimeError("physical reapproach requested")
                if len(samples) == 1:
                    samples.append(buffered)
            def pause(seconds):
                clock[0] += seconds
                if len(samples) == 2:
                    samples.append({**buffered, "sample_id": 3, "physics_frame": 84})
            driver.move.side_effect, driver.pause = move, pause
            with self.subTest(reason=reason), patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), \
                    patch("gameplay.ROUTE", [point]), self.assertRaisesRegex(RuntimeError, "physical reapproach requested"):
                driver.run()
            driver.interact.assert_not_called()
            self.assertEqual(len(driver.stops), 1)
            self.assertEqual(driver.stops[0]["drifted_sample_id"], 3)

    def test_path_only_waypoint_keeps_its_radius_even_when_interaction_is_available(self):
        point = {"name": "path-only point", "target": [1.3, 9], "screenshot": "checkpoint.png"}
        initial = self.state()
        samples = [initial]
        driver = self.driver(samples)
        driver.snapshot.side_effect = [None, RuntimeError("path checkpoint captured")]
        def move(direction):
            if direction != (0, 0):
                self.assertEqual(direction, (0, -1))
                samples.append({**initial, "sample_id": 2, "physics_frame": 72, "position": [1.3, 1, 9.7]})
        driver.move.side_effect = move
        self.assertTrue(inside_interaction_region(initial, point))
        self.assertFalse(inside_approach(initial, point))
        with patch("gameplay.ROUTE", [point]), self.assertRaisesRegex(RuntimeError, "path checkpoint captured"):
            driver.run()
        self.assertEqual(driver.milestones[0]["sample"]["sample_id"], 2)
        self.assertEqual(driver.stops, [])
        driver.interact.assert_not_called()

    def test_delayed_stop_drift_reapproaches_and_resettles_before_sole_action(self):
        point = {**ROUTE[-1], "stage": 1, "screenshot": "checkpoint.png"}
        initial = self.state(position=[0, 1, -10.25], movement_input=[0, -1], velocity=[0, 0, -4])
        drifted = self.state(sample_id=2, physics_frame=120, position=[0, 1, -13.33])
        samples, clock = [initial], [1.0]
        driver = self.driver(samples)
        driver.snapshot.side_effect = [None, RuntimeError("accepted checkpoint captured")]
        def move(direction):
            if direction == (0, 0):
                if len(samples) == 1:
                    samples.append(drifted)
                elif samples[-1]["sample_id"] == 4:
                    samples.append({**initial, "sample_id": 5, "physics_frame": 204,
                                    "movement_input": [0, 0], "velocity": [0, 0, .2]})
            else:
                self.assertEqual(samples[-1]["sample_id"], 3)
                driver.interact.assert_not_called()
                samples.append({**initial, "sample_id": 4, "physics_frame": 192,
                                "movement_input": [0, 1], "velocity": [0, 0, 4]})
        def pause(seconds):
            clock[0] += seconds
            if samples[-1]["sample_id"] == 2:
                samples.append({**drifted, "sample_id": 3, "physics_frame": 132})
            elif samples[-1]["sample_id"] == 5:
                samples.append({**initial, "sample_id": 6, "physics_frame": 216,
                                "movement_input": [0, 0], "velocity": [0, 0, 0]})
        def interact(state):
            self.assertEqual(state["sample_id"], 6)
            samples.append({**state, "sample_id": 7, "physics_frame": 228, "quest_stage": 1})
        driver.move.side_effect, driver.pause = move, pause
        driver.interact.side_effect = interact
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [point]):
            with self.assertRaisesRegex(RuntimeError, "accepted checkpoint captured"):
                driver.run()
        driver.interact.assert_called_once_with(samples[5])
        self.assertEqual(len(driver.actions), 1)
        self.assertEqual(driver.actions[0]["accepted_sample_id"], 7)
        self.assertEqual(driver.actions[0]["stop"]["after_sample_id"], 5)
        self.assertEqual(driver.actions[0]["stop"]["settled_sample_id"], 6)
        self.assertEqual(len(driver.stops), 2)
        self.assertEqual(driver.stops[0]["after_sample_id"], 2)
        self.assertEqual(driver.stops[0]["drifted_sample_id"], 3)
        self.assertIn(((0, 1),), [call.args for call in driver.move.call_args_list])

    def test_neutral_but_still_moving_never_authorizes_action(self):
        initial = self.at_stage(0, position=[1.3, 1, 7.8])
        samples, clock = [initial], [1.0]
        driver = self.driver(samples)
        driver.timeout = .4
        def pause(seconds):
            clock[0] += seconds
            previous = samples[-1]
            samples.append({**previous, "sample_id": previous["sample_id"] + 1,
                            "physics_frame": previous["physics_frame"] + 12, "velocity": [.2, 0, 0]})
        driver.pause = pause
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [ROUTE[0]]):
            with self.assertRaisesRegex(RuntimeError, "could not reach/complete"):
                driver.run()
        driver.interact.assert_not_called()
        self.assertEqual(driver.actions, [])

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
                    samples.append(self.state(sample_id=5, physics_frame=108, locomotion="wade", water_depth=.2))
            def settle(_):
                if samples[-1]["sample_id"] < 4:
                    number=samples[-1]["sample_id"]+1
                    samples.append(self.state(sample_id=number,physics_frame=48+number*12,locomotion="wade",water_depth=.2))
            driver.pause.side_effect=settle
            driver.snapshot.side_effect = capture
            with self.subTest(advances=advances), patch("gameplay.time.monotonic", side_effect=lambda: clock[0]):
                if advances:
                    self.assertEqual(driver.observe()["sample_id"], 5)
                    self.assertEqual(driver.capture_seconds, 12)
                else:
                    with self.assertRaisesRegex(RuntimeError, "stopped advancing"):
                        driver.observe()

    def test_historical_wade_is_drained_before_capture_decision(self):
        samples=[self.state(),self.state(sample_id=2,physics_frame=72,locomotion="wade",water_depth=.2),
                 self.state(sample_id=3,physics_frame=84)]
        driver=self.driver(samples)
        self.assertEqual(driver.observe()["sample_id"],3)
        self.assertEqual(len(driver.samples),3)
        driver.snapshot.assert_not_called()
        self.assertFalse(driver.captured)

    def test_snapshot_uses_actual_settled_mode_not_pre_release_wade(self):
        samples=[self.state(locomotion="wade",water_depth=.2)]
        driver=self.driver(samples)
        driver.move.side_effect=lambda _:samples.append(self.state(sample_id=2,physics_frame=72))
        def advance(_):
            n=samples[-1]["sample_id"]+1
            samples.append(self.state(sample_id=n,physics_frame=48+n*12))
        driver.pause.side_effect=advance
        self.assertEqual(driver.observe()["locomotion"],"walk")
        self.assertEqual(driver.snapshot_stops[0]["settled"]["sample_id"],4)
        driver.snapshot.assert_not_called()
        self.assertFalse(driver.captured)

    def test_snapshot_stop_requires_fresh_neutral_stable_samples(self):
        samples=[self.state(locomotion="wade",water_depth=.2)]
        driver=self.driver(samples)
        with self.assertRaisesRegex(TimeoutError,"two fresh neutral"):
            driver.observe()
        driver.snapshot.assert_not_called()
        self.assertFalse(driver.captured)

    def test_driver_drains_every_new_sample_through_corridor_guard(self):
        from corridor import ChartCorridor
        first=self.at_stage(1,position=[1.3,1,9])
        samples=[first];driver=self.driver(samples)
        driver.samples=[first];driver.accepted_stage=1
        driver.chart_corridor=ChartCorridor(first)
        samples.append(self.at_stage(1,sample_id=2,physics_frame=120,position=[1.3,1,7.8]))
        with self.assertRaisesRegex(ValueError,"inflated chart"):
            driver.drain_states()

    def test_slow_fresh_snapshot_settling_uses_remaining_route_budget(self):
        clock=[0.0];samples=[self.state(locomotion="swim",water_depth=1.2)]
        driver=self.driver(samples)
        def advance(_):
            clock[0]+=3
            number=samples[-1]['sample_id']+1
            speed=(1.,.303,.092,.028,.008)[min(number-2,4)]
            samples.append(self.state(sample_id=number,physics_frame=48+number*13,
                                      locomotion="swim",water_depth=1.2,velocity=[speed,0.,0.]))
        driver.pause.side_effect=advance
        with patch('gameplay.time.monotonic',side_effect=lambda:clock[0]):
            driver.begin_waypoint_budget(ROUTE[5],samples[0])
            settled=driver.settled_snapshot_state(samples[0])
        self.assertGreater(clock[0],10)
        self.assertEqual(settled['sample_id'],6)
        self.assertLess(settled['velocity'][0],.08)
        self.assertEqual(driver.budgets[0]['active_wall_limit_seconds'],75)
    def test_snapshot_settling_does_not_renew_total_route_budget(self):
        clock=[0.0];samples=[self.state(locomotion="swim",water_depth=1.2)]
        driver=self.driver(samples)
        def advance(_):
            clock[0]+=3
            n=samples[-1]['sample_id']+1
            samples.append(self.state(sample_id=n,physics_frame=48+n*13,
                                      locomotion="swim",water_depth=1.2,velocity=[1.,0.,0.]))
        driver.pause.side_effect=advance
        with patch('gameplay.time.monotonic',side_effect=lambda:clock[0]):
            driver.begin_waypoint_budget(ROUTE[5],samples[0]);clock[0]=72
            with self.assertRaisesRegex(RuntimeError,'budget expired'):
                driver.settled_snapshot_state(samples[0])
        driver.snapshot.assert_not_called()

    def test_corridor_replays_from_exact_accepted_map_sample(self):
        entry=self.at_stage(1,sample_id=3,physics_frame=84,position=[1.3,1,9])
        later=self.at_stage(1,sample_id=4,physics_frame=96,position=[2.4,1,9])
        driver=self.driver([]);driver.map_entry=entry;driver.samples=[entry,later]
        driver.begin_chart_corridor()
        self.assertEqual(driver.corridor_receipt['entry']['sample_id'],3)
        self.assertEqual(driver.corridor_receipt['samples'],1)
        self.assertIs(driver.chart_corridor.last,later)
        bad={**later,'position':[1.3,1,7.8]}
        driver.samples=[entry,bad,later]
        with self.assertRaisesRegex(ValueError,'inflated chart'):driver.begin_chart_corridor()

    def test_corridor_detour_keeps_original_budget(self):
        clock=[0.0];samples=[self.state()];driver=self.driver(samples)
        point=ROUTE[1]
        with patch("gameplay.time.monotonic",side_effect=lambda:clock[0]):
            driver.begin_waypoint_budget(point,samples[0])
            clock[0]=75
            with self.assertRaisesRegex(RuntimeError,"budget expired"):
                driver.check_waypoint_budget(self.state(sample_id=2,physics_frame=72))
        self.assertEqual(driver.budgets[0]["expired_budgets"],["active_wall"])
        driver.interact.assert_not_called()

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


    def test_restore_requires_exact_boolean_saved_audio_preference(self):
        for muted in (True, False):
            expected = self.finished(audio_muted=muted)
            receipt = {**expected, "found": True}
            self.assertEqual(validate_restored(receipt, expected), receipt)
            for invalid in (not muted, None, 0, 1, "false"):
                with self.subTest(muted=muted, invalid=invalid), self.assertRaises(ValueError):
                    validate_restored({**receipt, "audio_muted": invalid}, expected)
            for target in ("receipt", "expected"):
                broken_receipt, broken_expected = dict(receipt), dict(expected)
                del (broken_receipt if target == "receipt" else broken_expected)["audio_muted"]
                with self.subTest(missing=target), self.assertRaises(ValueError):
                    validate_restored(broken_receipt, broken_expected)


class WaypointBudgetTests(unittest.TestCase):
    state = GameplayObserverTests.state

    def driver(self, samples, **options):
        return RouteDriver(lambda: samples, Mock(), Mock(), Mock(), Mock(),
                           **{"physics_timeout": 15, "absolute_wall_timeout": 240, **options})

    def test_browser_snapshot_settling_preserves_physics_deadline(self):
        self.check_snapshot_budget_expiry('physics')

    def test_browser_snapshot_settling_preserves_absolute_wall_deadline(self):
        self.check_snapshot_budget_expiry('absolute_wall')

    def check_snapshot_budget_expiry(self, kind):
        # Same paired options as the actual browser RouteDriver, not native defaults.
        clock=[0.0];initial=self.state(locomotion='swim',water_depth=1.2)
        samples=[initial];driver=self.driver(samples)
        def advance(_):
            clock[0]=1 if kind=='physics' else 240
            samples.append(self.state(sample_id=2,physics_frame=960 if kind=='physics' else 73,
                                      locomotion='swim',water_depth=1.2,velocity=[1.,0.,0.]))
        driver.pause.side_effect=advance
        with patch('gameplay.time.monotonic',side_effect=lambda:clock[0]):
            budget=driver.begin_waypoint_budget(ROUTE[5],initial)
            with self.assertRaisesRegex(TimeoutError,kind):driver.settled_snapshot_state(initial)
        self.assertEqual((budget['physics_frame_deadline'],budget['absolute_wall_deadline']),(960,240))
        self.assertEqual(budget['expired_budgets'],[kind])
        driver.snapshot.assert_not_called()
        self.assertNotIn('settled',driver.snapshot_stops[-1])

    def test_entry_escape_consumes_existing_southeast_budget_without_renewal(self):
        clock=[0.0];entry=self.state(quest_stage=1,position=[1.3065,.5488,8.37065])
        driver=self.driver([entry]);driver.samples=[entry];driver.map_entry=entry;driver.accepted_stage=1
        with patch('gameplay.time.monotonic',side_effect=lambda:clock[0]):
            budget=driver.begin_waypoint_budget(ROUTE[1],entry)
            clock[0]=239
            driver.begin_chart_corridor()
            clear={**entry,'sample_id':2,'physics_frame':73,'position':[1.3065,.5488,8.6]}
            driver.chart_corridor.observe(clear)
            driver.check_waypoint_budget(clear)
            self.assertFalse(driver.chart_corridor.escaping)
            self.assertIs(driver.active_budget,budget)
            self.assertEqual(len(driver.budgets),1)
            clock[0]=240
            with self.assertRaisesRegex(TimeoutError,'absolute_wall'):driver.check_waypoint_budget(clear)
        self.assertEqual(budget['waypoint'],ROUTE[1]['name'])
        self.assertEqual((budget['physics_frame_deadline'],budget['absolute_wall_deadline']),(960,240))

    def test_profiles_are_finite_paired_and_bounded(self):
        for bad in (0, -1, True, float("nan"), float("inf"), "15"):
            for field in ("timeout", "physics_timeout", "absolute_wall_timeout"):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    self.driver([self.state()], **{field: bad})
        for options in ({"physics_timeout": 15.1}, {"absolute_wall_timeout": 241},
                        {"physics_timeout": None}, {"absolute_wall_timeout": None}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.driver([self.state()], **options)
        self.assertEqual(self.driver([]).budget_policy["physics_limit_seconds"], 15)
        self.assertEqual(self.driver([]).budget_policy["absolute_wall_limit_seconds"], 240)

    def test_native_default_retains_75_active_wall_seconds_and_ignores_physics_cap(self):
        clock, initial = [0.0], self.state()
        driver = self.driver([initial], physics_timeout=None, absolute_wall_timeout=None)
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]):
            driver.begin_waypoint_budget(ROUTE[0], initial)
            driver.capture_seconds = 10
            clock[0] = 80
            driver.check_waypoint_budget(self.state(sample_id=2, physics_frame=9060))
            clock[0] = 85
            with self.assertRaisesRegex(RuntimeError, "active_wall"):
                driver.check_waypoint_budget(self.state(sample_id=2, physics_frame=9060))
        self.assertEqual(driver.budgets[0]["expired_budgets"], ["active_wall"])

    def test_fresh_observations_never_renew_either_deadline(self):
        clock, initial = [0.0], self.state()
        driver = self.driver([initial])
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]):
            budget = driver.begin_waypoint_budget(ROUTE[0], initial)
            for index, (wall, frame) in enumerate(((30, 120), (80, 180), (120, 600)), start=2):
                clock[0] = wall
                driver.check_waypoint_budget(self.state(sample_id=index, physics_frame=frame))
                self.assertEqual((budget["absolute_wall_deadline"], budget["physics_frame_deadline"]), (240, 960))
            clock[0] = 130
            with self.assertRaisesRegex(TimeoutError, "physics"):
                driver.check_waypoint_budget(self.state(sample_id=5, physics_frame=960))
        self.assertEqual(budget["expired_budgets"], ["physics"])

    def test_slow_valid_stop_and_action_can_finish_beyond_old_wall_budget(self):
        initial = self.state(position=[1.3, 1, 7.8])
        samples, clock = [initial], [0.0]
        driver = self.driver(samples)
        driver.snapshot.side_effect = [None, RuntimeError("accepted checkpoint captured")]
        def pause(_):
            clock[0] += 80 if len(samples) == 1 else 1
            if len(samples) == 1:
                samples.append({**initial, "sample_id": 2, "physics_frame": 72})
        driver.pause = pause
        driver.interact.side_effect = lambda state: samples.append(
            {**state, "sample_id": 3, "physics_frame": 84, "quest_stage": 1})
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), \
                patch("gameplay.ROUTE", [{**ROUTE[0], "screenshot": "checkpoint.png"}]), \
                self.assertRaisesRegex(RuntimeError, "accepted checkpoint captured"):
            driver.run()
        driver.interact.assert_called_once()
        self.assertEqual(driver.budgets[0]["status"], "completed")
        self.assertGreater(driver.budgets[0]["elapsed_wall_seconds"], 75)
        self.assertLess(driver.budgets[0]["elapsed_physics_seconds"], 15)

    def test_budget_baseline_drains_observations_after_preceding_screenshot(self):
        samples, clock = [self.state()], [0.0]
        driver = self.driver(samples)
        def screenshot(name, _):
            if name == "tidal-01.png":
                clock[0] = 80
                samples.append(self.state(sample_id=2, physics_frame=1200))
            else:
                raise RuntimeError("checkpoint captured")
        driver.snapshot.side_effect = screenshot
        point = {"name": "already reached path point", "target": [1.3, 10], "screenshot": "checkpoint.png"}
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [point]), \
                self.assertRaisesRegex(RuntimeError, "checkpoint captured"):
            driver.run()
        budget = driver.budgets[0]
        self.assertEqual((budget["baseline_sample_id"], budget["baseline_physics_frame"]), (2, 1200))
        self.assertEqual((budget["absolute_wall_deadline"], budget["physics_frame_deadline"]), (320, 2100))
        self.assertEqual(budget["elapsed_physics_frames"], 0)

    def test_frozen_observations_still_fail_the_ten_second_silence_guard(self):
        samples, clock = [self.state()], [0.0]
        driver = self.driver(samples)
        driver.pause = lambda _: clock.__setitem__(0, clock[0] + 1)
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [ROUTE[0]]), \
                self.assertRaisesRegex(RuntimeError, "observations stopped advancing"):
            driver.run()
        self.assertEqual(driver.budgets[0]["status"], "failed")
        self.assertEqual(driver.budgets[0]["expired_budgets"], [])
        self.assertLess(driver.budgets[0]["elapsed_wall_seconds"], 240)
        driver.interact.assert_not_called()

    def test_moving_physics_without_spatial_progress_expires_simulation_budget(self):
        samples, clock = [self.state()], [0.0]
        driver = self.driver(samples)
        def pause(_):
            clock[0] += .1
            previous = samples[-1]
            samples.append({**previous, "sample_id": previous["sample_id"] + 1,
                            "physics_frame": previous["physics_frame"] + 60})
        driver.pause = pause
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [ROUTE[0]]), \
                self.assertRaisesRegex(TimeoutError, "physics"):
            driver.run()
        self.assertEqual(driver.budgets[0]["expired_budgets"], ["physics"])
        self.assertEqual(driver.budgets[0]["elapsed_physics_frames"], 900)
        driver.interact.assert_not_called()

    def test_absolute_wall_limit_counts_capture_time_and_preserves_failure_receipts(self):
        samples, clock = [self.state()], [0.0]
        driver = self.driver(samples)
        def move(direction):
            if direction != (0, 0) and len(samples) == 1:
                samples.append(self.state(sample_id=2, physics_frame=72, locomotion="wade", water_depth=.2))
        def screenshot(name, _):
            if name == "tidal-03.png":
                clock[0] += 241
                samples.append(self.state(sample_id=5, physics_frame=108, locomotion="wade", water_depth=.2))
        driver.move.side_effect, driver.snapshot.side_effect = move, screenshot
        def settle(_):
            if 2 <= samples[-1]["sample_id"] < 4:
                number=samples[-1]["sample_id"]+1
                samples.append(self.state(sample_id=number,physics_frame=48+number*12,locomotion="wade",water_depth=.2))
        driver.pause.side_effect=settle
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [ROUTE[0]]), \
                self.assertRaisesRegex(TimeoutError, "absolute_wall"):
            driver.run()
        diagnostics = route_diagnostics(driver)
        budget = diagnostics["waypoint_budgets"][0]
        self.assertEqual(budget["expired_budgets"], ["absolute_wall"])
        self.assertEqual(budget["measured_capture_seconds"], 241)
        self.assertEqual(budget["elapsed_active_wall_seconds"], 0)
        self.assertEqual(diagnostics["current_waypoint"], ROUTE[0]["name"])
        self.assertIn("physical_stops", diagnostics)
        self.assertIn("current_stop", diagnostics)
        driver.interact.assert_not_called()

    def test_stop_callback_overrun_fails_before_action_and_retains_stop(self):
        initial = self.state(position=[1.3, 1, 7.8])
        samples, clock = [initial], [0.0]
        driver = self.driver(samples)
        def move(_):
            if len(samples) == 1:
                clock[0] = 240
                samples.append({**initial, "sample_id": 2, "physics_frame": 72})
        driver.move.side_effect = move
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [ROUTE[0]]), \
                self.assertRaisesRegex(TimeoutError, "absolute_wall"):
            driver.run()
        diagnostics = route_diagnostics(driver)
        self.assertEqual(diagnostics["current_stop"]["after_sample_id"], 2)
        self.assertEqual(len(diagnostics["physical_stops"]), 1)
        self.assertEqual(diagnostics["waypoint_budgets"][0]["expired_budgets"], ["absolute_wall"])
        driver.interact.assert_not_called()

    def test_action_callback_cannot_complete_after_simulation_deadline(self):
        initial = self.state(position=[1.3, 1, 7.8])
        samples, clock = [initial], [0.0]
        driver = self.driver(samples)
        def pause(_):
            clock[0] += .1
            if len(samples) == 1:
                samples.append({**initial, "sample_id": 2, "physics_frame": 72})
        driver.pause = pause
        driver.interact.side_effect = lambda state: samples.append(
            {**state, "sample_id": 3, "physics_frame": 960, "quest_stage": 1})
        with patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), patch("gameplay.ROUTE", [ROUTE[0]]), \
                self.assertRaisesRegex(TimeoutError, "physics"):
            driver.run()
        driver.interact.assert_called_once()
        self.assertEqual(driver.budgets[0]["status"], "expired")
        self.assertEqual(driver.milestones, [])

    def test_malformed_frames_fail_before_any_budget_acceptance(self):
        for bad in (True, 0, 72.5, float("nan"), float("inf")):
            samples, clock = [self.state()], [0.0]
            driver = self.driver(samples)
            driver.move.side_effect = lambda _, value=bad: samples.append(self.state(sample_id=2, physics_frame=value)) if len(samples) == 1 else None
            with self.subTest(frame=bad), patch("gameplay.time.monotonic", side_effect=lambda: clock[0]), \
                    patch("gameplay.ROUTE", [ROUTE[0]]), self.assertRaises(ValueError):
                driver.run()
            self.assertEqual(driver.budgets[0]["status"], "failed")
            driver.interact.assert_not_called()


class AuthoringBoundaryTests(unittest.TestCase):
    def response(self, **changes):
        sample = {"schema": 1, "scanning": False, "process_frame": 42,
                  "types": {"res://swim_controller.gd": "GDScript"}}
        sample.update(changes)
        return {"success": True, "context": {"executed": True, "result": sample}}

    def test_initial_editor_scan_excludes_uncreated_dependencies_and_regression_fixtures(self):
        initial = set(initial_copy_files())
        self.assertFalse(initial & {"main.gd", "swim_controller.gd", "tide_audio.gd", "tide_interface.gd", "start.tscn", "project.godot", "water.gdshader", *DEFERRED_TEST_FILES})
        self.assertEqual(set(DEFERRED_TEST_FILES), {"verify_swimming.gd", "verify_treasure.gd", "verify_collision.gd", "verify_audio.gd", "verify_story.gd"})
        self.assertTrue(set(DEFERRED_TEST_FILES).issubset(GAME_FILES))
        self.assertEqual(initial | {"main.gd", "swim_controller.gd", "tide_audio.gd", "tide_interface.gd", "start.tscn", "project.godot", "water.gdshader", *DEFERRED_TEST_FILES}, set(GAME_FILES))
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
                 "completed": True, "position": [0, 4, -12], "language": "en", "audio_muted": True, "persistent": True, "reason": "exit"}
        receipt = {"schema": 1, "code": 0, "requested": True, "trusted": True,
                   "ok": True, "save_after_request": True, "saved": saved, "audio_closed": True}
        self.assertEqual(validate_web_exit(receipt, saved), saved)
        for changes in ({"code": True}, {"code": 1}, {"ok": False}, {"audio_closed": False}, {"audio_closed": None}, {"trusted": False},
                        {"requested": False}, {"save_after_request": False}, {"saved": None},
                        {"saved": {**saved, "persistent": False}},
                        {"saved": {**saved, "reason": "auto"}},
                        {"saved": {**saved, "audio_muted": False}},
                        {"saved": {**saved, "audio_muted": 1}},
                        {"saved": {**saved, "quest_stage": 3}},
                        {"saved": {**saved, "position": [10, 4, 0]}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_web_exit({**receipt, **changes}, saved)

    def test_public_web_exit_callbacks_fail_closed(self):
        subprocess.run(["node", str(Path(__file__).with_name("test_web_exit.js"))], check=True,
                       capture_output=True, text=True, timeout=10)

    def test_required_screenshot_timeout_is_finite_and_errors_are_not_masked(self):
        page = Mock()
        session = page.context.new_cdp_session.return_value
        png = b"\x89PNG\r\n\x1a\nfixture"
        with tempfile.TemporaryDirectory() as directory, patch("capture_browser.bounded_cdp") as send:
            send.side_effect = lambda session, method, params=None, timeout=120: {"data": base64.b64encode(png).decode()} if method != "detach" else None
            path = Path(directory) / "actual.png"
            receipt = capture_png(page, path)
            self.assertEqual(send.call_args_list[0].args, (session, "Page.captureScreenshot", {"format": "png", "fromSurface": True, "captureBeyondViewport": False}))
            self.assertEqual(send.call_args_list[0].kwargs, {"timeout": 120})
            page.screenshot.assert_not_called()
            page.evaluate.assert_not_called()
            self.assertEqual(path.read_bytes(), png)
            self.assertEqual(receipt["timeout_seconds"], 120)
            self.assertFalse(receipt["diagnostic"])
            send.reset_mock()
            capture_png(page, path, diagnostic=True)
            self.assertEqual(send.call_args_list[0].kwargs, {"timeout": 30})
            send.side_effect = [TimeoutError("capture failed"), None]
            with self.assertRaisesRegex(TimeoutError, "capture failed"):
                capture_png(page, path)
            send.side_effect = [TimeoutError("capture failed"), RuntimeError("detach failed")]
            with self.assertRaisesRegex(RuntimeError, "capture failed; CDP cleanup also failed: detach failed"):
                capture_png(page, path)
            send.side_effect = [{"data": base64.b64encode(b"not PNG").decode()}, None]
            with self.assertRaisesRegex(ValueError, "PNG"):
                capture_png(page, path)

    def test_passive_evaluation_invokes_functions_without_browser_activation(self):
        page = Mock()
        with patch("capture_browser.bounded_cdp") as send:
            send.side_effect = [{"result": {"type": "boolean", "value": False}}, None]
            self.assertIs(passive_evaluate(page, "name => name", "quote\"\n"), False)
            session, method, args = send.call_args_list[0].args
            self.assertEqual(method, "Runtime.evaluate")
            self.assertEqual(args["expression"], '(name => name)("quote\\\"\\n")')
            self.assertIs(args["userGesture"], False)
            self.assertIs(args["returnByValue"], True)
            self.assertIs(args["awaitPromise"], True)
            self.assertEqual(args["timeout"], 120000)
            page.evaluate.assert_not_called()
            for response in ({"exceptionDetails": {"text": "rejected Promise"}}, {"result": {"type": "undefined"}}, {"result": {"type": "function"}}, {"result": {"unserializableValue": "NaN"}}):
                send.side_effect = [response, None]
                with self.subTest(response=response), self.assertRaises(RuntimeError):
                    passive_evaluate(page, "() => Promise.reject(new Error('rejected Promise'))")

    def test_cdp_deadline_uses_driver_timeout_and_next_call_works(self):
        class Session:
            def __init__(self):
                self._impl_obj = self
                self._channel = self
                self.calls = []
            def _sync(self, coroutine):
                return asyncio.run(coroutine)
            async def send(self, command, timeout_calculator, payload):
                self.calls.append((command, timeout_calculator({}), payload))
                if payload.get("method") == "hung":
                    raise TimeoutError("driver deadline")
                return {"ok": True}
        session = Session()
        with self.assertRaises(TimeoutError):
            bounded_cdp(session, "hung", timeout=.1)
        self.assertEqual(session.calls[0], ("send", 100., {"method": "hung", "params": {}}))
        self.assertEqual(bounded_cdp(session, "next", {"ok": True}), {"ok": True})
        bounded_cdp(session, "detach", timeout=5)
        self.assertEqual(session.calls[-1], ("detach", 5000, {}))
        for timeout in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                bounded_cdp(session, "next", timeout=timeout)

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
