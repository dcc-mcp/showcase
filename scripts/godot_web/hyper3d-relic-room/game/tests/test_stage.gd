extends SceneTree
const Main = preload("res://scripts/main.gd")
var game: Node3D
func _init() -> void: call_deferred("run")
func run() -> void:
	game=Node3D.new(); game.set_script(Main); root.add_child(game)
	game.qa_enabled=true
	game.qa_stage("playing")
	game.courier.position=Vector3(30,-3,0)
	game.courier.velocity=Vector3(8,-20,0)
	game.courier.dash_remaining=.15
	game.courier.invulnerable=1.0
	var health: int=game.expedition.health
	for index in range(2): await physics_frame
	assert(game.courier.position.distance_to(game.SPAWN)<.5 and game.courier.dash_remaining==0.0 and game.courier.velocity.length()<1.1,"Open-edge recovery resets movement during damage grace")
	assert(game.expedition.health==health and game.camera.position.y>5.0)
	for sample in [{"point":Vector3(4,-.05,.83),"key":"column"},{"point":Vector3(4,-.05,-4),"key":"shrine"}]:
		game.courier.position=sample.point
		game._follow_camera(1.0); game._update_occluders(1.0/60.0)
		var faded := false
		for record in game.camera_occluders:
			if record.key==sample.key and record.occluded and record.alpha<=.2: faded=true
		assert(faded,"Previously observed obstruction must fade")
	game.courier.position=Vector3(4,-.05,-29)
	game._follow_camera(1.0); game._update_occluders(1.0/60.0)
	var native_fades := 0
	for record in game.camera_occluders:
		if record.key=="grove_tree" and record.occluded:
			for mesh in record.meshes:
				assert(mesh.material_override.albedo_color.a<=.2,"Whole-mesh material override must actually receive native tree fade")
				native_fades += 1
	assert(native_fades>0,"Observed Arc target obstruction must identify native tree materials")
	game._set_state("exhibit"); game._update_occluders(1.0/60.0)
	for record in game.camera_occluders: assert(record.alpha==1.0)
	assert(game._characters_ready() and game.loaded_assets.size()==11 and game.missing_assets.is_empty())
	assert(game.generated_instanced_triangles<300000,"Instanced source geometry upper budget includes hidden/dead instances; not GPU-visible triangles")
	print("RELIC_STAGE_PASS: edge recovery, observed occlusion recovery, actual assets/clip contract, 300k instanced budget; continuous geometry is test_expedition_route")
	game.queue_free()
	await process_frame
	quit(0)
