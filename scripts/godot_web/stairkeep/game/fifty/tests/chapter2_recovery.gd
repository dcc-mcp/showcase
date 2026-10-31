extends SceneTree
## Actual complete run -> authoritative replay -> full F11/F15 restore -> real suffix.
const Fixture = preload("res://fifty/tests/chapter2_fixture.gd")
const Navigation = preload("res://fifty/tests/qa_navigation.gd")
const Geometry = preload("res://fifty/scripts/d4.gd")
const SELF: String = "res://fifty/tests/chapter2_recovery.gd"
var output: String = ""
var report_path: String = ""
var report_sha256: String = ""
var case_index: int = 0
var stop_file: String = ""
var errors: Array = []
var checks: Array = []
var outcomes: Array = []
var stopped: bool = false


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not _arguments():
		quit(2)
		return
	var began: int = Time.get_ticks_msec()
	var bound: Dictionary = Fixture.read_case(report_path, report_sha256, case_index)
	if not bool(bound.get("ok", false)):
		push_error(JSON.stringify(bound))
		quit(2)
		return
	if bound["case"].get("mode", "") != "practice_checkpoint":
		push_error("A real completed chapter-two practice fixture is required.")
		quit(2)
		return
	for checkpoint_id: String in ["entry_11", "entry_15"]:
		if not stop_file.is_empty() and FileAccess.file_exists(stop_file):
			stopped = true
			break
		outcomes.append(_case(bound, checkpoint_id))
		if not errors.is_empty(): break
	var report: Dictionary = {"suite": "fifty_chapter2_actual_checkpoint_recovery/v1", "passed": errors.is_empty() and not stopped and outcomes.size() == 2, "measurement_completed": not stopped and outcomes.size() == 2,
		"engine": Engine.get_version_info(), "engine_pid": OS.get_process_id(), "fixture_report_sha256": report_sha256, "fixture_case": case_index,
		"test_sha256": FileAccess.get_sha256(SELF), "helper_sha256": FileAccess.get_sha256("res://fifty/tests/chapter2_fixture.gd"), "bound_source_hashes": bound["source_hashes"],
		"checks": checks, "errors": errors, "cases": outcomes, "elapsed_ms": Time.get_ticks_msec() - began, "stopped_at_case_boundary": stopped,
		"scope": "Both worlds derive from a completed real F1-20 route whose entire action journal is independently replayed by runtime before adoption. Each checkpoint restores complete resources/stock/flags/events/world and configured checkpoint prefix; audits remain transactional. Actual runtime paths replay the suffix to the F20 slice signal. F11 can discard the captured F15 checkpoint; F15 has no later configured checkpoint in authored 1-20, so its deletion claim is explicitly non-applicable. No injected resources, floor teleport, new million-run policy proof, actual UI/browser or 50-floor completion claim."}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		quit(2)
		return
	file.store_string(JSON.stringify(report, "  ") + "\n")
	file.close()
	print(JSON.stringify({"passed": report["passed"], "cases": outcomes.size(), "checks": checks.size(), "errors": errors.size(), "elapsed_ms": report["elapsed_ms"]}))
	quit(0 if bool(report["passed"]) or (stopped and errors.is_empty()) else 1)


func _arguments() -> bool:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
		elif argument.begins_with("--route-report="): report_path = argument.trim_prefix("--route-report=")
		elif argument.begins_with("--route-report-sha256="): report_sha256 = argument.trim_prefix("--route-report-sha256=")
		elif argument.begins_with("--case=") and argument.trim_prefix("--case=").is_valid_int(): case_index = int(argument.trim_prefix("--case="))
		elif argument.begins_with("--stop-file="): stop_file = argument.trim_prefix("--stop-file=")
		else: return false
	return not output.is_empty() and output.is_absolute_path() and not FileAccess.file_exists(output) and not report_path.is_empty() and report_sha256.length() == 64 and case_index >= 0


func _case(bound: Dictionary, checkpoint_id: String) -> Dictionary:
	var adopted: Dictionary = Fixture.adopt(bound["case"])
	var outcome: Dictionary = {"checkpoint_id": checkpoint_id, "passed": false, "initial_fixture_adoption": adopted.get("result", {})}
	if not _check(checkpoint_id + ": entire actual run replays before adoption", bool(adopted.get("ok", false)), adopted.get("result", {})): return outcome
	var game = adopted["game"]
	var completed: Dictionary = game.export_snapshot()
	var checkpoint: Dictionary = Fixture.checkpoint(completed, checkpoint_id)
	var expected_prefix: Array = Fixture.checkpoint_prefix(completed, checkpoint_id)
	var checkpoint_floors: Array = []
	for item: Dictionary in completed["checkpoints"]: checkpoint_floors.append(int(item["floor_id"]))
	if not _check(checkpoint_id + ": only configured complete entry checkpoints exist", not checkpoint.is_empty() and Navigation.same(checkpoint_floors, [1, 5, 11, 15]), {"actual_floors": checkpoint_floors}): return outcome
	var source_world: Dictionary = checkpoint["world"]
	var deltas: Dictionary = {"stock_changed": not Navigation.same(completed["core_state"]["purchases"], source_world["core_state"]["purchases"]), "flags_changed": not Navigation.same(completed["flags"], source_world["flags"]), "events_changed": not Navigation.same(completed["completed_events"], source_world["completed_events"]), "resources_changed": not Navigation.same(Navigation.budget(completed["core_state"]), Navigation.budget(source_world["core_state"]))}
	if not _check(checkpoint_id + ": restore tests real later resource stock flag and event changes", bool(deltas["stock_changed"]) and bool(deltas["flags_changed"]) and bool(deltas["events_changed"]) and bool(deltas["resources_changed"]), deltas): return outcome
	var cancelled: Dictionary = game.restore_checkpoint(checkpoint_id, false)
	if not _check(checkpoint_id + ": unconfirmed restoration leaves full snapshot unchanged", not bool(cancelled.get("ok", true)) and Navigation.same(completed, game.export_snapshot()), cancelled): return outcome
	var abandoned: Dictionary = game.give_up(true)
	var failed: Dictionary = game.export_snapshot()
	if not _check(checkpoint_id + ": explicit abandonment is not an unsatisfiable proof", bool(abandoned.get("ok", false)) and bool(failed["failed"]) and failed["failure"].get("kind", "") == "abandoned", abandoned): return outcome
	var loss_id: String = str(failed["failure"]["failure_id"])
	var restored_result: Dictionary = game.restore_checkpoint(checkpoint_id, true, loss_id)
	var restored: Dictionary = game.export_snapshot()
	var exact_world: bool = bool(restored_result.get("ok", false)) and Navigation.same(Navigation.world(restored), source_world) and Navigation.same(restored["checkpoints"], expected_prefix)
	for field: String in ["seed", "root_seed", "sequence_state", "attempt_index", "floor_transforms", "layout_sha256", "content_id", "content_sha256"]:
		exact_world = exact_world and Navigation.same(restored[field], completed[field])
	if not _check(checkpoint_id + ": complete same-run world and checkpoint prefix restore atomically", exact_world, restored_result): return outcome
	var audit: bool = Navigation.same(restored["failure_history"], failed["failure_history"]) and restored["actions"].size() == failed["actions"].size() + 1 and int(restored["recovery_count"]) == int(failed["recovery_count"]) + 1 and restored["consumed_loss_ids"].count(loss_id) == 1 and not bool(restored["failed"])
	if not _check(checkpoint_id + ": audit history retained and exact loss consumed once", audit): return outcome
	var stale: Dictionary = game.restore_checkpoint(checkpoint_id, true, loss_id)
	if not _check(checkpoint_id + ": duplicate consumed loss cannot replay restoration", not bool(stale.get("ok", true)) and Navigation.same(restored, game.export_snapshot()), stale): return outcome
	var missing_id: String = "entry_15" if checkpoint_id == "entry_11" else "entry_20"
	var missing: Dictionary = game.restore_checkpoint(missing_id, true)
	if not _check(checkpoint_id + ": uncaptured or discarded future checkpoint rejects unchanged", not bool(missing.get("ok", true)) and Navigation.same(restored, game.export_snapshot()), missing): return outcome
	var suffix: Dictionary = Fixture.replay_suffix(game, bound["case"], bound["route"], source_world)
	_check(checkpoint_id + ": real restored runtime suffix reaches exact authored F20 slice budget", bool(suffix.get("ok", false)), {"classification": suffix.get("classification", "unknown"), "actual_events": suffix.get("actual_events", 0), "error": suffix.get("error", "")})
	outcome.merge({"passed": bool(suffix.get("ok", false)), "full_pre_recovery_snapshot": completed, "failed_full_snapshot": failed, "full_restored_snapshot": restored, "checkpoint_world": source_world, "later_changes": deltas, "future_checkpoint_count_removed": completed["checkpoints"].size() - expected_prefix.size(), "future_checkpoint_deletion_nonvacuous": completed["checkpoints"].size() > expected_prefix.size(), "suffix": suffix}, true)
	return outcome


func _check(name: String, passed: bool, details: Dictionary = {}) -> bool:
	checks.append({"name": name, "passed": passed, "details": details})
	if not passed: errors.append({"name": name, "details": details})
	return passed
