extends SceneTree
# Continuous controller motion, never teleporting after initial scene spawn.
const Main = preload("res://scripts/main.gd")
var game: Node3D
var records := []
var minimum_y := 100.0
var maximum_y := -100.0
var floor_frames := 0
var total_frames := 0

func _init() -> void:
	call_deferred("run")

func walk_to(target: Vector2) -> bool:
	var before: Vector3 = game.courier.position
	for index in range(1000):
		var here := Vector2(game.courier.position.x, game.courier.position.z)
		if here.distance_to(target) < 0.18:
			game.courier.touch_axis = Vector2.ZERO
			records.append({"target":[target.x,target.y],"actual":[here.x,here.y],"y":game.courier.position.y,"frames":index,"on_floor":game.courier.is_on_floor()})
			return true
		var direction := (target - here).normalized()
		game.courier.touch_axis = Vector2(direction.x - direction.y, direction.x + direction.y).normalized()
		await physics_frame
		total_frames += 1
		if game.courier.is_on_floor(): floor_frames += 1
		minimum_y = minf(minimum_y, game.courier.position.y)
		maximum_y = maxf(maximum_y, game.courier.position.y)
		if game.expedition.state != "playing": break
	push_error("EXPEDITION_ROUTE_FAILED " + JSON.stringify({"target":[target.x,target.y],"position":str(game.courier.position),"start":str(before)}))
	return false

func run() -> void:
	game = Node3D.new()
	game.name = "RelicCourier"
	game.set_script(Main)
	root.add_child(game)
	game.qa_enabled = true
	game.qa_stage("playing")
	for point in [Vector2(3.3,7),Vector2(3.3,-5),Vector2(0,-6),Vector2(0,-10.6),Vector2(0,-13.7),Vector2(0,-18.7),Vector2(0,-22.5)]:
		if not await walk_to(point): quit(1); return
	assert(game.expedition.zone == "wilderness", "Physical passage reaches wilderness")
	for point in [Vector2(0,-18.7),Vector2(0,-13.7),Vector2(0,-10.6),Vector2(0,-6),Vector2(3.3,-5),Vector2(3.3,7),Vector2(0,11)]:
		if not await walk_to(point): quit(1); return
	assert(game.expedition.zone == "town", "Physical return reaches safe town")
	assert(minimum_y > -0.2, "No falling or hidden recovery along connected route")
	assert(maximum_y > 0.60, "Controller truly climbs raised rear landing")
	assert(float(floor_frames) / total_frames > 0.93, "Ground contact remains reliable on both ramps")
	# Purpose-specific chest clearance: approach and walk around, never through proxy.
	for point in [Vector2(-3,-4.2),Vector2(-5.5,-3.7),Vector2(-7,-4),Vector2(-7,-6.3),Vector2(-4,-6.3)]:
		if not await walk_to(point): quit(1); return
	for point in [Vector2(-9.5,-4.5),Vector2(-11.6,-4.9),Vector2(-11.6,-8.7),Vector2(-11.6,-10),Vector2(-11.6,-4.9)]:
		if not await walk_to(point): quit(1); return
	assert(game.courier.position.y < 0.1, "Stairs descend back to lower wing floor")
	print("RELIC_EXPEDITION_ROUTE_PASS ",JSON.stringify({"scope":"actual engine continuous controller physics, no OS input", "waypoints":records,"min_y":minimum_y,"max_y":maximum_y,"floor_ratio":float(floor_frames)/total_frames,"distance_m":game.courier.motion_distance}))
	for voice in game.audio_voices:
		voice.stop()
		voice.stream = null
	# Allow the native audio mixer to release stopped Ogg playback before fast fixed-fps shutdown.
	OS.delay_msec(75)
	game.queue_free()
	await process_frame
	await process_frame
	quit(0)
