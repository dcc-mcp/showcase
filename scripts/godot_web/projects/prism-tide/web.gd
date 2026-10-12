extends "res://prism_tide.gd"
# A small browser adapter adds explicit local checkpoints, never remote storage.
var save_status = "ready"
const SAVE_PATH = "user://prism-tide-web.json"
# Portrait is a native, quarter-turned view of the same optical field.
# No puzzle coordinates or historical source artwork are changed.
const MOBILE_SIZE = Vector2i(720, 1760)
const MOBILE_ORIGIN = Vector2(48, 340)
const MOBILE_CELL = 104.0
const MOBILE_BOARD = Rect2(32, 324, 656, 1072)
const MOBILE_CONTROLS = {
	"select": Rect2(32, 1520, 312, 100),
	"turn": Rect2(376, 1520, 312, 100),
	"reset": Rect2(32, 1640, 312, 100),
	"next": Rect2(376, 1640, 312, 100)
}
var mobile_layout = false
func _ready():
	mobile_layout = "--mobile-layout" in OS.get_cmdline_user_args()
	if mobile_layout:
		get_window().content_scale_size = MOBILE_SIZE
		get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	super._ready()
	web_ready()
	if "--web-test" in OS.get_cmdline_user_args(): web_test()
func _process(delta):
	super._process(delta)
	web_tick(delta)
func web_state():
	var state = {"case": "prism-tide", "level": level + 1, "moves": moves, "selected": selected, "won": won, "mirrors": mirrors.map(func(m): return m.slash), "gates": shutters.map(func(g): return g.open), "status": save_status, "persistent": OS.is_userfs_persistent(), "mobile_layout": mobile_layout}
	state["layout_width"] = MOBILE_SIZE.x if mobile_layout else 1280
	state["layout_height"] = MOBILE_SIZE.y if mobile_layout else 800
	state["layout_size"] = [state.layout_width, state.layout_height]
	state["minimum_text_size"] = 32 if mobile_layout else 10
	if mobile_layout:
		var targets = {"objects": []}
		for command in MOBILE_CONTROLS:
			targets[command] = mobile_rect_state(MOBILE_CONTROLS[command])
		for i in range(mirrors.size() + shutters.size()):
			var target = mobile_rect_state(mobile_object_rect(i))
			target["index"] = i
			target["kind"] = "mirror" if i < mirrors.size() else "gate"
			targets.objects.append(target)
		state["native_targets"] = targets
	return state
func mobile_rect_state(rect):
	return {"x": rect.position.x, "y": rect.position.y, "width": rect.size.x, "height": rect.size.y, "center_x": rect.get_center().x, "center_y": rect.get_center().y}
func mobile_object_rect(i):
	var item = mirrors[i] if i < mirrors.size() else shutters[i - mirrors.size()]
	return Rect2(center(item.p) - Vector2(44, 44), Vector2(88, 88))
func center(p):
	if mobile_layout:
		return MOBILE_ORIGIN + Vector2(p.y, 9 - p.x) * MOBILE_CELL + Vector2.ONE * MOBILE_CELL / 2.0
	return super.center(p)
func _unhandled_input(event):
	if not mobile_layout:
		super._unhandled_input(event)
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		# Touch is emulated as a mouse press by project.godot. Use the event's
		# logical position, not a stale global cursor or DOM command injection.
		for command in MOBILE_CONTROLS:
			if MOBILE_CONTROLS[command].has_point(event.position):
				web_command([command])
				get_viewport().set_input_as_handled()
				return
		for i in range(mirrors.size() + shutters.size()):
			if mobile_object_rect(i).has_point(event.position):
				selected = i
				report("select")
				web_publish()
				get_viewport().set_input_as_handled()
				return
	elif event is InputEventKey:
		super._unhandled_input(event)
func web_pause():
	pass
func web_save():
	if OS.has_feature("web") and not OS.is_userfs_persistent():
		save_status = "save_failed"
		return
	var f = FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if not f:
		save_status = "save_failed"
		return
	f.store_string(JSON.stringify(web_state()))
	f.close()
	save_status = "saved"
func web_load():
	if not FileAccess.file_exists(SAVE_PATH):
		save_status = "no_save"
		return
	var d = JSON.parse_string(FileAccess.get_file_as_string(SAVE_PATH))
	if not d is Dictionary:
		save_status = "invalid_save"
		return
	var saved_level = d.get("level")
	if not (saved_level is float or saved_level is int) or saved_level != float(int(saved_level)) or int(saved_level) < 1 or int(saved_level) > 3:
		save_status = "invalid_save"
		return
	var idx = int(saved_level) - 1
	if not d.get("mirrors") is Array or not d.get("gates") is Array: return
	if d.mirrors.size() != LAYOUTS[idx].mirrors.size() or d.gates.size() != LAYOUTS[idx].gates.size(): return
	for v in d.mirrors + d.gates:
		if not v is bool: return
	load_level(idx)
	for i in range(mirrors.size()): mirrors[i].slash = d.mirrors[i]
	for i in range(shutters.size()): shutters[i].open = d.gates[i]
	moves = maxi(0, int(d.get("moves", 0)))
	trace()
	save_status = "loaded"
func web_command(args):
	if args.is_empty(): return
	match str(args[0]):
		"select": selected = (selected + 1) % (mirrors.size() + shutters.size())
		"turn": activate(selected)
		"next":
			if won: load_level((level + 1) % 3)
		"reset": load_level(level)
		"save": web_save()
		"load": web_load()
	web_publish()

var web_callback: JavaScriptObject
var web_elapsed = 0.0
func web_ready():
	if OS.has_feature("web"):
		web_callback = JavaScriptBridge.create_callback(web_command)
		JavaScriptBridge.get_interface("window").showcaseCommand = web_callback
		web_publish()
func web_tick(delta):
	web_elapsed += delta
	if web_elapsed >= 0.1:
		web_elapsed = 0.0
		web_publish()
func web_publish():
	if OS.has_feature("web"):
		JavaScriptBridge.get_interface("window").showcaseReceive(JSON.stringify(web_state()))
func _notification(what):
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		web_pause()

func web_test():
	var checks = mobile_input_checks() if mobile_layout else {}
	for k in range(3):
		load_level(k)
		var solutions = [[0, 1], [0, 1, 4], [0, 1, 2, 3, 6, 7]]
		for i in solutions[k]: activate(i)
		checks["level_%d_solved" % (k + 1)] = won
		web_save()
		load_level(k)
		web_load()
		checks["level_%d_save_reset_load" % (k + 1)] = won and level == k and moves == solutions[k].size() and save_status == "loaded"
	var passed = checks.values().all(func(v): return v)
	print("PRISM_WEB_TEST " + JSON.stringify({"checks": checks, "passed": passed}))
	get_tree().quit(0 if passed else 1)

# The compact Web fallback font omits decorative arrow glyphs.
func text_at(s, p, size = 18, color = INK):
	super.text_at(s.replace("→", ">").replace("↺", ""), p, size, color)

# Desktop preserves the original composition. Portrait reallocates the same
# drawing primitives, palette, and live beam around a readable six-column board.
func _draw():
	if not mobile_layout:
		super._draw()
		return
	draw_rect(Rect2(Vector2.ZERO, Vector2(MOBILE_SIZE)), Color("071b24"))
	for i in range(36):
		var points = PackedVector2Array()
		for x in range(0, 721, 16):
			points.append(Vector2(x, 30 + i * 49 + sin(x * 0.007 + i * 0.45 + phase * 0.25) * 14))
		draw_polyline(points, Color(0.15, 0.36, 0.39, 0.13), 1, true)
	text_at("P / T", Vector2(32, 50), 32, TEAL)
	text_at("FIELD 0%d / 03" % (level + 1), Vector2(446, 50), 32, TEAL)
	text_at("PRISM TIDE", Vector2(32, 120), 60)
	text_at(TITLES[level], Vector2(32, 174), 36)
	text_at("Guide the light to the receiver.", Vector2(32, 220), 32, Color("9bb8ba"))
	box(Rect2(32, 242, 656, 64), Color("15343e"), 14)
	text_at("CONNECTED" if won else "SEEKING", Vector2(52, 286), 36, TEAL if won else GOLD)
	text_at("%02d turns" % moves, Vector2(488, 285), 32)
	box(MOBILE_BOARD, Color("0c2631"), 20)
	for x in range(10):
		for y in range(6):
			var p = center(Vector2i(x, y))
			draw_circle(p, 2.5, Color("3c5962"))
			line(p + Vector2(-40, -40), p + Vector2(-30, -40), Color("163640"), 2)
			line(p + Vector2(-40, -40), p + Vector2(-40, -30), Color("163640"), 2)
	for i in range(beam.size() - 1):
		var a = beam[i]
		var b = beam[i + 1]
		b.x = clampf(b.x, MOBILE_BOARD.position.x + 6, MOBILE_BOARD.end.x - 6)
		b.y = clampf(b.y, MOBILE_BOARD.position.y + 6, MOBILE_BOARD.end.y - 6)
		for width in [24, 14, 6]:
			line(a, b, Color(0.38, 0.97, 0.79, 0.04 if width == 24 else (0.12 if width == 14 else 0.45)), width)
		line(a, b, TEAL, 3)
	for i in range(mirrors.size()):
		var m = mirrors[i]
		var p = center(m.p)
		draw_circle(p, 40, Color("102c36"))
		draw_arc(p, 40, 0, TAU, 64, Color("9e805a"), 2, true)
		if selected == i:
			draw_arc(p, 48, -0.3, 4.8, 64, TEAL, 4, true)
		# The view quarter-turns the field: slash artwork must
		# rotate with the field as well as the beam's cell centers.
		var v = Vector2(25, 25) if m.slash else Vector2(25, -25)
		line(p - v, p + v, Color("786753"), 12)
		line(p - v, p + v, GOLD, 5)
		draw_circle(p - v, 4, GOLD)
		draw_circle(p + v, 4, GOLD)
	for i in range(shutters.size()):
		var gate = shutters[i]
		var p = center(gate.p)
		box(Rect2(p - Vector2(36, 36), Vector2(72, 72)), Color("243742"), 10)
		for dx in [-18, 0, 18]:
			line(p + Vector2(dx, -24), p + Vector2(dx, 24), Color("607780") if gate.open else Color("e99573"), 5)
		if gate.open:
			draw_circle(p, 13, Color("0c2631"))
		if selected == i + mirrors.size():
			draw_arc(p, 48, 0, TAU, 64, TEAL, 4, true)
	var s = center(source)
	draw_circle(s, 28, Color("285b58"))
	draw_circle(s, 15, TEAL)
	draw_circle(s, 6, INK)
	var target = center(receiver)
	draw_arc(target, 38, 0, TAU, 64, TEAL if won else Color("789b9d"), 3, true)
	draw_arc(target, 27, phase * 0.5, phase * 0.5 + 4.9, 48, TEAL if won else Color("456b75"), 3, true)
	draw_circle(target, 13, TEAL if won else Color("284653"))
	var is_mirror = selected < mirrors.size()
	var label = "Selected: Mirror %d of %d" % [selected + 1, mirrors.size()] if is_mirror else "Selected: Gate %d of %d" % [selected - mirrors.size() + 1, shutters.size()]
	var detail = "Tap object to select; Turn to rotate."
	if not is_mirror:
		detail = "Gate open / tap Toggle to close." if shutters[selected - mirrors.size()].open else "Gate closed / tap Toggle to open."
	text_at(label, Vector2(32, 1450), 36, TEAL)
	text_at(detail, Vector2(32, 1494), 32, Color("9bb8ba"))
	mobile_button("select", "Select next", false)
	mobile_button("turn", "Turn mirror" if is_mirror else "Toggle gate", true)
	mobile_button("reset", "Reset field", false)
	mobile_button("next", "Sail again" if level == 2 else "Next waters", won, not won)
func mobile_button(command, label, accent, disabled = false):
	var rect = MOBILE_CONTROLS[command]
	box(rect, TEAL if accent else Color("15343e"), 16)
	var color = Color("09262c") if accent else (Color("89a9ad") if disabled else INK)
	var extent = font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 36)
	text_at(label, Vector2(rect.get_center().x - extent.x / 2.0, rect.position.y + 63), 36, color)

# Exercise the same native event path as touch-emulated mouse input. These run
# only in the explicit headless --web-test mode, never through JavaScript.
func mobile_test_press(pos):
	var event = InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	event.position = pos
	_unhandled_input(event)
func mobile_input_checks():
	var checks = {}
	load_level(0)
	checks["mobile_logical_canvas"] = get_window().content_scale_size == MOBILE_SIZE
	checks["mobile_rotated_cells"] = center(Vector2i(1, 0)) - center(Vector2i(0, 0)) == Vector2(0, -MOBILE_CELL)
	checks["mobile_minimum_target_size"] = mobile_object_rect(0).size == Vector2(88, 88) and MOBILE_CONTROLS.turn.size.y >= 88
	mobile_test_press(mobile_object_rect(1).get_center())
	checks["mobile_object_selects_without_turning"] = selected == 1 and moves == 0
	mobile_test_press(MOBILE_CONTROLS.turn.get_center())
	checks["mobile_native_turn"] = mirrors[1].slash and moves == 1
	mobile_test_press(MOBILE_CONTROLS.select.get_center())
	checks["mobile_native_select"] = selected == 2 and moves == 1
	mobile_test_press(MOBILE_CONTROLS.next.get_center())
	checks["mobile_next_locked_until_connected"] = level == 0 and moves == 1
	mobile_test_press(MOBILE_CONTROLS.reset.get_center())
	checks["mobile_native_reset"] = selected == 0 and moves == 0 and not won
	mobile_test_press(MOBILE_CONTROLS.turn.get_center())
	mobile_test_press(MOBILE_CONTROLS.select.get_center())
	mobile_test_press(MOBILE_CONTROLS.turn.get_center())
	checks["mobile_native_solution"] = won and moves == 2
	mobile_test_press(MOBILE_CONTROLS.next.get_center())
	checks["mobile_native_next"] = level == 1 and moves == 0 and not won
	mobile_test_press(mobile_object_rect(4).get_center())
	mobile_test_press(MOBILE_CONTROLS.turn.get_center())
	checks["mobile_native_gate"] = selected == 4 and shutters[0].open and moves == 1
	var targets = web_state().native_targets
	checks["mobile_read_only_target_geometry"] = targets.objects.size() == 5 and targets.turn.center_x == MOBILE_CONTROLS.turn.get_center().x
	return checks
