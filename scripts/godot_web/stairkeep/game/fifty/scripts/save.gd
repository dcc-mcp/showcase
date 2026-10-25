class_name FiftySave
extends RefCounted
## Independent native slots for the fifty-floor runtime. No legacy migration.
## Checksums detect corruption; they are not an authenticity or anti-cheat key.

const FORMAT_ID: String = "stairkeep-fifty-save"
const SAVE_VERSION: int = 1
const STATE_SCHEMA: String = "stairkeep-fifty-state/v1"
const SLOT_ROOT: String = "user://stairkeep-fifty-save-v1/slots"
const MAX_BYTES: int = 8388608
const MAX_JSON_DEPTH: int = 64
const MAX_EXACT_INTEGER: int = 9007199254740991
const MODES: Array[String] = ["classic_restart", "practice_checkpoint"]
const ENVELOPE_FIELDS: Array[String] = ["format_id", "save_version", "slot_id", "mode", "runtime_identity", "snapshot", "snapshot_sha256", "payload_sha256"]
const IDENTITY_FIELDS: Array[String] = ["content_id", "content_sha256", "rules_sha256", "variant_spec", "snapshot_schema"]
const REQUIRED_METHODS: Array[String] = ["export_snapshot", "validate_snapshot", "import_snapshot", "runtime_identity"]
const RESERVED_SLOTS: Array[String] = ["con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"]


static func slot_path(slot_id: String, mode: String) -> String:
	if not _valid_slot(slot_id) or not MODES.has(mode):
		return ""
	return SLOT_ROOT + "/" + mode + "/" + slot_id + ".json"


static func encode_slot(runtime: Object, slot_id: String) -> Dictionary:
	if not _valid_slot(slot_id):
		return _fail("invalid_slot", "Choose an explicit lowercase slot ID of 1–32 safe characters.")
	var context: Dictionary = _runtime_context(runtime)
	if not context.get("ok", false):
		return context
	var candidate: Dictionary = context["snapshot"]
	var checked: Dictionary = _validate_candidate(runtime, candidate, context)
	if not checked.get("ok", false):
		return checked
	var payload: Dictionary = {
		"format_id": FORMAT_ID,
		"save_version": SAVE_VERSION,
		"slot_id": slot_id,
		"mode": context["mode"],
		"runtime_identity": context["identity"].duplicate(true),
		"snapshot": candidate.duplicate(true),
		"snapshot_sha256": _canonical(candidate).sha256_text(),
	}
	payload["payload_sha256"] = _canonical(payload).sha256_text()
	var text: String = _canonical(payload) + "\n"
	if text.to_utf8_buffer().size() > MAX_BYTES:
		return _fail("payload_too_large", "The complete snapshot exceeds this bounded slot.")
	return {"ok": true, "status": "encoded", "message": "Complete snapshot encoded; no persistence or state change occurred.", "slot_id": slot_id, "mode": context["mode"], "text": text, "payload": payload, "bytes": text.to_utf8_buffer().size(), "sha256": text.sha256_text(), "snapshot_sha256": payload["snapshot_sha256"]}


static func decode_slot(runtime: Object, slot_id: String, text: String) -> Dictionary:
	if not _valid_slot(slot_id):
		return _fail("invalid_slot", "Choose an explicit safe slot ID.")
	var context: Dictionary = _runtime_context(runtime)
	if not context.get("ok", false):
		return context
	return _decode(runtime, slot_id, text, context)


static func write_slot(runtime: Object, slot_id: String) -> Dictionary:
	var encoded: Dictionary = encode_slot(runtime, slot_id)
	if not encoded.get("ok", false):
		return encoded
	if OS.has_feature("web"):
		return _web_block()
	var mode: String = encoded["mode"]
	var path: String = slot_path(slot_id, mode)
	# A corrupt, unknown or future slot is not an overwrite target. It remains
	# available for inspection; choose another explicit slot instead.
	if FileAccess.file_exists(path):
		var existing: Dictionary = _read_candidate(runtime, slot_id, path)
		if not existing.get("ok", false):
			return {"ok": false, "status": "existing_slot_rejected", "message": "The existing slot was not overwritten.", "reason": existing.get("status", "invalid_slot_payload"), "slot_id": slot_id, "mode": mode}
	var pending: String = path + ".pending"
	if FileAccess.file_exists(pending):
		return _fail("pending_exists", "A previous pending file exists. No file was overwritten.")
	var directory: String = ProjectSettings.globalize_path(path.get_base_dir())
	var mkdir_error: Error = DirAccess.make_dir_recursive_absolute(directory)
	if mkdir_error != OK:
		return _fail("directory_failed", "Cannot create the independent slot directory.")
	var output: FileAccess = FileAccess.open(pending, FileAccess.WRITE)
	if output == null:
		return _fail("write_failed", "Cannot open this slot's pending file; the previous slot was preserved.")
	var bytes: PackedByteArray = str(encoded["text"]).to_utf8_buffer()
	output.store_buffer(bytes)
	output.flush()
	var write_error: Error = output.get_error()
	output.close()
	if write_error != OK or FileAccess.get_file_as_bytes(pending) != bytes:
		return _pending_failure("write_failed", "Pending bytes did not verify; the previous slot was preserved.", pending)
	# This is the only commit. Never delete the old slot and rewrite it.
	var rename_error: Error = DirAccess.rename_absolute(ProjectSettings.globalize_path(pending), ProjectSettings.globalize_path(path))
	if rename_error != OK:
		return _pending_failure("commit_failed", "Same-directory rename failed; no delete-and-rewrite fallback was attempted.", pending)
	return {"ok": true, "status": "saved_native", "message": "Complete native snapshot committed by same-directory rename.", "slot_id": slot_id, "mode": mode, "bytes": bytes.size(), "sha256": encoded["sha256"], "snapshot_sha256": encoded["snapshot_sha256"]}


static func load_slot(runtime: Object, slot_id: String) -> Dictionary:
	if not _valid_slot(slot_id):
		return _fail("invalid_slot", "Choose an explicit safe slot ID.")
	var context: Dictionary = _runtime_context(runtime)
	if not context.get("ok", false):
		return context
	if OS.has_feature("web"):
		return _web_block()
	var read: Dictionary = _read_candidate(runtime, slot_id, slot_path(slot_id, context["mode"]))
	if not read.get("ok", false):
		return read
	# All parsing, identities, checksums and runtime references passed first.
	# The runtime repeats its own validation and commits the full state once.
	var imported: Variant = runtime.call("import_snapshot", read["snapshot"].duplicate(true))
	if not (imported is Dictionary) or imported.get("ok", false) != true:
		return {"ok": false, "status": "import_rejected", "message": "The runtime rejected the candidate; no save file was changed.", "reason": imported.get("status", "invalid_runtime_result") if imported is Dictionary else "invalid_runtime_result"}
	return {"ok": true, "status": "loaded_native", "message": "Complete native snapshot restored in the already selected mode.", "slot_id": slot_id, "mode": context["mode"], "bytes": read["bytes"], "sha256": read["sha256"], "snapshot_sha256": read["snapshot_sha256"]}


static func _runtime_context(runtime: Object) -> Dictionary:
	if not is_instance_valid(runtime):
		return _fail("runtime_unavailable", "A loaded fifty-floor runtime is required.")
	for method: String in REQUIRED_METHODS:
		if not runtime.has_method(method):
			return _fail("runtime_api_mismatch", "The independent snapshot runtime API is required.")
	var raw_snapshot: Variant = runtime.call("export_snapshot")
	var raw_identity: Variant = runtime.call("runtime_identity")
	if not (raw_snapshot is Dictionary) or not (raw_identity is Dictionary):
		return _fail("runtime_api_mismatch", "Runtime snapshot and identity must be complete objects.")
	var mode: String = str(raw_snapshot.get("mode", "unselected"))
	if mode == "unselected":
		return _fail("mode_unselected", "Explicitly choose classic restart or practice checkpoint before save/load.")
	if not MODES.has(mode):
		return _fail("invalid_mode", "This death mode is not recognized.")
	var normalized_snapshot: Dictionary = _json_value(raw_snapshot)
	var normalized_identity: Dictionary = _json_value(raw_identity)
	if not normalized_snapshot.get("ok", false) or not normalized_identity.get("ok", false):
		return _fail("non_json_state", "The snapshot must contain bounded, lossless JSON values.")
	var identity: Dictionary = normalized_identity["value"]
	if not _keys_match(identity, IDENTITY_FIELDS) or identity.get("snapshot_schema") != STATE_SCHEMA:
		return _fail("runtime_identity_mismatch", "The runtime identity schema is not supported by this save version.")
	if not (identity["content_id"] is String) or str(identity["content_id"]).is_empty() or not _digest(identity["content_sha256"]) or not _digest(identity["rules_sha256"]):
		return _fail("runtime_identity_mismatch", "The runtime content and rules fingerprints must be explicit.")
	return {"ok": true, "snapshot": normalized_snapshot["value"], "identity": identity, "mode": mode}


static func _decode(runtime: Object, slot_id: String, text: String, context: Dictionary) -> Dictionary:
	var size: int = text.to_utf8_buffer().size()
	if size == 0 or size > MAX_BYTES:
		return _fail("invalid_payload_size", "The slot is empty or exceeds its bounded size.")
	var json: JSON = JSON.new()
	if json.parse(text) != OK or not (json.data is Dictionary):
		return _fail("invalid_json", "The slot is not a complete JSON object.")
	var normalized: Dictionary = _json_value(json.data)
	if not normalized.get("ok", false):
		return _fail("non_json_state", "The slot contains unsupported or imprecise JSON values.")
	var payload: Dictionary = normalized["value"]
	if not _keys_match(payload, ENVELOPE_FIELDS):
		return _fail("envelope_schema_mismatch", "Missing, unknown and future envelope fields are refused.")
	if payload["format_id"] != FORMAT_ID:
		return _fail("format_mismatch", "This is not a fifty-floor slot; no legacy migration was attempted.")
	if not (payload["save_version"] is int) or payload["save_version"] != SAVE_VERSION:
		return _fail("save_version_mismatch", "This save version is not supported; its bytes were preserved.")
	if payload["slot_id"] != slot_id:
		return _fail("slot_mismatch", "The payload belongs to a different explicit slot.")
	if payload["mode"] != context["mode"]:
		return _fail("mode_mismatch", "Choose the saved mode explicitly; load does not switch modes.")
	if not (payload["runtime_identity"] is Dictionary) or _canonical(payload["runtime_identity"]) != _canonical(context["identity"]):
		return _fail("identity_mismatch", "Content, rules, variant or snapshot identity differs.")
	if not (payload["snapshot"] is Dictionary) or not _digest(payload["snapshot_sha256"]) or not _digest(payload["payload_sha256"]):
		return _fail("invalid_integrity_fields", "The complete snapshot and its integrity fields are required.")
	if _canonical(payload["snapshot"]).sha256_text() != payload["snapshot_sha256"]:
		return _fail("snapshot_checksum_mismatch", "The snapshot checksum does not match.")
	var unhashed: Dictionary = payload.duplicate(true)
	unhashed.erase("payload_sha256")
	if _canonical(unhashed).sha256_text() != payload["payload_sha256"]:
		return _fail("payload_checksum_mismatch", "The slot checksum does not match.")
	var checked: Dictionary = _validate_candidate(runtime, payload["snapshot"], context)
	if not checked.get("ok", false):
		return checked
	return {"ok": true, "status": "decoded", "message": "Candidate fully prevalidated; no state or file changed.", "slot_id": slot_id, "mode": context["mode"], "snapshot": payload["snapshot"].duplicate(true), "bytes": size, "sha256": text.sha256_text(), "snapshot_sha256": payload["snapshot_sha256"]}


static func _validate_candidate(runtime: Object, candidate: Dictionary, context: Dictionary) -> Dictionary:
	if candidate.get("mode") != context["mode"]:
		return _fail("mode_mismatch", "The candidate does not match the explicitly selected mode.")
	for field: String in IDENTITY_FIELDS:
		if not candidate.has(field) or _canonical(candidate[field]) != _canonical(context["identity"][field]):
			return _fail("snapshot_identity_mismatch", "The full snapshot identity does not match its content and variant contract.")
	var checked: Variant = runtime.call("validate_snapshot", candidate.duplicate(true))
	if not (checked is Dictionary) or checked.get("ok", false) != true:
		return {"ok": false, "status": "snapshot_rejected", "message": "The runtime refused an invalid full-state candidate.", "reason": checked.get("status", "invalid_runtime_result") if checked is Dictionary else "invalid_runtime_result"}
	return {"ok": true}


static func _read_candidate(runtime: Object, slot_id: String, path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _fail("not_found" if not FileAccess.file_exists(path) else "read_failed", "This explicit slot could not be read.")
	var length: int = file.get_length()
	if length <= 0 or length > MAX_BYTES:
		file.close()
		return _fail("invalid_payload_size", "The slot is empty or exceeds its bounded size.")
	var bytes: PackedByteArray = file.get_buffer(length)
	file.close()
	if bytes.size() != length:
		return _fail("read_failed", "The complete slot bytes could not be read.")
	var text: String = bytes.get_string_from_utf8()
	if text.to_utf8_buffer() != bytes:
		return _fail("invalid_utf8", "The slot is not lossless UTF-8; its original bytes were preserved.")
	return decode_slot(runtime, slot_id, text)


static func _pending_failure(status: String, message: String, pending: String) -> Dictionary:
	# Only the exact temporary file created by this call is eligible for cleanup.
	# The authoritative slot is never removed, including after rename failure.
	var pending_absolute: String = ProjectSettings.globalize_path(pending).replace("\\", "/").simplify_path()
	var root_absolute: String = ProjectSettings.globalize_path(SLOT_ROOT).replace("\\", "/").simplify_path()
	var cleanup_ok: bool = false
	if pending_absolute.begins_with(root_absolute + "/") and pending_absolute.ends_with(".json.pending"):
		cleanup_ok = DirAccess.remove_absolute(pending_absolute) == OK
	return {"ok": false, "status": status, "message": message, "owned_pending_cleanup_ok": cleanup_ok}


static func _valid_slot(slot_id: String) -> bool:
	if slot_id.is_empty() or slot_id.length() > 32 or RESERVED_SLOTS.has(slot_id):
		return false
	for index: int in range(slot_id.length()):
		var character: String = slot_id.substr(index, 1)
		if not "abcdefghijklmnopqrstuvwxyz0123456789_-".contains(character):
			return false
		if index == 0 and not "abcdefghijklmnopqrstuvwxyz0123456789".contains(character):
			return false
	return true


static func _keys_match(value: Dictionary, expected: Array) -> bool:
	if value.size() != expected.size():
		return false
	for key: Variant in value:
		if not (key is String) or not expected.has(key):
			return false
	return true


static func _digest(value: Variant) -> bool:
	if not (value is String) or value.length() != 64:
		return false
	for index: int in range(value.length()):
		if not "0123456789abcdef".contains(value.substr(index, 1)):
			return false
	return true


static func _json_value(value: Variant, depth: int = 0) -> Dictionary:
	if depth > MAX_JSON_DEPTH:
		return {"ok": false}
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_STRING:
			return {"ok": true, "value": value}
		TYPE_INT:
			if value < -MAX_EXACT_INTEGER or value > MAX_EXACT_INTEGER:
				return {"ok": false}
			return {"ok": true, "value": value}
		TYPE_FLOAT:
			var number: float = value
			if not is_finite(number):
				return {"ok": false}
			if floor(number) == number:
				if number < -MAX_EXACT_INTEGER or number > MAX_EXACT_INTEGER:
					return {"ok": false}
				return {"ok": true, "value": int(number)}
			return {"ok": true, "value": number}
		TYPE_ARRAY:
			var array: Array = []
			for item: Variant in value:
				var normalized_item: Dictionary = _json_value(item, depth + 1)
				if not normalized_item.get("ok", false):
					return {"ok": false}
				array.append(normalized_item["value"])
			return {"ok": true, "value": array}
		TYPE_DICTIONARY:
			var object: Dictionary = {}
			for key: Variant in value:
				if not (key is String):
					return {"ok": false}
				var normalized_item: Dictionary = _json_value(value[key], depth + 1)
				if not normalized_item.get("ok", false):
					return {"ok": false}
				object[key] = normalized_item["value"]
			return {"ok": true, "value": object}
	return {"ok": false}


static func _canonical(value: Variant) -> String:
	return JSON.stringify(value, "", true, true)


static func _web_block() -> Dictionary:
	return _fail("blocked_web_persistence_unvalidated", "Durable Web storage and real-browser close/reopen have not been validated. No persistent-save success is claimed.")


static func _fail(status: String, message: String) -> Dictionary:
	return {"ok": false, "status": status, "message": message}
