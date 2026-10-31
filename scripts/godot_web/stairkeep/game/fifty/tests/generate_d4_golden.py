"""Generate geometry-only Godot golden data from the already tested Python oracle.

No engine, new runtime/schema adapter, campaign generation or combat is executed.
The synthetic two-floor stair/event payload deliberately uses only point/vector
operations. It does not claim the proposed Python schema supports fifty content.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ORACLE_SHA256 = "7b0c23aae35497dbe9988bb850513b1cf8b7a9a7600b68f4dba33ecc8d75070a"
PROPERTY_REPORT_SHA256 = "97b02b991e4a8be9542f6911a184f354767ac6af2c2f8cd7496e5f2009507bd6"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--python-properties", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Golden output must be new; existing evidence was not replaced")
    if digest(args.oracle) != ORACLE_SHA256 or digest(args.python_properties) != PROPERTY_REPORT_SHA256:
        raise SystemExit("The previously tested Python oracle/report bytes differ")
    properties = json.loads(args.python_properties.read_text(encoding="utf-8"))
    if not properties.get("passed") or properties.get("helper_sha256") != ORACLE_SHA256 or properties.get("tests_run") != 16:
        raise SystemExit("The bound report does not prove the expected 16 Python properties")
    spec = importlib.util.spec_from_file_location("stairkeep_reference_d4", args.oracle)
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load the exact source oracle")
    reference = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reference
    spec.loader.exec_module(reference)
    assert reference.point((0, 0), 3, 5, "rot90") == (4, 0)
    assert reference.point((2, 4), 3, 5, "rot90") == (0, 2)
    assert reference.grid(["abc", "def"], "rot90") == ["da", "eb", "fc"]
    elements = [item.value for item in reference.ELEMENTS]
    cardinal = {"north": [0, -1], "east": [1, 0], "south": [0, 1], "west": [-1, 0]}
    single = []
    for transform in elements:
        single.append({
            "transform": transform, "source_dimensions": [3, 5],
            "expected_dimensions": list(reference.dimensions(3, 5, transform)),
            "points": [{"source": [x, y], "expected": list(reference.point((x, y), 3, 5, transform))}
                       for y in range(5) for x in range(3)],
            "vectors": [{"source": vector, "expected": list(reference.vector(vector, transform))}
                        for vector in cardinal.values()],
            "directions": [{"source": direction, "expected": reference.direction(direction, transform)}
                           for direction in cardinal],
            "labelled_grid": {"source": ["abc", "def"], "expected": reference.grid(["abc", "def"], transform)},
            "inverse": reference.inverse(transform).value,
        })
    pairs = []
    for source_transform in elements:
        for target_transform in elements:
            upper_pos = list(reference.point([5, 1], 7, 5, source_transform))
            lower_pos = list(reference.point([1, 5], 5, 7, target_transform))
            pairs.append({
                "source_transform": source_transform, "target_transform": target_transform,
                "source_dimensions": [7, 5], "target_dimensions": [5, 7],
                "forward": {
                    "source": {"id": "golden_up", "floor": 1, "pos": [5, 1], "direction": "up", "target": {"floor": 2, "pos": [1, 5], "object_id": "golden_down"}},
                    "expected": {"id": "golden_up", "floor": 1, "pos": upper_pos, "direction": "up", "target": {"floor": 2, "pos": lower_pos, "object_id": "golden_down"}},
                },
                "reverse": {
                    "source": {"id": "golden_down", "floor": 2, "pos": [1, 5], "direction": "down", "target": {"floor": 1, "pos": [5, 1], "object_id": "golden_up"}},
                    "expected": {"id": "golden_down", "floor": 2, "pos": lower_pos, "direction": "down", "target": {"floor": 1, "pos": upper_pos, "object_id": "golden_up"}},
                },
                "source_event": {
                    "source": {"pos": [2, 3], "facing": "north", "direction_vector": [-1, 0], "direction_condition": {"mode": "approach", "vector": [1, 0]}},
                    "expected": {"pos": list(reference.point([2, 3], 7, 5, source_transform)), "facing": reference.direction("north", source_transform), "direction_vector": list(reference.vector([-1, 0], source_transform)), "direction_condition": {"mode": "approach", "vector": list(reference.vector([1, 0], source_transform))}},
                },
                "target_event": {
                    "source": {"pos": [3, 3], "facing": "west", "direction_vector": [0, 1], "direction_condition": {"mode": "facing", "vector": [0, -1]}},
                    "expected": {"pos": list(reference.point([3, 3], 5, 7, target_transform)), "facing": reference.direction("west", target_transform), "direction_vector": list(reference.vector([0, 1], target_transform)), "direction_condition": {"mode": "facing", "vector": list(reference.vector([0, -1], target_transform))}},
                },
            })
    result = {"schema_version": 1, "suite": "fifty_geometry_only_golden/v1", "oracle_sha256": ORACLE_SHA256,
              "python_properties_sha256": PROPERTY_REPORT_SHA256, "generator_sha256": digest(Path(__file__)),
              "coordinate_convention": "x right / y down; rot90 clockwise; reflection first, then named rotation",
              "elements": elements, "single_transform_cases": single, "crossfloor_pairs": pairs,
              "counts": {"elements": 8, "point_vectors": 120, "cardinal_vectors": 32, "compass_directions": 32, "crossfloor_transform_pairs": 64},
              "scope": "Exact geometry expectations from the existing tested Python point/vector/direction oracle. New runtime D4 functions must be independently checked by Godot. No new fifty schema support, content balance, engine acceptance or completed 50-floor content is implied.",
              "new_runtime_checked": False, "new_content_schema_checked": False}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"golden_generated": True, "counts": result["counts"], "sha256": digest(args.output), "output": str(args.output), "engine_started": False}))


if __name__ == "__main__":
    main()
