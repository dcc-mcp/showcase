extends RefCounted
# Original modular architecture; the generated kit remains separately named.
const WATER_SHADER = preload("res://assets/shaders/archive_water.gdshader")

func build(game: Node3D) -> void:
	var stone := weathered(Color("68685f"), 42)
	var paving := weathered(Color("8e8877"), 73)
	var dark := weathered(Color("323e42"), 93)
	var brass = game._material(Color("9a8050"), 0.65)
	var moss := weathered(Color("3d5146"), 153)
	_water(game)
	# Connected collision floors: bridge -> court -> wings -> raised rear archive.
	game._box("CourtyardFloor", Vector3(18, 0.65, 16), Vector3(0, -0.325, 0), stone, true)
	game._box("ArrivalBridge", Vector3(4.8, 0.75, 8), Vector3(0, -0.375, 12), paving, true)
	game._box("WestArchiveWing", Vector3(6, 0.65, 13), Vector3(-12, -0.325, -1.5), stone, true)
	game._box("EastArchiveWing", Vector3(6, 0.65, 15), Vector3(12, -0.325, -0.5), stone, true)
	game._box("RearArchiveVerandaWest", Vector3(11, 0.55, 4), Vector3(-8, 0.425, -10), paving, true)
	game._box("RearArchiveVerandaEast", Vector3(11, 0.55, 4), Vector3(8, 0.425, -10), paving, true)
	game._box("RearArchiveLanding", Vector3(5, 0.55, 5), Vector3(0, 0.425, -11.5), paving, true)
	_ramp(game, paving)
	for side in [-1, 1]:
		game._box("DeepFoundation", Vector3(1.1, 3.0, 16), Vector3(side * 8.45, -1.5, 0), dark)
		game._box("BridgeParapet", Vector3(0.42, 0.75, 8), Vector3(side * 2.18, 0.375, 12), stone, true)
		game._box("BridgeBrassCap", Vector3(0.50, 0.08, 8), Vector3(side * 2.18, 0.78, 12), brass)
		game._box("CourtFrontParapet", Vector3(6.2, 0.7, 0.55), Vector3(side * 5.8, 0.35, 7.75), stone, true)
		game._box("WingOuterWall", Vector3(0.6, 1.2, 14), Vector3(side * 14.7, 0.6, -1.0), stone, true)
		game._box("WingFrontWall", Vector3(6, 0.85, 0.6), Vector3(side * 12, 0.425, 5.4), stone, true)
		for z in [-6.5, -1.0, 4.6]:
			game._box("WingPier", Vector3(1.1, 1.8, 1.1), Vector3(side * 14.6, 0.9, z), dark)
		for z in [-5.8, -0.4, 5.0]:
			game._box("MossSeam", Vector3(0.25, 0.006, 4.7), Vector3(side * 7.85, 0.003, z), moss)
	# Long limestone bands and sparse broken flags replace the v1 checkerboard.
	for x in [-6.5, 0.0, 6.5]:
		game._box("LongWalkBand", Vector3(1.1, 0.008, 13.8), Vector3(x, 0.004, 0), paving)
	for z in [-5.0, 4.8]:
		game._box("CourtCrossBand", Vector3(17.3, 0.008, 1.1), Vector3(0, 0.004, z), paving)
	for index in range(15):
		var x := -6.5 + fmod(index * 3.71, 13.0)
		var z := -5.8 + fmod(index * 2.83, 11.6)
		var flag := BoxMesh.new()
		flag.size = Vector3(1.0 + fmod(index * 0.37, 0.65), 0.008, 0.55)
		var instance = game._mesh(flag, paving, Vector3(x, 0.004, z))
		instance.rotation.y = (index % 3 - 1) * 0.09
	# Rear facade: a tall asymmetric silhouette with a deep central doorway.
	for side in [-1, 1]:
		game._box("ArchiveFacade", Vector3(10.4, 6.6, 1.6), Vector3(side * 8.0, 3.7, -12.3), stone, true)
		game._box("FacadePlinth", Vector3(11.0, 0.7, 2.1), Vector3(side * 8.0, 1.0, -12.0), dark)
		game._box("FacadeCornice", Vector3(11.0, 0.45, 2.1), Vector3(side * 8.0, 7.1, -12.3), paving)
		game._box("ArchiveDoorReveal", Vector3(0.7, 7.1, 2.5), Vector3(side * 3.0, 4.0, -12.2), dark)
		for x in [5.0, 8.0, 11.0]:
			game._box("FacadeButtress", Vector3(0.6, 5.7, 0.55), Vector3(side * x, 3.65, -11.3), paving)
			game._box("RecessedArchiveWindow", Vector3(1.35, 2.7, 0.12), Vector3(side * x + 0.8, 4.1, -11.42), dark)
			game._box("WindowBrassLintel", Vector3(1.6, 0.12, 0.20), Vector3(side * x + 0.8, 5.5, -11.30), brass)
	# The rear doorway remains genuinely open into the wilderness trail.
	_build_wilderness(game, stone, dark, moss, paving)
	game._box("ArchiveEntranceLintel", Vector3(7.2, 1.0, 2.5), Vector3(0, 7.45, -12.2), stone)
	game._box("WestArchiveTower", Vector3(3.2, 9.5, 4), Vector3(-12, 5.45, -12), dark)
	game._box("TowerCrown", Vector3(3.9, 0.6, 4.6), Vector3(-12, 10.5, -12), paving)
	for index in range(8):
		var height := 9.0 + fmod(index * 3.7, 9.0)
		var cliff := _cliff_mesh(height, index)
		var cliff_color := Color("344b50").lightened(fmod(index * 0.17, 0.10))
		var cliff_instance = game._mesh(cliff, game._material(cliff_color), Vector3((-20.0 if index % 2 == 0 else 20.0) + sin(index) * 2.0, height / 2.0 - 4.5, -23 - index * 3))
		cliff_instance.rotation.y = index * 0.5
		cliff_instance.rotation.z = sin(index * 2.1) * 0.10
	for index in range(7):
		var height := 14.0 + fmod(index * 5.3, 10.0)
		var distant = game._mesh(_cliff_mesh(height, index + 20), game._material(Color("49636a")), Vector3(-31 + index * 10, height / 2.0 - 5.0, -48 - (index % 2) * 7))
		distant.scale = Vector3(1.5, 1.0, 1.4)
	# Generated pieces are placed as architecture at authored metre-scale heights.
	game._asset("arch", Vector3(0, 0.7, -11.9), 6.4, 7.0)
	game._asset("arch", Vector3(-9.8, 0, -6.4), 4.8, 6.0).rotation.y = -0.35
	game._asset("gate", Vector3(9.6, 0, -6.4), 4.3, 5.5).rotation.y = 0.35
	for point in [Vector3(-7.9, 0, -5.8), Vector3(7.9, 0, -5.8), Vector3(-7.9, 0, 4.8), Vector3(7.9, 0, 4.8), Vector3(-11.8, 0, 3.8), Vector3(11.8, 0, 4.2)]:
		game._asset("column", point, 4.6, 3.0)
		game._proxy(point + Vector3(0, 1.0, 0), Vector3(1.35, 2, 1.35))
	game._asset("portal", game.HOME, 4.8, 6.0).rotation.y = 0.18
	game._asset("shrine", Vector3(6.0, 0, -1.5), 4.2, 4.5).rotation.y = -0.30
	game._proxy(Vector3(6.0, 1.2, -1.5), Vector3(1.9, 2.4, 1.9))
	# The controller binds the actual hinged derivative and its Lid node.
	game.build_interactive_chest()
	var stairs: Node3D = game._asset("stairs", Vector3(-11.6, 0, -5.975), 1.6, 2.5)
	stairs.rotation.y = PI
	var measured: Dictionary = game.loaded_assets.get("stairs", {})
	if measured.has("source_bounds"):
		stairs.scale = Vector3(2.6 / (float(measured.source_bounds.x) * float(measured.scale)), 0.7 / 1.6, 3.1 / (float(measured.source_bounds.z) * float(measured.scale)))
		# Authored placement adapts the kit stairs to the actual .7m veranda rise.
		_traversal_ramp(game, "WestStairTraversalProxy", 2.6,
			Vector3(-11.6, 0, -4.425), Vector3(-11.6, 0.7, -7.525), paving, false)
		game._box("WestStairLandingTread", Vector3(2.6, 0.16, 0.55), Vector3(-11.6, 0.62, -7.8), paving, true)
	# Broken native masonry gives foreground parallax and close surface detail.
	for index in range(18):
		var side := -1.0 if index % 2 == 0 else 1.0
		var point := Vector3(side * (3.1 + fmod(index * 0.71, 3.9)), 0.16, 6.5 + fmod(index * 1.37, 3.2))
		var stone_mesh := BoxMesh.new()
		stone_mesh.size = Vector3(0.45 + fmod(index * 0.31, 0.9), 0.25 + fmod(index * 0.17, 0.45), 0.65)
		var rubble = game._mesh(stone_mesh, dark if index % 3 == 0 else stone, point)
		rubble.rotation = Vector3(index * 0.09, index * 0.57, index * 0.03)
	for point in [Vector3(-1.7, 0, 10), Vector3(1.7, 0, 10), Vector3(-5.8, 0, 5.3), Vector3(5.8, 0, 5.3), Vector3(-10.0, 0, -2.0), Vector3(10.0, 0, -2.0)]:
		game._box("ArchiveBeaconPlinth", Vector3(0.42, 1.35, 0.42), point + Vector3(0, 0.675, 0), dark)
		game._box("ArchiveBeaconLantern", Vector3(0.30, 0.40, 0.30), point + Vector3(0, 1.55, 0), game._material(Color("c8a265"), 0, true))
		game.torches.append(game._light(point + Vector3(0, 1.6, 0), Color("f2c27a"), 0.7, 5.0))

func weathered(color: Color, seed: int) -> StandardMaterial3D:
	var noise := FastNoiseLite.new()
	noise.seed = seed
	noise.frequency = 0.055
	var texture := NoiseTexture2D.new()
	texture.width = 256
	texture.height = 256
	texture.noise = noise
	texture.seamless = true
	var ramp := Gradient.new()
	ramp.set_color(0, Color(0.55, 0.58, 0.55))
	ramp.set_color(1, Color(0.95, 0.94, 0.90))
	texture.color_ramp = ramp
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.albedo_texture = texture
	material.roughness = 0.92
	var normal := NoiseTexture2D.new()
	normal.width = 256
	normal.height = 256
	normal.noise = noise
	normal.seamless = true
	normal.as_normal_map = true
	normal.bump_strength = 1.6
	material.normal_enabled = true
	material.normal_texture = normal
	material.normal_scale = 0.28
	material.uv1_triplanar = true
	material.uv1_world_triplanar = true
	material.uv1_scale = Vector3.ONE * 0.45
	return material

func _cliff_mesh(height: float, seed: int) -> ArrayMesh:
	# Original low-cost fractured silhouettes, with uneven ledges and peaks.
	var rings: Array[PackedVector3Array] = []
	for level in range(3):
		var ring := PackedVector3Array()
		for side in range(7):
			var angle := TAU * side / 7.0
			var variation := sin(side * 2.7 + seed * 1.71 + level * 0.8)
			var radius := (5.3 - level * 1.45) * (1.0 + variation * 0.24)
			var y := -height / 2.0 + level * height / 2.0
			if level > 0:
				y += sin(side * 3.9 + seed) * height * 0.08
			ring.append(Vector3(cos(angle) * radius + level * 0.25, y, sin(angle) * radius))
		rings.append(ring)
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	for level in range(2):
		for side in range(7):
			var next := (side + 1) % 7
			for vertex in [rings[level][side], rings[level + 1][side], rings[level][next], rings[level][next], rings[level + 1][side], rings[level + 1][next]]:
				surface.add_vertex(vertex)
	for side in range(7):
		for vertex in [rings[2][side], Vector3(0.5, height / 2.0 + height * 0.10, 0), rings[2][(side + 1) % 7]]:
			surface.add_vertex(vertex)
	surface.generate_normals()
	return surface.commit()

func _water(game: Node3D) -> MeshInstance3D:
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(160, 160)
	mesh.subdivide_width = 64
	mesh.subdivide_depth = 64
	var water := MeshInstance3D.new()
	water.name = "SunkenWater"
	water.mesh = mesh
	water.position.y = -3.4
	water.extra_cull_margin = 0.12
	var material := ShaderMaterial.new()
	material.shader = WATER_SHADER
	water.material_override = material
	game.add_child(water)
	return water

func _ramp(game: Node3D, material: Material) -> void:
	_traversal_ramp(game, "ArchiveAccessRamp", 4.0,
		Vector3(0, 0, -5.9), Vector3(0, 0.7, -9.0), material)

func _traversal_ramp(game: Node3D, node_name: String, width: float, low: Vector3, high: Vector3, material: Material, visible := true) -> StaticBody3D:
	assert(width > 0.0 and is_equal_approx(low.x, high.x) and not is_equal_approx(low.z, high.z))
	var min_z := minf(low.z, high.z)
	var max_z := maxf(low.z, high.z)
	var min_z_height := low.y if low.z < high.z else high.y
	var max_z_height := high.y if low.z < high.z else low.y
	var center_z := (min_z + max_z) * 0.5
	var half_run := (max_z - min_z) * 0.5
	var half_width := width * 0.5
	var bottom := minf(low.y, high.y) - 0.3
	var body := StaticBody3D.new()
	body.name = node_name
	body.position = Vector3(low.x, 0, center_z)
	var collider := CollisionShape3D.new()
	var shape := ConvexPolygonShape3D.new()
	# Exact floor joins avoid the vertical lip introduced by rotating a thin box.
	shape.points = PackedVector3Array([
		Vector3(-half_width, bottom, -half_run), Vector3(half_width, bottom, -half_run),
		Vector3(half_width, bottom, half_run), Vector3(-half_width, bottom, half_run),
		Vector3(-half_width, min_z_height, -half_run), Vector3(half_width, min_z_height, -half_run),
		Vector3(half_width, max_z_height, half_run), Vector3(-half_width, max_z_height, half_run)])
	collider.shape = shape
	body.add_child(collider)
	if visible:
		var surface := MeshInstance3D.new()
		surface.name = "TraversalSurface"
		var mesh := PlaneMesh.new()
		mesh.size = Vector2(width, low.distance_to(high))
		surface.mesh = mesh
		surface.material_override = material
		surface.position.y = (low.y + high.y) * 0.5
		surface.rotation.x = -atan((max_z_height - min_z_height) / (max_z - min_z))
		body.add_child(surface)
	game.add_child(body)
	return body

func _build_wilderness(game: Node3D, stone: Material, dark: Material, moss: Material, paving: Material) -> void:
	game._box("GateTrail", Vector3(6.0, 0.55, 8.0), Vector3(0, -0.275, -18), moss, true)
	# Down-ramp shares the archive landing edge and trail; no vertical .7m step.
	_traversal_ramp(game, "RearTrailRamp", 4.8,
		Vector3(0, 0, -18), Vector3(0, 0.7, -14), paving)
	game._box("WildGroveFloor", Vector3(24, 0.7, 23), Vector3(0, -0.35, -31.5), moss, true)
	for side in [-1, 1]:
		game._box("TrailCoping", Vector3(0.45, 0.55, 6.5), Vector3(side * 2.9, 0.275, -18.5), stone, true)
		game._box("GroveBoundary", Vector3(0.6, 0.85, 23), Vector3(side * 11.7, 0.425, -31.5), dark, true)
		for index in range(6):
			var z := -22.5 - index * 3.7
			var x: float = side * (9.0 + sin(index * 2.1) * 1.2)
			var tree: Node3D = game._asset("grove_tree", Vector3(x, 0, z), 4.5 + fmod(index * 0.43, 1.7), 3.2)
			tree.rotation.y = index * 1.31
			game._register_occluder(tree, "grove_tree")
			game._proxy(Vector3(x, 1.2, z), Vector3(0.5, 2.4, 0.5))
	game._box("GroveRearBoundary", Vector3(24, 1.0, 0.6), Vector3(0, 0.5, -42.7), dark, true)
	for index in range(13):
		var flag := BoxMesh.new()
		flag.size = Vector3(1.3, 0.008, 1.1)
		game._mesh(flag, paving, Vector3(sin(index * 1.1) * 1.1, 0.004, -20.5 - index * 1.65))
	# Trees are reused KayKit CC0 assets; terrain is authored here.
