extends RefCounted
## Web transport for the unchanged v1 full-snapshot envelope.
## IndexedDB commits are asynchronous; native slots and old files are never changed.

signal response_received

const Saves = preload("res://fifty/scripts/save.gd")
const Source = preload("res://fifty/view/indexeddb_source.gd")

var _api: Variant
var _callback: Variant
var _reply: Dictionary = {}
var _waiting := false


func write_slot(runtime: Object, slot_id: String) -> Dictionary:
	var encoded: Dictionary = Saves.encode_slot(runtime, slot_id)
	if not bool(encoded.get("ok", false)): return encoded
	var key: String = _key(encoded["payload"]["runtime_identity"], str(encoded["mode"]), slot_id)
	if key.is_empty(): return _fail("unsupported_content_profile")
	var existing: Dictionary = await _existing(runtime, slot_id, key, str(encoded["mode"]))
	if not bool(existing.get("ok", false)): return existing
	# A modal locks gameplay, but still refuse an asynchronously changed snapshot.
	var current: Dictionary = Saves.encode_slot(runtime, slot_id)
	if not bool(current.get("ok", false)) or current.get("sha256", "") != encoded["sha256"]:
		return _fail("web_runtime_changed")
	var expected: Variant = existing.get("text") if existing.get("status") == "read" else null
	var result: Dictionary = await _request("commit", key, expected, str(encoded["text"]))
	if bool(result.get("ok", false)):
		result["slot_id"] = slot_id
		result["mode"] = encoded["mode"]
		result["sha256"] = encoded["sha256"]
		result["snapshot_sha256"] = encoded["snapshot_sha256"]
	return result


func load_slot(runtime: Object, slot_id: String) -> Dictionary:
	# Reuse the same mode/identity/type checks before touching browser storage.
	var encoded: Dictionary = Saves.encode_slot(runtime, slot_id)
	if not bool(encoded.get("ok", false)): return encoded
	var key: String = _key(encoded["payload"]["runtime_identity"], str(encoded["mode"]), slot_id)
	if key.is_empty(): return _fail("unsupported_content_profile")
	var found: Dictionary = await _existing(runtime, slot_id, key, str(encoded["mode"]))
	if not bool(found.get("ok", false)): return found
	if found.get("status") == "not_found": return _fail("not_found")
	var decoded: Dictionary = Saves.decode_slot(runtime, slot_id, str(found["text"]))
	if not bool(decoded.get("ok", false)): return decoded
	# Import once, after complete envelope and runtime validation. A failed load
	# never replaces the live presenter runtime (the caller supplies a candidate).
	var imported: Variant = runtime.call("import_snapshot", decoded["snapshot"].duplicate(true))
	if not (imported is Dictionary) or imported.get("ok", false) != true:
		return _fail("import_rejected")
	return {"ok": true, "status": "loaded_web", "slot_id": slot_id,
		"mode": encoded["mode"], "sha256": decoded["sha256"],
		"snapshot_sha256": decoded["snapshot_sha256"], "migrated": found.get("migrated", false)}


func _existing(runtime: Object, slot_id: String, key: String, mode: String) -> Dictionary:
	var found: Dictionary = await _request("read", key)
	if not bool(found.get("ok", false)): return found
	if found.get("status") == "read":
		var existing_checked: Dictionary = Saves.decode_slot(runtime, slot_id, str(found.get("text", "")))
		if not bool(existing_checked.get("ok", false)):
			return {"ok": false, "status": "existing_slot_rejected", "reason": existing_checked.get("status", "invalid_payload")}
		return found
	if found.get("status") != "not_found": return _fail("web_invalid_reply")
	# Compatibility with a pre-existing current-format slot in Godot's mounted
	# user filesystem. Never inspect three-floor/chapter2/chapter3 save roots.
	var path: String = Saves.slot_path(slot_id, mode)
	if FileAccess.file_exists(path + ".pending"): return _fail("pending_exists")
	if not FileAccess.file_exists(path): return found
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null: return _fail("read_failed")
	var size: int = file.get_length()
	if size <= 0 or size > Saves.MAX_BYTES:
		file.close()
		return _fail("invalid_payload_size")
	var bytes: PackedByteArray = file.get_buffer(size)
	file.close()
	if bytes.size() != size: return _fail("read_failed")
	var text: String = bytes.get_string_from_utf8()
	if text.to_utf8_buffer() != bytes: return _fail("invalid_utf8")
	var checked: Dictionary = Saves.decode_slot(runtime, slot_id, text)
	if not bool(checked.get("ok", false)):
		return {"ok": false, "status": "existing_slot_rejected", "reason": checked.get("status", "invalid_payload")}
	# Add-only CAS migration; a competing browser tab wins without overwrite.
	var migrated: Dictionary = await _request("commit", key, null, text)
	if not bool(migrated.get("ok", false)):
		if migrated.get("status") == "web_conflict":
			var winner: Dictionary = await _request("read", key)
			if not bool(winner.get("ok", false)) or winner.get("status") != "read": return winner
			var winner_checked: Dictionary = Saves.decode_slot(runtime, slot_id, str(winner.get("text", "")))
			if not bool(winner_checked.get("ok", false)): return _fail("existing_slot_rejected")
			return winner
		return migrated
	return {"ok": true, "status": "read", "text": text, "migrated": true}


func _key(identity: Dictionary, mode: String, slot_id: String) -> String:
	if identity.get("content_id", "") != "stairkeep-fifty-slice/v1": return ""
	return str(identity["content_id"]) + "/" + mode + "/" + slot_id


func _request(operation: String, key: String, expected: Variant = null, text: String = "") -> Dictionary:
	if _waiting: return _fail("web_storage_busy")
	if not OS.has_feature("web") or not Engine.has_singleton("JavaScriptBridge"):
		return _fail("web_unavailable")
	var bridge: Object = Engine.get_singleton("JavaScriptBridge")
	if _api == null:
		bridge.call("eval", Source.SCRIPT, true)
		_api = bridge.call("get_interface", "StairkeepChapterOneStorageV1")
		if _api == null: return _fail("web_unavailable")
		if int(_api.contract) != 1:
			_api = null
			return _fail("web_unavailable")
	_waiting = true
	_reply = {}
	# Keep the JavaScriptObject alive through callback completion, as required
	# by JavaScriptBridge. The JavaScript operation owns its bounded timeout.
	_callback = bridge.call("create_callback", _receive)
	if _callback == null:
		_waiting = false
		return _fail("web_unavailable")
	if operation == "read":
		_api.read_slot(key, _callback)
	else:
		_api.commit_slot(key, expected, text, _callback)
	if _reply.is_empty(): await response_received
	var result: Dictionary = _reply.duplicate(true)
	_waiting = false
	_callback = null
	return result


func _receive(arguments: Array) -> void:
	if not _waiting or not _reply.is_empty(): return
	var decoded: Variant = JSON.parse_string(str(arguments[0])) if arguments.size() == 1 else null
	if not (decoded is Dictionary) or not (decoded.get("ok") is bool) or not (decoded.get("status") is String):
		_reply = _fail("web_invalid_reply")
	else:
		_reply = decoded
	# Resume callers after the JavaScript callback has returned. This also keeps
	# its reference alive until the next operation can replace it safely.
	call_deferred("_deliver")


func _deliver() -> void:
	response_received.emit()


func _fail(status: String) -> Dictionary:
	return {"ok": false, "status": status}
