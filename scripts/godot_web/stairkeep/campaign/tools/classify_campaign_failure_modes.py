#!/usr/bin/env python3
"""Read verified failure proofs; classify observed blockers without combat math."""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys


def need(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf8", newline="\n")


def budget(state):
    return {key: state[key] for key in ("hp", "atk", "def", "gold", "keys", "purchases")}


def range_stats(values):
    return {"min": min(values), "max": max(values), "median": statistics.median(values)} if values else {}


def classify(state, proof, offers):
    floor = int(state["floor"]) + 1
    blocked = {item["id"]: item for item in proof["blocked"]}
    # Standing on floor 1 does not imply an early failure: a policy can return
    # to an old shop after clearing the whole tower. A globally reachable final
    # boss blocker takes precedence over the terminal standing coordinate.
    if floor == 1 and "f21_boss" not in blocked:
        guard = blocked.get("f01_guard", {})
        combat = guard.get("combat", {})
        purchases = state["purchases"]
        if guard.get("kind") == "enemy" and combat.get("win") is False and int(combat.get("hit", -1)) <= 0 and int(purchases.get("f01_shop/edge", 0)) == 0:
            ward = int(purchases.get("f01_shop/ward", 0))
            flask = int(purchases.get("f01_shop/flask", 0))
            if ward > 0 and flask == 0:
                return "F1/ward_purchase_before_required_attack", guard
            if flask > 0 and ward == 0:
                return "F1/flask_purchase_before_required_attack", guard
            return "F1/armor_gate_with_other_spending_pattern", guard
        return "F1/other_proven_terminal_blocker", guard
    if floor == 21 or "f21_boss" in blocked:
        boss = blocked.get("f21_boss", {})
        combat = boss.get("combat", {})
        if boss and combat.get("win") is False and int(combat.get("hit", 0)) > 0 and int(combat.get("damage", -1)) >= int(state["hp"]):
            healing = [item for item in proof["shop_offers"] if offers.get(item["id"], {}).get("kind") == "potion"]
            if healing and all(int(item["bought"]) >= int(item["limit"]) for item in healing):
                return "F21/boss_hp_deficit_reachable_healing_stock_exhausted", boss
            return "F21/boss_hp_deficit_no_legal_remaining_recovery", boss
        if boss and combat.get("win") is False and int(combat.get("hit", -1)) <= 0:
            return "F21/boss_armor_gate", boss
        return "F21/other_proven_terminal_blocker", boss
    return f"F{floor}/other_proven_terminal_blocker", {}


def checkpoint_evidence(path, source_data_sha):
    if path is None:
        return {"provided": False, "late_random_failure_recovery_verified": False}
    report = read(path)
    workflow = report.get("evidence", {}).get("recovery_workflow", {})
    restored = workflow.get("restored_full_snapshot", {})
    loss = workflow.get("accepted_loss_snapshot", {})
    need(report.get("passed") is True and report.get("full_recovery_workflow_completed") is True and workflow.get("won") is True, "Checkpoint/guard report is not an actual completed recovery workflow.")
    need(report.get("data_file_sha256") == source_data_sha, "Checkpoint/guard experiment uses different canonical data.")
    return {"provided": True, "sha256": digest(path), "suite": report.get("suite"), "checks": len(report.get("checks", [])), "passed": True, "coverage": report.get("coverage"), "tested_loss_floor": int(loss.get("core_state", {}).get("floor", -1)) + 1, "restored_checkpoint_id": restored.get("checkpoint_id"), "restored_floor": int(restored.get("core_state", {}).get("floor", -1)) + 1, "actual_recovery_reached_floor21_victory": workflow.get("full_final_snapshot", {}).get("core_state", {}).get("won") is True, "late_random_failure_recovery_verified": False, "boundary": "The bound workflow proves the tested complete checkpoint recovery, not recovery of the distinct late randomized terminal states. A known-winning late preview on its authored path is not a winning suffix from these random histories."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Original byte-exact failure-replay-input.json")
    parser.add_argument("--replays", required=True, nargs="+", type=Path)
    parser.add_argument("--canonical-data", required=True, type=Path)
    parser.add_argument("--checkpoint-report", type=Path)
    parser.add_argument("--aggregator", type=Path, default=Path(__file__).with_name("aggregate_campaign_shards.py"))
    parser.add_argument("--replayer-script", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--classification-json", type=Path)
    parser.add_argument("--campaign-doc", type=Path)
    args = parser.parse_args()
    need(not args.output.exists(), "Analysis output must be a new directory; original evidence is never overwritten.")
    for target in (args.classification_json, args.campaign_doc):
        need(target is None or not target.exists(), "Named classification deliverables must be new files.")
    queue = read(args.input)
    canonical = read(args.canonical_data)
    need(digest(args.canonical_data) == queue["source_hashes"]["source_data_sha256"], "Canonical bytes differ from the actual baseline.")
    specification = importlib.util.spec_from_file_location("campaign_verified_aggregate", args.aggregator)
    aggregate = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(aggregate)
    # Reuse the strict read-only footer/index/input/full-proof validator. The
    # queue is already bound to the completed original aggregate summary.
    baseline_rows = [{"record": item} for item in queue["expected_records"]]
    shared = {key: queue[key] for key in ("engine", "master_layout_seed", "master_policy_seed")}
    verified, replay_sources = aggregate.consume_failure_replays(args.replays, baseline_rows, queue["source_hashes"], shared, queue["canonical_witness_binding"], args.input, args.replayer_script)
    original_summary = read(args.input.parent / "summary.json")
    need(original_summary["measurement_validation"]["passed"] is True, "Original baseline aggregate was not validated.")
    offers = {}
    for floor in canonical["floors"]:
        for item in floor["objects"]:
            if item["kind"] == "shop":
                for offer in canonical["shops"][item["type"]]["offers"]:
                    offers[item["id"] + "/" + offer["id"]] = offer
    by_portable_path = {item["portable_path"]: item["path"] for item in replay_sources}
    handles = {key: path.open("rb") for key, path in by_portable_path.items()}
    case_rows = []
    try:
        for index, item in sorted(verified.items()):
            proof_locator, trace_locator = item["verification_locator"], item["trace_locator"]
            handle = handles[proof_locator["path"]]
            handle.seek(int(proof_locator["byte_offset"]))
            event = json.loads(handle.read(int(proof_locator["byte_length"])))
            handle.seek(int(trace_locator["byte_offset"]))
            example = json.loads(handle.read(int(trace_locator["byte_length"]))) ["example"]
            state = event["full_terminal_state"]
            proof = event["continuous_reconstruction"]["global_navigation_proof"]
            category, main_blocker = classify(state, proof, offers)
            decisions = example["decisions"]
            purchases = []
            battles = []
            last_chapter_entry = None
            for decision in decisions:
                if decision.get("kind") == "buy":
                    offered = offers.get(decision["chosen_id"], {})
                    purchases.append({"decision": decision["decision"], "id": decision["chosen_id"], "offer_kind": offered.get("kind"), "cost": offered.get("cost"), "amount": offered.get("amount"), "before": decision.get("before"), "after": decision.get("after")})
                combat = decision.get("preview", {})
                if decision.get("kind") == "enemy" and combat:
                    battles.append({"decision": decision["decision"], "id": decision["chosen_id"], "actual_authoritative_preview": combat, "before": decision.get("before"), "after": decision.get("after")})
                if last_chapter_entry is None and int(decision.get("after", {}).get("floor", 0)) >= 19:
                    last_chapter_entry = {"decision": decision["decision"], "chosen_id": decision["chosen_id"], "before_budget": decision.get("before"), "after_budget": decision.get("after"), "scope": "Trace landmark only, not a serialized CampaignRules v2 chapter checkpoint. This baseline uses BaseRules; obtaining an actual complete checkpoint requires replay through CampaignRules."}
            healing = [entry for entry in proof["shop_offers"] if offers.get(entry["id"], {}).get("kind") == "potion"]
            highest_floor = max([int(state["floor"]) + 1] + [int(decision.get(side, {}).get("floor", 0)) for decision in decisions for side in ("before", "after")])
            row = {"index": index, "queue_offset": event["queue_offset"], "policy": event["actual_record"]["policy"], "layout_seed": event["actual_record"]["layout_seed"], "policy_seed": event["actual_record"]["policy_seed"], "layout_hash": event["actual_record"]["layout_hash"], "decision_signature": event["actual_record"]["decision_signature"], "category": category, "terminal_floor": int(state["floor"]) + 1, "failure_stage_floor":21 if category.startswith("F21/") else int(state["floor"]) + 1,"highest_floor_observed_in_trace":highest_floor,"full_terminal_state": state, "main_observed_blocker": main_blocker, "all_observed_blockers": proof["blocked"], "reachable_shop_offers": proof["shop_offers"], "healing_stock": healing, "replayed_resource_ledger": event["continuous_reconstruction"]["resources"], "purchases_in_actual_order": purchases, "highest_cost_actual_encounters": sorted(battles, key=lambda battle: int(battle["actual_authoritative_preview"].get("damage", -1)), reverse=True)[:12], "last_chapter_entry_trace_landmark": last_chapter_entry, "trace_locator": trace_locator, "verification_locator": proof_locator, "terminal_proof": {"complete_global_bfs": proof["complete"], "reachable_nodes": proof["reachable"], "legal_resource_actions": len(proof["options"]), "full_proof_locator": proof_locator}, "initial_solvable_by_bound_witness_and_isomorphism": event["initial_solvable"], "initial_unsatisfiable_proven": False, "checkpoint_recovery_for_this_exact_case_tested": False}
            case_rows.append(row)
    finally:
        for handle in handles.values():
            handle.close()
    counts = collections.Counter(item["category"] for item in case_rows)
    floors = collections.Counter(str(item["terminal_floor"]) for item in case_rows)
    late = [item for item in case_rows if item["failure_stage_floor"] == 21]
    backtracked_late = [item for item in late if item["terminal_floor"] != 21]
    checkpoint = checkpoint_evidence(args.checkpoint_report, queue["source_hashes"]["source_data_sha256"])
    categories = {}
    for category in sorted(counts):
        selected = [item for item in case_rows if item["category"] == category]
        categories[category] = {"count": len(selected), "indices": [item["index"] for item in selected], "examples": [{key: item[key] for key in ("index", "layout_seed", "policy_seed", "trace_locator", "verification_locator")} for item in selected[:3]], "terminal_hp": range_stats([int(item["full_terminal_state"]["hp"]) for item in selected]), "terminal_attack": range_stats([int(item["full_terminal_state"]["atk"]) for item in selected]), "terminal_defense": range_stats([int(item["full_terminal_state"]["def"]) for item in selected]), "terminal_gold": range_stats([int(item["full_terminal_state"]["gold"]) for item in selected])}
    summary = {"schema_version": 1, "suite": "campaign-failure-mode-readonly-analysis/v2", "scope": "Only observed complete failure replays and authoritative terminal combat previews are classified. No combat formula is duplicated and no new Godot simulation is run.", "source_input_sha256": digest(args.input), "source_data_sha256": digest(args.canonical_data), "aggregator_sha256": digest(args.aggregator), "analysis_sha256": digest(Path(__file__)), "replay_journal_sha256": {item["portable_path"]: item["sha256"] for item in replay_sources}, "original_measurement": original_summary["measurement_validation"], "original_outcomes": original_summary["all_policies"]["outcomes"], "verified_failed_runs": len(case_rows), "terminal_floors": dict(floors), "failure_stage_counts":dict(collections.Counter(str(item["failure_stage_floor"]) for item in case_rows)),"backtracked_final_boss_case_indices":[item["index"] for item in backtracked_late],"categories": categories, "initial_unsatisfiable_cases_proven": 0, "all_failed_initials_have_bound_winning_family_evidence": all(item["initial_solvable_by_bound_witness_and_isomorphism"] for item in case_rows), "checkpoint_evidence": checkpoint, "late_case_checkpoint_recovery_proven": 0, "purchase_guard_late_coverage": "The tested first-forge purchase guard and its first-chapter recovery do not certify recovery of these late floor-21 histories.", "verified_facts": ["A terminal global BFS with no legal resource action proves no ordinary winning suffix for that reached state.", "Canonical winning witnesses plus checked mirror/stair/ID/attribute and safe-spawn isomorphism prove the initial family solvable.", "Unspent gold does not buy an exhausted finite healing offer; actual offer stock and authoritative boss preview are retained per case.","Terminal standing floor is not failure stage. Run 599 returned to floor 1 after reaching the final chapter; its global blocker is the floor-21 boss."], "next_verification": [f"For each of the {len(late)} final-boss cases (including backtracked cases), replay its exact original actions through CampaignRules v2 to capture the real complete chapter-19 checkpoint, including HP/stats/keys/gold/world clears/stock/seed metadata.", "Restore that actual checkpoint and run an explicit alternate resource-conscious suffix or the bounded solver through production APIs. A budget-limited unknown remains unknown.", "If chapter 19 has no winning suffix, test an earlier complete chapter checkpoint; do not add rescue resources, refund purchases, change seeds silently, or claim the existing F1 guard solved the late case.", "Only after those actual recovery runs can checkpoint UI be presented as a verified recovery for the late cases. The existing backend mechanism is not evidence that the 21-floor UI is connected."], "not_claimed": ["No initial generated map was proven unsatisfiable.", "No late randomized failure was silently repaired by this analysis.", "No full checkpoint exists in a BaseRules terminal snapshot; trace budget landmarks are not CampaignRules Save v2 snapshots.", "No browser/human input, visual acceptance, hardware performance or hours-of-play verification."]}
    args.output.mkdir(parents=True)
    write(args.output / "summary.json", summary)
    write(args.output / "late-floor21.json", late)
    if args.classification_json:
        args.classification_json.parent.mkdir(parents=True,exist_ok=True)
        write(args.classification_json,{"summary":summary,"cases":case_rows,"late_final_boss_cases":late,"raw_locator_scope":"Trace and proof byte offsets/hashes refer to original private replay journals. A public sanitized derivative must remap locators and retain raw/public hash mappings."})
    with (args.output / "all-failure-cases.jsonl").open("w", encoding="utf8", newline="\n") as stream:
        for row in case_rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    lines = ["# Failure-mode analysis", "", f"The {len(case_rows)} nonwinning baseline runs were independently replayed and classified from actual global terminal proofs.", "", "| Category | Count | Example indices |", "| --- | ---: | --- |"]
    for category, item in categories.items():
        lines.append(f"| {category} | {item['count']} | {', '.join(str(entry['index']) for entry in item['examples'])} |")
    lines += ["", "Every case retains exact seeds, full terminal state, observed combat preview, finite offer inventory and byte/line locators to the full executable trace and proof. The canonical initial family is solvable; a policy dead end is a different reached state.", "", f"The bound checkpoint/guard workflow tested recovery from floor {checkpoint.get('tested_loss_floor', 'unknown')} using `{checkpoint.get('restored_checkpoint_id', 'unknown')}` and reached a real 21-floor victory. It does not test recovery of these {len(late)} late randomized histories. The baseline uses BaseRules and does not retain CampaignRules v2 complete checkpoints.", "", "For late cases, the next concrete test is exact replay through CampaignRules, complete chapter-checkpoint capture/restore, then an actual alternate winning suffix. No new rescue resources or silent seed changes are justified by this analysis.", "", "This is read-only logical evidence, not UI, browser or player-duration acceptance."]
    (args.output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf8", newline="\n")
    if args.campaign_doc:
        doc = ["# 原始 10,000 局的失败分类", "", "[逐局分类与完整证据定位](evidence/failure-classification.json.gz)", "", f"原始记录的终点楼层分布保持不变：F1 {floors.get('1',0)} 局，F21 {floors.get('21',0)} 局。但实际失败阶段是首店攻击门槛 {len(case_rows)-len(late)} 局、最终首领资源预算 {len(late)} 局。所有分类来自完整实际重放和全局不可行动证明；未改 baseline、经济或战斗规则。", "", "| 实际类型 | 数量 | 精确例子 index |", "| --- | ---: | --- |"]
        for category,item in categories.items():
            doc.append(f"| {category} | {item['count']} | {', '.join(str(example['index']) for example in item['examples'])} |")
        doc += ["", "**599 必须单列。** 它的终点坐标在 F1，但已到最终章后回旧商店购物。种子 `04f26220`，终局 HP 310、ATK 120、DEF 69、金币 792；全局 frontier 中 `f21_boss` 的真实预览是伤害 423、不可胜。它属于最终首领预算失败，不能算进首店门卫失败，也不能把首店保护测试当成它已被修复。", "", f"全部 {len(late)} 个最终首领阶段案例都保留实际首领预览、完整资源/钥匙/清除对象/商店库存、购买顺序及 trace/proof 的精确定位。它们的剩余金币不能购买已经耗尽的有限治疗库存；这是终局后缀无解，不是初始生成图无解。初始可赢证据仍是四条实际完整 canonical 见证，加上逐布局镜像/楼梯/对象属性同构和安全出生点空路径证明。", "", "恢复边界也须分开：现有 75 检查中的真实完整恢复工作流，从 `chapter-01/attempt-0` 回到完整首章快照并实际通关 21 层，证明了那个被测试的工作流。它没有逐个证明这 26 个随机晚期历史能从末章 checkpoint 恢复获胜；原始模拟使用 BaseRules，终局快照并不包含 CampaignRules Save v2 的完整章节 checkpoint。", "", "下一项可验证改进是先复用已有完整 checkpoint：按每个晚期案例的原始路径通过 CampaignRules v2 实际生成章节快照，再恢复 chapter 19 并用明确替代路线或有界求解器验证获胜后缀；若末章仍无解，再测更早章节。未知必须保留未知，不补发资源、不退款、不暗换种子。首店四种前缀保护只声明其已验证范围，不能声称解决全部晚期案例。", "", "本报告是只读逻辑分析。21 层 UI、浏览器真实输入、视觉质量和数小时玩家体验没有因此被验收。"]
        args.campaign_doc.parent.mkdir(parents=True,exist_ok=True)
        args.campaign_doc.write_text("\n".join(doc)+"\n",encoding="utf8",newline="\n")
    print(json.dumps({"verified_failed_runs": len(case_rows), "terminal_floors": dict(floors), "categories": dict(counts), "late_checkpoint_recovery_proven": 0, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"completed": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(2)
