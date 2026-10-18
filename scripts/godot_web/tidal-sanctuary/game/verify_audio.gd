extends SceneTree
## Headless state/guard regression only, not audible playback or browser proof.
## Run after import: godot --headless --path game --script res://verify_audio.gd

const TideAudio = preload("res://tide_audio.gd")
var failures: Array[String] = []
var checks := 0
var receipts: Array[Dictionary] = []

func _initialize() -> void:
	run.call_deferred()

func check(condition: bool, label: String) -> void:
	checks += 1
	if not condition:
		failures.append(label)
		push_error(label)

func capture(receipt: Dictionary) -> void:
	receipts.append(receipt.duplicate(true))

func event_count(event: String) -> int:
	var count := 0
	for receipt in receipts:
		if receipt.event == event:
			count += 1
	return count

func run() -> void:
	var audio = TideAudio.new()
	audio.name = "AudioMaster"
	audio.receipt_emitted.connect(capture)
	root.add_child(audio)
	var state: Dictionary = audio.get_state()
	check(not state.started and state.start_count == 0, "initial logical silence")
	check(not state.music_playing and not state.cue_playing, "no player starts on ready")
	check(state.music_loop, "OGG loop enabled")
	check(is_equal_approx(audio.get_node("Music").stream.get_length(), 32.0),
		"imported music duration is 32 seconds")
	for stage in range(4):
		check(is_equal_approx(TideAudio.CUE_STREAMS[stage].get_length(), TideAudio.CUE_DURATIONS[stage]),
			"imported cue %d has expected duration" % stage)
	check(audio.get_child_count() == 2, "exactly two player nodes")
	check(not audio.play_stage_cue(0), "no cue before Begin")
	check(not audio.start_from_gesture("  "), "empty gesture rejected")
	check(audio.set_muted(true, "load"), "saved mute preference applied")
	state = audio.get_state()
	check(not state.started and not state.music_playing and not state.cue_playing,
		"loading a saved preference cannot start playback")
	check(state.bus_muted, "saved preference mutes shared bus")
	check(audio.start_from_gesture("fixture_begin_muted"), "first muted Begin accepted")
	state = audio.get_state()
	check(state.started and state.start_count == 1 and state.music_playing,
		"muted Begin creates one logical loop")
	check(state.bus_muted, "muted Begin leaves bus silent")
	check(not audio.start_from_gesture("fixture_duplicate"), "second Begin is ignored")
	check(not audio.set_muted(false, "fixture_unmute"), "unmute returns persisted false")
	state = audio.get_state()
	check(not state.bus_muted and state.start_count == 1 and state.music_playing,
		"unmute retains existing loop")
	check(not audio.play_stage_cue(-1) and not audio.play_stage_cue(4), "invalid stages rejected")
	for stage in range(4):
		check(audio.play_stage_cue(stage), "stage %d first cue accepted" % stage)
		check(not audio.play_stage_cue(stage), "stage %d duplicate cue rejected" % stage)
	state = audio.get_state()
	check(state.cue_counts == [1, 1, 1, 1], "one cue per successful stage")
	check(event_count("cue") == 4, "no receipts for blocked or duplicate cues")
	check(audio.get_node("Cue").max_polyphony == 1, "cue playback cannot layer duplicate voices")
	check(audio.get_node("Music").playback_type == AudioServer.PLAYBACK_TYPE_DEFAULT
		and audio.get_node("Cue").playback_type == AudioServer.PLAYBACK_TYPE_DEFAULT,
		"players retain platform default playback mode")
	audio.set_focus_active(false)
	state = audio.get_state()
	check(state.music_paused and state.cue_paused and state.bus_muted, "focus loss pauses both voices")
	audio.set_muted(true, "fixture_hidden_mute")
	audio.set_focus_active(true)
	state = audio.get_state()
	check(not state.music_paused and not state.cue_paused and state.bus_muted,
		"focus return preserves mute preference")
	audio.set_muted(false, "fixture_resume")
	state = audio.get_state()
	check(state.start_count == 1 and not state.bus_muted, "focus/unmute do not restart music")
	var music_stream: AudioStream = audio.get_node("Music").stream
	audio.reset_cues()
	state = audio.get_state()
	check(state.cue_counts == [0, 0, 0, 0] and not state.cue_playing, "restart clears and stops cues")
	check(state.start_count == 1 and state.music_playing, "restart preserves music start")
	check(audio.get_node("Music").stream == music_stream, "restart preserves loop resource")
	music_stream = null
	check(audio.play_stage_cue(0), "restart allows first story cue again")
	check(not audio.play_stage_cue(0), "restart cue is still guarded")
	check(event_count("start") == 1, "exactly one start receipt")
	for receipt in receipts:
		check(receipt.schema == 1 and receipt.has("started") and receipt.has("muted"),
			"receipt has required shared fields")
		if receipt.event == "cue":
			var stage: int = receipt.stage
			check(receipt.name == TideAudio.CUE_NAMES[stage] and receipt.count == 1
				and is_equal_approx(receipt.duration, TideAudio.CUE_DURATIONS[stage]),
				"cue receipt names and durations agree with assets")
	audio.free()
	var restored = TideAudio.new()
	root.add_child(restored)
	restored.set_muted(false, "load")
	restored.set_focus_active(false)
	restored.set_focus_active(true)
	restored.reset_cues()
	state = restored.get_state()
	check(not state.started and state.start_count == 0 and not state.music_playing
		and not state.cue_playing, "fresh load/focus/reset never starts voices")
	check(restored.start_from_gesture("fixture_begin_unmuted"), "first unmuted Begin accepted")
	state = restored.get_state()
	check(state.start_count == 1 and not state.bus_muted, "fresh unmuted loop is enabled")
	await create_timer(TideAudio.FADE_SECONDS + 0.05).timeout
	check(is_equal_approx(restored.get_node("Music").volume_db, TideAudio.MUSIC_VOLUME_DB),
		"music fade reaches quiet target gain")
	restored.free()
	var before_ready = TideAudio.new()
	before_ready.set_muted(true, "load_before_ready")
	check(not before_ready.start_from_gesture("not_in_tree"), "detached node cannot start playback")
	root.add_child(before_ready)
	state = before_ready.get_state()
	check(state.muted and state.bus_muted and not state.started and not state.music_playing,
		"pre-ready saved mute survives readiness without playback")
	before_ready.free()
	# Allow the audio server to release stopped voice resources before tree exit.
	# Fixed-fps CI does not advance the audio mixer wall clock.
	OS.delay_msec(200)
	await process_frame
	print("TIDAL_AUDIO_CHECKS ", JSON.stringify({
		"schema": 1, "status": "passed" if failures.is_empty() else "failed",
		"checks": checks, "failures": failures, "audio_driver": AudioServer.get_driver_name(),
		"scope": "headless state and guard fixture; not audible output evidence",
	}))
	quit(0 if failures.is_empty() else 1)
