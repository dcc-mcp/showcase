class_name FiftyQaNavigation
extends RefCounted
## Exact-event QA navigation only. Resource, NPC and event rules stay in runtime.
## Neutral graph uses predecessor links; no resource setters or teleports.
const Geometry = preload("res://fifty/scripts/d4.gd")
const STEPS: Array[Vector2i] = [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]
const RESOURCE_KINDS: Array[String] = ["key", "door", "enemy", "potion", "atk", "def", "gold"]


static func prepare(game: RefCounted) -> Dictionary:
	var data: Dictionary = game.data
	var floors: Dictionary = {}
	var objects: Dictionary = {}
	var cells: Dictionary = {}
	for index: int in range(data.get("floors", []).size()):
		var floor: Dictionary = data["floors"][index]
		floors[int(floor["id"])] = index
		for item: Dictionary in floor["objects"]:
			objects[str(item["id"])] = {"floor": index, "item": item}
			cells[Vector3i(index, int(item["pos"][0]), int(item["pos"][1]))] = item
	return {"data": data, "floors": floors, "objects": objects, "cells": cells}


static func plan(game: RefCounted, event: String, prepared: Dictionary, max_nodes: int = 100000) -> Dictionary:
	var buy: bool = event.begins_with("buy:")
	var stable_id: String = event.trim_prefix("buy:")
	var object_id: String = stable_id.split("/")[0] if buy else stable_id
	if not prepared.get("objects", {}).has(object_id):
		return {"ok": false, "error": "Unknown authored event ID.", "event": event}
	var target: Dictionary = prepared["objects"][object_id]
	var item: Dictionary = target["item"]
	if buy and (item.get("kind", "") != "shop" or stable_id.split("/").size() != 2):
		return {"ok": false, "error": "Invalid shop/offer event.", "event": event}
	var before: Dictionary = game.export_snapshot()
	var core: Dictionary = game.state
	var cleared: Dictionary = {}
	for id: String in core.get("cleared", []): cleared[id] = true
	var completed: Variant = before.get("completed_events", [])
	var destination: Vector3i = Vector3i(int(target["floor"]), int(item["pos"][0]), int(item["pos"][1]))
	var start: Vector3i = Vector3i(int(core["floor"]), int(core["pos"][0]), int(core["pos"][1]))
	var queue: Array[Vector3i] = [start]
	var previous: Dictionary = {start: {}}
	var head: int = 0
	var goal: Variant = null
	while head < queue.size():
		if max_nodes > 0 and head >= max_nodes:
			return {"ok": false, "error": "Neutral navigation budget exhausted; not an impossibility proof.", "unknown": true, "visited": head}
		var at: Vector3i = queue[head]
		head += 1
		var distance: int = absi(at.y - destination.y) + absi(at.z - destination.z)
		if at.x == destination.x:
			if buy and distance <= 1 and _selected_shop(at, prepared) == object_id:
				goal = at
				break
			if not buy and ((item["kind"] == "stairs" and distance == 0) or distance == 1):
				goal = at
				break
		var current: Dictionary = _object(at, prepared, cleared, completed)
		if current.get("kind", "") == "stairs":
			var landing: Dictionary = _landing(current, prepared)
			if landing["ok"]: _visit(landing["node"], at, {"kind": "stairs"}, previous, queue)
		for delta: Vector2i in STEPS:
			var next: Vector3i = at + Vector3i(0, delta.x, delta.y)
			if not _walkable(next, prepared["data"]): continue
			var object: Dictionary = _object(next, prepared, cleared, completed)
			if object.get("kind", "") == "stairs":
				var landing: Dictionary = _landing(object, prepared)
				if landing["ok"]: _visit(landing["node"], at, {"kind": "move", "dx": delta.x, "dy": delta.y}, previous, queue)
			elif object.is_empty() or object.get("kind", "") == "shop":
				if not _uncompleted_enter_trigger(next, prepared["data"], completed):
					_visit(next, at, {"kind": "move", "dx": delta.x, "dy": delta.y}, previous, queue)
	if goal == null:
		return {"ok": false, "error": "Exact authored event has no clear/shop/stair approach path.", "unknown": true, "event": event, "visited": head, "neutral_graph_exhausted": true}
	var path: Array = []
	var cursor: Vector3i = goal
	while cursor != start:
		var link: Dictionary = previous[cursor]
		path.push_front(link["action"].duplicate(true))
		cursor = link["parent"]
	var approach_size: int = path.size()
	if buy:
		path.append({"kind": "buy", "offer": stable_id.split("/")[1]})
	elif item["kind"] == "stairs" and goal == destination:
		path.append({"kind": "stairs"})
	elif item["kind"] in ["npc", "event", "boundary"]:
		path.append({"kind": "interact", "cell": item["pos"].duplicate()})
	else:
		path.append({"kind": "move", "dx": destination.y - int(goal.y), "dy": destination.z - int(goal.z)})
	return {"ok": true, "event": event, "item": item, "floor": int(target["floor"]), "path": path, "approach_size": approach_size, "visited": head}


static func execute(game: RefCounted, actions: Array) -> Dictionary:
	var comparisons: int = 0
	var results: Array = []
	for index: int in range(actions.size()):
		var action: Dictionary = actions[index]
		var core: Dictionary = game.state
		var before_hp: int = int(core["hp"])
		var preview: Dictionary = {}
		var result: Dictionary
		match str(action.get("kind", "")):
			"move":
				var cell: Array = [int(core["pos"][0]) + int(action["dx"]), int(core["pos"][1]) + int(action["dy"])]
				preview = game.inspect(cell).get("combat", {})
				result = game.move(int(action["dx"]), int(action["dy"]))
			"interact":
				preview = game.inspect(action["cell"]).get("combat", {})
				result = game.interact(action["cell"])
			"stairs": result = game.use_stairs()
			"buy": result = game.buy(str(action["offer"]))
			_:
				return {"ok": false, "error": "Unsupported QA action.", "action": action}
		var after: Dictionary = game.state
		if not bool(result.get("ok", false)):
			return {"ok": false, "error": "Authoritative runtime rejected the authored path action.", "index": index, "action": action, "result": result, "full_failure_snapshot": game.export_snapshot(), "preview_comparisons": comparisons}
		if not preview.is_empty():
			comparisons += 1
			if not bool(preview.get("win", false)) or before_hp - int(after["hp"]) != int(preview.get("damage", -1)):
				return {"ok": false, "error": "Authoritative combat preview did not equal actual deduction.", "preview": preview, "before_hp": before_hp, "after_hp": after["hp"], "index": index}
		for stat: String in ["hp", "atk", "def", "gold"]:
			if int(after[stat]) < (1 if stat in ["hp", "atk"] else 0):
				return {"ok": false, "error": "Negative/invalid authoritative resource.", "stat": stat, "state": after}
		for group: String in ["keys", "purchases"]:
			for amount: Variant in after[group].values():
				if int(amount) < 0: return {"ok": false, "error": "Negative inventory.", "state": after}
		results.append({"ok": true, "action": result.get("action", ""), "status": result.get("status", ""), "event_id": result.get("event_id", result.get("selected_event_id", "")), "combat": preview})
	return {"ok": true, "actions_executed": actions.size(), "preview_comparisons": comparisons, "results": results}


static func world(snapshot: Dictionary) -> Dictionary:
	return {"core_state": snapshot["core_state"].duplicate(true), "flags": snapshot["flags"].duplicate(true), "completed_events": snapshot["completed_events"].duplicate(true), "slice_complete": snapshot["slice_complete"]}


static func economy(snapshot: Dictionary) -> Dictionary:
	var value: Dictionary = world(snapshot)
	value["core_state"].erase("pos")
	value["core_state"].erase("floor")
	return value


static func same(a: Variant, b: Variant) -> bool:
	var left: String = Geometry.canonical_json(a)
	return not left.is_empty() and left == Geometry.canonical_json(b)


static func budget(core: Dictionary) -> Dictionary:
	return {"hp": core["hp"], "atk": core["atk"], "def": core["def"], "gold": core["gold"], "keys": core["keys"].duplicate(true)}


static func _object(node: Vector3i, prepared: Dictionary, cleared: Dictionary, completed: Variant) -> Dictionary:
	var item: Dictionary = prepared["cells"].get(node, {})
	if item.is_empty(): return {}
	if RESOURCE_KINDS.has(str(item.get("kind", ""))) and cleared.has(str(item["id"])): return {}
	if item.get("kind", "") == "event":
		var ids: Array = item.get("event_ids", [])
		if not ids.is_empty() and ids.all(func(id: Variant) -> bool: return completed.has(id)):
			return {}
	return item


static func _landing(item: Dictionary, prepared: Dictionary) -> Dictionary:
	var target: Dictionary = item.get("target", {})
	if not prepared["floors"].has(int(target.get("floor", -1))) or not (target.get("pos") is Array): return {"ok": false}
	var node: Vector3i = Vector3i(int(prepared["floors"][int(target["floor"])]), int(target["pos"][0]), int(target["pos"][1]))
	return {"ok": _walkable(node, prepared["data"]), "node": node}


static func _walkable(node: Vector3i, data: Dictionary) -> bool:
	if node.x < 0 or node.x >= data["floors"].size(): return false
	var rows: Array = data["floors"][node.x]["grid"]
	return node.z >= 0 and node.z < rows.size() and node.y >= 0 and node.y < str(rows[node.z]).length() and str(rows[node.z])[node.y] != "#"


static func _selected_shop(at: Vector3i, prepared: Dictionary) -> String:
	for item: Dictionary in prepared["data"]["floors"][at.x]["objects"]:
		if item.get("kind", "") == "shop" and absi(int(item["pos"][0]) - at.y) + absi(int(item["pos"][1]) - at.z) <= 1:
			return str(item["id"])
	return ""


static func _uncompleted_enter_trigger(node: Vector3i, data: Dictionary, completed: Variant) -> bool:
	var floor_id: int = int(data["floors"][node.x]["id"])
	for id: String in data.get("events", {}):
		var event: Dictionary = data["events"][id]
		if completed.has(id) or int(event["floor"]) != floor_id or event["trigger"].get("kind", "") != "enter": continue
		for cell: Array in event["trigger"].get("cells", []):
			if int(cell[0]) == node.y and int(cell[1]) == node.z: return true
	return false


static func _visit(node: Vector3i, parent: Vector3i, action: Dictionary, previous: Dictionary, queue: Array[Vector3i]) -> void:
	if not previous.has(node):
		previous[node] = {"parent": parent, "action": action}
		queue.append(node)
