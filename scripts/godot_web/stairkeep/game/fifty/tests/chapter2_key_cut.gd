extends RefCounted
## Conservative ordinary-play impossibility certificate for a zero-yellow-key cut.
## No combat formula: every enemy/blue door/NPC/resource restriction is waived.
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const STEPS: Array[Vector2i] = [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]


static func prove(game: RefCounted, max_nodes: int = 100000) -> Dictionary:
	var before: Dictionary = game.export_snapshot()
	var info: Dictionary = game.profile_info()
	if max_nodes < 1 or max_nodes > 100000 or bool(before.get("slice_complete", true)) or bool(before.get("failed", true)) or int(before.get("core_state", {}).get("keys", {}).get("yellow", -1)) != 0:
		return {"status": "unknown", "complete": false, "reason": "Requires an active unfinished world, zero yellow keys, and a finite node budget."}
	var prepared: Dictionary = Navigation.prepare(game)
	var goal_id: String = str(info.get("slice_goal_object_id", ""))
	if not prepared["objects"].has(goal_id): return {"status": "unknown", "complete": false, "reason": "Configured slice goal is unavailable."}
	if prepared["objects"][goal_id]["item"].get("kind", "") != "event":
		return {"status": "unknown", "complete": false, "reason": "This certificate requires an interaction event goal. A pickup/enemy/door goal may complete remotely through clear_object, so adjacency would not be a sound necessary condition."}
	for event: Dictionary in prepared["data"].get("events", {}).values():
		for effect: Dictionary in event.get("effects", []):
			if str(effect.get("kind", "")) not in ["set_flag", "grant", "grant_key", "clear_object"]:
				return {"status": "unknown", "complete": false, "reason": "Unsupported future event mechanism cannot be omitted from a proof."}
	var opened: Dictionary = {}
	for id: String in before["core_state"]["cleared"]: opened[id] = true
	var initial_opened: Dictionary = opened.duplicate()
	var optimistic_events: Dictionary = {}
	var work: int = 0
	var closure_rounds: int = 0
	var component: Dictionary = {}
	while true:
		closure_rounds += 1
		component = _component(before["core_state"], prepared, opened, max_nodes - work)
		work += int(component.get("visited", 0))
		if not bool(component.get("complete", false)):
			return {"status": "unknown", "complete": false, "reason": "Relaxed BFS node budget exhausted; no impossibility claim.", "visited": work, "max_nodes": max_nodes, "closure_rounds": closure_rounds}
		var reachable: Dictionary = component["reachable"]
		var changed: bool = false
		for id: String in prepared["objects"]:
			var indexed: Dictionary = prepared["objects"][id]
			var item: Dictionary = indexed["item"]
			var node: Vector3i = Vector3i(int(indexed["floor"]), int(item["pos"][0]), int(item["pos"][1]))
			if item.get("kind", "") == "key" and item.get("type", "") == "yellow" and not initial_opened.has(id) and reachable.has(node):
				return {"status": "unknown", "complete": false, "reason": "The relaxed component may supply an uncollected yellow key.", "possible_source_object": id, "visited": work}
			if item.get("kind", "") == "shop" and _near(reachable, node):
				for offer: Dictionary in prepared["data"]["shops"][item["type"]]["offers"]:
					var kind: String = str(offer.get("kind", ""))
					if kind not in ["potion", "hp", "atk", "def"] and int(before["core_state"]["purchases"].get(id + "/" + str(offer["id"]), 0)) < int(offer.get("limit", 1)):
						return {"status": "unknown", "complete": false, "reason": "A reachable non-stat shop offer may change the key bound.", "shop": id, "offer": offer, "visited": work}
		for event_id: String in prepared["data"].get("events", {}):
			if before["completed_events"].has(event_id): continue
			var event: Dictionary = prepared["data"]["events"][event_id]
			if not _event_reachable(event, prepared, reachable): continue
			optimistic_events[event_id] = true
			for effect: Dictionary in event["effects"]:
				if effect["kind"] == "grant_key" and effect.get("color", "") == "yellow" and int(effect.get("amount", 0)) > 0:
					return {"status": "unknown", "complete": false, "reason": "A condition-relaxed reachable event may grant a yellow key.", "event_id": event_id, "visited": work}
				if effect["kind"] == "clear_object":
					var target_id: String = str(effect["object_id"])
					if not prepared["objects"].has(target_id): return {"status": "unknown", "complete": false, "reason": "Invalid unlock target cannot support a proof."}
					var target: Dictionary = prepared["objects"][target_id]["item"]
					if target.get("kind", "") == "door" and target.get("type", "") == "yellow" and not opened.has(target_id):
						opened[target_id] = true
						changed = true
		if not changed: break
	var goal: Dictionary = prepared["objects"][goal_id]
	var goal_node: Vector3i = Vector3i(int(goal["floor"]), int(goal["item"]["pos"][0]), int(goal["item"]["pos"][1]))
	var goal_possible: bool = _near(component["reachable"], goal_node)
	var nodes: Array = []
	for node: Vector3i in component["reachable"]:
		nodes.append([int(prepared["data"]["floors"][node.x]["id"]), node.y, node.z])
	var unchanged: bool = Navigation.same(before, game.export_snapshot())
	return {"status": "known_key_cut" if not goal_possible and unchanged else "unknown", "complete": not goal_possible and unchanged,
		"reason": "No yellow key can be acquired in the complete relaxed cross-floor closure, even after all condition-relaxed reachable yellow-door unlock events; configured slice goal and every adjacent approach remain unreachable." if not goal_possible else "The relaxed graph can approach the goal; this relaxation proves no loss.",
		"ordinary_play_scope": "No checkpoint/load/restart/explicit death is part of this impossibility claim. Such recovery changes the starting world.",
		"relaxation": "All walkable grid cells admit enemies, blue doors, NPCs, shops, resources and boundaries. Stair target links remain, and walking over a stair without teleport is additionally allowed. Every reachable once-uncompleted event ignores its conditions and direction; yellow-door clear_object effects are applied to a fixed point. Uncollected yellow pickups, yellow grant events and unknown shop kinds defeat the proof. No combat formula or policy heuristic is used.",
		"full_state_sha256": Geometry.content_hash(before), "content_id": before["content_id"], "content_sha256": before["content_sha256"], "rules_sha256": before["rules_sha256"], "goal_object_id": goal_id,
		"goal_floor_id": int(prepared["data"]["floors"][int(goal["floor"])]["id"]), "goal_cell": goal["item"]["pos"], "goal_or_adjacent_relaxed_reachable": goal_possible,
		"visited_work": work, "max_nodes": max_nodes, "closure_rounds": closure_rounds, "reachable_cells_floor_id_x_y": nodes,
		"blocked_yellow_frontier": component["blocked"].values(), "condition_relaxed_reachable_events": optimistic_events.keys(), "optimistically_cleared_yellow_doors": _new_ids(opened, initial_opened), "full_runtime_state_unchanged": unchanged}


static func _component(core: Dictionary, prepared: Dictionary, opened: Dictionary, max_nodes: int) -> Dictionary:
	if max_nodes < 1: return {"complete": false, "visited": 0}
	var start: Vector3i = Vector3i(int(core["floor"]), int(core["pos"][0]), int(core["pos"][1]))
	var queue: Array[Vector3i] = [start]
	var seen: Dictionary = {start: true}
	var blocked: Dictionary = {}
	var head: int = 0
	while head < queue.size():
		if head >= max_nodes: return {"complete": false, "visited": head}
		var at: Vector3i = queue[head]
		head += 1
		var current: Dictionary = prepared["cells"].get(at, {})
		if current.get("kind", "") == "stairs":
			var landing: Dictionary = current.get("target", {})
			if not prepared["floors"].has(int(landing.get("floor", -1))): return {"complete": false, "visited": head}
			var next: Vector3i = Vector3i(int(prepared["floors"][int(landing["floor"])]), int(landing["pos"][0]), int(landing["pos"][1]))
			# Authoritative stairs place the actor at the target without paying its tile.
			# Waiving a target yellow door keeps this graph an upper bound even for
			# an unusual but walkable non-stair landing in a future valid fixture.
			_visit(next, prepared, opened, seen, queue, blocked, true)
		for step: Vector2i in STEPS:
			_visit(at + Vector3i(0, step.x, step.y), prepared, opened, seen, queue, blocked)
	return {"complete": true, "visited": head, "reachable": seen, "blocked": blocked}


static func _visit(node: Vector3i, prepared: Dictionary, opened: Dictionary, seen: Dictionary, queue: Array[Vector3i], blocked: Dictionary, stair_landing: bool = false) -> void:
	if seen.has(node) or node.x < 0 or node.x >= prepared["data"]["floors"].size(): return
	var rows: Array = prepared["data"]["floors"][node.x]["grid"]
	if node.z < 0 or node.z >= rows.size() or node.y < 0 or node.y >= str(rows[node.z]).length() or str(rows[node.z])[node.y] == "#": return
	var item: Dictionary = prepared["cells"].get(node, {})
	if not stair_landing and item.get("kind", "") == "door" and item.get("type", "") == "yellow" and not opened.has(str(item["id"])):
		blocked[str(item["id"])] = {"object_id": item["id"], "floor_id": prepared["data"]["floors"][node.x]["id"], "cell": item["pos"], "reason": "Uncleared yellow door; current yellow inventory is zero."}
		return
	if stair_landing and not item.is_empty(): blocked.erase(str(item["id"]))
	seen[node] = true
	queue.append(node)


static func _near(reachable: Dictionary, node: Vector3i) -> bool:
	if reachable.has(node): return true
	for step: Vector2i in STEPS:
		if reachable.has(node + Vector3i(0, step.x, step.y)): return true
	return false


static func _event_reachable(event: Dictionary, prepared: Dictionary, reachable: Dictionary) -> bool:
	var trigger: Dictionary = event["trigger"]
	if trigger.get("kind", "") == "interact":
		if not prepared["objects"].has(str(trigger.get("object_id", ""))): return true
		var indexed: Dictionary = prepared["objects"][str(trigger["object_id"])]
		return _near(reachable, Vector3i(int(indexed["floor"]), int(indexed["item"]["pos"][0]), int(indexed["item"]["pos"][1])))
	if trigger.get("kind", "") == "enter":
		if not prepared["floors"].has(int(event["floor"])): return true
		for cell: Array in trigger.get("cells", []):
			if reachable.has(Vector3i(int(prepared["floors"][int(event["floor"])]), int(cell[0]), int(cell[1]))): return true
		return false
	return true


static func _new_ids(all_ids: Dictionary, original: Dictionary) -> Array:
	var result: Array = []
	for id: String in all_ids:
		if not original.has(id): result.append(id)
	return result
