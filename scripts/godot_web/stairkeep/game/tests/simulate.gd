extends SceneTree
## Decision-level exploration over the production rule object. Navigation uses
## real move/use_stairs calls; this harness never implements combat arithmetic.

const Rules = preload("res://scripts/rules.gd")
const POLICIES: Array[String] = ["resource", "attack", "defense", "cautious", "randomized"]
const DELTAS: Array[Vector2i] = [Vector2i.RIGHT, Vector2i.LEFT, Vector2i.DOWN, Vector2i.UP]
const VERSION: String = "frontier-v1"

var topology: Dictionary = {}
var objects: Dictionary = {}
var floor_ids: Dictionary = {}
var runs: int = 10000
var master_seed: int = 20261025
var output: String = "user://stairkeep-simulation.json"
var decision_limit: int = 96
var diagnostics: Array = []


func _initialize() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--runs="):
			runs = int(argument.trim_prefix("--runs="))
		elif argument.begins_with("--seed="):
			master_seed = int(argument.trim_prefix("--seed="))
		elif argument.begins_with("--output="):
			output = argument.trim_prefix("--output=")
	if runs < 1 or runs > 100000 or master_seed < 0:
		push_error("Use 1..100000 runs and a nonnegative seed.")
		quit(2)
		return
	var game = Rules.new()
	if game.state.is_empty():
		push_error("Production data did not load.")
		quit(2)
		return
	_index(game.data)
	var policy_results: Dictionary = {}
	for policy: String in POLICIES:
		policy_results[policy] = {"runs":0, "won":0, "dead_end":0, "limit":0, "error":0, "hp_min":2000000000, "hp_max":0, "gold_min":2000000000, "gold_max":0}
	var trace_hashes: Dictionary = {}
	var terminal_hashes: Dictionary = {}
	var samples: Dictionary = {}
	var invariant_errors: Array = []
	var preview_comparisons: int = 0
	var moves: int = 0
	var decisions: int = 0
	var started: int = Time.get_ticks_msec()
	for run_index: int in range(runs):
		game.reset()
		var policy: String = POLICIES[run_index % POLICIES.size()]
		var run_seed: int = master_seed + run_index * 104729
		var rng := RandomNumberGenerator.new()
		rng.seed = run_seed
		var trace: Array = []
		var status: String = "limit"
		var dead_end_evidence: Dictionary = {}
		for decision_index: int in range(decision_limit):
			if bool(game.state.won):
				status = "won"
				break
			var frontier: Dictionary = _frontier(game)
			var options: Array = frontier.options
			if options.is_empty():
				status = "dead_end"
				dead_end_evidence = {"reachable_navigation_nodes":frontier.reachable, "uncollected_objects":_remaining(game), "classification":"No legal resource-changing action exists after complete empty/shop/stair navigation BFS in this state.", "scope":"This particular state under the delivered move/use_stairs/buy rules, excluding reset or editing a save."}
				break
			var choice: Dictionary = _choose(game, options, policy, rng)
			var before: Dictionary = _budget(game.state)
			var executed: Dictionary = _execute(game, choice.path)
			preview_comparisons += int(executed.previews)
			moves += int(executed.moves)
			decisions += 1
			var event: Dictionary = {"target":choice.id, "kind":choice.kind, "navigation_steps":choice.path.size(), "before":before, "after":_budget(game.state)}
			trace.append(event)
			if not bool(executed.ok) or not _resources_valid(game.state):
				status = "error"
				if invariant_errors.size() < 20:
					invariant_errors.append({"run_index":run_index,"seed":run_seed,"policy":policy,"event":event,"execution":executed,"state":game.snapshot()})
				break
			if bool(game.state.won):
				status = "won"
				break
		var row: Dictionary = policy_results[policy]
		row.runs += 1
		row[status] += 1
		row.hp_min = mini(int(row.hp_min),int(game.state.hp))
		row.hp_max = maxi(int(row.hp_max),int(game.state.hp))
		row.gold_min = mini(int(row.gold_min),int(game.state.gold))
		row.gold_max = maxi(int(row.gold_max),int(game.state.gold))
		var sequence: Array = []
		for event: Dictionary in trace:
			sequence.append(event.target)
		trace_hashes[JSON.stringify(sequence).sha256_text()] = true
		terminal_hashes[JSON.stringify(_canonical_terminal(game.state)).sha256_text()] = true
		var sample_key: String = policy + "/" + status
		if not samples.has(sample_key):
			samples[sample_key] = {"run_index":run_index,"seed":run_seed,"policy":policy,"outcome":status,"state":game.snapshot(),"sequence":sequence,"events":trace,"dead_end_analysis":dead_end_evidence}
		if (run_index + 1) % 1000 == 0:
			print("SIMULATION_PROGRESS " + JSON.stringify({"complete":run_index + 1,"requested":runs,"elapsed_ms":Time.get_ticks_msec()-started}))
	var report: Dictionary = {
		"schema_version":1,"harness":VERSION,"engine":Engine.get_version_info().string,
		"source_data_sha256":FileAccess.get_sha256("res://data/levels.json"),
		"rule_source_sha256":FileAccess.get_sha256("res://scripts/rules.gd"),
		"master_seed":master_seed,"run_seed_formula":"master_seed + run_index * 104729",
		"policy_assignment":"POLICIES[run_index % 5]", "requested_runs":runs,"completed_runs":runs,
		"policies":policy_results,"unique_decision_sequences":trace_hashes.size(),"unique_terminal_states":terminal_hashes.size(),
		"decisions":decisions,"real_core_navigation_moves":moves,"combat_preview_actual_comparisons":preview_comparisons,
		"invariant_errors":invariant_errors,"examples":samples,"elapsed_ms":Time.get_ticks_msec()-started,
		"verification_scope":"Headless production StairRules actions. Fixed monster positions, no injected outcome, no copied battle formula. Reachability search includes every cleared/shop tile and stair transfer, and exposes every currently legal uncollected object and affordable in-stock purchase.",
		"not_claimed":["A high simulation win rate proves neither all reachable states solvable nor all policies safe.","No exhaustive search of every resource state or complete universal no-softlock proof.","No browser/native input, rendering, subjective difficulty, physical device or hours-of-play validation.","The harness does not implement the later 21-floor content, death/respawn, or mirrored-map variants."]
	}
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	if file == null:
		push_error("Could not write simulation report: " + output)
		quit(2)
		return
	file.store_string(JSON.stringify(report,"  "))
	file.close()
	print("SIMULATION_RESULT " + JSON.stringify({"report":output,"runs":runs,"policies":policy_results,"unique_sequences":trace_hashes.size(),"preview_comparisons":preview_comparisons,"invariant_errors":invariant_errors.size(),"elapsed_ms":report.elapsed_ms}))
	quit(0 if invariant_errors.is_empty() else 1)


func _index(data: Dictionary) -> void:
	for floor_index: int in range(data.floors.size()):
		var floor_item: Dictionary = data.floors[floor_index]
		floor_ids[int(floor_item.id)] = floor_index
		for y: int in range(floor_item.grid.size()):
			for x: int in range(str(floor_item.grid[y]).length()):
				if str(floor_item.grid[y])[x] != "#":
					topology[Vector3i(floor_index,x,y)] = true
		for item: Dictionary in floor_item.objects:
			objects[Vector3i(floor_index,int(item.pos[0]),int(item.pos[1]))] = item


func _item_at(node: Vector3i, cleared: Dictionary) -> Dictionary:
	var item: Dictionary = objects.get(node,{})
	return {} if cleared.has(str(item.get("id",""))) else item


func _stair_target(item: Dictionary) -> Vector3i:
	return Vector3i(int(floor_ids[int(item.target.floor)]),int(item.target.pos[0]),int(item.target.pos[1]))


func _frontier(game: RefCounted) -> Dictionary:
	var cleared: Dictionary = {}
	for item_id: String in game.state.cleared:
		cleared[item_id] = true
	var start := Vector3i(int(game.state.floor),int(game.state.pos[0]),int(game.state.pos[1]))
	var queue: Array[Vector3i] = [start]
	var paths: Dictionary = {start:[]}
	var options: Array = []
	var offered: Dictionary = {}
	while not queue.is_empty():
		var node: Vector3i = queue.pop_front()
		var path: Array = paths[node]
		var here: Dictionary = _item_at(node,cleared)
		if here.get("kind","") == "stairs":
			var target: Vector3i = _stair_target(here)
			if not paths.has(target):
				var next_path: Array = path.duplicate()
				next_path.append({"kind":"stairs"})
				paths[target] = next_path
				queue.append(target)
		if here.get("kind","") == "shop":
			_shop_options(game,here,path,offered,options)
		for delta: Vector2i in DELTAS:
			var next := Vector3i(node.x,node.y+delta.x,node.z+delta.y)
			if not topology.has(next):
				continue
			var item: Dictionary = _item_at(next,cleared)
			var kind: String = str(item.get("kind",""))
			if kind == "shop":
				_shop_options(game,item,path,offered,options)
			var move_action: Dictionary = {"kind":"move","dx":delta.x,"dy":delta.y}
			var next_path: Array = path.duplicate()
			next_path.append(move_action)
			if kind in ["", "shop", "stairs"]:
				var destination: Vector3i = _stair_target(item) if kind == "stairs" else next
				if not paths.has(destination):
					paths[destination] = next_path
					queue.append(destination)
				continue
			var id: String = str(item.id)
			if offered.has(id):
				continue
			var preview: Dictionary = {}
			if kind == "enemy":
				preview = game.combat(game.data.enemies[item.type])
				if not bool(preview.win):
					continue
			elif kind == "door":
				if int(game.state["keys"].get(item.get("type","yellow"),0)) < 1:
					continue
			elif kind not in ["key","potion","atk","def","gold"]:
				continue
			offered[id] = true
			options.append({"id":id,"kind":kind,"item":item,"preview":preview,"path":next_path})
	return {"options":options,"reachable":paths.size()}


func _shop_options(game: RefCounted, item: Dictionary, path: Array, offered: Dictionary, options: Array) -> void:
	for offer: Dictionary in game.data.shops[item.type].offers:
		var id: String = str(item.id)+"/"+str(offer.id)
		if offered.has(id) or int(game.state.gold) < int(offer.cost) or int(game.state.purchases.get(id,0)) >= int(offer.get("limit",1)):
			continue
		var next_path: Array = path.duplicate()
		next_path.append({"kind":"buy","offer":str(offer.id)})
		offered[id] = true
		options.append({"id":id,"kind":"buy","item":item,"offer":offer,"path":next_path})


func _choose(game: RefCounted, options: Array, policy: String, rng: RandomNumberGenerator) -> Dictionary:
	if policy == "randomized":
		return options[rng.randi_range(0,options.size()-1)]
	var best: Dictionary = options[0]
	var best_score: float = -INF
	for option: Dictionary in options:
		var kind: String = str(option.kind)
		var score: float = 0.0
		if kind in ["key","atk","def","potion","gold"]:
			score = 80.0
		elif kind == "enemy":
			score = 25.0 - float(option.preview.damage) * (0.25 if policy == "attack" else 0.65)
			if bool(option.item.get("victory",false)):
				score += 30.0
		elif kind == "door":
			score = 18.0
		elif kind == "buy":
			var upgrade: String = str(option.offer.kind)
			score = 20.0
			if policy == "attack" and upgrade == "atk":
				score = 110.0
			elif policy == "defense" and upgrade == "def":
				score = 110.0
			elif policy == "resource":
				score = 55.0 if upgrade == "atk" else 5.0
			elif policy == "cautious":
				score = 65.0 if upgrade == "atk" else 15.0
			if upgrade == "potion":
				score = 120.0 if int(game.state.hp) < 110 else 2.0
		if kind == "atk" and policy == "attack":
			score += 25.0
		if kind == "def" and policy == "defense":
			score += 25.0
		# A bounded seed-dependent perturbation makes close alternatives vary
		# without calling ten thousand copies of one scripted route exploration.
		score += rng.randf_range(-12.0,12.0)
		if score > best_score:
			best_score = score
			best = option
	return best


func _execute(game: RefCounted, path: Array) -> Dictionary:
	var comparisons: int = 0
	var moves: int = 0
	for action: Dictionary in path:
		var hp_before: int = int(game.state.hp)
		var preview: Dictionary = {}
		var result: Dictionary
		if action.kind == "move":
			var cell: Array = [int(game.state.pos[0])+int(action.dx),int(game.state.pos[1])+int(action.dy)]
			preview = game.inspect(cell).get("combat",{})
			result = game.move(int(action.dx),int(action.dy))
			moves += 1
		elif action.kind == "stairs":
			result = game.use_stairs()
			moves += 1
		else:
			result = game.buy(str(action.offer))
		if not bool(result.ok):
			return {"ok":false,"previews":comparisons,"moves":moves,"error":"planned legal action was rejected","action":action,"result":result}
		if not preview.is_empty():
			comparisons += 1
			if not bool(preview.win) or hp_before-int(game.state.hp) != int(preview.damage):
				return {"ok":false,"previews":comparisons,"moves":moves,"error":"preview did not equal actual deduction","preview":preview,"actual":hp_before-int(game.state.hp)}
	return {"ok":true,"previews":comparisons,"moves":moves}


func _resources_valid(state: Dictionary) -> bool:
	if int(state.hp) <= 0 or int(state.atk) <= 0 or int(state.def) < 0 or int(state.gold) < 0:
		return false
	for key: String in state["keys"]:
		if int(state["keys"][key]) < 0:
			return false
	var seen: Dictionary = {}
	for id: String in state.cleared:
		if seen.has(id):
			return false
		seen[id] = true
	return true


func _budget(state: Dictionary) -> Dictionary:
	return {"floor":state.floor,"hp":state.hp,"atk":state.atk,"def":state.def,"gold":state.gold,"keys":state["keys"].duplicate(true),"cleared_count":state.cleared.size(),"won":state.won}


func _canonical_terminal(state: Dictionary) -> Dictionary:
	var ids: Array = state.cleared.duplicate()
	ids.sort()
	return {"budget":_budget(state),"cleared":ids,"purchases":state.purchases}


func _remaining(game: RefCounted) -> Array:
	var remaining: Array = []
	for node: Vector3i in objects:
		var item: Dictionary = objects[node]
		if game.state.cleared.has(str(item.id)) or str(item.kind) in ["stairs","shop"]:
			continue
		var record: Dictionary = {"id":item.id,"floor_index":node.x,"kind":item.kind}
		if item.kind == "enemy":
			record["combat"] = game.combat(game.data.enemies[item.type])
		elif item.kind == "door":
			record["keys_owned"] = int(game.state["keys"].get(item.type,0))
		remaining.append(record)
	return remaining
