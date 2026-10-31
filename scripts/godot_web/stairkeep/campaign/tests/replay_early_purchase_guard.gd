extends "res://tests/replay_variant_routes.gd"
## Paired QA replay only. The unguarded baseline, data, rules and production
## guard defaults are unchanged. A blocked branch never silently continues the
## original policy: only a separately recorded explicit override may do so.

const Guard = preload("res://scripts/purchase_guard.gd")
const Followup = preload("res://tests/recovery_followup_helpers.gd")
const EARLY_SCRIPT: String = "res://tests/replay_early_purchase_guard.gd"
const WIN_MODES: Array[String] = ["none", "representatives", "all"]
const INITIAL_HISTORY: Array[String] = ["failure_events_seen", "consumed_loss_ids"]

var early_input_path: String = ""
var early_output_path: String = ""
var early_stop_path: String = ""
var early_offset: int = 0
var early_count: int = -1
var early_win_mode: String = "none"
var early_journal: FileAccess
var early_queue: Dictionary = {}
var early_base_dir: String = ""
var early_input_hash: String = ""
var early_types_won: Dictionary = {}
var early_line: int = 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not _early_arguments():
		quit(2)
		return
	var loaded: Dictionary = Followup.load_queue(early_input_path)
	if not bool(loaded.get("ok", false)):
		_early_abort("Cannot load bound recovery queue.", loaded)
		return
	early_queue = loaded["input"]
	early_base_dir = loaded["base_dir"]
	early_input_hash = loaded["input_sha256"]
	if not (early_queue.get("early_cases") is Array) or not (early_queue.get("late_cases") is Array):
		_early_abort("Recovery queue must declare both original cohorts.")
		return
	var cases: Array = early_queue["early_cases"]
	if cases.size() != 1336 or early_queue["late_cases"].size() != 26 or early_offset > cases.size():
		_early_abort("This harness binds the actual 1336 early / 26 late baseline partition.")
		return
	var seen: Dictionary = {}
	for item: Dictionary in cases:
		var id: int = int(item.get("index", -1))
		if id < 0 or id == 599 or seen.has(id) or item.get("cohort", "") != "early" or int(item.get("failure_stage_floor", 0)) != 1:
			_early_abort("Early cohort has an invalid, duplicate or late-stage member.", {"index": id})
			return
		seen[id] = true
	var end: int = cases.size() if early_count < 0 else mini(cases.size(), early_offset + early_count)
	var selected: Array = cases.slice(early_offset, end)
	var sources: Dictionary = Followup.verify_source_bindings(early_queue)
	if not bool(sources.get("ok", false)):
		_early_abort("Frozen source binding differs.", sources)
		return
	var raw_sources: Dictionary = Followup.verify_raw_sources(selected, early_queue["source_files"], early_base_dir)
	if not bool(raw_sources.get("ok", false)):
		_early_abort("Original raw replay bytes/engine/source binding differs.", raw_sources)
		return
	early_journal = FileAccess.open(early_output_path, FileAccess.WRITE)
	if early_journal == null:
		_early_abort("Cannot create the new paired journal.")
		return
	_early_append({"kind": "early_guard_header", "schema_version": 1,
		"engine_pid": OS.get_process_id(), "engine": Engine.get_version_info(),
		"input_sha256": early_input_hash, "harness_sha256": FileAccess.get_sha256(EARLY_SCRIPT),
		"helper_sha256": FileAccess.get_sha256("res://tests/recovery_followup_helpers.gd"),
		"route_helper_sha256": FileAccess.get_sha256("res://tests/replay_variant_routes.gd"),
		"source_bindings": sources, "raw_sources": raw_sources,
		"cohort": "early", "cohort_size": cases.size(), "offset": early_offset,
		"requested_cases": selected.size(), "winning_mode": early_win_mode,
		"guard_budget_scope": "preview(offer) receives no budget override: actual production QUERY_DEFAULTS and per-instance caps apply. Unknown is never a loss proof or a safety guarantee.",
		"pairing_scope": "Same actual CampaignRules seed and original Navigation actions. Every prefix input and full snapshot is paired. The guarded default branch stops at its first divergent purchase; only a fresh explicit confirmation rejoins the original losing-policy trace.",
		"recovery_scope": "Every completed case actually restores its complete initial chapter checkpoint. Full 21-floor wins are counted only when separately executed; restored-state equivalence and inherited initial-variant isomorphism proof do not count as a played winning suffix.",
		"ui_scope": "QA calls only; no player-facing warning UI or browser acceptance is claimed."})
	early_journal.flush()
	var began: int = Time.get_ticks_msec()
	var completed: int = 0
	var blocked: int = 0
	var unknown: int = 0
	var known_winning: int = 0
	var explicit_losses: int = 0
	var restored: int = 0
	var wins: int = 0
	var failures_local: Array = []
	var stopped: bool = false
	var records: Array = []
	for cohort_offset: int in range(early_offset, end):
		if not early_stop_path.is_empty() and FileAccess.file_exists(early_stop_path):
			stopped = true
			_early_append({"kind": "coordinated_stop", "before_cohort_offset": cohort_offset, "completed_cases": completed})
			break
		var result: Dictionary = _early_case(cases[cohort_offset], cohort_offset)
		_early_append(result)
		early_journal.flush()
		completed += 1
		blocked += int(bool(result.get("default_blocked", false)))
		unknown += int(result.get("classification", "") == "unknown")
		known_winning += int(result.get("classification", "") == "known_winning")
		explicit_losses += int(bool(result.get("explicit_override_reproduced_original_terminal", false)))
		restored += int(bool(result.get("initial_checkpoint_restored", false)))
		wins += int(bool(result.get("actual_complete_winning_recovery", false)))
		records.append({"cohort_offset": cohort_offset, "index": result.get("index", -1), "passed": result.get("passed", false), "prefix_type": result.get("prefix_type", ""), "classification": result.get("classification", ""), "default_blocked": result.get("default_blocked", false), "checkpoint_restored": result.get("initial_checkpoint_restored", false), "actual_complete_win": result.get("actual_complete_winning_recovery", false), "elapsed_ms": result.get("elapsed_ms", 0)})
		print(JSON.stringify({"early_cases_completed": completed, "requested_cases": selected.size(), "last_index": result.get("index", -1), "default_blocked": blocked, "unknown": unknown, "actual_complete_wins": wins, "elapsed_ms": Time.get_ticks_msec() - began}))
		if not bool(result.get("passed", false)):
			failures_local.append({"cohort_offset": cohort_offset, "index": result.get("index", -1), "errors": result.get("errors", [])})
			break
	var complete: bool = completed == selected.size() and not stopped and failures_local.is_empty()
	var footer: Dictionary = {"kind": "early_guard_footer", "measurement_completed": complete, "passed": complete,
		"input_sha256": early_input_hash, "harness_sha256": FileAccess.get_sha256(EARLY_SCRIPT),
		"queue_offset": early_offset, "next_queue_offset": early_offset + completed,
		"requested_cases": selected.size(), "completed_cases": completed, "stopped_at_case_boundary": stopped,
		"default_blocked_known_losses": blocked, "unknown_queries": unknown, "known_winning_queries": known_winning,
		"all_default_blocked": completed > 0 and blocked == completed,
		"explicit_override_original_terminal_reproductions": explicit_losses,
		"complete_initial_checkpoint_restores": restored,
		"actual_complete_winning_recoveries": wins, "winning_prefix_types": early_types_won.keys(),
		"initial_unsatisfiable_cases_proven": 0, "ui_warning_integration_tested": false,
		"case_summaries": records, "errors": failures_local, "elapsed_ms": Time.get_ticks_msec() - began}
	_early_append(footer)
	early_journal.flush()
	early_journal.close()
	footer["journal_sha256"] = FileAccess.get_sha256(early_output_path)
	var summary: FileAccess = FileAccess.open(early_output_path + ".summary.json", FileAccess.WRITE)
	if summary == null:
		print(JSON.stringify({"measurement_completed": false, "error": "Cannot create new summary; journal remains available."}))
		quit(1)
		return
	summary.store_string(JSON.stringify(footer, "  ") + "\n")
	summary.close()
	print(JSON.stringify({"measurement_completed": complete, "completed_cases": completed, "default_blocked": blocked, "unknown_queries": unknown, "checkpoint_restores": restored, "actual_complete_winning_recoveries": wins, "journal_sha256": footer["journal_sha256"], "elapsed_ms": footer["elapsed_ms"]}))
	quit(0 if complete or (stopped and failures_local.is_empty()) else 1)


func _early_arguments() -> bool:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--input="): early_input_path = argument.trim_prefix("--input=")
		elif argument.begins_with("--output="): early_output_path = argument.trim_prefix("--output=")
		elif argument.begins_with("--stop-file="): early_stop_path = argument.trim_prefix("--stop-file=")
		elif argument.begins_with("--winning="): early_win_mode = argument.trim_prefix("--winning=")
		elif argument.begins_with("--offset="):
			var text: String = argument.trim_prefix("--offset=")
			if not text.is_valid_int(): return false
			early_offset = int(text)
		elif argument.begins_with("--count="):
			var text: String = argument.trim_prefix("--count=")
			if not text.is_valid_int(): return false
			early_count = int(text)
		else:
			push_error("Unknown early guard replay argument: " + argument)
			return false
	if early_input_path.is_empty() or early_output_path.is_empty() or early_offset < 0 or early_count < -1 or not WIN_MODES.has(early_win_mode):
		push_error("Pass --input=<bound queue> --output=<new JSONL> [--offset=N --count=N --winning=none|representatives|all --stop-file=path].")
		return false
	if FileAccess.file_exists(early_output_path) or FileAccess.file_exists(early_output_path + ".summary.json"):
		push_error("Existing early guard journal/summary refused; evidence is never overwritten.")
		return false
	return true


func _early_case(item: Dictionary, cohort_offset: int) -> Dictionary:
	var began: int = Time.get_ticks_msec()
	var report: Dictionary = {"kind": "early_guard_case", "cohort_offset": cohort_offset, "index": int(item["index"]), "case_id": item["case_id"],
		"layout_seed": item["layout_seed"], "policy_seed": item["policy_seed"], "decision_signature": item["decision_signature"], "layout_hash": item["layout_hash"],
		"trace_locator": item["trace_locator"], "verification_locator": item["verification_locator"],
		"passed": false, "errors": [], "default_blocked": false, "initial_checkpoint_restored": false, "actual_complete_winning_recovery": false}
	var errors_local: Array = report["errors"]
	var trace_read: Dictionary = Followup.read_bound_line(item["trace_locator"], early_base_dir, early_queue["source_files"])
	var proof_read: Dictionary = Followup.read_bound_line(item["verification_locator"], early_base_dir, early_queue["source_files"])
	if not bool(trace_read.get("ok", false)) or not bool(proof_read.get("ok", false)):
		errors_local.append({"error": "Strict raw locator read failed.", "trace": trace_read, "verification": proof_read})
		return report
	var trace_record: Dictionary = trace_read["record"]
	var verification: Dictionary = proof_read["record"]
	if trace_record.get("kind", "") != "example" or verification.get("kind", "") != "verified_failure" or not bool(verification.get("verified", false)) or not bool(verification.get("initial_solvable", false)) or not bool(verification.get("terminal_no_winning_suffix", false)):
		errors_local.append("Original line is not a verified losing policy with a proven solvable initial variant.")
		return report
	var example: Dictionary = trace_record.get("example", {})
	var expected: Dictionary = item.get("original_expected_record", {})
	for key: String in ["index", "policy", "layout_seed", "policy_seed", "decision_signature", "layout_hash"]:
		if not Followup.same(item.get(key), expected.get(key)):
			errors_local.append("Queue case identity differs from its original expected record: " + key)
	for key: String in ["index", "policy", "layout_seed", "policy_seed", "decision_signature", "layout_hash", "decision_count", "policy_rng_final", "final", "outcome"]:
		if not Followup.same(expected.get(key), verification.get("expected_record", {}).get(key)) or not Followup.same(expected.get(key), example.get("record", {}).get(key)):
			errors_local.append("Original record identity differs: " + key)
	if not bool(verification.get("isomorphism_certificate", {}).get("ok", false)) or not bool(verification.get("canonical_witness_binding", {}).get("ok", false)):
		errors_local.append("Original initial-variant proof does not bind the actual canonical witnesses and mirrored graph.")
	var original_terminal: Dictionary = item["full_terminal_state"]
	if not Followup.core_equal(original_terminal, verification.get("full_terminal_state", {})) or not Followup.core_equal(original_terminal, example.get("final_state", {})):
		errors_local.append("Original full terminal state differs between the three bound receipts.")
	if not errors_local.is_empty(): return report
	var game = Campaign.new()
	var shadow = Campaign.new()
	# CampaignRules accepts the normalized eight-hex API value. The optional
	# 0x spelling belongs only to the separate witness CLI argument parser.
	var seed_argument: String = str(item["layout_seed"])
	var initialized: Dictionary = game.load_campaign(DATA_PATH, seed_argument)
	var paired_initialized: Dictionary = shadow.load_campaign(DATA_PATH, seed_argument)
	if not bool(initialized.get("ok", false)) or not bool(paired_initialized.get("ok", false)):
		errors_local.append({"error": "Actual CampaignRules seed initialization failed.", "actual": initialized, "shadow": paired_initialized})
		return report
	var initial: Dictionary = game.campaign_snapshot()
	if not Followup.same(initial, shadow.campaign_snapshot()) or not Followup.core_equal(initial["core_state"], example["initial_state"]) or initial["transformed_content_sha256"] != item["layout_hash"]:
		errors_local.append("Initial full paired snapshots/core/layout do not equal the original variant.")
		return report
	var initial_checkpoints: Array = initial.get("checkpoints", [])
	if initial_checkpoints.size() != 1 or not Followup.core_equal(initial_checkpoints[0]["core_state"], initial["core_state"]):
		errors_local.append("No complete initial entry checkpoint exists in the actual campaign.")
		return report
	report["initial_full_snapshot"] = initial
	report["initial_proven_winning_family"] = {"proven": true, "scope": "Inherited exact raw verification of four actual canonical witnesses plus this variant's complete mirror/stair/spawn isomorphism. This is not a newly played full route for this seed.", "canonical_witness_binding": verification["canonical_witness_binding"], "isomorphism_certificate_sha256": Variants.content_hash(verification["isomorphism_certificate"])}
	var decisions: Array = example.get("decisions", [])
	var chosen_ids: PackedStringArray = []
	var bad_at: int = -1
	for i: int in range(decisions.size()):
		var id: String = str(decisions[i].get("chosen_id", ""))
		chosen_ids.append(id)
		if bad_at < 0 and id in ["f01_shop/ward", "f01_shop/flask"]:
			bad_at = i
	if bad_at < 0 or decisions.size() != int(expected.get("decision_count", -1)) or "\n".join(chosen_ids).sha256_text() != item["decision_signature"]:
		errors_local.append("Original decision signature or early first-shop intervention point differs.")
		return report
	var prepared: Dictionary = Navigation.prepare(game)
	var paired_steps: Array = []
	var path_comparisons: int = 0
	var path_steps: int = 0
	var intervention_complete: bool = false
	var explicit_override: bool = false
	for decision_index: int in range(decisions.size()):
		var decision: Dictionary = decisions[decision_index]
		if not Followup.same(Followup.budget(game.state), decision["before"]) or not Followup.same(game.campaign_snapshot(), shadow.campaign_snapshot()):
			errors_local.append("Original before-budget/full paired snapshot differs at decision %d." % decision_index)
			break
		var path: Array = decision.get("path", [])
		if path.is_empty():
			errors_local.append("An original decision has no real executable path.")
			break
		for step_index: int in range(path.size()):
			var step: Dictionary = path[step_index]
			var before: Dictionary = game.campaign_snapshot()
			var original_step: Dictionary = Navigation.execute(shadow, [step])
			if not bool(original_step.get("ok", false)):
				errors_local.append({"error": "Original paired action rejected.", "decision": decision_index, "step": step_index, "result": original_step})
				break
			var actual_step: Dictionary = {}
			var is_intervention: bool = decision_index == bad_at and step_index == path.size() - 1
			if is_intervention:
				if step.get("kind", "") != "buy" or "f01_shop/" + str(step.get("offer", "")) != decision["chosen_id"] or int(before["core_state"]["purchases"].get("f01_shop/edge", 0)) != 0:
					errors_local.append("First early bad purchase is not the exact shop action before required edge.")
					break
				var offer: String = str(decision["chosen_id"])
				# Zero yellow keys also occurs before the key was collected. It
				# cannot stand in for proof that the defense door was opened.
				var prefix_state: String = "defense_door_open" if before["core_state"]["cleared"].has("f01_defense_door") else ("key_available" if int(before["core_state"]["keys"].get("yellow", 0)) > 0 else "key_uncollected")
				var prefix_type: String = prefix_state + "/" + str(step["offer"])
				report["prefix_type"] = prefix_type
				var guard = Guard.new(game)
				# Deliberately no budgets argument: this measures production defaults.
				var preview: Dictionary = guard.preview(offer)
				if not bool(preview.get("ok", false)) or not Followup.same(before, game.campaign_snapshot()) or not Followup.same(before, preview.get("before_snapshot", {})) or not Followup.same(shadow.campaign_snapshot(), preview.get("after_snapshot", {})):
					errors_local.append({"error": "Default preview is unavailable, mutates the original or differs from actual unguarded post-purchase snapshot.", "preview": _guard_record(preview)})
					break
				var classification: String = str(preview.get("classification", ""))
				report["classification"] = classification
				var default_commit: Dictionary = guard.commit(preview.get("token", ""), false)
				var known_losing: bool = classification == "known_losing"
				var default_blocked: bool = known_losing and not bool(default_commit.get("ok", true)) and default_commit.get("status", "") == "blocked_known_loss" and bool(default_commit.get("token_consumed", false)) and Followup.same(before, game.campaign_snapshot())
				report["default_blocked"] = default_blocked
				report["intervention"] = {"decision": decision_index, "path_step": step_index, "original_action": step,
					"guarded_pre_purchase_full_snapshot": before, "unguarded_actual_post_purchase_full_snapshot": shadow.campaign_snapshot(),
					"default_preview": _guard_record(preview), "default_commit": _guard_record(default_commit),
					"full_state_unchanged_after_default_block": default_blocked,
					"first_divergence": {"exists": default_blocked, "decision": decision_index, "path_step": step_index, "guarded_action": "blocked_known_loss" if default_blocked else "original_purchase_allowed", "unguarded_action": step},
					"original_policy_after_block_continued_without_confirmation": false}
				if known_losing:
					if not default_blocked or preview.get("solver_report", {}).get("result", "") != "unsatisfiable":
						errors_local.append("A known-losing default query did not block without any full-state mutation.")
						break
					# Default commit consumed its ticket. Only a fresh real query and an
					# explicit true commit may choose the original losing continuation.
					var confirmed_preview: Dictionary = guard.preview(offer)
					var confirmed: Dictionary = guard.commit(confirmed_preview.get("token", ""), true)
					var second_known_loss: bool = confirmed_preview.get("classification", "") == "known_losing"
					var confirmation_ok: bool = bool(confirmed_preview.get("ok", false)) and bool(confirmed.get("ok", false)) and bool(confirmed.get("confirmed", false)) and Followup.same(before, confirmed_preview.get("before_snapshot", {})) and Followup.same(shadow.campaign_snapshot(), confirmed_preview.get("after_snapshot", {}))
					# A bounded second query may honestly become unknown due to wall
					# time. The first exact, complete proof remains recorded; true is
					# still explicit consent to the same actual purchase, not a new
					# safety claim or a forced known-loss classification.
					# A fresh complete winning witness for the identical after-state
					# contradicts the first complete unsatisfiability proof. Only an
					# honest bounded unknown may accompany this explicit override.
					confirmation_ok = confirmation_ok and (bool(confirmed.get("accepted_known_loss", false)) if second_known_loss else confirmed_preview.get("classification", "") == "unknown")
					if not confirmation_ok:
						errors_local.append({"error": "Explicit confirmation failed to execute the same proven losing purchase.", "preview": _guard_record(confirmed_preview), "commit": _guard_record(confirmed)})
						break
					explicit_override = true
					report["explicit_override"] = {"performed": true, "confirmed": true, "branch_scope": "The player explicitly accepts the original losing purchase; the unchanged original policy is replayed only on this accepted-loss branch.", "preview": _guard_record(confirmed_preview), "commit": _guard_record(confirmed)}
				else:
					if classification not in ["unknown", "known_winning"] or not bool(default_commit.get("ok", false)):
						errors_local.append("An unproven-loss query did not retain the original legal purchase semantics.")
						break
					report["explicit_override"] = {"performed": false, "reason": "No explicit override is required for a query that is not a known loss. Unknown has no safety guarantee."}
				actual_step = {"ok": true, "preview_comparisons": 0, "moves": 0, "method": "guard_commit", "explicitly_confirmed": explicit_override}
				intervention_complete = true
			else:
				actual_step = Navigation.execute(game, [step])
			path_steps += 1
			path_comparisons += int(actual_step.get("preview_comparisons", 0))
			var after: Dictionary = game.campaign_snapshot()
			var pair_ok: bool = bool(actual_step.get("ok", false)) and Followup.same(after, shadow.campaign_snapshot())
			paired_steps.append({"decision": decision_index, "step": step_index, "action": step,
				"branch": "original_prefix" if not intervention_complete else ("explicitly_confirmed_original_policy" if explicit_override else "default_permitted_original_policy"),
				"before_full_snapshot_sha256": Variants.content_hash(before), "after_full_snapshot_sha256": Variants.content_hash(after),
				"paired_actual_full_snapshot_equal": pair_ok, "actual_execution": actual_step, "unguarded_execution": original_step})
			if not pair_ok:
				errors_local.append("Actual full paired snapshots differ after decision %d step %d." % [decision_index, step_index])
				break
		if not errors_local.is_empty(): break
		if not Followup.same(Followup.budget(game.state), decision["after"]):
			errors_local.append("Original after-budget differs at decision %d." % decision_index)
			break
	report["actual_paired_actions"] = paired_steps
	report["actual_action_count"] = path_steps
	report["preview_deduction_comparisons"] = path_comparisons
	if not errors_local.is_empty() or not intervention_complete: return report
	var terminal: Dictionary = game.campaign_snapshot()
	var proof: Dictionary = Navigation.frontier(game, 0, true, prepared)
	var terminal_proven: bool = Followup.core_equal(terminal["core_state"], original_terminal) and Followup.same(terminal, shadow.campaign_snapshot()) and bool(proof.get("complete", false)) and bool(proof.get("queue_exhausted", false)) and proof.get("errors", []).is_empty() and proof.get("options", []).is_empty() and not bool(game.state.get("won", false))
	report["original_terminal_reproduced"] = terminal_proven
	report["explicit_override_reproduced_original_terminal"] = terminal_proven and explicit_override
	report["actual_terminal_full_snapshot"] = terminal
	report["actual_terminal_global_proof"] = proof
	if not terminal_proven:
		errors_local.append("Actual original policy terminal differs or full global Navigation still has a legal resource action.")
		return report
	var failure: Dictionary = game.assess_failure()
	var failed: Dictionary = game.campaign_snapshot()
	if not bool(failure.get("ok", false)) or not bool(failed.get("failed", false)) or failed.get("failure_reason", "") != "resource_exhausted" or not Followup.core_equal(failed["core_state"], original_terminal) or not Followup.sequence_equal(terminal, failed):
		errors_local.append("Actual terminal resource failure did not retain exact resources/world/seed.")
		return report
	report["actual_failure"] = {"result": failure, "failure_event_id": failed["failure_event_id"], "sequence_unchanged": Followup.sequence_equal(terminal, failed)}
	var checkpoint_id: String = str(initial_checkpoints[0]["checkpoint_id"])
	var did_restore: bool = game.restore_checkpoint(checkpoint_id)
	var restored: Dictionary = game.campaign_snapshot()
	var expected_restored: Dictionary = initial.duplicate(true)
	# restore_checkpoint deliberately retains the immutable record of past losses
	# and consumed respawns. Compare every other full snapshot field exactly.
	for history: String in INITIAL_HISTORY:
		expected_restored[history] = failed[history].duplicate(true)
	var restore_ok: bool = did_restore and Followup.same(restored, expected_restored) and Followup.core_equal(restored["core_state"], initial["core_state"]) and Followup.sequence_equal(initial, restored) and not bool(restored.get("failed", true))
	report["initial_checkpoint_restored"] = restore_ok
	report["complete_initial_checkpoint_recovery"] = {"checkpoint_id": checkpoint_id, "restored": restore_ok, "full_initial_snapshot": initial, "full_restored_snapshot": restored,
		"equivalence": "All full snapshot fields equal the actual initial snapshot, except the two specified retained-history arrays which must equal their exact actual pre-restore values. Core including position/cleared/keys/all offer stock, complete checkpoint tree, campaign seed/attempt/sequence/content/rules all match.",
		"retained_history_fields": INITIAL_HISTORY, "actual_full_winning_suffix_tested": false}
	if not restore_ok:
		errors_local.append("Complete initial checkpoint did not restore the exact original core/stock/seed/history contract.")
		return report
	var prefix_type: String = str(report["prefix_type"])
	var run_win: bool = early_win_mode == "all" or (early_win_mode == "representatives" and not early_types_won.has(prefix_type))
	if run_win:
		var victory: Dictionary = _early_complete_recovery(game, str(decisions[bad_at]["chosen_id"]))
		report["winning_recovery"] = victory
		report["actual_complete_winning_recovery"] = bool(victory.get("passed", false))
		report["complete_initial_checkpoint_recovery"]["actual_full_winning_suffix_tested"] = true
		if bool(victory.get("passed", false)):
			early_types_won[prefix_type] = int(item["index"])
		else:
			errors_local.append("Actual complete restored/cancel/edge/blade winning workflow failed.")
	else:
		report["winning_recovery"] = {"tested": false, "reason": "Full restored wins are explicitly sampled or disabled for this benchmark; exact complete checkpoint restoration above was actually tested."}
	report["passed"] = errors_local.is_empty()
	report["elapsed_ms"] = Time.get_ticks_msec() - began
	return report


func _early_complete_recovery(game: RefCounted, bad_offer: String) -> Dictionary:
	var began: int = Time.get_ticks_msec()
	_index(game.data)
	var prepared: Dictionary = Navigation.prepare(game)
	var initial: Dictionary = game.campaign_snapshot()
	var routes: Array = game.data.get("validated_routes", [])
	var route: Dictionary = {}
	for candidate: Dictionary in routes:
		if candidate.get("name", "") == "blade":
			if not route.is_empty(): return {"tested": true, "passed": false, "error": "Duplicate actual blade witness."}
			route = candidate
	var events: Array = route.get("events", [])
	var ledger: Array = route.get("ledger", [])
	if events.is_empty() or events.size() != ledger.size():
		return {"tested": true, "passed": false, "error": "Missing exact authored blade route/ledger."}
	var trace: Array = []
	var expected_cleared: Dictionary = {}
	var expected_purchases: Dictionary = {}
	var cancellation: Dictionary = {}
	var guarded_edge: bool = false
	var comparisons: int = 0
	var steps: int = 0
	for event_index: int in range(events.size()):
		var event: String = str(events[event_index])
		var planned: Dictionary = _event_path(game, event, prepared)
		if not bool(planned.get("ok", false)):
			return {"tested": true, "passed": false, "event": event, "error": planned, "trace": trace}
		var path: Array = planned["path"].duplicate(true)
		var before: Dictionary = game.state
		var result: Dictionary = {}
		if event == "buy:f01_shop/edge" and not guarded_edge:
			if path.is_empty() or path[-1].get("kind", "") != "buy":
				return {"tested": true, "passed": false, "error": "Actual edge path has no buy action."}
			var buy_step: Dictionary = path.pop_back()
			var approached: Dictionary = Navigation.execute(game, path)
			if not bool(approached.get("ok", false)):
				return {"tested": true, "passed": false, "error": "Actual restored edge approach failed.", "result": approached}
			steps += path.size()
			comparisons += int(approached.get("preview_comparisons", 0))
			var full_before_cancel: Dictionary = game.campaign_snapshot()
			var guard = Guard.new(game)
			var preview: Dictionary = guard.preview(bad_offer)
			var canceled: Dictionary = guard.cancel(preview.get("token", ""))
			var canceled_ok: bool = bool(preview.get("ok", false)) and bool(canceled.get("ok", false)) and Followup.same(full_before_cancel, game.campaign_snapshot())
			cancellation = {"passed": canceled_ok, "bad_offer": bad_offer, "default_preview": _guard_record(preview), "cancel": _guard_record(canceled), "full_state_unchanged": Followup.same(full_before_cancel, game.campaign_snapshot()), "actual_before_cancel_full_snapshot": full_before_cancel}
			if not canceled_ok:
				return {"tested": true, "passed": false, "error": "Actual player cancellation changed the full restored state or failed.", "cancellation": cancellation}
			result = Navigation.execute(game, [buy_step])
			path.append(buy_step)
			steps += 1
			guarded_edge = bool(result.get("ok", false)) and int(game.state["purchases"].get("f01_shop/edge", 0)) == 1
		else:
			result = Navigation.execute(game, path)
			steps += path.size()
		comparisons += int(result.get("preview_comparisons", 0))
		if not bool(result.get("ok", false)):
			return {"tested": true, "passed": false, "event": event, "error": result, "trace": trace}
		var object_id: String = event.trim_prefix("buy:").split("/")[0] if event.begins_with("buy:") else event
		if event.begins_with("buy:"):
			var purchase_id: String = event.trim_prefix("buy:")
			expected_purchases[purchase_id] = int(expected_purchases.get(purchase_id, 0)) + 1
		elif not ["stairs", "shop"].has(str(objects[object_id]["item"]["kind"])):
			expected_cleared[object_id] = true
		var after: Dictionary = game.state
		var invariant: String = _event_invariants(after, ledger[event_index]["state"], expected_cleared, expected_purchases, game.campaign_snapshot(), initial)
		if ledger[event_index].has("damage") and int(before["hp"]) - int(after["hp"]) != int(ledger[event_index]["damage"]): invariant += " Actual damage differs from authored ledger."
		if not invariant.is_empty():
			return {"tested": true, "passed": false, "event": event, "error": invariant, "trace": trace}
		trace.append({"event_index": event_index, "event": event, "actions": path, "actual_execution": result, "before": Followup.budget(before), "after": Followup.budget(after), "actual_core_sha256": Variants.content_hash(after)})
	var won: bool = guarded_edge and bool(game.state.get("won", false)) and trace.size() == events.size() and _same_budget(game.state, route["final"]) and not game.is_failed() and Followup.sequence_equal(initial, game.campaign_snapshot())
	return {"tested": true, "passed": won, "route": "blade", "actual_campaign_seed": initial["campaign_seed"], "complete_checkpoint_full_state_used": true,
		"scope": "Actual CampaignRules restored checkpoint then actual authored blade actions. At the real edge purchase point the bad preview is canceled with full state unchanged, then original buy(edge) is actually executed; no gold/key/resource injection or budget override.",
		"cancellation": cancellation, "actual_edge_bought_once": guarded_edge, "events_checked": trace.size(), "expected_events": events.size(),
		"actual_actions": steps, "preview_deduction_comparisons": comparisons, "trace": trace, "full_final_snapshot": game.campaign_snapshot(), "elapsed_ms": Time.get_ticks_msec() - began}


func _guard_record(value: Dictionary) -> Dictionary:
	var result: Dictionary = value.duplicate(true)
	# Cryptographic one-shot tokens are authority handles, not replay inputs.
	# Keep all actual query bindings/results/accounting without leaking handles.
	result.erase("token")
	return result


func _early_append(value: Dictionary) -> void:
	early_journal.store_string(JSON.stringify(value) + "\n")
	early_line += 1


func _early_abort(message: String, observed: Dictionary = {}) -> void:
	print(JSON.stringify({"measurement_completed": false, "passed": false, "error": message, "observed": observed}))
	quit(2)
