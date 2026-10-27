extends Control
## One stroke, size and palette shared by the native HUD resource symbols.
var kind: String = "gold"
var ink: Color = Color("e8c48a")

func _ready() -> void:
	custom_minimum_size = Vector2(28,28)
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _draw() -> void:
	var points := PackedVector2Array()
	match kind:
		"hp":
			points = PackedVector2Array([Vector2(14,24),Vector2(3,13),Vector2(3,7),Vector2(7,4),Vector2(11,4),Vector2(14,8),Vector2(17,4),Vector2(21,4),Vector2(25,7),Vector2(25,13),Vector2(14,24)])
		"atk":
			points = PackedVector2Array([Vector2(7,22),Vector2(21,4),Vector2(25,3),Vector2(25,8),Vector2(11,25)])
			draw_line(Vector2(5,17),Vector2(15,25),ink,2,true)
		"def":
			points = PackedVector2Array([Vector2(14,3),Vector2(25,7),Vector2(22,18),Vector2(14,25),Vector2(6,18),Vector2(3,7),Vector2(14,3)])
		"yellow", "blue":
			draw_arc(Vector2(9,9),6,0,TAU,24,ink,2,true)
			draw_line(Vector2(13,13),Vector2(25,25),ink,2,true)
			draw_line(Vector2(20,20),Vector2(24,16),ink,2,true)
			draw_line(Vector2(24,24),Vector2(28,20),ink,2,true)
		_:
			draw_arc(Vector2(14,14),11,0,TAU,32,ink,2,true)
			draw_line(Vector2(14,7),Vector2(14,21),ink,2,true)
	if not points.is_empty():
		draw_polyline(points,ink,2,true)
