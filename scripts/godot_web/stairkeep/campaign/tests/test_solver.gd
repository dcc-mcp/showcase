extends SceneTree
## Small synthetic canonical fixtures exercise proof states through the real
## CampaignRules API. They are explicitly not campaign difficulty evidence.

const Campaign = preload("res://scripts/campaign_rules.gd")
const Solver = preload("res://tests/campaign_solver.gd")
const Navigation = preload("res://scripts/campaign_navigation.gd")

var checks: Array = []
var failures: Array = []
var production: Dictionary = {"requested":false,"initial_witness_binding":{},"topology":{},"cases":[],"complete":false}


func _initialize() -> void:
	var witness_report: String = ""
	var output: String = ""
	for argument: String in OS.get_cmdline_user_args():
		if argument == "--production-shop-regression": production.requested = true
		elif argument.begins_with("--witness-report="): witness_report = argument.trim_prefix("--witness-report=")
		elif argument.begins_with("--output="): output = argument.trim_prefix("--output=")
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string("res://data/levels21.json")) != OK or not (json.data is Dictionary):
		push_error("Production canonical JSON is unavailable for synthetic fixture construction.")
		quit(2)
		return
	var canonical: Dictionary = json.data
	var real = Campaign.new()
	_check("production data loads for bounded unknown test",bool(real.start_campaign(canonical,20261025).get("ok",false)))
	if not real.state.is_empty():
		var before: Dictionary = real.campaign_snapshot()
		var unknown: Dictionary = Solver.solve(real,{"max_expanded":1,"max_states":100,"max_msec":10000})
		_check("a nonempty search stopped at one expansion is unknown",unknown.result == "unknown",{"result":unknown.result,"reason":unknown.reason,"expanded":unknown.expanded})
		_check("unknown is not a conclusive loss receipt",not bool(unknown.get("receipt",{}).get("complete",true)))
		var rejected: Dictionary = real.mark_loss_proven(unknown.get("receipt",{}))
		_check("unknown receipt cannot mark a loss",not bool(rejected.get("ok",false)) and not real.is_failed())
		_check("search and rejected receipt leave source state intact",JSON.stringify(before) == JSON.stringify(real.campaign_snapshot()))
	var blocked_data: Dictionary = _fixture(canonical,false)
	var blocked = Campaign.new()
	var blocked_load: Dictionary = blocked.start_campaign(blocked_data,20261025)
	_check("synthetic blocked canonical passes real variant validation",bool(blocked_load.get("ok",false)),blocked_load if not bool(blocked_load.get("ok",false)) else null)
	if not blocked.state.is_empty():
		var blocked_before: Dictionary = blocked.campaign_snapshot()
		var unsat: Dictionary = Solver.solve(blocked,{"max_expanded":20,"max_states":100,"max_msec":10000})
		_check("complete no-resource frontier proves ordinary suffix unsatisfiable",unsat.result == "unsatisfiable" and int(unsat.expanded) == 1, {"result":unsat.result,"reason":unsat.reason,"expanded":unsat.expanded})
		_check("unsatisfiable includes complete exact-state bound receipt",bool(unsat.get("receipt",{}).get("complete",false)) and unsat.receipt.state_sha256 == blocked.current_state_sha256())
		_check("unsatisfiable proof source is not mutated",JSON.stringify(blocked_before) == JSON.stringify(blocked.campaign_snapshot()))
		var copy: RefCounted = blocked.clone_for_search()
		var accepted: Dictionary = copy.mark_loss_proven(unsat.get("receipt",{}))
		_check("verified bound unsatisfiable receipt can freeze its exact clone",bool(accepted.get("ok",false)) and copy.is_failed())
	var winning_data: Dictionary = _fixture(canonical,true)
	var winning = Campaign.new()
	var win_load: Dictionary = winning.start_campaign(winning_data,20261025)
	_check("synthetic winning canonical passes real variant validation",bool(win_load.get("ok",false)),win_load if not bool(win_load.get("ok",false)) else null)
	if not winning.state.is_empty():
		var winning_before: Dictionary = winning.campaign_snapshot()
		var found: Dictionary = Solver.solve(winning,{"max_expanded":20,"max_states":100,"max_msec":10000})
		_check("reachable weak victory enemy produces a verified witness",found.result == "witness" and bool(found.witness_verification.get("ok",false)),{"result":found.result,"reason":found.reason,"verification":found.witness_verification})
		_check("winning witness includes real moves and combat preview checks",int(found.witness_verification.get("moves",0)) > 0 and int(found.witness_verification.get("preview_actual_comparisons",0)) > 0)
		_check("winning search leaves its source state intact",JSON.stringify(winning_before) == JSON.stringify(winning.campaign_snapshot()))
	if bool(production.requested):
		_production_shop_regression(canonical,witness_report)
	var report: Dictionary = {"suite":"campaign-solver-three-state","fixture_scope":"The first tests use modified in-memory synthetic canonicals. The separately labelled optional production shop regression uses unmodified canonical data and actual initial-to-shop actions.","engine":Engine.get_version_info().string,"data_sha256":FileAccess.get_sha256("res://data/levels21.json"),"test_sha256":FileAccess.get_sha256("res://tests/test_solver.gd"),"solver_sha256":FileAccess.get_sha256("res://tests/campaign_solver.gd"),"navigation_sha256":FileAccess.get_sha256("res://scripts/campaign_navigation.gd"),"checks":checks,"failures":failures,"production":production,"passed":failures.is_empty()}
	if not output.is_empty():
		var file: FileAccess = FileAccess.open(output,FileAccess.WRITE)
		if file == null:
			_check("requested report can be written",false)
		else:
			file.store_string(JSON.stringify(report,"  "))
			file.close()
	var outcomes: Array = []
	for item: Dictionary in production.cases:
		outcomes.append({"prefix":item.prefix,"purchase":item.purchase,"solver_result":item.solver.result,"classification":item.classification,"closure_has_no_action":item.closure.get("no_resource_action",false),"post_purchase_budget":item.post_purchase_budget})
	print(JSON.stringify({"suite":report.suite,"passed":failures.is_empty(),"checks":checks,"failures":failures,"production_complete":production.complete,"production_cases":outcomes,"report":output}))
	quit(0 if failures.is_empty() else 1)


func _production_shop_regression(canonical: Dictionary, witness_path: String) -> void:
	production.initial_witness_binding = _witness_binding(witness_path,canonical)
	_check("production canonical has four hash-bound actual winning replay witnesses",bool(production.initial_witness_binding.get("ok",false)),production.initial_witness_binding)
	if not bool(production.initial_witness_binding.get("ok",false)):
		return
	production.topology = _first_floor_topology(canonical)
	var all_conclusive: bool = true
	for defense_first: bool in [false,true]:
		for offer: String in ["ward","flask"]:
			var game = Campaign.new()
			var loaded: Dictionary = game.start_campaign(canonical,20261025)
			var trace: Array = []
			var prefix: String = "defense_room_before_shop" if defense_first else "yellow_key_unspent_at_shop"
			var ok: bool = bool(loaded.get("ok",false))
			for event: String in ["f01_core_def","f01_core_atk","f01_entry_gold","f01_choice_key","f01_chapter_key","f01_scout","f01_trail_potion"]:
				if ok:
					ok = _production_event(game,event,trace)
			if defense_first:
				for event: String in ["f01_defense_door","f01_defense_gem","f01_defense_gold","f01_defense_potion"]:
					if ok:
						ok = _production_event(game,event,trace)
			if ok:
				ok = _production_event(game,"buy:f01_shop/"+offer,trace)
			_check("actual production prefix and purchase execute: "+prefix+"/"+offer,ok,{"trace":trace,"state":game.state})
			if not ok:
				all_conclusive = false
				continue
			var after_purchase: Dictionary = game.campaign_snapshot()
			var solved: Dictionary = Solver.solve(game,{"max_expanded":10000,"max_states":20000,"max_msec":30000})
			var conclusive: bool = str(solved.result) in ["witness","unsatisfiable"]
			var sound: bool = (solved.result == "unknown" and not bool(solved.get("receipt",{}).get("complete",true))) or (solved.result == "witness" and bool(solved.witness_verification.get("ok",false))) or (solved.result == "unsatisfiable" and bool(solved.get("receipt",{}).get("complete",false)) and solved.receipt.state_sha256 == game.current_state_sha256())
			_check("production result obeys witness/unsatisfiable/unknown semantics: "+prefix+"/"+offer,sound,{"result":solved.result,"reason":solved.reason,"expanded":solved.expanded})
			_check("production bad-shop query is conclusive, unknown stays unknown: "+prefix+"/"+offer,conclusive,{"result":solved.result,"reason":solved.reason})
			_check("production search preserves exact reached state: "+prefix+"/"+offer,JSON.stringify(after_purchase) == JSON.stringify(game.campaign_snapshot()))
			var closure: Dictionary = _resource_closure(game)
			production.cases.append({"prefix":prefix,"purchase":offer,"seed":20261025,"initial_witness_report_sha256":production.initial_witness_binding.report_sha256,"initial_to_purchase_trace":trace,"post_purchase_snapshot":after_purchase,"post_purchase_budget":_resources(game.state),"solver":solved,"closure":closure,"classification":"wrong_purchase_has_no_ordinary_winning_suffix" if solved.result == "unsatisfiable" else ("purchase_is_recoverable_with_verified_witness" if solved.result == "witness" else "unknown"),"scope":"Unmodified production canonical and real actions from initial. No resource injection, refund, rescue pickup, seed change or direct state setter."})
			all_conclusive = all_conclusive and conclusive and sound
	production.complete = all_conclusive and production.cases.size() == 4
	production["interpretation"] = "The initial canonical has four separately replayed winning witnesses. Each shop prefix is classified independently by actual search. A proven bad continuation is not initial-map unsatisfiability. No expected outcome is preselected for a purchase."


func _witness_binding(path: String, canonical: Dictionary) -> Dictionary:
	var result: Dictionary = {"ok":false,"report_sha256":"","reason":"Pass --witness-report=<actual canonical replay report>."}
	if path.is_empty() or not FileAccess.file_exists(path):
		return result
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(path)) != OK or not (json.data is Dictionary):
		result.reason = "Witness report is not valid JSON."
		return result
	var replay: Dictionary = json.data
	result.report_sha256 = FileAccess.get_sha256(path)
	result["data_sha256"] = str(replay.get("data_sha256",""))
	result["base_rules_sha256"] = str(replay.get("base_rules_sha256",""))
	var ok: bool = bool(replay.get("passed",false)) and replay.get("failures",[]).is_empty() and replay.get("routes",[]).size() >= 4 and result.data_sha256 == FileAccess.get_sha256("res://data/levels21.json") and result.base_rules_sha256 == FileAccess.get_sha256("res://scripts/base_rules.gd")
	var seen: Dictionary = {}
	for route: Dictionary in replay.get("routes",[]):
		if bool(route.get("passed",false)) and bool(route.get("final",{}).get("won",false)):
			seen[str(route.get("name",""))] = true
	for route: Dictionary in canonical.get("validated_routes",[]):
		ok = ok and seen.has(str(route.name))
	result["winning_routes"] = seen.keys()
	result.ok = ok
	result.reason = "Existing actual production-base replay report matches current canonical/base bytes and every authored winning route." if ok else "Replay report is incomplete or belongs to different canonical/base bytes."
	return result


func _production_event(game: RefCounted,event: String,trace: Array) -> bool:
	var target: String = event.trim_prefix("buy:") if event.begins_with("buy:") else event
	var frontier: Dictionary = Navigation.frontier(game,0,false)
	if not bool(frontier.complete):
		trace.append({"event":event,"error":"Incomplete navigation frontier.","frontier":frontier})
		return false
	for option: Dictionary in frontier.options:
		if str(option.id) != target:
			continue
		var before: Dictionary = _resources(game.state)
		var executed: Dictionary = Navigation.execute(game,option.path)
		trace.append({"event":event,"actions":option.path.duplicate(true),"before":before,"after":_resources(game.state),"execution":executed})
		return bool(executed.ok)
	trace.append({"event":event,"error":"Requested production event is not a currently legal reachable action.","state":game.state,"frontier_ids":_option_ids(frontier.options)})
	return false


func _resource_closure(source: RefCounted) -> Dictionary:
	var game: RefCounted = source.clone_for_search()
	var prepared: Dictionary = Navigation.prepare(game)
	var trace: Array = []
	for index: int in range(128):
		var frontier: Dictionary = Navigation.frontier(game,0,false,prepared)
		if not bool(frontier.complete):
			return {"complete":false,"error":"Global frontier was incomplete.","trace":trace,"frontier":frontier}
		var selected: Dictionary = {}
		for option: Dictionary in frontier.options:
			if str(option.kind) != "buy":
				selected = option
				break
		if selected.is_empty():
			var proof: Dictionary = Navigation.frontier(game,0,true,prepared)
			return {"complete":bool(proof.complete),"no_resource_action":bool(proof.complete) and proof.options.is_empty(),"trace":trace,"final_snapshot":game.campaign_snapshot(),"global_navigation_proof":proof,"note":"One actual resource-collection continuation is shown. Only the independent solver's conclusive result classifies all continuations from the immediate purchase state."}
		var before: Dictionary = _resources(game.state)
		var execution: Dictionary = Navigation.execute(game,selected.path)
		trace.append({"target":selected.id,"actions":selected.path.duplicate(true),"before":before,"after":_resources(game.state),"execution":execution})
		if not bool(execution.ok):
			return {"complete":false,"error":"Actual resource collection failed.","trace":trace,"execution":execution}
	return {"complete":false,"error":"Collection step budget reached.","trace":trace}


func _first_floor_topology(canonical: Dictionary) -> Dictionary:
	var floor: Dictionary = canonical.floors[0]
	var by_id: Dictionary = {}
	for item: Dictionary in floor.objects:
		by_id[str(item.id)] = item
	if not by_id.has("f01_guard") or not by_id.has("f01_attack_gem"):
		return {"complete":false,"reason":"Expected production first-floor IDs are unavailable."}
	var guard: Vector2i = _cell(by_id.f01_guard.pos)
	var start: Vector2i = _cell(floor.spawn)
	var queue: Array[Vector2i] = [start]
	var seen: Dictionary = {start:true}
	var head: int = 0
	while head < queue.size():
		var current: Vector2i = queue[head]
		head += 1
		for delta: Vector2i in [Vector2i.UP,Vector2i.DOWN,Vector2i.LEFT,Vector2i.RIGHT]:
			var next: Vector2i = current+delta
			if next == guard or seen.has(next) or next.y < 0 or next.y >= floor.grid.size() or next.x < 0 or next.x >= str(floor.grid[next.y]).length() or str(floor.grid[next.y])[next.x] == "#":
				continue
			seen[next] = true
			queue.append(next)
	var attack_upper: int = int(canonical.initial_player.atk)
	var gold_upper: int = int(canonical.initial_player.gold)
	var attack_sources: Array = []
	var gold_sources: Array = []
	var reachable_stairs: Array = []
	for item: Dictionary in floor.objects:
		if not seen.has(_cell(item.pos)):
			continue
		if item.kind == "atk":
			attack_upper += int(item.amount)
			attack_sources.append(item.id)
		elif item.kind == "gold":
			gold_upper += int(item.amount)
			gold_sources.append({"id":item.id,"amount":int(item.amount)})
		elif item.kind == "enemy":
			gold_upper += int(canonical.enemies[item.type].gold)
			gold_sources.append({"id":item.id,"amount":int(canonical.enemies[item.type].gold)})
		elif item.kind == "stairs":
			reachable_stairs.append(item.id)
	return {"complete":true,"scope":"Static optimistic first-floor topology: every object except f01_guard is passable, including all other doors/enemies. This over-approximates reachability and does not inject runtime resources.","guard_cell":by_id.f01_guard.pos,"guard_defense":int(canonical.enemies[by_id.f01_guard.type].def),"guard_removed_reachable_cells":seen.size(),"attack_gem_reachable_without_crossing_guard":seen.has(_cell(by_id.f01_attack_gem.pos)),"attack_door_reachable_without_crossing_guard":seen.has(_cell(by_id.f01_attack_door.pos)),"stairs_reachable_without_crossing_guard":reachable_stairs,"free_attack_upper_bound_before_guard_or_shop_edge":attack_upper,"attack_sources":attack_sources,"gold_upper_bound_before_guard":gold_upper,"gold_sources":gold_sources,"proof_role":"Structural cross-check only. Actual reachability, spending, combat and suffix solvability are separately tested through the production APIs."}


func _cell(value: Array) -> Vector2i:
	return Vector2i(int(value[0]),int(value[1]))


func _resources(state: Dictionary) -> Dictionary:
	return {"floor":int(state.floor),"pos":state.pos.duplicate(),"hp":int(state.hp),"atk":int(state.atk),"def":int(state.def),"gold":int(state.gold),"keys":state["keys"].duplicate(true),"cleared":state.cleared.duplicate(),"purchases":state.purchases.duplicate(true),"won":bool(state.won)}


func _option_ids(options: Array) -> Array:
	var result: Array = []
	for option: Dictionary in options:
		result.append(option.id)
	return result


func _fixture(canonical: Dictionary, winning: bool) -> Dictionary:
	var data: Dictionary = canonical.duplicate(true)
	data.enemies["solver_fixture"] = {"name":"Synthetic solver fixture","hp":1,"atk":1,"def":0 if winning else 999999,"gold":0}
	var first: Dictionary = data.floors[0]
	var retained: Array = []
	var victory_assigned: bool = false
	for item: Dictionary in first.objects:
		if item.kind not in ["enemy","door","stairs"]:
			continue
		if item.kind == "enemy":
			item.type = "solver_fixture"
			item["victory"] = winning and not victory_assigned
			victory_assigned = victory_assigned or winning
		retained.append(item)
	first.objects = retained
	data.floors[0] = first
	return data


func _check(name: String, passed: bool, observed: Variant = null) -> void:
	checks.append({"name":name,"passed":passed,"observed":observed})
	if not passed:
		failures.append(name)
		push_error(name + ": " + str(observed))
