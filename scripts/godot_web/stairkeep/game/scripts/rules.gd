class_name StairRules
extends RefCounted
## The only combat and persistent-state authority. Presentation never deals damage.

const SAVE_VERSION: int = 1
const SAVE_PATH: String = "user://stairkeep-save.json"
const PICKUPS: Array[String] = ["key", "door", "enemy", "potion", "atk", "def", "gold"]

var data: Dictionary = {}
var state: Dictionary = {}


func _init(path: String = "res://data/levels.json") -> void:
	if not path.is_empty() and FileAccess.file_exists(path):
		load_data(path)


func load_data(path: String = "res://data/levels.json") -> bool:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return false
	var json: JSON = JSON.new()
	if json.parse(file.get_as_text()) != OK:
		return false
	var parsed: Variant = json.data
	if not (parsed is Dictionary) or not _valid_data(parsed):
		return false
	data = parsed.duplicate(true)
	reset()
	return true


func new_game() -> Dictionary:
	return reset()


func reset() -> Dictionary:
	if data.is_empty():
		state = {}
		return {}
	var initial: Dictionary = data.get("initial_player", {})
	var spawn: Array = data["floors"][0].get("spawn", [1, 1])
	var keys: Dictionary = initial.get("keys", {"yellow": 0, "blue": 0}).duplicate(true)
	for key: String in keys:
		keys[key] = int(keys[key])
	state = {
		"floor": 0, "pos": [int(spawn[0]), int(spawn[1])],
		"hp": int(initial.get("hp", 260)), "atk": int(initial.get("atk", 24)),
		"def": int(initial.get("def", 8)), "gold": int(initial.get("gold", 0)),
		"keys": keys,
		"cleared": [], "purchases": {}, "won": false,
	}
	return snapshot()


func snapshot() -> Dictionary:
	return state.duplicate(true)


func floor_data() -> Dictionary:
	if state.is_empty() or data.is_empty():
		return {}
	return data["floors"][int(state["floor"])]


func walkable(cell: Variant, floor_index: int = -1) -> bool:
	if not _valid_pos(cell) or data.is_empty():
		return false
	var index: int = int(state.get("floor", 0)) if floor_index < 0 else floor_index
	if index < 0 or index >= data["floors"].size():
		return false
	var grid: Array = data["floors"][index]["grid"]
	var x: int = int(cell[0])
	var y: int = int(cell[1])
	return y >= 0 and y < grid.size() and x >= 0 and x < str(grid[y]).length() and str(grid[y])[x] != "#"


func object_at(cell: Array, include_cleared: bool = false) -> Dictionary:
	for item: Dictionary in floor_data().get("objects", []):
		if _same_cell(item["pos"], cell) and (include_cleared or not state["cleared"].has(str(item["id"]))):
			return item.duplicate(true)
	return {}


func inspect(cell: Array) -> Dictionary:
	var item: Dictionary = object_at(cell)
	var result: Dictionary = {"cell": cell.duplicate(), "walkable": walkable(cell), "object": item}
	if item.get("kind", "") == "enemy":
		var enemy: Dictionary = data["enemies"][item["type"]].duplicate(true)
		result["enemy"] = enemy
		result["combat"] = combat(enemy)
	elif item.get("kind", "") == "shop":
		result["shop"] = data["shops"][item["type"]].duplicate(true)
	elif item.get("kind", "") == "door":
		result["can_open"] = int(state["keys"].get(item.get("type", "yellow"), 0)) > 0
	return result


func combat(enemy: Dictionary) -> Dictionary:
	var hit: int = int(state.get("atk", 0)) - int(enemy.get("def", 0))
	var enemy_hp: int = int(enemy.get("hp", 0))
	if hit <= 0 or enemy_hp <= 0:
		return {"win": false, "damage": -1, "rounds": 0, "hit": maxi(hit, 0), "reason": "Attack cannot penetrate armor."}
	var rounds: int = ceili(float(enemy_hp) / float(hit))
	var retaliation: int = maxi(0, int(enemy.get("atk", 0)) - int(state.get("def", 0)))
	var damage: int = (rounds - 1) * retaliation
	var survives: bool = int(state.get("hp", 0)) > damage
	return {
		"win": survives, "damage": damage, "rounds": rounds,
		"hit": hit, "retaliation": retaliation,
		"reason": "Safe" if survives else "Not enough HP; find another route or upgrade.",
	}


func move(dx: int, dy: int) -> Dictionary:
	if abs(dx) + abs(dy) != 1:
		return _result(false, "blocked", "Move one cardinal tile.")
	if state.is_empty():
		return _result(false, "blocked", "No game loaded.")
	return interact([int(state["pos"][0]) + dx, int(state["pos"][1]) + dy])


func interact(cell: Array) -> Dictionary:
	if state.is_empty():
		return _result(false, "blocked", "No game loaded.")
	if bool(state["won"]):
		return _result(false, "won", "The beacon is restored. Start a new expedition to play again.")
	if not _valid_pos(cell) or _distance(cell, state["pos"]) != 1:
		return _result(false, "blocked", "Choose an adjacent tile.")
	if not walkable(cell):
		return _result(false, "wall", "Stone blocks this route.")
	var before: Dictionary = snapshot()
	var item: Dictionary = object_at(cell)
	var result: Dictionary = _resolve(item)
	if not bool(result["ok"]):
		return result
	if result["action"] != "stairs":
		state["pos"] = [int(cell[0]), int(cell[1])]
	result["changed"] = state != before
	result["state"] = snapshot()
	return result


func use_stairs() -> Dictionary:
	if state.is_empty() or bool(state.get("won", false)):
		return _result(false, "blocked", "No active expedition.")
	var item: Dictionary = object_at(state["pos"])
	if item.get("kind", "") != "stairs":
		return _result(false, "blocked", "Stand on a stair to use it.")
	var before: Dictionary = snapshot()
	var result: Dictionary = _resolve(item)
	result["changed"] = state != before
	result["state"] = snapshot()
	return result


func _resolve(item: Dictionary) -> Dictionary:
	if item.is_empty():
		return _result(true, "move", "")
	var kind: String = str(item.get("kind", ""))
	var item_id: String = str(item["id"])
	var amount: int = int(item.get("amount", 1))
	var key_type: String = str(item.get("type", "yellow"))
	match kind:
		"door":
			if int(state["keys"].get(key_type, 0)) < 1:
				return _result(false, "door_locked", "Requires one %s key." % key_type)
			state["keys"][key_type] = int(state["keys"][key_type]) - 1
			state["cleared"].append(item_id)
			return _result(true, "door", "Used one %s key. This door stays open." % key_type)
		"enemy":
			var enemy: Dictionary = data["enemies"][item["type"]]
			var preview: Dictionary = combat(enemy)
			if not bool(preview["win"]):
				var blocked: Dictionary = _result(false, "unwinnable", str(preview["reason"]))
				blocked["combat"] = preview
				return blocked
			state["hp"] = int(state["hp"]) - int(preview["damage"])
			state["gold"] = int(state["gold"]) + int(enemy.get("gold", 0))
			state["cleared"].append(item_id)
			state["won"] = bool(item.get("victory", false))
			var fought: Dictionary = _result(true, "victory" if bool(state["won"]) else "combat", "%s: -%d HP, +%d gold." % [enemy.get("name", "Enemy"), preview["damage"], int(enemy.get("gold", 0))])
			fought["combat"] = preview
			return fought
		"key":
			state["keys"][key_type] = int(state["keys"].get(key_type, 0)) + amount
			state["cleared"].append(item_id)
			return _result(true, "pickup", "+%d %s key." % [amount, key_type])
		"potion", "atk", "def", "gold":
			var stat: String = "hp" if kind == "potion" else kind
			state[stat] = int(state[stat]) + amount
			state["cleared"].append(item_id)
			return _result(true, "pickup", "+%d %s." % [amount, stat.to_upper()])
		"stairs":
			var target: Dictionary = item["target"]
			var index: int = _floor_index(int(target["floor"]))
			if index < 0 or not walkable(target["pos"], index):
				return _result(false, "blocked", "Stair destination is unavailable.")
			state["floor"] = index
			state["pos"] = [int(target["pos"][0]), int(target["pos"][1])]
			return _result(true, "stairs", "Entered %s." % data["floors"][index].get("name", "the next floor"))
		"shop":
			var shop_result: Dictionary = _result(true, "shop", "Choose an upgrade. Stock and prices persist.")
			shop_result["shop_id"] = item_id
			shop_result["shop"] = data["shops"][item["type"]].duplicate(true)
			return shop_result
	return _result(false, "blocked", "Unknown object.")


func buy(choice: String) -> Dictionary:
	if state.is_empty() or bool(state["won"]):
		return _result(false, "blocked", "No active expedition.")
	var shop_object: Dictionary = {}
	for item: Dictionary in floor_data().get("objects", []):
		if item.get("kind", "") == "shop" and _distance(item["pos"], state["pos"]) <= 1:
			shop_object = item
			break
	if shop_object.is_empty():
		return _result(false, "shop_unavailable", "Stand beside the forge to trade.")
	var shop: Dictionary = data["shops"][shop_object["type"]]
	for offer: Dictionary in shop["offers"]:
		if str(offer["id"]) != choice:
			continue
		var purchase_key: String = str(shop_object["id"]) + "/" + choice
		var bought: int = int(state["purchases"].get(purchase_key, 0))
		if bought >= int(offer.get("limit", 1)):
			return _result(false, "sold_out", "This upgrade is sold out.")
		var cost: int = int(offer["cost"])
		if int(state["gold"]) < cost:
			return _result(false, "no_gold", "Need %d gold." % cost)
		var kind: String = str(offer["kind"])
		var stat: String = "hp" if kind == "potion" else kind
		if not ["hp", "atk", "def"].has(stat):
			return _result(false, "blocked", "Unsupported shop offer.")
		state["gold"] = int(state["gold"]) - cost
		state[stat] = int(state[stat]) + int(offer["amount"])
		state["purchases"][purchase_key] = bought + 1
		var result: Dictionary = _result(true, "purchase", "%s purchased." % offer.get("label", choice))
		result["changed"] = true
		result["state"] = snapshot()
		return result
	return _result(false, "blocked", "Unknown shop choice.")


func save_game(path: String = SAVE_PATH) -> bool:
	if not _valid_state(state):
		return false
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify({"schema_version": SAVE_VERSION, "content_id": _content_id(), "state": state}))
	file.flush()
	return file.get_error() == OK


func load_game(path: String = SAVE_PATH) -> bool:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return false
	var json: JSON = JSON.new()
	if json.parse(file.get_as_text()) != OK:
		return false
	var parsed: Variant = json.data
	if not (parsed is Dictionary) or not _whole_number(parsed.get("schema_version")) or int(parsed["schema_version"]) != SAVE_VERSION:
		return false
	if parsed.get("content_id", "") != _content_id() or not (parsed.get("state") is Dictionary):
		return false
	var restored: Dictionary = parsed["state"]
	if not _valid_state(restored):
		return false
	state = restored.duplicate(true)
	# JSON numbers become floats; normalize persisted integral values at the boundary.
	for key: String in ["floor", "hp", "atk", "def", "gold"]:
		state[key] = int(state[key])
	state["pos"] = [int(state["pos"][0]), int(state["pos"][1])]
	for key: String in state["keys"]:
		state["keys"][key] = int(state["keys"][key])
	for key: String in state["purchases"]:
		state["purchases"][key] = int(state["purchases"][key])
	return true


func _valid_state(candidate: Dictionary) -> bool:
	if data.is_empty():
		return false
	for key: String in ["floor", "hp", "atk", "def", "gold", "pos", "keys", "cleared", "purchases", "won"]:
		if not candidate.has(key):
			return false
	if candidate.size() != 10:
		return false
	for key: String in ["floor", "hp", "atk", "def", "gold"]:
		if not _whole_number(candidate[key]):
			return false
	var index: int = int(candidate["floor"])
	if index < 0 or index >= data["floors"].size() or not walkable(candidate["pos"], index):
		return false
	if int(candidate["hp"]) < 1 or int(candidate["atk"]) < 1 or int(candidate["def"]) < 0 or int(candidate["gold"]) < 0:
		return false
	if not (candidate["keys"] is Dictionary) or not (candidate["purchases"] is Dictionary) or not (candidate["cleared"] is Array) or not (candidate["won"] is bool):
		return false
	var initial_keys: Dictionary = data["initial_player"]["keys"]
	if candidate["keys"].size() != initial_keys.size():
		return false
	for key: String in initial_keys:
		if not candidate["keys"].has(key) or not _whole_number(candidate["keys"][key]) or int(candidate["keys"][key]) < 0:
			return false
	var known: Dictionary = {}
	var available_purchases: Dictionary = {}
	var victory_ids: Array = []
	for floor_item: Dictionary in data["floors"]:
		for item: Dictionary in floor_item["objects"]:
			if str(item["kind"]) in PICKUPS:
				known[str(item["id"])] = true
			if bool(item.get("victory", false)):
				victory_ids.append(str(item["id"]))
			if item["kind"] == "shop":
				for offer: Dictionary in data["shops"][item["type"]]["offers"]:
					available_purchases[str(item["id"]) + "/" + str(offer["id"])] = int(offer.get("limit", 1))
	var seen: Dictionary = {}
	for id_value: Variant in candidate["cleared"]:
		if not (id_value is String) or not known.has(id_value) or seen.has(id_value):
			return false
		seen[id_value] = true
	for purchase_key: Variant in candidate["purchases"]:
		if not (purchase_key is String) or not available_purchases.has(purchase_key):
			return false
		var count: Variant = candidate["purchases"][purchase_key]
		if not _whole_number(count) or int(count) < 0 or int(count) > int(available_purchases[purchase_key]):
			return false
	var victory_cleared: bool = false
	for victory_id: String in victory_ids:
		victory_cleared = victory_cleared or seen.has(victory_id)
	return bool(candidate["won"]) == victory_cleared


func _valid_data(candidate: Dictionary) -> bool:
	if int(candidate.get("schema_version", -1)) != 1 or not (candidate.get("floors") is Array) or candidate["floors"].is_empty():
		return false
	if not (candidate.get("initial_player") is Dictionary) or not (candidate.get("enemies") is Dictionary) or not (candidate.get("shops") is Dictionary):
		return false
	var initial: Dictionary = candidate["initial_player"]
	if not (initial.get("keys") is Dictionary):
		return false
	var ids: Dictionary = {}
	for floor_item: Variant in candidate["floors"]:
		if not (floor_item is Dictionary) or not (floor_item.get("grid") is Array) or not (floor_item.get("objects") is Array):
			return false
		if not _valid_pos(floor_item.get("spawn", [])):
			return false
		for row: Variant in floor_item["grid"]:
			if not (row is String) or row.is_empty():
				return false
		for item: Variant in floor_item["objects"]:
			if not (item is Dictionary) or not _valid_pos(item.get("pos", [])) or not (item.get("id") is String) or ids.has(item["id"]):
				return false
			ids[item["id"]] = true
			if item.get("kind") == "enemy" and not candidate["enemies"].has(item.get("type", "")):
				return false
			if item.get("kind") == "shop" and not candidate["shops"].has(item.get("type", "")):
				return false
	return true


func _content_id() -> String:
	return JSON.stringify(data).sha256_text()


func _floor_index(floor_id: int) -> int:
	for index: int in range(data["floors"].size()):
		if int(data["floors"][index].get("id", index + 1)) == floor_id:
			return index
	return -1


func _result(ok: bool, action: String, message: String) -> Dictionary:
	return {"ok": ok, "result": action, "action": action, "message": message, "changed": false, "events": [action] if ok else [], "state": snapshot()}


func _whole_number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value)) and abs(float(value)) <= 2000000000.0


func _valid_pos(value: Variant) -> bool:
	return value is Array and value.size() == 2 and _whole_number(value[0]) and _whole_number(value[1])


func _same_cell(a: Array, b: Array) -> bool:
	return a.size() == 2 and b.size() == 2 and int(a[0]) == int(b[0]) and int(a[1]) == int(b[1])


func _distance(a: Array, b: Array) -> int:
	return abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1]))
