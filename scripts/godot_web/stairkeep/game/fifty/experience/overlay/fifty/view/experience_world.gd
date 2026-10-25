extends "res://fifty/view/world.gd"
## First-chapter presentation revision. Rules and authored resources stay authoritative.
## Existing same-character CC0 frames, not a new art set or physics controller.

const Assets = preload("res://fifty/view/experience_assets.gd")
const UI_FONT_PATH := "res://assets/experience/fonts/cjk-ui.otf"

var _map_stamp := ""
var _nodes: Dictionary = {}
var _wall_nodes: Array = []
var _hero_node: Node2D
var _hero_body: AnimatedSprite2D
var _route_layer: Node2D
var _route_cells: Array = []
var _animating := false
var _facing := 2
var _motion_serial := 0
var _ui_font: Font
var _hint := ""
var _last_cleared: Array = []
var _hint_label: Label
var _clipper: Control
var _overview_mode := false
var _view_stamp := ""
var _last_fit_rect := Rect2()
var _camera_target := Vector2.ZERO
var _camera_tween: Tween
var _direction_layer: Node2D
var _direction_cells: Array = []


func configure(rules: Object) -> void:
	_map_stamp = ""
	_last_cleared.clear()
	_route_cells.clear()
	_direction_cells.clear()
	_view_stamp = ""
	super.configure(rules)


func current_animation_busy() -> bool:
	return _animating


func _font() -> Font:
	if _ui_font == null:
		_ui_font = load(UI_FONT_PATH) as Font
		if _ui_font is FontFile:
			(_ui_font as FontFile).allow_system_fallback = false
	return _ui_font


func refresh() -> void:
	if _rules == null or _rules.state.is_empty():
		return
	var floor_data: Dictionary = _rules.floor_data()
	var stamp: String = str(_rules.state.get("floor", -1)) + ":" + str(floor_data.get("grid", [])) + ":" + str(floor_data.get("objects", []))
	for old_id: String in _last_cleared:
		if not _rules.state["cleared"].has(old_id):
			_map_stamp = "" # Full restore can close gates on an already visited floor.
			break
	if _board == null or stamp != _map_stamp:
		_view_stamp = ""
		if is_instance_valid(_camera_tween): _camera_tween.kill()
		_route_cells.clear()
		_direction_cells.clear()
		_motion_serial += 1
		_nodes.clear()
		_wall_nodes.clear()
		_route_layer = null
		_direction_layer = null
		_map_stamp = stamp
		super.refresh()
		_ensure_clipper()
		_board.reparent(_clipper,true)
		if int(_rules.state.get("floor",0)) == 0:
			_floor.modulate = Color("f6dfb4")
		# One warm, level floor language; bumps are not a walkability code.
		var rows: Array = _rules.floor_data().get("grid", [])
		for y: int in range(rows.size()):
			for x: int in range(str(rows[y]).length()):
				if _rules.walkable([x, y]):
					_floor.set_cell(Vector2i(x,y), 2, Vector2i.ZERO)
		_route_layer = Node2D.new()
		_route_layer.name = "WalkRouteFeedback"
		_route_layer.z_index = -1
		_board.add_child(_route_layer)
		_direction_layer = Node2D.new()
		_direction_layer.z_index = -1
		_board.add_child(_direction_layer)
	else:
		_sync_objects()
		if not _animating and is_instance_valid(_hero_node):
			_hero_node.position = _center(_rules.state["pos"])
	# Keep opened door frames as landmarks, including after returning to a floor.
	for item: Dictionary in _rules.floor_data().get("objects", []):
		if item.get("kind","") == "door" and _rules.state["cleared"].has(str(item["id"])):
			_show_open_door(item)
	set_route_preview(_route_cells)
	set_direction_candidates(_direction_cells)
	_update_occlusion()
	_update_badge_visibility()
	_last_cleared = _rules.state["cleared"].duplicate()


func _center(cell: Array) -> Vector2:
	return _floor.map_to_local(Vector2i(int(cell[0]), int(cell[1])))


func _add_pier(center: Vector2, _seed_index: int) -> void:
	# Exposed outside faces only, rather than a deep pillar under every tile.
	var cell: Vector2i = _floor.local_to_map(center)
	var body := Node2D.new()
	body.position = center
	body.z_index = -20
	_board.add_child(body)
	if not _rules.walkable([cell.x,cell.y+1]):
		_polygon(PackedVector2Array([Vector2(-128,0),Vector2(0,64),Vector2(0,130),Vector2(-128,66)]),Color("21394a"),body)
	if not _rules.walkable([cell.x+1,cell.y]):
		_polygon(PackedVector2Array([Vector2(0,64),Vector2(128,0),Vector2(128,66),Vector2(0,130)]),Color("152d3b"),body)


func _add_wall(cell: Array) -> void:
	var wall := Node2D.new()
	wall.position = _center(cell)
	wall.name = "SolidWall"
	_actors.add_child(wall)
	# Full tile caps join adjacent masonry; front faces only border real paths.
	var top := -26.0
	if _rules.walkable([int(cell[0]),int(cell[1])+1]):
		_polygon(PackedVector2Array([Vector2(-128,top),Vector2(0,64+top),Vector2(0,64),Vector2(-128,0)]),Color("3b5260"),wall)
	if _rules.walkable([int(cell[0])+1,int(cell[1])]):
		_polygon(PackedVector2Array([Vector2(0,64+top),Vector2(128,top),Vector2(128,0),Vector2(0,64)]),Color("293d4b"),wall)
	_polygon(_diamond(128,64),Color("536774"),wall,Vector2(0,top))
	var back_edge: bool = (_rules.walkable([int(cell[0])+1,int(cell[1])]) or _rules.walkable([int(cell[0]),int(cell[1])+1])) and not (_rules.walkable([int(cell[0])-1,int(cell[1])]) or _rules.walkable([int(cell[0]),int(cell[1])-1]))
	var clear_of_targets := true
	for item: Dictionary in _rules.floor_data().get("objects",[]):
		var at: Array = item["pos"]
		if absi(int(at[0])-int(cell[0])) + absi(int(at[1])-int(cell[1])) <= 1:
			clear_of_targets = false
	if int(_rules.state.get("floor",0)) != 0 and back_edge and clear_of_targets and (int(cell[0])*3+int(cell[1])) % 11 == 0:
		var column := _sprite("stoneColumn_N.png",Vector2(-128,-448))
		column.modulate = Color("91a6ad")
		wall.add_child(column)
	_wall_nodes.append(wall)


func _add_hero() -> void:
	_hero_node = Node2D.new()
	_hero_node.name = "PersistentPlayer"
	_hero_node.position = _center(_rules.state["pos"])
	_actors.add_child(_hero_node)
	_polygon(_diamond(69,33),Color("142b3980"),_hero_node)
	var rim: PackedVector2Array = _diamond(78,37)
	rim.append(rim[0])
	_line(rim,CYAN,5,_hero_node)
	_hero_body = AnimatedSprite2D.new()
	_hero_body.name = "SameCharacterActionFrames"
	_hero_body.sprite_frames = Assets.get_hero_frames()
	_hero_body.centered = false
	_hero_body.offset = Assets.get_hero_sprite_offset(false)
	_hero_body.scale = Vector2(1.45,1.45)
	_hero_body.modulate = Color("f2eee2")
	_hero_node.add_child(_hero_body)
	_hero_body.play(StringName("idle_%d" % _facing))
	_glow(_hero_node,Vector2(22,-112),Color("ffce8a"),0.36)


func _add_object(item: Dictionary) -> void:
	var before: int = _actors.get_child_count()
	super._add_object(item)
	if _actors.get_child_count() <= before:
		return
	var node: Node2D = _actors.get_child(_actors.get_child_count()-1) as Node2D
	_nodes[str(item["id"])] = node
	node.set_meta("object_kind",str(item.get("kind","")))
	node.set_meta("cell",item["pos"].duplicate())
	var kind: String = str(item.get("kind",""))
	if kind == "stairs":
		var ascent: String = _stairs_ascent_direction(item)
		for child: Node in node.get_children():
			if child is Sprite2D and (child as Sprite2D).texture != _halo_texture:
				(child as Sprite2D).texture = Assets.get_stairs_ascent_texture(ascent)
				(child as Sprite2D).offset = Assets.get_stairs_sprite_offset(Assets.get_stairs_source_direction_for_ascent(ascent))
				break
		for label: Node in node.find_children("*","Label",true,false):
			label.queue_free()
		_symbol_badge(node,("上楼" if item.get("direction","up") == "up" else "下楼") + "  %d层" % int(item["target"]["floor"]),CYAN,-180)
		if int(_rules.state.get("floor",0)) == 0 and item.get("direction","") == "up":
			var portal_direction: String = _door_direction(item)
			var portal := Sprite2D.new()
			portal.texture = Assets.get_open_door_texture(portal_direction)
			portal.centered = false
			portal.offset = Assets.get_door_sprite_offset(portal_direction)
			portal.modulate = Color("7bcac8")
			node.add_child(portal)
			node.move_child(portal,0)
	elif kind == "door":
		for child: Node in node.get_children():
			if child is Sprite2D:
				node.remove_child(child)
				child.queue_free()
				break
		var direction: String = _door_direction(item)
		var gate := Sprite2D.new()
		gate.texture = Assets.get_closed_door_texture(direction)
		gate.centered = false
		gate.offset = Assets.get_door_sprite_offset(direction)
		gate.modulate = Color("88c9db") if item.get("type","yellow") == "blue" else Color("e7c18a")
		node.add_child(gate)
		node.move_child(gate,0)
		_symbol_badge(node,"蓝门" if item.get("type","yellow") == "blue" else "黄门",CYAN if item.get("type","yellow") == "blue" else GOLD,-180)
	elif kind == "shop":
		for label: Node in node.find_children("*","Label",true,false):
			(label as Label).text = "商店"
	elif kind in ["key","potion","atk","def","gold"]:
		var names := {"key":"钥匙","potion":"生命","atk":"攻击","def":"防御","gold":"金币"}
		_symbol_badge(node,str(names[kind])+" +%d" % int(item.get("amount",1)),GOLD,-145)
		var label: Label = node.get_child(node.get_child_count()-1) as Label
		if label != null:
			label.set_meta("nearby_only",true)
	elif kind == "npc":
		for label: Node in node.find_children("*","Label",true,false):
			(label as Label).text = "交谈"
	elif kind == "event":
		for label: Node in node.find_children("*","Label",true,false):
			(label as Label).text = "线索"
	elif kind == "boundary":
		for label: Node in node.find_children("*","Label",true,false):
			(label as Label).text = "后续未开放"


func _add_enemy(parent: Node2D,item: Dictionary) -> void:
	super._add_enemy(parent,item)
	var cost: Dictionary = _rules.combat(_rules.data["enemies"][str(item["type"])])
	for label: Node in parent.find_children("*","Label",true,false):
		(label as Label).text = "损血 %d" % int(cost["damage"]) if bool(cost.get("win",false)) else "无法战胜"


func _symbol_badge(parent: Node2D,text: String,color: Color,top: float) -> void:
	super._symbol_badge(parent,text,color,top)
	var badge: Label = parent.get_child(parent.get_child_count()-1) as Label
	if badge != null:
		badge.add_theme_font_override("font",_font())
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE


func _sync_objects() -> void:
	for item: Dictionary in _rules.floor_data().get("objects",[]):
		var id: String = str(item["id"])
		if item.get("kind","") == "door" and _rules.state["cleared"].has(id):
			_show_open_door(item)
			continue
		var visible: Dictionary = _rules.object_at(item["pos"])
		var should_show: bool = not visible.is_empty() and str(visible.get("id","")) == id
		if not should_show and _nodes.has(id):
			var old: Node = _nodes[id]
			_nodes.erase(id)
			if is_instance_valid(old):
				old.queue_free()
		elif should_show and not _nodes.has(id):
			_add_object(item)
	# Damage labels depend on current equipment, but animated sprites keep phase.
	for item: Dictionary in _rules.floor_data().get("objects",[]):
		if item.get("kind","") != "enemy" or not _nodes.has(str(item["id"])):
			continue
		var cost: Dictionary = _rules.combat(_rules.data["enemies"][str(item["type"])])
		for label: Node in (_nodes[str(item["id"])] as Node).find_children("*","Label",true,false):
			(label as Label).text = "损血 %d" % int(cost["damage"]) if bool(cost.get("win",false)) else "无法战胜"


func _show_open_door(item: Dictionary) -> void:
	var id: String = str(item["id"])
	var node: Node2D = _nodes.get(id) as Node2D
	if is_instance_valid(node) and bool(node.get_meta("opened",false)):
		return
	if is_instance_valid(node):
		_nodes.erase(id)
		node.queue_free()
	node = Node2D.new()
	node.name = id
	node.position = _center(item["pos"])
	node.set_meta("opened",true)
	var door := Sprite2D.new()
	var direction: String = _door_direction(item)
	door.texture = Assets.get_open_door_texture(direction)
	door.centered = false
	door.offset = Assets.get_door_sprite_offset(direction)
	door.modulate = Color("88aebd") if item.get("type","yellow") == "blue" else Color("c9b58f")
	node.add_child(door)
	_actors.add_child(node)
	_nodes[id] = node


func _door_direction(item: Dictionary) -> String:
	var at: Array = item["pos"]
	var along_x: int = int(_rules.walkable([int(at[0])-1,int(at[1])]))+int(_rules.walkable([int(at[0])+1,int(at[1])]))
	var along_y: int = int(_rules.walkable([int(at[0]),int(at[1])-1]))+int(_rules.walkable([int(at[0]),int(at[1])+1]))
	return "E" if along_x > along_y else "N"


func _stairs_ascent_direction(item: Dictionary) -> String:
	var at: Array = item["pos"]
	for adjacent: Vector2i in [Vector2i.UP,Vector2i.LEFT,Vector2i.DOWN,Vector2i.RIGHT]:
		if not _rules.walkable([int(at[0])+adjacent.x,int(at[1])+adjacent.y]): continue
		var ascent: Vector2i = -adjacent if item.get("direction","up") == "up" else adjacent
		if ascent.x > 0: return "E"
		if ascent.x < 0: return "W"
		if ascent.y > 0: return "S"
		return "N"
	return "N"


func _animate_open_door(item: Dictionary) -> void:
	var id: String = str(item["id"])
	var closed: Node2D = _nodes.get(id) as Node2D
	# Detach only the lookup, so the same-position closed image can cross-fade.
	_nodes.erase(id)
	_show_open_door(item)
	var opened: Node2D = _nodes.get(id) as Node2D
	if is_instance_valid(opened):
		opened.modulate.a = 0.0
	var tween := create_tween().set_parallel(true)
	if is_instance_valid(closed):
		tween.tween_property(closed,"modulate:a",0.0,0.22)
	if is_instance_valid(opened):
		tween.tween_property(opened,"modulate:a",1.0,0.22)
	await tween.finished
	if is_instance_valid(closed):
		closed.queue_free()


func set_route_preview(path: Array) -> void:
	_route_cells = path.duplicate(true)
	if not is_instance_valid(_route_layer):
		return
	for child: Node in _route_layer.get_children():
		_route_layer.remove_child(child)
		child.queue_free()
	for cell: Array in _route_cells:
		if cell.size() == 2 and _rules.walkable(cell):
			_polygon(_diamond(24,12),Color(CYAN,0.65),_route_layer,_center(cell))
	set_direction_candidates(_direction_cells)


func projected_step_options() -> Array:
	var options: Array = []
	if _floor == null: return options
	var origin: Array = _rules.state.get("pos",[])
	if origin.size() != 2: return options
	var start: Vector2 = projected_cell_center(origin)
	for delta: Vector2i in [Vector2i.LEFT,Vector2i.UP,Vector2i.DOWN,Vector2i.RIGHT]:
		var cell: Array = [int(origin[0])+delta.x,int(origin[1])+delta.y]
		options.append({"cell":cell,"delta":[delta.x,delta.y],"screen":projected_cell_center(cell)-start,"walkable":_rules.walkable(cell)})
	return options


func set_direction_candidates(cells: Array) -> void:
	_direction_cells = cells.duplicate(true)
	if not is_instance_valid(_direction_layer): return
	for child: Node in _direction_layer.get_children():
		_direction_layer.remove_child(child)
		child.queue_free()
	var visible_cells: Array = cells.duplicate(true)
	var choosing: bool = not cells.is_empty()
	if not choosing and _route_cells.is_empty():
		for option: Dictionary in projected_step_options():
			if bool(option["walkable"]): visible_cells.append(option["cell"])
	for cell: Array in visible_cells:
		var rim: PackedVector2Array = _diamond(94 if choosing else 52,45 if choosing else 25)
		rim.append(rim[0])
		var line: Line2D = _line(rim,CYAN if choosing else Color(GOLD,0.55),7 if choosing else 4,_direction_layer)
		line.position = _center(cell)


func _ensure_clipper() -> void:
	if is_instance_valid(_clipper): return
	_clipper = Control.new()
	_clipper.name = "MapOnlyClip"
	_clipper.clip_contents = true
	_clipper.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_clipper)


func set_overview(enabled: bool) -> void:
	if is_instance_valid(_camera_tween): _camera_tween.kill()
	_overview_mode = enabled
	_view_stamp = ""
	fit_rect(_rect)


func set_action_hint(text: String) -> void:
	_hint = text
	if not is_instance_valid(_hint_label):
		_hint_label = Label.new()
		_hint_label.name = "PlainChineseActionHint"
		_hint_label.add_theme_font_override("font",_font())
		_hint_label.add_theme_font_size_override("font_size",16)
		_hint_label.add_theme_color_override("font_color",CYAN)
		_hint_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_hint_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_hint_label.z_index = 80
		add_child(_hint_label)
	_hint_label.text = text
	_hint_label.visible = not text.is_empty()
	_hint_label.position = _rect.position + Vector2(12,_rect.size.y-37)
	_hint_label.size = Vector2(maxf(1,_rect.size.x-24),36)


func fit_rect(rect: Rect2) -> void:
	_ensure_clipper()
	var previous_origin: Vector2 = _board.global_position if is_instance_valid(_board) else Vector2.ZERO
	if _animating and _view_stamp == _map_stamp:
		# A rule can already be on the next floor while the old board fades.
		# Keep that board's transform until its replacement is built.
		_rect = rect
		_clipper.position = rect.position
		_clipper.size = rect.size
		if is_instance_valid(_board): _board.global_position = previous_origin
		return
	var same_view: bool = _view_stamp == _map_stamp and _last_fit_rect == rect
	_clipper.position = rect.position
	_clipper.size = rect.size
	super.fit_rect(rect)
	if is_instance_valid(_board):
		if _board.get_parent() == _clipper:
			_board.position -= rect.position
		if not _overview_mode:
			var factor: float = _board.scale.x*1.6
			_board.scale = Vector2.ONE*factor
			var origin: Vector2 = previous_origin if same_view else rect.get_center()-_center(_rules.state["pos"])*factor
			var hero_screen: Vector2 = origin+_center(_rules.state["pos"])*factor
			var safe := Rect2(rect.position+rect.size*0.25,rect.size*0.50)
			origin += Vector2(clampf(hero_screen.x,safe.position.x,safe.end.x)-hero_screen.x,clampf(hero_screen.y,safe.position.y,safe.end.y)-hero_screen.y)
			var bounds: Rect2 = _scene_bounds()
			for axis: int in range(2):
				var low: float = rect.end[axis]-bounds.end[axis]*factor
				var high: float = rect.position[axis]-bounds.position[axis]*factor
				origin[axis] = clampf(origin[axis],low,high) if low <= high else rect.get_center()[axis]-bounds.get_center()[axis]*factor
			if not same_view:
				if is_instance_valid(_camera_tween): _camera_tween.kill()
				_board.global_position = origin
				_camera_target = origin
			elif not _camera_target.is_equal_approx(origin):
				if is_instance_valid(_camera_tween): _camera_tween.kill()
				_camera_target = origin
				_board.global_position = previous_origin
				_camera_tween = _board.create_tween()
				_camera_tween.tween_property(_board,"global_position",origin,0.18).set_trans(Tween.TRANS_SINE)
			else:
				_board.global_position = previous_origin
		_view_stamp = _map_stamp
		_last_fit_rect = rect
	if is_instance_valid(_actors):
		for raw: Node in _actors.find_children("*","Label",true,false):
			var label: Label = raw as Label
			label.add_theme_font_size_override("font_size",clampi(int(ceil(13.0/maxf(_board.scale.x,0.01))),28,100))
			var point_size: int = label.get_theme_font_size("font_size")
			var width: float = _font().get_string_size(label.text,HORIZONTAL_ALIGNMENT_LEFT,-1,point_size).x+18.0
			label.size.x = maxf(180.0,width)
			label.position.x = -label.size.x*0.5
	if is_instance_valid(_hint_label):
		set_action_hint(_hint)


func _scene_bounds() -> Rect2:
	var bounds := Rect2()
	var first := true
	var rows: Array = _rules.floor_data().get("grid",[])
	for y: int in range(rows.size()):
		for x: int in range(str(rows[y]).length()):
			if _rules.walkable([x,y]) or _near_path([x,y]):
				var tile := Rect2(_center([x,y])+Vector2(-140,-320),Vector2(280,500))
				bounds = tile if first else bounds.merge(tile)
				first = false
	return bounds


func _facing_for(delta: Array) -> int:
	if delta[0] > 0: return 2 # projected lower-right
	if delta[0] < 0: return 6 # projected upper-left
	if delta[1] > 0: return 4 # projected lower-left
	return 0 # projected upper-right


func _pose(action: String) -> void:
	if not is_instance_valid(_hero_body): return
	var wanted := StringName("%s_%d" % [action,_facing])
	if action == "pickup":
		_hero_body.stop()
		_hero_body.play(wanted)
	elif _hero_body.animation != wanted:
		var continuing_stride: bool = action == "run" and str(_hero_body.animation).begins_with("run_")
		var prior_frame: int = _hero_body.frame
		var prior_progress: float = _hero_body.frame_progress
		_hero_body.play(wanted)
		if continuing_stride:
			_hero_body.set_frame_and_progress(mini(prior_frame,_hero_body.sprite_frames.get_frame_count(wanted)-1),prior_progress)
	_hero_body.speed_scale = 1.8 if action == "pickup" else 1.0


func _float_text(at: Vector2,text: String,color: Color) -> void:
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font",_font())
	label.add_theme_font_size_override("font_size",clampi(int(18.0/maxf(_board.scale.x,0.05)),48,110))
	label.add_theme_color_override("font_color",color)
	label.add_theme_color_override("font_shadow_color",Color("07131e"))
	label.add_theme_constant_override("shadow_offset_x",3)
	label.add_theme_constant_override("shadow_offset_y",3)
	label.position = at + Vector2(-95,-210)
	label.z_index = 40
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_board.add_child(label)
	var tween := label.create_tween().set_parallel(true)
	tween.tween_property(label,"position",label.position+Vector2(0,-85),0.65)
	tween.tween_property(label,"modulate:a",0.0,0.65).set_delay(0.2)
	tween.chain().tween_callback(label.queue_free)


func present_transition(before: Dictionary,result: Dictionary,previous_item: Dictionary) -> void:
	if not bool(result.get("ok",false)) or not is_instance_valid(_hero_node):
		return
	_animating = true
	_motion_serial += 1
	var serial: int = _motion_serial
	var after: Dictionary = _rules.state
	if int(before.get("floor",-1)) != int(after.get("floor",-1)) or str(result.get("action","")) in ["checkpoint_restored","started","restarted"]:
		if previous_item.get("kind","") == "stairs" and before.get("pos",[]) != previous_item.get("pos",[]):
			var entry: Array = previous_item["pos"]
			var departure: Array = before["pos"]
			_facing = _facing_for([int(entry[0])-int(departure[0]),int(entry[1])-int(departure[1])])
			_pose("run")
			var approach := create_tween()
			approach.tween_property(_hero_node,"position",_center(entry),0.18).set_trans(Tween.TRANS_LINEAR)
			await approach.finished
		var out := create_tween()
		out.tween_property(_board,"modulate:a",0.20,0.10)
		await out.finished
		_map_stamp = ""
		refresh()
		_board.modulate.a = 0.20
		var fade := create_tween()
		fade.tween_property(_board,"modulate:a",1.0,0.16)
		await fade.finished
		_animating = false
		return
	var old_pos: Array = before.get("pos",[])
	var new_pos: Array = after.get("pos",[])
	var kind: String = str(previous_item.get("kind",""))
	if kind == "door":
		await _animate_open_door(previous_item)
		_float_text(_hero_node.position,"门已开启 · 钥匙 −1",GOLD)
	elif str(result.get("action","")) == "combat":
		var damage: int = int(before.get("hp",0))-int(after.get("hp",0))
		_float_text(_hero_node.position,"−%d 生命" % damage if damage > 0 else "无损战斗",Color("eea09c") if damage > 0 else CYAN)
		var enemy: Node2D = _nodes.get(str(previous_item.get("id",""))) as Node2D
		if is_instance_valid(enemy):
			var defeat := create_tween()
			defeat.tween_property(enemy,"modulate",Color("ffd7b7"),0.08)
			defeat.tween_property(enemy,"modulate:a",0.0,0.18)
			await defeat.finished
	if old_pos.size() == 2 and new_pos.size() == 2 and old_pos != new_pos:
		_facing = _facing_for([int(new_pos[0])-int(old_pos[0]),int(new_pos[1])-int(old_pos[1])])
		_pose("run")
		var step := create_tween()
		step.tween_property(_hero_node,"position",_center(new_pos),0.18).set_trans(Tween.TRANS_LINEAR)
		await step.finished
	if kind in ["key","potion","atk","def","gold"]:
		_pose("pickup")
		var labels := {"potion":"生命","atk":"攻击","def":"防御","gold":"金币"}
		var gained: int = 0
		var text := ""
		if kind == "key":
			var color: String = str(previous_item.get("type","yellow"))
			gained = int(after["keys"].get(color,0))-int(before["keys"].get(color,0))
			text = "+%d %s钥匙" % [gained,"蓝" if color == "blue" else "黄"]
		else:
			var stat: String = "hp" if kind == "potion" else kind
			gained = int(after.get(stat,0))-int(before.get(stat,0))
			text = "+%d %s" % [gained,str(labels.get(kind,"资源"))]
		_float_text(_hero_node.position,text,GOLD)
		var found: Node2D = _nodes.get(str(previous_item.get("id",""))) as Node2D
		if is_instance_valid(found):
			var pickup := create_tween().set_parallel(true)
			pickup.tween_property(found,"position",found.position+Vector2(0,-65),0.25)
			pickup.tween_property(found,"modulate:a",0.0,0.25)
			await pickup.finished
		await get_tree().create_timer(0.22).timeout
	elif str(result.get("action","")) == "purchase":
		_pose("pickup")
		_float_text(_hero_node.position,"购买成功",GOLD)
		await get_tree().create_timer(0.47).timeout
	elif kind == "event":
		_pose("pickup")
		await get_tree().create_timer(0.47).timeout
	elif kind == "npc":
		var target: Array = previous_item.get("pos",[])
		if target.size() == 2 and new_pos.size() == 2:
			_facing = _facing_for([int(target[0])-int(new_pos[0]),int(target[1])-int(new_pos[1])])
			_pose("idle")
		await get_tree().create_timer(0.16).timeout
	refresh()
	_animating = false
	# A following route step starts before this short idle delay, preserving run phase.
	get_tree().create_timer(0.10).timeout.connect(func():
		if serial == _motion_serial and not _animating:
			_pose("idle")
	)


func _update_badge_visibility() -> void:
	if not is_instance_valid(_actors): return
	for id: String in _nodes:
		var node: Node2D = _nodes[id] as Node2D
		if not is_instance_valid(node): continue
		var cell: Array = node.get_meta("cell",[])
		var close := cell.size() == 2 and absi(int(cell[0])-int(_rules.state["pos"][0]))+absi(int(cell[1])-int(_rules.state["pos"][1])) <= 2
		for label: Node in node.find_children("*","Label",true,false):
			if label.has_meta("nearby_only"):
				(label as Label).visible = close or cell == _hover


func _update_occlusion() -> void:
	if not is_instance_valid(_hero_node): return
	for wall: Node2D in _wall_nodes:
		if not is_instance_valid(wall): continue
		var offset: Vector2 = wall.position - _hero_node.position
		# Keep the solid low cap opaque; only a tall decorative column can fade.
		wall.modulate.a = 1.0
		for child: Node in wall.get_children():
			if child is Sprite2D:
				(child as Sprite2D).modulate.a = 0.25 if absf(offset.x) < 140 and offset.y > -5 and offset.y < 165 else 1.0


func cell_at(screenpos: Vector2) -> Array:
	if _floor == null or not _rect.has_point(screenpos):
		return []
	var picked: Array = []
	var depth := -INF
	for id: String in _nodes:
		var node: Node2D = _nodes[id] as Node2D
		if not is_instance_valid(node) or bool(node.get_meta("opened",false)):
			continue
		var cell: Array = node.get_meta("cell",[])
		if cell.size() != 2:
			continue
		var hit := false
		for child: Node in node.get_children():
			if child is Sprite2D:
				var static_sprite: Sprite2D = child as Sprite2D
				if static_sprite.texture != _halo_texture and static_sprite.is_pixel_opaque(static_sprite.to_local(screenpos)):
					hit = true
			elif child is AnimatedSprite2D:
				var animated_sprite: AnimatedSprite2D = child as AnimatedSprite2D
				var texture: Texture2D = animated_sprite.sprite_frames.get_frame_texture(animated_sprite.animation,animated_sprite.frame)
				if texture != null:
					var sprite_size: Vector2 = texture.get_size()
					var sprite_origin: Vector2 = animated_sprite.offset - (sprite_size*0.5 if animated_sprite.centered else Vector2.ZERO)
					hit = hit or Rect2(sprite_origin,sprite_size).grow(-8).has_point(animated_sprite.to_local(screenpos))
		if str(node.get_meta("object_kind","")) in ["key","potion","atk","def","gold"]:
			hit = hit or Rect2(-63,-133,126,125).has_point(node.to_local(screenpos))
		if hit and node.position.y >= depth:
			depth = node.position.y
			picked = cell.duplicate()
	if not picked.is_empty():
		return picked
	var grid_cell: Vector2i = _floor.local_to_map(_floor.to_local(screenpos))
	var result: Array = [grid_cell.x,grid_cell.y]
	return result if _rules.walkable(result) or _near_path(result) else []


func _process(_delta: float) -> void:
	if _animating:
		_update_occlusion()


func set_hover(cell: Array) -> void:
	super.set_hover(cell)
	_update_badge_visibility()
