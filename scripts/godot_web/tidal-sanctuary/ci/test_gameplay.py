"""Fail-closed unit fixtures, not claims that real input or rendering has passed."""
import copy
import unittest
from unittest.mock import Mock, patch
from common import GAME_FILES
from author_native import DEFERRED_TEST_FILES, EDITOR_PROBE_PATH, editor_idle_sample, initial_copy_files
from gameplay import (ROUTE, RouteDriver, complete, direction_to, keyboard_direction,
                      validate_progress, validate_restored, validate_state, validate_water_crossing)


class GameplayObserverTests(unittest.TestCase):
    def state(self, **changes):
        result = {"schema": 1, "sample_id": 1, "physics_frame": 60, "demo": False,
                  "position": [1.3, 1, 10], "locomotion": "walk", "water_depth": 0.0,
                  "camera_right": [1, 0], "camera_forward": [0, -1],
                  "action_rect": [1100, 620, 100, 40], "quest_stage": 0,
                  "treasures": [False, False], "completed": False, "language": "en"}
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
                 ("completed", 1), ("water_depth", float("nan")), ("water_depth", -1), ("language", "xx")]
        for field, value in cases:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_state(self.state(**{field: value}))
        for field in ("schema", "sample_id", "physics_frame", "demo", "position", "locomotion", "camera_right",
                      "camera_forward", "action_rect", "quest_stage", "treasures", "completed", "water_depth", "language"):
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
        driver.request_action(at_map, ROUTE[0])
        callback.assert_called_once_with(at_map)
        samples.append(self.at_stage(1, sample_id=2, physics_frame=72, position=[1.3, 1, 7.8]))
        driver.observe()
        self.assertEqual(driver.accepted_stage, 1)
        self.assertIsNone(driver.pending_action)
        self.assertEqual(driver.actions[0]["accepted_sample_id"], 2)
        # The same action cannot authorize a second, unrequested stage transition.
        samples.append(self.at_stage(2, sample_id=3, physics_frame=84, position=[1.3, 1, 7.8]))
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
        with self.assertRaisesRegex(ValueError, "away"):
            driver.request_action(initial, {**ROUTE[0], "target": [20, 20]})
        driver.request_action(initial, ROUTE[0])
        with self.assertRaisesRegex(ValueError, "predates"):
            driver.accept_progress(self.at_stage(1, position=[1.3, 1, 7.8]), initial)
        distant = self.at_stage(1, sample_id=2, physics_frame=180, position=[5, 1, 7.8])
        with self.assertRaisesRegex(ValueError, "interaction location"):
            driver.accept_progress(distant, initial)

    def test_failed_physical_callback_cannot_authorize_progress(self):
        initial = self.at_stage(0, position=[1.3, 1, 7.8])
        samples = [initial]
        driver = self.driver(samples, Mock(side_effect=RuntimeError("OS input failed")))
        driver.observe()
        with self.assertRaisesRegex(RuntimeError, "OS input failed"):
            driver.request_action(initial, ROUTE[0])
        samples.append(self.at_stage(1, sample_id=2, physics_frame=72, position=[1.3, 1, 7.8]))
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


if __name__ == "__main__":
    unittest.main()
