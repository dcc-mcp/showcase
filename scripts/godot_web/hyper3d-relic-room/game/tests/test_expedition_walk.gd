extends "res://tests/test_expedition_course.gd"
# Same course/waypoints/goals. Walk, defend on approach, and approach actual loot.
func walk_to(target: Vector2) -> bool:
	assert(not Input.is_action_pressed("run"), "Walk course never requests Run")
	for index in range(1000):
		var here := Vector2(game.courier.position.x, game.courier.position.z)
		if here.distance_to(target) < 0.20:
			steer(Vector2.ZERO)
			route.append({"target":[target.x,target.y],"actual":[here.x,here.y],"floor":game.courier.is_on_floor()})
			return true
		if game.expedition.zone == "wilderness" and game.pending_action.is_empty() and game._nearest_enemy(2.1) != "":
			var stats: Dictionary = game.expedition.snapshot()
			if "arc_bolt" in stats.unlocked_skills and stats.cooldowns.arc_bolt <= 0.0 and stats.mana >= 6:
				game._on_action("skill"); actions.arc_bolt += 1
			elif stats.cooldowns.melee <= 0.0:
				game._on_action("melee"); actions.melee += 1
		steer((target-here).normalized())
		await physics_frame
		if game.expedition.state != "playing": return false
	push_error("Walk course waypoint blocked: " + str(target))
	return false

func key_event(code: int, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.keycode = code
	event.pressed = pressed
	Input.parse_input_event(event)

func approach_loot() -> void:
	var nearest := ""
	var distance := 3.0
	var drops: Dictionary = game.expedition.snapshot().drops
	for id in drops:
		if drops[id].picked or drops[id].zone != game.expedition.zone or not game.drop_points.has(id): continue
		var reach: float = game._distance(game.drop_points[id])
		if reach < distance:
			nearest = id
			distance = reach
	if nearest == "" or game._near_drop() != "": return
	var before := distance
	var taps := []
	for attempt in range(40):
		if game._near_drop() != "": break
		var target: Vector3 = game.drop_points[nearest]
		var offset := Vector2(target.x-game.courier.position.x, target.z-game.courier.position.z).normalized()
		var directions := {KEY_S:Vector2(1,1).normalized(), KEY_D:Vector2(1,-1).normalized(), KEY_W:Vector2(-1,-1).normalized(), KEY_A:Vector2(-1,1).normalized()}
		var chosen: int = KEY_S
		var best := -2.0
		for code in directions:
			var alignment: float = offset.dot(directions[code])
			if alignment > best:
				best = alignment
				chosen = code
		key_event(chosen, true)
		await frames(3)
		key_event(chosen, false)
		await frames(1)
		taps.append(OS.get_keycode_string(chosen))
	print("LOOT_APPROACH ", JSON.stringify({"drop":nearest,"before":before,"after":game._distance(game.drop_points[nearest]),"key_taps":taps,"scope":"ordinary engine key events; no position or stats writes"}))
	assert(game._near_drop() != "", "Actual loot must be within the unchanged pickup range before E")

func interact() -> void:
	await approach_loot()
	actions.interact += 1
	key_event(KEY_E, true)
	await frames(3)
	key_event(KEY_E, false)
	await frames(2)
