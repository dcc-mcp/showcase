extends SceneTree
## Prepared native GD unit probe. Scope: unit geometry, never pixels or gameplay.
## Run only after normal engine access is authorized. This file is not an overlay.
## Pass -- --output=<new-json-path> to retain the complete measured report.

const Policy = preload("res://fifty/view/screen_input.gd")
const TILESET_PATH: String = "res://vendor/godot-isometric/tileset/tileset.tres"
const IDS: Array[String] = ["NW", "NE", "SW", "SE"]
const DELTAS: Array[Vector2i] = [Vector2i.LEFT, Vector2i.UP, Vector2i.DOWN, Vector2i.RIGHT]
const ORIGINS: Array[Vector2i] = [Vector2i.ZERO, Vector2i(7, 7), Vector2i(-4, 3)]
const TRUTH: Array[Dictionary] = [
	{"id": "idle", "intent": Vector2.ZERO, "top": []},
	{"id": "up", "intent": Vector2.UP, "top": ["NW", "NE"]},
	{"id": "down", "intent": Vector2.DOWN, "top": ["SW", "SE"]},
	{"id": "left", "intent": Vector2.LEFT, "top": ["NW", "SW"]},
	{"id": "right", "intent": Vector2.RIGHT, "top": ["NE", "SE"]},
	{"id": "up_left", "intent": Vector2(-1, -1), "top": ["NW"]},
	{"id": "up_right", "intent": Vector2(1, -1), "top": ["NE"]},
	{"id": "down_left", "intent": Vector2(-1, 1), "top": ["SW"]},
	{"id": "down_right", "intent": Vector2(1, 1), "top": ["SE"]},
]

var _layer: TileMapLayer
var _checks: Array[Dictionary] = []
var _cases: Array[Dictionary] = []
var _projections: Array[Dictionary] = []
var _output: String = ""
var _started_msec: int = 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_started_msec = Time.get_ticks_msec()
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):
			_output = argument.substr(9)
		else:
			_check("supported_argument", false, argument)
	var original: TileSet = load(TILESET_PATH) as TileSet
	if original == null:
		_check("official_tileset_loaded", false, TILESET_PATH)
		_finish()
		return
	var original_size: Vector2i = original.tile_size
	var duplicate: TileSet = original.duplicate(true) as TileSet
	duplicate.tile_size = Vector2i(256, 128)
	_layer = TileMapLayer.new()
	_layer.name = "ActualTileMapGeometryProbe"
	_layer.tile_set = duplicate
	_layer.collision_enabled = false
	root.add_child(_layer)
	_check("duplicate_is_separate", duplicate != original, "The source TileSet is not modified.")
	_check("source_tile_size_unchanged", original.tile_size == original_size, str(original.tile_size))
	_check("actual_tile_size", duplicate.tile_size == Vector2i(256, 128), str(duplicate.tile_size))
	_check("actual_isometric_shape", duplicate.tile_shape == TileSet.TILE_SHAPE_ISOMETRIC, str(duplicate.tile_shape))
	for origin_index: int in range(ORIGINS.size()):
		var origin: Vector2i = ORIGINS[origin_index]
		_layer.position = Vector2(113 + origin.x * 2, 71 + origin.y * 3)
		_layer.scale = Vector2.ONE * (0.75 + float(origin_index) * 0.30)
		var sample: Array = _options(origin, 15)
		var vectors: Array = []
		for index: int in range(sample.size()):
			var vector: Vector2 = sample[index]["screen"]
			vectors.append({"id": IDS[index], "screen": [vector.x, vector.y]})
			var sign_ok: bool = (vector.x < 0 if IDS[index] in ["NW", "SW"] else vector.x > 0) and (vector.y < 0 if IDS[index] in ["NW", "NE"] else vector.y > 0)
			_check("projected_quadrant_%d_%s" % [origin_index, IDS[index]], sign_ok, str(vector))
		_projections.append({"origin": [origin.x, origin.y], "scale": _layer.scale.x, "vectors": vectors})
		for row: Dictionary in TRUTH:
			for mask: int in range(16):
				_run_case(origin, row, mask)
	_check("complete_golden_matrix", _cases.size() == 432, "9 intents x 16 wall masks x 3 origins")
	_layer.queue_free()
	_finish()


func _options(origin: Vector2i, mask: int) -> Array:
	var options: Array = []
	var start: Vector2 = _layer.to_global(_layer.map_to_local(origin))
	for index: int in range(DELTAS.size()):
		var delta: Vector2i = DELTAS[index]
		var cell: Vector2i = origin + delta
		var projected: Vector2 = _layer.to_global(_layer.map_to_local(cell))
		options.append({"cell": [cell.x, cell.y], "delta": [delta.x, delta.y], "screen": projected - start, "walkable": (mask & (1 << index)) != 0})
	return options


func _run_case(origin: Vector2i, row: Dictionary, mask: int) -> void:
	# Expected top sets above are handwritten, not calculated by Policy's scoring.
	var expected_ids: Array[String] = []
	for id: String in row["top"]:
		var bit: int = IDS.find(id)
		if (mask & (1 << bit)) != 0:
			expected_ids.append(id)
	var expected_status: String = "idle" if row["id"] == "idle" else ("blocked" if expected_ids.is_empty() else ("step" if expected_ids.size() == 1 else "choose"))
	var result: Dictionary = Policy.resolve(row["intent"], _options(origin, mask))
	var actual_status: String = str(result.get("status", "missing"))
	var actual_ids: Array[String] = []
	var errors: Array[String] = []
	if actual_status != expected_status:
		errors.append("status differs")
	if actual_status == "step":
		_actual_choice(result, origin, mask, actual_ids, errors)
	elif actual_status == "choose":
		var choices: Variant = result.get("options")
		if not (choices is Array) or choices.size() != 2:
			errors.append("choose must return exactly two options")
		else:
			for option: Variant in choices:
				if option is Dictionary:
					_actual_choice(option, origin, mask, actual_ids, errors)
				else:
					errors.append("choice is not an option dictionary")
		var cells: Variant = result.get("cells")
		if not (cells is Array) or cells.size() != 2:
			errors.append("choose must return exactly two cells")
		elif choices is Array and choices.size() == 2 and choices[0] is Dictionary and choices[1] is Dictionary:
			if cells[0] != choices[0].get("cell") or cells[1] != choices[1].get("cell"):
				errors.append("choice cells disagree with options")
	elif actual_status in ["idle", "blocked"]:
		var cells: Variant = result.get("cells")
		var options: Variant = result.get("options")
		if result.has("cell") or result.has("delta") or not (cells is Array) or not (options is Array):
			errors.append("idle/blocked must not select a cell")
		elif not cells.is_empty() or not options.is_empty():
			errors.append("idle/blocked must return empty cell/option arrays")
	else:
		errors.append("unsupported status")
	expected_ids.sort()
	actual_ids.sort()
	if actual_ids != expected_ids:
		errors.append("selected direction set differs; blocked best must not fall back")
	_cases.append({"origin": [origin.x, origin.y], "intent": row["id"], "mask": mask, "expected_status": expected_status, "actual_status": actual_status, "expected_ids": expected_ids, "actual_ids": actual_ids, "pass": errors.is_empty(), "errors": errors})


func _actual_choice(choice: Dictionary, origin: Vector2i, mask: int, ids: Array[String], errors: Array[String]) -> void:
	var raw_cell: Variant = choice.get("cell")
	var raw_delta: Variant = choice.get("delta")
	if not (raw_cell is Array) or raw_cell.size() != 2 or not (raw_delta is Array) or raw_delta.size() != 2:
		errors.append("selected cell/delta shape differs")
		return
	# Validate original values before int/Vector2i conversion can truncate or wrap.
	for part: Variant in raw_cell + raw_delta:
		if not (part is int or part is float) or not is_finite(float(part)) or float(part) != floorf(float(part)):
			errors.append("selected coordinates must be finite whole numbers")
			return
	var dx: float = float(raw_delta[0])
	var dy: float = float(raw_delta[1])
	if absf(dx) + absf(dy) != 1.0 or float(raw_cell[0]) != float(origin.x) + dx or float(raw_cell[1]) != float(origin.y) + dy:
		errors.append("raw selection must be exactly one cardinal neighbor")
		return
	var cell: Vector2i = Vector2i(int(raw_cell[0]), int(raw_cell[1]))
	var delta: Vector2i = Vector2i(int(raw_delta[0]), int(raw_delta[1]))
	var index: int = DELTAS.find(delta)
	if absi(delta.x) + absi(delta.y) != 1 or cell != origin + delta or index < 0:
		errors.append("selection must be exactly one cardinal neighbor")
		return
	if (mask & (1 << index)) == 0:
		errors.append("selected cell is blocked")
	if ids.has(IDS[index]):
		errors.append("duplicate selected direction")
	ids.append(IDS[index])


func _check(name: String, passed: bool, detail: String) -> void:
	_checks.append({"name": name, "pass": passed, "detail": detail})


func _finish() -> void:
	var failed: int = 0
	for check: Dictionary in _checks:
		if not bool(check["pass"]): failed += 1
	for record: Dictionary in _cases:
		if not bool(record["pass"]): failed += 1
	var report: Dictionary = {"schema_version": 1, "suite": "screen-input-native-unit-probe", "scope": "unit-geometry-not-pixels", "pass": failed == 0, "checks": _checks, "cases": _cases, "case_count": _cases.size(), "failed": failed, "elapsed_msec": Time.get_ticks_msec() - _started_msec, "projection_samples": _projections, "source_sha256": FileAccess.get_sha256("res://fifty/view/screen_input.gd"), "tileset_sha256": FileAccess.get_sha256(TILESET_PATH), "not_claimed": ["pixels", "real keyboard/pointer events", "70ms timing", "path cancellation", "gameplay", "Web/WASM execution"]}
	var output_status: String = "stdout_summary_only"
	if not _output.is_empty():
		if FileAccess.file_exists(_output):
			output_status = "refused_existing_output"
			failed += 1
		else:
			var file: FileAccess = FileAccess.open(_output, FileAccess.WRITE)
			if file == null:
				output_status = "output_write_failed"
				failed += 1
			else:
				file.store_string(JSON.stringify(report, "  ", true, true) + "\n")
				file.flush()
				if file.get_error() != OK:
					output_status = "output_write_failed"
					failed += 1
				else:
					output_status = "json_written"
				file.close()
	print(JSON.stringify({"suite": report["suite"], "scope": report["scope"], "pass": failed == 0, "case_count": _cases.size(), "failed": failed, "elapsed_msec": report["elapsed_msec"], "output": _output, "output_status": output_status}))
	quit(0 if failed == 0 else 1)
