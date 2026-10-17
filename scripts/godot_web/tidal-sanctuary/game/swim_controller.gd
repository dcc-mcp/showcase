extends RefCounted
## Feet-origin CharacterBody3D locomotion. Call step once per physics tick,
## instead of calling move_and_slide in the scene. The terrain sample must be
## height_at(body.global_position.x, body.global_position.z), including offshore.
## Keep the capsule at y=.48 with height=.95 (bottom at local y=.005).

const WALK: StringName = &"walk"
const WADE: StringName = &"wade"
const SWIM: StringName = &"swim"
const CAPSULE_BOTTOM := 0.005
const SWIM_ENTER_DEPTH := 0.82
const SWIM_EXIT_DEPTH := 0.66

var sea_level := -0.15
var float_depth := 0.62
var walk_speed := 3.3
var wade_speed := 2.4
var swim_speed := 2.25
## A broad current gently turns the swimmer back before the visible ocean ends.
## These are world-space radii, not the much smaller island coastline.
var soft_boundary_radius := 24.0
var ocean_radius := 28.0
var safe_spawn_position := Vector3(1.3, 3.0, 10.0)
var log_transitions := true

var state: StringName = WALK
var water_depth := 0.0
var boundary_strength := 0.0
var transition_id := 0
var recovery_count := 0
var last_transition: Dictionary = {}
var transition_receipts: Array[Dictionary] = []
var _elapsed := 0.0

func is_swimming() -> bool:
 return state == SWIM

func floating_height() -> float:
 return sea_level - float_depth

func reset() -> void:
 state = WALK
 water_depth = 0.0
 boundary_strength = 0.0
 _elapsed = 0.0
 last_transition = {}
 transition_receipts.clear()

func restored_position(saved: Vector3, ground_height: float, fallback: Vector3) -> Vector3:
 ## Only for loading a save, never to constrain normal play. Invalid/out-of-world
 ## saves return to the supplied safe spawn. Deep-water saves resume afloat.
 if not saved.is_finite() or not is_finite(ground_height):
  return fallback
 if Vector2(saved.x, saved.z).length() > ocean_radius + 2.0:
  return fallback
 var result := saved
 if sea_level - ground_height >= SWIM_ENTER_DEPTH and saved.y <= sea_level + 0.25:
  result.y = floating_height()
 else:
  var floor_y := ground_height - CAPSULE_BOTTOM + 0.015
  result.y = clampf(saved.y, floor_y, maxf(floor_y, sea_level) + 3.0)
 return result

func step(body: CharacterBody3D, desired_move: Vector3, delta: float, ground_height: float) -> void:
 if not is_instance_valid(body) or not is_finite(delta) or delta <= 0.0:
  return
 # A corrupt save/transform is exceptional recovery. Normal shoreline/ocean
 # movement never writes position, clamps coordinates, or teleports the player.
 if not body.global_position.is_finite() or absf(body.global_position.y) > 1000.0 or Vector2(body.global_position.x, body.global_position.z).length() > 512.0:
  body.global_position = safe_spawn_position
  body.velocity = Vector3.ZERO
  recovery_count += 1
  water_depth = 0.0
  _transition(WALK, body, "invalid_position_recovery")
  boundary_strength = 0.0
  return
 if not body.velocity.is_finite():
  body.velocity = Vector3.ZERO
 if not desired_move.is_finite():
  desired_move = Vector3.ZERO
 if not is_finite(ground_height):
  # Do not inject NaNs into state/velocity if a malformed terrain sample arrives.
  ground_height = sea_level - 4.0 if body.global_position.y < sea_level else body.global_position.y

 _elapsed += delta
 water_depth = maxf(0.0, sea_level - ground_height)
 var feet_y := body.global_position.y + CAPSULE_BOTTOM
 var next_state := state
 if state == SWIM:
  if water_depth <= SWIM_EXIT_DEPTH or feet_y > sea_level + 0.35:
   next_state = WADE if water_depth > 0.04 and feet_y <= sea_level + 0.18 else WALK
 elif water_depth >= SWIM_ENTER_DEPTH and feet_y <= sea_level + 0.08:
  next_state = SWIM
 elif state == WADE:
  if water_depth <= 0.04 or feet_y > sea_level + 0.18:
   next_state = WALK
 elif water_depth >= 0.10 and feet_y <= sea_level + 0.08:
  next_state = WADE
 _transition(next_state, body, "shore_depth")

 desired_move.y = 0.0
 desired_move = desired_move.limit_length(1.0)
 var horizontal := Vector2(body.global_position.x, body.global_position.z)
 var radius := horizontal.length()
 boundary_strength = smoothstep(soft_boundary_radius, ocean_radius, radius)
 if boundary_strength > 0.0 and radius > 0.001:
  var outward := Vector3(horizontal.x / radius, 0.0, horizontal.y / radius)
  var outward_input := maxf(0.0, desired_move.dot(outward))
  desired_move -= outward * outward_input * boundary_strength
  desired_move -= outward * boundary_strength * 0.55
  desired_move = desired_move.limit_length(1.0)

 var speed := swim_speed if state == SWIM else (wade_speed if state == WADE else walk_speed)
 var response := 1.0 - exp(-delta * (5.5 if state == SWIM else 10.0))
 body.velocity.x = lerpf(body.velocity.x, desired_move.x * speed, response)
 body.velocity.z = lerpf(body.velocity.z, desired_move.z * speed, response)
 # Grounded motion mode still climbs the ramp when the swimming capsule touches
 # shore; floating mode would misclassify that same beach as an impassable wall.
 body.motion_mode = CharacterBody3D.MOTION_MODE_GROUNDED
 body.floor_max_angle = deg_to_rad(50.0)
 body.floor_stop_on_slope = true
 body.floor_constant_speed = true
 body.floor_snap_length = 0.0 if state == SWIM else 0.3
 if state == SWIM:
  var target_y := floating_height() + sin(_elapsed * 1.65) * 0.018
  # Exponential buoyancy is stable across 30/60/120 Hz and never needs a
  # frame-dependent lerp or a hard vertical position correction.
  body.velocity.y = clampf((target_y - body.global_position.y) * (1.0 - exp(-7.0 * delta)) / delta, -2.6, 2.6)
 else:
  body.velocity.y = maxf(-20.0, body.velocity.y - 18.0 * delta)
 body.move_and_slide()

func _transition(next_state: StringName, body: CharacterBody3D, reason: String) -> void:
 if next_state == state and reason != "invalid_position_recovery":
  return
 var previous := state
 state = next_state
 transition_id += 1
 last_transition = {
  "schema": 1, "transition_id": transition_id, "from": String(previous),
  "to": String(state), "reason": reason, "water_depth": water_depth,
  "position": [body.global_position.x, body.global_position.y, body.global_position.z],
  "physics_frame": Engine.get_physics_frames()
 }
 transition_receipts.append(last_transition.duplicate(true))
 if transition_receipts.size() > 64:
  transition_receipts.pop_front()
 if log_transitions:
  print("TIDAL_MOVEMENT_TRANSITION ", JSON.stringify(last_transition))
