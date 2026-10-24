extends CharacterBody3D
# World-only bounded AI. Numeric damage, health and cooldown authority is Expedition.
var enemy_id := ""
var spec := {}
var spawn_point := Vector3.ZERO
var visual: Node3D
var animations: AnimationPlayer
var telegraph: MeshInstance3D
var phase := "idle"
var phase_time := 0.0
var contact_sent := false
var dead := false
var motion_clip := ""
var attack_gate := 0.0
# Foot-range calibration at1.65m; actual rendered cadence remains a visual gate.
const WALK_NOMINAL_SPEED := 0.980544329

func setup(id: String, definition: Dictionary, point: Vector3, body: Node3D, player: AnimationPlayer) -> void:
	enemy_id = id
	spec = definition
	spawn_point = point
	global_position = point + Vector3(0, -0.05, 0)
	visual = body
	animations = player
	if animations: animations.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var collider := CollisionShape3D.new()
	var shape := CapsuleShape3D.new()
	shape.radius = 0.45
	shape.height = 1.6
	collider.position.y = 0.85
	collider.shape = shape
	add_child(collider)
	collision_layer = 2
	collision_mask = 1 | 2
	var ring := TorusMesh.new()
	ring.inner_radius = float(spec.attack_range) - 0.06
	ring.outer_radius = float(spec.attack_range)
	ring.rings = 40
	ring.ring_segments = 4
	telegraph = MeshInstance3D.new()
	telegraph.name = "AuthoredAttackWarning"
	telegraph.mesh = ring
	telegraph.position.y = 0.08
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("eaa362")
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	telegraph.material_override = material
	add_child(telegraph)
	reset_actor(false)

func reset_actor(is_dead: bool) -> void:
	dead = is_dead
	phase = "dead" if dead else "idle"
	phase_time = 0.0
	attack_gate = 0.0
	global_position = spawn_point + Vector3(0, -0.05, 0)
	velocity = Vector3.ZERO
	visible = not dead
	collision_layer = 0 if dead else 2
	telegraph.visible = false
	_play("Idle")

func tick_actor(delta: float, player_position: Vector3, enabled: bool, can_attack: bool) -> bool:
	if animations:
		animations.active = enabled and not dead
	if dead or not enabled:
		velocity = Vector3.ZERO
		return false
	if animations:
		animations.advance(delta)
		animations.advance(0.0)
	var offset := player_position - global_position
	offset.y = 0.0
	var distance := offset.length()
	var contact := false
	phase_time += delta
	attack_gate = maxf(0.0, attack_gate - delta)
	if phase == "attack":
		velocity.x = 0.0
		velocity.z = 0.0
		telegraph.visible = phase_time < float(spec.contact)
		if phase_time >= float(spec.contact) and not contact_sent:
			contact_sent = true
			contact = true
		if phase_time >= float(spec.windup) + float(spec.recovery):
			phase = "idle"
			phase_time = 0.0
			_play("Idle")
	else:
		var in_leash := Vector2(player_position.x - spawn_point.x, player_position.z - spawn_point.z).length() < 13.0
		if distance <= float(spec.attack_range) and in_leash and can_attack and attack_gate <= 0.0:
			phase = "attack"
			phase_time = 0.0
			contact_sent = false
			attack_gate = float(spec.contact) + float(spec.cooldown)
			_face(offset)
			_play("Attack")
		elif distance <= float(spec.attack_range) and in_leash:
			velocity.x = 0.0
			velocity.z = 0.0
			_play("Idle")
		elif distance < float(spec.aggro_range) and in_leash:
			velocity.x = offset.normalized().x * float(spec.speed)
			velocity.z = offset.normalized().z * float(spec.speed)
			_face(offset)
			_play("Walk")
		else:
			velocity.x = 0.0
			velocity.z = 0.0
			_play("Idle")
	velocity.y = -1.0 if is_on_floor() else velocity.y - 20.0 * delta
	var before := global_position
	move_and_slide()
	if motion_clip == "Walk" and animations:
		var speed := Vector2(global_position.x - before.x, global_position.z - before.z).length() / delta
		if speed < 0.1: _play("Idle")
		else: animations.speed_scale = clampf(speed / (WALK_NOMINAL_SPEED * float(spec.display_height) / 1.65), 0.2, 1.6)
	return contact

func _face(direction: Vector3) -> void:
	if visual and direction.length_squared() > 0.01:
		visual.rotation.y = atan2(-direction.x, -direction.z)

func _play(clip: String) -> void:
	if animations and motion_clip != clip and animations.has_animation(clip):
		animations.speed_scale = clampf(float(spec.speed) / (WALK_NOMINAL_SPEED * float(spec.display_height) / 1.65), 0.5, 3.2) if clip == "Walk" else 1.0
		animations.play(clip, 0.06)
		motion_clip = clip

func snapshot() -> Dictionary:
	return {"id": enemy_id, "phase": phase, "phase_time": phase_time, "contact_sent": contact_sent, "attack_gate": attack_gate,
		"position": {"x": position.x, "y": position.y, "z": position.z}, "dead": dead,
		"clip": motion_clip, "speed_scale": animations.speed_scale if animations else 0.0, "walk_nominal_speed_at_1_65m": WALK_NOMINAL_SPEED, "clip_position": animations.current_animation_position if animations else 0.0}
