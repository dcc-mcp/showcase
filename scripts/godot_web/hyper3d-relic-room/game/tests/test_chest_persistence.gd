extends SceneTree
# Two separate native processes use the same isolated QA save for reopen acceptance.
const Main = preload("res://scripts/main.gd")
var game: Node3D
var checks := 0
func _init() -> void: call_deferred("run")
func check(value: bool, message: String) -> void:
	checks += 1
	assert(value, message)
func frames(count: int) -> void:
	for index in range(count): await physics_frame
func write_text(path: String, content: String) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(content)
	file.close()
func run() -> void:
	game = Node3D.new()
	game.name = "RelicCourier"
	game.set_script(Main)
	root.add_child(game)
	game.qa_enabled = true
	game.save_path = "user://qa-chest-reopen.json"
	var reading := "--read" in OS.get_cmdline_user_args()
	if reading:
		game._on_action("start")
		check(game.expedition.state == "playing", "Fresh native process resumes safely in town")
		check(game._chest_opened(), "Fresh native process retains opened chest")
		check(game.expedition.snapshot().equipment.weapon == "bronze_edge", "Fresh native process retains equipped blade")
		check(is_equal_approx(game.chest_lid.rotation.x, -deg_to_rad(100.0)), "Reopened native scene displays actual lid already open")
		game.courier.position = game.CHEST + Vector3(0,-.05,1.7)
		game._interact()
		check(game.expedition.snapshot().drops.size() == 1 and game.expedition.snapshot().inventory.bronze_edge == 1, "Fresh reopen repeated E cannot duplicate loot or gear")
	else:
		for suffix in ["", ".bak", ".tmp"]:
			if FileAccess.file_exists(game.save_path+suffix): DirAccess.remove_absolute(ProjectSettings.globalize_path(game.save_path+suffix))
		game.qa_stage("playing")
		check(game._characters_ready() and game.chest_lid != null, "All actual assets and real Lid are available")
		var base: Node3D = game.chest_visual.find_child("Base",true,false)
		check(base != null, "Provider-derived stationary Base exists")
		var fixed: Transform3D = base.global_transform
		game.courier.position = game.CHEST + Vector3(0,-.05,1.7)
		game._interact()
		await frames(15)
		check(game.chest_progress > 0.0 and game.chest_lid.rotation.x < 0.0, "Only real Lid begins lifting")
		game.courier.position = game.CHEST + Vector3(0,-.05,2.2)
		await frames(2)
		check(not game.chest_opening and game.chest_progress == 0.0 and not game._chest_opened(), "Leaving into2.0–2.4m band cancels and produces no loot")
		check(is_zero_approx(game.chest_lid.rotation.x), "Cancelled lid returns fully closed")
		game.courier.position = game.CHEST + Vector3(0,-.05,1.7)
		game._interact()
		await frames(10)
		game._on_action("pause")
		var progress: float = game.chest_progress
		var rotation: float = game.chest_lid.rotation.x
		await frames(20)
		check(game.chest_progress == progress and game.chest_lid.rotation.x == rotation, "Pause freezes actual lid/progress")
		game._on_action("pause")
		await frames(45)
		check(game._chest_opened() and game.expedition.snapshot().drops.size() == 1, "Finishing real lid creates exactly one drop")
		check(base.global_transform.is_equal_approx(fixed), "Chest Base remains stationary throughout real lid action")
		check(is_equal_approx(game.chest_lid.rotation.x,-deg_to_rad(100.0)), "Actual lid reaches contract open angle")
		game._on_action("pause")
		game._on_action("menu")
		check(game.expedition.state == "title", "Successful Save & Title preserves an unpicked chest drop")
		game._on_action("start")
		game.courier.position = game.CHEST + Vector3(0,-.05,1.7)
		check(game._near_drop() == "chest:town_chest", "Title Continue restores the interaction anchor for cached unpicked loot")
		game._interact()
		check(game.expedition.snapshot().inventory.has("bronze_edge"), "E recovers real chest drop")
		game._on_action("bag")
		game._on_action("equip:bronze_edge")
		game._on_action("bag")
		check(game.expedition.snapshot().equipment.weapon == "bronze_edge", "Bag equips recovered chest gear")
		game._interact()
		check(game.expedition.snapshot().drops.size() == 1 and game.expedition.snapshot().inventory.bronze_edge == 1, "Repeated E is one-shot with clear opened feedback")
		check(game._save_progress(), "Verified atomic save succeeds")
		var content := FileAccess.get_file_as_string(game.save_path)
		write_text(game.save_path+".bak",content)
		DirAccess.remove_absolute(ProjectSettings.globalize_path(game.save_path))
		game.expedition.start(); game._load_progress()
		check(game._chest_opened() and game.expedition.snapshot().equipment.weapon == "bronze_edge", "Interrupted rename restores verified backup")
		check(game._save_progress() and FileAccess.file_exists(game.save_path+".bak"), "Recovery save preserves existing valid backup")
		write_text(game.save_path,"{")
		game.expedition.start(); game._load_progress()
		check(game._chest_opened(), "Corrupt primary falls back to valid backup")
		check(FileAccess.get_file_as_string(game.save_path) == "{", "Loader retains corrupt bytes for review")
		check(game._save_progress(), "Next save preserves rejected primary and promotes verified data")
		write_text(game.save_path,"x".repeat(70000))
		game.expedition.start(); game._load_progress()
		check(game._chest_opened(), "Oversized primary is rejected before parse and backup restores")
		check(game._save_progress(), "Final primary is valid for fresh-process read")
		# A real temporary-path directory forces FileAccess.open(WRITE) to fail.
		# Keep a valid older primary to catch accidental Title -> Continue rollback.
		var previous_path: String = game.save_path
		game.save_path = "user://qa-menu-write-failure-%d-%d.json" % [OS.get_process_id(), Time.get_ticks_usec()]
		var older = Main.Expedition.new(game.config)
		older.start()
		write_text(game.save_path, JSON.stringify(older.to_save()))
		var old_bytes := FileAccess.get_file_as_string(game.save_path)
		var temporary := ProjectSettings.globalize_path(game.save_path + ".tmp")
		check(DirAccess.make_dir_absolute(temporary) == OK, "Create only the unique QA temporary-path obstruction")
		var live: Dictionary = game.expedition.to_save()
		game._on_action("pause")
		game._on_action("menu")
		await frames(2)
		check(game.expedition.state == "paused" and game.ui.state == "paused", "Failed Save & Title stays in the current paused expedition")
		check(game.expedition.to_save() == live and game.expedition.snapshot().equipment.weapon == "bronze_edge", "Failed title command retains fresh inventory, equipment and chest progress")
		var description: Label = game.ui.modal_box.get_node("ScreenDescription")
		check(description.is_visible_in_tree() and description.text == game.ui.t("save_failed"), "Failed title command shows localized failure feedback inside the visible modal")
		check(FileAccess.get_file_as_string(game.save_path) == old_bytes, "Failed temporary write leaves the older primary intact")
		game._on_action("language")
		game._on_action("menu")
		check(game.expedition.state == "paused" and game.expedition.to_save() == live, "Repeated failed title command cannot discard unsaved progress")
		check(game.ui.locale == "zh" and game.ui.modal_box.get_node("ScreenDescription").text == game.ui.t("save_failed"), "Chinese paused menu also displays the save failure")
		game._on_action("pause")
		check(game.expedition.state == "playing" and game.expedition.to_save() == live, "Normal Continue after failure resumes the fresh in-memory expedition")
		game._on_action("bag")
		check(game.ui.bag_visible and game.expedition.snapshot().equipment.weapon == "bronze_edge", "Equipment remains inspectable after failure and Continue")
		game._on_action("bag")
		# Stage valid completed progress with the existing deterministic rules; this
		# checks caller persistence, not combat input or a rendered winning course.
		game.expedition.enter_zone("wilderness")
		for id in ["scout_1", "sentinel_1"]:
			while game.expedition.snapshot().enemies[id].alive:
				check(game.expedition.request_player_attack("melee", id, 1.0).ok, "Stage legitimate enemy progress for the won caller regression")
				game.expedition.tick(1.0)
			check(game.expedition.pickup("enemy:" + id, 0.0).ok, "Stage legitimate one-time pickups without duplicate item stacks")
		check(game.expedition.equip("arc_focus").ok, "Stage both equipment slots for completed progress")
		game.expedition.enter_zone("town")
		check(game.expedition.turn_in(0.0).ok, "Stage a valid completed quest before the actual write failure")
		game._set_state("won")
		var won_live: Dictionary = game.expedition.to_save()
		game._on_action("menu")
		check(game.expedition.state == "won" and game.ui.modal_box.get_node("ScreenDescription").text == game.ui.t("save_failed"), "Failed won Save & Title retains the win and visible failure feedback")
		game._on_action("start")
		check(game.expedition.state == "playing" and game.expedition.to_save() == won_live, "Won Explore restores current in-memory progress instead of the older disk save")
		check(game.expedition.snapshot().inventory.bronze_edge == 1 and game.expedition.snapshot().drops.size() == 3 and not game.drop_visuals["chest:town_chest"].visible, "Won Explore retains consumed chest/rewards without duplicate loot or stacked gear")
		# Restore the earlier valid incomplete progress and stage a legitimate loss.
		check(game.expedition.restore_save(live).ok, "Restore the owned incomplete QA progress for retry coverage")
		game._reset_world()
		game._set_state("playing")
		game.expedition.enter_zone("wilderness")
		for index in range(5):
			check(game.expedition.enemy_damage_player("sentinel_1", 1.0).ok, "Stage a legitimate loss with current gear retained")
			game.expedition.tick(1.65)
		check(game.expedition.state == "lost", "Damage exhaustion reaches the actual lost state")
		game._set_state("lost")
		var lost_live: Dictionary = game.expedition.to_save()
		game._on_action("menu")
		check(game.expedition.state == "lost" and game.expedition.to_save() == lost_live, "Failed lost Save & Title retains the latest incomplete progress")
		game._on_action("start")
		check(game.expedition.state == "playing" and game.expedition.to_save() == lost_live and game.expedition.health == game.expedition.max_health, "Lost Retry preserves in-memory loot/equipment and resets combat safely")
		check(FileAccess.get_file_as_string(game.save_path) == old_bytes, "All failed paused/won/lost transitions leave the older primary unchanged")
		check(DirAccess.remove_absolute(temporary) == OK, "Remove only the empty QA obstruction directory")
		game._on_action("pause")
		game._on_action("menu")
		check(game.expedition.state == "title", "Successful Save & Title still enters the normal title screen")
		game._on_action("start")
		check(game.expedition.state == "playing" and game.expedition.to_save() == live, "Normal title Continue reloads the newly saved gear after storage recovers")
		for suffix in ["", ".bak", ".tmp"]:
			if FileAccess.file_exists(game.save_path + suffix): DirAccess.remove_absolute(ProjectSettings.globalize_path(game.save_path + suffix))
		game.save_path = previous_path
	print("RELIC_CHEST_PERSISTENCE_PASS ",JSON.stringify({"mode":"fresh_process_read" if reading else "write_and_fault_recovery","checks":checks,"scope":"actual Godot engine/file IO with staged approach; no OS input claim","caller_failure_scopes":[] if reading else ["paused","won_explore","lost_retry","en","zh"],"lid_path":String(game.chest_lid.get_path())}))
	for voice in game.audio_voices:
		voice.stop(); voice.stream = null
	# Allow the native audio mixer to release stopped Ogg playback before fast fixed-fps shutdown.
	OS.delay_msec(75)
	game.queue_free()
	await process_frame
	await process_frame
	quit(0)
