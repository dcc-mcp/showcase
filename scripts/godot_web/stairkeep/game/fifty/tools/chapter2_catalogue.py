"""New original fixed planar floor layouts 11–20, build-time use only.

SPDX-License-Identifier: MIT
All geometry and names are newly authored for this project. There are no
external maps, downloads, assets, dependencies, runtime random placements or
physically overlapping bridges. Coordinates are zero-based x-right/y-down.
Markers become ordinary floor plus stable-ID objects in the content builder.
The file contains explicit canonical rows; no map is carved at runtime.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import Any

MARKER_LEGEND = {
    "S": "safe spawn", "V": "down-stair adjacent to S",
    "U": "up-stair; floor 20 may use an authored signal endpoint",
    "G": "mandatory ordinary enemy", "i": "main attack pickup",
    "h": "main health pickup", "g": "main gold pickup",
    "e": "optional enemy", "N": "NPC", "K": "one yellow key",
    "H": "main yellow gate", "B": "main blue gate", "q": "quest event",
    "A": "optional yellow branch gate", "a": "reward behind A",
    "M": "finite shop",
}
COMMON_MARKERS = frozenset("SVUGihge")
EXTRA_MARKERS = {
    11: frozenset("NKAa"), 12: frozenset("Hq"), 13: frozenset("q"),
    14: frozenset("Bq"), 15: frozenset("HKAa"), 16: frozenset("NM"),
    17: frozenset("KqAa"), 18: frozenset("Hq"),
    19: frozenset("BKAaM"), 20: frozenset("Hq"),
}

CATALOGUE: tuple[dict[str, Any], ...] = ({'id': 11,
  'name': '回潮廊桥',
  'topology': 'two offset loop courts with unequal approaches',
  'grid': ('#################',
           '#################',
           '#################',
           '#...........G..U#',
           '#.###.###########',
           '#.#N..###########',
           '#.###.###########',
           '#.#K........#####',
           '#.###.#####.#####',
           '#....g#####.#####',
           '#####.#####.#####',
           '#####i#####.#####',
           '#####.#####.#####',
           '#####h......A..a#',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 12,
  'name': '折页书庭',
  'topology': 'three-rung ladder and side returns',
  'grid': ('#################',
           '#################',
           '#################',
           '#...........G.HU#',
           '#.###.#####.#####',
           '#.###.#####.#####',
           '#.###.#####.#####',
           '#....q......#####',
           '#.###.#####.#####',
           '#.###g#####.#####',
           '#.###.#####.#####',
           '#....i......#####',
           '#####.###########',
           '#####h......#####',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 13,
  'name': '双井环渠',
  'topology': 'outer canal and inner well ring',
  'grid': ('#################',
           '#...........#####',
           '#.#########.#####',
           '#.###.......G..U#',
           '#.###.#####.#####',
           '#.#.......#.#####',
           '#.#.#.###.#.#####',
           '#.#.#q###.#.#####',
           '#.#.#.###.#.#####',
           '#.#..g....#.#####',
           '#.###.#####.#####',
           '#.###i#####.#####',
           '#.###.#####.#####',
           '#....h......#####',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 14,
  'name': '偏轴风桥',
  'topology': 'small upper court and displaced lower court',
  'grid': ('#################',
           '#.....###########',
           '#.###.###########',
           '#.###.......G.BU#',
           '#.###.###########',
           '#.........#######',
           '#####.###.#######',
           '#####q#.....#####',
           '#####.#.###.#####',
           '#####g#.###.#####',
           '#####.#.###.#####',
           '#####i#.###.#####',
           '#####.#.###.#####',
           '#####h......#####',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 15,
  'name': '锁匣回路',
  'topology': 'perimeter circuit with a folded temptation spur',
  'grid': ('#################',
           '#################',
           '#################',
           '#...........G.HU#',
           '#.###.#####.#####',
           '#.#.......#.#####',
           '#.#.#.###.#.#####',
           '#.#K..###.#.#####',
           '#.#.#.###.#.#####',
           '#.#..g###.#.#####',
           '#.###.###.#.#####',
           '#.###i#...#.#####',
           '#.###.#####.#####',
           '#....h......A..a#',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 16,
  'name': '盐灯市廊',
  'topology': 'market perimeter with cross-stall loops',
  'grid': ('#################',
           '#################',
           '#################',
           '#...........G..U#',
           '#.###.#####.#####',
           '#.#N..#####.#####',
           '#.###.#####.#####',
           '#...........#####',
           '#.###.#####.#####',
           '#.#..g..###.#####',
           '#.#.#.#.###.#####',
           '#.#..i..###M#####',
           '#.###.#####.#####',
           '#....h......#####',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 17,
  'name': '回声栈桥',
  'topology': 'three staggered loop terraces on one plane',
  'grid': ('#################',
           '#.....###########',
           '#.###.###########',
           '#.###.......G..U#',
           '#.###.###########',
           '#.........#######',
           '###.#.###.#######',
           '###K.q###.#######',
           '###.#.###.#######',
           '###..g......#####',
           '#####.#.###.#####',
           '#####i#.###.#####',
           '#####.#.###.#####',
           '#####h......A..a#',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 18,
  'name': '横闸内海',
  'topology': 'horizontal theta channels with an offset crosslink',
  'grid': ('#################',
           '#...........#####',
           '#.#########.#####',
           '#.###.......G.HU#',
           '#.###.#####.#####',
           '#.###.#####.#####',
           '#...........#####',
           '#.###q#####.#####',
           '#.###.#####.#####',
           '#.###g#####.#####',
           '#.###.#####.#####',
           '#.###i#####.#####',
           '#.###.#####.#####',
           '#....h......#####',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 19,
  'name': '四向门集',
  'topology': 'four pocket courts around a central junction',
  'grid': ('#################',
           '#################',
           '#################',
           '#...#.......G.BU#',
           '#.#.#.###.#.#####',
           '#...#.###...#####',
           '###.#.###.#######',
           '#..K........#####',
           '###.#.###.#######',
           '#...#g###...#####',
           '#.#.#.###.#.#####',
           '#...#i###..M#####',
           '#####.#####.#####',
           '#####h......A..a#',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')},
 {'id': 20,
  'name': '折光镜台',
  'topology': 'nested return spiral with multiple ordinary shortcuts',
  'grid': ('#################',
           '#...........#####',
           '#.#########.#####',
           '#.#.........G.HU#',
           '#.###.###.#.#####',
           '#.#.....#.#.#####',
           '#.#.#.#.#.#.#####',
           '#.#.#q#.#.#.#####',
           '#.#.#.#.#.#.#####',
           '#.#.#g#...#.#####',
           '#.#.#.###.#.#####',
           '#.#..i....#.#####',
           '#.###.#####.#####',
           '#....h......#####',
           '#VS...###.#######',
           '##..#####e#######',
           '#################')})


def parse_markers(grid: Sequence[str]) -> dict[str, list[int]]:
    if not grid or not isinstance(grid[0], str) or not grid[0]:
        raise ValueError("A nonempty rectangular ASCII grid is required")
    width = len(grid[0])
    markers: dict[str, list[int]] = {}
    for y, row in enumerate(grid):
        if not isinstance(row, str) or len(row) != width:
            raise ValueError("Rows must have equal width")
        for x, char in enumerate(row):
            if char in "#.":
                continue
            if char not in MARKER_LEGEND or char in markers:
                raise ValueError(f"Unknown or duplicate marker {char!r}")
            markers[char] = [x, y]
    return markers


def resolve_layout(floor_id: int) -> dict[str, Any]:
    if isinstance(floor_id, bool) or not isinstance(floor_id, int) or not 11 <= floor_id <= 20:
        raise ValueError("Only authored floor IDs 11 through 20 are provided")
    source = CATALOGUE[floor_id - 11]
    rows = list(source["grid"])
    return {"id": source["id"], "name": source["name"],
            "topology": source["topology"], "grid": rows,
            "markers": parse_markers(rows)}


def _reach(grid: Sequence[str], start: tuple[int, int], blocked=()) -> set[tuple[int, int]]:
    blocked = set(blocked)
    if start in blocked:
        return set()
    width, height = len(grid[0]), len(grid)
    seen = {start}
    todo = deque([start])
    while todo:
        x, y = todo.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pos = (x + dx, y + dy)
            xx, yy = pos
            if (0 <= xx < width and 0 <= yy < height and grid[yy][xx] != "#"
                    and pos not in blocked and pos not in seen):
                seen.add(pos)
                todo.append(pos)
    return seen


def _shape_signature(grid: Sequence[str]) -> tuple[str, ...]:
    """Ignore all labels and canonicalize all eight D4 images of plain walls."""
    plain = tuple("".join("#" if c == "#" else "." for c in row) for row in grid)
    candidates = []
    for reflected in (False, True):
        image = tuple(row[::-1] for row in plain) if reflected else plain
        for _ in range(4):
            candidates.append(image)
            image = tuple("".join(row) for row in zip(*image[::-1]))
    return min(candidates)


def validate_catalogue(previous_grids: Sequence[Sequence[str]] | None = None) -> list[dict[str, Any]]:
    """Light geometry validation, not a combat budget or engine test.

    By default also reject D4-equivalent plain grids from the sibling original
    first-ten catalogue. Pass explicit prior grids to use another caller-owned
    catalogue without changing any source file.
    """
    if previous_grids is None:
        from layout_catalogue import LAYOUTS
        previous_grids = [item["grid"] for item in LAYOUTS]
    signatures = {_shape_signature(grid) for grid in previous_grids}
    summaries = []
    for floor_id in range(11, 21):
        layout = resolve_layout(floor_id)
        grid, markers = layout["grid"], layout["markers"]
        width, height = len(grid[0]), len(grid)
        if layout["id"] != floor_id or not (15 <= width <= 19 and 15 <= height <= 19):
            raise ValueError(f"Wrong floor identity or dimensions: {floor_id}")
        if set(markers) != set(COMMON_MARKERS | EXTRA_MARKERS[floor_id]):
            raise ValueError(f"Wrong marker inventory on floor {floor_id}")
        if any(c != "#" for c in grid[0] + grid[-1]) or any(r[0] != "#" or r[-1] != "#" for r in grid):
            raise ValueError(f"Open outer boundary on floor {floor_id}")
        start = tuple(markers["S"])
        walkable = {(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c != "#"}
        if _reach(grid, start) != walkable:
            raise ValueError(f"Disconnected cells on floor {floor_id}")
        if sum(abs(a - b) for a, b in zip(start, markers["V"])) != 1:
            raise ValueError(f"V must be adjacent to S on floor {floor_id}")
        if not any(grid[start[1] + dy][start[0] + dx] == "."
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            raise ValueError(f"No empty safe retreat next to S on floor {floor_id}")
        gates = [key for key in ("G", "H", "B") if key in markers]
        for key in gates:
            if tuple(markers["U"]) in _reach(grid, start, [tuple(markers[key])]):
                raise ValueError(f"Main {key} is bypassable on floor {floor_id}")
        before_main = _reach(grid, start, [tuple(markers[key]) for key in gates])
        for key in ("K", "N", "q", "i", "h", "g", "M"):
            if key in markers and tuple(markers[key]) not in before_main:
                raise ValueError(f"Required {key} is behind a main gate on floor {floor_id}")
        if "A" in markers:
            accessible = _reach(grid, start, [tuple(markers["A"])])
            if tuple(markers["a"]) in accessible or tuple(markers["U"]) not in accessible:
                raise ValueError(f"A must seal only its optional reward on floor {floor_id}")
        without_optional_enemy = _reach(grid, start, [tuple(markers["e"])])
        if any(tuple(pos) not in without_optional_enemy for key, pos in markers.items() if key != "e"):
            raise ValueError(f"Optional enemy blocks a required marker on floor {floor_id}")
        signature = _shape_signature(grid)
        if signature in signatures:
            raise ValueError(f"D4-equivalent unlabeled grid on floor {floor_id}")
        signatures.add(signature)
        edges = sum((x + dx, y + dy) in walkable for x, y in walkable
                    for dx, dy in ((1, 0), (0, 1)))
        cycles = edges - len(walkable) + 1
        if cycles < 2:
            raise ValueError(f"Floor {floor_id} needs at least two independent cycles")
        summaries.append({"id": floor_id, "name": layout["name"], "width": width,
                          "height": height, "walkable_cells": len(walkable),
                          "independent_cycles": cycles, "markers": markers,
                          "main_gate_cuts": gates, "all_cells_connected": True,
                          "unlabeled_D4_unique_against_prior": True,
                          "scope": "static planar geometry; no resource or engine claim"})
    return summaries


if __name__ == "__main__":
    import json
    print(json.dumps({"passed": True, "floors": validate_catalogue()},
                     ensure_ascii=False, indent=2))
