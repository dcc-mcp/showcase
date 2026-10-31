extends Node
## Small presentation-only audio adapter. It never changes game state.
## The caller invokes unlock_from_gesture() from a real input/button handler.
## `unlocked` records that request; browser AudioContext acceptance is untested.

const MUSIC: AudioStreamOggVorbis = preload("res://assets/experience/audio/field-of-dreams.ogg")
const MUSIC_TRIM_DB := -8.0
const EFFECT_TRIM_DB := -2.0
const SAMPLE_RATE := 22050

var muted := false
var volume := 0.2
var unlocked := false
var _music: AudioStreamPlayer
var _effects: Array[AudioStreamPlayer] = []
var _sounds: Dictionary = {}
var _next_effect := 0


func _ready() -> void:
	_ensure_players()
	_apply_mix()


func unlock_from_gesture() -> void:
	_ensure_players()
	unlocked = true
	_apply_mix()


func play_feedback(kind: String) -> void:
	if not unlocked or muted or volume <= 0.0:
		return
	_ensure_players()
	var cue := kind.to_lower()
	if cue in ["key", "gem", "potion", "loot", "collect"]:
		cue = "pickup"
	elif cue in ["open_door", "unlock", "door_opened"]:
		cue = "door"
	elif cue in ["buy", "shop", "bought", "item_bought"]:
		cue = "purchase"
	elif cue in ["stair", "floor", "up", "down", "ascend", "descend"]:
		cue = "stairs"
	elif cue in ["deny", "failure", "cannot_win"]:
		cue = "blocked"
	elif cue in ["fight", "defeat_enemy", "enemy_cleared"]:
		cue = "combat"
	if not _sounds.has(cue):
		return
	var player: AudioStreamPlayer = _effects[_next_effect % _effects.size()]
	_next_effect += 1
	player.stream = _sounds[cue]
	player.play()


func set_muted(value: bool) -> void:
	muted = value
	_apply_mix()


func set_volume(value: float) -> void:
	volume = clampf(value, 0.0, 1.0)
	_apply_mix()


func _ensure_players() -> void:
	if is_instance_valid(_music):
		return
	_music = AudioStreamPlayer.new()
	_music.name = "ExperienceMusic"
	_music.playback_type = AudioServer.PLAYBACK_TYPE_STREAM
	var music_stream := MUSIC.duplicate() as AudioStreamOggVorbis
	music_stream.loop = true
	_music.stream = music_stream
	add_child(_music)
	for index: int in range(4):
		var player := AudioStreamPlayer.new()
		player.name = "ExperienceFeedback%d" % index
		player.playback_type = AudioServer.PLAYBACK_TYPE_STREAM
		add_child(player)
		_effects.append(player)
	for cue: String in ["pickup", "door", "purchase", "stairs", "blocked", "combat"]:
		_sounds[cue] = _make_feedback(cue)


func _apply_mix() -> void:
	if not is_instance_valid(_music):
		return
	var gain_db := linear_to_db(maxf(volume, 0.0001))
	_music.volume_db = gain_db + MUSIC_TRIM_DB
	_music.stream_paused = muted or volume <= 0.0
	for player: AudioStreamPlayer in _effects:
		player.volume_db = gain_db + EFFECT_TRIM_DB
		if muted or volume <= 0.0:
			player.stop()
	if unlocked and not muted and volume > 0.0 and not _music.playing:
		_music.play()


func _make_feedback(cue: String) -> AudioStreamWAV:
	# Original, bounded cue recipes for this chapter. No borrowed recordings or
	# Dawnkeep's rights-reserved sound generator/results are copied here.
	var frequencies: Array[float] = [880.0, 1320.0]
	var duration := 0.19
	var body := 0.0
	if cue == "door":
		frequencies = [147.0, 220.0]
		duration = 0.27
		body = 0.08
	elif cue == "purchase":
		frequencies = [660.0, 990.0, 1320.0]
		duration = 0.31
	elif cue == "stairs":
		frequencies = [330.0, 440.0, 660.0]
		duration = 0.34
	elif cue == "blocked":
		frequencies = [220.0, 174.0]
		duration = 0.17
	elif cue == "combat":
		frequencies = [196.0, 294.0]
		duration = 0.16
		body = 0.11
	var count := int(duration * SAMPLE_RATE)
	var pcm := PackedByteArray()
	pcm.resize(count * 2)
	for index: int in range(count):
		var time := float(index) / SAMPLE_RATE
		var value := 0.0
		for note: int in range(frequencies.size()):
			var start := float(note) * 0.045
			if time < start:
				continue
			var age := time - start
			var lifetime := duration - start
			var envelope := minf(age / 0.006, 1.0) * pow(maxf(1.0 - age / lifetime, 0.0), 3.0)
			var phase := TAU * frequencies[note] * age
			value += (sin(phase) + 0.12 * sin(phase * 2.0)) * envelope * 0.22 / frequencies.size()
		value += body * sin(TAU * (90.0 * time + 45.0 * time * time)) * exp(-32.0 * time) * minf(time / 0.004, 1.0)
		pcm.encode_s16(index * 2, int(clampf(value, -1.0, 1.0) * 32767.0))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = SAMPLE_RATE
	stream.stereo = false
	stream.data = pcm
	return stream
