extends SceneTree
## Actual main-scene headless regression. Run in a copied project and isolated HOME/XDG:
## godot --headless --path COPY --script res://verify_collision.gd --fixed-fps 240
## Uses imported mesh triangles, physics rays, and production controller movement.
## Spawns/stages are fixtures and interact calls are direct, not real keyboard,
## browser, manual-play, or rendered-quality proof. Fixture saves are disabled.

var game: Node3D
var failures: Array[String] = []
var checks: Array[Dictionary] = []
var meshes: Array[MeshInstance3D] = []
var bodies: Array[CollisionObject3D] = []
var mover: MovementRunner

class MovementRunner extends Node:
 var scene: Node3D
 var active := false
 var direction := Vector3.ZERO
 var ticks := 0
 var positions: Array[Vector3] = []
 var capture_chart := false
 var chart_face := 1
 var chart_run := 0
 var chart_max_run := 0
 var chart_states: Array[Dictionary] = []
 var chart_steps: Array[Dictionary] = []
 var chart_last_state: Dictionary = {}
 func _physics_process(delta: float) -> void:
  if not active:return
  scene.swim.step(scene.player, direction, delta, scene.height_at(scene.player.position.x, scene.player.position.z))
  ticks += 1
  positions.append(scene.player.position)
  if capture_chart:
   var snapshot: Dictionary = scene.swim.chart_motion_snapshot()
   var step: Dictionary = snapshot.frames[-1]
   chart_steps.append(step)
   var contact := false
   for hit in step.collisions:
    if hit.interaction_target == 0 and hit.intent == "solid" and chart_face * float(hit.normal[2]) > 0.999:
     contact = true
   var blocked: bool = contact and -chart_face * float(step.movement_input[1]) > 0.5 and -chart_face * float(step.requested_velocity[2]) > 0.1 and absf(float(step.velocity[2])) <= 0.08
   chart_run = chart_run + 1 if blocked else 0
   chart_max_run = maxi(chart_max_run, chart_run)
   scene.last_move = direction
   scene.sample_id += 1
   chart_last_state = scene.observed_state()
   if chart_steps.size() % 13 == 0:chart_states.append(chart_last_state)

func _initialize() -> void:
 run.call_deferred()

func check(condition: bool, description: String) -> void:
 if not condition:
  failures.append(description)
  push_error(description)

func vector(value: Vector3) -> Array:
 return [value.x, value.y, value.z]

func collect(node: Node) -> void:
 if node is MeshInstance3D and node.mesh:meshes.append(node)
 if node is CollisionObject3D:bodies.append(node)
 for child in node.get_children():collect(child)

func beneath(node: Node, ancestor: Node) -> bool:
 return node == ancestor or ancestor.is_ancestor_of(node)

func nearest_mesh(position: Vector3, max_distance := 0.20) -> MeshInstance3D:
 var result: MeshInstance3D
 var distance := max_distance
 for mesh in meshes:
  if mesh == game.terrain_mesh:continue
  var candidate := mesh.global_position.distance_to(position)
  if candidate < distance:
   result = mesh
   distance = candidate
 return result

func mesh_hit(mesh: MeshInstance3D, from: Vector3, to: Vector3) -> Dictionary:
 var result: Dictionary = {}
 var distance := INF
 var faces := mesh.mesh.get_faces()
 for i in range(0, faces.size(), 3):
  var point = Geometry3D.segment_intersects_triangle(from, to,
   mesh.global_transform * faces[i], mesh.global_transform * faces[i + 1], mesh.global_transform * faces[i + 2])
  if point != null and from.distance_to(point) < distance:
   distance = from.distance_to(point)
   result = {"position": point, "distance": distance}
 return result

func physics_hit(from: Vector3, to: Vector3, only_body: Node = null) -> Dictionary:
 var query := PhysicsRayQueryParameters3D.create(from, to)
 var excluded: Array[RID] = [game.player.get_rid()]
 if only_body != null:
  for body in bodies:
   if not beneath(body, only_body):excluded.append(body.get_rid())
 query.exclude = excluded
 return game.get_world_3d().direct_space_state.intersect_ray(query)

func aligned_ray(label: String, mesh: MeshInstance3D, from: Vector3, to: Vector3, only_body: Node = null, tolerance := 0.12, allow_buried := false) -> void:
 check(mesh != null, label + ": visible mesh fixture exists")
 if mesh == null:return
 var visual := mesh_hit(mesh, from, to)
 check(not visual.is_empty(), label + ": probe crosses visible mesh triangles")
 var actual := physics_hit(from, to, only_body)
 check(not actual.is_empty(), label + ": actual physics ray hits solid geometry")
 var error := -1.0
 var height_gap := 0.0
 if not visual.is_empty() and not actual.is_empty():
  error = visual.position.distance_to(actual.position)
  height_gap = visual.position.y - actual.position.y
  # Terrain occludes deliberately buried stone; only exposed height can sink feet.
  check(height_gap <= tolerance if allow_buried else error <= tolerance, label + ": visible surface stays within %.3f m of its support" % tolerance)
 checks.append({"check":"mesh_physics_alignment", "object":label, "from":vector(from), "to":vector(to), "surface_error":error, "height_gap":height_gap, "allow_buried":allow_buried, "tolerance":tolerance, "physics_hit":not actual.is_empty(), "visual_position":vector(visual.position) if not visual.is_empty() else [], "physics_position":vector(actual.position) if not actual.is_empty() else []})

func advance(ticks: int) -> void:
 var until := mover.ticks + ticks
 while mover.ticks < until:await physics_frame

func spawn(position: Vector3) -> void:
 mover.active = false
 game.player.position = position
 game.player.velocity = Vector3.ZERO
 game.swim.reset()
 game.swim.log_transitions = false
 mover.direction = Vector3.ZERO
 mover.positions.clear()
 await physics_frame
 await physics_frame
 mover.active = true
 await advance(3)

func spawn_ground(x: float, z: float) -> void:
 await spawn(Vector3(x, game.height_at(x, z) + 0.04, z))

func blocked_crossing(label: String, center: Vector3, half_width: float, start_distance: float, frames := 90) -> void:
 await spawn_ground(center.x - start_distance, center.z)
 var start: Vector3 = game.player.position
 mover.positions.clear()
 mover.direction = Vector3.RIGHT
 await advance(frames)
 mover.direction = Vector3.ZERO
 mover.active = false
 var maximum_x := start.x
 for position in mover.positions:maximum_x = maxf(maximum_x, position.x)
 check(maximum_x < center.x - half_width + 0.04, label + ": capsule cannot pass through solid from west")
 check(game.player.position.x > start.x + 0.10, label + ": controller moved toward tested solid")
 check(game.player.position.is_finite() and game.swim.recovery_count == 0, label + ": finite movement without recovery teleport")
 checks.append({"check":"actual_controller_blocker", "object":label, "fixture_start":vector(start), "finish":vector(game.player.position), "maximum_x":maximum_x, "ticks":frames})

func test_solids() -> void:
 var chart: Vector3 = game.lantern_points[0]
 var chest: Vector3 = game.lantern_points[1]
 var beacon: Vector3 = game.beacon.position
 var wall := Vector3(-4.25, game.height_at(-4.25, -8.65), -8.65)
 var cases: Array[Dictionary] = [
  {"name":"chart_pedestal", "point":chart + Vector3(0,0.35,0), "reach":1.0},
  {"name":"grove_chest", "point":chest + Vector3(0,0.24,0), "reach":1.0},
  {"name":"beacon_base", "point":beacon + Vector3(0,0.17,0), "reach":1.5},
  {"name":"west_return_wall", "point":wall + Vector3(0,0.24,0), "reach":1.0}
 ]
 for item in cases:
  var p: Vector3 = item.point
  aligned_ray(item.name, nearest_mesh(p), p - Vector3.RIGHT * item.reach, p + Vector3.RIGHT * item.reach)
 await blocked_crossing("chart_pedestal", chart, 0.425, 1.4)
 await blocked_crossing("grove_chest", chest, 0.41, 1.4)
 await blocked_crossing("beacon_base", beacon, 1.15, 2.0)
 await blocked_crossing("west_return_wall", wall, 0.335, 1.4)

func test_chart_normal_contacts() -> void:
 # These are explicit spawn/direct-controller fixtures, never OS-input proof.
 # Removing the real authored collider repeats exactly the same approach and
 # must destroy contact evidence and permit crossing its former face plane.
 var chart_body: CollisionObject3D
 for body in bodies:
  if body.get_meta("interaction_target", -1) == 0 and body.get_meta("collision_intent", "") == "solid":
   chart_body = body
   break
 check(chart_body != null, "chart normal fixture locates the actual authored collider")
 if chart_body == null:return
 var original_layer := chart_body.collision_layer
 for face in [1, -1]:
  for mode in ["solid", "collider_removed", "idle"]:
   for lane_offset in ([0.0] if mode == "idle" else [-0.06, 0.0, 0.06]):
    chart_body.collision_layer = 0 if mode == "collider_removed" else original_layer
    await physics_frame
    var direction := Vector3(0.2905 * face, 0, -0.9569 * face).normalized()
    var contact_x: float = 1.3 - 0.11 * face + float(lane_offset) / 0.9569
    var start_x: float = contact_x - direction.x * (0.63 / absf(direction.z))
    var start_z: float = 7.8 + 1.2 * face
    if mode == "idle":
     start_x = contact_x
     start_z = 7.8 + 0.571 * face
    await spawn_ground(start_x, start_z)
    game.swim.observe_chart_motion = true
    mover.chart_states.clear()
    mover.chart_steps.clear()
    mover.chart_run = 0
    mover.chart_max_run = 0
    mover.chart_face = face
    mover.capture_chart = true
    mover.direction = Vector3.ZERO if mode == "idle" else direction
    var beginning := mover.ticks
    while mover.ticks - beginning < 65 and mover.chart_run < 14:await physics_frame
    mover.active = false
    mover.capture_chart = false
    if not mover.chart_last_state.is_empty() and (mover.chart_states.is_empty() or mover.chart_states[-1].physics_frame != mover.chart_last_state.physics_frame):
     mover.chart_states.append(mover.chart_last_state)
    var minimum_side := 100.0
    var chart_hits := 0
    for step in mover.chart_steps:
     minimum_side = minf(minimum_side, face * (float(step.after[2]) - 7.8))
     for hit in step.collisions:
      if hit.interaction_target == 0 and hit.intent == "solid":chart_hits += 1
    var label: String = "chart_%s_face_%d_offset_%.2f" % [mode, face, lane_offset]
    if mode == "solid":
     check(mover.chart_max_run >= 12, label + ": actual contacts block normal velocity for twelve steps while sliding")
     check(minimum_side >= 0.565, label + ": capsule remains outside the flat face")
    elif mode == "collider_removed":
     check(chart_hits == 0, label + ": removed collider supplies no false contact")
     check(minimum_side < 0.35, label + ": same input crosses the absent collider face")
    else:
     check(mover.chart_max_run == 0, label + ": stationary input cannot pass contact gate")
    checks.append({"check":"actual_controller_chart_normal_contact", "case":label, "mode":mode,
     "expected_valid":mode == "solid", "face":face, "lane_offset":lane_offset, "after_physics_frame":int(mover.chart_steps[0].physics_frame) - 1,
     "minimum_side":minimum_side, "chart_hit_count":chart_hits, "maximum_contact_run":mover.chart_max_run,
     "samples":mover.chart_states.duplicate(true), "evidence_scope":"fixture spawn and direct production controller; real KinematicCollision3D receipts; not physical keyboard proof"})
    chart_body.collision_layer = original_layer
 game.swim.observe_chart_motion = false
 chart_body.collision_layer = original_layer
 await physics_frame

func first_mesh(node: Node) -> MeshInstance3D:
 for mesh in meshes:
  if beneath(mesh, node):return mesh
 return null

func test_imported_solids() -> void:
 var palms := 0
 var rocks := 0
 for node in game.get_children():
  if not node is Node3D:continue
  var path: String = node.scene_file_path
  var palm := "/palm-" in path
  var rock := "/shore-rock-" in path
  if not palm and not rock:continue
  var mesh := first_mesh(node)
  check(mesh != null, path + ": imported mesh exists")
  if mesh == null:continue
  var body: Node = game.get_node_or_null(mesh.get_meta("solid_body", NodePath("")))
  check(body is StaticBody3D, "%s at %s references an actual solid body" % [path.get_file(), str(node.position)])
  var from: Vector3
  var to: Vector3
  if palm:
   palms += 1
   # This local height crosses the lower trunk, never the fronds.
   from = node.global_transform * Vector3(-1.2, 0.4, 0)
   to = node.global_transform * Vector3(1.2, 0.4, 0)
  else:
   rocks += 1
   var bounds: AABB = mesh.global_transform * mesh.mesh.get_aabb()
   from = bounds.get_center() - Vector3.RIGHT * bounds.size.x
   to = bounds.get_center() + Vector3.RIGHT * bounds.size.x
  aligned_ray("%s_%d" % ["palm_trunk" if palm else "large_rock", palms if palm else rocks], mesh, from, to, body)
 check(palms == 7, "all seven authored palm trunks were tested")
 check(rocks == 24, "all twenty-four authored large rocks were tested")
 checks.append({"check":"imported_solids_coverage", "palms":palms, "large_rocks":rocks})

func collision_receipts() -> Array:
 var result: Array = []
 for index in range(game.player.get_slide_collision_count()):
  var collision: KinematicCollision3D = game.player.get_slide_collision(index)
  var body: Node = collision.get_collider()
  result.append({"body":str(body.get_path()), "reason":str(body.get_meta("collision_reason", "")), "normal":vector(collision.get_normal()), "position":vector(collision.get_position())})
 return result

func travel_z(target_z: float, max_ticks := 240) -> bool:
 var sign_z := 1.0 if game.player.position.z < target_z else -1.0
 mover.direction = Vector3(0,0,sign_z)
 var beginning := mover.ticks
 while (game.player.position.z - target_z) * sign_z < 0 and mover.ticks - beginning < max_ticks:await physics_frame
 mover.direction = Vector3.ZERO
 return (game.player.position.z - target_z) * sign_z >= 0

func test_other_paving() -> void:
 var count := 0
 for mesh in meshes:
  if not mesh.has_meta("support_body") or mesh.get_meta("threshold_step",false):continue
  var support: Node = game.get_node_or_null(mesh.get_meta("support_body"))
  check(support is StaticBody3D and beneath(support,game.terrain_mesh), "paving_%d declares actual solid terrain support" % count)
  check(str(mesh.get_meta("collision_intent","")) == "none", "paving_%d has explicit terrain-backed collision intent" % count)
  var bounds := mesh.mesh.get_aabb()
  var width := bounds.size.x * 0.30
  var depth := bounds.size.z * 0.30
  var offsets: Array[Vector2] = [Vector2.ZERO,Vector2(-width,-depth),Vector2(width,-depth),Vector2(-width,depth),Vector2(width,depth)]
  for index in range(offsets.size()):
   var offset := offsets[index]
   var point := mesh.global_transform * Vector3(offset.x,0,offset.y)
   aligned_ray("other_paving_%d_sample_%d" % [count,index],mesh,point+Vector3.UP,point-Vector3.UP,support,0.025,true)
  count += 1
 check(count == 29, "all twelve path stones and seventeen ruin paving tiles were sampled")
 checks.append({"check":"other_paving_coverage","patches":count,"samples_per_patch":5})

func test_steps() -> void:
 var steps: Array[MeshInstance3D] = []
 for mesh in meshes:
  if mesh.get_meta("threshold_step", false):steps.append(mesh)
 check(steps.size() == 8, "all eight threshold step meshes were located")
 for index in range(steps.size()):
  var mesh := steps[index]
  var support_body: Node = game.get_node_or_null(mesh.get_meta("solid_body", NodePath("")))
  var terrain_backed := str(mesh.get_meta("collision_intent", "")) == "none"
  var tolerance := 0.025 if terrain_backed else 0.045
  if terrain_backed:
   check("terrain" in str(mesh.get_meta("collision_reason", "")).to_lower(), "threshold_step_%d explicitly declares terrain-backed support" % index)
   var support := physics_hit(mesh.global_position + Vector3.UP, mesh.global_position - Vector3.UP)
   check(not support.is_empty() and beneath(support.collider, game.terrain_mesh), "threshold_step_%d is actually supported by the solid terrain" % index)
   support_body = null
  else:
   check(support_body is StaticBody3D, "threshold_step_%d has its intended actual support collider" % index)
  var offsets: Array[Vector2] = [Vector2.ZERO,Vector2(-0.4,-0.15),Vector2(0.4,-0.15),Vector2(-0.4,0.15),Vector2(0.4,0.15)]
  for sample_index in range(offsets.size()):
   var offset := offsets[sample_index]
   var point := mesh.global_transform * Vector3(offset.x,0,offset.y)
   aligned_ray("threshold_step_%d_sample_%d" % [index,sample_index], mesh, point + Vector3.UP, point - Vector3.UP, support_body, tolerance, terrain_backed)
 for lane_x in [0.0,-1.45,0.25]:
  await spawn_ground(lane_x,-3.60)
  var start: Vector3 = game.player.position
  var uphill := await travel_z(-6.60)
  check(uphill, "controller climbs all four threshold rows in lane x=%.2f" % lane_x)
  var summit: Vector3 = game.player.position
  var uphill_collisions := collision_receipts()
  # Independent top spawn prevents uphill failure from trivially passing descent.
  var down_start := Vector3(lane_x, game.height_at(lane_x,-6.70) + 0.30, -6.70)
  var supporting := physics_hit(down_start + Vector3.UP, down_start - Vector3.UP)
  if not supporting.is_empty():down_start.y = supporting.position.y + 0.03
  await spawn(down_start)
  var downhill := await travel_z(-3.60)
  check(downhill, "controller descends all four threshold rows in lane x=%.2f" % lane_x)
  mover.active = false
  check(game.player.position.is_finite() and game.swim.recovery_count == 0, "threshold traversal stays finite without recovery teleport")
  checks.append({"check":"actual_controller_threshold_traversal", "lane_x":lane_x, "fixture_start":vector(start), "summit":vector(summit), "finish":vector(game.player.position), "uphill":uphill, "downhill":downhill, "uphill_collisions":uphill_collisions, "downhill_fixture_start":vector(down_start)})

func test_beacon_approach() -> void:
 if not game.has_method("interaction_status"):return
 set_stage(3)
 var start := Vector3(0, game.height_at(0,-6.70) + 0.30, -6.70)
 var support := physics_hit(start + Vector3.UP, start - Vector3.UP)
 if not support.is_empty():start.y = support.position.y + 0.03
 await spawn(start)
 var reached := await travel_z(-10.25, 300)
 mover.direction = Vector3.ZERO
 await advance(45)
 mover.active = false
 var position: Vector3 = game.player.position
 var approach_distance := Vector2(position.x,position.z + 10.25).length()
 var target_distance: float = game.flat_distance(position,game.beacon.position)
 var speed := Vector2(game.player.velocity.x,game.player.velocity.z).length()
 var status: Dictionary = game.interaction_status()
 check(reached and approach_distance <= 0.25, "actual ruin-corridor movement reaches the CI ring approach disk")
 check(target_distance < 1.55 and bool(status.get("available",false)), "settled ring approach is actually within range and unobstructed")
 check(speed <= 0.08, "ring approach settles before the action")
 checks.append({"check":"actual_controller_beacon_approach", "fixture_start":vector(start), "finish":vector(position), "approach_distance":approach_distance, "target_distance":target_distance, "speed":speed, "available":status.get("available",false), "reason":status.get("reason",""), "collisions":collision_receipts()})

func set_stage(stage: int) -> void:
 for i in range(3):game.activated[i] = i < stage
 game.beacon_awakened = false
 game.completed = stage >= 3
 game.tip_until = 0.0
 game.update_state()

func interaction_available() -> bool:
 var status: Dictionary = game.interaction_status()
 check(status.has("available") and status.has("reason") and status.has("target"), "interaction_status provides available, reason, and target")
 return bool(status.get("available", false))

func test_interactions() -> void:
 check(game.has_method("interaction_status"), "shared interaction_status predicate exists")
 if not game.has_method("interaction_status"):return
 mover.active = false
 set_stage(0)
 for height in [8.0,-8.0]:
  game.player.position = game.lantern_points[0] + Vector3(0,height,0)
  await physics_frame
  check(not interaction_available(), "chart rejects %.1f m vertical separation" % height)
  game.interact()
  check(game.quest_stage() == 0, "direct chart action cannot advance at %.1f m vertical separation" % height)
 for stage in range(4):
  set_stage(stage)
  var point: Vector3 = game.target_point()
  game.player.position = point + Vector3(1.70,0,0)
  game.player.position.y = game.swim.floating_height() if stage == 2 else game.height_at(game.player.position.x,game.player.position.z) + 0.02
  await physics_frame
  check(not interaction_available(), "stage %d rejects out-of-range approach" % stage)
  game.interact()
  check(game.quest_stage() == stage, "stage %d out-of-range direct action cannot advance" % stage)
  var approach := 1.45 if stage == 3 else 1.25
  game.player.position = point + Vector3(approach,0,0)
  game.player.position.y = game.swim.floating_height() if stage == 2 else game.height_at(game.player.position.x,game.player.position.z) + 0.02
  await physics_frame
  check(interaction_available(), "stage %d reachable outside own collider" % stage)
  var blocker := StaticBody3D.new()
  blocker.name = "RegressionOnlyLineOfSightBlocker"
  var shape := CollisionShape3D.new()
  var box := BoxShape3D.new()
  box.size = Vector3(0.08,6.0,3.0)
  shape.shape = box
  blocker.add_child(shape)
  game.add_child(blocker)
  blocker.position = point + Vector3(approach * 0.5,1.0,0)
  await physics_frame
  await physics_frame
  check(not interaction_available(), "stage %d unavailable behind actual physics blocker" % stage)
  game.interact()
  check(game.quest_stage() == stage, "stage %d direct action cannot collect through blocker" % stage)
  blocker.queue_free()
  await physics_frame
  await physics_frame
  check(interaction_available(), "stage %d available after blocker removal" % stage)
  game.interact()
  check(game.quest_stage() == stage + 1, "stage %d advances exactly once from valid approach" % stage)
  for repeat in range(5):game.interact()
  check(game.quest_stage() == stage + 1, "stage %d repeated calls cannot skip subsequent objectives" % stage)
  checks.append({"check":"fixture_direct_interaction", "stage":stage, "approach":vector(game.player.position), "after":game.quest_stage(), "tested":["range","own_collider","physical_line_of_sight","blocker_removal","duplicate_calls"]})

func run() -> void:
 game = load("res://start.tscn").instantiate()
 root.add_child(game)
 game.begin_journey("fixture")
 game.set_physics_process(false)
 game.set_process(false)
 game.capture = true
 collect(game)
 mover = MovementRunner.new()
 mover.scene = game
 game.add_child(mover)
 await process_frame
 await physics_frame
 await physics_frame
 await test_solids()
 await test_chart_normal_contacts()
 test_imported_solids()
 test_other_paving()
 await test_steps()
 await test_beacon_approach()
 await test_interactions()
 mover.active = false
 game.queue_free()
 await process_frame
 # Fixed-fps fixtures advance simulated timers faster than the audio mixing thread.
 OS.delay_msec(200)
 await process_frame
 print("TIDAL_COLLISION_CHECK ", JSON.stringify({"schema":1, "engine":Engine.get_version_info().string, "passed":failures.is_empty(), "failures":failures, "checks":checks, "evidence_scope":"actual imported triangle/ray queries and controller physics; explicit fixture positions/stages and direct interaction calls; no rendered, physical-keyboard, browser, or manual-play proof"}))
 quit(0 if failures.is_empty() else 1)
