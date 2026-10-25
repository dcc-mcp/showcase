extends SceneTree
## Small authoritative runtime/mode/combat/save smoke before route batches.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Save = preload("res://fifty/scripts/save.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const SELF: String = "res://fifty/tests/test_runtime_smoke.gd"
var output: String = ""
var checks: Array = []
var errors: Array = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		elif argument.begins_with("--stop-file="):
			if FileAccess.file_exists(argument.trim_prefix("--stop-file=")):
				push_error("Smoke stopped before its single case.")
				quit(2)
				return
		else:
			push_error("Unknown runtime smoke argument: " + argument)
			quit(2)
			return
	if output.is_empty() or FileAccess.file_exists(output):
		push_error("Pass --output=<absolute new JSON>; existing evidence is preserved.")
		quit(2)
		return
	var began: int = Time.get_ticks_msec()
	var game = Runtime.new()
	var loaded: Dictionary = game.load_content()
	_check("canonical authored slice loads", bool(loaded.get("ok", false)), loaded)
	if bool(loaded.get("ok", false)):
		_exercise(game)
	var report: Dictionary = {"suite": "fifty_runtime_initial_smoke/v1", "passed": errors.is_empty(), "engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(),
		"test_sha256": FileAccess.get_sha256(SELF), "rules_sha256": Runtime.rules_fingerprint(), "content_sha256": FileAccess.get_sha256("res://fifty/data/content.json"),
		"source_hashes": {"runtime": FileAccess.get_sha256("res://fifty/scripts/runtime.gd"), "d4": FileAccess.get_sha256("res://fifty/scripts/d4.gd"), "save": FileAccess.get_sha256("res://fifty/scripts/save.gd"), "navigation": FileAccess.get_sha256("res://fifty/tests/qa_navigation.gd")},
		"checks": checks, "errors": errors, "elapsed_ms": Time.get_ticks_msec() - began,
		"scope": "Actual initial runtime modes, four independent hand-calculated combat boundaries, legal deliberate abandonment/recovery, and one full native slot roundtrip. No resource setters or teleports. No complete route, live UI, browser persistence or 50-floor victory claim."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		push_error("Cannot create new smoke JSON.")
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "checks": checks.size(), "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if errors.is_empty() else 1)


func _exercise(game: RefCounted) -> void:
	var initial_unselected: Dictionary = game.export_snapshot()
	_check("mode starts explicitly unselected", initial_unselected["mode"] == "unselected")
	_content_rejections(game, initial_unselected)
	for command: String in ["move", "stairs", "buy", "give_up", "restore", "restart"]:
		var result: Dictionary
		match command:
			"move": result = game.move(0, 1)
			"stairs": result = game.use_stairs()
			"buy": result = game.buy("edge")
			"give_up": result = game.give_up(true)
			"restore": result = game.restore_checkpoint("entry_01", true)
			_: result = game.restart_classic("00000002", true)
		_check("unselected rejects " + command + " without mutation", not bool(result.get("ok", true)) and Navigation.same(initial_unselected, game.export_snapshot()), result)
	var invalid_mode: Dictionary = game.choose_mode("automatic", "00000001")
	_check("no invented default mode", not bool(invalid_mode.get("ok", true)) and Navigation.same(initial_unselected, game.export_snapshot()))
	var started: Dictionary = game.choose_mode("classic_restart", "00000001")
	_check("explicit classic choice starts actual run", bool(started.get("ok", false)), started)
	if not bool(started.get("ok", false)): return
	var initial: Dictionary = game.export_snapshot()
	_check("ten authored floors are distinct from fifty target", game.data["floors"].size() == 10 and game.data["manifest"]["target_floors"] == 50 and game.data["manifest"]["not_authored_floors"].size() == 40 and not bool(initial["campaign_complete"]) and not bool(initial["core_state"]["won"]))
	var rejected: Dictionary = game.choose_mode("practice_checkpoint", "00000002")
	_check("mode cannot silently switch an active run", not bool(rejected.get("ok", true)) and Navigation.same(initial, game.export_snapshot()))
	var hp: int = int(game.state["hp"])
	var attack: int = int(game.state["atk"])
	var defense: int = int(game.state["def"])
	var cases: Array = [
		{"name": "ATK equals enemy DEF cannot penetrate", "enemy": {"hp": 1, "atk": defense, "def": attack}, "win": false, "damage": -1},
		{"name": "HP exactly equals two-hit damage is not survivable", "enemy": {"hp": attack + 1, "atk": defense + hp, "def": 0}, "win": false, "damage": hp, "rounds": 2},
		{"name": "first-hit kill prevents even lethal retaliation", "enemy": {"hp": attack, "atk": defense + hp * 2, "def": 0}, "win": true, "damage": 0, "rounds": 1},
		{"name": "zero retaliation over three hits costs no HP", "enemy": {"hp": attack * 2 + 1, "atk": defense, "def": 0}, "win": true, "damage": 0, "rounds": 3},
	]
	for item: Dictionary in cases:
		var actual: Dictionary = game.combat(item["enemy"])
		_check(str(item["name"]), bool(actual["win"]) == bool(item["win"]) and int(actual["damage"]) == int(item["damage"]) and (not item.has("rounds") or int(actual["rounds"]) == int(item["rounds"])) and Navigation.same(initial, game.export_snapshot()), {"actual": actual, "independent_expected": item})
	var classic_slot: String = "qa50c-" + str(OS.get_process_id())
	var classic_path: String = Save.slot_path(classic_slot, "classic_restart")
	if FileAccess.file_exists(classic_path):
		_check("classic QA pre-failure slot must be new", false, classic_path)
		return
	var classic_saved: Dictionary = Save.write_slot(game, classic_slot)
	_check("classic legal pre-failure native slot exists", bool(classic_saved.get("ok", false)), classic_saved)
	if not bool(classic_saved.get("ok", false)): return
	var classic_slot_sha256: String = FileAccess.get_sha256(classic_path)
	var unconfirmed: Dictionary = game.give_up(false)
	_check("abandonment requires explicit confirmation", not bool(unconfirmed.get("ok", true)) and Navigation.same(initial, game.export_snapshot()))
	var abandoned: Dictionary = game.give_up(true)
	var failed: Dictionary = game.export_snapshot()
	_check("voluntary abandonment is recorded separately from unsat", bool(abandoned.get("ok", false)) and bool(failed["failed"]) and failed["failure"]["kind"] == "abandoned" and Navigation.same(initial["core_state"], failed["core_state"]))
	var legal_before_failure: Dictionary = game.validate_snapshot(initial)
	_check("pre-failure snapshot legality is independent of failed-instance import permission", bool(legal_before_failure.get("ok", false)) and Navigation.same(failed, game.export_snapshot()), {"status": legal_before_failure.get("status", "")})
	var denied_import: Dictionary = game.import_snapshot(initial)
	_check("failed current classic instance rejects valid pre-failure import", not bool(denied_import.get("ok", true)) and denied_import.get("status", "") == "death_requires_restart" and Navigation.same(failed, game.export_snapshot()) and FileAccess.get_sha256(classic_path) == classic_slot_sha256, denied_import)
	var denied_load: Dictionary = Save.load_slot(game, classic_slot)
	_check("failed current classic native load leaves runtime and original slot unchanged", not bool(denied_load.get("ok", true)) and Navigation.same(failed, game.export_snapshot()) and FileAccess.get_sha256(classic_path) == classic_slot_sha256, {"result": denied_load, "native_slot": classic_path, "unchanged_sha256": classic_slot_sha256})
	var resumed = Runtime.new()
	resumed.load_content()
	resumed.choose_mode("classic_restart", "00000002")
	var manual_resume: Dictionary = Save.load_slot(resumed, classic_slot)
	_check("fresh explicitly selected classic instance may manually resume valid slot", bool(manual_resume.get("ok", false)) and Navigation.same(initial, resumed.export_snapshot()) and FileAccess.get_sha256(classic_path) == classic_slot_sha256, {"result": manual_resume, "scope": "Fresh runtime instance in this native process; no persistent tombstone, process restart or permadeath claim."})
	var wrong_loss: Dictionary = game.restart_classic("00000002", true, "stale")
	_check("classic rejects stale failure identity unchanged", not bool(wrong_loss.get("ok", true)) and Navigation.same(failed, game.export_snapshot()))
	var restarted: Dictionary = game.restart_classic("00000002", true, str(failed["failure"]["failure_id"]))
	var reset: Dictionary = game.export_snapshot()
	var history_kept: bool = reset["actions"].size() == failed["actions"].size() + 1 and Navigation.same(reset["actions"].slice(0, failed["actions"].size()), failed["actions"]) and reset["actions"][-1].get("kind", "") == "restart_classic" and reset["failure_history"] == failed["failure_history"] and reset["consumed_loss_ids"].has(failed["failure"]["failure_id"])
	_check("classic explicit new seed resets complete world and retains session audit", bool(restarted.get("ok", false)) and reset["seed"] != initial["seed"] and int(reset["attempt_index"]) == 1 and Navigation.same(reset["core_state"], _fresh_world("classic_restart", "00000002")["core_state"]) and reset["flags"] == game.data["flags"] and reset["completed_events"].is_empty() and history_kept and not bool(reset["failed"]), reset)
	var classic_checked: Dictionary = game.validate_snapshot(reset)
	_check("authoritative replay validates complete classic restart lineage", bool(classic_checked.get("ok", false)), {"status": classic_checked.get("status", "")})
	var practice = Runtime.new()
	practice.load_content()
	var selected: Dictionary = practice.choose_mode("practice_checkpoint", "00000001")
	_check("practice is separately and explicitly selected", bool(selected.get("ok", false)))
	if not bool(selected.get("ok", false)): return
	var practice_initial: Dictionary = practice.export_snapshot()
	var checkpoint: Dictionary = practice_initial["checkpoints"][0]
	var bad_restore: Dictionary = practice.restore_checkpoint(str(checkpoint["id"]), false)
	_check("practice restore requires confirmation", not bool(bad_restore.get("ok", true)) and Navigation.same(practice_initial, practice.export_snapshot()))
	practice.give_up(true)
	var practice_failed: Dictionary = practice.export_snapshot()
	var restored: Dictionary = practice.restore_checkpoint(str(checkpoint["id"]), true, str(practice_failed["failure"]["failure_id"]))
	var recovered: Dictionary = practice.export_snapshot()
	_check("practice restores entire source world with audit transaction", bool(restored.get("ok", false)) and Navigation.same(Navigation.world(recovered), checkpoint["world"]) and recovered["seed"] == practice_initial["seed"] and recovered["floor_transforms"] == practice_initial["floor_transforms"] and int(recovered["recovery_count"]) == 1 and recovered["failure_history"] == practice_failed["failure_history"] and recovered["consumed_loss_ids"].has(practice_failed["failure"]["failure_id"]), recovered)
	var checked: Dictionary = practice.validate_snapshot(recovered)
	_check("authoritative replay validates recovered audit and world", bool(checked.get("ok", false)), {"status": checked.get("status", "")})
	var slot: String = "qa50-" + str(OS.get_process_id())
	var path: String = Save.slot_path(slot, "practice_checkpoint")
	if FileAccess.file_exists(path):
		_check("QA native slot must be a new task-owned path", false, path)
		return
	var saved: Dictionary = Save.write_slot(practice, slot)
	_check("native write persists complete snapshot", bool(saved.get("ok", false)) and saved.get("status", "") == "saved_native", saved)
	if not bool(saved.get("ok", false)): return
	var bytes_before: String = FileAccess.get_sha256(path)
	var loaded = Runtime.new()
	loaded.load_content()
	loaded.choose_mode("practice_checkpoint", "00000002")
	var loaded_result: Dictionary = Save.load_slot(loaded, slot)
	_check("native same-mode different-seed roundtrip is complete", bool(loaded_result.get("ok", false)) and loaded_result.get("status", "") == "loaded_native" and Navigation.same(recovered, loaded.export_snapshot()) and FileAccess.get_sha256(path) == bytes_before, loaded_result)
	var encoded: Dictionary = Save.encode_slot(practice, slot)
	var altered: Dictionary = encoded["payload"].duplicate(true)
	altered["snapshot"]["core_state"]["gold"] = int(altered["snapshot"]["core_state"]["gold"]) + 1
	altered["snapshot_sha256"] = Geometry.content_hash(altered["snapshot"])
	altered.erase("payload_sha256")
	altered["payload_sha256"] = Geometry.content_hash(altered)
	var denied: Dictionary = Save.decode_slot(practice, slot, Geometry.canonical_json(altered))
	_check("re-signed unearned gold still fails authoritative action replay", not bool(denied.get("ok", true)) and Navigation.same(recovered, practice.export_snapshot()) and FileAccess.get_sha256(path) == bytes_before, denied)


func _fresh_world(mode: String, seed: String) -> Dictionary:
	var fresh = Runtime.new()
	fresh.load_content()
	fresh.choose_mode(mode, seed)
	return fresh.export_snapshot()


func _content_rejections(game: RefCounted, original: Dictionary) -> void:
	var canonical: Dictionary = game.data.duplicate(true)
	var changed_enter: Dictionary = canonical.duplicate(true)
	changed_enter["events"]["ev_mapper_intro"]["trigger"] = {"kind": "enter", "cells": [[11, 9]], "direction": [1, 0]}
	var enter_result: Dictionary = game.set_content(changed_enter)
	var enter_after: Dictionary = game.export_snapshot()
	_check("attached NPC cannot invoke a direction-bound enter event", not bool(enter_result.get("ok", true)) and Navigation.same(original, enter_after), {"fixture": "ev_mapper_intro changed to enter while still attached to f01_mapper", "fixture_input_sha256": Geometry.content_hash(changed_enter), "trigger": changed_enter["events"]["ev_mapper_intro"]["trigger"], "result": enter_result, "before_full_sha256": Geometry.content_hash(original), "actual_after_full_sha256": Geometry.content_hash(enter_after)})
	# Red-run cleanup also goes through the real unselected content API. No
	# original source file or authoritative resource/state field is assigned.
	if bool(enter_result.get("ok", false)): game.set_content(canonical)
	var wrong_target: Dictionary = canonical.duplicate(true)
	var mapper: Dictionary = {}
	var occupied: Dictionary = {}
	for item: Dictionary in wrong_target["floors"][0]["objects"]:
		occupied[Vector2i(int(item["pos"][0]), int(item["pos"][1]))] = true
		if item["id"] == "f01_mapper": mapper = item.duplicate(true)
	var cell: Array = []
	var floor: Dictionary = wrong_target["floors"][0]
	for y: int in range(floor["grid"].size()):
		for x: int in range(str(floor["grid"][y]).length()):
			var candidate: Array = [x, y]
			if str(floor["grid"][y])[x] != "#" and not occupied.has(Vector2i(x, y)) and candidate != floor["spawn"] and not floor.get("safe_start_candidates", []).has(candidate):
				cell = candidate
				break
		if not cell.is_empty(): break
	if mapper.is_empty() or cell.is_empty():
		_check("wrong-target fixture has an independent legal NPC cell", false)
		return
	mapper["id"] = "qa_other_mapper"
	mapper["pos"] = cell
	mapper["event_ids"] = ["ev_mapper_intro"]
	wrong_target["floors"][0]["objects"].append(mapper)
	wrong_target["events"]["ev_mapper_intro"]["trigger"] = {"kind": "interact", "object_id": "qa_other_mapper"}
	var path: String = "user://qa50-wrong-event-target-" + str(OS.get_process_id()) + ".json"
	if FileAccess.file_exists(path):
		_check("wrong-target content fixture path is new and QA-owned", false, path)
		return
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		_check("wrong-target content fixture can be written", false)
		return
	file.store_string(Geometry.canonical_json(wrong_target))
	file.close()
	var target_result: Dictionary = game.load_content(path)
	var target_after: Dictionary = game.export_snapshot()
	_check("one NPC cannot invoke another NPC's interaction event", not bool(target_result.get("ok", true)) and Navigation.same(original, target_after), {"fixture": "ev_mapper_intro points to legal qa_other_mapper but f01_mapper still attaches it", "fixture_native_path": path, "fixture_input_sha256": Geometry.content_hash(wrong_target), "fixture_sha256": FileAccess.get_sha256(path), "other_npc": mapper, "result": target_result, "before_full_sha256": Geometry.content_hash(original), "actual_after_full_sha256": Geometry.content_hash(target_after)})
	if bool(target_result.get("ok", false)): game.set_content(canonical)


func _check(name: String, passed: bool, observed: Variant = null) -> void:
	checks.append({"name": name, "passed": passed, "observed": observed})
	if not passed: errors.append({"name": name, "observed": observed})
