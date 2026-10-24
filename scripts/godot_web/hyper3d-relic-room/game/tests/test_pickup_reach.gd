extends SceneTree
const Main = preload("res://scripts/main.gd")
var game: Node3D
var checks := 0
func _init() -> void: call_deferred("run")
func check(value: bool, message: String) -> bool:
	checks += 1
	if not value:
		push_error(message)
		quit(1)
	return value
func frames(count: int) -> void:
	for frame in range(count): await physics_frame
func key(code: int, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.keycode = code
	event.pressed = pressed
	Input.parse_input_event(event)
func use_key() -> void:
	key(KEY_E, true)
	await frames(3)
	key(KEY_E, false)
	await frames(2)
func walk_to(target: Vector2) -> bool:
	for frame in range(1000):
		var here := Vector2(game.courier.position.x, game.courier.position.z)
		if here.distance_to(target) < 0.2:
			game.courier.touch_axis = Vector2.ZERO
			return true
		var direction := (target - here).normalized()
		game.courier.touch_axis = Vector2(direction.x-direction.y, direction.x+direction.y).normalized()
		await physics_frame
	return false
func run() -> void:
	game = Main.new()
	root.add_child(game)
	game.save_path = "user://qa-pickup-reach.json"
	game._on_action("start")
	for point in [Vector2(-3.3, 7), Vector2(-3.3, -3.4), Vector2(-5.5, -3.4)]:
		if not check(await walk_to(point), "Normal Walk reaches the original town chest route"): return
	await use_key()
	await frames(50)
	if not check(game._chest_opened(), "Normal E opens the real chest"): return
	key(KEY_S, true)
	for frame in range(30):
		if game._distance(game.drop_points["chest:town_chest"]) > 2.0: break
		await physics_frame
	key(KEY_S, false)
	await frames(2)
	var outside: float = game._distance(game.drop_points["chest:town_chest"])
	if not check(outside > 2.0 and outside < 2.1, "Ordinary short movement crosses the unchanged 2m pickup boundary"): return
	await use_key()
	if not check(not game.expedition.snapshot().drops["chest:town_chest"].picked, "Out-of-range E must not grant loot"): return
	print("PICKUP_BOUNDARY ", JSON.stringify({"outside_distance":outside,"toast":game.toast_key,"prompt":game._near_prompt()}))
	if not check(game.toast_key == "out_of_range" and game._near_prompt() == "out_of_range", "Visible nearby loot needs an approach hint instead of a silent rejected E"): return
	key(KEY_W, true)
	await frames(4)
	key(KEY_W, false)
	await frames(2)
	if not check(game._near_drop() == "chest:town_chest", "Normal movement into range enables the same pickup"): return
	await use_key()
	if not check(game.expedition.snapshot().inventory.get("bronze_edge", 0) == 1, "Normal E recovers the actual weapon model"): return
	game._on_action("bag")
	game._on_action("equip:bronze_edge")
	if not check(game.expedition.snapshot().equipment.weapon == "bronze_edge" and game.weapon_visual.get_meta("equipped_item") == "bronze_edge", "Picked equipment and visible weapon state agree"): return
	for voice in game.audio_voices:
		voice.stop()
		voice.stream = null
	OS.delay_msec(75)
	game.queue_free()
	await frames(2)
	print("RELIC_PICKUP_REACH_PASS ", checks, " no teleports, range/AI unchanged; engine key events, not OS input")
	quit(0)
