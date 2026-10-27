extends SceneTree

const Rules = preload("res://scripts/rules.gd")
var failures: Array[String] = []
var checks: Array[Dictionary] = []


func _initialize() -> void:
	_test_key_once_and_roundtrip()
	_test_combat_preview_and_rejection()
	_test_shop_tradeoffs()
	_test_save_restore_reset_and_reject()
	_test_production_data()
	print(JSON.stringify({"suite": "StairRules", "checks": checks, "failures": failures, "passed": failures.is_empty()}))
	quit(0 if failures.is_empty() else 1)


func _game() -> RefCounted:
	var game = Rules.new("")
	game.data = {
		"schema_version": 1, "title": "Test content",
		"initial_player": {"hp": 80, "atk": 24, "def": 8, "gold": 40, "keys": {"yellow": 0, "blue": 0}},
		"enemies": {
			"moss": {"name": "Moss", "hp": 20, "atk": 14, "def": 5, "gold": 8},
			"armor": {"name": "Armor", "hp": 10, "atk": 14, "def": 25, "gold": 10},
			"fatal": {"name": "Fatal", "hp": 100, "atk": 100, "def": 0, "gold": 10},
			"boss": {"name": "Boss", "hp": 1, "atk": 1, "def": 0, "gold": 10}},
		"shops": {"forge": {"name": "Forge", "offers": [
			{"id": "edge", "label": "Edge", "cost": 20, "kind": "atk", "amount": 6, "limit": 1},
			{"id": "ward", "label": "Ward", "cost": 20, "kind": "def", "amount": 4, "limit": 1},
			{"id": "flask", "label": "Flask", "cost": 15, "kind": "potion", "amount": 120, "limit": 2}]}},
		"floors": [
			{"id": 1, "name": "One", "spawn": [1, 3], "grid": ["#####", "#...#", "#...#", "#...#", "#####"], "objects": [
				{"id": "key", "kind": "key", "pos": [2, 3], "type": "yellow", "amount": 1},
				{"id": "door", "kind": "door", "pos": [3, 3], "type": "yellow"},
				{"id": "moss", "kind": "enemy", "pos": [3, 2], "type": "moss"},
				{"id": "up", "kind": "stairs", "pos": [3, 1], "target": {"floor": 2, "pos": [1, 3]}},
				{"id": "shop", "kind": "shop", "pos": [1, 2], "type": "forge"}]},
			{"id": 2, "name": "Two", "spawn": [1, 3], "grid": ["#####", "#...#", "#...#", "....#", "#####"], "objects": [
				{"id": "down", "kind": "stairs", "pos": [1, 3], "target": {"floor": 1, "pos": [3, 1]}},
				{"id": "armor", "kind": "enemy", "pos": [2, 3], "type": "armor"},
				{"id": "fatal", "kind": "enemy", "pos": [1, 2], "type": "fatal"},
				{"id": "boss", "kind": "enemy", "pos": [3, 1], "type": "boss", "victory": true}]}]}
	game.reset()
	return game


func _check(name: String, condition: bool, observed: Variant = null) -> void:
	checks.append({"name": name, "passed": condition, "observed": observed})
	if not condition:
		failures.append(name)
		push_error(name + ": " + str(observed))


func _test_key_once_and_roundtrip() -> void:
	var game = _game()
	var initial: Dictionary = game.snapshot()
	_check("use stairs elsewhere is blocked without mutation", not game.use_stairs()["ok"] and game.snapshot() == initial)
	_check("key picked", game.move(1, 0)["ok"] and game.state["keys"]["yellow"] == 1)
	_check("door consumes exactly one", game.move(1, 0)["ok"] and game.state["keys"]["yellow"] == 0)
	game.move(-1, 0)
	_check("reenter opened door for free", game.move(1, 0)["ok"] and game.state["keys"]["yellow"] == 0)
	game.move(0, -1)
	game.move(0, -1)
	_check("stair up", game.state["floor"] == 1 and game.state["pos"] == [1, 3])
	var carried: Dictionary = game.snapshot()
	var used: Dictionary = game.use_stairs()
	_check("use stairs on landing descends to return stair", used["ok"] and used["changed"] and game.state["floor"] == 0 and game.state["pos"] == [3, 1])
	used = game.use_stairs()
	_check("use stairs on return landing ascends", used["ok"] and game.state["floor"] == 1 and game.state["pos"] == [1, 3])
	_check("explicit stair roundtrip preserves full state", game.snapshot() == carried)
	# Spawn on the return stair: moving away and back is a deliberate descent.
	game.move(-1, 0)
	game.move(1, 0)
	_check("stair down preserves cleared objects", game.state["floor"] == 0 and "door" in game.state["cleared"] and "moss" in game.state["cleared"])
	game.move(0, 1)
	_check("defeated enemy stays gone", game.object_at([3, 2]).is_empty())
	game.move(0, 1)
	_check("opened door stays free across floor roundtrip", game.state["keys"]["yellow"] == 0 and game.state["pos"] == [3, 3])


func _test_combat_preview_and_rejection() -> void:
	var game = _game()
	game.state["pos"] = [2, 2]
	var before: Dictionary = game.snapshot()
	var preview: Dictionary = game.inspect([3, 2])["combat"]
	_check("inspection is pure", game.snapshot() == before)
	var result: Dictionary = game.move(1, 0)
	_check("preview equals HP actually spent", result["ok"] and int(before["hp"]) - int(game.state["hp"]) == int(preview["damage"]), {"preview": preview, "actual": int(before["hp"]) - int(game.state["hp"])})
	_check("hero first strike avoids final retaliation", preview["rounds"] == 2 and preview["damage"] == 6)
	game.state["floor"] = 1
	game.state["pos"] = [1, 3]
	before = game.snapshot()
	result = game.move(1, 0)
	_check("armor impossible action changes nothing", not result["ok"] and result["action"] == "unwinnable" and game.snapshot() == before)
	result = game.move(0, -1)
	_check("fatal damage action changes nothing", not result["ok"] and game.snapshot() == before)
	game.state["hp"] = 6
	var exact_hp: Dictionary = game.combat(game.data["enemies"]["moss"])
	_check("zero remaining HP is not victory", not exact_hp["win"] and exact_hp["damage"] == 6)
	game.state["hp"] = 80
	game.state["pos"] = [2, 1]
	result = game.move(1, 0)
	_check("final boss sets victory only after actual fight", result["ok"] and result["action"] == "victory" and game.state["won"])


func _test_shop_tradeoffs() -> void:
	var attack_route = _game()
	var defense_route = _game()
	var initial_gold: int = int(attack_route.state["gold"])
	_check("adjacent forge buys attack", attack_route.buy("edge")["ok"] and attack_route.state["atk"] == 30 and attack_route.state["gold"] == initial_gold - 20)
	_check("alternate spend buys defense", defense_route.buy("ward")["ok"] and defense_route.state["def"] == 12 and defense_route.state["atk"] == 24)
	_check("upgrade changes armor from impossible to winnable", attack_route.combat(attack_route.data["enemies"]["armor"])["win"] and not defense_route.combat(defense_route.data["enemies"]["armor"])["win"])
	var before: Dictionary = attack_route.snapshot()
	_check("finite stock does not spend twice", not attack_route.buy("edge")["ok"] and attack_route.snapshot() == before)
	attack_route.state["pos"] = [3, 3]
	before = attack_route.snapshot()
	_check("cannot buy remotely", not attack_route.buy("flask")["ok"] and attack_route.snapshot() == before)
	attack_route.state["pos"] = [1, 3]
	attack_route.state["gold"] = 0
	before = attack_route.snapshot()
	_check("insufficient gold leaves state intact", not attack_route.buy("flask")["ok"] and attack_route.snapshot() == before)


func _test_save_restore_reset_and_reject() -> void:
	var game = _game()
	game.buy("ward")
	game.move(1, 0)
	game.move(1, 0)
	game.move(0, -1)
	game.move(0, -1)
	var saved: Dictionary = game.snapshot()
	var path: String = "user://stairkeep-rule-test.json"
	_check("save writes validated snapshot", game.save_game(path))
	game.reset()
	_check("reset restores initial resources and world", game.state["hp"] == 80 and game.state["floor"] == 0 and game.state["cleared"].is_empty() and game.state["purchases"].is_empty())
	_check("load restores exact resources floor objects and purchases", game.load_game(path) and game.snapshot() == saved, game.snapshot())
	var before: Dictionary = game.snapshot()
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	file.store_string("{ broken")
	file.close()
	_check("corrupt JSON is rejected without mutation", not game.load_game(path) and game.snapshot() == before)
	game.save_game(path)
	file = FileAccess.open(path, FileAccess.READ)
	var payload: Dictionary = JSON.parse_string(file.get_as_text())
	file.close()
	payload["state"]["cleared"].append("not-a-real-object")
	file = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(payload))
	file.close()
	_check("unknown cleared id is rejected without mutation", not game.load_game(path) and game.snapshot() == before)
	payload["state"] = before.duplicate(true)
	payload["state"]["pos"] = [0, 0]
	file = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(payload))
	file.close()
	_check("wall-position save is rejected without mutation", not game.load_game(path) and game.snapshot() == before)
	payload["state"] = before.duplicate(true)
	payload["schema_version"] = 99
	file = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(payload))
	file.close()
	_check("future save schema is rejected", not game.load_game(path) and game.snapshot() == before)
	DirAccess.remove_absolute(path)


func _test_production_data() -> void:
	var game = Rules.new("")
	var loaded: bool = game.load_data()
	_check("delivered level data loads", loaded)
	if not loaded:
		return
	_check("delivered slice has three floors", game.data["floors"].size() == 3)
	_check("new game can save", game.save_game("user://stairkeep-data-test.json"))
	DirAccess.remove_absolute("user://stairkeep-data-test.json")
	game.state["atk"] = 33
	game.state["hp"] = 260
	var guard_preview: Dictionary = game.combat(game.data["enemies"]["stone_guard"])
	_check("production guard golden preview", guard_preview["win"] and guard_preview["damage"] == 80 and guard_preview["rounds"] == 6, guard_preview)
	game.state["hp"] = 80
	_check("production guard rejects exactly lethal result", not game.combat(game.data["enemies"]["stone_guard"])["win"])
	game.state["atk"] = 27
	_check("production guard rejects armor tie", game.combat(game.data["enemies"]["stone_guard"])["damage"] == -1)
	game.state["atk"] = 100
	game.state["hp"] = 200000
	# The sentinel is an explicit warning for the available route stats, not an invincible special case.
	game.state["atk"] = 38
	_check("production sealed sentinel cannot be fought at route maximum", not game.combat(game.data["enemies"]["sealed_sentinel"])["win"])
	for route: Dictionary in game.data.get("validated_routes", []):
		_test_production_route(game, route)


func _test_production_route(game: RefCounted, route: Dictionary) -> void:
	game.reset()
	var route_ok: bool = true
	var route_error: String = ""
	for entry: Dictionary in route["ledger"]:
		var event_id: String = str(entry["event"])
		var target_id: String = "f2_shop" if event_id.begins_with("buy:") else event_id
		var hp_before: int = int(game.state["hp"])
		if not _walk_to_object(game, target_id):
			route_ok = false
			route_error = "unreachable event " + event_id
			break
		if event_id.begins_with("buy:") and not game.buy(event_id.trim_prefix("buy:"))["ok"]:
			route_ok = false
			route_error = "failed purchase " + event_id
			break
		if entry.has("damage") and hp_before - int(game.state["hp"]) != int(entry["damage"]):
			route_ok = false
			route_error = "damage differs at " + event_id
			break
		var expected: Dictionary = entry["state"]
		for stat: String in ["hp", "atk", "def", "gold", "keys"]:
			var matches: bool = true
			if stat == "keys":
				for color: String in expected["keys"]:
					matches = matches and int(game.state["keys"][color]) == int(expected["keys"][color])
			else:
				matches = int(game.state[stat]) == int(expected[stat])
			if not matches:
				route_ok = false
				route_error = "%s differs at %s: %s vs %s" % [stat, event_id, game.state[stat], expected[stat]]
		if not route_ok:
			break
	_check("production route " + str(route["name"]), route_ok and bool(game.state["won"]), {"error": route_error, "state": game.snapshot(), "expected": route["final"]})


func _walk_to_object(game: RefCounted, target_id: String) -> bool:
	var target_floor: int = -1
	var target: Dictionary = {}
	for index: int in range(game.data["floors"].size()):
		for item: Dictionary in game.data["floors"][index]["objects"]:
			if item["id"] == target_id:
				target_floor = index
				target = item
	if target_floor < 0:
		return false
	while int(game.state["floor"]) != target_floor:
		var previous_floor: int = int(game.state["floor"])
		var wanted_floor_id: int = int(game.data["floors"][int(game.state["floor"]) + (1 if target_floor > int(game.state["floor"]) else -1)]["id"])
		var stair: Dictionary = {}
		for item: Dictionary in game.floor_data()["objects"]:
			if item["kind"] == "stairs" and int(item["target"]["floor"]) == wanted_floor_id:
				stair = item
		if stair.is_empty() or not _walk_to_cell(game, stair["pos"], str(stair["id"])):
			return false
		if int(game.state["floor"]) == previous_floor:
			return false
	return _walk_to_cell(game, target["pos"], target_id)


func _walk_to_cell(game: RefCounted, target: Array, allowed_id: String) -> bool:
	var start: Array = game.state["pos"].duplicate()
	if _cell_key(start) == _cell_key(target):
		return true
	var queue: Array = [start]
	var paths: Dictionary = {_cell_key(start): []}
	var found: Array = []
	while not queue.is_empty():
		var cell: Array = queue.pop_front()
		for delta: Array in [[1, 0], [-1, 0], [0, 1], [0, -1]]:
			var next: Array = [int(cell[0]) + int(delta[0]), int(cell[1]) + int(delta[1])]
			if paths.has(_cell_key(next)) or not game.walkable(next):
				continue
			var item: Dictionary = game.object_at(next)
			if not item.is_empty() and item["id"] != allowed_id and item["kind"] != "shop":
				continue
			var path: Array = paths[_cell_key(cell)].duplicate()
			path.append(delta)
			paths[_cell_key(next)] = path
			if _cell_key(next) == _cell_key(target):
				found = path
				queue.clear()
				break
			queue.append(next)
	if found.is_empty():
		return false
	for delta: Array in found:
		if not game.move(int(delta[0]), int(delta[1]))["ok"]:
			return false
	return true


func _cell_key(cell: Array) -> Vector2i:
	return Vector2i(int(cell[0]), int(cell[1]))
