extends SceneTree
const Interface = preload("res://scripts/interface.gd")
var ui: CanvasLayer
var actions: Array[String] = []
var checks := 0
var failures: Array[String] = []

func _init() -> void:
	call_deferred("run")

func expect(value: bool, message: String) -> void:
	checks += 1
	if not value: failures.append(message)

func stats() -> Dictionary:
	return {"health": 30, "max_health": 40, "mana": 10, "max_mana": 20,
		"level": 1, "xp": 0, "zone": "wilderness", "quest_complete": false,
		"unlocked_skills": ["melee", "arc_bolt"], "cooldowns": {"melee": 0.0, "arc_bolt": 0.0}}

func settled() -> void:
	var previous := []
	var stable := 0
	for frame in range(16):
		await process_frame
		var current := [ui.footer.get_global_rect(), ui.modal_box.get_global_rect(),
			ui.touch_controls.get_node("TouchActions").get_global_rect()]
		stable = stable + 1 if current == previous else 0
		previous = current
		if stable >= 2: return
	expect(false, "UI rectangles did not settle")

func check_bounds(dimensions: Vector2i) -> void:
	for control in ui.root.find_children("*", "Control", true, false):
		if not control.is_visible_in_tree(): continue
		var rect: Rect2 = control.get_global_rect()
		expect(rect.position.x >= -0.5 and rect.position.y >= -0.5 and
			rect.end.x <= dimensions.x + 0.5 and rect.end.y <= dimensions.y + 0.5,
			"Visible control outside supported viewport: " + str(control.get_path()))
		if control is Button:
			expect(rect.size.y >= 44.0, "Action hit region is shorter than44px")

func run() -> void:
	root.size = Vector2i(1280, 720)
	root.content_scale_size = root.size
	ui = Interface.new()
	root.add_child(ui)
	ui.action_requested.connect(func(action): actions.append(action))
	await settled()
	if ui.root.find_child("SkillBar", true, false) == null:
		print("RELIC_SKILL_UI_REVISION_RED: Melee and Arc lack persistent native skill controls")
		quit(1)
		return
	var current := stats()
	ui.show_state("playing", current)
	ui.update_game(current, 0.0, "", false)
	await settled()
	expect(ui.skill_bar.is_visible_in_tree(), "Desktop skills are hidden during play")
	expect(ui.skill_buttons.melee.text.contains("F / CLICK") and ui.skill_buttons.arc_bolt.text.begins_with("Q"), "Skill controls omit actual bindings")
	expect(ui.bars.health.value == 30 and ui.bars.health.max_value == 40, "HP bar differs from actual stats")
	expect(ui.bars.mana.value == 10 and ui.bars.mana.max_value == 20, "Mana bar differs from actual stats")
	expect(not ui.skill_buttons.melee.disabled and not ui.skill_buttons.arc_bolt.disabled, "Ready wilderness skills are disabled")
	current.skill_context = {"arc_bolt": {"reason": "no_mana", "mana_cost": 8.0, "range": 9.0}}
	ui.update_game(current, 0.0, "", false)
	expect(ui.skill_buttons.arc_bolt.disabled and ui.skill_buttons.arc_bolt.text.contains("LOW MANA"), "Low mana has no visible unavailable state")
	current.skill_context.arc_bolt = {"cooldown": 2.4, "mana_cost": 8.0, "range": 9.0}
	ui.update_game(current, 0.0, "", false)
	expect(ui.skill_buttons.arc_bolt.disabled and ui.skill_buttons.arc_bolt.text.contains("2.4s"), "Cooldown does not update the actual button")
	current.skill_context.arc_bolt.cooldown = 0.0
	current.mana = 2
	ui.update_game(current, 0.0, "", false)
	expect(ui.skill_buttons.arc_bolt.disabled and ui.skill_buttons.arc_bolt.text.contains("LOW MANA"), "Fallback mana gate ignores a supplied ability cost")
	current.mana = 10
	current.skill_context = {"arc_bolt": {"reason": "out_of_range", "range": 9.0}}
	ui.update_game(current, 0.0, "", false)
	expect(not ui.skill_buttons.arc_bolt.disabled and ui.skill_buttons.arc_bolt.text.contains("OUT OF RANGE"), "Target failure is not visible or cannot reach authoritative failure feedback")
	ui.skill_buttons.arc_bolt.pressed.emit()
	expect(actions == ["skill"], "Arc button does not use the existing action signal")
	actions.clear()
	current.unlocked_skills = ["melee"]
	current.skill_context = {}
	ui.update_game(current, 0.0, "", false)
	expect(ui.skill_buttons.arc_bolt.disabled and ui.skill_buttons.arc_bolt.text.contains("EQUIP FOCUS"), "Locked Arc lacks the actual unlock requirement")
	for dimensions in [Vector2i(1280, 720), Vector2i(960, 600)]:
		root.size = dimensions
		root.content_scale_size = dimensions
		for language in ["en", "zh"]:
			ui.locale = language
			ui.touch_visible = false
			ui.show_state("playing", current)
			ui.update_game(current, 0.0, "", false)
			await settled()
			check_bounds(dimensions)
			ui.touch_visible = true
			ui.show_state("playing", current)
			ui.update_game(current, 0.0, "", false)
			await settled()
			check_bounds(dimensions)
			expect(not ui.skill_bar.is_visible_in_tree(), "Touch duplicates the desktop skill hit regions")
			var touch_arc: Button = ui.touch_controls.get_node("TouchActions/TouchSkill")
			expect(touch_arc.disabled and ui._touch_button_at(touch_arc.get_global_rect().get_center()) == null, "Disabled touch skill can still emit an action")
			expect(ui.footer.get_global_rect().end.y + 4.0 <= ui.touch_controls.get_node("TouchActions").get_global_rect().position.y,
				"Touch action pad covers the objective/status footer")
			ui.show_state("paused", current)
			await settled()
			check_bounds(dimensions)
			expect(not ui.skill_bar.is_visible_in_tree() and not ui.touch_controls.visible, "Pause leaves live skill hit regions")
			var completed := current.duplicate(true)
			completed.quest_complete = true
			completed.save_available = true
			var before := JSON.stringify(completed)
			ui.show_state("title", completed)
			await settled()
			check_bounds(dimensions)
			expect(ui.modal_box.get_node("PrimaryAction").text == ui.t("continue_complete"), "Completed save looks like a fresh expedition")
			expect(ui.modal_box.get_node("ScreenDescription").text == ui.t("expedition_complete"), "Completed save does not explain its cleared expedition")
			ui.modal_box.get_node("NewExpedition").pressed.emit()
			await settled()
			check_bounds(dimensions)
			expect(actions.is_empty() and ui.confirming_new, "New expedition mutates domain before confirmation")
			expect(root.gui_get_focus_owner() == ui.modal_box.get_node("CancelNewExpedition"), "New-expedition confirmation does not default to keeping current progress")
			ui.change_locale()
			await settled()
			expect(ui.confirming_new and ui.modal_box.has_node("CancelNewExpedition"), "Locale change silently clears a pending new-expedition decision")
			ui.modal_box.get_node("CancelNewExpedition").pressed.emit()
			expect(actions.is_empty() and JSON.stringify(completed) == before, "Cancel changes current expedition data")
			ui.modal_box.get_node("NewExpedition").pressed.emit()
			var confirm: Button = ui.modal_box.get_node("ConfirmNewExpedition")
			confirm.pressed.emit()
			confirm.pressed.emit()
			expect(actions == ["new_expedition"] and JSON.stringify(completed) == before, "Confirmed new expedition must emit once without modifying save data in UI")
			actions.clear()
			ui.show_state("title", {"save_available": false})
			await settled()
			expect(ui.modal_box.get_node("PrimaryAction").disabled and root.gui_get_focus_owner() == ui.modal_box.get_node("NewExpedition"), "No-save title focuses an unavailable Continue action")
	if not failures.is_empty():
		print("RELIC_SKILL_UI_REVISION_FAIL: ", JSON.stringify(failures))
		ui.queue_free()
		quit(1)
		return
	print("RELIC_SKILL_UI_REVISION_PASS: %d native state/signal/settled-layout checks" % checks)
	print("RELIC_SKILL_UI_SCOPE: headless Control properties and direct signal contracts; no rendered pixels, physical input or gameplay acceptance")
	ui.queue_free()
	quit(0)
