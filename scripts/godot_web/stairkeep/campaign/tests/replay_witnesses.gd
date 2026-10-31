extends SceneTree
## Replays authored budgets through the unchanged production base rules.
## Navigation crosses real stairs and never silently collects another resource.

const BaseRules = preload("res://scripts/base_rules.gd")
const DATA_PATH: String = "res://data/levels21.json"

var failures: Array[String] = []
var objects_by_id: Dictionary = {}
var objects_by_cell: Dictionary = {}
var floor_index_by_id: Dictionary = {}
var navigation_moves: int = 0
var stair_transfers: int = 0
var preview_comparisons: int = 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var data_rules = BaseRules.new(DATA_PATH)
	if data_rules.data.is_empty():
		push_error("Campaign canonical data failed the production rules validator.")
		quit(1)
		return
	_index(data_rules.data)
	var outcomes: Array = []
	for route: Dictionary in data_rules.data.get("validated_routes", []):
		var rules = BaseRules.new(DATA_PATH)
		outcomes.append(_replay(rules, route))
	var report: Dictionary = {
		"scope": "21-floor canonical witness replay through production base_rules.gd; no browser or human play",
		"engine": Engine.get_version_info(),
		"data_sha256": FileAccess.get_sha256(DATA_PATH),
		"base_rules_sha256": FileAccess.get_sha256("res://scripts/base_rules.gd"),
		"test_sha256": FileAccess.get_sha256("res://tests/replay_witnesses.gd"),
		"routes": outcomes, "failures": failures,
		"navigation_moves": navigation_moves, "stair_transfers": stair_transfers,
		"preview_deduction_comparisons": preview_comparisons,
		"passed": failures.is_empty() and outcomes.size() >= 4,
	}
	var output: String = ""
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):
			output = argument.trim_prefix("--output=")
	if not output.is_empty():
		var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
		if file == null:
			failures.append("Cannot write requested replay report: " + output)
			report["passed"] = false
		else:
			file.store_string(JSON.stringify(report, "  ") + "\n")
			file.close()
	var route_summaries: Array = []
	for outcome: Dictionary in outcomes:
		var final_state: Dictionary = outcome.get("final", {})
		route_summaries.append({
			"name": outcome.get("name", ""), "passed": outcome.get("passed", false),
			"decision_count": outcome.get("decision_count", 0),
			"final": _resources(final_state) if not final_state.is_empty() else {},
			"won": final_state.get("won", false),
		})
	var failure_summaries: Array[String] = []
	for failure: String in failures:
		failure_summaries.append(failure.substr(0, 800))
	print(JSON.stringify({
		"passed": report["passed"], "engine": Engine.get_version_info().get("string", ""),
		"data_sha256": report["data_sha256"], "base_rules_sha256": report["base_rules_sha256"],
		"test_sha256": report["test_sha256"], "routes": route_summaries,
		"navigation_moves": navigation_moves, "stair_transfers": stair_transfers,
		"preview_deduction_comparisons": preview_comparisons,
		"failure_count": failures.size(), "failure_summaries": failure_summaries,
		"full_report_file": output,
	}, "  "))
	quit(0 if bool(report["passed"]) else 1)


func _index(data: Dictionary) -> void:
	for floor_index: int in range(data["floors"].size()):
		var floor: Dictionary = data["floors"][floor_index]
		floor_index_by_id[int(floor["id"])] = floor_index
		for item: Dictionary in floor["objects"]:
			objects_by_id[str(item["id"])] = {"floor": floor_index, "object": item}
			objects_by_cell[_node_key([floor_index, int(item["pos"][0]), int(item["pos"][1])])] = item


func _replay(rules, route: Dictionary) -> Dictionary:
	var name: String = str(route["name"])
	var before_failure_count: int = failures.size()
	var decisions: Array = []
	var events: Array = route.get("events", [])
	var ledger: Array = route.get("ledger", [])
	if events.size() != ledger.size():
		failures.append(name + ": event and ledger lengths differ")
		return {"name": name, "passed": false}
	for step: int in range(events.size()):
		var event: String = str(events[step])
		var expected: Dictionary = ledger[step]
		if str(expected.get("event", "")) != event:
			failures.append("%s step %d ledger identity differs" % [name, step])
			break
		var result: Dictionary = _event(rules, event)
		if not bool(result.get("ok", false)):
			failures.append("%s step %d %s: %s; at %s" % [name, step, event, str(result), str(rules.snapshot())])
			break
		if not _same_resources(rules.state, expected["state"]):
			failures.append("%s step %d %s resource mismatch: actual=%s expected=%s" % [name, step, event, str(_resources(rules.state)), str(expected["state"])])
			break
		if expected.has("damage") and int(result.get("damage", -1)) != int(expected["damage"]):
			failures.append("%s step %d %s design damage differs from actual rule" % [name, step, event])
			break
		decisions.append({"event": event, "state": _resources(rules.state), "damage": result.get("damage", null)})
	if failures.size() == before_failure_count:
		if not bool(rules.state.get("won", false)) or not _same_resources(rules.state, route["final"]):
			failures.append(name + ": final resource/victory assertion failed")
	return {"name": name, "policy": route.get("policy", ""), "passed": failures.size() == before_failure_count,
		"decision_count": decisions.size(), "final": rules.snapshot(), "decisions": decisions}


func _event(rules, event: String) -> Dictionary:
	var item_id: String = event
	var choice: String = ""
	if event.begins_with("buy:"):
		var parts: PackedStringArray = event.trim_prefix("buy:").split("/")
		if parts.size() != 2:
			return {"ok": false, "reason": "Invalid shop event"}
		item_id = parts[0]
		choice = parts[1]
	if not objects_by_id.has(item_id):
		return {"ok": false, "reason": "Unknown witness object: " + item_id}
	var entry: Dictionary = objects_by_id[item_id]
	var item: Dictionary = entry["object"]
	var navigation: Dictionary = _navigate(rules, int(entry["floor"]), item["pos"], not choice.is_empty())
	if not bool(navigation.get("ok", false)):
		return navigation
	if not choice.is_empty():
		return rules.buy(choice)
	var preview: Dictionary = {}
	var hp_before: int = int(rules.state["hp"])
	if item["kind"] == "enemy":
		preview = rules.combat(rules.data["enemies"][item["type"]])
		if not bool(preview.get("win", false)):
			return {"ok": false, "reason": "Witness encounter is unwinnable", "preview": preview}
	var result: Dictionary = rules.interact(item["pos"])
	if item["kind"] == "stairs" and bool(result.get("ok", false)):
		stair_transfers += 1
	if not preview.is_empty() and bool(result.get("ok", false)):
		var deducted: int = hp_before - int(rules.state["hp"])
		if deducted != int(preview["damage"]):
			return {"ok": false, "reason": "Production preview differs from deduction", "preview": preview, "deducted": deducted}
		preview_comparisons += 1
		result["damage"] = deducted
	return result


func _navigate(rules, target_floor: int, target_pos: Array, shop: bool) -> Dictionary:
	var start: Array = [int(rules.state["floor"]), int(rules.state["pos"][0]), int(rules.state["pos"][1])]
	var queue: Array = [start]
	var visited: Dictionary = {_node_key(start): true}
	var previous: Dictionary = {}
	var cleared: Dictionary = {}
	for item_id: String in rules.state["cleared"]:
		cleared[item_id] = true
	var head: int = 0
	var goal: String = ""
	while head < queue.size():
		var node: Array = queue[head]
		head += 1
		var distance: int = abs(int(node[1]) - int(target_pos[0])) + abs(int(node[2]) - int(target_pos[1]))
		if int(node[0]) == target_floor and (distance <= 1 if shop else distance == 1):
			goal = _node_key(node)
			break
		var edges: Array = []
		var standing: Dictionary = _uncleared_object(node, cleared)
		if standing.get("kind", "") == "stairs":
			edges.append({"kind": "use_stairs", "to": _stair_target(standing)})
		for delta: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var cell: Array = [int(node[1]) + delta.x, int(node[2]) + delta.y]
			if not rules.walkable(cell, int(node[0])):
				continue
			var neighbor: Array = [int(node[0]), int(cell[0]), int(cell[1])]
			var item: Dictionary = _uncleared_object(neighbor, cleared)
			if not item.is_empty() and not ["stairs", "shop"].has(item.get("kind", "")):
				continue
			var destination: Array = _stair_target(item) if item.get("kind", "") == "stairs" else neighbor
			edges.append({"kind": "move", "dx": delta.x, "dy": delta.y, "to": destination})
		for edge: Dictionary in edges:
			var key: String = _node_key(edge["to"])
			if visited.has(key):
				continue
			visited[key] = true
			previous[key] = {"from": _node_key(node), "edge": edge}
			queue.append(edge["to"])
	if goal.is_empty():
		return {"ok": false, "reason": "No resource-neutral cardinal path to witness event", "target_floor": target_floor + 1, "target_pos": target_pos}
	var path: Array = []
	var cursor: String = goal
	while cursor != _node_key(start):
		path.push_front(previous[cursor]["edge"])
		cursor = previous[cursor]["from"]
	var budget_before: Dictionary = _resources(rules.state)
	var cleared_before: Array = rules.state["cleared"].duplicate()
	var purchases_before: Dictionary = rules.state["purchases"].duplicate(true)
	for edge: Dictionary in path:
		var old_floor: int = int(rules.state["floor"])
		var result: Dictionary = rules.use_stairs() if edge["kind"] == "use_stairs" else rules.move(int(edge["dx"]), int(edge["dy"]))
		if not bool(result.get("ok", false)):
			return {"ok": false, "reason": "Production navigation rejected BFS edge", "edge": edge, "result": result}
		navigation_moves += 1
		if old_floor != int(rules.state["floor"]):
			stair_transfers += 1
		var actual: Array = [int(rules.state["floor"]), int(rules.state["pos"][0]), int(rules.state["pos"][1])]
		if actual != edge["to"]:
			return {"ok": false, "reason": "Production navigation differs from BFS destination", "expected": edge["to"], "actual": actual}
	if not _same_resources(rules.state, budget_before) or rules.state["cleared"] != cleared_before or rules.state["purchases"] != purchases_before:
		return {"ok": false, "reason": "Navigation changed a resource or object outside the witness"}
	return {"ok": true}


func _uncleared_object(node: Array, cleared: Dictionary) -> Dictionary:
	var item: Dictionary = objects_by_cell.get(_node_key(node), {})
	return {} if item.is_empty() or cleared.has(str(item["id"])) else item


func _stair_target(item: Dictionary) -> Array:
	var target: Dictionary = item["target"]
	return [int(floor_index_by_id[int(target["floor"])]), int(target["pos"][0]), int(target["pos"][1])]


func _resources(state: Dictionary) -> Dictionary:
	return {"hp": int(state["hp"]), "atk": int(state["atk"]), "def": int(state["def"]), "gold": int(state["gold"]), "keys": state["keys"].duplicate(true)}


func _same_resources(actual: Dictionary, expected: Dictionary) -> bool:
	for key: String in ["hp", "atk", "def", "gold"]:
		if int(actual.get(key, -1)) != int(expected.get(key, -2)):
			return false
	if actual.get("keys", {}).size() != expected.get("keys", {}).size():
		return false
	for color: String in expected.get("keys", {}):
		if int(actual.get("keys", {}).get(color, -1)) != int(expected["keys"][color]):
			return false
	return true


func _node_key(node: Array) -> String:
	return "%d:%d:%d" % [int(node[0]), int(node[1]), int(node[2])]
