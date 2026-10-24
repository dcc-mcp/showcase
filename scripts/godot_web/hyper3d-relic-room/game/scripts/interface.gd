extends CanvasLayer
signal action_requested(action: String)
signal touch_changed(axis: Vector2)

const COPY := {
 "en": {
 "sfx_on":"SFX ON", "sfx_off":"SFX OFF", "brand":"RELIC / COURIER", "tag":"THE SUNKEN ARCHIVE", "title":"Beyond the
archive gate.",
 "intro":"Search the grove for a lost arc focus. Read the wardens' windup, recover their spoils, and return prepared. The old chest may hold an edge.",
 "continue_complete":"EXPLORE WITH YOUR GEAR", "expedition_complete":"Expedition complete. Your gear and discoveries are saved.", "start":"CONTINUE EXPEDITION", "resume":"CONTINUE", "retry":"RETURN TO SAFETY", "menu":"SAVE & RETURN TO TITLE",
 "paused":"Take a breath.", "pause_copy":"The world is paused. Your progress is kept when you recover loot or equip gear.",
 "won":"A way forward.", "win_copy":"The grove is clear. Your focus and blade are ready for the next expedition.",
 "lost":"Return with what you learned.", "lose_copy":"Your recovered gear is safe. Continue in town and read the next attack before it lands.",
 "controls":"WASD / arrows MOVE · SPACE DASH · F / click ATTACK
Q ARC · E INTERACT · I BAG · ESC PAUSE",
 "objective":"Pass the rear gate. Recover the focus, equip your finds, then return.", "return":"The expedition is ready. Return to the turquoise beacon and press E.",
 "health":"HEALTH", "mana":"MANA", "level":"LEVEL", "ready":"DASH READY", "dash":"DASH", "interact":"USE", "melee":"ATTACK", "skill":"ARC", "bag":"BAG", "close_bag":"CLOSE BAG",
 "warm":"AMBER", "moon":"MOONLIGHT", "pause":"PAUSE", "touch":"TOUCH", "exhibit_title":"THE SUNKEN ARCHIVE", "placeholder":"Required expedition assets are not ready.",
 "pickup":"E  RECOVER LOOT", "turn_in":"E  COMPLETE EXPEDITION", "town_hint":"Find both wardens' spoils and equip focus + blade before returning.",
 "open_chest":"E  OPEN THE OLD CHEST", "chest_opened":"CHEST EMPTIED · YOUR FINDS ARE SAVED", "chest_opening":"OPENING · STEP AWAY TO CANCEL", "chest_cancelled":"Opening cancelled. The contents remain untouched.",
 "warning":"WARDEN ATTACK · DASH OR STEP ASIDE", "safe":"TOWN / SAFE GROUND", "wilderness":"THE WARDEN GROVE", "town":"ARCHIVE COURT",
 "safe_town":"The archive court is safe. Combat begins beyond the rear gate.", "skill_locked":"Recover and equip the arc focus to unlock Q.", "cooldown":"Recovering. Wait for the action to ready.", "no_mana":"Not enough mana. Let your focus recover.", "whiff":"The strike found no target.", "blocked":"Stone blocks the strike. Find a clear angle.", "out_of_range":"Too far. Close the distance.", "already_owned":"This duplicate find is cleared. Your equipped gear is unchanged.", "picked_up":"Loot recovered. Open I / BAG to equip it.",
 "fall_recovered":"Back on safe ground. Your recovered gear is intact.", "save_loaded":"Expedition restored safely in town.", "save_invalid":"The save could not be verified. A clean expedition is ready.", "save_failed":"Progress could not be saved. Keep this session open.", "assets_pending":"Required authored action is not ready.",
 "scout":"GROVE SCOUT", "sentinel":"ARCHIVE SENTINEL", "inventory":"FIELD SATCHEL", "inventory_hint":"The world waits while you inspect your gear. Equipped focus unlocks Arc; a bronze edge strengthens your strike.",
 "arc_focus":"ARC FOCUS", "bronze_edge":"BRONZE EDGE", "focus_copy":"Focus · +10 mana · unlocks Arc (Q)", "blade_copy":"Weapon · +5 melee damage", "equip":"EQUIP", "equipped":"EQUIPPED", "not_found":"NOT RECOVERED", "quest":"WARDENS", "saved":"Progress saves after loot and equipment.",
 "skill_ready":"READY", "skill_focus":"EQUIP FOCUS", "skill_mana":"LOW MANA", "skill_safe":"SAFE GROUND", "skill_target":"NO TARGET", "skill_range":"OUT OF RANGE", "skill_blocked":"BLOCKED", "skill_action":"ACTING", "skill_pending":"ACTION NOT READY", "action_busy":"An action is in progress. Wait for its recovery.", "range":"RANGE",
 "new_expedition":"NEW EXPEDITION", "new_title":"Leave the old path?", "new_copy":"A new expedition starts without gear and restores the wardens. Your current expedition changes only after confirmation.", "new_confirm":"START NEW EXPEDITION", "cancel":"KEEP CURRENT EXPEDITION"
 },
 "zh": {
 "sfx_on":"音效开", "sfx_off":"音效关", "brand":"遗迹 / 信使", "tag":"沉没档案馆", "title":"穿过档案馆，
踏入荒野。",
 "intro":"去林地寻找失落的奥术核心。看清守卫蓄势，收取战利品，整装后返回。古老宝箱里也许藏着一柄利刃。",
 "continue_complete":"携带装备，自由探索", "expedition_complete":"探险已完成，装备与发现均已保存。", "start":"继续探险", "resume":"继续", "retry":"返回安全地带", "menu":"保存并返回标题",
 "paused":"歇一口气。", "pause_copy":"世界已暂停。收取战利品或装备后会保存进度。",
 "won":"前路已经打开。", "win_copy":"林地恢复平静。核心与利刃已备好，等待下一次远行。",
 "lost":"带着经验，再次出发。", "lose_copy":"已经收取的装备仍然安全。回到城镇，看清下一次攻击再行动。",
 "controls":"WASD / 方向键 移动 · 空格 冲刺 · F / 点击 攻击
Q 奥术 · E 交互 · I 背包 · ESC 暂停",
 "objective":"穿过后方大门，回收核心，装备所得，再返回信标。", "return":"探险目标已完成。回到青绿色信标并按 E。",
 "health":"生命", "mana":"法力", "level":"等级", "ready":"冲刺就绪", "dash":"冲刺", "interact":"交互", "melee":"攻击", "skill":"奥术", "bag":"背包", "close_bag":"关闭背包",
 "warm":"琥珀", "moon":"月色", "pause":"暂停", "touch":"触控", "exhibit_title":"沉没档案馆", "placeholder":"探险所需模型尚未齐备。",
 "pickup":"E  收取战利品", "turn_in":"E  完成探险", "town_hint":"找齐两名守卫的战利品，装备核心与利刃后返回。",
 "open_chest":"E  打开古老宝箱", "chest_opened":"宝箱已空 · 所得已保存", "chest_opening":"开启中 · 走开可取消", "chest_cancelled":"开启已取消，宝物仍在箱中。",
 "warning":"守卫出招 · 冲刺或侧移", "safe":"城镇 / 安全地带", "wilderness":"守卫林地", "town":"档案馆庭院",
 "safe_town":"庭院是安全地带。穿过后方大门才能交战。", "skill_locked":"回收并装备奥术核心，解锁 Q。", "cooldown":"正在恢复，请等待动作就绪。", "no_mana":"法力不足，稍候即可恢复。", "whiff":"攻击没有命中目标。", "blocked":"石墙挡住攻击，请换一个角度。", "out_of_range":"距离太远，请靠近。", "already_owned":"重复战利品已收妥，已有装备保持不变。", "picked_up":"已收取战利品，打开 I / 背包装备。",
 "fall_recovered":"已返回安全地带，所得装备仍然完好。", "save_loaded":"探险进度已恢复，当前位于安全庭院。", "save_invalid":"存档未通过校验，已准备全新探险。", "save_failed":"进度保存失败，请暂时保留本次游戏。", "assets_pending":"所需动作尚未齐备。",
 "scout":"林地斥候", "sentinel":"档案馆卫士", "inventory":"行囊", "inventory_hint":"查看装备时世界会等待。装备核心可使用奥术，青铜刃可增强近战。",
 "arc_focus":"奥术核心", "bronze_edge":"青铜刃", "focus_copy":"核心 · 法力 +10 · 解锁奥术 Q", "blade_copy":"武器 · 近战伤害 +5", "equip":"装备", "equipped":"已装备", "not_found":"尚未收取", "quest":"守卫", "saved":"收取与装备后自动保存。",
 "skill_ready":"就绪", "skill_focus":"装备核心", "skill_mana":"法力不足", "skill_safe":"安全地带", "skill_target":"没有目标", "skill_range":"距离太远", "skill_blocked":"攻击被挡住", "skill_action":"动作中", "skill_pending":"动作尚未齐备", "action_busy":"动作中，请等待动作恢复。", "range":"距离",
 "new_expedition":"全新探险", "new_title":"再次出发？", "new_copy":"全新探险从没有装备开始，守卫会重新出现。确认后才会重置当前探险。", "new_confirm":"开始全新探险", "cancel":"保留当前探险"
 }
}
const SKILL_REASON_COPY := {
	"skill_locked": "skill_focus", "no_mana": "skill_mana", "safe_town": "skill_safe",
	"whiff": "skill_target", "out_of_range": "skill_range", "blocked": "skill_blocked",
	"assets_pending": "skill_pending", "busy": "skill_action", "windup": "skill_action",
	"recovery": "skill_action", "paused": "pause"
}
const BLOCKING_SKILL_REASONS := [
	"skill_locked", "cooldown", "no_mana", "safe_town", "assets_pending",
	"busy", "windup", "recovery", "paused"
]
var locale := "en"
var state := "title"
var mood := "warm"
var sfx_on := true
var root: Control
var modal: ColorRect
var modal_box: VBoxContainer
var hud: HBoxContainer
var hint: Label
var note: Label
var status: Label
var footer: PanelContainer
var header: HBoxContainer
var brand: Label
var mood_button: Button
var language_button: Button
var pause_button: Button
var touch_button: Button
var touch_controls: Control
var touch_held := {}
var touch_fingers := {}
var touch_visible := false
var labels := {}
var missing_assets := 0
var bag_button: Button
var latest_stats := {}
var bag_visible := false
var skill_bar: HBoxContainer
var skill_buttons := {}
var bars := {}
var touch_clearance: Control
var confirming_new := false

func _ready() -> void:
	root = Control.new()
	root.name = "NativeInterface"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	root.theme = _theme()
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 26)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 15)
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_child(column)
	header = HBoxContainer.new()
	header.add_theme_constant_override("separation", 10)
	column.add_child(header)
	brand = _label("", 23)
	brand.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(brand)
	mood_button = _button("", "mood", "MoodButton")
	language_button = _button("中文", "language", "LanguageButton")
	touch_button = _button("", "touch", "TouchToggle")
	pause_button = _button("", "pause", "PauseButton")
	bag_button = _button("", "bag", "BagButton")
	for control in [mood_button, language_button, touch_button, bag_button, pause_button]:
		header.add_child(control)
	hud = HBoxContainer.new()
	hud.add_theme_constant_override("separation", 12)
	column.add_child(hud)
	for key in ["health", "mana", "level"]:
		var panel := PanelContainer.new()
		panel.custom_minimum_size = Vector2(132, 54)
		panel.add_theme_stylebox_override("panel", _stat_style())
		var contents := VBoxContainer.new()
		contents.add_theme_constant_override("separation", 4)
		contents.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		panel.add_child(contents)
		var value := _label("", 18)
		value.name = key.capitalize() + "Status"
		value.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		contents.add_child(value)
		if key in ["health", "mana"]:
			var bar := ProgressBar.new()
			bar.name = key.capitalize() + "Bar"
			bar.custom_minimum_size.y = 6
			bar.show_percentage = false
			bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
			var background := StyleBoxFlat.new()
			background.bg_color = Color("0b1c24")
			background.set_corner_radius_all(3)
			var fill := background.duplicate() as StyleBoxFlat
			fill.bg_color = Color("e79c7a") if key == "health" else Color("74d5cf")
			bar.add_theme_stylebox_override("background", background)
			bar.add_theme_stylebox_override("fill", fill)
			contents.add_child(bar)
			bars[key] = bar
		hud.add_child(panel)
		labels[key] = value
	status = _label("", 15, Color("eacb85"))
	status.name = "GuardianStatus"
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	var warning_panel := PanelContainer.new()
	warning_panel.name = "GuardianPanel"
	warning_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	warning_panel.add_theme_stylebox_override("panel", _stat_style())
	warning_panel.add_child(status)
	hud.add_child(warning_panel)
	var spacer := Control.new()
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(spacer)
	footer = PanelContainer.new()
	footer.name = "FieldStudyPanel"
	footer.custom_minimum_size.x = 620
	footer.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	var footer_style := StyleBoxFlat.new()
	footer_style.bg_color = Color(0.025, 0.07, 0.085, 0.94)
	footer_style.set_corner_radius_all(6)
	footer_style.content_margin_left = 16
	footer_style.content_margin_right = 16
	footer_style.content_margin_top = 10
	footer_style.content_margin_bottom = 10
	footer.add_theme_stylebox_override("panel", footer_style)
	column.add_child(footer)
	var footer_text := VBoxContainer.new()
	footer_text.add_theme_constant_override("separation", 4)
	footer.add_child(footer_text)
	skill_bar = HBoxContainer.new()
	skill_bar.name = "SkillBar"
	skill_bar.add_theme_constant_override("separation", 10)
	footer_text.add_child(skill_bar)
	for skill in ["melee", "arc_bolt"]:
		var button := _button("", "melee" if skill == "melee" else "skill", "MeleeSkill" if skill == "melee" else "ArcSkill")
		button.custom_minimum_size = Vector2(240, 62)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.add_theme_font_size_override("font_size", 15)
		skill_bar.add_child(button)
		skill_buttons[skill] = button
	hint = _label("", 21, Color("a2fff0"))
	hint.name = "InteractionPrompt"
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	footer_text.add_child(hint)
	note = _label("", 15)
	note.name = "Objective"
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	footer_text.add_child(note)
	touch_clearance = Control.new()
	touch_clearance.name = "TouchClearance"
	touch_clearance.custom_minimum_size.y = 170
	touch_clearance.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(touch_clearance)
	modal = ColorRect.new()
	modal.name = "ModalBackdrop"
	modal.color = Color(0.02, 0.04, 0.07, 0.50)
	modal.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	modal.offset_top = 82
	root.add_child(modal)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_PASS
	modal.add_child(center)
	var panel := PanelContainer.new()
	panel.name = "ScreenPanel"
	panel.custom_minimum_size = Vector2(550, 0)
	center.add_child(panel)
	modal_box = VBoxContainer.new()
	modal_box.add_theme_constant_override("separation", 12)
	panel.add_child(modal_box)
	_make_touch_controls()
	_refresh_header()
	show_state("title")

func t(key: String) -> String:
	return COPY[locale].get(key, key)

func _theme() -> Theme:
	var result := Theme.new()
	var font = load("res://ui/relic-sans.otf")
	if font:
		font.allow_system_fallback = false
		result.default_font = font
	result.default_font_size = 17
	result.set_color("font_color", "Label", Color("e9eee7"))
	result.set_color("font_color", "Button", Color("d8efe8"))
	result.set_color("font_hover_color", "Button", Color("ffffff"))
	for kind in ["normal", "hover", "pressed", "disabled", "focus"]:
		var style := StyleBoxFlat.new()
		style.bg_color = Color("133136") if kind == "normal" else Color("24565b")
		if kind == "disabled":
			style.bg_color = Color("182126")
		style.border_color = Color("edca8a") if kind == "focus" else Color("3e7879")
		style.set_border_width_all(2 if kind == "focus" else 1)
		style.set_corner_radius_all(5)
		style.content_margin_left = 18
		style.content_margin_right = 18
		style.content_margin_top = 10
		style.content_margin_bottom = 10
		result.set_stylebox(kind, "Button", style)
	var panel := StyleBoxFlat.new()
	panel.bg_color = Color(0.035, 0.085, 0.105, 0.95)
	panel.border_color = Color("497a7a")
	panel.set_border_width_all(1)
	panel.set_corner_radius_all(8)
	panel.content_margin_left = 26
	panel.content_margin_right = 26
	panel.content_margin_top = 22
	panel.content_margin_bottom = 22
	result.set_stylebox("panel", "PanelContainer", panel)
	return result

func _label(text: String, size: int, color := Color("e9eee7")) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label

func _stat_style() -> StyleBoxFlat:
	var style := root.theme.get_stylebox("panel", "PanelContainer").duplicate() as StyleBoxFlat
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 9
	style.content_margin_bottom = 9
	return style

func _button(text: String, action: String, node_name: String) -> Button:
	var button := Button.new()
	button.name = node_name
	button.text = text
	button.custom_minimum_size.y = 44
	button.set_meta("action", action)
	button.pressed.connect(func(): _request_action(action))
	return button

func _request_action(action: String) -> void:
	match action:
		"ask_new_expedition": _show_new_confirmation()
		"cancel_new_expedition": show_state("title", latest_stats)
		"new_expedition":
			if not confirming_new: return
			confirming_new = false
			action_requested.emit(action)
		_: action_requested.emit(action)

func _show_new_confirmation() -> void:
	if state != "title": return
	confirming_new = true
	_clear_modal()
	modal_box.add_child(_label(t("new_title"), 30, Color("faf1d9")))
	var description := _label(t("new_copy"), 16)
	description.name = "NewExpeditionDescription"
	description.custom_minimum_size.x = 490
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	modal_box.add_child(description)
	modal_box.add_child(_button(t("new_confirm"), "new_expedition", "ConfirmNewExpedition"))
	var cancel := _button(t("cancel"), "cancel_new_expedition", "CancelNewExpedition")
	modal_box.add_child(cancel)
	call_deferred("_focus_primary", cancel)

func _refresh_header() -> void:
	brand.text = t("brand")
	mood_button.text = t(mood)
	language_button.text = "中文" if locale == "en" else "ENGLISH"
	touch_button.text = t("touch")
	pause_button.text = t("pause")
	bag_button.text = t("bag")

func show_state(next_state: String, stats := {}) -> void:
	state = next_state
	latest_stats = stats
	bag_visible = false
	confirming_new = false
	_refresh_header()
	modal.visible = state in ["title", "paused", "won", "lost"]
	hud.visible = state in ["playing", "paused"]
	pause_button.visible = state in ["playing", "paused"]
	bag_button.visible = state == "playing"
	touch_button.visible = state == "playing"
	mood_button.visible = state == "title"
	touch_controls.visible = touch_visible and state == "playing"
	footer.visible = state in ["playing", "exhibit"]
	touch_clearance.visible = touch_visible and state == "playing"
	skill_bar.visible = state == "playing" and not touch_visible
	_refresh_skills(stats)
	if not modal.visible:
		if state == "exhibit":
			note.text = t("objective")
			hint.text = t("exhibit_title")
		return
	_clear_modal()
	modal_box.add_child(_label(t("tag"), 12, Color("e8c68b")))
	var title_key: String = {"title":"title", "paused":"paused", "won":"won", "lost":"lost"}[state]
	var title := _label(t(title_key), 36, Color("faf1d9"))
	title.name = "ScreenTitle"
	modal_box.add_child(title)
	var copy_key: String = {"title":"intro", "paused":"pause_copy", "won":"win_copy", "lost":"lose_copy"}[state]
	var description := _label(t("expedition_complete") if state == "title" and stats.get("quest_complete", false) else t(copy_key), 16)
	description.name = "ScreenDescription"
	description.custom_minimum_size.x = 490
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	modal_box.add_child(description)
	var primary_key := "start"
	if state == "paused": primary_key = "resume"
	elif state == "won" or (state == "title" and stats.get("quest_complete", false)): primary_key = "continue_complete"
	elif state == "lost": primary_key = "retry"
	var primary := _button(t(primary_key), "pause" if state == "paused" else "start", "PrimaryAction")
	primary.disabled = missing_assets > 0
	if state == "title" and stats.has("save_available"):
		primary.disabled = primary.disabled or not bool(stats.save_available)
	primary.tooltip_text = t("placeholder") if missing_assets > 0 else ""
	modal_box.add_child(primary)
	var focus_target := primary
	if state == "title":
		var fresh := _button(t("new_expedition"), "ask_new_expedition", "NewExpedition")
		fresh.disabled = missing_assets > 0
		modal_box.add_child(fresh)
		if primary.disabled: focus_target = fresh
	if state == "paused": modal_box.add_child(_button(t("sfx_on" if sfx_on else "sfx_off"), "sfx", "SfxToggle"))
	if state != "title": modal_box.add_child(_button(t("menu"), "menu", "ReturnTitle"))
	var help_label := _label(t("controls"), 12, Color("a6b7b9"))
	help_label.name = "KeyboardHelp"
	modal_box.add_child(help_label)
	call_deferred("_focus_primary", focus_target)

func _clear_modal() -> void:
	for child in modal_box.get_children():
		modal_box.remove_child(child)
		child.queue_free()

func show_bag(stats: Dictionary) -> void:
	latest_stats = stats
	bag_visible = true
	modal.visible = true
	footer.visible = false
	touch_controls.visible = false
	touch_clearance.visible = false
	confirming_new = false
	_clear_modal()
	modal_box.add_child(_label(t("inventory"), 30, Color("faf1d9")))
	var description := _label(t("inventory_hint"), 15)
	description.custom_minimum_size.x = 490
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	modal_box.add_child(description)
	for id in ["arc_focus", "bronze_edge"]:
		var slot := "focus" if id == "arc_focus" else "weapon"
		var equipped: bool = stats.get("equipment", {}).get(slot, "") == id
		var owned: bool = id in stats.get("inventory", [])
		modal_box.add_child(_label(t(id) + " · " + t("focus_copy" if id == "arc_focus" else "blade_copy"), 16))
		var button := _button(t("equipped") if equipped else t("equip" if owned else "not_found"), "equip:" + id, "Equip" + id.capitalize().replace(" ", ""))
		button.disabled = equipped or not owned
		modal_box.add_child(button)
	modal_box.add_child(_label(t("saved"), 12, Color("a6b7b9")))
	var close := _button(t("close_bag"), "bag", "CloseBag")
	modal_box.add_child(close)
	call_deferred("_focus_primary", close)

func _focus_primary(button: Button) -> void:
	if is_instance_valid(button) and button.is_inside_tree() and not button.disabled:
		button.grab_focus()

func update_game(stats: Dictionary, cooldown: float, prompt: String, danger: bool) -> void:
	latest_stats = stats
	labels.health.text = "%s  %d / %d" % [t("health"), stats.get("health", 0), stats.get("max_health", 40)]
	labels.mana.text = "%s  %d / %d" % [t("mana"), stats.get("mana", 0), stats.get("max_mana", 20)]
	labels.level.text = "%s %d · XP %d" % [t("level"), stats.get("level", 1), stats.get("xp", 0)]
	for key in ["health", "mana"]:
		bars[key].max_value = maxf(1.0, float(stats.get("max_" + key, 40 if key == "health" else 20)))
		bars[key].value = clampf(float(stats.get(key, 0)), 0.0, bars[key].max_value)
	_refresh_skills(stats)
	status.text = t("warning") if danger else t("wilderness" if stats.get("zone", "town") == "wilderness" else "safe")
	if stats.has("target") and not danger and stats.get("zone", "town") == "wilderness":
		status.text = "%s  %d / %d" % [t(stats.target.variant), stats.target.health, stats.target.max_health]
	status.add_theme_color_override("font_color", Color("ffad7d") if danger else Color("eacb85"))
	if state == "playing" and not bag_visible:
		hint.text = t(prompt) if prompt != "" else (t("ready") if cooldown <= 0 else "%s %.1fs" % [t("dash"), cooldown])
		note.text = t("expedition_complete") if stats.get("quest_complete", false) else (t("return") if stats.get("goal_ready", false) else t("objective"))

func _skill_display(skill: String, stats: Dictionary) -> Dictionary:
	var context: Dictionary = stats.get("skill_context", {}).get(skill, {})
	var remaining := maxf(0.0, float(context.get("cooldown", stats.get("cooldowns", {}).get(skill, 0.0))))
	var cost := float(context.get("mana_cost", 0.0))
	var reason := String(context.get("reason", ""))
	if reason == "":
		if skill == "arc_bolt" and skill not in stats.get("unlocked_skills", ["melee"]): reason = "skill_locked"
		elif remaining > 0.0: reason = "cooldown"
		elif float(stats.get("mana", 0.0)) < cost: reason = "no_mana"
		elif stats.get("zone", "town") != "wilderness": reason = "safe_town"
	var short_key := String(SKILL_REASON_COPY.get(reason, "skill_ready"))
	var detail := "%.1fs" % remaining if reason == "cooldown" else t(short_key)
	var reach := float(context.get("range", 0.0))
	if reach > 0.0: detail += " · %.1fm" % reach
	if cost > 0.0: detail += " · %d %s" % [cost, t("mana")]
	var key := "F / CLICK" if skill == "melee" else "Q"
	var label := t("melee" if skill == "melee" else "skill")
	var disabled := reason in BLOCKING_SKILL_REASONS
	var tooltip_key := "action_busy" if short_key == "skill_action" else reason
	return {"text": "%s  %s\n%s" % [key, label, detail], "tooltip": t(tooltip_key) if tooltip_key != "" else t("skill_ready"), "disabled": disabled, "reason": reason}

func _refresh_skills(stats: Dictionary) -> void:
	for skill in ["melee", "arc_bolt"]:
		var display := _skill_display(skill, stats)
		var button: Button = skill_buttons[skill]
		button.text = display.text
		button.tooltip_text = display.tooltip
		button.disabled = display.disabled or state != "playing"
		var touch_name := "TouchMelee" if skill == "melee" else "TouchSkill"
		var touch := touch_controls.get_node_or_null("TouchActions/" + touch_name) as Button
		if touch:
			touch.text = display.text.replace("F / CLICK", "F")
			touch.tooltip_text = display.tooltip
			touch.disabled = button.disabled

func change_locale() -> void:
	var keep_confirmation := confirming_new
	locale = "zh" if locale == "en" else "en"
	show_bag(latest_stats) if bag_visible else show_state(state, latest_stats)
	if keep_confirmation: _show_new_confirmation()
	_refresh_touch()

func clear_touch() -> void:
	touch_held.clear()
	touch_fingers.clear()
	touch_changed.emit(Vector2.ZERO)
	for button in touch_controls.find_children("*", "Button", true, false):
		button.set_pressed_no_signal(false)

func _input(event: InputEvent) -> void:
	if not touch_controls.visible or state != "playing":
		return
	if event is InputEventScreenTouch:
		var finger_key := "finger_%d" % event.index
		if event.pressed:
			var button := _touch_button_at(event.position)
			if button:
				touch_fingers[event.index] = button
				button.set_pressed_no_signal(true)
				_set_finger_direction(finger_key, button)
				get_viewport().set_input_as_handled()
		elif touch_fingers.has(event.index):
			var button: Button = touch_fingers[event.index]
			touch_fingers.erase(event.index)
			touch_held.erase(finger_key)
			button.set_pressed_no_signal(false)
			_emit_touch()
			if not event.canceled and not button.disabled and button.get_global_rect().has_point(event.position):
				if button.has_meta("action"):
					action_requested.emit(String(button.get_meta("action")))
			get_viewport().set_input_as_handled()
	elif event is InputEventScreenDrag and touch_fingers.has(event.index):
		var old: Button = touch_fingers[event.index]
		if old.name in ["TouchUp", "TouchDown", "TouchLeft", "TouchRight"]:
			var button := _touch_button_at(event.position)
			old.set_pressed_no_signal(false)
			touch_held.erase("finger_%d" % event.index)
			if button and button.name in ["TouchUp", "TouchDown", "TouchLeft", "TouchRight"]:
				touch_fingers[event.index] = button
				button.set_pressed_no_signal(true)
				_set_finger_direction("finger_%d" % event.index, button)
			else:
				_emit_touch()
		get_viewport().set_input_as_handled()

func _touch_button_at(point: Vector2) -> Button:
	for button in touch_controls.find_children("*", "Button", true, false):
		if button.is_visible_in_tree() and not button.disabled and button.get_global_rect().has_point(point):
			return button
	return null

func _set_finger_direction(key: String, button: Button) -> void:
	var directions := {"TouchUp": Vector2.UP, "TouchDown": Vector2.DOWN,
		"TouchLeft": Vector2.LEFT, "TouchRight": Vector2.RIGHT}
	if directions.has(String(button.name)):
		touch_held[key] = directions[String(button.name)]
	_emit_touch()

func _make_touch_controls() -> void:
	touch_controls = Control.new()
	touch_controls.name = "TouchControls"
	touch_controls.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	touch_controls.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(touch_controls)
	var directions := GridContainer.new()
	directions.name = "TouchDirectionPad"
	directions.columns = 3
	directions.grow_vertical = Control.GROW_DIRECTION_BEGIN
	directions.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	directions.position = Vector2(26, -26)
	touch_controls.add_child(directions)
	var values := {"↑": Vector2.UP, "←": Vector2.LEFT, "↓": Vector2.DOWN, "→": Vector2.RIGHT}
	for text in ["", "↑", "", "←", "↓", "→"]:
		if text == "":
			var blank := Control.new()
			blank.custom_minimum_size = Vector2(50, 50)
			blank.mouse_filter = Control.MOUSE_FILTER_IGNORE
			directions.add_child(blank)
			continue
		var button := Button.new()
		button.text = text
		button.name = "Touch" + {"↑": "Up", "←": "Left", "↓": "Down", "→": "Right"}[text]
		button.custom_minimum_size = Vector2(50, 50)
		button.button_down.connect(func(): touch_held[text] = values[text]; _emit_touch())
		button.button_up.connect(func(): touch_held.erase(text); _emit_touch())
		directions.add_child(button)
	var actions := GridContainer.new()
	actions.columns = 3
	actions.name = "TouchActions"
	actions.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	actions.grow_vertical = Control.GROW_DIRECTION_BEGIN
	actions.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	actions.position = Vector2(-26, -26)
	touch_controls.add_child(actions)
	for action in ["melee", "skill", "dash", "interact", "bag"]:
		var button := _button(t(action), action, "Touch" + action.capitalize())
		button.custom_minimum_size = Vector2(110, 62)
		button.add_theme_font_size_override("font_size", 14)
		actions.add_child(button)
	_refresh_touch()

func _refresh_touch() -> void:
	for button in touch_controls.get_node("TouchActions").get_children():
		button.text = t(String(button.get_meta("action")))
	_refresh_skills(latest_stats)

func _emit_touch() -> void:
	var axis := Vector2.ZERO
	for value in touch_held.values():
		axis += value
	touch_changed.emit(axis.limit_length())
