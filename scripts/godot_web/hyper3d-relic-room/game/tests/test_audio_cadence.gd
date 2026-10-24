extends SceneTree
const Cadence = preload("res://scripts/footstep_cadence.gd")
var checks := 0

func _init() -> void:
	var counts: Array[int] = []
	for fps in [30, 60, 120, 144]:
		var cadence = Cadence.new()
		var count := 0
		var last := -10.0
		for frame in range(fps * 10):
			var time := float(frame + 1) / float(fps)
			if cadence.advance(time * 2.2, 1.0 / float(fps), true):
				if not expect(time - last >= Cadence.MIN_INTERVAL - 0.0001, "No rapid repeated contact at %d FPS" % fps): return
				last = time
				count += 1
		counts.append(count)
		if not expect(count >= 30 and count <= 32, "Measured 22m walk produces stride-scale contacts"): return
	if not expect(counts.max() - counts.min() <= 1, "Cadence is stable across normal frame rates"): return
	var stationary = Cadence.new()
	for frame in range(180):
		if not expect(not stationary.advance(0.0, 1.0 / 60.0, true), "No distance means no contact, even when movement requested"): return
	for inactive in ["paused", "airborne", "dash", "action", "idle"]:
		var cadence = Cadence.new()
		cadence.advance(0.6, 0.3, true)
		if not expect(not cadence.advance(10.0, 0.5, false), inactive + " emits no contact"): return
		if not expect(not cadence.advance(10.2, 0.3, true), inactive + " clears partial stride and backlog"): return
	var discontinuity = Cadence.new()
	if not expect(not discontinuity.advance(100.0, 1.0 / 60.0, true), "Teleport cannot create a contact burst"): return
	if not expect(not discontinuity.advance(100.1, 1.0 / 60.0, true), "Teleport does not leave queued contacts"): return
	for fps in [2, 5, 10]:
		var cadence = Cadence.new()
		var count := 0
		for frame in range(fps * 5):
			if cadence.advance(float(frame + 1) * 2.2 / float(fps), 1.0 / float(fps), true): count += 1
		if not expect(count <= fps * 5, "Slow frames emit at most one contact each"): return
	for invalid in [-1.0, 0.0, INF, NAN]:
		if not expect(not Cadence.new().advance(1.0, invalid, true), "Invalid elapsed time cannot sound"): return
	print("RELIC_AUDIO_CADENCE_PASS ", JSON.stringify({"checks": checks, "normal_fps_counts": counts,
		"scope": "Actual cadence code with measured-distance inputs; listening and OS input separate"}))
	quit(0)

func expect(value: bool, message: String) -> bool:
	checks += 1
	if not value:
		push_error(message)
		quit(1)
	return value
