extends Node2D
## Presentation only. All world changes, combat and persistence delegate to
## the separate fifty runtime/save owners. This scene is not the default entry.

const Runtime = preload("res://fifty/scripts/runtime.gd")
const Saves = preload("res://fifty/scripts/save.gd")
const WebSaves = preload("res://fifty/view/web_saves.gd")
const World = preload("res://fifty/view/experience_world.gd")
const ExperienceAudio = preload("res://fifty/view/experience_audio.gd")
const ScreenInput = preload("res://fifty/view/screen_input.gd")
const Keyboard = preload("res://fifty/view/keyboard_controller.gd")
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
const UI_FONT_PATH := "res://assets/experience/fonts/cjk-ui.otf"
const EXPERIENCE_REVISION := "web-save-06"
const WEB_SAVE_NOTICE := "网页存档保留在当前浏览器和地址；请等待“已保存”提示后再关闭。"
const AREAS := ["归潮门厅", "绳桥库", "回声索室", "双庭水闸", "盐封档案", "绕潮盘道", "守灯人廊", "三径蓄池", "四翼校准室", "无火信台"]
const STAT_NAMES := {"hp":"生命", "potion":"生命", "atk":"攻击", "def":"防御", "gold":"金币", "yellow":"黄钥匙", "blue":"蓝钥匙"}

var rules = Runtime.new()
var _web_saves = WebSaves.new()
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
var _busy := false
var _route_running := false
var _last_delta: Dictionary = {}
var _audio: Node
var _muted := false
var sound_button: Button
var view_button: Button
var _overview := false
var _cancel_route := false
var _pause_when_idle := false
var _keyboard = Keyboard.new()
var _keyboard_driver_busy := false
var _keyboard_dispatch_active := false
var _keyboard_context_suspended := true
var _keyboard_last_dispatch_frame := -1
var _confirm_after_frame := -1


func _ready() -> void:
	world = World.new()
	world.name = "IsometricWorld"
	add_child(world)
	world.cell_clicked.connect(_cell_clicked)
	world.cell_hovered.connect(_hovered)
	_setup_audio()
	_build_ui()
	get_viewport().gui_focus_changed.connect(_keyboard_focus_gained)
	get_window().focus_exited.connect(func(): _cancel_keyboard("window_focus"))
	var loaded: Dictionary = rules.load_content()
	content_ready = bool(loaded.get("ok", false))
	if content_ready:
		_show_modes()
	else:
		_open_modal("unavailable", "首章暂时无法打开", "首章内容未能载入，当前进度没有改变。")
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
	button.pressed.connect(func():
		_cancel_keyboard("ui_action")
		_unlock_audio()
		if not _input_locked(): callback.call()
	)
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
	var cjk_font: FontFile = load(UI_FONT_PATH) as FontFile
	cjk_font.allow_system_fallback = false
	theme.default_font = cjk_font
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
	brand.add_child(_label("阶 塔", 27, GOLD))
	brand.add_child(_label("潮痕信号 · 第一章 · 体验06", 12, MUTED))
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 7)
	heading.add_child(actions)
	header_actions.save = _button(actions, "存档", _save_slot)
	header_actions.load = _button(actions, "读档", _load_slot)
	if OS.has_feature("web"):
		header_actions.save.tooltip_text = WEB_SAVE_NOTICE
		header_actions.load.tooltip_text = WEB_SAVE_NOTICE
	header_actions.restart = _button(actions, "重开 / 回溯", _show_recovery)
	header_actions.mode = _button(actions, "模式", _show_modes)
	sound_button = _button(actions, "声音 开", _toggle_sound)
	sound_button.tooltip_text = "音量 20%，点击静音。"
	mode_label = _label("请先选择经典或练习模式，再进入首章。", 14, CYAN)
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
	floor_label = _label("第一章 · F1—F10", 16, GOLD)
	world_column.add_child(floor_label)
	world_host = Control.new()
	world_host.name = "WorldViewport"
	world_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	world_host.custom_minimum_size.y = 300
	world_host.size_flags_vertical = Control.SIZE_EXPAND_FILL
	world_column.add_child(world_host)
	world_host.resized.connect(_schedule_fit)
	world_column.add_child(_label("暖色地砖可走 · 深色石墙阻挡 · 青色楼梯通往上下层",13,MUTED,true))
	availability_label = _label("目标 50 层 · 当前开放 1—10 层，11—50 层尚未制作", 14, MUTED)
	if OS.has_feature("web"): availability_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	world_column.add_child(availability_label)
	var compass := HBoxContainer.new()
	compass.add_theme_constant_override("separation", 8)
	world_column.add_child(compass)
	for entry: Array in [["↖",-1,-1],["↗",1,-1],["↙",-1,1],["↘",1,1]]:
		_button(compass, str(entry[0]), _screen_step.bind(Vector2(entry[1],entry[2])))
	_button(compass, "互动 E / 空格", _confirm_target)
	view_button = _button(compass,"总览",_toggle_overview)
	var side := PanelContainer.new()
	side.name = "FieldNotebook"
	side.custom_minimum_size.x = 350
	body.add_child(side)
	tabs = TabContainer.new()
	tabs.custom_minimum_size.x = 322
	side.add_child(tabs)
	var inspect_page := VBoxContainer.new()
	inspect_page.name = "查看"
	inspect_page.add_theme_constant_override("separation", 10)
	tabs.add_child(inspect_page)
	inspect_title = _label("下一步走哪里？", 24, GOLD, true)
	inspect_page.add_child(inspect_title)
	inspect_copy = _label("先选择模式。点击空地前往，点击物件查看用途。", 16, CREAM, true)
	inspect_copy.custom_minimum_size = Vector2(0, 132)
	inspect_page.add_child(inspect_copy)
	inspect_cost = _label("", 22, CYAN, true)
	inspect_page.add_child(inspect_cost)
	approach_button = _button(inspect_page, "前往", _approach)
	var offer_scroll := ScrollContainer.new()
	offer_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	offer_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	inspect_page.add_child(offer_scroll)
	offers_box = VBoxContainer.new()
	offers_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	offer_scroll.add_child(offers_box)
	var bestiary := VBoxContainer.new()
	bestiary.name = "怪物图鉴"
	tabs.add_child(bestiary)
	bestiary.add_child(_label("先看代价，再决定路线", 20, GOLD, true))
	bestiary_list = ItemList.new()
	bestiary_list.custom_minimum_size.y = 150
	bestiary_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	bestiary_list.item_selected.connect(_bestiary_selected)
	bestiary.add_child(bestiary_list)
	bestiary_copy = _label("你先攻击。预计扣血按当前装备计算，与实际战斗一致。", 16, CREAM, true)
	bestiary_copy.custom_minimum_size.y = 145
	bestiary.add_child(bestiary_copy)
	var journal_scroll := ScrollContainer.new()
	journal_scroll.name = "线索"
	journal_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	tabs.add_child(journal_scroll)
	journal_box = VBoxContainer.new()
	journal_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	journal_box.add_theme_constant_override("separation", 12)
	journal_scroll.add_child(journal_box)
	toast = _label("先选择模式，再进入首章。", 16, CREAM, true)
	toast.custom_minimum_size.y = 37
	screen.add_child(toast)
	screen.add_child(_label("点地面走整路 · 方向键按住续步，双键选斜向 · 物件 E 确认 · Esc 停步/暂停", 13, MUTED,true))
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
	header_actions.save.disabled = not enabled
	header_actions.load.disabled = not enabled or _classic_failed()
	approach_button.disabled = not enabled
	_sync_control_lock()


func _input_locked() -> bool:
	return _busy or _route_running or (is_instance_valid(world) and world.current_animation_busy())


func _sync_control_lock() -> void:
	var locked: bool = _busy or _route_running
	for node: Node in ui.find_children("*", "BaseButton", true, false):
		var button: BaseButton = node as BaseButton
		if locked:
			if not button.has_meta("before_action_disabled"):
				button.set_meta("before_action_disabled", button.disabled)
			button.disabled = true
		elif button.has_meta("before_action_disabled"):
			button.disabled = bool(button.get_meta("before_action_disabled"))
			button.remove_meta("before_action_disabled")
	if is_instance_valid(seed_input): seed_input.editable = not locked
	world.set_process_unhandled_input(started and modal_kind == "" and not locked)


func _setup_audio() -> void:
	if is_instance_valid(_audio): return
	_audio = ExperienceAudio.new()
	add_child(_audio)
	_audio.call("set_volume",0.2)
	_audio.call("set_muted",_muted)


func _unlock_audio() -> void:
	if not is_instance_valid(_audio): _setup_audio()
	if is_instance_valid(_audio): _audio.call("unlock_from_gesture")


func _toggle_sound() -> void:
	_muted = not _muted
	if is_instance_valid(_audio): _audio.call("set_muted",_muted)
	sound_button.text = "声音 关" if _muted else "声音 开"


func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.pressed:
			_cancel_keyboard("pointer")
			_unlock_audio()
	elif event is InputEventScreenTouch:
		if event.pressed:
			_cancel_keyboard("touch")
			_unlock_audio()
	elif event is InputEventKey:
		if event.pressed and not event.echo: _unlock_audio()
		if not _keyboard_context_allowed():
			_cancel_keyboard("ui_context")
		elif not event.pressed and _direction_bit(event.physical_keycode) != 0:
			# Observe release before GUI processing, but never consume its event.
			_keyboard.sync_physical(_physical_direction_mask(),Time.get_ticks_msec())


func _open_modal(kind: String, title: String, copy: String) -> void:
	_cancel_keyboard("modal")
	modal_kind = kind
	world.set_process_unhandled_input(false)
	overlay.show()
	_clear_children(overlay_box)
	overlay_box.add_child(_label("阶塔 · 潮痕信号", 13, GOLD))
	overlay_box.add_child(_label(title, 27, CREAM, true))
	var body := _label(copy, 16, MUTED, true)
	body.custom_minimum_size.x = 570
	overlay_box.add_child(body)
	modal_feedback = _label("", 15, CYAN, true)
	modal_feedback.hide()
	overlay_box.add_child(modal_feedback)


func _close_modal() -> void:
	_cancel_keyboard("modal_close")
	modal_kind = ""
	overlay.hide()
	world.set_process_unhandled_input(started and not _input_locked())
	# Return keyboard input to the world; Tab can re-enter the native HUD.
	get_viewport().gui_release_focus()


func _show_modes() -> void:
	if _input_locked() or not content_ready:
		return
	selected_mode = ""
	var save_copy: String = WEB_SAVE_NOTICE if OS.has_feature("web") else "两种模式的存档分别保存。"
	_open_modal("mode", "选择你的登塔方式", "当前为首章 1—10 层。目标共 50 层，11—50 层尚未制作。\n请主动选择模式，" + save_copy)
	overlay_box.add_child(_label("经典失败限制与练习回溯均适用于本次打开的游戏。" if OS.has_feature("web") else "经典模式的失败限制适用于当前打开的游戏；关闭并重新打开后，仍可恢复已有手动存档。",14,MUTED,true))
	var group := ButtonGroup.new()
	group.allow_unpress = false
	for entry: Array in [[CLASSIC,"经典模式 · 失败后换新塔，从头再来"],[PRACTICE,"练习模式 · 可回溯已到达楼层的完整记录"]]:
		var choice := _button(overlay_box, str(entry[1]), _select_mode.bind(str(entry[0])))
		choice.toggle_mode = true
		choice.button_group = group
		choice.name = "ClassicChoice" if entry[0] == CLASSIC else "PracticeChoice"
		overlay_box.add_child(_label("重开会清空本塔全部进度，并使用新的塔种子。" if entry[0] == CLASSIC else "回溯会撤销记录点之后的所有变化，包括拾取、开门和购买。", 14, MUTED, true))
	seed_input = LineEdit.new()
	seed_input.name = "TowerSeed"
	seed_input.placeholder_text = "塔种子（1 至 4294967295）"
	seed_input.text = str(selected_seed)
	seed_input.custom_minimum_size.y = 40
	seed_input.text_changed.connect(func(_text: String): _refresh_mode_buttons())
	overlay_box.add_child(seed_input)
	start_button = _button(overlay_box, "进入首章", _begin)
	start_button.name = "StartChapter"
	start_button.disabled = true
	mode_load_button = _button(overlay_box, "读取所选模式的存档", _load_slot)
	mode_load_button.disabled = true
	if OS.has_feature("web"): mode_load_button.tooltip_text = WEB_SAVE_NOTICE
	if started:
		overlay_box.add_child(_label("当前模式请使用“重开 / 回溯”。切换另一种模式时，确认后才会开始新塔。",14,MUTED,true))
		if bool(_snapshot().get("failed",false)):
			_button(overlay_box, "返回重开 / 回溯选项", _show_recovery)
		else:
			_button(overlay_box, "继续当前塔", _close_modal)
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
	start_button.tooltip_text = "当前模式请使用“重开 / 回溯”。" if started and selected_mode == active_mode else "以所选模式进入第一章。"
	mode_load_button.disabled = not valid or (started and selected_mode != active_mode)
	if selected_mode == CLASSIC and _classic_failed():
		mode_load_button.disabled = true
	mode_load_button.tooltip_text = "请先主动进入该模式，再读取其存档。" if started and selected_mode != active_mode else "读取所选模式的首章存档。"
	if selected_mode == CLASSIC and _classic_failed():
		mode_load_button.tooltip_text = "本次经典挑战已结束，请换新塔种子重开。"
	if OS.has_feature("web"): mode_load_button.tooltip_text = WEB_SAVE_NOTICE


func _begin() -> void:
	if _input_locked() or selected_mode not in [CLASSIC, PRACTICE] or _seed_value() < 1:
		return
	if started and selected_mode == active_mode:
		_message("当前模式请使用“重开 / 回溯”。")
		return
	var mode: String = selected_mode
	var seed: int = _seed_value()
	if started:
		var change_copy: String = "将从 F1 开始新塔，替换当前进度。" + WEB_SAVE_NOTICE if OS.has_feature("web") else "将从 F1 开始新塔，替换当前未保存的进度。手动存档在再次保存前保持原样。"
		_confirm("确认开始另一种模式？", change_copy, _do_begin.bind(mode, seed))
	else:
		_do_begin(mode, seed)


func _do_begin(mode: String, seed: int) -> void:
	if _input_locked(): return
	_unlock_audio()
	_busy = true
	_sync_control_lock()
	# An active runtime cannot silently change mode. Only an explicitly confirmed
	# new-tower action constructs a replacement, leaving the old object untouched
	# if content validation or mode selection fails.
	var candidate = Runtime.new()
	var loaded: Dictionary = candidate.load_content()
	if not bool(loaded.get("ok",false)):
		_busy = false
		_sync_control_lock()
		_message("首章未能载入，当前塔没有改变。")
		return
	var result: Dictionary = candidate.choose_mode(mode, seed)
	if not bool(result.get("ok", false)):
		_busy = false
		_sync_control_lock()
		_message(_result_text(result, {}, {}))
		return
	rules = candidate
	active_mode = mode
	selected_mode = mode
	selected_seed = seed
	started = true
	selected = []
	_last_delta = {}
	_last_slice_notice = false
	world.configure(rules)
	_close_modal()
	_busy = false
	_sync_control_lock()
	_set_actions_enabled(true)
	_refresh()
	_message("体验06 · 已进入 F1。点地面走空路，方向键可按住续步；物件先看代价，再按 E 确认。")


func _snapshot() -> Dictionary:
	return rules.export_snapshot() if started else {}


func _refresh() -> void:
	if not started:
		return
	var state: Dictionary = rules.state
	var snap: Dictionary = _snapshot()
	for key: String in ["hp", "atk", "def", "gold"]:
		stats[key].text = "%s %d%s" % [_stat_name(key), int(state.get(key, 0)), _delta_suffix(key)]
	var failure_view: Dictionary = _failure_presentation(snap)
	stats.hp.add_theme_color_override("font_color", GOLD)
	if failure_view.get("kind","") == "combat_death":
		stats.hp.text = "生命 0 · 战败"
		stats.hp.add_theme_color_override("font_color", DANGER)
	elif failure_view.get("kind","") == "abandoned":
		stats.hp.text = "生命 %d · 已结束" % int(state.get("hp",0))
		stats.hp.add_theme_color_override("font_color", MUTED)
	for key: String in ["yellow", "blue"]:
		stats[key].text = "%s %d%s" % [_stat_name(key), int(state.get("keys", {}).get(key, 0)), _delta_suffix(key)]
	var floor_index: int = int(state.get("floor", 0))
	floor_label.text = "F%d / F10 · %s" % [floor_index + 1, str(rules.floor_data().get("name", AREAS[clampi(floor_index, 0, 9)]))]
	mode_label.text = "%s · 首章体验 · 暂定名，可更改" % ("经典模式 · 失败后整塔重开" if active_mode == CLASSIC else "练习模式 · 可完整回溯")
	var revisit_copy: String = "可上下楼回访" if OS.has_feature("web") else "可上下楼回访与存档"
	availability_label.text = "首章已完成 · " + revisit_copy + " · 11—50 层尚未制作" if bool(snap.get("slice_complete",false)) else "首章目标：F1 → F2 → F3，继续攀登至 F10 · 楼梯上按 E 可往返"
	if OS.has_feature("web"): availability_label.text += " · " + WEB_SAVE_NOTICE
	world.refresh()
	header_actions.load.disabled = _classic_failed()
	_inspect(selected)
	_refresh_bestiary()
	_refresh_journal(snap)
	_sync_control_lock()
	_schedule_fit()
	if not bool(snap.get("slice_complete",false)):
		_last_slice_notice = false
	if bool(snap.get("failed", false)):
		if modal_kind in ["", "slice"]:
			_show_recovery()
	elif bool(snap.get("slice_complete", false)) and not _last_slice_notice:
		_last_slice_notice = true
		var completion_copy: String = "第一章已完成。仍可回访早先楼层、交换线索。" + WEB_SAVE_NOTICE if OS.has_feature("web") else "第一章已完成。仍可回访早先楼层、交换线索并保存当前塔。"
		_open_modal("slice", "首章信号已点亮", completion_copy + "\n11—50 层尚未制作，当前并非 50 层全塔通关。")
		_button(overlay_box, "返回塔内", _close_modal).call_deferred("grab_focus")
		var save_button: Button = _button(overlay_box, "保存当前塔", _save_slot)
		if OS.has_feature("web"): save_button.tooltip_text = WEB_SAVE_NOTICE


func _clear_children(parent: Node) -> void:
	for child: Node in parent.get_children():
		parent.remove_child(child)
		child.queue_free()


func _inspect(cell: Array) -> void:
	_clear_children(offers_box)
	approach_button.hide()
	inspect_cost.text = ""
	inspect_cost.add_theme_color_override("font_color", CYAN)
	if cell.size() != 2:
		inspect_title.text = "选择下一步"
		inspect_copy.text = "点击空地逐格前往。点击敌人、门、物品或楼梯，先查看再操作。\n一把同色钥匙开一扇门；回访时，开过的门和拾取过的资源会保留状态。"
		world.set_route_preview([])
		world.set_action_hint("点击空地前往 · 点击物件查看 · 楼梯上按 E 往返")
		return
	if not rules.walkable(cell):
		inspect_title.text = "石墙，无法通行"
		inspect_copy.text = "请沿暖色地砖走。这里是墙壁，不能前往，也不会消耗生命或资源。"
		world.set_route_preview([])
		world.set_action_hint("石墙，无法通行 · 请沿暖色地砖走")
		return
	var info: Dictionary = rules.inspect(cell)
	var item: Dictionary = info.get("object", {})
	var kind: String = str(item.get("kind", ""))
	approach_button.show()
	approach_button.disabled = not bool(info.get("walkable", false))
	approach_button.text = "前往"
	inspect_title.text = _item_title(item)
	inspect_copy.text = "沿可通行的空地逐格前往。不会自动绕过敌人、门或楼梯。"
	match kind:
		"enemy":
			inspect_title.text = _enemy_label(str(item.get("type","")))
			var fight: Dictionary = info.get("combat", {})
			var enemy: Dictionary = info.get("enemy", rules.data.get("enemies", {}).get(str(item.get("type", "")), {}))
			inspect_copy.text = "生命 %d · 攻击 %d · 防御 %d\n击败获得 %d 金币。你先攻击。\n\n%s" % [int(enemy.get("hp",0)), int(enemy.get("atk",0)), int(enemy.get("def",0)), int(enemy.get("gold",0)), "当前配置可战胜，预览扣血等于实际扣血。" if bool(fight.get("win",false)) else "当前无法战胜，请先寻找补给或调整路线。"]
			inspect_cost.text = "预计扣血 %d · %d 回合" % [int(fight.get("damage",0)), int(fight.get("rounds",0))] if int(fight.get("damage",-1)) >= 0 else "攻击不足，无法破防"
			inspect_cost.add_theme_color_override("font_color", CYAN if bool(fight.get("win",false)) else DANGER)
			approach_button.disabled = not bool(fight.get("win",false))
			approach_button.text = "前往并战斗" if bool(fight.get("win",false)) else "暂不可战胜"
		"door":
			var color: String = str(item.get("type","yellow"))
			var held: int = int(rules.state.get("keys",{}).get(color,0))
			inspect_copy.text = "开启消耗 1 把同色钥匙。开过的门在上下楼回访时仍保持开启。"
			inspect_cost.text = "消耗 1 把%s · 持有 %d 把" % [_stat_name(color),held]
			approach_button.text = "前往并开门" if held > 0 else "缺少%s" % _stat_name(color)
			approach_button.disabled = held < 1
		"stairs":
			var target: int = int(item.get("target",{}).get("floor",0))
			var stair_verb: String = "上楼" if item.get("direction","") == "up" else "下楼"
			inspect_title.text = "%s · 前往 F%d" % [stair_verb,target]
			inspect_copy.text = "走进楼梯会切换到 F%d。落脚后，再按 E 可沿此楼梯返回。\n门、怪物、钥匙、商店库存均保留当前状态。" % target
			inspect_cost.text = "F%d → F%d" % [int(rules.state.get("floor",0))+1,target]
			approach_button.text = "%s至 F%d" % [stair_verb,target]
		"boundary":
			inspect_title.text = "后续楼层尚未制作"
			inspect_copy.text = "本次首章开放至 F10。11—50 层尚不可进入，已开放楼层可继续回访。" + WEB_SAVE_NOTICE if OS.has_feature("web") else "本次首章开放至 F10。11—50 层尚不可进入，已开放楼层可继续回访和存档。"
			approach_button.disabled = true
		"npc":
			inspect_title.text = str(item.get("name","制图人" if int(rules.state.floor) == 0 else "守灯人"))
			inspect_copy.text = "在相邻格交谈。高处找到的线索，也许值得带回来。"
			approach_button.text = "前往并交谈"
			var npc_events: Array = info.get("available_events",[])
			if not npc_events.is_empty():
				inspect_copy.text = str(npc_events[0].get("text",inspect_copy.text))
			_show_event_effects(npc_events)
		"event":
			inspect_title.text = str(item.get("name","首章线索" if int(rules.state.floor) < 9 else "未点亮的信号"))
			inspect_copy.text = "前往阅读或使用。条件满足后才能触发，每份奖励只领取一次。"
			approach_button.text = "前往并查看"
			var place_events: Array = info.get("available_events",[])
			if not place_events.is_empty():
				inspect_copy.text = str(place_events[0].get("text",inspect_copy.text))
			_show_event_effects(place_events)
		"shop":
			var shop: Dictionary = info.get("shop", {})
			inspect_title.text = str(shop.get("name","修补商店"))
			inspect_copy.text = "站在商店格或相邻格即可购买。库存有限，先比较升级对后续路线的帮助。\n当前持有 %d 金币。" % int(rules.state.get("gold",0))
			approach_button.text = "前往商店"
			if _cell_distance(cell,rules.state.get("pos",[])) <= 1: approach_button.hide()
			for offer: Dictionary in shop.get("offers", []):
				var amount: int = int(offer.get("amount",0))
				var label: String = str(offer.get("label","补给"))
				var used: int = int(rules.state.get("purchases",{}).get(str(item.get("id",""))+"/"+str(offer.get("id","")),0))
				var remaining: int = maxi(0,int(offer.get("limit",1))-used)
				var resource: String = _stat_name(str(offer.get("kind","")))
				var reason: String = _shop_reason(item,offer,remaining)
				var buy_button := _button(offers_box, "购买 %s · %s +%d\n价格 %d 金币 · 剩余 %d 件" % [label,resource,amount,int(offer.get("cost",0)),remaining], _buy.bind(str(offer.get("id",""))))
				buy_button.tooltip_text = reason if not reason.is_empty() else "点击购买一次；金币、属性与库存会同时更新。"
				buy_button.disabled = not reason.is_empty()
				offers_box.add_child(_label(reason if not reason.is_empty() else "可购买 · %d 金币 → %s +%d" % [int(offer.get("cost",0)),resource,amount],13,DANGER if not reason.is_empty() else CYAN,true))
		"key":
			inspect_title.text = _stat_name(str(item["type"]))
			inspect_cost.text = "拾取：%s +%d" % [inspect_title.text,int(item["amount"])]
			inspect_copy.text = "同色钥匙用于同色门。每份钥匙只拾取一次，已打开的门不会重复扣钥匙。"
			approach_button.text = "前往并拾取"
		"potion", "atk", "def", "gold":
			inspect_cost.text = "拾取：%s +%d" % [_stat_name(kind),int(item["amount"])]
			inspect_copy.text = "拾取后立即生效。每份资源只获得一次，上下楼不会刷新。"
			approach_button.text = "前往并拾取"
		_:
			inspect_title.text = "可通行空地" if bool(info.get("walkable",false)) else "墙壁"
			inspect_copy.text = "点击空地会自动沿安全空路逐格前往；也可使用方向键或左下方按钮。" if bool(info.get("walkable",false)) else "这里不可通行，请选择相邻的空地。"
	var path: Array = _safe_path(cell)
	world.set_route_preview(path)
	if path.is_empty() and _cell_distance(cell,rules.state.get("pos",[])) > 0:
		approach_button.disabled = true
		approach_button.tooltip_text = "尚无畅通路线，请先处理沿途障碍。"
	else:
		approach_button.tooltip_text = "逐格执行，抵达物件时只交互一次。"
	world.set_action_hint(inspect_title.text + " · " + approach_button.text)
	if selected.is_empty():
		approach_button.disabled = true
		approach_button.tooltip_text = "先点击地图上的这个目标，再选择操作。"
	_sync_control_lock()


func _show_event_effects(available: Array) -> void:
	if available.is_empty():
		inspect_cost.text = "当前无可领取的互动，请先完成相关线索。"
		inspect_cost.add_theme_color_override("font_color", MUTED)
		approach_button.disabled = true
		return
	# The runtime executes the first eligible event, in authored order. Show only
	# that event's typed finite grants; do not add the other eligible branches.
	inspect_cost.text = _event_effects_text(available[0].get("effects",[]))
	inspect_copy.text += "\n\n本次互动只领取一次；下列增量仅对应当前可触发的这一条。"


func _event_effects_text(effects: Array) -> String:
	var rewards := PackedStringArray()
	for effect: Dictionary in effects:
		match str(effect.get("kind","")):
			"grant":
				rewards.append("%s +%d" % [_stat_name(str(effect["stat"])),int(effect["amount"])])
			"grant_key":
				rewards.append("%s +%d" % [_stat_name(str(effect["color"])),int(effect["amount"])])
	return "获得：" + " / ".join(rewards) if not rewards.is_empty() else "一次性首章事件"


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
	return str(enemy.get("name","塔中守卫"))


func _bestiary_selected(index: int) -> void:
	if index < 0 or index >= _enemy_ids.size():
		return
	var enemy: Dictionary = rules.data.get("enemies", {})[_enemy_ids[index]]
	var fight: Dictionary = rules.combat(enemy)
	bestiary_copy.text = "生命 %d · 攻击 %d · 防御 %d\n击败获得 %d 金币\n\n%s\n\n你先攻击。预览使用当前装备，与实际扣血采用同一规则。" % [int(enemy.get("hp",0)),int(enemy.get("atk",0)),int(enemy.get("def",0)),int(enemy.get("gold",0)),"可战胜 · 预计扣血 %d" % int(fight.get("damage",0)) if bool(fight.get("win",false)) else ("无法破防" if int(fight.get("damage",-1)) < 0 else "当前生命不足，不能战胜")]


func _refresh_journal(snap: Dictionary) -> void:
	_clear_children(journal_box)
	journal_box.add_child(_label("线索与回访", 20, GOLD, true))
	var flags: Dictionary = snap.get("flags",{})
	var copper_status: String = "已兑换" if bool(flags.get("copper_redeemed",false)) else ("已找到铜签，请返回 F1 找制图人" if bool(flags.get("copper_found",false)) else "前往 F3 寻找铜签，再带回 F1")
	var keeper_status: String = "已领取补给" if bool(flags.get("keeper_supplied",false)) else ("已读档案，请拜访 F7 守灯人" if bool(flags.get("archive_read",false)) else "前往 F5 阅读封存档案")
	journal_box.add_child(_label("F3 → F1 · %s\nF5 → F7 · %s" % [copper_status,keeper_status], 16, CREAM, true))
	var events: Array = snap.get("completed_events", [])
	journal_box.add_child(_label("已记录 %d 条首章事件" % events.size(), 14, CYAN, true))
	var registry: Dictionary = rules.data.get("events", {})
	for event_id: String in events:
		var entry: Dictionary = registry.get(event_id, {})
		var text: String = str(entry.get("text", "已记录一条首章线索或交换。"))
		journal_box.add_child(_label("✓ F%d · %s" % [int(entry.get("floor",0)),text], 15, MUTED, true))
	var boundary := Button.new()
	boundary.text = "11—50 层 · 尚未制作"
	boundary.disabled = true
	boundary.custom_minimum_size.y = 44
	journal_box.add_child(boundary)


func _cell_clicked(cell: Array) -> void:
	if not started or modal_kind != "" or _input_locked():
		return
	_cancel_keyboard("map_click")
	get_viewport().gui_release_focus()
	var confirm_again: bool = selected == cell and not rules.object_at(cell).is_empty()
	world.set_direction_candidates([])
	selected = cell.duplicate()
	if not confirm_again and not rules.object_at(cell).is_empty(): _confirm_after_frame = Engine.get_process_frames()
	world.set_hover(selected)
	_inspect(selected)
	tabs.current_tab = 0
	if not rules.walkable(cell): return
	if rules.object_at(cell).is_empty() and rules.walkable(cell):
		await _approach()
	elif confirm_again and not approach_button.disabled:
		await _approach()


func _hovered(cell: Array) -> void:
	if not started or modal_kind != "" or _input_locked(): return
	if selected.is_empty():
		_inspect(cell)
	else:
		# Keep the visible highlight bound to the action card's explicit target.
		world.set_hover(selected)


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
	_cancel_keyboard("point_route")
	if not started or modal_kind != "" or selected.size() != 2 or _input_locked():
		return
	if not rules.object_at(selected).is_empty() and Engine.get_process_frames() <= _confirm_after_frame:
		return
	if _cell_distance(selected,rules.state.get("pos",[])) == 0:
		if rules.object_at(selected).get("kind","") == "stairs":
			await _use_stairs()
		return
	var path: Array = _safe_path(selected)
	if path.is_empty():
		_message("没有畅通路线。请先处理途中障碍，或移动到物件旁边。")
		return
	_route_running = true
	_cancel_route = false
	_sync_control_lock()
	for index: int in range(path.size()):
		if _cancel_route: break
		var cell: Array = path[index]
		world.set_route_preview(path.slice(index))
		var result: Dictionary = await _commit(Callable(rules,"interact").bind(cell),cell)
		if not bool(result.get("ok",false)) or str(result.get("action","")) in ["stairs","combat","event","npc"]:
			break
		if modal_kind != "" or rules.is_failed(): break
	_route_running = false
	world.set_route_preview([])
	_sync_control_lock()
	if modal_kind == "": _inspect(selected)
	_apply_pending_pause()


func _step(dx: int, dy: int) -> void:
	if not _keyboard_dispatch_active: _cancel_keyboard("manual_step")
	if started and modal_kind == "" and not _input_locked():
		selected = []
		world.set_hover([])
		var pos: Array = rules.state.get("pos",[])
		var target: Array = [int(pos[0])+dx,int(pos[1])+dy]
		world.set_direction_candidates([])
		if not rules.object_at(target).is_empty():
			_confirm_after_frame = Engine.get_process_frames()
			selected = target
			world.set_hover(selected)
			_inspect(selected)
			tabs.current_tab = 0
			_message("已选中%s。查看代价后，按 E / 空格或再点一次确认。" % inspect_title.text)
			return
		await _commit(Callable(rules,"move").bind(dx,dy),target)


func _screen_step(intent: Vector2) -> void:
	_cancel_keyboard("direction_button")
	if not started or modal_kind != "" or _input_locked(): return
	var initiating_focus: Control = get_viewport().gui_get_focus_owner()
	if not (initiating_focus is BaseButton): initiating_focus = null
	var resolved: Dictionary = ScreenInput.resolve(intent,world.projected_step_options())
	world.set_direction_candidates([])
	if resolved.get("status","") == "step":
		var delta: Array = resolved["delta"]
		await _step(int(delta[0]),int(delta[1]))
	elif resolved.get("status","") == "choose":
		selected = []
		world.set_hover([])
		_inspect([])
		world.set_direction_candidates(resolved["cells"])
		_message("这个画面方向有两个邻格。请点其中一个，或同时按两个方向键选斜向；不会替你转弯。")
		world.set_action_hint("选择亮框中的邻格 · 例如 ↑+← 对应画面左上")
	elif resolved.get("status","") == "blocked":
		_message("该方向被墙挡住；请选另一格，不会自动改走别的方向。")
	# Object previews do not reach _commit; return only the same button's focus.
	if modal_kind == "" and is_instance_valid(initiating_focus) and get_viewport().gui_get_focus_owner() == initiating_focus:
		get_viewport().gui_release_focus()


func _direction_bit(key: int) -> int:
	match key:
		KEY_W,KEY_UP: return Keyboard.UP
		KEY_S,KEY_DOWN: return Keyboard.DOWN
		KEY_A,KEY_LEFT: return Keyboard.LEFT
		KEY_D,KEY_RIGHT: return Keyboard.RIGHT
	return 0


func _physical_direction_mask() -> int:
	var mask := 0
	if Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP): mask |= Keyboard.UP
	if Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN): mask |= Keyboard.DOWN
	if Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT): mask |= Keyboard.LEFT
	if Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT): mask |= Keyboard.RIGHT
	return mask


func _keyboard_context_allowed() -> bool:
	return started and modal_kind == "" and is_inside_tree() and get_window().has_focus() and get_viewport().gui_get_focus_owner() == null


func _cancel_keyboard(reason: String) -> void:
	_keyboard.cancel(reason,_physical_direction_mask())
	if is_instance_valid(world): world.set_direction_candidates([])


func _keyboard_focus_gained(_control: Control) -> void:
	_cancel_keyboard("gui_focus")
	_keyboard_context_suspended = true


func _process(_delta: float) -> void:
	_keyboard.sync_physical(_physical_direction_mask(),Time.get_ticks_msec())
	if not _keyboard_context_allowed():
		if not _keyboard_context_suspended: _cancel_keyboard("context")
		_keyboard_context_suspended = true
		return
	_keyboard_context_suspended = false
	_pump_keyboard()


func _pump_keyboard() -> void:
	if _keyboard_driver_busy or not _keyboard_context_allowed(): return
	if Engine.get_process_frames() == _keyboard_last_dispatch_frame: return
	var result: Dictionary = _keyboard.poll(Time.get_ticks_msec(),_input_locked(),world.projected_step_options())
	match str(result.get("status","idle")):
		"step":
			_keyboard_last_dispatch_frame = Engine.get_process_frames()
			var delta: Array = result["delta"]
			var pos: Array = rules.state.get("pos",[])
			var target: Array = [int(pos[0])+int(delta[0]),int(pos[1])+int(delta[1])]
			if target != result.get("cell",[]):
				_cancel_keyboard("stale_target")
				return
			if not rules.object_at(target).is_empty():
				_cancel_keyboard("object_preview")
				await _step(int(delta[0]),int(delta[1]))
				return
			_keyboard_driver_busy = true
			_keyboard_dispatch_active = true
			await _step(int(delta[0]),int(delta[1]))
			# A cancellation epoch never skips completion of the in-flight cell.
			_keyboard_dispatch_active = false
			_keyboard_driver_busy = false
		"choose":
			selected = []
			world.set_hover([])
			_inspect([])
			world.set_direction_candidates(result["cells"])
			_message("方向分叉：再按一个方向键选斜向；选定后按住可沿该方向续步。")
		"blocked":
			world.set_direction_candidates([])
			_message("前方有墙，已停止续步；不会自动转向另一条路。")


func _confirm_target() -> void:
	_cancel_keyboard("explicit_confirm")
	if not started or modal_kind != "" or _input_locked(): return
	if selected.size() == 2 and not rules.object_at(selected).is_empty():
		if not approach_button.disabled: await _approach()
	elif rules.object_at(rules.state.get("pos",[])).get("kind","") == "stairs":
		await _use_stairs()
	else:
		_message("先点击物件查看代价；点击空地可直接走过去。")


func _toggle_overview() -> void:
	_overview = not _overview
	view_button.text = "近看" if _overview else "总览"
	world.set_overview(_overview)


func _apply_pending_pause() -> void:
	if not _pause_when_idle or _input_locked(): return
	_pause_when_idle = false
	if modal_kind == "" and not rules.is_failed(): _pause()


func _use_stairs() -> void:
	_cancel_keyboard("stairs")
	if started and modal_kind == "" and not _input_locked():
		selected = []
		await _commit(Callable(rules,"use_stairs"),rules.state.get("pos",[]))


func _buy(choice: String) -> void:
	_cancel_keyboard("purchase")
	if not started or modal_kind != "" or _input_locked(): return
	var item: Dictionary = _transaction_shop()
	if item.is_empty():
		_message("距离商店太远，请先前往商店格或相邻格。")
		return
	if selected.size() == 2:
		var inspected: Dictionary = rules.object_at(selected)
		if inspected.get("kind","") == "shop" and inspected.get("id","") != item.get("id",""):
			_message("请先走到所选商店旁，再购买这里的物品。")
			return
	var offer: Dictionary = {}
	for value: Dictionary in rules.data["shops"][item["type"]].get("offers",[]):
		if str(value["id"]) == choice: offer = value.duplicate(true)
	if offer.is_empty():
		_message("这间商店没有所选商品，请重新查看。")
		return
	await _commit(Callable(rules,"buy").bind(choice),item["pos"],offer)


func _commit(command: Callable, target: Array = [], offer: Dictionary = {}) -> Dictionary:
	# The authority executes exactly once. Animation never replays a rule action.
	if _busy or not started: return {}
	var initiating_focus: Control = get_viewport().gui_get_focus_owner()
	if not (initiating_focus is BaseButton):
		initiating_focus = null
	if not _keyboard_dispatch_active: _cancel_keyboard("manual_command")
	world.set_direction_candidates([])
	_busy = true
	_sync_control_lock()
	var before: Dictionary = rules.state.duplicate(true)
	var previous_item: Dictionary = rules.object_at(target).duplicate(true) if target.size() == 2 else {}
	var result: Dictionary = command.call()
	await world.present_transition(before,result,previous_item)
	var after: Dictionary = rules.state.duplicate(true)
	if not bool(result.get("ok",false)) or str(result.get("action","")) != "move" or before.get("floor",-1) != after.get("floor",-1):
		_cancel_keyboard("world_transition")
	_last_delta = _state_delta(before,after)
	if str(result.get("action","")) == "stairs":
		selected = []
		world.set_hover([])
	if is_instance_valid(_audio) and bool(result.get("ok",false)):
		var sound_kind: String = str(result.get("action",""))
		if sound_kind in ["pickup","door","purchase","stairs","combat"]:
			_audio.call("play_feedback",sound_kind)
		elif sound_kind == "event" and not _last_delta.is_empty():
			_audio.call("play_feedback","pickup")
	_busy = false
	_sync_control_lock()
	_refresh()
	if modal_kind == "" and is_instance_valid(initiating_focus) and get_viewport().gui_get_focus_owner() == initiating_focus:
		get_viewport().gui_release_focus()
	var feedback: String = _result_text(result,before,previous_item)
	if bool(result.get("ok",false)) and str(result.get("action","")) == "purchase":
		var key: String = str(previous_item.get("id",""))+"/"+str(offer.get("id",""))
		var remaining: int = maxi(0,int(offer.get("limit",0))-int(after.get("purchases",{}).get(key,0)))
		feedback = "已购买%s · %s · 金币 %d → %d · 余货 %d 件" % [str(offer.get("label","补给")),_delta_text(),int(before.get("gold",0)),int(after.get("gold",0)),remaining]
	elif not bool(result.get("ok",false)) and str(result.get("status",result.get("action",""))) == "no_gold" and offer.has("cost"):
		feedback = "金币不足：需 %d，当前 %d，还差 %d。购买未发生。" % [int(offer["cost"]),int(after.get("gold",0)),maxi(0,int(offer["cost"])-int(after.get("gold",0)))]
	elif bool(result.get("ok",false)) and not _last_delta.is_empty():
		feedback += " · " + _delta_text()
	_message(feedback)
	if bool(result.get("ok",false)) and str(result.get("action","")) == "event" and not bool(_snapshot().get("slice_complete",false)) and modal_kind == "":
		_open_modal("dialogue","塔中留言",str(result.get("message","")))
		_button(overlay_box,"返回塔内",_close_modal).call_deferred("grab_focus")
	_apply_pending_pause()
	return result


func _stat_name(key: String) -> String:
	return str(STAT_NAMES.get(key,"资源"))


func _cell_distance(a: Array, b: Array) -> int:
	if a.size() != 2 or b.size() != 2: return 99999
	return absi(int(a[0])-int(b[0])) + absi(int(a[1])-int(b[1]))


func _item_title(item: Dictionary) -> String:
	if item.has("name"): return str(item["name"])
	return str({"enemy":"守卫", "door":"门", "stairs":"楼梯", "npc":"塔中人", "event":"线索", "shop":"商店", "key":"钥匙", "potion":"补给", "atk":"攻击晶石", "def":"防御晶石", "gold":"金币"}.get(str(item.get("kind","")),"空地"))


func _transaction_shop() -> Dictionary:
	# Mirrors only which shop the authority addresses, not its transaction logic.
	for item: Dictionary in rules.floor_data().get("objects",[]):
		if item.get("kind","") == "shop" and _cell_distance(item["pos"],rules.state.get("pos",[])) <= 1:
			return item
	return {}


func _shop_reason(item: Dictionary, offer: Dictionary, remaining: int) -> String:
	var reasons := PackedStringArray()
	var distance: int = _cell_distance(item.get("pos",[]),rules.state.get("pos",[]))
	if distance > 1: reasons.append("距离过远：相隔 %d 格，请先前往商店旁" % distance)
	if remaining <= 0: reasons.append("已售罄：本塔库存不会刷新")
	var cost: int = int(offer.get("cost",0))
	var gold: int = int(rules.state.get("gold",0))
	if gold < cost: reasons.append("金币不足：需 %d，现有 %d，还差 %d" % [cost,gold,cost-gold])
	if rules.is_failed(): reasons.append("本次挑战已结束，请先重开或回溯")
	return "；".join(reasons)


func _state_delta(before: Dictionary, after: Dictionary) -> Dictionary:
	var delta: Dictionary = {}
	for key: String in ["hp","atk","def","gold"]:
		var amount: int = int(after.get(key,0))-int(before.get(key,0))
		if amount != 0: delta[key] = amount
	for key: String in ["yellow","blue"]:
		var amount: int = int(after.get("keys",{}).get(key,0))-int(before.get("keys",{}).get(key,0))
		if amount != 0: delta[key] = amount
	return delta


func _delta_suffix(key: String) -> String:
	return " (%+d)" % int(_last_delta[key]) if _last_delta.has(key) else ""


func _delta_text() -> String:
	var parts := PackedStringArray()
	for key: String in ["hp","atk","def","gold","yellow","blue"]:
		if _last_delta.has(key): parts.append("%s %+d" % [_stat_name(key),int(_last_delta[key])])
	return "，".join(parts)


func _result_text(result: Dictionary, before: Dictionary, item: Dictionary) -> String:
	var code: String = str(result.get("status",result.get("action",result.get("result",""))))
	if bool(result.get("ok",false)):
		match code:
			"stairs":
				return "已从 F%d %s至 F%d · %s。站在楼梯上按 E 可返回。" % [int(before.get("floor",0))+1,"上楼" if int(rules.state.get("floor",0)) > int(before.get("floor",0)) else "下楼",int(rules.state.get("floor",0))+1,str(rules.floor_data().get("name",""))]
			"combat", "victory": return "已击败%s" % _enemy_label(str(item.get("type","")))
			"pickup": return "已拾取%s" % _item_title(item)
			"door": return "门已打开，之后往返不再消耗钥匙"
			"event": return str(result.get("message","已记录这条线索。"))
			"move", "shop": return "已到达 F%d。点击物件查看下一步。" % (int(rules.state.get("floor",0))+1)
			"purchase": return "购买成功"
			"checkpoint_restored": return "已完整回到记录点，之后的拾取和购买已撤销。"
			"restarted", "started": return "新塔已从 F1 开始。"
			"abandoned": return "已主动结束本次挑战，请选择重开或回溯。"
			"combat_death": return "本次战斗已结束挑战，请按当前模式继续。"
			"saved_native": return "已保存当前模式的首章进度。"
			"saved_web": return "已保存：浏览器已确认提交并读回当前模式的首章进度。"
			"loaded_web": return "已恢复首章存档；旧文件已复制到浏览器存档，原文件保留。" if bool(result.get("migrated",false)) else "已恢复此浏览器中所选模式的完整首章存档。"
			"loaded_native", "snapshot_loaded": return "已恢复所选模式的完整首章存档。"
		return "操作已完成。"
	match code:
		"wall": return "墙壁不可通行，请选择空地。"
		"blocked": return "请操作相邻格；使用楼梯时，需要站在楼梯格上。"
		"door_locked": return "缺少%s：需要 1 把，当前持有 %d 把。" % [_stat_name(str(item.get("type","yellow"))),int(rules.state.get("keys",{}).get(item.get("type","yellow"),0))]
		"unwinnable":
			var fight: Dictionary = result.get("combat",{})
			return "攻击不足，无法破防；本次未战斗、未扣血。" if int(fight.get("damage",-1)) < 0 else "生命不足：预计扣血 %d，当前生命 %d。请先补给；本次未扣血。" % [int(fight.get("damage",0)),int(rules.state.get("hp",0))]
		"no_gold": return "金币不足，购买未发生。请核对右侧价格与当前余额。"
		"sold_out": return "商品已售罄，本塔库存不会刷新；本次未扣金币。"
		"shop_unavailable": return "距离商店太远，请站到商店格或相邻格再购买。"
		"event_unavailable": return "这条线索尚未满足条件，或已领取过。请查看线索页。"
		"not_authored": return "11—50 层尚未制作，当前无法进入。"
		"mode_required", "mode_unselected", "mode_already_selected": return "请先主动选择模式；当前模式需用“重开 / 回溯”继续。"
		"failed", "death_requires_restart": return "本次挑战已结束，请按当前模式重开或回溯。"
		"invalid_seed", "invalid_new_seed": return "请输入 1 至 4294967295 之间的整数；经典重开需使用不同的新种子。"
		"confirmation_required": return "请先确认重开或回溯；当前塔没有改变。"
		"stale_loss_id": return "此恢复请求已失效或已使用，请重新选择重开 / 回溯。"
		"wrong_mode": return "当前模式不支持此恢复操作，请使用对应的重开 / 回溯选项。"
		"unknown_checkpoint", "checkpoint_mismatch": return "该记录点不属于当前塔，当前进度没有改变。"
		"not_found": return "没有找到此模式的首章存档。当前塔没有改变。"
		"blocked_web_persistence_unvalidated": return "此浏览器的持久存档尚未验证，本次没有保存或恢复进度。"
		"web_commit_unconfirmed": return "浏览器未确认保存完成，存档可能已更新。请保留页面，重新读取核对；当前塔没有被替换。"
		"web_conflict": return "存档已被另一页面更新，本次没有覆盖。请保留当前页面并核对存档。"
		"web_unavailable", "web_storage_unavailable", "web_open_blocked", "web_open_failed", "web_transaction_failed", "web_transaction_aborted", "web_read_failed", "web_write_failed", "web_storage_changed", "web_invalid_database", "web_timeout":
			if result.get("error_name", "") == "QuotaExceededError": return "浏览器存档空间不足，未完成保存。请保留当前页面和已有存档。"
			return "浏览器无法完成本地存档操作。当前塔仍在页面中，请保留页面并重试；没有收到保存成功回执。"
		"web_runtime_changed", "web_storage_busy": return "进度或存档操作仍在变化，本次未保存。请等待动作结束后再试。"
		"web_invalid_reply", "web_invalid_record", "web_invalid_request": return "浏览器存档未通过校验。请保留页面和原存档，本次没有保存或恢复进度。"
		"identity_mismatch", "snapshot_rejected", "snapshot_identity_mismatch": return "存档与当前版本或模式不匹配，当前塔和存档均保持原样。"
		"mode_mismatch": return "存档模式不同，请先主动选择相同模式。当前塔没有改变。"
		"existing_slot_rejected": return "原存档与当前塔不兼容或已损坏，已保留原文件，本次没有覆盖。"
		"pending_exists": return "有一份未完成的临时存档，本次没有覆盖任何存档。"
		"import_rejected": return "完整存档未能恢复，当前塔没有改变。请按当前模式的规则继续。"
		"read_failed", "invalid_utf8", "invalid_json", "invalid_payload_size", "payload_checksum_mismatch", "snapshot_checksum_mismatch": return "存档无法完整读取或校验未通过，当前塔与原存档保持不变。"
		"format_mismatch", "save_version_mismatch", "envelope_schema_mismatch", "slot_mismatch": return "此存档不属于当前首章版本或存档位，未读取或改写进度。"
		"directory_failed", "write_failed", "commit_failed": return "存档写入未完成，请勿关闭当前塔；原存档未被删除。"
		"action_limit": return "本次操作记录已达上限。" + WEB_SAVE_NOTICE if OS.has_feature("web") else "本次操作记录已达上限，请保存当前塔后再决定后续操作。"
		"attempt_limit": return "本次重开次数已达上限，当前塔没有改变。"
	return "操作未完成，当前进度保持原样。请重新选择目标或查看重开 / 回溯选项。"


func _message(text: String) -> void:
	toast.text = text
	if is_instance_valid(modal_feedback) and overlay.visible:
		modal_feedback.text = text
		modal_feedback.show()


func _save_slot() -> void:
	_cancel_keyboard("save")
	if _input_locked(): return
	if started:
		_busy = true
		_sync_control_lock()
		var result: Dictionary
		if OS.has_feature("web"):
			_message("正在等待浏览器确认存档，请保留此页面……")
			result = await _web_saves.write_slot(rules, SLOT)
		else:
			result = Saves.write_slot(rules, SLOT)
		_busy = false
		_sync_control_lock()
		_message(_result_text(result,{},{}))
		_apply_pending_pause()


func _load_slot() -> void:
	_cancel_keyboard("load")
	if _input_locked(): return
	var intended_mode: String = active_mode if started else selected_mode
	if intended_mode == CLASSIC and _classic_failed():
		_message("本次经典挑战已结束。请使用新塔种子重开，或主动选择另一种模式。")
		return
	if modal_kind == "mode":
		if selected_mode not in [CLASSIC,PRACTICE] or _seed_value() < 1 or (started and selected_mode != active_mode):
			return
		intended_mode = selected_mode
	if intended_mode not in [CLASSIC,PRACTICE]:
		return
	if started:
		_confirm("确认读取存档？", "当前未保存的进度将被此模式的完整首章存档替换。另一模式的存档保持独立。", _do_load_slot.bind(intended_mode))
	else:
		_do_load_slot(intended_mode)


func _do_load_slot(intended_mode: String) -> void:
	if _input_locked(): return
	# A fresh candidate must not bypass the failed-session Classic recovery rule.
	if intended_mode == CLASSIC and _classic_failed():
		_message("本次经典挑战已结束，当前打开的游戏中不能用旧存档撤销失败；请换新种子重开。")
		return
	_busy = true
	_sync_control_lock()
	var candidate = Runtime.new()
	var loaded: Dictionary = candidate.load_content()
	if not bool(loaded.get("ok",false)):
		_busy = false
		_sync_control_lock()
		_message("首章内容未能载入，当前塔没有改变。")
		return
	var chosen: Dictionary = candidate.choose_mode(intended_mode,selected_seed)
	if not bool(chosen.get("ok",false)):
		_busy = false
		_sync_control_lock()
		_message(_result_text(chosen,{},{}))
		return
	var result: Dictionary
	if OS.has_feature("web"):
		_message("正在读取浏览器存档并校验完整进度……")
		result = await _web_saves.load_slot(candidate, SLOT)
	else:
		result = Saves.load_slot(candidate, SLOT)
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
		_last_delta = {}
		_last_slice_notice = false
		world.configure(rules)
		_close_modal()
		_busy = false
		_sync_control_lock()
		_set_actions_enabled(true)
		_refresh()
	_busy = false
	_sync_control_lock()
	_message(_result_text(result,{},{}))
	_apply_pending_pause()


func _confirm(title: String, copy: String, callback: Callable) -> void:
	_open_modal("confirm",title,copy)
	_button(overlay_box,"确认",callback).call_deferred("grab_focus")
	_button(overlay_box,"保留当前塔",_cancel_confirmation)


func _cancel_confirmation() -> void:
	if bool(_snapshot().get("failed",false)):
		_show_recovery()
	else:
		_close_modal()


func _show_recovery() -> void:
	if _busy or not started:
		return
	var snap: Dictionary = _snapshot()
	var failed: bool = bool(snap.get("failed",false))
	var failure_view: Dictionary = _failure_presentation(snap)
	var outcome_copy: String = str(failure_view.get("copy",""))
	if not outcome_copy.is_empty():
		outcome_copy += "\n\n"
	if active_mode == CLASSIC:
		var recovery_copy: String = WEB_SAVE_NOTICE if OS.has_feature("web") else "本次挑战结束后，当前游戏中不能读档撤销失败。手动存档仍保留。"
		_open_modal("recovery", str(failure_view.get("title","从 F1 开始一座新塔？")), outcome_copy + "经典模式会换一个新种子，从 F1 重开。当前塔的资源、房间状态和选择全部重置。\n" + recovery_copy)
		var next_seed := LineEdit.new()
		next_seed.text = str((selected_seed % 4294967295) + 1)
		next_seed.placeholder_text = "新的塔种子"
		next_seed.custom_minimum_size.y = 40
		overlay_box.add_child(next_seed)
		_button(overlay_box,"经典重开 · 从 F1 开始",func():
			if not next_seed.text.is_valid_int():
				_message("请输入有效的新塔种子。")
				return
			var seed: int = int(next_seed.text)
			if seed < 1 or seed > 4294967295:
				_message("新塔种子范围为 1 至 4294967295。")
				return
			var result: Dictionary = await _commit(Callable(rules,"restart_classic").bind(seed,true,_failure_id(snap)))
			if bool(result.get("ok",false)):
				selected_seed = seed
				selected = []
				_last_delta = {}
				_close_modal()
				_refresh()
				_message("新塔已从 F1 开始，全部资源、库存、线索与房间状态已重置。")
		)
	else:
		_open_modal("recovery",str(failure_view.get("title","回到已到达的楼层记录点？")),outcome_copy + "练习模式会恢复记录点当时的完整世界。之后获得或消耗的生命、钥匙、金币、库存与线索全部回退；保留同一座塔和同一布局。")
		if OS.has_feature("web"): overlay_box.add_child(_label(WEB_SAVE_NOTICE,14,MUTED,true))
		var checkpoints: Array = snap.get("checkpoints",[])
		var checkpoint_choice := OptionButton.new()
		checkpoint_choice.custom_minimum_size.y = 44
		overlay_box.add_child(checkpoint_choice)
		for checkpoint: Dictionary in checkpoints:
			var id: String = str(checkpoint.get("id",""))
			if id.is_empty():
				continue
			var caption: String = "F%d · %s" % [int(checkpoint.get("floor_id",0)),str(checkpoint.get("label","已到达的记录点"))]
			checkpoint_choice.add_item(caption)
			checkpoint_choice.set_item_metadata(checkpoint_choice.item_count-1,id)
		var return_button := _button(overlay_box,"完整回溯至所选记录点",func():
			if checkpoint_choice.selected >= 0:
				_restore_checkpoint(str(checkpoint_choice.get_selected_metadata()),_failure_id(snap))
		)
		return_button.disabled = checkpoint_choice.item_count == 0
		if checkpoints.is_empty():
			overlay_box.add_child(_label("尚无可用的楼层记录点。",16,MUTED,true))
	if not failed:
		_button(overlay_box,"保留当前塔",_close_modal)
	_button(overlay_box,"选择模式",_show_modes)


func _failure_id(snap: Dictionary) -> String:
	return str(snap.get("failure",{}).get("failure_id",snap.get("failure_id","")))


func _failure_presentation(snap: Dictionary) -> Dictionary:
	if not bool(snap.get("failed",false)):
		return {}
	var failure: Dictionary = snap.get("failure",{})
	var kind: String = str(failure.get("kind",""))
	if kind == "combat_death":
		var combat: Dictionary = failure.get("combat",{})
		return {"kind":kind,"title":"战斗失败", "copy":"进入战斗时生命为 %d。本次战斗造成 %s 点伤害，挑战已结束；终战生命记录为 %s。" % [int(rules.state.get("hp",0)),str(combat.get("damage","未记录")),str(failure.get("terminal_hp","未记录"))]}
	if kind == "abandoned":
		return {"kind":kind,"title":"你已结束本次挑战", "copy":"你选择结束本次挑战，结束时还保有 %d 点生命。" % int(rules.state.get("hp",0))}
	return {"kind":kind,"title":"本次挑战已结束", "copy":"请选择下方的重开或回溯方式。"}


func _classic_failed() -> bool:
	return started and active_mode == CLASSIC and rules.is_failed()


func _restore_checkpoint(id: String, failure_id: String) -> void:
	if _input_locked(): return
	var result: Dictionary = await _commit(Callable(rules,"restore_checkpoint").bind(id,true,failure_id))
	if bool(result.get("ok",false)):
		selected = []
		_close_modal()
		_refresh()
	_message("已完整回到记录点，之后的拾取、购买和世界变化已撤销。" if bool(result.get("ok",false)) else _result_text(result,{},{}))


func _pause() -> void:
	if _input_locked(): return
	var pause_copy: String = WEB_SAVE_NOTICE + "当前打开期间，你可上下楼回访；门、怪物和补给保留当前状态。" if OS.has_feature("web") else "离开前请保存。你可上下楼回访；门、怪物和补给保留当前状态。"
	_open_modal("pause","灯下歇一会儿", pause_copy)
	_button(overlay_box,"返回塔内",_close_modal).call_deferred("grab_focus")
	var save_button: Button = _button(overlay_box,"保存当前塔",_save_slot)
	if OS.has_feature("web"): save_button.tooltip_text = WEB_SAVE_NOTICE
	_button(overlay_box,"重开 / 回溯",_show_recovery)
	_button(overlay_box,"结束本次挑战",func(): _confirm("确认结束本次挑战？","经典模式需要换新塔重开；练习模式可回到已到达的记录点。这会记为你主动结束本次挑战。",_end_run))
	_button(overlay_box,"选择模式",_show_modes)


func _end_run() -> void:
	if _input_locked(): return
	_close_modal()
	await _commit(Callable(rules,"give_up").bind(true))


func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	if event.physical_keycode == KEY_ESCAPE and started:
		_cancel_keyboard("escape")
		if _input_locked():
			_cancel_route = true
			_pause_when_idle = true
			_message("当前格完成后停步并暂停，不再执行后续路径。")
		elif modal_kind == "":
			_pause()
		elif not bool(_snapshot().get("failed",false)):
			_close_modal()
		get_viewport().set_input_as_handled()
		return
	if not started or modal_kind != "":
		return
	var bit: int = _direction_bit(event.physical_keycode)
	if bit != 0:
		if not _keyboard_context_allowed():
			_cancel_keyboard("ui_focus")
			return
		if _input_locked() and not _keyboard_driver_busy and not _route_running:
			_cancel_keyboard("busy_interaction")
		else:
			var now: int = Time.get_ticks_msec()
			_keyboard.sync_physical(_physical_direction_mask(),now)
			_keyboard.press(bit,now)
			if _input_locked() and int(_keyboard.debug_state().get("pending_count",0)) > 0:
				_message("已记住下一个方向；只保留一步，Esc 可取消。")
			if _route_running: _cancel_route = true
			_pump_keyboard()
		get_viewport().set_input_as_handled()
	elif event.physical_keycode in [KEY_E,KEY_SPACE,KEY_ENTER]:
		_cancel_keyboard("confirm_edge")
		if not _keyboard_context_allowed(): return
		if not _input_locked():
			_confirm_target()
		else:
			_message("移动中不接受确认；请停步后重新按键。")
		get_viewport().set_input_as_handled()


func view_status() -> Dictionary:
	return {"presentation_revision":EXPERIENCE_REVISION,"keyboard_controller":_keyboard.debug_state(),"started":started,"selected_mode":selected_mode,"active_mode":active_mode,"mode_required":true,"start_disabled":start_button.disabled if is_instance_valid(start_button) else true,"content_ready":content_ready,"authored_floors":10,"target_floors":50,"unmade_floors":[11,50],"modal":modal_kind,"visual_review":"not-tested","real_input":"not-tested"}
