extends SceneTree
const Main = preload("res://scripts/main.gd")
var game: Node3D
var records := []

func _init() -> void:
	call_deferred("run")

func run() -> void:
	game = Node3D.new()
	game.set_script(Main)
	root.add_child(game)
	game.qa_enabled = true
	for dimensions in [Vector2i(1280, 720), Vector2i(960, 600), Vector2i(1920, 1080), Vector2i(1024, 768)]:
		root.content_scale_size = dimensions
		root.size = dimensions
		await process_frame
		for language in ["en", "zh"]:
			game.ui.locale = language
			for state in ["title", "playing", "paused", "won", "lost", "exhibit", "bag", "touch"]:
				game.ui.touch_visible = state == "touch"
				game.qa_stage("playing" if state in ["bag", "touch"] else state)
				if state == "bag": game._on_action("bag")
				var previous := ""
				var stable := 0
				var sample := {}
				var waited := 0
				for frame in range(16):
					await process_frame
					waited += 1
					sample = game.qa_layout_snapshot()
					var geometry := JSON.stringify(sample.controls)
					stable = stable + 1 if geometry == previous else 0
					previous = geometry
					if stable >= 2:
						break
				assert(stable >= 2, "Layout did not settle")
				assert(sample.viewport_width == dimensions.x and sample.viewport_height == dimensions.y, "Requested logical viewport was not applied")
				var failures := []
				for control in sample.controls:
					if control.type in ["Button", "Label", "PanelContainer"]:
						if control.x < -0.5 or control.y < -0.5 or control.x + control.width > dimensions.x + 0.5 or control.y + control.height > dimensions.y + 0.5:
							failures.append(control.path)
						if control.height + 0.5 < control.minimum_height:
							failures.append(control.path + " minimum height")
				sample["frames_waited"] = waited
				sample["stable_samples"] = stable + 1
				sample["tolerance_pixels"] = 0.5
				sample["failures"] = failures
				records.append(sample)
				if not failures.is_empty():
					print("RELIC_LAYOUT_FAILURE ", JSON.stringify(sample))
					quit(1)
					return
	var output := FileAccess.open("res://tests/layout-results.json", FileAccess.WRITE)
	output.store_string(JSON.stringify({"scope": "headless settled runtime geometry; no pixels or real input", "engine": Engine.get_version_info().string, "cases": records}, "\t"))
	print("RELIC_LAYOUT_TESTS_PASS: %d size/locale/state cases; no button/label/panel outside supported viewport" % records.size())
	game.queue_free()
	quit(0)
