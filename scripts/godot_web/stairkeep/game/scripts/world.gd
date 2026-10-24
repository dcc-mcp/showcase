class_name StairWorld
extends Node2D
## Native world. Projection and stationary goblin animation reuse the official
## MIT isometric demo; all environment PNGs are unedited Kenney CC0 assets.

signal cell_clicked(cell: Array)
signal cell_hovered(cell: Array)

const KENNEY: String = "res://assets/kenney/"
const OFFICIAL: String = "res://vendor/godot-isometric/"
const GOLD: Color = Color("edc889")
const CYAN: Color = Color("71d7d1")
const INK: Color = Color("122936")

var _rules
var _board: Node2D
var _floor: TileMapLayer
var _actors: Node2D
var _highlight: Polygon2D
var _rect: Rect2 = Rect2(25, 135, 890, 560)
var _hover: Array = []
var _tileset: TileSet
var _frames: SpriteFrames
var _textures: Dictionary = {}
var _halo_texture: GradientTexture2D


func configure(rules: Object) -> void:
	_rules = rules
	_ensure_resources()
	refresh()


func _ensure_resources() -> void:
	if _tileset != null:
		return
	# Keep the upstream isometric shape/layout rather than approximating the
	# projection in JavaScript or maintaining a second hand-written transform.
	var upstream: TileSet = load(OFFICIAL + "tileset/tileset.tres")
	_tileset = upstream.duplicate(true)
	while _tileset.get_source_count() > 0:
		_tileset.remove_source(_tileset.get_source_id(0))
	_tileset.tile_size = Vector2i(256, 128)
	var floor_names: Array[String] = ["stone_N.png", "stoneUneven_N.png", "stoneTile_N.png"]
	for source_index: int in range(floor_names.size()):
		var atlas := TileSetAtlasSource.new()
		atlas.texture = _texture(floor_names[source_index])
		atlas.texture_region_size = Vector2i(256, 512)
		atlas.create_tile(Vector2i.ZERO)
		atlas.get_tile_data(Vector2i.ZERO, 0).texture_origin = Vector2i(0, -172)
		_tileset.add_source(atlas, source_index)
	var prototype: PackedScene = load(OFFICIAL + "player/goblin.tscn")
	var goblin: Node = prototype.instantiate()
	_frames = (goblin.get_node("Sprite2D") as AnimatedSprite2D).sprite_frames
	goblin.free()
	var gradient := Gradient.new()
	gradient.colors = PackedColorArray([Color(1, 1, 1, 0.48), Color(1, 1, 1, 0)])
	gradient.offsets = PackedFloat32Array([0.05, 1.0])
	_halo_texture = GradientTexture2D.new()
	_halo_texture.gradient = gradient
	_halo_texture.width = 256
	_halo_texture.height = 256
	_halo_texture.fill = GradientTexture2D.FILL_RADIAL
	_halo_texture.fill_from = Vector2(0.5, 0.5)
	_halo_texture.fill_to = Vector2(0.5, 0.0)


func _texture(name: String) -> Texture2D:
	if not _textures.has(name):
		_textures[name] = load(KENNEY + name)
	return _textures[name]


func refresh() -> void:
	if _rules == null or _rules.state.is_empty():
		return
	if _board != null:
		_board.free()
	_board = Node2D.new()
	_board.name = "IsometricDiorama"
	add_child(_board)
	_floor = TileMapLayer.new()
	_floor.name = "OfficialProjectionKenneyFloor"
	_floor.tile_set = _tileset
	_floor.collision_enabled = false
	_floor.z_index = -10
	_board.add_child(_floor)
	_actors = Node2D.new()
	_actors.name = "DepthSortedObjects"
	_actors.y_sort_enabled = true
	_board.add_child(_actors)
	var grid: Array = _rules.floor_data().get("grid", [])
	for y: int in range(grid.size()):
		for x: int in range(str(grid[y]).length()):
			var cell: Array = [x, y]
			if _rules.walkable(cell):
				_floor.set_cell(Vector2i(x, y), (x + y * 3) % 3, Vector2i.ZERO)
				_add_pier(_floor.map_to_local(Vector2i(x, y)), x + y)
			elif _near_path(cell):
				_add_wall(cell)
	for item: Dictionary in _rules.floor_data().get("objects", []):
		if not _rules.state["cleared"].has(str(item["id"])):
			_add_object(item)
	_add_hero()
	_highlight = Polygon2D.new()
	_highlight.name = "HoveredWalkTile"
	_highlight.polygon = _diamond(118, 58)
	_highlight.color = Color(CYAN, 0.24)
	_highlight.z_index = -2
	_board.add_child(_highlight)
	fit_rect(_rect)
	set_hover(_hover)


func _near_path(cell: Array) -> bool:
	for offset: Vector2i in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		if _rules.walkable([int(cell[0]) + offset.x, int(cell[1]) + offset.y]):
			return true
	return false


func _diamond(half_width: float, half_height: float) -> PackedVector2Array:
	return PackedVector2Array([Vector2(0, -half_height), Vector2(half_width, 0), Vector2(0, half_height), Vector2(-half_width, 0)])


func _polygon(points: PackedVector2Array, color: Color, parent: Node2D, at: Vector2 = Vector2.ZERO) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.polygon = points
	shape.color = color
	shape.position = at
	parent.add_child(shape)
	return shape


func _line(points: PackedVector2Array, color: Color, width: float, parent: Node2D) -> Line2D:
	var line := Line2D.new()
	line.points = points
	line.default_color = color
	line.width = width
	line.antialiased = true
	parent.add_child(line)
	return line


func _add_pier(center: Vector2, seed_index: int) -> void:
	var body := Node2D.new()
	body.position = center
	body.z_index = -20
	_board.add_child(body)
	var depth: float = 110.0 + float(seed_index % 3) * 12.0
	_polygon(PackedVector2Array([Vector2(-128, 0), Vector2(0, 64), Vector2(0, 64 + depth), Vector2(-128, depth)]), Color("183244"), body)
	_polygon(PackedVector2Array([Vector2(0, 64), Vector2(128, 0), Vector2(128, depth), Vector2(0, 64 + depth)]), Color("102431"), body)
	# Sparse inset seams and brass glints read as stonework, not a grid overlay.
	if seed_index % 3 == 0:
		_line(PackedVector2Array([Vector2(-66, 35), Vector2(-66, depth + 12)]), Color("285263"), 3, body)
		_line(PackedVector2Array([Vector2(61, 40), Vector2(61, 65)]), Color("8e8058"), 3, body)


func _add_wall(cell: Array) -> void:
	var center: Vector2 = _floor.map_to_local(Vector2i(int(cell[0]), int(cell[1])))
	var wall := Node2D.new()
	wall.position = center
	_actors.add_child(wall)
	var top: float = -43.0
	_polygon(PackedVector2Array([Vector2(-107, top), Vector2(0, 53 + top), Vector2(0, 54), Vector2(-107, 0)]), Color("3b5260"), wall)
	_polygon(PackedVector2Array([Vector2(0, 53 + top), Vector2(107, top), Vector2(107, 0), Vector2(0, 54)]), Color("293d4b"), wall)
	_polygon(_diamond(107, 53), Color("536774"), wall, Vector2(0, top))
	if (int(cell[0]) * 3 + int(cell[1])) % 5 == 0:
		var column := _sprite("stoneColumn_N.png", Vector2(-128, -448))
		column.modulate = Color("9cafaf")
		wall.add_child(column)
		_glow(wall, Vector2(0, -92), Color("efbd73"), 0.75)


func _sprite(name: String, offset: Vector2) -> Sprite2D:
	var sprite := Sprite2D.new()
	sprite.texture = _texture(name)
	sprite.centered = false
	sprite.offset = offset
	return sprite


func _glow(parent: Node2D, at: Vector2, color: Color, strength: float = 1.0) -> void:
	var light := Sprite2D.new()
	light.texture = _halo_texture
	light.position = at
	light.scale = Vector2(1.1, 0.68) * strength
	light.modulate = color
	light.z_index = -1
	parent.add_child(light)


func _add_hero() -> void:
	var cell: Array = _rules.state["pos"]
	var hero := Node2D.new()
	hero.name = "Wanderer"
	hero.position = _floor.map_to_local(Vector2i(int(cell[0]), int(cell[1])))
	_actors.add_child(hero)
	_glow(hero, Vector2.ZERO, CYAN, 1.25)
	_polygon(_diamond(73, 35), Color(CYAN, 0.25), hero)
	var rim: PackedVector2Array = _diamond(81, 39)
	rim.append(rim[0])
	_line(rim, CYAN, 5, hero)
	var person := _sprite("wanderer.png", Vector2(-128, -453))
	person.scale = Vector2(1.6, 1.6)
	person.modulate = Color("dceae4")
	hero.add_child(person)
	_glow(hero, Vector2(31, -135), Color("ffc66d"), 0.55)


func _add_object(item: Dictionary) -> void:
	var cell: Array = item["pos"]
	var marker := Node2D.new()
	marker.name = str(item["id"])
	marker.position = _floor.map_to_local(Vector2i(int(cell[0]), int(cell[1])))
	_actors.add_child(marker)
	var kind: String = str(item.get("kind", ""))
	match kind:
		"enemy":
			_add_enemy(marker, item)
		"door":
			var blue: bool = item.get("type", "yellow") == "blue"
			var gate := _sprite("stoneWallDoorClosed_N.png", Vector2(-80, -448))
			gate.modulate = Color("88c9db") if blue else Color("e7c18a")
			marker.add_child(gate)
			_key_symbol(marker, Color("88d6ee") if blue else GOLD, Vector2(7, -102), 0.60)
		"stairs":
			var stairs := _sprite("stairs_N.png", Vector2(-128, -435))
			stairs.modulate = Color("99dbd5")
			marker.add_child(stairs)
			_glow(marker, Vector2(0, -50), CYAN, 1.2)
			var arrow := PackedVector2Array([Vector2(-28, -103), Vector2(0, -125), Vector2(28, -103)])
			if item.get("direction", "up") == "down":
				arrow = PackedVector2Array([Vector2(-28, -125), Vector2(0, -103), Vector2(28, -125)])
			_line(arrow, CYAN, 9, marker)
		"shop":
			marker.add_child(_sprite("tableRoundItemsChairs_N.png", Vector2(-128, -452)))
			_glow(marker, Vector2(0, -80), GOLD, 1.0)
			_symbol_badge(marker, "SHOP", GOLD, -145)
		"key":
			var color: Color = Color("88d6ee") if item.get("type", "yellow") == "blue" else GOLD
			_glow(marker, Vector2(0, -50), color)
			_key_symbol(marker, color, Vector2(0, -60))
		"atk", "def":
			var color: Color = Color("ed8380") if kind == "atk" else Color("7db5ed")
			_gem(marker, color, kind == "def")
		"potion":
			_potion(marker)
		"gold":
			_coins(marker)


func _add_enemy(parent: Node2D, item: Dictionary) -> void:
	var monster := AnimatedSprite2D.new()
	monster.sprite_frames = _frames
	monster.animation = &"front_idle"
	var enemy_type: String = str(item.get("type", "moss"))
	var big: bool = enemy_type in ["warden", "sealed_sentinel", "stone_guard"]
	monster.scale = Vector2(2.15, 2.15) if big else Vector2(1.7, 1.7)
	monster.position.y = -89 if big else -70
	var tint: Color = Color("99b99e")
	if enemy_type in ["cinder", "warden"]:
		tint = Color("d9989d")
	elif enemy_type in ["stone_guard", "hall_guard", "sealed_sentinel"]:
		tint = Color("a3a6d4")
	monster.modulate = tint
	parent.add_child(monster)
	monster.play()
	_polygon(_diamond(64 if big else 51, 27), Color("12232a80"), parent)
	var preview: Dictionary = _rules.combat(_rules.data["enemies"][enemy_type])
	var cost: String = str(preview["damage"]) if preview["win"] else "X"
	_symbol_badge(parent, cost, Color("ed9a91") if preview["win"] else Color("ff6f7b"), -270 if big else -170)
	if big:
		var crest := PackedVector2Array([Vector2(-30, -174), Vector2(-23, -197), Vector2(0, -180), Vector2(23, -197), Vector2(30, -174)])
		_line(crest, GOLD, 7, parent)


func _symbol_badge(parent: Node2D, text: String, color: Color, top: float) -> void:
	var badge := Label.new()
	badge.text = text
	badge.position = Vector2(-65, top)
	badge.size = Vector2(130, 55)
	badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	badge.add_theme_font_size_override("font_size", 39 if text != "SHOP" else 29)
	badge.add_theme_color_override("font_color", color)
	badge.add_theme_color_override("font_shadow_color", Color("08131e"))
	badge.add_theme_constant_override("shadow_offset_x", 3)
	badge.add_theme_constant_override("shadow_offset_y", 3)
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(badge)


func _key_symbol(parent: Node2D, color: Color, at: Vector2, factor: float = 1.0) -> void:
	var key := Node2D.new()
	key.position = at
	key.rotation = -0.35
	key.scale = Vector2.ONE * factor
	parent.add_child(key)
	var ring := Line2D.new()
	for index: int in range(25):
		var angle: float = TAU * float(index) / 24.0
		ring.add_point(Vector2(cos(angle), sin(angle)) * 23.0 + Vector2(-26, 0))
	ring.default_color = color
	ring.width = 12
	ring.antialiased = true
	key.add_child(ring)
	_line(PackedVector2Array([Vector2(-1, 0), Vector2(60, 0), Vector2(60, 17)]), color, 12, key)
	_line(PackedVector2Array([Vector2(38, 0), Vector2(38, 16)]), color, 12, key)


func _gem(parent: Node2D, color: Color, shield: bool) -> void:
	_glow(parent, Vector2(0, -55), color, 0.9)
	if shield:
		_polygon(PackedVector2Array([Vector2(-37, -105), Vector2(37, -105), Vector2(31, -56), Vector2(0, -28), Vector2(-31, -56)]), color.darkened(0.23), parent)
		_line(PackedVector2Array([Vector2(-31, -99), Vector2(31, -99), Vector2(26, -60), Vector2(0, -36), Vector2(-26, -60), Vector2(-31, -99)]), color.lightened(0.35), 6, parent)
	else:
		_polygon(PackedVector2Array([Vector2(0, -121), Vector2(43, -81), Vector2(0, -30), Vector2(-43, -81)]), color, parent)
		_polygon(PackedVector2Array([Vector2(0, -121), Vector2(0, -30), Vector2(-43, -81)]), color.darkened(0.22), parent)
		_line(PackedVector2Array([Vector2(-43, -81), Vector2(0, -121), Vector2(43, -81)]), color.lightened(0.5), 5, parent)


func _potion(parent: Node2D) -> void:
	_glow(parent, Vector2(0, -55), Color("e88283"), 0.75)
	_polygon(PackedVector2Array([Vector2(-15, -114), Vector2(15, -114), Vector2(15, -95), Vector2(35, -68), Vector2(31, -36), Vector2(-31, -36), Vector2(-35, -68), Vector2(-15, -95)]), Color("a8cfcc"), parent)
	_polygon(PackedVector2Array([Vector2(-27, -68), Vector2(27, -68), Vector2(25, -42), Vector2(-25, -42)]), Color("cb696d"), parent)
	_line(PackedVector2Array([Vector2(-19, -119), Vector2(19, -119)]), GOLD, 12, parent)
	_line(PackedVector2Array([Vector2(-23, -59), Vector2(-23, -48)]), Color("f4d8cb"), 5, parent)


func _coins(parent: Node2D) -> void:
	_glow(parent, Vector2(0, -35), GOLD, 0.8)
	for index: int in range(3):
		var offset := Vector2(float(index - 1) * 27.0, -37.0 - float(index % 2) * 15.0)
		_polygon(_diamond(31, 14), GOLD.darkened(0.15), parent, offset)
		var rim: PackedVector2Array = _diamond(27, 12)
		for point_index: int in range(rim.size()):
			rim[point_index] += offset + Vector2(0, -6)
		rim.append(rim[0])
		_line(rim, GOLD.lightened(0.25), 6, parent)


func fit_rect(rect: Rect2) -> void:
	_rect = rect
	if _floor == null:
		return
	var bounds := Rect2()
	var first: bool = true
	var grid: Array = _rules.floor_data().get("grid", [])
	for y: int in range(grid.size()):
		for x: int in range(str(grid[y]).length()):
			if _rules.walkable([x, y]) or _near_path([x, y]):
				var point: Vector2 = _floor.map_to_local(Vector2i(x, y))
				var tile_bounds := Rect2(point + Vector2(-135, -210), Vector2(270, 415))
				bounds = tile_bounds if first else bounds.merge(tile_bounds)
				first = false
	var factor: float = minf(rect.size.x / maxf(bounds.size.x, 1.0), rect.size.y / maxf(bounds.size.y, 1.0))
	_board.scale = Vector2.ONE * factor
	_board.position = rect.get_center() - bounds.get_center() * factor


func projected_cell_center(cell: Array) -> Vector2:
	if _floor == null or cell.size() != 2:
		return Vector2.ZERO
	return _floor.to_global(_floor.map_to_local(Vector2i(int(cell[0]), int(cell[1]))))


func cell_at(screenpos: Vector2) -> Array:
	if _floor == null:
		return []
	var cell: Vector2i = _floor.local_to_map(_floor.to_local(screenpos))
	var result: Array = [cell.x, cell.y]
	return result if _rules.walkable(result) else []


func set_hover(cell: Array) -> void:
	_hover = cell.duplicate()
	if _highlight == null:
		return
	_highlight.visible = cell.size() == 2 and _rules.walkable(cell)
	if _highlight.visible:
		_highlight.position = _floor.map_to_local(Vector2i(int(cell[0]), int(cell[1])))


func _unhandled_input(event: InputEvent) -> void:
	if _floor == null:
		return
	if event is InputEventMouseMotion:
		var cell: Array = cell_at(get_global_mouse_position())
		if cell != _hover:
			set_hover(cell)
			cell_hovered.emit(cell)
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		var cell: Array = cell_at(get_global_mouse_position())
		if not cell.is_empty():
			cell_clicked.emit(cell)
			get_viewport().set_input_as_handled()
	elif event is InputEventScreenTouch and event.pressed:
		# Godot's default touch-to-mouse conversion already sends the pointer
		# event above. Handling both streams would execute one tap twice.
		if bool(ProjectSettings.get_setting("input_devices/pointing/emulate_mouse_from_touch", true)):
			return
		var cell: Array = cell_at(event.position)
		if not cell.is_empty():
			set_hover(cell)
			cell_hovered.emit(cell)
			cell_clicked.emit(cell)
			get_viewport().set_input_as_handled()
