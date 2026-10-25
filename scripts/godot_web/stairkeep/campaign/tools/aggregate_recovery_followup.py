"""Read-only, byte-bound validation of early guard and late checkpoint QA journals.

Full mode requires the exact 1336 + 26 original cohort, once each, with actual
complete winning recovery traces. --allow-partial validates completed shards for
calibration without claiming completion of the complete recovery measurement.
No rules, combat arithmetic, baseline outcomes, journals or queues are modified.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

BOUND_INPUT = "45b905d9157585ba8a06df612c9a727ad5bbe3ee7c89c4e4bae0253f94c567d0"
DEFAULT_BUDGETS = {"max_expanded": 5000, "max_states": 20000, "max_msec": 15000, "navigation_max_nodes": 0}
IDENTITY = ("index", "layout_seed", "policy_seed", "decision_signature")
SEQUENCE = ("content_id", "canonical_content_sha256", "rules_version", "rules_sha256", "variant_spec", "root_seed", "campaign_seed", "sequence_state", "attempt_index", "variant_draw_count", "floor_mirrors", "resolved_start", "transformed_content_sha256")
SOURCE_FILES = {
    "source_data_sha256": "data/levels21.json", "base_rules_sha256": "scripts/base_rules.gd",
    "variant_sha256": "scripts/campaign_variant.gd", "navigation_sha256": "scripts/campaign_navigation.gd",
    "simulation_sha256": "tests/simulate_campaign.gd", "campaign_rules_sha256": "scripts/campaign_rules.gd",
    "campaign_save_v2_sha256": "scripts/campaign_save_v2.gd", "purchase_guard_sha256": "scripts/purchase_guard.gd",
    "failure_replayer_sha256": "tests/replay_campaign_failures.gd",
}
PREFIX_COUNTS = {"defense_door_open/flask": 452, "defense_door_open/ward": 394, "key_available/flask": 151,
                 "key_available/ward": 139, "key_uncollected/flask": 95, "key_uncollected/ward": 105}


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize(value: Any, field: str = "") -> Any:
    if isinstance(value, dict):
        return {key: normalize(item, key) for key, item in value.items()}
    if isinstance(value, list):
        result = [normalize(item) for item in value]
        if field in ("cleared", "cleared_object_ids"):
            result.sort()
        elif field == "floors" and all(isinstance(item, dict) and "id" in item for item in result):
            result.sort(key=lambda item: int(item["id"]))
        elif field == "objects" and all(isinstance(item, dict) and "id" in item for item in result):
            result.sort(key=lambda item: str(item["id"]))
        return result
    if isinstance(value, float):
        require(math.isfinite(value) and value.is_integer(), "Nonintegral value in an integer canonical snapshot")
        return int(value)
    require(value is None or isinstance(value, (str, int, bool)), "Unsupported canonical value")
    return value


def same(left: Any, right: Any) -> bool:
    # Python equates True with 1, whereas the bound Godot serializer does not.
    # Compare canonical encodings so boolean and numeric types remain distinct.
    return json.dumps(normalize(left), ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(normalize(right), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    text = json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sequence_equal(left: dict, right: dict) -> bool:
    return all(same(left.get(key), right.get(key)) for key in SEQUENCE)


def budget(core: dict) -> dict:
    return {key: copy.deepcopy(core[key]) for key in ("pos", "hp", "atk", "def", "gold", "keys", "purchases", "won")} | {
        "floor": int(core["floor"]) + 1, "cleared_count": len(core["cleared"])}


def valid_core(core: dict) -> None:
    for stat in ("hp", "atk", "def", "gold"):
        require(isinstance(core.get(stat), (int, float)) and not isinstance(core[stat], bool) and float(core[stat]).is_integer() and core[stat] >= 0, "Invalid or negative core resource: " + stat)
    require(core["hp"] > 0, "Authoritative ordinary core HP must remain positive")
    for group in ("keys", "purchases"):
        require(all(not isinstance(n, bool) and isinstance(n, (int, float)) and float(n).is_integer() and n >= 0 for n in core[group].values()), "Negative/noninteger inventory: " + group)
    require(len(core["cleared"]) == len(set(core["cleared"])), "Duplicate cleared objects")


def state_binding(snapshot: dict) -> str:
    return content_hash({"canonical": snapshot["canonical_content_sha256"], "rules": snapshot["rules_sha256"],
                         "variant": snapshot["transformed_content_sha256"], "seed": snapshot["campaign_seed"],
                         "core_state": snapshot["core_state"], "failed": snapshot["failed"], "story_flags": snapshot["story_flags"]})


def complete_unsat(report: dict, snapshot: dict) -> None:
    receipt = report.get("receipt", {})
    require(report.get("result") == "unsatisfiable" and receipt.get("status") == "unsatisfiable" and receipt.get("complete") is True, "A known loss has no complete unsatisfiability receipt")
    require(receipt.get("state_sha256") == state_binding(snapshot), "Loss receipt belongs to a different exact state")
    for field in ("canonical_content_sha256", "transformed_content_sha256", "rules_sha256"):
        require(receipt.get(field) == snapshot[field], "Loss receipt source binding differs: " + field)


def empty_global(proof: dict) -> None:
    require(proof.get("complete") is True and proof.get("queue_exhausted") is True and proof.get("scope") == "global", "Terminal Navigation proof is incomplete or local")
    require(proof.get("options") == [] and proof.get("errors") == [], "Terminal proof has a legal action or a schema error")
    require(len(proof.get("nodes", [])) == int(proof.get("reachable", -1)), "Terminal proof node coverage differs")


class Validator:
    def __init__(self, input_path: Path, project: Path, harness_hashes: dict | None = None):
        self.input_path = input_path.resolve()
        require(sha_file(input_path) == BOUND_INPUT, "The original recovery queue SHA differs")
        self.queue = json.loads(input_path.read_text(encoding="utf-8"))
        require(len(self.queue["early_cases"]) == 1336 and len(self.queue["late_cases"]) == 26, "Original cohort sizes differ")
        self.base = (self.input_path.parent / self.queue["input"]["path_base"]).resolve()
        self.project = project.resolve()
        self.source_hashes = {key: sha_file(project / relative) for key, relative in SOURCE_FILES.items()}
        for key, digest in self.source_hashes.items():
            require(digest == self.queue["source_bindings"][key], "Frozen source differs: " + key)
        self.hashes = harness_hashes or {
            "early": sha_file(project / "tests/replay_early_purchase_guard.gd"),
            "late": sha_file(project / "tests/replay_late_checkpoint_recovery.gd"),
            "helper": sha_file(project / "tests/recovery_followup_helpers.gd"),
            "route": sha_file(project / "tests/replay_variant_routes.gd"),
        }
        self.hashes.setdefault("solver", sha_file(project / "tests/campaign_solver.gd"))
        self.canonical = json.loads((project / "data/levels21.json").read_text(encoding="utf-8"))
        self.blade = next(route for route in self.canonical["validated_routes"] if route["name"] == "blade")
        self.objects = {item["id"]: item for floor in self.canonical["floors"] for item in floor["objects"]}
        self.raw_sources: dict = {}
        self.engine: dict | None = None
        self.seen = {"early": {}, "late": {}}
        self.offsets = {"early": set(), "late": set()}
        self.receipts: list[dict] = []
        self.journals: list[dict] = []
        self.stats = {"early": collections.Counter(), "late": collections.Counter()}
        self.prefixes: collections.Counter = collections.Counter()
        self.checkpoint_results: collections.Counter = collections.Counter()
        self.nearest: collections.Counter = collections.Counter()

    def original(self, case: dict) -> dict:
        locator = case["trace_locator"]
        relative = locator["path"]
        path = (self.base / relative).resolve()
        require(path.is_relative_to(self.base), "Original source leaves its declared workspace root")
        expected = self.queue["source_files"][relative]
        if relative not in self.raw_sources:
            digest = sha_file(path)
            require(digest == expected["raw_sha256"] == expected["sha256"] and path.stat().st_size == expected["bytes"], "Original raw journal changed: " + relative)
            self.raw_sources[relative] = {"sha256": digest, "bytes": path.stat().st_size}
        with path.open("rb") as file:
            file.seek(int(locator["byte_offset"]))
            raw = file.read(int(locator["byte_length"]))
        require(len(raw) == locator["byte_length"] and hashlib.sha256(raw).hexdigest() == locator["line_sha256"], "Original exact trace line differs")
        record = json.loads(raw)
        require(record["kind"] == "example", "Original locator has the wrong record kind")
        example = record["example"]
        for key in IDENTITY + ("layout_hash",):
            require(same(case[key], example["record"][key]), "Original case identity differs: " + key)
        require(same(case["full_terminal_state"], example["final_state"]), "Original terminal state differs from queue")
        require(hashlib.sha256("\n".join(d["chosen_id"] for d in example["decisions"]).encode()).hexdigest() == case["decision_signature"], "Original decision signature differs")
        return example

    def identity(self, cohort: str, row: dict, offset_field: str) -> tuple[int, dict]:
        offset = row.get(offset_field)
        require(not isinstance(offset, bool) and isinstance(offset, (int, float)) and float(offset).is_integer(), "Missing exact cohort offset")
        offset = int(offset)
        cases = self.queue[cohort + "_cases"]
        require(0 <= offset < len(cases), "Cohort offset outside original queue")
        case = cases[offset]
        for field in IDENTITY:
            require(same(row.get(field), case[field]), "Follow-up identity differs: " + field)
        require(case["index"] not in self.seen[cohort] and offset not in self.offsets[cohort], "Repeated sample/shard is not an independent original case")
        self.seen[cohort][case["index"]] = offset
        self.offsets[cohort].add(offset)
        return offset, case

    def route_win(self, value: dict, start: dict, early: bool) -> dict:
        trace = value.get("trace", [])
        require(value.get("passed" if early else "won") is True and value.get("tested", True) is True and not value.get("fatal", False), "Winning route was not actually verified")
        require(len(trace) == len(self.blade["events"]), "Complete initial blade route omits events")
        final = value["full_final_snapshot" if early else "final_snapshot"]
        require(sequence_equal(start, final) and final["failed"] is False and final["core_state"]["won"] is True, "Winning final state changes seed/rules or lacks actual victory")
        purchases: collections.Counter = collections.Counter()
        cleared = set()
        last = budget(start["core_state"])
        steps = comparisons = 0
        for position, (event, ledger, actual) in enumerate(zip(self.blade["events"], self.blade["ledger"], trace)):
            require(actual["event"] == event and int(actual["event_index" if early else "canonical_index"]) == position, "Actual winning event order differs")
            require(same(actual["before"], last), "Winning budget trace is discontinuous")
            execution = actual["actual_execution"]
            require(execution.get("ok") is True and not execution.get("error"), "Actual winning action failed")
            actions = actual["actions" if early else "path"]
            require(actions and all(step.get("kind") in ("move", "stairs", "buy") for step in actions), "Winning path contains an unsupported or absent actual action")
            steps += len(actions)
            comparisons += int(execution.get("preview_comparisons", 0))
            for field in ("hp", "atk", "def", "gold", "keys"):
                require(same(actual["after"][field], ledger["state"][field]), "Actual winning event differs from authored resource ledger: " + event)
            if "damage" in ledger:
                require(actual["before"]["hp"] - actual["after"]["hp"] == ledger["damage"], "Actual deduction differs from the independently authored ledger")
            if event.startswith("buy:"):
                purchases[event[4:]] += 1
            elif self.objects[event]["kind"] not in ("stairs", "shop"):
                cleared.add(event)
            require(same(actual["after"]["purchases"], dict(purchases)) and actual["after"]["cleared_count"] == len(cleared), "Actual event inventory/world counts differ")
            last = actual["after"]
        core = final["core_state"]
        valid_core(core)
        require(same(last, budget(core)) and set(core["cleared"]) == cleared and same(core["purchases"], dict(purchases)), "Actual final world/stock differs from the complete winning events")
        require(trace[-1]["actual_core_sha256" if early else "full_core_sha256"] == content_hash(core), "Actual final winning core hash differs")
        for field, expected in self.blade["final"].items():
            require(same(core[field], expected), "Actual final resource budget differs: " + field)
        if early:
            require(value.get("events_checked") == len(trace) == value.get("expected_events") and value.get("actual_actions") == steps, "Early winning action/event totals differ")
            require(value.get("actual_edge_bought_once") is True and core["purchases"]["f01_shop/edge"] == 1, "Actual recovered edge was not bought exactly once")
            cancel = value["cancellation"]
            require(cancel.get("passed") is True and cancel.get("full_state_unchanged") is True and cancel["cancel"].get("ok") is True, "Actual cancel workflow did not pass")
            require(same(cancel["actual_before_cancel_full_snapshot"], cancel["default_preview"]["before_snapshot"]), "Canceled preview does not bind the actual full state")
        return {"events": len(trace), "actions": steps, "combat_comparisons": comparisons, "final_core_sha256": content_hash(core)}

    def early_case(self, row: dict) -> dict:
        offset, case = self.identity("early", row, "cohort_offset")
        original = self.original(case)
        require(row.get("passed") is True and row.get("errors") == [], "Early case did not pass")
        initial = row["initial_full_snapshot"]
        terminal = row["actual_terminal_full_snapshot"]
        require(initial["campaign_seed"] == case["layout_seed"] and initial["transformed_content_sha256"] == case["layout_hash"] and same(initial["core_state"], original["initial_state"]), "Actual initial variant differs")
        require(same(terminal["core_state"], case["full_terminal_state"]) and sequence_equal(initial, terminal) and row.get("original_terminal_reproduced") is True, "Original losing terminal was not actually reproduced")
        empty_global(row["actual_terminal_global_proof"])
        intervention = row["intervention"]
        preview = intervention["default_preview"]
        commit = intervention["default_commit"]
        before = intervention["guarded_pre_purchase_full_snapshot"]
        after = intervention["unguarded_actual_post_purchase_full_snapshot"]
        for field, snapshot in (("before", before), ("after", after)):
            require(same(preview[field + "_snapshot"], snapshot), "Guard preview differs from the actual paired snapshot")
            binding = preview[field + "_binding"]
            require(binding["full_snapshot_sha256"] == content_hash(snapshot) and binding["state_sha256"] == state_binding(snapshot), "Guard binding differs from full actual state")
            require(binding["guard_source_sha256"] == self.source_hashes["purchase_guard_sha256"] and binding["navigation_source_sha256"] == self.source_hashes["navigation_sha256"] and binding["solver_source_sha256"] == self.hashes["solver"], "Guard query source binding differs from the frozen actual sources")
            require(binding["rules_fingerprint"] == snapshot["rules_sha256"], "Guard rules fingerprint differs from the actual snapshot")
        require(same(preview["requested_budgets"], DEFAULT_BUDGETS) and same(preview["effective_budgets"], DEFAULT_BUDGETS), "Guard did not use unchanged production defaults")
        require(preview.get("ok") is True and "token" not in preview and "token" not in commit, "Unavailable guard preview or leaked authority token")
        classification = row["classification"]
        require(classification in ("known_losing", "unknown", "known_winning") and preview["classification"] == classification, "Guard classification differs")
        decision_index, path_step = int(intervention["decision"]), int(intervention["path_step"])
        original_decision = original["decisions"][decision_index]
        require(original_decision["chosen_id"] in ("f01_shop/ward", "f01_shop/flask") and path_step == len(original_decision["path"]) - 1, "Intervention is not the original early purchase")
        prefix = "defense_door_open" if "f01_defense_door" in before["core_state"]["cleared"] else ("key_available" if before["core_state"]["keys"]["yellow"] > 0 else "key_uncollected")
        prefix += "/" + original_decision["chosen_id"].split("/")[-1]
        require(row["prefix_type"] == prefix, "Incorrect actual prefix label")
        self.prefixes[prefix] += 1
        if classification == "known_losing":
            complete_unsat(preview["solver_report"], after)
            require(row["default_blocked"] is True and intervention["full_state_unchanged_after_default_block"] is True and commit.get("ok") is False and commit.get("status") == "blocked_known_loss", "Known loss was not default-blocked")
            require(same(commit["actual_after_snapshot"], before) and same(commit["after_snapshot"], before) and commit.get("token_consumed") is True, "Default block mutated the full state or retained its ticket")
            explicit = row["explicit_override"]
            second, accepted = explicit["preview"], explicit["commit"]
            require(explicit.get("performed") is True and accepted.get("confirmed") is True and accepted.get("ok") is True and accepted.get("buy_result", {}).get("ok") is True, "Original purchase did not receive explicit actual confirmation")
            require(same(second["before_snapshot"], before) and same(second["after_snapshot"], after) and same(accepted["actual_after_snapshot"], after), "Explicit purchase does not equal the exact original post-state")
            require(second["classification"] in ("known_losing", "unknown"), "A complete winning witness contradicts the first complete loss proof")
            if second["classification"] == "known_losing":
                complete_unsat(second["solver_report"], after)
                require(accepted.get("accepted_known_loss") is True, "Known-loss confirmation was not recorded")
            self.stats["early"]["second_query/" + second["classification"]] += 1
            require(row.get("explicit_override_reproduced_original_terminal") is True, "Confirmed original policy terminal was not reproduced")
        else:
            require(row.get("default_blocked") is False and commit.get("ok") is True and same(commit["actual_after_snapshot"], after), "Unknown/winning query changed original legal purchase semantics")
        flattened = [action for decision in original["decisions"] for action in decision["path"]]
        paired = row["actual_paired_actions"]
        require(len(paired) == len(flattened) == row["actual_action_count"], "Actual paired action coverage differs")
        previous = content_hash(initial)
        for action, record in zip(flattened, paired):
            require(same(action, record["action"]) and record["paired_actual_full_snapshot_equal"] is True, "Original/actual action pairing differs")
            require(record["before_full_snapshot_sha256"] == previous and record["actual_execution"]["ok"] is True and record["unguarded_execution"]["ok"] is True, "Actual full snapshot chain is discontinuous or failed")
            previous = record["after_full_snapshot_sha256"]
        require(previous == content_hash(terminal), "Actual paired chain does not end at the original full terminal snapshot")
        require(intervention["original_policy_after_block_continued_without_confirmation"] is False, "Blocked branch silently continued the original policy")
        recovery = row["complete_initial_checkpoint_recovery"]
        restored = recovery["full_restored_snapshot"]
        expected = copy.deepcopy(initial)
        event_id = row["actual_failure"]["failure_event_id"]
        expected["failure_events_seen"] = list(dict.fromkeys(initial["failure_events_seen"] + [event_id]))
        require(recovery["retained_history_fields"] == ["failure_events_seen", "consumed_loss_ids"] and same(restored, expected), "Complete initial restoration omitted a field or manufactured resources/stock/history")
        require(row["initial_checkpoint_restored"] is True and recovery["restored"] is True and sequence_equal(initial, restored), "Initial checkpoint restoration did not pass")
        valid_core(restored["core_state"])
        actual_win = row["actual_complete_winning_recovery"]
        win = self.route_win(row["winning_recovery"], restored, True) if actual_win else None
        require(actual_win == recovery["actual_full_winning_suffix_tested"], "Actual full winning coverage is mislabeled")
        self.stats["early"]["classification/" + classification] += 1
        self.stats["early"]["default_blocks"] += int(row["default_blocked"])
        self.stats["early"]["initial_restores"] += 1
        self.stats["early"]["actual_complete_wins"] += int(actual_win)
        self.stats["early"]["explicit_terminal_reproductions"] += int(row.get("explicit_override_reproduced_original_terminal", False))
        return {"cohort": "early", "cohort_offset": offset, **{key: case[key] for key in IDENTITY}, "prefix_type": prefix,
                "classification": classification, "default_blocked": row["default_blocked"], "initial_checkpoint_restored": True,
                "actual_complete_winning_recovery": actual_win, "actual_winning_trace": win,
                "pre_purchase_current_state_winning_suffix_tested": False,
                "pre_purchase_solvability_inferred_from_initial_rollback": False,
                "original_trace_locator": case["trace_locator"], "original_verification_locator": case["verification_locator"]}

    def restore_late(self, evidence: dict, original_failed: dict) -> dict:
        checkpoint_id = evidence["checkpoint_id"]
        position = next(i for i, checkpoint in enumerate(original_failed["checkpoints"]) if checkpoint["checkpoint_id"] == checkpoint_id)
        checkpoint = original_failed["checkpoints"][position]
        expected = copy.deepcopy(checkpoint)
        expected["checkpoints"] = original_failed["checkpoints"][:position + 1]
        for key in ("failure_events_seen", "consumed_loss_ids"):
            expected[key] = original_failed[key]
        actual = evidence["actual_restored_snapshot"]
        require(evidence["full_snapshot_matches_contract"] is True and evidence["historical_lists_preserved"] is True and same(expected, actual), "Late complete checkpoint restoration does not match its actual captured snapshot")
        require(evidence["captured_checkpoint_sha256"] == content_hash(checkpoint) and evidence["expected_complete_snapshot_sha256"] == content_hash(expected) and evidence["actual_complete_snapshot_sha256"] == content_hash(actual), "Late restoration snapshot hashes differ")
        valid_core(actual["core_state"])
        return actual

    def late_attempt(self, row: dict, restored: dict) -> None:
        attempt = row["attempt"]
        require(attempt.get("fatal") is False, "Late suffix hit a fatal actual-action invariant")
        outcome = str(attempt.get("result", "unknown"))
        self.checkpoint_results[outcome] += 1
        if outcome == "proven_no_ordinary_suffix":
            complete_unsat(attempt["solver"], restored)
        if attempt.get("won") is True:
            final = attempt["final_snapshot"]
            require(final["core_state"]["won"] is True and final["failed"] is False and sequence_equal(restored, final), "Nearest-checkpoint win lacks a real bound winning final state")
            paths = attempt.get("trace", attempt.get("actual_actions", []))
            require(paths, "A claimed checkpoint win has no actual action trace")
            for step in paths:
                require(step.get("actual_execution", step.get("execution", {})).get("ok") is True, "A claimed checkpoint win contains a failed actual action")
            valid_core(final["core_state"])

    @staticmethod
    def locator(meta: dict, path: Path) -> dict:
        return {"path": path.name, **{key: meta[key] for key in ("line", "byte_offset", "byte_length", "line_sha256")}}

    @staticmethod
    def require_locator(locator: dict, metas: dict, path: Path, kind: str, index: int) -> dict:
        require(locator.get("path") == path.name and locator.get("byte_offset") in metas, "Internal proof locator does not point into this actual journal")
        meta = metas[locator["byte_offset"]]
        for field in ("line", "byte_offset", "byte_length", "line_sha256"):
            require(locator.get(field) == meta[field], "Internal proof byte locator differs: " + field)
        require(meta["kind"] == kind and meta["index"] == index, "Internal proof locator has the wrong kind or original index")
        return meta

    def consume(self, path: Path, cohort: str) -> None:
        require(path.resolve() not in {Path(item["private_source_path"]) for item in self.journals}, "Duplicate journal file")
        summary = json.loads(Path(str(path) + ".summary.json").read_text(encoding="utf-8"))
        digest = sha_file(path)
        require(summary.get("journal_sha256") == digest and summary.get("measurement_completed") is True and summary.get("errors") == [], "Journal summary is incomplete, errored or does not bind actual bytes")
        header = footer = None
        metas: dict = {}
        offsets_here = []
        indices_here = []
        local_results = []
        current: dict | None = None
        expected_engine_fields = ("major", "minor", "patch", "status", "build", "hash")
        with path.open("rb") as file:
            line = 0
            while raw := file.readline():
                line += 1
                require(raw.endswith(b"\n"), "Truncated journal line")
                offset = file.tell() - len(raw)
                row = json.loads(raw)
                kind = row.get("kind")
                meta = {"line": line, "byte_offset": offset, "byte_length": len(raw), "line_sha256": hashlib.sha256(raw).hexdigest(), "kind": kind, "index": row.get("index")}
                metas[offset] = meta
                require(footer is None, "Journal has records after its completion footer")
                if line == 1:
                    header = row
                    require(kind == ("early_guard_header" if cohort == "early" else "late_recovery_header"), "Unexpected journal cohort/header")
                    require(row["input_sha256"] == BOUND_INPUT and row["helper_sha256"] == self.hashes["helper"], "Journal input/helper binding differs")
                    require(row["harness_sha256" if cohort == "early" else "test_sha256"] == self.hashes[cohort], "Old smoke or different harness cannot stand in for this frozen run")
                    if self.engine is None:
                        self.engine = row["engine"]
                    require(all(row["engine"].get(field) == self.engine.get(field) for field in expected_engine_fields), "Recovery engines differ")
                    if cohort == "early":
                        require(row["source_bindings"].get("ok") is True and row["source_bindings"]["observed"] == self.source_hashes, "Early source binding differs")
                        require(row["raw_sources"].get("ok") is True and row["route_helper_sha256"] == self.hashes["route"], "Early raw/route helper binding differs")
                    else:
                        require(row["source_bindings"] == self.queue["source_bindings"], "Late source binding differs")
                    continue
                require(header is not None, "Missing recovery header")
                if cohort == "early":
                    if kind == "early_guard_case":
                        receipt = self.early_case(row)
                        receipt["followup_locator"] = self.locator(meta, path)
                        self.receipts.append(receipt)
                        offsets_here.append(receipt["cohort_offset"])
                        indices_here.append(receipt["index"])
                        # Retain only the small footer projection. Full per-case
                        # snapshots and traces are released before the next line.
                        local_results.append({"cohort_offset": row["cohort_offset"], "index": row["index"], "passed": row["passed"],
                                              "prefix_type": row["prefix_type"], "classification": row["classification"],
                                              "default_blocked": row["default_blocked"], "checkpoint_restored": row["initial_checkpoint_restored"],
                                              "actual_complete_win": row["actual_complete_winning_recovery"], "elapsed_ms": row["elapsed_ms"]})
                    elif kind == "early_guard_footer":
                        footer = row
                    else:
                        raise ValueError("Unexpected/incomplete early journal record: " + str(kind))
                else:
                    if kind == "late_queue_preflight":
                        require(row["preflight"].get("ok") is True and row["preflight"]["raw_verification_identities_verified"] == 26, "Late full-queue preflight did not pass")
                    elif kind == "source_binding_result":
                        require(row["sources"].get("ok") is True and row["sources"]["observed"] == self.source_hashes and row["raw_sources"].get("ok") is True, "Late raw/source preflight did not pass")
                    elif kind == "late_case_begin":
                        require(current is None, "Nested or repeated unfinished late case")
                        cohort_offset, case = self.identity("late", row, "queue_offset")
                        current = {"case": case, "offset": cohort_offset, "example": self.original(case), "original": None,
                                   "initial_win": None, "restored": {}, "winning_chapters": {1}, "winning_records": {}, "attempt_rows": {}}
                    elif kind == "original_campaign_failure_rebuilt":
                        require(current is not None and row["index"] == current["case"]["index"], "Original late proof has a different case")
                        case, original = current["case"], current["example"]
                        require(row["base_terminal_equal"] is True and same(row["full_terminal_core"], case["full_terminal_state"]) and row["decision_signature"] == case["decision_signature"], "Late original terminal/decision identity differs")
                        require(row["decisions_replayed"] == len(original["decisions"]) and same(row["initial_full_snapshot"]["core_state"], original["initial_state"]), "Late original actual replay coverage differs")
                        failed = row["assessed_full_campaign_snapshot"]
                        require(failed["failed"] is True and failed["failure_reason"] == "resource_exhausted" and same(failed["core_state"], case["full_terminal_state"]), "Late actual failure does not equal the original terminal")
                        empty_global(failed["last_failure_event"]["frontier"])
                        require(sequence_equal(row["initial_full_snapshot"], failed), "Late original replay changed campaign seed/variant")
                        current["original"] = row
                    elif kind == "checkpoint_restored":
                        require(current is not None and current["original"] is not None and row["index"] == current["case"]["index"], "Late checkpoint is unbound")
                        current["restored"][int(row["chapter"])] = self.restore_late(row["restore"], current["original"]["assessed_full_campaign_snapshot"])
                    elif kind in ("checkpoint_suffix_attempt", "checkpoint_solver_attempt"):
                        require(current is not None and row["index"] == current["case"]["index"], "Late suffix has another original index")
                        chapter = int(row["chapter"])
                        require(chapter in current["restored"], "Late suffix has no complete actual checkpoint restore")
                        self.late_attempt(row, current["restored"][chapter])
                        current["attempt_rows"][offset] = {"won": row["attempt"].get("won", False), "result": row["attempt"].get("result")}
                        if row["attempt"].get("won") is True:
                            current["winning_chapters"].add(chapter)
                            current["winning_records"][chapter] = {
                                "checkpoint_id": row["checkpoint_id"], "checkpoint_floor": chapter,
                                "method": row.get("strategy", "bounded_solver"),
                                "final_hp": row["attempt"]["final_snapshot"]["core_state"]["hp"],
                                "actual_win_receipt_locator": self.locator(meta, path),
                                "actual_winning_final_snapshot_sha256": content_hash(row["attempt"]["final_snapshot"]),
                            }
                    elif kind == "initial_checkpoint_complete_blade":
                        require(current is not None and row["index"] == current["case"]["index"], "Initial late winning replay has another case")
                        start = self.restore_late(row["restore"], current["original"]["assessed_full_campaign_snapshot"])
                        require(same(start["core_state"], current["example"]["initial_state"]), "Late initial checkpoint core is not the actual initial variant")
                        current["initial_win"] = self.route_win(row["attempt"], start, False)
                        current["winning_records"][1] = {
                            "checkpoint_id": row["restore"]["checkpoint_id"], "checkpoint_floor": 1,
                            "method": "complete_blade/initial_checkpoint",
                            "final_hp": row["attempt"]["final_snapshot"]["core_state"]["hp"],
                            "actual_win_receipt_locator": self.locator(meta, path),
                            "actual_winning_final_snapshot_sha256": content_hash(row["attempt"]["final_snapshot"]),
                        }
                    elif kind == "late_case_summary":
                        require(current is not None and current["initial_win"] is not None, "Late summary has no actual complete initial winning replay")
                        result = row["result"]
                        case = current["case"]
                        require(result.get("passed") is True and result.get("initial_blade_won") is True and result.get("all_checkpoints_solvable_claimed") is False and result.get("error") == "", "Late case did not pass or overclaims checkpoint coverage")
                        for field in IDENTITY:
                            require(same(result[field], case[field]), "Late final summary identity differs")
                        require(result["queue_offset"] == current["offset"], "Late final cohort offset differs")
                        self.require_locator(result["original_replay_locator"], metas, path, "original_campaign_failure_rebuilt", case["index"])
                        self.require_locator(result["initial_winning_locator"], metas, path, "initial_checkpoint_complete_blade", case["index"])
                        for attempt in result["checkpoint_attempts"]:
                            for tried in attempt.get("attempts", []):
                                locator = tried["locator"]
                                target = metas.get(locator["byte_offset"], {})
                                self.require_locator(locator, metas, path, target.get("kind", ""), case["index"])
                                actual = current["attempt_rows"][locator["byte_offset"]]
                                require(tried["won"] == actual["won"] and tried["result"] == actual["result"], "Checkpoint summary attempt differs from its actual proof line")
                        nearest = max(current["winning_chapters"])
                        require(result["nearest_verified_winning_checkpoint"] == nearest, "Nearest verified checkpoint differs from actual winning suffix records")
                        self.nearest[str(nearest)] += 1
                        self.stats["late"]["initial_restores"] += 1
                        self.stats["late"]["actual_complete_wins"] += 1
                        receipt = {"cohort": "late", "cohort_offset": current["offset"], **{key: case[key] for key in IDENTITY},
                                   "original_terminal_floor": result["original_terminal_floor"], "failure_stage_floor": 21,
                                   "initial_checkpoint_restored": True, "actual_complete_winning_recovery": True,
                                   "actual_winning_trace": current["initial_win"], "nearest_verified_winning_checkpoint": nearest,
                                   "nearest_possible_checkpoint_proven": False, "checkpoint_attempts": result["checkpoint_attempts"],
                                   "nearest_actual_winning_recovery": current["winning_records"][nearest],
                                   "initial_fallback_passed": True, "initial_fallback_final_hp": current["winning_records"][1]["final_hp"],
                                   "followup_locator": self.locator(meta, path), "original_replay_locator": result["original_replay_locator"], "initial_winning_locator": result["initial_winning_locator"],
                                   "original_trace_locator": case["trace_locator"], "original_verification_locator": case["verification_locator"]}
                        self.receipts.append(receipt)
                        offsets_here.append(current["offset"])
                        indices_here.append(case["index"])
                        local_results.append(result)
                        current = None
                    elif kind == "late_recovery_footer":
                        footer = row
                    else:
                        raise ValueError("Unexpected/error late journal record: " + str(kind))
        require(footer is not None and current is None, "Journal lacks a completed footer/case")
        copy_summary = dict(summary)
        copy_summary.pop("journal_sha256")
        require(copy_summary == footer and footer.get("measurement_completed") is True, "Summary is not the exact complete journal footer")
        require(footer["input_sha256"] == BOUND_INPUT and footer["harness_sha256" if cohort == "early" else "test_sha256"] == self.hashes[cohort], "Footer input/harness binding differs from its header")
        if cohort == "late":
            require(footer["helper_sha256"] == self.hashes["helper"] and footer["source_bindings"] == self.queue["source_bindings"], "Late footer helper/source binding differs")
        start = int(header["offset"])
        requested = int(header["requested_cases" if cohort == "early" else "requested"])
        require(offsets_here == list(range(start, start + requested)), "Shard offsets are missing, reordered or repeated")
        require(int(footer["completed_cases" if cohort == "early" else "completed"]) == requested == len(local_results), "Shard count differs from actual result lines")
        if cohort == "early":
            require(footer["case_summaries"] == local_results, "Early footer per-case summaries differ")
            require(len(footer["case_summaries"]) == requested, "Early footer case summary count differs")
            for field, count in (("default_blocked_known_losses", sum(r["default_blocked"] for r in local_results)),
                                 ("unknown_queries", sum(r["classification"] == "unknown" for r in local_results)),
                                 ("actual_complete_winning_recoveries", sum(r["actual_complete_win"] for r in local_results)),
                                 ("complete_initial_checkpoint_restores", sum(r["checkpoint_restored"] for r in local_results))):
                require(footer[field] == count, "Early footer counter differs: " + field)
        else:
            require(footer["results"] == local_results and footer["initial_checkpoint_actual_blade_wins"] == requested, "Late footer results/win counter differs")
            require(footer["coverage"]["completed_indices"] == sorted(indices_here) and footer["coverage"]["completed_identities_unique"] is True and footer["coverage"]["selected_set_complete"] is True, "Late footer coverage differs")
        self.journals.append({"cohort": cohort, "path": path.name, "private_source_path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest,
                              "summary_sha256": sha_file(Path(str(path) + ".summary.json")), "offset": start, "completed_cases": requested,
                              "indices": indices_here, "harness_sha256": self.hashes[cohort], "elapsed_ms": footer["elapsed_ms"]})

    def report(self) -> dict:
        coverage = {}
        for cohort in ("early", "late"):
            expected = self.queue[cohort + "_cases"]
            missing = [row["index"] for offset, row in enumerate(expected) if offset not in self.offsets[cohort]]
            coverage[cohort] = {"expected": len(expected), "verified_unique_cases": len(self.seen[cohort]), "missing_indices": missing,
                                "exact_set_complete": not missing and len(self.seen[cohort]) == len(expected)}
            if coverage[cohort]["exact_set_complete"]:
                actual_partition = sorted((item["offset"], item["completed_cases"]) for item in self.journals if item["cohort"] == cohort)
                expected_partition = [(0, 334), (334, 334), (668, 334), (1002, 334)] if cohort == "early" else [(0, 7), (7, 7), (14, 6), (20, 6)]
                require(actual_partition == expected_partition, "Complete cohort must use the four actual bulk parts; overlapping/calibration probes cannot replace them")
                coverage[cohort]["exact_four_bulk_part_partition"] = True
        full = all(value["exact_set_complete"] for value in coverage.values())
        if coverage["early"]["exact_set_complete"]:
            require(dict(self.prefixes) == PREFIX_COUNTS, "Full actual prefix counts differ from the original six-way audit")
        wins = self.stats["early"]["actual_complete_wins"] + self.stats["late"]["actual_complete_wins"]
        restores = self.stats["early"]["initial_restores"] + self.stats["late"]["initial_restores"]
        return {"schema_version": 1, "suite": "strict_recovery_followup_aggregate/v1", "validation_passed": True,
                "measurement_completed": full and wins == 1362 and restores == 1362,
                "input_sha256": BOUND_INPUT, "harness_hashes": self.hashes, "source_hashes": self.source_hashes,
                "engine": self.engine, "coverage": coverage, "early": dict(self.stats["early"]), "late": dict(self.stats["late"]),
                "six_prefix_counts": dict(sorted(self.prefixes.items())), "expected_six_prefix_counts": PREFIX_COUNTS,
                "actual_complete_winning_recoveries": wins, "complete_initial_checkpoint_restores": restores,
                "all_1336_default_blocked": coverage["early"]["exact_set_complete"] and self.stats["early"]["default_blocks"] == 1336,
                "early_outcomes_are_separate": {
                    "default_purchase_blocks_without_state_mutation": self.stats["early"]["default_blocks"],
                    "original_explicitly_accepted_policy_still_loses": self.stats["early"]["explicit_terminal_reproductions"],
                    "full_initial_rollback_then_alternate_blade_actual_wins": self.stats["early"]["actual_complete_wins"],
                    "current_pre_purchase_winning_suffixes_executed": 0,
                    "current_pre_purchase_solvability_proven_by_initial_rollback": False,
                    "scope": "A post-purchase unsatisfiability proof and a state-preserving block do not establish that the preserved pre-purchase state has a winning suffix. A complete initial rollback followed by blade is a distinct legal recovery experiment."},
                "late_nearest_verified_winning_checkpoints": dict(self.nearest), "late_checkpoint_attempt_result_counts": dict(self.checkpoint_results),
                "original_raw_sources": self.raw_sources, "initial_unsatisfiable_cases_proven": 0,
                "ui_warning_integration_tested": False, "original_random_policy_changed": False,
                "scope": "All counts concern unique original indices, actual native QA calls and recorded complete winning traces. The original explicitly accepted random action policy still loses. Actual wins select a different blade route after a complete legal initial-checkpoint rollback. Unknown nearest-checkpoint attempts are not unsatisfiable, and nearest verified is not nearest possible. No difficulty/data/rules/default-budget changes or UI/browser acceptance are implied."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--early", type=Path, nargs="+", default=[])
    parser.add_argument("--late", type=Path, nargs="+", default=[])
    parser.add_argument("--output", type=Path, required=True, help="A new evidence directory")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    require(not args.output.exists(), "Output directory already exists; existing evidence is never replaced")
    require(args.early or args.late, "Pass at least one completed journal")
    validator = Validator(args.input, args.source_root)
    for cohort, paths in (("early", args.early), ("late", args.late)):
        for path in paths:
            validator.consume(path, cohort)
    report = validator.report()
    require(args.allow_partial or report["measurement_completed"], "Complete mode requires exact early 1336 + late 26 coverage and 1362 actual complete winning recoveries")
    args.output.mkdir(parents=True)
    receipts = args.output / "case-receipts.jsonl.gz"
    with receipts.open("wb") as raw_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as packed:
            for row in sorted(validator.receipts, key=lambda item: (item["cohort"], item["cohort_offset"])):
                packed.write((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    journal_manifest = [{key: value for key, value in row.items() if key != "private_source_path"} for row in validator.journals]
    (args.output / "journal-manifest.json").write_text(json.dumps(journal_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    late_table = []
    for row in sorted((item for item in validator.receipts if item["cohort"] == "late"), key=lambda item: item["cohort_offset"]):
        nearest = row["nearest_actual_winning_recovery"]
        late_table.append({"index": row["index"], "layout_seed": row["layout_seed"], "terminal_floor": row["original_terminal_floor"],
                           "failure_stage_floor": row["failure_stage_floor"], "checkpoint_id": nearest["checkpoint_id"],
                           "checkpoint_floor": nearest["checkpoint_floor"], "nearest_verified_method": nearest["method"],
                           "final_hp": nearest["final_hp"], "actual_win_receipt_locator": nearest["actual_win_receipt_locator"],
                           "actual_winning_final_snapshot_sha256": nearest["actual_winning_final_snapshot_sha256"],
                           "initial_fallback_passed": row["initial_fallback_passed"], "initial_fallback_final_hp": row["initial_fallback_final_hp"],
                           "initial_fallback_receipt_locator": row["initial_winning_locator"], "nearest_possible_checkpoint_proven": False})
    table_json = args.output / "late-case-table.json"
    table_json.write_text(json.dumps({"schema_version": 1, "input_sha256": BOUND_INPUT, "verified_cases": len(late_table),
                                    "scope": "Nearest checkpoint with an actually replayed winning suffix; no mathematical nearest-possible or later-checkpoint impossibility claim. Initial fallback is a separate actually replayed complete blade win.",
                                    "cases": late_table}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    table_csv = args.output / "late-case-table.csv"
    with table_csv.open("w", encoding="utf-8", newline="") as file:
        fields = list(late_table[0]) if late_table else ["index", "layout_seed", "terminal_floor", "failure_stage_floor", "checkpoint_id", "checkpoint_floor", "nearest_verified_method", "final_hp", "actual_win_receipt_locator", "initial_fallback_passed"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in late_table:
            writer.writerow({key: json.dumps(value, separators=(",", ":")) if isinstance(value, dict) else value for key, value in row.items()})
    report["case_receipts"] = {"path": receipts.name, "sha256": sha_file(receipts), "bytes": receipts.stat().st_size, "unique_cases": len(validator.receipts)}
    report["journal_manifest"] = {"path": "journal-manifest.json", "sha256": sha_file(args.output / "journal-manifest.json")}
    report["late_case_tables"] = [{"path": path.name, "sha256": sha_file(path), "bytes": path.stat().st_size, "cases": len(late_table)} for path in (table_json, table_csv)]
    report["aggregator_sha256"] = sha_file(Path(__file__))
    (args.output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief_coverage = {cohort: {"expected": value["expected"], "verified_unique_cases": value["verified_unique_cases"], "missing_cases": len(value["missing_indices"]), "exact_set_complete": value["exact_set_complete"]} for cohort, value in report["coverage"].items()}
    print(json.dumps({"validation_passed": True, "measurement_completed": report["measurement_completed"], "coverage": brief_coverage,
                      "actual_complete_winning_recoveries": report["actual_complete_winning_recoveries"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
