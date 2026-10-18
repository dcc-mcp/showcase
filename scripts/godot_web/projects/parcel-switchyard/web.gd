extends "res://parcel_game.gd"
## Additive Web presentation. The original parcel_game.gd remains byte-identical.
## Game rules, order sequence, capacity, travel time and score use the original.
const PHONE_SIZE := Vector2i(720, 1320)
const DESKTOP_SIZE := Vector2i(1280, 720)
var mobile_layout := false
var paused := false
var state_clock := 0.0
var publication_id := 0
var language := "en"
var chinese: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://translations.json"))
var chinese_font: Font = preload("res://parcel-interface.otf")
var draw_texts: Array[String] = []
var missing_translations: Array[String] = []
var missing_glyphs: Array[int] = []
var draw_receipt: Dictionary = {}
var draw_pending := false
var draw_id := 0
var web_callback: JavaScriptObject
var touch_origin := Vector2.ZERO
var touch_id := -1
var touch_moved := false

func _ready() -> void:
	# Keep the original Latin face, but do not depend on OS fallback glyphs on Web.
	var english_font := FontVariation.new()
	english_font.base_font = font
	english_font.fallbacks = [chinese_font]
	font = english_font
	language = "zh" if "--lang=zh" in OS.get_cmdline_user_args() else "en"
	mobile_layout = "--mobile-layout" in OS.get_cmdline_user_args()
	super._ready()
	web_layout(mobile_layout)
	if "--web-test" in OS.get_cmdline_user_args():
		get_tree().quit(0 if _web_tests() else 1)
		return
	if OS.has_feature("web"):
		web_callback = JavaScriptBridge.create_callback(web_command)
		JavaScriptBridge.get_interface("window").showcaseCommand = web_callback
		web_publish()

func _fit() -> void:
	# Content scaling is handled by the Window; never scale a phone into 1280x720.
	scale = Vector2.ONE
	position = Vector2.ZERO

func web_layout(mobile: bool) -> void:
	mobile_layout = mobile
	get_window().content_scale_size = PHONE_SIZE if mobile else DESKTOP_SIZE
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_window().content_scale_aspect = Window.CONTENT_SCALE_ASPECT_KEEP
	_fit()
	queue_redraw()
	web_publish()

func control_rect(command: String) -> Rect2:
	if mobile_layout:
		if command.begins_with("route:"):
			return Rect2(36 + int(command.trim_prefix("route:")) * 220, 754, 208, 128)
		return {"send": Rect2(36, 888, 648, 128), "auto": Rect2(36, 1022, 208, 128), "pause": Rect2(256, 1022, 208, 128), "reset": Rect2(476, 1022, 208, 128)}.get(command, Rect2())
	if command.begins_with("route:"):
		return Rect2(961, 287 + int(command.trim_prefix("route:")) * 66, 258, 56)
	return {"send": send_rect, "auto": auto_rect, "reset": Rect2(1045, 24, 188, 54), "pause": Rect2(845, 24, 188, 54)}.get(command, Rect2())

func commands() -> Array[String]:
	return ["route:0", "route:1", "route:2", "send", "auto", "pause", "reset"]

func command(value: String) -> void:
	if value == "reset":
		_reset()
	elif value == "pause":
		paused = not paused
	elif value == "stop":
		paused = true
	elif value.begins_with("route:"):
		var route := int(value.trim_prefix("route:"))
		if route >= 0 and route < 3: selected = route
	elif not paused:
		if value == "send": _dispatch()
		elif value == "auto": auto_send = not auto_send
	queue_redraw()
	web_publish()

func _reset() -> void:
	super._reset()
	paused = false

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var value: String = {KEY_1: "route:0", KEY_2: "route:1", KEY_3: "route:2", KEY_SPACE: "send", KEY_A: "auto", KEY_R: "reset", KEY_P: "pause"}.get(event.keycode, "")
		if not value.is_empty(): command(value)
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_pointer(get_global_transform_with_canvas().affine_inverse() * event.position)
	elif event is InputEventScreenTouch:
		if event.pressed and touch_id < 0:
			touch_id = event.index
			touch_origin = event.position
			touch_moved = false
		elif not event.pressed and event.index == touch_id:
			if not touch_moved and event.position.distance_to(touch_origin) <= 18:
				_pointer(get_global_transform_with_canvas().affine_inverse() * event.position)
			touch_id = -1
	elif event is InputEventScreenDrag and event.index == touch_id:
		if event.position.distance_to(touch_origin) > 18: touch_moved = true

func _pointer(point: Vector2) -> void:
	for value in commands():
		if control_rect(value).has_point(point):
			command(value)
			return

func _process(delta: float) -> void:
	if not paused: super._process(delta)
	state_clock += delta
	if state_clock >= 0.1:
		state_clock = 0.0
		web_publish()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		paused = true
		queue_redraw()
		web_publish()

func web_command(args: Array) -> void:
	if args.is_empty(): return
	var value := str(args[0])
	if value in ["layout:mobile", "layout:desktop"]: web_layout(value == "layout:mobile")
	else: command(value)

func web_state() -> Dictionary:
	var targets := {}
	for value in commands():
		var rect := control_rect(value)
		targets[value] = [rect.position.x, rect.position.y, rect.size.x, rect.size.y]
	return {"publication_id": publication_id, "process_frame": Engine.get_process_frames(), "case": "parcel-switchyard", "language": language, "draw_receipt": draw_receipt, "mobile_layout": mobile_layout, "layout_size": [720, 1320] if mobile_layout else [1280, 720], "targets": targets, "selected": selected, "next_target": _next_target(), "sent": sent, "delivered": delivered, "missed": missed, "streak": streak, "best": best, "active": parcels.size(), "auto": auto_send, "paused": paused, "notice": localized(notice), "elapsed": elapsed, "minimum_mobile_text_units": 40}

func localized(value: String) -> String:
	return str(chinese.get(value, value)) if language == "zh" else value

func _txt(at: Vector2, value: String, size: int, color: Color = INK) -> void:
	var translated := localized(value)
	var active_font: Font = chinese_font if language == "zh" else font
	if language == "zh" and not chinese.has(value):
		for character in value:
			var cp: int = character.unicode_at(0)
			if ((cp >= 65 and cp <= 90) or (cp >= 97 and cp <= 122)) and value not in missing_translations:
				missing_translations.append(value)
	for index in range(translated.length()):
		var cp := translated.unicode_at(index)
		if cp > 32 and not active_font.has_char(cp) and cp not in missing_glyphs: missing_glyphs.append(cp)
	draw_texts.append(translated)
	draw_string(active_font, at, translated, HORIZONTAL_ALIGNMENT_LEFT, -1, size, color)

func record_draw() -> void:
	if draw_pending or DisplayServer.get_name() == "headless": return
	draw_pending = true
	var texts := draw_texts.duplicate()
	var untranslated := missing_translations.duplicate()
	var missing := missing_glyphs.duplicate()
	var drawn_language := language
	await RenderingServer.frame_post_draw
	draw_id += 1
	draw_receipt = {"draw_id": draw_id, "draw_frame": Engine.get_frames_drawn(), "language": drawn_language, "labels": texts, "missing_translations": untranslated, "missing_glyphs": missing}
	draw_pending = false
	web_publish()

func web_publish() -> void:
	publication_id += 1
	if OS.has_feature("web"):
		JavaScriptBridge.get_interface("window").showcaseReceive(JSON.stringify(web_state()))

func _draw() -> void:
	draw_texts.clear()
	missing_translations.clear()
	missing_glyphs.clear()
	if not mobile_layout:
		super._draw()
		for value in ["pause", "reset"]:
			var rect := control_rect(value)
			_rr(rect, INK, 12)
			_txt(rect.position + Vector2(16, 35), ("Resume [P]" if paused else "Pause [P]") if value == "pause" else "Fresh shift [R]", 18, PAPER)
	else:
		_draw_phone()
	record_draw()

func _draw_phone() -> void:
	draw_rect(Rect2(Vector2.ZERO, PHONE_SIZE), PAPER)
	_txt(Vector2(36, 70), "Parcel Switchyard", 48)
	_txt(Vector2(36, 116), "MATCH LABELS. SEND HOME.", 40, Color("526a62"))
	for i in range(3):
		var x := 36 + i * 220
		_rr(Rect2(x, 144, 208, 100), Color("e3e3d6"), 14)
		_txt(Vector2(x + 16, 181), ["HOME", "WRONG", "STREAK"][i], 40, Color("526a62"))
		_txt(Vector2(x + 16, 226), str([delivered, missed, streak][i]), 42)
	_rr(Rect2(36, 266, 648, 322), INK, 22)
	var hub := Vector2(308, 427)
	for lane in range(2):
		var points := _phone_incoming(lane)
		draw_polyline(points, Color("47656a"), 40, true)
		draw_polyline(points, Color("28454d"), 22, true)
	for route in range(3):
		var points := _phone_outgoing(route)
		draw_polyline(points, ROUTE_COLORS[route].darkened(0.5), 40, true)
		draw_polyline(points, Color("28454d"), 22, true)
		var at := points[-1]
		_rr(Rect2(at - Vector2(24, 36), Vector2(70, 64)), ROUTE_COLORS[route], 10)
		_txt(at + Vector2(-8, 12), str(route + 1), 34)
	draw_circle(hub, 37, Color("75948b"))
	draw_circle(hub, 30, Color("233e46"))
	var direction := Vector2(1, (selected - 1) * 0.7).normalized()
	_line(hub - direction * 22, hub + direction * 22, ROUTE_COLORS[selected], 7)
	draw_circle(hub, 6, PAPER)
	for parcel in parcels:
		var fraction := float(parcel["progress"])
		var point: Vector2
		if fraction < 0.48: point = _path_point(_phone_incoming(int(parcel["lane"])), fraction / 0.48)
		else: point = _path_point(_phone_outgoing(int(parcel["route"])), (fraction - 0.48) / 0.52)
		_box(point, int(parcel["target"]))
	_txt(Vector2(58, 305), "PAUSED" if paused else "SORTING FLOOR", 40, PAPER)
	_txt(Vector2(58, 566), "%d / 6 PARCELS" % parcels.size(), 40, MUTED)
	_txt(Vector2(36, 650), "NEXT PARCEL", 40, Color("526a62"))
	_txt(Vector2(36, 708), "%d  %s" % [_next_target() + 1, ROUTE_NAMES[_next_target()].capitalize()], 48)
	_rr(Rect2(572, 618, 112, 112), ROUTE_COLORS[_next_target()], 16)
	_txt(Vector2(608, 692), str(_next_target() + 1), 56)
	for route in range(3):
		var rect := control_rect("route:" + str(route))
		_rr(rect, INK if selected == route else Color("e3e3d6"), 14, ROUTE_COLORS[route], 4)
		_txt(rect.position + Vector2(16, 43), str(route + 1) + ("  ON" if selected == route else ""), 40, ROUTE_COLORS[route].darkened(0.45) if selected != route else ROUTE_COLORS[route])
		_txt(rect.position + Vector2(16, 88), ROUTE_NAMES[route].capitalize(), 40, PAPER if selected == route else INK)
	var send := control_rect("send")
	_rr(send, Color("c5d1c6") if paused else TEAL, 16)
	_txt(send.position + Vector2(28, 72), "RESUME TO SEND" if paused else "SEND PARCEL", 42)
	for value in ["auto", "pause", "reset"]:
		var rect := control_rect(value)
		_rr(rect, INK if value == "auto" and auto_send else Color("e3e3d6"), 14)
		var label: String = {"auto": "AUTO " + ("ON" if auto_send else "OFF"), "pause": "RESUME" if paused else "PAUSE", "reset": "RESET"}[value]
		_txt(rect.position + Vector2(12, 68), label, 40, PAPER if value == "auto" and auto_send else INK)
	var lines: Array[String] = ["Pick a route above.", "Then send the next parcel."]
	if notice.begins_with("Busy"): lines = ["Tracks are full.", "Wait for a parcel to arrive."]
	elif notice.begins_with("Nice"): lines = ["Nice routing!", "Another parcel is home."]
	elif notice.begins_with("Wrong"): lines = ["Wrong stop. Try again.", "Match the number and name."]
	elif paused: lines = ["Shift paused.", "Tap Resume when you're ready."]
	_txt(Vector2(36, 1200), lines[0], 40, Color("526a62"))
	_txt(Vector2(36, 1248), lines[1], 40, Color("526a62"))
	_txt(Vector2(36, 1300), "EVERY PARCEL HAS A HOME.", 40, Color("526a62"))

func _phone_incoming(lane: int) -> PackedVector2Array:
	return PackedVector2Array([Vector2(92, 360 + lane * 134), Vector2(182, 360 + lane * 134), Vector2(260, 427), Vector2(308, 427)])

func _phone_outgoing(route: int) -> PackedVector2Array:
	return PackedVector2Array([Vector2(308, 427), Vector2(382, 427), Vector2(472, 336 + route * 91), Vector2(600, 336 + route * 91)])

func _web_tests() -> bool:
	var checks: Array[Dictionary] = []
	var english_missing: Array[int] = []
	for key: String in chinese:
		for i in range(key.length()):
			var cp := key.unicode_at(i)
			if cp > 32 and not font.has_char(cp) and cp not in english_missing: english_missing.append(cp)
	checks.append({"name": "english_full_catalog_glyph_coverage", "pass": english_missing.is_empty(), "missing": english_missing})
	checks.append({"name": "english_original_latin_metrics_retained", "pass": font.get_string_size("Parcel Switchyard", HORIZONTAL_ALIGNMENT_LEFT, -1, 41) == ThemeDB.fallback_font.get_string_size("Parcel Switchyard", HORIZONTAL_ALIGNMENT_LEFT, -1, 41)})
	for key: String in chinese:
		var value: String = chinese[key]
		var missing: Array[int] = []
		for i in range(value.length()):
			if value.unicode_at(i) > 32 and not chinese_font.has_char(value.unicode_at(i)): missing.append(value.unicode_at(i))
		checks.append({"name": "chinese_glyph_coverage_" + key, "pass": missing.is_empty(), "missing": missing})
	for label in ["HOME", "WRONG", "STREAK"]:
		var measured := chinese_font.get_string_size(chinese[label], HORIZONTAL_ALIGNMENT_LEFT, -1, 40).x
		checks.append({"name": "chinese_score_fit_" + label, "pass": measured <= 176, "measured_units": measured})
	for label in ["MATCH LABELS. SEND HOME.", "Tap Resume when you're ready.", "Match the number and name."]:
		var measured := chinese_font.get_string_size(chinese[label], HORIZONTAL_ALIGNMENT_LEFT, -1, 40).x
		checks.append({"name": "chinese_instruction_fit_" + label, "pass": measured <= 648, "measured_units": measured})
	checks.append({"name": "original_nine_rule_checks", "pass": _run_tests()})
	_reset()
	command("send")
	var before := JSON.stringify(parcels)
	for phone in [true, false, true, false]:
		web_layout(phone)
		checks.append({"name": "layout_preserves_state_" + str(checks.size()), "pass": JSON.stringify(parcels) == before and sent == 1})
	command("pause")
	_process(0.1)
	command("send")
	checks.append({"name": "pause_freezes_and_blocks_dispatch", "pass": paused and sent == 1 and JSON.stringify(parcels) == before})
	command("pause")
	_advance(4.0)
	checks.append({"name": "resume_delivers", "pass": delivered == 1})
	web_layout(true)
	for value in commands():
		var rect := control_rect(value)
		checks.append({"name": "phone_target_" + value, "pass": rect.size.x >= 128 and rect.size.y >= 128 and Rect2(Vector2.ZERO, PHONE_SIZE).encloses(rect)})
	for label in ["HOME", "WRONG", "STREAK"]:
		var measured := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 40).x
		checks.append({"name": "phone_score_label_fits_" + label, "pass": measured <= 176, "measured_units": measured, "available_units": 176})
	for label in ["MATCH LABELS. SEND HOME.", "Tap Resume when you're ready.", "Match the number and name."]:
		var measured := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 40).x
		checks.append({"name": "phone_instruction_fits_" + str(checks.size()), "pass": measured <= 648, "measured_units": measured, "available_units": 648})
	_reset()
	for route in range(3):
		var press := InputEventScreenTouch.new()
		press.index = 0
		press.position = control_rect("route:" + str(route)).get_center()
		press.pressed = true
		_unhandled_input(press)
		press.pressed = false
		_unhandled_input(press)
		checks.append({"name": "synthetic_touch_route_" + str(route), "pass": selected == route})
	for attempt in range(3): command("reset")
	checks.append({"name": "reset_all_state", "pass": not paused and not auto_send and sent == 0 and delivered == 0 and missed == 0 and streak == 0 and best == 0 and parcels.is_empty() and selected == 1})
	var passed := checks.all(func(check): return check["pass"])
	print("PARCEL_WEB_TEST_REPORT " + JSON.stringify({"passed": passed, "checks": checks, "scope": "headless rule/layout and synthetic event regressions; not real browser input"}))
	return passed
