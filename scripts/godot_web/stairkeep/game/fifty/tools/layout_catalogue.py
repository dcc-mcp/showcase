"""Original fixed layouts for the authored floors 1–10.

This is build-time content, not a runtime random map generator.  Coordinates are
zero based, with x increasing right and y increasing down.  Every non-# cell is
walkable before object semantics are applied.  The builder replaces markers
with ordinary floor and creates the corresponding stable-ID objects.

All maps and names in this file were newly authored for this project.  No
external game maps, dialogue, assets, downloads or new dependencies are used.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import Any


MARKER_LEGEND = {
    "S": "safe landing/spawn; no persistent object",
    "V": "down-stair beside S; floor 1 keeps this cell empty",
    "U": "up-stair; floor 10 uses this as its authored-slice endpoint",
    "G": "mandatory ordinary enemy separating S from U",
    "K": "one yellow key",
    "i": "main-route attack pickup",
    "h": "main-route health pickup",
    "A": "yellow attack-branch door",
    "a": "attack-branch gem",
    "$": "attack-branch gold",
    "D": "yellow defense-branch door",
    "d": "defense-branch gem",
    "p": "defense-branch health pickup",
    "M": "finite-stock shop: floors 2, 5 and 8 only",
    "N": "original NPC: floors 1 and 7 only",
    "q": "quest token: floor 3 only",
    "B": "blue return-visit door: floor 5 only",
    "z": "reward behind the blue door: floor 5 only",
}

REQUIRED_MARKERS = frozenset("SVUGKihAa$Ddp")


# These are explicit canonical rows.  The upper branch chambers have sealed
# necks, while the exploration graph beneath them differs on every floor.
# G is a deliberate single-cell neck, making ordinary combat unavoidable on
# the route to U without adding an assumed boss to every tenth floor.
LAYOUTS: tuple[dict[str, Any], ...] = (
    {
        "id": 1,
        "name": "双环门厅",
        "topology": "two loops joined by the main spine",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "###.........###",
            "###.###.###.###",
            "###.###K###.###",
            "###.###.###.###",
            "###....i...N###",
            "#######.#######",
            "#######h#######",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
    {
        "id": 2,
        "name": "梳齿钟廊",
        "topology": "comb branches and an upper side loop",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "###.........###",
            "###.#.#.#######",
            "#M.....K......#",
            "###.###.###.###",
            "###...#i#...###",
            "###.###.###.###",
            "###.###h#######",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
    {
        "id": 3,
        "name": "水镜八庭",
        "topology": "offset figure-eight with a token spur",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "###.........###",
            "###.###.#######",
            "###.###K#######",
            "###.........###",
            "###.###i###.###",
            "###.###.###.###",
            "###q..#h....###",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
    {
        "id": 4,
        "name": "绞盘双桥",
        "topology": "barbell courts with parallel bridge connections",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "#.............#",
            "#.###.#.#.###.#",
            "#.###..K..###.#",
            "#.###.#.#.###.#",
            "#.....#i#.....#",
            "###.###.#######",
            "###....h#######",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
    {
        "id": 5,
        "name": "三渠档库",
        "topology": "three braided channels and a sealed return archive",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "###.........###",
            "###.###.###.###",
            "###....K....###",
            "###.###.###.###",
            "#B.....i...M###",
            "#.#####.#######",
            "#.#####h#######",
            "#.#####.#######",
            "#z####VS.######",
            "###############",
        ),
    },
    {
        "id": 6,
        "name": "回环机井",
        "topology": "perimeter circuit with an inner folded return",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "#.............#",
            "#.#####.#####.#",
            "#.#....K....#.#",
            "#.###.#.###.#.#",
            "#.###..i....#.#",
            "#.#####.#####.#",
            "#......h......#",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
    {
        "id": 7,
        "name": "错庭风站",
        "topology": "offset courts joined by a bent link",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "#...........###",
            "#.###.#.#######",
            "#......K..#####",
            "#######.#.#####",
            "#######i......#",
            "#######.#.###.#",
            "#######h#....N#",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
    {
        "id": 8,
        "name": "三径引线",
        "topology": "theta routes with a crossbar spur",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "#.............#",
            "#.#####.#####.#",
            "#.#####K#####.#",
            "#M#.........#.#",
            "#.#####i#####.#",
            "#.#####.#####.#",
            "#......h......#",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
    {
        "id": 9,
        "name": "四翼机杼",
        "topology": "central hub with four pocketed wings",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "###.........###",
            "#####.#.#.#####",
            "#...###K###...#",
            "#.............#",
            "#...###i###...#",
            "#####.....#####",
            "#####..h..#####",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
    {
        "id": 10,
        "name": "马蹄信台",
        "topology": "horseshoe perimeter with offset inner hooks",
        "grid": (
            "###############",
            "#a.$###U###d.p#",
            "###.###G###.###",
            "###.###.###.###",
            "###A###.###D###",
            "#.............#",
            "#.#####.#####.#",
            "#.#....K....#.#",
            "#.#####.###.#.#",
            "#.#.#..i#...#.#",
            "#.#.#.#.#####.#",
            "#......h......#",
            "#######.#######",
            "######VS.######",
            "###############",
        ),
    },
)


def parse_markers(grid: Sequence[str]) -> dict[str, list[int]]:
    """Read unique marker coordinates from explicit rectangular ASCII rows."""
    if not grid or not isinstance(grid[0], str) or not grid[0]:
        raise ValueError("A nonempty rectangular string grid is required")
    width = len(grid[0])
    markers: dict[str, list[int]] = {}
    for y, row in enumerate(grid):
        if not isinstance(row, str) or len(row) != width:
            raise ValueError("Grid rows must have equal width")
        for x, cell in enumerate(row):
            if cell in "#.":
                continue
            if cell not in MARKER_LEGEND:
                raise ValueError(f"Unknown marker {cell!r} at {[x, y]}")
            if cell in markers:
                raise ValueError(f"Duplicate marker {cell!r}")
            markers[cell] = [x, y]
    return markers


def resolve_layout(floor_id: int) -> dict[str, Any]:
    """Return a fresh build input; callers cannot mutate canonical row data."""
    if isinstance(floor_id, bool) or not isinstance(floor_id, int):
        raise ValueError("floor_id must be an integer from 1 through 10")
    if not 1 <= floor_id <= len(LAYOUTS):
        raise ValueError("Only authored floor IDs 1 through 10 exist")
    source = LAYOUTS[floor_id - 1]
    grid = list(source["grid"])
    return {
        "id": source["id"],
        "name": source["name"],
        "topology": source["topology"],
        "grid": grid,
        "markers": parse_markers(grid),
    }


def _reachable(grid: Sequence[str], start: tuple[int, int],
               blocked: tuple[int, int] | None = None) -> set[tuple[int, int]]:
    width, height = len(grid[0]), len(grid)
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cell = (x + dx, y + dy)
            xx, yy = cell
            if (0 <= xx < width and 0 <= yy < height and cell != blocked
                    and grid[yy][xx] != "#" and cell not in seen):
                seen.add(cell)
                queue.append(cell)
    return seen


def validate_catalogue() -> list[dict[str, Any]]:
    """Lightweight geometry checks only; no runtime or combat acceptance."""
    summaries: list[dict[str, Any]] = []
    shapes: set[tuple[str, ...]] = set()
    for expected_id, source in enumerate(LAYOUTS, 1):
        layout = resolve_layout(expected_id)
        grid, markers = layout["grid"], layout["markers"]
        width, height = len(grid[0]), len(grid)
        if layout["id"] != expected_id or not (11 <= width <= 15 and 11 <= height <= 15):
            raise ValueError(f"Invalid authored floor identity/dimensions: {expected_id}")
        expected = set(REQUIRED_MARKERS)
        if expected_id in (2, 5, 8):
            expected.add("M")
        if expected_id in (1, 7):
            expected.add("N")
        if expected_id == 3:
            expected.add("q")
        if expected_id == 5:
            expected.update(("B", "z"))
        if set(markers) != expected:
            raise ValueError(f"Wrong marker set on floor {expected_id}")
        if (any(cell != "#" for cell in grid[0] + grid[-1])
                or any(row[0] != "#" or row[-1] != "#" for row in grid)):
            raise ValueError(f"Unsealed outer boundary on floor {expected_id}")
        start = tuple(markers["S"])
        walkable = {(x, y) for y, row in enumerate(grid)
                    for x, cell in enumerate(row) if cell != "#"}
        if _reachable(grid, start) != walkable:
            raise ValueError(f"Disconnected walkable cells on floor {expected_id}")
        if sum(abs(a - b) for a, b in zip(start, markers["V"])) != 1:
            raise ValueError(f"Down-stair is not adjacent to S on floor {expected_id}")
        if not any(grid[start[1] + dy][start[0] + dx] == "."
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            raise ValueError(f"No ordinary safe retreat next to S on floor {expected_id}")
        gates = {"G": ("U",), "A": ("a", "$"), "D": ("d", "p")}
        if expected_id == 5:
            gates["B"] = ("z",)
        for gate, targets in gates.items():
            accessible = _reachable(grid, start, tuple(markers[gate]))
            if any(tuple(markers[target]) in accessible for target in targets):
                raise ValueError(f"Bypassable {gate} gate on floor {expected_id}")
        shape = tuple("".join("#" if cell == "#" else "." for cell in row)
                      for row in grid)
        if shape in shapes:
            raise ValueError(f"Repeated exploration geometry on floor {expected_id}")
        shapes.add(shape)
        edges = sum((x + dx, y + dy) in walkable for x, y in walkable
                    for dx, dy in ((1, 0), (0, 1)))
        summaries.append({
            "id": expected_id,
            "name": layout["name"],
            "width": width,
            "height": height,
            "walkable_cells": len(walkable),
            "independent_cycles": edges - len(walkable) + 1,
            "markers": markers,
            "all_cells_connected": True,
            "gate_cut_checks": list(gates),
        })
    return summaries


if __name__ == "__main__":
    import json
    print(json.dumps({"passed": True, "scope": "static original geometry only",
                      "floors": validate_catalogue()}, ensure_ascii=False, indent=2))
