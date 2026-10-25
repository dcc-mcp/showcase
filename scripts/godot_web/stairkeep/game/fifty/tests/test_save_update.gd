extends SceneTree
## Positive same-slot replacement, independent from corrupt-slot refusal tests.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Save = preload("res://fifty/scripts/save.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const SELF: String = "res://fifty/tests/test_save_update.gd"
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
				quit(2)
				return
		else:
			push_error("Unknown native save-update argument: " + argument)
			quit(2)
			return
	if output.is_empty() or FileAccess.file_exists(output):
		quit(2)
		return
	var began: int = Time.get_ticks_msec()
	var game = Runtime.new()
	var loaded: Dictionary = game.load_content()
	var selected: Dictionary = game.choose_mode("practice_checkpoint", "00000001") if bool(loaded.get("ok", false)) else loaded
	_check("explicit practice world loads", bool(selected.get("ok", false)), selected)
	var receipt: Dictionary = {}
	if bool(selected.get("ok", false)):
		var initial: Dictionary = game.export_snapshot()
		var slot: String = "qa50replace-" + str(OS.get_process_id())
		var path: String = Save.slot_path(slot, "practice_checkpoint")
		if FileAccess.file_exists(path) or FileAccess.file_exists(path + ".pending"):
			_check("replacement QA begins at a new owned slot", false)
		else:
			var first: Dictionary = Save.write_slot(game, slot)
			var first_hash: String = FileAccess.get_sha256(path)
			_check("first native slot write succeeds", bool(first.get("ok", false)) and first.get("status", "") == "saved_native", first)
			if bool(first.get("ok", false)):
				var code: int = int(initial["floor_transforms"]["1"])
				var vector: Array = Geometry.transform_vector([-1, 0], code)
				var action: Dictionary = {"kind": "move", "dx": int(vector[0]), "dy": int(vector[1])}
				var moved: Dictionary = Navigation.execute(game, [action])
				var changed: Dictionary = game.export_snapshot()
				_check("one actual neutral action changes the replayable save state", bool(moved.get("ok", false)) and Navigation.same(Navigation.economy(initial), Navigation.economy(changed)) and not Navigation.same(initial, changed), moved)
				var replaced: Dictionary = Save.write_slot(game, slot)
				var next_hash: String = FileAccess.get_sha256(path)
				_check("existing valid native slot is replaced by the newer complete snapshot", bool(replaced.get("ok", false)) and replaced.get("status", "") == "saved_native" and not next_hash.is_empty() and next_hash != first_hash and not FileAccess.file_exists(path + ".pending"), replaced)
				var reader = Runtime.new()
				reader.load_content()
				reader.choose_mode("practice_checkpoint", "00000008")
				var restored: Dictionary = Save.load_slot(reader, slot)
				_check("reading the updated slot restores the newer full action journal", bool(restored.get("ok", false)) and Navigation.same(changed, reader.export_snapshot()) and Navigation.same(changed, game.export_snapshot()) and FileAccess.get_sha256(path) == next_hash, restored)
				receipt = {"native_slot": path, "initial_file_sha256": first_hash, "updated_file_sha256": next_hash, "initial_snapshot_sha256": Geometry.content_hash(initial), "updated_snapshot_sha256": Geometry.content_hash(changed), "actual_update_actions": [action], "full_updated_snapshot": changed}
	var report: Dictionary = {"suite": "fifty_native_valid_slot_update/v1", "passed": errors.is_empty(), "engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(), "test_sha256": FileAccess.get_sha256(SELF), "save_sha256": FileAccess.get_sha256("res://fifty/scripts/save.gd"), "rules_sha256": Runtime.rules_fingerprint(), "checks": checks, "errors": errors, "receipt": receipt, "elapsed_ms": Time.get_ticks_msec() - began,
		"scope": "One task-owned native slot is actually saved, the runtime takes one legal neutral move, the valid existing slot is saved again, and a fresh same-mode runtime loads the newer complete snapshot. No corrupt-slot fallback deletion, cross-process writers, crash/power-loss durability, GUI or browser persistence is certified."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "checks": checks.size(), "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if errors.is_empty() else 1)


func _check(name: String, passed: bool, observed: Variant = null) -> void:
	checks.append({"name": name, "passed": passed, "observed": observed})
	if not passed: errors.append({"name": name, "observed": observed})
