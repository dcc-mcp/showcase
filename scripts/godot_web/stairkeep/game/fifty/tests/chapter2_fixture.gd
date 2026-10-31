extends RefCounted
## Test-only fixture reader. Every adopted world must pass authoritative action replay.
const Runtime = preload("res://fifty/scripts/runtime.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const DATA: String = "res://fifty/data/chapter2-content.json"
const PROFILE: String = "stairkeep-fifty-chapter2/v1"


static func read_case(path: String, expected_sha256: String, index: int) -> Dictionary:
	if expected_sha256.length() != 64 or FileAccess.get_sha256(path) != expected_sha256:
		return {"ok": false, "error": "Actual route report SHA mismatch."}
	var parsed: JSON = JSON.new()
	if parsed.parse(FileAccess.get_file_as_string(path)) != OK or not (parsed.data is Dictionary):
		return {"ok": false, "error": "Actual route report is unavailable."}
	var report: Dictionary = parsed.data
	if report.get("suite", "") != "fifty_chapter2_actual_authored_route_matrix/v1" or not bool(report.get("passed", false)) or not bool(report.get("measurement_completed", false)) or report.get("content_id", "") != PROFILE:
		return {"ok": false, "error": "Require a completed actual chapter-two route report."}
	if index < 0 or index >= report.get("cases", []).size(): return {"ok": false, "error": "Case index outside actual report."}
	for source: String in report.get("source_hashes", {}):
		if FileAccess.get_sha256(source) != report["source_hashes"][source]:
			return {"ok": false, "error": "The fixture's measured source differs.", "source": source}
	var item: Dictionary = report["cases"][index]
	if not bool(item.get("passed", false)) or not bool(item.get("authoritative_full_action_replay", {}).get("ok", false)):
		return {"ok": false, "error": "Fixture case did not complete its authoritative replay."}
	var catalogue: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DATA))
	for route: Dictionary in catalogue.get("validated_routes", []):
		if str(route["name"]) == str(item["route"]):
			return {"ok": true, "case": item, "route": route, "report_sha256": expected_sha256, "source_hashes": report["source_hashes"]}
	return {"ok": false, "error": "The fixture route no longer exists in bound canonical content."}


static func adopt(item: Dictionary) -> Dictionary:
	var game = Runtime.new()
	var loaded: Dictionary = game.load_content(DATA)
	if not bool(loaded.get("ok", false)): return {"ok": false, "result": loaded}
	var snapshot: Dictionary = item["full_final_snapshot"]
	var chosen: Dictionary = game.choose_mode(str(snapshot["mode"]), str(snapshot["root_seed"]))
	if not bool(chosen.get("ok", false)): return {"ok": false, "result": chosen}
	var accepted: Dictionary = game.import_snapshot(snapshot)
	var passed: bool = bool(accepted.get("ok", false)) and Navigation.same(snapshot, game.export_snapshot())
	return {"ok": passed, "game": game, "result": accepted, "full_snapshot_sha256": Geometry.content_hash(game.export_snapshot()), "basis": "Runtime reconstructs the run and replays all real actions before one atomic import; no test-side state assignment."}


static func checkpoint(snapshot: Dictionary, id: String) -> Dictionary:
	for item: Dictionary in snapshot.get("checkpoints", []):
		if str(item["id"]) == id: return item
	return {}


static func checkpoint_prefix(snapshot: Dictionary, id: String) -> Array:
	var prefix: Array = []
	for item: Dictionary in snapshot.get("checkpoints", []):
		prefix.append(item.duplicate(true))
		if str(item["id"]) == id: return prefix
	return []


static func ledger_error(snapshot: Dictionary, row: Dictionary) -> Array[String]:
	var errors: Array[String] = []
	if not Navigation.same(Navigation.budget(snapshot["core_state"]), row["state"]): errors.append("resources")
	for field: String in ["flags", "completed_events", "slice_complete"]:
		if not Navigation.same(snapshot[field], row[field]): errors.append(field)
	if not Navigation.same(snapshot["core_state"]["purchases"], row["purchases"]): errors.append("stock")
	if snapshot["core_state"]["cleared"].size() != int(row["cleared_count"]): errors.append("cleared_count")
	return errors


static func replay_suffix(game: RefCounted, fixture: Dictionary, route: Dictionary, source_world: Dictionary) -> Dictionary:
	var cut: int = -1
	for index: int in range(fixture.get("trace", []).size()):
		if Navigation.same(Navigation.economy(fixture["trace"][index]["actual_world"]), Navigation.economy(source_world)):
			cut = index
	if cut < 0:
		return {"ok": false, "classification": "unknown_no_matching_actual_resource_boundary", "full_state": game.export_snapshot()}
	var prepared: Dictionary = Navigation.prepare(game)
	var trace: Array = []
	var comparisons: int = 0
	for index: int in range(cut + 1, route["events"].size()):
		var event: String = str(route["events"][index])
		var before: Dictionary = game.export_snapshot()
		if not Navigation.same(Navigation.budget(before["core_state"]), route["ledger"][index]["before"]):
			return {"ok": false, "error": "Suffix before-budget mismatch.", "event": event, "full_state": before, "trace": trace}
		var planned: Dictionary = Navigation.plan(game, event, prepared)
		if not bool(planned.get("ok", false)): return {"ok": false, "classification": "unknown_navigation", "event": event, "details": planned, "full_state": before, "trace": trace}
		var executed: Dictionary = Navigation.execute(game, planned["path"])
		var after: Dictionary = game.export_snapshot()
		if not bool(executed.get("ok", false)): return {"ok": false, "error": "Actual suffix API rejection.", "event": event, "details": executed, "trace": trace}
		comparisons += int(executed.get("preview_comparisons", 0))
		var mismatch: Array[String] = ledger_error(after, route["ledger"][index])
		var selected: String = str(executed["results"][-1].get("event_id", ""))
		if route["ledger"][index].has("selected_event_id") and selected != str(route["ledger"][index]["selected_event_id"]): mismatch.append("selected_event_id")
		trace.append({"event_index": index, "event": event, "actions": planned["path"], "before_full_snapshot_sha256": Geometry.content_hash(before), "after_full_snapshot_sha256": Geometry.content_hash(after), "actual_world": Navigation.world(after), "selected_event_id": selected})
		if not mismatch.is_empty(): return {"ok": false, "error": "Suffix exact ledger differs.", "fields": mismatch, "trace": trace}
	var final: Dictionary = game.export_snapshot()
	var checked: Dictionary = game.validate_snapshot(final)
	var passed: bool = bool(checked.get("ok", false)) and Navigation.same(Navigation.economy(final), Navigation.economy(fixture["full_final_snapshot"])) and bool(final["slice_complete"]) and not bool(final["campaign_complete"]) and not bool(final["core_state"]["won"])
	return {"ok": passed, "classification": "actual_winning_suffix" if passed else "actual_suffix_failed", "matched_actual_resource_boundary": cut, "actual_events": trace.size(), "preview_actual_comparisons": comparisons, "trace": trace, "full_final_snapshot": final, "authoritative_full_replay": checked}
