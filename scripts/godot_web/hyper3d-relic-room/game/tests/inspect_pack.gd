extends SceneTree

func _init() -> void:
	var paths: Array[String] = []
	_inventory("res://", paths)
	var total := 0
	var entries := []
	for path in paths:
		assert(not path.begins_with("res://addons/") and not path.begins_with("res://tests/"), "Release must exclude adapter and QA sources")
		var file := FileAccess.open(path, FileAccess.READ)
		if file:
			var bytes := file.get_length()
			total += bytes
			entries.append({"path": path, "bytes": bytes})
	assert(not ProjectSettings.has_setting("autoload/DccMcpRuntimePeer"))
	assert(FileAccess.file_exists("res://assets/asset-map.json"))
	var data = JSON.parse_string(FileAccess.get_file_as_string("res://data/arpg.json"))
	assert(data is Dictionary and data.schema_version == 1 and data.zones.size() == 2)
	var core = load("res://scripts/expedition.gd").new(data)
	core.start()
	assert(core.snapshot().state == "playing" and core.snapshot().zone == "town" and core.snapshot().enemies.size() == 2)
	for sound in ["creak1", "chop", "handleCoins", "metalLatch", "footstep00", "knifeSlice"]:
		assert(load("res://audio/" + sound + ".ogg") is AudioStream, "Release pack must contain actual licensed SFX")
	for notice in ["res://audio/AUDIO-SOURCES.json", "res://notices/KENNEY-RPG-AUDIO.txt", "res://notices/ASSET-RIGHTS.md", "res://ui/FONT-LICENSE.txt"]:
		assert(FileAccess.file_exists(notice), "Release rights receipt missing: " + notice)
	print("RELIC_PACK_INSPECTION ", JSON.stringify({"engine": Engine.get_version_info().string,
		"physics_3d": ProjectSettings.get_setting("physics/3d/physics_engine", "DEFAULT"),
		"uncompressed_file_bytes": total, "file_count": entries.size(), "files": entries}))
	quit(0)

func _inventory(path: String, output: Array[String]) -> void:
	for name in DirAccess.get_files_at(path):
		output.append(path.path_join(name))
	for name in DirAccess.get_directories_at(path):
		_inventory(path.path_join(name), output)
