extends SceneTree
const Main = preload("res://scripts/main.gd")
var game: Node3D
func _init() -> void: call_deferred("run")
func run() -> void:
	game = Node3D.new()
	game.set_script(Main)
	root.add_child(game)
	game.qa_enabled = true
	game.save_path = "user://qa-native-interface.json"
	for suffix in ["", ".bak", ".tmp"]:
		if FileAccess.file_exists(game.save_path+suffix): DirAccess.remove_absolute(ProjectSettings.globalize_path(game.save_path+suffix))
	assert(game.expedition.state == "title" and game.ui.modal.visible)
	var font: Font = game.ui.root.theme.default_font
	assert(font != null and not font.allow_system_fallback)
	for language in game.ui.COPY:
		for text in game.ui.COPY[language].values():
			for character in String(text):
				if character.unicode_at(0)>32 and not font.has_char(character.unicode_at(0)):
					push_error("Bundled font missing U+%04X %s" % [character.unicode_at(0), character])
					quit(1)
					return
	game._on_action("start")
	assert(game.expedition.state=="playing" and game.courier.enabled)
	game._on_action("touch")
	await process_frame
	await process_frame
	var button: Button = game.ui.touch_controls.get_node("TouchDirectionPad/TouchUp")
	var touch := InputEventScreenTouch.new()
	touch.index=1; touch.position=button.get_global_rect().get_center(); touch.pressed=true
	game.ui._input(touch)
	assert(game.courier.touch_axis.length()>0.0,"Native touch direction uses the same controller")
	touch.pressed=false; touch.canceled=true
	game.ui._input(touch)
	assert(game.courier.touch_axis==Vector2.ZERO,"Canceled finger releases movement")
	game.courier.touch_axis=Vector2.LEFT
	game._on_action("pause")
	assert(game.courier.touch_axis==Vector2.ZERO and not game.courier.enabled)
	game._on_action("sfx")
	assert(AudioServer.is_bus_mute(0) and not game.sfx_enabled)
	game._on_action("sfx")
	assert(not AudioServer.is_bus_mute(0) and game.sfx_enabled)
	var elapsed: float=game.expedition.elapsed
	for index in range(10): await physics_frame
	assert(game.expedition.elapsed==elapsed)
	game._on_action("pause")
	game._on_action("bag")
	assert(game.bag_open and not game.courier.enabled and game.ui.bag_visible)
	game._on_action("language")
	assert(game.ui.locale=="zh" and game.ui.bag_visible)
	game._on_action("touch")
	assert(game.ui.bag_visible,"Touch toggle cannot hide a suspended inventory")
	game._on_action("bag")
	game._notification(Main.NOTIFICATION_APPLICATION_FOCUS_OUT)
	assert(game.expedition.state=="paused","Focus loss suspends the expedition")
	game._on_action("menu")
	game._on_action("mood")
	assert(game.mood=="moon" and game.expedition.state=="title")
	for action in ["melee","skill","interact","inventory","dash"]:
		assert(InputMap.has_action(action))
	print("RELIC_NATIVE_TESTS_PASS: actual native UI transitions, bundled font coverage, touch/cancel, pause, inventory, focus-loss handler, bilingual and mood; no OS-input claim")
	for voice in game.audio_voices:
		voice.stop(); voice.stream=null
	OS.delay_msec(75)
	game.queue_free()
	await process_frame
	await process_frame
	quit(0)
