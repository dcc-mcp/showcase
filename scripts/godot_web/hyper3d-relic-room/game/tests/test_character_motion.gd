extends SceneTree
# Real imported skins/clips plus instrumented native motion; pixels/OS input separate.
const Main = preload("res://scripts/main.gd")
var game: Node3D

func _init() -> void:
	call_deferred("run")

func run() -> void:
	game = Node3D.new()
	game.set_script(Main)
	root.add_child(game)
	if not expect(game._characters_ready(), "Actual provider character derivatives, skins and required clips must be ready"):
		return
	var skeletons: Array = game.courier.model.find_children("*", "Skeleton3D", true, false)
	if not expect(skeletons.size() == 1 and skeletons[0].get_bone_count() > 8, "Courier must bind a real joint hierarchy"):
		return
	var skeleton: Skeleton3D = skeletons[0]
	game.save_path = "user://qa-character-motion.json"
	for suffix in ["", ".bak", ".tmp"]:
		if FileAccess.file_exists(game.save_path+suffix): DirAccess.remove_absolute(ProjectSettings.globalize_path(game.save_path+suffix))
	for mesh in game.courier.model.find_children("*", "MeshInstance3D", true, false):
		if not expect(mesh.mesh is ArrayMesh, "Visible courier meshes must be imported skinned geometry, with no primitive fallback"):
			return
	game._on_action("start")
	for frame in range(15): await physics_frame
	var idle_position: Vector3 = game.courier.position
	var idle_time: float = game.courier.animations.current_animation_position
	var idle_pose := bone_poses(skeleton)
	for frame in range(24): await physics_frame
	if not expect(game.courier.motion_clip == "Idle" and game.courier.animations.current_animation_position > idle_time and bone_poses(skeleton) != idle_pose, "Idle must advance actual joint poses"):
		return
	if not expect(game.courier.position.distance_to(idle_position) < 0.05, "In-place Idle must not move the controller"):
		return
	Input.action_press("move_forward")
	Input.action_press("move_right")
	var before_walk: Vector3 = game.courier.position
	for frame in range(30): await physics_frame
	if not expect(game.courier.motion_clip == "Walk" and game.courier.position.distance_to(before_walk) > 1.0 and bone_poses(skeleton) != idle_pose, "Walk must accompany actual native movement and joint motion"):
		return
	game.courier.invulnerable = 1.0
	game.courier.model.visible = false
	game._on_action("pause")
	if not expect(game.courier.model.visible, "Pause during a blink-off frame must restore visible character geometry"):
		return
	var frozen_time: float = game.courier.animations.current_animation_position
	var frozen_guardian: float = game.guardian_player.current_animation_position
	var frozen_pose := bone_poses(skeleton)
	var frozen_position: Vector3 = game.courier.position
	var frozen_clock: float = game.expedition.elapsed
	for frame in range(15): await physics_frame
	if not expect(is_equal_approx(frozen_time, game.courier.animations.current_animation_position) and is_equal_approx(frozen_guardian, game.guardian_player.current_animation_position) and frozen_pose == bone_poses(skeleton) and game.courier.position == frozen_position and game.expedition.elapsed == frozen_clock, "Pause must freeze both characters, controller and expedition clock"):
		return
	game._on_action("pause")
	Input.action_press("dash")
	for frame in range(3): await physics_frame
	Input.action_release("dash")
	if not expect(game.courier.motion_clip == "Dash" and game.courier.dash_remaining > 0.0, "Dash clip must synchronize with the actual timed dash"):
		return
	Input.action_release("move_forward")
	Input.action_release("move_right")
	game.courier.model.visible = false
	game._set_state("won")
	if not expect(game.courier.model.visible, "Victory during a blink-off frame must restore visible character geometry"):
		return
	game._on_action("start")
	if not expect(game.courier.position == game.SPAWN and game.courier.motion_clip == "Idle" and game.courier.dash_remaining == 0.0 and game.expedition.health == 40 and game.expedition.snapshot().inventory.is_empty(), "Retry must reset controller, dash, clip and expedition state"):
		return
	print("RELIC_CHARACTER_MOTION_PASS ", JSON.stringify({"courier": game.courier.animation_snapshot(), "guardian_clips": game.loaded_assets["guardian_character"].authored_clips, "bone_count": skeleton.get_bone_count(), "scope": "Native imported skins, changing joint poses and instrumented movement; no OS-input or rendered-deformation claim"}))
	for voice in game.audio_voices:
		voice.stop(); voice.stream = null
	OS.delay_msec(75)
	game.queue_free()
	await process_frame
	await process_frame
	quit(0)

func bone_poses(skeleton: Skeleton3D) -> Array:
	var result := []
	for index in range(skeleton.get_bone_count()): result.append(skeleton.get_bone_pose(index))
	return result

func expect(condition: bool, message: String) -> bool:
	if not condition:
		push_error(message)
		quit(1)
	return condition
