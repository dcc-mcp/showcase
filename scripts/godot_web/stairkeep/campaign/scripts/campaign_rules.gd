class_name CampaignRules
extends RefCounted
## Campaign lifecycle around the frozen StairRules. Combat arithmetic lives only
## in base_rules.gd; terminal losses are explicit metadata, not fabricated HP writes.

const BaseRules = preload("res://scripts/base_rules.gd")
const VariantRules = preload("res://scripts/campaign_variant.gd")
const Storage = preload("res://scripts/campaign_save_v2.gd")
const CONTENT_ID: String = "stairkeep-campaign-21/v1"
const RULES_VERSION: String = "stairkeep-campaign-rules/v2-confirmed-loss-1"
const MAX_ATTEMPTS: int = 100000
const RULE_FILES: Array[String] = ["base_rules.gd", "campaign_variant.gd", "campaign_rules.gd", "campaign_save_v2.gd", "campaign_navigation.gd"]

var _core = BaseRules.new("")
var _canonical: Dictionary = {}
var _canonical_sha: String = ""
var _rules_sha: String = ""
var _transformed_sha: String = ""
var _root_seed: String = ""
var _campaign_seed: String = ""
var _sequence_state: String = ""
var _attempt_index: int = 0
var _mirrors: Dictionary = {}
var _resolved_start: Array = []
var _story_flags: Dictionary = {}
var _failed: bool = false
var _failure_reason: String = ""
var _failure_event_id: String = ""
var _terminal_hp: Variant = null
var _last_failure_event: Dictionary = {}
var _failure_events_seen: Array = []
var _consumed_loss_ids: Array = []
var _decision_index: int = 0
var _decision_hash: String = ""
var _decision_log: Array = []
var _checkpoint_id: String = ""
var _checkpoints: Array = []
var last_error: String = ""

# A snapshot getter is deliberately not an authority setter for search clients.
var state: Dictionary:
	get:
		return _core.snapshot()
var data: Dictionary:
	get:
		return _core.data


func _init(path: String = "", seed: Variant = 20261025) -> void:
	if not path.is_empty():
		load_campaign(path, seed)


func load_data(path: String = "res://data/levels21.json") -> bool:
	return bool(load_campaign(path, _root_seed if not _root_seed.is_empty() else "013528a1")["ok"])


func load_campaign(path: String = "res://data/levels21.json", seed: Variant = 20261025) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return _error("content_unavailable", "Campaign data could not be opened.")
	var json: JSON = JSON.new()
	if json.parse(file.get_as_text()) != OK or not (json.data is Dictionary):
		return _error("invalid_content", "Campaign data is not a complete JSON object.")
	return start_campaign(json.data, seed)


func start_campaign(canonical: Dictionary, seed: Variant = 20261025) -> Dictionary:
	if str(canonical.get("content_id", "")) != CONTENT_ID:
		return _error("content_mismatch", "This independent rules object only accepts the 21-floor campaign content ID.")
	var generated: Dictionary = VariantRules.generate(canonical, seed)
	if not bool(generated.get("ok", false)):
		return _error("invalid_variant", str(generated.get("message", generated.get("errors", "Variant validation failed."))))
	var fingerprint: String = rules_fingerprint()
	if fingerprint.is_empty():
		return _error("rules_unavailable", "Cannot hash all campaign rule sources; no version binding was invented.")
	_canonical = canonical.duplicate(true)
	_canonical_sha = str(generated["canonical_sha256"])
	_rules_sha = fingerprint
	_root_seed = str(generated["seed"])
	_campaign_seed = _root_seed
	_sequence_state = _root_seed
	_attempt_index = 0
	_failure_events_seen = []
	_consumed_loss_ids = []
	_install_variant(generated)
	return _result(true, "campaign_started", "A separately versioned campaign was initialized.")


func _install_variant(generated: Dictionary) -> void:
	_core = BaseRules.new("")
	_core.data = generated["data"]
	_core.reset()
	# Search clones share this content tree. Seal every nested container once,
	# rather than exposing a mutable alias or copying the campaign on each read.
	_freeze_content(_core.data)
	_mirrors = generated["mirrors"].duplicate(true)
	_resolved_start = generated["resolved_start"].duplicate()
	_transformed_sha = str(generated["transformed_sha256"])
	_story_flags = {}
	_failed = false
	_failure_reason = ""
	_failure_event_id = ""
	_terminal_hp = null
	_last_failure_event = {}
	_decision_index = 0
	_decision_hash = _initial_log_hash(_root_seed, _campaign_seed, _attempt_index)
	_decision_log = []
	_checkpoint_id = ""
	_checkpoints = []
	_capture_chapter_entry()
	last_error = ""


func reset() -> Dictionary:
	return restart_same_seed()


func new_game() -> Dictionary:
	return restart_same_seed()


func restart_same_seed() -> Dictionary:
	if _canonical.is_empty():
		return _error("not_loaded", "No campaign is loaded.")
	var generated: Dictionary = VariantRules.generate(_canonical, _campaign_seed)
	if not bool(generated.get("ok", false)):
		return _error("invalid_variant", "The same seed could not be regenerated; the active state was preserved.")
	_install_variant(generated)
	return _result(true, "restarted_same_seed", "Initial resources, world and stock restored. Seed, sequence and attempt index did not change.")


func respawn_new_variant(confirmed: bool, loss_id: String) -> Dictionary:
	if not confirmed:
		return _error("confirmation_required", "A new variant requires explicit confirmation of the displayed loss ID.")
	if not _failed or loss_id.is_empty() or loss_id != _failure_event_id or _consumed_loss_ids.has(loss_id):
		return _error("stale_loss_id", "This loss is not the active unconsumed failure. The sequence was not advanced.")
	if _attempt_index >= MAX_ATTEMPTS:
		return _error("attempt_limit", "The bounded sequence index is exhausted.")
	var next_seed: String = "%08x" % VariantRules.next32(_sequence_state.hex_to_int())
	var generated: Dictionary = VariantRules.generate(_canonical, next_seed)
	if not bool(generated.get("ok", false)):
		return _error("invalid_variant", "New variant validation failed. The old failure and sequence were preserved.")
	_consumed_loss_ids.append(loss_id)
	_sequence_state = next_seed
	_campaign_seed = next_seed
	_attempt_index += 1
	_install_variant(generated)
	return _result(true, "respawned_new_variant", "The sequence advanced exactly once and the whole expedition restarted at its safe first-floor spawn.")


func is_failed() -> bool:
	return _failed


func is_active() -> bool:
	return not _canonical.is_empty() and not _failed and not bool(_core.state.get("won", false))


func inspect(cell: Array) -> Dictionary:
	return _core.inspect(cell)


func combat(enemy: Dictionary) -> Dictionary:
	return _core.combat(enemy)


func floor_data() -> Dictionary:
	return _core.floor_data()


func object_at(cell: Array, include_cleared: bool = false) -> Dictionary:
	return _core.object_at(cell, include_cleared)


func walkable(cell: Variant, floor_index: int = -1) -> bool:
	return _core.walkable(cell, floor_index)


func move(dx: int, dy: int) -> Dictionary:
	var destination: Array = [int(_core.state.get("pos", [0, 0])[0]) + dx, int(_core.state.get("pos", [0, 0])[1]) + dy]
	return _perform("move", {"dx": dx, "dy": dy}, destination)


func interact(cell: Array) -> Dictionary:
	return _perform("interact", {"cell": cell.duplicate()}, cell)


func use_stairs() -> Dictionary:
	return _perform("use_stairs", {}, _core.state.get("pos", []).duplicate())


func buy(choice: String) -> Dictionary:
	return _perform("buy", {"choice": choice}, [])


func _perform(command: String, arguments: Dictionary, destination: Array) -> Dictionary:
	if not is_active():
		return _error("terminal" if _failed else "not_active", "This expedition cannot take actions. Inspect it, restore a checkpoint, or choose a complete restart.")
	var before: Dictionary = _core.snapshot()
	var item: Dictionary = _core.object_at(destination) if destination.size() == 2 else {}
	var result: Dictionary
	match command:
		"move": result = _core.move(int(arguments["dx"]), int(arguments["dy"]))
		"interact": result = _core.interact(destination)
		"use_stairs": result = _core.use_stairs()
		"buy": result = _core.buy(str(arguments["choice"]))
		_: return _error("unknown_command", "Unknown campaign command.")
	if bool(result.get("ok", false)) and _resource_signature(before) != _resource_signature(_core.state):
		_record(command, {"input": arguments, "object_id": item.get("id", ""), "action": result.get("action", "")}, before, _core.snapshot())
	if bool(result.get("ok", false)) and result.get("action", "") == "stairs":
		_capture_chapter_entry()
	result["failed"] = _failed
	result["campaign_seed"] = _campaign_seed
	return result


func challenge_enemy(cell: Array, confirmed: bool = false) -> Dictionary:
	if not is_active():
		return _error("not_active", "No active campaign can accept a challenge.")
	if cell.size() != 2 or absi(int(cell[0]) - int(_core.state["pos"][0])) + absi(int(cell[1]) - int(_core.state["pos"][1])) != 1:
		return _error("not_adjacent", "Unsafe challenges still require an adjacent enemy.")
	var item: Dictionary = _core.object_at(cell)
	if item.get("kind", "") != "enemy":
		return _error("not_enemy", "There is no adjacent enemy at that tile.")
	var preview: Dictionary = _core.combat(_core.data["enemies"][item["type"]])
	if bool(preview["win"]):
		return interact(cell)
	if int(preview["damage"]) < 0:
		return _error("armor_impenetrable", "An attack that cannot penetrate armor has no finite combat outcome and cannot be executed.")
	if not confirmed:
		var pending: Dictionary = _error("confirmation_required", "This challenge is lethal. It is not executed without explicit confirmation.")
		pending["combat"] = preview
		pending["terminal_hp"] = int(_core.state["hp"]) - int(preview["damage"])
		return pending
	var before: Dictionary = _core.snapshot()
	var terminal: int = int(before["hp"]) - int(preview["damage"])
	_record("unsafe_challenge", {"cell": cell.duplicate(), "object_id": item["id"], "preview": preview, "terminal_hp": terminal}, before, before)
	return _mark_failure("combat_death", {"object_id": item["id"], "cell": cell.duplicate(), "combat": preview, "terminal_hp": terminal, "core_state": before})


func assess_failure(max_nodes: int = 0) -> Dictionary:
	if _failed:
		return _result(true, "already_failed", "The existing failure was retained; no count or seed changed.")
	if not is_active():
		return _result(true, "won" if bool(_core.state.get("won", false)) else "not_loaded", "No active failure assessment is needed.")
	var navigation: Script = load("res://scripts/campaign_navigation.gd")
	if navigation == null:
		return _error("unknown", "Navigation coverage is unavailable, so no loss was declared.")
	var frontier: Dictionary = navigation.frontier(self, max_nodes, true)
	if not bool(frontier.get("complete", false)):
		return {"ok": true, "action": "unknown", "result": "unknown", "failed": false, "frontier": frontier, "message": "Navigation was not exhausted; this is not a loss proof."}
	if not frontier.get("options", []).is_empty():
		return {"ok": true, "action": "actions_available", "result": "actions_available", "failed": false, "frontier": frontier}
	return _mark_failure("resource_exhausted", {"core_state": _core.snapshot(), "frontier": frontier})


func mark_loss_proven(receipt: Dictionary) -> Dictionary:
	if not is_active():
		return _error("not_active", "A terminal or unloaded campaign cannot accept a solver result.")
	if not _valid_loss_receipt(receipt):
		return _error("unbound_solver_result", "The solver result is incomplete or belongs to another exact state/version. Unknown is never converted to loss.")
	return _mark_failure("loss_proven", {"core_state": _core.snapshot(), "solver_receipt": receipt.duplicate(true)})


func _mark_failure(reason: String, evidence: Dictionary) -> Dictionary:
	if _failed:
		return _result(true, "already_failed", "This failure was already counted.")
	_failure_event_id = VariantRules.content_hash({"content": _canonical_sha, "rules": _rules_sha, "variant": _transformed_sha, "seed": _campaign_seed, "attempt": _attempt_index, "decision_hash": _decision_hash, "reason": reason, "state": _core.snapshot()})
	_failed = true
	_failure_reason = reason
	_terminal_hp = evidence.get("terminal_hp", null)
	_last_failure_event = evidence.duplicate(true)
	_last_failure_event["reason"] = reason
	_last_failure_event["event_id"] = _failure_event_id
	if not _failure_events_seen.has(_failure_event_id):
		_failure_events_seen.append(_failure_event_id)
	return _result(true, "failed", "Combat death and exhausted resources are distinct recorded reasons. No seed was advanced.")


func _record(command: String, arguments: Dictionary, before: Dictionary, after: Dictionary) -> void:
	_decision_index += 1
	var record: Dictionary = {"decision_index": _decision_index, "command": command, "arguments": arguments.duplicate(true), "before_sha256": VariantRules.content_hash(before), "after_sha256": VariantRules.content_hash(after), "after_budget": _budget(after)}
	_decision_log.append(record)
	_decision_hash = (_decision_hash + "\n" + VariantRules.canonical_json(record)).sha256_text()


func _capture_chapter_entry() -> void:
	var floor_id: int = int(_core.floor_data().get("id", 0))
	if floor_id < 1 or (floor_id - 1) % 3 != 0:
		return
	var id: String = "chapter-%02d/attempt-%d" % [floor_id, _attempt_index]
	for checkpoint: Dictionary in _checkpoints:
		if checkpoint.get("checkpoint_id", "") == id:
			return
	_checkpoint_id = id
	_checkpoints.append(_snapshot(false))


func restore_checkpoint(id: String) -> bool:
	for index: int in range(_checkpoints.size()):
		var checkpoint: Dictionary = _checkpoints[index]
		if checkpoint.get("checkpoint_id", "") == id:
			# Restoring an earlier timeline drops later entry snapshots. Keeping
			# them would make the restored log older than its own checkpoints.
			var kept: Array = _checkpoints.slice(0, index + 1).duplicate(true)
			var seen: Array = _failure_events_seen.duplicate()
			var consumed: Array = _consumed_loss_ids.duplicate()
			if not restore_snapshot(checkpoint):
				return false
			_checkpoints = kept
			_failure_events_seen = seen
			_consumed_loss_ids = consumed
			return true
	last_error = "Unknown checkpoint; no state changed."
	return false


func snapshot() -> Dictionary:
	return campaign_snapshot()


func campaign_snapshot() -> Dictionary:
	return _snapshot(true)


func _snapshot(include_checkpoints: bool) -> Dictionary:
	return {
		"schema_version": 2, "content_id": CONTENT_ID, "canonical_content_sha256": _canonical_sha,
		"rules_version": RULES_VERSION, "rules_sha256": _rules_sha, "variant_spec": VariantRules.SPEC,
		"root_seed": _root_seed, "campaign_seed": _campaign_seed, "sequence_state": _sequence_state,
		"attempt_index": _attempt_index, "variant_draw_count": 43,
		"floor_mirrors": _mirrors.duplicate(true), "resolved_start": _resolved_start.duplicate(), "transformed_content_sha256": _transformed_sha,
		"core_state": _core.snapshot(), "story_flags": _story_flags.duplicate(true),
		"failed": _failed, "failure_reason": _failure_reason, "failure_event_id": _failure_event_id,
		"terminal_hp": _terminal_hp, "last_failure_event": _last_failure_event.duplicate(true),
		"failure_events_seen": _failure_events_seen.duplicate(), "consumed_loss_ids": _consumed_loss_ids.duplicate(),
		"decision_index": _decision_index, "decision_log_hash": _decision_hash, "decision_log": _decision_log.duplicate(true),
		"checkpoint_id": _checkpoint_id, "checkpoints": _checkpoints.duplicate(true) if include_checkpoints else [],
	}


func restore_snapshot(saved: Dictionary) -> bool:
	# Rebuild and validate in a different object. Rejection cannot partly mutate this one.
	var candidate = get_script().new()
	var check: Dictionary = candidate._restore_candidate(_canonical, saved, true)
	if not bool(check.get("ok", false)):
		last_error = str(check.get("message", "Snapshot validation failed."))
		return false
	_copy_runtime(candidate)
	return true


func clone_for_search() -> RefCounted:
	var clone = get_script().new()
	clone._copy_runtime(self)
	return clone


func _copy_runtime(other: RefCounted) -> void:
	_canonical = other._canonical
	_canonical_sha = other._canonical_sha
	_rules_sha = other._rules_sha
	_transformed_sha = other._transformed_sha
	_root_seed = other._root_seed
	_campaign_seed = other._campaign_seed
	_sequence_state = other._sequence_state
	_attempt_index = other._attempt_index
	_mirrors = other._mirrors.duplicate(true)
	_resolved_start = other._resolved_start.duplicate()
	_core = BaseRules.new("")
	_core.data = other._core.data
	_core.state = other._core.snapshot()
	_story_flags = other._story_flags.duplicate(true)
	_failed = other._failed
	_failure_reason = other._failure_reason
	_failure_event_id = other._failure_event_id
	_terminal_hp = other._terminal_hp
	_last_failure_event = other._last_failure_event.duplicate(true)
	_failure_events_seen = other._failure_events_seen.duplicate()
	_consumed_loss_ids = other._consumed_loss_ids.duplicate()
	_decision_index = other._decision_index
	_decision_hash = other._decision_hash
	_decision_log = other._decision_log.duplicate(true)
	_checkpoint_id = other._checkpoint_id
	_checkpoints = other._checkpoints.duplicate(true)
	last_error = ""


func _restore_candidate(canonical: Dictionary, saved: Dictionary, validate_checkpoints: bool) -> Dictionary:
	if canonical.is_empty() or saved.get("schema_version", -1) != 2:
		return _error("invalid_schema", "Only Save v2 for the already selected campaign may load; v1 was not migrated.")
	for field: String in ["content_id", "canonical_content_sha256", "rules_version", "rules_sha256", "variant_spec", "root_seed", "campaign_seed", "sequence_state", "transformed_content_sha256", "decision_log_hash", "checkpoint_id", "failure_reason", "failure_event_id"]:
		if not (saved.get(field) is String):
			return _error("invalid_schema", "Missing or non-string v2 field: " + field)
	if saved["content_id"] != CONTENT_ID or saved["canonical_content_sha256"] != VariantRules.content_hash(canonical) or saved["rules_version"] != RULES_VERSION or saved["rules_sha256"] != rules_fingerprint() or saved["variant_spec"] != VariantRules.SPEC:
		return _error("version_mismatch", "Content, rules or variant specification does not match. The save was preserved.")
	for field: String in ["attempt_index", "variant_draw_count", "decision_index"]:
		if not _whole(saved.get(field)) or int(saved[field]) < 0:
			return _error("invalid_schema", "Invalid integral v2 field: " + field)
	if int(saved["attempt_index"]) > MAX_ATTEMPTS or int(saved["variant_draw_count"]) != 43 or int(saved["decision_index"]) > 100000:
		return _error("invalid_sequence", "Sequence or decision count is outside the bounded schema.")
	for field: String in ["root_seed", "campaign_seed", "sequence_state"]:
		if VariantRules.normalize_seed(saved[field]) != saved[field]:
			return _error("invalid_seed", "Seed fields must contain normalized eight-character lowercase hex.")
	var expected_seed: int = str(saved["root_seed"]).hex_to_int()
	for step: int in range(int(saved["attempt_index"])):
		expected_seed = VariantRules.next32(expected_seed)
	if str(saved["campaign_seed"]) != "%08x" % expected_seed or saved["sequence_state"] != saved["campaign_seed"]:
		return _error("invalid_sequence", "The current seed is not the declared root-seed sequence element.")
	var generated: Dictionary = VariantRules.generate(canonical, saved["campaign_seed"])
	if not bool(generated.get("ok", false)) or saved["transformed_content_sha256"] != generated.get("transformed_sha256", "") or VariantRules.canonical_json(saved.get("floor_mirrors")) != VariantRules.canonical_json(generated["mirrors"]) or VariantRules.canonical_json(saved.get("resolved_start")) != VariantRules.canonical_json(generated["resolved_start"]):
		return _error("variant_mismatch", "Stored mirrors or spawn differ from regeneration of the same seed.")
	if not (saved.get("core_state") is Dictionary) or not (saved.get("story_flags") is Dictionary) or not saved["story_flags"].is_empty():
		return _error("invalid_state", "Core state is absent or unsupported story flags were supplied.")
	if not (saved.get("failed") is bool) or not (saved.get("last_failure_event") is Dictionary) or not (saved.get("failure_events_seen") is Array) or not (saved.get("consumed_loss_ids") is Array) or not (saved.get("decision_log") is Array) or not (saved.get("checkpoints") is Array):
		return _error("invalid_schema", "Failure, history and checkpoint fields have invalid types.")
	if not saved.has("terminal_hp"):
		return _error("invalid_schema", "The terminal_hp field must explicitly contain an integer or null.")
	var start_result: Dictionary = start_campaign(canonical, saved["campaign_seed"])
	if not bool(start_result["ok"]):
		return start_result
	if not _core._valid_state(saved["core_state"]) or not _within_resource_bounds(saved["core_state"]):
		return _error("invalid_state", "Resources, objects, stock or position are outside the campaign bounds.")
	_core.state = saved["core_state"].duplicate(true)
	_normalize_core()
	_root_seed = saved["root_seed"]
	_sequence_state = saved["sequence_state"]
	_attempt_index = int(saved["attempt_index"])
	var seen: Array = saved["failure_events_seen"]
	var consumed: Array = saved["consumed_loss_ids"]
	if not _unique_hashes(seen) or not _unique_hashes(consumed):
		return _error("invalid_history", "Failure IDs must be unique SHA-256 strings.")
	if consumed.size() != _attempt_index:
		return _error("invalid_history", "Every sequence advance must have exactly one distinct confirmed loss ID.")
	for id: String in consumed:
		if not seen.has(id):
			return _error("invalid_history", "A consumed loss must occur in the retained failure history.")
	var failed: bool = saved["failed"]
	var reason: String = saved["failure_reason"]
	if failed:
		if bool(_core.state["won"]) or not ["combat_death", "resource_exhausted", "loss_proven"].has(reason) or not seen.has(saved["failure_event_id"]):
			return _error("invalid_failure", "Failure flags, reason and stable event ID are inconsistent.")
		var event: Dictionary = saved["last_failure_event"]
		if event.get("reason", "") != reason or event.get("event_id", "") != saved["failure_event_id"] or VariantRules.content_hash(event.get("core_state", {})) != VariantRules.content_hash(_core.state):
			return _error("invalid_failure", "Failure evidence belongs to a different core state.")
		var expected_failure_id: String = VariantRules.content_hash({"content": _canonical_sha, "rules": _rules_sha, "variant": _transformed_sha, "seed": _campaign_seed, "attempt": _attempt_index, "decision_hash": saved["decision_log_hash"], "reason": reason, "state": _core.snapshot()})
		if saved["failure_event_id"] != expected_failure_id:
			return _error("invalid_failure", "The stable failure ID does not match this exact state and decision history.")
		if reason == "combat_death":
			var item: Dictionary = _object_by_id(str(event.get("object_id", "")))
			var adjacent: bool = item.has("pos") and absi(int(item["pos"][0]) - int(_core.state["pos"][0])) + absi(int(item["pos"][1]) - int(_core.state["pos"][1])) == 1
			if item.get("kind", "") != "enemy" or not adjacent or _core.state["cleared"].has(str(item.get("id", ""))) or not _whole(saved.get("terminal_hp")):
				return _error("invalid_failure", "Combat death lacks its actual finite enemy preview.")
			var preview: Dictionary = _core.combat(_core.data["enemies"][item["type"]])
			if bool(preview["win"]) or int(preview["damage"]) < 0 or int(saved["terminal_hp"]) != int(_core.state["hp"]) - int(preview["damage"]) or int(saved["terminal_hp"]) > 0 or VariantRules.content_hash(event.get("combat", {})) != VariantRules.content_hash(preview):
				return _error("invalid_failure", "Terminal HP does not equal the authoritative combat preview.")
		elif saved.get("terminal_hp") != null:
			return _error("invalid_failure", "Resource/proven losses cannot invent terminal combat HP.")
		elif reason == "resource_exhausted":
			var navigation: Script = load("res://scripts/campaign_navigation.gd")
			var frontier: Dictionary = navigation.frontier(self, 0, false)
			if not bool(frontier.get("complete", false)) or not frontier.get("options", []).is_empty():
				return _error("invalid_failure", "The restored state still has a legal resource action; resource exhaustion was not proven.")
		elif reason == "loss_proven" and (not (event.get("solver_receipt") is Dictionary) or not _valid_loss_receipt(event["solver_receipt"])):
			return _error("invalid_failure", "The retained solver receipt does not bind an exhaustive result to the exact active state.")
	else:
		if not reason.is_empty() or not str(saved["failure_event_id"]).is_empty() or saved.get("terminal_hp") != null or not saved["last_failure_event"].is_empty():
			return _error("invalid_failure", "An active/won state contains stale failure metadata.")
	if not _valid_log(saved["decision_log"], int(saved["decision_index"]), saved["decision_log_hash"], _root_seed, _campaign_seed, _attempt_index):
		return _error("invalid_history", "Decision log index or hash chain is invalid.")
	_failed = failed
	_failure_reason = reason
	_failure_event_id = saved["failure_event_id"]
	_terminal_hp = int(saved["terminal_hp"]) if saved.get("terminal_hp") != null else null
	_last_failure_event = saved["last_failure_event"].duplicate(true)
	_failure_events_seen = seen.duplicate()
	_consumed_loss_ids = consumed.duplicate()
	_decision_index = int(saved["decision_index"])
	_decision_hash = saved["decision_log_hash"]
	_decision_log = saved["decision_log"].duplicate(true)
	_checkpoint_id = saved["checkpoint_id"]
	_checkpoints = []
	if validate_checkpoints:
		var checkpoint_ids: Dictionary = {}
		if saved["checkpoints"].size() > 7:
			return _error("invalid_checkpoint", "Only one full entry checkpoint per chapter is allowed.")
		for checkpoint: Variant in saved["checkpoints"]:
			if not (checkpoint is Dictionary) or checkpoint_ids.has(checkpoint.get("checkpoint_id", "")) or not checkpoint.get("checkpoints", []).is_empty():
				return _error("invalid_checkpoint", "Checkpoint ID is duplicated or contains recursive history.")
			var candidate = get_script().new()
			var checked: Dictionary = candidate._restore_candidate(canonical, checkpoint, false)
			if not bool(checked.get("ok", false)) or checkpoint.get("campaign_seed", "") != _campaign_seed or checkpoint.get("root_seed", "") != _root_seed or int(checkpoint.get("attempt_index", -1)) != _attempt_index or bool(checkpoint.get("failed", true)) or int(checkpoint.get("decision_index", -1)) > _decision_index:
				return _error("invalid_checkpoint", "Checkpoint version/seed/state is invalid or newer than the active state.")
			var floor_id: int = int(candidate.floor_data().get("id", 0))
			var expected_id: String = "chapter-%02d/attempt-%d" % [floor_id, _attempt_index]
			if floor_id < 1 or (floor_id - 1) % 3 != 0 or checkpoint["checkpoint_id"] != expected_id or VariantRules.canonical_json(checkpoint["decision_log"]) != VariantRules.canonical_json(_decision_log.slice(0, int(checkpoint["decision_index"]))):
				return _error("invalid_checkpoint", "Checkpoint does not belong to an entry on this decision-history prefix.")
			checkpoint_ids[checkpoint["checkpoint_id"]] = true
			_checkpoints.append(checkpoint.duplicate(true))
	return {"ok": true}


func _within_resource_bounds(candidate: Dictionary) -> bool:
	var limits: Dictionary = {"hp": int(_canonical["initial_player"]["hp"]), "atk": int(_canonical["initial_player"]["atk"]), "def": int(_canonical["initial_player"]["def"]), "gold": int(_canonical["initial_player"].get("gold", 0))}
	var keys: Dictionary = _canonical["initial_player"]["keys"].duplicate(true)
	for floor_item: Dictionary in _canonical["floors"]:
		for item: Dictionary in floor_item["objects"]:
			var kind: String = str(item["kind"])
			if kind in ["potion", "atk", "def", "gold"]:
				var stat: String = "hp" if kind == "potion" else kind
				limits[stat] = int(limits[stat]) + int(item.get("amount", 1))
			elif kind == "key":
				keys[item["type"]] = int(keys.get(item["type"], 0)) + int(item.get("amount", 1))
			elif kind == "enemy":
				limits["gold"] = int(limits["gold"]) + int(_canonical["enemies"][item["type"]].get("gold", 0))
			elif kind == "shop":
				for offer: Dictionary in _canonical["shops"][item["type"]]["offers"]:
					var stat: String = "hp" if offer["kind"] == "potion" else str(offer["kind"])
					limits[stat] = int(limits[stat]) + int(offer["amount"]) * int(offer.get("limit", 1))
	for stat: String in limits:
		if int(candidate[stat]) > int(limits[stat]):
			return false
	for color: String in keys:
		if int(candidate["keys"][color]) > int(keys[color]):
			return false
	return true


func _normalize_core() -> void:
	for stat: String in ["floor", "hp", "atk", "def", "gold"]:
		_core.state[stat] = int(_core.state[stat])
	_core.state["pos"] = [int(_core.state["pos"][0]), int(_core.state["pos"][1])]
	for color: String in _core.state["keys"]:
		_core.state["keys"][color] = int(_core.state["keys"][color])
	for purchase: String in _core.state["purchases"]:
		_core.state["purchases"][purchase] = int(_core.state["purchases"][purchase])


func _object_by_id(id: String) -> Dictionary:
	for item: Dictionary in _core.floor_data().get("objects", []):
		if str(item["id"]) == id:
			return item
	return {}


func _valid_log(log: Array, count: int, expected: String, root: String, seed: String, attempt: int) -> bool:
	if log.size() != count:
		return false
	var value: String = _initial_log_hash(root, seed, attempt)
	for index: int in range(log.size()):
		var record: Variant = log[index]
		if not (record is Dictionary) or not _whole(record.get("decision_index")) or int(record["decision_index"]) != index + 1 or not (record.get("command") is String) or not (record.get("arguments") is Dictionary) or not _is_hash(record.get("before_sha256")) or not _is_hash(record.get("after_sha256")) or not (record.get("after_budget") is Dictionary):
			return false
		value = (value + "\n" + VariantRules.canonical_json(record)).sha256_text()
	return value == expected


func _initial_log_hash(root: String, seed: String, attempt: int) -> String:
	return VariantRules.content_hash({"content": _canonical_sha, "rules": _rules_sha, "root_seed": root, "campaign_seed": seed, "attempt_index": attempt, "log_version": 1})


func current_state_sha256() -> String:
	return VariantRules.content_hash({"canonical": _canonical_sha, "rules": _rules_sha, "variant": _transformed_sha, "seed": _campaign_seed, "core_state": _core.snapshot(), "failed": _failed, "story_flags": _story_flags})


func _valid_loss_receipt(receipt: Dictionary) -> bool:
	return receipt.get("status", "") == "unsatisfiable" and receipt.get("complete") is bool and bool(receipt["complete"]) and receipt.get("state_sha256", "") == current_state_sha256() and receipt.get("canonical_content_sha256", "") == _canonical_sha and receipt.get("transformed_content_sha256", "") == _transformed_sha and receipt.get("rules_sha256", "") == _rules_sha


static func rules_fingerprint() -> String:
	var hashes: Dictionary = {}
	for leaf: String in RULE_FILES:
		var path: String = "res://scripts/" + leaf
		if not FileAccess.file_exists(path):
			return ""
		var bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
		if bytes.is_empty():
			return ""
		var hash: HashingContext = HashingContext.new()
		hash.start(HashingContext.HASH_SHA256)
		hash.update(bytes)
		hashes[leaf] = hash.finish().hex_encode()
	return VariantRules.content_hash(hashes)


func save_v2(path: String = Storage.DEFAULT_PATH) -> Dictionary:
	var snapshot_value: Dictionary = campaign_snapshot()
	var checked = get_script().new()
	var validation: Dictionary = checked._restore_candidate(_canonical, snapshot_value, true)
	if not bool(validation.get("ok", false)):
		return _error("invalid_snapshot", str(validation.get("message", "Snapshot is not valid; no file was written.")))
	var payload: Dictionary = snapshot_value.duplicate(true)
	var core: Dictionary = payload["core_state"]
	var serialized_state: Dictionary = {"floor": core["floor"], "pos": core["pos"], "hp": core["hp"], "atk": core["atk"], "def": core["def"], "gold": core["gold"], "keys_by_color": core["keys"], "cleared_object_ids": core["cleared"], "purchase_counts_by_shop_and_offer": core["purchases"], "story_flags": payload["story_flags"], "won": core["won"], "failed": payload["failed"], "failure_reason": payload["failure_reason"], "failure_event_id": payload["failure_event_id"], "terminal_hp": payload["terminal_hp"], "last_failure_event": payload["last_failure_event"]}
	payload.erase("core_state")
	for key: String in ["story_flags", "failed", "failure_reason", "failure_event_id", "terminal_hp", "last_failure_event"]:
		payload.erase(key)
	payload["state"] = serialized_state
	return Storage.write_atomic(path, VariantRules.canonical_json(payload))


func save_game(path: String = Storage.DEFAULT_PATH) -> bool:
	return bool(save_v2(path).get("ok", false))


func load_v2(path: String = Storage.DEFAULT_PATH) -> Dictionary:
	var read: Dictionary = Storage.read_payload(path)
	if not bool(read.get("ok", false)):
		return read
	var payload: Dictionary = read["payload"]
	if not (payload.get("state") is Dictionary):
		return _error("invalid_schema", "Save v2 state is missing; no current state changed.")
	var saved: Dictionary = payload["state"]
	var core: Dictionary = {}
	for field: String in ["floor", "pos", "hp", "atk", "def", "gold", "won"]:
		if not saved.has(field):
			return _error("invalid_schema", "Save v2 core field is missing: " + field)
		core[field] = saved[field]
	for pair: Array in [["keys", "keys_by_color"], ["cleared", "cleared_object_ids"], ["purchases", "purchase_counts_by_shop_and_offer"]]:
		if not saved.has(pair[1]):
			return _error("invalid_schema", "Save v2 resource field is missing: " + str(pair[1]))
		core[pair[0]] = saved[pair[1]]
	payload["core_state"] = core
	for field: String in ["story_flags", "failed", "failure_reason", "failure_event_id", "terminal_hp", "last_failure_event"]:
		if not saved.has(field):
			return _error("invalid_schema", "Save v2 metadata field is missing: " + field)
		payload[field] = saved[field]
	payload.erase("state")
	if not restore_snapshot(payload):
		return _error("rejected", last_error)
	return _result(true, "loaded_v2", "The complete same-seed snapshot was independently rebuilt and restored.")


func load_game(path: String = Storage.DEFAULT_PATH) -> bool:
	return bool(load_v2(path).get("ok", false))


func _result(ok: bool, action: String, message: String) -> Dictionary:
	return {"ok": ok, "action": action, "result": action, "message": message, "state": _core.snapshot(), "failed": _failed, "failure_reason": _failure_reason, "failure_event_id": _failure_event_id, "terminal_hp": _terminal_hp, "failure_count": _failure_events_seen.size(), "campaign_seed": _campaign_seed, "sequence_state": _sequence_state, "attempt_index": _attempt_index}


func _error(action: String, message: String) -> Dictionary:
	last_error = message
	return _result(false, action, message)


func _resource_signature(value: Dictionary) -> String:
	return VariantRules.content_hash({"hp": value["hp"], "atk": value["atk"], "def": value["def"], "gold": value["gold"], "keys": value["keys"], "cleared": value["cleared"], "purchases": value["purchases"], "won": value["won"]})


func _freeze_content(value: Variant) -> void:
	if value is Dictionary:
		for child: Variant in value.values():
			_freeze_content(child)
		value.make_read_only()
	elif value is Array:
		for child: Variant in value:
			_freeze_content(child)
		value.make_read_only()


func _budget(value: Dictionary) -> Dictionary:
	return {"hp": int(value["hp"]), "atk": int(value["atk"]), "def": int(value["def"]), "gold": int(value["gold"]), "keys": value["keys"].duplicate(true), "purchases": value["purchases"].duplicate(true)}


func _is_hash(value: Variant) -> bool:
	if not (value is String) or value.length() != 64:
		return false
	for letter: String in value:
		if not "0123456789abcdef".contains(letter):
			return false
	return true


func _unique_hashes(values: Array) -> bool:
	var seen: Dictionary = {}
	for value: Variant in values:
		if not _is_hash(value) or seen.has(value):
			return false
		seen[value] = true
	return true


func _whole(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value)) and abs(float(value)) <= 2000000000.0
