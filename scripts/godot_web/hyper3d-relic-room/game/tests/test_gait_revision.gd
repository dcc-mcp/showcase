extends SceneTree
# Instrumented controller/collision regression; no OS input or gait-quality claim.
const Courier = preload("res://scripts/courier.gd")
var actor: CharacterBody3D
var checks := 0

func _init() -> void:
	call_deferred("run")

func expect(condition: bool, message: String) -> bool:
	checks += 1
	if not condition:
		push_error("RELIC_GAIT_FAILED: " + message)
		quit(1)
	return condition

func _step(delta: float) -> void:
	await physics_frame
	actor._physics_process(delta)

func _settle(point: Vector3) -> void:
	actor.reset_at(point)
	actor.enabled = true
	actor.touch_axis = Vector2.ZERO
	for frame in range(12): await _step(1.0 / Engine.physics_ticks_per_second)

func run() -> void:
	for action in ["move_left", "move_right", "move_forward", "move_back", "dash"]:
		if not InputMap.has_action(action): InputMap.add_action(action)
	var floor := StaticBody3D.new()
	var floor_collider := CollisionShape3D.new()
	var floor_shape := BoxShape3D.new()
	floor_shape.size = Vector3(30, 0.4, 30)
	floor_collider.shape = floor_shape
	floor.position.y = -0.2
	floor.add_child(floor_collider)
	root.add_child(floor)
	actor = CharacterBody3D.new()
	actor.set_script(Courier)
	var collider := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.25
	capsule.height = 1.0
	collider.shape = capsule
	collider.position.y = 0.55
	actor.add_child(collider)
	actor.model = Node3D.new()
	actor.add_child(actor.model)
	root.add_child(actor)
	actor.set_physics_process(false)
	await _settle(Vector3.ZERO)
	actor.touch_axis = Vector2.ONE
	actor.model.rotation.y = 0.0
	actor._physics_process(0.2)
	if not expect(actor.model.rotation.y >= -PI * 0.5 - 0.0001 and actor.model.rotation.y <= 0.0,
			"a 200ms frame must not turn past the requested right-facing heading"):
		return
	var yaw_results := []
	for rate in [30, 60, 120]:
		actor.model.rotation.y = 0.0
		for frame in range(rate): actor._physics_process(1.0 / rate)
		yaw_results.append(actor.model.rotation.y)
	if not expect(absf(yaw_results[0] - yaw_results[1]) < 0.0001 and absf(yaw_results[1] - yaw_results[2]) < 0.0001,
			"equal turn time must give equal facing across 30/60/120 frame partitions"):
		return
	if not expect(actor.get("locomotion_speed") != null and actor.get("grounded_motion_distance") != null,
			"audio integration needs measured speed and cumulative grounded walk distance"):
		return
	await _settle(Vector3.ZERO)
	actor.touch_axis = Vector2.ONE
	var before := actor.position
	for frame in range(30): await _step(1.0 / Engine.physics_ticks_per_second)
	if not expect(actor.position.distance_to(before) > 0.9 and actor.position.distance_to(before) < 1.25,
			"the existing Walk clip uses the agreed 2.2m/s fast-walk pace"):
		return
	if not expect(actor.grounded_motion_distance > 0.9 and absf(actor.locomotion_speed - Courier.SPEED) < 0.05,
			"grounded gait uses actual post-slide displacement"):
		return
	var distance: float = actor.grounded_motion_distance
	actor.enabled = false
	actor.pause_animation(true)
	for frame in range(8): await _step(1.0 / Engine.physics_ticks_per_second)
	if not expect(actor.locomotion_speed == 0.0 and actor.grounded_motion_distance == distance,
			"pause freezes measured gait without resetting its cumulative cursor"):
		return
	await _settle(Vector3(-4, 2, 0))
	actor.touch_axis = Vector2.ONE
	for frame in range(3): await _step(1.0 / Engine.physics_ticks_per_second)
	if not expect(not actor.is_on_floor() and actor.grounded_motion_distance == 0.0,
			"airborne horizontal movement cannot produce grounded walk distance"):
		return
	await _settle(Vector3.ZERO)
	actor.heading = Vector3.RIGHT
	actor.request_dash()
	for frame in range(2): await _step(1.0 / Engine.physics_ticks_per_second)
	if not expect(actor.dash_remaining > 0.0 and actor.grounded_motion_distance == 0.0,
			"dash travel cannot advance walk-footstep distance"):
		return
	var dash_distances := []
	for rate in [30, 60, 120, 37, 144]:
		Engine.physics_ticks_per_second = rate
		await _settle(Vector3.ZERO)
		actor.heading = Vector3.RIGHT
		actor.request_dash()
		var start := actor.position
		for frame in range(int(ceil(Courier.DASH_DURATION * rate))): await _step(1.0 / rate)
		dash_distances.append(actor.position.distance_to(start))
		if not expect(absf(dash_distances[-1] - Courier.DASH_SPEED * Courier.DASH_DURATION) < 0.015,
				"dash includes the last partial tick at " + str(rate) + "Hz"):
			return
		if not expect(actor.grounded_motion_distance == 0.0,
				"dash never contributes to walk distance at " + str(rate) + "Hz"):
			return
	Engine.physics_ticks_per_second = 60
	await _settle(Vector3.ZERO)
	actor.touch_axis = Vector2.ONE
	actor.set_action("Attack", Vector3.RIGHT)
	for frame in range(8): await _step(1.0 / Engine.physics_ticks_per_second)
	if not expect(actor.locomotion_speed == 0.0 and actor.grounded_motion_distance == 0.0,
			"an attack freezes walking despite held direction"):
		return
	var wall := StaticBody3D.new()
	var wall_collider := CollisionShape3D.new()
	var wall_shape := BoxShape3D.new()
	wall_shape.size = Vector3(0.25, 3, 6)
	wall_collider.shape = wall_shape
	wall.position = Vector3(1.6, 1.5, 0)
	wall.add_child(wall_collider)
	root.add_child(wall)
	await _settle(Vector3.ZERO)
	actor.touch_axis = Vector2.ONE
	for frame in range(60): await _step(1.0 / Engine.physics_ticks_per_second)
	distance = actor.grounded_motion_distance
	for frame in range(30): await _step(1.0 / Engine.physics_ticks_per_second)
	if not expect(actor.position.x < 1.3 and actor.locomotion_speed < 0.01 and absf(actor.grounded_motion_distance - distance) < 0.01,
			"holding against a blocking wall must not keep generating walk distance"):
		return
	print("RELIC_GAIT_PASS ", JSON.stringify({"checks": checks, "yaw": yaw_results, "dash_distances": dash_distances,
		"scope": "isolated actual controller and native collision; no OS input, hearing or visual gait acceptance"}))
	quit(0)
