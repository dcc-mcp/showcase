extends "res://tests/simulate_campaign.gd"
## Independent failure evidence. The baseline simulation and five bound source
## files are not changed. Each example/proof is streamed, then released.

var replay_input: String = ""
var replay_output: String = "res://tests/campaign-failure-replay.jsonl"
var replay_offset: int = 0
var replay_count: int = -1
var replay_stop_file: String = ""
var replay_witness_path: String = ""
var replay_errors: Array = []
var replay_line: int = 0
var replay_source: Dictionary = {}
var witness_binding: Dictionary = {}


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--input="): replay_input = argument.trim_prefix("--input=")
		elif argument.begins_with("--output="): replay_output = argument.trim_prefix("--output=")
		elif argument.begins_with("--offset="): replay_offset = int(argument.trim_prefix("--offset="))
		elif argument.begins_with("--count="): replay_count = int(argument.trim_prefix("--count="))
		elif argument.begins_with("--stop-file="): replay_stop_file = argument.trim_prefix("--stop-file=")
		elif argument.begins_with("--witness-report="): replay_witness_path = argument.trim_prefix("--witness-report=")
		else:
			push_error("Unknown replay argument: "+argument)
			quit(2)
			return
	if replay_input.is_empty() or not FileAccess.file_exists(replay_input) or replay_offset < 0 or replay_count < -1:
		push_error("Pass --input=<failure-replay-input.json>, nonnegative --offset and optional --count.")
		quit(2)
		return
	if FileAccess.file_exists(replay_output) or FileAccess.file_exists(replay_output+".summary.json"):
		push_error("Replay output and summary must be new files; existing evidence was not overwritten.")
		quit(2)
		return
	var parsed := JSON.new()
	if parsed.parse(FileAccess.get_file_as_string(replay_input)) != OK or not (parsed.data is Dictionary):
		push_error("Replay input is not a JSON object.")
		quit(2)
		return
	replay_source = parsed.data
	if not _bind_sources():
		print(JSON.stringify({"measurement_completed":false,"errors":replay_errors}))
		quit(2)
		return
	var content := JSON.new()
	if content.parse(FileAccess.get_file_as_string(DATA_PATH)) != OK or not (content.data is Dictionary):
		push_error("Bound canonical data could not be read.")
		quit(2)
		return
	canonical = content.data
	witness_binding = _bind_witnesses()
	if not bool(witness_binding.get("ok",false)):
		print(JSON.stringify({"measurement_completed":false,"errors":["Four actual hash-bound canonical winning witnesses are required."],"binding":witness_binding}))
		quit(2)
		return
	master_seed = str(replay_source.master_layout_seed).hex_to_int()
	master_policy_seed = str(replay_source.master_policy_seed).hex_to_int()
	horizon = int(replay_source.local_floor_horizon)
	max_decisions = int(replay_source.max_decisions)
	example_limit = 1
	var expected_records: Array = replay_source.expected_records
	var end: int = expected_records.size() if replay_count < 0 else mini(expected_records.size(),replay_offset+replay_count)
	if replay_offset > expected_records.size():
		push_error("Replay offset is outside the failure queue.")
		quit(2)
		return
	var requested: int = end-replay_offset
	journal = FileAccess.open(replay_output,FileAccess.WRITE)
	if journal == null:
		push_error("Cannot create a new replay journal.")
		quit(2)
		return
	_append({"kind":"replay_header","schema_version":1,"engine_pid":OS.get_process_id(),"source_hashes":replay_source.source_hashes,"engine":Engine.get_version_info(),"input_sha256":FileAccess.get_sha256(replay_input),"source_aggregate_summary_sha256":replay_source.get("source_aggregate_summary_sha256",""),"replayer_sha256":FileAccess.get_sha256("res://tests/replay_campaign_failures.gd"),"master_layout_seed":replay_source.master_layout_seed,"master_policy_seed":replay_source.master_policy_seed,"offset":replay_offset,"requested_replays":requested,"witness_binding":witness_binding,"scope":"Exact original policy replays plus independent continuous action reconstruction, complete terminal BFS and H/V graph/spawn isomorphism certificates. No baseline changes, generated rescues or alternative policies."})
	journal.flush()
	var began: int = Time.get_ticks_usec()
	var completed: int = 0
	var proven_policy_dead_ends: int = 0
	var stopped: bool = false
	var totals: Dictionary = {"gross_battle_damage":0,"gross_healing":0,"gold_spent":0,"gold_gained":0,"keys_consumed":{},"keys_collected":{},"navigation_moves":0,"preview_actual_comparisons":0}
	for queue_index: int in range(replay_offset,end):
		if not replay_stop_file.is_empty() and FileAccess.file_exists(replay_stop_file):
			stopped = true
			_append({"kind":"coordinated_stop","before_queue_offset":queue_index,"completed_replays":completed})
			break
		var expected: Dictionary = expected_records[queue_index]
		examples.clear()
		var example_offset: int = journal.get_position()
		var example_line: int = replay_line+1
		# Inherited _one_run uses exactly the bound baseline RNG/selector. With
		# examples cleared and limit=1 it appends one full example immediately.
		var record: Dictionary = _one_run(int(expected.index))
		var example_length: int = journal.get_position()-example_offset
		if example_length > 0:
			replay_line += 1
		var differences: Array = _record_differences(expected,record)
		var bucket: String = str(record.get("policy",""))+"/"+str(record.get("outcome",""))
		var retained: Array = examples.get(bucket,[])
		var example: Dictionary = retained[0] if retained.size() == 1 else {}
		if example.is_empty() or example_length <= 0:
			differences.append("The inherited simulation did not retain exactly one full example.")
		var reconstructed: Dictionary = _reconstruct(record,example) if not example.is_empty() else {"ok":false,"error":"No example to reconstruct."}
		var certificate: Dictionary = _isomorphism_certificate(str(record.get("layout_seed","")))
		var matches: bool = differences.is_empty() and bool(reconstructed.get("ok",false)) and bool(certificate.get("ok",false)) and errors.is_empty()
		var dead_end: bool = record.get("outcome","") == "dead_end"
		var terminal_proven: bool = dead_end and bool(reconstructed.get("terminal_no_resource_action",false))
		var initial_solvable: bool = bool(certificate.get("ok",false)) and bool(witness_binding.get("ok",false))
		var classification: String = "policy_dead_end_with_proven_solvable_initial_variant" if matches and terminal_proven and initial_solvable else "unresolved_policy_outcome"
		if not matches:
			replay_errors.append({"index":expected.index,"record_differences":differences,"reconstruction_error":reconstructed.get("error",""),"isomorphism_errors":certificate.get("errors",[]),"baseline_errors":errors.duplicate()})
		if terminal_proven:
			proven_policy_dead_ends += 1
		if bool(reconstructed.get("ok",false)):
			_merge_resources(totals,reconstructed.resources)
		_append({"kind":"verified_failure","queue_offset":queue_index,"index":expected.index,"expected_record":expected,"actual_record":record,"record_matches":differences.is_empty(),"differences":differences,"verified":matches,"example_locator":{"line":example_line,"byte_offset":example_offset,"byte_length":example_length},"full_terminal_state":example.get("final_state",{}),"continuous_reconstruction":reconstructed,"isomorphism_certificate":certificate,"canonical_witness_binding":witness_binding,"initial_solvable":initial_solvable,"initial_unsatisfiable_proven":false,"terminal_no_winning_suffix":terminal_proven,"classification":classification})
		completed += 1
		journal.flush()
		# Do not retain thousands of full path/state trees in memory.
		examples.clear()
		if completed % 25 == 0:
			print(JSON.stringify({"replay_completed":completed,"requested":requested,"errors":replay_errors.size(),"elapsed_ms":float(Time.get_ticks_usec()-began)/1000.0}))
	var complete: bool = completed == requested and not stopped and replay_errors.is_empty() and errors.is_empty()
	var footer: Dictionary = {"kind":"replay_footer","measurement_completed":complete,"requested_replays":requested,"completed_replays":completed,"queue_offset":replay_offset,"next_queue_offset":replay_offset+completed,"stopped_at_case_boundary":stopped,"policy_dead_ends_with_full_terminal_proof":proven_policy_dead_ends,"initial_unsatisfiable_cases_proven":0,"resources_for_replayed_failure_subset":totals,"errors":replay_errors,"baseline_errors":errors,"elapsed_ms":float(Time.get_ticks_usec()-began)/1000.0,"source_hashes":replay_source.source_hashes,"input_sha256":FileAccess.get_sha256(replay_input),"replayer_sha256":FileAccess.get_sha256("res://tests/replay_campaign_failures.gd")}
	_append(footer)
	journal.flush()
	journal.close()
	footer["journal_sha256"] = FileAccess.get_sha256(replay_output)
	var summary: FileAccess = FileAccess.open(replay_output+".summary.json",FileAccess.WRITE)
	if summary != null:
		summary.store_string(JSON.stringify(footer,"  ")+"\n")
		summary.close()
	print(JSON.stringify({"measurement_completed":complete,"requested_replays":requested,"completed_replays":completed,"errors":replay_errors.size(),"policy_dead_end_proofs":proven_policy_dead_ends,"journal_sha256":footer.journal_sha256,"elapsed_ms":footer.elapsed_ms}))
	quit(0 if complete or (stopped and replay_errors.is_empty() and errors.is_empty()) else 1)


func _append(value: Dictionary) -> void:
	journal.store_string(JSON.stringify(value)+"\n")
	replay_line += 1


func _bind_sources() -> bool:
	if replay_source.get("schema_version",-1) != 1 or not (replay_source.get("expected_records") is Array):
		replay_errors.append("Unsupported failure queue schema.")
		return false
	var files: Dictionary = {"source_data_sha256":DATA_PATH,"base_rules_sha256":"res://scripts/base_rules.gd","variant_sha256":"res://scripts/campaign_variant.gd","navigation_sha256":"res://scripts/campaign_navigation.gd","simulation_sha256":"res://tests/simulate_campaign.gd"}
	for field: String in files:
		if replay_source.get("source_hashes",{}).get(field,"") != FileAccess.get_sha256(files[field]):
			replay_errors.append("Frozen source hash differs: "+field)
	var engine: Dictionary = replay_source.get("engine",{})
	for field: String in ["major","minor","patch","status","build","hash"]:
		if engine.get(field) != Engine.get_version_info().get(field):
			replay_errors.append("Engine version/build differs: "+field)
	if replay_source.get("policies",{}) != DEFINITIONS or replay_source.get("variant_spec","") != VariantBuilder.SPEC or int(replay_source.get("layout_draws_per_run",0)) != 43:
		replay_errors.append("Policy/variant configuration differs from the baseline.")
	if VariantBuilder.normalize_seed(replay_source.get("master_layout_seed")) != replay_source.get("master_layout_seed") or VariantBuilder.normalize_seed(replay_source.get("master_policy_seed")) != replay_source.get("master_policy_seed"):
		replay_errors.append("Master seeds are not normalized.")
	return replay_errors.is_empty()


func _bind_witnesses() -> Dictionary:
	if replay_witness_path.is_empty():
		replay_witness_path = replay_input.get_base_dir().path_join("canonical-winning-witnesses.json")
	var expected: Dictionary = replay_source.get("canonical_witness_binding",{})
	var result: Dictionary = {"ok":false,"report_sha256":"","routes":[],"scope":"Four actual canonical winning replays plus the independently checked coordinate/attribute isomorphism and empty spawn path imply a winning initial variant. This does not claim every spending policy wins."}
	if not FileAccess.file_exists(replay_witness_path) or not bool(expected.get("passed",false)):
		return result
	var parsed := JSON.new()
	if parsed.parse(FileAccess.get_file_as_string(replay_witness_path)) != OK or not (parsed.data is Dictionary):
		return result
	var report: Dictionary = parsed.data
	result.report_sha256 = FileAccess.get_sha256(replay_witness_path)
	var ok: bool = result.report_sha256 == expected.get("sha256","") and report.get("passed",false) == true and report.get("failures",[]).is_empty() and report.get("data_sha256","") == replay_source.source_hashes.source_data_sha256 and report.get("base_rules_sha256","") == replay_source.source_hashes.base_rules_sha256
	for route: Dictionary in report.get("routes",[]):
		ok = ok and bool(route.get("passed",false)) and bool(route.get("final",{}).get("won",false))
		result.routes.append(str(route.get("name","")))
	var names: Array = result.routes.duplicate()
	names.sort()
	result.ok = ok and names == ["balanced","blade","bulwark","frugal"]
	return result


func _record_differences(expected: Dictionary,actual: Dictionary) -> Array:
	var differences: Array = []
	var non_deterministic: Array[String] = ["elapsed_ms","variant_prepare_ms","frontier_ms","execution_ms"]
	for field: String in expected:
		if non_deterministic.has(field):
			continue
		if not actual.has(field) or VariantBuilder.canonical_json(expected[field]) != VariantBuilder.canonical_json(actual[field]):
			differences.append(field)
	for field: String in actual:
		if not expected.has(field) and not non_deterministic.has(field):
			differences.append("extra:"+field)
	return differences


func _reconstruct(record: Dictionary,example: Dictionary) -> Dictionary:
	var generated: Dictionary = VariantBuilder.generate(canonical,str(record.layout_seed))
	if not bool(generated.get("ok",false)):
		return {"ok":false,"error":"Variant regeneration failed during continuous reconstruction."}
	var game = BaseRules.new("")
	game.data = generated.data
	game.reset()
	if VariantBuilder.canonical_json(game.snapshot()) != VariantBuilder.canonical_json(example.get("initial_state",{})):
		return {"ok":false,"error":"Initial full state differs from the retained replay example."}
	var totals: Dictionary = {"gross_battle_damage":0,"gross_healing":0,"gold_spent":0,"gold_gained":0,"keys_consumed":{},"keys_collected":{},"navigation_moves":0,"preview_actual_comparisons":0}
	for decision: Dictionary in example.get("decisions",[]):
		var before: Dictionary = game.snapshot()
		var execution: Dictionary = Navigation.execute(game,decision.path)
		if not bool(execution.get("ok",false)):
			return {"ok":false,"error":"Continuous actual-action reconstruction failed.","decision":decision.get("decision"),"execution":execution}
		var after: Dictionary = game.snapshot()
		if decision.has("before") and (VariantBuilder.canonical_json(_budget(before)) != VariantBuilder.canonical_json(decision.before) or VariantBuilder.canonical_json(_budget(after)) != VariantBuilder.canonical_json(decision.after)):
			return {"ok":false,"error":"Continuous replay resource budget differs from the original decision.","decision":decision.get("decision")}
		var hp_delta: int = int(after.hp)-int(before.hp)
		totals.gross_battle_damage += maxi(0,-hp_delta)
		totals.gross_healing += maxi(0,hp_delta)
		var gold_delta: int = int(after.gold)-int(before.gold)
		totals.gold_spent += maxi(0,-gold_delta)
		totals.gold_gained += maxi(0,gold_delta)
		for color: String in before["keys"]:
			var delta: int = int(after["keys"][color])-int(before["keys"][color])
			totals.keys_consumed[color] = int(totals.keys_consumed.get(color,0))+maxi(0,-delta)
			totals.keys_collected[color] = int(totals.keys_collected.get(color,0))+maxi(0,delta)
		totals.navigation_moves += int(execution.get("moves",0))
		totals.preview_actual_comparisons += int(execution.get("preview_comparisons",0))
	if VariantBuilder.canonical_json(game.snapshot()) != VariantBuilder.canonical_json(example.get("final_state",{})) or VariantBuilder.canonical_json(_budget(game.state)) != VariantBuilder.canonical_json(record.final):
		return {"ok":false,"error":"The reconstructed final full state or original final budget differs."}
	var proof: Dictionary = Navigation.frontier(game,0,true,Navigation.prepare(game))
	var no_action: bool = bool(proof.get("complete",false)) and proof.get("options",[]).is_empty()
	if record.outcome == "dead_end" and not no_action:
		return {"ok":false,"error":"The original dead end lacks a complete no-action terminal proof.","global_navigation_proof":proof}
	return {"ok":true,"resources":totals,"final_state_sha256":VariantBuilder.content_hash(game.snapshot()),"terminal_no_resource_action":no_action,"global_navigation_proof":proof,"scope":"A second continuous replay of the full retained path through actual BaseRules actions, independent of the original policy selector pass. One selected frontier resource action per decision makes before/after HP and key differences unambiguous."}


func _merge_resources(total: Dictionary,part: Dictionary) -> void:
	for key: String in ["gross_battle_damage","gross_healing","gold_spent","gold_gained","navigation_moves","preview_actual_comparisons"]:
		total[key] = int(total[key])+int(part[key])
	for key: String in ["keys_consumed","keys_collected"]:
		for color: String in part[key]:
			total[key][color] = int(total[key].get(color,0))+int(part[key][color])


func _map(cell: Array,width: int,height: int,flags: Dictionary) -> Array:
	return [width-1-int(cell[0]) if bool(flags.h) else int(cell[0]),height-1-int(cell[1]) if bool(flags.v) else int(cell[1])]


func _isomorphism_certificate(layout_seed: String) -> Dictionary:
	var generated: Dictionary = VariantBuilder.generate(canonical,layout_seed)
	var certificate: Dictionary = {"ok":false,"errors":[],"layout_seed":layout_seed,"canonical_hash":"","layout_hash":"","floors":[],"spawn_connectivity":{},"scope":"Every H/V cell image, cardinal edge, stable object ID and complete object attribute dictionary is compared. Stair target coordinates use the destination floor's mirror. A safe empty path connects the resolved spawn to the mirrored canonical default spawn."}
	if not bool(generated.get("ok",false)):
		certificate.errors.append("Could not regenerate the bound variant.")
		return certificate
	certificate.canonical_hash = generated.canonical_sha256
	certificate.layout_hash = generated.transformed_sha256
	var sources: Dictionary = {}
	var targets: Dictionary = {}
	for floor: Dictionary in canonical.floors:
		sources[int(floor.id)] = floor
	for floor: Dictionary in generated.data.floors:
		targets[int(floor.id)] = floor
	for floor_id: int in range(1,22):
		var source: Dictionary = sources[floor_id]
		var target: Dictionary = targets[floor_id]
		var flags: Dictionary = generated.mirrors[str(floor_id)]
		var width: int = str(source.grid[0]).length()
		var height: int = source.grid.size()
		var row: Dictionary = {"floor_id":floor_id,"width":width,"height":height,"mirror":flags,"verified_cells":0,"verified_cardinal_edges":0,"objects":[]}
		for y: int in range(height):
			for x: int in range(width):
				var mapped: Array = _map([x,y],width,height,flags)
				if str(source.grid[y])[x] != str(target.grid[int(mapped[1])])[int(mapped[0])]:
					certificate.errors.append("Cell mirror mismatch at floor "+str(floor_id))
				row.verified_cells += 1
				if str(source.grid[y])[x] == "#":
					continue
				for delta: Vector2i in [Vector2i.RIGHT,Vector2i.DOWN]:
					var next := Vector2i(x+delta.x,y+delta.y)
					if next.x < width and next.y < height and str(source.grid[next.y])[next.x] != "#":
						var mapped_next: Array = _map([next.x,next.y],width,height,flags)
						if absi(int(mapped[0])-int(mapped_next[0]))+absi(int(mapped[1])-int(mapped_next[1])) != 1:
							certificate.errors.append("Cardinal adjacency was not preserved.")
						row.verified_cardinal_edges += 1
		var by_id: Dictionary = {}
		for item: Dictionary in target.objects:
			by_id[str(item.id)] = item
		if by_id.size() != source.objects.size():
			certificate.errors.append("Object bijection count differs at floor "+str(floor_id))
		for item: Dictionary in source.objects:
			var expected: Dictionary = item.duplicate(true)
			expected.pos = _map(item.pos,width,height,flags)
			if item.has("facing"):
				expected.facing = [-int(item.facing[0]) if bool(flags.h) else int(item.facing[0]),-int(item.facing[1]) if bool(flags.v) else int(item.facing[1])]
			if item.kind == "stairs":
				var destination: Dictionary = sources[int(item.target.floor)]
				expected.target.pos = _map(item.target.pos,str(destination.grid[0]).length(),destination.grid.size(),generated.mirrors[str(int(item.target.floor))])
			var actual: Dictionary = by_id.get(str(item.id),{})
			var equal: bool = VariantBuilder.canonical_json(expected) == VariantBuilder.canonical_json(actual)
			if not equal:
				certificate.errors.append("Object attributes/position differ: "+str(item.id))
			var object_row: Dictionary = {"id":item.id,"kind":item.kind,"source_pos":item.pos,"expected_pos":expected.pos,"actual_pos":actual.get("pos",[]),"expected_all_attributes_sha256":VariantBuilder.content_hash(expected),"actual_all_attributes_sha256":VariantBuilder.content_hash(actual),"all_attributes_match":equal}
			if item.kind == "stairs":
				object_row["source_target"] = item.target
				object_row["expected_target"] = expected.target
				object_row["actual_target"] = actual.get("target",{})
			row.objects.append(object_row)
		var expected_spawn: Array = _map(source.spawn,width,height,flags)
		if floor_id == 1:
			expected_spawn = generated.resolved_start
		if VariantBuilder.canonical_json(expected_spawn) != VariantBuilder.canonical_json(target.spawn):
			certificate.errors.append("Floor spawn differs from its declared transform.")
		certificate.floors.append(row)
	certificate.spawn_connectivity = _spawn_certificate(sources[1],targets[1],generated.mirrors["1"],generated.resolved_start)
	if not bool(certificate.spawn_connectivity.get("ok",false)):
		certificate.errors.append("Resolved spawn is not connected by a neutral empty path to the transformed canonical spawn.")
	certificate.ok = certificate.errors.is_empty()
	return certificate


func _spawn_certificate(source: Dictionary,target: Dictionary,flags: Dictionary,resolved: Array) -> Dictionary:
	var width: int = str(source.grid[0]).length()
	var height: int = source.grid.size()
	var selected: Array = []
	for candidate: Array in source.safe_start_candidates:
		if VariantBuilder.canonical_json(_map(candidate,width,height,flags)) == VariantBuilder.canonical_json(resolved):
			selected = candidate
	var result: Dictionary = {"ok":false,"canonical_candidate":selected,"resolved_start":resolved,"canonical_default_spawn":source.spawn,"canonical_empty_path":[],"mirrored_empty_path":[]}
	if selected.is_empty():
		return result
	var occupied: Dictionary = {}
	var transformed_occupied: Dictionary = {}
	for item: Dictionary in source.objects:
		occupied[Vector2i(int(item.pos[0]),int(item.pos[1]))] = true
	for item: Dictionary in target.objects:
		transformed_occupied[Vector2i(int(item.pos[0]),int(item.pos[1]))] = true
	var start := Vector2i(int(selected[0]),int(selected[1]))
	var goal := Vector2i(int(source.spawn[0]),int(source.spawn[1]))
	var queue: Array[Vector2i] = [start]
	var previous: Dictionary = {start:start}
	var head: int = 0
	while head < queue.size() and not previous.has(goal):
		var current: Vector2i = queue[head]
		head += 1
		for delta: Vector2i in [Vector2i.RIGHT,Vector2i.LEFT,Vector2i.DOWN,Vector2i.UP]:
			var next: Vector2i = current+delta
			if next.x < 0 or next.y < 0 or next.x >= width or next.y >= height or previous.has(next) or occupied.has(next) or str(source.grid[next.y])[next.x] == "#":
				continue
			previous[next] = current
			queue.append(next)
	if not previous.has(goal) or occupied.has(start):
		return result
	var path: Array = []
	var cursor: Vector2i = goal
	path.push_front([cursor.x,cursor.y])
	while cursor != start:
		cursor = previous[cursor]
		path.push_front([cursor.x,cursor.y])
	for cell: Array in path:
		var mapped: Array = _map(cell,width,height,flags)
		if transformed_occupied.has(Vector2i(int(mapped[0]),int(mapped[1]))) or str(target.grid[int(mapped[1])])[int(mapped[0])] == "#":
			return result
		result.mirrored_empty_path.append(mapped)
	result.canonical_empty_path = path
	result.ok = true
	return result
