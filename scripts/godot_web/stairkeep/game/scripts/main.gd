extends Node2D
## Native presentation. Every move, preview and purchase delegates to StairRules.

const Rules = preload("res://scripts/rules.gd")
const World = preload("res://scripts/world.gd")
const Icon = preload("res://scripts/ui_icon.gd")
const GOLD := Color("e8c48a")
const CYAN := Color("7bcac8")
const CREAM := Color("f2e9d8")
const MUTED := Color("91a6af")
const INK := Color("101f2c")
const ENEMY_NAMES := {"moss":"Mossling", "cinder":"Cinder imp", "goblin":"Brass-tooth", "skeleton":"Bone archer", "stone_guard":"Stone guard", "hall_guard":"Hall sentinel", "warden":"Beacon warden", "sealed_sentinel":"Sealed sentinel"}
const FLOOR_NAMES := ["THE LANTERN GATE", "THE BRASS FORGE", "THE SEALED BEACON"]

var rules = Rules.new()
var world
var ui: Control
var stats: Dictionary = {}
var floor_label: Label
var inspector_title: Label
var inspector_copy: Label
var inspector_cost: Label
var inspector_action: Button
var shop_box: VBoxContainer
var toast: Label
var overlay: Control
var overlay_box: VBoxContainer
var selected: Array = []
var started := false
var paused := false
var move_clock := 0.0
var message_time := 0.0
var modal_kind := "title"
var layout_nodes: Dictionary = {}


func _ready() -> void:
	world = World.new()
	add_child(world)
	world.configure(rules)
	world.cell_clicked.connect(_cell_clicked)
	world.cell_hovered.connect(_hovered)
	_build_ui()
	_update()
	_show_modal("title")
	get_viewport().size_changed.connect(_layout)
	_layout()
	if "--layout-test" in OS.get_cmdline_user_args():
		call_deferred("_layout_test")


func _style(color: Color, border: Color = Color("314653")) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = color
	s.border_color = border
	s.set_border_width_all(1)
	s.set_corner_radius_all(6)
	s.content_margin_left = 18
	s.content_margin_right = 18
	s.content_margin_top = 12
	s.content_margin_bottom = 12
	return s


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	ui = Control.new()
	layer.add_child(ui)
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var theme := Theme.new()
	theme.default_font_size = 18
	theme.set_color("font_color", "Label", CREAM)
	theme.set_color("font_color", "Button", CREAM)
	theme.set_color("font_hover_color", "Button", GOLD)
	theme.set_color("font_disabled_color", "Button", Color("667984"))
	theme.set_stylebox("panel", "PanelContainer", _style(INK))
	theme.set_stylebox("normal", "Button", _style(Color("182f3d")))
	theme.set_stylebox("hover", "Button", _style(Color("244251"), GOLD))
	theme.set_stylebox("pressed", "Button", _style(Color("30515b"), CYAN))
	theme.set_stylebox("disabled", "Button", _style(Color("111f29")))
	theme.set_stylebox("focus", "Button", _style(Color(0,0,0,0), CYAN))
	ui.theme = theme
	var heading := _label("S T A I R K E E P", 30, GOLD)
	heading.position = Vector2(30, 19)
	ui.add_child(heading)
	layout_nodes.heading = heading
	var note := _label("WORKING TITLE  /  THREE-FLOOR EXPEDITION", 12, MUTED)
	note.position = Vector2(33, 58)
	ui.add_child(note)
	var actions := HBoxContainer.new()
	actions.position = Vector2(790, 25)
	actions.add_theme_constant_override("separation", 9)
	ui.add_child(actions)
	layout_nodes.actions = actions
	_button(actions, "Save", _save)
	_button(actions, "Load", _load)
	_button(actions, "Restart", func(): _show_modal("restart"))
	_button(actions, "Menu", func(): _show_modal("pause"))
	var row := HBoxContainer.new()
	row.position = Vector2(26, 89)
	row.size = Vector2(1228, 48)
	row.add_theme_constant_override("separation", 10)
	ui.add_child(row)
	layout_nodes.stats = row
	for key: String in ["hp", "atk", "def", "gold", "yellow", "blue"]:
		var panel := PanelContainer.new()
		panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(panel)
		var stat_row := HBoxContainer.new()
		stat_row.add_theme_constant_override("separation", 10)
		panel.add_child(stat_row)
		var icon = Icon.new()
		icon.kind = key
		icon.ink = CYAN if key == "blue" else GOLD
		stat_row.add_child(icon)
		var text := _label("", 18, CYAN if key == "blue" else GOLD)
		stat_row.add_child(text)
		stats[key] = text
	floor_label = _label("", 15, GOLD)
	floor_label.position = Vector2(32, 158)
	ui.add_child(floor_label)
	var side := PanelContainer.new()
	side.position = Vector2(946, 157)
	side.size = Vector2(305, 538)
	ui.add_child(side)
	layout_nodes.inspector = side
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 15)
	side.add_child(column)
	column.add_child(_label("FIELD NOTES", 12, MUTED))
	inspector_title = _label("The lantern gate", 25, GOLD)
	inspector_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(inspector_title)
	inspector_copy = _label("", 16, CREAM)
	inspector_copy.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inspector_copy.custom_minimum_size.y = 100
	column.add_child(inspector_copy)
	inspector_cost = _label("", 24, CYAN)
	column.add_child(inspector_cost)
	inspector_action = _button(column, "Approach", _approach_selected)
	shop_box = VBoxContainer.new()
	shop_box.add_theme_constant_override("separation", 7)
	column.add_child(shop_box)
	column.add_child(_label("Every encounter is deterministic.\nYou strike first. No dice rolls.", 13, MUTED))
	toast = _label("Inspect a creature before spending your health.", 17, CREAM)
	toast.position = Vector2(32, 686)
	toast.size = Vector2(1210, 45)
	toast.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	toast.z_index = 100
	ui.add_child(toast)
	var footer := _label("W / A / S / D  Move   •   Click a tile to inspect / approach   •   E  Use stairs   •   Esc  Pause", 14, MUTED)
	footer.position = Vector2(32, 751)
	ui.add_child(footer)
	var dpad := HBoxContainer.new()
	dpad.position = Vector2(949, 710)
	dpad.add_theme_constant_override("separation", 5)
	ui.add_child(dpad)
	layout_nodes.compass = dpad
	for entry: Array in [["NW",-1,0],["NE",0,-1],["SW",0,1],["SE",1,0]]:
		_button(dpad, str(entry[0]), _step.bind(int(entry[1]), int(entry[2])))
	overlay = Control.new()
	ui.add_child(overlay)
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var shade := ColorRect.new()
	shade.color = Color(0.015,0.025,0.045,0.89)
	overlay.add_child(shade)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var center := CenterContainer.new()
	overlay.add_child(center)
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var box := PanelContainer.new()
	box.custom_minimum_size = Vector2(580,0)
	center.add_child(box)
	overlay_box = VBoxContainer.new()
	overlay_box.add_theme_constant_override("separation", 18)
	box.add_child(overlay_box)


func _label(text: String, font_size: int = 18, color: Color = CREAM) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


func _button(parent: Node, text: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = 44
	button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	button.pressed.connect(callback)
	parent.add_child(button)
	return button


func _layout() -> void:
	world.fit_rect(Rect2(25, 197, 900, 460))


func _update() -> void:
	var s: Dictionary = rules.state
	stats.hp.text = "HP   %d" % int(s.hp)
	stats.atk.text = "ATK   %d" % int(s.atk)
	stats.def.text = "DEF   %d" % int(s.def)
	stats.gold.text = "GOLD   %d" % int(s.gold)
	stats.yellow.text = "Y KEY   %d" % int(s["keys"].yellow)
	stats.blue.text = "B KEY   %d" % int(s["keys"].blue)
	floor_label.text = "%02d / %02d    %s" % [int(s.floor) + 1, rules.data.floors.size(), FLOOR_NAMES[int(s.floor)]]
	world.refresh()
	_inspect(selected)


func _inspect(cell: Array) -> void:
	for child: Node in shop_box.get_children():
		child.queue_free()
	inspector_action.hide()
	inspector_cost.text = ""
	if cell.is_empty():
		inspector_title.text = "Choose your route"
		inspector_copy.text = "A key opens one door. Defeated foes and opened gates stay cleared when you return.\n\nThe upper stair is your objective."
		return
	var info: Dictionary = rules.inspect(cell)
	var item: Dictionary = info.get("object", {})
	var kind: String = str(item.get("kind", ""))
	inspector_action.show()
	inspector_action.disabled = not bool(info.walkable)
	inspector_action.text = "Approach / interact"
	match kind:
		"enemy":
			var enemy: Dictionary = info.enemy
			var fight: Dictionary = info.combat
			inspector_title.text = ENEMY_NAMES.get(item.type, "Sentinel")
			inspector_copy.text = "HP %d  /  ATK %d  /  DEF %d\nReward: %d gold\n\n%s" % [enemy.hp, enemy.atk, enemy.def, enemy.gold, "You can survive this encounter." if fight.win else str(fight.reason)]
			inspector_cost.text = "COST  %d HP" % int(fight.damage) if int(fight.damage) >= 0 else "ARMOR TOO STRONG"
			inspector_cost.add_theme_color_override("font_color", CYAN if fight.win else Color("e5968d"))
			inspector_action.disabled = not bool(fight.win)
		"shop":
			inspector_title.text = "The brass forge"
			inspector_copy.text = "Spend gold on power, protection, or a second chance. The stone guard needs a sharper blade.\nStand next to the forge to trade."
			inspector_action.hide()
			for offer: Dictionary in info.shop.offers:
				var caption: String = "+%d %s  /  %d GOLD" % [int(offer.amount), "HP" if offer.kind == "potion" else str(offer.kind).to_upper(), int(offer.cost)]
				var purchase: Button = _button(shop_box, caption, _buy.bind(str(offer.id)))
				var distance: int = absi(int(cell[0])-int(rules.state.pos[0])) + absi(int(cell[1])-int(rules.state.pos[1]))
				purchase.disabled = distance > 1 or int(rules.state.gold) < int(offer.cost) or int(rules.state.purchases.get(str(item.id)+"/"+str(offer.id),0)) >= int(offer.get("limit",1))
		"door":
			inspector_title.text = "%s gate" % str(item.type).capitalize()
			inspector_copy.text = "Opening this gate spends one matching key. Once open, it stays open across all floor changes."
			inspector_cost.text = "1 %s KEY" % str(item.type).to_upper()
		"stairs":
			inspector_title.text = "The stairwell"
			inspector_copy.text = "Ascend or return to a previous floor. Every resource, enemy, and door keeps its state.\n\nPress E while standing here to travel again."
		"key":
			inspector_title.text = "%s key" % str(item.type).capitalize()
			inspector_copy.text = "Choose which gate deserves this key. You can inspect every room before committing."
		"potion", "atk", "def", "gold":
			inspector_title.text = "A useful find"
			inspector_copy.text = "Gain +%d %s. The resource is collected once." % [int(item.get("amount",1)), "HP" if kind == "potion" else kind.to_upper()]
		_:
			inspector_title.text = "Quiet stone"
			inspector_copy.text = "Click Approach to walk here through clear tiles. Movement stops before another encounter."


func _hovered(cell: Array) -> void:
	if started and not paused and selected.is_empty():
		_inspect(cell)


func _cell_clicked(cell: Array) -> void:
	if not started or paused:
		return
	selected = cell.duplicate()
	world.set_hover(cell)
	_inspect(cell)
	var pos: Array = rules.state.pos
	if absi(int(cell[0]) - int(pos[0])) + absi(int(cell[1]) - int(pos[1])) == 1:
		_apply(rules.interact(cell))


func _approach_selected() -> void:
	if selected.is_empty() or paused:
		return
	var path: Array = _safe_path(selected)
	if path.is_empty():
		_message("No clear route. Approach a neighboring tile first.")
		return
	for cell: Array in path:
		var result: Dictionary = rules.interact(cell)
		if not bool(result.ok) or str(result.action) in ["stairs", "combat", "victory"]:
			_apply(result)
			return
	_update()


func _safe_path(target: Array) -> Array:
	var start: Vector2i = Vector2i(int(rules.state.pos[0]), int(rules.state.pos[1]))
	var end: Vector2i = Vector2i(int(target[0]),int(target[1]))
	var queue: Array[Vector2i] = [start]
	var previous: Dictionary = {start: start}
	while not queue.is_empty():
		var current: Vector2i = queue.pop_front()
		if current == end:
			var result: Array = []
			while current != start:
				result.push_front([current.x,current.y])
				current = previous[current]
			return result
		for delta: Vector2i in [Vector2i.UP,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]:
			var next: Vector2i = current + delta
			var cell: Array = [next.x,next.y]
			if previous.has(next) or not rules.walkable(cell):
				continue
			var obj: Dictionary = rules.object_at(cell)
			if not obj.is_empty() and next != end:
				continue
			previous[next] = current
			queue.append(next)
	return []


func _step(dx: int, dy: int) -> void:
	if started and not paused:
		selected = [int(rules.state.pos[0])+dx,int(rules.state.pos[1])+dy]
		_apply(rules.move(dx,dy))


func _apply(result: Dictionary) -> void:
	if str(result.get("action", "")) in ["combat", "victory"]:
		_message("Encounter cleared: -%d HP. The way remains open." % int(result.combat.damage))
	elif str(result.get("action", "")) == "purchase":
		_message("Trade completed. Resources and remaining stock updated.")
	elif str(result.get("action", "")) == "stairs":
		_message("Floor changed. Previous gates, encounters and resources are preserved.")
	elif not str(result.get("message", "")).is_empty():
		_message(str(result.message))
	_update()
	if bool(rules.state.won):
		_show_modal("victory")


func _buy(choice: String) -> void:
	_apply(rules.buy(choice))


func _save() -> void:
	if not rules.save_game():
		_message("Save failed. Your current expedition is still open.")
	elif OS.has_feature("web") and not OS.is_userfs_persistent():
		_message("Session-only save: browser storage is unavailable. Reload will lose it.")
	elif OS.has_feature("web"):
		_message("Save written. Keep browser site storage enabled to retain it across reloads.")
	else:
		_message("Expedition saved on this device.")


func _load(path: String = Rules.SAVE_PATH) -> void:
	if rules.load_game(path):
		started = true
		paused = false
		overlay.hide()
		selected = []
		_update()
		_message("Saved expedition restored.")
		if bool(rules.state.won):
			_show_modal("victory")
	else:
		_message("No compatible save could be loaded. Current progress is unchanged.")


func _message(text: String) -> void:
	toast.text = text
	message_time = 5.0


func _show_modal(kind: String) -> void:
	modal_kind = kind
	paused = true
	overlay.show()
	for child: Node in overlay_box.get_children():
		child.free()
	overlay_box.add_child(_label("STAIRKEEP  /  WORKING TITLE", 14, GOLD))
	var title: String = {"title":"Think before you climb.","pause":"A moment by the lantern.","restart":"Begin a new expedition?","victory":"The beacon burns again."}.get(kind,"Stairkeep")
	overlay_box.add_child(_label(title, 30, CREAM))
	var copy: String = "Three floors. Fixed enemies. One life to budget.\nInspect combat costs, choose your keys, and rebuild the beacon.\n\nMove with WASD or the compass. Click an object to inspect.\nApproach walks through clear tiles. E uses the stair underfoot."
	if kind == "restart":
		copy = "This resets the current expedition. Your manual save remains\navailable until you save over it."
	elif kind == "pause":
		copy = "Save before leaving. Your progress belongs to this device.\nA gate costs one matching key; an opened gate stays open.\nCombat previews and actual damage use the same formula."
	elif kind == "victory":
		copy = "You restored the beacon with %d HP and %d gold.\nDifferent keys and forge choices lead to different routes.\n\nThis is the three-floor slice; the 21-floor campaign is in production." % [int(rules.state.hp), int(rules.state.gold)]
	overlay_box.add_child(_label(copy, 17, MUTED))
	var first: Button
	if kind in ["title","restart","victory"]:
		first = _button(overlay_box, "Begin expedition" if kind == "title" else "New expedition", _begin)
	if kind in ["pause","restart"]:
		var resume := _button(overlay_box, "Return to the tower", _resume)
		if first == null:
			first = resume
	if kind in ["title","pause"]:
		_button(overlay_box, "Continue saved expedition", _load)
	if kind == "pause":
		_button(overlay_box, "Save expedition", _save)
		_button(overlay_box, "New expedition", func(): _show_modal("restart"))
	first.call_deferred("grab_focus")


func _begin() -> void:
	rules.reset()
	started = true
	paused = false
	selected = []
	overlay.hide()
	_update()
	_message("Find the yellow key, then decide which gate to open.")


func _resume() -> void:
	paused = false
	overlay.hide()


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	if event.keycode == KEY_ESCAPE:
		if paused and started and modal_kind != "victory":
			_resume()
		elif started:
			_show_modal("pause")
		return
	if paused or not started:
		return
	match event.physical_keycode:
		KEY_W, KEY_UP: _step(0,-1)
		KEY_A, KEY_LEFT: _step(-1,0)
		KEY_S, KEY_DOWN: _step(0,1)
		KEY_D, KEY_RIGHT: _step(1,0)
		KEY_E:
			var item: Dictionary = rules.object_at(rules.state.pos)
			if item.get("kind", "") == "stairs":
				_apply(rules.use_stairs())
	get_viewport().set_input_as_handled()


func _layout_test() -> void:
	_begin()
	await get_tree().process_frame
	await get_tree().process_frame
	var checks: Array = []
	var passed := true
	for floor_index: int in range(rules.data.floors.size()):
		rules.state.floor = floor_index
		world.refresh()
		for item: Dictionary in rules.floor_data().objects:
			var cell: Array = item.pos
			var actual: Array = world.cell_at(world.projected_cell_center(cell))
			var match_cell: bool = actual.size() == 2 and int(actual[0]) == int(cell[0]) and int(actual[1]) == int(cell[1])
			passed = passed and match_cell
			checks.append({"floor":floor_index+1,"cell":cell,"actual":actual,"roundtrip":match_cell})
			if item.kind == "shop":
				_inspect(cell)
	await get_tree().process_frame
	await get_tree().process_frame
	var rectangles: Dictionary = {}
	for key: String in layout_nodes:
		var rect: Rect2 = layout_nodes[key].get_global_rect()
		var fits: bool = get_viewport_rect().encloses(rect)
		passed = passed and fits
		rectangles[key] = {"position":[rect.position.x,rect.position.y],"size":[rect.size.x,rect.size.y],"within_viewport":fits}
	var inspector_rect: Rect2 = layout_nodes.inspector.get_global_rect()
	var compass_rect: Rect2 = layout_nodes.compass.get_global_rect()
	var overlap: bool = inspector_rect.intersects(compass_rect)
	passed = passed and not overlap
	# This valid save fixture verifies UI restoration, not a played victory.
	rules.state.won = true
	rules.state.cleared.append("f3_warden")
	var win_save_path := "user://stairkeep-ui-victory-test.json"
	var saved: bool = rules.save_game(win_save_path)
	_load(win_save_path)
	var victory_restored: bool = saved and paused and overlay.visible and modal_kind == "victory"
	DirAccess.remove_absolute(win_save_path)
	passed = passed and victory_restored
	print(JSON.stringify({"suite":"native_scene_layout","viewport":[get_viewport_rect().size.x,get_viewport_rect().size.y],"projection":checks,"settled_controls":rectangles,"inspector_compass_overlap":overlap,"victory_save_ui_restored":victory_restored,"theme_assigned":ui.theme != null,"native_controls":true,"passed":passed,"scope":"Headless scene geometry after deferred Container sorting and valid victory-save UI restoration; state selected by harness. No rendered pixels or real input.","visual_review":"not-tested"}))
	get_tree().quit(0 if passed else 1)
