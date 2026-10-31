#!/usr/bin/env python3
"""Read-only, conditional initial-solvability certificates for recorded variants.

No engine, subprocess, combat formula, policy repair, source write or simulation.
An optional certificate is created exclusively; existing files are never replaced.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from copy import deepcopy
from datetime import datetime, timezone
import glob
import hashlib
import json
from pathlib import Path
import sys
import time

SPEC = "stairkeep-variant/xorshift32-hv-v1"
CERT_SPEC = "stairkeep-initial-layout-bijection/v1"
MASK = 0xFFFFFFFF
ZERO_SEED = 0x6D2B79F5
DRAW_COUNT = 43
FLOOR_COUNT = 21
DELTAS = ((-1, 0), (1, 0), (0, -1), (0, 1))
CAMPAIGN = Path(__file__).resolve().parents[1]
WORKSPACE = next((p for p in CAMPAIGN.parents if (p / "output").is_dir()), Path.cwd())


class InvalidEvidence(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidEvidence(message)


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), f"{path.name}: JSON root is not an object")
    return value, {"path": display_path(path), "sha256": sha_bytes(raw), "bytes": len(raw)}


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()
    except ValueError:
        return path.name


def normalize(value, field: str = ""):
    """Exact field normalization used by CampaignVariant.canonical_json.

    JSON.stringify's compact/sorted/integer representation is checked against
    all 100 recorded Godot layout hashes before a coverage certificate can pass.
    """
    if isinstance(value, dict):
        require(all(isinstance(k, str) for k in value), "Non-string JSON key")
        return {k: normalize(v, k) for k, v in value.items()}
    if isinstance(value, list):
        result = [normalize(v) for v in value]
        if field == "floors":
            result.sort(key=lambda item: int(item["id"]))
        elif field == "objects":
            result.sort(key=lambda item: item["id"])
        elif field in ("cleared", "cleared_object_ids"):
            result.sort()
        return result
    if isinstance(value, float):
        require(value.is_integer(), "Non-integral JSON number")
        return int(value)
    require(value is None or isinstance(value, (str, int, bool)), "Unsupported JSON value")
    return value


def compact(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_hash(value) -> str:
    return sha_bytes(compact(normalize(value)))


def normalize_seed(value) -> str:
    require(type(value) is int or isinstance(value, str), "Seed must be uint32 or 8 hex digits")
    if isinstance(value, str):
        require(len(value) == 8 and all(c in "0123456789abcdefABCDEF" for c in value), "Bad seed string")
        value = int(value, 16)
    require(0 <= value <= MASK, "Seed out of uint32 range")
    return f"{value or ZERO_SEED:08x}"


def next32(value: int) -> int:
    value = (value ^ ((value << 13) & MASK)) & MASK
    value = (value ^ (value >> 17)) & MASK
    return (value ^ ((value << 5) & MASK)) & MASK


def draws_for_seed(seed: str) -> tuple[list[int], dict[int, int], int]:
    current = int(normalize_seed(seed), 16)
    draws, flags = [], {}
    for floor_id in range(1, FLOOR_COUNT + 1):
        current = next32(current)
        draws.append(current)
        horizontal = bool(current & 1)
        current = next32(current)
        draws.append(current)
        # code bit 0 = horizontal; bit 1 = vertical
        flags[floor_id] = int(horizontal) | (int(bool(current & 1)) << 1)
    current = next32(current)
    draws.append(current)
    return draws, flags, current % 4


def transform(cell, width: int, height: int, code: int) -> list[int]:
    x, y = map(int, cell)
    return [width - 1 - x if code & 1 else x, height - 1 - y if code & 2 else y]


def walkable(floor: dict) -> set[tuple[int, int]]:
    return {(x, y) for y, row in enumerate(floor["grid"]) for x, c in enumerate(row) if c == "."}


def edges_of(cells: set[tuple[int, int]]) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    return {tuple(sorted(((x, y), (x + dx, y + dy)))) for x, y in cells
            for dx, dy in ((1, 0), (0, 1)) if (x + dx, y + dy) in cells}


def empty_path(floor: dict, start, goal) -> list[list[int]]:
    allowed = walkable(floor) - {tuple(o["pos"]) for o in floor["objects"]}
    start, goal = tuple(start), tuple(goal)
    require(start in allowed and goal in allowed, "Safe prefix occupies an object/wall")
    parent, queue = {start: None}, deque([start])
    while queue and goal not in parent:
        x, y = queue.popleft()
        for dx, dy in DELTAS:
            point = (x + dx, y + dy)
            if point in allowed and point not in parent:
                parent[point] = (x, y)
                queue.append(point)
    require(goal in parent, "Safe spawn cannot reach the reflected canonical start")
    result, point = [], goal
    while point is not None:
        result.append(list(point))
        point = parent[point]
    return list(reversed(result))


def same_object_attributes(source: dict, target: dict) -> bool:
    """All non-geometric fields, including future economic flags, must match."""
    if source.keys() != target.keys():
        return False
    for key, value in source.items():
        if key in ("pos", "facing"):
            continue
        if key == "target":
            if value.keys() != target[key].keys():
                return False
            if any(target[key][k] != v for k, v in value.items() if k != "pos"):
                return False
        elif target[key] != value:
            return False
    return True


class GeometryAudit:
    """84 finite local cases, then actual per-seed composition and stair audit."""

    def __init__(self, canonical: dict):
        self.canonical = canonical
        self.floors = sorted(canonical["floors"], key=lambda floor: int(floor["id"]))
        require([f["id"] for f in self.floors] == list(range(1, 22)), "Floor IDs must be 1..21")
        self.by_floor = {f["id"]: f for f in self.floors}
        self.by_object = {}
        for floor in self.floors:
            require(floor["grid"] and all(isinstance(row, str) and len(row) == len(floor["grid"][0])
                    and not (set(row) - {"#", "."}) for row in floor["grid"]), "Invalid rectangular grid")
            for field in ("markers", "trigger_cells", "interactive_areas", "regions"):
                require(not floor.get(field), f"Unsupported operative floor geometry: {field}")
            occupied = set()
            for item in floor["objects"]:
                require(item["id"] not in self.by_object, "Duplicate object ID")
                require(tuple(item["pos"]) in walkable(floor), "Object is not walkable")
                require(tuple(item["pos"]) not in occupied, "Overlapping object")
                for field in ("cells", "rect", "area", "trigger_cells"):
                    require(field not in item, f"Unsupported object geometry: {field}")
                occupied.add(tuple(item["pos"]))
                self.by_object[item["id"]] = (floor["id"], item)
        self.candidates = self.floors[0]["safe_start_candidates"]
        require(len(self.candidates) == 4, "Exactly four safe start candidates required")
        require(len({tuple(p) for p in self.candidates}) == 4, "Duplicate spawn candidate")
        require(canonical.get("variant_spawn_candidates", self.candidates) == self.candidates, "Spawn alias differs")
        self.cases, self.local_certificates = {}, []
        for floor in self.floors:
            for code in range(4):
                self._local_case(floor, code)
        self._stair_check({f["id"]: f for f in self.floors})
        self.static_root_parts = {
            key: compact(normalize(value, key)) for key, value in canonical.items()
            if key not in ("floors", "variant_spawn_candidates")
        }

    def _local_case(self, source: dict, code: int) -> None:
        n, height, width = source["id"], len(source["grid"]), len(source["grid"][0])
        case = deepcopy(source)
        case["grid"] = [row[::-1] if code & 1 else row for row in
                        (source["grid"][::-1] if code & 2 else source["grid"])]
        t = lambda cell: transform(cell, width, height, code)
        rectangle = {(x, y) for y in range(height) for x in range(width)}
        require({tuple(t(p)) for p in rectangle} == rectangle, "Mirror is not a rectangular bijection")
        require(all(t(t(p)) == list(p) for p in rectangle), "Mirror is not an involution")
        source_cells, target_cells = walkable(source), walkable(case)
        require({tuple(t(p)) for p in source_cells} == target_cells, "Walkable cells not preserved")
        mapped_edges = {tuple(sorted((tuple(t(a)), tuple(t(b))))) for a, b in edges_of(source_cells)}
        require(mapped_edges == edges_of(target_cells), "Grid adjacency not preserved in both directions")
        case["spawn"] = t(source["spawn"])
        if "safe_start_candidates" in source:
            case["safe_start_candidates"] = [t(p) for p in source["safe_start_candidates"]]
        for original, item in zip(source["objects"], case["objects"]):
            item["pos"] = t(original["pos"])
            if "facing" in item:
                item["facing"] = [-original["facing"][0] if code & 1 else original["facing"][0],
                                  -original["facing"][1] if code & 2 else original["facing"][1]]
            require(same_object_attributes(original, item), "Local non-geometric attributes changed")
        safe_prefixes = []
        if n == 1:
            for chosen in source["safe_start_candidates"]:
                prefix = empty_path(case, t(chosen), t(source["spawn"]))
                require(all(abs(t(chosen)[0] - item["pos"][0]) + abs(t(chosen)[1] - item["pos"][1]) > 1
                            for item in case["objects"] if item["kind"] == "enemy"), "Spawn adjacent to enemy")
                safe_prefixes.append({"chosen_canonical": chosen, "resolved": t(chosen), "empty_path": prefix})
        self.cases[(n, code)] = case
        self.local_certificates.append({
            "id": f"floor-{n:02d}-mirror-{code}", "floor": n, "mirror_code": code,
            "width": width, "height": height, "rectangle_cells": len(rectangle),
            "walkable_cells": len(source_cells), "undirected_walkable_edges": len(mapped_edges),
            "object_count": len(case["objects"]), "grid_bijection": True,
            "grid_adjacency_preserved": True, "object_attributes_preserved": True,
            "safe_spawn_prefixes": safe_prefixes,
        })

    def _stair_check(self, floors: dict[int, dict]) -> int:
        indexed = {item["id"]: (n, item) for n, floor in floors.items() for item in floor["objects"]}
        count = 0
        for n, floor in floors.items():
            for item in floor["objects"]:
                if item["kind"] != "stairs":
                    continue
                target = item["target"]
                require(target["object_id"] in indexed, "Missing stair target ID")
                destination_id, destination = indexed[target["object_id"]]
                require(destination_id == target["floor"] and destination["kind"] == "stairs"
                        and destination["pos"] == target["pos"], "Stair lands at wrong floor/position")
                require(destination["target"]["floor"] == n and destination["target"]["pos"] == item["pos"]
                        and destination["target"]["object_id"] == item["id"], "Stair link not reciprocal")
                require(item.get("direction") == ("up" if destination_id > n else "down"), "Bad stair direction")
                count += 1
        return count

    def variant(self, seed: str) -> dict:
        draws, flags, spawn_index = draws_for_seed(seed)
        floors = {n: deepcopy(self.cases[(n, flags[n])]) for n in range(1, 22)}
        for n, floor in floors.items():
            for item in floor["objects"]:
                _, original = self.by_object[item["id"]]
                require(same_object_attributes(original, item), "Per-seed economic/object identity changed")
                if item["kind"] == "stairs":
                    destination = self.by_floor[item["target"]["floor"]]
                    item["target"]["pos"] = transform(original["target"]["pos"], len(destination["grid"][0]),
                                                        len(destination["grid"]), flags[destination["id"]])
        first, original_first = floors[1], self.by_floor[1]
        first["spawn"] = transform(self.candidates[spawn_index], len(first["grid"][0]), len(first["grid"]), flags[1])
        canonical_start = transform(original_first["spawn"], len(first["grid"][0]), len(first["grid"]), flags[1])
        prefix = empty_path(first, first["spawn"], canonical_start)
        stairs_count = self._stair_check(floors)
        require(sum(len(f["objects"]) for f in floors.values()) == len(self.by_object), "Object count changed")
        # Only these root values change in the production generator. Hash the
        # immutable root encodings unchanged, avoiding 10,000 copies of ledgers.
        parts = dict(self.static_root_parts)
        parts["floors"] = compact(normalize(list(floors.values()), "floors"))
        if "variant_spawn_candidates" in self.canonical:
            parts["variant_spawn_candidates"] = compact(first["safe_start_candidates"])
        digest = hashlib.sha256()
        digest.update(b"{")
        for position, key in enumerate(sorted(parts)):
            if position:
                digest.update(b",")
            digest.update(compact(key) + b":" + parts[key])
        digest.update(b"}")
        return {"seed": normalize_seed(seed), "layout_hash": digest.hexdigest(),
                "draw_count": len(draws), "draws_sha256": sha_bytes(compact(draws)),
                "floor_transform_codes": "".join(str(flags[n]) for n in range(1, 22)),
                "spawn_choice_index": spawn_index, "resolved_start": first["spawn"],
                "empty_prefix": prefix, "object_count": len(self.by_object), "stairs_checked": stairs_count,
                "structural_invariants": True}


def check_witness_premise(path: Path, canonical: dict, source_hashes: dict) -> dict:
    report, evidence = read_json(path)
    require(report.get("passed") is True and report.get("failures") == [], "Canonical witness receipt did not pass")
    require(report.get("data_sha256") == source_hashes["data"], "Witness receipt binds different canonical bytes")
    require(report.get("base_rules_sha256") == source_hashes["base_rules"], "Witness receipt binds different base rules")
    require(report.get("test_sha256") == source_hashes["canonical_replayer"], "Witness replayer source changed")
    require(report.get("preview_deduction_comparisons", 0) > 0, "Witness has no recorded preview/deduction comparisons")
    authored = {r["name"]: r for r in canonical["witness_routes"]}
    require(len(authored) == 4 and set(authored) == {"blade", "bulwark", "balanced", "frugal"}, "Expected four authored witnesses")
    actual = report.get("routes", [])
    require(len(actual) == 4 and {r.get("name") for r in actual} == set(authored), "Witness receipt missing/duplicates routes")
    routes = []
    for route in actual:
        name, final = route["name"], route.get("final", {})
        expected = authored[name]
        decisions = route.get("decisions", [])
        require(route.get("passed") is True and final.get("won") is True, f"Witness {name} did not win")
        require([step.get("event") for step in decisions] == expected["events"], f"Witness {name} event sequence differs")
        require(route.get("decision_count") == len(expected["events"]), "Witness decision count mismatch")
        require(final.get("floor") == 20 and "f21_boss" in final.get("cleared", []), "Witness did not reach final victory object")
        for stat in ("hp", "atk", "def", "gold", "keys", "won"):
            require(final.get(stat) == expected["final"][stat], f"Witness {name} final {stat} differs")
        routes.append({"name": name, "decision_count": len(decisions), "won": True,
                       "final_hp": final["hp"], "events_sha256": sha_bytes(compact(expected["events"]))})
    return {"status": "accepted-recorded-premise", "report": evidence, "engine": report.get("engine"),
            "routes": routes, "navigation_moves": report.get("navigation_moves"),
            "preview_deduction_comparisons": report["preview_deduction_comparisons"],
            "scope": "Four prior real Godot canonical wins; this Python audit does not rerun or attest the engine."}


def load_run_report(path: Path, hashes: dict) -> tuple[dict, dict]:
    report, evidence = read_json(path)
    require(report.get("variant_spec") == SPEC, f"{path.name}: wrong variant spec")
    require(report.get("measurement_completed") is True, f"{path.name}: incomplete measurement")
    require(report.get("invariants_passed") is True and not report.get("errors"), f"{path.name}: simulation invariants/errors")
    require(report.get("source_data_sha256") == hashes["data"], f"{path.name}: canonical bytes differ")
    require(report.get("base_rules_sha256") == hashes["base_rules"], f"{path.name}: base rules differ")
    require(report.get("variant_sha256") == hashes["variant"], f"{path.name}: generator source differs")
    require(report.get("navigation_sha256") == hashes["navigation"], f"{path.name}: navigation source differs")
    require(report.get("layout_draws_per_run") == DRAW_COUNT, f"{path.name}: wrong draw count")
    runs = report.get("runs")
    require(isinstance(runs, list), f"{path.name}: missing runs")
    require(report.get("completed_runs") == len(runs) == report.get("requested_runs"), f"{path.name}: run counts differ")
    expected_indices = list(range(report["start_index"], report["start_index"] + len(runs)))
    require(sorted(r["index"] for r in runs) == expected_indices, f"{path.name}: missing/duplicate run indices")
    evidence.update({"start_index": report["start_index"], "runs": len(runs),
                     "simulation_sha256": report.get("simulation_sha256"),
                     "simulator_matches_current": report.get("simulation_sha256") == hashes["simulation"]})
    return report, evidence


def audit_run(row: dict, report: dict, geometry: GeometryAudit, canonical_hash: str) -> dict:
    index = row["index"]
    require(type(index) is int and index >= 0, "Invalid absolute run index")
    seed = normalize_seed(row["layout_seed"])
    master = int(normalize_seed(report["master_layout_seed"]), 16)
    require(seed == normalize_seed((master + index * 104729) & MASK), f"Run {index}: layout seed derivation differs")
    require(row.get("canonical_hash") == canonical_hash, f"Run {index}: canonical content hash differs")
    require(row.get("layout_draw_count") == DRAW_COUNT, f"Run {index}: wrong draw count")
    require(row.get("layout_seed_after") == seed, f"Run {index}: layout seed mutated during policy run")
    result = geometry.variant(seed)
    require(result["draw_count"] == DRAW_COUNT, "Independent generator did not consume 43 draws")
    require(result["resolved_start"] == row.get("resolved_start"), f"Run {index}: spawn mismatch")
    require(result["layout_hash"] == row.get("layout_hash"),
            f"Run {index}: layout_hash mismatch expected={row.get('layout_hash')} actual={result['layout_hash']}")
    result.update({"index": index, "layout_hash_matches_recorded_godot": True,
                   "initial_winning_path_exists_conditionally": True,
                   "observed_policy": row.get("policy"), "observed_policy_outcome": row.get("outcome")})
    return result


def expand_reports(patterns: list[str]) -> list[Path]:
    paths = []
    for pattern in patterns:
        found = [Path(p).resolve() for p in glob.glob(pattern)]
        require(found, f"No report matches {pattern}")
        paths.extend(found)
    require(len(paths) == len(set(paths)), "Same report path supplied more than once")
    return sorted(paths)


def run_audit(args) -> dict:
    started = time.monotonic()
    source_paths = {
        "data": args.data, "variant": args.campaign / "scripts/campaign_variant.gd",
        "base_rules": args.campaign / "scripts/base_rules.gd",
        "navigation": args.campaign / "scripts/campaign_navigation.gd",
        "simulation": args.campaign / "tests/simulate_campaign.gd",
        "canonical_replayer": args.campaign / "tests/replay_witnesses.gd",
    }
    sources = {name: {"path": display_path(path), "sha256": sha_bytes(path.read_bytes()),
                       "bytes": path.stat().st_size} for name, path in source_paths.items()}
    hashes = {name: item["sha256"] for name, item in sources.items()}
    canonical, _ = read_json(args.data)
    canonical_hash = content_hash(canonical)
    geometry = GeometryAudit(canonical)
    witness = check_witness_premise(args.witness_report, canonical, hashes)
    calibration_report, calibration_evidence = load_run_report(args.calibration_report, hashes)
    require(calibration_report["start_index"] == 0 and len(calibration_report["runs"]) == 100,
            "Calibration requires the complete existing 100-run report, indices 0..99")
    for row in calibration_report["runs"]:
        audit_run(row, calibration_report, geometry, canonical_hash)
    cache = {args.calibration_report.resolve(): (calibration_report, calibration_evidence)}
    records, evidence, indices, failures = [], [], set(), []
    reports = expand_reports(args.reports)
    for path in reports:
        report, manifest = cache.get(path, (None, None))
        if report is None:
            report, manifest = load_run_report(path, hashes)
        evidence.append(manifest)
        for row in report["runs"]:
            index = row["index"]
            if index in indices:
                failures.append(f"Duplicate absolute index {index} across reports")
                continue
            indices.add(index)
            try:
                records.append(audit_run(row, report, geometry, canonical_hash))
            except (InvalidEvidence, KeyError, TypeError, ValueError) as error:
                failures.append(str(error))
        if args.progress:
            print(f"Audited {len(indices)} indices; {len(failures)} failures", file=sys.stderr, flush=True)
    expected = set(range(args.start_index, args.start_index + args.expected_runs))
    missing, unexpected = sorted(expected - indices), sorted(indices - expected)
    if missing:
        failures.append(f"Missing {len(missing)} expected absolute indices")
    if unexpected:
        failures.append(f"Unexpected {len(unexpected)} absolute indices")
    for name, path in source_paths.items():
        require(sha_bytes(path.read_bytes()) == hashes[name], f"Frozen input changed during audit: {name}")
    require(sha_bytes(Path(__file__).read_bytes()), "Cannot hash this auditor")
    passed = not failures and len(records) == args.expected_runs
    outcomes = dict(Counter(record["observed_policy_outcome"] for record in records))
    return {
        "$schema": "tools/variant_bijection_certificate.schema.json", "schema_version": 1,
        "certificate_spec": CERT_SPEC, "variant_spec": SPEC, "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed", "passed": passed,
        "scope": "Conditional existence of an ordinary winning base-rule path in each recorded initial mirror/spawn layout. No strategy-success or all-uint32 claim.",
        "sources": sources, "auditor_sha256": sha_bytes(Path(__file__).read_bytes()),
        "canonical_content_hash": canonical_hash,
        "economic_catalog_hashes": {name: content_hash(canonical[name]) for name in ("initial_player", "enemies", "shops")},
        "witness_premise": witness,
        "calibration": {"report": calibration_evidence, "runs": 100, "indices": [0, 99],
                        "layout_hashes_matched": 100, "serialization_adjustments_after_comparison": False},
        "local_transform_certificates": geometry.local_certificates,
        "coverage": {"expected_runs": args.expected_runs, "expected_start_index": args.start_index,
                     "expected_last_index": args.start_index + args.expected_runs - 1,
                     "observed_unique_indices": len(indices), "passed_run_certificates": len(records),
                     "missing_indices": missing, "unexpected_indices": unexpected,
                     "floor_transform_instances": 21 * len(records), "object_instances": len(geometry.by_object) * len(records),
                     "stair_link_instances": sum(row["stairs_checked"] for row in records),
                     "observed_policy_outcomes_retained": outcomes},
        "input_reports": evidence, "runs": sorted(records, key=lambda row: row["index"]), "errors": failures,
        "proof_steps": [
            "Each selected H/V transform is one of 84 enumerated local bijections preserving walkable cells and both directions of four-neighbor adjacency.",
            "Every object ID and every non-geometric attribute, initial resource value, enemy catalog and shop stock/cost is invariant; only positions/facing and declared spawn fields change.",
            "Every stair target is reflected with its destination floor flags and all 40 directed links remain reciprocal.",
            "The chosen first-floor spawn has an explicit empty prefix to the reflected canonical start, crossing no object, door, enemy or stair and consuming no resource.",
            "Reflect each canonical witness move delta by its current floor flags, retain object/offer IDs, and map stair arrivals using destination flags. Under the recorded base-rule semantics, the resource/event sequence and winning outcome are unchanged.",
            "This is a conditional transport argument using four hash-bound prior Godot wins, not a new engine replay or an exhaustive policy/state search.",
        ],
        "limitations": [
            "Recorded canonical witness provenance is a premise; this audit checks its source hashes/events/final results but does not authenticate or rerun Godot.",
            "The rule-semantic premise is zero-cost ordinary movement, Manhattan adjacency and coordinate-independent combat/economy in the exact recorded base rules. Additional wrapper/UI gates require separate engine acceptance.",
            "Only completed input report indices are enumerated. This is not enumeration of all 2^32 seeds, although H/V isometry is a general mathematical property.",
            "A winning initial layout does not imply all policies or reached resource states remain winnable. Existing dead_end outcomes are retained unchanged.",
            "No browser, GUI, persistence, audio, art, human-duration or physical-device claim.",
            "The independent hash serializer is accepted only after 100 actual recorded Godot layout hashes match; any mismatch fails rather than adjusting the reported hashes.",
        ],
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=CAMPAIGN)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--reports", nargs="+", default=[str(WORKSPACE / "output/campaign-sim-100.json")])
    parser.add_argument("--calibration-report", type=Path, default=WORKSPACE / "output/campaign-sim-100.json")
    parser.add_argument("--witness-report", type=Path, default=WORKSPACE / "output/campaign-witnesses-final.json")
    parser.add_argument("--expected-runs", type=int, default=100)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--output", type=Path, help="Create a new certificate exclusively; never overwrite")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    args.campaign = args.campaign.resolve()
    args.data = (args.data or args.campaign / "data/levels21.json").resolve()
    try:
        require(args.expected_runs > 0 and args.start_index >= 0, "Invalid requested coverage")
        if args.output:
            require(not args.output.exists(), "Output already exists; choose a new certificate path")
        report = run_audit(args)
    except (InvalidEvidence, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        report = {"schema_version": 1, "certificate_spec": CERT_SPEC, "status": "failed", "passed": False,
                  "errors": [str(error)], "scope": "Input/calibration failure; no initial-solvability certificate issued."}
    serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized)
        except OSError as error:
            print(json.dumps({"passed": False, "errors": [f"Certificate was not written: {error}"]}), file=sys.stderr)
            return 2
        print(json.dumps({"passed": report["passed"], "output": display_path(args.output),
                          "coverage": report.get("coverage"), "errors": report["errors"],
                          "elapsed_seconds": report.get("elapsed_seconds")}, ensure_ascii=False))
    else:
        print(serialized, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
