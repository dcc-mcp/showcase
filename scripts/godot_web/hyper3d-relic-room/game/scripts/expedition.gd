class_name ArchiveExpedition
extends RefCounted
## Deterministic domain model. Caller owns contact timing, LOS, positions and I/O.

const SAVE_VERSION := 1
const SAVE_KEYS := ["version", "data_fingerprint", "opened_chests", "killed_enemies", "spawned_drop_ids", "picked_drop_ids", "inventory", "equipment", "unlocked_skills", "xp", "level", "quest_complete"]
var state := "title"
var zone := "town"
var health := 0
var max_health := 0
var mana := 0.0
var max_mana := 0.0
var xp := 0
var level := 1
var elapsed := 0.0
var attack_bonus := 0
var quest_complete := false
var _data: Dictionary
var _fingerprint: String
var _enemies: Dictionary = {}
var _drops: Dictionary = {}
var _opened: Dictionary = {}
var _inventory: Dictionary = {}
var _equipment := {"weapon": "", "focus": ""}
var _skills: Array = ["melee"]
var _cooldowns: Dictionary = {}
var _events: Array = []

func _init(definition: Dictionary) -> void:
	_data = definition.duplicate(true)
	assert(int(_data.get("schema_version", 0)) == 1)
	_fingerprint = JSON.stringify(_data, "", true).sha256_text()
	_reset()

func _reset() -> void:
	zone = "town"
	xp = 0
	level = 1
	elapsed = 0.0
	quest_complete = false
	_enemies.clear()
	_drops.clear()
	_opened.clear()
	_inventory.clear()
	_equipment = {"weapon": "", "focus": ""}
	_cooldowns.clear()
	for skill in _data.skills:
		_cooldowns[skill] = 0.0
	for encounter in _data.encounters:
		var spec: Dictionary = _data.enemy_variants[encounter.variant]
		_enemies[encounter.id] = {"variant": encounter.variant, "zone": encounter.zone,
			"health": int(spec.max_health), "max_health": int(spec.max_health), "alive": true, "cooldown": 0.0}
	_rebuild_stats()
	health = max_health
	mana = max_mana
	_events.clear()

func start() -> void:
	_reset()
	state = "playing"
	_emit("started")

func tick(delta: float) -> void:
	if state != "playing" or not is_finite(delta) or delta <= 0.0:
		return
	elapsed += delta
	mana = minf(max_mana, mana + float(_data.player.mana_regen) * delta)
	for key in _cooldowns:
		_cooldowns[key] = maxf(0.0, float(_cooldowns[key]) - delta)
	for enemy in _enemies.values():
		enemy.cooldown = maxf(0.0, float(enemy.cooldown) - delta)

func toggle_pause() -> void:
	if state == "playing" or state == "paused":
		state = "paused" if state == "playing" else "playing"
		_emit("state_changed", {"state": state})

func enter_zone(zone_id: String) -> Dictionary:
	if state != "playing": return _deny("inactive")
	if not _data.zones.has(zone_id): return _deny("unknown_zone")
	if zone == zone_id: return _deny("already_here")
	zone = zone_id
	if bool(_data.zones[zone].safe):
		health = max_health
		mana = max_mana
	_emit("zone_entered", {"zone": zone})
	return {"ok": true, "reason": "", "zone": zone}

func request_player_attack(skill_id: String, target_id: String, distance: float) -> Dictionary:
	# Invoke only at the caller's authored contact/release, after its LOS check.
	if state != "playing": return _deny("inactive")
	if not _data.skills.has(skill_id): return _deny("unknown_skill")
	if skill_id not in _skills: return _deny("skill_locked")
	if not _enemies.has(target_id): return _deny("unknown_enemy")
	var enemy: Dictionary = _enemies[target_id]
	if zone != enemy.zone or bool(_data.zones[zone].safe): return _deny("wrong_zone")
	if not enemy.alive: return _deny("enemy_dead")
	var skill: Dictionary = _data.skills[skill_id]
	if not _within(distance, float(skill.range)): return _deny("out_of_range")
	if float(_cooldowns[skill_id]) > 0.0: return _deny("cooldown")
	if mana < float(skill.mana_cost): return _deny("no_mana")
	mana -= float(skill.mana_cost)
	_cooldowns[skill_id] = float(skill.cooldown)
	var damage := int(skill.damage) + (attack_bonus if bool(skill.uses_attack_bonus) else 0)
	enemy.health = maxi(0, int(enemy.health) - damage)
	_emit("enemy_damaged", {"enemy_id": target_id, "skill_id": skill_id, "damage": damage, "health": enemy.health})
	if int(enemy.health) == 0:
		enemy.alive = false
		var spec: Dictionary = _data.enemy_variants[enemy.variant]
		xp += int(spec.xp)
		_emit("enemy_defeated", {"enemy_id": target_id, "xp": int(spec.xp)})
		_spawn_drop("enemy:" + target_id, String(spec.drop_item), target_id, "enemy", zone)
		if level == 1 and xp >= int(_data.progression.level2_xp):
			level = 2
			var old_max := max_health
			_rebuild_stats()
			health += max_health - old_max
			_emit("level_up", {"level": level})
	return {"ok": true, "reason": "", "damage": damage, "killed": not enemy.alive, "enemy_id": target_id}

func enemy_damage_player(enemy_id: String, distance: float) -> Dictionary:
	if state != "playing": return _deny("inactive")
	if not _enemies.has(enemy_id): return _deny("unknown_enemy")
	var enemy: Dictionary = _enemies[enemy_id]
	if zone != enemy.zone or bool(_data.zones[zone].safe): return _deny("wrong_zone")
	if not enemy.alive: return _deny("enemy_dead")
	var spec: Dictionary = _data.enemy_variants[enemy.variant]
	if not _within(distance, float(spec.attack_range)): return _deny("out_of_range")
	if float(enemy.cooldown) > 0.0: return _deny("cooldown")
	enemy.cooldown = float(spec.cooldown)
	health = maxi(0, health - int(spec.damage))
	_emit("player_damaged", {"enemy_id": enemy_id, "damage": int(spec.damage), "health": health})
	if health == 0:
		state = "lost"
		_emit("state_changed", {"state": state})
	return {"ok": true, "reason": "", "damage": int(spec.damage)}

func open_chest(chest_id: String, distance: float) -> Dictionary:
	if state != "playing": return _deny("inactive")
	if not _data.chests.has(chest_id): return _deny("unknown_chest")
	if _opened.has(chest_id): return _deny("already_open")
	var chest: Dictionary = _data.chests[chest_id]
	if zone != chest.zone: return _deny("wrong_zone")
	if not _within(distance, float(chest.range)): return _deny("out_of_range")
	_opened[chest_id] = true
	var drop_id := "chest:" + chest_id
	_spawn_drop(drop_id, String(chest.drop_item), chest_id, "chest", zone)
	_emit("chest_opened", {"chest_id": chest_id, "drop_id": drop_id})
	return {"ok": true, "reason": "", "drop_id": drop_id}

func _spawn_drop(drop_id: String, item_id: String, source_id: String, source_type: String, drop_zone: String) -> void:
	_drops[drop_id] = {"id": drop_id, "item_id": item_id, "source_id": source_id,
		"source_type": source_type, "zone": drop_zone, "picked": false}
	_emit("drop_spawned", _drops[drop_id].duplicate(true))

func pickup(drop_id: String, distance: float) -> Dictionary:
	if state != "playing": return _deny("inactive")
	if not _drops.has(drop_id): return _deny("unknown_drop")
	var drop: Dictionary = _drops[drop_id]
	if drop.picked: return _deny("already_picked")
	if zone != drop.zone: return _deny("wrong_zone")
	if not _within(distance, float(_data.interaction.pickup_range)): return _deny("out_of_range")
	drop.picked = true
	var already_owned := _inventory.has(drop.item_id)
	_inventory[drop.item_id] = 1
	var event := {"drop_id": drop_id, "item_id": drop.item_id, "already_owned": already_owned}
	_emit("item_picked", event)
	if already_owned: _emit("item_already_owned", event)
	return {"ok": true, "reason": "already_owned" if already_owned else "", "item_id": drop.item_id, "already_owned": already_owned}

func equip(item_id: String) -> Dictionary:
	if state != "playing": return _deny("inactive")
	if not _data.items.has(item_id): return _deny("unknown_item")
	if int(_inventory.get(item_id, 0)) < 1: return _deny("not_owned")
	var slot := String(_data.items[item_id].slot)
	if _equipment[slot] == item_id: return _deny("already_equipped")
	var previous_skills := _skills.duplicate()
	_equipment[slot] = item_id
	_rebuild_stats()
	health = mini(health, max_health)
	mana = minf(mana, max_mana)
	_emit("item_equipped", {"item_id": item_id, "slot": slot})
	for skill in _skills:
		if skill not in previous_skills: _emit("skill_unlocked", {"skill_id": skill})
	return {"ok": true, "reason": "", "slot": slot}

func _rebuild_stats() -> void:
	max_health = int(_data.player.max_health) + (int(_data.progression.level2_health_bonus) if level >= 2 else 0)
	max_mana = float(_data.player.max_mana)
	attack_bonus = int(_data.progression.level2_attack_bonus) if level >= 2 else 0
	_skills = ["melee"]
	for item_id in _equipment.values():
		if item_id == "": continue
		var item: Dictionary = _data.items[item_id]
		max_mana += float(item.max_mana_bonus)
		attack_bonus += int(item.attack_bonus)
		if item.unlocks_skill != "" and item.unlocks_skill not in _skills: _skills.append(item.unlocks_skill)

func _goal_ready() -> bool:
	for enemy_id in _data.goal.enemy_ids:
		if _enemies[enemy_id].alive: return false
	for item_id in _data.goal.equipped_items:
		if item_id not in _equipment.values(): return false
	return "arc_bolt" in _skills

func turn_in(distance: float) -> Dictionary:
	if state != "playing": return _deny("inactive")
	if zone != _data.goal.return_zone: return _deny("wrong_zone")
	if not _within(distance, float(_data.interaction.turn_in_range)): return _deny("out_of_range")
	if not _goal_ready(): return _deny("goal_incomplete")
	quest_complete = true
	state = "won"
	_emit("quest_complete")
	return {"ok": true, "reason": ""}

func snapshot() -> Dictionary:
	return {"state": state, "zone": zone, "health": health, "max_health": max_health,
		"mana": mana, "max_mana": max_mana, "xp": xp, "level": level, "elapsed": elapsed,
		"attack_bonus": attack_bonus, "cooldowns": _cooldowns.duplicate(true), "unlocked_skills": _skills.duplicate(),
		"inventory": _inventory.duplicate(true), "equipment": _equipment.duplicate(true),
		"enemies": _enemies.duplicate(true), "drops": _drops.duplicate(true),
		"opened_chests": _opened.keys(), "killed_enemies": _killed_ids(),
		"goal_ready": _goal_ready(), "quest_complete": quest_complete}

func drain_events() -> Array:
	var result := _events.duplicate(true)
	_events.clear()
	return result

func to_save() -> Dictionary:
	var opened := _opened.keys()
	var spawned := _drops.keys()
	var picked: Array = []
	for key in _drops:
		if _drops[key].picked: picked.append(key)
	opened.sort()
	spawned.sort()
	picked.sort()
	var skills := _skills.duplicate()
	skills.sort()
	return {"version": SAVE_VERSION, "data_fingerprint": _fingerprint, "opened_chests": opened,
		"killed_enemies": _killed_ids(), "spawned_drop_ids": spawned, "picked_drop_ids": picked,
		"inventory": _inventory.duplicate(true), "equipment": _equipment.duplicate(true),
		"unlocked_skills": skills, "xp": xp, "level": level, "quest_complete": quest_complete}

func restore_save(value: Dictionary) -> Dictionary:
	# Invalid data always produces a clean playable town plus a visible-feedback ID.
	start()
	if not _valid_save(value):
		_emit("save_rejected", {"reason": "invalid_save"})
		return _deny("invalid_save")
	for key in value.killed_enemies:
		_enemies[key].health = 0
		_enemies[key].alive = false
		var enemy: Dictionary = _enemies[key]
		_spawn_drop("enemy:" + key, String(_data.enemy_variants[enemy.variant].drop_item), key, "enemy", String(enemy.zone))
	for key in value.opened_chests:
		_opened[key] = true
		var chest: Dictionary = _data.chests[key]
		_spawn_drop("chest:" + key, String(chest.drop_item), key, "chest", String(chest.zone))
	for key in value.picked_drop_ids: _drops[key].picked = true
	_inventory = value.inventory.duplicate(true)
	_equipment = value.equipment.duplicate(true)
	xp = int(value.xp)
	level = int(value.level)
	quest_complete = value.quest_complete
	_rebuild_stats()
	health = max_health
	mana = max_mana
	state = "won" if quest_complete else "playing"
	_events.clear()
	_emit("save_restored")
	return {"ok": true, "reason": ""}

func _valid_save(value: Dictionary) -> bool:
	if not _same_keys(value, SAVE_KEYS): return false
	if not _whole(value.version) or int(value.version) != SAVE_VERSION: return false
	if not value.data_fingerprint is String or value.data_fingerprint != _fingerprint: return false
	if not _known_ids(value.opened_chests, _data.chests.keys()) or not _known_ids(value.killed_enemies, _enemies.keys()): return false
	var expected_drops: Dictionary = {}
	var expected_xp := 0
	for key in value.killed_enemies:
		var variant: Dictionary = _data.enemy_variants[_enemies[key].variant]
		expected_drops["enemy:" + key] = variant.drop_item
		expected_xp += int(variant.xp)
	for key in value.opened_chests: expected_drops["chest:" + key] = _data.chests[key].drop_item
	if not _known_ids(value.spawned_drop_ids, expected_drops.keys()) or value.spawned_drop_ids.size() != expected_drops.size(): return false
	if not _known_ids(value.picked_drop_ids, expected_drops.keys()): return false
	var expected_inventory: Dictionary = {}
	for key in value.picked_drop_ids:
		var item_id: String = expected_drops[key]
		expected_inventory[item_id] = 1
	if not value.inventory is Dictionary or not _same_keys(value.inventory, expected_inventory.keys()): return false
	for key in expected_inventory:
		if not _whole(value.inventory[key]) or int(value.inventory[key]) != expected_inventory[key]: return false
	if not value.equipment is Dictionary or not _same_keys(value.equipment, ["weapon", "focus"]): return false
	var expected_skills: Array = ["melee"]
	for slot in value.equipment:
		var item_id = value.equipment[slot]
		if not item_id is String: return false
		if item_id == "": continue
		if not expected_inventory.has(item_id) or _data.items[item_id].slot != slot: return false
		var skill: String = _data.items[item_id].unlocks_skill
		if skill != "" and skill not in expected_skills: expected_skills.append(skill)
	if not _known_ids(value.unlocked_skills, expected_skills) or value.unlocked_skills.size() != expected_skills.size(): return false
	if not _whole(value.xp) or int(value.xp) != expected_xp or not _whole(value.level): return false
	if int(value.level) != (2 if expected_xp >= int(_data.progression.level2_xp) else 1): return false
	if not value.quest_complete is bool: return false
	if value.quest_complete:
		for key in _data.goal.enemy_ids:
			if key not in value.killed_enemies: return false
		for key in _data.goal.equipped_items:
			if key not in value.equipment.values(): return false
		if "arc_bolt" not in expected_skills: return false
	return true

func _killed_ids() -> Array:
	var result: Array = []
	for key in _enemies:
		if not _enemies[key].alive: result.append(key)
	result.sort()
	return result

func _known_ids(value: Variant, known: Array) -> bool:
	if not value is Array: return false
	var seen: Dictionary = {}
	for key in value:
		if not key is String or key not in known or seen.has(key): return false
		seen[key] = true
	return true

func _same_keys(value: Dictionary, keys: Array) -> bool:
	if value.size() != keys.size(): return false
	for key in value:
		if key not in keys: return false
	return true

func _whole(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT: return false
	return is_finite(float(value)) and float(value) >= 0.0 and float(value) <= 2147483647.0 and float(value) == floorf(float(value))

func _within(distance: float, limit: float) -> bool:
	return is_finite(distance) and distance >= 0.0 and distance <= limit

func _deny(reason: String) -> Dictionary:
	return {"ok": false, "reason": reason}

func _emit(kind: String, values: Dictionary = {}) -> void:
	var event := values.duplicate(true)
	event["type"] = kind
	_events.append(event)
