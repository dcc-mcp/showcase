extends SceneTree
## Real bad purchases/doors are played from F1; no synthetic budget or teleport.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Fixture = preload("res://fifty/tests/chapter2_fixture.gd")
const KeyCut = preload("res://fifty/tests/chapter2_key_cut.gd")
const DATA: String = "res://fifty/data/chapter2-content.json"
const BUDGET: String = "res://fifty/data/chapter2-budget.json"
const SELF: String = "res://fifty/tests/chapter2_choices.gd"
var output: String = ""
var expected_content_sha256: String = ""
var expected_budget_sha256: String = ""
var winning_report: String = ""
var winning_sha256: String = ""
var winning_case: int = 0
var selected_scenario: String = ""
var stop_file: String = ""
var max_nodes: int = 100000
var checks: Array = []
var errors: Array = []
var outcomes: Array = []
var stopped: bool = false


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not _arguments():
		quit(2)
		return
	var began: int = Time.get_ticks_msec()
	var witness: Dictionary = Fixture.read_case(winning_report, winning_sha256, winning_case)
	if not bool(witness.get("ok", false)):
		push_error(JSON.stringify(witness))
		quit(2)
		return
	var design: Variant = JSON.parse_string(FileAccess.get_file_as_string(BUDGET))
	if not (design is Dictionary) or not (design.get("recovery_scenarios") is Array):
		quit(2)
		return
	var selected: Array = []
	for scenario: Dictionary in design["recovery_scenarios"]:
		if selected_scenario.is_empty() or str(scenario["id"]) == selected_scenario: selected.append(scenario)
	if selected.is_empty() or selected.size() > 2:
		quit(2)
		return
	for scenario: Dictionary in selected:
		if not stop_file.is_empty() and FileAccess.file_exists(stop_file):
			stopped = true
			break
		outcomes.append(_case(scenario, witness))
		if not errors.is_empty(): break
	var report: Dictionary = {"suite": "fifty_chapter2_real_key_choice_counterexamples/v1", "passed": errors.is_empty() and not stopped and outcomes.size() == selected.size(), "measurement_completed": not stopped and outcomes.size() == selected.size(), "engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(), "content_sha256": expected_content_sha256, "budget_sha256": expected_budget_sha256, "winning_fixture_report_sha256": winning_sha256, "winning_fixture_case": winning_case, "source_hashes": _sources(), "checks": checks, "errors": errors, "cases": outcomes, "stopped_at_case_boundary": stopped, "elapsed_ms": Time.get_ticks_msec() - began,
		"scope": "Each counterexample starts from a new authoritative run and executes the complete authored prefix and bad branch by real move/interact/stairs/buy APIs. A separate exact-head real winning report proves this seed's initial world can win. A complete cross-floor key-cut relaxation can prove only that the later zero-yellow-key world cannot reach its slice goal through ordinary play. Exhausted budgets or an incomplete strategy are unknown, never initial unsatisfiability. Recovery uses an explicit abandoned failure and a complete real checkpoint, then an actual winning suffix; no resource injection or difficulty change."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "cases": outcomes.size(), "checks": checks.size(), "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if bool(report["passed"]) or (stopped and errors.is_empty()) else 1)


func _arguments() -> bool:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		elif argument.begins_with("--content-sha256="): expected_content_sha256 = argument.trim_prefix("--content-sha256=")
		elif argument.begins_with("--budget-sha256="): expected_budget_sha256 = argument.trim_prefix("--budget-sha256=")
		elif argument.begins_with("--winning-report="): winning_report = argument.trim_prefix("--winning-report=")
		elif argument.begins_with("--winning-report-sha256="): winning_sha256 = argument.trim_prefix("--winning-report-sha256=")
		elif argument.begins_with("--winning-case=") and argument.trim_prefix("--winning-case=").is_valid_int(): winning_case = int(argument.trim_prefix("--winning-case="))
		elif argument.begins_with("--scenario="): selected_scenario = argument.trim_prefix("--scenario=")
		elif argument.begins_with("--stop-file="): stop_file = argument.trim_prefix("--stop-file=")
		elif argument.begins_with("--max-proof-nodes=") and argument.trim_prefix("--max-proof-nodes=").is_valid_int(): max_nodes = int(argument.trim_prefix("--max-proof-nodes="))
		else: return false
	return not output.is_empty() and output.is_absolute_path() and not FileAccess.file_exists(output) and expected_content_sha256.length() == 64 and expected_budget_sha256.length() == 64 and FileAccess.get_sha256(DATA) == expected_content_sha256 and FileAccess.get_sha256(BUDGET) == expected_budget_sha256 and not winning_report.is_empty() and winning_sha256.length() == 64 and winning_case >= 0 and max_nodes >= 1 and max_nodes <= 100000


func _case(scenario: Dictionary, witness: Dictionary) -> Dictionary:
	var result: Dictionary = {"id": scenario["id"], "passed": false, "classification": "unknown", "initial_winning_witness": {"report_sha256": winning_sha256, "case": winning_case, "seed": witness["case"]["seed"], "route": witness["case"]["route"], "authoritative_full_action_replay": witness["case"]["authoritative_full_action_replay"]}}
	var name: String = str(scenario["id"])
	var route: Dictionary = witness["route"]
	if not _check(name + ": actual winning witness binds same seed and recovery route", str(witness["case"]["seed"]) == str(scenario["requested_seed"]) and str(witness["case"]["route"]) == str(scenario["recovery_route"])): return result
	var prefix: Array = scenario["prefix_events"]
	if not _check(name + ": prefix and suffix refer to the exact authored route", Navigation.same(prefix, route["events"].slice(0, prefix.size())) and Navigation.same(scenario["recovery_suffix_events"], route["events"].slice(prefix.size()))): return result
	var game = Runtime.new()
	var loaded: Dictionary = game.load_content(DATA)
	var started: Dictionary = game.choose_mode("practice_checkpoint", str(scenario["requested_seed"])) if bool(loaded.get("ok", false)) else loaded
	if not _check(name + ": actual initial runtime starts explicitly", bool(started.get("ok", false)), started): return result
	result["initial_full_snapshot"] = game.export_snapshot()
	var prefix_result: Dictionary = _events(game, prefix, route["ledger"].slice(0, prefix.size()))
	result["prefix_actual_trace"] = prefix_result
	if not _check(name + ": full F1-to-checkpoint prefix executes without setters", bool(prefix_result.get("ok", false)), {"error": prefix_result.get("error", "")}): return result
	var entered: Dictionary = game.export_snapshot()
	var checkpoint: Dictionary = Fixture.checkpoint(entered, str(scenario["checkpoint_id"]))
	if not _check(name + ": real captured checkpoint matches canonical resource flag stock world", not checkpoint.is_empty() and Navigation.same(Navigation.economy(checkpoint.get("world", {})), Navigation.economy(scenario["canonical_checkpoint_world"]))): return result
	var bad_result: Dictionary = _events(game, scenario["bad_suffix_events"], scenario["bad_ledger"])
	result["bad_branch_actual_trace"] = bad_result
	if not _check(name + ": actual bad branch reaches the exact planned resource world", bool(bad_result.get("ok", false)) and Navigation.same(Navigation.economy(game.export_snapshot()), Navigation.economy(scenario["canonical_bad_world"])), {"error": bad_result.get("error", "")}): return result
	result["full_bad_branch_snapshot"] = game.export_snapshot()
	var planned: Dictionary = Navigation.plan(game, str(scenario["failed_interaction"]["object_id"]), Navigation.prepare(game))
	if not _check(name + ": locked gate is actually approachable", bool(planned.get("ok", false)), planned): return result
	var approach: Dictionary = Navigation.execute(game, planned["path"].slice(0, int(planned["approach_size"])))
	if not _check(name + ": locked-gate approach uses actual neutral steps", bool(approach.get("ok", false)), approach): return result
	var gate_before: Dictionary = game.export_snapshot()
	var last: Dictionary = planned["path"][-1]
	if not _check(name + ": failed gate action is an ordinary movement", last.get("kind", "") == "move"): return result
	var blocked: Dictionary = game.move(int(last["dx"]), int(last["dy"]))
	if not _check(name + ": no yellow key means real gate refusal without full-state change", not bool(blocked.get("ok", true)) and str(blocked.get("action", blocked.get("status", ""))) == str(scenario["failed_interaction"]["expected_action"]) and Navigation.same(gate_before, game.export_snapshot()), blocked): return result
	var proof: Dictionary = KeyCut.prove(game, max_nodes)
	result["full_terminal_state"] = game.export_snapshot()
	result["ordinary_play_key_cut_proof"] = proof
	result["classification"] = proof.get("status", "unknown")
	if not _check(name + ": complete independent relaxed key cut certifies only this later ordinary world", proof.get("status", "unknown") == "known_key_cut" and bool(proof.get("complete", false)), {"classification": proof.get("status", "unknown"), "reason": proof.get("reason", ""), "visited_work": proof.get("visited_work", 0)}): return result
	var abandoned: Dictionary = game.give_up(true)
	var failed: Dictionary = game.export_snapshot()
	if not _check(name + ": recovery failure is explicit abandonment not invented solver death", bool(abandoned.get("ok", false)) and failed["failure"].get("kind", "") == "abandoned", abandoned): return result
	var restored_result: Dictionary = game.restore_checkpoint(str(scenario["checkpoint_id"]), true, str(failed["failure"]["failure_id"]))
	var restored: Dictionary = game.export_snapshot()
	if not _check(name + ": complete checkpoint restores consumed keys and rejects all later gains", bool(restored_result.get("ok", false)) and Navigation.same(Navigation.world(restored), checkpoint["world"]) and Navigation.same(restored["checkpoints"], Fixture.checkpoint_prefix(entered, str(scenario["checkpoint_id"]))) and Navigation.same(restored["seed"], entered["seed"]) and Navigation.same(restored["floor_transforms"], entered["floor_transforms"]), restored_result): return result
	result["full_restored_snapshot"] = restored
	var suffix: Dictionary = _events(game, scenario["recovery_suffix_events"], route["ledger"].slice(prefix.size()))
	result["recovery_actual_trace"] = suffix
	var final: Dictionary = game.export_snapshot()
	var checked: Dictionary = game.validate_snapshot(final)
	var expected: Dictionary = scenario["expected_recovered_final"]
	var expected_budget: Dictionary = {"hp": expected["hp"], "atk": expected["atk"], "def": expected["def"], "gold": expected["gold"], "keys": expected["keys"]}
	var recovered: bool = bool(suffix.get("ok", false)) and Navigation.same(Navigation.budget(final["core_state"]), expected_budget) and Navigation.same(Navigation.economy(final), Navigation.economy(witness["case"]["full_final_snapshot"])) and bool(final["slice_complete"]) and not bool(final["campaign_complete"]) and not bool(final["core_state"]["won"]) and bool(checked.get("ok", false))
	_check(name + ": actual restored suffix reaches the exact authored F20 budget", recovered, {"replay": checked, "error": suffix.get("error", "")})
	result["full_final_snapshot"] = final
	result["authoritative_full_action_replay"] = checked
	result["passed"] = recovered
	return result


func _events(game: RefCounted, events: Array, ledger: Array) -> Dictionary:
	if events.size() != ledger.size(): return {"ok": false, "error": "Event and exact ledger sizes differ."}
	var prepared: Dictionary = Navigation.prepare(game)
	var trace: Array = []
	var comparisons: int = 0
	for index: int in range(events.size()):
		var before: Dictionary = game.export_snapshot()
		if not Navigation.same(Navigation.budget(before["core_state"]), ledger[index]["before"]): return {"ok": false, "error": "Before budget differs.", "event": events[index], "full_state": before, "trace": trace}
		var planned: Dictionary = Navigation.plan(game, str(events[index]), prepared)
		if not bool(planned.get("ok", false)): return {"ok": false, "classification": "unknown_navigation", "event": events[index], "details": planned, "trace": trace}
		var executed: Dictionary = Navigation.execute(game, planned["path"])
		if not bool(executed.get("ok", false)): return {"ok": false, "error": "Actual API rejected event.", "event": events[index], "details": executed, "trace": trace}
		comparisons += int(executed.get("preview_comparisons", 0))
		var after: Dictionary = game.export_snapshot()
		var mismatch: Array[String] = Fixture.ledger_error(after, ledger[index])
		var selected_event: String = str(executed["results"][-1].get("event_id", ""))
		if ledger[index].has("selected_event_id") and str(ledger[index]["selected_event_id"]) != selected_event: mismatch.append("selected_event_id")
		trace.append({"event": events[index], "actions": planned["path"], "before_full_snapshot_sha256": Geometry.content_hash(before), "after_full_snapshot_sha256": Geometry.content_hash(after), "actual_world": Navigation.world(after), "selected_event_id": selected_event})
		if not mismatch.is_empty(): return {"ok": false, "error": "Actual ledger differs.", "fields": mismatch, "trace": trace}
	return {"ok": true, "events": trace.size(), "preview_actual_comparisons": comparisons, "trace": trace}


func _check(name: String, passed: bool, details: Dictionary = {}) -> bool:
	checks.append({"name": name, "passed": passed, "details": details})
	if not passed: errors.append({"name": name, "details": details})
	return passed


func _sources() -> Dictionary:
	var result: Dictionary = {}
	for source: String in [SELF, DATA, BUDGET, "res://scripts/rules.gd", "res://fifty/scripts/runtime.gd", "res://fifty/scripts/content.gd", "res://fifty/scripts/d4.gd", "res://fifty/tests/qa_navigation.gd", "res://fifty/tests/chapter2_fixture.gd", "res://fifty/tests/chapter2_key_cut.gd"]:
		result[source] = FileAccess.get_sha256(source)
	return result
