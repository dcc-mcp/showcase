extends SceneTree
## Positive registered enter-event adapter test on a detached canonical fixture.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const DATA: String = "res://fifty/data/content.json"
const SELF: String = "res://fifty/tests/test_direction_event.gd"
var output: String = ""
var stop_file: String = ""
var checks: Array = []
var errors: Array = []
var cases: Array = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		elif argument.begins_with("--stop-file="): stop_file = argument.trim_prefix("--stop-file=")
		else:
			push_error("Unknown directional event QA argument: " + argument)
			quit(2)
			return
	if output.is_empty() or FileAccess.file_exists(output):
		quit(2)
		return
	var json: JSON = JSON.new()
	if json.parse(FileAccess.get_file_as_string(DATA)) != OK or not (json.data is Dictionary):
		quit(2)
		return
	var fixture: Dictionary = json.data.duplicate(true)
	fixture["flags"]["qa_enter_seen"] = false
	fixture["events"]["qa_direction_enter"] = {"floor": 1, "trigger": {"kind": "enter", "cells": [[7, 13]], "direction": [0, 1]}, "conditions": [], "effects": [{"kind": "grant", "stat": "gold", "amount": 1}, {"kind": "set_flag", "flag": "qa_enter_seen", "value": true}], "once": true, "text": "QA registered enter direction fixture."}
	var began: int = Time.get_ticks_msec()
	var stopped: bool = false
	for seed: String in ["00000001", "00000002"]:
		if not stop_file.is_empty() and FileAccess.file_exists(stop_file):
			stopped = true
			break
		var game = Runtime.new()
		var loaded: Dictionary = game.set_content(fixture)
		var started: Dictionary = game.choose_mode("practice_checkpoint", seed) if bool(loaded.get("ok", false)) else loaded
		_check(seed + " positive enter fixture is registered without NPC attachment", bool(started.get("ok", false)), started)
		if not bool(started.get("ok", false)): continue
		var initial: Dictionary = game.export_snapshot()
		var code: int = int(initial["floor_transforms"]["1"])
		_check(seed + " spawn placement does not trigger an enter effect", not bool(initial["flags"]["qa_enter_seen"]) and int(initial["core_state"]["gold"]) == int(fixture["initial_player"].get("gold", 0)) and not initial["completed_events"].has("qa_direction_enter"))
		var commands: Array = []
		for delta: Array in [[-1, 0], [1, 0]]:
			var vector: Array = Geometry.transform_vector(delta, code)
			commands.append({"kind": "move", "dx": int(vector[0]), "dy": int(vector[1])})
		var wrong: Dictionary = Navigation.execute(game, commands)
		var after_wrong: Dictionary = game.export_snapshot()
		_check(seed + " wrong transformed approach does not bypass direction", bool(wrong.get("ok", false)) and not bool(after_wrong["flags"]["qa_enter_seen"]) and int(after_wrong["core_state"]["gold"]) == int(initial["core_state"]["gold"]), wrong)
		var correct: Array = []
		for delta: Array in [[0, -1], [0, 1]]:
			var vector: Array = Geometry.transform_vector(delta, code)
			correct.append({"kind": "move", "dx": int(vector[0]), "dy": int(vector[1])})
		var entered: Dictionary = Navigation.execute(game, correct)
		var after_right: Dictionary = game.export_snapshot()
		_check(seed + " correct transformed approach grants exactly once", bool(entered.get("ok", false)) and bool(after_right["flags"]["qa_enter_seen"]) and int(after_right["core_state"]["gold"]) == int(initial["core_state"]["gold"]) + 1 and after_right["completed_events"].has("qa_direction_enter"), entered)
		var repeated: Dictionary = Navigation.execute(game, correct)
		var final: Dictionary = game.export_snapshot()
		_check(seed + " repeated correct approach has no second grant", bool(repeated.get("ok", false)) and Navigation.same(Navigation.economy(after_right), Navigation.economy(final)), repeated)
		var validated: Dictionary = game.validate_snapshot(final)
		_check(seed + " authoritative replay includes direction event and once state", bool(validated.get("ok", false)), {"status": validated.get("status", "")})
		commands.append_array(correct)
		commands.append_array(correct)
		cases.append({"seed": seed, "actual_floor1_d4_code": code, "initial_full_snapshot": initial, "actual_actions": commands, "wrong_approach_world": Navigation.world(after_wrong), "correct_approach_world": Navigation.world(after_right), "full_final_snapshot": final})
	var report: Dictionary = {"suite": "fifty_positive_direction_enter_adapter/v1", "passed": errors.is_empty() and not stopped and cases.size() == 2, "measurement_completed": not stopped and cases.size() == 2,
		"engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(), "test_sha256": FileAccess.get_sha256(SELF), "rules_sha256": Runtime.rules_fingerprint(), "production_content_sha256": FileAccess.get_sha256(DATA), "detached_fixture_sha256": Geometry.content_hash(fixture),
		"cases": cases, "checks": checks, "errors": errors, "elapsed_ms": Time.get_ticks_msec() - began,
		"scope": "Two actual API runs of one valid standalone enter event added only to a detached QA canonical copy. Spawn does not trigger, wrong approach does not trigger, correct transformed approach grants one gold through the event API once, and full journal replay validates it. This is positive adapter integration, not authored production event/balance coverage or all-eight-D4 runtime direction coverage; the separate independent geometry golden covers all eight transforms."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "cases": cases.size(), "checks": checks.size(), "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if errors.is_empty() else 1)


func _check(name: String, passed: bool, observed: Variant = null) -> void:
	checks.append({"name": name, "passed": passed, "observed": observed})
	if not passed: errors.append({"name": name, "observed": observed})
