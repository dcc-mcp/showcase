extends SceneTree
## Coordinator-run headless instrumentation. No player input or rendered review.
## Use a fresh isolated user-data directory: the production chapter2-preview
## slot must be absent before this helper writes its two review fixtures.

const LegacyScene = preload("res://fifty/view/preview.tscn")
const ChapterScene = preload("res://fifty/view/chapter2.tscn")
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Saves = preload("res://fifty/scripts/save.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const PRACTICE: String = "practice_checkpoint"
const CHAPTER_CONTENT: String = "res://fifty/data/chapter2-content.json"
const CHAPTER_ID: String = "stairkeep-fifty-chapter2/v1"
const KENNEY_PNGS: Array[String] = ["stone_N.png", "stoneUneven_N.png", "stoneTile_N.png", "stoneColumn_N.png", "stoneWallDoorClosed_N.png", "stairs_N.png", "tableRoundItemsChairs_N.png", "wanderer.png", "woodenCrates_N.png", "barrel_N.png"]

var output_path: String = ""
var route_report_path: String = ""
var route_report_sha256: String = ""
var checks: Array = []
var errors: Array = []
var argument_errors: Array[String] = []
var source_hashes: Dictionary = {}
var fixture_binding: Dictionary = {}
var began: int = 0
var measurement_completed: bool = false


func _initialize() -> void:
	call_deferred("_run")


func _record(name: String, passed: bool, observed: Variant = {}) -> void:
	var row: Dictionary = {"name":name,"passed":passed,"observed":observed}
	checks.append(row)
	if not passed:
		errors.append(row)


func _parse_arguments() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var seen: Dictionary = {}
	var index: int = 0
	while index < args.size():
		var argument: String = args[index]
		var key: String = argument.get_slice("=",0)
		if key not in ["--output","--route-report","--route-report-sha256"]:
			argument_errors.append("Unknown argument; only output and bound route-report options are supported.")
			index += 1
			continue
		if seen.has(key):
			argument_errors.append("Duplicate argument: " + key)
		seen[key] = true
		var value: String = ""
		if argument.contains("="):
			value = argument.substr(key.length()+1)
		elif index+1 < args.size():
			index += 1
			value = args[index]
		else:
			argument_errors.append("Missing value: " + key)
		match key:
			"--output": output_path = value
			"--route-report": route_report_path = value
			"--route-report-sha256": route_report_sha256 = value.to_lower()
		index += 1


func _valid_sha256(value: String) -> bool:
	if value.length() != 64:
		return false
	for index: int in range(value.length()):
		if not "0123456789abcdef".contains(value.substr(index,1)):
			return false
	return true


func _verdict(result: Dictionary) -> Dictionary:
	return {"ok":bool(result.get("ok",false)),"status":str(result.get("status",result.get("action",""))),"message":str(result.get("message",""))}


func _rectangles(view: Node) -> Dictionary:
	var sample: Dictionary = {}
	for name: String in ["ui","world_host","tabs","overlay","floor_label","availability_label"]:
		var control: Control = view.get(name) as Control
		if control == null:
			sample[name] = {"missing":true}
			continue
		var rect: Rect2 = control.get_global_rect()
		var minimum: Vector2 = control.get_combined_minimum_size()
		sample[name] = {"rect":[rect.position.x,rect.position.y,rect.size.x,rect.size.y],"minimum":[minimum.x,minimum.y],"visible":control.is_visible_in_tree()}
	return sample


func _settle(view: Node) -> Dictionary:
	var previous: String = ""
	var stable: int = 0
	var last: Dictionary = {}
	for frame: int in range(30):
		await process_frame
		last = _rectangles(view)
		var serialized: String = JSON.stringify(last,"",true,true)
		stable = stable+1 if serialized == previous else 0
		previous = serialized
		if frame >= 3 and stable >= 3:
			return {"settled":true,"frames":frame+1,"sample":last}
	return {"settled":false,"frames":30,"sample":last}


func _layout_fits(layout: Dictionary) -> bool:
	if not bool(layout.get("settled",false)):
		return false
	var viewport: Rect2 = Rect2(Vector2.ZERO,Vector2(1280,800)).grow(0.5)
	for name: String in layout.get("sample",{}):
		var item: Dictionary = layout["sample"][name]
		if bool(item.get("missing",false)):
			return false
		if not bool(item.get("visible",false)):
			continue
		var raw: Array = item.get("rect",[])
		if raw.size() != 4:
			return false
		var rect: Rect2 = Rect2(float(raw[0]),float(raw[1]),float(raw[2]),float(raw[3]))
		if rect.size.x <= 0 or rect.size.y <= 0 or not viewport.encloses(rect):
			return false
	return true


func _resources(view: Node) -> Dictionary:
	var world: Node = view.get("world") as Node
	if world == null:
		return {"passed":false,"missing":"world"}
	var floor: TileMapLayer = world.get("_floor") as TileMapLayer
	var tiles: TileSet = floor.tile_set if floor != null else null
	var upstream: TileSet = load("res://vendor/godot-isometric/tileset/tileset.tres") as TileSet
	var png_rows: Array = []
	var png_ok: bool = true
	for name: String in KENNEY_PNGS:
		var path: String = "res://assets/kenney/" + name
		var texture: Texture2D = load(path) as Texture2D
		var image := Image.new()
		var decoded: Error = image.load(path)
		var valid: bool = texture != null and texture.get_width() == 256 and texture.get_height() == 512 and decoded == OK and not image.is_empty() and image.get_width() == 256 and image.get_height() == 512
		png_ok = png_ok and valid
		png_rows.append({"name":name,"passed":valid,"texture_loaded":texture != null,"png_decode_error":decoded,"sha256":FileAccess.get_sha256(path)})
	var atlas_ok: bool = tiles != null and tiles.get_source_count() == 3
	var atlas_rows: Array = []
	if tiles != null:
		for index: int in range(tiles.get_source_count()):
			var source_id: int = tiles.get_source_id(index)
			var atlas: TileSetAtlasSource = tiles.get_source(source_id) as TileSetAtlasSource
			var valid: bool = atlas != null and atlas.texture != null and atlas.texture.get_width() == 256 and atlas.texture.get_height() == 512
			atlas_ok = atlas_ok and valid
			atlas_rows.append({"source_id":source_id,"passed":valid})
	var projection_ok: bool = false
	var used: int = floor.get_used_cells().size() if floor != null else 0
	if floor != null and tiles != null and upstream != null and used > 0:
		var cell: Vector2i = floor.get_used_cells()[0]
		projection_ok = tiles.tile_shape == TileSet.TILE_SHAPE_ISOMETRIC and tiles.tile_layout == upstream.tile_layout and tiles.tile_size == Vector2i(256,128) and floor.local_to_map(floor.map_to_local(cell)) == cell
	var frames: SpriteFrames = world.get("_frames") as SpriteFrames
	var frame_count: int = 0
	var frames_ok: bool = frames != null and frames.has_animation(&"front_idle")
	if frames != null:
		for animation: String in frames.get_animation_names():
			for index: int in range(frames.get_frame_count(animation)):
				var texture: Texture2D = frames.get_frame_texture(animation,index)
				frames_ok = frames_ok and texture != null and texture.get_width() > 0 and texture.get_height() > 0
				frame_count += 1
	var goblin := Image.new()
	var goblin_error: Error = goblin.load("res://vendor/godot-isometric/player/goblin.png")
	frames_ok = frames_ok and frame_count > 0 and goblin_error == OK and not goblin.is_empty()
	return {"passed":png_ok and atlas_ok and projection_ok and frames_ok,"upstream_tileset_loaded":upstream != null,"tileset_loaded":tiles != null,"used_cells":used,"projection_roundtrip":projection_ok,"atlas_sources":atlas_rows,"kenney_pngs":png_rows,"all_frames_loaded":frames_ok,"animation_frame_count":frame_count,"goblin_png_decode_error":goblin_error}


func _release(view: Node) -> void:
	view.queue_free()
	for frame: int in range(4):
		await process_frame


func _check_initial(view: Node, profile: String, count: int, slot: String, content: String, label: String) -> void:
	var layout: Dictionary = await _settle(view)
	_record(profile + " title containers settle inside the logical viewport",_layout_fits(layout),layout)
	var status: Dictionary = view.call("view_status")
	var expected_start: int = count+1
	var unmade_range: Array = status.get("unmade_floors",[])
	var metadata_ok: bool = bool(status.get("content_ready",false)) and int(status.get("authored_floors",0)) == count and int(status.get("target_floors",0)) == 50 and unmade_range.size() == 2 and int(unmade_range[0]) == expected_start and int(unmade_range[1]) == 50
	_record(profile + " has the selected profile and honest authored range",metadata_ok and status.get("slot_id","") == slot and status.get("content_path","") == content and status.get("profile_label","") == label,status)
	var load_button: Button = view.get("mode_load_button") as Button
	_record(profile + " starts without a default mode or enabled load",not bool(status.get("started",true)) and status.get("selected_mode","x") == "" and status.get("active_mode","x") == "" and bool(status.get("start_disabled",false)) and load_button != null and load_button.disabled,status)
	var rules: Object = view.get("rules")
	var before: String = Geometry.content_hash(rules.call("export_snapshot"))
	view.call("_select_mode",PRACTICE)
	var selected: Dictionary = view.call("view_status")
	_record(profile + " choosing Practice does not start or change game state",not bool(selected.get("started",true)) and not bool(selected.get("start_disabled",true)) and Geometry.content_hash(rules.call("export_snapshot")) == before,selected)


func _start_practice(view: Node, label: String) -> bool:
	var seed_input: LineEdit = view.get("seed_input") as LineEdit
	if seed_input == null:
		_record(label + " has a seed input",false)
		return false
	seed_input.text = "1"
	view.call("_begin")
	var layout: Dictionary = await _settle(view)
	var rules: Object = view.get("rules")
	var snapshot: Dictionary = rules.call("export_snapshot")
	var status: Dictionary = view.call("view_status")
	var ok: bool = bool(status.get("started",false)) and status.get("active_mode","") == PRACTICE and snapshot.get("seed","") == "00000001" and int(snapshot.get("core_state",{}).get("floor",-1)) == 0
	_record(label + " explicitly begins Practice seed 1 through production view methods",ok,status)
	_record(label + " active containers settle inside the viewport",_layout_fits(layout),layout)
	var resources: Dictionary = _resources(view)
	_record(label + " loads actual MIT TileSet, ten CC0 PNGs and animation frames",bool(resources.get("passed",false)),resources)
	return ok


func _fresh_chapter_load(label: String) -> Node:
	var view: Node = ChapterScene.instantiate()
	root.add_child(view)
	await _settle(view)
	var initial: Dictionary = view.call("view_status")
	_record(label + " fresh view still requires an explicit mode",not bool(initial.get("started",true)) and initial.get("selected_mode","x") == "" and bool(initial.get("start_disabled",false)),initial)
	view.call("_select_mode",PRACTICE)
	view.call("_do_load_slot",PRACTICE)
	var layout: Dictionary = await _settle(view)
	_record(label + " loaded containers settle inside the viewport",_layout_fits(layout),layout)
	var resources: Dictionary = _resources(view)
	_record(label + " loaded world has real textures, frames and projection",bool(resources.get("passed",false)),resources)
	return view


func _modal_text(view: Node) -> String:
	var box: VBoxContainer = view.get("overlay_box") as VBoxContainer
	var lines := PackedStringArray()
	if box != null:
		for child: Node in box.get_children():
			if child is Label:
				lines.append((child as Label).text)
	return "\n".join(lines)


func _bind_sources(report: Dictionary) -> bool:
	var expected: Dictionary = report.get("source_hashes",{})
	var observed: Dictionary = {}
	var ok: bool = not expected.is_empty()
	for path: String in expected:
		var digest: String = FileAccess.get_sha256(path) if path.begins_with("res://") else ""
		var matches: bool = _valid_sha256(digest) and digest == str(expected[path])
		ok = ok and matches
		observed[path] = {"expected":expected[path],"actual":digest,"match":matches}
		source_hashes[path] = digest
	for path: String in ["res://fifty/view/preview.gd","res://fifty/view/world.gd","res://fifty/view/preview.tscn","res://fifty/view/chapter2.tscn","res://fifty/tests/chapter2_preview_scene.gd","res://fifty/data/content.json"]:
		source_hashes[path] = FileAccess.get_sha256(path)
	_record("bound route report sources match the current staged production sources",ok,observed)
	return ok


func _run() -> void:
	began = Time.get_ticks_msec()
	_parse_arguments()
	if output_path.is_empty() or FileAccess.file_exists(output_path):
		push_error("Pass a new --output path; existing evidence is never overwritten.")
		quit(2)
		return
	_record("CLI options are complete and explicit",argument_errors.is_empty() and not route_report_path.is_empty() and _valid_sha256(route_report_sha256),{"errors":argument_errors})
	_record("coordinator uses the headless display server",DisplayServer.get_name() == "headless",{"display_server":DisplayServer.get_name()})
	if not errors.is_empty():
		_finish()
		return
	var actual_hash: String = FileAccess.get_sha256(route_report_path)
	_record("route report bytes match the explicitly supplied SHA256",actual_hash == route_report_sha256,{"name":route_report_path.get_file(),"sha256":actual_hash})
	var file: FileAccess = FileAccess.open(route_report_path,FileAccess.READ)
	if file == null or file.get_length() > 16*1024*1024:
		_record("route report is a bounded readable file",false)
		_finish()
		return
	var parser := JSON.new()
	var parsed: Error = parser.parse(file.get_as_text())
	file.close()
	if parsed != OK or not (parser.data is Dictionary):
		_record("route report is complete JSON",false)
		_finish()
		return
	var report: Dictionary = parser.data
	var cases: Array = report.get("cases",[])
	var report_ok: bool = bool(report.get("passed",false)) and bool(report.get("measurement_completed",false)) and report.get("errors",[1]).is_empty() and report.get("content_id","") == CHAPTER_ID and report.get("mode","") == PRACTICE and int(report.get("completed_cases",0)) == 2 and cases.size() == 2
	_record("fixture is the completed same-source two-route Practice measurement",report_ok,{"suite":report.get("suite",""),"content_id":report.get("content_id",""),"completed_cases":report.get("completed_cases",0)})
	_bind_sources(report)
	if not errors.is_empty():
		_finish()
		return
	var fixture_case: Dictionary = cases[0]
	var snapshot: Dictionary = fixture_case.get("full_final_snapshot",{})
	var fixture_ok: bool = bool(fixture_case.get("passed",false)) and fixture_case.get("route","") == "keen" and fixture_case.get("seed","") == "00000001" and fixture_case.get("mode","") == PRACTICE and bool(fixture_case.get("authoritative_full_action_replay",{}).get("ok",false)) and int(fixture_case.get("actual_actions",0)) > 0 and snapshot.get("actions",[]).size() == int(fixture_case.get("actual_actions",0)) and bool(snapshot.get("slice_complete",false)) and not bool(snapshot.get("failed",true)) and not bool(snapshot.get("campaign_complete",true)) and int(snapshot.get("core_state",{}).get("floor",-1)) == 19 and not bool(snapshot.get("core_state",{}).get("won",true))
	fixture_binding = {"report_name":route_report_path.get_file(),"report_sha256":actual_hash,"json_pointer":"/cases/0/full_final_snapshot","route":fixture_case.get("route",""),"seed":fixture_case.get("seed",""),"actual_actions":fixture_case.get("actual_actions",0),"snapshot_sha256":Geometry.content_hash(snapshot)}
	_record("selected fixture is the actual completed F20 full action snapshot",fixture_ok,fixture_binding)
	if not errors.is_empty():
		_finish()
		return
	root.size = Vector2i(1280,800)
	var legacy: Node = LegacyScene.instantiate()
	root.add_child(legacy)
	await _check_initial(legacy,"v1",10,"first-chapter","res://fifty/data/content.json","First chapter")
	await _start_practice(legacy,"v1")
	var legacy_rules: Object = legacy.get("rules")
	var legacy_identity: Dictionary = legacy_rules.call("runtime_identity")
	var legacy_slot: String = Saves.slot_path(str(legacy.get("slot_id")),PRACTICE,str(legacy_identity.get("content_id","")))
	await _release(legacy)
	var view: Node = ChapterScene.instantiate()
	root.add_child(view)
	await _check_initial(view,"chapter2",20,"chapter2-preview",CHAPTER_CONTENT,"Chapters 1–2")
	await _start_practice(view,"chapter2")
	var rules: Object = view.get("rules")
	var identity: Dictionary = rules.call("runtime_identity")
	var slot_id: String = str(view.get("slot_id"))
	var chapter_slot: String = Saves.slot_path(slot_id,PRACTICE,str(identity.get("content_id","")))
	_record("profile labels select distinct chapter and mode save namespaces",legacy_identity.get("content_id","") == "stairkeep-fifty-slice/v1" and identity.get("content_id","") == CHAPTER_ID and not legacy_slot.is_empty() and not chapter_slot.is_empty() and legacy_slot != chapter_slot and legacy_slot.contains("/chapter1/") and chapter_slot.contains("/chapter2/"),{"v1_slot":legacy_slot,"chapter2_slot":chapter_slot})
	var names_before: String = Geometry.content_hash(rules.call("export_snapshot"))
	var data: Dictionary = rules.get("data")
	var floor_11: String = str(data["floors"][10].get("name_en",""))
	var floor_20: String = str(data["floors"][19].get("name_en",""))
	_record("floor naming helper uses the actual F11 and F20 English metadata",not floor_11.is_empty() and not floor_20.is_empty() and view.call("_floor_name",10) == floor_11 and view.call("_floor_name",19) == floor_20,{"F11":view.call("_floor_name",10),"F20":view.call("_floor_name",19),"scope":"Read-only production presentation helper; not additional travel to these floors."})
	_record("naming inspection leaves the authoritative initial state unchanged",names_before == Geometry.content_hash(rules.call("export_snapshot")))
	_record("fixture slot is initially absent in the isolated user-data directory",not FileAccess.file_exists(chapter_slot),{"slot":chapter_slot})
	await _release(view)
	if not errors.is_empty():
		_finish()
		return
	var completed = Runtime.new()
	var loaded: Dictionary = completed.load_content(CHAPTER_CONTENT)
	var started: Dictionary = completed.choose_mode(PRACTICE,1)
	var imported: Dictionary = completed.import_snapshot(snapshot)
	_record("real final snapshot is authoritatively replayed into a fresh Practice runtime",bool(loaded.get("ok",false)) and bool(started.get("ok",false)) and bool(imported.get("ok",false)) and Geometry.content_hash(completed.export_snapshot()) == Geometry.content_hash(snapshot),{"load":_verdict(loaded),"start":_verdict(started),"import":_verdict(imported),"snapshot_sha256":Geometry.content_hash(completed.export_snapshot())})
	if not errors.is_empty():
		_finish()
		return
	var saved: Dictionary = Saves.write_slot(completed,slot_id)
	_record("real completed runtime writes the production chapter2 slot",bool(saved.get("ok",false)) and FileAccess.file_exists(chapter_slot),_verdict(saved))
	if not errors.is_empty():
		_finish()
		return
	var completed_view: Node = await _fresh_chapter_load("completed F20")
	var completed_rules: Object = completed_view.get("rules")
	var actual: Dictionary = completed_rules.call("export_snapshot")
	var completed_status: Dictionary = completed_view.call("view_status")
	var completed_world: Node = completed_view.get("world")
	var overlay: Control = completed_view.get("overlay") as Control
	var scope_label: Label = completed_view.get("availability_label") as Label
	var floor_label: Label = completed_view.get("floor_label") as Label
	_record("view loads the whole actual completed snapshot rather than an initial state",Geometry.content_hash(actual) == Geometry.content_hash(snapshot) and int(completed_view.get("selected_seed")) == 1,{"snapshot_sha256":Geometry.content_hash(actual),"selected_seed":completed_view.get("selected_seed")})
	_record("F20 is slice complete with a blocked-world slice modal, not fifty-floor victory",bool(actual.get("slice_complete",false)) and not bool(actual.get("failed",true)) and not bool(actual.get("campaign_complete",true)) and not bool(actual.get("core_state",{}).get("won",true)) and int(actual.get("core_state",{}).get("floor",-1)) == 19 and completed_status.get("modal","") == "slice" and overlay != null and overlay.visible and not completed_world.is_processing_unhandled_input(),{"status":completed_status,"slice_complete":actual.get("slice_complete"),"campaign_complete":actual.get("campaign_complete"),"core_won":actual.get("core_state",{}).get("won"),"modal_copy":_modal_text(completed_view)})
	_record("completed scope still displays twenty of fifty and the unmade range",scope_label != null and scope_label.text.contains("20 / 50") and scope_label.text.contains("21–50") and floor_label != null and floor_label.text.begins_with("20 / 20"),{"scope":scope_label.text if scope_label != null else "","floor":floor_label.text if floor_label != null else ""})
	await _release(completed_view)
	var core_before_end: String = Geometry.content_hash(completed.state)
	var ended: Dictionary = completed.give_up(true)
	var failed_snapshot: Dictionary = completed.export_snapshot()
	_record("completed actual run is voluntarily ended through the authoritative API",bool(ended.get("ok",false)) and bool(failed_snapshot.get("failed",false)) and bool(failed_snapshot.get("slice_complete",false)) and failed_snapshot.get("failure",{}).get("kind","") == "abandoned" and Geometry.content_hash(completed.state) == core_before_end,{"result":_verdict(ended),"core_unchanged":Geometry.content_hash(completed.state) == core_before_end,"snapshot_sha256":Geometry.content_hash(failed_snapshot)})
	var failed_saved: Dictionary = Saves.write_slot(completed,slot_id)
	_record("completed and failed full snapshot writes through production Save",bool(failed_saved.get("ok",false)),_verdict(failed_saved))
	if not errors.is_empty():
		_finish()
		return
	var failed_view: Node = await _fresh_chapter_load("completed then abandoned")
	var failed_rules: Object = failed_view.get("rules")
	var restored: Dictionary = failed_rules.call("export_snapshot")
	var failed_status: Dictionary = failed_view.call("view_status")
	var failed_world: Node = failed_view.get("world")
	var failed_overlay: Control = failed_view.get("overlay") as Control
	var stats: Dictionary = failed_view.get("stats")
	var hp: Label = stats.get("hp") as Label
	_record("failed-plus-complete load preserves the entire authoritative ended snapshot",Geometry.content_hash(restored) == Geometry.content_hash(failed_snapshot),{"expected_sha256":Geometry.content_hash(failed_snapshot),"actual_sha256":Geometry.content_hash(restored)})
	_record("failure recovery takes precedence over the completed slice modal",bool(restored.get("failed",false)) and bool(restored.get("slice_complete",false)) and not bool(restored.get("campaign_complete",true)) and not bool(restored.get("core_state",{}).get("won",true)) and failed_status.get("modal","") == "recovery" and failed_overlay != null and failed_overlay.visible and not failed_world.is_processing_unhandled_input(),{"status":failed_status,"modal_copy":_modal_text(failed_view),"world_input_enabled":failed_world.is_processing_unhandled_input()})
	_record("voluntary end shows remaining HP and its actual cause",hp != null and hp.text == "HP %d / RUN ENDED" % int(restored.get("core_state",{}).get("hp",0)) and _modal_text(failed_view).contains("You ended this run."),{"hud":hp.text if hp != null else "","core_hp":restored.get("core_state",{}).get("hp")})
	await _release(failed_view)
	measurement_completed = true
	_finish()


func _finish() -> void:
	var result: Dictionary = {"suite":"fifty-chapter2-preview-instrumented-scene/v1","measurement_completed":measurement_completed,"passed":measurement_completed and errors.is_empty(),"checks":checks,"errors":errors,"elapsed_ms":Time.get_ticks_msec()-began,"engine":Engine.get_version_info(),"display_server":DisplayServer.get_name(),"logical_viewport":[1280,800],"source_hashes":source_hashes,"route_fixture":fixture_binding,"pixels_reviewed":false,"real_keyboard_mouse_touch_tested":false,"browser_tested":false,"physical_device_tested":false,"F10_milestone_UI_executed":false,"scope":"Coordinator-run headless scene/resource/direct-production-method instrumentation; inspect checks for stages actually reached. A successful complete run authoritatively imports the bound real F20 route snapshot, then saves/loads it through production APIs. No state/HP/CP injection; no rendered-pixel or physical-input acceptance. F10 UI milestone travel is not separately executed by this helper."}
	var file: FileAccess = FileAccess.open(output_path,FileAccess.WRITE)
	if file == null:
		push_error("Could not write the new scene evidence output.")
		quit(2)
		return
	file.store_string(JSON.stringify(result,"  ") + "\n")
	file.close()
	print(JSON.stringify({"passed":result["passed"],"checks":checks.size(),"errors":errors.size(),"elapsed_ms":result["elapsed_ms"]}))
	quit(0 if errors.is_empty() else 1)
