extends SceneTree
# Actual engine scene/physics/action-timing regression. Staged positions are explicit;
# this is not an OS-input course or a claim of visual acceptance.
const Main = preload("res://scripts/main.gd")
var game: Node3D
var checks := 0
var action_markers := []

func _init() -> void:
	call_deferred("run")

func check(value: bool, message: String) -> void:
	checks += 1
	if not value:
		push_error("EXPEDITION_NATIVE_FAILURE: " + message)
		quit(1)
		assert(value, message)

func frames(count: int) -> void:
	for index in range(count): await physics_frame

func strike(skill: String, frames_to_wait := 48) -> void:
	game._request_attack(skill)
	await frames(frames_to_wait)

func run() -> void:
	game = Node3D.new()
	game.name = "RelicCourier"
	game.set_script(Main)
	root.add_child(game)
	game.qa_enabled = true
	game.save_path = "user://qa-expedition-native.json"
	for suffix in ["", ".tmp", ".bak"]:
		if FileAccess.file_exists(game.save_path + suffix):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(game.save_path + suffix))
	check(game.courier.animations.has_animation("Attack") and game.courier.animations.has_animation("Cast"), "Actual generated courier action clips imported")
	check(game.guardian_player.has_animation("Attack"), "Actual guardian Attack clip imported")
	for clip in ["Attack", "Cast"]:
		check(game.courier.animations.get_animation(clip).loop_mode == Animation.LOOP_NONE, "Action is nonloop: " + clip)
	check(game.focus_socket != null and game.focus_visual.get_parent() == game.focus_socket, "Equipped focus is bound to actual hand skeleton")
	game.qa_stage("playing")
	game.courier.position = Vector3(-4, -0.05, -24.4)
	await frames(2)
	game._request_attack("melee")
	check(not game.pending_action.is_empty(), "One action windup scheduled")
	game._request_attack("melee")
	await frames(6)
	check(game.expedition.snapshot().enemies.scout_1.health == 30, "No damage before actual .18 contact")
	var elapsed: float = game.pending_action.elapsed
	var health: int = game.expedition.health
	game._on_action("pause")
	var clip_time: float = game.courier.animations.current_animation_position
	await frames(25)
	check(is_equal_approx(game.pending_action.elapsed, elapsed), "Pause freezes pending contact timer")
	check(is_equal_approx(game.courier.animations.current_animation_position, clip_time), "Pause freezes real action clip")
	check(game.expedition.health == health, "Pause freezes enemy damage")
	game._on_action("pause")
	await frames(10)
	check(game.expedition.snapshot().enemies.scout_1.health == 20, "Exactly one melee hit after contact")
	action_markers.append({"clip":"Attack", "contact_seconds":0.18, "health_after":20})
	await frames(40)
	await strike("melee")
	await strike("melee")
	check(not game.expedition.snapshot().enemies.scout_1.alive, "Three contact-confirmed strikes defeat scout")
	check(game.enemies.scout_1.dead, "World removes defeated actor collider/visual")
	check(game.drop_visuals.has("enemy:scout_1"), "Actual defeat creates one visible drop")
	game._interact()
	check(game.expedition.snapshot().inventory.has("arc_focus"), "Nearby E recovers focus")
	game._on_action("bag")
	var before_bag: float = game.expedition.elapsed
	await frames(20)
	check(game.bag_open and game.expedition.elapsed == before_bag, "Inventory suspends world while core accepts equip")
	game._on_action("equip:arc_focus")
	check(game.expedition.snapshot().equipment.focus == "arc_focus" and game.focus_visual.visible, "Equip unlocks skill and reveals provider crystal on hand")
	game._on_action("bag")
	game.courier.position = Vector3(4, -0.05, -29.0)
	await frames(2)
	game._request_attack("arc_bolt")
	await frames(15)
	check(game.expedition.snapshot().enemies.sentinel_1.health == 54, "No Arc damage before .32 release")
	await frames(7)
	check(game.expedition.snapshot().enemies.sentinel_1.health == 30, "Arc applies 24 damage at release")
	check(game.vfx_remaining > 0.0, "Release produces actual native beam")
	action_markers.append({"clip":"Cast", "release_seconds":0.32, "health_after":30})
	await frames(60)
	await strike("arc_bolt", 60)
	game.courier.position = game.enemies.sentinel_1.position + Vector3(0, 0, 1.5)
	await frames(2)
	await strike("melee")
	check(not game.expedition.snapshot().enemies.sentinel_1.alive, "Mixed Arc/melee defeats sentinel")
	game._interact()
	game._on_action("bag")
	game._on_action("equip:bronze_edge")
	game._on_action("bag")
	check(game.expedition.snapshot().goal_ready, "Two enemies and equipped items satisfy return objective")
	game.courier.position = Vector3(0, -0.05, 10)
	await frames(2)
	game._interact()
	check(game.expedition.state == "won", "Return interaction completes the same expedition")
	check(game._save_progress(), "Atomic user-path save succeeds")
	var saved: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(game.save_path))
	game.expedition.start()
	game._load_progress()
	check(game.expedition.state == "won" and game.expedition.snapshot().inventory.has("arc_focus"), "Native file JSON roundtrip retains completed quest and gear")
	print("RELIC_EXPEDITION_NATIVE_PASS ", JSON.stringify({"checks":checks, "scope":"actual Godot engine staged scene integration; no OS input/pixel claim", "markers":action_markers}))
	for voice in game.audio_voices:
		voice.stop()
		voice.stream = null
	# Allow the native audio mixer to release stopped Ogg playback before fast fixed-fps shutdown.
	OS.delay_msec(75)
	game.queue_free()
	await process_frame
	await process_frame
	quit(0)
