extends SceneTree
const Main = preload("res://scripts/main.gd")
class Probe extends Main:
	var sounds: Array[String] = []
	func _sound(name: String) -> void: sounds.append(name)
var checks := 0
func _init() -> void: call_deferred("run")
func check(value: bool, message: String) -> bool:
	checks += 1
	if not value:
		push_error(message)
		quit(1)
	return value
func run() -> void:
	var game := Probe.new()
	root.add_child(game)
	game.save_path = "user://qa-feedback-revision.json"
	game._on_action("start")
	for i in range(4): await physics_frame
	game.set_physics_process(false)
	game.courier.set_physics_process(false)
	game.courier.position = Vector3(-4, -0.05, -24.2)
	game.expedition.enter_zone("wilderness")
	game.sounds.clear()
	game._request_attack("melee")
	if not check(game.sounds.is_empty(), "Attack audio must wait for its animation event, not input press"): return
	if not check(game.courier.animations.has_animation("Run"), "Independent authored Run clip must exist"): return
	if not check(game.weapon_visual != null and game.weapon_socket.bone_name == "Hand.R", "Weapon must be a separate imported model on the right-hand bone"): return
	var grip_before: Vector3 = game.weapon_visual.global_position
	game.courier._advance_animation(0.17)
	game.weapon_socket.get_parent().force_update_all_bone_transforms()
	await process_frame
	await process_frame
	if not check(game.weapon_visual.global_position.distance_to(grip_before) > 0.02 and game.weapon_visual.global_position.distance_to(game.weapon_socket.global_position) < 0.08, "Independent weapon follows the animated wrist within its calibrated grip offset"): return
	game._update_player_action(0.17)
	if not check(not game.sounds.has("chop"), "No impact before the .18 animation contact"): return
	game.courier._advance_animation(0.02)
	game._update_player_action(0.02)
	if not check(game.sounds.count("knifeSlice") == 1 and game.sounds.count("chop") == 1, "One swing and confirmed impact at animation contact"): return
	game._update_player_action(0.0)
	if not check(game.sounds.count("chop") == 1, "No duplicate impact while the animation is held"): return
	var stats: Dictionary = game._ui_stats()
	if not check(stats.skill_context.arc_bolt.mana_cost == 6 and stats.skill_context.melee.range == 2.2, "HUD must receive authoritative skill costs and range"): return
	game.courier._advance_animation(0.5)
	game._update_player_action(0.5)
	if not check(game.pending_action.is_empty(), "Completed nonloop animation must release the next attack"): return
	game.courier.position = game.SPAWN
	game.expedition.enter_zone("town")
	game.sounds.clear()
	game._request_attack("arc_bolt")
	if not check(not game.pending_action.is_empty() and game.cast_ring.visible, "Fresh town Q has an explicit harmless skill rehearsal"): return
	game.courier._advance_animation(0.33)
	game._update_player_action(0.33)
	if not check(game.vfx.visible and not game.cast_ring.visible and game.expedition.mana == 20, "Training transitions windup to beam without damage or mana cost"): return
	game.courier._advance_animation(0.5)
	game._update_player_action(0.5)
	game.courier.running = false
	game.courier._update_animation(1.45)
	var walk_clip: Animation = game.courier.animations.get_animation("Walk")
	game.courier.running = true
	game.courier._update_animation(2.8)
	var run_clip: Animation = game.courier.animations.get_animation("Run")
	if not check(game.courier.motion_clip == "Run" and run_clip != walk_clip and run_clip.length < walk_clip.length, "Run uses an independent retimed animation resource"): return
	var distinct := false
	for track in range(run_clip.get_track_count()):
		if run_clip.track_get_type(track) == Animation.TYPE_ROTATION_3D:
			distinct = distinct or run_clip.track_get_key_value(track, 0) != walk_clip.track_get_key_value(track, 0)
	if not check(distinct, "Run has authored pose differences, not only a faster Walk playback"): return
	game._on_action("bag")
	if not check(game.bag_open and not game.ui.skill_bar.visible, "Bag modal cannot leave live skill controls behind it"): return
	game.expedition.open_chest("town_chest", 0.0)
	game.expedition.pickup("chest:town_chest", 0.0)
	game._on_action("equip:bronze_edge")
	if not check(game.weapon_visual.visible and game.weapon_visual.get_meta("equipped_item") == "bronze_edge", "Equipment authority and visible independent weapon agree"): return
	game._on_action("bag")
	game._on_action("menu")
	var saved_bytes := FileAccess.get_file_as_bytes(game.save_path)
	game._on_action("new_expedition")
	if not check(game.expedition.state == "playing" and game.expedition.snapshot().inventory.is_empty(), "Confirmed new expedition resets persistent gameplay"): return
	var preserved := false
	var directory := DirAccess.open(ProjectSettings.globalize_path("user://"))
	for file in directory.get_files():
		if file.begins_with("qa-feedback-revision.json.before-new-"):
			preserved = preserved or FileAccess.get_file_as_bytes("user://" + file) == saved_bytes
	if not check(preserved, "New expedition preserves exact prior save bytes in a separate archive"): return
	game.sounds.clear()
	game.courier.touch_axis = Vector2(1, -1)
	for frame in range(120):
		game.courier._physics_process(1.0 / 60.0)
		await physics_frame
	var walk_contacts := game.sounds.count("footstep00")
	game.sounds.clear()
	Input.action_press("run")
	for frame in range(120):
		game.courier._physics_process(1.0 / 60.0)
		await physics_frame
	Input.action_release("run")
	var run_contacts := game.sounds.count("footstep00")
	if not check(walk_contacts >= 3 and walk_contacts <= 5 and run_contacts >= 6 and run_contacts <= 9, "Real grounded Walk and Run emit separate clip-matched footfall cadences"): return
	game._on_action("bag")
	var stopped := game.sounds.size()
	for frame in range(30): game.courier._physics_process(1.0 / 60.0)
	if not check(game.sounds.size() == stopped, "Paused/inventory animation cannot emit backlog footsteps"): return
	print("RELIC_FOOT_CONTACTS ", JSON.stringify({"walk_2s":walk_contacts, "run_2s":run_contacts}))
	var previous_library: AnimationLibrary = game.courier.animations.get_animation_library("")
	game.courier.bind_animation_player(game.courier.animations)
	if not check(game.courier.animations.has_animation("Run") and game.courier.animations.get_animation_library("") != previous_library, "Rebinding uses an isolated animation library without duplicate Run registration"): return
	game.queue_free()
	await process_frame
	await process_frame
	print("RELIC_FEEDBACK_REVISION_PASS ", checks, " animation/audio/socket/state checks; rendered quality and real input NOT_RUN")
	quit(0)
