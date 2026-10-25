extends SceneTree
## Geometry-only independent golden comparison. No active run, save or combat.
const Geometry = preload("res://fifty/scripts/d4.gd")
const GOLDEN_PATH: String = "res://fifty/tests/d4_golden.json"
const SELF_PATH: String = "res://fifty/tests/test_d4_geometry.gd"
const EXPECTED_GOLDEN_SHA256: String = "696fd8519a1c64b7c66e74ed99085e1199cc24719a60d406c81fc2cd55f015ec"
var output_path: String = ""
var stop_path: String = ""
var checks: Array = []
var errors: Array = []
var stopped: bool = false


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output_path = argument.trim_prefix("--output=")
		elif argument.begins_with("--stop-file="): stop_path = argument.trim_prefix("--stop-file=")
		else:
			push_error("Unknown geometry QA argument: " + argument)
			quit(2)
			return
	if output_path.is_empty() or FileAccess.file_exists(output_path):
		push_error("Pass --output=<absolute new JSON>; existing evidence is not overwritten.")
		quit(2)
		return
	var json: JSON = JSON.new()
	if FileAccess.get_sha256(GOLDEN_PATH) != EXPECTED_GOLDEN_SHA256 or json.parse(FileAccess.get_file_as_string(GOLDEN_PATH)) != OK or not (json.data is Dictionary):
		push_error("The independent Python golden bytes are unavailable or changed.")
		quit(2)
		return
	var golden: Dictionary = json.data
	var elements: Array = golden["elements"]
	var began: int = Time.get_ticks_msec()
	for code: int in range(8):
		if _stop(): break
		var item: Dictionary = golden["single_transform_cases"][code]
		var mismatch: Array = []
		if Geometry.CODE_NAMES[code] != elements[code] or item["transform"] != elements[code]: mismatch.append("D4 code/name order differs")
		var size: Array = item["source_dimensions"]
		if not _same(Geometry.transform_dimensions(int(size[0]), int(size[1]), code), item["expected_dimensions"]): mismatch.append("dimensions")
		for point: Dictionary in item["points"]:
			var actual: Array = Geometry.transform_cell(point["source"], int(size[0]), int(size[1]), code)
			if not _same(actual, point["expected"]): mismatch.append({"point": point, "actual": actual})
			var target_size: Array = item["expected_dimensions"]
			var inverse: int = elements.find(item["inverse"])
			if Geometry.inverse(code) != inverse or not _same(Geometry.transform_cell(actual, int(target_size[0]), int(target_size[1]), inverse), point["source"]): mismatch.append("inverse at " + str(point["source"]))
		for vector: Dictionary in item["vectors"]:
			if not _same(Geometry.transform_vector(vector["source"], code), vector["expected"]): mismatch.append({"vector": vector})
		for direction: Dictionary in item["directions"]:
			if Geometry.transform_direction(str(direction["source"]), code) != str(direction["expected"]): mismatch.append({"direction": direction})
		if not _same(Geometry.transform_grid(item["labelled_grid"]["source"], code), item["labelled_grid"]["expected"]): mismatch.append("labelled grid")
		_record("golden single transform " + str(elements[code]), mismatch.is_empty(), mismatch, {"points_checked": 15, "vectors_checked": 4, "directions_checked": 4})
	for pair: Dictionary in golden["crossfloor_pairs"]:
		if _stop(): break
		var source_code: int = elements.find(pair["source_transform"])
		var target_code: int = elements.find(pair["target_transform"])
		var original: Dictionary = _synthetic(pair)
		var original_hash: String = Geometry.content_hash(original)
		var transformed: Dictionary = Geometry.transform(original, {"1": source_code, "2": target_code})
		var mismatch: Array = []
		if not bool(transformed.get("ok", false)):
			mismatch.append(transformed)
		else:
			var result: Dictionary = transformed["data"]
			var up: Dictionary = result["floors"][0]["objects"][0]
			var down: Dictionary = result["floors"][1]["objects"][0]
			if not _same(up, _stair_projection(pair["forward"]["expected"])): mismatch.append({"forward": up, "expected": pair["forward"]["expected"]})
			if not _same(down, _stair_projection(pair["reverse"]["expected"])): mismatch.append({"reverse": down, "expected": pair["reverse"]["expected"]})
			for side: int in range(2):
				var name: String = "source_event" if side == 0 else "target_event"
				var event_object: Dictionary = result["floors"][side]["objects"][1]
				var expected: Dictionary = pair[name]["expected"]
				for field: String in ["pos", "facing", "direction_vector", "direction_condition"]:
					if not _same(event_object[field], expected[field]): mismatch.append(name + "/" + field)
				var trigger: Dictionary = result["events"][name]["trigger"]
				if not _same(trigger["cells"], [expected["pos"]]) or not _same(trigger["direction"], expected["direction_condition"]["vector"]): mismatch.append(name + "/enter trigger")
			if not _same(result["flags"], original["flags"]) or result["events"]["source_event"]["effects"] != original["events"]["source_event"]["effects"]: mismatch.append("Semantic flag/effect changed under a geometric transform")
		if Geometry.content_hash(original) != original_hash: mismatch.append("transform mutated input")
		_record("golden crossfloor " + str(pair["source_transform"]) + "/" + str(pair["target_transform"]), mismatch.is_empty(), mismatch)
	if not stopped:
		_record("compass API does not rotate semantic up/down", Geometry.transform_direction("up", 1).is_empty() and Geometry.transform_direction("down", 3).is_empty())
		_record("invalid point outside rectangle rejected", Geometry.transform_cell([-1, 0], 3, 5, 0).is_empty() and Geometry.transform_cell([3, 0], 3, 5, 0).is_empty())
		_record("invalid D4 code rejected", Geometry.transform_cell([0, 0], 3, 5, 8).is_empty() and Geometry.transform_dimensions(3, 5, -1).is_empty())
	var report: Dictionary = {"suite": "fifty_d4_independent_geometry_golden/v1", "passed": errors.is_empty() and not stopped,
		"measurement_completed": not stopped and checks.size() == 75, "stopped_at_case_boundary": stopped,
		"engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(),
		"golden_sha256": FileAccess.get_sha256(GOLDEN_PATH), "test_sha256": FileAccess.get_sha256(SELF_PATH),
		"geometry_sha256": FileAccess.get_sha256("res://fifty/scripts/d4.gd"), "checks": checks, "errors": errors,
		"elapsed_ms": Time.get_ticks_msec() - began,
		"scope": "8 known D4 projections with 120 points/32 vectors/32 compass directions/labelled grids/inverses, plus all 64 independent source/destination stair transforms and enter-event conditions through the new geometry module. This synthetic geometry test is not new content-schema validation, runtime movement/save QA, visual review or 50-floor completion."}
	var file: FileAccess = FileAccess.open(output_path, FileAccess.WRITE)
	if file == null:
		push_error("Cannot create the new geometry QA report.")
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "measurement_completed": report["measurement_completed"], "checks": checks.size(), "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if bool(report["passed"]) or (stopped and errors.is_empty()) else 1)


func _synthetic(pair: Dictionary) -> Dictionary:
	var floors: Array = []
	var events: Dictionary = {}
	for side: int in range(2):
		var size: Array = pair["source_dimensions"] if side == 0 else pair["target_dimensions"]
		var stair: Dictionary = _stair_projection(pair["forward"]["source"] if side == 0 else pair["reverse"]["source"])
		var event_name: String = "source_event" if side == 0 else "target_event"
		var event_object: Dictionary = pair[event_name]["source"].duplicate(true)
		event_object["id"] = event_name
		event_object["kind"] = "event"
		var rows: Array = []
		for row: int in range(int(size[1])): rows.append(".".repeat(int(size[0])))
		floors.append({"id": side + 1, "grid": rows, "width": int(size[0]), "height": int(size[1]), "spawn": stair["pos"].duplicate(), "objects": [stair, event_object]})
		events[event_name] = {"floor": side + 1, "trigger": {"kind": "enter", "cells": [event_object["pos"].duplicate()], "direction": event_object["direction_condition"]["vector"].duplicate()}, "conditions": [], "effects": [{"kind": "set_flag", "flag": "golden_seen", "value": true}]}
	return {"floors": floors, "events": events, "flags": {"golden_seen": false}}


func _stair_projection(value: Dictionary) -> Dictionary:
	return {"id": value["id"], "kind": "stairs", "pos": value["pos"].duplicate(), "direction": value["direction"], "target": value["target"].duplicate(true)}


func _same(a: Variant, b: Variant) -> bool:
	var canonical: String = Geometry.canonical_json(a)
	return not canonical.is_empty() and canonical == Geometry.canonical_json(b)


func _record(name: String, passed: bool, observed: Variant = null, details: Dictionary = {}) -> void:
	checks.append({"name": name, "passed": passed, "observed": observed if not passed else null, "details": details})
	if not passed: errors.append({"name": name, "observed": observed})


func _stop() -> bool:
	if not stop_path.is_empty() and FileAccess.file_exists(stop_path): stopped = true
	return stopped
