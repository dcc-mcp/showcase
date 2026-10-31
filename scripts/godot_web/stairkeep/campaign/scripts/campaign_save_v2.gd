class_name CampaignSaveV2
extends RefCounted
## Native atomic storage only. A Web virtual-FS write is not a durability receipt.

const DEFAULT_PATH: String = "user://stairkeep-campaign-v2.json"
const MAX_BYTES: int = 4194304


static func write_atomic(path: String, serialized: String) -> Dictionary:
	if OS.has_feature("web"):
		return {"ok": false, "status": "blocked_web_persistence_unvalidated", "message": "A durable Web storage backend and actual-browser close/reopen check are not implemented. No persistent-save success is claimed."}
	if serialized.is_empty() or serialized.to_utf8_buffer().size() > MAX_BYTES:
		return {"ok": false, "status": "invalid_payload", "message": "Save is empty or exceeds the bounded native slot."}
	var final_path: String = ProjectSettings.globalize_path(path)
	var pending: String = final_path + ".pending"
	var file: FileAccess = FileAccess.open(pending, FileAccess.WRITE)
	if file == null:
		return {"ok": false, "status": "write_failed", "message": "Cannot open the pending save; the previous slot was not changed."}
	file.store_string(serialized)
	file.flush()
	var error: Error = file.get_error()
	file.close()
	if error != OK or FileAccess.get_file_as_string(pending) != serialized:
		return {"ok": false, "status": "write_failed", "message": "Pending-save verification failed; the previous slot was not changed."}
	# Same-directory rename is the only commit. Never unlink an existing save first.
	var renamed: Error = DirAccess.rename_absolute(pending, final_path)
	if renamed != OK:
		return {"ok": false, "status": "commit_failed", "message": "Atomic rename failed; no delete-and-rewrite fallback was attempted.", "error": int(renamed)}
	return {"ok": true, "status": "saved_native", "message": "Complete native snapshot committed by a same-directory rename.", "bytes": serialized.to_utf8_buffer().size(), "sha256": serialized.sha256_text()}


static func read_payload(path: String) -> Dictionary:
	if OS.has_feature("web"):
		return {"ok": false, "status": "blocked_web_persistence_unvalidated", "message": "The separate campaign Web persistence backend has not been accepted."}
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {"ok": false, "status": "not_found", "message": "No campaign save is available in this slot."}
	if file.get_length() > MAX_BYTES:
		file.close()
		return {"ok": false, "status": "invalid_payload", "message": "Save exceeds the bounded campaign slot."}
	var text: String = file.get_as_text()
	file.close()
	var json: JSON = JSON.new()
	if json.parse(text) != OK or not (json.data is Dictionary):
		return {"ok": false, "status": "invalid_json", "message": "Save is not a complete JSON object; existing bytes were preserved."}
	var payload: Dictionary = json.data
	if payload.get("schema_version", -1) == 1:
		return {"ok": false, "status": "legacy_v1", "message": "This is a three-floor Save v1. Continue it in the original slice or start a new campaign; no migration or overwrite occurred."}
	return {"ok": true, "status": "read", "payload": payload, "sha256": text.sha256_text()}
