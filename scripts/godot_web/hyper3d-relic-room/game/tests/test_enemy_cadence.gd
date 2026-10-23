extends SceneTree
const Main = preload("res://scripts/main.gd")
var game: Node3D
func _init() -> void: call_deferred("run")
func frames(count: int) -> void:
	for index in range(count): await physics_frame
func run() -> void:
	game = Node3D.new()
	game.set_script(Main)
	root.add_child(game)
	game.qa_enabled = true
	game.qa_stage("playing")
	game.courier.position = Vector3(-4, -.05, -24.7)
	game.courier.invulnerable = 0.0
	var hit_frames := []
	var previous: int = game.expedition.health
	for index in range(240):
		await physics_frame
		if game.expedition.health < previous:
			hit_frames.append(index)
			previous = game.expedition.health
	assert(hit_frames.size() >= 2, "Two legitimate consecutive enemy attacks land")
	for index in range(1,hit_frames.size()):
		assert((hit_frames[index]-hit_frames[index-1])/60.0 >= 1.25, "Enemy telegraphs respect domain cooldown")
	game.qa_stage("playing")
	game.courier.position = Vector3(-4,-.05,-24.7)
	game.courier.invulnerable = 0.0
	await frames(10)
	assert(game.enemies.scout_1.phase == "attack", "Real authored Attack windup begins")
	game.courier.position = Vector3(-4,-.05,-21.5)
	await frames(32)
	assert(game.expedition.health == 40, "Leaving range before contact causes a real whiff")
	assert(game.enemies.scout_1.attack_gate > 0.0, "Whiff retains bounded attack recovery")
	game.qa_stage("playing")
	game.courier.position = Vector3(-4,-.05,-24.7)
	game.courier.invulnerable = 0.0
	await frames(15)
	game.courier.heading = Vector3.RIGHT
	game.courier.request_dash()
	await frames(16)
	assert(game.expedition.health == 40, "Dash through contact avoids damage without changing authored clip")
	game.qa_stage("playing")
	game.courier.position = Vector3(-4,-.05,-24.7)
	game.courier.invulnerable = 0.0
	game._proxy(Vector3(-4,1.0,-25.35),Vector3(2,2,.20))
	await frames(2)
	game._request_attack("melee")
	await frames(48)
	assert(game.expedition.health==40 and game.expedition.snapshot().enemies.scout_1.health==30,"A real static wall blocks both enemy contact and melee LOS")
	print("RELIC_ENEMY_CADENCE_PASS ",JSON.stringify({"hit_frames":hit_frames,"scope":"native engine staged range/contact/dodge regression, not OS input"}))
	for voice in game.audio_voices:
		voice.stop(); voice.stream = null
	# Allow the native audio mixer to release stopped Ogg playback before fast fixed-fps shutdown.
	OS.delay_msec(75)
	game.queue_free()
	await process_frame
	await process_frame
	quit(0)
