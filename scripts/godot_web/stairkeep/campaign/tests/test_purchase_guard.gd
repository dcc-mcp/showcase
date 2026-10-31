extends "res://tests/replay_variant_routes.gd"
## Experimental backend guard. Full gameplay suffixes reuse the real campaign
## replay paths; no economy edits, state setters, refunds or combat formulas.

const Guard = preload("res://scripts/purchase_guard.gd")
const Solver = preload("res://tests/campaign_solver.gd")
const PREFIX: Array[String] = ["f01_core_def", "f01_core_atk", "f01_entry_gold", "f01_choice_key", "f01_chapter_key", "f01_scout", "f01_trail_potion"]
const DEFENSE_PREFIX: Array[String] = ["f01_defense_door", "f01_defense_gem", "f01_defense_gold", "f01_defense_potion"]
const PROOF_BUDGETS: Dictionary = {"max_expanded": 500, "max_states": 2000, "max_msec": 30000}
const UNKNOWN_BUDGETS: Dictionary = {"max_expanded": 1, "max_states": 100, "max_msec": 10000}

var checks: Array = []
var evidence: Dictionary = {"production_cases": [], "token_and_unknown_cases": [], "budget_cases": [], "recovery_workflow": {}}
var recovery_game: RefCounted
var canonical: Dictionary = {}
var blade: Dictionary = {}
var cases_only: bool = false


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--output="):
			output = argument.trim_prefix("--output=")
		elif argument == "--cases-only":
			cases_only = true
		else:
			print(JSON.stringify({"passed": false, "error": "Unknown purchase-guard test argument: " + argument}))
			quit(2)
			return
	var json: JSON = JSON.new()
	if json.parse(FileAccess.get_file_as_string(DATA_PATH)) != OK or not (json.data is Dictionary):
		print(JSON.stringify({"passed": false, "error": "Production canonical data is not available."}))
		quit(2)
		return
	canonical = json.data
	for route: Dictionary in canonical.get("validated_routes", []):
		if str(route.get("name", "")) == "blade":
			blade = route
	if blade.is_empty():
		print(JSON.stringify({"passed": false, "error": "The authored blade witness is absent."}))
		quit(2)
		return
	var started: int = Time.get_ticks_msec()
	_test_four_production_purchases()
	_test_budget_limits()
	_test_tokens_and_unknown()
	if not cases_only and recovery_game != null:
		_recover_cancel_and_win()
	var report: Dictionary = {
		"suite": "experimental_purchase_guard_backend", "passed": failures.is_empty(),
		"coverage": "guard-cases-only" if cases_only else "guard-cases-and-complete-21-floor-recovery",
		"engine": Engine.get_version_info(), "content_sha256": Variants.content_hash(canonical),
		"data_file_sha256": FileAccess.get_sha256(DATA_PATH),
		"rules_sha256": Campaign.rules_fingerprint(),
		"guard_sha256": FileAccess.get_sha256("res://scripts/purchase_guard.gd"),
		"solver_sha256": FileAccess.get_sha256("res://tests/campaign_solver.gd"),
		"test_sha256": FileAccess.get_sha256("res://tests/test_purchase_guard.gd"),
		"checks": checks, "failures": failures, "evidence": evidence,
		"full_recovery_workflow_completed": bool(evidence["recovery_workflow"].get("won", false)),
		"elapsed_ms": Time.get_ticks_msec() - started,
		"scope": "A tested backend protection facade is not a shipped game prompt. The 21-floor UI is not connected. Bounded unknown is not safe; an existing winning suffix does not guarantee every later policy. Original economy, fixed rules, data, unguarded simulations and baseline failures are unchanged.",
	}
	if not cases_only and not bool(report["full_recovery_workflow_completed"]):
		report["passed"] = false
		_check("required actual recovery suffix completed", false)
	if not output.is_empty():
		var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
		if file == null:
			_check("complete guard report can be written", false)
			report["passed"] = false
		else:
			file.store_string(JSON.stringify(report, "  ") + "\n")
			file.close()
	var case_summary: Array = []
	for item: Dictionary in evidence["production_cases"]:
		case_summary.append({"prefix": item["prefix"], "offer": item["offer"], "classification": item["classification"], "default_blocked": item["default_blocked"], "explicit_accepted": item["explicit_accepted"], "actual_post_purchase_solver": item["actual_post_purchase_solver"], "expanded": item["expanded"]})
	print(JSON.stringify({"suite": report["suite"], "passed": report["passed"], "coverage": report["coverage"], "checks": checks.size(), "failures": failures, "cases": case_summary, "full_21_floor_recovery_won": report["full_recovery_workflow_completed"], "recovery_final": evidence["recovery_workflow"].get("final_budget", {}), "known_winning_preview_verified": evidence["recovery_workflow"].get("known_winning_preview_verified", false), "elapsed_ms": report["elapsed_ms"], "full_report": output}))
	quit(0 if bool(report["passed"]) else 1)


func _check(name: String, passed: bool, observed: Variant = null) -> void:
	checks.append({"name": name, "passed": passed, "observed": observed})
	if not passed:
		failures.append(name)
		push_error(name + ": " + str(observed))


func _setup_prefix(defense_first: bool) -> Dictionary:
	var game = Campaign.new()
	var opened: Dictionary = game.start_campaign(canonical, 20261025)
	var trace: Array = []
	if not bool(opened.get("ok", false)):
		return {"ok": false, "game": game, "trace": trace, "error": opened}
	_index(game.data)
	var prepared: Dictionary = Navigation.prepare(game)
	for event: String in PREFIX:
		if not _actual_event(game, event, prepared, trace):
			return {"ok": false, "game": game, "trace": trace}
	if defense_first:
		for event: String in DEFENSE_PREFIX:
			if not _actual_event(game, event, prepared, trace):
				return {"ok": false, "game": game, "trace": trace}
	var approached: Dictionary = _approach_offer(game, "f01_shop/ward", prepared)
	trace.append({"event": "approach:f01_shop", "execution": approached})
	return {"ok": bool(approached.get("ok", false)), "game": game, "trace": trace}


func _test_four_production_purchases() -> void:
	for defense_first: bool in [false, true]:
		for choice: String in ["ward", "flask"]:
			var prefix: String = "defense_room_before_shop" if defense_first else "yellow_key_unspent_at_shop"
			var label: String = prefix + "/" + choice
			var reached: Dictionary = _setup_prefix(defense_first)
			_check("real initial-to-shop prefix " + label, bool(reached.get("ok", false)))
			if not bool(reached.get("ok", false)):
				continue
			var game: RefCounted = reached["game"]
			var guard = Guard.new(game)
			var before: Dictionary = game.campaign_snapshot()
			var preview: Dictionary = guard.preview("f01_shop/" + choice, PROOF_BUDGETS)
			_check("guard proves exact losing counterfactual " + label, bool(preview.get("ok", false)) and preview.get("classification", "") == "known_losing", _preview_summary(preview))
			_check("preview leaves entire authoritative campaign unchanged " + label, _equal(before, game.campaign_snapshot()))
			if not bool(preview.get("ok", false)):
				continue
			var original_token: String = str(preview["token"])
			var original_preview: Dictionary = preview.duplicate(true)
			# Public dictionaries are a view, never the authority for a commit.
			preview["classification"] = "known_winning"
			preview["offer"] = "f01_shop/edge"
			preview["choice"] = "edge"
			if preview.get("after_snapshot") is Dictionary:
				preview["after_snapshot"]["core_state"]["hp"] = 2000000000
			var fake_dict: Dictionary = guard.commit({"token": original_token, "classification": "known_winning"}, false)
			_check("dictionary cannot impersonate opaque token " + label, not bool(fake_dict.get("ok", true)) and _equal(before, game.campaign_snapshot()))
			var blocked: Dictionary = guard.commit(original_token, false)
			var blocked_ok: bool = not bool(blocked.get("ok", true)) and blocked.get("classification", "") == "known_losing" and _equal(before, game.campaign_snapshot())
			_check("tampered public view cannot bypass default losing block " + label, blocked_ok, blocked)
			var repeated: Dictionary = guard.commit(original_token, true)
			_check("blocked commit token is one-use " + label, not bool(repeated.get("ok", true)) and _equal(before, game.campaign_snapshot()))
			var explicit_preview: Dictionary = guard.preview("f01_shop/" + choice, PROOF_BUDGETS)
			var accepted: Dictionary = guard.commit(str(explicit_preview.get("token", "")), true)
			var accepted_ok: bool = bool(accepted.get("ok", false)) and bool(accepted.get("accepted_known_loss", false)) and _equal(game.campaign_snapshot(), explicit_preview.get("after_snapshot", {}))
			_check("explicit confirmation retains actual losing purchase " + label, accepted_ok, _commit_summary(accepted))
			_check("guard never advances layout or respawn sequence " + label, _same_sequence(before, game.campaign_snapshot()))
			var post: Dictionary = game.campaign_snapshot()
			var actual_solver: Dictionary = Solver.solve(game, PROOF_BUDGETS)
			_check("accepted production purchase is still genuinely unsatisfiable " + label, actual_solver.get("result", "") == "unsatisfiable" and bool(actual_solver.get("receipt", {}).get("complete", false)), {"result": actual_solver.get("result"), "expanded": actual_solver.get("expanded")})
			_check("post-purchase proof leaves actual loss state unchanged " + label, _equal(post, game.campaign_snapshot()))
			var record: Dictionary = {"prefix": prefix, "offer": choice, "initial_to_shop": reached["trace"], "before_snapshot": before, "preview": original_preview, "default_blocked": blocked_ok, "default_commit": blocked, "explicit_preview": explicit_preview, "explicit_commit": accepted, "explicit_accepted": accepted_ok, "classification": original_preview.get("classification", ""), "actual_post_purchase_solver": actual_solver.get("result", ""), "expanded": actual_solver.get("expanded", 0), "post_purchase_snapshot": post, "actual_solver": actual_solver}
			evidence["production_cases"].append(record)
			if not defense_first and choice == "ward" and accepted_ok and actual_solver.get("result", "") == "unsatisfiable":
				var marked: Dictionary = game.mark_loss_proven(actual_solver.get("receipt", {}))
				_check("accepted wrong purchase can record bound proven loss", bool(marked.get("ok", false)) and game.is_failed())
				var loss: Dictionary = game.campaign_snapshot()
				var entry: Dictionary = loss["checkpoints"][0]
				var restored: bool = game.restore_checkpoint(str(entry["checkpoint_id"]))
				_check("complete entry checkpoint restores economy world stock and position", restored and not game.is_failed() and _equal(game.state, entry["core_state"]) and _same_sequence(entry, game.campaign_snapshot()))
				_check("checkpoint recovery retains historical failure without granting resources", restored and game.campaign_snapshot()["failure_events_seen"].has(loss["failure_event_id"]) and game.state["cleared"].is_empty() and game.state["purchases"].is_empty())
				if restored:
					recovery_game = game
					evidence["recovery_workflow"]["accepted_loss_snapshot"] = loss
					evidence["recovery_workflow"]["restored_full_snapshot"] = game.campaign_snapshot()


func _test_tokens_and_unknown() -> void:
	var reached: Dictionary = _setup_prefix(false)
	_check("token tests reach genuine production shop", bool(reached.get("ok", false)))
	if not bool(reached.get("ok", false)):
		return
	var game: RefCounted = reached["game"]
	var guard = Guard.new(game)
	var before: Dictionary = game.campaign_snapshot()
	var unknown: Dictionary = guard.preview("f01_shop/ward", UNKNOWN_BUDGETS)
	_check("bounded result remains unknown and never safe", bool(unknown.get("ok", false)) and unknown.get("classification", "") == "unknown" and not bool(unknown.get("safe", false)), _preview_summary(unknown))
	_check("bounded preview does not mutate source or seeds", _equal(before, game.campaign_snapshot()))
	if not bool(unknown.get("ok", false)):
		return
	var other_guard = Guard.new(game)
	var cross_guard: Dictionary = other_guard.commit(str(unknown["token"]), false)
	_check("another guard cannot consume an unissued token", not bool(cross_guard.get("ok", true)) and _equal(before, game.campaign_snapshot()))
	var unknown_commit: Dictionary = guard.commit(str(unknown["token"]), false)
	var after: Dictionary = game.campaign_snapshot()
	_check("unknown keeps original purchase semantics with no safety guarantee", bool(unknown_commit.get("ok", false)) and unknown_commit.get("classification", "") == "unknown" and not bool(unknown_commit.get("safe", false)) and _equal(after, unknown["after_snapshot"]) and _same_sequence(before, after), _commit_summary(unknown_commit))
	_check("successful commit token cannot buy twice", not bool(guard.commit(str(unknown["token"]), false).get("ok", true)) and _equal(after, game.campaign_snapshot()))
	evidence["token_and_unknown_cases"].append({"kind": "bounded_unknown", "preview": unknown, "commit": unknown_commit, "before": before, "after": after})
	reached = _setup_prefix(false)
	if not bool(reached.get("ok", false)):
		_check("stale-token prefix reaches shop", false)
		return
	game = reached["game"]
	guard = Guard.new(game)
	var pending: Dictionary = guard.preview("f01_shop/ward", UNKNOWN_BUDGETS)
	var movement: Dictionary = _move_one_clear_tile(game)
	_check("staleness is produced by a real movement", bool(movement.get("ok", false)))
	var changed: Dictionary = game.campaign_snapshot()
	var stale: Dictionary = guard.commit(str(pending.get("token", "")), true)
	_check("state-changed token is rejected without overwriting new state", not bool(stale.get("ok", true)) and _equal(changed, game.campaign_snapshot()))
	if bool(movement.get("ok", false)):
		Navigation.execute(game, [{"kind": "move", "dx": -int(movement["dx"]), "dy": -int(movement["dy"])}])
	var returned: Dictionary = game.campaign_snapshot()
	_check("stale token stays consumed after moving back", not bool(guard.commit(str(pending.get("token", "")), true).get("ok", true)) and _equal(returned, game.campaign_snapshot()))
	var cancel_preview: Dictionary = guard.preview("f01_shop/ward", UNKNOWN_BUDGETS)
	var cancel_before: Dictionary = game.campaign_snapshot()
	var canceled: Dictionary = guard.cancel(str(cancel_preview.get("token", "")))
	_check("cancel consumes ticket and changes no campaign field", bool(canceled.get("ok", false)) and _equal(cancel_before, game.campaign_snapshot()))
	_check("canceled token cannot later commit", not bool(guard.commit(str(cancel_preview.get("token", "")), true).get("ok", true)) and _equal(cancel_before, game.campaign_snapshot()))
	evidence["token_and_unknown_cases"].append({"kind": "stale_and_cancel", "stale_commit": stale, "cancel": canceled, "full_final_snapshot": game.campaign_snapshot()})


func _test_budget_limits() -> void:
	var reached: Dictionary = _setup_prefix(false)
	_check("budget tests reach actual production shop", bool(reached.get("ok", false)))
	if not bool(reached.get("ok", false)):
		return
	var game: RefCounted = reached["game"]
	var before: Dictionary = game.campaign_snapshot()
	for invalid: Dictionary in [{"max_msec": 30001}, {"max_expanded": 5001}, {"max_states": 20001}, {"navigation_max_nodes": 100001}, {"max_msec": 2000000000}, {"max_expanded": 0}, {"max_states": 0}, {"max_msec": 0}]:
		var guard = Guard.new(game)
		var rejected: Dictionary = guard.preview("f01_shop/ward", invalid)
		var stats: Dictionary = guard.query_stats()
		_check("hard per-query bound rejects " + str(invalid), not bool(rejected.get("ok", true)) and rejected.get("status", "") == "invalid_budgets" and rejected.get("classification", "") == "unknown" and int(stats.get("queries_used", -1)) == 0 and _equal(before, game.campaign_snapshot()), {"status": rejected.get("status"), "stats": stats})
		evidence["budget_cases"].append({"kind": "invalid_per_query", "request": invalid, "result": rejected, "stats": stats})
	for raised: Dictionary in [{"max_queries": 17}, {"max_total_msec": 120001}]:
		var guard = Guard.new(game, raised)
		var rejected: Dictionary = guard.preview("f01_shop/ward", UNKNOWN_BUDGETS)
		_check("constructor cannot raise production limits " + str(raised), not bool(rejected.get("ok", true)) and rejected.get("status", "") == "invalid_instance_limits" and int(guard.query_stats().get("queries_used", -1)) == 0 and _equal(before, game.campaign_snapshot()), rejected)
	var defaults = Guard.new(game)
	var default_query: Dictionary = defaults.preview("f01_shop/ward", {"max_expanded": 1})
	var effective: Dictionary = default_query.get("effective_budgets", {})
	_check("missing limits use explicit bounded guard defaults", bool(default_query.get("ok", false)) and int(effective.get("max_expanded", -1)) == 1 and int(effective.get("max_states", -1)) == 20000 and int(effective.get("max_msec", -1)) == 15000 and int(effective.get("navigation_max_nodes", -1)) == 0, effective)
	if default_query.has("token"):
		defaults.cancel(default_query["token"])
	evidence["budget_cases"].append({"kind": "explicit_default_limits", "result": default_query, "stats": defaults.query_stats()})
	var limited = Guard.new(game, {"max_queries": 1})
	var first: Dictionary = limited.preview("f01_shop/ward", UNKNOWN_BUDGETS)
	_check("reduced query quota permits one real solver invocation", bool(first.get("ok", false)) and int(limited.query_stats().get("queries_used", -1)) == 1)
	if first.has("token"):
		limited.cancel(first["token"])
	var public_stats: Dictionary = limited.query_stats()
	public_stats["queries_used"] = 0
	public_stats["limits"]["max_queries"] = 16
	var second: Dictionary = limited.preview("f01_shop/ward", UNKNOWN_BUDGETS)
	_check("cancel and returned stats cannot refill per-instance query quota", not bool(second.get("ok", true)) and second.get("status", "") == "query_limit_reached" and second.get("classification", "") == "unknown" and int(limited.query_stats().get("queries_used", -1)) == 1 and _equal(before, game.campaign_snapshot()), limited.query_stats())
	evidence["budget_cases"].append({"kind": "query_quota_not_refunded", "first": first, "second": second, "stats": limited.query_stats()})
	var timed = Guard.new(game, {"max_total_msec": 1})
	var timed_first: Dictionary = timed.preview("f01_shop/ward", PROOF_BUDGETS)
	var timed_stats: Dictionary = timed.query_stats()
	_check("effective query time is bounded by remaining total time", bool(timed_first.get("ok", false)) and int(timed_first.get("effective_budgets", {}).get("max_msec", -1)) == 1 and int(timed_stats.get("queries_used", -1)) == 1 and int(timed_stats.get("total_query_msec", 0)) >= 1, timed_stats)
	if timed_first.has("token"):
		timed.cancel(timed_first["token"])
	var timed_second: Dictionary = timed.preview("f01_shop/ward", UNKNOWN_BUDGETS)
	_check("measured cumulative query wall time forbids another invocation", not bool(timed_second.get("ok", true)) and timed_second.get("status", "") == "total_time_limit_reached" and timed_second.get("classification", "") == "unknown" and int(timed.query_stats().get("queries_used", -1)) == 1 and _equal(before, game.campaign_snapshot()), timed.query_stats())
	evidence["budget_cases"].append({"kind": "measured_total_time_quota", "first": timed_first, "second": timed_second, "stats": timed.query_stats(), "scope": "Actual solver wall time on the real 21-floor state; the one-millisecond cooperative budget may be crossed by the current call's initialization, and no subsequent solver query is allowed."})


func _recover_cancel_and_win() -> void:
	var game: RefCounted = recovery_game
	_index(game.data)
	var prepared: Dictionary = Navigation.prepare(game)
	var initial: Dictionary = game.campaign_snapshot()
	var expected_cleared: Dictionary = {}
	var expected_purchases: Dictionary = {}
	var trace: Array = []
	var complete: bool = true
	var guarded_edge: bool = false
	var known_winning_preview: bool = false
	var events: Array = blade["events"]
	var ledger: Array = blade["ledger"]
	for index: int in range(events.size()):
		var event: String = str(events[index])
		# This late query is a real counterfactual purchase with an immediately
		# reachable final boss. Cancel it so the authored blade budget is exact.
		if index == events.size() - 1:
			var late: Dictionary = _late_known_winning_query(game, prepared)
			evidence["recovery_workflow"]["late_known_winning_query"] = late
			known_winning_preview = bool(late.get("ok", false))
			_check("real late production purchase has a verified winning suffix", known_winning_preview, late.get("summary", {}))
		var before: Dictionary = game.state
		var execution: Dictionary
		var path: Array = []
		if event == "buy:f01_shop/edge" and not guarded_edge:
			var approach: Dictionary = _approach_offer(game, "f01_shop/edge", prepared)
			_check("recovered run reaches edge offer by actual navigation", bool(approach.get("ok", false)))
			if not bool(approach.get("ok", false)):
				complete = false
				break
			var guard = Guard.new(game)
			var bad: Dictionary = guard.preview("f01_shop/ward", PROOF_BUDGETS)
			var cancel_before: Dictionary = game.campaign_snapshot()
			var canceled: Dictionary = guard.cancel(str(bad.get("token", "")))
			_check("recovered player can cancel proven bad offer", bad.get("classification", "") == "known_losing" and bool(canceled.get("ok", false)) and _equal(cancel_before, game.campaign_snapshot()))
			var edge: Dictionary = guard.preview("f01_shop/edge", UNKNOWN_BUDGETS)
			# A small solver budget is not a veto: the unchanged original edge
			# purchase is allowed, and the entire real suffix below proves it.
			execution = guard.commit(str(edge.get("token", "")), false)
			_check("cancel then actual edge purchase retains original economy", bool(execution.get("ok", false)) and _equal(game.campaign_snapshot(), edge.get("after_snapshot", {})), _commit_summary(execution))
			evidence["recovery_workflow"]["canceled_bad_preview"] = bad
			evidence["recovery_workflow"]["edge_approach"] = approach
			evidence["recovery_workflow"]["actual_edge_preview"] = edge
			evidence["recovery_workflow"]["actual_edge_commit"] = execution
			path = approach.get("actions", []).duplicate(true)
			path.append({"kind": "purchase_guard_commit", "offer": "f01_shop/edge", "confirmed": false, "classification": execution.get("classification", "")})
			guarded_edge = true
		else:
			var planned: Dictionary = _event_path(game, event, prepared)
			if not bool(planned.get("ok", false)):
				_check("full recovered blade path exists at " + event, false, planned)
				complete = false
				break
			path = planned["path"]
			execution = Navigation.execute(game, path)
		if not bool(execution.get("ok", false)):
			_check("full recovered blade action executes at " + event, false, execution)
			complete = false
			break
		var object_id: String = event.trim_prefix("buy:").split("/")[0] if event.begins_with("buy:") else event
		if event.begins_with("buy:"):
			var purchase_id: String = event.trim_prefix("buy:")
			expected_purchases[purchase_id] = int(expected_purchases.get(purchase_id, 0)) + 1
		elif not ["stairs", "shop"].has(str(objects[object_id]["item"]["kind"])):
			expected_cleared[object_id] = true
		var after: Dictionary = game.state
		var mismatch: String = _event_invariants(after, ledger[index]["state"], expected_cleared, expected_purchases, game.campaign_snapshot(), initial)
		if ledger[index].has("damage") and int(before["hp"]) - int(after["hp"]) != int(ledger[index]["damage"]):
			mismatch += " Damage differs from authored actual budget."
		if not mismatch.is_empty():
			_check("recovered blade exact event budget " + event, false, {"reason": mismatch, "actual": _budget(after), "expected": ledger[index]["state"]})
			complete = false
			break
		trace.append({"index": index, "event": event, "actions": path.duplicate(true), "before": _budget(before), "after": _budget(after), "core_sha256": Variants.content_hash(after)})
	_check("accepted loss checkpoint recovery cancel and edge reach actual 21-floor victory", complete and guarded_edge and bool(game.state.get("won", false)) and trace.size() == events.size() and _same_budget(game.state, blade["final"]), {"events": trace.size(), "expected_events": events.size(), "final": _budget(game.state)})
	evidence["recovery_workflow"]["won"] = complete and guarded_edge and bool(game.state.get("won", false)) and trace.size() == events.size()
	evidence["recovery_workflow"]["known_winning_preview_verified"] = known_winning_preview
	evidence["recovery_workflow"]["events"] = trace
	evidence["recovery_workflow"]["final_budget"] = _budget(game.state)
	evidence["recovery_workflow"]["full_final_snapshot"] = game.campaign_snapshot()


func _late_known_winning_query(game: RefCounted, prepared: Dictionary) -> Dictionary:
	var approached: Dictionary = _approach_offer(game, "f19_shop/flask", prepared)
	if not bool(approached.get("ok", false)):
		return {"ok": false, "summary": approached}
	var guard = Guard.new(game)
	var before: Dictionary = game.campaign_snapshot()
	var preview: Dictionary = guard.preview("f19_shop/flask", PROOF_BUDGETS)
	var canceled: Dictionary = guard.cancel(str(preview.get("token", "")))
	var report: Dictionary = preview.get("solver_report", {})
	var ok: bool = bool(preview.get("ok", false)) and preview.get("classification", "") == "known_winning" and report.get("result", "") == "witness" and bool(report.get("witness_verification", {}).get("ok", false)) and bool(canceled.get("ok", false)) and _equal(before, game.campaign_snapshot())
	return {"ok": ok, "summary": _preview_summary(preview), "navigation": approached, "preview": preview, "cancel": canceled, "unchanged_full_snapshot_sha256": Variants.content_hash(before)}


func _approach_offer(game: RefCounted, id: String, prepared: Dictionary) -> Dictionary:
	_index(game.data)
	var planned: Dictionary = _event_path(game, "buy:" + id, prepared)
	if not bool(planned.get("ok", false)):
		return planned
	var path: Array = planned["path"].duplicate(true)
	if path.is_empty() or path[-1].get("kind", "") != "buy":
		return {"ok": false, "error": "Navigation did not finish with the selected shop action."}
	path.pop_back()
	var before: Dictionary = game.state
	var result: Dictionary = Navigation.execute(game, path)
	if not bool(result.get("ok", false)):
		return result
	var after: Dictionary = game.state
	if not _same_budget(after, before) or Variants.canonical_json(after["cleared"]) != Variants.canonical_json(before["cleared"]) or Variants.canonical_json(after["purchases"]) != Variants.canonical_json(before["purchases"]):
		return {"ok": false, "error": "Approaching the offer changed an economic/object state."}
	return {"ok": true, "actions": path, "before": before, "after": after, "execution": result}


func _actual_event(game: RefCounted, event: String, prepared: Dictionary, trace: Array) -> bool:
	var planned: Dictionary = _event_path(game, event, prepared)
	if not bool(planned.get("ok", false)):
		trace.append({"event": event, "error": planned})
		return false
	var before: Dictionary = game.state
	var result: Dictionary = Navigation.execute(game, planned["path"])
	trace.append({"event": event, "actions": planned["path"].duplicate(true), "before": before, "after": game.state, "execution": result})
	return bool(result.get("ok", false))


func _move_one_clear_tile(game: RefCounted) -> Dictionary:
	var state_value: Dictionary = game.state
	for delta: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var cell: Array = [int(state_value["pos"][0]) + delta.x, int(state_value["pos"][1]) + delta.y]
		if game.walkable(cell) and game.object_at(cell).is_empty():
			var result: Dictionary = Navigation.execute(game, [{"kind": "move", "dx": delta.x, "dy": delta.y}])
			if bool(result.get("ok", false)):
				return {"ok": true, "dx": delta.x, "dy": delta.y, "execution": result}
	return {"ok": false, "error": "No clear neighboring test movement exists."}


func _equal(a: Dictionary, b: Dictionary) -> bool:
	return Variants.canonical_json(a) == Variants.canonical_json(b)


func _same_sequence(before: Dictionary, after: Dictionary) -> bool:
	for key: String in ["content_id", "canonical_content_sha256", "rules_sha256", "variant_spec", "root_seed", "campaign_seed", "sequence_state", "attempt_index", "variant_draw_count", "floor_mirrors", "resolved_start", "transformed_content_sha256"]:
		if Variants.canonical_json(before.get(key)) != Variants.canonical_json(after.get(key)):
			return false
	return true


func _preview_summary(result: Dictionary) -> Dictionary:
	var report: Dictionary = result.get("solver_report", {})
	return {"ok": result.get("ok", false), "classification": result.get("classification", ""), "offer": result.get("offer", ""), "solver_result": report.get("result", ""), "reason": report.get("reason", result.get("message", "")), "expanded": report.get("expanded", 0), "before_binding": result.get("before_binding", {}), "after_binding": result.get("after_binding", {})}


func _commit_summary(result: Dictionary) -> Dictionary:
	return {"ok": result.get("ok", false), "classification": result.get("classification", ""), "accepted_known_loss": result.get("accepted_known_loss", false), "message": result.get("message", ""), "before_binding": result.get("before_binding", {}), "after_binding": result.get("after_binding", {})}
