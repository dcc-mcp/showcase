extends SceneTree

const Stage = preload("res://scripts/archive_stage.gd")
var failures := 0

func _init() -> void:
	call_deferred("run")

func check(value: bool, message: String) -> void:
	if not value:
		failures += 1
		print("ENVIRONMENT_FAIL: " + message)

func surface_height(body: StaticBody3D, world_z: float) -> float:
	var collider: CollisionShape3D = body.find_children("*", "CollisionShape3D", false, false)[0]
	var point: Vector3
	var normal: Vector3
	if collider.shape is BoxShape3D:
		point = collider.global_transform * Vector3(0, collider.shape.size.y * 0.5, 0)
		normal = collider.global_basis.y.normalized()
	else:
		var points: PackedVector3Array = collider.shape.points
		var bottom := INF
		for vertex in points:
			bottom = minf(bottom, vertex.y)
		var top: Array[Vector3] = []
		for vertex in points:
			if vertex.y > bottom + 0.001:
				top.append(collider.global_transform * vertex)
		point = top[0]
		normal = (top[1] - point).cross(top[2] - point).normalized()
	return point.y - (normal.x * (body.global_position.x - point.x) + normal.z * (world_z - point.z)) / normal.y

func run() -> void:
	var game := Node3D.new()
	root.add_child(game)
	var stage = Stage.new()
	var material := StandardMaterial3D.new()
	stage._ramp(game, material)
	var access: StaticBody3D = game.get_node("ArchiveAccessRamp")
	var joined_height := surface_height(access, -9.0)
	check(absf(joined_height - 0.7) < 0.001, "Rear landing joint expected 0.700m, got %.6fm" % joined_height)
	if stage.has_method("_traversal_ramp"):
		for sample in [
			{"name":"RearJoin", "low":Vector3(0, 0, -18), "high":Vector3(0, 0.7, -14), "width":4.8},
			{"name":"WestJoin", "low":Vector3(-11.6, 0, -4.425), "high":Vector3(-11.6, 0.7, -7.525), "width":2.6}]:
			var ramp: StaticBody3D = stage._traversal_ramp(game, sample.name, sample.width, sample.low, sample.high, material)
			check(absf(surface_height(ramp, sample.low.z) - sample.low.y) < 0.001, sample.name + " lower joint")
			check(absf(surface_height(ramp, sample.high.z) - sample.high.y) < 0.001, sample.name + " upper joint")
			var surface: MeshInstance3D = ramp.get_node("TraversalSurface")
			for sign_value in [-1.0, 1.0]:
				var vertex: Vector3 = surface.global_transform * Vector3(0, 0, sign_value * surface.mesh.size.y * 0.5)
				check(absf(surface_height(ramp, vertex.z) - vertex.y) < 0.001, sample.name + " rendered and collision top agree")
	else:
		check(false, "Shared endpoint-aligned traversal ramp is missing")
	if stage.has_method("_water"):
		var water: MeshInstance3D = stage._water(game)
		check(water.name == "SunkenWater" and water.mesh is PlaneMesh, "Water uses a real subdivided surface")
		check(water.mesh.subdivide_width == 64 and water.mesh.subdivide_depth == 64, "Water geometry stays bounded")
		check(water.material_override is ShaderMaterial and water.material_override.shader != null, "Water shader is assigned")
		check(is_equal_approx(water.position.y, -3.4), "Existing visible water height is retained")
	else:
		check(false, "Flowing water surface is missing")
	game.queue_free()
	await process_frame
	print("ENVIRONMENT_REVISION_CHECKS failures=%d; geometry/resource checks only, not rendered quality or real input" % failures)
	quit(1 if failures else 0)
