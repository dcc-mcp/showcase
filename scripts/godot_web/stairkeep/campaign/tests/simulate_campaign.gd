extends SceneTree
## Seeded policy exploration, not a witness loop, universal solver or play test.
## Every encounter uses frozen base_rules.combat() through shared Navigation.

const BaseRules = preload("res://scripts/base_rules.gd")
const VariantBuilder = preload("res://scripts/campaign_variant.gd")
const Navigation = preload("res://scripts/campaign_navigation.gd")
const DATA_PATH: String = "res://data/levels21.json"
const MASK: int = 0xffffffff
const POLICIES: Array[String] = ["resource", "attack", "defense", "cautious", "randomized"]
const DEFINITIONS: Dictionary = {
	"resource": "Current-floor legal actions; reachable free keys/stats/coins before low-cost encounters. If the observed frontier contains an armor-impenetrable enemy, an affordable ATK offer is prepared first. No witness sequence is consulted.",
	"attack": "Current-floor legal actions; ATK pickups and purchases, then keys/resources, favor fewer-HP-cost encounters. Observed armor-gate preparation precedes other shopping. No witness sequence is consulted.",
	"defense": "Current-floor legal actions; DEF pickups/purchases and conservative encounters, with explicit observed armor-gate ATK preparation before DEF or healing purchases. No future unreachable guard is inspected.",
	"cautious": "Current-floor legal actions; free resources and low-loss encounters, healing when HP is low relative to observed costs; explicitly prepare ATK against an observed armor-impenetrable gate before other purchases.",
	"randomized": "Uncorrected seeded random selection among current-floor legal frontier options. When none exist, choose among the complete global frontier. No armor-gate preparation, shopping correction, route repair or hidden resource grant.",
}

var runs: int = 10
var start_index: int = 0
var master_seed: int = 20261025
var master_policy_seed: int = 0
var max_decisions: int = 1000
var example_limit: int = 2
var horizon: int = 0
var progress_every: int = 100
var output_path: String = "res://tests/campaign-simulation-result.json"
var stop_file_path: String = ""
var stop_file_requested: bool = false
var stopped_at_case_boundary: bool = false
var policy_rng: int = 1
var policy_draws: int = 0
var canonical: Dictionary = {}
var run_records: Array = []
var failure_seeds: Array = []
var examples: Dictionary = {}
var decision_signatures: Dictionary = {}
var policy_signatures: Dictionary = {}
var per_policy: Dictionary = {}
var errors: Array[String] = []
var run_times_ms: Array[float] = []
var total_moves: int = 0
var total_comparisons: int = 0
var total_local_queries: int = 0
var total_global_queries: int = 0
var total_nav_nodes: int = 0
var total_mismatches: int = 0
var journal: FileAccess = null


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if not _arguments():
		print(JSON.stringify({"measurement_completed": false, "errors": errors}))
		quit(1)
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(DATA_PATH))
	if not (parsed is Dictionary):
		errors.append("Cannot read campaign canonical JSON.")
		print(JSON.stringify({"measurement_completed": false, "errors": errors}))
		quit(1)
		return
	canonical = parsed
	var checked: Dictionary = VariantBuilder.validate(canonical)
	if not bool(checked.get("ok", false)):
		errors.append("Canonical validation failed: " + str(checked))
		print(JSON.stringify({"measurement_completed": false, "errors": errors}))
		quit(1)
		return
	journal = FileAccess.open(output_path + ".journal.jsonl", FileAccess.WRITE)
	if journal == null:
		errors.append("Cannot open the run journal; exploration did not start: " + output_path)
		print(JSON.stringify({"measurement_completed": false, "errors": errors}))
		quit(1)
		return
	var began: int = Time.get_ticks_usec()
	journal.store_string(JSON.stringify({"kind": "header", "engine_pid": OS.get_process_id(), "source_data_sha256": FileAccess.get_sha256(DATA_PATH),
		"master_layout_seed": VariantBuilder.normalize_seed(master_seed), "master_policy_seed": "%08x" % master_policy_seed,
		"start_index": start_index, "requested_runs": runs, "policies": DEFINITIONS}) + "\n")
	journal.flush()
	for offset: int in range(runs):
		if stop_file_requested and FileAccess.file_exists(stop_file_path):
			stopped_at_case_boundary = true
			journal.store_string(JSON.stringify({"kind": "coordinated_stop", "before_absolute_run_index": start_index + offset,
				"completed_runs": run_records.size(), "stopped_at_case_boundary": true}) + "\n")
			break
		var record: Dictionary = _one_run(start_index + offset)
		run_records.append(record)
		journal.store_string(JSON.stringify({"kind": "run", "record": record}) + "\n")
		if str(record.get("outcome", "")) != "won":
			failure_seeds.append({"index": record.index, "policy": record.policy, "layout_seed": record.layout_seed,
				"policy_seed": record.policy_seed, "layout_hash": record.get("layout_hash", ""),
				"outcome": record.outcome, "decision_signature": record.get("decision_signature", "")})
		if progress_every > 0 and (offset + 1) % progress_every == 0:
			journal.flush()
			print(JSON.stringify({"progress_completed": offset + 1, "requested_runs": runs,
				"elapsed_seconds": float(Time.get_ticks_usec() - began) / 1000000.0,
				"last_policy": record.policy, "last_outcome": record.outcome}))
	journal.flush()
	journal.close()
	var elapsed_ms: float = float(Time.get_ticks_usec() - began) / 1000.0
	var report: Dictionary = {
		"schema_version": 1, "scope": "21-floor logical/state exploration only; no browser, visuals, human play or hours-of-play claim",
		"measurement_completed": run_records.size() == runs, "invariants_passed": errors.is_empty() and total_mismatches == 0,
		"stop_control_enabled": stop_file_requested, "stopped_at_case_boundary": stopped_at_case_boundary,
		"next_unstarted_absolute_run_index": start_index + run_records.size(),
		"engine": Engine.get_version_info(), "source_data_sha256": FileAccess.get_sha256(DATA_PATH),
		"base_rules_sha256": FileAccess.get_sha256("res://scripts/base_rules.gd"),
		"variant_sha256": FileAccess.get_sha256("res://scripts/campaign_variant.gd"),
		"navigation_sha256": FileAccess.get_sha256("res://scripts/campaign_navigation.gd"),
		"simulation_sha256": FileAccess.get_sha256("res://tests/simulate_campaign.gd"),
		"variant_spec": VariantBuilder.SPEC, "layout_draws_per_run": 43, "respawn_actions": 0,
		"master_layout_seed": VariantBuilder.normalize_seed(master_seed), "master_policy_seed": "%08x" % master_policy_seed,
		"seed_derivation": "layout=(master_layout_seed + absolute_run_index*104729) uint32, then VariantBuilder.normalize_seed; policy=(master_policy_seed XOR layout_seed_uint32 XOR ((absolute_run_index+1)*2654435761 uint32)) uint32, zero replaced by 6d2b79f5",
		"policy_rng": "Independent local xorshift32 state, never passed to layout generation or controlled-respawn sequence; scored-policy tie perturbation <=0.001",
		"start_index": start_index, "requested_runs": runs, "completed_runs": run_records.size(),
		"local_floor_horizon": horizon, "policies": DEFINITIONS, "max_decisions": max_decisions,
		"local_global_contract": "Local frontiers are never complete. No local actions triggers one full global BFS. Only complete global BFS with zero legal resource actions is dead_end. It is not a general all-future-state unsatisfiability proof.",
		"elapsed_ms": elapsed_ms, "mean_ms_per_run": elapsed_ms / maxf(1.0, float(run_records.size())),
		"run_time_p50_ms": _percentile(run_times_ms, 0.50), "run_time_p95_ms": _percentile(run_times_ms, 0.95),
		"navigation_moves": total_moves, "preview_actual_comparisons": total_comparisons,
		"preview_actual_mismatches": total_mismatches,
		"local_frontier_queries": total_local_queries, "global_frontier_queries": total_global_queries,
		"navigation_nodes_processed": total_nav_nodes,
		"distinct_decision_sequences": decision_signatures.size(),
		"decision_signature_scope": "SHA256 of the ordered chosen frontier-option IDs, including shop/offer IDs; coordinates and automatic navigation are excluded",
		"per_policy": per_policy, "runs": run_records, "failure_seeds": failure_seeds,
		"example_limit_per_policy_outcome": example_limit, "examples": examples, "errors": errors,
		"journal_path": output_path + ".journal.jsonl", "journal_sha256": FileAccess.get_sha256(output_path + ".journal.jsonl"),
	}
	var report_file: FileAccess = FileAccess.open(output_path, FileAccess.WRITE)
	if report_file == null:
		errors.append("Cannot write full final report: " + output_path)
		report.invariants_passed = false
	else:
		report_file.store_string(JSON.stringify(report, "  ") + "\n")
		report_file.close()
	print(JSON.stringify({"measurement_completed": report.measurement_completed, "invariants_passed": report.invariants_passed,
		"stopped_at_case_boundary": stopped_at_case_boundary,
		"requested_runs": runs, "completed_runs": run_records.size(), "elapsed_ms": elapsed_ms,
		"mean_ms_per_run": report.mean_ms_per_run, "run_time_p50_ms": report.run_time_p50_ms,
		"run_time_p95_ms": report.run_time_p95_ms, "per_policy": per_policy,
		"distinct_decision_sequences": decision_signatures.size(), "preview_actual_mismatches": total_mismatches,
		"navigation_moves": total_moves, "preview_actual_comparisons": total_comparisons,
		"local_frontier_queries": total_local_queries, "global_frontier_queries": total_global_queries,
		"failure_seed_count": failure_seeds.size(), "error_count": errors.size(), "full_report_file": output_path}, "  "))
	# A coordinated cancellation is not a test failure. Callers must inspect
	# measurement_completed rather than treating exit 0 as all cases completed.
	quit(0 if bool(report.invariants_passed) and (bool(report.measurement_completed) or stopped_at_case_boundary) else 1)


func _one_run(index: int) -> Dictionary:
	var began: int = Time.get_ticks_usec()
	var policy: String = POLICIES[index % POLICIES.size()]
	var layout_seed: String = VariantBuilder.normalize_seed((master_seed + index * 104729) & MASK)
	var initial_policy_seed: int = (master_policy_seed ^ layout_seed.hex_to_int() ^ (((index + 1) * 2654435761) & MASK)) & MASK
	if initial_policy_seed == 0:
		initial_policy_seed = 0x6d2b79f5
	policy_rng = initial_policy_seed
	policy_draws = 0
	var generated: Dictionary = VariantBuilder.generate(canonical, layout_seed)
	var record: Dictionary = {"index": index, "policy": policy, "layout_seed": layout_seed,
		"policy_seed": "%08x" % initial_policy_seed, "outcome": "variant_error"}
	if not bool(generated.get("ok", false)):
		errors.append("Variant generation failed at run %d: %s" % [index, str(generated)])
		record["error"] = generated
		return record
	var game = BaseRules.new("")
	game.data = generated.data
	game.reset()
	var prepared: Dictionary = Navigation.prepare(game)
	var generation_us: int = Time.get_ticks_usec() - began
	var initial_state: Dictionary = game.snapshot()
	var trace: Array = []
	var chosen_ids: Array[String] = []
	var last_frontier: Dictionary = {}
	var outcome: String = "step_limit"
	var run_moves: int = 0
	var run_comparisons: int = 0
	var local_queries: int = 0
	var global_queries: int = 0
	var nav_nodes: int = 0
	var frontier_us: int = 0
	var execution_us: int = 0
	var gate_preparations: int = 0
	var record_trace: bool = _needs_example_for_policy(policy)
	for decision: int in range(max_decisions):
		if bool(game.state.get("won", false)):
			outcome = "won"
			break
		var scan_began: int = Time.get_ticks_usec()
		var frontier: Dictionary = Navigation.frontier_local(game, horizon, 0, false, prepared)
		local_queries += 1
		nav_nodes += int(frontier.get("reachable", 0))
		var view: String = "local"
		if frontier.get("options", []).is_empty():
			frontier = Navigation.frontier(game, 0, false, prepared)
			global_queries += 1
			nav_nodes += int(frontier.get("reachable", 0))
			view = "global_fallback"
		frontier_us += Time.get_ticks_usec() - scan_began
		last_frontier = frontier
		if not frontier.get("errors", []).is_empty():
			outcome = "navigation_error"
			errors.append("Run %d navigation errors: %s" % [index, str(frontier.errors)])
			break
		var options: Array = frontier.get("options", [])
		if options.is_empty():
			outcome = "dead_end" if view == "global_fallback" and bool(frontier.get("complete", false)) else "unknown_navigation_incomplete"
			break
		var choice: Dictionary = _choose(game, policy, frontier)
		if bool(choice.get("armor_gate_preparation", false)):
			gate_preparations += 1
		var option: Dictionary = choice.option
		var before: Dictionary = _budget(game.state) if record_trace else {}
		var execute_began: int = Time.get_ticks_usec()
		var executed: Dictionary = Navigation.execute(game, option.path)
		execution_us += Time.get_ticks_usec() - execute_began
		run_moves += int(executed.get("moves", 0))
		run_comparisons += int(executed.get("preview_comparisons", 0))
		chosen_ids.append(str(option.id))
		if record_trace:
			trace.append({"decision": decision, "view": view, "chosen_id": option.id, "kind": option.kind,
				"observed_armor_gate_preparation": choice.get("armor_gate_preparation", false),
				"path": option.path, "preview": option.get("preview", {}),
				"before": before, "after": _budget(game.state), "execute_result": executed.duplicate(true)})
		else:
			# Preserve the full executable action sequence for a first rare error
			# without copying every state vector after routine example slots fill.
			trace.append({"decision": decision, "view": view, "chosen_id": option.id, "kind": option.kind, "path": option.path})
		if not bool(executed.get("ok", false)):
			var message: String = str(executed.get("error", ""))
			if message.to_lower().contains("preview"):
				total_mismatches += 1
				outcome = "preview_mismatch"
			else:
				outcome = "execute_error"
			errors.append("Run %d execution failure: %s" % [index, str(executed)])
			break
	if bool(game.state.get("won", false)):
		outcome = "won"
	var elapsed_ms: float = float(Time.get_ticks_usec() - began) / 1000.0
	run_times_ms.append(elapsed_ms)
	var signature: String = "\n".join(chosen_ids).sha256_text()
	decision_signatures[signature] = true
	record.merge({"outcome": outcome, "layout_hash": generated.transformed_sha256,
		"canonical_hash": generated.canonical_sha256, "resolved_start": generated.resolved_start,
		"layout_draw_count": generated.draw_count, "layout_seed_after": generated.seed,
		"policy_rng_final": "%08x" % policy_rng, "policy_draws": policy_draws,
		"decision_count": chosen_ids.size(), "decision_signature": signature,
		"final": _budget(game.state), "navigation_moves": run_moves, "preview_actual_comparisons": run_comparisons,
		"local_queries": local_queries, "global_queries": global_queries, "nav_nodes": nav_nodes,
		"armor_gate_preparations": gate_preparations,
		"elapsed_ms": elapsed_ms, "variant_prepare_ms": float(generation_us) / 1000.0,
		"frontier_ms": float(frontier_us) / 1000.0, "execution_ms": float(execution_us) / 1000.0}, true)
	_update_policy(policy, record, signature)
	total_moves += run_moves
	total_comparisons += run_comparisons
	total_local_queries += local_queries
	total_global_queries += global_queries
	total_nav_nodes += nav_nodes
	var bucket: String = policy + "/" + outcome
	if not examples.has(bucket):
		examples[bucket] = []
	if examples[bucket].size() < example_limit:
		var example: Dictionary = {"record": record.duplicate(true), "initial_state": initial_state,
			"trace_detail": "paths_and_budgets" if record_trace else "complete_paths_only",
			"decisions": trace, "final_state": game.snapshot(), "floor_mirrors": generated.mirrors,
			"terminal_frontier": {"scope": last_frontier.get("scope", ""), "complete": last_frontier.get("complete", false),
				"queue_exhausted": last_frontier.get("queue_exhausted", false), "reachable": last_frontier.get("reachable", 0),
				"legal_resource_actions": last_frontier.get("options", []).size(),
				"reason": last_frontier.get("reason", ""), "blocked": last_frontier.get("blocked", []),
				"shop_offers": last_frontier.get("shop_offers", []), "errors": last_frontier.get("errors", [])}}
		examples[bucket].append(example)
		journal.store_string(JSON.stringify({"kind": "example", "bucket": bucket, "example": example}) + "\n")
	return record


func _choose(game, policy: String, frontier: Dictionary) -> Dictionary:
	var options: Array = frontier.options
	if policy == "randomized":
		return {"option": options[_policy_random_index(options.size())], "armor_gate_preparation": false}
	var minimum_breakthrough: int = 2147483647
	var largest_observed_cost: int = 0
	for boundary: Dictionary in frontier.get("blocked", []):
		if boundary.get("kind", "") != "enemy":
			continue
		var combat: Dictionary = boundary.get("combat", {})
		if int(combat.get("hit", 0)) <= 0:
			# Only inspect the object actually present on the observed frontier,
			# never an enemy in an unreachable future room or floor.
			for item: Dictionary in game.data.floors[int(boundary.floor_index)].objects:
				if str(item.id) == str(boundary.id):
					minimum_breakthrough = mini(minimum_breakthrough, int(game.data.enemies[item.type]["def"]) + 1 - int(game.state.atk))
					break
		largest_observed_cost = maxi(largest_observed_cost, int(combat.get("damage", 0)))
	var best: Dictionary = options[0]
	var best_score: float = -INF
	var best_gate: bool = false
	for option: Dictionary in options:
		var gate: bool = option.kind == "buy" and option.get("offer", {}).get("kind", "") == "atk" and int(option.get("offer", {}).get("amount", 0)) >= minimum_breakthrough
		var score: float = 10000.0 if gate else _score(game, policy, option, largest_observed_cost)
		score -= float(option.get("path", []).size()) * 0.00001
		score += float(_next_policy32() % 1000) / 1000000.0
		if score > best_score:
			best_score = score
			best = option
			best_gate = gate
	return {"option": best, "armor_gate_preparation": best_gate}


func _score(game, policy: String, option: Dictionary, observed_cost: int) -> float:
	var kind: String = str(option.kind)
	var hp: int = int(game.state.hp)
	var floor_number: int = int(game.state.floor) + 1
	if kind == "key":
		return 940.0
	if kind == "gold":
		return 880.0
	if kind == "atk":
		return 980.0 if policy == "attack" else 920.0
	if kind == "def":
		return 980.0 if policy == "defense" else 910.0
	if kind == "potion":
		return 900.0 if hp < 200 + floor_number * 15 else 850.0
	if kind == "door":
		return 540.0 if policy == "resource" else 360.0
	if kind == "enemy":
		var damage: int = int(option.get("preview", {}).get("damage", 0))
		var reward: int = int(game.data.enemies[option.item.type].get("gold", 0))
		var penalty: float = 0.35 if policy == "attack" else (0.55 if policy == "resource" else 1.5)
		return 430.0 + float(reward) * 0.25 - float(damage) * penalty
	if kind == "buy":
		var offered_kind: String = str(option.offer.kind)
		if offered_kind == "atk":
			return 960.0 if policy == "attack" else (680.0 if policy == "cautious" else 720.0)
		if offered_kind == "def":
			return 960.0 if policy == "defense" else (700.0 if policy == "cautious" else 650.0)
		if offered_kind == "potion":
			var threshold: int = maxi(120 + floor_number * 15, observed_cost * (2 if policy == "cautious" else 1))
			return 800.0 if hp < threshold else 40.0
	return 0.0


func _update_policy(policy: String, record: Dictionary, signature: String) -> void:
	if not per_policy.has(policy):
		per_policy[policy] = {"runs": 0, "outcomes": {}, "distinct_decision_sequences": 0,
			"min_final_hp": int(record.final.hp), "max_final_hp": int(record.final.hp),
			"min_final_gold": int(record.final.gold), "max_final_gold": int(record.final.gold),
			"sum_decisions": 0, "sum_elapsed_ms": 0.0, "armor_gate_preparations": 0}
		policy_signatures[policy] = {}
	var stats: Dictionary = per_policy[policy]
	stats.runs += 1
	stats.outcomes[record.outcome] = int(stats.outcomes.get(record.outcome, 0)) + 1
	policy_signatures[policy][signature] = true
	stats.distinct_decision_sequences = policy_signatures[policy].size()
	stats.min_final_hp = mini(int(stats.min_final_hp), int(record.final.hp))
	stats.max_final_hp = maxi(int(stats.max_final_hp), int(record.final.hp))
	stats.min_final_gold = mini(int(stats.min_final_gold), int(record.final.gold))
	stats.max_final_gold = maxi(int(stats.max_final_gold), int(record.final.gold))
	stats.sum_decisions += int(record.decision_count)
	stats.sum_elapsed_ms += float(record.elapsed_ms)
	stats.armor_gate_preparations += int(record.armor_gate_preparations)


func _needs_example_for_policy(policy: String) -> bool:
	for outcome: String in ["won", "dead_end"]:
		if examples.get(policy + "/" + outcome, []).size() < example_limit:
			return true
	return false


func _budget(state: Dictionary) -> Dictionary:
	return {"floor": int(state.floor) + 1, "pos": state.pos.duplicate(), "hp": int(state.hp),
		"atk": int(state.atk), "def": int(state.def), "gold": int(state.gold),
		"keys": state["keys"].duplicate(true), "cleared_count": state.cleared.size(),
		"purchases": state.purchases.duplicate(true), "won": bool(state.won)}


func _next_policy32() -> int:
	policy_rng = (policy_rng ^ ((policy_rng << 13) & MASK)) & MASK
	policy_rng = (policy_rng ^ (policy_rng >> 17)) & MASK
	policy_rng = (policy_rng ^ ((policy_rng << 5) & MASK)) & MASK
	policy_draws += 1
	return policy_rng


func _policy_random_index(count: int) -> int:
	# Rejection avoids a modulo bias for the requested option count. This local
	# stream never enters VariantBuilder.generate() or any respawn method.
	var limit: int = 4294967296 - (4294967296 % count)
	var value: int = _next_policy32()
	while value >= limit:
		value = _next_policy32()
	return value % count


func _percentile(values: Array[float], fraction: float) -> float:
	if values.is_empty():
		return 0.0
	var ordered: Array[float] = values.duplicate()
	ordered.sort()
	return ordered[clampi(ceili(float(ordered.size()) * fraction) - 1, 0, ordered.size() - 1)]


func _arguments() -> bool:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--runs="):
			runs = int(argument.trim_prefix("--runs="))
		elif argument.begins_with("--start-index="):
			start_index = int(argument.trim_prefix("--start-index="))
		elif argument.begins_with("--seed="):
			master_seed = _seed_number(argument.trim_prefix("--seed="))
		elif argument.begins_with("--policy-seed="):
			master_policy_seed = _seed_number(argument.trim_prefix("--policy-seed="))
		elif argument.begins_with("--max-decisions="):
			max_decisions = int(argument.trim_prefix("--max-decisions="))
		elif argument.begins_with("--examples="):
			example_limit = int(argument.trim_prefix("--examples="))
		elif argument.begins_with("--horizon="):
			horizon = int(argument.trim_prefix("--horizon="))
		elif argument.begins_with("--progress-every="):
			progress_every = int(argument.trim_prefix("--progress-every="))
		elif argument.begins_with("--output="):
			output_path = argument.trim_prefix("--output=")
		elif argument.begins_with("--stop-file="):
			stop_file_requested = true
			stop_file_path = argument.trim_prefix("--stop-file=").replace("\\", "/").simplify_path()
		else:
			errors.append("Unknown argument: " + argument)
	if runs < 1 or runs > 100000 or start_index < 0 or max_decisions < 1 or example_limit < 1 or horizon < 0 or horizon > 20 or master_seed < 0 or master_policy_seed < 0:
		errors.append("Invalid run count, index, seed, horizon, decision limit or retained-example limit.")
	if stop_file_requested and (stop_file_path.is_empty() or not stop_file_path.is_absolute_path() or stop_file_path.begins_with("res://") or stop_file_path.begins_with("user://")):
		errors.append("Stop-file control requires an absolute task filesystem path; the path is omitted from reports.")
	if master_seed >= 0:
		master_seed = VariantBuilder.normalize_seed(master_seed).hex_to_int()
	if master_policy_seed == 0:
		master_policy_seed = (master_seed ^ 0xa511e9b3) & MASK
	return errors.is_empty()


func _seed_number(word: String) -> int:
	var value: int = -1
	if word.begins_with("0x"):
		var hexadecimal: String = word.trim_prefix("0x")
		value = hexadecimal.hex_to_int() if hexadecimal.is_valid_hex_number() else -1
	elif word.is_valid_int():
		value = int(word)
	elif word.length() == 8 and word.is_valid_hex_number():
		value = word.hex_to_int()
	return value if value >= 0 and value <= MASK else -1
