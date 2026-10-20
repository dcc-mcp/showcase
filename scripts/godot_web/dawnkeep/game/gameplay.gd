# Copyright DCC-MCP. Original gameplay code; case license is declared at packaging.
# Original Dawnkeep / 曙光守誓 simulation. Visuals and UI are separate adapters.
extends Node

signal state_changed(state: Dictionary)
signal game_event(key: String, data: Dictionary)
signal finished(victory: bool)

const LANES = [
	[Vector3(-15,0,-7), Vector3(-8,0,-7), Vector3(-8,0,2), Vector3(-2,0,2), Vector3(-2,0,-5), Vector3(7,0,-5), Vector3(7,0,5), Vector3(13,0,5)],
	[Vector3(-15,0,8), Vector3(-11,0,8), Vector3(-11,0,2), Vector3(-2,0,2), Vector3(-2,0,-5), Vector3(7,0,-5), Vector3(7,0,5), Vector3(13,0,5)]
]
const PADS = [Vector3(-11,0,-4), Vector3(-5,0,-7), Vector3(-5,0,-1), Vector3(-8,0,5), Vector3(-3,0,5), Vector3(1,0,-2), Vector3(2,0,-8), Vector3(5,0,-1), Vector3(10,0,-3), Vector3(10,0,2), Vector3(4,0,7), Vector3(10,0,8)]
const TOWER_DATA = {
	"sunbow": {"cost":80, "damage":13.0, "interval":0.72, "range":5.4, "branches":["pierce", "volley"], "upgrade_cost":110},
	"ember": {"cost":115, "damage":32.0, "interval":2.1, "range":5.8, "branches":["inferno", "siege"], "upgrade_cost":145},
	"frost": {"cost":100, "damage":7.0, "interval":1.1, "range":5.0, "branches":["deepfreeze", "shatter"], "upgrade_cost":125},
	"storm": {"cost":145, "damage":18.0, "interval":1.5, "range":5.4, "branches":["conduit", "tempest"], "upgrade_cost":175}
}
const ENEMY_DATA = {
	"scout": {"hp":62.0, "speed":2.0, "armor":0.0, "gold":9, "xp":12, "leak":1, "damage":10.0, "attack_interval":1.25},
	"skeleton": {"hp":114.0, "speed":1.55, "armor":0.32, "gold":13, "xp":18, "leak":1, "damage":15.0, "attack_interval":1.45},
	"runner": {"hp":75.0, "speed":3.0, "armor":0.05, "gold":11, "xp":15, "leak":1, "damage":9.0, "attack_interval":0.95},
	"brute": {"hp":280.0, "speed":1.05, "armor":0.18, "gold":25, "xp":34, "leak":3, "damage":26.0, "attack_interval":1.9},
	"wraith": {"hp":145.0, "speed":2.2, "armor":0.40, "gold":17, "xp":24, "leak":2, "damage":18.0, "attack_interval":1.2},
	"boss": {"hp":2900.0, "speed":0.65, "armor":0.22, "gold":250, "xp":450, "leak":20, "damage":36.0, "attack_interval":1.5}
}
const SHOP_DATA = {
	"blade": {"cost":110, "max_count":3},
	"plate": {"cost":95, "max_count":3},
	"focus": {"cost":120, "max_count":3},
	"boots": {"cost":85, "max_count":2},
	"potion": {"cost":45, "max_count":99}
}
# Each entry: enemy kind, count, lane (2 alternates), interval. Waves are finite.
const WAVES = [
	[["scout",7,0,1.25],["scout",4,1,1.25]],
	[["scout",5,1,0.9],["skeleton",5,0,1.4],["runner",4,1,0.8]],
	[["runner",8,2,0.85],["skeleton",6,0,1.05],["brute",2,1,2.0]],
	[["skeleton",8,2,0.95],["brute",4,0,1.8],["runner",6,1,0.7]],
	[["wraith",6,1,1.0],["skeleton",7,0,0.95],["brute",4,2,1.6],["runner",5,2,0.7]],
	[["brute",6,2,1.3],["wraith",8,0,0.9],["runner",8,1,0.7]],
	[["skeleton",10,2,0.75],["wraith",8,1,0.85],["brute",6,0,1.2],["runner",7,2,0.65]],
	[["skeleton",5,2,0.8],["boss",1,0,1.0],["brute",4,1,1.6],["wraith",7,2,1.0],["runner",8,1,0.7]]
]

var world: Node3D
var visuals: Node
var hud: Control
var hero: CharacterBody3D
var towers: Dictionary = {}
var enemies: Dictionary = {}
var spawn_queue: Array = []
var gold: int = 420
var nexus_hp: int = 20
var wave: int = 0
var phase: String = "build"
var selected_pad: int = -1
var paused: bool = false
var speed: float = 1.0
var kills: int = 0
var deaths: int = 0
var elapsed: float = 0.0
var hero_level: int = 1
var hero_xp: int = 0
var hero_hp: float = 240.0
var hero_max_hp: float = 240.0
var hero_damage: float = 32.0
var hero_respawn: float = 0.0
var equipment: Dictionary = {"blade":0, "plate":0, "focus":0, "boots":0, "potion":0}
var skill_cooldowns: Dictionary = {"q":0.0, "e":0.0, "r":0.0}
var skill_max_cooldowns: Dictionary = {"q":8.0, "e":16.0, "r":30.0}
var _move_input: Vector2 = Vector2.ZERO
var _move_target: Vector3 = Vector3.ZERO
var _has_move_target: bool = false
var _hero_facing: Vector3 = Vector3(0,0,-1)
var _hero_attack_timer: float = 0.0
var _hero_attack_flash: float = 0.0
var _hero_hurt_flash: float = 0.0
var _rally_timer: float = 0.0
var _spawn_timer: float = 0.0
var _next_enemy_id: int = 1
var _ui_timer: float = 0.0
var _call_available: bool = false
var _last_action: String = "ready"
var _boss_id: int = -1
var _ready_for_play: bool = false
var _early_calls: int = 0
var _pending_wave_rewards: Dictionary = {}
var _ground_zones: Array = []
var _pending_blasts: Array = []

func setup(p_world: Node3D, p_visuals: Node, p_hud: Control = null) -> void:
	world = p_world
	visuals = p_visuals
	hud = p_hud
	process_mode = Node.PROCESS_MODE_ALWAYS
	_create_hero_body()
	_ready_for_play = true
	restart()

func _create_hero_body() -> void:
	hero = CharacterBody3D.new()
	hero.name = "DawnWardenBody"
	hero.motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
	hero.collision_layer = 2
	hero.collision_mask = 1
	var collision = CollisionShape3D.new()
	var capsule = CapsuleShape3D.new()
	capsule.radius = 0.38
	capsule.height = 1.55
	collision.shape = capsule
	collision.position.y = 0.8
	hero.add_child(collision)
	world.add_child(hero)

func restart() -> void:
	if not _ready_for_play:
		return
	for id in enemies.keys():
		_visual("remove_enemy", [id, false])
	for id in towers.keys():
		_visual("remove_tower", [id])
		var old_body = towers[id].get("body")
		if is_instance_valid(old_body):
			old_body.queue_free()
	enemies.clear()
	towers.clear()
	spawn_queue.clear()
	_ground_zones.clear()
	_pending_blasts.clear()
	gold = 420
	nexus_hp = 20
	wave = 0
	phase = "build"
	selected_pad = -1
	paused = false
	speed = 1.0
	kills = 0
	deaths = 0
	elapsed = 0.0
	hero_level = 1
	hero_xp = 0
	hero_max_hp = 240.0
	hero_hp = hero_max_hp
	hero_damage = 32.0
	hero_respawn = 0.0
	equipment = {"blade":0, "plate":0, "focus":0, "boots":0, "potion":0}
	skill_cooldowns = {"q":0.0, "e":0.0, "r":0.0}
	_move_input = Vector2.ZERO
	_has_move_target = false
	_hero_facing = Vector3(-1,0,0)
	_hero_attack_timer = 0.0
	_hero_attack_flash = 0.0
	_hero_hurt_flash = 0.0
	_rally_timer = 0.0
	_spawn_timer = 0.0
	_next_enemy_id = 1
	_boss_id = -1
	_early_calls = 0
	_pending_wave_rewards.clear()
	_call_available = false
	_last_action = "ready"
	hero.position = Vector3(-6,0,0)
	hero.velocity = Vector3.ZERO
	_visual("select_pad", [-1,0.0])
	_visual("effect", ["restart",hero.position,1.0])
	_update_hero_visual()
	_emit_state()

func _physics_process(delta: float) -> void:
	if not _ready_for_play or paused or phase in ["victory", "defeat"]:
		return
	var dt: float = minf(delta,0.08) * speed
	elapsed += dt
	for key in skill_cooldowns.keys():
		skill_cooldowns[key] = maxf(0.0, float(skill_cooldowns[key]) - dt)
	_rally_timer = maxf(0.0, _rally_timer - dt)
	_hero_attack_flash = maxf(0.0, _hero_attack_flash-dt)
	_hero_hurt_flash = maxf(0.0, _hero_hurt_flash-dt)
	_update_spawns(dt)
	_update_hero(dt)
	_update_enemies(dt)
	_update_towers(dt)
	_update_effect_zones(dt)
	_check_wave_complete()
	_update_hero_visual()
	_ui_timer -= delta
	if _ui_timer <= 0.0:
		_ui_timer = 0.10
		_emit_state()

func select_pad(index: int) -> void:
	if index < -1 or index >= PADS.size():
		return
	selected_pad = index
	var radius: float = 0.0
	if towers.has(index):
		radius = float(_tower_stats(towers[index])["range"])
	_visual("select_pad", [index,radius])
	_emit_state()

func build_tower(kind: String) -> bool:
	if not _can_act() or selected_pad < 0 or towers.has(selected_pad) or not TOWER_DATA.has(kind):
		return _reject("invalid_build")
	if hero.position.distance_to(PADS[selected_pad]) < 1.18:
		return _reject("hero_on_pad")
	var data: Dictionary = TOWER_DATA[kind]
	if gold < int(data["cost"]):
		return _reject("not_enough_gold")
	gold -= int(data["cost"])
	var body = StaticBody3D.new()
	body.name = "TowerCollider%d" % selected_pad
	body.position = PADS[selected_pad]
	body.collision_layer = 1
	body.collision_mask = 2
	var collision = CollisionShape3D.new()
	var shape = CylinderShape3D.new()
	shape.radius = 0.77
	shape.height = 2.0
	collision.shape = shape
	collision.position.y = 1.0
	body.add_child(collision)
	world.add_child(body)
	towers[selected_pad] = {"id":selected_pad,"kind":kind,"level":1,"branch":"","spent":int(data["cost"]),"timer":0.1,"body":body,"shots":0}
	_visual("spawn_tower", [selected_pad,kind,PADS[selected_pad],1,""])
	_visual("effect", ["build",PADS[selected_pad],1.4])
	select_pad(selected_pad)
	_event("tower_built", {"kind":kind})
	return true

func upgrade_tower(branch: String) -> bool:
	if not _can_act() or not towers.has(selected_pad):
		return _reject("no_tower")
	var tower: Dictionary = towers[selected_pad]
	var data: Dictionary = TOWER_DATA[tower["kind"]]
	if int(tower["level"]) >= 2 or branch not in data["branches"]:
		return _reject("invalid_upgrade")
	var cost: int = int(data["upgrade_cost"])
	if gold < cost:
		return _reject("not_enough_gold")
	gold -= cost
	tower["level"] = 2
	tower["branch"] = branch
	tower["spent"] += cost
	_visual("update_tower", [selected_pad,2,branch])
	_visual("effect", ["upgrade",PADS[selected_pad],1.8])
	select_pad(selected_pad)
	_event("tower_upgraded", {"kind":tower["kind"],"branch":branch})
	return true

func sell_tower() -> bool:
	if not _can_act() or not towers.has(selected_pad):
		return _reject("no_tower")
	var tower: Dictionary = towers[selected_pad]
	var refund: int = int(floor(float(tower["spent"])*0.7))
	gold += refund
	if is_instance_valid(tower.get("body")):
		tower["body"].queue_free()
	_visual("remove_tower", [selected_pad])
	towers.erase(selected_pad)
	_visual("select_pad", [selected_pad,0.0])
	_event("tower_sold", {"gold":refund})
	return true

func buy_item(item: String) -> bool:
	if not _can_act() or not SHOP_DATA.has(item) or hero_respawn > 0.0:
		return _reject("invalid_purchase")
	var data: Dictionary = SHOP_DATA[item]
	if int(equipment[item]) >= int(data["max_count"]):
		return _reject("item_maxed")
	if gold < int(data["cost"]):
		return _reject("not_enough_gold")
	if item == "potion" and hero_hp >= hero_max_hp:
		return _reject("health_full")
	gold -= int(data["cost"])
	equipment[item] += 1
	match item:
		"blade": hero_damage += 12.0
		"plate":
			hero_max_hp += 65.0
			hero_hp += 65.0
		"potion": hero_hp = minf(hero_max_hp,hero_hp+150.0)
	_visual("effect", ["purchase",hero.position,1.4])
	_event("item_bought", {"item":item})
	return true

func start_wave() -> bool:
	if not _can_act() or wave >= WAVES.size():
		return _reject("cannot_start_wave")
	var accelerated: bool = phase == "wave"
	if accelerated and not _call_available:
		return _reject("wave_not_ready")
	if accelerated:
		# Only after the old wave fully spawned and <= 4 enemies remain.
		# The risk is real: the survivors stay and the next wave overlaps.
		gold += 30
		_early_calls += 1
	wave += 1
	if wave < WAVES.size():
		_pending_wave_rewards[wave] = 40+wave*5
	phase = "wave"
	_call_available = false
	var entries: Array = WAVES[wave-1]
	for group in entries:
		for i in range(int(group[1])):
			var lane: int = int(group[2])
			if lane == 2:
				lane = i % 2
			spawn_queue.append({"kind":group[0],"lane":lane,"interval":float(group[3]),"wave":wave})
	_spawn_timer = 0.25
	_event("wave_started", {"wave":wave,"early":accelerated,"bonus":30 if accelerated else 0})
	return true

func cast_skill(skill: String) -> bool:
	skill = skill.to_lower()
	if not _can_act() or not skill_cooldowns.has(skill) or hero_respawn > 0.0:
		return _reject("skill_unavailable")
	if float(skill_cooldowns[skill]) > 0.0:
		return _reject("skill_cooling")
	if skill == "r" and hero_level < 3:
		return _reject("skill_locked")
	var focus: float = 1.0+0.20*float(equipment["focus"])
	var cooldown_factor: float = 1.0-0.08*float(equipment["focus"])
	skill_cooldowns[skill] = float(skill_max_cooldowns[skill])*cooldown_factor
	match skill:
		"q":
			var damage: float = (85.0+12.0*float(hero_level-1))*focus
			for id in _enemies_in_radius(hero.position,4.9):
				_damage_enemy(id,damage,"holy")
			_visual("effect", ["cleave",hero.position,4.9])
			_hero_attack_flash = 0.4
		"e":
			hero_hp = minf(hero_max_hp, hero_hp+(75.0+10.0*float(hero_level))*focus)
			_rally_timer = 6.0
			_visual("effect", ["rally",hero.position,5.8])
		"r":
			# Telegraph a short delay, then three independently scheduled impacts.
			for i in range(3):
				_pending_blasts.append({"position":hero.position,"timer":0.38+float(i)*0.35,"radius":7.0,"damage":(76.0+hero_level*8.0)*focus,"kind":"starfall"})
			_visual("effect", ["starfall_warning",hero.position,7.0])
	_event("skill_cast", {"skill":skill})
	return true

func set_move_target(position: Vector3) -> void:
	if not _can_act() or hero_respawn > 0.0:
		return
	_move_target = Vector3(clampf(position.x,-16.7,14.7),0,clampf(position.z,-9.8,10.3))
	_has_move_target = true
	_move_input = Vector2.ZERO
	_visual("effect", ["move",_move_target,0.45])

func set_move_input(direction: Vector2) -> void:
	_move_input = direction.limit_length(1.0)
	if _move_input.length_squared() > 0.01:
		_has_move_target = false

func toggle_pause() -> void:
	if phase in ["victory","defeat"]:
		return
	paused = not paused
	_move_input = Vector2.ZERO
	if paused:
		hero.velocity = Vector3.ZERO
	_emit_state()

func set_speed(value: float) -> void:
	speed = 2.0 if value >= 1.5 else 1.0
	_emit_state()

func _can_act() -> bool:
	return _ready_for_play and not paused and phase not in ["victory","defeat"]

func _reject(key: String) -> bool:
	_last_action = key
	game_event.emit(key,{})
	_emit_state()
	return false

func _event(key: String, data: Dictionary) -> void:
	_last_action = key
	game_event.emit(key,data)
	_emit_state()

func _update_spawns(dt: float) -> void:
	if phase != "wave" or spawn_queue.is_empty():
		return
	_spawn_timer -= dt
	while _spawn_timer <= 0.0 and not spawn_queue.is_empty():
		var entry: Dictionary = spawn_queue.pop_front()
		_spawn_enemy(str(entry["kind"]),int(entry["lane"]),int(entry["wave"]))
		_spawn_timer += float(entry["interval"])

func _spawn_enemy(kind: String, lane: int, spawn_wave: int) -> int:
	var id: int = _next_enemy_id
	_next_enemy_id += 1
	var data: Dictionary = ENEMY_DATA[kind]
	var scale_hp: float = 1.0+0.055*float(spawn_wave-1)
	if kind == "boss":
		scale_hp = 1.0
	var hp: float = float(data["hp"])*scale_hp
	var offset: float = float((id%3)-1)*0.28
	var position: Vector3 = LANES[lane][0]+Vector3(0,0,offset)
	enemies[id] = {"id":id,"kind":kind,"lane":lane,"segment":0,"distance":0.0,"progress":0.0,"position":position,"direction":Vector3.RIGHT,"hp":hp,"max_hp":hp,"armor":float(data["armor"]),"speed":float(data["speed"]),"gold":int(data["gold"]),"xp":int(data["xp"]),"leak":int(data["leak"]),"damage":float(data["damage"])*(1.0+0.025*float(spawn_wave-1)),"attack_interval":float(data["attack_interval"]),"attack_timer":0.45,"slow":1.0,"slow_timer":0.0,"burn_timer":0.0,"burn_damage":0.0,"vulnerable":0.0,"stun":0.0,"attacking":false,"boss_phase":1,"slam_timer":6.0,"offset":offset,"spawn_wave":spawn_wave}
	if kind == "boss":
		_boss_id = id
		_event("boss_arrived", {"id":id})
	_visual("spawn_enemy", [id,kind,position])
	return id

func _update_hero(dt: float) -> void:
	if hero_respawn > 0.0:
		hero_respawn = maxf(0.0,hero_respawn-dt)
		hero.velocity = Vector3.ZERO
		if hero_respawn <= 0.0:
			hero.position = Vector3(10,0,5)
			hero_hp = hero_max_hp
			_visual("effect", ["respawn",hero.position,2.0])
			_event("hero_respawned",{})
		return
	if phase == "build":
		hero_hp = minf(hero_max_hp,hero_hp+hero_max_hp*0.08*dt)
	else:
		hero_hp = minf(hero_max_hp,hero_hp+(1.6+float(equipment["plate"])*0.6)*dt)
	var direction = Vector3(_move_input.x,0,_move_input.y)
	if _has_move_target:
		var offset: Vector3 = _move_target-hero.position
		offset.y = 0
		if offset.length() <= 0.22:
			_has_move_target = false
		else:
			direction = _steer_direction(offset.normalized())
	var move_speed: float = 5.8+float(equipment["boots"])*0.9
	if _rally_timer > 0.0:
		move_speed *= 1.12
	hero.velocity = direction*move_speed*speed
	hero.move_and_slide()
	hero.position.x = clampf(hero.position.x,-16.7,14.7)
	hero.position.z = clampf(hero.position.z,-9.8,10.3)
	hero.position.y = 0
	if direction.length_squared() > 0.01:
		_hero_facing = direction.normalized()
	_hero_attack_timer -= dt
	if _hero_attack_timer <= 0.0:
		var targets: Array = _enemies_in_radius(hero.position,3.2)
		if not targets.is_empty():
			targets.sort_custom(func(a,b): return hero.position.distance_squared_to(enemies[a]["position"]) < hero.position.distance_squared_to(enemies[b]["position"]))
			var id: int = int(targets[0])
			var target_position: Vector3 = enemies[id]["position"]
			_hero_facing = (target_position-hero.position).normalized()
			_hero_attack_timer = 0.70/(1.55 if _rally_timer > 0.0 else 1.0)
			_hero_attack_flash = 0.25
			_visual("projectile", [hero.position+Vector3.UP, target_position+Vector3.UP*0.7,"hero"])
			_damage_enemy(id,hero_damage,"physical")
			# Basic attacks cleave nearby attackers so the hero is the primary defender.
			for other_id in targets.slice(1,4):
				if enemies.has(other_id) and Vector3(enemies[other_id]["position"]).distance_to(target_position) < 1.8:
					_damage_enemy(int(other_id),hero_damage*0.52,"physical")

func _steer_direction(direction: Vector3) -> Vector3:
	# Short obstacle feelers keep click-to-move useful around solid towers/props.
	# Manual WASD remains unassisted and uses CharacterBody3D sliding.
	if not is_inside_tree() or world.get_world_3d() == null:
		return direction
	var space = world.get_world_3d().direct_space_state
	var origin: Vector3 = hero.global_position+Vector3(0,0.7,0)
	var query = PhysicsRayQueryParameters3D.create(origin,origin+direction*1.35,1,[hero.get_rid()])
	if space.intersect_ray(query).is_empty():
		return direction
	var best: Vector3 = Vector3.ZERO
	var best_score: float = -100.0
	for degrees in [40.0,-40.0,75.0,-75.0,110.0,-110.0]:
		var candidate: Vector3 = direction.rotated(Vector3.UP,deg_to_rad(degrees))
		query.to = origin+candidate*1.4
		if space.intersect_ray(query).is_empty():
			var score: float = candidate.dot(direction)
			if score > best_score:
				best = candidate
				best_score = score
	return best

func _update_enemies(dt: float) -> void:
	for id in enemies.keys():
		if not enemies.has(id):
			continue
		var enemy: Dictionary = enemies[id]
		enemy["slow_timer"] = maxf(0.0,float(enemy["slow_timer"])-dt)
		enemy["stun"] = maxf(0.0,float(enemy["stun"])-dt)
		enemy["vulnerable"] = maxf(0.0,float(enemy["vulnerable"])-dt)
		if float(enemy["slow_timer"]) <= 0.0:
			enemy["slow"] = 1.0
		if float(enemy["burn_timer"]) > 0.0:
			enemy["burn_timer"] -= dt
			_damage_enemy(id,float(enemy["burn_damage"])*dt,"magic")
			if not enemies.has(id):
				continue
		enemy["attack_timer"] -= dt
		enemy["attacking"] = false
		var position: Vector3 = enemy["position"]
		var hero_distance: float = position.distance_to(hero.position)
		var kind: String = enemy["kind"]
		if kind == "boss":
			_update_boss(enemy,dt)
		if float(enemy["stun"]) > 0.0:
			_render_enemy(enemy)
			continue
		var attack_radius: float = 2.3 if kind == "boss" else 1.65
		var can_fight: bool = hero_respawn <= 0.0 and hero_distance < 3.2
		if can_fight:
			var toward_hero: Vector3 = (hero.position-position).normalized()
			enemy["direction"] = toward_hero
			if hero_distance > attack_radius:
				position += toward_hero*float(enemy["speed"])*float(enemy["slow"])*dt
				enemy["position"] = position
			else:
				enemy["attacking"] = true
				if float(enemy["attack_timer"]) <= 0.0:
					enemy["attack_timer"] = float(enemy["attack_interval"])
					_damage_hero(float(enemy["damage"]))
		else:
			_move_enemy_on_lane(enemy,dt)
		if enemies.has(id):
			_render_enemy(enemy)

func _move_enemy_on_lane(enemy: Dictionary, dt: float) -> void:
	var lane: Array = LANES[int(enemy["lane"])]
	var segment: int = int(enemy["segment"])
	var position: Vector3 = enemy["position"]
	var remaining: float = float(enemy["speed"])*float(enemy["slow"])*dt
	while remaining > 0.0 and segment < lane.size()-1:
		var next: Vector3 = lane[segment+1]+Vector3(0,0,float(enemy["offset"]))
		var delta: Vector3 = next-position
		var distance: float = delta.length()
		if distance <= remaining:
			position = next
			remaining -= distance
			segment += 1
		else:
			enemy["direction"] = delta/distance
			position += delta/distance*remaining
			remaining = 0.0
		enemy["progress"] += minf(distance, float(enemy["speed"])*float(enemy["slow"])*dt)
	enemy["segment"] = segment
	enemy["position"] = position
	if segment >= lane.size()-1:
		var id: int = int(enemy["id"])
		nexus_hp = maxi(0,nexus_hp-int(enemy["leak"]))
		_visual("effect", ["core_hit",Vector3(13,0,5),2.0])
		_visual("remove_enemy", [id,false])
		enemies.erase(id)
		_event("core_damaged", {"hp":nexus_hp,"damage":int(enemy["leak"])})
		if nexus_hp <= 0:
			_end_game(false)

func _update_boss(enemy: Dictionary,dt: float) -> void:
	var ratio: float = float(enemy["hp"])/float(enemy["max_hp"])
	if ratio < 0.50 and int(enemy["boss_phase"]) == 1:
		enemy["boss_phase"] = 2
		enemy["speed"] = float(enemy["speed"])*1.40
		enemy["attack_interval"] = float(enemy["attack_interval"])*0.75
		_visual("effect", ["boss_enrage",enemy["position"],4.0])
		_event("boss_enraged",{})
	enemy["slam_timer"] -= dt
	if float(enemy["slam_timer"]) <= 0.0:
		enemy["slam_timer"] = 6.0 if int(enemy["boss_phase"]) == 1 else 4.5
		var position: Vector3 = enemy["position"]
		_pending_blasts.append({"position":position,"timer":1.0,"radius":4.5,"damage":56.0,"kind":"boss_slam"})
		_visual("effect", ["boss_warning",position,4.5])

func _render_enemy(enemy: Dictionary) -> void:
	var status = {"slow":float(enemy["slow_timer"])>0.0,"burn":float(enemy["burn_timer"])>0.0,"stun":float(enemy["stun"])>0.0,"attacking":bool(enemy["attacking"]),"boss_phase":int(enemy["boss_phase"])}
	_visual("update_enemy", [int(enemy["id"]),enemy["position"],enemy["direction"],float(enemy["hp"])/float(enemy["max_hp"]),status])

func _damage_hero(damage: float) -> void:
	if hero_respawn > 0.0 or phase in ["victory","defeat"]:
		return
	var reduction: float = 1.0-0.07*float(equipment["plate"])
	hero_hp = maxf(0.0,hero_hp-damage*reduction)
	_hero_hurt_flash = 0.18
	if hero_hp <= 0.0:
		deaths += 1
		hero_respawn = minf(14.0,7.0+float(deaths))
		gold = maxi(0,gold-30)
		_has_move_target = false
		_move_input = Vector2.ZERO
		_rally_timer = 0.0
		_visual("effect", ["hero_death",hero.position,2.0])
		_event("hero_fallen", {"respawn":hero_respawn,"gold_lost":30})

func _update_towers(dt: float) -> void:
	for id in towers.keys():
		var tower: Dictionary = towers[id]
		tower["timer"] -= dt
		if float(tower["timer"]) > 0.0:
			continue
		var stats: Dictionary = _tower_stats(tower)
		var origin: Vector3 = PADS[id]
		var targets: Array = _enemies_in_radius(origin,float(stats["range"]))
		if targets.is_empty():
			continue
		targets.sort_custom(func(a,b): return float(enemies[a]["progress"]) > float(enemies[b]["progress"]))
		var target: int = int(targets[0])
		var position: Vector3 = enemies[target]["position"]
		var haste: float = 1.25 if _rally_timer>0 and origin.distance_to(hero.position)<5.8 else 1.0
		tower["timer"] = float(stats["interval"])/haste
		tower["shots"] += 1
		var kind: String = tower["kind"]
		var branch: String = tower["branch"]
		_visual("projectile", [origin+Vector3.UP*2.0,position+Vector3.UP*0.7,kind])
		match kind:
			"sunbow":
				_damage_enemy(target,float(stats["damage"]),"pierce" if branch=="pierce" else "physical")
				if branch == "volley":
					for extra in targets.slice(1,3):
						if enemies.has(extra):
							_visual("projectile", [origin+Vector3.UP*2.0,enemies[extra]["position"]+Vector3.UP*0.7,"sunbow"])
							_damage_enemy(int(extra),float(stats["damage"])*0.72,"physical")
			"ember":
				var radius: float = 2.35 if branch=="siege" else 1.7
				for hit in _enemies_in_radius(position,radius):
					_damage_enemy(int(hit),float(stats["damage"]),"magic")
					if branch=="inferno" and enemies.has(hit):
						enemies[hit]["burn_timer"] = 3.0
						enemies[hit]["burn_damage"] = 10.0
				_visual("effect", ["ember_burst",position,radius])
				if branch == "inferno":
					_ground_zones.append({"position":position,"radius":1.8,"timer":2.2,"tick":0.4,"damage":6.0})
			"frost":
				_damage_enemy(target,float(stats["damage"]),"magic")
				if enemies.has(target):
					enemies[target]["slow"] = 0.36 if branch=="deepfreeze" else 0.62
					enemies[target]["slow_timer"] = 2.2
					if branch == "shatter":
						enemies[target]["vulnerable"] = 3.0
					if branch=="deepfreeze" and int(tower["shots"])%4==0:
						enemies[target]["stun"] = 0.40 if enemies[target]["kind"]=="boss" else 0.85
			"storm":
				var count: int = 5 if branch=="conduit" else 3
				var hit_ids: Array = [target]
				var previous: Vector3 = position
				_damage_enemy(target,float(stats["damage"]),"magic")
				for chain in range(count-1):
					var next_id: int = -1
					var nearest: float = 3.5
					for candidate in enemies.keys():
						if candidate in hit_ids:
							continue
						var distance: float = previous.distance_to(enemies[candidate]["position"])
						if distance < nearest:
							nearest = distance
							next_id = int(candidate)
					if next_id < 0:
						break
					var next_pos: Vector3 = enemies[next_id]["position"]
					_visual("projectile", [previous+Vector3.UP,next_pos+Vector3.UP,"chain"])
					_damage_enemy(next_id,float(stats["damage"])*pow(0.85,chain+1),"magic")
					if branch=="tempest" and enemies.has(next_id):
						enemies[next_id]["stun"] = 0.30
					hit_ids.append(next_id)
					previous = next_pos

func _tower_stats(tower: Dictionary) -> Dictionary:
	var data: Dictionary = TOWER_DATA[tower["kind"]]
	var stats: Dictionary = {"damage":float(data["damage"]),"interval":float(data["interval"]),"range":float(data["range"])}
	match str(tower["branch"]):
		"pierce":
			stats["damage"] = 28.0
			stats["range"] = 6.4
		"volley":
			stats["damage"] = 16.0
			stats["interval"] = 0.58
		"inferno": stats["damage"] = 43.0
		"siege":
			stats["damage"] = 66.0
			stats["range"] = 7.0
			stats["interval"] = 2.5
		"deepfreeze":
			stats["damage"] = 11.0
			stats["range"] = 5.8
		"shatter":
			stats["damage"] = 24.0
			stats["interval"] = 0.9
		"conduit": stats["damage"] = 26.0
		"tempest":
			stats["damage"] = 28.0
			stats["interval"] = 1.05
	return stats

func _enemies_in_radius(center: Vector3,radius: float) -> Array:
	var result: Array = []
	for id in enemies.keys():
		if center.distance_squared_to(enemies[id]["position"]) <= radius*radius:
			result.append(id)
	return result

func _damage_enemy(id: int,damage: float,kind: String) -> void:
	if not enemies.has(id):
		return
	var enemy: Dictionary = enemies[id]
	var armor: float = float(enemy["armor"])
	if kind=="holy":
		armor = 0.0
	elif kind=="magic":
		armor *= 0.35
	elif kind=="pierce":
		armor *= 0.15
	var vulnerability: float = 1.25 if float(enemy["vulnerable"])>0.0 else 1.0
	enemy["hp"] -= damage*(1.0-armor)*vulnerability
	if float(enemy["hp"]) <= 0.0:
		gold += int(enemy["gold"])
		kills += 1
		_gain_xp(int(enemy["xp"]))
		_visual("remove_enemy", [id,true])
		_visual("effect", ["enemy_death",enemy["position"],0.6 if enemy["kind"]!="boss" else 3.0])
		enemies.erase(id)
		if enemy["kind"]=="boss":
			_event("boss_defeated",{})

func _gain_xp(amount: int) -> void:
	hero_xp += amount
	while hero_xp >= _xp_next() and hero_level < 10:
		hero_xp -= _xp_next()
		hero_level += 1
		hero_max_hp += 28.0
		hero_damage += 6.0
		if hero_respawn <= 0.0:
			hero_hp = minf(hero_max_hp,hero_hp+75.0)
		_visual("effect", ["level_up",hero.position,2.5])
		_event("level_up", {"level":hero_level})
	if hero_level >= 10:
		hero_xp = mini(hero_xp,_xp_next())

func _xp_next() -> int:
	return 45+hero_level*35

func _update_effect_zones(dt: float) -> void:
	for index in range(_ground_zones.size()-1,-1,-1):
		var zone: Dictionary = _ground_zones[index]
		zone["timer"] -= dt
		zone["tick"] -= dt
		if float(zone["tick"]) <= 0.0:
			zone["tick"] += 0.4
			for id in _enemies_in_radius(zone["position"],float(zone["radius"])):
				_damage_enemy(int(id),float(zone["damage"]),"magic")
		if float(zone["timer"]) <= 0.0:
			_ground_zones.remove_at(index)
	for index in range(_pending_blasts.size()-1,-1,-1):
		var blast: Dictionary = _pending_blasts[index]
		blast["timer"] -= dt
		if float(blast["timer"]) > 0.0:
			continue
		_visual("effect", [blast["kind"],blast["position"],blast["radius"]])
		if blast["kind"]=="boss_slam":
			if hero.position.distance_to(blast["position"]) < float(blast["radius"]):
				_damage_hero(float(blast["damage"]))
		else:
			for id in _enemies_in_radius(blast["position"],float(blast["radius"])):
				_damage_enemy(int(id),float(blast["damage"]),"holy")
		_pending_blasts.remove_at(index)

func _check_wave_complete() -> void:
	if phase != "wave":
		return
	_call_available = spawn_queue.is_empty() and enemies.size()<=4 and not enemies.is_empty() and wave<WAVES.size()
	var all_clear: bool = spawn_queue.is_empty() and enemies.is_empty()
	if all_clear and wave < WAVES.size():
		phase = "build"
		_call_available = false
	# Early calls overlap waves; completion belongs to each enemy's spawn wave,
	# not the newest wave number. Queued enemies still prevent its clear reward.
	var outstanding_waves: Dictionary = {}
	for entry: Dictionary in spawn_queue:
		outstanding_waves[int(entry["wave"])] = true
	for enemy: Dictionary in enemies.values():
		outstanding_waves[int(enemy["spawn_wave"])] = true
	for completed_wave in _pending_wave_rewards.keys():
		if outstanding_waves.has(completed_wave):
			continue
		var bonus: int = int(_pending_wave_rewards[completed_wave])
		_pending_wave_rewards.erase(completed_wave)
		gold += bonus
		if hero_respawn <= 0.0:
			hero_hp = minf(hero_max_hp,hero_hp+hero_max_hp*0.25)
		_event("wave_cleared", {"wave":completed_wave,"gold":bonus})
	if all_clear and wave >= WAVES.size():
		_end_game(true)

func _end_game(victory: bool) -> void:
	if phase in ["victory","defeat"]:
		return
	phase = "victory" if victory else "defeat"
	paused = false
	_move_input = Vector2.ZERO
	_has_move_target = false
	hero.velocity = Vector3.ZERO
	_visual("effect", [phase,Vector3(13,0,5),5.0])
	_event(phase,{"wave":wave,"kills":kills})
	finished.emit(victory)

func _update_hero_visual() -> void:
	_visual("update_hero", [hero.position,_hero_facing,{"moving":hero.velocity.length()>0.2 and hero_respawn<=0.0,"attack":_hero_attack_flash>0.0,"hurt":_hero_hurt_flash>0.0,"dead":hero_respawn>0.0,"hp_ratio":hero_hp/hero_max_hp,"level":hero_level,"rally":_rally_timer>0.0}])

func _visual(method: String,args: Array) -> void:
	if is_instance_valid(visuals) and visuals.has_method(method):
		visuals.callv(method,args)

func _vector_dict(position: Vector3) -> Dictionary:
	return {"x":position.x,"y":position.y,"z":position.z}

func _emit_state() -> void:
	state_changed.emit(snapshot())

func snapshot() -> Dictionary:
	# New containers and value-only data: reading snapshots cannot mutate simulation.
	var tower_list: Array = []
	for id in towers.keys():
		var tower: Dictionary = towers[id]
		var row: Dictionary = {"id":id,"kind":tower["kind"],"level":tower["level"],"branch":tower["branch"],"spent":tower["spent"],"refund":int(floor(float(tower["spent"])*0.7)),"position":_vector_dict(PADS[id]),"stats":_tower_stats(tower)}
		tower_list.append(row)
	var enemy_list: Array = []
	var boss: Dictionary = {}
	for id in enemies.keys():
		var enemy: Dictionary = enemies[id]
		var row: Dictionary = {"id":id,"kind":enemy["kind"],"lane":enemy["lane"],"position":_vector_dict(enemy["position"]),"hp":enemy["hp"],"max_hp":enemy["max_hp"],"progress":enemy["progress"],"slow":float(enemy["slow_timer"])>0.0,"attacking":enemy["attacking"],"boss_phase":enemy["boss_phase"]}
		enemy_list.append(row)
		if enemy["kind"]=="boss":
			boss = row.duplicate(true)
	var pad_list: Array = []
	for i in range(PADS.size()):
		pad_list.append({"id":i,"position":_vector_dict(PADS[i]),"occupied":towers.has(i)})
	var shop: Array = []
	for key in SHOP_DATA.keys():
		var data: Dictionary = SHOP_DATA[key]
		shop.append({"key":key,"cost":data["cost"],"count":equipment[key],"max_count":data["max_count"],"available":gold>=int(data["cost"]) and int(equipment[key])<int(data["max_count"]) and hero_respawn<=0.0 and (key!="potion" or hero_hp<hero_max_hp)})
	var build_options: Array = []
	for key in TOWER_DATA.keys():
		var data: Dictionary = TOWER_DATA[key]
		build_options.append({"key":key,"cost":data["cost"],"available":gold>=int(data["cost"])})
	var selected: Dictionary = {"pad":selected_pad,"occupied":towers.has(selected_pad),"upgrades":[]}
	if towers.has(selected_pad):
		var tower: Dictionary = towers[selected_pad]
		var data: Dictionary = TOWER_DATA[tower["kind"]]
		selected.merge({"kind":tower["kind"],"level":tower["level"],"branch":tower["branch"],"refund":int(floor(float(tower["spent"])*0.7)),"stats":_tower_stats(tower)})
		for branch in data["branches"]:
			selected["upgrades"].append({"key":branch,"cost":data["upgrade_cost"],"available":int(tower["level"])==1 and gold>=int(data["upgrade_cost"])})
	var preview: Array = []
	if wave<WAVES.size():
		for group in WAVES[wave]:
			preview.append({"kind":group[0],"count":group[1],"lane":group[2]})
	var hero_state: Dictionary = {"position":_vector_dict(hero.position) if is_instance_valid(hero) else {},"hp":hero_hp,"max_hp":hero_max_hp,"level":hero_level,"xp":hero_xp,"xp_next":_xp_next(),"damage":hero_damage,"speed":5.8+float(equipment["boots"])*0.9,"dead":hero_respawn>0.0,"respawn":hero_respawn,"equipment":equipment.duplicate(true),"rally":_rally_timer,"target":_vector_dict(_move_target) if _has_move_target else {},"moving":is_instance_valid(hero) and hero.velocity.length()>0.2}
	return {"version":1,"phase":phase,"mode":phase,"gold":gold,"hp":nexus_hp,"nexus_hp":nexus_hp,"core_hp":nexus_hp,"core_max_hp":20,"max_hp":20,"wave":wave,"waves":WAVES.size(),"total_waves":WAVES.size(),"enemies_left":enemies.size()+spawn_queue.size(),"spawn_remaining":spawn_queue.size(),"kills":kills,"deaths":deaths,"elapsed":elapsed,"paused":paused,"speed":speed,"selected_pad":selected_pad,"selected":selected,"towers":tower_list,"enemies":enemy_list,"pads":pad_list,"hero":hero_state,"shop":shop,"build_options":build_options,"skills":{ "q":{"key":"q","cooldown":skill_cooldowns["q"],"max_cooldown":skill_max_cooldowns["q"]*(1.0-0.08*float(equipment["focus"])),"unlocked":true}, "e":{"key":"e","cooldown":skill_cooldowns["e"],"max_cooldown":skill_max_cooldowns["e"]*(1.0-0.08*float(equipment["focus"])),"unlocked":true}, "r":{"key":"r","cooldown":skill_cooldowns["r"],"max_cooldown":skill_max_cooldowns["r"]*(1.0-0.08*float(equipment["focus"])),"unlocked":hero_level>=3}},"cooldowns":skill_cooldowns.duplicate(true),"cooldown_max":skill_max_cooldowns.duplicate(true),"q_cd":skill_cooldowns["q"],"e_cd":skill_cooldowns["e"],"r_cd":skill_cooldowns["r"],"r_unlocked":hero_level>=3,"boss":boss,"can_start_wave":_can_act() and wave<WAVES.size() and (phase=="build" or _call_available),"early_call":_call_available,"early_bonus":30,"early_calls":_early_calls,"wave_preview":preview,"last_action":_last_action}
