extends SceneTree
# One continuous native controller course. No position writes after the normal spawn.
const Main = preload("res://scripts/main.gd")
var game: Node3D
var route := []
var actions := {"melee":0,"arc_bolt":0,"interact":0,"equip":0}
func _init() -> void: call_deferred("run")
func frames(count: int) -> void:
	for index in range(count): await physics_frame
func steer(direction: Vector2) -> void:
	game.courier.touch_axis = Vector2(direction.x-direction.y,direction.x+direction.y).normalized() if direction.length_squared()>0.001 else Vector2.ZERO
func walk_to(target: Vector2) -> bool:
	for index in range(1000):
		var here := Vector2(game.courier.position.x,game.courier.position.z)
		if here.distance_to(target)<0.20:
			steer(Vector2.ZERO)
			route.append({"target":[target.x,target.y],"actual":[here.x,here.y],"floor":game.courier.is_on_floor()})
			return true
		steer((target-here).normalized())
		await physics_frame
		if game.expedition.state != "playing": return false
	push_error("Course waypoint blocked: "+str(target)+" from "+str(game.courier.position))
	return false
func interact() -> void:
	actions.interact += 1
	Input.action_press("interact")
	await physics_frame
	Input.action_release("interact")
	await physics_frame
func equip(item: String) -> void:
	game._on_action("bag")
	game._on_action("equip:"+item)
	game._on_action("bag")
	actions.equip += 1
func fight(id: String, allow_arc: bool) -> bool:
	for index in range(1600):
		if game.enemies[id].dead:
			steer(Vector2.ZERO)
			return true
		if game.expedition.state != "playing": return false
		var offset: Vector3 = game.enemies[id].position-game.courier.position
		var distance := Vector2(offset.x,offset.z).length()
		steer(Vector2(offset.x,offset.z).normalized() if distance>1.5 else Vector2.ZERO)
		var stats: Dictionary = game.expedition.snapshot()
		if game.pending_action.is_empty():
			if allow_arc and distance<8.3 and stats.cooldowns.arc_bolt<=0.0 and stats.mana>=6:
				game._on_action("skill"); actions.arc_bolt += 1
			elif distance<2.1 and stats.cooldowns.melee<=0.0:
				game._on_action("melee"); actions.melee += 1
		await physics_frame
	return false
func run() -> void:
	game = Node3D.new()
	game.name = "RelicCourier"
	game.set_script(Main)
	root.add_child(game)
	game.qa_enabled = true
	game.save_path = "user://qa-expedition-course.json"
	for suffix in ["", ".bak", ".tmp"]:
		if FileAccess.file_exists(game.save_path+suffix): DirAccess.remove_absolute(ProjectSettings.globalize_path(game.save_path+suffix))
	assert(game._characters_ready(),"Exact final generated actors/chest are required")
	game._on_action("start")
	for point in [Vector2(-3.3,7),Vector2(-3.3,-3.4),Vector2(-5.5,-3.4)]:
		if not await walk_to(point): quit(1); return
	await interact()
	await frames(50)
	assert(game._chest_opened(),"Continuous approach opens the actual chest")
	await interact()
	equip("bronze_edge")
	for point in [Vector2(-3.3,-3.4),Vector2(-3.3,-5.3),Vector2(0,-6),Vector2(0,-10.6),Vector2(0,-13.7),Vector2(0,-18.7),Vector2(0,-22.5),Vector2(-3.3,-24.5)]:
		if not await walk_to(point): quit(1); return
	if not await fight("scout_1",false): push_error("Scout course fight failed"); quit(1); return
	await interact()
	equip("arc_focus")
	assert(game.focus_visual.visible,"Recovered focus is visible on generated courier hand")
	if not await walk_to(Vector2(4,-31.5)): quit(1); return
	if not await fight("sentinel_1",true): push_error("Sentinel course fight failed"); quit(1); return
	await interact()
	assert(game.expedition.snapshot().drops["enemy:sentinel_1"].picked,"Legitimate duplicate blade is cleared without duplicating gear")
	for point in [Vector2(0,-23),Vector2(0,-18.7),Vector2(0,-13.7),Vector2(0,-10.6),Vector2(0,-6),Vector2(3.3,-5),Vector2(3.3,7),Vector2(0,11)]:
		if not await walk_to(point): quit(1); return
	await interact()
	assert(game.expedition.state=="won" and game.expedition.quest_complete,"Full continuous course completes original return goal")
	assert(actions.arc_bolt>0 and game.expedition.snapshot().inventory.bronze_edge==1,"Course used unlocked Arc and retained unique gear")
	var stats: Dictionary = game.qa_snapshot()
	print("RELIC_EXPEDITION_COURSE_PASS ",JSON.stringify({"scope":"continuous native controller + same action handlers, no teleports or OS input", "route":route,"actions":actions,"health":stats.health,"elapsed":stats.elapsed,"distance_m":stats.distance_moved,"inventory":stats.inventory,"equipment":stats.equipment,"opened_chests":stats.opened_chests,"quest_complete":stats.quest_complete}))
	for voice in game.audio_voices:
		voice.stop(); voice.stream = null
	OS.delay_msec(75)
	game.queue_free()
	await process_frame
	await process_frame
	quit(0)
