"""Stdlib geometry proposal tests, NOT Godot/50-floor/gameplay acceptance.

Run from any directory with Python >=3.10:
    python -B path/to/campaign/tests/test_d4_grid.py --output=new-report.json

The frozen 21-floor JSON is a read-only coordinate/reference/budget fixture.
No engine is launched and no combat formula, active state or save is copied.
Synthetic NPC/event schemas test only the explicit proposed Python adapter.
"""

from __future__ import annotations

import argparse
from collections import deque
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import time
import unittest

CAMPAIGN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAMPAIGN / "tools"))
from d4_grid import (D4, ELEMENTS, compose, dimensions, direction,
                     distinct_layout_choices, grid, inverse, point,
                     spatial_fingerprint, transform_layout, vector)

FIXTURE = CAMPAIGN / "data" / "levels21.json"
FIXTURE_SHA256 = "b11c41ed50566f0fcfc7c50f59641c987d29b249435ff08487ab17fd580550d1"


def synthetic():
    """Different-size floors, explicit world directions and stable ID triggers."""
    return {
        "initial_player": {"hp": 30, "atk": 10, "def": 4, "gold": 0,
                           "keys": {"yellow": 0}},
        "enemies": {"test_guard": {"hp": 12, "atk": 7, "def": 2, "gold": 8}},
        "shops": {"test_forge": {"offers": [{"id": "edge", "cost": 8, "amount": 2}]}},
        "variant_spawn_candidates": [[1, 3], [1, 2]],
        "floors": [
            {"id": 1, "grid": ["#######", "#..#..#", "#.....#", "#.....#", "#######"],
             "spawn": [1, 3], "safe_start_candidates": [[1, 3], [1, 2]],
             "topology": {"room_centers": {"a": [1, 1], "b": [5, 3]},
                          "edges": [["a", "b"]], "selector": [1, 0]},
             "objects": [
                 {"id": "key", "kind": "key", "pos": [2, 3], "type": "yellow", "amount": 1},
                 {"id": "door", "kind": "door", "pos": [3, 2], "type": "yellow"},
                 {"id": "guard", "kind": "enemy", "pos": [4, 2], "type": "test_guard"},
                 {"id": "sage", "kind": "npc", "pos": [1, 1], "facing": "north",
                  "direction_vector": [-1, 0], "dialogue": {"line": "A stable clue."},
                  "trigger": {"rect": {"min": [1, 1], "max": [2, 2]},
                              "direction_condition": {"mode": "approach", "vector": [1, 0]},
                              "effects": [{"kind": "reveal", "target_id": "secret"}]}},
                 {"id": "up", "kind": "stairs", "pos": [5, 1], "direction": "up",
                  "target": {"floor": 2, "pos": [1, 5], "object_id": "down"}}],
             "events": [{"id": "rune", "kind": "event", "pos": [5, 3],
                         "trigger": {"cells": [[4, 3], [5, 3]],
                                     "direction_condition": {"mode": "facing", "vector": [0, -1]}},
                         "effects": [{"kind": "open", "target_id": "door"}]}],
             "hidden_events": [{"id": "secret", "kind": "hidden_event", "pos": [4, 3],
                                "hidden": True, "path": [[4, 3], [5, 3]],
                                "requires": {"flag": "sage_spoken"}}],
             "checkpoints": [{"id": "entry_checkpoint", "kind": "checkpoint", "pos": [2, 1]}]},
            {"id": 2, "grid": ["#####", "#...#", "#.#.#", "#...#", "#.#.#", "#...#", "#####"],
             "spawn": [1, 5],
             "objects": [{"id": "down", "kind": "stairs", "pos": [1, 5], "direction": "down",
                          "target": {"floor": 1, "pos": [5, 1], "object_id": "up"}}],
             "restore_points": [{"id": "return_anchor", "kind": "restore_point", "pos": [3, 3],
                                 "requires": {"event_id": "rune"}}]},
        ]}


def object_index(layout):
    return {item["id"]: (floor["id"], item)
            for floor in layout["floors"]
            for key in ("objects", "events", "hidden_events", "checkpoints", "restore_points")
            for item in floor.get(key, [])}


def open_cells(rows):
    return {(x, y) for y, row in enumerate(rows)
            for x, tile in enumerate(row) if tile != "#"}


def adjacency(rows):
    cells = open_cells(rows)
    return {(a, b) for a in cells for b in
            ((a[0] + 1, a[1]), (a[0] - 1, a[1]),
             (a[0], a[1] + 1), (a[0], a[1] - 1)) if b in cells}


def shortest(rows, start, finish, blocked=frozenset()):
    cells = open_cells(rows) - set(blocked)
    queue = deque([(start, 0)])
    seen = {start}
    while queue:
        current, steps = queue.popleft()
        if current == finish:
            return steps
        for next_cell in ((current[0] + 1, current[1]), (current[0] - 1, current[1]),
                          (current[0], current[1] + 1), (current[0], current[1] - 1)):
            if next_cell in cells and next_cell not in seen:
                seen.add(next_cell)
                queue.append((next_cell, steps + 1))
    return None


class GeometryProperties(unittest.TestCase):
    def test_known_clockwise_and_reflection_coordinates(self):
        self.assertEqual(point((0, 0), 3, 5, D4.ROT90), (4, 0))
        self.assertEqual(point((2, 4), 3, 5, D4.ROT90), (0, 2))
        self.assertEqual(point((0, 0), 3, 5, D4.MIRROR_X), (2, 0))
        self.assertEqual(grid(["abc", "def"], D4.ROT90), ["da", "eb", "fc"])
        self.assertEqual(vector((1, 0), D4.ROT90), (0, 1))
        self.assertEqual(direction("north", D4.ROT90), "east")

    def test_bijection_inverse_all_cells_non_square(self):
        for transform in ELEMENTS:
            width, height = dimensions(3, 5, transform)
            mapped = {point((x, y), 3, 5, transform) for y in range(5) for x in range(3)}
            self.assertEqual(mapped, {(x, y) for y in range(height) for x in range(width)})
            for y in range(5):
                for x in range(3):
                    target = point((x, y), 3, 5, transform)
                    self.assertEqual(point(target, width, height, inverse(transform)), (x, y))
            self.assertIs(compose(transform, inverse(transform)), D4.IDENTITY)

    def test_closure_and_associativity(self):
        for before in ELEMENTS:
            width, height = dimensions(3, 5, before)
            for after in ELEMENTS:
                combined = compose(after, before)
                self.assertIn(combined, ELEMENTS)
                for cell in ((0, 0), (1, 2), (2, 4)):
                    self.assertEqual(point(point(cell, 3, 5, before), width, height, after),
                                     point(cell, 3, 5, combined))
                for last in ELEMENTS:
                    self.assertIs(compose(last, combined), compose(compose(last, after), before))

    def test_distances_and_adjacency_graph(self):
        rows = ["#####", "#...#", "#.#.#", "#...#", "###.#", "#...#", "#####"]
        cells = sorted(open_cells(rows))
        for transform in ELEMENTS:
            mapped = grid(rows, transform)
            transform_cell = lambda cell: point(cell, 5, 7, transform)
            self.assertEqual({(transform_cell(a), transform_cell(b)) for a, b in adjacency(rows)},
                             adjacency(mapped))
            for a in cells:
                for b in cells:
                    x, y = transform_cell(a), transform_cell(b)
                    self.assertEqual(abs(a[0]-b[0]) + abs(a[1]-b[1]),
                                     abs(x[0]-y[0]) + abs(x[1]-y[1]))
                    self.assertEqual((a[0]-b[0])**2 + (a[1]-b[1])**2,
                                     (x[0]-y[0])**2 + (x[1]-y[1])**2)
            self.assertEqual(shortest(rows, (1, 1), (1, 5)),
                             shortest(mapped, transform_cell((1, 1)), transform_cell((1, 5))))

    def test_direction_condition_and_reflection_handedness(self):
        directions = ((1, 0), (-1, 0), (0, 1), (0, -1))
        for transform in ELEMENTS:
            for actual in directions:
                for required in directions:
                    # Facing/approach equality and dot conditions commute with D4.
                    a, b = vector(actual, transform), vector(required, transform)
                    self.assertEqual(actual == required, a == b)
                    self.assertEqual(sum(x*y for x, y in zip(actual, required)),
                                     sum(x*y for x, y in zip(a, b)))
            east, south = vector((1, 0), transform), vector((0, 1), transform)
            cross = east[0]*south[1] - east[1]*south[0]
            self.assertEqual(cross, -1 if "mirror" in transform.value else 1)
        with self.assertRaises(ValueError):
            direction("up", D4.ROT90)


class LayoutProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = FIXTURE.read_bytes()
        if sha256(raw).hexdigest() != FIXTURE_SHA256:
            raise AssertionError("Frozen 21-floor fixture bytes changed")
        cls.canonical = json.loads(raw)

    def test_frozen_fixture_counts(self):
        self.assertEqual(len(self.canonical["floors"]), 21)
        self.assertEqual(len(object_index(self.canonical)), 410)

    def test_frozen_roundtrip_all_eight_and_budget_identity(self):
        before = deepcopy(self.canonical)
        source_index = object_index(before)
        for transform in ELEMENTS:
            actual = transform_layout(before, transform)
            self.assertEqual(transform_layout(actual, inverse(transform)), before)
            for key in ("initial_player", "enemies", "shops", "validated_routes", "witness_routes"):
                self.assertEqual(actual[key], before[key])
            for stable_id, (floor_id, item) in object_index(actual).items():
                original = source_index[stable_id][1]
                self.assertEqual(floor_id, source_index[stable_id][0])
                self.assertEqual({key: value for key, value in item.items()
                                  if key not in {"pos", "target"}},
                                 {key: value for key, value in original.items()
                                  if key not in {"pos", "target"}})
            self.assertEqual(before, self.canonical)

    def test_frozen_all_cells_objects_topology_and_graph(self):
        for transform in ELEMENTS:
            actual = transform_layout(self.canonical, transform)
            for original, mapped in zip(self.canonical["floors"], actual["floors"]):
                width, height = len(original["grid"][0]), len(original["grid"])
                convert = lambda cell: point(cell, width, height, transform)
                self.assertEqual({(convert(a), convert(b)) for a, b in adjacency(original["grid"])},
                                 adjacency(mapped["grid"]))
                self.assertEqual(mapped["spawn"], list(convert(original["spawn"])))
                for old, new in zip(original["objects"], mapped["objects"]):
                    self.assertEqual(new["pos"], list(convert(old["pos"])))
                for room_id, cell in original["topology"]["room_centers"].items():
                    self.assertEqual(mapped["topology"]["room_centers"][room_id], list(convert(cell)))
                for field in ("edges", "selector", "main_path", "choice_rooms", "bonus_leaves"):
                    self.assertEqual(mapped["topology"].get(field), original["topology"].get(field))

    def test_safe_start_candidate_order_alias_and_safety(self):
        source = self.canonical["floors"][0]
        self.assertEqual(len(source["safe_start_candidates"]), 4)
        for transform in ELEMENTS:
            actual = transform_layout(self.canonical, transform)
            floor = actual["floors"][0]
            expected = [list(point(cell, 13, 13, transform)) for cell in source["safe_start_candidates"]]
            self.assertEqual(floor["safe_start_candidates"], expected)
            self.assertEqual(actual["variant_spawn_candidates"], expected)
            blocked = {tuple(item["pos"]) for item in floor["objects"]}
            enemies = {tuple(item["pos"]) for item in floor["objects"] if item["kind"] == "enemy"}
            for candidate in map(tuple, expected):
                self.assertNotIn(candidate, blocked)
                self.assertEqual(floor["grid"][candidate[1]][candidate[0]], ".")
                self.assertTrue(all(abs(candidate[0]-enemy[0]) + abs(candidate[1]-enemy[1]) > 1
                                    for enemy in enemies))
                self.assertIsNotNone(shortest(floor["grid"], candidate, tuple(floor["spawn"]), blocked))

    def test_independent_floor_transforms_and_bidirectional_stair_ids(self):
        fixture = synthetic()
        for first in ELEMENTS:
            for second in ELEMENTS:
                transformed = transform_layout(fixture, {1: first, 2: second})
                index = object_index(transformed)
                for stable_id in ("up", "down"):
                    floor_id, stair = index[stable_id]
                    target_floor, target = index[stair["target"]["object_id"]]
                    self.assertEqual(stair["target"]["floor"], target_floor)
                    self.assertEqual(stair["target"]["pos"], target["pos"])
                    self.assertEqual(target["target"]["object_id"], stable_id)
                    self.assertEqual(target["target"]["pos"], stair["pos"])
                    self.assertEqual(stair["direction"], "up" if floor_id == 1 else "down")
                self.assertEqual(transform_layout(transformed, {1: inverse(first), 2: inverse(second)}),
                                 fixture)

    def test_npc_hidden_events_conditions_and_restore_ids(self):
        fixture = synthetic()
        for transform in ELEMENTS:
            actual = transform_layout(fixture, transform)
            index = object_index(actual)
            sage = index["sage"][1]
            self.assertEqual(sage["facing"], direction("north", transform))
            self.assertEqual(sage["direction_vector"], list(vector((-1, 0), transform)))
            self.assertEqual(sage["trigger"]["direction_condition"]["vector"],
                             list(vector((1, 0), transform)))
            covered = {point((x, y), 7, 5, transform) for x in (1, 2) for y in (1, 2)}
            rect = sage["trigger"]["rect"]
            self.assertEqual(covered, {(x, y) for x in range(rect["min"][0], rect["max"][0]+1)
                                      for y in range(rect["min"][1], rect["max"][1]+1)})
            self.assertEqual(index["rune"][1]["trigger"]["cells"],
                             [list(point(cell, 7, 5, transform)) for cell in ((4, 3), (5, 3))])
            self.assertEqual(index["secret"][1]["path"],
                             [list(point(cell, 7, 5, transform)) for cell in ((4, 3), (5, 3))])
            self.assertTrue(index["secret"][1]["hidden"])
            self.assertEqual(index["return_anchor"][1]["requires"], {"event_id": "rune"})
            self.assertEqual(sage["trigger"]["effects"], [{"kind": "reveal", "target_id": "secret"}])
            self.assertEqual(transform_layout(actual, inverse(transform)), fixture)

    def test_no_input_or_result_aliasing_and_fixed_floor_transform(self):
        fixture = synthetic()
        original = deepcopy(fixture)
        first = transform_layout(fixture, D4.ROT90)
        second = transform_layout(fixture, D4.ROT90)
        self.assertEqual(first, second)
        first["floors"][0]["objects"][0]["pos"][0] = 99
        first["enemies"]["test_guard"]["hp"] = 999
        self.assertEqual(fixture, original)
        self.assertEqual(second, transform_layout(original, D4.ROT90))

    def test_actual_symmetry_dedup_and_previous_equivalence_exclusion(self):
        # Distinct stable IDs on identical mirrored pickups must not create novelty.
        symmetric = {"floors": [{"id": 1, "grid": ["....."]*5, "spawn": [2, 2],
                                 "objects": [{"id": "a", "name": "West coins", "kind": "gold", "pos": [1, 2], "amount": 2},
                                             {"id": "b", "name": "East coins", "kind": "gold", "pos": [3, 2], "amount": 2}]}]}
        all_choices = distinct_layout_choices(symmetric)
        self.assertEqual(sorted(map(len, all_choices.equivalence_groups)), [4, 4])
        self.assertEqual(len(all_choices.representatives), 2)
        previous = transform_layout(symmetric, D4.MIRROR_X)
        choices = distinct_layout_choices(symmetric, previous_layout=previous)
        self.assertEqual(len(choices.representatives), 1)
        for transform in choices.representatives:
            self.assertNotEqual(spatial_fingerprint(transform_layout(symmetric, transform)),
                                spatial_fingerprint(previous))
        fully_symmetric = {"floors": [{"id": 1, "grid": ["....."]*5,
                                      "spawn": [2, 2], "objects": []}]}
        self.assertFalse(distinct_layout_choices(fully_symmetric).spatial_change_possible)
        impossible = distinct_layout_choices(fully_symmetric, previous_layout=fully_symmetric)
        self.assertEqual(impossible.representatives, ())
        self.assertFalse(impossible.spatial_change_possible)

    def test_frozen_actual_layout_choices_are_distinct(self):
        choices = distinct_layout_choices(self.canonical)
        fingerprints = {spatial_fingerprint(transform_layout(self.canonical, transform))
                        for transform in choices.representatives}
        self.assertEqual(len(fingerprints), len(choices.representatives))
        previous = transform_layout(self.canonical, D4.ROT90)
        excluded = distinct_layout_choices(self.canonical, previous_layout=previous)
        self.assertTrue(excluded.spatial_change_possible)
        for transform in excluded.representatives:
            self.assertNotEqual(spatial_fingerprint(transform_layout(self.canonical, transform)),
                                spatial_fingerprint(previous))

    def test_identical_monster_aliases_and_names_are_not_novel_encounters(self):
        fixture = {"enemies": {
            "opaque_a": {"name": "First", "hp": 10, "atk": 8, "def": 2, "gold": 3},
            "opaque_b": {"name": "Second", "hp": 10, "atk": 8, "def": 2, "gold": 3}},
            "floors": [{"id": 1, "grid": ["....."]*5, "spawn": [2, 2],
                        "objects": [{"id": "one", "name": "West", "kind": "enemy",
                                     "pos": [1, 2], "type": "opaque_a"},
                                    {"id": "two", "name": "East", "kind": "enemy",
                                     "pos": [3, 2], "type": "opaque_b"}]}]}
        reflected = transform_layout(fixture, D4.MIRROR_X)
        self.assertNotEqual(object_index(fixture)["one"][1]["pos"],
                            object_index(reflected)["one"][1]["pos"])
        self.assertEqual(spatial_fingerprint(fixture), spatial_fingerprint(reflected))
        choices = distinct_layout_choices(fixture, previous_layout=reflected)
        self.assertEqual(len(choices.representatives), 1)
        fixture["enemies"]["opaque_b"]["appearance"] = "declared-red-sprite"
        self.assertNotEqual(spatial_fingerprint(fixture),
                            spatial_fingerprint(transform_layout(fixture, D4.MIRROR_X)))
        unsupported = synthetic()
        unsupported["floors"][0]["objects"][3]["type"] = "unresolved-npc-script"
        with self.assertRaises(ValueError):
            distinct_layout_choices(unsupported)

    def test_invalid_geometry_and_unregistered_semantics_rejected(self):
        for bad in ((True, 0), (0.0, 1), (-1, 0), (7, 0)):
            with self.assertRaises(ValueError):
                point(bad, 7, 5, D4.ROT90)
        with self.assertRaises(ValueError):
            grid(["...", ".."], D4.ROT90)
        for change in (
            lambda layout: layout["floors"][0]["objects"][0].update(id="door"),
            lambda layout: layout["floors"][0]["objects"][0].update(pos=[3, 2]),
            lambda layout: layout["floors"][0]["objects"][-1]["target"].update(pos=[3, 3]),
            lambda layout: layout["floors"][0]["objects"][-1].update(direction="down"),
            lambda layout: layout.update(variant_spawn_candidates=[[1, 2], [1, 3]]),
            lambda layout: layout["floors"][0]["objects"][3].update(facing="left"),
            lambda layout: layout["floors"][0]["objects"][3].update(heading=90),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                direction_condition={"mode": "clockwise", "vector": [1, 0]}),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                effects=[{"kind": "teleport", "pos": [1, 1]}]),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                effects=[{"kind": "teleport", "coords": [1, 1]}]),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                effects=[{"kind": "set_flag", "coordinates": [1, 1]}]),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                effects=[{"kind": "teleport", "destination": [1, 1]}]),
            lambda layout: layout["floors"][0]["objects"][3].update(requires={"direction": "left"}),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                effects=[{"kind": "open", "target_id": [1, 1]}]),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                effects=[{"kind": "set_flag"}]),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                effects=[{"kind": "set_flag", "flag": "test", "value": 1}]),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(
                effects=[{"kind": "grant_key", "key": "yellow", "amount": True}]),
            lambda layout: layout["floors"][0]["objects"][3]["trigger"].update(mode="clockwise"),
            lambda layout: layout["floors"][0].update(trigger_cells=[[1, 1]]),
            lambda layout: layout["floors"][0].update(regions=[{"min": [1, 1], "max": [2, 2]}]),
            lambda layout: layout["floors"][0]["topology"].update(markers=[[1, 1]]),
        ):
            layout = synthetic()
            change(layout)
            with self.assertRaises(ValueError):
                transform_layout(layout, D4.IDENTITY)
            with self.assertRaises(ValueError):
                spatial_fingerprint(layout)
            with self.assertRaises(ValueError):
                distinct_layout_choices(synthetic(), previous_layout=layout)
        with self.assertRaises(ValueError):
            transform_layout(synthetic(), {1: D4.ROT90})
        with self.assertRaises(ValueError):
            transform_layout(synthetic(), {True: D4.ROT90, 2: D4.IDENTITY})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON report; refuses an existing file")
    parser.add_argument("--verbose", action="store_true")
    arguments = parser.parse_args()
    if arguments.output and arguments.output.exists():
        parser.error("output exists; prior evidence is never overwritten")
    captured = io.StringIO()
    began = time.perf_counter()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=captured, verbosity=2).run(suite)
    report = {
        "suite": "stairkeep-proposed-d4-geometry/v1", "passed": result.wasSuccessful(),
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "elapsed_ms": round((time.perf_counter()-began)*1000, 3),
        "helper_sha256": sha256((CAMPAIGN / "tools" / "d4_grid.py").read_bytes()).hexdigest(),
        "test_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": sha256(FIXTURE.read_bytes()).hexdigest(),
        "expected_fixture_sha256": FIXTURE_SHA256,
        "python": sys.version.split()[0], "test_output": captured.getvalue(),
        "scope": "Python stdlib geometry/reference/static-budget properties on frozen 21-floor data and synthetic proposed NPC/event schema.",
        "engine_integration_tested": False, "fifty_floor_content_generated": False,
        "fifty_floor_balance_tested": False, "save_or_respawn_policy_changed": False,
    }
    if arguments.output:
        with arguments.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    if arguments.verbose or not result.wasSuccessful():
        print(captured.getvalue(), end="")
    print(json.dumps({key: report[key] for key in
                      ("suite", "passed", "tests_run", "failures", "errors", "elapsed_ms")}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
