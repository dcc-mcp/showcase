class_name CampaignSolver
extends SceneTree
## A bounded, three-valued ordinary-continuation solver. No battle formula here.
## Static solve() is callable from tests without constructing another SceneTree.

const Navigation = preload("res://scripts/campaign_navigation.gd")
const Campaign = preload("res://scripts/campaign_rules.gd")
const SOLVER_VERSION: String = "campaign-frontier-search/v1"


func _initialize() -> void:
	var data_path: String = "res://data/levels21.json"
	var output: String = "user://stairkeep-campaign-solver.json"
	var seed_value: int = 20261025
	var max_expanded: int = 5000
	var max_msec: int = 15000
	var max_states: int = 20000
	var snapshot_path: String = ""
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--data="): data_path = arg.trim_prefix("--data=")
		elif arg.begins_with("--output="): output = arg.trim_prefix("--output=")
		elif arg.begins_with("--seed="): seed_value = int(arg.trim_prefix("--seed="))
		elif arg.begins_with("--max-expanded="): max_expanded = int(arg.trim_prefix("--max-expanded="))
		elif arg.begins_with("--max-ms="): max_msec = int(arg.trim_prefix("--max-ms="))
		elif arg.begins_with("--max-states="): max_states = int(arg.trim_prefix("--max-states="))
		elif arg.begins_with("--snapshot="): snapshot_path = arg.trim_prefix("--snapshot=")
	var game = Campaign.new()
	var loaded: Dictionary = game.load_campaign(data_path,seed_value)
	if not bool(loaded.get("ok",false)):
		push_error("Campaign data could not be loaded: " + str(loaded))
		quit(2)
		return
	if not snapshot_path.is_empty():
		var parsed := JSON.new()
		if parsed.parse(FileAccess.get_file_as_string(snapshot_path)) != OK or not (parsed.data is Dictionary) or not game.restore_snapshot(parsed.data):
			push_error("The supplied campaign snapshot was not accepted.")
			quit(2)
			return
	var result: Dictionary = solve(game,{"max_expanded":max_expanded,"max_msec":max_msec,"max_states":max_states})
	var file: FileAccess = FileAccess.open(output,FileAccess.WRITE)
	if file == null:
		push_error("Could not write solver report.")
		quit(2)
		return
	file.store_string(JSON.stringify(result,"  "))
	file.close()
	print("CAMPAIGN_SOLVER_RESULT " + JSON.stringify({"result":result.result,"reason":result.reason,"expanded":result.expanded,"stored_states":result.stored_states,"dominance_pruned":result.dominance_pruned,"report":output}))
	# Unknown is a correctly bounded result, not unsatisfiable or a runner crash.
	quit(0 if result.result in ["witness","unsatisfiable","unknown"] else 1)


static func solve(game: RefCounted, configuration: Dictionary = {}) -> Dictionary:
	var started: int = Time.get_ticks_msec()
	var limits: Dictionary = {"max_expanded":int(configuration.get("max_expanded",5000)),"max_msec":int(configuration.get("max_msec",15000)),"max_states":int(configuration.get("max_states",20000)),"navigation_max_nodes":int(configuration.get("navigation_max_nodes",0))}
	var report: Dictionary = {
		"schema_version":1,"solver":SOLVER_VERSION,"result":"unknown","reason":"Not started.",
		"engine":Engine.get_version_info().string,"limits":limits,"expanded":0,"stored_states":0,"dominance_pruned":0,"terminal_states":0,"elapsed_ms":0,
		"witness":[],"witness_verification":{},"terminal_example":{},"errors":[],
		"solver_source_sha256":FileAccess.get_sha256("res://tests/campaign_solver.gd"),"navigation_source_sha256":FileAccess.get_sha256("res://scripts/campaign_navigation.gd"),
		"scope":"A winning suffix inside the current run using ordinary move/use_stairs/buy. Explicit unsafe combat, death/respawn, reset, save editing and a different run are excluded.",
		"dominance_basis":"States must have identical rule/content/variant/seed/attempt/failure/story and other non-audit metadata, plus identical discrete core fields. Only decision index/log/hash and checkpoint id/list are omitted: they are append-only audit or excluded restore/save/respawn state and do not gate ordinary move/use_stairs/buy. The signature removes current hp/atk/def/gold/key quantities, retains key-color schema, and normalizes cleared IDs as a set. A vector dominates only if every resource is >=. Current base combat/costs are monotone for these ordinary actions; changing those semantics requires reviewing this contract.",
		"not_claimed":["A budget-limited search is never unsatisfiable.","A winning witness from the initial state does not prove all later spending choices safe.","Headless state/action search does not prove real keyboard/browser input, visual quality, or hours of play."]
	}
	if limits.max_expanded < 1 or limits.max_states < 1 or limits.max_msec < 1:
		report.reason = "Positive state, expansion and time budgets are required."
		return report
	for method: String in ["campaign_snapshot","restore_snapshot","clone_for_search"]:
		if not game.has_method(method):
			report.reason = "The rule object lacks the strict snapshot/clone API: " + method
			return report
	var initial: Dictionary = game.campaign_snapshot()
	if not (initial.get("core_state") is Dictionary):
		report.reason = "The rule object did not expose core_state in its bound snapshot."
		return report
	report["initial_snapshot"] = initial
	report["active_data_sha256"] = JSON.stringify(game.data).sha256_text()
	report["receipt"] = {"status":"unknown","complete":false,"state_sha256":game.current_state_sha256() if game.has_method("current_state_sha256") else "","canonical_content_sha256":initial.get("canonical_content_sha256",""),"transformed_content_sha256":initial.get("transformed_content_sha256",""),"rules_sha256":initial.get("rules_sha256",""),"solver":SOLVER_VERSION}
	if bool(game.state.get("won",false)):
		report.result = "witness"
		report.reason = "The input state is already won."
		report.witness_verification = {"ok":true,"already_won":true,"final_snapshot":initial}
		report.receipt.status = "witness"
		report.receipt.complete = true
		return report
	if game.has_method("is_failed") and bool(game.is_failed()):
		report.result = "unsatisfiable"
		report.reason = "The supplied run is frozen by its explicit failure mode. No ordinary continuation is allowed; restart/respawn is outside this query."
		report.terminal_example = {"snapshot":initial,"basis":"Rule object's is_failed() gate; this is not a navigation-BFS claim."}
		report.receipt.status = "unsatisfiable"
		report.receipt.complete = true
		return report
	var working: RefCounted = game.clone_for_search()
	if working == null or not working.restore_snapshot(initial):
		report.reason = "An isolated clone could not restore the input snapshot."
		return report
	# Branches descend only by isolated clones and actual production actions.
	# Do not regenerate every floor/checkpoint by restoring a serialized snapshot
	# for each successor. External snapshots were strictly validated above.
	var nodes: Array[Dictionary] = [{"game":working,"parent":-1,"choice":{}}]
	var open: Array[int] = [0]
	var dominance: Dictionary = {}
	_register(dominance,initial)
	while not open.is_empty():
		if int(report.expanded) >= int(limits.max_expanded) or Time.get_ticks_msec()-started >= int(limits.max_msec):
			report.reason = "Expansion or time budget reached with unexplored states."
			break
		var current_index: int = open.pop_back()
		var current: Dictionary = nodes[current_index]
		working = current.game
		if working == null:
			report.reason = "An isolated frontier state is missing."
			report.errors.append({"node":current_index,"kind":"missing_clone"})
			break
		report.expanded += 1
		if working.has_method("is_failed") and bool(working.is_failed()):
			report.terminal_states += 1
			if report.terminal_example.is_empty():
				report.terminal_example = {"snapshot":working.campaign_snapshot(),"basis":"Frozen failure-mode gate."}
			nodes[current_index]["game"] = null
			continue
		var frontier: Dictionary = Navigation.frontier(working,int(limits.navigation_max_nodes),false)
		if not bool(frontier.complete):
			report.reason = "An incomplete navigation frontier prevents a complete successor expansion."
			report.errors.append({"node":current_index,"frontier":frontier})
			break
		if frontier.options.is_empty():
			report.terminal_states += 1
			if report.terminal_example.is_empty():
				report.terminal_example = {"snapshot":working.campaign_snapshot(),"frontier_proof":Navigation.frontier(working,0,true)}
			nodes[current_index]["game"] = null
			continue
		var choices: Array = frontier.options
		for choice: Dictionary in choices:
			choice["search_score"] = _score(choice,working.state)
		choices.sort_custom(func(a: Dictionary,b: Dictionary) -> bool: return float(a.search_score) < float(b.search_score))
		var halted: bool = false
		for choice: Dictionary in choices:
			if nodes.size() >= int(limits.max_states) or Time.get_ticks_msec()-started >= int(limits.max_msec):
				report.reason = "Stored-state or time budget reached before all successors were expanded."
				halted = true
				break
			working = current.game.clone_for_search()
			if working == null:
				report.reason = "The rule object could not clone a verified parent state."
				report.errors.append({"node":current_index,"kind":"parent_clone_failed"})
				halted = true
				break
			var execution: Dictionary = Navigation.execute(working,choice.path)
			if not bool(execution.ok):
				report.reason = "A predicted legal successor failed actual production-rule execution."
				report.errors.append({"node":current_index,"choice":choice.id,"execution":execution})
				halted = true
				break
			var snapshot: Dictionary = working.campaign_snapshot()
			var event: Dictionary = {"target":choice.id,"kind":choice.kind,"actions":choice.path.duplicate(true)}
			if bool(working.state.get("won",false)):
				var witness: Array = _witness(nodes,current_index)
				witness.append(event)
				var verification: Dictionary = _verify_witness(game,initial,witness,snapshot)
				report.witness = witness
				report.witness_verification = verification
				report.result = "witness" if bool(verification.ok) else "unknown"
				report.reason = "A complete winning sequence was replayed from the input snapshot through actual production rules." if bool(verification.ok) else "Candidate winning sequence failed independent continuous replay."
				report.stored_states = nodes.size()
				report.elapsed_ms = Time.get_ticks_msec()-started
				report.receipt.status = report.result
				report.receipt.complete = bool(verification.ok)
				return report
			if _is_dominated(dominance,snapshot):
				report.dominance_pruned += 1
				continue
			_register(dominance,snapshot)
			nodes.append({"game":working,"parent":current_index,"choice":event})
			open.append(nodes.size()-1)
		# Parent links retain only the action witness after expansion; release
		# expanded authority clones instead of keeping every full history in RAM.
		nodes[current_index]["game"] = null
		if halted:
			break
	if open.is_empty() and report.errors.is_empty() and str(report.reason) == "Not started.":
		report.result = "unsatisfiable"
		report.reason = "All legal ordinary-action successor states were exhausted, modulo the declared conservative resource dominance."
		report.receipt.status = "unsatisfiable"
		report.receipt.complete = true
	elif str(report.reason) == "Not started.":
		report.reason = "Unexplored states remain."
	report.stored_states = nodes.size()
	report["unexplored_states"] = open.size()
	report["discrete_signatures"] = dominance.size()
	report.elapsed_ms = Time.get_ticks_msec()-started
	return report


static func _signature(snapshot: Dictionary) -> String:
	var discrete: Dictionary = snapshot.duplicate(true)
	# _perform() gates ordinary actions only on loaded/failed/won and delegates
	# results to immutable data + core state. These five fields only record the
	# past or service save/restore_checkpoint, which this query excludes. Keep
	# every other current/future metadata field conservatively in the signature.
	for audit: String in ["decision_index","decision_log_hash","decision_log","checkpoint_id","checkpoints"]:
		discrete.erase(audit)
	var core: Dictionary = discrete.core_state
	for resource: String in ["hp","atk","def","gold"]:
		core.erase(resource)
	var colors: Array = core.get("keys",{}).keys()
	colors.sort()
	core.erase("keys")
	core["key_color_schema"] = colors
	if core.get("cleared") is Array:
		core.cleared.sort()
	# Variant/data binding, seed sequence, attempt, failure and story metadata
	# remain exact. Position remains exact; no component isomorphism is assumed.
	discrete.core_state = core
	return JSON.stringify(discrete).sha256_text()


static func _vector(snapshot: Dictionary) -> Array:
	var state: Dictionary = snapshot.core_state
	var result: Array = [int(state.hp),int(state.atk),int(state.def),int(state.gold)]
	var colors: Array = state["keys"].keys()
	colors.sort()
	for color: String in colors:
		result.append(int(state["keys"][color]))
	return result


static func _dominates(a: Array,b: Array) -> bool:
	if a.size() != b.size():
		return false
	for index: int in range(a.size()):
		if int(a[index]) < int(b[index]):
			return false
	return true


static func _is_dominated(registry: Dictionary,snapshot: Dictionary) -> bool:
	var signature: String = _signature(snapshot)
	var vector: Array = _vector(snapshot)
	for previous: Array in registry.get(signature,[]):
		if _dominates(previous,vector):
			return true
	return false


static func _register(registry: Dictionary,snapshot: Dictionary) -> void:
	var signature: String = _signature(snapshot)
	var vector: Array = _vector(snapshot)
	var retained: Array = []
	for previous: Array in registry.get(signature,[]):
		if not _dominates(vector,previous):
			retained.append(previous)
	retained.append(vector)
	registry[signature] = retained


static func _score(choice: Dictionary,state: Dictionary) -> float:
	match str(choice.kind):
		"atk": return 125.0
		"key": return 110.0
		"def": return 105.0
		"gold": return 100.0
		"potion": return 100.0
		"door": return 50.0
		"enemy": return (150.0 if bool(choice.item.get("victory",false)) else 45.0)-float(choice.preview.get("damage",0))*0.1
		"buy":
			if choice.offer.kind == "atk": return 120.0
			if choice.offer.kind == "def": return 35.0
			return 130.0 if int(state.hp) < 110 else 5.0
	return 0.0


static func _witness(nodes: Array[Dictionary], index: int) -> Array:
	var events: Array = []
	var current: int = index
	while current >= 0:
		var node: Dictionary = nodes[current]
		if not node.choice.is_empty():
			events.push_front(node.choice)
		current = int(node.parent)
	return events


static func _verify_witness(game: RefCounted,initial: Dictionary,witness: Array,expected: Dictionary) -> Dictionary:
	var replay: RefCounted = game.clone_for_search()
	if replay == null or not replay.restore_snapshot(initial):
		return {"ok":false,"error":"Could not restore initial state in a fresh replay clone."}
	var moves: int = 0
	var comparisons: int = 0
	for event: Dictionary in witness:
		var execution: Dictionary = Navigation.execute(replay,event.actions)
		moves += int(execution.get("moves",0))
		comparisons += int(execution.get("preview_comparisons",0))
		if not bool(execution.ok):
			return {"ok":false,"error":"Continuous replay action failed.","event":event,"execution":execution}
	var actual: Dictionary = replay.campaign_snapshot()
	var matches: bool = JSON.stringify(actual.core_state) == JSON.stringify(expected.core_state)
	return {"ok":bool(replay.state.get("won",false)) and matches,"won":bool(replay.state.get("won",false)),"core_state_matches_search":matches,"moves":moves,"preview_actual_comparisons":comparisons,"final_snapshot":actual}
