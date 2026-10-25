class_name CampaignVariant
extends RefCounted
## Pure, versioned layout transforms. No RNG, sequence state or canonical data is
## mutated here. All 43 draws belong to this one reproducible local stream.

const SPEC: String = "stairkeep-variant/xorshift32-hv-v1"
const MASK: int = 0xffffffff
const ZERO_SEED: int = 0x6d2b79f5
const FLOOR_COUNT: int = 21
const DRAW_COUNT: int = 43
const KINDS: Array[String] = ["key", "door", "enemy", "potion", "atk", "def", "gold", "stairs", "shop"]
const DELTAS: Array[Vector2i] = [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]


static func normalize_seed(value: Variant) -> String:
	var number: int = -1
	if value is int:
		number = value
	elif value is String:
		var word: String = str(value).to_lower()
		if word.length() != 8:
			return ""
		for letter: String in word:
			if not "0123456789abcdef".contains(letter):
				return ""
		number = word.hex_to_int()
	if number < 0 or number > MASK:
		return ""
	return "%08x" % (ZERO_SEED if number == 0 else number)


static func next32(value: int) -> int:
	var result: int = value & MASK
	result = (result ^ ((result << 13) & MASK)) & MASK
	result = (result ^ (result >> 17)) & MASK
	result = (result ^ ((result << 5) & MASK)) & MASK
	return result


static func transform_cell(cell: Array, width: int, height: int, h: bool, v: bool) -> Array:
	return [width - 1 - int(cell[0]) if h else int(cell[0]), height - 1 - int(cell[1]) if v else int(cell[1])]


static func canonical_json(value: Variant) -> String:
	var errors: Array[String] = []
	var normalized: Variant = _normalize_json(value, "", errors)
	return "" if not errors.is_empty() else JSON.stringify(normalized, "", true, true)


static func content_hash(value: Variant) -> String:
	var serialized: String = canonical_json(value)
	return "" if serialized.is_empty() else serialized.sha256_text()


static func validate(canonical: Dictionary) -> Dictionary:
	var errors: Array[String] = []
	if not (canonical.get("floors") is Array) or canonical["floors"].size() != FLOOR_COUNT:
		return {"ok": false, "errors": ["Canonical campaign must contain exactly 21 floors."]}
	if not (canonical.get("initial_player") is Dictionary) or not (canonical.get("enemies") is Dictionary) or not (canonical.get("shops") is Dictionary):
		return {"ok": false, "errors": ["initial_player, enemies and shops must be dictionaries."]}
	var initial: Dictionary = canonical["initial_player"]
	for stat: String in ["hp", "atk", "def", "gold"]:
		if not _whole(initial.get(stat)) or int(initial[stat]) < (1 if stat in ["hp", "atk"] else 0):
			errors.append("Invalid initial player " + stat)
	if not (initial.get("keys") is Dictionary) or initial["keys"].is_empty():
		errors.append("Player keys must declare nonempty colors.")
	else:
		for color: Variant in initial["keys"]:
			if not (color is String) or str(color).is_empty() or not _whole(initial["keys"][color]) or int(initial["keys"][color]) < 0:
				errors.append("Invalid initial key color/count.")
	_validate_catalogs(canonical, errors)
	var by_floor: Dictionary = {}
	var occupied: Dictionary = {}
	var ids: Dictionary = {}
	for floor_value: Variant in canonical["floors"]:
		if not (floor_value is Dictionary):
			errors.append("Floor entry must be a dictionary.")
			continue
		var floor_item: Dictionary = floor_value
		if not _whole(floor_item.get("id")) or int(floor_item["id"]) < 1 or int(floor_item["id"]) > FLOOR_COUNT:
			errors.append("Floor ID must be an integer in 1..21.")
			continue
		var floor_id: int = int(floor_item["id"])
		if by_floor.has(floor_id):
			errors.append("Duplicate floor ID %d." % floor_id)
			continue
		by_floor[floor_id] = floor_item
		if not _valid_grid(floor_item.get("grid")):
			errors.append("Floor %d grid must be a nonempty rectangle of # and ." % floor_id)
			continue
		if not _walkable(floor_item, floor_item.get("spawn")):
			errors.append("Floor %d spawn is not a walkable integer coordinate." % floor_id)
		if not (floor_item.get("objects") is Array):
			errors.append("Floor %d objects must be an array." % floor_id)
			continue
		var cells: Dictionary = {}
		occupied[floor_id] = cells
		# This rules version supports single-tile objects only. Refuse unhandled
		# geometry rather than reflecting its artwork but keeping stale triggers.
		for geometry_key: String in ["markers", "trigger_cells", "interactive_areas", "regions"]:
			if floor_item.has(geometry_key):
				var extra_geometry: Variant = floor_item[geometry_key]
				if not ((extra_geometry is Array or extra_geometry is Dictionary) and extra_geometry.is_empty()):
					errors.append("Unsupported coordinate field " + geometry_key)
		for object_value: Variant in floor_item["objects"]:
			if not (object_value is Dictionary):
				errors.append("Object entry must be a dictionary.")
				continue
			var item: Dictionary = object_value
			if not (item.get("id") is String) or str(item["id"]).is_empty() or ids.has(item["id"]):
				errors.append("Object IDs must be nonempty and globally unique.")
				continue
			ids[item["id"]] = true
			if not _walkable(floor_item, item.get("pos")):
				errors.append("Object %s is outside walkable grid." % item["id"])
				continue
			var coordinate: Vector2i = _cell(item["pos"])
			if cells.has(coordinate):
				errors.append("Objects overlap at floor %d %s." % [floor_id, coordinate])
			cells[coordinate] = item
			_validate_object(item, canonical, errors)
	for floor_id: int in range(1, FLOOR_COUNT + 1):
		if not by_floor.has(floor_id):
			errors.append("Missing floor ID %d." % floor_id)
	if not errors.is_empty():
		return {"ok": false, "errors": errors}
	_validate_stairs(by_floor, occupied, errors)
	_validate_safe_starts(by_floor[1], occupied[1], errors)
	if canonical.has("variant_spawn_candidates") and canonical_json(canonical["variant_spawn_candidates"]) != canonical_json(by_floor[1].get("safe_start_candidates")):
		errors.append("Root spawn-candidate alias differs from the first-floor canonical candidates.")
	var json_errors: Array[String] = []
	_normalize_json(canonical, "", json_errors)
	errors.append_array(json_errors)
	return {"ok": errors.is_empty(), "errors": errors}


static func generate(canonical: Dictionary, input_seed: Variant) -> Dictionary:
	var seed: String = normalize_seed(input_seed)
	if seed.is_empty():
		return {"ok": false, "message": "Seed must be a uint32 or eight hexadecimal digits."}
	var checked: Dictionary = validate(canonical)
	if not bool(checked["ok"]):
		return {"ok": false, "message": "Canonical content validation failed.", "errors": checked["errors"]}
	var source: Dictionary = canonical.duplicate(true)
	var floors: Array = source["floors"]
	floors.sort_custom(_floor_less)
	var mirrors: Dictionary = {}
	var draws: Array[int] = []
	var local_state: int = seed.hex_to_int()
	for floor_id: int in range(1, FLOOR_COUNT + 1):
		local_state = next32(local_state)
		draws.append(local_state)
		var horizontal: bool = (local_state & 1) != 0
		local_state = next32(local_state)
		draws.append(local_state)
		mirrors[str(floor_id)] = {"h": horizontal, "v": (local_state & 1) != 0}
	local_state = next32(local_state)
	draws.append(local_state)
	var candidates: Array = floors[0]["safe_start_candidates"]
	var chosen: Array = candidates[local_state % candidates.size()]
	var by_id: Dictionary = {}
	for floor_item: Dictionary in floors:
		by_id[int(floor_item["id"])] = floor_item
	var variant: Dictionary = source.duplicate(true)
	for floor_item: Dictionary in variant["floors"]:
		var floor_id: int = int(floor_item["id"])
		var source_floor: Dictionary = by_id[floor_id]
		var flags: Dictionary = mirrors[str(floor_id)]
		var grid: Array = source_floor["grid"]
		var width: int = str(grid[0]).length()
		var height: int = grid.size()
		var new_grid: Array[String] = []
		for y: int in range(height):
			var source_y: int = height - 1 - y if bool(flags["v"]) else y
			var row: String = str(grid[source_y])
			new_grid.append(row.reverse() if bool(flags["h"]) else row)
		floor_item["grid"] = new_grid
		floor_item["spawn"] = transform_cell(source_floor["spawn"], width, height, flags["h"], flags["v"])
		if floor_item.has("safe_start_candidates"):
			var transformed_candidates: Array = []
			for candidate: Array in source_floor["safe_start_candidates"]:
				transformed_candidates.append(transform_cell(candidate, width, height, flags["h"], flags["v"]))
			floor_item["safe_start_candidates"] = transformed_candidates
		for item: Dictionary in floor_item["objects"]:
			item["pos"] = transform_cell(item["pos"], width, height, flags["h"], flags["v"])
			if item.has("facing"):
				var facing: Array = item["facing"]
				item["facing"] = [-int(facing[0]) if flags["h"] else int(facing[0]), -int(facing[1]) if flags["v"] else int(facing[1])]
			if item["kind"] == "stairs":
				var target: Dictionary = item["target"]
				var destination: Dictionary = by_id[int(target["floor"])]
				var target_flags: Dictionary = mirrors[str(int(target["floor"]))]
				target["pos"] = transform_cell(target["pos"], str(destination["grid"][0]).length(), destination["grid"].size(), target_flags["h"], target_flags["v"])
	var first_flags: Dictionary = mirrors["1"]
	var resolved_start: Array = transform_cell(chosen, str(floors[0]["grid"][0]).length(), floors[0]["grid"].size(), first_flags["h"], first_flags["v"])
	variant["floors"][0]["spawn"] = resolved_start.duplicate()
	if variant.has("variant_spawn_candidates"):
		variant["variant_spawn_candidates"] = variant["floors"][0]["safe_start_candidates"].duplicate(true)
	return {
		"ok": true, "message": "", "data": variant, "seed": seed,
		"mirrors": mirrors, "resolved_start": resolved_start, "draw_count": DRAW_COUNT,
		"canonical_sha256": content_hash(canonical), "transformed_sha256": content_hash(variant),
		"draws": draws,
	}


static func _validate_catalogs(canonical: Dictionary, errors: Array[String]) -> void:
	for enemy_id: Variant in canonical["enemies"]:
		var enemy_value: Variant = canonical["enemies"][enemy_id]
		if not (enemy_id is String) or not (enemy_value is Dictionary):
			errors.append("Invalid enemy catalog entry.")
			continue
		var enemy: Dictionary = enemy_value
		for stat: String in ["hp", "atk", "def", "gold"]:
			if not _whole(enemy.get(stat)) or int(enemy[stat]) < (1 if stat == "hp" else 0):
				errors.append("Invalid enemy %s %s." % [enemy_id, stat])
	for shop_id: Variant in canonical["shops"]:
		var shop_value: Variant = canonical["shops"][shop_id]
		if not (shop_id is String) or not (shop_value is Dictionary) or not (shop_value.get("offers") is Array):
			errors.append("Invalid shop catalog entry.")
			continue
		var offer_ids: Dictionary = {}
		for offer_value: Variant in shop_value["offers"]:
			if not (offer_value is Dictionary):
				errors.append("Invalid shop offer.")
				continue
			var offer: Dictionary = offer_value
			if not (offer.get("id") is String) or str(offer["id"]).is_empty() or offer_ids.has(offer["id"]):
				errors.append("Shop offer IDs must be nonempty and unique within each shop.")
			else:
				offer_ids[offer["id"]] = true
			if not str(offer.get("kind", "")) in ["atk", "def", "potion"]:
				errors.append("Unsupported shop offer kind.")
			for stat: String in ["cost", "amount", "limit"]:
				if not _whole(offer.get(stat)) or int(offer[stat]) < (0 if stat == "cost" else 1):
					errors.append("Invalid shop offer " + stat)


static func _validate_object(item: Dictionary, canonical: Dictionary, errors: Array[String]) -> void:
	var kind: String = str(item.get("kind", ""))
	if not kind in KINDS:
		errors.append("Unsupported object kind on " + str(item["id"]))
	if kind == "enemy" and not canonical["enemies"].has(item.get("type", "")):
		errors.append("Unknown enemy type on " + str(item["id"]))
	if kind == "shop" and not canonical["shops"].has(item.get("type", "")):
		errors.append("Unknown shop type on " + str(item["id"]))
	if kind in ["key", "door"]:
		var keys_value: Variant = canonical["initial_player"].get("keys")
		if not (keys_value is Dictionary) or not keys_value.has(item.get("type", "")):
			errors.append("Unknown key color on " + str(item["id"]))
	if kind in ["key", "potion", "atk", "def", "gold"]:
		if not _whole(item.get("amount", 1)) or int(item.get("amount", 1)) < 1:
			errors.append("Pickup amount must be positive on " + str(item["id"]))
	if item.has("facing") and not _valid_pos(item["facing"]):
		errors.append("Facing must be an integer vector on " + str(item["id"]))
	for geometry_key: String in ["cells", "rect", "area", "trigger_cells"]:
		if item.has(geometry_key):
			errors.append("Unsupported multi-cell object field " + geometry_key)


static func _validate_stairs(floors: Dictionary, occupied: Dictionary, errors: Array[String]) -> void:
	for floor_id: int in range(1, FLOOR_COUNT + 1):
		for item: Dictionary in floors[floor_id]["objects"]:
			if item["kind"] != "stairs":
				continue
			if not (item.get("target") is Dictionary):
				errors.append("Stair target must be a dictionary: " + str(item["id"]))
				continue
			var target: Dictionary = item["target"]
			if not _whole(target.get("floor")) or not floors.has(int(target["floor"])) or int(target["floor"]) == floor_id:
				errors.append("Stair target floor is invalid: " + str(item["id"]))
				continue
			var target_floor: int = int(target["floor"])
			if not _walkable(floors[target_floor], target.get("pos")):
				errors.append("Stair target is not walkable: " + str(item["id"]))
				continue
			var destination: Dictionary = occupied[target_floor].get(_cell(target["pos"]), {})
			if destination.is_empty() or destination.get("kind", "") != "stairs":
				errors.append("Stair target must land on its return stair: " + str(item["id"]))
				continue
			if target.has("object_id") and target["object_id"] != destination["id"]:
				errors.append("Stair target object ID differs: " + str(item["id"]))
			var return_target: Variant = destination.get("target")
			if not (return_target is Dictionary) or not _whole(return_target.get("floor")) or int(return_target["floor"]) != floor_id or not _valid_pos(return_target.get("pos")) or _cell(return_target["pos"]) != _cell(item["pos"]):
				errors.append("Stair link is not reciprocal: " + str(item["id"]))
			if item.has("direction") and str(item["direction"]) != ("up" if target_floor > floor_id else "down"):
				errors.append("Stair direction conflicts with destination floor: " + str(item["id"]))


static func _validate_safe_starts(first: Dictionary, occupied: Dictionary, errors: Array[String]) -> void:
	if not (first.get("safe_start_candidates") is Array) or first["safe_start_candidates"].is_empty():
		errors.append("First floor must declare safe_start_candidates.")
		return
	var spawn: Vector2i = _cell(first["spawn"])
	if occupied.has(spawn):
		errors.append("First-floor default spawn must be an empty tile.")
		return
	var queue: Array[Vector2i] = [spawn]
	var component: Dictionary = {spawn: true}
	while not queue.is_empty():
		var current: Vector2i = queue.pop_front()
		for delta: Vector2i in DELTAS:
			var next: Vector2i = current + delta
			if component.has(next) or occupied.has(next) or not _walkable(first, [next.x, next.y]):
				continue
			component[next] = true
			queue.append(next)
	var previous: Vector2i = Vector2i(-1, -1)
	for candidate: Variant in first["safe_start_candidates"]:
		if not _walkable(first, candidate):
			errors.append("Safe start candidate is not walkable.")
			continue
		var point: Vector2i = _cell(candidate)
		if point.y < previous.y or (point.y == previous.y and point.x <= previous.x):
			errors.append("Safe start candidates must be unique and sorted by (y,x).")
		previous = point
		if occupied.has(point) or not component.has(point):
			errors.append("Safe start candidate is occupied or outside the default empty component.")
		for delta: Vector2i in DELTAS:
			var neighbor: Dictionary = occupied.get(point + delta, {})
			if neighbor.get("kind", "") == "enemy":
				errors.append("Safe start candidate has an adjacent enemy.")


static func _valid_grid(value: Variant) -> bool:
	if not (value is Array) or value.is_empty() or not (value[0] is String) or str(value[0]).is_empty():
		return false
	var width: int = str(value[0]).length()
	for row: Variant in value:
		if not (row is String) or str(row).length() != width:
			return false
		for letter: String in str(row):
			if letter != "#" and letter != ".":
				return false
	return true


static func _walkable(floor_item: Dictionary, coordinate: Variant) -> bool:
	if not _valid_pos(coordinate):
		return false
	var grid: Array = floor_item["grid"]
	var x: int = int(coordinate[0])
	var y: int = int(coordinate[1])
	return y >= 0 and y < grid.size() and x >= 0 and x < str(grid[y]).length() and str(grid[y])[x] == "."


static func _whole(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value)) and abs(float(value)) <= 2000000000.0


static func _valid_pos(value: Variant) -> bool:
	return value is Array and value.size() == 2 and _whole(value[0]) and _whole(value[1])


static func _cell(value: Array) -> Vector2i:
	return Vector2i(int(value[0]), int(value[1]))


static func _floor_less(a: Dictionary, b: Dictionary) -> bool:
	return int(a["id"]) < int(b["id"])


static func _object_less(a: Dictionary, b: Dictionary) -> bool:
	return str(a["id"]) < str(b["id"])


static func _normalize_json(value: Variant, field: String, errors: Array[String]) -> Variant:
	if value is Dictionary:
		var result: Dictionary = {}
		for key: Variant in value:
			if not (key is String):
				errors.append("Canonical JSON dictionary keys must be strings.")
				continue
			result[key] = _normalize_json(value[key], str(key), errors)
		return result
	if value is Array:
		var result: Array = []
		for entry: Variant in value:
			result.append(_normalize_json(entry, "", errors))
		if field == "floors":
			if result.all(func(entry: Variant) -> bool: return entry is Dictionary and entry.has("id")):
				result.sort_custom(_floor_less)
		elif field == "objects":
			if result.all(func(entry: Variant) -> bool: return entry is Dictionary and entry.has("id")):
				result.sort_custom(_object_less)
		elif field in ["cleared", "cleared_object_ids"]:
			result.sort()
		return result
	if value is float:
		if not is_finite(value) or value != floorf(value):
			errors.append("Canonical JSON numbers must be finite integers.")
			return null
		return int(value)
	if value == null or value is int or value is bool or value is String:
		return value
	errors.append("Unsupported value in canonical JSON.")
	return null
