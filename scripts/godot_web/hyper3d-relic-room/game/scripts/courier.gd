extends CharacterBody3D
# Adapted from Kenney's MIT Starter Kit 3D Platformer axis/rotation movement.
# Its frame-dependent speed and jump system are replaced by a timed dash.
signal footstep_contact
const SPEED := 1.45
const RUN_SPEED := 2.8
const DASH_SPEED := 11.5
const DASH_DURATION := 0.20
const DASH_COOLDOWN := 1.8
var enabled := false
var touch_axis := Vector2.ZERO
var dash_remaining := 0.0
var cooldown := 0.0
var heading := Vector3.FORWARD
var invulnerable := 0.0
var motion_distance := 0.0
var locomotion_speed := 0.0
var grounded_motion_distance := 0.0
var model: Node3D
var animations: AnimationPlayer
var animation_paused := false
var motion_clip := ""
var walk_nominal_speed := 1.39445
var action_clip := ""
var running := false

func _init() -> void:
	floor_snap_length = 0.25
	floor_constant_speed = true

func bind_animation_player(player: AnimationPlayer) -> void:
	animations = player
	if animations:
		var library := animations.get_animation_library("").duplicate(true) as AnimationLibrary
		animations.remove_animation_library("")
		animations.add_animation_library("", library)
		if library.has_animation("Run"): library.remove_animation("Run")
		animations.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		var run := animations.get_animation("Walk").duplicate(true) as Animation
		run.length = 0.72
		for track in range(run.get_track_count()):
			var bone := String(run.track_get_path(track)).get_slice(":", 1)
			for key in range(run.track_get_key_count(track)):
				run.track_set_key_time(track, key, run.track_get_key_time(track, key) * 0.72)
				if run.track_get_type(track) == Animation.TYPE_ROTATION_3D:
					var lean := -8.0 if bone == "Chest" else (-24.0 if bone.begins_with("Forearm") else 0.0)
					if lean != 0.0:
						run.track_set_key_value(track, key, run.track_get_key_value(track, key) * Quaternion(Vector3.RIGHT, deg_to_rad(lean)))
		library.add_animation("Run", run)
	motion_clip = ""
	_update_animation(0.0)

func pause_animation(paused: bool) -> void:
	animation_paused = paused
	if paused:
		locomotion_speed = 0.0
	if animations:
		animations.active = not paused

func _update_animation(horizontal_speed: float, dashing := false) -> void:
	if not animations or animation_paused:
		return
	var moving := enabled and horizontal_speed > 0.15
	var desired := action_clip if action_clip != "" else ("Dash" if enabled and (dashing or dash_remaining > 0.0) else (("Run" if running else "Walk") if moving else "Idle"))
	var nominal := walk_nominal_speed / 0.72 if desired == "Run" else walk_nominal_speed
	var playback_speed := animations.get_animation("Dash").length / DASH_DURATION if desired == "Dash" else (clampf(horizontal_speed / nominal, 0.2, 1.6) if desired in ["Walk", "Run"] else 1.0)
	animations.speed_scale = playback_speed
	if desired != motion_clip:
		animations.play(desired, 0.04 if desired == "Dash" else 0.12)
		motion_clip = desired

func _advance_animation(delta: float) -> void:
	if not animations or animation_paused: return
	var before := animations.current_animation_position
	var length := animations.current_animation_length
	animations.advance(delta)
	animations.advance(0.0) # Commit this clock position before sampling contacts/socket poses.
	if enabled and is_on_floor() and locomotion_speed > 0.15 and motion_clip in ["Walk", "Run"] and length > 0.0:
		# Authored left/right stance begins at phases 0 and .5; follow clip time,
		# rather than a second velocity/distance timer that drifts from the feet.
		var phase := before / length
		var next := phase + delta * animations.speed_scale / length
		if (phase < 0.5 and next >= 0.5) or next >= 1.0:
			footstep_contact.emit()

func animation_snapshot() -> Dictionary:
	if not animations:
		return {"ready": false}
	return {"ready": true, "player_path": String(animations.get_path()), "clip": motion_clip,
		"position": animations.current_animation_position, "length": animations.current_animation_length,
		"playing": animations.is_playing(), "paused": animation_paused, "speed_scale": animations.speed_scale,
		"walk_nominal_speed_mps": walk_nominal_speed}

func _physics_process(delta: float) -> void:
	if not enabled:
		velocity = Vector3.ZERO
		locomotion_speed = 0.0
		_update_animation(0.0)
		_advance_animation(delta)
		return
	cooldown = maxf(0.0, cooldown - delta)
	invulnerable = maxf(0.0, invulnerable - delta)
	var axis := Input.get_vector("move_left", "move_right", "move_forward", "move_back") + touch_axis
	axis = axis.limit_length()
	# Match the isometric camera's screen-right and screen-up ground vectors.
	var direction := Vector3(axis.x + axis.y, 0.0, -axis.x + axis.y).normalized()
	if action_clip != "":
		direction = Vector3.ZERO
	if direction.length_squared() > 0.01:
		heading = direction
	if Input.is_action_just_pressed("dash"):
		request_dash()
	var dash_time := minf(delta, dash_remaining)
	dash_remaining = maxf(0.0, dash_remaining - delta)
	# Integrate the final partial dash tick instead of dropping a frame of travel.
	running = Input.is_action_pressed("run")
	var speed := RUN_SPEED if running else SPEED
	var target := (heading * DASH_SPEED * dash_time + direction * speed * (delta - dash_time)) / delta
	velocity.x = target.x
	velocity.z = target.z
	var was_grounded := is_on_floor()
	velocity.y = -1.0 if was_grounded else velocity.y - 20.0 * delta
	var before := position
	move_and_slide()
	var travel := Vector2(position.x - before.x, position.z - before.z).length()
	motion_distance += travel
	locomotion_speed = travel / delta
	if was_grounded and is_on_floor() and dash_time <= 0.0 and action_clip == "":
		grounded_motion_distance += travel
	_update_animation(locomotion_speed if is_on_floor() else 0.0, dash_time > 0.0)
	_advance_animation(delta)
	if model and direction.length_squared() > 0.01:
		model.rotation.y = lerp_angle(model.rotation.y, atan2(-heading.x, -heading.z), 1.0 - exp(-delta * 12.0))
	if model:
		model.visible = invulnerable <= 0.0 or fmod(invulnerable, 0.16) < 0.10

func request_dash() -> void:
	if enabled and cooldown <= 0.0 and action_clip == "":
		dash_remaining = DASH_DURATION
		cooldown = DASH_COOLDOWN

func set_action(clip: String, target := Vector3.ZERO) -> void:
	action_clip = clip
	if clip != "":
		dash_remaining = 0.0
		locomotion_speed = 0.0
		var direction := target - global_position
		direction.y = 0.0
		if direction.length_squared() > 0.01:
			heading = direction.normalized()
			model.rotation.y = atan2(-heading.x, -heading.z)
		motion_clip = ""
	_update_animation(0.0)

func reset_at(point: Vector3) -> void:
	action_clip = ""
	position = point
	velocity = Vector3.ZERO
	dash_remaining = 0.0
	cooldown = 0.0
	invulnerable = 1.2
	touch_axis = Vector2.ZERO
	motion_distance = 0.0
	locomotion_speed = 0.0
	grounded_motion_distance = 0.0
	pause_animation(false)
	if animations:
		motion_clip = "Idle"
		animations.speed_scale = 1.0
		animations.play("Idle", 0.0)
		animations.seek(0.0, true)
	if model:
		model.visible = true
