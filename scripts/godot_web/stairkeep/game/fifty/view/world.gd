extends "res://scripts/world.gd"
## Thin presentation extension of the existing native isometric renderer.
## Same CC0 PNGs / MIT TileSet projection, no alternate geometry or rule model.

const FLOOR_TINTS := [
	Color("fff6df"), Color("e5e5dc"), Color("d5e6e9"), Color("e5eeee"),
	Color("f0eee1"), Color("dbe4df"), Color("fff2d5"), Color("d6e7e5"),
	Color("e7e3ee"), Color("eee8d9")
]


func refresh() -> void:
	super.refresh()
	if _floor != null and _rules != null and not _rules.state.is_empty():
		var floor_index: int = clampi(int(_rules.state.get("floor", 0)), 0, 9)
		_floor.modulate = FLOOR_TINTS[floor_index]


func _add_object(item: Dictionary) -> void:
	# The original renderer iterates authored objects. Respect the new runtime's
	# hidden-event / completed-event visibility instead of revealing the raw list.
	var visible_item: Dictionary = _rules.object_at(item.get("pos", []))
	if visible_item.is_empty() or visible_item.get("id", "") != item.get("id", ""):
		return
	var kind: String = str(item.get("kind", ""))
	if kind not in ["npc", "event", "boundary"]:
		super._add_object(item)
		return
	var cell: Array = item.get("pos", [])
	if cell.size() != 2:
		return
	var marker := Node2D.new()
	marker.name = str(item.get("id", "StoryMarker"))
	marker.position = _floor.map_to_local(Vector2i(int(cell[0]), int(cell[1])))
	_actors.add_child(marker)
	if kind == "boundary":
		var sealed := _sprite("stoneWallDoorClosed_N.png", Vector2(-80, -448))
		sealed.modulate = Color("71818a")
		marker.add_child(sealed)
		_symbol_badge(marker, "LATER", Color("91a6af"), -176)
		return
	_glow(marker, Vector2(0, -35), GOLD, 0.85)
	if kind == "npc":
		var person: Sprite2D = _sprite("wanderer.png", Vector2(-128, -453))
		person.modulate = Color("e8cfaa")
		marker.add_child(person)
		_symbol_badge(marker, "NPC", GOLD, -176)
	else:
		_polygon(_diamond(53, 26), Color("bd9b62"), marker, Vector2(0, -32))
		var edge: PackedVector2Array = _diamond(57, 28)
		for index: int in range(edge.size()):
			edge[index] += Vector2(0, -32)
		edge.append(edge[0])
		_line(edge, GOLD, 4, marker)
		_symbol_badge(marker, "NOTE", GOLD, -146)


func _symbol_badge(parent: Node2D, text: String, color: Color, top: float) -> void:
	super._symbol_badge(parent, text, color, top)
	var badge: Label = parent.get_child(parent.get_child_count()-1) as Label
	if badge != null:
		badge.set_meta("fifty_badge", true)
		badge.position.x = -90
		badge.size = Vector2(180, 80)


func fit_rect(rect: Rect2) -> void:
	super.fit_rect(rect)
	if _board == null or _actors == null:
		return
	# A 15x15 first-chapter board uses a smaller projection than the old slice.
	# Keep its native text badges readable in screen space; pixel review pending.
	var point_size: int = clampi(int(ceil(13.0 / maxf(_board.scale.x, 0.01))), 39, 100)
	for node: Node in _actors.find_children("*", "Label", true, false):
		if node.has_meta("fifty_badge"):
			(node as Label).add_theme_font_size_override("font_size", point_size)
