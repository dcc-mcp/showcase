extends "res://tests/simulate.gd"
## New evidence only: the frozen frontier-v1 harness and three-floor rules/data
## remain byte-identical. Seed affects the policy RNG, not this fixed map.

var source_report: String = ""
var classification_output: String = "user://stairkeep-slice-classification.json"
var classification_errors: Array = []


func _initialize() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--report="):
			source_report = argument.trim_prefix("--report=")
		elif argument.begins_with("--output="):
			classification_output = argument.trim_prefix("--output=")
	if source_report.is_empty() or not FileAccess.file_exists(source_report):
		push_error("Pass --report=<frozen simulation-10000.json>; the old report is read-only.")
		quit(2)
		return
	var parsed := JSON.new()
	if parsed.parse(FileAccess.get_file_as_string(source_report)) != OK or not (parsed.data is Dictionary):
		push_error("Frozen report could not be parsed.")
		quit(2)
		return
	var baseline: Dictionary = parsed.data
	var game = Rules.new()
	var binding: Dictionary = {
		"frozen_report_sha256":FileAccess.get_sha256(source_report),
		"rules_sha256":FileAccess.get_sha256("res://scripts/rules.gd"),
		"data_sha256":FileAccess.get_sha256("res://data/levels.json"),
		"frozen_harness_sha256":FileAccess.get_sha256("res://tests/simulate.gd"),
		"classifier_sha256":FileAccess.get_sha256("res://tests/classify_slice.gd"),
		"engine":Engine.get_version_info().string,
	}
	if game.state.is_empty() or str(baseline.get("harness","")) != VERSION or str(baseline.get("rule_source_sha256","")) != binding.rules_sha256 or str(baseline.get("source_data_sha256","")) != binding.data_sha256 or str(baseline.get("engine","")) != binding.engine:
		push_error("The frozen report's rule/data/engine/harness version does not match this reproduction.")
		quit(2)
		return
	if not baseline.get("invariant_errors",[]).is_empty() or not baseline.get("policies",{}).has("randomized"):
		push_error("This classifier expects the recorded invariant-clean randomized-policy report.")
		quit(2)
		return
	_index(game.data)
	var policy: String = "randomized"
	var reproduced: Dictionary = {"runs":0,"won":0,"dead_end":0,"limit":0,"error":0}
	var failures: Array = []
	var started: int = Time.get_ticks_msec()
	var initial: Dictionary = game.snapshot()
	var requested: int = int(baseline.completed_runs)
	var seed_base: int = int(baseline.master_seed)
	for run_index: int in range(requested):
		if POLICIES[run_index % POLICIES.size()] != policy:
			continue
		game.reset()
		var run_seed: int = seed_base + run_index * 104729
		var rng := RandomNumberGenerator.new()
		rng.seed = run_seed
		var trace: Array = []
		var status: String = "limit"
		for decision_index: int in range(decision_limit):
			if bool(game.state.won):
				status = "won"
				break
			var frontier: Dictionary = _frontier(game)
			if frontier.options.is_empty():
				status = "dead_end"
				break
			# Exactly the frozen selector/RNG calls, with no extra random draws.
			var choice: Dictionary = _choose(game,frontier.options,policy,rng)
			var before: Dictionary = _budget(game.state)
			var executed: Dictionary = _execute(game,choice.path)
			trace.append({"target":choice.id,"kind":choice.kind,"actions":choice.path.duplicate(true),"before":before,"after":_budget(game.state),"execution":executed})
			if not bool(executed.ok) or not _resources_valid(game.state):
				status = "error"
				classification_errors.append({"run_index":run_index,"seed":run_seed,"error":"replay invariant or action failure","execution":executed})
				break
			if bool(game.state.won):
				status = "won"
				break
		reproduced.runs += 1
		reproduced[status] += 1
		if status == "dead_end":
			var terminal: Dictionary = game.snapshot()
			var proof: Dictionary = _terminal_proof(game)
			var route_index: int = failures.size() % game.data.validated_routes.size()
			var witness: Dictionary = _initial_witness(game.data.validated_routes[route_index],run_seed)
			var consistent: bool = bool(proof.complete) and int(proof.legal_resource_actions) == 0 and bool(witness.won)
			if not consistent:
				classification_errors.append({"run_index":run_index,"seed":run_seed,"error":"terminal proof or initial witness failed","proof":proof,"witness":witness})
			var sequence: Array = []
			for event: Dictionary in trace:
				sequence.append(event.target)
			failures.append({
				"run_index":run_index,"seed":run_seed,"policy":policy,
				"classification":"policy_reached_unsalvageable_state" if consistent else "unknown",
				"initial_solvable":bool(witness.won),"terminal_no_winning_suffix":bool(proof.complete) and int(proof.legal_resource_actions) == 0,
				"initial_state":initial,"terminal_state":terminal,"decision_sequence":sequence,"sequence_sha256":JSON.stringify(sequence).sha256_text(),"trace":trace,
				"terminal_navigation_proof":proof,"same_seed_initial_witness":witness,
			})
		if int(reproduced.runs) % 250 == 0:
			print("CLASSIFICATION_PROGRESS " + JSON.stringify({"replayed":reproduced.runs,"dead_ends":failures.size(),"elapsed_ms":Time.get_ticks_msec()-started}))
	var expected: Dictionary = baseline.policies[policy]
	var counts_match: bool = true
	for field: String in ["runs","won","dead_end","limit","error"]:
		counts_match = counts_match and int(expected[field]) == int(reproduced[field])
	if not counts_match:
		classification_errors.append({"error":"randomized replay counts differ from frozen report","expected":expected,"actual":reproduced})
	var first_sample_matches: bool = false
	if not failures.is_empty() and baseline.examples.has("randomized/dead_end"):
		var old_sample: Dictionary = baseline.examples["randomized/dead_end"]
		first_sample_matches = int(old_sample.run_index) == int(failures[0].run_index) and int(old_sample.seed) == int(failures[0].seed) and _normalized_state(old_sample.state) == _normalized_state(failures[0].terminal_state) and old_sample.sequence == failures[0].decision_sequence
	if not first_sample_matches:
		classification_errors.append({"error":"the first retained frozen failure sample was not exactly reproduced"})
	var report: Dictionary = {
		"schema_version":1,"suite":"frozen-three-floor-policy-failure-classification/v1","binding":binding,
			"master_seed":seed_base,"policy_assignment":"POLICIES[run_index % 5]","run_seed_formula":"master_seed + run_index * 104729",
			"replay_scope":"Only the 2,000 randomized-policy runs; the source report records no failures in the other 8,000 runs. The frozen report is not edited.",
			"expected_randomized_counts":expected,"reproduced_randomized_counts":reproduced,"counts_match":counts_match,"first_frozen_failure_sample_matches":first_sample_matches,
			"failed_runs":failures,"errors":classification_errors,"elapsed_ms":Time.get_ticks_msec()-started,
			"conclusion":"Each retained failure has two independent facts: its fixed canonical initial state has a real-core winning witness, while the reached terminal state has no legal resource-changing action after exhaustive navigation BFS. A bad continuation does not make the generated initial map unsatisfiable.",
			"seed_scope":"The frozen three-floor game has no runtime map generation. These seeds belong to the randomized policy selector. The initial witness is replayed with the same recorded seed context but deliberately follows a different, explicit decision sequence.",
			"not_claimed":["No complete enumeration of all reachable resource states.","No universal guarantee that every player policy succeeds.","No evidence for the later 21-floor campaign, mirrored variants, browser interaction, or hours of play."],
	}
	var file: FileAccess = FileAccess.open(classification_output,FileAccess.WRITE)
	if file == null:
		push_error("Could not write the new classification output.")
		quit(2)
		return
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("CLASSIFICATION_RESULT " + JSON.stringify({"report":classification_output,"reproduced":reproduced,"failed_runs_saved":failures.size(),"counts_match":counts_match,"first_sample_matches":first_sample_matches,"errors":classification_errors.size()}))
	quit(0 if classification_errors.is_empty() else 1)


func _initial_witness(route: Dictionary, run_seed: int) -> Dictionary:
	var game = Rules.new()
	var events: Array = []
	var error: String = ""
	for entry: Dictionary in route.ledger:
		var event_id: String = str(entry.event)
		var frontier: Dictionary = _frontier(game)
		var chosen: Dictionary = {}
		for option: Dictionary in frontier.options:
			if (event_id.begins_with("buy:") and option.kind == "buy" and str(option.offer.id) == event_id.trim_prefix("buy:")) or str(option.id) == event_id:
				chosen = option
				break
		if chosen.is_empty():
			error = "Witness event is not a legal reachable frontier: " + event_id
			break
		var before: Dictionary = _budget(game.state)
		var executed: Dictionary = _execute(game,chosen.path)
		events.append({"event":event_id,"actions":chosen.path.duplicate(true),"before":before,"after":_budget(game.state),"execution":executed})
		if not bool(executed.ok) or not _budget_matches(game.state,entry.state):
			error = "Witness action or ledger differs at " + event_id
			break
	return {"same_recorded_seed":run_seed,"route":route.name,"won":error.is_empty() and bool(game.state.won),"final_state":game.snapshot(),"events":events,"error":error}


func _budget_matches(actual: Dictionary, expected: Dictionary) -> bool:
	for field: String in ["hp","atk","def","gold"]:
		if int(actual[field]) != int(expected[field]):
			return false
	for color: String in expected["keys"]:
		if int(actual["keys"][color]) != int(expected["keys"][color]):
			return false
	return true


func _normalized_state(state: Dictionary) -> Dictionary:
	var result: Dictionary = state.duplicate(true)
	for field: String in ["floor","hp","atk","def","gold"]:
		result[field] = int(result[field])
	result.pos = [int(result.pos[0]),int(result.pos[1])]
	for color: String in result["keys"]:
		result["keys"][color] = int(result["keys"][color])
	for id: String in result.purchases:
		result.purchases[id] = int(result.purchases[id])
	return result


func _terminal_proof(game: RefCounted) -> Dictionary:
	var cleared: Dictionary = {}
	for id: String in game.state.cleared:
		cleared[id] = true
	var start := Vector3i(int(game.state.floor),int(game.state.pos[0]),int(game.state.pos[1]))
	var queue: Array[Vector3i] = [start]
	var visited: Dictionary = {start:true}
	var nodes: Array = []
	var edges: Array = []
	var blocked: Dictionary = {}
	var shops: Dictionary = {}
	var legal_count: int = 0
	while not queue.is_empty():
		var node: Vector3i = queue.pop_front()
		nodes.append([node.x,node.y,node.z])
		var here: Dictionary = _item_at(node,cleared)
		if here.get("kind","") == "shop":
			shops[str(here.id)] = here
		if here.get("kind","") == "stairs":
			var target: Vector3i = _stair_target(here)
			edges.append({"from":[node.x,node.y,node.z],"to":[target.x,target.y,target.z],"action":"use_stairs"})
			if not visited.has(target):
				visited[target] = true
				queue.append(target)
		for delta: Vector2i in DELTAS:
			var next := Vector3i(node.x,node.y+delta.x,node.z+delta.y)
			if not topology.has(next):
				continue
			var item: Dictionary = _item_at(next,cleared)
			var kind: String = str(item.get("kind",""))
			if kind in ["","shop","stairs"]:
				if kind == "shop":
					shops[str(item.id)] = item
				var destination: Vector3i = _stair_target(item) if kind == "stairs" else next
				edges.append({"from":[node.x,node.y,node.z],"to":[destination.x,destination.y,destination.z],"action":"move","dx":delta.x,"dy":delta.y})
				if not visited.has(destination):
					visited[destination] = true
					queue.append(destination)
				continue
			var id: String = str(item.id)
			if not blocked.has(id):
				var record: Dictionary = {"id":id,"kind":kind,"floor_index":next.x,"cell":[next.y,next.z],"approachable_from":[],"legal":false}
				if kind == "enemy":
					record["combat_preview"] = game.combat(game.data.enemies[item.type])
					record.legal = bool(record.combat_preview.win)
					record["reason"] = str(record.combat_preview.reason)
				elif kind == "door":
					record["key_color"] = item.type
					record["keys_owned"] = int(game.state["keys"].get(item.type,0))
					record.legal = int(record.keys_owned) >= 1
					record["reason"] = "Requires one matching key."
				else:
					record.legal = kind in ["key","potion","atk","def","gold"]
					record["reason"] = "Reachable resource." if bool(record.legal) else "Unsupported object kind."
				if bool(record.legal):
					legal_count += 1
				blocked[id] = record
			blocked[id].approachable_from.append([node.x,node.y,node.z])
	var shop_proof: Array = []
	for shop_id: String in shops:
		var item: Dictionary = shops[shop_id]
		for offer: Dictionary in game.data.shops[item.type].offers:
			var purchase_key: String = shop_id+"/"+str(offer.id)
			var bought: int = int(game.state.purchases.get(purchase_key,0))
			var in_stock: bool = bought < int(offer.get("limit",1))
			var affordable: bool = int(game.state.gold) >= int(offer.cost)
			var legal: bool = in_stock and affordable
			legal_count += 1 if legal else 0
			shop_proof.append({"shop":shop_id,"offer":offer.id,"price":int(offer.cost),"gold_owned":int(game.state.gold),"bought":bought,"limit":int(offer.get("limit",1)),"affordable":affordable,"in_stock":in_stock,"legal":legal})
	var frozen_frontier: Dictionary = _frontier(game)
	var agrees: bool = int(frozen_frontier.reachable) == visited.size() and int(frozen_frontier.options.size()) == legal_count
	return {"complete":agrees,"queue_exhausted":true,"reachable_count":visited.size(),"reachable_nodes_floor_x_y":nodes,"navigation_edges":edges,"blocked_frontier_objects":blocked.values(),"reachable_shop_offers":shop_proof,"legal_resource_actions":legal_count,"frozen_frontier_options":frozen_frontier.options.size(),"frozen_frontier_agrees":agrees,"remaining_objects":_remaining(game),"proof_scope":"Ordinary movement, stairs and purchases in this exact reached state. Every navigation edge preserves resources; every boundary resource action is illegal. Therefore no winning suffix exists without restart, save editing, or a future rule change."}
