extends SceneTree
## New profile namespaces, semantic rejection, and byte-preserved old owned slots.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Save = preload("res://fifty/scripts/save.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const FIRST: String = "stairkeep-fifty-slice/v1"
const SECOND: String = "stairkeep-fifty-chapter2/v1"
const MODE: String = "practice_checkpoint"
const DATA: String = "res://fifty/data/chapter2-content.json"
const SELF: String = "res://fifty/tests/chapter2_save_profiles.gd"
var output: String = ""
var content_sha256: String = ""
var legacy_file: String = ""
var legacy_sha256: String = ""
var legacy_receipt: String = ""
var legacy_receipt_sha256: String = ""
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
		elif argument.begins_with("--content-sha256="): content_sha256 = argument.trim_prefix("--content-sha256=")
		elif argument.begins_with("--legacy-v1-fixture="): legacy_file = argument.trim_prefix("--legacy-v1-fixture=")
		elif argument.begins_with("--legacy-v1-sha256="): legacy_sha256 = argument.trim_prefix("--legacy-v1-sha256=")
		elif argument.begins_with("--legacy-v1-receipt="): legacy_receipt = argument.trim_prefix("--legacy-v1-receipt=")
		elif argument.begins_with("--legacy-v1-receipt-sha256="): legacy_receipt_sha256 = argument.trim_prefix("--legacy-v1-receipt-sha256=")
		elif argument.begins_with("--stop-file="): stop_file = argument.trim_prefix("--stop-file=")
		else:
			quit(2)
			return
	if output.is_empty() or not output.is_absolute_path() or FileAccess.file_exists(output) or content_sha256.length() != 64 or FileAccess.get_sha256(DATA) != content_sha256:
		push_error("Require a new output and the frozen chapter-two --content-sha256.")
		quit(2)
		return
	if not legacy_file.is_empty() and (legacy_sha256.length() != 64 or FileAccess.get_sha256(legacy_file) != legacy_sha256 or legacy_receipt.is_empty() or legacy_receipt_sha256.length() != 64 or FileAccess.get_sha256(legacy_receipt) != legacy_receipt_sha256):
		push_error("The supplied old native fixture and external native receipt require exact SHA bindings.")
		quit(2)
		return
	var began: int = Time.get_ticks_msec()
	_exercise()
	var complete: bool = bool(evidence.get("profile_isolation_complete", false)) and bool(evidence.get("old_v1_owned_slot_tested", false))
	var report: Dictionary = {"suite": "fifty_chapter2_native_save_profile_isolation/v1", "passed": errors.is_empty() and not stopped, "measurement_completed": complete and errors.is_empty() and not stopped, "stopped_at_case_boundary": stopped, "engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(), "test_sha256": FileAccess.get_sha256(SELF), "source_hashes": _sources(), "checks": checks, "errors": errors, "evidence": evidence, "elapsed_ms": Time.get_ticks_msec() - began,
		"scope": "Native chapter1/chapter2 namespaces are distinct while format/save version stay at v1. Cross-profile decode/import/native load and invalid existing-slot overwrite reject without runtime or source-slot mutation. The old-v1 fixture path is newly QA-owned, copied only when explicit fixture and external native-origin receipt hashes are supplied; this test does not generate that old native receipt or read pre-existing user saves. Without that fixture this is a partial profile-isolation probe, not completed old-slot coverage. Integrity checksums are not authentication; no migration or browser durability is claimed."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "measurement_completed": report["measurement_completed"], "checks": checks.size(), "errors": errors.size()}))
	quit(0 if errors.is_empty() else 1)


func _exercise() -> void:
	if _stop(): return
	var first = Runtime.new()
	var second = Runtime.new()
	var loaded_first: Dictionary = first.load_content("res://fifty/data/content.json")
	var loaded_second: Dictionary = second.load_content(DATA)
	if not _check("both explicit known profiles validate", bool(loaded_first.get("ok", false)) and bool(loaded_second.get("ok", false)), {"first": loaded_first, "second": loaded_second}): return
	var started_first: Dictionary = first.choose_mode(MODE, "00000001")
	var started_second: Dictionary = second.choose_mode(MODE, "00000008")
	if not _check("both profiles explicitly choose same mode independently", bool(started_first.get("ok", false)) and bool(started_second.get("ok", false)) and first.runtime_identity()["content_id"] == FIRST and second.runtime_identity()["content_id"] == SECOND): return
	var slot: String = "qa2profile-" + str(OS.get_process_id())
	var first_path: String = Save.slot_path(slot, MODE, FIRST)
	var second_path: String = Save.slot_path(slot, MODE, SECOND)
	var expected_root: String = "user://stairkeep-fifty-chapters-save-v1/"
	if not _check("profile namespaces distinct with legacy-root isolation", first_path == expected_root + "chapter1/slots/" + MODE + "/" + slot + ".json" and second_path == expected_root + "chapter2/slots/" + MODE + "/" + slot + ".json" and Save.slot_path(slot, MODE) == first_path and first_path != second_path): return
	if not _check("only newly owned slot targets are used", not FileAccess.file_exists(first_path) and not FileAccess.file_exists(second_path)): return
	var first_before: Dictionary = first.export_snapshot()
	var second_before: Dictionary = second.export_snapshot()
	var written_first: Dictionary = Save.write_slot(first, slot)
	if not _check("actual first-profile native slot saved", bool(written_first.get("ok", false)) and written_first.get("status", "") == "saved_native", written_first): return
	var first_hash: String = FileAccess.get_sha256(first_path)
	var absent_second: Dictionary = Save.load_slot(second, slot)
	if not _check("same named first-profile slot is not read from second profile", not bool(absent_second.get("ok", true)) and absent_second.get("status", "") == "not_found" and Navigation.same(second_before, second.export_snapshot()) and FileAccess.get_sha256(first_path) == first_hash and not FileAccess.file_exists(second_path), absent_second): return
	var foreign_decode: Dictionary = Save.decode_slot(second, slot, FileAccess.get_file_as_string(first_path))
	var foreign_import: Dictionary = second.import_snapshot(first_before)
	if not _check("cross-profile semantic decode and runtime import reject unchanged", not bool(foreign_decode.get("ok", true)) and foreign_decode.get("status", "") == "identity_mismatch" and not bool(foreign_import.get("ok", true)) and Navigation.same(second_before, second.export_snapshot()) and FileAccess.get_sha256(first_path) == first_hash, {"decode": foreign_decode, "import": foreign_import}): return
	var written_second: Dictionary = Save.write_slot(second, slot)
	if not _check("actual second-profile native slot saved separately", bool(written_second.get("ok", false)) and written_second.get("status", "") == "saved_native" and FileAccess.get_sha256(first_path) == first_hash, written_second): return
	var second_hash: String = FileAccess.get_sha256(second_path)
	var reader = Runtime.new()
	reader.load_content(DATA)
	reader.choose_mode(MODE, "00000007")
	var roundtrip: Dictionary = Save.load_slot(reader, slot)
	if not _check("new-profile different-seed native roundtrip restores complete snapshot", bool(roundtrip.get("ok", false)) and Navigation.same(second_before, reader.export_snapshot()) and FileAccess.get_sha256(first_path) == first_hash and FileAccess.get_sha256(second_path) == second_hash, roundtrip): return
	var reverse_decode: Dictionary = Save.decode_slot(first, slot, FileAccess.get_file_as_string(second_path))
	if not _check("reverse profile decode rejects with original state and bytes unchanged", not bool(reverse_decode.get("ok", true)) and reverse_decode.get("status", "") == "identity_mismatch" and Navigation.same(first_before, first.export_snapshot()) and FileAccess.get_sha256(first_path) == first_hash and FileAccess.get_sha256(second_path) == second_hash, reverse_decode): return
	for direction: int in range(2):
		if _stop(): return
		var source = first if direction == 0 else second
		var target = second if direction == 0 else first
		var profile: String = SECOND if direction == 0 else FIRST
		var foreign_slot: String = "qa2foreign-" + str(OS.get_process_id()) + "-" + str(direction)
		var encoded: Dictionary = Save.encode_slot(source, foreign_slot)
		if not _check("foreign native fixture encodes from actual source runtime", bool(encoded.get("ok", false)), encoded): return
		var path: String = Save.slot_path(foreign_slot, MODE, profile)
		if not _owned_file(path, str(encoded["text"]).to_utf8_buffer()): return
		var original_hash: String = FileAccess.get_sha256(path)
		var original_state: Dictionary = target.export_snapshot()
		var rejected_load: Dictionary = Save.load_slot(target, foreign_slot)
		var rejected_write: Dictionary = Save.write_slot(target, foreign_slot)
		if not _check("foreign existing native slot load and overwrite reject unchanged " + str(direction), not bool(rejected_load.get("ok", true)) and rejected_load.get("status", "") == "identity_mismatch" and not bool(rejected_write.get("ok", true)) and rejected_write.get("status", "") == "existing_slot_rejected" and FileAccess.get_sha256(path) == original_hash and Navigation.same(original_state, target.export_snapshot()) and FileAccess.get_sha256(first_path) == first_hash and FileAccess.get_sha256(second_path) == second_hash, {"load": rejected_load, "write": rejected_write, "original_fixture_sha256": original_hash}): return
	evidence["profile_isolation_complete"] = true
	evidence["native_first_profile_slot_sha256"] = first_hash
	evidence["native_second_profile_slot_sha256"] = second_hash
	evidence["full_first_snapshot"] = first_before
	evidence["full_second_snapshot"] = second_before
	evidence["old_v1_owned_slot_tested"] = false
	if _stop(): return
	if not legacy_file.is_empty(): _legacy(first, second)


func _legacy(first: RefCounted, second: RefCounted) -> void:
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(legacy_file)
	var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
	if not _check("externally bound old native fixture has genuine old profile envelope shape", parsed is Dictionary and parsed.get("format_id", "") == "stairkeep-fifty-save" and int(parsed.get("save_version", -1)) == 1 and parsed.get("runtime_identity", {}).get("content_id", "") == FIRST and parsed.get("mode", "") == MODE): return
	var slot: String = str(parsed["slot_id"])
	if not _check("legacy fixture slot ID is safe in current profile API", not Save.slot_path(slot, MODE, FIRST).is_empty()): return
	var old_path: String = "user://stairkeep-fifty-save-v1/slots/" + MODE + "/" + slot + ".json"
	if not _owned_file(old_path, bytes): return
	var old_hash: String = FileAccess.get_sha256(old_path)
	for target in [first, second]:
		var before: Dictionary = target.export_snapshot()
		var decode: Dictionary = Save.decode_slot(target, slot, bytes.get_string_from_utf8())
		var load: Dictionary = Save.load_slot(target, slot)
		if not _check("old native slot neither decodes nor silently migrates into " + str(before["content_id"]), not bool(decode.get("ok", true)) and not bool(load.get("ok", true)) and Navigation.same(before, target.export_snapshot()) and FileAccess.get_sha256(old_path) == old_hash and not FileAccess.file_exists(Save.slot_path(slot, MODE, str(before["content_id"]))), {"decode": decode, "load": load}): return
	evidence["old_v1_owned_slot_tested"] = true
	evidence["old_v1_fixture_sha256"] = legacy_sha256
	evidence["old_v1_native_origin_external_receipt_sha256"] = legacy_receipt_sha256
	evidence["old_v1_origin_scope"] = "External native-origin receipt bytes are SHA-bound, not independently fabricated or regenerated by this test. Old file copied into a new QA-owned legacy namespace target; no pre-existing user file was read or replaced."
	evidence["old_v1_qa_copy_sha256_after"] = FileAccess.get_sha256(old_path)


func _owned_file(path: String, bytes: PackedByteArray) -> bool:
	if not _check("fixture target is new and only under owned user namespace", path.begins_with("user://stairkeep-fifty-") and not FileAccess.file_exists(path), {"path": path}): return false
	if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir())) != OK:
		return _check("owned fixture directory created", false)
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null: return _check("owned fixture file created", false)
	file.store_buffer(bytes)
	file.close()
	return _check("owned fixture writes exact bytes", FileAccess.get_file_as_bytes(path) == bytes)


func _check(name: String, passed: bool, details: Dictionary = {}) -> bool:
	checks.append({"name": name, "passed": passed, "details": details})
	if not passed: errors.append({"name": name, "details": details})
	return passed


func _stop() -> bool:
	stopped = not stop_file.is_empty() and FileAccess.file_exists(stop_file)
	return stopped


func _sources() -> Dictionary:
	var result: Dictionary = {}
	for source: String in [SELF, DATA, "res://fifty/data/content.json", "res://scripts/rules.gd", "res://fifty/scripts/runtime.gd", "res://fifty/scripts/content.gd", "res://fifty/scripts/d4.gd", "res://fifty/scripts/save.gd", "res://fifty/tests/qa_navigation.gd"]:
		result[source] = FileAccess.get_sha256(source)
	return result
