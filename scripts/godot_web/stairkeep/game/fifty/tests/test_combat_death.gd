extends SceneTree
## A deliberately low-supply ordinary prefix. No forged HP, stats or position.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const SELF: String = "res://fifty/tests/test_combat_death.gd"
var output: String = ""
var stop_file: String = ""
var modes: Array[String] = ["classic_restart", "practice_checkpoint"]
var checks: Array = []
var errors: Array = []
var outcomes: Array = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		elif argument.begins_with("--stop-file="): stop_file = argument.trim_prefix("--stop-file=")
		elif argument.begins_with("--mode="):
			var selected: String = argument.trim_prefix("--mode=")
			if selected not in ["classic_restart", "practice_checkpoint"]:
				quit(2)
				return
			modes = [selected]
		else:
			push_error("Unknown combat-death QA argument: " + argument)
			quit(2)
			return
	if output.is_empty() or FileAccess.file_exists(output):
		push_error("Pass --output=<new JSON>; no existing evidence is overwritten.")
		quit(2)
		return
	var started: int = Time.get_ticks_msec()
	var stopped: bool = false
	for mode: String in modes:
		if not stop_file.is_empty() and FileAccess.file_exists(stop_file):
			stopped = true
			break
		var result: Dictionary = _case(mode)
		outcomes.append(result)
		if not bool(result.get("passed", false)): errors.append({"mode": mode, "error": result.get("error", "Actual combat death was not tested.")})
	var report: Dictionary = {"suite": "fifty_actual_finite_combat_death/v1", "passed": errors.is_empty() and not stopped and outcomes.size() == modes.size(),
		"measurement_completed": not stopped and outcomes.size() == modes.size(), "engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(),
		"test_sha256": FileAccess.get_sha256(SELF), "source_hashes": {"runtime": FileAccess.get_sha256("res://fifty/scripts/runtime.gd"), "content": FileAccess.get_sha256("res://fifty/data/content.json"), "geometry": FileAccess.get_sha256("res://fifty/scripts/d4.gd"), "navigation": FileAccess.get_sha256("res://fifty/tests/qa_navigation.gd")},
		"cases": outcomes, "checks": checks, "errors": errors, "elapsed_ms": Time.get_ticks_msec() - started,
		"scope": "Actual low-supply API movement through required main-path pickups and guards, without optional branches/shops/NPC supplies. When an actually reachable finite lethal enemy is found, ordinary refusal, cancellation, confirmed challenge and mode-specific recovery are checked. Failure to find such a prefix is not-tested, never replaced with give_up or injected HP. This is an intentional strategy loss, not proof of initially unsatisfiable content or a change to the winning routes."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "cases": outcomes.size(), "checks": checks.size(), "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if bool(report["passed"]) or (stopped and errors.is_empty()) else 1)


func _case(mode: String) -> Dictionary:
	var began: int = Time.get_ticks_msec()
	var result: Dictionary = {"mode": mode, "seed": "00000001", "passed": false, "prefix": []}
	var game = Runtime.new()
	var loaded: Dictionary = game.load_content()
	var chosen: Dictionary = game.choose_mode(mode, "00000001") if bool(loaded.get("ok", false)) else loaded
	if not bool(chosen.get("ok", false)):
		result["error"] = {"stage": "initialization", "result": chosen}
		return result
	var initial: Dictionary = game.export_snapshot()
	result["initial_full_snapshot"] = initial
	var prepared: Dictionary = Navigation.prepare(game)
	for floor_id: int in range(1, 11):
		for suffix: String in ["core_potion", "core_atk", "choice_key"]:
			var event: String = "f%02d_%s" % [floor_id, suffix]
			var performed: Dictionary = _event(game, event, prepared)
			result["prefix"].append(performed)
			if not bool(performed.get("ok", false)):
				result["error"] = {"stage": "low-supply prefix", "details": performed}
				return result
		var enemy_id: String = "f%02d_guard" % floor_id
		var plan: Dictionary = Navigation.plan(game, enemy_id, prepared)
		if not bool(plan.get("ok", false)):
			result["error"] = {"stage": "guard approach", "details": plan}
			return result
		var actions: Array = plan["path"].slice(0, int(plan["approach_size"]))
		var approach: Dictionary = Navigation.execute(game, actions)
		result["prefix"].append({"event": "approach:" + enemy_id, "actions": actions, "execution": approach, "after_full_snapshot_sha256": Geometry.content_hash(game.export_snapshot()), "actual_world": Navigation.world(game.export_snapshot())})
		if not bool(approach.get("ok", false)):
			result["error"] = {"stage": "actual guard approach", "details": approach}
			return result
		var cell: Array = plan["item"]["pos"]
		var preview: Dictionary = game.inspect(cell).get("combat", {})
		if not bool(preview.get("win", false)):
			if int(preview.get("damage", -1)) <= 0 or int(preview["damage"]) < int(game.state["hp"]):
				result["error"] = {"status": "not_tested_no_finite_lethal_prefix", "enemy": enemy_id, "preview": preview, "full_state": game.export_snapshot()}
				return result
			result["finite_lethal_floor"] = floor_id
			result["enemy_id"] = enemy_id
			result["actual_preview"] = preview
			return _death_and_recovery(game, initial, cell, preview, result, began)
		var fought: Dictionary = Navigation.execute(game, [plan["path"][-1]])
		result["prefix"].append({"event": enemy_id, "actions": [plan["path"][-1]], "execution": fought, "actual_world": Navigation.world(game.export_snapshot()), "after_full_snapshot_sha256": Geometry.content_hash(game.export_snapshot())})
		if not bool(fought.get("ok", false)):
			result["error"] = {"stage": "actual penetrable guard", "details": fought}
			return result
		if floor_id < 10:
			var climbed: Dictionary = _event(game, "f%02d_up" % floor_id, prepared)
			result["prefix"].append(climbed)
			if not bool(climbed.get("ok", false)):
				result["error"] = {"stage": "actual stair", "details": climbed}
				return result
	result["error"] = {"status": "not_tested_no_finite_lethal_prefix", "reason": "All ten main-path guards were survivable; no death claim is made."}
	return result


func _death_and_recovery(game: RefCounted, initial: Dictionary, cell: Array, preview: Dictionary, result: Dictionary, began: int) -> Dictionary:
	var start_errors: int = errors.size()
	var mode: String = str(result["mode"])
	var before: Dictionary = game.export_snapshot()
	var pos: Array = game.state["pos"]
	var refused: Dictionary = game.move(int(cell[0]) - int(pos[0]), int(cell[1]) - int(pos[1]))
	_check(mode + ": ordinary lethal move rejects with no deduction/history mutation", not bool(refused.get("ok", true)) and Navigation.same(before, game.export_snapshot()), {"actual": refused, "preview": preview})
	var canceled: Dictionary = game.unsafe_challenge(cell, false)
	_check(mode + ": unconfirmed lethal challenge leaves full state unchanged", not bool(canceled.get("ok", true)) and Navigation.same(before, game.export_snapshot()), canceled)
	var confirmed: Dictionary = game.unsafe_challenge(cell, true)
	var failed: Dictionary = game.export_snapshot()
	var terminal_hp: int = int(before["core_state"]["hp"]) - int(preview["damage"])
	_check(mode + ": confirmed real combat death uses identical authoritative preview", bool(confirmed.get("ok", false)) and bool(failed["failed"]) and failed["failure"]["kind"] == "combat_death" and int(failed["failure"]["terminal_hp"]) == terminal_hp and terminal_hp <= 0 and Navigation.same(failed["failure"]["combat"], preview) and Navigation.same(before["core_state"], failed["core_state"]), {"result": confirmed, "terminal_hp": terminal_hp, "scope": "The failure metadata records lethal HP; the frozen Base core retains its valid positive checkpoint HP, as the runtime contract specifies."})
	var loss_id: String = str(failed["failure"].get("failure_id", ""))
	var wrong: Dictionary = game.restart_classic("00000002", true, "stale") if mode == "classic_restart" else game.restore_checkpoint(str(initial["checkpoints"][0]["id"]), true, "stale")
	_check(mode + ": stale loss identity cannot recover or mutate", not bool(wrong.get("ok", true)) and Navigation.same(failed, game.export_snapshot()), wrong)
	var recovery: Dictionary
	if mode == "classic_restart":
		var canceled_restart: Dictionary = game.restart_classic("00000002", false, loss_id)
		_check("combat death classic new run requires explicit confirmation", not bool(canceled_restart.get("ok", true)) and Navigation.same(failed, game.export_snapshot()))
		recovery = game.restart_classic("00000002", true, loss_id)
		var after: Dictionary = game.export_snapshot()
		var expected: Dictionary = game.data["initial_player"]
		var clean_world: bool = int(after["core_state"]["floor"]) == 0 and Navigation.same(after["core_state"]["pos"], game.data["floors"][0]["spawn"]) and after["checkpoints"].size() == 1 and not bool(after["campaign_complete"]) and not bool(after["core_state"]["won"])
		_check("combat death classic resets complete world once with new seed", clean_world and bool(recovery.get("ok", false)) and after["seed"] != failed["seed"] and int(after["attempt_index"]) == int(failed["attempt_index"]) + 1 and Navigation.same(Navigation.budget(after["core_state"]), Navigation.budget({"hp": expected["hp"], "atk": expected["atk"], "def": expected["def"], "gold": expected.get("gold", 0), "keys": expected["keys"]})) and after["core_state"]["cleared"].is_empty() and after["core_state"]["purchases"].is_empty() and Navigation.same(after["flags"], game.data["flags"]) and after["completed_events"].is_empty() and not bool(after["failed"]) and not bool(after["slice_complete"]) and after["consumed_loss_ids"].has(loss_id), after)
	else:
		var checkpoint: Dictionary = initial["checkpoints"][0]
		var canceled_restore: Dictionary = game.restore_checkpoint(str(checkpoint["id"]), false, loss_id)
		_check("combat death practice requires explicit complete restore", not bool(canceled_restore.get("ok", true)) and Navigation.same(failed, game.export_snapshot()))
		recovery = game.restore_checkpoint(str(checkpoint["id"]), true, loss_id)
		var after: Dictionary = game.export_snapshot()
		_check("combat death practice restores entire actual checkpoint with same seed D4", bool(recovery.get("ok", false)) and Navigation.same(Navigation.world(after), checkpoint["world"]) and after["seed"] == failed["seed"] and after["floor_transforms"] == failed["floor_transforms"] and int(after["attempt_index"]) == int(failed["attempt_index"]) and after["failure_history"] == failed["failure_history"] and after["consumed_loss_ids"].has(loss_id) and int(after["recovery_count"]) == int(failed["recovery_count"]) + 1 and after["checkpoints"].size() == 1, after)
	var recovered: Dictionary = game.export_snapshot()
	var duplicate: Dictionary = game.restart_classic("00000003", true, loss_id) if mode == "classic_restart" else game.restore_checkpoint(str(initial["checkpoints"][0]["id"]), true, loss_id)
	_check(mode + ": consumed combat loss cannot recover a second time", not bool(duplicate.get("ok", true)) and Navigation.same(recovered, game.export_snapshot()), duplicate)
	var validated: Dictionary = game.validate_snapshot(recovered)
	_check(mode + ": complete authoritative journal reproduces combat death and recovery", bool(validated.get("ok", false)) and Navigation.same(recovered, game.export_snapshot()), {"status": validated.get("status", "")})
	result.merge({"passed": errors.size() == start_errors, "pre_death_full_snapshot": before, "failed_full_snapshot": failed, "recovered_full_snapshot": recovered, "recovery_result": recovery, "authoritative_replay_status": validated.get("status", ""), "elapsed_ms": Time.get_ticks_msec() - began}, true)
	return result


func _event(game: RefCounted, id: String, prepared: Dictionary) -> Dictionary:
	var before: Dictionary = game.export_snapshot()
	var plan: Dictionary = Navigation.plan(game, id, prepared)
	if not bool(plan.get("ok", false)): return {"ok": false, "event": id, "planning": plan, "full_state": before}
	var execution: Dictionary = Navigation.execute(game, plan["path"])
	return {"ok": execution.get("ok", false), "event": id, "actions": plan["path"], "execution": execution, "before_full_snapshot_sha256": Geometry.content_hash(before), "after_full_snapshot_sha256": Geometry.content_hash(game.export_snapshot()), "actual_world": Navigation.world(game.export_snapshot())}


func _check(name: String, passed: bool, observed: Variant = null) -> void:
	checks.append({"name": name, "passed": passed, "observed": observed})
	if not passed: errors.append({"name": name, "observed": observed})
