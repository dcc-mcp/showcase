extends SceneTree
## Actual headless Godot physics regressions, separate from rendered/device QA.
## Run: godot --headless --path game --script res://verify_swimming.gd --fixed-fps 240

const SwimController = preload("res://swim_controller.gd")
var failures: Array[String] = []
var receipts: Array[Dictionary] = []
var world: Node3D
var actor: CharacterBody3D
var mover: MovementRunner
var movement: RefCounted

class MovementRunner extends Node:
 var body: CharacterBody3D
 var controller: RefCounted
 var sample_height: Callable
 var direction := Vector3.ZERO
 var active := true
 var ticks := 0
 var max_displacement := 0.0
 var max_radius := 0.0
 var finite := true
 func _physics_process(delta: float) -> void:
  if not active:
   return
  var previous := body.global_position
  controller.step(body, direction, delta, sample_height.call(previous.x, previous.z))
  ticks += 1
  max_displacement = maxf(max_displacement, body.global_position.distance_to(previous))
  max_radius = maxf(max_radius, Vector2(body.global_position.x, body.global_position.z).length())
  finite = finite and body.global_position.is_finite() and body.velocity.is_finite() and is_finite(controller.water_depth)

func terrain_height(x: float, _z: float) -> float:
 return clampf(0.9 - x * 0.4, -3.0, 0.9)

func _initialize() -> void:
 run.call_deferred()

func check(condition: bool, description: String) -> void:
 if not condition:
  failures.append(description)
  push_error(description)

func advance(ticks: int) -> void:
 var until := mover.ticks + ticks
 while mover.ticks < until:
  await physics_frame

func reset_actor(position: Vector3) -> void:
 mover.active = false
 actor.global_position = position
 actor.velocity = Vector3.ZERO
 movement.reset()
 movement.safe_spawn_position = Vector3(0.0, 0.95, 0.0)
 mover.direction = Vector3.ZERO
 mover.max_displacement = 0.0
 mover.max_radius = Vector2(position.x, position.z).length()
 # Reset CharacterBody3D collision state after this test fixture's explicit spawn.
 await physics_frame
 mover.active = true
 await advance(2)

func travel_to(x: float, max_ticks: int) -> bool:
 var sign_x := 1.0 if actor.global_position.x < x else -1.0
 mover.direction = Vector3(sign_x, 0.0, 0.0)
 var start_tick := mover.ticks
 while (actor.global_position.x - x) * sign_x < 0.0 and mover.ticks - start_tick < max_ticks:
  await physics_frame
 mover.direction = Vector3.ZERO
 return (actor.global_position.x - x) * sign_x >= 0.0

func build_fixture() -> void:
 world = Node3D.new()
 root.add_child(world)
 var terrain := StaticBody3D.new()
 var collider := CollisionShape3D.new()
 var heightmap := HeightMapShape3D.new()
 heightmap.map_width = 65
 heightmap.map_depth = 33
 var heights := PackedFloat32Array()
 for iz in range(33):
  for ix in range(65):
   heights.append(terrain_height((ix - 32) * 0.5, (iz - 16) * 0.5))
 heightmap.map_data = heights
 collider.shape = heightmap
 terrain.scale = Vector3(0.5, 1.0, 0.5)
 terrain.add_child(collider)
 world.add_child(terrain)
 actor = CharacterBody3D.new()
 var capsule := CollisionShape3D.new()
 var shape := CapsuleShape3D.new()
 shape.radius = 0.22
 shape.height = 0.95
 capsule.shape = shape
 capsule.position.y = 0.48
 actor.add_child(capsule)
 world.add_child(actor)
 movement = SwimController.new()
 movement.log_transitions = false
 mover = MovementRunner.new()
 mover.body = actor
 mover.controller = movement
 mover.sample_height = terrain_height
 world.add_child(mover)

func run() -> void:
 build_fixture()
 for tick_rate in [30, 60, 120]:
  Engine.physics_ticks_per_second = tick_rate
  await reset_actor(Vector3(0.0, 1.0, 0.0))
  await advance(tick_rate)
  check(actor.is_on_floor(), "spawn settles on actual heightfield at %d Hz" % tick_rate)
  mover.max_displacement = 0.0
  var cycle_transition_start: int = movement.transition_id
  var cycles: Array[Dictionary] = []
  for cycle in range(3):
   var outbound: bool = await travel_to(10.0, tick_rate * 10)
   check(outbound, "walk to deep water cycle %d at %d Hz" % [cycle, tick_rate])
   await advance(tick_rate * 2)
   check(movement.is_swimming(), "deep water enters swimming at %d Hz" % tick_rate)
   check(absf(actor.position.y - movement.floating_height()) < 0.04, "stable float height at %d Hz" % tick_rate)
   var inbound: bool = await travel_to(0.0, tick_rate * 10)
   check(inbound, "swim to dry land without beach wall cycle %d at %d Hz" % [cycle, tick_rate])
   await advance(tick_rate)
   check(movement.state == SwimController.WALK and actor.is_on_floor(), "re-emerges walking on collision floor at %d Hz" % tick_rate)
   check(movement.recovery_count == 0, "normal play never uses recovery")
   cycles.append({"cycle": cycle, "outbound": outbound, "inbound": inbound, "state": String(movement.state), "land_y": actor.position.y})
  check(mover.max_displacement < 3.5 / tick_rate + 0.02, "continuous movement without teleport at %d Hz" % tick_rate)
  receipts.append({"check": "walk_water_walk", "tick_rate": tick_rate, "cycles": cycles, "transition_count": movement.transition_id - cycle_transition_start, "max_step": mover.max_displacement})

 Engine.physics_ticks_per_second = 60
 # Hold within the swim hysteresis band from both directions. Rounded capsule
 # support on a slope is intentionally tested, rather than replacing physics.
 await reset_actor(Vector3(4.4, terrain_height(4.4, 0.0) + 0.08, 0.0))
 await advance(120)
 var wade_transitions: int = movement.transition_id
 var wade_x := actor.position.x
 await advance(600)
 check(movement.state == SwimController.WADE, "stationary shore remains wading")
 check(movement.transition_id == wade_transitions, "wading shore does not jitter state")
 check(absf(actor.position.x - wade_x) < 0.035, "stationary slope does not creep")
 receipts.append({"check": "idle_shore_wade", "seconds": 10, "state": String(movement.state), "new_transitions": movement.transition_id - wade_transitions, "drift": actor.position.x - wade_x})

 await reset_actor(Vector3(6.0, movement.floating_height(), 0.0))
 check(movement.is_swimming(), "deep reset enters swim")
 await travel_to(4.75, 240)
 await advance(120)
 var swim_transitions: int = movement.transition_id
 await advance(600)
 check(movement.is_swimming(), "stationary hysteresis band retains swim")
 check(movement.transition_id == swim_transitions, "swimming shore does not jitter state")
 receipts.append({"check": "idle_shore_swim", "seconds": 10, "state": String(movement.state), "depth": movement.water_depth, "new_transitions": movement.transition_id - swim_transitions})

 # Outside the heightfield: buoyancy must not depend on a hidden ocean floor.
 await reset_actor(Vector3(19.0, -2.0, 0.0))
 await advance(180)
 var idle_start := actor.position
 await advance(600)
 check(movement.is_swimming(), "open sea without seabed collision remains swimming")
 check(absf(actor.position.y - movement.floating_height()) < 0.04, "idle buoyancy holds open-water surface")
 check(Vector2(actor.position.x - idle_start.x, actor.position.z - idle_start.z).length() < 0.001, "idle swim has no unintended lateral drift")
 receipts.append({"check": "idle_ocean_no_collision", "seconds": 10, "position": [actor.position.x, actor.position.y, actor.position.z], "surface_error": absf(actor.position.y - movement.floating_height())})

 await reset_actor(Vector3(26.0, movement.floating_height(), 0.0))
 mover.direction = Vector3.RIGHT
 await advance(1200)
 check(mover.max_radius < movement.ocean_radius + 0.1, "gentle current bounds sustained outward input")
 check(mover.max_displacement < 0.08, "ocean boundary has no teleport")
 var boundary_x := actor.position.x
 var returned: bool = await travel_to(22.0, 600)
 check(returned, "player can steer back from current boundary")
 receipts.append({"check": "gentle_boundary", "seconds": 20, "furthest_radius": mover.max_radius, "steady_x": boundary_x, "max_step": mover.max_displacement, "return_success": returned})

 mover.active = false
 var fallback := Vector3(0.0, 0.95, 0.0)
 check(movement.restored_position(Vector3(NAN, 0, 0), NAN, fallback) == fallback, "rejects NaN saved position")
 check(movement.restored_position(Vector3(INF, 0, 0), 0.0, fallback) == fallback, "rejects infinite saved position")
 check(movement.restored_position(Vector3(500, 0, 0), -3.0, fallback) == fallback, "rejects outside-world saved position")
 var restored: Vector3 = movement.restored_position(Vector3(10, -99, 0), -3.0, fallback)
 check(is_equal_approx(restored.y, movement.floating_height()), "underwater save resumes at swim surface")
 var land_restore: Vector3 = movement.restored_position(Vector3(0, -2, 0), 0.9, fallback)
 check(land_restore.y >= 0.9, "land save is lifted above capsule floor")
 actor.global_position = Vector3(600, 0, 0)
 movement.step(actor, Vector3(NAN, 0, 0), 1.0 / 60.0, -3.0)
 check(actor.position == movement.safe_spawn_position and actor.velocity == Vector3.ZERO, "invalid transform recovery uses configured safe spawn")
 actor.velocity = Vector3(NAN, INF, 0)
 movement.step(actor, Vector3(NAN, 0, 0), 1.0 / 60.0, NAN)
 check(actor.position.is_finite() and actor.velocity.is_finite(), "bad inputs cannot poison actor state")
 var before_invalid_delta := actor.position
 movement.step(actor, Vector3.RIGHT, NAN, 0.9)
 movement.step(actor, Vector3.RIGHT, 0.0, 0.9)
 check(actor.position == before_invalid_delta, "invalid or zero time step makes no movement")
 check(mover.finite, "all regular simulation states remain finite")
 receipts.append({"check": "save_and_finite_state", "safe_spawn": [movement.safe_spawn_position.x, movement.safe_spawn_position.y, movement.safe_spawn_position.z], "recovery_count": movement.recovery_count, "last_transition": movement.last_transition})
 print("TIDAL_SWIMMING_CHECK ", JSON.stringify({"schema": 1, "engine": Engine.get_version_info().string, "route": "actual headless Godot CharacterBody3D + HeightMapShape3D, not rendered or physical-device proof", "passed": failures.is_empty(), "failures": failures, "checks": receipts}))
 quit(0 if failures.is_empty() else 1)
