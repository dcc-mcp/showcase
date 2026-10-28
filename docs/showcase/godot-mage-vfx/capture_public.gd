extends SceneTree
## Reproducible native Movie Maker observer; no source effects are modified.

const FPS := 30
const PREWARM := 30
var study: Node3D
var case_name := "single"
var duration := 4.0
var output := ""
var frame := 0
var seeded_particles := 0
var frames: Array[Dictionary] = []
var previous := Vector3i.ZERO
var caption: Label
var done := false
var fixed_camera: Camera3D

class CaptureTick extends Node:
	var tick: Callable
	func _process(delta: float) -> void:
		tick.call(delta)

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--case="): case_name = arg.trim_prefix("--case=")
		if arg.begins_with("--duration="): duration = float(arg.trim_prefix("--duration="))
		if arg.begins_with("--output="): output = arg.trim_prefix("--output=")
	assert(case_name in ["single", "combo", "detail", "gallery"])
	assert(not output.is_empty())
	call_deferred("_setup")

func _setup() -> void:
	seed(12345)
	node_added.connect(_seed_particles)
	var scene_path := "res://mage_spells/combat_vfx_gallery.tscn" if case_name == "gallery" else "res://mage_spells/mage_motion_study.tscn"
	study = load(scene_path).instantiate() as Node3D
	assert(study != null)
	if case_name == "gallery":
		study.auto_play = false
	else:
		assert(study.mage_scene != null, "This capture requires the authorized existing imported mage")
		study.auto_cast = false
		study.camera_feedback_enabled = false
		if case_name in ["single", "detail"]: study.sound_gain_db = -8.0
	root.add_child(study)
	if case_name != "gallery":
		assert(study.get_state().mage_kind == "imported_skeletal")
		_validate_socket()
	for node in study.get_children():
		if node is CanvasLayer: node.hide()
	# Replace only the existing demonstration HUD with native editorial captions.
	var layer := CanvasLayer.new()
	root.add_child(layer)
	var heading := Label.new()
	heading.text = "ARCANE / COMBAT CAST" if case_name != "gallery" else "SIX REUSABLE EFFECTS"
	heading.position = Vector2(42, 28)
	heading.add_theme_font_size_override("font_size", 25)
	layer.add_child(heading)
	var subheading := Label.new()
	subheading.text = {"single":"01 / SIGIL + GATHER + RELEASE", "combo":"02 / FLIGHT + CONTACT", "detail":"03 / SIGIL LAYERS + DECAY", "gallery":"03 / FIRE  /  AURA  /  ATTACK  /  IMPACT"}[case_name]
	subheading.position = Vector2(44, 65)
	subheading.add_theme_font_size_override("font_size", 15)
	subheading.modulate = Color("9bb6cf")
	layer.add_child(subheading)
	caption = Label.new()
	caption.position = Vector2(44, root.size.y - 42)
	caption.add_theme_font_size_override("font_size", 16)
	caption.modulate = Color("d0deed")
	layer.add_child(caption)
	var credit := Label.new()
	credit.text = "Mage mesh / PBR: Hyper3D Rodin Gen-2.5   |   Animation: Kay Lousberg (CC0), retarget and Godot VFX: DCC-MCP contributors"
	credit.position = Vector2(44, root.size.y - 19)
	credit.add_theme_font_size_override("font_size", 10)
	credit.modulate = Color("8d9cae")
	layer.add_child(credit)
	fixed_camera = root.get_camera_3d()
	assert(fixed_camera != null)
	var observer := CaptureTick.new()
	observer.process_priority = 1000
	observer.tick = _record
	root.add_child(observer)

func _seed_particles(node: Node) -> void:
	if not node is GPUParticles3D: return
	var names: Array[String] = []
	for property in node.get_property_list(): names.append(property.name)
	if "use_fixed_seed" in names and "seed" in names:
		node.set("use_fixed_seed", true)
		node.set("seed", 12345)
		seeded_particles += 1

func _set_camera() -> void:
	var sweep := smoothstep(0.0, duration, maxf(0.0, float(frame - PREWARM) / FPS))
	if case_name == "gallery":
		fixed_camera.position = Vector3(0.0,13.8,13.45)
		fixed_camera.fov = 43.0
		fixed_camera.look_at(Vector3(0.0,0.0,-2.3))
		return
	# Capture-only framing for the authorized imported mage and impact.
	if case_name == "single":
		fixed_camera.position = Vector3(-0.7 - sweep * 0.12, 3.15, 3.25 - sweep * 0.12)
		fixed_camera.fov = 48.0
		fixed_camera.look_at(Vector3(-2.7, 1.0, 0.0))
	elif case_name == "detail":
		fixed_camera.position = Vector3(-1.15 - sweep * 0.12, 3.75, 3.25 - sweep * 0.12)
		fixed_camera.fov = 52.0
		fixed_camera.look_at(Vector3(-2.5, 1.05, 0.0))
	else:
		fixed_camera.position = Vector3(-0.3 + sweep * 0.5, 3.2, 8.0 - sweep * 0.5)
		fixed_camera.fov = 49.0
		fixed_camera.look_at(Vector3(0.0, 1.1, -0.4))

func _record(_delta: float) -> void:
	_set_camera()
	if done:
		# Let the final requested frame reach Movie Maker before exiting.
		quit()
		return
	frame += 1
	if frame == PREWARM:
		if case_name == "gallery": study.play_cycle()
	if frame == PREWARM + 15 and case_name == "single": study.cast_spell()
	if frame == PREWARM + 12 and case_name in ["combo", "detail"]: assert(study.cast_combo("arcane_surge"))
	if frame == PREWARM + 156 and case_name == "gallery": study.get_node("Timeline").stop()
	if frame < PREWARM: return
	var elapsed := float(frame - PREWARM) / FPS
	var row := {"observer_frame":frame - PREWARM, "time_seconds":elapsed,
		"camera_position":[fixed_camera.position.x,fixed_camera.position.y,fixed_camera.position.z], "camera_fov":fixed_camera.fov}
	if case_name == "gallery":
		caption.text = "Animated mesh + particle fire   /   Attached + world auras   /   Sweep + spell impact"
		row["events"] = study.event_count
		row["particle_fire_emitting"] = study.get_node("ParticleFire/Flames").emitting
		row["mesh_fire_visible"] = study.get_node("MeshFire").visible
	else:
		var state: Dictionary = study.get_state()
		assert(study.mage_scene != null and state.mage_kind == "imported_skeletal")
		_validate_socket()
		var count := Vector3i(state.cast_count, state.release_count, state.impact_count)
		row["state"] = state
		var origin: Node3D = study.get("_cast_hand")
		row["cast_origin"] = [origin.global_position.x, origin.global_position.y, origin.global_position.z]
		var rig := origin.get_parent().get_parent() as Skeleton3D
		row["stance"] = {}
		for bone in ["Hips", "LeftFoot", "RightFoot"]:
			var point := rig.global_transform * rig.get_bone_global_pose(rig.find_bone(bone)).origin
			row["stance"][bone] = [point.x, point.y, point.z]
		row["mage_origin_screen"] = _screen(study.get_node("Mage").global_position)
		row["cast_origin_screen"] = _screen(origin.global_position)
		caption.text = "Gather  /  Contract  /  Release  /  Contact  /  Settle"
		if count != previous:
			row["event_delta"] = [count.x-previous.x,count.y-previous.y,count.z-previous.z]
			print("PUBLIC_CAPTURE_EVENT " + JSON.stringify(row))
		previous = count
	frames.append(row)
	if frame == PREWARM + int(duration*FPS) - 1:
		var state: Dictionary = study.get_state() if case_name != "gallery" else {"events":study.event_count}
		if case_name != "gallery":
			var expected := 1 if case_name == "single" else 2
			assert(state.release_count == expected and state.impact_count == expected)
			assert(state.active_projectiles.is_empty())
		else:
			assert(study.event_count >= 6)
		var report := {"case":case_name,"capture_fps":FPS,"prewarm_frames":PREWARM,"duration_seconds":duration,
			"scene": "res://mage_spells/combat_vfx_gallery.tscn" if case_name == "gallery" else "res://mage_spells/mage_motion_study.tscn",
			"public_asset_assertion":"authorized existing imported mage; imported_skeletal, RightCastSocket bone and BoneAttachment CastOrigin asserted every mage frame",
			"asset_credit":"Hyper3D / Rodin Gen-2.5 generated mesh and PBR; 20-joint fitted rig, retarget and Godot VFX by DCC-MCP contributors; spell animation by Kay Lousberg (CC0)",
			"rights_scope":"User authorized public model use; provider account license independently unverified; no new generation or legal certification",
			"fixed_seed":12345,"seeded_particle_nodes":seeded_particles,
			"camera_binding":"after-controller observer process_priority 1000 before render sync",
			"editorial_changes":"native captions and three native camera moves; three independent natural-speed performances; no retiming, AI frames or post-added audio; gallery remains in the editable project",
			"timing_scope":"observer frames; compare encoded pixel transitions separately",
			"final_state":state,"frames":frames}
		var file := FileAccess.open(output,FileAccess.WRITE)
		assert(file != null)
		file.store_string(JSON.stringify(report,"\t"))
		print("PUBLIC_CAPTURE_OK " + case_name)
		done = true

func _screen(point: Vector3) -> Array:
	var screen := fixed_camera.unproject_position(point)
	return [screen.x,screen.y]

func _validate_socket() -> void:
	var origin: Node3D = study.get("_cast_hand")
	assert(origin != null and origin.name == "CastOrigin")
	var attachment := origin.get_parent() as BoneAttachment3D
	assert(attachment != null and attachment.bone_name == "RightCastSocket")
	var skeleton := attachment.get_parent() as Skeleton3D
	assert(skeleton != null and skeleton.find_bone("RightCastSocket") >= 0)
	assert(skeleton.get_bone_count() == 20)
