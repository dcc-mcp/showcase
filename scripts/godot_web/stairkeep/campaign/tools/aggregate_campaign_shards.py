#!/usr/bin/env python3
"""Read-only verification and portable evidence packaging for campaign shards.

Default contract: four completed 2,500-run shards, absolute indices 0..9,999.
Only stdlib is used. Inputs are never rewritten; an output directory must be new.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import sys
import zipfile

POLICIES = ("resource", "attack", "defense", "cautious", "randomized")
WITNESS_NAMES = {"blade", "bulwark", "balanced", "frugal"}
HASH_FIELDS = ("source_data_sha256", "base_rules_sha256", "variant_sha256", "navigation_sha256", "simulation_sha256")
SOURCE_FILES = {"source_data_sha256": "data/levels21.json", "base_rules_sha256": "scripts/base_rules.gd", "variant_sha256": "scripts/campaign_variant.gd", "navigation_sha256": "scripts/campaign_navigation.gd", "simulation_sha256": "tests/simulate_campaign.gd"}
CONFIG_FIELDS = ("variant_spec", "layout_draws_per_run", "master_layout_seed", "master_policy_seed", "seed_derivation", "policy_rng", "policies", "max_decisions", "local_floor_horizon", "local_global_contract", "decision_signature_scope")
SUM_FIELDS = {"navigation_moves": "navigation_moves", "preview_actual_comparisons": "preview_actual_comparisons", "local_frontier_queries": "local_queries", "global_frontier_queries": "global_queries", "navigation_nodes_processed": "nav_nodes"}
ALLOWED_OUTCOMES = {"won", "dead_end", "step_limit", "unknown_navigation_incomplete"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
MASK = 0xFFFFFFFF
ZERO_SEED = 0x6D2B79F5


class Invalid(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Invalid(message)


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bad_constant(word):
    raise Invalid(f"Non-finite JSON constant: {word}")


def read_json(path):
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream, parse_constant=bad_constant)
    need(isinstance(value, dict), f"Expected JSON object: {Path(path).name}")
    return value


def integral(value, label, minimum=0):
    need(not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and int(value) == value and value >= minimum, f"Invalid integral {label}: {value!r}")
    return int(value)


def number(value, label):
    need(not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value), f"Invalid finite {label}")
    return float(value)


def seed(word, label):
    need(isinstance(word, str) and re.fullmatch(r"[0-9a-f]{8}", word), f"Invalid normalized seed {label}")
    return int(word, 16)


def normalized_seed(value):
    return f"{(value or ZERO_SEED):08x}"


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def full_budget(state):
    return {"floor": integral(state["floor"], "full state floor") + 1, "pos": state["pos"], "hp": state["hp"], "atk": state["atk"], "def": state["def"], "gold": state["gold"], "keys": state["keys"], "cleared_count": len(state["cleared"]), "purchases": state["purchases"], "won": state["won"]}


def portable_locator(shard_start, kind, line=None, offset=None, length=None, raw=None):
    result = {"path": f"inputs/shard-{shard_start:05d}.{kind}"}
    if line is not None:
        result.update({"line": line, "byte_offset": offset, "byte_length": length, "line_sha256": hashlib.sha256(raw).hexdigest()})
    return result


def validate_record(record, report, index):
    need(integral(record.get("index"), "run index") == index, f"Run index mismatch: {index}")
    need(record.get("policy") == POLICIES[index % 5], f"Wrong policy assignment at {index}")
    layout = (seed(report["master_layout_seed"], "master layout") + index * 104729) & MASK
    layout_word = normalized_seed(layout)
    policy = (seed(report["master_policy_seed"], "master policy") ^ int(layout_word, 16) ^ (((index + 1) * 2654435761) & MASK)) & MASK
    need(record.get("layout_seed") == layout_word and record.get("policy_seed") == normalized_seed(policy), f"Seed derivation mismatch at {index}")
    need(record.get("layout_seed_after") == layout_word, f"Unexpected layout seed binding at {index}")
    for field in ("layout_hash", "canonical_hash", "decision_signature"):
        need(bool(SHA.fullmatch(str(record.get(field, "")))), f"Invalid {field} at {index}")
    need(record.get("layout_draw_count") == 43, f"Wrong layout draw count at {index}")
    seed(record.get("policy_rng_final"), f"policy RNG final at {index}")
    need(record.get("outcome") in ALLOWED_OUTCOMES, f"Error/unsupported outcome at {index}: {record.get('outcome')}")
    need(integral(record.get("decision_count"), "decision count") <= report["max_decisions"], f"Decision limit exceeded at {index}")
    for field in ("navigation_moves", "preview_actual_comparisons", "local_queries", "global_queries", "nav_nodes", "armor_gate_preparations", "policy_draws"):
        integral(record.get(field), f"{field} at {index}")
    for field in ("elapsed_ms", "variant_prepare_ms", "frontier_ms", "execution_ms"):
        need(number(record.get(field), field) >= 0, f"Negative timing at {index}")
    final = record.get("final")
    need(isinstance(final, dict), f"Missing final budget at {index}")
    need(1 <= integral(final.get("floor"), "final floor", 1) <= 21, f"Invalid final floor at {index}")
    for field in ("hp", "atk"):
        integral(final.get(field), f"final {field}", 1)
    for field in ("def", "gold", "cleared_count"):
        integral(final.get(field), f"final {field}")
    need(isinstance(final.get("keys"), dict) and isinstance(final.get("purchases"), dict), f"Missing key/stock budget at {index}")
    for count in list(final["keys"].values()) + list(final["purchases"].values()):
        integral(count, f"key/purchase quantity at {index}")
    need(final.get("won") is (record["outcome"] == "won"), f"Outcome and won flag differ at {index}")


def inspect_journal(path, report, records, shard_start):
    need(sha_file(path) == report["journal_sha256"], f"Journal hash differs: {path.name}")
    run_locations, example_locations, examples = {}, {}, {}
    header_seen = False
    offset = 0
    with path.open("rb") as stream:
        for line_no, raw in enumerate(stream, 1):
            need(raw.endswith(b"\n"), f"Truncated journal line {line_no}: {path.name}")
            entry = json.loads(raw, parse_constant=bad_constant)
            kind = entry.get("kind")
            location = portable_locator(shard_start, "journal.jsonl", line_no, offset, len(raw), raw)
            if kind == "header":
                need(line_no == 1 and not header_seen, f"Unexpected journal header: {path.name}")
                header_seen = True
                for field in ("start_index", "requested_runs", "source_data_sha256", "master_layout_seed", "master_policy_seed", "policies"):
                    need(entry.get(field) == report.get(field), f"Journal header {field} differs: {path.name}")
            elif kind == "run":
                record = entry.get("record", {})
                index = integral(record.get("index"), "journal run index")
                need(index in records and index not in run_locations and record == records[index], f"Journal run missing, duplicate or differs from report: {index}")
                run_locations[index] = location
            elif kind == "example":
                example = entry.get("example", {})
                index = integral(example.get("record", {}).get("index"), "example run index")
                need(index in records and index not in examples and example["record"] == records[index], f"Journal example record mismatch: {index}")
                need(entry.get("bucket") == f"{records[index]['policy']}/{records[index]['outcome']}", f"Example bucket mismatch: {index}")
                need(full_budget(example["final_state"]) == records[index]["final"], f"Example full state differs from retained budget: {index}")
                decisions = example.get("decisions", [])
                need(len(decisions) == records[index]["decision_count"], f"Incomplete executable example sequence: {index}")
                sequence = "\n".join(str(item["chosen_id"]) for item in decisions)
                need(hashlib.sha256(sequence.encode()).hexdigest() == records[index]["decision_signature"], f"Example decision signature mismatch: {index}")
                examples[index], example_locations[index] = example, location
            else:
                raise Invalid(f"Unexpected/incomplete journal entry {kind!r}: {path.name}:{line_no}")
            offset += len(raw)
    need(header_seen and set(run_locations) == set(records), f"Journal does not cover every report run: {path.name}")
    report_examples = {int(item["record"]["index"]): item for bucket in report.get("examples", {}).values() for item in bucket}
    need(report_examples == examples, f"Report and journal examples differ: {path.name}")
    return run_locations, examples, example_locations


def validate_shards(paths, args):
    need(len(paths) == args.expected_shards, f"Need {args.expected_shards} shard reports, got {len(paths)}")
    all_runs, all_examples, rows, sources, binding, shared = {}, {}, [], [], None, None
    for path in paths:
        report = read_json(path)
        start = integral(report.get("start_index"), "shard start")
        need(report.get("measurement_completed") is True and report.get("invariants_passed") is True, f"Shard is not completed/invariant-clean: {path.name}")
        need(report.get("stopped_at_case_boundary", False) is False, f"Stopped shard is not a completed measurement: {path.name}")
        need(report.get("errors") == [] and report.get("preview_actual_mismatches") == 0, f"Shard errors or damage mismatch: {path.name}")
        need(report.get("requested_runs") == args.per_shard and report.get("completed_runs") == args.per_shard and len(report.get("runs", [])) == args.per_shard, f"Wrong per-shard count: {path.name}")
        need(report.get("layout_draws_per_run") == 43 and report.get("respawn_actions") == 0, f"Unexpected layout/respawn semantics: {path.name}")
        own_binding = {field: report.get(field) for field in HASH_FIELDS}
        need(all(SHA.fullmatch(str(value)) for value in own_binding.values()), f"Invalid source fingerprint: {path.name}")
        own_shared = {field: report.get(field) for field in CONFIG_FIELDS}
        own_shared["engine"] = report.get("engine")
        if binding is None:
            binding, shared = own_binding, own_shared
        need(own_binding == binding and own_shared == shared, f"Shard sources, engine or policy/config differ: {path.name}")
        records = {}
        for record in report["runs"]:
            index = integral(record.get("index"), "absolute index")
            need(index not in records and index not in all_runs, f"Duplicate absolute index {index}")
            validate_record(record, report, index)
            records[index] = record
        need(set(records) == set(range(start, start + args.per_shard)), f"Shard range has omissions: {path.name}")
        for total_field, run_field in SUM_FIELDS.items():
            need(integral(report.get(total_field), total_field) == sum(int(item[run_field]) for item in records.values()), f"Shard total {total_field} differs: {path.name}")
        need(report.get("distinct_decision_sequences") == len({item["decision_signature"] for item in records.values()}), f"Shard distinct sequence count differs: {path.name}")
        failures = {int(item["index"]): item for item in report.get("failure_seeds", [])}
        expected_failed = {index for index, item in records.items() if item["outcome"] != "won"}
        need(len(failures) == len(report.get("failure_seeds", [])) and set(failures) == expected_failed, f"Failure seed ledger does not cover all nonwins: {path.name}")
        for index, failed in failures.items():
            need(all(failed.get(field) == records[index].get(field) for field in ("policy", "layout_seed", "policy_seed", "layout_hash", "outcome", "decision_signature")), f"Failure ledger differs at {index}")
        for policy in POLICIES:
            selected = [item for item in records.values() if item["policy"] == policy]
            stored = report.get("per_policy", {}).get(policy, {})
            need(stored.get("runs") == len(selected) and stored.get("outcomes") == dict(collections.Counter(item["outcome"] for item in selected)), f"Per-policy outcome counts differ: {path.name}/{policy}")
            if selected:
                need(stored.get("distinct_decision_sequences") == len({item["decision_signature"] for item in selected}), f"Per-policy distinct sequences differ: {policy}")
                need(stored.get("sum_decisions") == sum(int(item["decision_count"]) for item in selected), f"Per-policy decisions differ: {policy}")
        journal = Path(str(path) + ".journal.jsonl")
        need(journal.is_file(), f"Paired journal is missing: {journal.name}")
        locations, examples, example_locations = inspect_journal(journal, report, records, start)
        for offset_in_report, record in enumerate(report["runs"]):
            index = int(record["index"])
            all_runs[index] = record
            rows.append({"record": record, "report_locator": {"path": f"inputs/shard-{start:05d}.report.json", "json_pointer": f"/runs/{offset_in_report}"}, "journal_locator": locations[index]})
        for index, example in examples.items():
            all_examples[index] = {"example": example, "journal_locator": example_locations[index]}
        sources.append({"start_index": start, "completed_runs": args.per_shard, "report_path": path, "journal_path": journal, "original_report_sha256": sha_file(path), "journal_sha256": report["journal_sha256"], "elapsed_ms": report["elapsed_ms"], "report": report})
    expected = set(range(args.expected_start, args.expected_start + args.expected_total))
    need(set(all_runs) == expected, f"Absolute index coverage differs: missing={sorted(expected-set(all_runs))[:10]}, extra={sorted(set(all_runs)-expected)[:10]}")
    counts = collections.Counter(record["policy"] for record in all_runs.values())
    expected_counts = collections.Counter(POLICIES[index % 5] for index in expected)
    need(counts == expected_counts, f"Aggregate policy coverage differs: {dict(counts)}")
    need(len({record["canonical_hash"] for record in all_runs.values()}) == 1, "Different canonical semantic hashes were mixed.")
    rows.sort(key=lambda row: int(row["record"]["index"]))
    return rows, all_examples, sorted(sources, key=lambda item: item["start_index"]), binding, shared


def metric(values):
    values = sorted(values)
    if not values:
        return {"count": 0}
    return {"count": len(values), "min": values[0], "max": values[-1], "mean": statistics.fmean(values), "median": statistics.median(values), "p95_nearest_rank": values[max(0, math.ceil(len(values) * .95) - 1)]}


def bind_canonical(args, binding, examples):
    canonical, source_verification = None, {"provided": bool(args.source_root), "passed": False}
    if args.source_root:
        root = args.source_root.resolve()
        for field, relative in SOURCE_FILES.items():
            path = root / relative
            need(path.is_file() and sha_file(path) == binding[field], f"Frozen source file differs: {relative}")
        canonical = read_json(root / "data/levels21.json")
        source_verification = {"provided": True, "passed": True, "checked_files": SOURCE_FILES}
    initial = canonical.get("initial_player") if canonical else None
    for item in examples.values():
        state = item["example"]["initial_state"]
        budget = {key: state[key] for key in ("hp", "atk", "def", "gold", "keys")}
        if initial is None:
            initial = budget
        need(all(initial[key] == budget[key] for key in budget), "Example initial resources differ from the fixed canonical initial budget.")
    need(initial is not None, "No bound canonical or retained initial-state example is available.")
    witness = {"provided": bool(args.canonical_witness_report), "passed": False, "scope": "Canonical initial solvability only; per-variant isomorphism certificates are a separate obligation."}
    if args.canonical_witness_report:
        data = read_json(args.canonical_witness_report)
        passed = data.get("passed") is True and data.get("failures") == [] and data.get("data_sha256") == binding["source_data_sha256"] and data.get("base_rules_sha256") == binding["base_rules_sha256"]
        routes = data.get("routes", [])
        passed = passed and len(routes) == 4 and {item.get("name") for item in routes} == WITNESS_NAMES and all(item.get("passed") is True and item.get("final", {}).get("won") is True for item in routes)
        need(passed, "Canonical witness report is incomplete or has different data/base hashes.")
        witness.update({"passed": True, "sha256": sha_file(args.canonical_witness_report), "route_names": [item["name"] for item in routes]})
    return canonical, initial, source_verification, witness


def price_catalog(canonical):
    if canonical is None:
        return None
    result = {}
    for floor in canonical["floors"]:
        for item in floor["objects"]:
            if item["kind"] == "shop":
                for offer in canonical["shops"][item["type"]]["offers"]:
                    result[item["id"] + "/" + offer["id"]] = (int(offer["cost"]), int(offer["limit"]))
    return result


def consume_failure_replays(paths, baseline_rows, binding, shared, witness, bound_input, replayer_script=None):
    """Stream proofs; retain states/locators, not every large path/proof tree."""
    expected = {int(row["record"]["index"]): row["record"] for row in baseline_rows if row["record"]["outcome"] != "won"}
    ordered = sorted(expected)
    need(witness.get("passed") is True, "Failure proof completion requires the bound canonical winning-witness report.")
    need(bound_input is not None and bound_input.is_file(), "Pass --replay-input with the original byte-exact queue actually executed by the replay workers.")
    original_queue = read_json(bound_input)
    input_sha256 = sha_file(bound_input)
    original_summary_path = bound_input.parent / "summary.json"
    original_witness_path = bound_input.parent / "canonical-winning-witnesses.json"
    need(original_queue.get("expected_records") == [expected[index] for index in ordered] and original_queue.get("source_hashes") == binding and original_queue.get("engine") == shared["engine"], "Original replay queue differs from this baseline failure set or source/engine binding.")
    need(original_queue.get("canonical_witness_binding", {}).get("sha256") == witness["sha256"] and original_witness_path.is_file() and sha_file(original_witness_path) == witness["sha256"], "Original replay queue's canonical winning-witness bytes are missing or changed.")
    need(original_summary_path.is_file() and sha_file(original_summary_path) == original_queue.get("source_aggregate_summary_sha256"), "The original aggregate summary bound by the executed queue is missing or changed.")
    verified, covered_offsets, sources = {}, set(), []
    common_replayer_hash = None
    timing = {"elapsed_ms", "variant_prepare_ms", "frontier_ms", "execution_ms"}
    for part, path in enumerate(paths):
        path = path.resolve()
        summary_path = Path(str(path) + ".summary.json")
        need(summary_path.is_file(), f"Missing completed replay summary: {summary_path.name}")
        summary = read_json(summary_path)
        need(summary.get("measurement_completed") is True and summary.get("stopped_at_case_boundary") is False and summary.get("errors") == [] and summary.get("baseline_errors") == [], f"Replay fragment is not fully completed/clean: {path.name}")
        journal_hash = sha_file(path)
        need(summary.get("journal_sha256") == journal_hash, f"Replay journal hash differs: {path.name}")
        header, footer, pending = None, None, None
        fragment_offsets, fragment_indices = set(), set()
        offset = 0
        portable_path = f"replays/part-{part:02d}.jsonl"
        with path.open("rb") as stream:
            for line_no, raw in enumerate(stream, 1):
                need(raw.endswith(b"\n"), f"Truncated replay journal: {path.name}:{line_no}")
                entry = json.loads(raw, parse_constant=bad_constant)
                location = {"path": portable_path, "line": line_no, "byte_offset": offset, "byte_length": len(raw), "line_sha256": hashlib.sha256(raw).hexdigest()}
                kind = entry.get("kind")
                if kind == "replay_header":
                    need(line_no == 1 and header is None, f"Unexpected replay header: {path.name}")
                    header = entry
                    need(entry.get("source_hashes") == binding and entry.get("engine") == shared["engine"], f"Replay source or engine differs: {path.name}")
                    need(entry.get("master_layout_seed") == shared["master_layout_seed"] and entry.get("master_policy_seed") == shared["master_policy_seed"], f"Replay master seeds differ: {path.name}")
                    need(entry.get("input_sha256") == input_sha256 and summary.get("input_sha256") == input_sha256 and entry.get("source_aggregate_summary_sha256") == original_queue["source_aggregate_summary_sha256"], f"Replay worker executed a different queue/aggregate summary: {path.name}")
                    fingerprint = str(entry.get("replayer_sha256", ""))
                    need(bool(SHA.fullmatch(fingerprint)), f"Missing replayer source hash: {path.name}")
                    if common_replayer_hash is None:
                        common_replayer_hash = fingerprint
                    need(fingerprint == common_replayer_hash and summary.get("replayer_sha256") == fingerprint, "Different replayer implementations were mixed.")
                    if replayer_script:
                        need(sha_file(replayer_script) == fingerprint, "Current replayer script differs from executed source.")
                    need(entry.get("witness_binding", {}).get("ok") is True and entry["witness_binding"].get("report_sha256") == witness["sha256"] and len(entry["witness_binding"].get("routes", [])) == 4 and set(entry["witness_binding"]["routes"]) == WITNESS_NAMES, f"Replay canonical witness binding differs: {path.name}")
                elif kind == "example":
                    need(header is not None and footer is None and pending is None, f"Unpaired replay example: {path.name}:{line_no}")
                    pending = (entry["example"], location)
                elif kind == "verified_failure":
                    need(header is not None and footer is None and pending is not None, f"Failure proof lacks its streamed example: {path.name}:{line_no}")
                    example, example_location = pending
                    index = integral(entry.get("index"), "replay absolute index")
                    queue_offset = integral(entry.get("queue_offset"), "replay queue offset")
                    need(index in expected and index not in verified and queue_offset < len(ordered) and ordered[queue_offset] == index, f"Replay index/queue offset duplicate or differs: {index}")
                    begin, count = integral(header.get("offset"), "fragment offset"), integral(header.get("requested_replays"), "fragment requested count")
                    need(begin <= queue_offset < begin + count and queue_offset not in covered_offsets, f"Overlapping/out-of-fragment replay queue offset: {queue_offset}")
                    need(entry.get("expected_record") == expected[index], f"Replayer was given a different baseline record: {index}")
                    actual = entry.get("actual_record", {})
                    need({k: v for k, v in actual.items() if k not in timing} == {k: v for k, v in expected[index].items() if k not in timing}, f"Replayed non-timing fields differ: {index}")
                    need(entry.get("verified") is True and entry.get("record_matches") is True and entry.get("differences") == [], f"Replay record or reconstruction failed: {index}")
                    need(example.get("record") == actual, f"Replay example record differs: {index}")
                    trace_ids = "\n".join(str(item["chosen_id"]) for item in example.get("decisions", []))
                    need(len(example.get("decisions", [])) == actual["decision_count"] and hashlib.sha256(trace_ids.encode()).hexdigest() == actual["decision_signature"], f"Replay executable trace is incomplete: {index}")
                    locator = entry.get("example_locator", {})
                    need(all(locator.get(key) == example_location[key] for key in ("line", "byte_offset", "byte_length")), f"Replay example byte locator differs: {index}")
                    full_state = entry.get("full_terminal_state", {})
                    need(full_state == example.get("final_state") and full_budget(full_state) == expected[index]["final"], f"Full terminal replay state differs: {index}")
                    reconstruction = entry.get("continuous_reconstruction", {})
                    proof = reconstruction.get("global_navigation_proof", {})
                    need(reconstruction.get("ok") is True and proof.get("scope") == "global" and proof.get("complete") is True and proof.get("queue_exhausted") is True and proof.get("errors") == [], f"Replay lacks full global terminal BFS: {index}")
                    nodes = proof.get("nodes", [])
                    need(len(nodes) == proof.get("reachable") and len({tuple(node) for node in nodes}) == len(nodes), f"Terminal BFS node inventory differs: {index}")
                    dead_end = actual["outcome"] == "dead_end"
                    if dead_end:
                        need(proof.get("options") == [] and proof.get("legal_resource_actions") == 0 and reconstruction.get("terminal_no_resource_action") is True and entry.get("terminal_no_winning_suffix") is True, f"Dead end was not proven actionless: {index}")
                    certificate = entry.get("isomorphism_certificate", {})
                    need(certificate.get("ok") is True and certificate.get("errors") == [] and certificate.get("layout_seed") == actual["layout_seed"] and certificate.get("layout_hash") == actual["layout_hash"] and certificate.get("canonical_hash") == actual["canonical_hash"], f"Variant isomorphism binding failed: {index}")
                    floors = certificate.get("floors", [])
                    need(len(floors) == 21 and {int(floor["floor_id"]) for floor in floors} == set(range(1, 22)), f"Isomorphism misses a floor: {index}")
                    object_ids = set()
                    for floor in floors:
                        need(floor.get("verified_cells") == int(floor["width"]) * int(floor["height"]), f"Not all cell images were checked: {index}")
                        for item in floor.get("objects", []):
                            need(item.get("id") not in object_ids and item.get("all_attributes_match") is True and item.get("expected_pos") == item.get("actual_pos") and item.get("expected_all_attributes_sha256") == item.get("actual_all_attributes_sha256") and bool(SHA.fullmatch(str(item.get("actual_all_attributes_sha256", "")))), f"Object coordinate/ID/attribute certificate differs: {index}")
                            object_ids.add(item["id"])
                            if item.get("kind") == "stairs":
                                need(item.get("expected_target") == item.get("actual_target"), f"Stair target image differs: {index}")
                    spawn = certificate.get("spawn_connectivity", {})
                    canonical_path, mapped_path = spawn.get("canonical_empty_path", []), spawn.get("mirrored_empty_path", [])
                    need(spawn.get("ok") is True and bool(canonical_path) and len(canonical_path) == len(mapped_path) and mapped_path[0] == actual["resolved_start"], f"Spawn neutral path certificate failed: {index}")
                    for path_cells in (canonical_path, mapped_path):
                        need(all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(path_cells, path_cells[1:])), f"Spawn path has a non-cardinal jump: {index}")
                    need(entry.get("initial_solvable") is True and entry.get("initial_unsatisfiable_proven") is False and entry.get("canonical_witness_binding", {}).get("report_sha256") == witness["sha256"], f"Initial solvability was not bound: {index}")
                    resources = reconstruction.get("resources", {})
                    need(resources.get("navigation_moves") == actual["navigation_moves"] and resources.get("preview_actual_comparisons") == actual["preview_actual_comparisons"], f"Reconstruction action counters differ: {index}")
                    initial = example["initial_state"]
                    need(int(initial["hp"]) + int(resources["gross_healing"]) - int(resources["gross_battle_damage"]) == int(full_state["hp"]), f"Failure-subset HP ledger does not conserve: {index}")
                    need(int(initial["gold"]) + int(resources["gold_gained"]) - int(resources["gold_spent"]) == int(full_state["gold"]), f"Failure-subset gold ledger does not conserve: {index}")
                    for color in initial["keys"]:
                        need(int(initial["keys"][color]) + int(resources["keys_collected"].get(color, 0)) - int(resources["keys_consumed"].get(color, 0)) == int(full_state["keys"][color]), f"Failure-subset key ledger differs: {index}/{color}")
                    verified[index] = {"full_terminal_state": full_state, "trace_locator": example_location, "verification_locator": location, "resources": resources, "classification": entry["classification"], "initial_solvable": True, "terminal_no_winning_suffix": dead_end, "isomorphism_summary": {"floors": len(floors), "objects": len(object_ids), "verified_cells": sum(int(floor["verified_cells"]) for floor in floors), "spawn_empty_path_length": len(mapped_path), "layout_hash": certificate["layout_hash"]}, "replayer_sha256": fingerprint}
                    fragment_offsets.add(queue_offset)
                    fragment_indices.add(index)
                    covered_offsets.add(queue_offset)
                    pending = None
                elif kind == "replay_footer":
                    need(header is not None and footer is None and pending is None, f"Unexpected replay footer: {path.name}")
                    footer = entry
                else:
                    raise Invalid(f"Unexpected or stopped replay entry: {path.name}:{line_no}/{kind}")
                offset += len(raw)
        need(header is not None and footer is not None and pending is None, f"Replay fragment is unfinished: {path.name}")
        need(footer.get("measurement_completed") is True and footer.get("stopped_at_case_boundary") is False and footer.get("errors") == [] and footer.get("baseline_errors") == [], f"Replay footer does not claim clean completion: {path.name}")
        begin, count = int(header["offset"]), int(header["requested_replays"])
        need(fragment_offsets == set(range(begin, begin + count)) and footer.get("completed_replays") == count and footer.get("requested_replays") == count and footer.get("next_queue_offset") == begin + count, f"Partial replay fragment was promoted as complete: {path.name}")
        need(footer.get("policy_dead_ends_with_full_terminal_proof") == sum(expected[index]["outcome"] == "dead_end" for index in fragment_indices) and footer.get("initial_unsatisfiable_cases_proven") == 0, f"Replay terminal proof count differs: {path.name}")
        for key, value in footer.items():
            need(summary.get(key) == value, f"Replay summary/footer field differs: {path.name}/{key}")
        sources.append({"path": path, "summary_path": summary_path, "portable_path": portable_path, "sha256": journal_hash, "offset": begin, "completed_replays": count, "indices": sorted(fragment_indices), "engine_pid": header.get("engine_pid"), "source_aggregate_summary_sha256": header.get("source_aggregate_summary_sha256"), "replayer_sha256": fingerprint})
    need(set(verified) == set(expected) and covered_offsets == set(range(len(ordered))), f"Failure replay coverage is not global: missing indices={sorted(set(expected)-set(verified))[:20]}")
    return verified, sources


def policy_summary(records, initial, prices):
    result = {"runs": len(records), "outcomes": dict(collections.Counter(row["outcome"] for row in records)), "unique_layout_seeds": len({row["layout_seed"] for row in records}), "unique_layouts": len({row["layout_hash"] for row in records}), "unique_decision_sequences": len({row["decision_signature"] for row in records})}
    for key in ("hp", "atk", "def", "gold", "floor", "cleared_count"):
        result["final_" + key] = metric([int(row["final"][key]) for row in records])
    result["net_hp_delta_final_minus_initial"] = metric([int(row["final"]["hp"]) - int(initial["hp"]) for row in records])
    result["final_keys"] = {color: metric([int(row["final"]["keys"].get(color, 0)) for row in records]) for color in initial["keys"]}
    result["decisions"] = metric([int(row["decision_count"]) for row in records])
    result["elapsed_ms"] = metric([float(row["elapsed_ms"]) for row in records])
    for field in ("navigation_moves", "preview_actual_comparisons", "local_queries", "global_queries", "nav_nodes", "armor_gate_preparations"):
        result[field] = sum(int(row[field]) for row in records)
    if prices is not None:
        spends = []
        for row in records:
            spent = 0
            for purchase, quantity in row["final"]["purchases"].items():
                need(purchase in prices and 0 <= int(quantity) <= prices[purchase][1], f"Unknown or over-stock purchase: {purchase}")
                spent += int(quantity) * prices[purchase][0]
            spends.append(spent)
        result["gross_gold_spent_from_exact_purchase_inventory"] = metric(spends)
        result["total_gold_spent"] = sum(spends)
    return result


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def json_lines(path, values):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for value in values:
            stream.write(compact(value) + "\n")


def build(args):
    paths = [path.resolve() for path in args.reports]
    rows, examples, sources, binding, shared = validate_shards(paths, args)
    canonical, initial, source_check, witness = bind_canonical(args, binding, examples)
    prices = price_catalog(canonical)
    records = [row["record"] for row in rows]
    failed = []
    for row in rows:
        record, index = row["record"], int(row["record"]["index"])
        if record["outcome"] == "won":
            continue
        sample = examples.get(index)
        failed.append({"index": index, "policy": record["policy"], "layout_seed": record["layout_seed"], "policy_seed": record["policy_seed"], "record": record, "report_locator": row["report_locator"], "journal_locator": row["journal_locator"], "terminal_budget": record["final"], "full_terminal_state": sample["example"]["final_state"] if sample else None, "trace_locator": sample["journal_locator"] if sample else None, "retained_terminal_frontier_summary": sample["example"].get("terminal_frontier") if sample else None, "observed_classification": "policy_terminal_dead_end" if record["outcome"] == "dead_end" else "policy_search_unresolved", "initial_unsatisfiable_proven": False, "independent_failure_replay_required": True, "replay_obligations": ["Reproduce index/policy/layout_hash/decision_signature/final/policy_rng_final exactly.", "Retain the full core terminal state and complete executable path.", "For a dead_end, rerun complete global navigation BFS and retain nodes/boundary proof.", "Bind canonical winning witnesses to this mirrored variant with a coordinate/stair/ID isomorphism and safe-spawn connectivity certificate."]})
    replay_records, replay_sources = {}, []
    if args.failure_replays:
        replay_records, replay_sources = consume_failure_replays(args.failure_replays, rows, binding, shared, witness, args.replay_input, args.replayer_script)
        for item in failed:
            proof = replay_records[item["index"]]
            item.update({"full_terminal_state": proof["full_terminal_state"], "trace_locator": proof["trace_locator"], "terminal_proof_locator": proof["verification_locator"], "isomorphism_certificate_locator": proof["verification_locator"], "observed_classification": proof["classification"], "independent_failure_replay_required": False, "replay_obligations": [], "initial_solvable_by_bound_isomorphism_and_witnesses": proof["initial_solvable"], "terminal_no_winning_suffix": proof["terminal_no_winning_suffix"], "replayed_resource_ledger": proof["resources"], "isomorphism_summary": proof["isomorphism_summary"]})
    summary = {"schema_version": 1, "suite": "campaign-shard-readonly-aggregation/v1", "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "measurement_validation": {"passed": True, "completed_runs": len(rows), "expected_range": [args.expected_start, args.expected_start + args.expected_total - 1], "shards": len(sources), "runs_per_shard": args.per_shard, "duplicate_or_missing_indices": 0, "errors": 0, "preview_actual_mismatches": 0}, "source_hashes": binding, "shared_configuration": shared, "source_file_verification": source_check, "canonical_initial_witnesses": witness, "initial_resources": initial, "all_policies": policy_summary(records, initial, prices), "per_policy": {policy: policy_summary([row for row in records if row["policy"] == policy], initial, prices) for policy in POLICIES}, "failure_count": len(failed), "failure_records_with_retained_full_state_and_trace": sum(item["full_terminal_state"] is not None for item in failed), "independent_failure_replays_still_required": len(failed), "failure_evidence_complete": not failed, "initial_unsatisfiable_cases_proven": 0, "sum_shard_elapsed_ms": sum(float(item["elapsed_ms"]) for item in sources), "max_shard_elapsed_ms": max(float(item["elapsed_ms"]) for item in sources), "initial_solvability_interpretation": "A policy dead end is not initial-map unsatisfiability. Bound canonical winning witnesses support canonical solvability. Per-failure variant isomorphism and full replay are still required before classifying every mirrored initial state as proven solvable.", "resource_metric_limits": ["Final HP minus initial HP is net change, not gross battle damage: healing can offset damage.", "Gross gold spend is computed only when the exact hash-bound canonical offer table is supplied.", "All-run gross battle damage, healing and key consumption were not retained by the baseline; they are not invented from final budgets.", "No human input, browser, visuals, physical-device performance or hours-of-play evidence is implied."], "inputs": [{"start_index": item["start_index"], "completed_runs": item["completed_runs"], "original_report_sha256": item["original_report_sha256"], "journal_sha256": item["journal_sha256"], "report_path": f"inputs/shard-{item['start_index']:05d}.report.json", "journal_path": f"inputs/shard-{item['start_index']:05d}.journal.jsonl"} for item in sources]}
    if args.failure_replays:
        totals = {key: sum(int(item["resources"][key]) for item in replay_records.values()) for key in ("gross_battle_damage", "gross_healing", "gold_spent", "gold_gained", "navigation_moves", "preview_actual_comparisons")}
        for key in ("keys_consumed", "keys_collected"):
            colors = {color for item in replay_records.values() for color in item["resources"][key]}
            totals[key] = {color: sum(int(item["resources"][key].get(color, 0)) for item in replay_records.values()) for color in sorted(colors)}
        summary.update({"failure_records_with_retained_full_state_and_trace": len(replay_records), "independent_failure_replays_still_required": 0, "failure_evidence_complete": True, "failed_initial_variants_with_bound_solvability_certificate": len(replay_records), "failure_subset_gross_resource_ledger": {"scope": "Only the independently replayed nonwinning subset, not all runs.", "runs": len(replay_records), **totals}, "failure_replay_inputs": [{key: item[key] for key in ("portable_path", "sha256", "offset", "completed_replays", "engine_pid", "source_aggregate_summary_sha256", "replayer_sha256")} for item in replay_sources], "initial_solvability_interpretation": "Every original nonwin was independently replayed with exact record equality, full terminal state/path and complete global BFS. Each initial failed variant also has a coordinate/ID/stair/attribute isomorphism and empty spawn path tied to four actual canonical winning witnesses. Dead-end outcomes are policy failures in a solvable initial family; bounded/other outcomes retain their own scope. No initial unsatisfiability is inferred."})
        summary["bound_failure_replay_input"] = {"path": "failure-replays/bound-input.json", "sha256": sha_file(args.replay_input), "original_aggregate_summary_path": "failure-replays/summary.json", "original_aggregate_summary_sha256": sha_file(args.replay_input.parent / "summary.json"), "original_winning_witnesses_path": "failure-replays/canonical-winning-witnesses.json", "original_winning_witnesses_sha256": witness["sha256"]}
        summary["canonical_initial_witnesses"]["path"] = "failure-replays/canonical-winning-witnesses.json"
    if args.check_only:
        print(compact({"validated": True, "runs": len(rows), "failures": len(failed), "failure_evidence_complete": summary["failure_evidence_complete"], "policies": {p: summary["per_policy"][p]["outcomes"] for p in POLICIES}, "source_hashes": binding, "writes": 0}))
        return
    out = args.output.resolve()
    need(not out.exists(), f"Output must be a new directory: {out.name}")
    out.mkdir(parents=True)
    (out / "inputs").mkdir()
    dump(out / "summary.json", summary)
    json_lines(out / "runs.jsonl", rows)
    json_lines(out / "failure-records.jsonl", failed)
    json_lines(out / "retained-examples.jsonl", ({"index": index, **item} for index, item in sorted(examples.items())))
    if not args.failure_replays:
        replay_input = {"schema_version": 1, "scope": "Exact independent replay of every nonwinning baseline run; no baseline edits or new policy decisions.", "source_hashes": binding, "engine": shared["engine"], "master_layout_seed": shared["master_layout_seed"], "master_policy_seed": shared["master_policy_seed"], "policies": shared["policies"], "variant_spec": shared["variant_spec"], "layout_draws_per_run": shared["layout_draws_per_run"], "local_floor_horizon": shared["local_floor_horizon"], "max_decisions": shared["max_decisions"], "canonical_witness_binding": witness, "expected_records": [item["record"] for item in failed], "source_aggregate_summary_sha256": sha_file(out / "summary.json")}
        dump(out / "failure-replay-input.json", replay_input)
    else:
        # Preserve the exact input actually executed, not a regenerated queue
        # bound to this later final summary's timestamp/hash.
        (out / "failure-replays").mkdir()
        shutil.copyfile(args.replay_input, out / "failure-replays/bound-input.json")
        shutil.copyfile(args.replay_input.parent / "summary.json", out / "failure-replays/summary.json")
        shutil.copyfile(args.replay_input.parent / "canonical-winning-witnesses.json", out / "failure-replays/canonical-winning-witnesses.json")
    for item in sources:
        target = f"shard-{item['start_index']:05d}"
        sanitized = dict(item["report"])
        sanitized["journal_path"] = f"inputs/{target}.journal.jsonl"
        dump(out / "inputs" / (target + ".report.json"), sanitized)
        shutil.copyfile(item["journal_path"], out / "inputs" / (target + ".journal.jsonl"))
    if args.canonical_witness_report and not args.failure_replays:
        shutil.copyfile(args.canonical_witness_report, out / "canonical-winning-witnesses.json")
    if replay_sources:
        (out / "replays").mkdir()
        for item in replay_sources:
            destination = out / item["portable_path"]
            shutil.copyfile(item["path"], destination)
            shutil.copyfile(item["summary_path"], Path(str(destination) + ".summary.json"))
        if args.replayer_script:
            shutil.copyfile(args.replayer_script, out / "replay_campaign_failures.gd")
    shutil.copyfile(Path(__file__), out / "aggregate_campaign_shards.py")
    (out / "README.txt").write_text("This package validates completed shard measurements; it does not replace real game acceptance.\n\nsummary.json contains counts, source bindings and honest metric limits. runs.jsonl covers every absolute index exactly once. failure-records.jsonl preserves every nonwin, its final budget and exact report/journal locator. If failure_evidence_complete is false, missing full states/traces are explicitly null and failure-replay-input.json queues the remaining proof work. If true, every failure has an exact independent replay, full state/trace locator, full global BFS and graph/spawn certificate in replays/. Four locally completed replay fragments are accepted only when their queue offsets and absolute indices cover the entire failure set without overlap.\n\nInput journals are byte-exact and line/byte locators remain valid. Input report copies have only journal_path replaced by the portable package path; original report hashes are recorded separately. Source fingerprints are not claims that the current files were tested unless source_file_verification.passed is true.\n\nA policy failure is not an unsatisfiable initial map. Exactly four distinct canonical winning witnesses and per-variant graph/spawn certificates are separate evidence obligations. A net HP decrease is not gross damage. Gross failure-subset resource ledgers do not cover successful runs.\n", encoding="utf-8", newline="\n")
    entries = []
    for path in sorted(out.rglob("*")):
        if path.is_file():
            entries.append({"path": path.relative_to(out).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)})
    dump(out / "manifest.json", {"schema_version": 1, "files": entries, "note": "Manifest covers payload files, excluding itself and the external archive receipt."})
    archive = out.with_suffix(".zip")
    need(not archive.exists(), f"Archive already exists: {archive.name}")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(out).as_posix())
    receipt = {"archive": archive.name, "bytes": archive.stat().st_size, "sha256": sha_file(archive), "manifest_sha256": sha_file(out / "manifest.json"), "completed_runs": len(rows), "failure_count": len(failed), "failure_evidence_complete": summary["failure_evidence_complete"]}
    dump(archive.with_suffix(".zip.receipt.json"), receipt)
    print(compact({"validated": True, "runs": len(rows), "failures": len(failed), "output": str(out), "archive": receipt}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--expected-total", type=int, default=10000)
    parser.add_argument("--expected-start", type=int, default=0)
    parser.add_argument("--expected-shards", type=int, default=4)
    parser.add_argument("--per-shard", type=int, default=2500)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--canonical-witness-report", type=Path)
    parser.add_argument("--failure-replays", nargs="+", type=Path)
    parser.add_argument("--replay-input", type=Path, help="Original byte-exact failure queue executed by replay workers; its sibling summary/witness bytes are preserved.")
    parser.add_argument("--replayer-script", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/campaign-10000-aggregate"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        need(args.expected_total > 0 and args.expected_shards > 0 and args.per_shard > 0 and args.expected_total == args.expected_shards * args.per_shard, "Expected total must equal shard count times per-shard count.")
        build(args)
    except (Invalid, OSError, ValueError, KeyError, TypeError) as error:
        print(compact({"validated": False, "error": str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
