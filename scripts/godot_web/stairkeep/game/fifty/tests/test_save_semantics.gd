extends SceneTree
## Full authored run fixture -> real checkpoint transaction -> native slots.
## Detached malicious payloads never assign authoritative resources or position.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Save = preload("res://fifty/scripts/save.gd")
const BaseRules = preload("res://scripts/rules.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const SELF: String = "res://fifty/tests/test_save_semantics.gd"
var output: String = ""
var route_report: String = ""
var legacy_21: String = ""
var selected_case: int = 0
var limit: int = 99
var stop_file: String = ""
var stopped: bool = false
var checks: Array = []
var errors: Array = []
var evidence: Dictionary = {}


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		elif argument.begins_with("--route-report="): route_report = argument.trim_prefix("--route-report=")
		elif argument.begins_with("--legacy-21="): legacy_21 = argument.trim_prefix("--legacy-21=")
		elif argument.begins_with("--case=") and argument.trim_prefix("--case=").is_valid_int(): selected_case = int(argument.trim_prefix("--case="))
		elif argument.begins_with("--max-tamper=") and argument.trim_prefix("--max-tamper=").is_valid_int(): limit = int(argument.trim_prefix("--max-tamper="))
		elif argument.begins_with("--stop-file="):
			stop_file = argument.trim_prefix("--stop-file=")
			if FileAccess.file_exists(stop_file):
				quit(2)
				return
		else:
			push_error("Unknown save QA argument: " + argument)
			quit(2)
			return
	if output.is_empty() or FileAccess.file_exists(output) or route_report.is_empty() or selected_case < 0 or limit < 1 or limit > 99:
		push_error("Pass --route-report=<actual practice JSON> --output=<new JSON>, optional --case/--max-tamper/--legacy-21.")
		quit(2)
		return
	var started: int = Time.get_ticks_msec()
	var json: JSON = JSON.new()
	if json.parse(FileAccess.get_file_as_string(route_report)) != OK or not (json.data is Dictionary):
		push_error("The actual route fixture is unavailable.")
		quit(2)
		return
	var producer: Dictionary = json.data
	if producer.get("suite", "") != "fifty_actual_authored_route_matrix/v1" or not bool(producer.get("passed", false)) or selected_case >= producer.get("cases", []).size():
		push_error("A passed actual route case is required; no synthetic state fixture is accepted.")
		quit(2)
		return
	for source: String in producer.get("source_hashes", {}):
		if FileAccess.get_sha256(source) != producer["source_hashes"][source]:
			push_error("The actual route fixture source differs: " + source)
			quit(2)
			return
	var fixture: Dictionary = producer["cases"][selected_case]
	if fixture.get("mode", "") != "practice_checkpoint" or not bool(fixture.get("passed", false)) or not bool(fixture.get("authoritative_full_action_replay", {}).get("ok", false)):
		push_error("Supply an actual completed practice route with its authoritative action replay receipt.")
		quit(2)
		return
	var game = Runtime.new()
	game.load_content()
	game.choose_mode("practice_checkpoint", fixture["full_final_snapshot"]["root_seed"])
	var imported: Dictionary = game.import_snapshot(fixture["full_final_snapshot"])
	_check("actual route fixture imports only after full authoritative replay", bool(imported.get("ok", false)) and Navigation.same(game.export_snapshot(), fixture["full_final_snapshot"]), {"result": imported, "source_report_sha256": FileAccess.get_sha256(route_report), "case": selected_case})
	if bool(imported.get("ok", false)): _exercise(game)
	var report: Dictionary = {"suite": "fifty_full_native_save_semantics/v1", "passed": errors.is_empty() and not stopped, "measurement_completed": not stopped and bool(evidence.get("tamper_coverage_complete", false)), "stopped_at_case_boundary": stopped, "engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(),
		"test_sha256": FileAccess.get_sha256(SELF), "route_fixture_sha256": FileAccess.get_sha256(route_report), "fixture_case": selected_case, "rules_sha256": Runtime.rules_fingerprint(),
		"save_sha256": FileAccess.get_sha256("res://fifty/scripts/save.gd"), "checks": checks, "errors": errors, "evidence": evidence, "elapsed_ms": Time.get_ticks_msec() - started,
		"scope": "Only original actual route fixtures bound to their current sources are accepted, and the runtime independently replays their complete action history before adoption. A real F5 checkpoint transaction and native slots then exercise full world/audit persistence. Re-signed illegal history/resources/flags/stock/references are rejected without current-state or original-file mutation. Checksums are integrity checks, not authentication. No GUI, browser durability, original-slot migration or fifty-floor completion is claimed."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "checks": checks.size(), "errors": errors.size(), "tamper_cases": evidence.get("tamper_cases_tested", 0), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if errors.is_empty() else 1)


func _exercise(game: RefCounted) -> void:
	var completed: Dictionary = game.export_snapshot()
	var checkpoint: Dictionary = {}
	for item: Dictionary in completed["checkpoints"]:
		if item["id"] == "entry_05": checkpoint = item
	if checkpoint.is_empty():
		_check("actual F5 captured checkpoint exists", false)
		return
	game.give_up(true)
	var failed: Dictionary = game.export_snapshot()
	var restored_result: Dictionary = game.restore_checkpoint(str(checkpoint["id"]), true, str(failed["failure"]["failure_id"]))
	var actual: Dictionary = game.export_snapshot()
	_check("actual F5 restore removes every future resource NPC flag stock and checkpoint", bool(restored_result.get("ok", false)) and Navigation.same(Navigation.world(actual), checkpoint["world"]) and actual["checkpoints"].size() == 5 and actual["seed"] == completed["seed"] and actual["floor_transforms"] == completed["floor_transforms"] and actual["failure_history"] == failed["failure_history"] and actual["consumed_loss_ids"].has(failed["failure"]["failure_id"]), restored_result)
	evidence["full_pre_recovery_snapshot"] = completed
	evidence["full_restored_snapshot"] = actual
	var slot: String = "qa50sem-" + str(OS.get_process_id())
	var path: String = Save.slot_path(slot, "practice_checkpoint")
	if FileAccess.file_exists(path):
		_check("semantic QA slot must be new", false)
		return
	var written: Dictionary = Save.write_slot(game, slot)
	_check("full midrun restored world and history really save natively", bool(written.get("ok", false)) and written.get("status", "") == "saved_native", written)
	if not bool(written.get("ok", false)): return
	var hash_before: String = FileAccess.get_sha256(path)
	var reader = Runtime.new()
	reader.load_content()
	reader.choose_mode("practice_checkpoint", "00000008")
	var read: Dictionary = Save.load_slot(reader, slot)
	_check("native load preserves every checkpoint world and recovery audit field", bool(read.get("ok", false)) and Navigation.same(actual, reader.export_snapshot()) and FileAccess.get_sha256(path) == hash_before, read)
	var encoded: Dictionary = Save.encode_slot(game, slot)
	if not bool(encoded.get("ok", false)):
		_check("legal semantic fixture encodes", false, encoded)
		return
	var good: Dictionary = encoded["payload"]
	var mutations: Array[String] = ["hp", "gold", "flags", "stock", "checkpoint", "actions", "history", "consumed", "recovery_count", "future_reference", "foreign_identity", "future_version", "mode", "checksum"]
	var exercised: Array = []
	for index: int in range(mini(limit, mutations.size())):
		if not stop_file.is_empty() and FileAccess.file_exists(stop_file):
			stopped = true
			break
		var name: String = mutations[index]
		var bad_slot: String = "qa50bad-" + str(OS.get_process_id()) + "-" + str(index)
		var payload: Dictionary = good.duplicate(true)
		payload["slot_id"] = bad_slot
		match name:
			"hp": payload["snapshot"]["core_state"]["hp"] = int(payload["snapshot"]["core_state"]["hp"]) + 1
			"gold": payload["snapshot"]["core_state"]["gold"] = int(payload["snapshot"]["core_state"]["gold"]) + 1
			"flags": payload["snapshot"]["flags"]["archive_read"] = not bool(payload["snapshot"]["flags"]["archive_read"])
			"stock":
				var purchase: String = str(payload["snapshot"]["core_state"]["purchases"].keys()[0])
				payload["snapshot"]["core_state"]["purchases"][purchase] = 0
			"checkpoint": payload["snapshot"]["checkpoints"][0]["world"]["core_state"]["gold"] = int(payload["snapshot"]["checkpoints"][0]["world"]["core_state"]["gold"]) + 1
			"actions": payload["snapshot"]["actions"].pop_back()
			"history": payload["snapshot"]["failure_history"].pop_back()
			"consumed": payload["snapshot"]["consumed_loss_ids"].clear()
			"recovery_count": payload["snapshot"]["recovery_count"] = int(payload["snapshot"]["recovery_count"]) - 1
			"future_reference": payload["snapshot"]["actions"][-1]["checkpoint_id"] = "entry_50"
			"foreign_identity": payload["runtime_identity"]["content_id"] = "stairkeep-campaign-21/v1"
			"future_version": payload["save_version"] = 999
			"mode": payload["mode"] = "classic_restart"
			"checksum": payload["snapshot"]["core_state"]["gold"] = int(payload["snapshot"]["core_state"]["gold"]) + 1
		if name != "checksum": _resign(payload)
		var text: String = Geometry.canonical_json(payload)
		var bad_path: String = Save.slot_path(bad_slot, "practice_checkpoint")
		if FileAccess.file_exists(bad_path):
			_check("malicious fixture slot is new", false, bad_path)
			return
		var file: FileAccess = FileAccess.open(bad_path, FileAccess.WRITE)
		if file == null:
			_check("malicious fixture bytes can be saved for QA", false)
			return
		file.store_string(text)
		file.close()
		var malicious_hash: String = FileAccess.get_sha256(bad_path)
		var decoded: Dictionary = Save.decode_slot(game, bad_slot, text)
		var rejected: Dictionary = Save.load_slot(game, bad_slot)
		var refused_overwrite: Dictionary = Save.write_slot(game, bad_slot)
		var preserved: bool = Navigation.same(actual, game.export_snapshot()) and FileAccess.get_sha256(path) == hash_before and FileAccess.get_sha256(bad_path) == malicious_hash
		_check("illegal " + name + " payload rejects decode/load/overwrite with full state and bytes unchanged", not bool(decoded.get("ok", true)) and not bool(rejected.get("ok", true)) and not bool(refused_overwrite.get("ok", true)) and preserved, {"mutation": name, "attacker_recomputed_both_checksums": name != "checksum", "decode": decoded, "native_load": rejected, "native_overwrite": refused_overwrite, "fixture_sha256": malicious_hash, "fixture_native_path": bad_path})
		exercised.append(name)
	evidence["tamper_cases_tested"] = exercised.size()
	evidence["tamper_cases_available"] = mutations.size()
	evidence["tamper_coverage_complete"] = exercised.size() == mutations.size()
	evidence["tested_mutations"] = exercised
	evidence["original_valid_slot_sha256"] = hash_before
	evidence["original_valid_slot_native_path"] = path
	if stopped: return
	for invalid: String in ["", "../escape", "CON", "con", "MixedCase"]:
		var invalid_result: Dictionary = Save.write_slot(game, invalid)
		_check("invalid explicit slot ID rejects " + invalid, not bool(invalid_result.get("ok", true)) and Navigation.same(actual, game.export_snapshot()) and FileAccess.get_sha256(path) == hash_before, invalid_result)
	_check("classic and practice slot directories are physically distinct", Save.slot_path(slot, "classic_restart") != path and Save.slot_path(slot, "unselected").is_empty())
	_legacy(game, actual, slot, path, hash_before)


func _legacy(game: RefCounted, actual: Dictionary, slot: String, valid_path: String, valid_hash: String) -> void:
	var original = BaseRules.new()
	var old_path: String = "user://qa50-original3-" + str(OS.get_process_id()) + ".json"
	if FileAccess.file_exists(old_path):
		_check("original-three QA fixture path is new", false)
		return
	var made: bool = original.save_game(old_path)
	var old_hash: String = FileAccess.get_sha256(old_path)
	var rejected: Dictionary = Save.decode_slot(game, slot, FileAccess.get_file_as_string(old_path))
	_check("actual original-three native format refuses without migration or mutation", made and not bool(rejected.get("ok", true)) and Navigation.same(actual, game.export_snapshot()) and FileAccess.get_sha256(old_path) == old_hash and FileAccess.get_sha256(valid_path) == valid_hash, {"original_native_sha256": old_hash, "result": rejected})
	if not legacy_21.is_empty():
		var legacy_hash: String = FileAccess.get_sha256(legacy_21)
		var original_json: JSON = JSON.new()
		var original_identity: bool = original_json.parse(FileAccess.get_file_as_string(legacy_21)) == OK and original_json.data is Dictionary and original_json.data.get("schema_version", -1) == 2 and original_json.data.get("content_id", "") == "stairkeep-campaign-21/v1" and original_json.data.get("state") is Dictionary
		var legacy_result: Dictionary = Save.decode_slot(game, slot, FileAccess.get_file_as_string(legacy_21))
		_check("supplied original-21 native slot refuses identity unchanged", original_identity and not legacy_hash.is_empty() and not bool(legacy_result.get("ok", true)) and Navigation.same(actual, game.export_snapshot()) and FileAccess.get_sha256(legacy_21) == legacy_hash and FileAccess.get_sha256(valid_path) == valid_hash, {"supplied_native_sha256": legacy_hash, "original_declared_identity_matches": original_identity, "result": legacy_result})
		evidence["actual_legacy21_slot_tested"] = original_identity and not legacy_hash.is_empty()
	else:
		var legacy_identity_fixture: Dictionary = {"schema_version": 2, "content_id": "stairkeep-campaign-21/v1", "state": {}}
		var legacy_result: Dictionary = Save.decode_slot(game, slot, Geometry.canonical_json(legacy_identity_fixture))
		_check("declared original-21 format and identity fixture is refused", not bool(legacy_result.get("ok", true)) and Navigation.same(actual, game.export_snapshot()) and FileAccess.get_sha256(valid_path) == valid_hash, legacy_result)
		evidence["actual_legacy21_slot_tested"] = false
		evidence["legacy21_scope"] = "Only a declared old-format/identity fixture; no genuine retained old-21 native slot bytes were supplied. That exact native-slot rejection remains not-tested; no migration is attempted."


func _resign(payload: Dictionary) -> void:
	payload["snapshot_sha256"] = Geometry.content_hash(payload["snapshot"])
	payload.erase("payload_sha256")
	payload["payload_sha256"] = Geometry.content_hash(payload)


func _check(name: String, passed: bool, observed: Variant = null) -> void:
	checks.append({"name": name, "passed": passed, "observed": observed})
	if not passed: errors.append({"name": name, "observed": observed})
