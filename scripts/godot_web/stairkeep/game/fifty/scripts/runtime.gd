class_name FiftyRuntime
extends RefCounted
## Explicit authored-content profiles inside the existing game project.
## Ordinary combat delegates to the frozen authority; this file has no formula.

const BaseRules = preload("res://scripts/rules.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Content = preload("res://fifty/scripts/content.gd")
const CONTENT_PATH: String = "res://fifty/data/content.json"
const CHAPTER2_CONTENT_PATH: String = "res://fifty/data/chapter2-content.json"
const SNAPSHOT_SCHEMA: String = "stairkeep-fifty-state/v1"
const VARIANT_SPEC: String = "fifty/xorshift32-d4-v1"
const MODES: Array[String] = ["classic_restart", "practice_checkpoint"]
const MAX_ACTIONS: int = 30000
const MAX_ATTEMPTS: int = 100000
const RULE_FILES: Array[String] = ["res://scripts/rules.gd", "res://fifty/scripts/runtime.gd", "res://fifty/scripts/content.gd", "res://fifty/scripts/d4.gd"]

var _core = BaseRules.new("")
var _canonical: Dictionary = {}
var _content_sha_cache: String = ""
var _data: Dictionary = {}
var _mode: String = "unselected"
var _seed: String = ""
var _root_seed: String = ""
var _attempt: int = 0
var _previous_signature: String = ""
var _generated: Dictionary = {}
var _flags: Dictionary = {}
var _completed_events: Array = []
var _slice_complete: bool = false
var _failed: bool = false
var _failure: Dictionary = {}
var _failure_history: Array = []
var _origin_consumed: Array = []
var _consumed: Array = []
var _recovery_count: int = 0
var _actions: Array = []
var _checkpoints: Array = []
var last_error: String = ""

var data: Dictionary:
	get: return _data if not _data.is_empty() else _canonical
var state: Dictionary:
	get: return _core.snapshot()


func load_content(path: String = CONTENT_PATH) -> Dictionary:
	if _mode != "unselected":
		return _error("mode_already_selected", "A running mode cannot silently load different content.")
	var json: JSON = JSON.new()
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 8000000:
		return _error("content_unavailable", "The authored content file is unavailable.")
	var text: String = file.get_as_text()
	file.close()
	if json.parse(text) != OK or not (json.data is Dictionary):
		return _error("invalid_content", "Content must be a complete JSON dictionary.")
	return set_content(json.data)


func set_content(content: Dictionary) -> Dictionary:
	if _mode != "unselected":
		return _error("mode_already_selected", "Content cannot replace an active expedition.")
	var checked: Dictionary = Content.validate(content)
	if not bool(checked.get("ok", false)):
		var rejected: Dictionary = _error("invalid_content", "The authored slice did not validate.")
		rejected["errors"] = checked.get("errors", [])
		return rejected
	_canonical = content.duplicate(true)
	Geometry.freeze_tree(_canonical)
	_content_sha_cache = ""
	last_error = ""
	return _result(true, "content_loaded", "Choose a mode explicitly before starting.")


func choose_mode(mode: String, seed: Variant) -> Dictionary:
	if _mode != "unselected":
		return _error("mode_already_selected", "Changing mode cannot silently reset a running expedition.")
	if not MODES.has(mode) or _canonical.is_empty():
		return _error("mode_required", "Load content and explicitly choose classic_restart or practice_checkpoint.")
	var normalized: String = Geometry.normalize_seed(seed)
	if normalized.is_empty():
		return _error("invalid_seed", "Use an unsigned 32-bit integer or eight hexadecimal characters.")
	return _begin(mode, normalized, normalized, 0, "", [])


func _begin(mode: String, seed: String, root_seed: String, attempt: int, previous: String, origin_consumed: Array) -> Dictionary:
	var generated: Dictionary = Geometry.generate(_canonical, seed, previous)
	if not bool(generated.get("ok", false)):
		return _error("invalid_variant", str(generated.get("message", generated.get("error", "D4 generation failed."))))
	var full_data: Dictionary = generated["data"]
	var base_data: Dictionary = _base_adapter(full_data)
	var candidate = BaseRules.new("")
	if not candidate._valid_data(base_data):
		return _error("invalid_core_data", "The frozen authority rejected the adapted authored floors.")
	candidate.data = base_data
	candidate.reset()
	if not candidate._valid_state(candidate.state):
		return _error("invalid_initial_state", "The transformed initial state is invalid.")
	_core = candidate
	_data = full_data
	Geometry.freeze_tree(_data)
	Geometry.freeze_tree(_core.data)
	_generated = generated.duplicate(true)
	_generated.erase("data")
	_mode = mode
	_seed = seed
	_root_seed = root_seed
	_attempt = attempt
	_previous_signature = previous
	_flags = _canonical["flags"].duplicate(true)
	_completed_events = []
	_slice_complete = false
	_failed = false
	_failure = {}
	_failure_history = []
	_origin_consumed = origin_consumed.duplicate()
	_consumed = origin_consumed.duplicate()
	_recovery_count = 0
	_actions = []
	_checkpoints = []
	_capture_entry()
	last_error = ""
	var info: Dictionary = profile_info()
	return _result(true, "started", "The authored %d-floor slice is ready; %d higher floors are not made." % [int(info["authored_count"]), int(info["target_count"]) - int(info["authored_count"])])


func _base_adapter(full_data: Dictionary) -> Dictionary:
	var adapted: Dictionary = full_data.duplicate(true)
	for floor: Dictionary in adapted["floors"]:
		var items: Array = []
		for item: Dictionary in floor["objects"]:
			if item["kind"] not in ["npc", "event", "boundary"]:
				items.append(item)
		floor["objects"] = items
	return adapted


func runtime_identity() -> Dictionary:
	return {"content_id": str(_canonical.get("content_id", "")), "content_sha256": _canonical_content_sha(), "rules_sha256": rules_fingerprint(), "variant_spec": VARIANT_SPEC, "snapshot_schema": SNAPSHOT_SCHEMA}


func _canonical_content_sha() -> String:
	# Only successful content replacement invalidates this immutable tree.
	# State, checkpoints and run seeds do not change canonical content.
	if _content_sha_cache.is_empty():
		_content_sha_cache = Geometry.content_hash(_canonical)
	return _content_sha_cache


func profile_info() -> Dictionary:
	if _canonical.is_empty(): return {}
	var profile: Dictionary = Content.profile_definition(str(_canonical["content_id"]))
	if profile.is_empty(): return {}
	var authored_count: int = int(profile["authored_count"])
	var target_count: int = int(profile["target_count"])
	var authored: Array = []
	var unmade: Array = []
	for id: int in range(1, authored_count + 1): authored.append(id)
	for id: int in range(authored_count + 1, target_count + 1): unmade.append(id)
	return {"content_id": str(_canonical["content_id"]), "authored_count": authored_count, "target_count": target_count, "authored_floors": authored, "not_authored_floors": unmade, "checkpoint_floors": Content.checkpoint_floors(_canonical), "slice_goal_object_id": str(_canonical["completion"]["slice_goal_object_id"])}


static func rules_fingerprint() -> String:
	var bindings: Dictionary = {}
	for path: String in RULE_FILES:
		var digest: String = FileAccess.get_sha256(path)
		if digest.is_empty(): return ""
		bindings[path] = digest
	return Geometry.content_hash(bindings)


func floor_data() -> Dictionary:
	if _core.state.is_empty() or _data.is_empty(): return {}
	return _data["floors"][int(_core.state["floor"])]


func walkable(cell: Variant, floor_index: int = -1) -> bool:
	return _mode != "unselected" and _core.walkable(cell, floor_index)


func object_at(cell: Array, include_cleared: bool = false) -> Dictionary:
	if _core.state.is_empty(): return {}
	for item: Dictionary in floor_data().get("objects", []):
		if not Content.same_cell(item["pos"], cell): continue
		if not include_cleared and _core.state["cleared"].has(str(item["id"])): continue
		if not include_cleared and item.has("hidden_until_flag") and not bool(_flags.get(item["hidden_until_flag"], false)): continue
		if not include_cleared and item["kind"] == "event" and _all_completed(item["event_ids"]): continue
		return item.duplicate(true)
	return {}


func inspect(cell: Array) -> Dictionary:
	var item: Dictionary = object_at(cell)
	var result: Dictionary = {"cell": cell.duplicate(), "walkable": walkable(cell), "object": item, "available_events": available_events(cell)}
	match str(item.get("kind", "")):
		"enemy":
			result["enemy"] = _data["enemies"][item["type"]].duplicate(true)
			result["combat"] = combat(result["enemy"])
		"shop":
			result["shop"] = _data["shops"][item["type"]].duplicate(true)
		"door":
			result["can_open"] = int(_core.state["keys"].get(item["type"], 0)) > 0
	return result


func combat(enemy: Dictionary) -> Dictionary:
	if _mode == "unselected":
		return {"win": false, "damage": -1, "rounds": 0, "reason": "Choose a mode before combat."}
	return _core.combat(enemy)


func available_events(cell: Array) -> Array:
	var options: Array = []
	if _mode == "unselected" or _failed: return options
	var item: Dictionary = object_at(cell)
	if item.get("kind") not in ["npc", "event"]: return options
	for id: String in item.get("event_ids", []):
		if _event_eligible(id):
			var event: Dictionary = _data["events"][id]
			if event["trigger"]["kind"] != "interact" or event["trigger"].get("object_id", "") != item["id"]: continue
			options.append({"id": id, "text": event["text"], "effects": event["effects"].duplicate(true)})
	return options


func is_active() -> bool:
	return _mode != "unselected" and not _failed


func is_failed() -> bool:
	return _failed


func is_slice_complete() -> bool:
	return _slice_complete


func move(dx: int, dy: int) -> Dictionary:
	if not is_active(): return _inactive()
	if abs(dx) + abs(dy) != 1: return _error("blocked", "Move one cardinal cell.")
	var cell: Array = [int(_core.state["pos"][0]) + dx, int(_core.state["pos"][1]) + dy]
	return _interact(cell, {"kind": "move", "dx": dx, "dy": dy})


func interact(cell: Array) -> Dictionary:
	if not is_active(): return _inactive()
	return _interact(cell, {"kind": "interact", "cell": cell.duplicate()})


func _interact(cell: Array, action: Dictionary) -> Dictionary:
	if _actions.size() >= MAX_ACTIONS: return _error("action_limit", "The bounded action journal is full.")
	if not Content.pos(cell) or _distance(cell, _core.state["pos"]) != 1:
		return _error("blocked", "Choose an adjacent cell.")
	if not walkable(cell): return _error("wall", "Stone blocks this route.")
	var old_floor: int = int(_core.state["floor"])
	var old_pos: Array = _core.state["pos"].duplicate()
	var item: Dictionary = object_at(cell)
	if item.get("kind") == "boundary":
		var info: Dictionary = profile_info()
		return _error("not_authored", "Floors %d-%d are not authored; this boundary cannot be crossed." % [int(info["authored_count"]) + 1, int(info["target_count"])])
	var result: Dictionary
	if item.get("kind") in ["npc", "event"]:
		var options: Array = available_events(cell)
		if options.is_empty(): return _error("event_unavailable", "No unclaimed event branch currently meets its conditions.")
		var selected: String = str(options[0]["id"])
		_apply_event(selected)
		if item["kind"] == "event":
			_core.state["pos"] = [int(cell[0]), int(cell[1])]
		result = _result(true, "event", str(_data["events"][selected]["text"]))
		result["selected_event_id"] = selected
		action["selected_event_id"] = selected
	else:
		result = _core.interact(cell)
		if not bool(result.get("ok", false)): return result
	var entered: bool = old_floor != int(_core.state["floor"]) or not Content.same_cell(old_pos, _core.state["pos"])
	if entered:
		_enter_events([int(cell[0]) - int(old_pos[0]), int(cell[1]) - int(old_pos[1])] if old_floor == int(_core.state["floor"]) else [0, 0])
	_update_completion()
	_actions.append(action.duplicate(true))
	_capture_entry()
	result["state"] = state
	result["changed"] = true
	result["slice_complete"] = _slice_complete
	return result


func use_stairs() -> Dictionary:
	if not is_active(): return _inactive()
	if _actions.size() >= MAX_ACTIONS: return _error("action_limit", "The bounded action journal is full.")
	var result: Dictionary = _core.use_stairs()
	if not bool(result.get("ok", false)): return result
	_enter_events([0, 0])
	_update_completion()
	_actions.append({"kind": "stairs"})
	_capture_entry()
	result["state"] = state
	return result


func buy(choice: String) -> Dictionary:
	if not is_active(): return _inactive()
	if _actions.size() >= MAX_ACTIONS: return _error("action_limit", "The bounded action journal is full.")
	var result: Dictionary = _core.buy(choice)
	if bool(result.get("ok", false)):
		_actions.append({"kind": "buy", "offer": choice})
		result["state"] = state
	return result


func _event_eligible(id: String) -> bool:
	if _completed_events.has(id) or not _data.get("events", {}).has(id): return false
	var event: Dictionary = _data["events"][id]
	if int(event["floor"]) != int(floor_data().get("id", -1)): return false
	for condition: Dictionary in event["conditions"]:
		var actual: bool = false
		if condition["kind"] == "flag":
			actual = bool(_flags[condition["flag"]])
		elif condition["kind"] == "cleared":
			actual = _core.state["cleared"].has(condition["object_id"])
		if actual != bool(condition["value"]): return false
	return true


func _apply_event(id: String) -> void:
	if not _event_eligible(id): return
	var event: Dictionary = _data["events"][id]
	for effect: Dictionary in event["effects"]:
		match str(effect["kind"]):
			"set_flag":
				_flags[effect["flag"]] = bool(effect["value"])
			"grant":
				_core.state[effect["stat"]] = int(_core.state[effect["stat"]]) + int(effect["amount"])
			"grant_key":
				_core.state["keys"][effect["color"]] = int(_core.state["keys"][effect["color"]]) + int(effect["amount"])
			"clear_object":
				if not _core.state["cleared"].has(effect["object_id"]):
					_core.state["cleared"].append(effect["object_id"])
	_completed_events.append(id)


func _enter_events(delta: Array) -> void:
	var ids: Array = _data["events"].keys()
	ids.sort()
	for id: String in ids:
		var event: Dictionary = _data["events"][id]
		var trigger: Dictionary = event["trigger"]
		if trigger["kind"] != "enter" or not _event_eligible(id): continue
		if trigger.has("direction") and not Content.same_cell(trigger["direction"], delta): continue
		for cell: Array in trigger["cells"]:
			if Content.same_cell(cell, _core.state["pos"]):
				_apply_event(id)
				break


func _all_completed(ids: Array) -> bool:
	for id: String in ids:
		if not _completed_events.has(id): return false
	return true


func _update_completion() -> void:
	var goal: String = str(_data["completion"]["slice_goal_object_id"])
	if _core.state["cleared"].has(goal):
		_slice_complete = true
		return
	for floor: Dictionary in _data["floors"]:
		for item: Dictionary in floor["objects"]:
			if item["id"] == goal and item["kind"] == "event" and _all_completed(item["event_ids"]):
				_slice_complete = true


func unsafe_challenge(cell: Array, confirmed: bool = false) -> Dictionary:
	if not is_active(): return _inactive()
	if not confirmed: return _error("confirmation_required", "A lethal challenge requires explicit confirmation.")
	if _actions.size() >= MAX_ACTIONS: return _error("action_limit", "The bounded action journal is full.")
	if not Content.pos(cell) or _distance(cell, _core.state["pos"]) != 1:
		return _error("blocked", "Choose an adjacent enemy.")
	var item: Dictionary = object_at(cell)
	if item.get("kind") != "enemy": return _error("blocked", "This cell is not an active enemy.")
	var preview: Dictionary = combat(_data["enemies"][item["type"]])
	if bool(preview["win"]) or int(preview["damage"]) < 0:
		return _error("not_lethal", "Only a finite, penetrable, explicitly lethal challenge is supported.")
	_mark_failure("combat_death", {"enemy_id": item["id"], "cell": cell.duplicate(), "combat": preview, "terminal_hp": int(_core.state["hp"]) - int(preview["damage"])})
	_actions.append({"kind": "challenge", "cell": cell.duplicate()})
	var result: Dictionary = _result(true, "combat_death", "The confirmed challenge ended this attempt. Core HP remains a valid checkpoint source; terminal_hp records the same preview's lethal result.")
	result["combat"] = preview
	result["terminal_hp"] = _failure["terminal_hp"]
	result["failure_id"] = _failure["failure_id"]
	return result


func give_up(confirmed: bool = false) -> Dictionary:
	if not is_active(): return _inactive()
	if not confirmed: return _error("confirmation_required", "Abandoning an attempt requires explicit confirmation.")
	if _actions.size() >= MAX_ACTIONS: return _error("action_limit", "The bounded action journal is full.")
	_mark_failure("abandoned", {"terminal_hp": null})
	_actions.append({"kind": "give_up"})
	return _result(true, "abandoned", "This is a voluntary abandonment, not a proof that the world is unsatisfiable.")


func _mark_failure(kind: String, details: Dictionary) -> void:
	var failure: Dictionary = details.duplicate(true)
	failure["kind"] = kind
	failure["failure_id"] = Geometry.content_hash({"seed": _seed, "attempt": _attempt, "recovery_count": _recovery_count, "action_index": _actions.size(), "core_state": state, "kind": kind, "details": details})
	_failed = true
	_failure = failure
	_failure_history.append(failure.duplicate(true))


func restart_classic(seed: Variant, confirmed: bool = false, loss_id: String = "") -> Dictionary:
	if _mode != "classic_restart": return _error("wrong_mode", "Classic restart requires the explicitly selected classic mode.")
	if not confirmed: return _error("confirmation_required", "A new run requires explicit confirmation.")
	if not _valid_confirmation(loss_id): return _error("stale_loss_id", "The supplied loss is stale or already consumed.")
	var normalized: String = Geometry.normalize_seed(seed)
	if normalized.is_empty() or normalized == _seed:
		return _error("invalid_new_seed", "Choose a different valid run seed for classic restart.")
	if _attempt >= MAX_ATTEMPTS: return _error("attempt_limit", "The bounded attempt sequence is exhausted.")
	if _actions.size() >= MAX_ACTIONS: return _error("action_limit", "The bounded action journal is full.")
	var previous: String = str(_generated.get("layout_signature", ""))
	var previous_actions: Array = _actions.duplicate(true)
	var previous_history: Array = _failure_history.duplicate(true)
	var previous_consumed: Array = _consumed.duplicate()
	var was_failed: bool = _failed
	var result: Dictionary = _begin("classic_restart", normalized, _root_seed, _attempt + 1, previous, [])
	if not bool(result.get("ok", false)): return result
	# A new classic WORLD starts clean. Its audit lineage stays replayable from
	# the original seed, so imported attempt/history fields are never trusted.
	_actions = previous_actions
	_actions.append({"kind": "restart_classic", "seed": normalized, "loss_id": loss_id})
	_failure_history = previous_history
	_consumed = previous_consumed
	if was_failed: _consumed.append(loss_id)
	return result


func restore_checkpoint(id: String, confirmed: bool = false, loss_id: String = "") -> Dictionary:
	if _mode != "practice_checkpoint": return _error("wrong_mode", "Checkpoint restoration requires the explicitly selected practice mode.")
	if not confirmed: return _error("confirmation_required", "Restoration requires explicit confirmation.")
	if not _valid_confirmation(loss_id): return _error("stale_loss_id", "The supplied loss is stale or already consumed.")
	if _actions.size() >= MAX_ACTIONS: return _error("action_limit", "The bounded action journal is full.")
	var at: int = -1
	for index: int in range(_checkpoints.size()):
		if _checkpoints[index]["id"] == id:
			at = index
			break
	if at < 0: return _error("unknown_checkpoint", "Only a captured checkpoint from this exact run can be restored.")
	var checkpoint: Dictionary = _checkpoints[at]
	var world: Dictionary = checkpoint["world"]
	if checkpoint["seed"] != _seed or checkpoint["layout_sha256"] != _generated["layout_sha256"] or not _core._valid_state(world["core_state"]):
		return _error("checkpoint_mismatch", "Checkpoint identity does not match this run.")
	var was_failed: bool = _failed
	_core.state = world["core_state"].duplicate(true)
	_flags = world["flags"].duplicate(true)
	_completed_events = world["completed_events"].duplicate()
	_slice_complete = bool(world["slice_complete"])
	# The complete gameplay world and future checkpoint timeline rewind together.
	# The explicit recovery transaction remains in the audit journal/history.
	_checkpoints = _checkpoints.slice(0, at + 1)
	_failed = false
	_failure = {}
	if was_failed: _consumed.append(loss_id)
	_recovery_count += 1
	_actions.append({"kind": "restore", "checkpoint_id": id, "loss_id": loss_id})
	return _result(true, "checkpoint_restored", "Resources, stock, flags, completed events and the checkpoint timeline restored from one complete same-seed snapshot.")


func _valid_confirmation(loss_id: String) -> bool:
	if _failed:
		return not loss_id.is_empty() and loss_id == str(_failure.get("failure_id", "")) and not _consumed.has(loss_id)
	return loss_id.is_empty()


func _capture_entry() -> void:
	var floor_id: int = int(floor_data()["id"])
	if not Content.checkpoint_floors(_canonical).has(floor_id): return
	var id: String = "entry_%02d" % floor_id
	for checkpoint: Dictionary in _checkpoints:
		if checkpoint["id"] == id: return
	_checkpoints.append({"id": id, "label": str(floor_data().get("name", "Floor %d" % floor_id)), "floor_id": floor_id, "seed": _seed, "layout_sha256": _generated["layout_sha256"], "world": _world_snapshot()})


func _world_snapshot() -> Dictionary:
	return {"core_state": state, "flags": _flags.duplicate(true), "completed_events": _completed_events.duplicate(), "slice_complete": _slice_complete}


func export_snapshot() -> Dictionary:
	var identity: Dictionary = runtime_identity()
	var result: Dictionary = identity.duplicate(true)
	result.merge({"mode": _mode, "root_seed": _root_seed, "seed": _seed, "sequence_state": _seed, "attempt_index": _attempt, "floor_transforms": _generated.get("transforms", {}).duplicate(true), "layout_sha256": _generated.get("layout_sha256", ""), "layout_signature": _generated.get("layout_signature", ""), "previous_layout_signature": _previous_signature, "selection_receipt": _generated.get("selection_receipt", {}).duplicate(true), "core_state": state, "flags": _flags.duplicate(true), "completed_events": _completed_events.duplicate(), "slice_complete": _slice_complete, "campaign_complete": false, "failed": _failed, "failure": _failure.duplicate(true), "failure_history": _failure_history.duplicate(true), "origin_consumed_loss_ids": _origin_consumed.duplicate(), "consumed_loss_ids": _consumed.duplicate(), "recovery_count": _recovery_count, "actions": _actions.duplicate(true), "checkpoints": _checkpoints.duplicate(true)}, true)
	return result


func snapshot() -> Dictionary:
	return export_snapshot()


func validate_snapshot(candidate: Dictionary) -> Dictionary:
	var verified: Dictionary = _verify_snapshot(candidate)
	return {"ok": bool(verified.get("ok", false)), "status": verified.get("status", "invalid_snapshot"), "message": verified.get("message", "")}


func import_snapshot(candidate: Dictionary) -> Dictionary:
	if _mode == "classic_restart" and _failed:
		return _error("death_requires_restart", "This failed classic attempt requires an explicit new-seed restart; an old slot cannot roll back this live failure.")
	var verified: Dictionary = _verify_snapshot(candidate)
	if not bool(verified.get("ok", false)):
		return _error(str(verified.get("status", "invalid_snapshot")), str(verified.get("message", "The complete snapshot failed validation.")))
	_adopt(verified["runtime"])
	return _result(true, "snapshot_loaded", "A complete independently replayed same-mode snapshot was committed.")


func _verify_snapshot(candidate: Dictionary) -> Dictionary:
	if _mode == "unselected" or candidate.get("mode") != _mode:
		return {"ok": false, "status": "mode_required", "message": "Choose the same explicit mode before importing a slot."}
	var identity: Dictionary = runtime_identity()
	for key: String in identity:
		if candidate.get(key) != identity[key]:
			return {"ok": false, "status": "identity_mismatch", "message": "Snapshot content, rules or variant identity differs: " + key}
	for key: String in ["seed", "root_seed"]:
		if not (candidate.get(key) is String) or Geometry.normalize_seed(candidate[key]) != candidate[key]:
			return {"ok": false, "status": "invalid_seed", "message": "Snapshot seed is not canonical."}
	if candidate.get("sequence_state") != candidate["seed"] or not Content.whole(candidate.get("attempt_index")) or int(candidate["attempt_index"]) < 0 or int(candidate["attempt_index"]) > MAX_ATTEMPTS:
		return {"ok": false, "status": "invalid_sequence", "message": "Snapshot sequence metadata is invalid."}
	if not (candidate.get("actions") is Array) or candidate["actions"].size() > MAX_ACTIONS or not (candidate.get("origin_consumed_loss_ids") is Array):
		return {"ok": false, "status": "invalid_journal", "message": "Snapshot action history is missing or exceeds its bound."}
	var previous: Variant = candidate.get("previous_layout_signature")
	if not (previous is String) or (not str(previous).is_empty() and not _hash(previous)):
		return {"ok": false, "status": "invalid_layout", "message": "Previous-layout binding is malformed."}
	var origin_seen: Dictionary = {}
	for id: Variant in candidate["origin_consumed_loss_ids"]:
		if not _hash(id) or origin_seen.has(id):
			return {"ok": false, "status": "invalid_history", "message": "Initial consumed-loss audit IDs are malformed."}
		origin_seen[id] = true
	if not candidate["origin_consumed_loss_ids"].is_empty():
		return {"ok": false, "status": "invalid_history", "message": "This protocol derives consumed losses from the complete journal, not a supplied historical origin."}
	var rebuilt = get_script().new()
	rebuilt._canonical = _canonical
	rebuilt._content_sha_cache = ""
	var begun: Dictionary = rebuilt._begin(_mode, candidate["root_seed"], candidate["root_seed"], 0, "", [])
	if not bool(begun.get("ok", false)):
		return {"ok": false, "status": "invalid_variant", "message": "Snapshot variant could not be independently regenerated."}
	for index: int in range(candidate["actions"].size()):
		var value: Variant = candidate["actions"][index]
		if not (value is Dictionary):
			return {"ok": false, "status": "invalid_journal", "message": "Journal action is not a dictionary."}
		var replayed: Dictionary = rebuilt._replay_action(value)
		if not bool(replayed.get("ok", false)):
			return {"ok": false, "status": "invalid_journal", "message": "Authoritative action replay rejected step %d." % index}
	var actual: Dictionary = rebuilt.export_snapshot()
	var serialized: String = Geometry.canonical_json(candidate)
	if serialized.is_empty() or serialized != Geometry.canonical_json(actual):
		return {"ok": false, "status": "snapshot_mismatch", "message": "Complete snapshot differs from its real action replay; resources, flags, stock, checkpoints and history cannot be injected."}
	return {"ok": true, "status": "validated", "message": "Complete authoritative replay matched.", "runtime": rebuilt}


func _replay_action(action: Dictionary) -> Dictionary:
	match str(action.get("kind", "")):
		"move":
			if not Content.whole(action.get("dx")) or not Content.whole(action.get("dy")): return {"ok": false}
			return move(int(action["dx"]), int(action["dy"]))
		"interact":
			if not Content.pos(action.get("cell")): return {"ok": false}
			return interact(action["cell"])
		"stairs":
			return use_stairs()
		"buy":
			if not (action.get("offer") is String): return {"ok": false}
			return buy(action["offer"])
		"challenge":
			if not Content.pos(action.get("cell")): return {"ok": false}
			return unsafe_challenge(action["cell"], true)
		"give_up":
			return give_up(true)
		"restore":
			if not (action.get("checkpoint_id") is String) or not (action.get("loss_id") is String): return {"ok": false}
			return restore_checkpoint(action["checkpoint_id"], true, action["loss_id"])
		"restart_classic":
			if not (action.get("seed") is String) or not (action.get("loss_id") is String): return {"ok": false}
			return restart_classic(action["seed"], true, action["loss_id"])
	return {"ok": false}


func clone_for_search() -> RefCounted:
	if _mode == "unselected": return null
	var clone = get_script().new()
	clone._adopt(self)
	return clone


func _adopt(source: RefCounted) -> void:
	_canonical = source._canonical
	_content_sha_cache = source._content_sha_cache
	_data = source._data
	_core = BaseRules.new("")
	_core.data = source._core.data
	_core.state = source._core.snapshot()
	_mode = source._mode
	_seed = source._seed
	_root_seed = source._root_seed
	_attempt = source._attempt
	_previous_signature = source._previous_signature
	_generated = source._generated.duplicate(true)
	_flags = source._flags.duplicate(true)
	_completed_events = source._completed_events.duplicate()
	_slice_complete = source._slice_complete
	_failed = source._failed
	_failure = source._failure.duplicate(true)
	_failure_history = source._failure_history.duplicate(true)
	_origin_consumed = source._origin_consumed.duplicate()
	_consumed = source._consumed.duplicate()
	_recovery_count = source._recovery_count
	_actions = source._actions.duplicate(true)
	_checkpoints = source._checkpoints.duplicate(true)
	last_error = ""


func _inactive() -> Dictionary:
	return _error("mode_required" if _mode == "unselected" else "failed", "Choose a mode before acting." if _mode == "unselected" else "Confirm this failure's restart or complete checkpoint restoration.")


func _result(ok: bool, action: String, message: String) -> Dictionary:
	return {"ok": ok, "status": action, "action": action, "result": action, "message": message, "changed": ok, "state": state}


func _error(status: String, message: String) -> Dictionary:
	last_error = message
	return _result(false, status, message)


static func _distance(a: Array, b: Array) -> int:
	return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))


static func _hash(value: Variant) -> bool:
	if not (value is String) or str(value).length() != 64: return false
	for letter: String in str(value):
		if not "0123456789abcdef".contains(letter): return false
	return true
