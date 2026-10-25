extends SceneTree
## Copy this NEW helper into an owned extraction of the frozen first-chapter source.
## Uses only v1 runtime/save APIs; never accesses pre-existing user slots.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Save = preload("res://fifty/scripts/save.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const EXPECTED: Dictionary = {
	"res://fifty/scripts/runtime.gd": "1d3ab254eedf81e6a591d57c89110641c29171407e0b51f3441664145ba61463",
	"res://fifty/scripts/save.gd": "4e08ddffc85edf89a3207a85080d2b4ec5abc4b97514c845e64047a1b3ed440b",
	"res://fifty/scripts/content.gd": "947c56a0f0fbfd68d071cb02f6a26695747de891c5fa7925fe46867c8d6d7dbd",
	"res://fifty/scripts/d4.gd": "be66aa8198f777d72778b1fd2dde9b75798419254139a4f44956f133983220b2",
	"res://fifty/data/content.json": "3703b2cbc43d2297d42d335ad85ebac3f464d9f6c68d536d75a990e9bdd75fd5",
	"res://scripts/rules.gd": "e89070d800c3a7769c4440b6eec8ed4702afaa45ef0055e78c67959b310c0495"
}
var output: String = ""


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		else:
			quit(2)
			return
	if output.is_empty() or not output.is_absolute_path() or FileAccess.file_exists(output) or FileAccess.file_exists(output + ".report.json"):
		push_error("Pass --output=<new absolute old-v1 payload path>; neither payload nor receipt may exist.")
		quit(2)
		return
	var before_sources: Dictionary = _sources()
	if not _same(before_sources, EXPECTED):
		push_error("Use only the frozen first-chapter source extraction. New chapter-two rules must not generate the legacy fixture.")
		quit(2)
		return
	var game = Runtime.new()
	var loaded: Dictionary = game.load_content()
	var started: Dictionary = game.choose_mode("practice_checkpoint", "00000001") if bool(loaded.get("ok", false)) else loaded
	if not bool(started.get("ok", false)):
		push_error(JSON.stringify(started))
		quit(1)
		return
	var initial: Dictionary = game.export_snapshot()
	var slot: String = "qa2legacy-" + str(OS.get_process_id())
	var native_path: String = Save.slot_path(slot, "practice_checkpoint")
	if native_path != "user://stairkeep-fifty-save-v1/slots/practice_checkpoint/" + slot + ".json" or FileAccess.file_exists(native_path):
		push_error("Legacy QA target is not a new exact v1 namespace slot.")
		quit(2)
		return
	var saved: Dictionary = Save.write_slot(game, slot)
	if not bool(saved.get("ok", false)) or saved.get("status", "") != "saved_native":
		push_error(JSON.stringify(saved))
		quit(1)
		return
	var native_bytes: PackedByteArray = FileAccess.get_file_as_bytes(native_path)
	var native_sha256: String = FileAccess.get_sha256(native_path)
	var fresh = Runtime.new()
	var fresh_content: Dictionary = fresh.load_content()
	var fresh_start: Dictionary = fresh.choose_mode("practice_checkpoint", "00000008") if bool(fresh_content.get("ok", false)) else fresh_content
	var reread: Dictionary = Save.load_slot(fresh, slot) if bool(fresh_start.get("ok", false)) else fresh_start
	var checked: Dictionary = fresh.validate_snapshot(fresh.export_snapshot())
	var passed: bool = bool(reread.get("ok", false)) and reread.get("status", "") == "loaded_native" and bool(checked.get("ok", false)) and _same(initial, fresh.export_snapshot()) and _same(initial, game.export_snapshot()) and FileAccess.get_file_as_bytes(native_path) == native_bytes and FileAccess.get_sha256(native_path) == native_sha256 and _same(before_sources, _sources())
	if not passed:
		push_error("Actual old native save/fresh load/full snapshot verification failed.")
		quit(1)
		return
	var payload: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if payload == null:
		quit(2)
		return
	payload.store_buffer(native_bytes)
	payload.close()
	passed = FileAccess.get_file_as_bytes(output) == native_bytes and FileAccess.get_sha256(output) == native_sha256
	var report: Dictionary = {"suite": "fifty_chapter2_old_v1_native_fixture/v1", "passed": passed, "measurement_completed": passed, "engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(), "mode": "practice_checkpoint", "seed": "00000001", "slot_id": slot, "old_namespace": "user://stairkeep-fifty-save-v1/slots", "native_path": native_path, "fixture": output, "fixture_sha256": FileAccess.get_sha256(output), "fixture_bytes": native_bytes.size(), "fixture_created": passed, "fresh_native_load_passed": bool(reread.get("ok", false)), "complete_snapshot_equal": _same(initial, fresh.export_snapshot()), "native_bytes_unchanged_after_load": FileAccess.get_file_as_bytes(native_path) == native_bytes, "runtime_identity": game.runtime_identity(), "save_result": saved, "fresh_load_result": reread, "full_snapshot_replay_result": checked, "source_before": before_sources, "source_after": _sources(), "scope": "Actual frozen v1 Save.write_slot and fresh Save.load_slot, then byte-identical copy into a new explicit payload file. Isolated task-owned user directory only; no real user slot, executable inspection, new runtime impersonation, injected resource or migration."}
	var receipt: FileAccess = FileAccess.open(output + ".report.json", FileAccess.WRITE)
	if receipt == null:
		quit(2)
		return
	receipt.store_string(JSON.stringify(report, "  ") + "\n")
	receipt.close()
	print(JSON.stringify({"passed": passed, "fixture_sha256": report["fixture_sha256"], "fixture_bytes": native_bytes.size(), "report": output + ".report.json"}))
	quit(0 if passed else 1)


func _sources() -> Dictionary:
	var result: Dictionary = {}
	for path: String in EXPECTED: result[path] = FileAccess.get_sha256(path)
	return result


func _same(a: Variant, b: Variant) -> bool:
	return Geometry.canonical_json(a) == Geometry.canonical_json(b)
