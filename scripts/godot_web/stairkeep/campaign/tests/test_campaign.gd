extends SceneTree

const Campaign = preload("res://scripts/campaign_rules.gd")
const Variants = preload("res://scripts/campaign_variant.gd")
const Storage = preload("res://scripts/campaign_save_v2.gd")
var checks: Array = []
var failures: Array = []


func _initialize() -> void:
	_test_variants()
	_test_death_and_sequence()
	_test_snapshots_and_native_storage()
	_test_navigation_loss()
	_test_production_content()
	print(JSON.stringify({"suite": "campaign_lifecycle_v2", "checks": checks, "failures": failures, "passed": failures.is_empty(), "scope": "Instrumented headless rule, transform and native-file checks. No GUI/Web persistence or human-duration acceptance."}))
	quit(0 if failures.is_empty() else 1)


func _check(name: String, passed: bool, observed: Variant = null) -> void:
	checks.append({"name": name, "passed": passed, "observed": observed})
	if not passed:
		failures.append(name)
		push_error(name + ": " + str(observed))


func _fixture(exhausted: bool = false) -> Dictionary:
	var canonical: Dictionary = {"schema_version": 1, "content_id": Campaign.CONTENT_ID, "title": "Lifecycle fixture", "initial_player": {"hp": 50, "atk": 10, "def": 2, "gold": 30, "keys": {"yellow": 0, "blue": 0}}, "enemies": {"mite": {"name": "Mite", "hp": 10, "atk": 3, "def": 0, "gold": 8}, "lethal": {"name": "Lethal", "hp": 200, "atk": 70, "def": 0, "gold": 0}, "armor": {"name": "Armor", "hp": 100, "atk": 8, "def": 99, "gold": 0}}, "shops": {"forge": {"name": "Forge", "offers": [{"id": "edge", "label": "Edge", "cost": 10, "kind": "atk", "amount": 2, "limit": 1}, {"id": "flask", "label": "Flask", "cost": 20, "kind": "potion", "amount": 30, "limit": 1}]}}, "floors": []}
	for floor_id: int in range(1, 22):
		var width: int = 11 if floor_id == 2 else 9
		var height: int = 13 if floor_id == 2 else 9
		var grid: Array = []
		for y: int in range(height):
			grid.append("#".repeat(width) if y == 0 or y == height - 1 else "#" + ".".repeat(width - 2) + "#")
		var floor_item: Dictionary = {"id": floor_id, "name": "Floor %d" % floor_id, "grid": grid, "spawn": [1, height - 2], "objects": []}
		if floor_id > 1:
			var previous_width: int = 11 if floor_id == 3 else 9
			floor_item["objects"].append({"id": "f%02d_down" % floor_id, "kind": "stairs", "pos": [1, height - 2], "direction": "down", "target": {"floor": floor_id - 1, "pos": [previous_width - 2, 1], "object_id": "f%02d_up" % (floor_id - 1)}})
		if floor_id < 21:
			var next_height: int = 13 if floor_id == 1 else 9
			floor_item["objects"].append({"id": "f%02d_up" % floor_id, "kind": "stairs", "pos": [width - 2, 1], "direction": "up", "target": {"floor": floor_id + 1, "pos": [1, next_height - 2], "object_id": "f%02d_down" % (floor_id + 1)}})
		if floor_id == 1:
			floor_item["safe_start_candidates"] = [[2, 6], [3, 6], [1, 7], [3, 7]]
			floor_item["objects"].append({"id": "lethal", "kind": "enemy", "type": "lethal", "pos": [7, 2]})
			floor_item["objects"].append({"id": "armor", "kind": "enemy", "type": "armor", "pos": [6, 3]})
			if not exhausted:
				floor_item["objects"].append_array([{"id": "key", "kind": "key", "type": "yellow", "amount": 1, "pos": [2, 7]}, {"id": "door", "kind": "door", "type": "yellow", "pos": [4, 7]}, {"id": "mite", "kind": "enemy", "type": "mite", "pos": [5, 5]}, {"id": "gold", "kind": "gold", "amount": 3, "pos": [3, 5]}, {"id": "shop", "kind": "shop", "type": "forge", "pos": [4, 5]}])
		if floor_id == 21:
			floor_item["objects"].append({"id": "final", "kind": "enemy", "type": "armor" if exhausted else "mite", "victory": true, "pos": [width - 2, 1]})
		canonical["floors"].append(floor_item)
	return canonical


func _game(seed: Variant = 1, exhausted: bool = false) -> RefCounted:
	var game = Campaign.new()
	var result: Dictionary = game.start_campaign(_fixture(exhausted), seed)
	_check("fixture initializes seed " + str(seed) + (" exhausted" if exhausted else ""), bool(result.get("ok", false)), result.get("message", ""))
	return game


func _test_variants() -> void:
	var canonical: Dictionary = _fixture()
	var before: String = Variants.content_hash(canonical)
	var vectors: Array = [
		{"seed": 1, "head": ["00042021", "04080601", "9dcca8c5", "1255994f", "8ef917d1", "2c6f5bd0"], "draw43": "48213943", "next": "00042021"},
		{"seed": 20261025, "head": ["200a0c91", "529b97fd", "2ce0de2f", "d381921d", "d98a1d7c", "de9fddae"], "draw43": "e6af7b5f", "next": "200a0c91"},
		{"seed": 0, "head": ["40aec71f", "91e00c19", "9c0fe128", "6570f69d", "0fce02cc", "3d6b45e7"], "draw43": "12790098", "next": "40aec71f"}]
	for vector: Dictionary in vectors:
		var generated: Dictionary = Variants.generate(canonical, vector["seed"])
		_check("golden variant generates " + str(vector["seed"]), bool(generated["ok"]), generated.get("message", ""))
		if not bool(generated["ok"]):
			continue
		var head: Array = []
		for index: int in range(6):
			head.append("%08x" % int(generated["draws"][index]))
		_check("exact first six PRNG outputs " + str(vector["seed"]), head == vector["head"], head)
		_check("exact 43rd PRNG output " + str(vector["seed"]), "%08x" % int(generated["draws"][42]) == vector["draw43"] and int(generated["draw_count"]) == 43)
		_check("sequence uses first draw only " + str(vector["seed"]), "%08x" % Variants.next32(str(generated["seed"]).hex_to_int()) == vector["next"])
		var index: int = int(generated["draws"][42]) % 4
		var mirror: Dictionary = generated["mirrors"]["1"]
		var expected: Array = Variants.transform_cell(canonical["floors"][0]["safe_start_candidates"][index], 9, 9, mirror["h"], mirror["v"])
		_check("43rd draw selects canonical then transformed safe spawn " + str(vector["seed"]), generated["resolved_start"] == expected and generated["data"]["floors"][0]["spawn"] == expected)
		var same: Dictionary = Variants.generate(canonical, generated["seed"])
		_check("same seed exact transformed hash " + str(vector["seed"]), same["transformed_sha256"] == generated["transformed_sha256"])
		_check("source remains immutable " + str(vector["seed"]), Variants.content_hash(canonical) == before)
	_check("zero seed normalization", Variants.normalize_seed(0) == "6d2b79f5")
	_check("bad seed rejected", Variants.normalize_seed(-1).is_empty() and Variants.normalize_seed("zzzzzzzz").is_empty())
	var original: Array = [2, 3]
	for flags: Array in [[false, false], [true, false], [false, true], [true, true]]:
		var once: Array = Variants.transform_cell(original, 11, 13, flags[0], flags[1])
		_check("reflection involution " + str(flags), Variants.transform_cell(once, 11, 13, flags[0], flags[1]) == original)
	_check("different-size destination example", Variants.transform_cell([1, 7], 11, 13, false, true) == [1, 5])
	var generated: Dictionary = Variants.generate(canonical, 1)
	if bool(generated["ok"]):
		var first_up: Dictionary = _find(generated["data"], "f01_up")
		_check("stairs target uses destination dimensions and mirror", first_up["pos"] == [1, 7] and first_up["target"]["pos"] == [9, 1], first_up)
		var graph_matches: bool = true
		for floor_item: Dictionary in canonical["floors"]:
			var id: int = int(floor_item["id"])
			var mirrored: Dictionary = generated["data"]["floors"][id - 1]
			var flags: Dictionary = generated["mirrors"][str(id)]
			for y: int in range(floor_item["grid"].size()):
				for x: int in range(str(floor_item["grid"][y]).length()):
					var target: Array = Variants.transform_cell([x, y], str(floor_item["grid"][0]).length(), floor_item["grid"].size(), flags["h"], flags["v"])
					graph_matches = graph_matches and str(floor_item["grid"][y])[x] == str(mirrored["grid"][target[1]])[target[0]]
		_check("all 21 transformed grid graphs preserve cells", graph_matches)
		_check("enemy/shop catalogs and object resources conserved", Variants.content_hash(canonical["enemies"]) == Variants.content_hash(generated["data"]["enemies"]) and Variants.content_hash(canonical["shops"]) == Variants.content_hash(generated["data"]["shops"]))
	var bad: Dictionary = canonical.duplicate(true)
	bad["floors"][0]["safe_start_candidates"] = [[7, 2]]
	_check("occupied unsafe spawn rejected", not Variants.generate(bad, 1)["ok"])
	bad = canonical.duplicate(true)
	bad["floors"][0]["objects"][0]["target"]["pos"] = [0, 0]
	_check("broken stair target rejected", not Variants.generate(bad, 1)["ok"])


func _test_death_and_sequence() -> void:
	var game = _game()
	var initial: Dictionary = game.campaign_snapshot()
	var copy: Dictionary = game.state
	copy["hp"] = 99999
	_check("state getter cannot mutate authoritative resources", game.state["hp"] == 50)
	var lethal: Dictionary = _find(game.data, "lethal")
	_check("actual safe navigation to lethal encounter", _approach(game, lethal["pos"]))
	var before: Dictionary = game.campaign_snapshot()
	var normal: Dictionary = game.interact(lethal["pos"])
	_check("ordinary lethal move remains rejected and alive", not normal["ok"] and not game.is_failed() and game.campaign_snapshot() == before)
	var preview: Dictionary = game.inspect(lethal["pos"])["combat"]
	var pending: Dictionary = game.challenge_enemy(lethal["pos"], false)
	_check("unsafe challenge needs explicit confirmation", not pending["ok"] and pending["action"] == "confirmation_required" and game.campaign_snapshot() == before)
	var death: Dictionary = game.challenge_enemy(lethal["pos"], true)
	_check("confirmed terminal HP equals same preview", death["ok"] and death["failure_reason"] == "combat_death" and int(death["terminal_hp"]) == int(before["core_state"]["hp"]) - int(preview["damage"]) and int(death["terminal_hp"]) <= 0)
	_check("death does not fabricate positive-core combat rewards", game.state == before["core_state"] and not game.state["cleared"].has("lethal") and int(game.state["hp"]) == 50)
	var lost: Dictionary = game.campaign_snapshot()
	var restored_loss = game.clone_for_search()
	_check("actual combat loss snapshot validates", restored_loss.restore_snapshot(lost))
	var forged_death: Dictionary = lost.duplicate(true)
	forged_death["last_failure_event"]["object_id"] = "final"
	_check("remote enemy cannot fabricate death evidence", not restored_loss.restore_snapshot(forged_death))
	game.challenge_enemy(lethal["pos"], true)
	game.assess_failure()
	_check("repeated failure presentation counts once and never advances", game.campaign_snapshot() == lost and death["failure_count"] == 1)
	_check("failed campaign ordinary actions are frozen", not game.move(1, 0)["ok"] and game.campaign_snapshot() == lost)
	_check("unconfirmed new variant preserves sequence", not game.respawn_new_variant(false, death["failure_event_id"])["ok"] and game.campaign_snapshot() == lost)
	_check("wrong loss ID preserves sequence", not game.respawn_new_variant(true, "a".repeat(64))["ok"] and game.campaign_snapshot() == lost)
	var reborn: Dictionary = game.respawn_new_variant(true, death["failure_event_id"])
	_check("confirmed loss advances exactly once", reborn["ok"] and reborn["campaign_seed"] == "00042021" and reborn["attempt_index"] == 1 and not game.is_failed())
	var after: Dictionary = game.campaign_snapshot()
	_check("duplicate respawn token cannot advance again", not game.respawn_new_variant(true, death["failure_event_id"])["ok"] and game.campaign_snapshot() == after)
	game.restart_same_seed()
	var restarted: Dictionary = game.campaign_snapshot()
	_check("same-seed restart keeps sequence and exact initial world", restarted["campaign_seed"] == after["campaign_seed"] and restarted["sequence_state"] == after["sequence_state"] and restarted["attempt_index"] == 1 and restarted["core_state"] == after["core_state"] and restarted["transformed_content_sha256"] == after["transformed_content_sha256"])
	var original_seed = _game()
	lethal = _find(original_seed.data, "lethal")
	_approach(original_seed, lethal["pos"])
	var first_death: Dictionary = original_seed.challenge_enemy(lethal["pos"], true)
	original_seed.restart_same_seed()
	_approach(original_seed, lethal["pos"])
	var same_death: Dictionary = original_seed.challenge_enemy(lethal["pos"], true)
	_check("same-seed identical failure ID is counted only once", first_death["failure_event_id"] == same_death["failure_event_id"] and same_death["failure_count"] == 1)
	_check("original initial state was not changed through source sharing", initial["core_state"]["hp"] == 50)


func _test_snapshots_and_native_storage() -> void:
	var game = _game(20261025)
	_check("shared campaign content is recursively read-only", _readonly_tree(game.data))
	var key: Dictionary = _find(game.data, "key")
	_check("real move collects key in mirrored map", _walk_to(game, key["pos"]) and game.state["keys"]["yellow"] == 1)
	var good: Dictionary = game.campaign_snapshot()
	var clone = game.clone_for_search()
	_check("search clone shares only recursively read-only content", _readonly_tree(clone.data) and Variants.content_hash(clone.data) == str(good["transformed_content_sha256"]))
	var nested: Dictionary = clone.campaign_snapshot()
	nested["core_state"]["keys"]["yellow"] = 0
	_check("nested snapshot does not pollute source", game.state["keys"]["yellow"] == 1)
	_check("same binding restores complete snapshot", clone.restore_snapshot(good) and Variants.content_hash(clone.campaign_snapshot()) == Variants.content_hash(good))
	var bad: Dictionary = good.duplicate(true)
	bad["floor_mirrors"]["2"]["h"] = not bad["floor_mirrors"]["2"]["h"]
	_check("tampered mirror rejected without partial mutation", not clone.restore_snapshot(bad) and Variants.content_hash(clone.campaign_snapshot()) == Variants.content_hash(good))
	bad = good.duplicate(true)
	bad["core_state"]["hp"] = 2000000000
	_check("content resource upper bound enforced", not clone.restore_snapshot(bad) and Variants.content_hash(clone.campaign_snapshot()) == Variants.content_hash(good))
	bad = good.duplicate(true)
	bad["rules_sha256"] = "f".repeat(64)
	_check("rule hash mismatch rejected", not clone.restore_snapshot(bad))
	bad = good.duplicate(true)
	bad["consumed_loss_ids"] = ["a".repeat(64)]
	bad["failure_events_seen"] = ["a".repeat(64)]
	_check("consumed-loss count must equal sequence index", not clone.restore_snapshot(bad))
	bad = good.duplicate(true)
	bad["failed"] = true
	bad["failure_reason"] = "resource_exhausted"
	bad["failure_event_id"] = Variants.content_hash({"content": bad["canonical_content_sha256"], "rules": bad["rules_sha256"], "variant": bad["transformed_content_sha256"], "seed": bad["campaign_seed"], "attempt": bad["attempt_index"], "decision_hash": bad["decision_log_hash"], "reason": "resource_exhausted", "state": bad["core_state"]})
	bad["failure_events_seen"] = [bad["failure_event_id"]]
	bad["last_failure_event"] = {"reason": "resource_exhausted", "event_id": bad["failure_event_id"], "core_state": bad["core_state"].duplicate(true), "frontier": {"complete": true, "options": []}}
	_check("claimed resource failure must survive actual new frontier", not clone.restore_snapshot(bad) and not clone.is_failed())
	bad = good.duplicate(true)
	bad["attempt_index"] = 1
	bad["campaign_seed"] = "%08x" % Variants.next32(str(good["root_seed"]).hex_to_int())
	bad["sequence_state"] = bad["campaign_seed"]
	_check("sequence cannot advance without confirmed loss history", not clone.restore_snapshot(bad))
	_check("nested-history negative fixture has an entry checkpoint", not good["checkpoints"].is_empty())
	if not good["checkpoints"].is_empty():
		for malformed: Dictionary in [{"label": "integer", "value": 1}, {"label": "null", "value": null}, {"label": "dictionary", "value": {}}]:
			bad = good.duplicate(true)
			bad["checkpoints"][0]["checkpoints"] = malformed["value"]
			var before_rejection: String = Variants.canonical_json(clone.campaign_snapshot())
			var rejected: bool = not clone.restore_snapshot(bad)
			_check("nested checkpoint %s history is rejected without mutation" % malformed["label"], rejected and Variants.canonical_json(clone.campaign_snapshot()) == before_rejection)
	var path: String = "user://campaign-lifecycle-v2-test.json"
	_check("native Save v2 writes atomically", game.save_v2(path)["ok"])
	var first_bytes: String = FileAccess.get_file_as_string(path)
	game.restart_same_seed()
	_check("native full load restores state and nested keys", game.load_v2(path)["ok"] and Variants.content_hash(game.campaign_snapshot()) == Variants.content_hash(good))
	var gold: Dictionary = _find(game.data, "gold")
	_walk_to(game, gold["pos"])
	_check("native atomic replacement supports an existing slot", game.save_v2(path)["ok"] and FileAccess.get_file_as_string(path) != first_bytes)
	var second_bytes: String = FileAccess.get_file_as_string(path)
	var legacy_path: String = "user://campaign-legacy-v1-test.json"
	_write(legacy_path, "{\"schema_version\":1,\"state\":{\"hp\":1}}")
	var active: String = Variants.content_hash(game.campaign_snapshot())
	var legacy: Dictionary = game.load_v2(legacy_path)
	_check("v1 is rejected and its bytes preserved", not legacy["ok"] and legacy["status"] == "legacy_v1" and FileAccess.get_file_as_string(legacy_path) == "{\"schema_version\":1,\"state\":{\"hp\":1}}" and Variants.content_hash(game.campaign_snapshot()) == active)
	var corrupt_path: String = "user://campaign-invalid-v2-test.json"
	_write(corrupt_path, "{partial")
	_check("corrupt load preserves active state and good slot", not game.load_v2(corrupt_path)["ok"] and Variants.content_hash(game.campaign_snapshot()) == active and FileAccess.get_file_as_string(path) == second_bytes)
	var failed_write: Dictionary = Storage.write_atomic("user://does-not-exist-campaign-test/save.json", second_bytes)
	_check("failed pending write does not change existing good slot", not failed_write["ok"] and FileAccess.get_file_as_string(path) == second_bytes)
	# Reach multiple chapter entries, then restore the first timeline and save again.
	game.restart_same_seed()
	for floor_id: int in range(1, 7):
		var up: Dictionary = _find(game.data, "f%02d_up" % floor_id)
		if not _walk_to(game, up["pos"]):
			_check("checkpoint navigation floor %d" % floor_id, false)
			break
	var checkpoints: Array = game.campaign_snapshot()["checkpoints"]
	_check("entry snapshots are complete and bounded", checkpoints.size() == 3)
	var first_checkpoint: String = str(checkpoints[0]["checkpoint_id"]) if not checkpoints.is_empty() else ""
	_check("early checkpoint restores whole timeline", game.restore_checkpoint(first_checkpoint) and game.state["floor"] == 0 and game.campaign_snapshot()["checkpoints"].size() == 1)
	_check("restored early checkpoint remains saveable", game.save_v2(path)["ok"])
	# Persist an actual death, reload, and verify the very next sequence element.
	var lethal: Dictionary = _find(game.data, "lethal")
	_approach(game, lethal["pos"])
	var death: Dictionary = game.challenge_enemy(lethal["pos"], true)
	_check("terminal Save v2 stores truthful loss metadata", game.save_v2(path)["ok"])
	game.restart_same_seed()
	_check("load restores failure and matching terminal HP", game.load_v2(path)["ok"] and game.is_failed() and game.campaign_snapshot()["terminal_hp"] == death["terminal_hp"])
	var next: Dictionary = game.respawn_new_variant(true, death["failure_event_id"])
	_check("load then respawn preserves exact sequence", next["ok"] and next["campaign_seed"] == "200a0c91" and next["attempt_index"] == 1)
	for file_path: String in [path, legacy_path, corrupt_path]:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(file_path))


func _test_navigation_loss() -> void:
	var active = _game(1)
	var before: Dictionary = active.campaign_snapshot()
	var bounded: Dictionary = active.assess_failure(1)
	_check("navigation budget exhaustion is unknown not loss", bounded["action"] == "unknown" and not active.is_failed() and active.campaign_snapshot() == before)
	var available: Dictionary = active.assess_failure()
	_check("reachable actions keep campaign active", available["action"] == "actions_available" and not active.is_failed())
	var exhausted = _game(1, true)
	var loss: Dictionary = exhausted.assess_failure()
	_check("complete 21-floor BFS proves resource exhaustion", loss["ok"] and loss["failure_reason"] == "resource_exhausted" and exhausted.is_failed() and loss["terminal_hp"] == null)
	var lost: Dictionary = exhausted.campaign_snapshot()
	exhausted.assess_failure()
	_check("repeated resource loss counts once", exhausted.campaign_snapshot() == lost and loss["failure_count"] == 1)
	var copy = exhausted.clone_for_search()
	_check("resource loss snapshot revalidates frontier", copy.restore_snapshot(lost))
	_check("complete checkpoint recovery clears failure without seed advance", exhausted.restore_checkpoint(str(lost["checkpoints"][0]["checkpoint_id"])) and not exhausted.is_failed() and exhausted.campaign_snapshot()["campaign_seed"] == lost["campaign_seed"])
	var receipt: Dictionary = {"status": "unknown_budget_exhausted", "complete": false}
	_check("unknown solver result cannot declare loss", not active.mark_loss_proven(receipt)["ok"] and not active.is_failed())


func _test_production_content() -> void:
	var game = Campaign.new()
	var loaded: Dictionary = game.load_campaign()
	_check("delivered 21-floor campaign loads", bool(loaded["ok"]), loaded.get("message", ""))
	if bool(loaded["ok"]):
		_check("delivered canonical stays separate from slice", game.data["content_id"] == Campaign.CONTENT_ID and game.data["floors"].size() == 21)
		var snapshot_value: Dictionary = game.campaign_snapshot()
		_check("delivered campaign Save v2 validates", game.clone_for_search().restore_snapshot(snapshot_value))


func _find(data: Dictionary, id: String) -> Dictionary:
	for floor_item: Dictionary in data["floors"]:
		for item: Dictionary in floor_item["objects"]:
			if str(item["id"]) == id:
				return item
	return {}


func _approach(game: RefCounted, target: Array) -> bool:
	for offset: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var adjacent: Array = [int(target[0]) + offset.x, int(target[1]) + offset.y]
		if game.walkable(adjacent) and game.object_at(adjacent).is_empty() and _walk_to(game, adjacent):
			return true
	return false


func _walk_to(game: RefCounted, target: Array) -> bool:
	var state_value: Dictionary = game.state
	var start: Vector2i = Vector2i(int(state_value["pos"][0]), int(state_value["pos"][1]))
	var end: Vector2i = Vector2i(int(target[0]), int(target[1]))
	if start == end:
		return true
	var queue: Array[Vector2i] = [start]
	var previous: Dictionary = {start: start}
	while not queue.is_empty():
		var current: Vector2i = queue.pop_front()
		if current == end:
			var path: Array = []
			while current != start:
				path.push_front(current)
				current = previous[current]
			for cell: Vector2i in path:
				if not game.interact([cell.x, cell.y])["ok"]:
					return false
			return true
		for delta: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
			var next: Vector2i = current + delta
			var coordinates: Array = [next.x, next.y]
			if previous.has(next) or not game.walkable(coordinates):
				continue
			var item: Dictionary = game.object_at(coordinates)
			if not item.is_empty() and next != end and item["kind"] != "shop":
				continue
			previous[next] = current
			queue.append(next)
	return false


func _write(path: String, text: String) -> void:
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(text)
	file.close()


func _readonly_tree(value: Variant) -> bool:
	if value is Dictionary:
		if not value.is_read_only():
			return false
		for child: Variant in value.values():
			if not _readonly_tree(child):
				return false
	elif value is Array:
		if not value.is_read_only():
			return false
		for child: Variant in value:
			if not _readonly_tree(child):
				return false
	return true
