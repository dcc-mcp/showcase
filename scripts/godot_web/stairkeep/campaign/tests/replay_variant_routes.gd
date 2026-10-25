extends SceneTree
## Complete witnesses through CampaignRules, Navigation actions and native Save
## v2 round trips. No state setters, combat arithmetic or omitted snapshot fields.

const Campaign = preload("res://scripts/campaign_rules.gd")
const Navigation = preload("res://scripts/campaign_navigation.gd")
const Variants = preload("res://scripts/campaign_variant.gd")
const DATA_PATH: String = "res://data/levels21.json"
const DEFAULT_ROUTES: Array[String] = ["blade", "bulwark", "balanced", "frugal"]
const EQUIVALENCE: String = "Entire snapshot compared with CampaignVariant.canonical_json; no fields removed. Dictionary order, integral JSON numbers and specified set-like cleared-ID ordering are normalized by the versioned canonical serializer."

var seeds: Array = [0, 1, 20261025, 0xffffffff]
var selected_routes: Array[String] = []
var output: String = ""
var keep_saves: bool = false
var failures: Array[String] = []
var objects: Dictionary = {}
var floor_indices: Dictionary = {}
var action_count: int = 0
var preview_count: int = 0
var save_count: int = 0
var event_count: int = 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not _arguments():
		quit(2)
		return
	var catalog = Campaign.new()
	var loaded: Dictionary = catalog.load_campaign(DATA_PATH, seeds[0])
	if not bool(loaded.get("ok", false)):
		print(JSON.stringify({"passed": false, "error": loaded.get("message", "Cannot load campaign.")}))
		quit(1)
		return
	var routes: Array = []
	var requested_routes: Array[String] = DEFAULT_ROUTES.duplicate() if selected_routes.is_empty() else selected_routes.duplicate()
	for route: Dictionary in catalog.data.get("validated_routes", []):
		if requested_routes.has(str(route.get("name", ""))):
			routes.append(route)
	for name: String in requested_routes:
		var found: int = 0
		for route: Dictionary in routes:
			if str(route["name"]) == name:
				found += 1
		if found != 1:
			print(JSON.stringify({"passed": false, "error": "Route must occur exactly once: " + name}))
			quit(2)
			return
	if routes.is_empty():
		print(JSON.stringify({"passed": false, "error": "No validated witness routes were selected."}))
		quit(2)
		return
	var started: int = Time.get_ticks_msec()
	var outcomes: Array = []
	for seed: Variant in seeds:
		for route: Dictionary in routes:
			outcomes.append(_replay(seed, route))
	var report: Dictionary = {
		"suite": "complete_variant_routes_and_native_save_v2", "passed": failures.is_empty(),
		"scope": "Full authored 21-floor witnesses through CampaignRules and actual Navigation move/use_stairs/buy, with mid-campaign and won native-file Save v2 reloads. No GUI/browser persistence or human-duration acceptance.",
		"engine": Engine.get_version_info(), "content_id": Campaign.CONTENT_ID,
		"canonical_content_sha256": catalog.campaign_snapshot()["canonical_content_sha256"],
		"rules_sha256": Campaign.rules_fingerprint(), "variant_spec": Variants.SPEC,
		"source_data_sha256": FileAccess.get_sha256(DATA_PATH),
		"test_sha256": FileAccess.get_sha256("res://tests/replay_variant_routes.gd"),
		"snapshot_equivalence": EQUIVALENCE, "runs": outcomes, "failures": failures,
		"events_checked": event_count, "actual_actions": action_count,
		"preview_deduction_comparisons": preview_count, "native_save_roundtrips": save_count,
		"elapsed_ms": Time.get_ticks_msec() - started,
	}
	if not output.is_empty():
		var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
		if file == null:
			failures.append("Requested report could not be written.")
			report["passed"] = false
		else:
			file.store_string(JSON.stringify(report, "  ") + "\n")
			file.close()
	var summaries: Array = []
	for outcome: Dictionary in outcomes:
		summaries.append({"route": outcome.get("route", ""), "seed": outcome.get("campaign_seed", ""), "passed": outcome.get("passed", false), "events": outcome.get("events_checked", 0), "final": outcome.get("final_budget", {}), "won": outcome.get("won", false), "save_roundtrips": outcome.get("save_roundtrips", 0), "elapsed_ms": outcome.get("elapsed_ms", 0)})
	var failure_summary: Array = []
	for failure: String in failures.slice(0, 8):
		failure_summary.append(failure.substr(0, 700))
	print(JSON.stringify({"passed": report["passed"], "runs": outcomes.size(), "results": summaries, "events_checked": event_count, "actual_actions": action_count, "preview_deduction_comparisons": preview_count, "native_save_roundtrips": save_count, "elapsed_ms": report["elapsed_ms"], "failure_count": failures.size(), "failures": failure_summary, "full_report": output}))
	quit(0 if bool(report["passed"]) else 1)


func _arguments() -> bool:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--seeds="):
			seeds = []
			for raw: String in argument.trim_prefix("--seeds=").split(",", false):
				var word: String = raw.strip_edges().to_lower()
				var seed: Variant
				if word.begins_with("0x") and word.length() <= 10:
					var digits: String = word.trim_prefix("0x")
					var valid: bool = not digits.is_empty()
					for letter: String in digits:
						valid = valid and "0123456789abcdef".contains(letter)
					if not valid:
						print("Invalid hexadecimal seed: " + raw)
						return false
					seed = digits.hex_to_int()
				elif word.begins_with("hex:"):
					seed = word.trim_prefix("hex:")
				elif word.is_valid_int():
					seed = word.to_int()
				else:
					seed = word
				if Variants.normalize_seed(seed).is_empty():
					print("Seed is outside the normalized uint32 contract: " + raw)
					return false
				seeds.append(seed)
		elif argument.begins_with("--routes="):
			selected_routes.clear()
			for name: String in argument.trim_prefix("--routes=").split(",", false):
				if not selected_routes.has(name.strip_edges()):
					selected_routes.append(name.strip_edges())
		elif argument.begins_with("--output="):
			output = argument.trim_prefix("--output=")
		elif argument == "--keep-saves":
			keep_saves = true
		else:
			print("Unknown replay argument: " + argument)
			return false
	return not seeds.is_empty() and seeds.size() <= 64


func _replay(seed: Variant, route: Dictionary) -> Dictionary:
	var started: int = Time.get_ticks_msec()
	var game = Campaign.new()
	var load_result: Dictionary = game.load_campaign(DATA_PATH, seed)
	var name: String = str(route["name"])
	var label: String = name + "/" + Variants.normalize_seed(seed)
	var before_failure_count: int = failures.size()
	var before_save_count: int = save_count
	if not bool(load_result.get("ok", false)):
		failures.append(label + ": initialization failed: " + str(load_result))
		return {"route": name, "campaign_seed": Variants.normalize_seed(seed), "passed": false}
	_index(game.data)
	var prepared: Dictionary = Navigation.prepare(game)
	var initial: Dictionary = game.campaign_snapshot()
	var expected_cleared: Dictionary = {}
	var expected_purchases: Dictionary = {}
	var decisions: Array = []
	var save_receipts: Array = []
	var mid_saved: bool = false
	var events: Array = route.get("events", [])
	var ledger: Array = route.get("ledger", [])
	if events.size() != ledger.size():
		failures.append(label + ": authored event and ledger lengths differ")
	for index: int in range(mini(events.size(), ledger.size())):
		var event: String = str(events[index])
		var expected: Dictionary = ledger[index]
		if expected.get("event", "") != event:
			failures.append("%s event %d ledger identity mismatch" % [label, index])
			break
		var planned: Dictionary = _event_path(game, event, prepared)
		if not bool(planned.get("ok", false)):
			failures.append("%s event %d %s path rejected: %s" % [label, index, event, str(planned)])
			break
		var before: Dictionary = game.state
		var executed: Dictionary = Navigation.execute(game, planned["path"])
		action_count += int(executed.get("moves", 0)) + (1 if bool(planned.get("buy", false)) else 0)
		preview_count += int(executed.get("preview_comparisons", 0))
		if not bool(executed.get("ok", false)):
			failures.append("%s event %d %s actual action failed: %s" % [label, index, event, str(executed)])
			break
		var after: Dictionary = game.state
		if bool(planned.get("buy", false)):
			var purchase_id: String = event.trim_prefix("buy:")
			expected_purchases[purchase_id] = int(expected_purchases.get(purchase_id, 0)) + 1
		elif not ["stairs", "shop"].has(str(planned["item"]["kind"])):
			expected_cleared[str(planned["item"]["id"])] = true
		var snapshot_value: Dictionary = game.campaign_snapshot()
		var invariant_error: String = _event_invariants(after, expected["state"], expected_cleared, expected_purchases, snapshot_value, initial)
		if expected.has("damage") and int(before["hp"]) - int(after["hp"]) != int(expected["damage"]):
			invariant_error += " Actual HP deduction differs from authored damage."
		if expected.has("rounds") and int(planned.get("preview", {}).get("rounds", -1)) != int(expected["rounds"]):
			invariant_error += " Authoritative preview rounds differ from authored rounds."
		if str(planned["item"]["kind"]) == "stairs":
			var target: Dictionary = planned["item"]["target"]
			if int(after["floor"]) != int(floor_indices[int(target["floor"])]) or not _same_cell(after["pos"], target["pos"]):
				invariant_error += " Stair endpoint differs from the transformed destination."
		if not invariant_error.is_empty():
			failures.append("%s event %d %s: %s actual=%s expected=%s" % [label, index, event, invariant_error, str(_budget(after)), str(expected["state"])])
			break
		event_count += 1
		decisions.append({"index": index, "event": event, "before": _budget(before), "after": _budget(after), "floor": int(after["floor"]) + 1, "pos": after["pos"].duplicate(), "path": planned["path"].duplicate(true), "preview": planned.get("preview", {}), "cleared_ids_sha256": Variants.content_hash(after["cleared"]), "purchase_counts_sha256": Variants.content_hash(after["purchases"]), "core_state_sha256": Variants.content_hash(after)})
		if not mid_saved and int(after["floor"]) >= 3:
			var mid: Dictionary = _disk_roundtrip(game, label, "chapter", index)
			save_receipts.append(mid["receipt"])
			if not bool(mid.get("ok", false)):
				failures.append(label + ": mid-campaign native roundtrip failed: " + str(mid["receipt"]))
				break
			game = mid["game"]
			prepared = Navigation.prepare(game)
			_index(game.data)
			mid_saved = true
	if failures.size() == before_failure_count:
		var final_snapshot: Dictionary = game.campaign_snapshot()
		if decisions.size() != events.size() or not bool(game.state.get("won", false)) or not _same_budget(game.state, route["final"]) or not mid_saved:
			failures.append(label + ": incomplete route, final budget/victory or required chapter-save check failed")
		else:
			var final_save: Dictionary = _disk_roundtrip(game, label, "won", events.size())
			save_receipts.append(final_save["receipt"])
			if not bool(final_save.get("ok", false)):
				failures.append(label + ": won native roundtrip failed: " + str(final_save["receipt"]))
			else:
				game = final_save["game"]
				if not bool(game.state.get("won", false)) or Variants.canonical_json(game.campaign_snapshot()) != Variants.canonical_json(final_snapshot):
					failures.append(label + ": won snapshot changed on complete native restore")
	var last: Dictionary = game.campaign_snapshot()
	# Prefixes make copied all-digit hexadecimal seeds unambiguous at the CLI.
	for receipt: Dictionary in save_receipts:
		receipt["replay_seed_argument"] = "0x" + str(initial["campaign_seed"])
	return {"route": name, "policy": route.get("policy", ""), "input_seed": str(seed), "campaign_seed": initial["campaign_seed"], "passed": failures.size() == before_failure_count, "events_checked": decisions.size(), "won": game.state.get("won", false), "final_budget": _budget(game.state), "final_cleared_count": game.state.get("cleared", []).size(), "final_cleared_ids_sha256": Variants.content_hash(game.state.get("cleared", [])), "final_purchase_counts": game.state.get("purchases", {}).duplicate(true), "root_seed": last["root_seed"], "sequence_state": last["sequence_state"], "attempt_index": last["attempt_index"], "floor_mirrors": last["floor_mirrors"], "resolved_start": initial["resolved_start"], "transformed_content_sha256": initial["transformed_content_sha256"], "full_final_snapshot_sha256": Variants.content_hash(last), "events": decisions, "save_roundtrips": save_count - before_save_count, "native_save_receipts": save_receipts, "elapsed_ms": Time.get_ticks_msec() - started}


func _event_path(game: RefCounted, event: String, prepared: Dictionary) -> Dictionary:
	var id: String = event.trim_prefix("buy:") if event.begins_with("buy:") else event
	var buy: bool = event.begins_with("buy:")
	var object_id: String = id.split("/")[0] if buy else id
	if not objects.has(object_id):
		return {"ok": false, "error": "Unknown stable event object."}
	var entry: Dictionary = objects[object_id]
	var item: Dictionary = entry["item"]
	if str(item["kind"]) == "stairs" and not buy:
		return _stair_path(game, entry, prepared)
	var local: bool = int(game.state["floor"]) == int(entry["floor"])
	var frontier: Dictionary = Navigation.frontier_local(game, 0, 0, false, prepared) if local else Navigation.frontier(game, 0, false, prepared)
	if not frontier.get("errors", []).is_empty():
		return {"ok": false, "error": "Navigation encountered schema errors.", "errors": frontier["errors"]}
	for option: Dictionary in frontier["options"]:
		if str(option["id"]) == id:
			return {"ok": true, "path": option["path"], "buy": buy, "item": item, "preview": option.get("preview", {}), "navigation_scope": frontier.get("scope", "")}
	if local:
		# A local policy horizon is only a speed hint, never an impossibility
		# verdict. A witness may require neutral travel through another floor.
		frontier = Navigation.frontier(game, 0, false, prepared)
		if not frontier.get("errors", []).is_empty():
			return {"ok": false, "error": "Global Navigation encountered schema errors.", "errors": frontier["errors"]}
		for option: Dictionary in frontier["options"]:
			if str(option["id"]) == id:
				return {"ok": true, "path": option["path"], "buy": buy, "item": item, "preview": option.get("preview", {}), "navigation_scope": "global-fallback"}
	return {"ok": false, "error": "The exact authored event has no legal reachable Navigation option.", "event": event, "floor": int(game.state["floor"]) + 1, "blocked": frontier.get("blocked", []), "offers": frontier.get("shop_offers", [])}


func _stair_path(game: RefCounted, entry: Dictionary, prepared: Dictionary, global_only: bool = false) -> Dictionary:
	var state_value: Dictionary = game.state
	var item: Dictionary = entry["item"]
	var target: Vector3i = Vector3i(int(entry["floor"]), int(item["pos"][0]), int(item["pos"][1]))
	var start: Vector3i = Vector3i(int(state_value["floor"]), int(state_value["pos"][0]), int(state_value["pos"][1]))
	var local: bool = start.x == target.x and not global_only
	var proof: Dictionary = Navigation.frontier_local(game, 0, 0, true, prepared) if local else Navigation.frontier(game, 0, true, prepared)
	if not proof.get("errors", []).is_empty() or not bool(proof.get("queue_exhausted", false)):
		return {"ok": false, "error": "Resource-neutral Navigation graph is incomplete.", "errors": proof.get("errors", [])}
	var adjacency: Dictionary = {}
	for edge: Dictionary in proof["edges"]:
		var from: Vector3i = _node(edge["from"])
		if not adjacency.has(from):
			adjacency[from] = []
		adjacency[from].append(edge)
	var queue: Array[Vector3i] = [start]
	var previous: Dictionary = {start: {}}
	var head: int = 0
	var goal: Variant = null
	while head < queue.size():
		var current: Vector3i = queue[head]
		head += 1
		if current.x == target.x and absi(current.y - target.y) + absi(current.z - target.z) <= 1:
			goal = current
			break
		for edge: Dictionary in adjacency.get(current, []):
			var destination: Vector3i = _node(edge["to"])
			if not previous.has(destination):
				previous[destination] = {"from": current, "action": edge["action"]}
				queue.append(destination)
	if goal == null:
		if local:
			return _stair_path(game, entry, prepared, true)
		return {"ok": false, "error": "No real resource-neutral graph path approaches the authored stair."}
	var path: Array = []
	var cursor: Vector3i = goal
	while cursor != start:
		path.push_front(previous[cursor]["action"].duplicate(true))
		cursor = previous[cursor]["from"]
	if goal == target:
		path.append({"kind": "stairs"})
	else:
		path.append({"kind": "move", "dx": target.y - int(goal.y), "dy": target.z - int(goal.z)})
	return {"ok": true, "path": path, "buy": false, "item": item, "preview": {}}


func _disk_roundtrip(game: RefCounted, label: String, stage: String, index: int) -> Dictionary:
	var safe_label: String = label.replace("/", "-")
	var path: String = "user://variant-route-" + safe_label + "-" + stage + ".json"
	var before: Dictionary = game.campaign_snapshot()
	var before_json: String = Variants.canonical_json(before)
	var saved: Dictionary = game.save_v2(path)
	var receipt: Dictionary = {"stage": stage, "after_event_index": index, "native_slot": path, "before_full_snapshot_sha256": before_json.sha256_text(), "saved": saved, "equivalence": EQUIVALENCE, "passed": false}
	if not bool(saved.get("ok", false)):
		return {"ok": false, "receipt": receipt}
	var raw: String = FileAccess.get_file_as_string(path)
	receipt["save_bytes"] = raw.to_utf8_buffer().size()
	receipt["save_file_sha256"] = raw.sha256_text()
	var restored = Campaign.new()
	var initialized: Dictionary = restored.load_campaign(DATA_PATH, before["root_seed"])
	if not bool(initialized.get("ok", false)):
		receipt["initialization"] = initialized
		return {"ok": false, "receipt": receipt}
	var loaded: Dictionary = restored.load_v2(path)
	receipt["load_ok"] = bool(loaded.get("ok", false))
	receipt["load_message"] = str(loaded.get("message", ""))
	if not bool(loaded.get("ok", false)):
		return {"ok": false, "receipt": receipt}
	var after_json: String = Variants.canonical_json(restored.campaign_snapshot())
	receipt["after_full_snapshot_sha256"] = after_json.sha256_text()
	receipt["passed"] = not before_json.is_empty() and before_json == after_json
	if bool(receipt["passed"]):
		save_count += 1
		if not keep_saves:
			DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	return {"ok": receipt["passed"], "game": restored, "receipt": receipt}


func _event_invariants(actual: Dictionary, expected: Dictionary, cleared: Dictionary, purchases: Dictionary, snapshot_value: Dictionary, initial: Dictionary) -> String:
	if not _same_budget(actual, expected):
		return "Full authored resource budget differs."
	var actual_ids: Array = actual["cleared"].duplicate()
	var expected_ids: Array = cleared.keys()
	actual_ids.sort()
	expected_ids.sort()
	if actual_ids != expected_ids:
		return "Cleared/picked/opened object set differs from exactly the executed events."
	if Variants.canonical_json(actual["purchases"]) != Variants.canonical_json(purchases):
		return "Exact per-shop/offer purchase counts differ."
	if bool(snapshot_value["failed"]):
		return "A winning witness entered a campaign failure mode."
	for binding: String in ["content_id", "canonical_content_sha256", "rules_version", "rules_sha256", "variant_spec", "root_seed", "campaign_seed", "sequence_state", "attempt_index", "variant_draw_count", "floor_mirrors", "resolved_start", "transformed_content_sha256"]:
		if Variants.canonical_json(snapshot_value[binding]) != Variants.canonical_json(initial[binding]):
			return "Seed/content/mirror binding changed during ordinary route: " + binding
	return ""


func _same_budget(actual: Dictionary, expected: Dictionary) -> bool:
	for stat: String in ["hp", "atk", "def", "gold"]:
		if int(actual.get(stat, -1)) != int(expected.get(stat, -2)):
			return false
	if actual.get("keys", {}).size() != expected.get("keys", {}).size():
		return false
	for color: String in expected.get("keys", {}):
		if int(actual.get("keys", {}).get(color, -1)) != int(expected["keys"][color]):
			return false
	return true


func _budget(state_value: Dictionary) -> Dictionary:
	return {"hp": int(state_value["hp"]), "atk": int(state_value["atk"]), "def": int(state_value["def"]), "gold": int(state_value["gold"]), "keys": state_value["keys"].duplicate(true)}


func _same_cell(a: Array, b: Array) -> bool:
	return a.size() == 2 and b.size() == 2 and int(a[0]) == int(b[0]) and int(a[1]) == int(b[1])


func _node(value: Array) -> Vector3i:
	return Vector3i(int(value[0]), int(value[1]), int(value[2]))


func _index(data: Dictionary) -> void:
	objects.clear()
	floor_indices.clear()
	for floor_index: int in range(data["floors"].size()):
		var floor_item: Dictionary = data["floors"][floor_index]
		floor_indices[int(floor_item["id"])] = floor_index
		for item: Dictionary in floor_item["objects"]:
			objects[str(item["id"])] = {"floor": floor_index, "item": item}
