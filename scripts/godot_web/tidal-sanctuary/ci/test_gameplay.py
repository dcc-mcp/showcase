"""Fail-closed unit fixtures, not claims that real input or rendering has passed."""
import copy
import unittest
from common import GAME_FILES
from gameplay import (ROUTE, complete, direction_to, keyboard_direction,
                      validate_restored, validate_state, validate_water_crossing)


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
        for changes in ({"quest_stage": 3}, {"treasures": [True, False]}, {"completed": False}):
            self.assertFalse(complete(self.finished(**changes)))

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


if __name__ == "__main__":
    unittest.main()
