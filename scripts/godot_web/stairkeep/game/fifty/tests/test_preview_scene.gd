extends SceneTree
## Instrumented scene/state checks only. No keyboard, pointer, pixels or browser.
const Preview = preload("res://fifty/view/preview.tscn")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Saves = preload("res://fifty/scripts/save.gd")
const Runtime = preload("res://fifty/scripts/runtime.gd")
var output_path: String = ""
var death_report_path: String = ""
var complete_report_path: String = ""
var checks: Array = []
var errors: Array = []


func _initialize() -> void:
	call_deferred("_run")


func _record(label: String, passed: bool, observed: Variant = {}) -> void:
	var row: Dictionary = {"name": label, "passed": passed, "observed": observed}
	checks.append(row)
	if not passed: errors.append(row)


func _rectangles(view: Node) -> Dictionary:
	var result: Dictionary = {}
	for key: String in ["ui", "world_host", "tabs", "overlay"]:
		var control: Control = view.get(key) as Control
		if control == null:
			result[key] = {"missing": true}
			continue
		var rect: Rect2 = control.get_global_rect()
		var minimum: Vector2 = control.get_combined_minimum_size()
		result[key] = {"rect": [rect.position.x, rect.position.y, rect.size.x, rect.size.y],
			"combined_minimum": [minimum.x, minimum.y], "visible_in_tree": control.is_visible_in_tree()}
	return result


func _settle(view: Node) -> Dictionary:
	var previous: String = ""
	var stable: int = 0
	var last: Dictionary = {}
	for frame: int in range(24):
		await process_frame
		last = _rectangles(view)
		# UI rectangles may contain fractional canvas coordinates. The integer-only
		# gameplay serializer is deliberately unsuitable for this measurement.
		var serialized: String = JSON.stringify(last, "", true, true)
		stable = stable + 1 if serialized == previous else 0
		previous = serialized
		if frame >= 3 and stable >= 3:
			return {"settled": true, "frames": frame + 1, "sample": last}
	return {"settled": false, "frames": 24, "sample": last}


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output_path = argument.trim_prefix("--output=")
		elif argument.begins_with("--death-report="): death_report_path = argument.trim_prefix("--death-report=")
		elif argument.begins_with("--complete-report="): complete_report_path = argument.trim_prefix("--complete-report=")
		elif argument.begins_with("--stop-file="): pass
		else:
			push_error("Unknown preview QA argument: " + argument)
			quit(2)
			return
	if output_path.is_empty() or FileAccess.file_exists(output_path):
		push_error("Pass a new --output=<path>; existing evidence is retained.")
		quit(2)
		return
	var began: int = Time.get_ticks_msec()
	root.size = Vector2i(1280, 800)
	var view: Node = Preview.instantiate()
	root.add_child(view)
	var initial_layout: Dictionary = await _settle(view)
	var initial: Dictionary = view.call("view_status")
	_record("scene imports and initial containers settle", bool(initial_layout["settled"]), initial_layout)
	_record("mode has no default and first chapter is honestly scoped",
		bool(initial.get("content_ready", false)) and not bool(initial.get("started", true)) and initial.get("selected_mode", "x") == "" and bool(initial.get("start_disabled", false)) and int(initial.get("authored_floors", 0)) == 10 and int(initial.get("target_floors", 0)) == 50, initial)
	var load_button: Button = view.get("mode_load_button") as Button
	_record("unselected mode cannot load", load_button != null and load_button.disabled, {"disabled": load_button.disabled if load_button != null else false})
	var rules: Object = view.get("rules")
	var unselected_before: String = Geometry.content_hash(rules.call("export_snapshot"))
	view.call("_select_mode", "classic_restart")
	var selected: Dictionary = view.call("view_status")
	_record("choosing a mode does not silently start or reset",
		not bool(selected["start_disabled"]) and not bool(selected["started"]) and unselected_before == Geometry.content_hash(rules.call("export_snapshot")), selected)
	var seed_input: LineEdit = view.get("seed_input") as LineEdit
	seed_input.text = "1"
	view.call("_begin")
	var active_layout: Dictionary = await _settle(view)
	rules = view.get("rules")
	var active: Dictionary = view.call("view_status")
	_record("explicit classic begins an actual runtime", bool(active["started"]) and active["active_mode"] == "classic_restart" and bool(rules.call("is_active")), active)
	_record("active containers settle at base logical size", bool(active_layout["settled"]), active_layout)
	var world: Node = view.get("world")
	var tile_map: TileMapLayer = world.get("_floor") as TileMapLayer
	var tile_set: TileSet = tile_map.tile_set if tile_map != null else null
	var floor_texture: Texture2D = load("res://assets/kenney/stone_N.png") as Texture2D
	var upstream_tiles: TileSet = load("res://vendor/godot-isometric/tileset/tileset.tres") as TileSet
	var frames: SpriteFrames = world.get("_frames") as SpriteFrames
	_record("licensed native world creates actual floor tiles and resources", tile_map != null and tile_set != null and tile_set.get_source_count() == 3 and tile_map.get_used_cells().size() > 0 and upstream_tiles != null and floor_texture != null and floor_texture.get_width() == 256 and frames != null and frames.get_animation_names().size() > 0,
		{"used_cells": tile_map.get_used_cells().size() if tile_map != null else 0, "tile_set_loaded": tile_set != null,
		"texture_loaded": floor_texture != null, "upstream_loaded": upstream_tiles != null, "frames_loaded": frames != null,
		"world_script": world.get_script().resource_path})
	var bestiary: ItemList = view.get("bestiary_list") as ItemList
	_record("bestiary is populated from authored enemies", bestiary != null and bestiary.item_count >= 10, {"entries": bestiary.item_count if bestiary != null else 0})
	var inspect_before: String = Geometry.content_hash(rules.call("export_snapshot"))
	var displayed_resources: Dictionary = {}
	var resources_correct: bool = true
	for item: Dictionary in rules.get("data")["floors"][0]["objects"]:
		var item_kind: String = str(item.get("kind", ""))
		if item_kind not in ["atk", "def", "potion", "gold", "key"] or displayed_resources.has(item_kind): continue
		view.call("_inspect", item["pos"])
		var cost: String = (view.get("inspect_cost") as Label).text
		var expected_resource: String = "HP" if item_kind == "potion" else item_kind.to_upper()
		if item_kind == "key": expected_resource = str(item["type"]).to_upper() + " KEY"
		var expected_cost: String = "GAIN +%d %s" % [int(item["amount"]), expected_resource]
		displayed_resources[item_kind] = {"object_id": item["id"], "amount": item["amount"], "actual": cost, "expected": expected_cost}
		resources_correct = resources_correct and cost == expected_cost
	_record("actual first-floor inspection displays five typed resource amounts", resources_correct and displayed_resources.size() == 5, displayed_resources)
	var authored: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://fifty/data/content.json"))
	var archive_copy: String = view.call("_event_effects_text", authored["events"]["ev_archive"]["effects"])
	var exchange_copy: String = view.call("_event_effects_text", authored["events"]["ev_mapper_exchange"]["effects"])
	_record("event presentation helper displays production typed grants", archive_copy.contains("+3 ATK") and archive_copy.contains("+2 DEF") and archive_copy.contains("+45 HP") and exchange_copy.contains("+1 BLUE KEY"), {"archive": archive_copy, "exchange": exchange_copy, "scope": "Direct presentation helper with production effect data; not an additional completed event route."})
	_record("resource and typed-event inspection leave authoritative state unchanged", Geometry.content_hash(rules.call("export_snapshot")) == inspect_before)
	var other = Runtime.new()
	var other_loaded: Dictionary = other.load_content()
	var other_started: Dictionary = other.choose_mode("classic_restart", 2)
	var other_saved: Dictionary = Saves.write_slot(other, "first-chapter")
	_record("alternate seed save fixture is produced by actual runtime", bool(other_loaded.get("ok", false)) and bool(other_started.get("ok", false)) and bool(other_saved.get("ok", false)), other_saved)
	view.call("_do_load_slot", "classic_restart")
	await _settle(view)
	rules = view.get("rules")
	var loaded_snapshot: Dictionary = rules.call("export_snapshot")
	_record("successful load synchronizes the validated hexadecimal seed", loaded_snapshot.get("seed", "") == "00000002" and int(view.get("selected_seed")) == 2, {"snapshot_seed": loaded_snapshot.get("seed"), "selected_seed": view.get("selected_seed")})
	view.call("_show_recovery")
	await process_frame
	var restart_seed_valid: bool = false
	var overlay_box: VBoxContainer = view.get("overlay_box") as VBoxContainer
	for child: Node in overlay_box.get_children():
		if child is LineEdit and not child.is_queued_for_deletion():
			restart_seed_valid = (child as LineEdit).text == "3"
	_record("default restart seed differs from the loaded seed", restart_seed_valid, {})
	view.call("_close_modal")
	view.call("_show_modes")
	view.call("_select_mode", "classic_restart")
	await process_frame
	var before_begin: String = Geometry.content_hash(rules.call("export_snapshot"))
	view.call("_begin")
	_record("same-mode Begin cannot bypass recovery", before_begin == Geometry.content_hash(rules.call("export_snapshot")))
	view.call("_close_modal")
	view.call("_save_slot")
	var slot: String = Saves.slot_path("first-chapter", "classic_restart")
	_record("view saves through its independent native slot", FileAccess.file_exists(slot), {"slot": slot})
	var slot_before: String = FileAccess.get_sha256(slot)
	var failure: Dictionary = rules.call("give_up", true)
	view.call("_apply", failure)
	await process_frame
	var ended_stats: Dictionary = view.get("stats")
	var ended_hp: String = (ended_stats["hp"] as Label).text
	_record("voluntary end preserves actual HP and identifies the ended run", ended_hp == "HP %d / RUN ENDED" % int(rules.get("state").get("hp", 0)), {"hud": ended_hp})
	var failed_snapshot: String = Geometry.content_hash(rules.call("export_snapshot"))
	var instance: int = rules.get_instance_id()
	view.call("_load_slot")
	_record("failed Classic header load cannot restore the earlier save", Geometry.content_hash(rules.call("export_snapshot")) == failed_snapshot and (view.get("rules") as Object).get_instance_id() == instance and slot_before == FileAccess.get_sha256(slot), view.call("view_status"))
	view.call("_show_modes")
	view.call("_select_mode", "classic_restart")
	await process_frame
	load_button = view.get("mode_load_button") as Button
	_record("failed Classic same-mode load button stays disabled", load_button.disabled, {"disabled": load_button.disabled})
	view.call("_do_load_slot", "classic_restart")
	_record("failed Classic candidate-load path also refuses", Geometry.content_hash(rules.call("export_snapshot")) == failed_snapshot and (view.get("rules") as Object).get_instance_id() == instance and slot_before == FileAccess.get_sha256(slot), {})
	view.call("_select_mode", "practice_checkpoint")
	view.call("_begin")
	await process_frame
	_record("changing mode while failed opens an explicit confirmation", view.call("view_status")["modal"] == "confirm" and Geometry.content_hash(rules.call("export_snapshot")) == failed_snapshot, view.call("view_status"))
	view.call("_cancel_confirmation")
	await process_frame
	_record("canceling a mode replacement returns the failed run to recovery", view.call("view_status")["modal"] == "recovery" and not world.is_processing_unhandled_input() and Geometry.content_hash(rules.call("export_snapshot")) == failed_snapshot, view.call("view_status"))
	var identity: Dictionary = rules.call("runtime_identity")
	view.queue_free()
	for frame: int in range(4): await process_frame
	var death_hud_tested: bool = false
	if not death_report_path.is_empty():
		var fixture: Variant = JSON.parse_string(FileAccess.get_file_as_string(death_report_path))
		var snapshot: Dictionary = {}
		if fixture is Dictionary and bool(fixture.get("passed", false)):
			for candidate: Dictionary in fixture.get("cases", []):
				if candidate.get("mode", "") == "classic_restart": snapshot = candidate.get("failed_full_snapshot", {}).duplicate(true)
		var dead = Runtime.new()
		var dead_loaded: Dictionary = dead.load_content()
		var dead_started: Dictionary = dead.choose_mode("classic_restart", 1)
		var imported: Dictionary = dead.import_snapshot(snapshot)
		var saved: Dictionary = Saves.write_slot(dead, "first-chapter") if bool(imported.get("ok", false)) else {}
		_record("death HUD fixture is an authoritatively replayed real failed encounter", bool(dead_loaded.get("ok", false)) and bool(dead_started.get("ok", false)) and bool(imported.get("ok", false)) and bool(saved.get("ok", false)), {"import": imported.get("reason", imported.get("result", "")), "save_ok": saved.get("ok", false)})
		var dead_view: Node = Preview.instantiate()
		root.add_child(dead_view)
		await _settle(dead_view)
		dead_view.call("_select_mode", "classic_restart")
		(dead_view.get("seed_input") as LineEdit).text = "1"
		dead_view.call("_begin")
		await _settle(dead_view)
		dead_view.call("_do_load_slot", "classic_restart")
		await _settle(dead_view)
		var dead_rules: Object = dead_view.get("rules")
		var dead_stats: Dictionary = dead_view.get("stats")
		var dead_hp: String = (dead_stats["hp"] as Label).text
		var dead_snapshot: Dictionary = dead_rules.call("export_snapshot")
		var failure_copy: Dictionary = dead_view.call("_failure_presentation", dead_snapshot)
		death_hud_tested = dead_hp == "HP 0 / DEFEATED" and int(dead_rules.get("state").get("hp", 0)) == 111 and Geometry.content_hash(dead_snapshot) == Geometry.content_hash(snapshot) and str(failure_copy.get("copy", "")).contains("160") and str(failure_copy.get("copy", "")).contains("-49")
		_record("finite combat death HUD reads recorded outcome without changing authoritative state", death_hud_tested, {"hud": dead_hp, "legal_core_hp": dead_rules.get("state").get("hp"), "recovery_copy": failure_copy})
		dead_view.queue_free()
		for frame: int in range(4): await process_frame
	if not complete_report_path.is_empty():
		var complete_fixture: Variant = JSON.parse_string(FileAccess.get_file_as_string(complete_report_path))
		var complete_snapshot: Dictionary = {}
		if complete_fixture is Dictionary and bool(complete_fixture.get("passed", false)):
			for candidate: Dictionary in complete_fixture.get("cases", []):
				if candidate.get("mode", "") == "classic_restart" and candidate.get("seed", "") == "00000001":
					complete_snapshot = candidate.get("full_final_snapshot", {}).duplicate(true)
					break
		var completed = Runtime.new()
		completed.load_content()
		completed.choose_mode("classic_restart", 1)
		var completion_import: Dictionary = completed.import_snapshot(complete_snapshot)
		var completion_end: Dictionary = completed.give_up(true)
		var completion_failed: Dictionary = completed.export_snapshot()
		var completion_save: Dictionary = Saves.write_slot(completed, "first-chapter")
		_record("completed then ended fixture uses actual winning route and legal APIs", bool(completion_import.get("ok", false)) and bool(completion_end.get("ok", false)) and bool(completion_save.get("ok", false)) and bool(completion_failed.get("slice_complete", false)) and bool(completion_failed.get("failed", false)), {})
		var completed_view: Node = Preview.instantiate()
		root.add_child(completed_view)
		await _settle(completed_view)
		completed_view.call("_select_mode", "classic_restart")
		(completed_view.get("seed_input") as LineEdit).text = "1"
		completed_view.call("_begin")
		await _settle(completed_view)
		completed_view.call("_do_load_slot", "classic_restart")
		await _settle(completed_view)
		var completion_status: Dictionary = completed_view.call("view_status")
		var completed_world: Node = completed_view.get("world")
		_record("failed completed chapter opens recovery instead of the active completion modal", completion_status.get("modal", "") == "recovery" and not completed_world.is_processing_unhandled_input() and Geometry.content_hash((completed_view.get("rules") as Object).call("export_snapshot")) == Geometry.content_hash(completion_failed), completion_status)
		completed_view.queue_free()
		for frame: int in range(4): await process_frame
	var report: Dictionary = {"suite": "fifty-preview-instrumented-scene/v1", "passed": errors.is_empty(), "measurement_completed": true,
		"engine": Engine.get_version_info(), "display_server": DisplayServer.get_name(), "logical_viewport": [1280, 800],
		"runtime_identity": identity, "checks": checks, "errors": errors, "elapsed_ms": Time.get_ticks_msec() - began,
		"death_hud_tested": death_hud_tested,
		"scope": "Actual headless scene instantiation, later-frame Control rectangles and direct production-method instrumentation. No input injection or OS window.",
		"real_keyboard_mouse_touch_tested": false, "pixels_reviewed": false, "browser_tested": false, "physical_device_tested": false}
	var file: FileAccess = FileAccess.open(output_path, FileAccess.WRITE)
	if file == null:
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "checks": checks.size(), "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if errors.is_empty() else 1)
