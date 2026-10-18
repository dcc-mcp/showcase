extends Node
## One instance per game. Playback is requested only by the owner's Begin gesture
## and successful story transitions. Receipts describe intent, not audible output.

signal receipt_emitted(receipt: Dictionary)

const BUS_NAME: StringName = &"AudioMaster"
const MUSIC_SOURCE = preload("res://assets/audio/tidekeeper-loop.ogg")
const CUE_STREAMS: Array[AudioStream] = [
	preload("res://assets/audio/chart_read.wav"),
	preload("res://assets/audio/key_pickup.wav"),
	preload("res://assets/audio/pearl_pickup.wav"),
	preload("res://assets/audio/beacon_resolve.wav"),
]
const CUE_NAMES: Array[String] = ["chart_read", "key_pickup", "pearl_pickup", "beacon_resolve"]
const CUE_DURATIONS: Array[float] = [0.72, 1.05, 1.65, 4.8]
const MUSIC_VOLUME_DB := -5.0
const CUE_VOLUME_DB := -3.0
const FADE_SECONDS := 1.5

var _music: AudioStreamPlayer
var _cue: AudioStreamPlayer
var _fade: Tween
var _created_bus := false
var _started := false
var _muted := false
var _focus_active := true
var _start_count := 0
var _cue_counts: Array[int] = [0, 0, 0, 0]

func _ready() -> void:
	_ensure_players()

func _exit_tree() -> void:
	if is_instance_valid(_fade):
		_fade.kill()
		_fade = null
	if is_instance_valid(_music):
		_music.stop()
	if is_instance_valid(_cue):
		_cue.stop()
	# Native Ogg voices retire on the mixer wall clock, including normal quit.
	# The Web sample graph uses its existing asynchronous normal-exit path.
	if _started and not OS.has_feature("web"):
		OS.delay_msec(200)
	if _created_bus:
		var bus_index := AudioServer.get_bus_index(BUS_NAME)
		if bus_index >= 0:
			AudioServer.remove_bus(bus_index)

func _ensure_players() -> void:
	if is_instance_valid(_music):
		return
	var bus_index := AudioServer.get_bus_index(BUS_NAME)
	if bus_index < 0:
		# Godot 4.6.3 Web add_bus(-1) can reorder Sample buses and detach Master.
		# Growing the count appends through set_sample_bus_count without moving it.
		bus_index = AudioServer.bus_count
		AudioServer.bus_count = bus_index + 1
		AudioServer.set_bus_name(bus_index, BUS_NAME)
		AudioServer.set_bus_send(bus_index, &"Master")
		_created_bus = true
	AudioServer.set_bus_mute(bus_index, _muted or not _focus_active)
	_music = AudioStreamPlayer.new()
	_music.name = "Music"
	_music.bus = BUS_NAME
	_music.autoplay = false
	_music.max_polyphony = 1
	_music.playback_type = AudioServer.PLAYBACK_TYPE_DEFAULT
	var loop_stream := MUSIC_SOURCE.duplicate() as AudioStreamOggVorbis
	loop_stream.loop = true
	loop_stream.loop_offset = 0.0
	_music.stream = loop_stream
	_music.volume_db = -40.0
	add_child(_music)
	_cue = AudioStreamPlayer.new()
	_cue.name = "Cue"
	_cue.bus = BUS_NAME
	_cue.autoplay = false
	_cue.max_polyphony = 1
	_cue.playback_type = AudioServer.PLAYBACK_TYPE_DEFAULT
	_cue.volume_db = CUE_VOLUME_DB
	add_child(_cue)

## Call directly from a real Begin click, key, or touch; never from load/demo.
## A muted Begin is still the sole logical start. Unmute does not restart it.
func start_from_gesture(trigger: String) -> bool:
	if _started or trigger.strip_edges().is_empty() or not is_inside_tree():
		return false
	_ensure_players()
	_started = true
	_start_count += 1
	_music.play()
	_music.stream_paused = not _focus_active
	_fade = create_tween()
	_fade.tween_property(_music, "volume_db", MUSIC_VOLUME_DB, FADE_SECONDS)
	if not _focus_active:
		_fade.pause()
	_emit_receipt("start", {"trigger": trigger, "start_count": _start_count})
	return true

## The caller must have already committed a successful stage transition.
## The single cue voice replaces an unfinished cue during very fast progress.
func play_stage_cue(previous_stage: int) -> bool:
	if not _started or previous_stage < 0 or previous_stage >= CUE_STREAMS.size():
		return false
	if _cue_counts[previous_stage] != 0:
		return false
	_ensure_players()
	_cue_counts[previous_stage] = 1
	_cue.stream = CUE_STREAMS[previous_stage]
	_cue.play()
	_cue.stream_paused = not _focus_active
	_emit_receipt("cue", {
		"stage": previous_stage,
		"name": CUE_NAMES[previous_stage],
		"duration": CUE_DURATIONS[previous_stage],
		"count": _cue_counts[previous_stage],
	})
	return true

## The owner persists the returned preference. Loading it never starts a voice.
func set_muted(value: bool, trigger: String = "button") -> bool:
	_ensure_players()
	var changed := _muted != value
	_muted = value
	_apply_bus_mute()
	if changed:
		_emit_receipt("mute", {"trigger": trigger})
	return _muted

func set_focus_active(value: bool) -> void:
	if _focus_active == value:
		return
	_ensure_players()
	_focus_active = value
	_apply_bus_mute()
	_music.stream_paused = not value
	_cue.stream_paused = not value
	if is_instance_valid(_fade) and _fade.is_valid():
		if value:
			_fade.play()
		else:
			_fade.pause()
	_emit_receipt("focus", {"trigger": "focus_in" if value else "focus_out", "active": value})

## A real journey restart may permit cues again, but keeps the original loop.
func reset_cues() -> void:
	_cue_counts = [0, 0, 0, 0]
	if is_instance_valid(_cue):
		_cue.stop()

func _apply_bus_mute() -> void:
	var bus_index := AudioServer.get_bus_index(BUS_NAME)
	if bus_index >= 0:
		AudioServer.set_bus_mute(bus_index, _muted or not _focus_active)

func get_state() -> Dictionary:
	_ensure_players()
	return {
		"started": _started,
		"muted": _muted,
		"focus_active": _focus_active,
		"start_count": _start_count,
		"cue_counts": _cue_counts.duplicate(),
		"music_playing": _music.playing,
		"cue_playing": _cue.playing,
		"music_paused": _music.stream_paused,
		"cue_paused": _cue.stream_paused,
		"music_position": _music.get_playback_position(),
		"bus_muted": AudioServer.is_bus_mute(AudioServer.get_bus_index(BUS_NAME)),
		"music_loop": (_music.stream as AudioStreamOggVorbis).loop,
	}

func _emit_receipt(event: String, details: Dictionary) -> void:
	var receipt := {
		"schema": 1,
		"event": event,
		"started": _started,
		"muted": _muted,
		"focus_active": _focus_active,
		"voice_intent": "paused" if not _focus_active else (
			"muted" if _muted else ("music" if _started else "silent")),
	}
	receipt.merge(details)
	if event == "cue" and _focus_active and not _muted:
		receipt["voice_intent"] = "music_and_cue"
	print("TIDAL_AUDIO ", JSON.stringify(receipt))
	receipt_emitted.emit(receipt)
