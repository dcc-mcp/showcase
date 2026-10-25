extends Node2D
## Presentation only. All world changes, combat and persistence delegate to
## the separate fifty runtime/save owners. This scene is not the default entry.

const Runtime = preload("res://fifty/scripts/runtime.gd")
const Saves = preload("res://fifty/scripts/save.gd")
const World = preload("res://fifty/view/world.gd")
const Icon = preload("res://scripts/ui_icon.gd")
const INK := Color("101f2c")
const GOLD := Color("e8c48a")
const CYAN := Color("7bcac8")
const CREAM := Color("f2e9d8")
const MUTED := Color("91a6af")
const DANGER := Color("e5968d")
const SLOT := "first-chapter"
const CLASSIC := "classic_restart"
const PRACTICE := "practice_checkpoint"
const AREAS := ["RETURNING TIDE HALL", "ROPE BRIDGE STORE", "ECHO RIGGING ROOM", "TWIN COURT SLUICE", "SALT SEALED ARCHIVE", "TIDAL SPIRAL", "LIGHTKEEPER'S GALLERY", "THREE PATH RESERVOIR", "FOUR WING CALIBRATION", "UNLIT SIGNAL PLATFORM"]

var rules = Runtime.new()
var world
var ui: Control
var world_host: Control
var mode_label: Label
var floor_label: Label
var availability_label: Label
var toast: Label
var stats: Dictionary = {}
var tabs: TabContainer
var inspect_title: Label
var inspect_copy: Label
var inspect_cost: Label
var approach_button: Button
var offers_box: VBoxContainer
var bestiary_list: ItemList
var bestiary_copy: Label
var journal_box: VBoxContainer
var overlay: Control
var overlay_box: VBoxContainer
var modal_feedback: Label
var start_button: Button
var mode_load_button: Button
var seed_input: LineEdit
var header_actions: Dictionary = {}
var selected: Array = []
var selected_mode := ""
var active_mode := ""
var selected_seed := 20261025
var started := false
var content_ready := false
var modal_kind := ""
var _last_slice_notice := false
var _enemy_ids: Array[String] = []


func _ready() -> void:
	world = World.new()
	world.name = "IsometricWorld"
	add_child(world)
	world.cell_clicked.connect(_cell_clicked)
	world.cell_hovered.connect(_hovered)
	_build_ui()
	var loaded: Dictionary = rules.load_content()
	content_ready = bool(loaded.get("ok", false))
	if content_ready:
		_show_modes()
	else:
		_open_modal("unavailable", "The chapter could not open.", "The current tower is unchanged. This preview needs its first chapter content before play.")
	get_viewport().size_changed.connect(_schedule_fit)
	_schedule_fit()


func _style(background: Color, border: Color = Color("314653")) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = background
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	style.content_margin_left = 14
	style.content_margin_right = 14
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	return style


func _label(text: String, point_size: int = 16, color: Color = CREAM, wrap: bool = false) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", point_size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if wrap:
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return label


func _button(parent: Node, caption: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = caption
	button.custom_minimum_size.y = 44
	button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	button.pressed.connect(callback)
	parent.add_child(button)
	return button


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Presentation"
	add_child(layer)
	ui = Control.new()
	ui.name = "UI"
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(ui)
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var theme := Theme.new()
	theme.default_font_size = 16
	theme.set_color("font_color", "Label", CREAM)
	theme.set_color("font_color", "Button", CREAM)
	theme.set_color("font_hover_color", "Button", GOLD)
	theme.set_color("font_disabled_color", "Button", Color("73838c"))
	theme.set_stylebox("panel", "PanelContainer", _style(INK))
	for state: String in ["normal", "hover", "pressed", "disabled"]:
		var fill: Color = {"normal":Color("182f3d"), "hover":Color("244251"), "pressed":Color("30515b"), "disabled":Color("111f29")}[state]
		theme.set_stylebox(state, "Button", _style(fill, GOLD if state == "hover" else Color("314653")))
	theme.set_stylebox("focus", "Button", _style(Color(0, 0, 0, 0), CYAN))
	ui.theme = theme
	var margin := MarginContainer.new()
	margin.name = "Screen"
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(margin)
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for edge: String in ["left", "right"]:
		margin.add_theme_constant_override("margin_" + edge, 20)
	for edge: String in ["top", "bottom"]:
		margin.add_theme_constant_override("margin_" + edge, 16)
	var screen := VBoxContainer.new()
	screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	screen.add_theme_constant_override("separation", 8)
	margin.add_child(screen)
	var heading := HBoxContainer.new()
	screen.add_child(heading)
	var brand := VBoxContainer.new()
	brand.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.add_child(brand)
	brand.add_child(_label("S T A I R K E E P", 27, GOLD))
	brand.add_child(_label("TIDE-MARK SIGNAL  /  FIRST CHAPTER", 12, MUTED))
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 7)
	heading.add_child(actions)
	header_actions.save = _button(actions, "Save", _save_slot)
	header_actions.load = _button(actions, "Load", _load_slot)
	header_actions.restart = _button(actions, "Restart / return", _show_recovery)
	header_actions.mode = _button(actions, "Mode", _show_modes)
	mode_label = _label("Choose a mode to begin.  •  Working title, may change.", 14, CYAN)
	screen.add_child(mode_label)
	var status := HBoxContainer.new()
	status.add_theme_constant_override("separation", 8)
	screen.add_child(status)
	for key: String in ["hp", "atk", "def", "gold", "yellow", "blue"]:
		var panel := PanelContainer.new()
		panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		status.add_child(panel)
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 7)
		panel.add_child(row)
		var icon = Icon.new()
		icon.kind = key
		icon.ink = CYAN if key == "blue" else GOLD
		row.add_child(icon)
		var value := _label("—", 17, GOLD)
		row.add_child(value)
		stats[key] = value
	var body := HBoxContainer.new()
	body.name = "Body"
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 16)
	screen.add_child(body)
	var world_column := VBoxContainer.new()
	world_column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	world_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	world_column.custom_minimum_size.x = 500
	body.add_child(world_column)
	floor_label = _label("FIRST CHAPTER  /  FLOORS 1–10 AVAILABLE", 16, GOLD)
	world_column.add_child(floor_label)
	world_host = Control.new()
	world_host.name = "WorldViewport"
	world_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	world_host.custom_minimum_size.y = 300
	world_host.size_flags_vertical = Control.SIZE_EXPAND_FILL
	world_column.add_child(world_host)
	world_host.resized.connect(_schedule_fit)
	availability_label = _label("50 floors planned  •  Floors 11–50 are not yet built", 14, MUTED)
	world_column.add_child(availability_label)
	var compass := HBoxContainer.new()
	compass.add_theme_constant_override("separation", 8)
	world_column.add_child(compass)
	for entry: Array in [["NW",-1,0],["NE",0,-1],["SW",0,1],["SE",1,0]]:
		_button(compass, str(entry[0]), _step.bind(int(entry[1]), int(entry[2])))
	_button(compass, "Use stairs / E", _use_stairs)
	var side := PanelContainer.new()
	side.name = "FieldNotebook"
	side.custom_minimum_size.x = 350
	body.add_child(side)
	tabs = TabContainer.new()
	tabs.custom_minimum_size.x = 322
	side.add_child(tabs)
	var inspect_page := VBoxContainer.new()
	inspect_page.name = "Inspect"
	inspect_page.add_theme_constant_override("separation", 10)
	tabs.add_child(inspect_page)
	inspect_title = _label("The next step", 24, GOLD, true)
	inspect_page.add_child(inspect_title)
	inspect_copy = _label("Choose a mode, then inspect the tower.", 16, CREAM, true)
	inspect_copy.custom_minimum_size = Vector2(0, 132)
	inspect_page.add_child(inspect_copy)
	inspect_cost = _label("", 22, CYAN, true)
	inspect_page.add_child(inspect_cost)
	approach_button = _button(inspect_page, "Approach / interact", _approach)
	var offer_scroll := ScrollContainer.new()
	offer_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	offer_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	inspect_page.add_child(offer_scroll)
	offers_box = VBoxContainer.new()
	offers_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	offer_scroll.add_child(offers_box)
	var bestiary := VBoxContainer.new()
	bestiary.name = "Bestiary"
	tabs.add_child(bestiary)
	bestiary.add_child(_label("Measure the cost first.", 20, GOLD, true))
	bestiary_list = ItemList.new()
	bestiary_list.custom_minimum_size.y = 150
	bestiary_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	bestiary_list.item_selected.connect(_bestiary_selected)
	bestiary.add_child(bestiary_list)
	bestiary_copy = _label("Enemy costs use your current equipment. You strike first.", 16, CREAM, true)
	bestiary_copy.custom_minimum_size.y = 145
	bestiary.add_child(bestiary_copy)
	var journal_scroll := ScrollContainer.new()
	journal_scroll.name = "Clues"
	journal_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	tabs.add_child(journal_scroll)
	journal_box = VBoxContainer.new()
	journal_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	journal_box.add_theme_constant_override("separation", 12)
	journal_scroll.add_child(journal_box)
	toast = _label("Select Classic or Practice before entering the tower.", 16, CREAM, true)
	toast.custom_minimum_size.y = 37
	screen.add_child(toast)
	screen.add_child(_label("WASD / arrows: move  •  Click: inspect  •  E: stairs  •  Esc: pause", 13, MUTED))
	overlay = Control.new()
	overlay.name = "Modal"
	overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	ui.add_child(overlay)
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var shade := ColorRect.new()
	shade.color = Color(0.015, 0.025, 0.045, 0.94)
	overlay.add_child(shade)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var center := CenterContainer.new()
	overlay.add_child(center)
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var card := PanelContainer.new()
	card.custom_minimum_size.x = 620
	center.add_child(card)
	overlay_box = VBoxContainer.new()
	overlay_box.add_theme_constant_override("separation", 12)
	card.add_child(overlay_box)
	_set_actions_enabled(false)


func _schedule_fit() -> void:
	call_deferred("_fit_world")


func _fit_world() -> void:
	if not is_inside_tree():
		return
	await get_tree().process_frame
	await get_tree().process_frame
	if is_instance_valid(world_host) and started:
		world.fit_rect(world_host.get_global_rect().grow(-10))


func _set_actions_enabled(enabled: bool) -> void:
	for key: String in ["save", "load", "restart"]:
		header_actions[key].disabled = not enabled
	header_actions.load.disabled = not enabled or _classic_failed()
	approach_button.disabled = not enabled


func _open_modal(kind: String, title: String, copy: String) -> void:
	modal_kind = kind
	world.set_process_unhandled_input(false)
	overlay.show()
	for child: Node in overlay_box.get_children():
		child.free()
	overlay_box.add_child(_label("STAIRKEEP  /  TIDE-MARK SIGNAL", 13, GOLD))
	overlay_box.add_child(_label(title, 27, CREAM, true))
	var body := _label(copy, 16, MUTED, true)
	body.custom_minimum_size.x = 570
	overlay_box.add_child(body)
	modal_feedback = _label("", 15, CYAN, true)
	modal_feedback.hide()
	overlay_box.add_child(modal_feedback)


func _close_modal() -> void:
	modal_kind = ""
	overlay.hide()
	world.set_process_unhandled_input(started)
	# Return keyboard input to the world; Tab can re-enter the native HUD.
	get_viewport().gui_release_focus()


func _show_modes() -> void:
	if not content_ready:
		return
	selected_mode = ""
	_open_modal("mode", "Choose how you want to climb.", "First chapter: floors 1–10. Fifty floors are planned; 11–50 are not yet built.\nChoose a mode yourself. Your saved slots stay separate.")
	overlay_box.add_child(_label("Classic's restart rule applies to the current open session. An existing manual save may still resume after closing and reopening.",14,MUTED,true))
	var group := ButtonGroup.new()
	group.allow_unpress = false
	for entry: Array in [[CLASSIC,"CLASSIC  ·  A new tower after a lost run"],[PRACTICE,"PRACTICE  ·  Return to earned chapter checkpoints"]]:
		var choice := _button(overlay_box, str(entry[1]), _select_mode.bind(str(entry[0])))
		choice.toggle_mode = true
		choice.button_group = group
		choice.name = "ClassicChoice" if entry[0] == CLASSIC else "PracticeChoice"
		overlay_box.add_child(_label("A restart loses the whole current tower and uses a new seed." if entry[0] == CLASSIC else "Returning loses everything since that checkpoint, including later finds and purchases.", 14, MUTED, true))
	seed_input = LineEdit.new()
	seed_input.name = "TowerSeed"
	seed_input.placeholder_text = "Tower seed (1 to 4294967295)"
	seed_input.text = str(selected_seed)
	seed_input.custom_minimum_size.y = 40
	seed_input.text_changed.connect(func(_text: String): _refresh_mode_buttons())
	overlay_box.add_child(seed_input)
	start_button = _button(overlay_box, "Enter first chapter", _begin)
	start_button.name = "StartChapter"
	start_button.disabled = true
	mode_load_button = _button(overlay_box, "Load selected mode's saved slot", _load_slot)
	mode_load_button.disabled = true
	if started:
		overlay_box.add_child(_label("To restart or return within your current mode, use Restart / return. Selecting the other mode starts a separate new tower after confirmation.",14,MUTED,true))
		if bool(_snapshot().get("failed",false)):
			_button(overlay_box, "Return to recovery choices", _show_recovery)
		else:
			_button(overlay_box, "Keep playing this tower", _close_modal)
	else:
		overlay_box.get_node("ClassicChoice").call_deferred("grab_focus")


func _select_mode(mode: String) -> void:
	selected_mode = mode
	_refresh_mode_buttons()


func _seed_value() -> int:
	if not is_instance_valid(seed_input) or not seed_input.text.is_valid_int():
		return -1
	var value: int = int(seed_input.text)
	return value if value >= 1 and value <= 4294967295 else -1


func _refresh_mode_buttons() -> void:
	var valid: bool = selected_mode in [CLASSIC, PRACTICE] and _seed_value() >= 1
	start_button.disabled = not valid or (started and selected_mode == active_mode)
	start_button.tooltip_text = "Use Restart / return to recover within the current mode." if started and selected_mode == active_mode else "Enter this mode's first chapter."
	mode_load_button.disabled = not valid or (started and selected_mode != active_mode)
	if selected_mode == CLASSIC and _classic_failed():
		mode_load_button.disabled = true
	mode_load_button.tooltip_text = "Start the selected mode first to load its own slot." if started and selected_mode != active_mode else "Load this mode's first-chapter save."
	if selected_mode == CLASSIC and _classic_failed():
		mode_load_button.tooltip_text = "This Classic run has ended. Restart it with a new tower seed."


func _begin() -> void:
	if selected_mode not in [CLASSIC, PRACTICE] or _seed_value() < 1:
		return
	if started and selected_mode == active_mode:
		_message("Use Restart / return for your current mode.")
		return
	var mode: String = selected_mode
	var seed: int = _seed_value()
	if started:
		_confirm("Replace this tower?", "This starts from floor 1 in the selected mode. Current tower progress is replaced. Your manual save stays until you save over it.", _do_begin.bind(mode, seed))
	else:
		_do_begin(mode, seed)


func _do_begin(mode: String, seed: int) -> void:
	# An active runtime cannot silently change mode. Only an explicitly confirmed
	# new-tower action constructs a replacement, leaving the old object untouched
	# if content validation or mode selection fails.
	var candidate = Runtime.new()
	var loaded: Dictionary = candidate.load_content()
	if not bool(loaded.get("ok",false)):
		_message("The chapter could not open. Your current tower is unchanged.")
		return
	var result: Dictionary = candidate.choose_mode(mode, seed)
	if not bool(result.get("ok", false)):
		_message(str(result.get("message", "The chapter could not start.")))
		return
	rules = candidate
	active_mode = mode
	selected_mode = mode
	selected_seed = seed
	started = true
	selected = []
	_last_slice_notice = false
	world.configure(rules)
	_set_actions_enabled(true)
	_close_modal()
	_refresh()
	_message("Find the mapmaker. Look for clues worth bringing back.")


func _snapshot() -> Dictionary:
	return rules.export_snapshot() if started else {}


func _refresh() -> void:
	if not started:
		return
	var state: Dictionary = rules.state
	var snap: Dictionary = _snapshot()
	for key: String in ["hp", "atk", "def", "gold"]:
		stats[key].text = "%s  %d" % [key.to_upper(), int(state.get(key, 0))]
	var failure_view: Dictionary = _failure_presentation(snap)
	stats.hp.add_theme_color_override("font_color", GOLD)
	if failure_view.get("kind","") == "combat_death":
		stats.hp.text = "HP 0 / DEFEATED"
		stats.hp.add_theme_color_override("font_color", DANGER)
	elif failure_view.get("kind","") == "abandoned":
		stats.hp.text = "HP %d / RUN ENDED" % int(state.get("hp",0))
		stats.hp.add_theme_color_override("font_color", MUTED)
	for key: String in ["yellow", "blue"]:
		stats[key].text = "%s  %d" % ["Y KEY" if key == "yellow" else "B KEY", int(state.get("keys", {}).get(key, 0))]
	var floor_index: int = int(state.get("floor", 0))
	floor_label.text = "%02d / 10    %s" % [floor_index + 1, AREAS[clampi(floor_index, 0, 9)]]
	mode_label.text = "%s  •  First chapter preview  •  Working title, may change" % ("CLASSIC · full restart" if active_mode == CLASSIC else "PRACTICE · chapter return")
	availability_label.text = "Chapter / slice complete  •  Floors 11–50 are not yet built" if bool(snap.get("slice_complete",false)) else "10 floors available of 50 planned  •  Floors 11–50 are not yet built"
	world.refresh()
	header_actions.load.disabled = _classic_failed()
	_inspect(selected)
	_refresh_bestiary()
	_refresh_journal(snap)
	_schedule_fit()
	if not bool(snap.get("slice_complete",false)):
		_last_slice_notice = false
	if bool(snap.get("failed", false)):
		if modal_kind in ["", "slice"]:
			_show_recovery()
	elif bool(snap.get("slice_complete", false)) and not _last_slice_notice:
		_last_slice_notice = true
		_open_modal("slice", "The first signal is lit.", "Chapter / slice complete. You can still return to earlier floors and save this tower.\nFloors 11–50 are not yet built. This is not the end of the planned tower.")
		_button(overlay_box, "Return to the chapter", _close_modal).call_deferred("grab_focus")
		_button(overlay_box, "Save this tower", _save_slot)


func _clear_children(parent: Node) -> void:
	for child: Node in parent.get_children():
		child.free()


func _inspect(cell: Array) -> void:
	_clear_children(offers_box)
	approach_button.hide()
	inspect_cost.text = ""
	inspect_cost.add_theme_color_override("font_color", CYAN)
	if cell.size() != 2:
		inspect_title.text = "Choose your route"
		inspect_copy.text = "Inspect enemies before spending health. One matching key opens one door. Opened gates and collected resources stay changed when you return."
		return
	var info: Dictionary = rules.inspect(cell)
	var item: Dictionary = info.get("object", {})
	var kind: String = str(item.get("kind", ""))
	approach_button.show()
	approach_button.disabled = not bool(info.get("walkable", false))
	inspect_title.text = str(item.get("name_en", str(item.get("type", kind)).replace("_", " ").capitalize()))
	inspect_copy.text = "Approach along clear tiles. Movement stops at encounters and stairs."
	match kind:
		"enemy":
			inspect_title.text = _enemy_label(str(item.get("type","")))
			var fight: Dictionary = info.get("combat", {})
			var enemy: Dictionary = info.get("enemy", rules.data.get("enemies", {}).get(str(item.get("type", "")), {}))
			inspect_copy.text = "HP %d  ·  ATK %d  ·  DEF %d\nReward: %d gold\n\n%s" % [int(enemy.get("hp",0)), int(enemy.get("atk",0)), int(enemy.get("def",0)), int(enemy.get("gold",0)), "You can survive this encounter." if bool(fight.get("win",false)) else "You cannot win this encounter with your current resources."]
			inspect_cost.text = "%d HP cost" % int(fight.get("damage",0)) if int(fight.get("damage",-1)) >= 0 else "Cannot break this armor"
			inspect_cost.add_theme_color_override("font_color", CYAN if bool(fight.get("win",false)) else DANGER)
			approach_button.disabled = not bool(fight.get("win",false))
		"door":
			inspect_copy.text = "Opening spends one matching key. Once open, the gate stays open when you return."
			inspect_cost.text = "1 %s KEY" % str(item.get("type","yellow")).to_upper()
		"stairs":
			inspect_title.text = "The stairwell"
			inspect_copy.text = "Travel between the available chapter floors. Your gates, encounters and supplies keep their state. Press E while standing here."
		"boundary":
			inspect_title.text = "Higher floors are not yet built"
			inspect_copy.text = "This chapter ends on floor 10. Floors 11–50 are planned and cannot be entered in this preview. You can revisit and save the available chapter."
			approach_button.disabled = true
		"npc":
			inspect_title.text = "The mapmaker" if int(rules.state.floor) == 0 else "The lightkeeper"
			inspect_copy.text = "Talk from the neighboring tile. A clue found higher in the tower may be worth bringing back."
			var npc_events: Array = info.get("available_events",[])
			if not npc_events.is_empty():
				inspect_copy.text = str(npc_events[0].get("text",inspect_copy.text))
			_show_event_effects(npc_events)
		"event":
			inspect_title.text = "A chapter clue" if int(rules.state.floor) < 9 else "The unlit signal"
			inspect_copy.text = "Approach to read or use this place. Its requirements and one-time rewards belong to this tower's progress."
			var place_events: Array = info.get("available_events",[])
			if not place_events.is_empty():
				inspect_copy.text = str(place_events[0].get("text",inspect_copy.text))
			_show_event_effects(place_events)
		"shop":
			inspect_title.text = "The tide-road trader"
			inspect_copy.text = "Stand beside the trader. Stock is limited; compare the route ahead before spending."
			approach_button.hide()
			var shop: Dictionary = info.get("shop", {})
			for offer: Dictionary in shop.get("offers", []):
				var amount: int = int(offer.get("amount",0))
				var label: String = str(offer.get("name_en", {"edge":"Sharpen blade","ward":"Reinforce armor","flask":"Sealed water"}.get(str(offer.get("id","")),"Trade")))
				var used: int = int(rules.state.get("purchases",{}).get(str(item.get("id",""))+"/"+str(offer.get("id","")),0))
				var remaining: int = maxi(0,int(offer.get("limit",1))-used)
				var resource: String = "HP" if offer.get("kind","") == "potion" else str(offer.get("kind","resource")).to_upper()
				var buy_button := _button(offers_box, "%s  +%d %s\n%d gold  ·  %d left" % [label,amount,resource,int(offer.get("cost",0)),remaining], _buy.bind(str(offer.get("id",""))))
				buy_button.tooltip_text = "+%d %s · %d remaining" % [amount,str(offer.get("kind","resource")),remaining]
				var distance: int = absi(int(cell[0])-int(rules.state.pos[0]))+absi(int(cell[1])-int(rules.state.pos[1]))
				buy_button.disabled = distance > 1 or remaining == 0 or int(rules.state.gold) < int(offer.get("cost",0))
		"key":
			var color: String = str(item["type"]).to_upper()
			inspect_title.text = "%s key" % str(item["type"]).capitalize()
			inspect_cost.text = "GAIN +%d %s KEY" % [int(item["amount"]),color]
			inspect_copy.text = "Collect this matching-color key once. An opened gate stays open when you return."
		"potion", "atk", "def", "gold":
			var resource: String = "HP" if kind == "potion" else kind.to_upper()
			inspect_cost.text = "GAIN +%d %s" % [int(item["amount"]),resource]
			inspect_copy.text = "A one-time find. Returning here will preserve whether you collected it."
		_:
			inspect_title.text = "Quiet stone"


func _show_event_effects(available: Array) -> void:
	if available.is_empty():
		inspect_cost.text = "No unclaimed interaction is available now."
		inspect_cost.add_theme_color_override("font_color", MUTED)
		approach_button.disabled = true
		return
	# The runtime executes the first eligible event, in authored order. Show only
	# that event's typed finite grants; do not add the other eligible branches.
	inspect_cost.text = _event_effects_text(available[0].get("effects",[]))
	inspect_copy.text += "\n\nThis interaction can be claimed once."


func _event_effects_text(effects: Array) -> String:
	var rewards := PackedStringArray()
	for effect: Dictionary in effects:
		match str(effect.get("kind","")):
			"grant":
				rewards.append("+%d %s" % [int(effect["amount"]),str(effect["stat"]).to_upper()])
			"grant_key":
				rewards.append("+%d %s KEY" % [int(effect["amount"]),str(effect["color"]).to_upper()])
	return "GAIN  " + "  /  ".join(rewards) if not rewards.is_empty() else "One-time chapter event"


func _refresh_bestiary() -> void:
	var previous: int = bestiary_list.get_selected_items()[0] if bestiary_list.is_anything_selected() else -1
	bestiary_list.clear()
	_enemy_ids.clear()
	var enemies: Dictionary = rules.data.get("enemies", {})
	for id: String in enemies:
		_enemy_ids.append(id)
		bestiary_list.add_item(_enemy_label(id))
	if not _enemy_ids.is_empty():
		var index: int = clampi(previous, 0, _enemy_ids.size()-1)
		bestiary_list.select(index)
		_bestiary_selected(index)


func _enemy_label(id: String) -> String:
	var enemy: Dictionary = rules.data.get("enemies",{}).get(id,{})
	if enemy.has("name_en"):
		return str(enemy.name_en)
	var words: String = id
	if id.length() > 4 and id.left(1) == "f" and id.substr(1,2).is_valid_int() and id.substr(3,1) == "_":
		words = id.substr(4)
	return words.replace("_"," ").capitalize()


func _bestiary_selected(index: int) -> void:
	if index < 0 or index >= _enemy_ids.size():
		return
	var enemy: Dictionary = rules.data.get("enemies", {})[_enemy_ids[index]]
	var fight: Dictionary = rules.combat(enemy)
	bestiary_copy.text = "HP %d  ·  ATK %d  ·  DEF %d\nReward: %d gold\n\n%s\n\nCosts reflect your current equipment. You strike first." % [int(enemy.get("hp",0)),int(enemy.get("atk",0)),int(enemy.get("def",0)),int(enemy.get("gold",0)),"Cost: %d HP" % int(fight.get("damage",0)) if bool(fight.get("win",false)) else "Cannot win with your current resources."]


func _refresh_journal(snap: Dictionary) -> void:
	_clear_children(journal_box)
	journal_box.add_child(_label("Clues & return visits", 20, GOLD, true))
	var flags: Dictionary = snap.get("flags",{})
	var copper_status: String = "Completed" if bool(flags.get("copper_redeemed",false)) else ("Return to F1" if bool(flags.get("copper_found",false)) else "Find the tag on F3")
	var keeper_status: String = "Completed" if bool(flags.get("keeper_supplied",false)) else ("Visit the lightkeeper on F7" if bool(flags.get("archive_read",false)) else "Read the sealed archive on F5")
	journal_box.add_child(_label("F3 → F1 · %s\nF5 → F7 · %s" % [copper_status,keeper_status], 16, CREAM, true))
	var events: Array = snap.get("completed_events", [])
	journal_box.add_child(_label("%d chapter moments recorded" % events.size(), 14, CYAN, true))
	var registry: Dictionary = rules.data.get("events", {})
	for event_id: String in events:
		var entry: Dictionary = registry.get(event_id, {})
		var text: String = str(entry.get("text", "A chapter clue or exchange has been recorded."))
		journal_box.add_child(_label("✓ F%d · %s" % [int(entry.get("floor",0)),text], 15, MUTED, true))
	var boundary := Button.new()
	boundary.text = "Floors 11–50 · not yet built"
	boundary.disabled = true
	boundary.custom_minimum_size.y = 44
	journal_box.add_child(boundary)


func _cell_clicked(cell: Array) -> void:
	if not started or modal_kind != "":
		return
	selected = cell.duplicate()
	world.set_hover(selected)
	_inspect(selected)
	tabs.current_tab = 0


func _hovered(cell: Array) -> void:
	if started and modal_kind == "" and selected.is_empty():
		_inspect(cell)


func _safe_path(target: Array) -> Array:
	var origin := Vector2i(int(rules.state.pos[0]), int(rules.state.pos[1]))
	var end := Vector2i(int(target[0]), int(target[1]))
	var queue: Array[Vector2i] = [origin]
	var previous: Dictionary = {origin:origin}
	while not queue.is_empty():
		var current: Vector2i = queue.pop_front()
		if current == end:
			var path: Array = []
			while current != origin:
				path.push_front([current.x,current.y])
				current = previous[current]
			return path
		for delta: Vector2i in [Vector2i.UP,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]:
			var next: Vector2i = current+delta
			var cell: Array = [next.x,next.y]
			if previous.has(next) or not rules.walkable(cell):
				continue
			if next != end and not rules.object_at(cell).is_empty():
				continue
			previous[next] = current
			queue.append(next)
	return []


func _approach() -> void:
	if not started or modal_kind != "" or selected.size() != 2:
		return
	var path: Array = _safe_path(selected)
	if path.is_empty():
		_message("No clear route. Move beside the object first.")
		return
	for cell: Array in path:
		var result: Dictionary = rules.interact(cell)
		if not bool(result.get("ok",false)) or str(result.get("action","")) in ["stairs","combat","event","npc"]:
			_apply(result)
			return
	_refresh()


func _step(dx: int, dy: int) -> void:
	if started and modal_kind == "":
		selected = []
		_apply(rules.move(dx,dy))


func _use_stairs() -> void:
	if started and modal_kind == "":
		selected = []
		_apply(rules.use_stairs())


func _buy(choice: String) -> void:
	if started and modal_kind == "":
		_apply(rules.buy(choice))


func _apply(result: Dictionary) -> void:
	if str(result.get("action","")) == "stairs":
		selected = []
		world.set_hover([])
	_message(str(result.get("message", "The tower remembers your choice.")))
	_refresh()
	if bool(result.get("ok",false)) and str(result.get("action","")) == "event" and not bool(_snapshot().get("slice_complete",false)):
		_open_modal("dialogue","A message in the tower",str(result.get("message","")))
		_button(overlay_box,"Return to the tower",_close_modal).call_deferred("grab_focus")


func _message(text: String) -> void:
	toast.text = text
	if is_instance_valid(modal_feedback) and overlay.visible:
		modal_feedback.text = text
		modal_feedback.show()


func _save_slot() -> void:
	if started:
		var result: Dictionary = Saves.write_slot(rules, SLOT)
		if bool(result.get("ok",false)):
			_message("Tower saved in this mode's first-chapter slot.")
		elif result.get("status","") == "blocked_web_persistence_unvalidated":
			_message("Saving in this browser has not been verified. This tower has not been saved.")
		else:
			_message("The save could not be written. Your current tower is still open.")


func _load_slot() -> void:
	var intended_mode: String = active_mode if started else selected_mode
	if intended_mode == CLASSIC and _classic_failed():
		_message("This Classic run has ended. Start a new Classic tower or explicitly choose another mode.")
		return
	if modal_kind == "mode":
		if selected_mode not in [CLASSIC,PRACTICE] or _seed_value() < 1 or (started and selected_mode != active_mode):
			return
		intended_mode = selected_mode
	if intended_mode not in [CLASSIC,PRACTICE]:
		return
	if started:
		_confirm("Load the saved tower?", "Your current unsaved progress will be replaced by this mode's saved first-chapter tower. Other mode slots stay separate.", _do_load_slot.bind(intended_mode))
	else:
		_do_load_slot(intended_mode)


func _do_load_slot(intended_mode: String) -> void:
	# A fresh candidate must not bypass the failed-session Classic recovery rule.
	if intended_mode == CLASSIC and _classic_failed():
		_message("Loading this Classic mode is unavailable after the run ends in the current session.")
		return
	var candidate = Runtime.new()
	var loaded: Dictionary = candidate.load_content()
	if not bool(loaded.get("ok",false)):
		_message("The chapter could not open. Your current tower is unchanged.")
		return
	var chosen: Dictionary = candidate.choose_mode(intended_mode,selected_seed)
	if not bool(chosen.get("ok",false)):
		_message(str(chosen.get("message","The selected mode could not open.")))
		return
	var result: Dictionary = Saves.load_slot(candidate, SLOT)
	if bool(result.get("ok",false)):
		rules = candidate
		active_mode = intended_mode
		selected_mode = intended_mode
		var accepted_snapshot: Dictionary = rules.export_snapshot()
		selected_seed = str(accepted_snapshot["seed"]).hex_to_int()
		if is_instance_valid(seed_input):
			seed_input.text = str(selected_seed)
		started = true
		selected = []
		_last_slice_notice = false
		world.configure(rules)
		_set_actions_enabled(true)
		_close_modal()
		_refresh()
	if bool(result.get("ok",false)):
		_message("Saved tower restored in the selected mode.")
	elif result.get("status","") == "blocked_web_persistence_unvalidated":
		_message("Loading saved towers in this browser has not been verified. Your current tower is unchanged.")
	else:
		_message("This mode's save is unavailable or incompatible. Your current tower is unchanged.")


func _confirm(title: String, copy: String, callback: Callable) -> void:
	_open_modal("confirm",title,copy)
	_button(overlay_box,"Confirm",callback).call_deferred("grab_focus")
	_button(overlay_box,"Keep this tower",_cancel_confirmation)


func _cancel_confirmation() -> void:
	if bool(_snapshot().get("failed",false)):
		_show_recovery()
	else:
		_close_modal()


func _show_recovery() -> void:
	if not started:
		return
	var snap: Dictionary = _snapshot()
	var failed: bool = bool(snap.get("failed",false))
	var failure_view: Dictionary = _failure_presentation(snap)
	var outcome_copy: String = str(failure_view.get("copy",""))
	if not outcome_copy.is_empty():
		outcome_copy += "\n\n"
	if active_mode == CLASSIC:
		_open_modal("recovery", str(failure_view.get("title","Begin a new tower?")), outcome_copy + "Classic restarts from floor 1 with a new seed. All current tower resources, cleared rooms and choices reset. Loading this mode is unavailable after a run ends in this open session. Your manual save is kept.")
		var next_seed := LineEdit.new()
		next_seed.text = str((selected_seed % 4294967295) + 1)
		next_seed.placeholder_text = "New tower seed"
		next_seed.custom_minimum_size.y = 40
		overlay_box.add_child(next_seed)
		_button(overlay_box,"Restart Classic from floor 1",func():
			if not next_seed.text.is_valid_int():
				return
			var seed: int = int(next_seed.text)
			if seed < 1 or seed > 4294967295:
				return
			var result: Dictionary = rules.restart_classic(seed,true,_failure_id(snap))
			if bool(result.get("ok",false)):
				selected_seed = seed
				selected = []
				_close_modal()
				_refresh()
			_message(str(result.get("message","New tower started.")))
		)
	else:
		_open_modal("recovery",str(failure_view.get("title","Return to a chapter checkpoint?")),outcome_copy + "Practice restores the complete earned checkpoint. Everything gained or spent after it is lost. The same tower seed and its earlier choices remain.")
		var checkpoints: Array = snap.get("checkpoints",[])
		var checkpoint_choice := OptionButton.new()
		checkpoint_choice.custom_minimum_size.y = 44
		overlay_box.add_child(checkpoint_choice)
		for checkpoint: Dictionary in checkpoints:
			var id: String = str(checkpoint.get("id",""))
			if id.is_empty():
				continue
			var caption: String = str(checkpoint.get("label","Return to an earned checkpoint"))
			checkpoint_choice.add_item(caption)
			checkpoint_choice.set_item_metadata(checkpoint_choice.item_count-1,id)
		var return_button := _button(overlay_box,"Return to selected checkpoint",func():
			if checkpoint_choice.selected >= 0:
				_restore_checkpoint(str(checkpoint_choice.get_selected_metadata()),_failure_id(snap))
		)
		return_button.disabled = checkpoint_choice.item_count == 0
		if checkpoints.is_empty():
			overlay_box.add_child(_label("No earned checkpoint is available yet.",16,MUTED,true))
	if not failed:
		_button(overlay_box,"Keep this tower",_close_modal)
	_button(overlay_box,"Choose a mode",_show_modes)


func _failure_id(snap: Dictionary) -> String:
	return str(snap.get("failure",{}).get("failure_id",snap.get("failure_id","")))


func _failure_presentation(snap: Dictionary) -> Dictionary:
	if not bool(snap.get("failed",false)):
		return {}
	var failure: Dictionary = snap.get("failure",{})
	var kind: String = str(failure.get("kind",""))
	if kind == "combat_death":
		var combat: Dictionary = failure.get("combat",{})
		return {"kind":kind,"title":"Defeated.","copy":"You entered the encounter with %d HP. It dealt %s damage and ended the run. Final combat HP: %s." % [int(rules.state.get("hp",0)),str(combat.get("damage","unavailable")),str(failure.get("terminal_hp","unavailable"))]}
	if kind == "abandoned":
		return {"kind":kind,"title":"You ended this run.","copy":"You chose to end this attempt with %d HP remaining." % int(rules.state.get("hp",0))}
	return {"kind":kind,"title":"This run has ended.","copy":"Choose how to continue below."}


func _classic_failed() -> bool:
	return started and active_mode == CLASSIC and bool(_snapshot().get("failed",false))


func _restore_checkpoint(id: String, failure_id: String) -> void:
	var result: Dictionary = rules.restore_checkpoint(id,true,failure_id)
	if bool(result.get("ok",false)):
		selected = []
		_close_modal()
		_refresh()
	_message("Returned to the checkpoint. Later gains and purchases have been undone." if bool(result.get("ok",false)) else str(result.get("message","This checkpoint could not be restored.")))


func _pause() -> void:
	_open_modal("pause","A moment by the lantern.","Save before leaving. You can revisit available floors; their doors, encounters and supplies remain changed.")
	_button(overlay_box,"Return to the tower",_close_modal).call_deferred("grab_focus")
	_button(overlay_box,"Save this tower",_save_slot)
	_button(overlay_box,"Restart / return",_show_recovery)
	_button(overlay_box,"End this run",func(): _confirm("End this run?","Classic will need a new tower. Practice can return to an earned checkpoint. This records that you chose to end the attempt.",_end_run))
	_button(overlay_box,"Choose a mode",_show_modes)


func _end_run() -> void:
	var result: Dictionary = rules.give_up(true)
	if bool(result.get("ok",false)):
		_close_modal()
	_apply(result)


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	if event.physical_keycode == KEY_ESCAPE and started:
		if modal_kind == "":
			_pause()
		elif not bool(_snapshot().get("failed",false)):
			_close_modal()
		get_viewport().set_input_as_handled()
		return
	if not started or modal_kind != "":
		return
	match event.physical_keycode:
		KEY_W,KEY_UP: _step(0,-1)
		KEY_A,KEY_LEFT: _step(-1,0)
		KEY_S,KEY_DOWN: _step(0,1)
		KEY_D,KEY_RIGHT: _step(1,0)
		KEY_E: _use_stairs()
	get_viewport().set_input_as_handled()


func view_status() -> Dictionary:
	return {"started":started,"selected_mode":selected_mode,"active_mode":active_mode,"mode_required":true,"start_disabled":start_button.disabled if is_instance_valid(start_button) else true,"content_ready":content_ready,"authored_floors":10,"target_floors":50,"unmade_floors":[11,50],"modal":modal_kind,"visual_review":"not-tested","real_input":"not-tested"}
