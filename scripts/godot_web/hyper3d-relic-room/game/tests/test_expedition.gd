extends SceneTree
const Expedition = preload("res://scripts/expedition.gd")
var definition: Dictionary
var checks := 0

func _init() -> void:
	call_deferred("run")

func run() -> void:
	definition = JSON.parse_string(FileAccess.get_file_as_string("res://data/arpg.json"))
	chest_and_save()
	combat_loop()
	death_and_retry()
	print("ARCHIVE_EXPEDITION_TESTS_PASS ", JSON.stringify({"checks": checks,
		"scope": "Pure deterministic model in Godot4.6.3; no Nodes, physical input, rendered contact or filesystem save acceptance"}))
	quit(0)

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		push_error(message)
		quit(1)
		assert(false, message)

func chest_and_save() -> void:
	var model = Expedition.new(definition)
	check(not model.open_chest("town_chest", 1.0).ok, "Title state must reject mutations")
	model.start()
	check(model.zone == "town" and model.health == 40, "Start in safe town")
	check(not model.equip("bronze_edge").ok and not model.equip("invented").ok, "Cannot equip unowned or unknown gear")
	check(not model.enemy_damage_player("scout_1", 0.0).ok, "Safe town rejects enemy damage")
	check(not model.open_chest("unknown", 0.0).ok, "Unknown chest rejected")
	for distance in [-1.0, INF, NAN, 2.01]:
		check(not model.open_chest("town_chest", distance).ok, "Invalid or distant chest interaction rejected")
	var opened: Dictionary = model.open_chest("town_chest", 1.0)
	check(opened.ok and opened.drop_id == "chest:town_chest", "Chest produces its deterministic one-time drop")
	check(not model.open_chest("town_chest", 1.0).ok and model.snapshot().drops.size() == 1, "Duplicate chest opening cannot mint loot")
	var before_pickup: Dictionary = JSON.parse_string(JSON.stringify(model.to_save()))
	var unpicked = Expedition.new(definition)
	check(unpicked.restore_save(before_pickup).ok, "Unpicked chest drop survives JSON save roundtrip")
	check(not unpicked.open_chest("town_chest", 1.0).ok and unpicked.snapshot().drops.size() == 1, "Reopen keeps chest open and exactly one unpicked drop")
	check(not model.pickup(opened.drop_id, 2.01).ok, "Out-of-range pickup cannot add inventory")
	check(model.pickup(opened.drop_id, 1.0).ok, "Pick up the opened chest drop")
	check(not model.pickup(opened.drop_id, 1.0).ok, "Duplicate pickup rejected")
	check(model.equip("bronze_edge").ok and model.attack_bonus == 5, "Owned blade equips with measured bonus")
	check(not model.equip("bronze_edge").ok and model.attack_bonus == 5, "Repeated equip cannot stack stats")
	model.toggle_pause()
	var saved: Dictionary = JSON.parse_string(JSON.stringify(model.to_save()))
	var restored = Expedition.new(definition)
	check(restored.restore_save(saved).ok, "Paused progress restores from real JSON data types")
	var snapshot: Dictionary = restored.snapshot()
	check(snapshot.state == "playing" and snapshot.zone == "town" and snapshot.elapsed == 0.0, "Transient state restores at safe town, unpaused")
	check(snapshot.equipment.weapon == "bronze_edge" and snapshot.inventory.bronze_edge == 1, "Reopen retains equipped gear")
	check(snapshot.drops[opened.drop_id].picked and not restored.pickup(opened.drop_id, 1.0).ok, "Picked loot cannot respawn on reopen")
	check(not restored.open_chest("town_chest", 1.0).ok, "Opened chest persists across reopen")
	snapshot.inventory.bronze_edge = 999
	check(restored.snapshot().inventory.bronze_edge == 1, "Returned snapshot cannot mutate domain state")
	var unequipped := saved.duplicate(true)
	unequipped.equipment.weapon = ""
	check(restored.restore_save(unequipped).ok and restored.snapshot().inventory.bronze_edge == 1, "Owned but unequipped inventory is valid and retained")
	check(restored.equip("bronze_edge").ok, "Restored unequipped item can be equipped")
	var corruptions: Array = []
	for field in ["version", "data_fingerprint", "opened_chests", "spawned_drop_ids", "picked_drop_ids", "inventory", "equipment", "unlocked_skills", "xp", "level", "quest_complete"]:
		var broken := saved.duplicate(true)
		broken[field] = null
		corruptions.append(broken)
	var forged := saved.duplicate(true)
	forged.equipment.focus = "arc_focus"
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.inventory.bronze_edge = 2
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.opened_chests.append("town_chest")
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.unlocked_skills.append("arc_bolt")
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.extra_field = true
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.version = 2
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.data_fingerprint = "0".repeat(64)
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.killed_enemies = ["unknown_enemy"]
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.picked_drop_ids = ["enemy:unknown_enemy"]
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.xp = 1.5
	corruptions.append(forged)
	forged = saved.duplicate(true)
	forged.quest_complete = true
	corruptions.append(forged)
	corruptions.append({})
	for broken in corruptions:
		var result: Dictionary = restored.restore_save(broken)
		check(not result.ok and result.reason == "invalid_save", "Corrupt/altered save must return visible-feedback ID without crashing")
		check(restored.state == "playing" and restored.zone == "town" and restored.snapshot().inventory.is_empty(), "Rejected save clean-starts instead of partially applying progress")
	var events: Array = restored.drain_events()
	check(events[-1].type == "save_rejected" and restored.drain_events().is_empty(), "Events are copied and drained once")

func combat_loop() -> void:
	var model = Expedition.new(definition)
	model.start()
	model.open_chest("town_chest", 1.0)
	model.pickup("chest:town_chest", 1.0)
	model.equip("bronze_edge")
	check(not model.turn_in(1.0).ok, "Cannot win before the expedition objective")
	check(model.enter_zone("wilderness").ok and not model.enter_zone("unknown").ok, "Only declared zones are available")
	check(not model.request_player_attack("arc_bolt", "scout_1", 1.0).ok, "Arc starts locked")
	var before: Dictionary = model.snapshot()
	for distance in [-1.0, INF, NAN, 2.21]:
		check(not model.request_player_attack("melee", "scout_1", distance).ok, "Invalid/out-of-range hits cannot deal damage")
	check(model.snapshot() == before, "Rejected hits spend no mana, cooldown or health")
	check(model.request_player_attack("melee", "scout_1", 2.2).damage == 15, "Blade affects actual contact damage")
	check(not model.request_player_attack("melee", "scout_1", 1.0).ok, "Same-frame duplicate contact denied by cooldown")
	model.tick(0.55)
	check(model.request_player_attack("melee", "scout_1", 1.0).killed, "Scout defeat produces guaranteed focus")
	check(not model.request_player_attack("melee", "scout_1", 1.0).ok and model.xp == 10, "Dead enemy cannot mint XP or drops twice")
	check(model.pickup("enemy:scout_1", 1.0).ok and model.equip("arc_focus").ok, "Focus pickup and equip unlock the skill")
	check("arc_bolt" in model.snapshot().unlocked_skills and model.snapshot().equipment.weapon == "bronze_edge", "Focus and weapon remain equipped together")
	check(model.max_mana == 30.0, "Focus increases mana capacity")
	check(not model.enemy_damage_player("sentinel_1", -1.0).ok and not model.enemy_damage_player("sentinel_1", INF).ok, "Enemy damage rejects invalid ranges")
	check(model.enemy_damage_player("sentinel_1", 2.0).ok and model.health == 32, "Confirmed enemy contact damages player")
	check(not model.enemy_damage_player("sentinel_1", 2.0).ok and model.health == 32, "Enemy contact cooldown prevents duplicate damage")
	model.toggle_pause()
	before = model.snapshot()
	model.tick(100.0)
	check(model.snapshot() == before, "Pause freezes elapsed time, mana and all cooldowns")
	check(not model.request_player_attack("arc_bolt", "sentinel_1", 1.0).ok and not model.enemy_damage_player("sentinel_1", 1.0).ok, "Pause rejects both combat directions")
	check(not model.enter_zone("town").ok and not model.open_chest("town_chest", 1.0).ok, "Pause rejects travel and loot mutations")
	model.toggle_pause()
	model.mana = 0.0
	before = model.snapshot()
	check(model.request_player_attack("arc_bolt", "sentinel_1", 8.5).reason == "no_mana" and model.snapshot() == before, "Mana rejection leaves state unchanged")
	model.tick(10.0)
	for index in range(3):
		var strike: Dictionary = model.request_player_attack("arc_bolt", "sentinel_1", 8.5)
		check(strike.ok and strike.damage == 24, "Unlocked Arc performs deterministic ranged contact damage")
		if index < 2: model.tick(0.9)
	check(model.level == 2 and model.xp == 25 and model.max_health == 50, "Defeats advance the declared level threshold")
	var repeated_item: Dictionary = model.pickup("enemy:sentinel_1", 1.0)
	check(repeated_item.ok and repeated_item.reason == "already_owned" and model.snapshot().inventory.bronze_edge == 1, "A legitimate repeated item clears its drop without adding another item or stats")
	check(model.snapshot().drops["enemy:sentinel_1"].picked and not model.pickup("enemy:sentinel_1", 1.0).ok, "Repeated item pickup cannot leave an undismissable orb or be picked twice")
	var loot_events: Array = model.drain_events()
	check(loot_events[-1].type == "item_already_owned" and model.attack_bonus == 7, "Duplicate item has an explicit feedback event without stacking bonuses")
	check(model.snapshot().goal_ready and not model.turn_in(1.0).ok, "Goal requires returning to town")
	var persisted: Dictionary = JSON.parse_string(JSON.stringify(model.to_save()))
	var reopened = Expedition.new(definition)
	check(reopened.restore_save(persisted).ok, "Killed-enemy, picked-drop and equipment progress restore together")
	check(reopened.zone == "town" and reopened.health == 50 and reopened.mana == 30.0, "Restore clears transient combat and refills at safe town")
	check(not reopened.snapshot().enemies.scout_1.alive and not reopened.snapshot().enemies.sentinel_1.alive, "Killed enemies remain defeated after reopen")
	check(reopened.snapshot().drops.size() == 3 and reopened.snapshot().equipment.focus == "arc_focus", "No duplicate loot or lost gear after progressed reopen")
	check(reopened.snapshot().drops["chest:town_chest"].picked and reopened.snapshot().drops["enemy:sentinel_1"].picked and reopened.snapshot().inventory.bronze_edge == 1, "Restore retains both picked sources of the same unique item")
	check(not reopened.turn_in(2.31).ok and reopened.turn_in(2.3).ok and reopened.state == "won", "Only in-range town turn-in completes the loop")
	var completed: Dictionary = reopened.to_save()
	check(model.restore_save(completed).ok and model.state == "won" and model.quest_complete, "Completed quest persists without replaying rewards")
	before = model.snapshot()
	model.tick(100.0)
	check(model.snapshot() == before and not model.turn_in(0.0).ok, "Completed state rejects duplicate turn-in and ticking")
	model.start()
	check(model.state == "playing" and model.level == 1 and model.health == 40 and model.snapshot().inventory.is_empty() and model.snapshot().drops.is_empty(), "Explicit retry creates a fresh expedition")

func death_and_retry() -> void:
	var model = Expedition.new(definition)
	model.start()
	model.enter_zone("wilderness")
	for index in range(5):
		check(model.enemy_damage_player("sentinel_1", 1.0).ok, "Valid repeated attack after recovery")
		model.tick(1.65)
	check(model.state == "lost" and model.health == 0, "Health exhaustion is a terminal loss")
	check(not model.pickup("invented", 0.0).ok and not model.enter_zone("town").ok, "Dead player cannot change expedition progress")
	model.start()
	check(model.state == "playing" and model.health == 40 and model.zone == "town", "Retry clears the loss and returns safely")
