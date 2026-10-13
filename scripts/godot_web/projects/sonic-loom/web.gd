extends "res://loom.gd"
# Web adapter only. The original instrument and PCM synthesis stay in loom.gd.
const WEB_MASTER_GAIN_DB = -6.0
const WEB_PEAK_BUDGET = 0.8
func _ready():
	mobile_layout = "--mobile-layout" in OS.get_cmdline_user_args()
	if mobile_layout:
		get_window().content_scale_size = MOBILE_SIZE
		get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	super._ready()
	# The Web sample path honors bus gain but does not implement bus effects.
	# Leave headroom for three rhythm voices and all four overlapping bell notes.
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Master"), WEB_MASTER_GAIN_DB)
	for p in players + note_players: p.max_polyphony = 1
	if "--web-audio-test" in OS.get_cmdline_user_args():
		get_tree().quit(0 if run_web_audio_tests() else 1)
		return
	web_ready()
	if "--web-layout-test" in OS.get_cmdline_user_args(): web_layout_test()
func _process(delta):
	super._process(delta)
	web_tick(delta)
func web_state():
	return {"case": "sonic-loom", "mobile_layout": mobile_layout, "layout_size": [720,1320] if mobile_layout else [1280,800], "viewport_size": [get_viewport_rect().size.x,get_viewport_rect().size.y], "native_targets": mobile_targets() if mobile_layout else {}, "mobile_lane": mobile_lane, "minimum_text_size": 32 if mobile_layout else 10, "pattern": pattern, "bpm": bpm, "playing": playing, "step": step, "muted": muted, "status": status, "persistent": OS.is_userfs_persistent(), "master_gain_db": AudioServer.get_bus_volume_db(AudioServer.get_bus_index("Master"))}

# Native, deterministic gain regression, separate from the real-browser meter.
# The sum of each playable WAV's absolute peak is a conservative per-channel bound for ANY
# timing/phase alignment, including all 64 cells on at the maximum 160 BPM.
func run_web_audio_tests() -> bool:
	var master = AudioServer.get_bus_index("Master")
	var master_db = AudioServer.get_bus_volume_db(master)
	var checks = []
	checks.append({"name": "Web Master gain", "pass": is_equal_approx(master_db, WEB_MASTER_GAIN_DB), "db": master_db})
	checks.append({"name": "gain-only Master bus", "pass": AudioServer.get_bus_effect_count(master) == 0 and not AudioServer.is_bus_mute(master)})
	# trigger() uses only players[0..2]; GLASS uses four separate note_players.
	var voices = [players[0], players[1], players[2]] + note_players
	var dry_bound = 0.0
	for index in range(voices.size()):
		var p: AudioStreamPlayer = voices[index]
		var wav = p.stream as AudioStreamWAV
		var supported = wav != null and wav.format == AudioStreamWAV.FORMAT_16_BITS and not wav.stereo and wav.loop_mode == AudioStreamWAV.LOOP_DISABLED
		checks.append({"name": "voice %d is mono one-shot PCM" % index, "pass": supported})
		if not supported:
			print(JSON.stringify({"passed": false, "checks": checks}))
			return false
		var pcm = wav.data
		var peak = 0.0
		for offset in range(0, pcm.size(), 2):
			peak = maxf(peak, absf(float(pcm.decode_s16(offset)) / 32767.0))
		var voice_bound = peak * db_to_linear(p.volume_db) * p.max_polyphony
		dry_bound += voice_bound
		checks.append({"name": "voice %d bounded at original level" % index, "pass": peak > 0.01 and peak < 1.0 and p.max_polyphony == 1 and p.mix_target == AudioStreamPlayer.MIX_TARGET_STEREO and p.bus == &"Master" and is_equal_approx(p.volume_db, -5.0 if index < 3 else -8.0), "pcm_peak": peak, "gain_db": p.volume_db, "max_polyphony": p.max_polyphony, "dry_peak_bound": voice_bound})
	var output_bound = dry_bound * db_to_linear(master_db)
	checks.append({"name": "all seven voices retain at least 20 percent peak margin", "pass": voices.size() == 7 and output_bound < WEB_PEAK_BUDGET, "dry_peak_bound": dry_bound, "output_peak_bound": output_bound, "peak_budget": WEB_PEAK_BUDGET})
	var passed = true
	for check in checks: passed = passed and check["pass"]
	print(JSON.stringify({"passed": passed, "verification": "native per-channel PCM triangle bound; not a browser measurement", "checks": checks}))
	return passed
func web_pause():
	if playing: toggle_play()
	for p in players: p.stop()
	for p in note_players: p.stop()
func web_command(args):
	if args.is_empty(): return
	if str(args[0]) in ["layout:mobile", "layout:desktop"]:
		web_layout(str(args[0]) == "layout:mobile")
		return
	var command = str(args[0])
	var parts = command.split(":")
	if parts.size() == 3 and parts[0] == "cell":
		var lane = int(parts[1])
		var index = int(parts[2])
		if lane >= 0 and lane < 4 and index >= 0 and index < 16: toggle_cell(lane, index)
	elif parts.size() == 2 and parts[0] == "mute":
		var lane = int(parts[1])
		if lane >= 0 and lane < 4: muted[lane] = not muted[lane]
	match command:
		"toggle": toggle_play()
		"pause": web_pause()
		"reset": reset_pattern()
		"save":
			if not save_pattern(): status = "SAVE FAILED / STORAGE UNAVAILABLE"
		"load": load_pattern()
		"slower": set_tempo(bpm - 4)
		"faster": set_tempo(bpm + 4)
	web_publish()

var web_callback: JavaScriptObject
var web_elapsed = 0.0
func web_ready():
	if OS.has_feature("web"):
		web_callback = JavaScriptBridge.create_callback(web_command)
		JavaScriptBridge.get_interface("window").showcaseCommand = web_callback
		web_publish()
func web_tick(delta):
	web_elapsed += delta
	if web_elapsed >= 0.1:
		web_elapsed = 0.0
		web_publish()
func web_publish():
	if OS.has_feature("web"):
		JavaScriptBridge.get_interface("window").showcaseReceive(JSON.stringify(web_state()))
func _notification(what):
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		web_pause()

# The compact Web fallback font omits arrow glyphs; keep control hints legible.
func txt(pos: Vector2, value: String, size: int, color: Color = TEXT):
	super.txt(pos, value.replace("↑ ↓", "UP/DN"), size, color)

# IDBFS may fall back to memory when the browser denies persistent storage.
func save_pattern(path: String = "user://sonic-loom.json") -> bool:
	if OS.has_feature("web") and not OS.is_userfs_persistent():
		status = "SAVE FAILED / STORAGE UNAVAILABLE"
		return false
	return super.save_pattern(path)

# Portrait instrument: one voice and all sixteen steps remain readable together.
var mobile_layout = false
var mobile_lane = 0
const MOBILE_SIZE = Vector2i(720, 1320)
func mobile_voice_rect(lane):
	return Rect2(32 + (lane % 2) * 340, 286 + (lane / 2 as int) * 100, 316, 88)
func mobile_cell_rect(index):
	return Rect2(32 + (index % 4) * 168, 616 + (index / 4 as int) * 126, 144, 106)
func mobile_button_rect(command):
	var rects = {"toggle": Rect2(32,158,284,96), "slower": Rect2(344,158,96,96), "faster": Rect2(592,158,96,96), "mute": Rect2(478,488,210,88), "reset": Rect2(32,1144,208,96), "load": Rect2(256,1144,208,96), "save": Rect2(480,1144,208,96)}
	return rects.get(command, Rect2())
func mobile_targets():
	var targets = {}
	for command in ["toggle","slower","faster","mute","reset","load","save"]:
		var r = mobile_button_rect(command)
		targets[command] = [r.position.x,r.position.y,r.size.x,r.size.y]
	for lane in range(4):
		var r = mobile_voice_rect(lane)
		targets["voice:"+str(lane)] = [r.position.x,r.position.y,r.size.x,r.size.y]
	for index in range(16):
		var r = mobile_cell_rect(index)
		targets["cell:"+str(mobile_lane)+":"+str(index)] = [r.position.x,r.position.y,r.size.x,r.size.y]
	return targets
func _unhandled_input(event):
	if not mobile_layout or not event is InputEventMouseButton:
		super._unhandled_input(event)
		return
	if not event.pressed or event.button_index != MOUSE_BUTTON_LEFT: return
	var pos = event.position
	for lane in range(4):
		if mobile_voice_rect(lane).has_point(pos):
			mobile_lane = lane
			queue_redraw()
			web_publish()
			return
	for index in range(16):
		if mobile_cell_rect(index).has_point(pos):
			toggle_cell(mobile_lane,index)
			web_publish()
			return
	for command in ["toggle","slower","faster","mute","reset","load","save"]:
		if mobile_button_rect(command).has_point(pos):
			if command == "mute": muted[mobile_lane] = not muted[mobile_lane]
			else: web_command([command])
			web_publish()
			return
func _draw():
	if not mobile_layout:
		super._draw()
		return
	draw_rect(Rect2(Vector2.ZERO,Vector2(MOBILE_SIZE)),BG)
	txt(Vector2(32,76),"Sonic Loom",56)
	txt(Vector2(32,122),"FOUR VOICES / A MINOR",32,MUTED)
	var play_rect = mobile_button_rect("toggle")
	box(play_rect,AMBER,16)
	txt(play_rect.position+Vector2(30,63),"II  PAUSE" if playing else ">  PLAY",40,BG)
	for command in ["slower","faster"]:
		var r = mobile_button_rect(command)
		box(r,PANEL,16)
		txt(r.position+Vector2(33,62),"-" if command == "slower" else "+",44)
	txt(Vector2(465,213),str(bpm),44)
	txt(Vector2(456,248),"BPM",32,MUTED)
	for lane in range(4):
		var r = mobile_voice_rect(lane)
		box(r,PANEL,14,COLORS[lane] if mobile_lane == lane else Color('#405960'))
		draw_circle(r.position+Vector2(22,43),7,MUTED if muted[lane] else COLORS[lane])
		txt(r.position+Vector2(42,56),NAMES[lane],36)
		var count = 0
		for value in pattern[lane]: count += int(value)
		txt(r.position+Vector2(215,56),"%02d" % count,32,MUTED)
	txt(Vector2(32,543),NAMES[mobile_lane]+" / "+("OFF" if muted[mobile_lane] else "ON"),36,COLORS[mobile_lane])
	var mute_rect = mobile_button_rect("mute")
	box(mute_rect,PANEL,14)
	txt(mute_rect.position+Vector2(26,56),"UNMUTE" if muted[mobile_lane] else "MUTE",32)
	txt(Vector2(32,601),"STEP %02d / 16" % (step+1 if step>=0 else 1),32,AMBER)
	txt(Vector2(390,601),"TAP TO EDIT",32,MUTED)
	for index in range(16):
		var r = mobile_cell_rect(index)
		var active = bool(pattern[mobile_lane][index])
		var color = COLORS[mobile_lane] if active else PANEL
		if muted[mobile_lane] and active: color = color.darkened(0.45)
		box(r,color,14,TEXT if playing and step == index else Color('#405960'))
		txt(r.position+Vector2(14,38),"%02d" % (index+1),32,BG if active else MUTED)
		var mid = r.position+Vector2(96,65)
		if active: draw_circle(mid,12,BG)
		else: draw_circle(mid,4,MUTED)
		if playing and step == index: draw_line(r.position+Vector2(12,94),r.position+Vector2(132,94),TEXT,6)
	for command in ["reset","load","save"]:
		var r = mobile_button_rect(command)
		box(r,PANEL,14)
		txt(r.position+Vector2(32,62),command.to_upper(),36)
	var short_status = "Choose a voice. Tap a step."
	if status == "PATTERN SAVED / LOCAL DEVICE": short_status = "Pattern saved locally."
	elif status == "SAVED PATTERN RESTORED": short_status = "Saved pattern restored."
	elif status == "SAVE FAILED / STORAGE UNAVAILABLE": short_status = "Storage unavailable. Not saved."
	elif status == "NO SAVED PATTERN YET": short_status = "No saved pattern yet."
	txt(Vector2(32,1294),short_status,32,MUTED)

# Browser layout changes preserve the native game/session; only presentation changes.
func web_layout(mobile: bool):
	mobile_layout = mobile
	get_window().content_scale_size = MOBILE_SIZE if mobile else Vector2i(1280, 800)
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_window().content_scale_aspect = Window.CONTENT_SCALE_ASPECT_KEEP
	queue_redraw()
	web_publish()

func web_layout_test():
	var before = JSON.stringify(pattern)
	var checks = []
	for compact in [true, false, true, false]:
		web_layout(compact)
		checks.append(mobile_layout == compact)
		checks.append(get_window().content_scale_size == (MOBILE_SIZE if compact else Vector2i(1280,800)))
		checks.append(JSON.stringify(pattern) == before)
	var passed = checks.all(func(value): return value)
	print("RESPONSIVE_LAYOUT " + JSON.stringify({"passed":passed,"checks":checks.size(),"case":"sonic-loom"}))
	get_tree().quit(0 if passed else 1)
