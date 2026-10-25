extends SceneTree
## Two authored resource policies through actual runtime actions, never setters.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Save = preload("res://fifty/scripts/save.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const DATA: String = "res://fifty/data/content.json"
const SELF: String = "res://fifty/tests/replay_routes.gd"
var output: String = ""
var stop_file: String = ""
var selected_mode: String = "classic_restart"
var seeds: Array[String] = ["00000001", "00000002", "00000003", "00000004", "00000005", "00000006", "00000007", "00000008"]
var names: Array[String] = ["blade", "bulwark"]
var offset: int = 0
var count: int = -1
var native_save: bool = true
var catalogue: Dictionary = {}
var outcomes: Array = []
var errors: Array = []
var stopped: bool = false


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not _arguments():
		quit(2)
		return
	var json: JSON = JSON.new()
	if json.parse(FileAccess.get_file_as_string(DATA)) != OK or not (json.data is Dictionary):
		push_error("Canonical route data is unavailable.")
		quit(2)
		return
	catalogue = json.data
	var routes: Dictionary = {}
	for route: Dictionary in catalogue.get("validated_routes", []):
		if routes.has(str(route["name"])):
			push_error("Duplicate authored route name.")
			quit(2)
			return
		routes[str(route["name"])] = route
	for name: String in names:
		if not routes.has(name):
			push_error("Unknown authored route: " + name)
			quit(2)
			return
	var novelty: Dictionary = _content_audit()
	if not bool(novelty["passed"]): errors.append({"stage": "content audit", "details": novelty})
	var total: int = seeds.size() * names.size()
	var end: int = total if count < 0 else mini(total, offset + count)
	if offset > total:
		push_error("Case offset outside bounded seed/route matrix.")
		quit(2)
		return
	var began: int = Time.get_ticks_msec()
	for index: int in range(offset, end):
		if not stop_file.is_empty() and FileAccess.file_exists(stop_file):
			stopped = true
			break
		var route: Dictionary = routes[names[index % names.size()]]
		var seed: String = seeds[int(float(index) / float(names.size()))]
		var outcome: Dictionary = _case(index, seed, route)
		outcomes.append(outcome)
		print(JSON.stringify({"case": index, "seed": seed, "route": route["name"], "passed": outcome["passed"], "events": outcome.get("events_checked", 0), "elapsed_ms": outcome.get("elapsed_ms", 0)}))
		if not bool(outcome["passed"]):
			errors.append({"index": index, "error": outcome.get("error", "Unknown failure")})
			break
	var report: Dictionary = {"suite": "fifty_actual_authored_route_matrix/v1", "passed": errors.is_empty() and not stopped and outcomes.size() == end - offset,
		"measurement_completed": not stopped and outcomes.size() == end - offset, "engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(),
		"mode": selected_mode, "seeds": seeds, "routes": names, "case_offset": offset, "requested_cases": end - offset, "completed_cases": outcomes.size(),
		"source_hashes": _sources(), "content_audit": novelty, "cases": outcomes, "errors": errors, "stopped_at_case_boundary": stopped,
		"elapsed_ms": Time.get_ticks_msec() - began,
		"scope": "Actual Navigation move/interact/use_stairs/buy paths replay two authored resource policies across bounded independent D4 seeds. Exact authored resource/event/flag/stock budgets are checked. This is not exhaustive frontier-policy exploration, a 10k simulation, duration/visual/input acceptance, or completed 50-floor content. Floor-10 signal completion remains a playable slice with campaign_complete/core.won false."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		push_error("Cannot create new route report.")
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "completed_cases": outcomes.size(), "requested_cases": end - offset, "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if bool(report["passed"]) or (stopped and errors.is_empty()) else 1)


func _arguments() -> bool:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		elif argument.begins_with("--stop-file="): stop_file = argument.trim_prefix("--stop-file=")
		elif argument.begins_with("--mode="): selected_mode = argument.trim_prefix("--mode=")
		elif argument == "--no-native-save": native_save = false
		elif argument.begins_with("--seeds="):
			seeds.clear()
			for value: String in argument.trim_prefix("--seeds=").split(",", false):
				var normalized: String = Geometry.normalize_seed(value)
				if normalized.is_empty() or seeds.has(normalized): return false
				seeds.append(normalized)
		elif argument.begins_with("--routes="):
			names.clear()
			for name: String in argument.trim_prefix("--routes=").split(",", false):
				if names.has(name): return false
				names.append(name)
		elif argument.begins_with("--offset="):
			if not argument.trim_prefix("--offset=").is_valid_int(): return false
			offset = int(argument.trim_prefix("--offset="))
		elif argument.begins_with("--count="):
			if not argument.trim_prefix("--count=").is_valid_int(): return false
			count = int(argument.trim_prefix("--count="))
		else:
			push_error("Unknown route QA argument: " + argument)
			return false
	if output.is_empty() or FileAccess.file_exists(output) or offset < 0 or count < -1 or seeds.is_empty() or seeds.size() > 16 or names.is_empty() or names.size() > 4 or seeds.size() * names.size() > 64 or selected_mode not in ["classic_restart", "practice_checkpoint"]:
		push_error("Pass --output=<new JSON>, explicit --mode, bounded --seeds/--routes, optional --offset/--count/--stop-file.")
		return false
	return true


func _case(index: int, seed: String, route: Dictionary) -> Dictionary:
	var began: int = Time.get_ticks_msec()
	var result: Dictionary = {"index": index, "seed": seed, "route": route["name"], "policy": route["policy"], "mode": selected_mode, "passed": false, "trace": [], "negative_probes": [], "native_saves": []}
	var game = Runtime.new()
	var loaded: Dictionary = game.load_content()
	var started: Dictionary = game.choose_mode(selected_mode, seed) if bool(loaded.get("ok", false)) else loaded
	if not bool(started.get("ok", false)):
		result["error"] = {"stage": "initialization", "result": started}
		return result
	var initial: Dictionary = game.export_snapshot()
	result["initial_full_snapshot"] = initial
	var prepared: Dictionary = Navigation.prepare(game)
	var trace: Array = result["trace"]
	var comparisons: int = 0
	var actions: int = 0
	var doors_revisited: int = 0
	var stock_checks: int = 0
	var npc_checks: int = 0
	var events: Array = route["events"]
	var ledger: Array = route["ledger"]
	if events.size() != ledger.size():
		result["error"] = "Authored events/ledger lengths differ."
		return result
	for event_index: int in range(events.size()):
		var event: String = str(events[event_index])
		var before: Dictionary = game.export_snapshot()
		if not Navigation.same(Navigation.budget(before["core_state"]), ledger[event_index]["before"]):
			result["error"] = {"stage": "before budget", "event": event, "actual": Navigation.budget(before["core_state"]), "expected": ledger[event_index]["before"]}
			return result
		var planned: Dictionary = Navigation.plan(game, event, prepared)
		if not bool(planned.get("ok", false)):
			result["error"] = {"stage": "plan", "event": event, "details": planned, "full_counterexample_state": before}
			return result
		var path: Array = planned["path"]
		var approach: Array = path.slice(0, int(planned["approach_size"]))
		var approached: Dictionary = Navigation.execute(game, approach)
		if not bool(approached.get("ok", false)) or not Navigation.same(Navigation.economy(before), Navigation.economy(game.export_snapshot())):
			result["error"] = {"stage": "neutral approach", "event": event, "details": approached, "full_counterexample_state": game.export_snapshot()}
			return result
		var last: Dictionary = path[-1]
		var action_before: Dictionary = game.state
		var executed: Dictionary = Navigation.execute(game, [last])
		if not bool(executed.get("ok", false)):
			result["error"] = {"stage": "actual authored event", "event": event, "details": executed}
			return result
		comparisons += int(approached.get("preview_comparisons", 0)) + int(executed.get("preview_comparisons", 0))
		actions += path.size()
		var item: Dictionary = planned["item"]
		if item["kind"] == "door":
			var color: String = str(item["type"])
			if int(action_before["keys"][color]) - int(game.state["keys"][color]) != 1:
				result["error"] = {"stage": "door key charged exactly once", "event": event}
				return result
			var after_open: Dictionary = game.export_snapshot()
			var revisit: Array = [{"kind": "move", "dx": -int(last["dx"]), "dy": -int(last["dy"])}, last.duplicate(true)]
			var revisited: Dictionary = Navigation.execute(game, revisit)
			if not bool(revisited.get("ok", false)) or not Navigation.same(Navigation.economy(after_open), Navigation.economy(game.export_snapshot())):
				result["error"] = {"stage": "opened door revisit double charged or failed", "event": event, "details": revisited}
				return result
			path.append_array(revisit)
			actions += revisit.size()
			doors_revisited += 1
		if event.begins_with("buy:"):
			var choice: String = event.trim_prefix("buy:").split("/")[1]
			for offer: Dictionary in game.data["shops"][item["type"]]["offers"]:
				if str(offer["id"]) == choice and int(game.state["purchases"].get(event.trim_prefix("buy:"), 0)) == int(offer["limit"]):
					var stock_before: Dictionary = game.export_snapshot()
					var rejected: Dictionary = game.buy(choice)
					result["negative_probes"].append({"event": event, "kind": "sold_out", "result": rejected, "full_before_sha256": Geometry.content_hash(stock_before), "full_after_sha256": Geometry.content_hash(game.export_snapshot())})
					if bool(rejected.get("ok", true)) or not Navigation.same(stock_before, game.export_snapshot()):
						result["error"] = {"stage": "shop stock exceeded or mutated on refusal", "event": event}
						return result
					stock_checks += 1
		if item["kind"] == "npc" and game.available_events(item["pos"]).is_empty():
			var npc_before: Dictionary = game.export_snapshot()
			var repeated: Dictionary = game.interact(item["pos"])
			result["negative_probes"].append({"event": event, "kind": "npc no second reward", "result": repeated, "full_before_sha256": Geometry.content_hash(npc_before), "full_after_sha256": Geometry.content_hash(game.export_snapshot())})
			if bool(repeated.get("ok", true)) or not Navigation.same(npc_before, game.export_snapshot()):
				result["error"] = {"stage": "NPC rewarded the same exhausted interaction again", "event": event}
				return result
			npc_checks += 1
		var after: Dictionary = game.export_snapshot()
		var mismatch: String = _ledger_error(after, ledger[event_index], initial)
		var selected_event: String = str(executed["results"][-1].get("event_id", ""))
		if ledger[event_index].has("selected_event_id") and selected_event != str(ledger[event_index]["selected_event_id"]): mismatch += " selected_event_id"
		if not mismatch.is_empty():
			result["error"] = {"stage": "authored exact ledger", "event": event, "reason": mismatch, "expected": ledger[event_index], "actual_world": Navigation.world(after)}
			return result
		trace.append({"event_index": event_index, "event": event, "actions": path, "before_full_snapshot_sha256": Geometry.content_hash(before), "after_full_snapshot_sha256": Geometry.content_hash(after), "actual_world": Navigation.world(after), "selected_event_id": selected_event, "preview_deduction_comparisons": int(executed.get("preview_comparisons", 0)), "navigation_nodes": planned.get("visited", 0)})
		if native_save and index == offset and event == "f05_archive":
			var saved: Dictionary = _roundtrip(game, index)
			result["native_saves"].append(saved["receipt"])
			if not bool(saved.get("ok", false)):
				result["error"] = {"stage": "native complete slot roundtrip", "details": saved["receipt"]}
				return result
			game = saved["game"]
			prepared = Navigation.prepare(game)
	var final: Dictionary = game.export_snapshot()
	var checked: Dictionary = game.validate_snapshot(final)
	var final_match: bool = Navigation.same(Navigation.budget(final["core_state"]), _resource_budget(route["final"])) and _same_set(final["core_state"]["cleared"], route["final_cleared"]) and Navigation.same(final["core_state"]["purchases"], route["final_purchases"]) and Navigation.same(final["flags"], route["final_flags"]) and Navigation.same(final["completed_events"], route["completed_events"]) and bool(final["slice_complete"]) and not bool(final["campaign_complete"]) and not bool(final["core_state"]["won"])
	result.merge({"passed": final_match and bool(checked.get("ok", false)) and Navigation.same(final, game.export_snapshot()), "events_checked": trace.size(), "actual_actions": actions, "preview_deduction_comparisons": comparisons, "door_revisit_checks": doors_revisited, "stock_refusal_checks": stock_checks, "npc_once_checks": npc_checks, "full_final_snapshot": final, "final_budget": Navigation.budget(final["core_state"]), "authoritative_full_action_replay": {"ok": checked.get("ok", false), "status": checked.get("status", "")}, "elapsed_ms": Time.get_ticks_msec() - began}, true)
	if not bool(result["passed"]): result["error"] = "Final authored budget/flags/stock or full authoritative action replay differs."
	return result


func _roundtrip(game: RefCounted, index: int) -> Dictionary:
	var slot: String = "qa50r-" + str(OS.get_process_id()) + "-" + str(index)
	var path: String = Save.slot_path(slot, selected_mode)
	var before: Dictionary = game.export_snapshot()
	var receipt: Dictionary = {"slot_id": slot, "native_path": path, "before_full_snapshot_sha256": Geometry.content_hash(before), "passed": false}
	if FileAccess.file_exists(path):
		receipt["error"] = "QA slot already exists; no overwrite was attempted."
		return {"ok": false, "receipt": receipt}
	var saved: Dictionary = Save.write_slot(game, slot)
	receipt["save"] = saved
	if not bool(saved.get("ok", false)): return {"ok": false, "receipt": receipt}
	var next = Runtime.new()
	next.load_content()
	next.choose_mode(selected_mode, "6d2b79f5")
	var loaded: Dictionary = Save.load_slot(next, slot)
	receipt["load"] = loaded
	receipt["native_file_sha256"] = FileAccess.get_sha256(path)
	receipt["after_full_snapshot_sha256"] = Geometry.content_hash(next.export_snapshot())
	receipt["passed"] = bool(loaded.get("ok", false)) and Navigation.same(before, next.export_snapshot()) and Navigation.same(before, game.export_snapshot())
	return {"ok": receipt["passed"], "game": next, "receipt": receipt}


func _ledger_error(snapshot: Dictionary, ledger: Dictionary, initial: Dictionary) -> String:
	var mismatch: String = ""
	if not Navigation.same(Navigation.budget(snapshot["core_state"]), ledger["state"]): mismatch += " resources"
	if not Navigation.same(snapshot["flags"], ledger["flags"]): mismatch += " flags"
	if not Navigation.same(snapshot["completed_events"], ledger["completed_events"]): mismatch += " completed_events"
	if not Navigation.same(snapshot["core_state"]["purchases"], ledger["purchases"]): mismatch += " stock"
	if snapshot["core_state"]["cleared"].size() != int(ledger["cleared_count"]): mismatch += " cleared_count"
	if bool(snapshot["slice_complete"]) != bool(ledger["slice_complete"]): mismatch += " slice_complete"
	for field: String in ["seed", "root_seed", "sequence_state", "attempt_index", "floor_transforms", "layout_sha256", "layout_signature", "content_sha256", "rules_sha256"]:
		if not Navigation.same(snapshot[field], initial[field]): mismatch += " fixed_run/" + field
	if bool(snapshot["failed"]) or bool(snapshot["campaign_complete"]) or bool(snapshot["core_state"]["won"]): mismatch += " invalid_terminal_status"
	return mismatch


func _content_audit() -> Dictionary:
	var fingerprints: Dictionary = {}
	var floors: Array = []
	for floor: Dictionary in catalogue["floors"]:
		var orbit: Array[String] = []
		for code: int in range(8): orbit.append(Geometry.content_hash(Geometry.transform_grid(floor["grid"], code)))
		orbit.sort()
		fingerprints[orbit[0]] = true
		floors.append({"id": floor["id"], "authored": floor.get("authored", false), "objects": floor["objects"].size(), "topology_d4_orbit_sha256": orbit[0]})
	var passed: bool = floors.size() == 10 and fingerprints.size() == 10 and int(catalogue["manifest"]["target_floors"]) == 50 and catalogue["manifest"]["not_authored_floors"].size() == 40
	for floor: Dictionary in floors: passed = passed and bool(floor["authored"]) and int(floor["objects"]) > 0
	return {"passed": passed, "unique_nonempty_authored_floors": fingerprints.size(), "floors": floors, "scope": "Ten canonical grids have ten distinct D4 geometry orbits; names, IDs, stat reskins and rotations alone cannot satisfy this count. This is topology identity, not a visual quality review."}


func _same_set(a: Array, b: Array) -> bool:
	var left: Array = a.duplicate()
	var right: Array = b.duplicate()
	left.sort()
	right.sort()
	return Navigation.same(left, right)


func _resource_budget(value: Dictionary) -> Dictionary:
	return {"hp": value["hp"], "atk": value["atk"], "def": value["def"], "gold": value["gold"], "keys": value["keys"].duplicate(true)}


func _sources() -> Dictionary:
	var result: Dictionary = {}
	for path: String in [SELF, DATA, "res://scripts/rules.gd", "res://fifty/scripts/runtime.gd", "res://fifty/scripts/content.gd", "res://fifty/scripts/d4.gd", "res://fifty/scripts/save.gd", "res://fifty/tests/qa_navigation.gd"]:
		result[path] = FileAccess.get_sha256(path)
	return result
