class_name CampaignNavigation
extends RefCounted
## Complete ordinary-action frontier shared by failure assessment and search.
## Battle costs always come from the supplied rule object's combat() method.

const DELTAS: Array[Vector2i] = [Vector2i.RIGHT,Vector2i.LEFT,Vector2i.DOWN,Vector2i.UP]
const RESOURCE_KINDS: Array[String] = ["key","potion","atk","def","gold"]


static func prepare(game: RefCounted) -> Dictionary:
	# CampaignRules seals the transformed tree recursively. Hold that immutable
	# dictionary identity, so a new mirrored variant cannot reuse stale indexes.
	var data: Dictionary = game.data
	var floor_ids: Dictionary = {}
	var object_cache: Dictionary = {}
	var errors: Array = []
	for floor_index: int in range(data.get("floors",[]).size()):
		var floor_id: int = int(data.floors[floor_index].get("id",floor_index+1))
		if floor_ids.has(floor_id):
			errors.append("Duplicate floor id.")
		floor_ids[floor_id] = floor_index
		var indexed: Dictionary = {}
		for item: Dictionary in data.floors[floor_index].get("objects",[]):
			var cell := Vector2i(int(item.pos[0]),int(item.pos[1]))
			if indexed.has(cell):
				errors.append("Multiple objects occupy one cell on floor " + str(floor_index))
			indexed[cell] = item
		indexed.make_read_only()
		object_cache[floor_index] = indexed
	floor_ids.make_read_only()
	object_cache.make_read_only()
	errors.make_read_only()
	var prepared: Dictionary = {"data":data,"floor_ids":floor_ids,"object_cache":object_cache,"errors":errors}
	prepared.make_read_only()
	return prepared


static func frontier(game: RefCounted, max_nodes: int = 0, include_proof: bool = true, prepared: Dictionary = {}) -> Dictionary:
	return _scan(game,max_nodes,include_proof,-1,prepared)


static func frontier_local(game: RefCounted, floor_horizon: int = 0, max_nodes: int = 0, include_proof: bool = false, prepared: Dictionary = {}) -> Dictionary:
	# A policy horizon never certifies failure, even if its local queue empties.
	return _scan(game,max_nodes,include_proof,maxi(0,floor_horizon),prepared)


static func _scan(game: RefCounted, max_nodes: int, include_proof: bool, floor_horizon: int, prepared: Dictionary) -> Dictionary:
	var state: Dictionary = game.state
	var data: Dictionary = game.data
	var result: Dictionary = {"complete":false,"options":[],"reachable":0,"nodes":[],"edges":[],"blocked":[],"shop_offers":[],"errors":[],"reason":"","scope":"global" if floor_horizon < 0 else "local-policy","floor_horizon":floor_horizon,"omitted_portals":0,"cache_reused":false}
	if state.is_empty() or not (data.get("floors") is Array) or data.floors.is_empty():
		result.reason = "No loaded campaign."
		return result
	if bool(state.get("won",false)):
		result.reason = "Already won; no failure assessment is needed."
		return result
	if game.has_method("is_failed") and bool(game.is_failed()):
		result.reason = "This run is frozen by the failure state; no active-navigation BFS was performed."
		result["terminal"] = "failed"
		return result
	var floor_ids: Dictionary = {}
	var object_cache: Dictionary = {}
	if prepared.get("data") is Dictionary and prepared.get("floor_ids") is Dictionary and prepared.get("object_cache") is Dictionary and is_same(prepared.data,data):
		floor_ids = prepared.floor_ids
		object_cache = prepared.object_cache
		result.errors.append_array(prepared.get("errors",[]))
		result.cache_reused = true
	else:
		for floor_index: int in range(data.floors.size()):
			var floor_id: int = int(data.floors[floor_index].get("id",floor_index+1))
			if floor_ids.has(floor_id):
				result.errors.append("Duplicate floor id.")
			floor_ids[floor_id] = floor_index
	var cleared: Dictionary = {}
	for item_id: String in state.get("cleared",[]):
		cleared[item_id] = true
	var start := Vector3i(int(state.floor),int(state.pos[0]),int(state.pos[1]))
	if not _walkable(data,start):
		result.reason = "The current cell is not walkable."
		return result
	var queue: Array[Vector3i] = [start]
	var previous: Dictionary = {start:{}}
	var offered: Dictionary = {}
	var boundaries: Dictionary = {}
	var shops: Dictionary = {}
	var head: int = 0
	while head < queue.size():
		if max_nodes > 0 and head >= max_nodes:
			result.reason = "Navigation node budget reached; the frontier is incomplete."
			break
		var node: Vector3i = queue[head]
		head += 1
		if include_proof:
			result.nodes.append([node.x,node.y,node.z])
		var here: Dictionary = _item_at(data,node,cleared,object_cache,result.errors)
		if str(here.get("kind","")) == "shop":
			_shop_options(game,data,state,here,node,previous,offered,shops,result.options,result.errors)
		if str(here.get("kind","")) == "stairs":
			var target: Variant = _stair_target(data,here,floor_ids)
			if target == null:
				result.errors.append("Invalid stair target: " + str(here.get("id","")))
			elif floor_horizon >= 0 and absi(int(target.x)-start.x) > floor_horizon:
				result.omitted_portals += 1
			else:
				var action: Dictionary = {"kind":"stairs"}
				_edge(node,target,action,include_proof,result.edges)
				_visit(target,node,action,previous,queue)
		for delta: Vector2i in DELTAS:
			var next := Vector3i(node.x,node.y+delta.x,node.z+delta.y)
			if not _walkable(data,next):
				continue
			var item: Dictionary = _item_at(data,next,cleared,object_cache,result.errors)
			var kind: String = str(item.get("kind",""))
			var action: Dictionary = {"kind":"move","dx":delta.x,"dy":delta.y}
			if kind in ["","shop","stairs"]:
				if kind == "shop":
					_shop_options(game,data,state,item,node,previous,offered,shops,result.options,result.errors)
				var destination: Variant = _stair_target(data,item,floor_ids) if kind == "stairs" else next
				if destination == null:
					result.errors.append("Invalid stair target: " + str(item.get("id","")))
					continue
				if floor_horizon >= 0 and absi(int(destination.x)-start.x) > floor_horizon:
					result.omitted_portals += 1
					continue
				_edge(node,destination,action,include_proof,result.edges)
				_visit(destination,node,action,previous,queue)
				continue
			var item_id: String = str(item.get("id",""))
			if item_id.is_empty():
				result.errors.append("An occupied cell has no stable id.")
				continue
			if not boundaries.has(item_id):
				var boundary: Dictionary = {"id":item_id,"kind":kind,"floor_index":next.x,"cell":[next.y,next.z],"legal":false,"reason":"","approachable_from":[]}
				var preview: Dictionary = {}
				if kind == "enemy":
					if not data.get("enemies",{}).has(item.get("type","")):
						result.errors.append("Enemy type is missing: " + item_id)
					else:
						preview = game.combat(data.enemies[item.type])
						boundary.legal = bool(preview.get("win",false))
						boundary.reason = str(preview.get("reason",""))
						boundary["combat"] = preview
				elif kind == "door":
					var color: String = str(item.get("type","yellow"))
					boundary["key_color"] = color
					boundary["keys_owned"] = int(state.get("keys",{}).get(color,0))
					boundary.legal = int(boundary.keys_owned) >= 1
					boundary.reason = "One matching key is available." if bool(boundary.legal) else "No matching key."
				elif RESOURCE_KINDS.has(kind):
					boundary.legal = true
					boundary.reason = "Uncollected reachable resource."
				else:
					boundary.reason = "Unsupported object kind."
					result.errors.append("Unsupported object kind: " + kind)
				boundaries[item_id] = boundary
				if bool(boundary.legal) and not offered.has(item_id):
					var path: Array = _path(previous,node)
					path.append(action)
					offered[item_id] = true
					result.options.append({"id":item_id,"kind":kind,"item":item,"preview":preview,"path":path})
			if include_proof:
				boundaries[item_id].approachable_from.append([node.x,node.y,node.z])
	result.reachable = head
	result["discovered_nodes"] = previous.size()
	result["queue_exhausted"] = head == queue.size()
	result.complete = floor_horizon < 0 and bool(result.queue_exhausted) and result.errors.is_empty()
	if result.complete:
		result.reason = "All reachable clear/shop/stair nodes and adjacent resource actions were exhausted."
	elif floor_horizon >= 0 and bool(result.queue_exhausted):
		result.reason = "Only the policy floor horizon was exhausted. Global completeness and failure are not claimed."
	result.blocked = boundaries.values()
	result.shop_offers = shops.values()
	result["legal_resource_actions"] = result.options.size()
	result["proof_scope"] = "Ordinary move/use_stairs/buy in this run. Navigation preserves the resource vector; resources, enemies and closed doors form the decision boundary. Restart, respawn and explicit unsafe challenge are outside this frontier."
	return result


static func _walkable(data: Dictionary, node: Vector3i) -> bool:
	if node.x < 0 or node.x >= data.floors.size():
		return false
	var grid: Array = data.floors[node.x].grid
	return node.z >= 0 and node.z < grid.size() and node.y >= 0 and node.y < str(grid[node.z]).length() and str(grid[node.z])[node.y] != "#"


static func _item_at(data: Dictionary, node: Vector3i, cleared: Dictionary, cache: Dictionary, errors: Array) -> Dictionary:
	if not cache.has(node.x):
		var indexed: Dictionary = {}
		for item: Dictionary in data.floors[node.x].objects:
			var cell := Vector2i(int(item.pos[0]),int(item.pos[1]))
			if indexed.has(cell):
				errors.append("Multiple objects occupy one cell on floor " + str(node.x))
			indexed[cell] = item
		cache[node.x] = indexed
	var item: Dictionary = cache[node.x].get(Vector2i(node.y,node.z),{})
	return {} if cleared.has(str(item.get("id",""))) else item


static func _stair_target(data: Dictionary, item: Dictionary, floor_ids: Dictionary) -> Variant:
	var target: Dictionary = item.get("target",{})
	if not floor_ids.has(int(target.get("floor",-1))) or not (target.get("pos") is Array) or target.pos.size() != 2:
		return null
	var node := Vector3i(int(floor_ids[int(target.floor)]),int(target.pos[0]),int(target.pos[1]))
	return node if _walkable(data,node) else null


static func _visit(target: Vector3i, parent: Vector3i, action: Dictionary, previous: Dictionary, queue: Array[Vector3i]) -> void:
	if not previous.has(target):
		previous[target] = {"parent":parent,"action":action}
		queue.append(target)


static func _edge(from: Vector3i, to: Vector3i, action: Dictionary, include_proof: bool, edges: Array) -> void:
	if include_proof:
		edges.append({"from":[from.x,from.y,from.z],"to":[to.x,to.y,to.z],"action":action})


static func _path(previous: Dictionary, destination: Vector3i) -> Array:
	var path: Array = []
	var node: Vector3i = destination
	while not previous[node].is_empty():
		var link: Dictionary = previous[node]
		path.push_front(link.action)
		node = link.parent
	return path


static func _shop_options(_game: RefCounted, data: Dictionary, state: Dictionary, item: Dictionary, at: Vector3i, previous: Dictionary, offered: Dictionary, shops: Dictionary, options: Array, errors: Array) -> void:
	# Base buy() selects the first adjacent shop in declared object order.
	# Match that dispatch even if a later map places two shops close together.
	var selected_shop: String = ""
	for candidate: Dictionary in data.floors[at.x].objects:
		if candidate.get("kind","") == "shop" and absi(int(candidate.pos[0])-at.y)+absi(int(candidate.pos[1])-at.z) <= 1:
			selected_shop = str(candidate.id)
			break
	if selected_shop != str(item.id):
		return
	if not data.get("shops",{}).has(item.get("type","")):
		errors.append("Shop type is missing: " + str(item.get("id","")))
		return
	for offer: Dictionary in data.shops[item.type].offers:
		var id: String = str(item.id)+"/"+str(offer.id)
		if shops.has(id):
			continue
		var bought: int = int(state.get("purchases",{}).get(id,0))
		var stock: int = int(offer.get("limit",1))
		var cost: int = int(offer.cost)
		var legal: bool = bought < stock and int(state.gold) >= cost
		var supported: bool = str(offer.get("kind","")) in ["atk","def","potion"] and cost >= 0
		if not supported:
			errors.append("Unsupported shop offer: " + id)
			legal = false
		shops[id] = {"id":id,"shop":item.id,"offer":offer.id,"cost":cost,"gold_owned":int(state.gold),"bought":bought,"limit":stock,"legal":legal,"reason":"Affordable and in stock." if legal else "Unaffordable or out of stock."}
		if legal and not offered.has(id):
			var path: Array = _path(previous,at)
			path.append({"kind":"buy","offer":str(offer.id)})
			offered[id] = true
			options.append({"id":id,"kind":"buy","item":item,"offer":offer,"path":path})


static func execute(game: RefCounted, path: Array) -> Dictionary:
	var comparisons: int = 0
	var moves: int = 0
	for action: Dictionary in path:
		var state: Dictionary = game.state
		var before_hp: int = int(state.hp)
		var preview: Dictionary = {}
		var action_result: Dictionary
		match str(action.get("kind","")):
			"move":
				var cell: Array = [int(state.pos[0])+int(action.dx),int(state.pos[1])+int(action.dy)]
				preview = game.inspect(cell).get("combat",{})
				action_result = game.move(int(action.dx),int(action.dy))
				moves += 1
			"stairs":
				action_result = game.use_stairs()
				moves += 1
			"buy":
				action_result = game.buy(str(action.offer))
			_:
				return {"ok":false,"error":"Unsupported navigation action.","action":action,"preview_comparisons":comparisons,"moves":moves}
		if not bool(action_result.get("ok",false)):
			return {"ok":false,"error":"A planned ordinary action was rejected.","action":action,"result":action_result,"preview_comparisons":comparisons,"moves":moves}
		if not preview.is_empty():
			comparisons += 1
			var actual: int = before_hp-int(game.state.hp)
			if not bool(preview.get("win",false)) or actual != int(preview.damage):
				return {"ok":false,"error":"Battle preview differed from actual deduction.","preview":preview,"actual_damage":actual,"preview_comparisons":comparisons,"moves":moves}
	return {"ok":true,"preview_comparisons":comparisons,"moves":moves}
