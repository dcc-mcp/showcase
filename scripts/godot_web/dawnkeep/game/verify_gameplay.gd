# Copyright DCC-MCP. Headless simulation checks, not real-input acceptance evidence.
extends SceneTree

const Gameplay = preload("res://gameplay.gd")
var failures: Array = []
var checks: Array = []
var game
var world: Node3D
var balance_mode: String = ""
var balance_ticks: int = 0
var balance_events: Array = []
var observed_events: Array = []

class VisualProbe:
	extends Node
	var calls: Dictionary = {}
	func spawn_enemy(_id,_kind,_position):
		calls["spawn_enemy"] = int(calls.get("spawn_enemy",0))+1
	func remove_enemy(_id,_defeated):
		calls["remove_enemy"] = int(calls.get("remove_enemy",0))+1
	func effect(_kind,_position,_radius):
		calls["effect"] = int(calls.get("effect",0))+1

func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if "--balance-active" in args:
		balance_mode = "active"
	elif "--balance-afk" in args:
		balance_mode = "afk"
	call_deferred("_run" if balance_mode.is_empty() else "_run_balance")

func check(condition: bool,label: String) -> void:
	checks.append({"name":label,"passed":condition})
	if not condition:
		failures.append(label)
		push_error(label)

func reset_game() -> void:
	game.restart()
	game.set_physics_process(false)
	observed_events.clear()

func _record_event(key: String, data: Dictionary) -> void:
	observed_events.append({"key":key,"data":data.duplicate(true)})

func _cleared_wave_events() -> Array[int]:
	var result: Array[int] = []
	for event: Dictionary in observed_events:
		if event["key"] == "wave_cleared":
			result.append(int(event["data"]["wave"]))
	return result

func _shop_available(item: String) -> bool:
	for entry: Dictionary in game.snapshot()["shop"]:
		if entry["key"] == item:
			return bool(entry["available"])
	return false

func _run() -> void:
	world = Node3D.new()
	root.add_child(world)
	var probe = VisualProbe.new()
	root.add_child(probe)
	game = Gameplay.new()
	root.add_child(game)
	game.setup(world,probe,null)
	game.set_physics_process(false)
	game.game_event.connect(_record_event)
	check(game.gold==420 and game.nexus_hp==20 and game.hero_hp==240.0,"initial economy and health")
	check(game.hero is CharacterBody3D and game.hero.collision_mask==1,"real colliding hero body")
	check(Gameplay.LANES.size()==2 and Gameplay.PADS.size()==12,"two lanes and twelve fixed pads")
	check(not game.build_tower("sunbow"),"build requires pad selection")
	game.select_pad(0)
	check(game.build_tower("sunbow") and game.gold==340,"sunbow build costs 80")
	check(not game.build_tower("frost"),"occupied pad rejects duplicate build")
	check(game.upgrade_tower("pierce") and game.gold==230,"split branch upgrade costs 110")
	check(not game.upgrade_tower("volley"),"branch commitment cannot change")
	check(game.sell_tower() and game.gold==363,"selling returns floor 70 percent")
	check(game.towers.is_empty(),"selling removes simulation tower")
	for kind in Gameplay.TOWER_DATA.keys():
		for branch in Gameplay.TOWER_DATA[kind]["branches"]:
			reset_game()
			game.gold = 1000
			game.select_pad(2)
			check(game.build_tower(kind) and game.upgrade_tower(branch),"build and upgrade "+kind+"/"+branch)
			check(game._tower_stats(game.towers[2])["damage"]>0,"valid branch stats "+branch)
	reset_game()
	check(game.buy_item("blade") and game.hero_damage==44.0 and game.gold==310,"blade adds 12 damage")
	check(game.buy_item("plate") and game.hero_max_hp==305.0,"plate adds max health")
	check(game.buy_item("focus"),"focus purchase succeeds")
	check(not _shop_available("potion"),"full health disables potion in shop snapshot")
	check(not game.buy_item("potion"),"full health potion rejected without charge")
	game.hero_hp = 30.0
	game.gold = 45
	check(_shop_available("potion"),"injured hero can buy an affordable potion")
	check(game.buy_item("potion") and game.hero_hp==180.0 and game.gold==0,"potion heals 150 for 45 gold")
	reset_game()
	var enemy_id: int = game._spawn_enemy("scout",0,1)
	game.enemies[enemy_id]["position"] = game.hero.position+Vector3(1,0,0)
	check(game.cast_skill("q") and game.kills==1 and game.gold==429,"Q deals damage and awards kill bounty")
	check(not game.cast_skill("q"),"skill cooldown prevents spam")
	check(not game.cast_skill("r"),"ultimate requires level three")
	game._gain_xp(195)
	check(game.hero_level==3 and game.hero_damage==44.0,"experience levels hero and improves attack")
	check(game.cast_skill("r") and game._pending_blasts.size()==3,"ultimate schedules three impacts")
	game._update_effect_zones(2.0)
	check(game._pending_blasts.is_empty(),"scheduled impacts resolve")
	game.hero_hp = 10.0
	check(game.cast_skill("e") and game.hero_hp>10.0 and game._rally_timer==6.0,"rally heals and grants finite buff")
	var readback: Dictionary = game.snapshot()
	readback["hero"]["equipment"]["blade"] = 999
	readback["cooldowns"]["q"] = -999
	check(game.equipment["blade"]==0 and game.skill_cooldowns["q"]>=0,"snapshot is deep detached and read only")
	check(JSON.stringify(readback).length()>100,"snapshot is JSON serializable")
	reset_game()
	check(game.start_wave() and game.wave==1 and game.spawn_queue.size()==11,"first wave queues eleven enemies")
	check(not game.start_wave(),"cannot call wave while spawning")
	game._update_spawns(100.0)
	check(game.spawn_queue.is_empty() and game.enemies.size()==11,"finite spawn queue drains deterministically")
	for id in game.enemies.keys().slice(0,7):
		game._damage_enemy(id,10000.0,"holy")
	game._check_wave_complete()
	var previous_gold: int = game.gold
	check(game.snapshot()["early_call"],"early call unlocks at four surviving enemies")
	check(game.start_wave() and game.wave==2 and game.enemies.size()==4 and game.gold==previous_gold+30,"early call grants 30 while survivors remain")
	check(_cleared_wave_events().is_empty(),"early call does not announce an unfinished previous wave as cleared")
	game._check_wave_complete()
	check(game.gold==previous_gold+30 and _cleared_wave_events().is_empty(),"survivors and queued enemies prevent both completion rewards")
	game._update_spawns(100.0)
	for id in game.enemies.keys():
		if int(game.enemies[id]["spawn_wave"]) == 2:
			game._damage_enemy(id,10000.0,"holy")
	var before_reward: int = game.gold
	game._check_wave_complete()
	check(game.gold==before_reward+50 and _cleared_wave_events()==[2],"overlapped wave two earns its own completion reward before wave one")
	check(game.phase=="wave" and game.enemies.size()==4,"older wave survivors keep combat active after newer wave clears")
	before_reward = game.gold
	game._check_wave_complete()
	check(game.gold==before_reward and _cleared_wave_events()==[2],"rechecking cleared overlapping wave cannot duplicate its reward")
	for id in game.enemies.keys():
		game._damage_enemy(id,10000.0,"holy")
	before_reward = game.gold
	game._check_wave_complete()
	check(game.gold==before_reward+45 and _cleared_wave_events()==[2,1],"last wave-one survivors award wave-one completion exactly once")
	check(game.phase=="build" and game._pending_wave_rewards.is_empty(),"all overlapped waves cleared returns to build with no pending rewards")
	before_reward = game.gold
	game._check_wave_complete()
	check(game.gold==before_reward and _cleared_wave_events()==[2,1],"build-phase completion recheck cannot pay again")
	game.start_wave()
	check(not game._pending_wave_rewards.is_empty(),"a newly started wave has a pending completion reward")
	reset_game()
	check(game._pending_wave_rewards.is_empty(),"restart clears pending rewards from the previous run")
	game.start_wave()
	game._update_spawns(100.0)
	for id in game.enemies.keys():
		game._damage_enemy(id,10000.0,"holy")
	before_reward = game.gold
	game._check_wave_complete()
	check(game.gold==before_reward+45 and _cleared_wave_events()==[1],"new run receives only its fresh wave-one reward after restart")
	reset_game()
	game._damage_hero(10000.0)
	check(game.hero_respawn==8.0 and game.hero_hp==0 and game.gold==390,"death costs gold and starts respawn")
	check(not game.cast_skill("e") and not game.buy_item("blade"),"dead hero cannot cast or buy")
	game._update_hero(8.1)
	check(game.hero_respawn==0 and game.hero_hp==game.hero_max_hp and game.hero.position==Vector3(10,0,5),"hero respawns near core with full health")
	reset_game()
	game.start_wave()
	game.spawn_queue.clear()
	var boss_id: int = game._spawn_enemy("boss",0,8)
	game._damage_enemy(boss_id,1600,"holy")
	game._update_boss(game.enemies[boss_id],0.1)
	check(game.enemies[boss_id]["boss_phase"]==2,"boss enrages below half health")
	game._update_boss(game.enemies[boss_id],10.0)
	check(game._pending_blasts.size()==1,"boss telegraphs delayed area attack")
	game.enemies[boss_id]["segment"] = 6
	game.enemies[boss_id]["position"] = Vector3(12.99,0,5)
	game.enemies[boss_id]["offset"] = 0.0
	game._move_enemy_on_lane(game.enemies[boss_id],1.0)
	check(game.nexus_hp==0 and game.phase=="defeat","boss reaching core is genuine defeat")
	reset_game()
	game.wave = 8
	game.phase = "wave"
	game._check_wave_complete()
	check(game.phase=="victory","all final wave enemies cleared gives victory")
	game.restart()
	check(game.phase=="build" and game.wave==0 and game.gold==420 and game.kills==0,"restart clears terminal state")
	game.toggle_pause()
	var old_elapsed: float = game.elapsed
	game._physics_process(1.0)
	check(game.elapsed==old_elapsed and not game.start_wave(),"pause freezes simulation and commands")
	game.toggle_pause()
	game.set_speed(2.0)
	check(game.speed==2.0,"two times speed is explicit")
	game.set_speed(999.0)
	check(game.speed==2.0,"speed clamps to supported values")
	# Physics acceptance inside a headless unit fixture: move into a real tower collider.
	reset_game()
	await physics_frame
	game.select_pad(0)
	game.build_tower("sunbow")
	game.hero.position = Vector3(-13,0,-4)
	game.set_move_input(Vector2.RIGHT)
	game.set_physics_process(true)
	for i in range(45):
		await physics_frame
	game.set_move_input(Vector2.ZERO)
	game.set_physics_process(false)
	check(game.hero.position.x < -12.0 and game.hero.position.x > -13.0,"hero is physically blocked by tower cylinder")
	game.set_move_target(Vector3(-9,0,-4))
	game.set_physics_process(true)
	for i in range(150):
		await physics_frame
	game.set_physics_process(false)
	check(game.hero.position.distance_to(Vector3(-9,0,-4))<0.5,"click movement steers around a solid tower")
	game.select_pad(0)
	check(game.sell_tower(),"tower sale succeeds before collision removal check")
	await physics_frame
	await physics_frame
	game.hero.position = Vector3(-13,0,-4)
	game.set_move_input(Vector2.RIGHT)
	game.set_physics_process(true)
	for i in range(45):
		await physics_frame
	game.set_move_input(Vector2.ZERO)
	game.set_physics_process(false)
	check(game.hero.position.x > -10.0,"sold tower no longer blocks the hero")
	var wall := StaticBody3D.new()
	wall.position = Vector3(5,1,0)
	var wall_collision := CollisionShape3D.new()
	var wall_shape := BoxShape3D.new()
	wall_shape.size = Vector3(1,2,6)
	wall_collision.shape = wall_shape
	wall.add_child(wall_collision)
	world.add_child(wall)
	await physics_frame
	game.hero.position = Vector3(2,0,0)
	game.set_move_input(Vector2.RIGHT)
	game.set_physics_process(true)
	for i in range(60):
		await physics_frame
	game.set_physics_process(false)
	check(game.hero.position.x > 3.5 and game.hero.position.x < 4.2,"box scenery blocks the capsule without penetration")
	game.set_move_input(Vector2(1,1).normalized())
	game.set_physics_process(true)
	for i in range(20):
		await physics_frame
	game.set_move_input(Vector2.ZERO)
	game.set_physics_process(false)
	check(game.hero.position.x < 4.2 and game.hero.position.z > 1.0,"diagonal movement slides along box scenery")
	check(is_zero_approx(game.hero.position.y),"floating hero remains on the gameplay plane")
	wall.queue_free()
	await physics_frame
	game.hero.position = Gameplay.PADS[1]
	game.select_pad(1)
	var saved_gold: int = game.gold
	check(not game.build_tower("sunbow") and game.gold==saved_gold,"building cannot trap hero inside tower")
	check(probe.calls.get("spawn_enemy",0)>0 and probe.calls.get("effect",0)>0,"visual adapter receives gameplay events")
	print("DAWNKEEP_GAMEPLAY_CHECKS "+JSON.stringify({"checks":checks,"passed":failures.is_empty(),"failures":failures,"scope":"headless simulation and physical collision fixture; not real-input acceptance"}))
	quit(0 if failures.is_empty() else 1)


func _run_balance() -> void:
	# Public-command-only controller. No direct state assignment, spawning, kills,
	# health overrides, teleportation, or terminal-state injection in this mode.
	world = Node3D.new()
	root.add_child(world)
	game = Gameplay.new()
	root.add_child(game)
	game.setup(world,null,null)
	game.game_event.connect(_balance_event)
	if balance_mode == "active":
		for item in ["blade","plate","focus","boots"]:
			game.buy_item(item)

func _balance_event(key: String,data: Dictionary) -> void:
	if key in ["wave_cleared","hero_fallen","boss_arrived","boss_defeated","victory","defeat"]:
		balance_events.append({"time":game.elapsed,"key":key,"data":data})

func _physics_process(_dt: float) -> bool:
	if balance_mode.is_empty() or game == null:
		return false
	balance_ticks += 1
	var state: Dictionary = game.snapshot()
	if state["phase"] in ["victory","defeat"] or balance_ticks>60*900:
		var expected: String = "victory" if balance_mode=="active" else "defeat"
		var passed: bool = state["phase"]==expected
		print("DAWNKEEP_BALANCE "+JSON.stringify({"controller":balance_mode,"passed":passed,"expected":expected,"phase":state["phase"],"wave":state["wave"],"hp":state["core_hp"],"kills":state["kills"],"deaths":state["deaths"],"elapsed":state["elapsed"],"hero_level":state["hero"]["level"],"gold":state["gold"],"equipment":state["hero"]["equipment"],"events":balance_events,"scope":"automated public-command simulation; not real-input acceptance"}))
		quit(0 if passed else 1)
		return false
	if state["phase"]=="build":
		game.start_wave()
	if balance_mode=="afk":
		return false
	var hero_state: Dictionary = state["hero"]
	if balance_ticks%15==0:
		for item in ["blade","plate","blade","focus","plate","focus","boots"]:
			var limit: int = 2 if item=="boots" else 3
			if int(hero_state["equipment"][item])<limit:
				game.buy_item(item)
				break
	if hero_state["dead"]:
		return false
	if float(hero_state["hp"])<float(hero_state["max_hp"])*0.7:
		game.cast_skill("e")
	if float(hero_state["hp"])<float(hero_state["max_hp"])*0.3 and balance_ticks%30==0:
		game.buy_item("potion")
	var p: Dictionary = hero_state["position"]
	var here = Vector3(p["x"],p["y"],p["z"])
	var target: Dictionary = {}
	var best: float = -INF
	var near: int = 0
	var boss_near: bool = false
	for enemy in state["enemies"]:
		var ep: Dictionary = enemy["position"]
		var distance: float = here.distance_to(Vector3(ep["x"],ep["y"],ep["z"]))
		if distance<4.9:
			near += 1
			if enemy["kind"]=="boss":
				boss_near = true
		var priority: float = float(enemy["progress"])-distance*0.12
		if priority>best:
			best = priority
			target = enemy
	if near>=2 or boss_near:
		game.cast_skill("q")
	if near>=4 or boss_near:
		game.cast_skill("r")
	if not target.is_empty():
		var p2: Dictionary = target["position"]
		var direction: Vector3 = Vector3(p2["x"],p2["y"],p2["z"])-here
		if direction.length()>2.2:
			direction = direction.normalized()
			game.set_move_input(Vector2(direction.x,direction.z))
		else:
			game.set_move_input(Vector2.ZERO)
	else:
		game.set_move_input(Vector2.ZERO)
	return false
