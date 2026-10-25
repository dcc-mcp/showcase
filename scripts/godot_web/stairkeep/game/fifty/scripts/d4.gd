class_name FiftyD4
extends RefCounted
## Independent D4 geometry/selection protocol. No active state, save or global RNG.
## The signature is a conservative novelty key, never a save-equivalence proof.

const SPEC: String = "fifty/xorshift32-d4-v1"
const MASK: int = 0xffffffff
const ZERO_SEED: int = 0x6d2b79f5
const CODE_NAMES: Array[String] = ["identity", "rot90", "rot180", "rot270", "mirror_x", "mirror_x_rot90", "mirror_x_rot180", "mirror_x_rot270"]
const MATRICES: Array = [[1, 0, 0, 1], [0, -1, 1, 0], [-1, 0, 0, -1], [0, 1, -1, 0], [-1, 0, 0, 1], [0, -1, -1, 0], [1, 0, 0, -1], [0, 1, 1, 0]]
const COMPASS: Dictionary = {"north": [0, -1], "east": [1, 0], "south": [0, 1], "west": [-1, 0]}


static func normalize_seed(value: Variant) -> String:
	var number: int = -1
	if value is int:
		number = int(value)
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


static func canonical_json(value: Variant) -> String:
	var errors: Array[String] = []
	var normalized: Variant = _normalize(value, errors)
	return "" if not errors.is_empty() else JSON.stringify(normalized, "", true, true)


static func content_hash(value: Variant) -> String:
	var serialized: String = canonical_json(value)
	return "" if serialized.is_empty() else serialized.sha256_text()


static func freeze_tree(value: Variant) -> Variant:
	if value is Dictionary:
		for key: Variant in value:
			freeze_tree(value[key])
		value.make_read_only()
	elif value is Array:
		for child: Variant in value:
			freeze_tree(child)
		value.make_read_only()
	return value


static func transform_vector(value: Array, code: int) -> Array:
	if not _cell(value) or not _code(code):
		return []
	var matrix: Array = MATRICES[code]
	var x: int = int(value[0])
	var y: int = int(value[1])
	return [int(matrix[0]) * x + int(matrix[1]) * y, int(matrix[2]) * x + int(matrix[3]) * y]


static func transform_dimensions(width: int, height: int, code: int) -> Array:
	if width < 1 or height < 1 or not _code(code):
		return []
	var matrix: Array = MATRICES[code]
	return [absi(int(matrix[0])) * width + absi(int(matrix[1])) * height, absi(int(matrix[2])) * width + absi(int(matrix[3])) * height]


static func transform_cell(value: Array, width: int, height: int, code: int) -> Array:
	if not _inside(value, width, height) or not _code(code):
		return []
	var matrix: Array = MATRICES[code]
	var mapped: Array = transform_vector(value, code)
	var tx: int = mini(0, int(matrix[0]) * (width - 1)) + mini(0, int(matrix[1]) * (height - 1))
	var ty: int = mini(0, int(matrix[2]) * (width - 1)) + mini(0, int(matrix[3]) * (height - 1))
	return [int(mapped[0]) - tx, int(mapped[1]) - ty]


static func compose(after: int, before: int) -> int:
	if not _code(after) or not _code(before):
		return -1
	var left: Array = MATRICES[after]
	var right: Array = MATRICES[before]
	var product: Array = [int(left[0]) * int(right[0]) + int(left[1]) * int(right[2]), int(left[0]) * int(right[1]) + int(left[1]) * int(right[3]), int(left[2]) * int(right[0]) + int(left[3]) * int(right[2]), int(left[2]) * int(right[1]) + int(left[3]) * int(right[3])]
	for candidate: int in range(8):
		if product == MATRICES[candidate]:
			return candidate
	return -1


static func inverse(code: int) -> int:
	if not _code(code):
		return -1
	for candidate: int in range(8):
		if compose(candidate, code) == 0:
			return candidate
	return -1


static func transform_direction(name: String, code: int) -> String:
	if not COMPASS.has(name) or not _code(code):
		return ""
	var mapped: Array = transform_vector(COMPASS[name], code)
	for label: String in COMPASS:
		if COMPASS[label] == mapped:
			return label
	return ""


static func transform_grid(rows: Array, code: int) -> Array:
	var size: Array = _grid_size(rows)
	if size.is_empty() or not _code(code):
		return []
	var width: int = int(size[0])
	var height: int = int(size[1])
	var output_size: Array = transform_dimensions(width, height, code)
	var buffers: Array = []
	for y: int in range(int(output_size[1])):
		var row: Array = []
		row.resize(int(output_size[0]))
		buffers.append(row)
	for y: int in range(height):
		for x: int in range(width):
			var target: Array = transform_cell([x, y], width, height, code)
			buffers[int(target[1])][int(target[0])] = str(rows[y])[x]
	var result: Array = []
	for row: Array in buffers:
		var line: String = ""
		for letter: Variant in row:
			line += str(letter)
		result.append(line)
	return result


static func transform(canonical: Dictionary, codes: Dictionary) -> Dictionary:
	var index: Dictionary = _index(canonical)
	if not index["ok"]:
		return index
	var floors: Dictionary = index["floors"]
	if codes.size() != floors.size():
		return _fail("One explicit transform is required for every authored floor.")
	for key: Variant in codes:
		if not (key is String) or not floors.has(key) or not _whole(codes[key]) or not _code(int(codes[key])):
			return _fail("Invalid floor ID or D4 code.")
	var result: Dictionary = canonical.duplicate(true)
	for floor_item: Dictionary in result["floors"]:
		var floor_id: String = str(int(floor_item["id"]))
		var source: Dictionary = floors[floor_id]
		var width: int = str(source["grid"][0]).length()
		var height: int = source["grid"].size()
		var code: int = int(codes[floor_id])
		var dimensions: Array = transform_dimensions(width, height, code)
		floor_item["grid"] = transform_grid(source["grid"], code)
		if floor_item.has("width"):
			floor_item["width"] = dimensions[0]
		if floor_item.has("height"):
			floor_item["height"] = dimensions[1]
		if floor_item.has("spawn"):
			floor_item["spawn"] = transform_cell(source["spawn"], width, height, code)
		if floor_item.has("safe_start_candidates"):
			floor_item["safe_start_candidates"] = _map_cells(source["safe_start_candidates"], width, height, code)
		if floor_item.get("topology") is Dictionary and floor_item["topology"].get("room_centers") is Dictionary:
			for room: Variant in floor_item["topology"]["room_centers"]:
				floor_item["topology"]["room_centers"][room] = transform_cell(source["topology"]["room_centers"][room], width, height, code)
		for item: Dictionary in floor_item["objects"]:
			item["pos"] = transform_cell(item["pos"], width, height, code)
			if item.has("facing"):
				item["facing"] = transform_direction(item["facing"], code) if item["facing"] is String else transform_vector(item["facing"], code)
			if item.has("direction_vector"):
				item["direction_vector"] = transform_vector(item["direction_vector"], code)
			if item.has("direction_condition"):
				item["direction_condition"]["vector"] = transform_vector(item["direction_condition"]["vector"], code)
			if item["kind"] == "stairs":
				var target: Dictionary = item["target"]
				var destination_id: String = str(int(target["floor"]))
				var destination: Dictionary = floors[destination_id]
				target["pos"] = transform_cell(target["pos"], str(destination["grid"][0]).length(), destination["grid"].size(), int(codes[destination_id]))
	if result.has("variant_spawn_candidates"):
		var first_id: String = str(int(index["floor_ids"][0]))
		var first: Dictionary = floors[first_id]
		result["variant_spawn_candidates"] = _map_cells(canonical["variant_spawn_candidates"], str(first["grid"][0]).length(), first["grid"].size(), int(codes[first_id]))
	for event_id: Variant in result.get("events", {}):
		var event: Dictionary = result["events"][event_id]
		var source_floor: Dictionary = floors[str(int(event["floor"]))]
		var trigger: Dictionary = event["trigger"]
		var code: int = int(codes[str(int(event["floor"]))])
		if trigger["kind"] == "enter":
			trigger["cells"] = _map_cells(trigger["cells"], str(source_floor["grid"][0]).length(), source_floor["grid"].size(), code)
			if trigger.has("direction"):
				trigger["direction"] = transform_vector(trigger["direction"], code)
	var checked: Dictionary = _index(result)
	return checked if not checked["ok"] else {"ok": true, "data": result}


static func generate(canonical: Dictionary, seed: Variant, previous_layout_signature: String = "") -> Dictionary:
	var normalized_seed: String = normalize_seed(seed)
	if normalized_seed.is_empty():
		return _fail("Seed must be a uint32 integer or eight hexadecimal digits.")
	var index: Dictionary = _index(canonical)
	if not index["ok"]:
		return index
	var canonical_sha: String = content_hash(canonical)
	if canonical_sha.is_empty():
		return _fail("Content is not canonical integer JSON.")
	var state: int = normalized_seed.hex_to_int()
	var base_codes: Dictionary = {}
	var draws: Array = []
	for floor_id: int in index["floor_ids"]:
		state = next32(state)
		draws.append(state)
		base_codes[str(floor_id)] = state % 8
	var candidate_signatures: Array = []
	var candidate_groups: Array = []
	var signatures_seen: Dictionary = {}
	var layouts: Dictionary = {}
	var maps: Dictionary = {}
	var original_signature_result: Dictionary = _signature(canonical)
	if not original_signature_result["ok"]:
		return original_signature_result
	var comparison_signature: String = previous_layout_signature if not previous_layout_signature.is_empty() else str(original_signature_result["signature"])
	for global_code: int in range(8):
		var choices: Dictionary = {}
		for floor_id: int in index["floor_ids"]:
			choices[str(floor_id)] = compose(global_code, int(base_codes[str(floor_id)]))
		var transformed: Dictionary = transform(canonical, choices)
		if not transformed["ok"]:
			return transformed
		var signature_result: Dictionary = _signature(transformed["data"])
		if not signature_result["ok"]:
			return signature_result
		var signature: String = signature_result["signature"]
		candidate_signatures.append(signature)
		if signatures_seen.has(signature):
			candidate_groups[int(signatures_seen[signature])]["global_codes"].append(global_code)
		else:
			signatures_seen[signature] = candidate_groups.size()
			candidate_groups.append({"signature": signature, "global_codes": [global_code], "representative_code": global_code})
			layouts[signature] = transformed["data"]
			maps[signature] = choices
	var eligible_signatures: Array = []
	var eligible_global_codes: Array = []
	for group: Dictionary in candidate_groups:
		if str(group["signature"]) != previous_layout_signature:
			eligible_signatures.append(group["signature"])
			eligible_global_codes.append(group["representative_code"])
	var spatial_change_possible: bool = false
	for signature: String in candidate_signatures:
		if signature != comparison_signature:
			spatial_change_possible = true
	if eligible_signatures.is_empty():
		for group: Dictionary in candidate_groups:
			eligible_signatures.append(group["signature"])
			eligible_global_codes.append(group["representative_code"])
	state = next32(state)
	draws.append(state)
	var selected_index: int = state % eligible_signatures.size()
	var selected_signature: String = eligible_signatures[selected_index]
	var data: Dictionary = layouts[selected_signature]
	var receipt: Dictionary = {"spec": SPEC, "base_codes": base_codes, "all_codes": [0, 1, 2, 3, 4, 5, 6, 7], "candidate_signatures": candidate_signatures, "candidate_groups": candidate_groups, "eligible_signatures": eligible_signatures, "eligible_global_codes": eligible_global_codes, "selected_index": selected_index, "selected_global_code": eligible_global_codes[selected_index], "draw_count": draws.size(), "draws": draws, "rng_final": "%08x" % state, "previous_signature": previous_layout_signature, "comparison_signature": comparison_signature, "spatial_change_possible": spatial_change_possible}
	return {"ok": true, "data": data, "seed": normalized_seed, "transforms": maps[selected_signature].duplicate(true), "layout_sha256": content_hash(data), "layout_signature": selected_signature, "selection_receipt": receipt, "canonical_sha256": canonical_sha}


static func _normalize(value: Variant, errors: Array[String]) -> Variant:
	if value is Dictionary:
		var result: Dictionary = {}
		for key: Variant in value:
			if not (key is String):
				errors.append("Non-string JSON key.")
				continue
			result[key] = _normalize(value[key], errors)
		return result
	if value is Array:
		var result: Array = []
		for item: Variant in value:
			result.append(_normalize(item, errors))
		return result
	if value is float:
		if not is_finite(value) or value != floorf(value) or absf(value) > 9007199254740991.0:
			errors.append("Non-integer or unsafe JSON number.")
			return null
		return int(value)
	if value == null or value is bool or value is int or value is String:
		return value
	errors.append("Unsupported JSON value.")
	return null


static func _whole(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value)) and absf(float(value)) <= 2000000000.0


static func _cell(value: Variant) -> bool:
	return value is Array and value.size() == 2 and _whole(value[0]) and _whole(value[1])


static func _inside(value: Variant, width: int, height: int) -> bool:
	return _cell(value) and width > 0 and height > 0 and int(value[0]) >= 0 and int(value[0]) < width and int(value[1]) >= 0 and int(value[1]) < height


static func _code(value: int) -> bool:
	return value >= 0 and value < 8


static func _grid_size(value: Variant) -> Array:
	if not (value is Array) or value.is_empty() or not (value[0] is String) or str(value[0]).is_empty():
		return []
	var width: int = str(value[0]).length()
	for row: Variant in value:
		if not (row is String) or str(row).length() != width:
			return []
	return [width, value.size()]


static func _map_cells(cells: Array, width: int, height: int, code: int) -> Array:
	var result: Array = []
	for cell: Array in cells:
		result.append(transform_cell(cell, width, height, code))
	return result


static func _fail(message: String) -> Dictionary:
	return {"ok": false, "message": message}


static func _index(canonical: Dictionary) -> Dictionary:
	# The caller owns complete content validation; this guard keeps malformed
	# geometry/references from producing partially transformed data.
	if not (canonical.get("floors") is Array) or canonical["floors"].is_empty():
		return _fail("No authored floors.")
	for field: String in ["initial_player", "enemies", "shops", "completion"]:
		if canonical.has(field) and not (canonical[field] is Dictionary):
			return _fail("Malformed content dictionary: " + field)
	if canonical.get("initial_player") is Dictionary and canonical["initial_player"].has("keys") and not (canonical["initial_player"]["keys"] is Dictionary):
		return _fail("Malformed initial key dictionary.")
	var floors: Dictionary = {}
	var objects: Dictionary = {}
	var floor_ids: Array[int] = []
	for value: Variant in canonical["floors"]:
		if not (value is Dictionary) or not _whole(value.get("id")) or int(value["id"]) < 1 or not (value.get("objects") is Array):
			return _fail("Malformed authored floor.")
		var floor_item: Dictionary = value
		var floor_id: int = int(floor_item["id"])
		var key: String = str(floor_id)
		var size: Array = _grid_size(floor_item.get("grid"))
		if floors.has(key) or size.is_empty():
			return _fail("Duplicate floor ID or nonrectangular grid.")
		var width: int = int(size[0])
		var height: int = int(size[1])
		if (floor_item.has("width") and (not _whole(floor_item["width"]) or int(floor_item["width"]) != width)) or (floor_item.has("height") and (not _whole(floor_item["height"]) or int(floor_item["height"]) != height)):
			return _fail("Declared floor dimensions differ from the grid.")
		for field: String in ["spawn"]:
			if floor_item.has(field) and not _inside(floor_item[field], width, height):
				return _fail("Invalid floor spawn.")
		if floor_item.has("safe_start_candidates"):
			if not _valid_cells(floor_item["safe_start_candidates"], width, height):
				return _fail("Invalid safe-start coordinates.")
		if floor_item.get("topology") is Dictionary and floor_item["topology"].has("room_centers"):
			if not (floor_item["topology"]["room_centers"] is Dictionary):
				return _fail("Invalid room-center map.")
			for room: Variant in floor_item["topology"]["room_centers"]:
				if not _inside(floor_item["topology"]["room_centers"][room], width, height):
					return _fail("Invalid room-center coordinate.")
		var occupied: Dictionary = {}
		for object_value: Variant in floor_item["objects"]:
			if not (object_value is Dictionary):
				return _fail("Malformed object.")
			var item: Dictionary = object_value
			if not (item.get("id") is String) or str(item["id"]).is_empty() or objects.has(item["id"]) or not (item.get("kind") is String) or not _inside(item.get("pos"), width, height):
				return _fail("Invalid object identity or coordinate.")
			var cell_key: String = canonical_json(item["pos"])
			if occupied.has(cell_key):
				return _fail("Overlapping object coordinates.")
			occupied[cell_key] = true
			if item.has("facing") and ((item["facing"] is String and not COMPASS.has(item["facing"])) or (not (item["facing"] is String) and not _cell(item["facing"]))):
				return _fail("Unsupported facing.")
			if item.has("direction_vector") and not _cell(item["direction_vector"]):
				return _fail("Malformed direction vector.")
			if item.has("direction_condition") and (not (item["direction_condition"] is Dictionary) or not _cell(item["direction_condition"].get("vector")) or not str(item["direction_condition"].get("mode", "")) in ["approach", "facing"]):
				return _fail("Unsupported direction condition.")
			if item.has("event_ids") and not (item["event_ids"] is Array):
				return _fail("Attached event IDs must be an array.")
			for unsupported: String in ["cells", "rect", "area", "path", "trigger", "triggers", "trigger_cells"]:
				if item.has(unsupported):
					return _fail("Object geometry requires an explicit adapter: " + unsupported)
			objects[item["id"]] = {"floor": floor_id, "object": item}
		floors[key] = floor_item
		floor_ids.append(floor_id)
	floor_ids.sort()
	for record: Dictionary in objects.values():
		var item: Dictionary = record["object"]
		if item["kind"] != "stairs":
			continue
		if not (item.get("target") is Dictionary):
			return _fail("Malformed stair target.")
		var target: Dictionary = item["target"]
		if not _whole(target.get("floor")) or not floors.has(str(int(target["floor"]))) or not (target.get("object_id") is String) or not objects.has(target["object_id"]):
			return _fail("Missing stair target floor/object.")
		var target_record: Dictionary = objects[target["object_id"]]
		var target_item: Dictionary = target_record["object"]
		if int(target_record["floor"]) != int(target["floor"]) or target_item["kind"] != "stairs" or canonical_json(target.get("pos")) != canonical_json(target_item["pos"]):
			return _fail("Stair target coordinates and identity disagree.")
		if item.get("direction") != ("up" if int(target["floor"]) > int(record["floor"]) else "down"):
			return _fail("Stair direction disagrees with destination floor.")
		var reverse_value: Variant = target_item.get("target")
		if not (reverse_value is Dictionary) or reverse_value.get("object_id") != item["id"] or not _whole(reverse_value.get("floor")) or int(reverse_value["floor"]) != int(record["floor"]) or canonical_json(reverse_value.get("pos")) != canonical_json(item["pos"]):
			return _fail("Stair link is not reciprocal.")
	if canonical.has("variant_spawn_candidates"):
		var first: Dictionary = floors[str(floor_ids[0])]
		if not _valid_cells(canonical["variant_spawn_candidates"], str(first["grid"][0]).length(), first["grid"].size()):
			return _fail("Malformed root spawn candidates.")
		if first.has("safe_start_candidates") and canonical_json(canonical["variant_spawn_candidates"]) != canonical_json(first["safe_start_candidates"]):
			return _fail("Spawn aliases disagree.")
	if not (canonical.get("events", {}) is Dictionary) or not (canonical.get("flags", {}) is Dictionary):
		return _fail("Events and flags must be dictionaries.")
	for record: Dictionary in objects.values():
		for event_id: Variant in record["object"].get("event_ids", []):
			if not (event_id is String) or not canonical.get("events", {}).has(event_id):
				return _fail("Unknown attached event ID.")
	for event_id: Variant in canonical.get("events", {}):
		var event_value: Variant = canonical["events"][event_id]
		if not (event_id is String) or not (event_value is Dictionary):
			return _fail("Malformed event identity.")
		var event: Dictionary = event_value
		if not _whole(event.get("floor")) or not floors.has(str(int(event["floor"]))) or not (event.get("trigger") is Dictionary):
			return _fail("Malformed event floor/trigger.")
		var floor_item: Dictionary = floors[str(int(event["floor"]))]
		var trigger: Dictionary = event["trigger"]
		if trigger.get("kind") == "enter":
			if not _valid_cells(trigger.get("cells"), str(floor_item["grid"][0]).length(), floor_item["grid"].size()) or trigger["cells"].is_empty():
				return _fail("Malformed enter-event cells.")
			if trigger.has("direction") and (not _cell(trigger["direction"]) or absi(int(trigger["direction"][0])) + absi(int(trigger["direction"][1])) != 1):
				return _fail("Enter-event direction must be a cardinal unit vector.")
		elif trigger.get("kind") == "interact":
			if not (trigger.get("object_id") is String) or not objects.has(trigger["object_id"]) or int(objects[trigger["object_id"]]["floor"]) != int(event["floor"]):
				return _fail("Malformed event interaction target.")
		else:
			return _fail("Unsupported event trigger kind.")
		if not (event.get("conditions", []) is Array) or not (event.get("effects", []) is Array):
			return _fail("Malformed event conditions/effects.")
		if not _event_semantics(event, canonical, objects):
			return _fail("Unsupported or malformed event conditions/effects.")
	return {"ok": true, "floors": floors, "objects": objects, "floor_ids": floor_ids}


static func _valid_cells(value: Variant, width: int, height: int) -> bool:
	if not (value is Array):
		return false
	for cell: Variant in value:
		if not _inside(cell, width, height):
			return false
	return true


static func _signature(data: Dictionary) -> Dictionary:
	var index: Dictionary = _index(data)
	if not index["ok"]:
		return index
	var errors: Array[String] = []
	var rows: Array = []
	for floor_id: int in index["floor_ids"]:
		var floor_item: Dictionary = index["floors"][str(floor_id)]
		var entities: Array = []
		for item: Dictionary in floor_item["objects"]:
			entities.append(_object_projection(item, floor_id, data, index, errors, true))
		_sort_json(entities)
		var row: Dictionary = {"floor": floor_id, "grid": floor_item["grid"], "spawn": floor_item.get("spawn"), "objects": entities}
		# Only the actual spawn denotes this run's start. Candidate-list ordering,
		# room labels and source witness metadata cannot manufacture novelty.
		rows.append(row)
	var events: Array = []
	for event_id: Variant in data.get("events", {}):
		events.append(_event_projection(data["events"][event_id], data, index, errors))
	_sort_json(events)
	var flags: Array = []
	for flag: Variant in data.get("flags", {}):
		flags.append(_flag_projection(str(flag), data, index, errors))
	_sort_json(flags)
	var projection: Dictionary = {"floors": rows, "events": events, "flags": flags}
	if data.get("completion") is Dictionary and data["completion"].has("slice_goal_object_id"):
		projection["completion"] = _object_reference(data["completion"]["slice_goal_object_id"], data, index, errors)
	if not errors.is_empty():
		return _fail(errors[0])
	var signature: String = content_hash(projection)
	return _fail("Encounter projection is not integer JSON.") if signature.is_empty() else {"ok": true, "signature": signature}


static func layout_signature(data: Dictionary) -> String:
	var result: Dictionary = _signature(data)
	return str(result.get("signature", ""))


static func _object_projection(item: Dictionary, floor_id: int, data: Dictionary, index: Dictionary, errors: Array[String], include_events: bool) -> Dictionary:
	var result: Dictionary = {"floor": floor_id, "kind": item["kind"], "pos": item["pos"]}
	for field: String in ["amount", "victory", "slice_goal", "hidden", "appearance", "facing", "direction_vector", "direction_condition"]:
		if item.has(field):
			result[field] = item[field]
	var kind: String = str(item["kind"])
	if kind == "enemy":
		var definition_value: Variant = data.get("enemies", {}).get(item.get("type", ""))
		if not (definition_value is Dictionary):
			errors.append("Unknown enemy definition in encounter projection.")
		else:
			var definition: Dictionary = definition_value
			var encounter: Dictionary = {}
			for stat: String in ["hp", "atk", "def", "gold"]:
				if not _whole(definition.get(stat)):
					errors.append("Malformed enemy stat in encounter projection.")
				else:
					encounter[stat] = int(definition[stat])
			if definition.has("appearance"):
				encounter["appearance"] = definition["appearance"]
			result["encounter"] = encounter
	elif kind == "shop":
		var definition_value: Variant = data.get("shops", {}).get(item.get("type", ""))
		if not (definition_value is Dictionary) or not (definition_value.get("offers") is Array):
			errors.append("Unknown shop definition in encounter projection.")
		else:
			var offers: Array = []
			for offer_value: Variant in definition_value["offers"]:
				if not (offer_value is Dictionary):
					errors.append("Malformed shop offer in encounter projection.")
					continue
				var offer: Dictionary = offer_value
				var terms: Dictionary = {"kind": offer.get("kind")}
				for field: String in ["cost", "amount", "limit"]:
					if not _whole(offer.get(field)):
						errors.append("Malformed shop offer terms in encounter projection.")
					else:
						terms[field] = int(offer[field])
				offers.append(terms)
			_sort_json(offers)
			result["offers"] = offers
	elif kind in ["key", "door"]:
		result["color"] = item.get("type")
	elif item.has("type"):
		errors.append("Opaque non-enemy/shop type needs an encounter adapter.")
	if kind == "stairs":
		result["direction"] = item["direction"]
		result["target"] = {"floor": item["target"]["floor"], "pos": item["target"]["pos"]}
	if item.has("hidden_until_flag"):
		result["hidden_until"] = _flag_projection(str(item["hidden_until_flag"]), data, index, errors)
	if include_events and item.has("event_ids"):
		var events: Array = []
		for event_id: Variant in item["event_ids"]:
			if not data.get("events", {}).has(event_id):
				errors.append("Unknown attached event in encounter projection.")
			else:
				events.append(_event_projection(data["events"][event_id], data, index, errors))
		result["events"] = events
	return result


static func _object_reference(object_id: Variant, data: Dictionary, index: Dictionary, errors: Array[String]) -> Dictionary:
	if not (object_id is String) or not index["objects"].has(object_id):
		errors.append("Unknown object reference in encounter projection.")
		return {}
	var record: Dictionary = index["objects"][object_id]
	# No recursive attached events/hidden flags: references denote the concrete
	# entity's current location and encounter terms, not an ID spelling.
	var item: Dictionary = record["object"].duplicate(true)
	item.erase("hidden_until_flag")
	return _object_projection(item, int(record["floor"]), data, index, errors, false)


static func _event_anchor(event: Dictionary, data: Dictionary, index: Dictionary, errors: Array[String]) -> Dictionary:
	var trigger: Dictionary = event["trigger"]
	var result: Dictionary = {"floor": int(event["floor"]), "kind": trigger["kind"]}
	if trigger["kind"] == "interact":
		result["object"] = _object_reference(trigger["object_id"], data, index, errors)
	else:
		var cells: Array = trigger["cells"].duplicate(true)
		_sort_json(cells)
		result["cells"] = cells
		if trigger.has("direction"):
			result["direction"] = trigger["direction"]
	return result


static func _flag_projection(flag: String, data: Dictionary, index: Dictionary, errors: Array[String]) -> Dictionary:
	if not data.get("flags", {}).has(flag) or not (data["flags"][flag] is bool):
		errors.append("Unknown flag in encounter projection.")
		return {}
	var setters: Array = []
	for event_id: Variant in data.get("events", {}):
		var event: Dictionary = data["events"][event_id]
		for effect: Dictionary in event.get("effects", []):
			if effect["kind"] == "set_flag" and effect["flag"] == flag:
				setters.append({"trigger": _event_anchor(event, data, index, errors), "value": effect["value"]})
	_sort_json(setters)
	return {"initial": data["flags"][flag], "setters": setters}


static func _event_projection(event: Dictionary, data: Dictionary, index: Dictionary, errors: Array[String]) -> Dictionary:
	var conditions: Array = []
	for condition: Dictionary in event.get("conditions", []):
		var requirement: Dictionary = {"kind": condition["kind"], "value": condition["value"]}
		if condition["kind"] == "flag":
			requirement["flag"] = _flag_projection(str(condition["flag"]), data, index, errors)
		else:
			requirement["object"] = _object_reference(condition["object_id"], data, index, errors)
		conditions.append(requirement)
	_sort_json(conditions)
	var effects: Array = []
	for effect: Dictionary in event.get("effects", []):
		var terms: Dictionary = {"kind": effect["kind"]}
		match str(effect["kind"]):
			"set_flag":
				terms["flag"] = _flag_projection(str(effect["flag"]), data, index, errors)
				terms["value"] = effect["value"]
			"clear_object":
				terms["object"] = _object_reference(effect["object_id"], data, index, errors)
			"grant":
				terms["stat"] = effect["stat"]
				terms["amount"] = int(effect["amount"])
			"grant_key":
				terms["color"] = effect["color"]
				terms["amount"] = int(effect["amount"])
		effects.append(terms)
	return {"trigger": _event_anchor(event, data, index, errors), "conditions": conditions, "effects": effects, "once": event.get("once", true)}


static func _event_semantics(event: Dictionary, data: Dictionary, objects: Dictionary) -> bool:
	for condition_value: Variant in event.get("conditions", []):
		if not (condition_value is Dictionary) or not (condition_value.get("value") is bool):
			return false
		var condition: Dictionary = condition_value
		match str(condition.get("kind", "")):
			"flag":
				if condition.size() != 3 or not (condition.get("flag") is String) or not data.get("flags", {}).has(condition["flag"]):
					return false
			"cleared":
				if condition.size() != 3 or not (condition.get("object_id") is String) or not objects.has(condition["object_id"]):
					return false
			_:
				return false
	for effect_value: Variant in event.get("effects", []):
		if not (effect_value is Dictionary):
			return false
		var effect: Dictionary = effect_value
		match str(effect.get("kind", "")):
			"set_flag":
				if effect.size() != 3 or not (effect.get("flag") is String) or not data.get("flags", {}).has(effect["flag"]) or not (effect.get("value") is bool):
					return false
			"grant":
				if effect.size() != 3 or not str(effect.get("stat", "")) in ["hp", "atk", "def", "gold"] or not _whole(effect.get("amount")) or int(effect["amount"]) < 1:
					return false
			"grant_key":
				if effect.size() != 3 or not (effect.get("color") is String) or not data.get("initial_player", {}).get("keys", {}).has(effect["color"]) or not _whole(effect.get("amount")) or int(effect["amount"]) < 1:
					return false
			"clear_object":
				if effect.size() != 2 or not (effect.get("object_id") is String) or not objects.has(effect["object_id"]):
					return false
			_:
				return false
	return true


static func _sort_json(values: Array) -> void:
	values.sort_custom(func(left: Variant, right: Variant) -> bool: return canonical_json(left) < canonical_json(right))
