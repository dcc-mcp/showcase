extends SceneTree
const Main = preload("res://scripts/main.gd")
var checks := 0

func _init() -> void:
	call_deferred("run")

func run() -> void:
	var game = Main.new()
	root.add_child(game)
	game.save_path = "user://qa-audio-policy.json"
	game._on_action("start")
	game.set_physics_process(false)
	game.courier.set_physics_process(false)
	for index in range(6): game._sound("footstep00")
	var playing: int = game.audio_voices.filter(func(voice): return voice.playing).size()
	if not expect(playing == 1, "Repeated footstep requests use one voice, without re-entry"): return
	if not expect(game.audio_voices[0].volume_db <= -23.0 and game.audio_voices[0].max_polyphony == 1, "Footsteps have bounded gain and polyphony"): return
	if not expect(not game.audio_voices[0].stream.loop, "Footsteps never loop"): return
	for index in range(6): game._sound("chop")
	if not expect(game.audio_voices.size() == 4 and game.audio_voices[0].playing, "Combat cannot steal the dedicated footstep channel"): return
	for voice in game.audio_voices:
		if not expect(voice.max_polyphony == 1 and voice.volume_db <= -16.0, "The finite voice pool retains mix headroom"): return
	game._on_action("pause")
	for voice in game.audio_voices:
		if not expect(not voice.playing and not voice.stream_paused, "Pause cancels one-shots instead of queuing a resume burst"): return
	game._on_action("pause")
	for voice in game.audio_voices:
		if not expect(not voice.playing, "Resume cannot replay canceled sounds"): return
	game.bag_open = true
	game._sync_controls()
	game._sound("metalLatch")
	if not expect(game.audio_voices.any(func(voice): return voice.playing and not voice.stream_paused), "Equipment feedback plays immediately inside the bag"): return
	game._set_state("title")
	for voice in game.audio_voices:
		if not expect(not voice.playing, "Title transition clears all old sounds"): return
	game.queue_free()
	await process_frame
	await process_frame
	print("RELIC_AUDIO_POLICY_PASS ", JSON.stringify({"checks": checks, "scope": "Dummy-audio playback state; no listening claim"}))
	quit(0)

func expect(value: bool, message: String) -> bool:
	checks += 1
	if not value:
		push_error(message)
		quit(1)
	return value
