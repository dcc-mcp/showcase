extends Node3D
const Expedition = preload("res://scripts/expedition.gd")
const Courier = preload("res://scripts/courier.gd")
const EnemyActor = preload("res://scripts/enemy_actor.gd")
const Interface = preload("res://scripts/interface.gd")
const ArchiveStage = preload("res://scripts/archive_stage.gd")
const FootstepCadence = preload("res://scripts/footstep_cadence.gd")
const HOME := Vector3(0, 0, 10.0)
const CHEST := Vector3(-5.5, 0, -5.1)
const SPAWN := Vector3(0, -0.05, 11.0)
var config := {}
var expedition
var courier: CharacterBody3D
var ui: CanvasLayer
var camera: Camera3D
var sunlight: DirectionalLight3D
var environment: WorldEnvironment
var generated: Node3D
var sky_material: ProceduralSkyMaterial
var exhibit_view := "orbit"
var asset_instances: Array[Dictionary] = []
var camera_occluders: Array[Dictionary] = []
var torches: Array[OmniLight3D] = []
var loaded_assets := {}
var missing_assets := {}
var asset_map := {}
var guardian: Node3D
var guardian_player: AnimationPlayer
var guardian_motion_clip := ""
var enemies := {}
var drop_visuals := {}
var drop_points := {}
var focus_socket: BoneAttachment3D
var focus_visual: Node3D
var chest_visual: Node3D
var chest_lid: Node3D
var chest_rest := Vector3.ZERO
var chest_progress := 0.0
var chest_opening := false
var bag_open := false
var pending_action := {}
var vfx: MeshInstance3D
var vfx_remaining := 0.0
var audio_voices: Array[AudioStreamPlayer] = []
var audio_cursor := 0
var sfx_enabled := true
var footstep_cadence = FootstepCadence.new()
var mood := "warm"
var visual_time := 0.0
var exhibit_angle := 0.0
var last_reported_state := ""
var generated_instanced_triangles := 0
var qa_enabled := false
var save_path := "user://expedition-save.json"
var save_notice := ""
var toast_key := ""
var toast_until := 0.0

func _ready() -> void:
	qa_enabled = "--qa" in OS.get_cmdline_user_args()
	if qa_enabled:
		save_path = "user://qa-expedition-save.json"
		for argument in OS.get_cmdline_user_args():
			if argument.begins_with("--save-path="):
				var requested := argument.trim_prefix("--save-path=")
				var pattern := RegEx.new()
				pattern.compile("^user://qa-[A-Za-z0-9_-]+[.]json$")
				if pattern.search(requested): save_path = requested
	_install_input()
	config = JSON.parse_string(FileAccess.get_file_as_string("res://data/arpg.json"))
	expedition = Expedition.new(config)
	asset_map = JSON.parse_string(FileAccess.get_file_as_string("res://assets/asset-map.json"))
	_build_world()
	_build_player()
	_build_encounters()
	_validate_combat_contract()
	_build_effects()
	ui = Interface.new()
	ui.name = "UserInterface"
	add_child(ui)
	if OS.has_feature("web"):
		ui.locale = "zh" if JavaScriptBridge.eval("new URLSearchParams(window.location.search).get('lang') || 'en'", true) == "zh" else "en"
	ui.action_requested.connect(_on_action)
	ui.touch_changed.connect(func(axis: Vector2): courier.touch_axis = axis)
	ui.missing_assets = missing_assets.size()
	_set_mood("warm")
	_set_state("title")
	print("RELIC_COURIER_READY ", JSON.stringify(qa_snapshot()))
	call_deferred("_report_first_frame")

func _report_first_frame() -> void:
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	if OS.get_name() == "Windows" and not OS.has_feature("web"):
		print("RELIC_NATIVE_WINDOW ", JSON.stringify({"pid": OS.get_process_id(), "hwnd": DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE), "engine": Engine.get_version_info().string}))
	print("RELIC_FRAME_READY " if _characters_ready() else "RELIC_ASSETS_PENDING ", JSON.stringify(qa_snapshot()))

func _install_input() -> void:
	var keys := {"move_left": [KEY_A, KEY_LEFT], "move_right": [KEY_D, KEY_RIGHT], "move_forward": [KEY_W, KEY_UP],
		"move_back": [KEY_S, KEY_DOWN], "dash": [KEY_SPACE], "interact": [KEY_E], "pause": [KEY_ESCAPE],
		"melee": [KEY_F], "skill": [KEY_Q], "inventory": [KEY_I]}
	for action in keys:
		if not InputMap.has_action(action): InputMap.add_action(action)
		for key in keys[action]:
			var event := InputEventKey.new()
			event.physical_keycode = key
			if not InputMap.action_has_event(action, event): InputMap.action_add_event(action, event)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed and _world_active():
		_request_attack("melee")
		get_viewport().set_input_as_handled()

func _build_world() -> void:
	environment = WorldEnvironment.new()
	environment.name = "SunkenArchiveEnvironment"
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_SKY
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	sky_material = ProceduralSkyMaterial.new()
	var sky := Sky.new()
	sky.sky_material = sky_material
	environment.environment.sky = sky
	add_child(environment)
	sunlight = DirectionalLight3D.new()
	sunlight.name = "ArchiveSun"
	sunlight.rotation_degrees = Vector3(-38, -28, 0)
	sunlight.shadow_enabled = true
	sunlight.directional_shadow_max_distance = 70
	add_child(sunlight)
	camera = Camera3D.new()
	camera.name = "ExpeditionCamera"
	camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	camera.fov = 48.0
	camera.near = 0.10
	camera.far = 150.0
	add_child(camera)
	camera.current = true
	generated = Node3D.new()
	generated.name = "Hyper3DGeneratedAssets"
	add_child(generated)
	ArchiveStage.new().build(self)
	var dais := CylinderMesh.new()
	dais.top_radius = 2.0
	dais.bottom_radius = 2.2
	dais.height = 0.3
	dais.radial_segments = 12
	_mesh(dais, _material(Color("7b6845"), 0.5), Vector3(0, 0.15, 0))
	guardian = _asset("guardian_character", Vector3(0, 0.3, 0), 3.1, 4.2)
	guardian_player = _character_animation(guardian, "guardian_character")
	_proxy(Vector3(0, 1.2, 0), Vector3(1.5, 2.4, 1.5))
	_play_guardian("Idle")
	for point in [Vector3(-12, 0, -2.6), Vector3(12, 0, -1.0)]:
		_asset("pedestal", point, 1.5, 2.0)
		_asset("crystal", point + Vector3(0, 1.65, 0), 0.8, 1.4)
		_proxy(point + Vector3(0, 0.65, 0), Vector3(0.9, 1.3, 0.9))
	_ring(HOME + Vector3(0, 0.09, 0), 2.0, Color("79d9d2"))
	_apply_exhibit_view("arrival-wide")

func build_interactive_chest() -> void:
	chest_visual = _asset("chest_interactive", CHEST, 1.35, 2.0)
	chest_visual.rotation.y = -0.25
	chest_lid = chest_visual.find_child("Lid", true, false)
	if chest_lid:
		chest_rest = chest_lid.rotation
	else:
		missing_assets["chest_interactive"] = "Real hinged Lid node required"
	_proxy(CHEST + Vector3(0, 0.5, 0), Vector3(1.45, 1.0, 1.45))

func _build_encounters() -> void:
	for encounter in config.encounters:
		var actor := CharacterBody3D.new()
		actor.set_script(EnemyActor)
		actor.name = String(encounter.id).capitalize()
		add_child(actor)
		var spec: Dictionary = config.enemy_variants[encounter.variant]
		var visual := _asset(String(spec.asset_key), Vector3.ZERO, float(spec.display_height), 4.2, actor)
		visual.position.y = 0.05
		var player := _character_animation(visual, "guardian_character")
		var point := Vector3(encounter.position[0], encounter.position[1], encounter.position[2])
		actor.setup(encounter.id, spec, point, visual, player)
		enemies[encounter.id] = actor

func _validate_combat_contract() -> void:
	if not courier.animations or not guardian_player: return
	for skill in config.skills:
		var spec: Dictionary = config.skills[skill]
		var clip := "Cast" if skill == "arc_bolt" else "Attack"
		if not courier.animations.has_animation(clip): continue
		var length: float = courier.animations.get_animation(clip).length
		if not is_equal_approx(length, float(spec.windup) + float(spec.recovery)) or float(spec.contact) > length:
			missing_assets["combat_contract"] = "Skill timing must match the imported action clip: " + skill
	for variant in config.enemy_variants:
		var spec: Dictionary = config.enemy_variants[variant]
		if guardian_player.has_animation("Attack") and not is_equal_approx(guardian_player.get_animation("Attack").length, float(spec.windup) + float(spec.recovery)):
			missing_assets["combat_contract"] = "Enemy timing must match imported Attack: " + variant

func _build_focus_socket(character: Node3D) -> void:
	var skeletons := character.find_children("*", "Skeleton3D", true, false)
	if skeletons.is_empty(): return
	var skeleton: Skeleton3D = skeletons[0]
	for index in range(skeleton.get_bone_count()):
		var label := skeleton.get_bone_name(index).to_lower()
		if "hand" in label and ("right" in label or label.ends_with(".r") or label.ends_with("_r")):
			focus_socket = BoneAttachment3D.new()
			focus_socket.name = "EquippedArcFocusSocket"
			skeleton.add_child(focus_socket)
			focus_socket.bone_idx = index
			focus_visual = _asset("crystal", Vector3(0, 0.02, 0), 0.22, 0.3, focus_socket)
			focus_visual.visible = false
			return

func _build_effects() -> void:
	vfx = _mesh(BoxMesh.new(), _material(Color("70e7df"), 0.0, true), Vector3.ZERO)
	vfx.name = "AuthoredArcBeam"
	vfx.visible = false
	for index in range(4):
		var voice := AudioStreamPlayer.new()
		voice.name = "CourierFootsteps" if index == 0 else "LicensedSfxVoice%d" % index
		voice.volume_db = -23.0 if index == 0 else -16.0
		voice.max_polyphony = 1
		add_child(voice)
		audio_voices.append(voice)

func _sound(name: String) -> void:
	if not sfx_enabled: return
	var path := "res://audio/" + name + ".ogg"
	if ResourceLoader.exists(path) and not audio_voices.is_empty():
		var footstep := name == "footstep00"
		var voice := audio_voices[0] if footstep else audio_voices[1 + audio_cursor]
		if footstep and voice.playing: return
		if not footstep: audio_cursor = (audio_cursor + 1) % (audio_voices.size() - 1)
		var stream = load(path).duplicate()
		if stream is AudioStreamOggVorbis: stream.loop = false
		voice.stream = stream
		voice.play()

func _update_footsteps(delta: float) -> void:
	var walking: bool = _world_active() and courier.is_on_floor() and courier.locomotion_speed > 0.15 \
		and courier.dash_remaining <= 0.0 and courier.action_clip == ""
	if footstep_cadence.advance(courier.grounded_motion_distance, delta, walking):
		_sound("footstep00")

func _world_active() -> bool:
	return expedition != null and expedition.state == "playing" and not bag_open

func _physics_process(delta: float) -> void:
	if not expedition or not ui: return
	if _world_active():
		expedition.tick(delta)
		_update_zone()
		_update_player_action(delta)
		_update_chest(delta)
		var enemy_stats: Dictionary = expedition.snapshot().enemies
		for id in enemies:
			var actor = enemies[id]
			if actor.tick_actor(delta, courier.global_position, expedition.zone == "wilderness", float(enemy_stats[id].cooldown) <= 0.0):
				if courier.dash_remaining <= 0.0 and courier.invulnerable <= 0.0 and _line_clear(actor.global_position, courier.global_position, [actor.get_rid(), courier.get_rid()]):
					var outcome: Dictionary = expedition.enemy_damage_player(id, _flat_distance(actor.global_position, courier.global_position))
					if outcome.ok:
						courier.invulnerable = 0.6
						_sound("chop")
		if courier.position.y < -2.0:
			courier.reset_at(SPAWN)
			pending_action.clear()
			expedition.enter_zone("town")
			_toast("fall_recovered")
		_follow_camera(delta)
		if Input.is_action_just_pressed("interact"): _interact()
		if Input.is_action_just_pressed("melee"): _request_attack("melee")
		if Input.is_action_just_pressed("skill"): _request_attack("arc_bolt")
	_update_footsteps(delta)
	if Input.is_action_just_pressed("inventory") and expedition.state == "playing": _on_action("bag")
	if Input.is_action_just_pressed("pause"): _on_action("pause")
	if expedition.state != last_reported_state: _set_state(expedition.state)
	_consume_events()

func _process(delta: float) -> void:
	visual_time += delta
	if not ui or not expedition: return
	if vfx_remaining > 0.0 and _world_active():
		vfx_remaining -= delta
		vfx.visible = vfx_remaining > 0.0
	if expedition.state == "exhibit" and exhibit_view == "orbit":
		exhibit_angle += delta * 0.035
		camera.position = Vector3(cos(exhibit_angle) * 30.0, 17.0, sin(exhibit_angle) * 30.0 + 2.0)
		camera.look_at(Vector3(0, 2.5, -1.0))
	var stats: Dictionary = expedition.snapshot()
	var target := _nearest_enemy(10.0)
	if target != "": stats["target"] = stats.enemies[target]
	ui.update_game(stats, courier.cooldown, _near_prompt(), _danger())
	if toast_until > visual_time and expedition.state == "playing": ui.note.text = ui.t(toast_key)
	_update_occluders(delta)

func _update_zone() -> void:
	var next := "wilderness" if courier.position.z < -20.0 else "town"
	if expedition.zone != next: expedition.enter_zone(next)

func _request_attack(skill: String) -> void:
	if not _world_active() or not pending_action.is_empty() or chest_opening: return
	var stats: Dictionary = expedition.snapshot()
	if expedition.zone != "wilderness":
		_toast("safe_town")
		return
	if skill == "arc_bolt" and not _arc_unlocked(stats):
		_toast("skill_locked")
		return
	var definition: Dictionary = config.skills[skill]
	if float(stats.get("cooldowns", {}).get(skill, 0.0)) > 0.0:
		_toast("cooldown")
		return
	if float(stats.get("mana", 0.0)) < float(definition.mana_cost):
		_toast("no_mana")
		return
	var target := _nearest_enemy(float(definition.range) + 1.5)
	var point: Vector3 = enemies[target].global_position if target != "" else courier.global_position + courier.heading * 2.0
	var clip := "Cast" if skill == "arc_bolt" else "Attack"
	if not courier.animations or not courier.animations.has_animation(clip):
		_toast("assets_pending")
		return
	pending_action = {"skill": skill, "target": target, "elapsed": 0.0, "contact": float(definition.contact),
		"duration": float(definition.windup) + float(definition.recovery), "sent": false}
	courier.set_action(clip, point)
	_sound("knifeSlice")

func _update_player_action(delta: float) -> void:
	if pending_action.is_empty(): return
	pending_action.elapsed += delta
	if pending_action.elapsed >= pending_action.contact and not pending_action.sent:
		pending_action.sent = true
		var id: String = pending_action.target
		if enemies.has(id) and not enemies[id].dead:
			var target: Vector3 = enemies[id].global_position
			if _line_clear(courier.global_position, target, [courier.get_rid(), enemies[id].get_rid()]):
				var outcome: Dictionary = expedition.request_player_attack(pending_action.skill, id, _flat_distance(courier.global_position, target))
				if outcome.ok:
					_sound("chop")
					if pending_action.skill == "arc_bolt": _show_arc(target)
				else: _toast(String(outcome.reason))
			else: _toast("blocked")
		else: _toast("whiff")
	if pending_action.elapsed >= pending_action.duration:
		pending_action.clear()
		courier.set_action("")

func _show_arc(target: Vector3) -> void:
	var origin := focus_socket.global_position if focus_socket else courier.global_position + Vector3(0, 1.15, 0)
	var finish := target + Vector3(0, 1.1, 0)
	(vfx.mesh as BoxMesh).size = Vector3(0.065, 0.065, origin.distance_to(finish))
	vfx.position = (origin + finish) * 0.5
	vfx.look_at(finish)
	vfx.visible = true
	vfx_remaining = 0.16

func _nearest_enemy(radius: float) -> String:
	var nearest := ""
	for id in enemies:
		if enemies[id].dead: continue
		var distance := _flat_distance(courier.global_position, enemies[id].global_position)
		if distance < radius:
			radius = distance
			nearest = id
	return nearest

func _line_clear(start: Vector3, finish: Vector3, exclusions: Array[RID]) -> bool:
	var query := PhysicsRayQueryParameters3D.create(start + Vector3(0, 1, 0), finish + Vector3(0, 1, 0), 1 | 2, exclusions)
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()

func _flat_distance(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x - b.x, a.z - b.z).length()

func _distance(point: Vector3) -> float:
	return _flat_distance(courier.global_position, point)

func _danger() -> bool:
	for actor in enemies.values():
		if actor.phase == "attack" and not actor.dead: return true
	return false

func _arc_unlocked(stats: Dictionary) -> bool:
	var skills = stats.get("unlocked_skills", stats.get("skills", []))
	return skills.has("arc_bolt")

func _near_drop() -> String:
	var stats: Dictionary = expedition.snapshot()
	for id in stats.get("drops", {}):
		var drop: Dictionary = stats.drops[id]
		if not drop.get("picked", false) and drop_points.has(id) and _distance(drop_points[id]) <= 2.0: return id
	return ""

func _near_prompt() -> String:
	if not _world_active(): return ""
	if chest_opening: return "chest_opening"
	if _near_drop() != "": return "pickup"
	if _distance(CHEST) <= 2.0:
		return "chest_opened" if _chest_opened() else "open_chest"
	if _distance(HOME) < 2.3 and expedition.quest_complete: return "expedition_complete"
	if _distance(HOME) < 2.3: return "turn_in" if expedition.snapshot().get("goal_ready", false) else "town_hint"
	return ""

func _interact() -> void:
	if not _world_active(): return
	var drop := _near_drop()
	if drop != "":
		var outcome: Dictionary = expedition.pickup(drop, _distance(drop_points[drop]))
		if outcome.ok:
			_sound("handleCoins")
			_toast("already_owned" if outcome.get("already_owned", false) else "picked_up")
			_save_progress()
		return
	if _distance(CHEST) <= 2.0:
		if chest_opening: _toast("chest_opening")
		elif _chest_opened(): _toast("chest_opened")
		elif chest_lid:
			chest_opening = true
			chest_progress = 0.0
			_sound("creak1")
		return
	if _distance(HOME) < 2.3:
		if expedition.quest_complete:
			_toast("expedition_complete")
			return
		var outcome: Dictionary = expedition.turn_in(_distance(HOME))
		if outcome.ok: _save_progress()
		else: _toast("town_hint")

func _chest_opened() -> bool:
	return "town_chest" in expedition.snapshot().get("opened_chests", [])

func _update_chest(delta: float) -> void:
	if not chest_lid: return
	if chest_opening:
		if _distance(CHEST) > float(config.chests.town_chest.range):
			chest_opening = false
			chest_progress = 0.0
			_toast("chest_cancelled")
		else:
			chest_progress = minf(1.0, chest_progress + delta / 0.75)
			if chest_progress >= 1.0:
				chest_opening = false
				var outcome: Dictionary = expedition.open_chest("town_chest", _distance(CHEST))
				if outcome.ok:
					_save_progress()
					_chest_particles()
				else:
					chest_progress = 0.0
					_toast(String(outcome.reason))
	chest_lid.rotation = chest_rest + Vector3(-deg_to_rad(100.0) * (1.0 if _chest_opened() else smoothstep(0.0, 1.0, chest_progress)), 0, 0)

func _chest_particles() -> void:
	var particles := CPUParticles3D.new()
	particles.name = "AuthoredChestDust"
	particles.one_shot = true
	particles.amount = 14
	particles.lifetime = 0.65
	particles.explosiveness = 0.9
	particles.direction = Vector3.UP
	particles.spread = 35.0
	particles.initial_velocity_min = 0.3
	particles.initial_velocity_max = 0.8
	particles.gravity = Vector3(0, -0.5, 0)
	particles.color = Color("d9c689")
	particles.mesh = SphereMesh.new()
	particles.mesh.radius = 0.025
	particles.mesh.height = 0.05
	add_child(particles)
	particles.add_to_group("ExpeditionEffects")
	particles.global_position = CHEST + Vector3(0, 0.9, 0)
	particles.finished.connect(particles.queue_free)
	particles.emitting = true

func _consume_events() -> void:
	for event in expedition.drain_events():
		print("RELIC_EVENT ", JSON.stringify(event))
	var stats: Dictionary = expedition.snapshot()
	for id in enemies:
		var record: Dictionary = stats.get("enemies", {}).get(id, {})
		var killed: bool = record.get("dead", false) or float(record.get("health", 1)) <= 0.0
		if killed and not enemies[id].dead:
			drop_points["enemy:" + id] = enemies[id].global_position + Vector3(0, 0.8, 0)
			enemies[id].reset_actor(true)
			_save_progress()
	for id in stats.get("drops", {}):
		var drop: Dictionary = stats.drops[id]
		var point := CHEST + Vector3(0, 0.95, 0)
		var owner: String = String(drop.get("enemy_id", drop.get("source_id", "")))
		if enemies.has(owner): point = enemies[owner].global_position + Vector3(0, 0.8, 0)
		elif id != "chest:town_chest":
			for enemy_id in enemies:
				if String(id).contains(enemy_id): point = enemies[enemy_id].spawn_point + Vector3(0, 0.8, 0)
		point = drop_points.get(id, point)
		drop_points[id] = point
		if not drop_visuals.has(id):
			drop_visuals[id] = _asset("crystal", point, 0.35, 0.5)
		drop_visuals[id].position = drop_points[id]
		drop_visuals[id].visible = not drop.get("picked", false)
	if focus_visual: focus_visual.visible = stats.get("equipment", {}).get("focus", "") == "arc_focus"

func _on_action(action: String) -> void:
	if action.begins_with("equip:"):
		var outcome: Dictionary = expedition.equip(action.trim_prefix("equip:"))
		if outcome.ok:
			_sound("metalLatch")
			_save_progress()
			_consume_events()
			ui.show_bag(expedition.snapshot())
		return
	match action:
		"start":
			if not _characters_ready(): return
			AudioServer.set_bus_mute(0, not sfx_enabled)
			if expedition.state in ["won", "lost"]:
				expedition.restore_save(expedition.to_save())
			else:
				expedition.start()
				_load_progress()
			_reset_world()
			_set_state("playing" if expedition.quest_complete else expedition.state)
		"sfx":
			sfx_enabled = not sfx_enabled
			AudioServer.set_bus_mute(0, not sfx_enabled)
			ui.sfx_on = sfx_enabled
			ui.show_state(expedition.state, expedition.snapshot())
		"pause":
			if bag_open: _on_action("bag")
			elif expedition.state in ["playing", "paused"]:
				expedition.toggle_pause()
				_set_state(expedition.state)
		"bag":
			if expedition.state != "playing": return
			bag_open = not bag_open
			_sync_controls()
			ui.show_bag(expedition.snapshot()) if bag_open else ui.show_state("playing", expedition.snapshot())
		"menu":
			if not _save_progress():
				var description := ui.modal_box.get_node_or_null("ScreenDescription") as Label
				if description: description.text = ui.t("save_failed")
				return
			bag_open = false
			_set_state("title")
		"language":
			ui.change_locale()
			ui.show_bag(expedition.snapshot()) if bag_open else ui.show_state(expedition.state, expedition.snapshot())
		"mood": _set_mood("moon" if mood == "warm" else "warm")
		"touch":
			ui.touch_visible = not ui.touch_visible
			ui.show_bag(expedition.snapshot()) if bag_open else ui.show_state(expedition.state, expedition.snapshot())
			ui.clear_touch()
		"dash": courier.request_dash()
		"interact": _interact()
		"melee": _request_attack("melee")
		"skill": _request_attack("arc_bolt")

func _reset_world() -> void:
	bag_open = false
	pending_action.clear()
	chest_opening = false
	chest_progress = 0.0
	courier.reset_at(SPAWN)
	drop_points.clear()
	for visual in drop_visuals.values(): visual.visible = false
	for actor in enemies.values(): actor.reset_actor(false)
	_consume_events()
	_update_chest(0.0)
	_follow_camera(1.0)

func _set_state(state: String) -> void:
	expedition.state = state
	last_reported_state = state
	if state in ["title", "won", "lost"]:
		pending_action.clear()
		courier.set_action("")
	if state != "playing": bag_open = false
	_sync_controls()
	ui.show_state(state, expedition.snapshot())
	if state == "title": _apply_exhibit_view("arrival-wide")
	print("RELIC_STATE ", JSON.stringify(qa_snapshot()))

func _sync_controls() -> void:
	courier.enabled = _world_active()
	courier.pause_animation(expedition.state == "paused" or bag_open)
	if not _world_active() and courier.model: courier.model.visible = true
	if guardian_player: guardian_player.active = expedition.state != "paused" and not bag_open
	for actor in enemies.values():
		if actor.animations: actor.animations.active = _world_active()
	for effect in get_tree().get_nodes_in_group("ExpeditionEffects"):
		effect.speed_scale = 1.0 if _world_active() else 0.0
	for voice in audio_voices:
		# One-shots must not queue silently in menus and burst on resume.
		if not _world_active(): voice.stop()
		voice.stream_paused = false
	if not _world_active():
		footstep_cadence.reset(courier.grounded_motion_distance)
		if not audio_voices.is_empty(): audio_voices[0].stop()
	courier.touch_axis = Vector2.ZERO
	ui.clear_touch()

func _toast(key: String) -> void:
	toast_key = key
	toast_until = visual_time + 2.8

func _read_verified_save(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {"ok": false, "exists": false}
	var file := FileAccess.open(path, FileAccess.READ)
	if not file: return {"ok": false, "exists": true}
	# The persistent schema is only a few KiB. Bound allocation before JSON parsing.
	if file.get_length() > 65536:
		file.close()
		return {"ok": false, "exists": true}
	var parser := JSON.new()
	var parse_error := parser.parse(file.get_as_text())
	file.close()
	if parse_error != OK: return {"ok": false, "exists": true}
	var value = parser.data
	if not value is Dictionary: return {"ok": false, "exists": true}
	var probe = Expedition.new(config)
	var validation: Dictionary = probe.restore_save(value)
	return {"ok": validation.ok, "exists": true, "value": value}

func _save_progress() -> bool:
	var temp := save_path + ".tmp"
	var backup := save_path + ".bak"
	var file := FileAccess.open(temp, FileAccess.WRITE)
	if not file:
		_toast("save_failed")
		return false
	file.store_string(JSON.stringify(expedition.to_save()))
	file.flush()
	var write_error := file.get_error()
	file.close()
	if write_error != OK or not _read_verified_save(temp).ok:
		_toast("save_failed")
		return false
	var absolute := ProjectSettings.globalize_path(save_path)
	var previous := ProjectSettings.globalize_path(backup)
	var primary: Dictionary = _read_verified_save(save_path)
	if primary.exists:
		if primary.ok:
			if FileAccess.file_exists(backup):
				var backup_result: Dictionary = _read_verified_save(backup)
				var backup_error := DirAccess.remove_absolute(previous) if backup_result.ok else DirAccess.rename_absolute(previous, previous + ".rejected-" + str(Time.get_ticks_usec()))
				if backup_error != OK:
					_toast("save_failed")
					return false
			if DirAccess.rename_absolute(absolute, previous) != OK:
				_toast("save_failed")
				return false
		else:
			# Preserve rejected bytes; never replace the valid backup with corruption.
			var rejected := absolute + ".rejected-" + str(Time.get_unix_time_from_system()) + "-" + str(Time.get_ticks_usec())
			if DirAccess.rename_absolute(absolute, rejected) != OK:
				_toast("save_failed")
				return false
	if DirAccess.rename_absolute(ProjectSettings.globalize_path(temp), absolute) != OK:
		# Keep the verified backup in place for the bounded loader on next launch.
		_toast("save_failed")
		return false
	return true

func _load_progress() -> void:
	var rejected := false
	for candidate in [save_path, save_path + ".bak"]:
		var result: Dictionary = _read_verified_save(candidate)
		if result.ok:
			expedition.restore_save(result.value)
			save_notice = "save_loaded"
			_toast(save_notice)
			return
		rejected = rejected or result.exists
	if rejected:
		expedition.start()
		save_notice = "save_invalid"
		_toast(save_notice)

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and is_instance_valid(ui):
		ui.clear_touch()
		courier.touch_axis = Vector2.ZERO
		if expedition.state == "playing" and not bag_open: _on_action("pause")

func _build_player() -> void:
	courier = CharacterBody3D.new()
	courier.name = "Courier"
	courier.set_script(Courier)
	add_child(courier)
	var collider := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.25
	capsule.height = 1.0
	collider.shape = capsule
	collider.position.y = 0.55
	courier.add_child(collider)
	var body := Node3D.new()
	body.name = "CourierModel"
	body.position.y = collider.position.y - capsule.height * 0.5
	courier.add_child(body)
	courier.model = body
	var character := _asset("courier_character", Vector3.ZERO, 1.65, 2.0, body)
	courier.bind_animation_player(_character_animation(character, "courier_character"))
	courier.collision_layer = 4
	courier.collision_mask = 1 | 2
	courier.reset_at(SPAWN)
	_build_focus_socket(character)

func _set_mood(value: String) -> void:
	mood = value
	ui.mood = mood
	var warm := mood == "warm"
	sky_material.sky_top_color = Color("203441") if warm else Color("080e23")
	sky_material.sky_horizon_color = Color("71827e") if warm else Color("273b55")
	sky_material.ground_horizon_color = sky_material.sky_horizon_color
	sky_material.ground_bottom_color = Color("132932") if warm else Color("070e1b")
	environment.environment.ambient_light_color = Color("9faeaa") if warm else Color("849fce")
	environment.environment.ambient_light_energy = 0.25
	sunlight.light_color = Color("ffe3bb") if warm else Color("9ebdff")
	sunlight.light_energy = 0.62 if warm else 0.42
	for torch in torches:
		torch.light_energy = 0.45 if warm else 0.70
	ui._refresh_header()

func _asset(key: String, point: Vector3, target_height := -1.0, width_limit := 4.5, visual_parent: Node3D = null) -> Node3D:
	var holder := Node3D.new()
	holder.name = key.capitalize()
	holder.position = point
	(visual_parent if visual_parent else generated).add_child(holder)
	var spec: Dictionary = asset_map.get(key, {})
	var path: String = spec.get("path", "res://assets/" + key.replace("_", "-") + ".glb")
	if ResourceLoader.exists(path):
		var packed = load(path)
		if packed is PackedScene:
			var model: Node3D = packed.instantiate()
			holder.add_child(model)
			if key in ["arch", "guardian"]:
				_adapt_archive_stone(model, key)
			var measured := _measure_meshes(model, model, [])
			if measured.size() > 0:
				var bounds: AABB = measured[0]
				var height: float = target_height if target_height > 0 else float(spec.get("height", 1.5))
				var factor := height / maxf(bounds.size.y, 0.001)
				factor = minf(factor, width_limit / maxf(bounds.size.x, bounds.size.z))
				model.scale *= factor
				model.position -= Vector3(bounds.get_center().x, bounds.position.y, bounds.get_center().z) * factor
				var triangles: int = measured[1]
				loaded_assets[key] = {"path": path, "source_bounds": {"x": bounds.size.x, "y": bounds.size.y, "z": bounds.size.z}, "scale": factor, "triangles": triangles}
				asset_instances.append({"key": key, "x": point.x, "y": point.y, "z": point.z, "target_height": height, "scale": factor, "triangles": triangles})
				generated_instanced_triangles += triangles
				if key in ["column", "shrine", "gate", "arch", "portal"]:
					_register_occluder(holder, key)
				return holder
	missing_assets[key] = path
	if key in ["courier_character", "guardian_character", "chest_interactive"]:
		push_error("Required generated character unavailable: " + path)
		return holder
	# shortcut: explicit development proxies; replace with cleared GLBs before acceptance.
	var mesh := MeshInstance3D.new()
	var prism := CylinderMesh.new()
	prism.top_radius = 0.3
	prism.bottom_radius = 0.5
	prism.height = float(spec.get("height", 1.0))
	prism.radial_segments = 5
	mesh.mesh = prism
	mesh.position.y = prism.height * 0.5
	mesh.material_override = _material(Color("a05487"))
	holder.add_child(mesh)
	return holder

func _character_animation(character: Node3D, key: String) -> AnimationPlayer:
	if missing_assets.has(key):
		return null
	var players := character.find_children("*", "AnimationPlayer", true, false)
	if players.size() != 1:
		missing_assets[key] = "Exactly one authored AnimationPlayer is required"
		push_error(key + ": " + str(missing_assets[key]))
		return null
	var player: AnimationPlayer = players[0]
	var skeletons := character.find_children("*", "Skeleton3D", true, false)
	var skinned_meshes := 0
	for mesh in character.find_children("*", "MeshInstance3D", true, false):
		if mesh.skin != null and mesh.get_node_or_null(mesh.skeleton) is Skeleton3D:
			skinned_meshes += 1
	if skeletons.is_empty() or skinned_meshes == 0:
		missing_assets[key] = "A bound skeleton and skinned provider mesh are required"
		push_error(key + ": " + str(missing_assets[key]))
		return null
	var clips := {}
	for clip in (["Idle", "Walk", "Dash", "Attack", "Cast"] if key == "courier_character" else ["Idle", "Walk", "Dash", "Attack"]):
		if not player.has_animation(clip):
			missing_assets[key] = "Missing required authored clip: " + clip
			push_error(key + ": " + str(missing_assets[key]))
			return null
		var animation := player.get_animation(clip)
		animation.loop_mode = Animation.LOOP_LINEAR if clip in ["Idle", "Walk"] else Animation.LOOP_NONE
		clips[clip] = animation.length
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	loaded_assets[key]["animation_player"] = String(player.get_path())
	loaded_assets[key]["authored_clips"] = clips
	loaded_assets[key]["skeleton_paths"] = skeletons.map(func(skeleton: Node): return String(skeleton.get_path()))
	loaded_assets[key]["skinned_meshes"] = skinned_meshes
	return player

func _register_occluder(holder: Node3D, key: String) -> void:
	var materials := []
	var meshes := holder.find_children("*", "MeshInstance3D", true, false)
	if holder is MeshInstance3D: meshes.append(holder)
	for mesh in meshes:
		# Native authored props use a whole-mesh override, which masks surface overrides.
		if mesh.material_override is StandardMaterial3D:
			var override_material: StandardMaterial3D = mesh.material_override.duplicate()
			mesh.material_override = override_material
			materials.append({"material": override_material, "alpha": override_material.albedo_color.a, "transparency": override_material.transparency})
			continue
		for index in range(mesh.mesh.get_surface_count()):
			var source: Material = mesh.get_active_material(index)
			if source is StandardMaterial3D:
				var material: StandardMaterial3D = source.duplicate()
				mesh.set_surface_override_material(index, material)
				materials.append({"material": material, "alpha": material.albedo_color.a, "transparency": material.transparency})
	camera_occluders.append({"holder": holder, "key": key, "meshes": meshes, "materials": materials, "alpha": 1.0, "occluded": false})

func _update_occluders(delta: float) -> void:
	# Only presentation changes: the camera and all physics proxies stay intact.
	var targets := _body_sight_points(courier.global_position, 1.65, 0.52)
	var target_id := _nearest_enemy(10.0)
	if target_id != "":
		var actor = enemies[target_id]
		var height: float = actor.spec.display_height
		var measured: Dictionary = loaded_assets.guardian_character.source_bounds
		var radius := float(measured.x) * height / float(measured.y) * 0.5 + 0.15
		targets.append_array(_body_sight_points(actor.global_position, height, radius))
	for record in camera_occluders:
		var blocked := false
		if _world_active():
			for mesh in record.meshes:
				var inverse: Transform3D = mesh.global_transform.affine_inverse()
				var start: Vector3 = inverse * camera.global_position
				var bounds: AABB = mesh.get_aabb().grow(0.08)
				for target in targets:
					var finish: Vector3 = inverse * target
					if bounds.intersects_segment(start, finish) != null:
						blocked = true
						break
				if blocked: break
		record.occluded = blocked
		# Fade immediately for input readability; restore smoothly after passing.
		record.alpha = 0.18 if blocked else (lerpf(record.alpha, 1.0, minf(delta * 9.0, 1.0)) if _world_active() else 1.0)
		for entry in record.materials:
			var material: StandardMaterial3D = entry.material
			material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA if record.alpha < 0.99 else entry.transparency
			var color := material.albedo_color
			color.a = entry.alpha * record.alpha
			material.albedo_color = color

func _body_sight_points(origin: Vector3, height: float, radius: float) -> Array[Vector3]:
	var result: Array[Vector3] = []
	var screen_right := Vector3(camera.global_basis.x.x, 0, camera.global_basis.x.z).normalized()
	# Bounded9rays include feet/head and both sides of the measured character body.
	for offset in [-radius, 0.0, radius]:
		for elevation in [0.15, height * 0.5, height * 0.95]:
			result.append(origin + screen_right * offset + Vector3.UP * elevation)
	return result

func _characters_ready() -> bool:
	return courier != null and courier.animations != null and guardian_player != null and missing_assets.is_empty()

func _play_guardian(clip: String) -> void:
	if guardian_player and guardian_motion_clip != clip:
		guardian_player.play(clip, 0.08)
		guardian_motion_clip = clip

func _adapt_archive_stone(node: Node, key: String) -> void:
	# Scene-only art adaptation. Keep provider texture slots; never mutate GLBs.
	if node is MeshInstance3D and node.mesh:
		for surface in range(node.mesh.get_surface_count()):
			var source: Material = node.get_active_material(surface)
			if source is StandardMaterial3D:
				var material: StandardMaterial3D = source.duplicate()
				if key == "arch" and material.albedo_texture == null and material.emission_texture != null:
					# The API baked this asset into emission. Reuse its image and UVs
					# as lit stone; no image or GLB data is changed.
					material.albedo_texture = material.emission_texture
					material.albedo_color = Color.WHITE
					material.emission_enabled = false
				material.albedo_color *= Color("8c988e") if key == "guardian" else Color("b9ad91")
				material.roughness = maxf(material.roughness, 0.9)
				material.metallic = minf(material.metallic, 0.05)
				if material.albedo_texture == null:
					var weathering := ArchiveStage.new().weathered(Color.WHITE, 115 if key == "guardian" else 118)
					material.albedo_texture = weathering.albedo_texture
					material.uv1_triplanar = true
					material.uv1_world_triplanar = true
					material.uv1_scale = Vector3.ONE * 0.45
				node.set_surface_override_material(surface, material)
	for child in node.get_children():
		_adapt_archive_stone(child, key)

func _measure_meshes(node: Node, model: Node3D, accumulator: Array) -> Array:
	if node is MeshInstance3D and node.mesh:
		var bounds: AABB = (model.global_transform.affine_inverse() * node.global_transform) * node.get_aabb()
		var triangles := 0
		for surface in range(node.mesh.get_surface_count()):
			var arrays: Array = node.mesh.surface_get_arrays(surface)
			var indices = arrays[Mesh.ARRAY_INDEX]
			triangles += indices.size() / 3 if indices != null and indices.size() else arrays[Mesh.ARRAY_VERTEX].size() / 3
		if accumulator.is_empty():
			accumulator.append(bounds)
			accumulator.append(triangles)
		else:
			accumulator[0] = accumulator[0].merge(bounds)
			accumulator[1] += triangles
	for child in node.get_children():
		_measure_meshes(child, model, accumulator)
	return accumulator

func _material(color: Color, metallic := 0.0, emissive := false) -> StandardMaterial3D:
	var result := StandardMaterial3D.new()
	result.albedo_color = color
	result.roughness = 0.8
	result.metallic = metallic
	if emissive:
		result.emission_enabled = true
		result.emission = color
		result.emission_energy_multiplier = 0.8
	return result

func _mesh(shape: Mesh, material: Material, point: Vector3) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	instance.mesh = shape
	instance.material_override = material
	instance.position = point
	add_child(instance)
	return instance

func _box(label: String, size: Vector3, point: Vector3, material: Material, collision := false, visible_mesh := true) -> void:
	if visible_mesh:
		var mesh := BoxMesh.new()
		mesh.size = size
		var instance := _mesh(mesh, material, point)
		instance.name = label
		if label in ["ArchiveFacade", "ArchiveDoorReveal", "ArchiveEntranceLintel", "WestArchiveTower"]:
			_register_occluder(instance, label)
	if collision:
		_proxy(point, size)

func _proxy(point: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.name = "GameplayCollisionProxy"
	body.position = point
	var collider := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collider.shape = shape
	body.add_child(collider)
	add_child(body)

func _light(point: Vector3, color: Color, energy: float, radius: float) -> OmniLight3D:
	var light := OmniLight3D.new()
	light.position = point
	light.light_color = color
	light.light_energy = energy
	light.omni_range = radius
	add_child(light)
	return light

func _ring(point: Vector3, radius: float, color: Color) -> MeshInstance3D:
	var torus := TorusMesh.new()
	torus.inner_radius = radius - 0.035
	torus.outer_radius = radius + 0.035
	torus.rings = 32
	torus.ring_segments = 4
	return _mesh(torus, _material(color, 0.3, true), point)

func qa_snapshot() -> Dictionary:
	var result: Dictionary = expedition.snapshot() if expedition else {}
	result.merge({"engine": Engine.get_version_info().string, "locale": ui.locale if ui else "en", "mood": mood,
		"viewport": {"width": get_viewport().get_visible_rect().size.x, "height": get_viewport().get_visible_rect().size.y},
		"generated_assets": loaded_assets, "missing_assets": missing_assets, "generated_instanced_triangles": generated_instanced_triangles,
		"stage_revision": "Sunken Archive expedition", "generated_instances": asset_instances, "camera_view": exhibit_view,
		"characters_ready": _characters_ready(), "courier_animation": courier.animation_snapshot() if courier else {},
		"enemy_actors": enemies.values().map(func(actor): return actor.snapshot()), "pending_action": pending_action,
		"audio": {"sfx_enabled": sfx_enabled, "master_muted": AudioServer.is_bus_mute(0), "max_voices": audio_voices.size()}, "bag_open": bag_open, "chest_opening": chest_opening, "chest_progress": chest_progress,
		"lid_path": String(chest_lid.get_path()) if chest_lid else "", "save_notice": save_notice,
		"occluded_architecture": camera_occluders.filter(func(record: Dictionary): return record.occluded).map(func(record: Dictionary): return {"key": record.key, "path": String(record.holder.get_path()), "alpha": record.alpha}),
		"walkable_bounds_m": {"x": 30.0, "z": 59.0}, "rear_ramp_rise_m": 0.7, "rear_ramp_length_m": 3.1,
		"player_position": {"x": courier.position.x, "y": courier.position.y, "z": courier.position.z} if courier else {},
		"dash_cooldown": courier.cooldown if courier else 0.0, "distance_moved": courier.motion_distance if courier else 0.0,
		"qa_enabled": qa_enabled})
	return result

func qa_stage(state: String) -> Dictionary:
	if not qa_enabled or state not in ["title", "playing", "paused", "won", "lost", "exhibit"]:
		return {"error": "QA state staging requires --qa and a known state"}
	expedition.start()
	_reset_world()
	_set_state(state)
	return qa_snapshot()

func qa_layout_snapshot() -> Dictionary:
	var controls := []
	for control in ui.root.find_children("*", "Control", true, false):
		if not control.is_visible_in_tree():
			continue
		var rect: Rect2 = control.get_global_rect()
		var minimum: Vector2 = control.get_combined_minimum_size()
		var record := {"path": String(ui.root.get_path_to(control)), "type": control.get_class(),
			"x": rect.position.x, "y": rect.position.y, "width": rect.size.x, "height": rect.size.y,
			"minimum_width": minimum.x, "minimum_height": minimum.y, "mouse_filter": control.mouse_filter,
			"clip_contents": control.clip_contents, "local_visible": control.visible, "tree_visible": control.is_visible_in_tree()}
		if control is Label or control is Button:
			record["text"] = control.text
		if control is Button:
			record["disabled"] = control.disabled
		controls.append(record)
	var focused := get_viewport().gui_get_focus_owner()
	return {"state": expedition.state, "locale": ui.locale, "frame": Engine.get_process_frames(),
		"viewport_width": get_viewport().get_visible_rect().size.x, "viewport_height": get_viewport().get_visible_rect().size.y,
		"focus": String(focused.get_path()) if focused else "", "controls": controls}

func _follow_camera(delta: float) -> void:
	var target := courier.position + Vector3(8.0, 8.8, 8.0)
	camera.position = camera.position.lerp(target, minf(delta * 7.0, 1.0))
	camera.look_at(courier.position + Vector3(0, 0.85, 0))

func _apply_exhibit_view(view: String) -> void:
	camera.fov = 48.0
	if view == "hero-close":
		camera.position = Vector3(3.8, 2.8, 17.4)
		camera.look_at(Vector3(0, 3.0, -6.0))
	else:
		camera.position = Vector3(24, 20, 32)
		camera.look_at(Vector3(0, 2.4, -1.0))

func qa_set_view(view: String) -> Dictionary:
	if not qa_enabled or view not in ["arrival-wide", "hero-close", "orbit"]:
		return {"error": "Known preview view and explicit --qa are required"}
	exhibit_view = view
	_apply_exhibit_view(view)
	return qa_snapshot()
