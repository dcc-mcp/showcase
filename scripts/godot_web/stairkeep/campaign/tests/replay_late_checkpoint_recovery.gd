extends "res://tests/replay_variant_routes.gd"
## Rebuild real Save-v2 checkpoints from the exact retained failure paths.
## No baseline/source/economy edits, synthetic checkpoint or seed replacement.

const Recovery = preload("res://tests/recovery_followup_helpers.gd")
const SuffixSolver = preload("res://tests/campaign_solver.gd")
const ROUTE_ORDER: Array[String] = ["blade", "bulwark", "balanced", "frugal"]
const BOUND_RECOVERY_INPUT_SHA256: String = "45b905d9157585ba8a06df612c9a727ad5bbe3ee7c89c4e4bae0253f94c567d0"
const BOUND_CLASSIFICATION_SHA256: String = "b5fbebe1a7d081d810d45fab736d04a788d55883383bdf146982ce517f39041d"
const EXPECTED_LATE_INDICES: Array[int] = [24, 169, 599, 1289, 1349, 1634, 1979, 1994, 2279, 2479, 2739, 3129, 3354, 3379, 4554, 5269, 5704, 5854, 7609, 7784, 7899, 8179, 8194, 8574, 8704, 9019]
const CASE_IDENTITY_FIELDS: Array[String] = ["index", "policy", "layout_seed", "policy_seed", "decision_signature", "layout_hash"]
# Stable replay fields contain only exact integers, strings and resource trees.
# Timing measurements are not identities and cannot use the integer serializer.
const RECORD_REPLAY_FIELDS: Array[String] = ["index", "policy", "layout_seed", "policy_seed", "decision_signature", "layout_hash", "decision_count", "policy_rng_final", "final", "outcome", "canonical_hash", "layout_seed_after", "layout_draw_count", "resolved_start", "policy_draws", "navigation_moves", "preview_actual_comparisons", "armor_gate_preparations"]

var recovery_input: String = ""
var recovery_output: String = ""
var recovery_offset: int = 0
var recovery_count: int = -1
var recovery_stop_file: String = ""
var recovery_nearest: bool = true
var recovery_planner: String = "campaign"
var recovery_policy_limit: int = 128
var recovery_solver_msec: int = 1000
var recovery_journal: FileAccess
var recovery_line: int = 0
var recovery_loaded: Dictionary = {}
var recovery_queue: Dictionary = {}
var recovery_canonical: Dictionary = {}
var recovery_routes: Dictionary = {}
var recovery_errors: Array = []
var recovery_results: Array = []
var recovery_started: int = 0
var recovery_requested: int = 0
var recovery_stopped: bool = false
var recovery_preflight: Dictionary = {}
var recovery_selected_indices: Array[int] = []


func _run() -> void:
	if not _recovery_arguments():
		quit(2)
		return
	recovery_loaded = Recovery.load_queue(recovery_input)
	if not bool(recovery_loaded.get("ok", false)):
		print(JSON.stringify(recovery_loaded))
		quit(2)
		return
	recovery_queue = recovery_loaded["input"]
	recovery_preflight = _late_queue_preflight()
	if not bool(recovery_preflight.get("ok", false)):
		print(JSON.stringify({"kind": "late_recovery_preflight_rejected", "preflight": recovery_preflight}))
		quit(2)
		return
	var all_cases: Array = recovery_queue["late_cases"]
	if recovery_offset > all_cases.size():
		print("Offset is outside the bound late-case queue.")
		quit(2)
		return
	var end: int = all_cases.size() if recovery_count < 0 else mini(all_cases.size(), recovery_offset + recovery_count)
	var selected: Array = all_cases.slice(recovery_offset, end)
	recovery_requested = selected.size()
	for item: Dictionary in selected:
		recovery_selected_indices.append(int(item["index"]))
	if FileAccess.file_exists(recovery_output) or FileAccess.file_exists(recovery_output + ".summary.json"):
		print("Output/summary already exists; original evidence was not overwritten.")
		quit(2)
		return
	recovery_journal = FileAccess.open(recovery_output, FileAccess.WRITE)
	if recovery_journal == null:
		print("Cannot open the new recovery journal.")
		quit(2)
		return
	recovery_started = Time.get_ticks_msec()
	_emit_recovery({"kind": "late_recovery_header", "schema_version": 1, "engine_pid": OS.get_process_id(), "engine": Engine.get_version_info(), "input_sha256": recovery_loaded["input_sha256"], "input_file": recovery_loaded["input_file"], "source_bindings": recovery_queue["source_bindings"], "test_sha256": FileAccess.get_sha256("res://tests/replay_late_checkpoint_recovery.gd"), "helper_sha256": FileAccess.get_sha256("res://tests/recovery_followup_helpers.gd"), "offset": recovery_offset, "requested": recovery_requested, "nearest_checkpoint_search": recovery_nearest, "planner": recovery_planner, "resource_policy_decisions": recovery_policy_limit, "solver_msec_per_checkpoint": recovery_solver_msec, "stop_contract": "Stop is checked before each case; the in-flight case completes its mandatory initial-checkpoint winning replay.", "scope": "Exact original paths execute through CampaignRules to capture actual full checkpoints. Winning suffixes and unknowns are separate observations; no resources, stock or seeds are manufactured."})
	_emit_recovery({"kind": "late_queue_preflight", "preflight": recovery_preflight, "selected_indices": recovery_selected_indices})
	print(JSON.stringify({"kind": "late_recovery_started", "engine_pid": OS.get_process_id(), "offset": recovery_offset, "requested": recovery_requested}))
	var sources: Dictionary = Recovery.verify_source_bindings(recovery_queue)
	var raw_sources: Dictionary = Recovery.verify_raw_sources(selected, recovery_queue["source_files"], recovery_loaded["base_dir"])
	_emit_recovery({"kind": "source_binding_result", "sources": sources, "raw_sources": raw_sources})
	if not bool(sources.get("ok", false)) or not bool(raw_sources.get("ok", false)):
		recovery_errors.append({"stage": "source_binding", "sources": sources, "raw_sources": raw_sources})
		_finish_recovery()
		return
	var json: JSON = JSON.new()
	if json.parse(FileAccess.get_file_as_string(DATA_PATH)) != OK or not (json.data is Dictionary):
		recovery_errors.append({"stage": "canonical", "error": "Current bound canonical JSON could not load."})
		_finish_recovery()
		return
	recovery_canonical = json.data
	for route: Dictionary in recovery_canonical.get("validated_routes", []):
		recovery_routes[str(route["name"])] = route
	if not recovery_routes.has("blade"):
		recovery_errors.append({"stage": "canonical", "error": "The mandatory complete blade witness is absent."})
		_finish_recovery()
		return
	for local_offset: int in range(selected.size()):
		if not recovery_stop_file.is_empty() and FileAccess.file_exists(recovery_stop_file):
			recovery_stopped = true
			break
		var item: Dictionary = selected[local_offset]
		var result: Dictionary = _recover_case(item, recovery_offset + local_offset)
		recovery_results.append(result)
		if not bool(result.get("passed", false)):
			recovery_errors.append({"index": item.get("index"), "error": result.get("error", "Recovery case did not pass.")})
		_emit_recovery({"kind": "late_case_summary", "result": result})
		print(JSON.stringify({"kind": "late_case_complete", "index": item.get("index"), "completed": recovery_results.size(), "requested": recovery_requested, "passed": result.get("passed", false), "initial_blade_won": result.get("initial_blade_won", false), "nearest_verified_winning_checkpoint": result.get("nearest_verified_winning_checkpoint"), "elapsed_ms": result.get("elapsed_ms", 0)}))
	_finish_recovery()


func _late_queue_preflight() -> Dictionary:
	if recovery_loaded.get("input_sha256", "") != BOUND_RECOVERY_INPUT_SHA256:
		return {"ok": false, "error": "This follow-up requires the exact SHA-bound original 26/1336 recovery queue."}
	if recovery_queue.get("source_bindings", {}).get("classification_sha256", "") != BOUND_CLASSIFICATION_SHA256:
		return {"ok": false, "error": "Original classification binding differs."}
	if not (recovery_queue.get("late_cases") is Array) or recovery_queue["late_cases"].size() != EXPECTED_LATE_INDICES.size():
		return {"ok": false, "error": "The complete input must contain exactly 26 late cases."}
	if not (recovery_queue.get("late_case_indices") is Array) or not Recovery.same(recovery_queue["late_case_indices"], EXPECTED_LATE_INDICES):
		return {"ok": false, "error": "The queue's declared late indices differ from the bound classification."}
	var seen: Dictionary = {}
	var raw_identities_verified: int = 0
	for value: Variant in recovery_queue["late_cases"]:
		if not (value is Dictionary):
			return {"ok": false, "error": "A late-case entry is not a dictionary."}
		var item: Dictionary = value
		if not Recovery.whole(item.get("index")):
			return {"ok": false, "error": "Every late index must be an exact integer."}
		var index: int = int(item["index"])
		if seen.has(index) or not EXPECTED_LATE_INDICES.has(index):
			return {"ok": false, "error": "Duplicate or unexpected late index.", "index": index}
		if item.get("cohort", "") != "late" or not Recovery.whole(item.get("failure_stage_floor")) or int(item["failure_stage_floor"]) != 21:
			return {"ok": false, "error": "Late cohort/failure-stage membership differs.", "index": index}
		if not (item.get("original_expected_record") is Dictionary):
			return {"ok": false, "error": "Late case has no original expected record.", "index": index}
		var expected: Dictionary = item["original_expected_record"]
		for field: String in CASE_IDENTITY_FIELDS:
			if not item.has(field) or not expected.has(field) or not Recovery.same(item[field], expected[field]):
				return {"ok": false, "error": "Queue identity differs from its embedded original record: " + field, "index": index}
		if not (item.get("verification_locator") is Dictionary):
			return {"ok": false, "error": "Late case has no bound original verification locator.", "index": index}
		var read: Dictionary = Recovery.read_bound_line(item["verification_locator"], recovery_loaded["base_dir"], recovery_queue["source_files"])
		if not bool(read.get("ok", false)):
			return {"ok": false, "error": "Original raw verification locator failed.", "index": index, "detail": read.get("error")}
		var proof: Dictionary = read["record"]
		var identity: Dictionary = _original_record_identity(item, proof)
		if not bool(identity.get("ok", false)):
			identity["index"] = index
			return identity
		seen[index] = true
		raw_identities_verified += 1
	var actual_indices: Array = seen.keys()
	actual_indices.sort()
	if not seen.has(599) or not Recovery.same(actual_indices, EXPECTED_LATE_INDICES):
		return {"ok": false, "error": "The complete late cohort differs from the exact bound index set.", "actual_indices": actual_indices}
	return {"ok": true, "input_sha256": BOUND_RECOVERY_INPUT_SHA256, "classification_sha256": BOUND_CLASSIFICATION_SHA256, "expected_indices": EXPECTED_LATE_INDICES.duplicate(), "actual_indices": actual_indices, "unique_count": seen.size(), "raw_verification_identities_verified": raw_identities_verified, "cohort": "late", "failure_stage_floor": 21, "includes_historical_case_599": true, "scope": "The entire input cohort is checked before selecting an offset/count shard; terminal floor does not define late membership."}


func _original_record_identity(item: Dictionary, proof: Dictionary, trace_original: Dictionary = {}) -> Dictionary:
	if proof.get("kind", "") != "verified_failure" or not bool(proof.get("verified", false)) or not Recovery.whole(proof.get("index")) or int(proof["index"]) != int(item["index"]):
		return {"ok": false, "error": "Original raw verification kind/verified index differs."}
	if not (proof.get("expected_record") is Dictionary) or not (proof.get("actual_record") is Dictionary):
		return {"ok": false, "error": "Original raw verification omits its expected/actual replay records."}
	var embedded: Dictionary = item["original_expected_record"]
	var records: Array = [proof["expected_record"], proof["actual_record"]]
	if not trace_original.is_empty():
		records.append(trace_original)
	for record: Dictionary in records:
		for field: String in RECORD_REPLAY_FIELDS:
			if not embedded.has(field) or not record.has(field) or not Recovery.same(embedded[field], record[field]):
				return {"ok": false, "error": "Original expected/actual/trace stable replay field differs: " + field}
	return {"ok": true}


func _recovery_arguments() -> bool:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--input="): recovery_input = argument.trim_prefix("--input=")
		elif argument.begins_with("--output="): recovery_output = argument.trim_prefix("--output=")
		elif argument.begins_with("--offset="): recovery_offset = int(argument.trim_prefix("--offset="))
		elif argument.begins_with("--count="): recovery_count = int(argument.trim_prefix("--count="))
		elif argument.begins_with("--stop-file="): recovery_stop_file = argument.trim_prefix("--stop-file=")
		elif argument.begins_with("--planner="): recovery_planner = argument.trim_prefix("--planner=")
		elif argument == "--initial-only": recovery_nearest = false
		elif argument.begins_with("--policy-decisions="): recovery_policy_limit = int(argument.trim_prefix("--policy-decisions="))
		elif argument.begins_with("--solver-ms="): recovery_solver_msec = int(argument.trim_prefix("--solver-ms="))
		else:
			print("Unknown late-recovery argument: " + argument)
			return false
	return not recovery_input.is_empty() and not recovery_output.is_empty() and recovery_offset >= 0 and recovery_count >= -1 and recovery_planner in ["campaign", "base"] and recovery_policy_limit >= 0 and recovery_policy_limit <= 512 and recovery_solver_msec >= 0 and recovery_solver_msec <= 30000


func _recover_case(item: Dictionary, queue_offset: int) -> Dictionary:
	var began: int = Time.get_ticks_msec()
	var index: int = int(item["index"])
	_emit_recovery({"kind": "late_case_begin", "index": index, "queue_offset": queue_offset, "layout_seed": item.get("layout_seed"), "policy_seed": item.get("policy_seed"), "decision_signature": item.get("decision_signature")})
	var trace_read: Dictionary = Recovery.read_bound_line(item["trace_locator"], recovery_loaded["base_dir"], recovery_queue["source_files"])
	var proof_read: Dictionary = Recovery.read_bound_line(item["verification_locator"], recovery_loaded["base_dir"], recovery_queue["source_files"])
	if not bool(trace_read.get("ok", false)) or not bool(proof_read.get("ok", false)):
		return {"index": index, "passed": false, "error": "Original bound trace/proof bytes failed.", "trace": trace_read.get("error"), "proof": proof_read.get("error")}
	var trace_record: Dictionary = trace_read["record"]
	var proof_record: Dictionary = proof_read["record"]
	if trace_record.get("kind", "") != "example" or not (trace_record.get("example") is Dictionary) or proof_record.get("kind", "") != "verified_failure" or not bool(proof_record.get("verified", false)) or int(proof_record.get("index", -1)) != index:
		return {"index": index, "passed": false, "error": "Original trace/proof record kinds or verified identity differ."}
	var example: Dictionary = trace_record["example"]
	var original_record: Dictionary = example.get("record", {})
	var identity: Dictionary = _original_record_identity(item, proof_record, original_record)
	if not bool(identity.get("ok", false)) or original_record.is_empty():
		return {"index": index, "passed": false, "error": identity.get("error", "Original trace record is absent.")}
	var game = Campaign.new()
	# API accepts normalized eight-character hex; 0x is only a CLI notation.
	var loaded: Dictionary = game.start_campaign(recovery_canonical, str(item["layout_seed"]))
	if not bool(loaded.get("ok", false)):
		return {"index": index, "passed": false, "error": "Campaign seed initialization failed.", "load": loaded}
	var initial: Dictionary = game.campaign_snapshot()
	if initial["transformed_content_sha256"] != item.get("layout_hash", "") or not Recovery.core_equal(game.state, example.get("initial_state", {})):
		return {"index": index, "passed": false, "error": "The actual mirrored initial state differs from the raw original."}
	var chosen: PackedStringArray = []
	var moves: int = 0
	var comparisons: int = 0
	var decisions: Array = example.get("decisions", [])
	for decision: Dictionary in decisions:
		var before: Dictionary = game.state
		if decision.has("before") and not Recovery.same(Recovery.budget(before), decision["before"]):
			return {"index": index, "passed": false, "error": "Original before-budget mismatch.", "decision": decision.get("decision")}
		var executed: Dictionary = Navigation.execute(game, decision.get("path", []))
		if not bool(executed.get("ok", false)):
			return {"index": index, "passed": false, "error": "Original actual path execution failed.", "decision": decision.get("decision"), "execution": executed}
		var after: Dictionary = game.state
		if decision.has("after") and not Recovery.same(Recovery.budget(after), decision["after"]):
			return {"index": index, "passed": false, "error": "Original after-budget mismatch.", "decision": decision.get("decision")}
		moves += int(executed.get("moves", 0))
		comparisons += int(executed.get("preview_comparisons", 0))
		chosen.append(str(decision.get("chosen_id", "")))
	var terminal: Dictionary = game.state
	var signature: String = "\n".join(chosen).sha256_text()
	if signature != item["decision_signature"] or decisions.size() != int(original_record.get("decision_count", -1)) or not Recovery.core_equal(terminal, example.get("final_state", {})) or not Recovery.core_equal(terminal, item.get("full_terminal_state", {})) or not Recovery.core_equal(terminal, proof_record.get("full_terminal_state", {})):
		return {"index": index, "passed": false, "error": "Complete original terminal state/signature differs.", "actual_terminal": terminal, "actual_signature": signature}
	var original_campaign: Dictionary = game.campaign_snapshot()
	if not Recovery.sequence_equal(initial, original_campaign):
		return {"index": index, "passed": false, "error": "Original-path replay changed seed/variant sequence metadata."}
	var assessed: Dictionary = game.assess_failure()
	var failed: Dictionary = game.campaign_snapshot()
	var original_proof: Dictionary = proof_record.get("continuous_reconstruction", {}).get("global_navigation_proof", {})
	var actual_proof: Dictionary = failed.get("last_failure_event", {}).get("frontier", {})
	if not bool(assessed.get("ok", false)) or not game.is_failed() or failed.get("failure_reason", "") != "resource_exhausted" or not Recovery.core_equal(game.state, terminal) or not bool(actual_proof.get("complete", false)) or not actual_proof.get("options", []).is_empty() or int(actual_proof.get("reachable", -1)) != int(original_proof.get("reachable", -2)):
		return {"index": index, "passed": false, "error": "Actual campaign failure assessment did not reproduce the complete terminal proof.", "assessment": assessed}
	var captured: Array = failed["checkpoints"]
	var original_row: Dictionary = {"kind": "original_campaign_failure_rebuilt", "index": index, "queue_offset": queue_offset, "trace_locator": item["trace_locator"], "verification_locator": item["verification_locator"], "layout_seed": item["layout_seed"], "policy_seed": item["policy_seed"], "decision_signature": signature, "decisions_replayed": decisions.size(), "actual_moves": moves, "preview_deduction_comparisons": comparisons, "base_terminal_equal": true, "full_terminal_core": terminal, "captured_checkpoint_ids": _checkpoint_ids(captured), "initial_full_snapshot": initial, "assessed_full_campaign_snapshot": failed}
	var original_locator: Dictionary = _emit_recovery(original_row)
	var nearest: Variant = null
	var checkpoint_results: Array = []
	var fatal: bool = false
	if recovery_nearest:
		for position: int in range(captured.size() - 1, -1, -1):
			var checkpoint: Dictionary = captured[position]
			var chapter: int = int(checkpoint["core_state"]["floor"]) + 1
			if chapter == 1:
				continue
			var attempt: Dictionary = _checkpoint_search(game, checkpoint, index)
			checkpoint_results.append(_attempt_summary(attempt))
			if bool(attempt.get("fatal", false)):
				fatal = true
				break
			if bool(attempt.get("won", false)):
				nearest = chapter
				break
	# This independent complete replay is mandatory even when a later checkpoint
	# already won. It is not inferred from a canonical-family certificate.
	var first: Dictionary = captured[0] if not captured.is_empty() else {}
	var restored: Dictionary = _restore_actual_checkpoint(game, first)
	if not bool(restored.get("ok", false)):
		return {"index": index, "passed": false, "error": "Mandatory actual initial-checkpoint restore failed.", "restore": restored, "original_replay_locator": original_locator}
	var initial_game: RefCounted = restored["game"]
	if not Recovery.core_equal(initial_game.state, example["initial_state"]):
		return {"index": index, "passed": false, "error": "Initial checkpoint did not restore the complete same-seed initial core."}
	var blade_result: Dictionary = _ordered_suffix(initial_game, recovery_routes["blade"], 1, true)
	var initial_locator: Dictionary = _emit_recovery({"kind": "initial_checkpoint_complete_blade", "index": index, "restore": restored["evidence"], "attempt": blade_result})
	var initial_won: bool = bool(blade_result.get("won", false)) and not bool(blade_result.get("fatal", false))
	if nearest == null and initial_won:
		nearest = 1
	return {"index": index, "queue_offset": queue_offset, "passed": initial_won and not fatal, "error": "" if initial_won and not fatal else "A mandatory initial winning replay or an actual-action invariant failed.", "layout_seed": item["layout_seed"], "policy_seed": item["policy_seed"], "decision_signature": signature, "original_replay_locator": original_locator, "initial_winning_locator": initial_locator, "original_terminal_floor": int(terminal["floor"]) + 1, "captured_checkpoint_ids": _checkpoint_ids(captured), "checkpoint_attempts": checkpoint_results, "nearest_verified_winning_checkpoint": nearest, "nearest_search_performed": recovery_nearest, "initial_blade_won": initial_won, "all_checkpoints_solvable_claimed": false, "initial_final_budget": blade_result.get("final_budget", {}), "elapsed_ms": Time.get_ticks_msec() - began}


func _restore_actual_checkpoint(source: RefCounted, checkpoint: Dictionary) -> Dictionary:
	if checkpoint.is_empty():
		return {"ok": false, "error": "No actual captured checkpoint was supplied."}
	var before: Dictionary = source.campaign_snapshot()
	var at: int = -1
	for index: int in range(before["checkpoints"].size()):
		if before["checkpoints"][index]["checkpoint_id"] == checkpoint["checkpoint_id"]:
			at = index
			break
	if at < 0:
		return {"ok": false, "error": "Checkpoint is not in this actually replayed run."}
	var expected: Dictionary = checkpoint.duplicate(true)
	expected["checkpoints"] = before["checkpoints"].slice(0, at + 1).duplicate(true)
	expected["failure_events_seen"] = before["failure_events_seen"].duplicate()
	expected["consumed_loss_ids"] = before["consumed_loss_ids"].duplicate()
	var game: RefCounted = source.clone_for_search()
	var ok: bool = game.restore_checkpoint(str(checkpoint["checkpoint_id"]))
	var after: Dictionary = game.campaign_snapshot()
	var matches: bool = ok and Recovery.same(after, expected) and Recovery.core_equal(game.state, checkpoint["core_state"]) and Recovery.sequence_equal(before, after) and not game.is_failed()
	return {"ok": matches, "game": game, "evidence": {"checkpoint_id": checkpoint["checkpoint_id"], "captured_checkpoint_sha256": Variants.content_hash(checkpoint), "expected_complete_snapshot_sha256": Variants.content_hash(expected), "actual_complete_snapshot_sha256": Variants.content_hash(after), "full_snapshot_matches_contract": matches, "historical_lists_preserved": Recovery.same(after["failure_events_seen"], before["failure_events_seen"]) and Recovery.same(after["consumed_loss_ids"], before["consumed_loss_ids"]), "contract": "Complete captured checkpoint plus its earlier checkpoint prefix; preserve failure_events_seen and consumed_loss_ids exactly as restore_checkpoint specifies. No other field is dropped or patched.", "actual_restored_snapshot": after}}


func _checkpoint_search(source: RefCounted, checkpoint: Dictionary, index: int) -> Dictionary:
	var chapter: int = int(checkpoint["core_state"]["floor"]) + 1
	var restored: Dictionary = _restore_actual_checkpoint(source, checkpoint)
	if not bool(restored.get("ok", false)):
		var failed: Dictionary = {"checkpoint_id": checkpoint.get("checkpoint_id"), "chapter": chapter, "won": false, "fatal": true, "result": "restore_error", "restore": restored.get("evidence", {})}
		_emit_recovery({"kind": "checkpoint_attempt", "index": index, "attempt": failed})
		return failed
	var base: RefCounted = restored["game"]
	_emit_recovery({"kind": "checkpoint_restored", "index": index, "chapter": chapter, "restore": restored["evidence"]})
	var tried: Array = []
	for name: String in ROUTE_ORDER:
		if not recovery_routes.has(name):
			continue
		var candidate: RefCounted = base.clone_for_search()
		var result: Dictionary = _ordered_suffix(candidate, recovery_routes[name], chapter, false)
		var locator: Dictionary = _emit_recovery({"kind": "checkpoint_suffix_attempt", "index": index, "checkpoint_id": checkpoint["checkpoint_id"], "chapter": chapter, "strategy": "authored_id_order/" + name, "attempt": result})
		tried.append({"strategy": name, "result": result.get("result", "unknown"), "won": result.get("won", false), "locator": locator})
		if bool(result.get("fatal", false)) or bool(result.get("won", false)):
			return {"checkpoint_id": checkpoint["checkpoint_id"], "chapter": chapter, "won": result.get("won", false), "fatal": result.get("fatal", false), "result": result.get("result", "unknown"), "strategy": name, "attempts": tried}
	if recovery_policy_limit > 0:
		var resource_result: Dictionary = _resource_suffix(base.clone_for_search())
		var resource_locator: Dictionary = _emit_recovery({"kind": "checkpoint_suffix_attempt", "index": index, "checkpoint_id": checkpoint["checkpoint_id"], "chapter": chapter, "strategy": "observed_resource_policy", "attempt": resource_result})
		tried.append({"strategy": "observed_resource_policy", "result": resource_result.get("result"), "won": resource_result.get("won", false), "locator": resource_locator})
		if bool(resource_result.get("fatal", false)) or bool(resource_result.get("won", false)):
			return {"checkpoint_id": checkpoint["checkpoint_id"], "chapter": chapter, "won": resource_result.get("won", false), "fatal": resource_result.get("fatal", false), "result": resource_result.get("result", "unknown"), "strategy": "observed_resource_policy", "attempts": tried}
	if recovery_solver_msec > 0:
		var solved: Dictionary = SuffixSolver.solve(base, {"max_expanded": 100, "max_states": 1000, "max_msec": recovery_solver_msec, "navigation_max_nodes": 0})
		var solver_result: Dictionary = {"result": "unknown", "won": false, "fatal": false, "solver": solved}
		if solved.get("result", "") == "witness" and bool(solved.get("witness_verification", {}).get("ok", false)):
			var replay: RefCounted = base.clone_for_search()
			var actual_paths: Array = []
			var actual_ok: bool = true
			for event: Dictionary in solved.get("witness", []):
				var executed: Dictionary = Navigation.execute(replay, event["actions"])
				actual_paths.append({"target": event.get("target"), "actions": event["actions"], "execution": executed, "after": Recovery.budget(replay.state)})
				if not bool(executed.get("ok", false)):
					actual_ok = false
					break
			solver_result["won"] = actual_ok and bool(replay.state["won"])
			solver_result["fatal"] = not actual_ok
			solver_result["result"] = "verified_winning_suffix" if bool(solver_result["won"]) else "solver_replay_error"
			solver_result["actual_actions"] = actual_paths
			solver_result["final_snapshot"] = replay.campaign_snapshot()
		elif solved.get("result", "") == "unsatisfiable" and bool(solved.get("receipt", {}).get("complete", false)) and solved.get("receipt", {}).get("state_sha256", "") == base.current_state_sha256():
			solver_result["result"] = "proven_no_ordinary_suffix"
		var solver_locator: Dictionary = _emit_recovery({"kind": "checkpoint_solver_attempt", "index": index, "checkpoint_id": checkpoint["checkpoint_id"], "chapter": chapter, "attempt": solver_result})
		tried.append({"strategy": "bounded_solver", "result": solver_result["result"], "won": solver_result["won"], "locator": solver_locator})
		return {"checkpoint_id": checkpoint["checkpoint_id"], "chapter": chapter, "won": solver_result["won"], "fatal": solver_result["fatal"], "result": solver_result["result"], "strategy": "bounded_solver", "attempts": tried}
	return {"checkpoint_id": checkpoint["checkpoint_id"], "chapter": chapter, "won": false, "fatal": false, "result": "unknown_no_verified_suffix", "attempts": tried}


func _ordered_suffix(game: RefCounted, route: Dictionary, chapter: int, exact_initial: bool) -> Dictionary:
	var began: int = Time.get_ticks_msec()
	_index(game.data)
	var prepared: Dictionary = Navigation.prepare(game)
	var initial: Dictionary = game.campaign_snapshot()
	var events: Array = route["events"]
	var start: int = 0
	if chapter > 1:
		start = -1
		for index: int in range(events.size()):
			var event: String = str(events[index])
			if not event.begins_with("buy:") and objects.has(event) and int(objects[event]["floor"]) + 1 == chapter and objects[event]["item"]["kind"] != "stairs":
				start = index
				break
		if start < 0:
			return {"result": "unknown_no_chapter_suffix", "won": false, "fatal": false, "route": route["name"]}
	var occurrences: Dictionary = {}
	for index: int in range(start):
		var event: String = str(events[index])
		if event.begins_with("buy:"):
			var key: String = event.trim_prefix("buy:")
			occurrences[key] = int(occurrences.get(key, 0)) + 1
	var expected_cleared: Dictionary = {}
	var expected_purchases: Dictionary = {}
	var trace: Array = []
	var skipped: Array = []
	for index: int in range(start, events.size()):
		var event: String = str(events[index])
		var before: Dictionary = game.state
		if event.begins_with("buy:"):
			var purchase: String = event.trim_prefix("buy:")
			occurrences[purchase] = int(occurrences.get(purchase, 0)) + 1
			if not exact_initial and int(before["purchases"].get(purchase, 0)) >= int(occurrences[purchase]):
				skipped.append({"event": event, "reason": "Actual purchase count already covers this canonical occurrence.", "actual_count": before["purchases"].get(purchase, 0), "canonical_occurrence": occurrences[purchase], "core_state_sha256": Variants.content_hash(before)})
				continue
		elif before["cleared"].has(event):
			if exact_initial:
				return {"result": "unexpected_precleared_initial", "won": false, "fatal": true, "event": event}
			skipped.append({"event": event, "reason": "Object is already cleared in this actual checkpoint timeline.", "core_state_sha256": Variants.content_hash(before)})
			continue
		var planning: Dictionary = _planning_authority(game)
		if not bool(planning.get("ok", false)):
			return {"result": "planning_error", "won": false, "fatal": true, "error": planning.get("error"), "trace": trace, "skipped": skipped}
		var path: Dictionary = _event_path(planning["game"], event, prepared)
		if not bool(path.get("ok", false)):
			return {"result": "unknown_id_order_not_executable", "won": false, "fatal": false, "route": route["name"], "first_unavailable_event": event, "planning": path, "trace": trace, "skipped": skipped, "final_snapshot": game.campaign_snapshot(), "elapsed_ms": Time.get_ticks_msec() - began}
		var execution: Dictionary = Navigation.execute(game, path["path"])
		var after: Dictionary = game.state
		var error: String = _actual_delta_error(before, after, event, path["item"], execution)
		if not bool(execution.get("ok", false)) or not error.is_empty():
			return {"result": "actual_action_error", "won": false, "fatal": true, "event": event, "error": error, "execution": execution, "trace": trace, "skipped": skipped}
		if exact_initial:
			if event.begins_with("buy:"):
				var id: String = event.trim_prefix("buy:")
				expected_purchases[id] = int(expected_purchases.get(id, 0)) + 1
			elif not ["stairs", "shop"].has(str(path["item"]["kind"])):
				expected_cleared[event] = true
			var ledger: Dictionary = route["ledger"][index]
			if ledger.get("event", "") != event or not _same_budget(after, ledger["state"]) or not Recovery.same(after["purchases"], expected_purchases) or not _same_id_set(after["cleared"], expected_cleared.keys()) or (ledger.has("damage") and int(before["hp"]) - int(after["hp"]) != int(ledger["damage"])):
				return {"result": "initial_blade_ledger_mismatch", "won": false, "fatal": true, "event": event, "actual": Recovery.budget(after), "expected": ledger.get("state"), "trace": trace}
		trace.append({"event": event, "canonical_index": index, "path": path["path"].duplicate(true), "before": Recovery.budget(before), "after": Recovery.budget(after), "actual_execution": execution, "cleared_added": _added_ids(before["cleared"], after["cleared"]), "full_core_sha256": Variants.content_hash(after)})
		if bool(after["won"]):
			var final: Dictionary = game.campaign_snapshot()
			var bound: bool = Recovery.sequence_equal(initial, final)
			var exact: bool = not exact_initial or (_same_budget(after, route["final"]) and index == events.size() - 1)
			return {"result": "verified_winning_suffix" if bound and exact else "winning_binding_error", "won": bound and exact, "fatal": not bound or not exact, "route": route["name"], "chapter": chapter, "exact_initial_blade": exact_initial, "start_canonical_index": start, "trace": trace, "skipped": skipped, "final_budget": Recovery.budget(after), "final_snapshot": final, "elapsed_ms": Time.get_ticks_msec() - began}
	return {"result": "unknown_id_order_exhausted_without_victory", "won": false, "fatal": false, "route": route["name"], "trace": trace, "skipped": skipped, "final_snapshot": game.campaign_snapshot(), "elapsed_ms": Time.get_ticks_msec() - began}


func _resource_suffix(game: RefCounted) -> Dictionary:
	var initial: Dictionary = game.campaign_snapshot()
	var prepared: Dictionary = Navigation.prepare(game)
	var trace: Array = []
	for decision: int in range(recovery_policy_limit):
		var planning: Dictionary = _planning_authority(game)
		if not bool(planning.get("ok", false)):
			return {"result": "planning_error", "won": false, "fatal": true, "error": planning.get("error"), "trace": trace}
		var frontier: Dictionary = Navigation.frontier(planning["game"], 0, false, prepared)
		if not bool(frontier.get("complete", false)):
			return {"result": "unknown_incomplete_frontier", "won": false, "fatal": false, "frontier": frontier, "trace": trace}
		if frontier["options"].is_empty():
			return {"result": "policy_reached_resource_dead_end_not_checkpoint_unsat", "won": false, "fatal": false, "trace": trace, "actual_terminal_core": game.state}
		var options: Array = frontier["options"].duplicate()
		var armor_gate: bool = false
		for blocked: Dictionary in frontier.get("blocked", []):
			armor_gate = armor_gate or (blocked.get("kind", "") == "enemy" and int(blocked.get("combat", {}).get("damage", 0)) < 0)
		var policy_state: Dictionary = game.state
		options.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
			var left: float = _recovery_score(a, policy_state, armor_gate)
			var right: float = _recovery_score(b, policy_state, armor_gate)
			return str(a["id"]) < str(b["id"]) if left == right else left > right)
		var choice: Dictionary = options[0]
		var before: Dictionary = game.state
		var execution: Dictionary = Navigation.execute(game, choice["path"])
		var after: Dictionary = game.state
		var event: String = "buy:" + str(choice["id"]) if choice["kind"] == "buy" else str(choice["id"])
		var error: String = _actual_delta_error(before, after, event, choice["item"], execution)
		if not bool(execution.get("ok", false)) or not error.is_empty():
			return {"result": "actual_policy_action_error", "won": false, "fatal": true, "event": event, "error": error, "execution": execution, "trace": trace}
		trace.append({"event": event, "path": choice["path"].duplicate(true), "before": Recovery.budget(before), "after": Recovery.budget(after), "execution": execution, "full_core_sha256": Variants.content_hash(after)})
		if bool(after["won"]):
			var final: Dictionary = game.campaign_snapshot()
			var bound: bool = Recovery.sequence_equal(initial, final)
			return {"result": "verified_winning_suffix" if bound else "winning_binding_error", "won": bound, "fatal": not bound, "trace": trace, "final_budget": Recovery.budget(after), "final_snapshot": final}
	return {"result": "unknown_resource_policy_budget", "won": false, "fatal": false, "decisions": recovery_policy_limit, "trace": trace, "actual_terminal_core": game.state}


func _planning_authority(game: RefCounted) -> Dictionary:
	return Recovery.planning_game(game) if recovery_planner == "base" else {"ok": true, "game": game}


func _actual_delta_error(before: Dictionary, after: Dictionary, event: String, item: Dictionary, execution: Dictionary) -> String:
	if not bool(execution.get("ok", false)):
		return "The selected ordinary actions were rejected by the actual campaign."
	var expected_ids: Array = before["cleared"].duplicate()
	var expected_stock: Dictionary = before["purchases"].duplicate(true)
	if event.begins_with("buy:"):
		var id: String = event.trim_prefix("buy:")
		expected_stock[id] = int(expected_stock.get(id, 0)) + 1
	elif not ["stairs", "shop"].has(str(item["kind"])):
		expected_ids.append(str(item["id"]))
	if not _same_id_set(expected_ids, after["cleared"]) or not Recovery.same(expected_stock, after["purchases"]):
		return "Actual clear/stock deltas changed an object outside the selected decision."
	if item["kind"] == "stairs" and (not _same_budget(before, after) or int(after["floor"]) != int(floor_indices[int(item["target"]["floor"])]) or not _same_cell(after["pos"], item["target"]["pos"])):
		return "Actual stair changed resources or missed its transformed destination."
	if item["kind"] == "enemy" and int(execution.get("preview_comparisons", 0)) < 1:
		return "An enemy decision lacked an actual preview/deduction comparison."
	return ""


func _recovery_score(option: Dictionary, state: Dictionary, armor_gate: bool) -> float:
	var kind: String = str(option["kind"])
	if kind == "enemy":
		return 10000.0 if bool(option["item"].get("victory", false)) else 30.0 - float(option.get("preview", {}).get("damage", 0)) * 0.05
	if kind == "atk": return 160.0
	if kind == "def": return 150.0
	if kind == "key": return 145.0
	if kind == "gold": return 140.0
	if kind == "potion": return 130.0
	if kind == "door": return 90.0
	if kind == "buy":
		var offer: Dictionary = option["offer"]
		if offer["kind"] == "atk": return 300.0 if armor_gate else 80.0
		if offer["kind"] == "def": return 70.0
		return 110.0 if int(state["hp"]) < 250 else 20.0
	return 0.0


func _same_id_set(a: Array, b: Array) -> bool:
	var left: Array = a.duplicate()
	var right: Array = b.duplicate()
	left.sort()
	right.sort()
	return left == right


func _added_ids(before: Array, after: Array) -> Array:
	var result: Array = []
	for id: String in after:
		if not before.has(id):
			result.append(id)
	return result


func _checkpoint_ids(checkpoints: Array) -> Array:
	var result: Array = []
	for checkpoint: Dictionary in checkpoints:
		result.append(checkpoint["checkpoint_id"])
	return result


func _attempt_summary(attempt: Dictionary) -> Dictionary:
	return {"checkpoint_id": attempt.get("checkpoint_id"), "chapter": attempt.get("chapter"), "result": attempt.get("result", "unknown"), "won": attempt.get("won", false), "fatal": attempt.get("fatal", false), "strategy": attempt.get("strategy"), "attempts": attempt.get("attempts", [])}


func _emit_recovery(value: Dictionary) -> Dictionary:
	var offset: int = recovery_journal.get_position()
	var text: String = JSON.stringify(value) + "\n"
	recovery_journal.store_string(text)
	recovery_journal.flush()
	recovery_line += 1
	return {"path": recovery_output.get_file(), "line": recovery_line, "byte_offset": offset, "byte_length": text.to_utf8_buffer().size(), "line_sha256": text.sha256_text()}


func _finish_recovery() -> void:
	var initial_wins: int = 0
	var verified_nearest: Dictionary = {}
	var completed_indices: Array[int] = []
	var completed_seen: Dictionary = {}
	var identities_unique: bool = true
	var every_result_passed: bool = true
	for result: Dictionary in recovery_results:
		if not Recovery.whole(result.get("index")):
			identities_unique = false
		else:
			var index: int = int(result["index"])
			if completed_seen.has(index) or not recovery_selected_indices.has(index):
				identities_unique = false
			completed_seen[index] = true
			completed_indices.append(index)
		every_result_passed = every_result_passed and bool(result.get("passed", false))
		if bool(result.get("initial_blade_won", false)):
			initial_wins += 1
		var key: String = str(result.get("nearest_verified_winning_checkpoint", "unknown"))
		verified_nearest[key] = int(verified_nearest.get(key, 0)) + 1
	completed_indices.sort()
	var selected_sorted: Array[int] = recovery_selected_indices.duplicate()
	selected_sorted.sort()
	var selected_coverage_complete: bool = identities_unique and Recovery.same(completed_indices, selected_sorted)
	var exact_26_completed: bool = identities_unique and Recovery.same(completed_indices, EXPECTED_LATE_INDICES)
	var complete: bool = bool(recovery_preflight.get("ok", false)) and selected_coverage_complete and every_result_passed and initial_wins == recovery_requested and recovery_results.size() == recovery_requested and recovery_errors.is_empty() and not recovery_stopped
	var footer: Dictionary = {"kind": "late_recovery_footer", "measurement_completed": complete, "requested": recovery_requested, "completed": recovery_results.size(), "offset": recovery_offset, "next_offset": recovery_offset + recovery_results.size(), "stopped_at_case_boundary": recovery_stopped, "all_26_complete": complete and exact_26_completed, "coverage": {"queue_preflight": recovery_preflight, "expected_all_26_indices": EXPECTED_LATE_INDICES.duplicate(), "selected_indices": selected_sorted, "completed_indices": completed_indices, "completed_identities_unique": identities_unique, "selected_set_complete": selected_coverage_complete, "exact_26_set_completed": exact_26_completed, "every_result_passed": every_result_passed}, "initial_checkpoint_actual_blade_wins": initial_wins, "nearest_verified_winning_checkpoints": verified_nearest, "results": recovery_results, "errors": recovery_errors, "source_bindings": recovery_queue.get("source_bindings", {}), "input_sha256": recovery_loaded.get("input_sha256", ""), "test_sha256": FileAccess.get_sha256("res://tests/replay_late_checkpoint_recovery.gd"), "helper_sha256": FileAccess.get_sha256("res://tests/recovery_followup_helpers.gd"), "elapsed_ms": Time.get_ticks_msec() - recovery_started, "scope": "Only actually replayed cases, actual complete checkpoints and actually winning suffixes. Unknown attempts are not unsatisfiable, a verified earlier win does not prove a later checkpoint impossible, and no full-checkpoint/UI/browser/all-policy claim is made."}
	_emit_recovery(footer)
	recovery_journal.close()
	footer["journal_sha256"] = FileAccess.get_sha256(recovery_output)
	var summary: FileAccess = FileAccess.open(recovery_output + ".summary.json", FileAccess.WRITE)
	if summary == null:
		print("Cannot write recovery summary.")
		quit(1)
		return
	summary.store_string(JSON.stringify(footer, "  ") + "\n")
	summary.close()
	print(JSON.stringify({"kind": "late_recovery_finished", "measurement_completed": complete, "completed": recovery_results.size(), "requested": recovery_requested, "initial_blade_wins": initial_wins, "nearest_verified": verified_nearest, "errors": recovery_errors.size(), "elapsed_ms": footer["elapsed_ms"], "journal_sha256": footer["journal_sha256"]}))
	quit(0 if complete or (recovery_stopped and recovery_errors.is_empty()) else 1)
