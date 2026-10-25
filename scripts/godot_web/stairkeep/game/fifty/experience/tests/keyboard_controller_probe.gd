extends SceneTree
## Future authorized headless unit probe. This does not exercise the UI adapter,
## OS keyboard echo, timers, animation, focus signals, rules, gameplay or pixels.
## Apply the experience overlay to a project before running this external script.
## --traces=<json> --output=<new-report.json>; existing reports are never replaced.

const Controller = preload("res://fifty/view/keyboard_controller.gd")
const Geometry = preload("res://fifty/view/screen_input.gd")
const EXPECTED_TRACES_SHA256: String = "48187bbe9886efc5ab635a0b1c4915f34666277577b1e868dd96e0cfd50870c5"
const MAX_BYTES: int = 8388608
const STATE_KEYS: Array = ["pending_count", "need_all_up", "physical_mask", "pending_mask", "continuous", "repeat_due", "latch"]

var _errors: Array = []
var _runs: Array = []
var _geometry: Array = []
var _events: int = 0
var _polls: int = 0
var _state_assertions: int = 0
var _unsupported: int = 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var traces_path: String = get_script().resource_path.get_base_dir().path_join("keyboard_traces.json")
	var output_path: String = ""
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--traces="): traces_path = arg.trim_prefix("--traces=")
		elif arg.begins_with("--output="): output_path = arg.trim_prefix("--output=")
		else: _error("unsupported_argument", arg, true)
	if not output_path.is_empty() and FileAccess.file_exists(output_path):
		_error("output_exists", output_path)
		_finish({}, traces_path, "")
		return
	var fixture: Dictionary = _read_fixture(traces_path)
	if not fixture.is_empty() and _preflight(fixture):
		var names: Dictionary = {}
		for value: Variant in fixture["cases"]:
			if not value is Dictionary:
				_error("unsupported_case", "case is not an object", true)
				continue
			var item: Dictionary = value
			if not _case_valid(item): continue
			var name: String = item["name"]
			if names.has(name):
				_error("duplicate_case", name, true)
				continue
			names[name] = true
			var reasons: Array = item.get("repeat_for_reasons", [""])
			for reason: Variant in reasons:
				_run_trace(item, str(reason))
	# Exact coverage is bound to the reviewed corpus, not merely a pass count.
	if not fixture.is_empty():
		_check(fixture.get("cases", []).size() == 34, "source_case_coverage", fixture.get("cases", []).size(), 34)
		_check(_runs.size() == 39, "expanded_trace_coverage", _runs.size(), 39)
		_check(_events == 272, "event_coverage", _events, 272)
	_finish(fixture, traces_path, output_path)


func _read_fixture(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		_error("fixture_open", path)
		return {}
	if file.get_length() > MAX_BYTES:
		file.close()
		_error("fixture_size", path, true)
		return {}
	var source: String = file.get_as_text()
	file.close()
	var parser: JSON = JSON.new()
	if parser.parse(source) != OK or not parser.data is Dictionary:
		_error("fixture_json", parser.get_error_message(), true)
		return {}
	_check(FileAccess.get_sha256(path) == EXPECTED_TRACES_SHA256, "fixture_sha256", FileAccess.get_sha256(path), EXPECTED_TRACES_SHA256)
	if FileAccess.get_sha256(path) != EXPECTED_TRACES_SHA256: return {}
	return parser.data


func _preflight(fixture: Dictionary) -> bool:
	var start: int = _errors.size()
	_known_keys(fixture, ["schema", "scope", "bits", "geometry", "timing_contract", "cases"], "root")
	_check(_same(fixture.get("schema"), 1), "schema", fixture.get("schema"), 1)
	_check(fixture.get("scope") is String, "scope", fixture.get("scope"), "String")
	_check(_same(fixture.get("bits"), {"UP": Controller.UP, "DOWN": Controller.DOWN, "LEFT": Controller.LEFT, "RIGHT": Controller.RIGHT}), "bits", fixture.get("bits"), "production constants")
	var contract: Dictionary = {
		"chord_window_ms": Controller.CHORD_MS,
		"first_repeat_after_dispatched_step_ms": Controller.FIRST_REPEAT_MS,
		"subsequent_repeat_after_dispatched_step_ms": Controller.REPEAT_MS,
		"completed_tap_ready_when_all_physical_movement_keys_released": true,
		"compatible_partial_release_preserves_latch_and_repeat_deadline": true,
		"neutral_release_resume_requires_70ms_stable_hold_and_is_not_a_completed_press_tap": true,
		"physical_sync_removals_are_atomic": true, "busy_polls_dispatch_nothing": true,
		"pending_limit": 1, "catch_up": false,
		"same_resolved_direction_modifier_preserves_repeat_deadline": true,
		"new_press_turn_inside_held_segment_is_immediately_pending": true,
		"initial_window_deadline_is_not_extended_by_second_press": true,
		"blocked_is_emitted_once_then_stops_until_new_accepted_press": true,
		"rank_all_geometry_before_intersecting_walkable_edges": true, "lower_angle_fallback": false}
	_check(_same(fixture.get("timing_contract"), contract), "timing_contract", fixture.get("timing_contract"), contract)
	if not fixture.get("geometry") is Array or fixture["geometry"].size() != 4:
		_error("unsupported_geometry", "expected all four geometric neighbors", true)
	else:
		var seen: Array = []
		for value: Variant in fixture["geometry"]:
			if not value is Dictionary:
				_error("unsupported_geometry", value, true)
				continue
			_known_keys(value, ["grid", "screen"], "geometry")
			if not _delta(value.get("grid")) or not _pair(value.get("screen")):
				_error("unsupported_geometry", value, true)
				continue
			var grid: Array = _normalize(value["grid"])
			if seen.has(grid): _error("duplicate_geometry", grid, true)
			seen.append(grid)
			var screen: Vector2 = Vector2(float(value["screen"][0]), float(value["screen"][1]))
			if screen == Vector2.ZERO: _error("zero_geometry", grid, true)
			_geometry.append({"cell": grid.duplicate(), "delta": grid, "screen": screen, "walkable": true})
	_check(fixture.get("cases") is Array, "cases", typeof(fixture.get("cases")), "Array")
	return _errors.size() == start


func _case_valid(item: Dictionary) -> bool:
	var start: int = _errors.size()
	_known_keys(item, ["name", "options", "events", "repeat_for_reasons"], "case")
	if not item.get("name") is String or str(item.get("name", "")).is_empty(): _error("unsupported_case_name", item.get("name"), true)
	if not _walkable_set(item.get("options")): _error("unsupported_case_options", item.get("options"), true)
	if not item.get("events") is Array: _error("unsupported_case_events", item.get("name"), true)
	if item.has("repeat_for_reasons"):
		if not item["repeat_for_reasons"] is Array or item["repeat_for_reasons"].is_empty():
			_error("unsupported_expansion", item.get("name"), true)
		else:
			var seen: Array = []
			for reason: Variant in item["repeat_for_reasons"]:
				if not reason is String or str(reason).is_empty() or seen.has(reason): _error("unsupported_expansion_reason", reason, true)
				seen.append(reason)
	return _errors.size() == start


func _run_trace(item: Dictionary, reason: String) -> void:
	var controller: Variant = Controller.new()
	var walkable: Array = _normalize(item["options"])
	var records: Array = []
	var label: String = item["name"] + ("/" + reason if not reason.is_empty() else "")
	var start: int = _errors.size()
	var last_time: int = -1
	for index: int in range(item["events"].size()):
		var value: Variant = item["events"][index]
		var context: String = "%s[%d]" % [label, index]
		if not value is Dictionary or not _event_valid(value, context, last_time):
			if not value is Dictionary: _error("unsupported_event", context, true)
			break
		var event: Dictionary = value.duplicate(true)
		var stamp: int = int(event["t"])
		last_time = stamp
		if event.get("reason", "") == "$reason":
			if reason.is_empty():
				_error("unsupported_reason_placeholder", context, true)
				break
			event["reason"] = reason
		var before: Dictionary = controller.debug_state()
		var raw: Dictionary = {}
		var actual: Array = []
		match event["op"]:
			"press":
				if bool(event.get("repeat", false)) and (int(before["held_mask"]) & int(event["bit"])) == 0:
					_error("unsupported_unheld_echo", context, true)
					break
				controller.press(int(event["bit"]), stamp)
				if bool(event.get("repeat", false)):
					_check(_same(controller.debug_state(), before), context + ":duplicate_bit_idempotence", controller.debug_state(), before)
			"release": controller.release(int(event["bit"]), stamp)
			"sync": controller.sync_physical(int(event["physical"]), stamp)
			"cancel": controller.cancel(str(event["reason"]), int(event["physical"]))
			"options": walkable = _normalize(event["value"])
			"poll":
				var options: Array = _options(walkable)
				raw = controller.poll(stamp, bool(event.get("busy", false)), options)
				actual = _action(raw, before, options, context)
				_polls += 1
				_check(_same(actual, event["expect"]), context + ":action", actual, event["expect"])
		var after: Dictionary = controller.debug_state()
		_check(after.get("pending_count") in [0, 1], context + ":single_pending", after.get("pending_count"), "0 or 1")
		for key: String in event.get("state", {}):
			var observed: Variant = _state_value(after, key)
			_state_assertions += 1
			_check(_same(observed, event["state"][key]), context + ":state:" + key, observed, event["state"][key])
		records.append({"index": index, "event": event, "before": _normalize(before), "raw_result": _normalize(raw), "action": actual, "after": _normalize(after)})
		_events += 1
	_runs.append({"name": label, "passed": _errors.size() == start, "events": records})


func _event_valid(event: Dictionary, context: String, last_time: int) -> bool:
	var start: int = _errors.size()
	var op: String = str(event.get("op", ""))
	var allowed: Array = ["t", "op", "state"]
	match op:
		"press": allowed.append_array(["bit", "repeat"])
		"release": allowed.append("bit")
		"sync": allowed.append("physical")
		"cancel": allowed.append_array(["reason", "physical"])
		"options": allowed.append("value")
		"poll": allowed.append_array(["busy", "expect"])
		_: _error("unsupported_opcode", {"context": context, "op": op}, true)
	_known_keys(event, allowed, context)
	if not _integer(event.get("t")) or float(event.get("t", -1)) < maxi(0, last_time): _error("unsupported_timestamp", context, true)
	if op in ["press", "release"] and not (_integer(event.get("bit")) and int(event["bit"]) in [1, 2, 4, 8]): _error("unsupported_bit", context, true)
	if event.has("repeat") and not event["repeat"] is bool: _error("unsupported_repeat", context, true)
	if op in ["sync", "cancel"] and not (_integer(event.get("physical")) and int(event["physical"]) >= 0 and int(event["physical"]) <= 15): _error("unsupported_physical", context, true)
	if op == "cancel" and not event.get("reason") is String: _error("unsupported_cancel_reason", context, true)
	if op == "options" and not _walkable_set(event.get("value")): _error("unsupported_options_update", context, true)
	if event.has("busy") and not event["busy"] is bool: _error("unsupported_busy", context, true)
	if op == "poll" and not _expected_valid(event.get("expect")): _error("unsupported_expectation", context, true)
	if event.has("state"):
		if not event["state"] is Dictionary: _error("unsupported_state", context, true)
		else: _known_keys(event["state"], STATE_KEYS, context + ":state")
	return _errors.size() == start


func _action(raw: Dictionary, before: Dictionary, options: Array, context: String) -> Array:
	var status: String = str(raw.get("status", ""))
	match status:
		"idle": return []
		"step":
			_check(_delta(raw.get("delta")), context + ":cardinal_delta", raw.get("delta"), "one grid edge")
			_check(_same(raw.get("cell"), raw.get("delta")), context + ":origin_cell", raw.get("cell"), raw.get("delta"))
			_check(_legal(raw.get("delta"), options), context + ":step_walkable", raw.get("delta"), true)
			return [{"kind": "step", "grid": _normalize(raw.get("delta"))}]
		"choose":
			var cells: Variant = raw.get("cells")
			if not cells is Array or cells.size() != 2 or _same(cells[0], cells[1]):
				_error("invalid_choose", context)
				return []
			for cell: Variant in cells:
				_check(_delta(cell) and _legal(cell, options), context + ":choose_walkable", cell, true)
			var offered: Variant = raw.get("options")
			_check(offered is Array and offered.size() == cells.size(), context + ":choose_options_count", offered, cells.size())
			if offered is Array and offered.size() == cells.size():
				for i: int in range(cells.size()):
					_check(offered[i] is Dictionary and _same(offered[i].get("cell"), cells[i]) and _same(offered[i].get("delta"), cells[i]), context + ":choose_options", offered[i], cells[i])
			return [{"kind": "choose", "choices": _normalize(cells)}]
		"blocked":
			# blocked has no public delta. This is contextual diagnostics, not an
			# active latch: use the pre-poll latch or the production geometry query
			# with every edge walkable. Never manufacture it from the expectation.
			var grid: Variant = null
			if raw.get("reason", "") == "latched_wall" and _delta(before.get("latched_delta")):
				grid = _normalize(before["latched_delta"])
			else:
				var intent: Vector2 = before.get("pending_intent", Vector2.ZERO)
				if intent == Vector2.ZERO: intent = _mask_intent(int(before.get("held_mask", 0)))
				var geometric: Array = options.duplicate(true)
				for option: Dictionary in geometric: option["walkable"] = true
				var diagnostic: Dictionary = Geometry.resolve(intent, geometric)
				if diagnostic.get("status") == "step": grid = _normalize(diagnostic.get("delta"))
				else: _error("unsupported_blocked_target", {"context": context, "diagnostic": _normalize(diagnostic)}, true)
			return [{"kind": "blocked", "grid": grid}]
	_error("unsupported_result_status", {"context": context, "raw": _normalize(raw)}, true)
	return []


func _state_value(state: Dictionary, key: String) -> Variant:
	match key:
		"pending_count", "need_all_up", "physical_mask": return state.get(key)
		"continuous": return state.get("hold_active")
		"repeat_due": return null if int(state.get("next_repeat_at", -1)) < 0 else state["next_repeat_at"]
		"latch": return null if state.get("latched_delta", []).is_empty() else _normalize(state["latched_delta"])
		"pending_mask":
			if int(state.get("pending_count", 0)) == 0: return null
			var intent: Vector2 = state["pending_intent"]
			return (Controller.RIGHT if intent.x > 0 else Controller.LEFT if intent.x < 0 else 0) | (Controller.DOWN if intent.y > 0 else Controller.UP if intent.y < 0 else 0)
	_error("unsupported_state_alias", key, true)
	return null


func _options(walkable: Array) -> Array:
	var result: Array = _geometry.duplicate(true)
	for option: Dictionary in result: option["walkable"] = walkable.has(option["delta"])
	return result


func _legal(delta: Variant, options: Array) -> bool:
	for option: Dictionary in options:
		if _same(option["delta"], delta): return bool(option["walkable"])
	return false


func _expected_valid(value: Variant) -> bool:
	if not value is Array or value.size() > 1: return false
	for action: Variant in value:
		if not action is Dictionary: return false
		var kind: String = str(action.get("kind", ""))
		if kind in ["step", "blocked"]:
			if action.size() != 2 or not _delta(action.get("grid")): return false
		elif kind == "choose":
			if action.size() != 2 or not _walkable_set(action.get("choices")) or action["choices"].size() != 2: return false
		else: return false
	return true


func _walkable_set(value: Variant) -> bool:
	if not value is Array: return false
	var seen: Array = []
	for entry: Variant in value:
		if not _delta(entry): return false
		var delta: Array = _normalize(entry)
		if seen.has(delta): return false
		seen.append(delta)
	return true


func _integer(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and floor(float(value)) == float(value) and abs(float(value)) <= 9007199254740991.0


func _pair(value: Variant) -> bool:
	return value is Array and value.size() == 2 and _integer(value[0]) and _integer(value[1])


func _delta(value: Variant) -> bool:
	return _pair(value) and abs(int(value[0])) + abs(int(value[1])) == 1


func _mask_intent(mask: int) -> Vector2:
	return Vector2(int((mask & Controller.RIGHT) != 0) - int((mask & Controller.LEFT) != 0), int((mask & Controller.DOWN) != 0) - int((mask & Controller.UP) != 0))


func _normalize(value: Variant) -> Variant:
	if value is Vector2: return [value.x, value.y]
	if value is float and _integer(value): return int(value)
	if value is Array:
		var result: Array = []
		for entry: Variant in value: result.append(_normalize(entry))
		return result
	if value is Dictionary:
		var result: Dictionary = {}
		for key: Variant in value: result[key] = _normalize(value[key])
		return result
	return value


func _same(left: Variant, right: Variant) -> bool:
	return _normalize(left) == _normalize(right)


func _known_keys(value: Dictionary, allowed: Array, context: String) -> void:
	for key: Variant in value:
		if not key in allowed: _error("unsupported_field", {"context": context, "key": key}, true)


func _check(passed: bool, label: String, actual: Variant, expected: Variant) -> void:
	if not passed: _error("assertion", {"label": label, "actual": _normalize(actual), "expected": _normalize(expected)})


func _error(kind: String, detail: Variant, unsupported: bool = false) -> void:
	_errors.append({"kind": kind, "detail": _normalize(detail), "unsupported": unsupported})
	if unsupported: _unsupported += 1


func _finish(fixture: Dictionary, path: String, output: String) -> void:
	var report: Dictionary = {"schema_version": 1, "scope": "production-gd-unit-not-ui", "fixture_scope": fixture.get("scope", ""),
		"passed": _errors.is_empty(), "unsupported": _unsupported, "source_cases": fixture.get("cases", []).size(), "expanded_traces": _runs.size(),
		"events": _events, "polls": _polls, "state_assertions": _state_assertions,
		"bindings": {"fixture_path": path, "fixture_sha256": FileAccess.get_sha256(path), "expected_fixture_sha256": EXPECTED_TRACES_SHA256,
			"controller_sha256": FileAccess.get_sha256("res://fifty/view/keyboard_controller.gd"), "screen_input_sha256": FileAccess.get_sha256("res://fifty/view/screen_input.gd"),
			"probe_sha256": FileAccess.get_sha256(get_script().resource_path)},
		"adapters": {"geometry": "all four fixture edges at synthetic origin; options are only the walkable subset",
			"echo": "repeat:true invokes duplicate held-bit press; proves API idempotence, not OS echo filtering",
			"blocked_grid": "pre-poll public latch, otherwise production geometry resolver with all edges walkable; diagnostic only",
			"options_event": "updates supplied geometry walkability; no controller or rule mutation",
			"state_aliases": {"continuous": "hold_active", "repeat_due": "next_repeat_at (-1 becomes null)", "latch": "latched_delta (empty becomes null)", "pending_mask": "sign bits of public pending_intent; absent becomes null"}},
		"not_claimed": ["real keyboard or pointer", "OS echo filtering", "actual timer cadence or control feel", "focus/window/load/floor adapter signals", "driver await and busy tickets", "object confirmation or rule costs", "gameplay", "Web", "rendered pixels"],
		"errors": _errors, "traces": _runs}
	if not output.is_empty():
		var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
		if file == null:
			_error("report_open", output)
			report["passed"] = false
		else:
			file.store_string(JSON.stringify(report, "\t") + "\n")
			file.close()
	print(JSON.stringify({"suite": "keyboard_controller_probe", "scope": report["scope"], "passed": report["passed"], "expanded_traces": _runs.size(), "events": _events, "errors": _errors.size(), "unsupported": _unsupported, "report": output}))
	quit(0 if _errors.is_empty() else 1)
