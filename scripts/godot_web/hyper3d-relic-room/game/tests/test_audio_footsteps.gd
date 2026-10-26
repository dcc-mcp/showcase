extends SceneTree
const Main = preload("res://scripts/main.gd")

class AudioProbe extends Main:
	var requests: Array[String] = []
	func _sound(name: String) -> void:
		requests.append(name)

func _init() -> void:
	call_deferred("run")

func run() -> void:
	var game := AudioProbe.new()
	root.add_child(game)
	game.save_path = "user://qa-footstep-regression.json"
	game._on_action("start")
	for frame in range(20): await physics_frame
	if not game.courier.is_on_floor():
		push_error("FOOTSTEP_FIXTURE_NOT_GROUNDED")
		quit(2)
		return
	game.set_physics_process(false)
	game.courier.set_physics_process(false)
	var before: Vector3 = game.courier.position
	# Requested velocity alone must not sound like movement against a wall.
	game.courier.velocity = Vector3(4.0, 0.0, 0.0)
	game.requests.clear()
	for frame in range(120): game._physics_process(1.0 / 60.0)
	var footsteps := game.requests.count("footstep00")
	print("RELIC_FOOTSTEP_STATIONARY ", JSON.stringify({"seconds": 2.0,
		"measured_distance": game.courier.position.distance_to(before),
		"requested_speed": 4.0, "footstep_requests": footsteps,
		"scope": "Instrumented headless regression; no keyboard or listening acceptance"}))
	game.queue_free()
	await process_frame
	await process_frame
	if footsteps != 0:
		push_error("Stationary controller produced footsteps")
		quit(1)
		return
	print("RELIC_AUDIO_FOOTSTEPS_PASS")
	quit(0)
