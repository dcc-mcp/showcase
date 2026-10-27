extends SceneTree
const Main = preload("res://scripts/main.gd")
var game: Node3D

func _init() -> void:
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(1280, 720)
	root.content_scale_size = Vector2i(1280, 720)
	game = Node3D.new()
	game.set_script(Main)
	root.add_child(game)
	game._on_action("start")
	game._on_action("touch")
	for frame in range(4):
		await process_frame
	var right: Button = game.ui.touch_controls.get_node("TouchDirectionPad/TouchRight")
	var dash: Button = game.ui.touch_controls.get_node("TouchActions/TouchDash")
	var right_point: Vector2 = right.get_global_rect().get_center()
	var dash_point: Vector2 = dash.get_global_rect().get_center()
	var before: Vector3 = game.courier.position
	_touch(0, right_point, true)
	for frame in range(8):
		await physics_frame
	assert(game.courier.position.distance_to(before) > 0.1, "Direction hold must move across frames")
	assert(game.courier.touch_axis == Vector2.RIGHT)
	_touch(1, dash_point, true)
	for frame in range(3):
		await physics_frame
	_touch(1, dash_point, false)
	await physics_frame
	assert(game.courier.cooldown > 0.0, "Second finger action must dash while first direction remains held")
	assert(game.courier.touch_axis == Vector2.RIGHT)
	_touch(0, right_point, false, true)
	await physics_frame
	assert(game.courier.touch_axis == Vector2.ZERO, "Canceled touch must release direction")
	for frame in range(20):
		await physics_frame
	assert(game.courier.touch_axis == Vector2.ZERO)
	var stopped: Vector3 = game.courier.position
	for frame in range(4):
		await physics_frame
	assert(game.courier.position.distance_to(stopped) < 0.02, "Movement must stop after released input and bounded dash")
	_touch(2, right_point, true)
	await physics_frame
	game._on_action("pause")
	assert(game.courier.touch_axis == Vector2.ZERO and game.ui.touch_fingers.is_empty())
	print("RELIC_TOUCH_TESTS_PASS: separated-frame hold/move, simultaneous second-finger dash, cancel release, pause release")
	print("RELIC_TOUCH_TEST_SCOPE: injected Godot ScreenTouch events; no native/physical touch claim")
	game.queue_free()
	quit(0)

func _touch(index: int, point: Vector2, pressed: bool, canceled := false) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.position = point
	event.pressed = pressed
	event.canceled = canceled
	Input.parse_input_event(event)
