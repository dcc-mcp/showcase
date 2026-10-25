class_name FiftyContent
extends RefCounted
## The authored 1-10 slice is a separate content identity, not fifty empty floors.

const CONTENT_ID: String = "stairkeep-fifty-slice/v1"
const KINDS: Array[String] = ["key", "door", "enemy", "potion", "atk", "def", "gold", "shop", "stairs", "npc", "event", "boundary"]
const STATS: Array[String] = ["hp", "atk", "def", "gold"]
const PICKUPS: Array[String] = ["key", "door", "enemy", "potion", "atk", "def", "gold"]
const DIRECTIONS: Array[String] = ["north", "east", "south", "west"]


static func validate(content: Dictionary) -> Dictionary:
	var errors: Array[String] = []
	if content.get("schema_version") != 1 or content.get("content_id") != CONTENT_ID:
		return {"ok": false, "errors": ["Unsupported fifty-slice content identity/schema."]}
	if not (content.get("manifest") is Dictionary) or not (content.get("floors") is Array):
		return {"ok": false, "errors": ["Manifest and authored floors are required."]}
	var manifest: Dictionary = content["manifest"]
	var authored: Array = []
	var unmade: Array = []
	for id: int in range(1, 11): authored.append(id)
	for id: int in range(11, 51): unmade.append(id)
	if manifest.get("target_floors") != 50 or not _numbers_equal(manifest.get("authored_floors"), authored) or not _numbers_equal(manifest.get("not_authored_floors"), unmade):
		errors.append("Manifest must distinguish ten authored floors from forty not-authored floors.")
	if content["floors"].size() != 10:
		errors.append("This slice requires exactly ten authored floors, not placeholders.")
	for field: String in ["initial_player", "enemies", "shops", "flags", "events", "completion"]:
		if not (content.get(field) is Dictionary):
			errors.append("Missing dictionary: " + field)
	if not errors.is_empty():
		return {"ok": false, "errors": errors}
	var initial: Dictionary = content["initial_player"]
	for stat: String in STATS:
		if not whole(initial.get(stat)) or int(initial[stat]) < (1 if stat in ["hp", "atk"] else 0):
			errors.append("Invalid initial stat: " + stat)
	if not (initial.get("keys") is Dictionary) or initial["keys"].is_empty():
		errors.append("Initial key colours must be declared.")
	else:
		for color: Variant in initial["keys"]:
			if not (color is String) or str(color).is_empty() or not whole(initial["keys"][color]) or int(initial["keys"][color]) < 0:
				errors.append("Invalid initial key colour/count.")
	for flag: Variant in content["flags"]:
		if not (flag is String) or str(flag).is_empty() or not (content["flags"][flag] is bool):
			errors.append("Flags must be named booleans.")
	for enemy_id: Variant in content["enemies"]:
		var value: Variant = content["enemies"][enemy_id]
		if not (enemy_id is String) or not (value is Dictionary):
			errors.append("Invalid enemy catalog entry.")
			continue
		for stat: String in ["hp", "atk", "def", "gold"]:
			if not whole(value.get(stat)) or int(value[stat]) < (1 if stat == "hp" else 0):
				errors.append("Invalid enemy stat: " + str(enemy_id) + "/" + stat)
		if whole(value.get("hp")) and whole(value.get("atk")) and int(value["hp"]) * int(value["atk"]) > 2000000000:
			errors.append("Enemy worst-case damage exceeds this snapshot protocol's safe finite bound.")
	for shop_id: Variant in content["shops"]:
		var shop: Variant = content["shops"][shop_id]
		if not (shop_id is String) or not (shop is Dictionary) or not (shop.get("offers") is Array):
			errors.append("Invalid shop catalog entry.")
			continue
		var offer_ids: Dictionary = {}
		for offer: Variant in shop["offers"]:
			if not (offer is Dictionary) or not (offer.get("id") is String) or offer_ids.has(offer.get("id")):
				errors.append("Shop offer IDs must be unique.")
				continue
			offer_ids[offer["id"]] = true
			if not ["potion", "hp", "atk", "def"].has(offer.get("kind")):
				errors.append("Unsupported shop stat.")
			for number: String in ["cost", "amount", "limit"]:
				if not whole(offer.get(number)) or int(offer[number]) < (0 if number == "cost" else 1):
					errors.append("Invalid shop offer " + number)
	var floor_ids: Dictionary = {}
	var objects: Dictionary = {}
	for index: int in range(content["floors"].size()):
		var floor_value: Variant = content["floors"][index]
		if not (floor_value is Dictionary):
			errors.append("Floor must be a dictionary.")
			continue
		var floor: Dictionary = floor_value
		if not whole(floor.get("id")) or int(floor["id"]) != index + 1:
			errors.append("Authored floor IDs must be contiguous 1-10 in order.")
			continue
		floor_ids[str(int(floor["id"]))] = floor
		if not (floor.get("grid") is Array) or floor["grid"].is_empty() or floor["grid"].size() > 64 or not (floor.get("objects") is Array):
			errors.append("Invalid floor grid/object list.")
			continue
		var width: int = str(floor["grid"][0]).length()
		if width < 3 or width > 64:
			errors.append("Floor width must be 3-64.")
		for row: Variant in floor["grid"]:
			if not (row is String) or str(row).length() != width:
				errors.append("Floor rows must form a rectangle.")
				continue
			for tile: String in str(row):
				if tile != "#" and tile != ".":
					errors.append("Only explicit wall/floor tiles are supported.")
		if floor.has("width") and floor["width"] != width:
			errors.append("Declared width differs from actual grid.")
		if floor.has("height") and floor["height"] != floor["grid"].size():
			errors.append("Declared height differs from actual grid.")
		if not walkable(floor, floor.get("spawn")):
			errors.append("Floor spawn must be a walkable cell.")
		var occupied: Dictionary = {}
		for item_value: Variant in floor["objects"]:
			if not (item_value is Dictionary):
				errors.append("Object must be a dictionary.")
				continue
			var item: Dictionary = item_value
			if not _only(item, ["id", "kind", "pos", "type", "amount", "target", "direction", "victory", "event_ids", "facing", "direction_vector", "slice_goal", "hidden_until_flag", "name", "description", "label", "palette", "bestiary_note", "message"]):
				errors.append("Unknown object fields require an explicit geometry/rule adapter.")
			if not (item.get("id") is String) or str(item["id"]).is_empty() or objects.has(item["id"]):
				errors.append("Object stable IDs must be globally unique.")
				continue
			objects[item["id"]] = {"floor": int(floor["id"]), "item": item}
			if not walkable(floor, item.get("pos")):
				errors.append("Objects need explicit walkable coordinates.")
				continue
			var cell: String = "%d,%d" % [int(item["pos"][0]), int(item["pos"][1])]
			if occupied.has(cell): errors.append("Only one main object may occupy a cell.")
			occupied[cell] = true
			var kind: String = str(item.get("kind", ""))
			if not KINDS.has(kind): errors.append("Unsupported object kind: " + kind)
			if bool(item.get("victory", false)):
				errors.append("A ten-floor slice must not set whole-campaign victory.")
			if item.has("facing") and not DIRECTIONS.has(str(item["facing"])):
				errors.append("Facing must be an explicit compass direction.")
			if item.has("direction_vector") and (not pos(item["direction_vector"]) or abs(int(item["direction_vector"][0])) + abs(int(item["direction_vector"][1])) != 1):
				errors.append("Object direction must be an explicit cardinal vector.")
			if kind == "enemy" and not content["enemies"].has(item.get("type", "")):
				errors.append("Unknown enemy type.")
			if kind == "shop" and not content["shops"].has(item.get("type", "")):
				errors.append("Unknown shop type.")
			if kind in ["key", "door"] and not initial.get("keys", {}).has(item.get("type", "")):
				errors.append("Unknown key/door colour.")
			if kind in ["key", "potion", "atk", "def", "gold"] and (not whole(item.get("amount")) or int(item["amount"]) < 1):
				errors.append("Pickups require a positive explicit amount.")
			if kind in ["npc", "event"] and (not (item.get("event_ids") is Array) or item["event_ids"].is_empty()):
				errors.append("NPC/event objects need explicit event IDs.")
			if item.has("hidden_until_flag") and not content["flags"].has(item["hidden_until_flag"]):
				errors.append("Hidden object flag is undeclared.")
			if item.has("hidden_until_flag") and kind not in ["npc", "event"]:
				errors.append("This slice only adapts hidden NPC/event objects.")
	if not errors.is_empty():
		return {"ok": false, "errors": errors}
	for id: String in objects:
		var entry: Dictionary = objects[id]
		var item: Dictionary = entry["item"]
		if item["kind"] == "stairs":
			var target: Variant = item.get("target")
			if not (target is Dictionary) or not whole(target.get("floor")) or not floor_ids.has(str(int(target["floor"]))) or not objects.has(target.get("object_id", "")):
				errors.append("Stair destination must be authored with a stable target ID.")
				continue
			if not _only(target, ["floor", "pos", "object_id"]):
				errors.append("Unknown stair target fields are unsupported.")
			var destination: Dictionary = objects[target["object_id"]]
			if int(destination["floor"]) != int(target["floor"]) or destination["item"]["kind"] != "stairs" or not same_cell(destination["item"]["pos"], target.get("pos", [])):
				errors.append("Stair target ID/position mismatch.")
			var reverse: Variant = destination["item"].get("target")
			if not (reverse is Dictionary) or reverse.get("object_id", "") != id or reverse.get("floor") != entry["floor"] or not same_cell(reverse.get("pos", []), item["pos"]):
				errors.append("Stairs must be reciprocal.")
			if item.get("direction") not in ["up", "down"] or (item["direction"] == "up" and int(target["floor"]) <= int(entry["floor"])) or (item["direction"] == "down" and int(target["floor"]) >= int(entry["floor"])):
				errors.append("Stair floor direction is inconsistent.")
		if item["kind"] in ["npc", "event"]:
			for event_id: Variant in item["event_ids"]:
				if not (event_id is String) or not content["events"].has(event_id):
					errors.append("Object references an unknown event.")
					continue
				var attached: Variant = content["events"][event_id]
				if not (attached is Dictionary) or not (attached.get("trigger") is Dictionary) or attached["trigger"].get("kind") != "interact" or attached["trigger"].get("object_id") != id:
					errors.append("Attached object events must be interaction events for this exact object.")
	for event_id: Variant in content["events"]:
		_validate_event(event_id, content["events"][event_id], content, floor_ids, objects, errors)
	var goal_id: Variant = content["completion"].get("slice_goal_object_id")
	if not (goal_id is String) or not objects.has(goal_id) or not bool(objects[goal_id]["item"].get("slice_goal", false)):
		errors.append("The slice requires an explicit authored slice_goal object.")
	if errors.is_empty():
		_validate_bounds(content, errors)
	return {"ok": errors.is_empty(), "errors": errors}


static func _validate_event(id: Variant, value: Variant, content: Dictionary, floors: Dictionary, objects: Dictionary, errors: Array[String]) -> void:
	if not (id is String) or str(id).is_empty() or not (value is Dictionary):
		errors.append("Events require stable IDs and dictionaries.")
		return
	var event: Dictionary = value
	if not _only(event, ["floor", "trigger", "conditions", "effects", "once", "text"]):
		errors.append("Unknown event fields require an explicit adapter.")
	if not whole(event.get("floor")) or not floors.has(str(int(event["floor"]))) or not (event.get("trigger") is Dictionary) or not (event.get("conditions") is Array) or not (event.get("effects") is Array) or event.get("once") != true or not (event.get("text") is String):
		errors.append("Event has unsupported schema: " + str(id))
		return
	var trigger: Dictionary = event["trigger"]
	if trigger.get("kind") == "interact":
		if not _only(trigger, ["kind", "object_id"]): errors.append("Unsupported interaction trigger fields.")
		if not objects.has(trigger.get("object_id", "")) or objects[trigger["object_id"]]["floor"] != event["floor"] or not ["npc", "event"].has(objects[trigger["object_id"]]["item"]["kind"]) or not objects[trigger["object_id"]]["item"]["event_ids"].has(id):
			errors.append("Interaction event/object references must agree.")
	elif trigger.get("kind") == "enter":
		if not _only(trigger, ["kind", "cells", "direction"]): errors.append("Unsupported enter trigger fields.")
		if not (trigger.get("cells") is Array) or trigger["cells"].is_empty():
			errors.append("Enter event needs explicit trigger cells.")
		else:
			for cell: Variant in trigger["cells"]:
				if not walkable(floors[str(int(event["floor"]))], cell): errors.append("Invalid enter trigger cell.")
		if trigger.has("direction") and (not pos(trigger["direction"]) or abs(int(trigger["direction"][0])) + abs(int(trigger["direction"][1])) != 1):
			errors.append("Enter direction must be a cardinal vector.")
	else:
		errors.append("Unsupported event trigger.")
	for condition: Variant in event["conditions"]:
		if not (condition is Dictionary) or not (condition.get("value") is bool):
			errors.append("Event conditions must be typed booleans.")
			continue
		if condition.get("kind") == "flag":
			if not _only(condition, ["kind", "flag", "value"]): errors.append("Unsupported flag condition fields.")
			if not content["flags"].has(condition.get("flag", "")): errors.append("Unknown condition flag.")
		elif condition.get("kind") == "cleared":
			if not _only(condition, ["kind", "object_id", "value"]): errors.append("Unsupported cleared condition fields.")
			if not objects.has(condition.get("object_id", "")) or not PICKUPS.has(objects[condition["object_id"]]["item"]["kind"]): errors.append("Unknown cleared condition object.")
		else:
			errors.append("Unsupported event condition.")
	for effect: Variant in event["effects"]:
		if not (effect is Dictionary):
			errors.append("Event effects must be typed dictionaries.")
			continue
		match str(effect.get("kind", "")):
			"set_flag":
				if not _only(effect, ["kind", "flag", "value"]): errors.append("Unsupported set_flag fields.")
				if not content["flags"].has(effect.get("flag", "")) or not (effect.get("value") is bool): errors.append("Invalid set_flag effect.")
			"grant":
				if not _only(effect, ["kind", "stat", "amount"]): errors.append("Unsupported stat grant fields.")
				if not STATS.has(effect.get("stat", "")) or not whole(effect.get("amount")) or int(effect["amount"]) < 1: errors.append("Invalid finite stat grant.")
			"grant_key":
				if not _only(effect, ["kind", "color", "amount"]): errors.append("Unsupported key grant fields.")
				if not content["initial_player"]["keys"].has(effect.get("color", "")) or not whole(effect.get("amount")) or int(effect["amount"]) < 1: errors.append("Invalid finite key grant.")
			"clear_object":
				if not _only(effect, ["kind", "object_id"]): errors.append("Unsupported object unlock fields.")
				if not objects.has(effect.get("object_id", "")) or not PICKUPS.has(objects[effect["object_id"]]["item"]["kind"]): errors.append("Invalid object unlock effect.")
			_:
				errors.append("Unsupported event effect.")


static func _validate_bounds(content: Dictionary, errors: Array[String]) -> void:
	# Conservative finite bounds prevent accepted events/shops from producing
	# a state that the frozen authority cannot later validate.
	var totals: Dictionary = {}
	for stat: String in STATS: totals[stat] = int(content["initial_player"][stat])
	for color: String in content["initial_player"]["keys"]: totals["key/" + color] = int(content["initial_player"]["keys"][color])
	for floor: Dictionary in content["floors"]:
		for item: Dictionary in floor["objects"]:
			var kind: String = str(item["kind"])
			if kind in ["potion", "atk", "def", "gold"]:
				_add_bound(totals, "hp" if kind == "potion" else kind, int(item["amount"]), errors)
			elif kind == "key":
				_add_bound(totals, "key/" + str(item["type"]), int(item["amount"]), errors)
			elif kind == "enemy":
				_add_bound(totals, "gold", int(content["enemies"][item["type"]]["gold"]), errors)
			elif kind == "shop":
				for offer: Dictionary in content["shops"][item["type"]]["offers"]:
					_add_bound(totals, "hp" if offer["kind"] in ["potion", "hp"] else str(offer["kind"]), int(offer["amount"]) * int(offer["limit"]), errors)
	for event: Dictionary in content["events"].values():
		for effect: Dictionary in event["effects"]:
			if effect["kind"] == "grant":
				_add_bound(totals, str(effect["stat"]), int(effect["amount"]), errors)
			elif effect["kind"] == "grant_key":
				_add_bound(totals, "key/" + str(effect["color"]), int(effect["amount"]), errors)


static func _add_bound(totals: Dictionary, stat: String, amount: int, errors: Array[String]) -> void:
	var current: int = int(totals.get(stat, 0))
	if amount > 2000000000 - current:
		errors.append("Finite resource upper bound exceeds the authority's safe range: " + stat)
	else:
		totals[stat] = current + amount


static func _only(value: Dictionary, fields: Array) -> bool:
	for key: Variant in value:
		if not (key is String) or not fields.has(key): return false
	return true


static func whole(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value)) and abs(float(value)) <= 2000000000.0


static func pos(value: Variant) -> bool:
	return value is Array and value.size() == 2 and whole(value[0]) and whole(value[1])


static func same_cell(a: Variant, b: Variant) -> bool:
	return pos(a) and pos(b) and int(a[0]) == int(b[0]) and int(a[1]) == int(b[1])


static func walkable(floor: Dictionary, cell: Variant) -> bool:
	if not pos(cell) or not (floor.get("grid") is Array): return false
	var x: int = int(cell[0])
	var y: int = int(cell[1])
	return y >= 0 and y < floor["grid"].size() and floor["grid"][y] is String and x >= 0 and x < str(floor["grid"][y]).length() and str(floor["grid"][y])[x] != "#"


static func _numbers_equal(value: Variant, expected: Array) -> bool:
	if not (value is Array) or value.size() != expected.size(): return false
	for index: int in range(expected.size()):
		if not whole(value[index]) or int(value[index]) != int(expected[index]): return false
	return true
