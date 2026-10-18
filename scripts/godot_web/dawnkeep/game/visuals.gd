# Dawnkeep visual adapter. Original environment and architecture authored in Blender;
# characters/foliage are licensed KayKit assets. No gameplay state is owned here.
extends Node3D

const ORIGINAL = "res://assets/original/"
const KAYKIT = "res://assets/kaykit/"
const PADS = [Vector3(-11,0,-4),Vector3(-5,0,-7),Vector3(-5,0,-1),Vector3(-8,0,5),Vector3(-3,0,5),Vector3(1,0,-2),Vector3(2,0,-8),Vector3(5,0,-1),Vector3(10,0,-3),Vector3(10,0,2),Vector3(4,0,7),Vector3(10,0,8)]
const PALETTE = {"sunbow":Color("ffd881"),"ember":Color("ff9c49"),"frost":Color("77ece6"),"storm":Color("bcb0ff")}
var gameplay: Node
var enemy_nodes: Dictionary = {}
var tower_nodes: Dictionary = {}
var prefabs: Dictionary = {}
var hero_root: Node3D
var hero_model: Node3D
var hero_anim: AnimationPlayer
var hero_health: MeshInstance3D
var hero_ring: MeshInstance3D
var range_ring: MeshInstance3D
var selected_ring: MeshInstance3D
var pad_rings: Array[MeshInstance3D] = []
var crystal: Node3D
var crystal_height: float = 0.0
var clock_time: float = 0.0
var effects: Array[Dictionary] = []
var hero_last_attack: bool = false
var hero_dead: bool = false
var hero_action_time: float = 0.0
var hero_last_position: Vector3

func setup(p_gameplay: Node) -> void:
	gameplay = p_gameplay
	name = "DawnkeepArt"
	var terrain = _instantiate(ORIGINAL+"world.glb",self)
	if terrain: _paint_meadow(terrain)
	var ground = StaticBody3D.new()
	ground.name = "WalkableGround"
	ground.collision_layer = 1
	ground.collision_mask = 0
	var shape = CollisionShape3D.new()
	var box = BoxShape3D.new()
	box.size = Vector3(35,0.3,24)
	shape.shape = box
	shape.position.y = -0.15
	ground.add_child(shape)
	add_child(ground)
	var shrine = _instantiate(ORIGINAL+"shrine.glb",self)
	if shrine:
		shrine.position = Vector3(13,0,5)
		_solid(shrine.position,2.05,.65)
		crystal = _find_named(shrine,"Heart_main_crystal")
		if crystal: crystal_height = crystal.position.y
	for p in [Vector3(11.3,0,8.1),Vector3(14.8,0,2.4)]:
		var standard = _instantiate(ORIGINAL+"standard.glb",self)
		if standard: standard.position = p
	_cliff_boundaries()
	_scatter_forest()
	# Native watchstones and lichen rocks are tangible solids; road slabs and grass are decor.
	for p in [Vector3(-12.7,0,-9.4),Vector3(-10,0,-9.8),Vector3(3.8,0,-9.3),Vector3(10,0,-8.6)]:
		_solid(p,.55,2.5)
	for p in [Vector3(-13,0,-10),Vector3(-5,0,-10),Vector3(11,0,-9),Vector3(15,0,-2),Vector3(15,0,9),Vector3(-7,0,10),Vector3(-16,0,2)]:
		_solid(p,.6,.55)
	for i in range(PADS.size()):
		var pad = _cylinder(1.0,0.08,Color("6b8380"),false)
		pad.position = PADS[i]+Vector3(0,0.025,0)
		pad.name = "BuildSocket_%02d"%i
		add_child(pad)
		var ring = _ring(0.84,Color("c5b477"),0.045)
		ring.position = PADS[i]+Vector3(0,0.09,0)
		add_child(ring)
		pad_rings.append(ring)
		# Four corner marks make an empty socket legible from the game camera.
		for k in range(4):
			var a = float(k)*PI*.5+PI*.25
			var dot = _cylinder(.065,.025,Color("d0c592"),true)
			dot.position = PADS[i]+Vector3(cos(a)*.67,.085,sin(a)*.67)
			add_child(dot)
	range_ring = _ring(1.0,Color(.5,.91,.9,.43),0.018)
	range_ring.visible = false
	add_child(range_ring)
	selected_ring = _ring(1.05,Color("fff0ac"),0.045)
	selected_ring.visible = false
	add_child(selected_ring)
	for portal in [Vector3(-15,0,-7),Vector3(-15,0,8)]:
		var ring = _ring(.87,Color(.88,.36,.31,.8),0.055)
		ring.position = portal+Vector3(0,.08,0)
		add_child(ring)
		var inner = _ring(.59,Color(.8,.28,.3,.3),.02)
		inner.position = portal+Vector3(0,.08,0)
		add_child(inner)
	_build_hero()

func _instantiate(path: String, parent: Node) -> Node3D:
	if not prefabs.has(path):
		if not ResourceLoader.exists(path):
			push_warning("Missing visual asset: "+path)
			return null
		prefabs[path] = load(path)
	var model = prefabs[path].instantiate() as Node3D
	parent.add_child(model)
	return model

func _scatter_forest() -> void:
	# Northern/western canopy silhouettes frame the board. The near edge stays low.
	var trees = [Vector3(-15.4,0,-9.5),Vector3(-11.5,0,-10.1),Vector3(-7.7,0,-10.1),Vector3(-3.5,0,-9.8),Vector3(.2,0,-10.4),Vector3(5.5,0,-9.7),Vector3(9.0,0,-9.2),Vector3(12.3,0,-7.5),Vector3(15.0,0,-4.5),Vector3(-16,0,-3.7),Vector3(-16.0,0,.2),Vector3(-15.8,0,4.5)]
	var rng = RandomNumberGenerator.new()
	rng.seed = 18026
	for i in range(trees.size()):
		var file = ["Tree_1_A_Color1.gltf","Tree_2_A_Color1.gltf","Tree_3_A_Color1.gltf"][i%3]
		var tree = _instantiate(KAYKIT+"forest/"+file,self)
		if not tree: continue
		tree.position = trees[i]
		var s = rng.randf_range(.75,1.05)
		tree.scale = Vector3.ONE*s
		tree.rotation.y = rng.randf_range(0,TAU)
		# Only trunks block. Never generate broad canopy colliders.
		_solid(tree.position,.34,1.65)
	var clusters = [Vector3(-14,0,-9),Vector3(-9.4,0,-9.1),Vector3(-5.2,0,-9.6),Vector3(3,0,-10),Vector3(8.8,0,-8.6),Vector3(12.6,0,-6.3),Vector3(15.3,0,-1),Vector3(15.4,0,7.7),Vector3(12.8,0,9.4),Vector3(7,0,9.5),Vector3(1.4,0,9.5),Vector3(-5,0,9.3),Vector3(-10,0,10.1),Vector3(-14.2,0,10),Vector3(-15.2,0,2.4),Vector3(-12.3,0,-.6),Vector3(3,0,3.8),Vector3(1.5,0,-6.7)]
	for i in range(clusters.size()):
		var p: Vector3 = clusters[i]
		var shrub = _instantiate(KAYKIT+"forest/"+["Bush_1_A_Color1.gltf","Bush_2_A_Color1.gltf"][i%2],self)
		if shrub:
			shrub.position = p
			shrub.scale = Vector3.ONE*rng.randf_range(2.1,3.0)
			shrub.rotation.y = rng.randf_range(0,TAU)
		for k in range(2):
			var grass = _instantiate(KAYKIT+"forest/Grass_1_A_Color1.gltf",self)
			if grass:
				grass.position = p+Vector3(rng.randf_range(-1,1),0,rng.randf_range(-1,1))
				grass.scale = Vector3.ONE*rng.randf_range(.6,1.0)
				grass.rotation.y = rng.randf_range(0,TAU)
	for p in [Vector3(-13.5,0,-9.2),Vector3(13,0,-8.1),Vector3(15,0,0),Vector3(14.5,0,9),Vector3(-7,0,10),Vector3(-16,0,6)]:
		var rock = _instantiate(KAYKIT+"forest/Rock_1_A_Color1.gltf",self)
		if rock:
			rock.position = p
			rock.scale = Vector3.ONE*2.1
			_solid(p,.58,1.13)
			rock.rotation.y = rng.randf_range(0,TAU)

func _solid(pos: Vector3, radius: float, height: float) -> void:
	var body = StaticBody3D.new()
	body.collision_layer = 1
	body.collision_mask = 0
	body.position = pos
	var collision = CollisionShape3D.new()
	var shape = CylinderShape3D.new()
	shape.radius = radius
	shape.height = height
	collision.shape = shape
	collision.position.y = height*.5
	body.add_child(collision)
	add_child(body)

func _build_hero() -> void:
	hero_root = Node3D.new()
	hero_root.name = "OathkeeperVisual"
	add_child(hero_root)
	hero_model = _instantiate(KAYKIT+"characters/Knight.glb",hero_root)
	if hero_model:
		hero_model.scale = Vector3.ONE*1.06
		_hero_livery(hero_model)
		hero_anim = _find_anim(hero_model)
		_play(hero_anim,["Idle_A","Idle"],true)
	hero_ring = _ring(.67,Color("ffce72"),.045)
	hero_ring.position.y = .09
	hero_root.add_child(hero_ring)
	hero_health = _healthbar(hero_root,2.5,Color("8cf0d6"),1.1)

func spawn_enemy(id: int, kind: String, pos: Vector3) -> void:
	if enemy_nodes.has(id): remove_enemy(id,false)
	var root = Node3D.new()
	root.name = "Enemy_%d_%s"%[id,kind]
	add_child(root)
	root.position = pos
	var file = "Skeleton_Minion.glb"
	if kind in ["skeleton","brute","boss"]: file = "Skeleton_Warrior.glb"
	elif kind == "runner": file = "Skeleton_Rogue.glb"
	elif kind == "wraith": file = "Skeleton_Mage.glb"
	var model = _instantiate(KAYKIT+"characters/"+file,root)
	var sc = 1.0
	if kind == "scout": sc = .8
	elif kind == "runner": sc = .84
	elif kind == "brute": sc = 1.3
	elif kind == "boss": sc = 1.9
	if model: model.scale = Vector3.ONE*sc
	var anim: AnimationPlayer = _find_anim(model) if model else null
	_play(anim,["Skeletons_Walking","Running_A","Walking_A","Walking"],true)
	var hp = _healthbar(root,2.38*sc,Color("ef8c7c"),.9*minf(sc,1.5))
	hp.visible = kind == "boss"
	var sigil = _ring(.4*sc,Color(.75,.3,.25,.32),.025)
	sigil.position.y = .07
	root.add_child(sigil)
	if kind == "boss":
		# An original broken crown makes the champion legible at strategic distance.
		var crown = _ring(.6,Color("f0ad58"),.07)
		crown.position.y = 3.72
		root.add_child(crown)
		for k in range(5):
			var tooth = _crystal_mesh(.16,.62,Color("e4ae66"))
			var a = float(k)*TAU/5
			tooth.position = Vector3(cos(a)*.6,3.92,sin(a)*.6)
			root.add_child(tooth)
	enemy_nodes[id] = {"root":root,"model":model,"anim":anim,"hp":hp,"sigil":sigil,"attacking":false,"kind":kind,"scale":sc}

func update_enemy(id: int, pos: Vector3, direction: Vector3, hp_ratio: float, status: Dictionary) -> void:
	if not enemy_nodes.has(id): return
	var d: Dictionary = enemy_nodes[id]
	var root: Node3D = d.root
	root.position = pos
	if direction.length_squared()>.001 and d.model:
		d.model.rotation.y = atan2(direction.x,direction.z)
	var hp: MeshInstance3D = d.hp
	hp.scale.x = maxf(.01,hp_ratio)
	hp.visible = hp_ratio<.995 or d.kind == "boss"
	var attacking = bool(status.get("attacking",false))
	if attacking != d.attacking:
		d.attacking = attacking
		if attacking: _play(d.anim,["Melee_1H_Attack_Chop","Melee_1H_Attack_Slice_Diagonal","Melee_1H_Attack_Slice_Horizontal"],true)
		else: _play(d.anim,["Skeletons_Walking","Running_A","Walking_A"],true)
	var material: StandardMaterial3D = d.sigil.material_override
	if float(status.get("stun",0))>0 or float(status.get("slow",0))>0: material.albedo_color = Color(.3,.92,1,.8)
	elif float(status.get("burn",0))>0: material.albedo_color = Color(1,.4,.12,.9)
	elif int(status.get("boss_phase",1))>1: material.albedo_color = Color(1,.15,.15,.8)
	else: material.albedo_color = Color(.8,.34,.25,.32)

func remove_enemy(id: int, defeated: bool) -> void:
	if not enemy_nodes.has(id): return
	var d: Dictionary = enemy_nodes[id]
	enemy_nodes.erase(id)
	if defeated:
		d.hp.visible = false
		d.sigil.visible = false
		_play(d.anim,["Skeletons_Death","Death_A","Death_B"],false)
		effects.append({"node":d.root,"remaining":.85,"life":.85,"type":"corpse"})
	else: d.root.queue_free()

func spawn_tower(id: int, kind: String, pos: Vector3, level: int, branch: String) -> void:
	remove_tower(id)
	var node = _instantiate(ORIGINAL+"tower_"+kind+".glb",self)
	if not node:return
	node.position = pos
	tower_nodes[id] = {"node":node,"kind":kind,"upgrade":null}
	if id>=0 and id<pad_rings.size(): pad_rings[id].visible = false
	update_tower(id,level,branch)

func update_tower(id: int, level: int, _branch: String) -> void:
	if not tower_nodes.has(id):return
	var d: Dictionary = tower_nodes[id]
	if level>1 and d.upgrade == null:
		var ring = _ring(.76,PALETTE.get(d.kind,Color.WHITE),.045)
		ring.position.y = 1.55
		d.node.add_child(ring)
		d.upgrade = ring
		d.node.scale = Vector3.ONE*1.08

func remove_tower(id: int) -> void:
	if not tower_nodes.has(id): return
	tower_nodes[id].node.queue_free()
	tower_nodes.erase(id)
	if id>=0 and id<pad_rings.size():pad_rings[id].visible = true

func update_hero(pos: Vector3, direction: Vector3, anim: Dictionary) -> void:
	if not hero_root:return
	hero_root.position = pos
	if hero_model and direction.length_squared()>.001:hero_model.rotation.y = atan2(direction.x,direction.z)
	var dead = bool(anim.get("dead",false))
	var attack = bool(anim.get("attack",false))
	if dead and not hero_dead: _play(hero_anim,["Death_A","Death_B"],false)
	elif not dead:
		if attack and not hero_last_attack:
			hero_action_time = .42
			if hero_anim: hero_anim.speed_scale = 1.5
			_play(hero_anim,["Melee_1H_Attack_Chop","Melee_1H_Attack_Slice_Diagonal"],false)
		elif not attack and hero_action_time<=0:
			if hero_anim: hero_anim.speed_scale = 1.0
			if bool(anim.get("moving",false)):_play(hero_anim,["Running_A","Walking_A"],true)
			else:_play(hero_anim,["Idle_A","Idle"],true)
	hero_dead = dead
	hero_last_attack = attack
	hero_health.scale.x = maxf(.01,float(anim.get("hp_ratio",1.0)))
	hero_health.visible = not dead
	hero_ring.visible = not dead
	var material: StandardMaterial3D = hero_ring.material_override
	material.albedo_color = Color("9cfff2") if bool(anim.get("rally",false)) else Color("ffce72")

func select_pad(index: int, radius: float) -> void:
	if not range_ring:return
	var valid = index>=0 and index<PADS.size()
	range_ring.visible = valid and radius>0
	selected_ring.visible = valid
	if valid:
		range_ring.position = PADS[index]+Vector3(0,.10,0)
		range_ring.scale = Vector3(radius,1,radius)
		selected_ring.position = PADS[index]+Vector3(0,.11,0)

func projectile(from: Vector3, to: Vector3, kind: String) -> void:
	var color: Color = PALETTE.get(kind,Color("ffe2a1"))
	if kind == "storm":
		# Branching three-segment electricity; instantaneous hit, brief afterimage.
		var last = from
		for i in range(1,5):
			var next = from.lerp(to,float(i)/4)
			if i<4: next+=Vector3(sin(clock_time*31+i)*.25,.12,cos(i*4.5)*.22)
			var bolt = _beam(last,next,.045,color)
			add_child(bolt)
			effects.append({"node":bolt,"remaining":.13,"life":.13,"type":"fade"})
			last = next
		return
	var bolt = _crystal_mesh(.12,.45,color)
	add_child(bolt)
	bolt.position = from
	var time = clampf(from.distance_to(to)/20.,.12,.45)
	effects.append({"node":bolt,"remaining":time,"life":time,"type":"projectile","from":from,"to":to,"arc":2.0 if kind=="ember" else .2})

func effect(kind: String, pos: Vector3, radius: float) -> void:
	if kind == "restart":
		for fx in effects:
			if is_instance_valid(fx.node):fx.node.queue_free()
		effects.clear()
		return
	var c = Color("82e5db")
	var lifetime = .55
	if kind in ["cleave","hit","build","upgrade"]: c = Color("ffe0a0")
	elif kind in ["starfall_warning","boss_warning"]:
		c = Color(1,.42,.23,.75)
		lifetime = .8
	elif kind in ["starfall","boss_slam"]:
		c = Color("ffa767")
		lifetime = .65
	elif kind in ["level_up","respawn","rally"]:
		c = Color("a2fff2")
		lifetime = 1.0
	var ring = _ring(maxf(radius,.2),c,.035)
	ring.position = pos+Vector3(0,.16,0)
	add_child(ring)
	effects.append({"node":ring,"remaining":lifetime,"life":lifetime,"type":"warning" if kind.ends_with("warning") else "ring"})
	if not kind.ends_with("warning"):
		for i in range(7):
			var shard = _crystal_mesh(.06,.3,c)
			add_child(shard)
			var a = float(i)*TAU/7+clock_time
			shard.position = pos+Vector3(cos(a)*radius*.45,.3,sin(a)*radius*.45)
			effects.append({"node":shard,"remaining":lifetime,"life":lifetime,"type":"spark","velocity":Vector3(cos(a)*1.2,1.8,sin(a)*1.2)})
	if kind == "starfall":
		var ray = _beam(pos+Vector3(0,8,0),pos+Vector3(0,.2,0),.18,Color("bcfff1"))
		add_child(ray)
		effects.append({"node":ray,"remaining":.25,"life":.25,"type":"fade"})

func _process(delta: float) -> void:
	clock_time += delta
	hero_action_time = maxf(0.0,hero_action_time-delta)
	if crystal:
		crystal.position.y = crystal_height+sin(clock_time*1.5)*.1
		crystal.rotate_y(delta*.18)
	for i in range(effects.size()-1,-1,-1):
		var d: Dictionary = effects[i]
		if not is_instance_valid(d.node):effects.remove_at(i);continue
		d.remaining -= delta
		if d.remaining<=0:
			d.node.queue_free()
			effects.remove_at(i)
			continue
		var t = 1.0-float(d.remaining)/float(d.life)
		var node: Node3D = d.node
		match d.type:
			"projectile":node.position = d.from.lerp(d.to,t)+Vector3(0,sin(t*PI)*d.arc,0)
			"ring":node.scale = Vector3.ONE*(.7+t*.5)
			"spark":node.position += d.velocity*delta
			"corpse":
				if t>.65:node.position.y -= delta*1.5
		if node is MeshInstance3D and d.type != "projectile":
			var material = node.material_override as StandardMaterial3D
			if material: material.albedo_color.a = (1.0-t)*.85

func _find_named(node: Node, needle: String) -> Node3D:
	if needle in str(node.name) and node is Node3D:return node
	for child in node.get_children():
		var found = _find_named(child,needle)
		if found:return found
	return null

func _find_anim(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:return node
	for child in node.get_children():
		var found = _find_anim(child)
		if found:return found
	return null

func _play(player: AnimationPlayer, candidates: Array, loop: bool) -> void:
	if not player:return
	for candidate in candidates:
		for animation in player.get_animation_list():
			if str(animation)==str(candidate) or str(animation).ends_with("/"+str(candidate)):
				if player.current_animation==animation and player.is_playing():return
				player.get_animation(animation).loop_mode = Animation.LOOP_LINEAR if loop else Animation.LOOP_NONE
				player.play(animation,.12)
				return

func _material(color: Color, glow: bool = false) -> StandardMaterial3D:
	var material = StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = .85
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if glow:
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled = true
		material.emission = Color(color.r,color.g,color.b)
		material.emission_energy_multiplier = .3
	return material

func _ring(radius: float, color: Color, thickness: float) -> MeshInstance3D:
	var node = MeshInstance3D.new()
	var mesh = TorusMesh.new()
	mesh.inner_radius = maxf(.01,radius-thickness)
	mesh.outer_radius = radius+thickness
	mesh.rings = 48
	mesh.ring_segments = 6
	node.mesh = mesh
	node.material_override = _material(color,true)
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node

func _cylinder(radius: float, height: float, color: Color, glow: bool) -> MeshInstance3D:
	var node = MeshInstance3D.new()
	var mesh = CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 8
	node.mesh = mesh
	node.material_override = _material(color,glow)
	return node

func _crystal_mesh(radius: float, height: float, color: Color) -> MeshInstance3D:
	var node = MeshInstance3D.new()
	var mesh = PrismMesh.new()
	mesh.size = Vector3(radius*2,height,radius*2)
	node.mesh = mesh
	node.material_override = _material(color,true)
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return node

func _beam(a: Vector3, b: Vector3, width: float, color: Color) -> MeshInstance3D:
	var node = _cylinder(width,a.distance_to(b),color,true)
	node.position = (a+b)*.5
	var d = (b-a).normalized()
	if absf(d.dot(Vector3.UP))<.999:node.basis = Basis(Quaternion(Vector3.UP,d))
	return node

func _healthbar(parent: Node3D, height: float, color: Color, width: float) -> MeshInstance3D:
	var node = MeshInstance3D.new()
	var quad = QuadMesh.new()
	quad.size = Vector2(width,.075)
	node.mesh = quad
	var material = _material(color,true)
	material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	material.no_depth_test = true
	node.material_override = material
	node.position.y = height
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(node)
	return node

func _paint_meadow(node: Node) -> void:
	if node is MeshInstance3D:
		var material = ShaderMaterial.new()
		material.shader = preload("res://shaders/meadow.gdshader")
		for i in range(node.mesh.get_surface_count()):
			var old: Material = node.mesh.surface_get_material(i)
			if old and str(old.resource_name).begins_with("grass"):
				node.set_surface_override_material(i,material)
	for child in node.get_children():_paint_meadow(child)

func _cliff_boundaries() -> void:
	var rim = [Vector2(-16.9,-9.3),Vector2(-12.2,-11.2),Vector2(-5.5,-10.8),Vector2(1,-11.7),Vector2(8.9,-10.9),Vector2(15.5,-8.6),Vector2(17,-3.2),Vector2(16.5,3.1),Vector2(16.9,8.2),Vector2(13,10.8),Vector2(5.2,11.4),Vector2(-2.7,10.9),Vector2(-9.3,11.6),Vector2(-15.6,10),Vector2(-17.2,4.7),Vector2(-17,-2.3)]
	for i in range(rim.size()):
		var a: Vector2 = rim[i]
		var b: Vector2 = rim[(i+1)%rim.size()]
		var middle: Vector2 = (a+b)*.5
		var body = StaticBody3D.new()
		body.name = "CliffEdge_%02d"%i
		body.collision_layer = 1
		body.collision_mask = 0
		body.position = Vector3(middle.x,1,middle.y)
		body.rotation.y = -atan2(b.y-a.y,b.x-a.x)
		var collision = CollisionShape3D.new()
		var box = BoxShape3D.new()
		box.size = Vector3(a.distance_to(b),2,.18)
		collision.shape = box
		body.add_child(collision)
		add_child(body)

func _hero_livery(node: Node) -> void:
	# Original warm heraldry over the CC0 mesh. Keeps the blue-and-gold armor.
	if node is MeshInstance3D and "Cape" in str(node.name):
		var material = StandardMaterial3D.new()
		material.albedo_color = Color("cd683b")
		material.roughness = .95
		node.material_override = material
	elif node is MeshInstance3D and str(node.name).begins_with("Knight_") and "Head" not in str(node.name):
		for i in range(node.mesh.get_surface_count()):
			var original: Material = node.mesh.surface_get_material(i)
			if original is StandardMaterial3D:
				var tinted = original.duplicate() as StandardMaterial3D
				tinted.albedo_color = Color(.62,.8,1.0)
				node.set_surface_override_material(i,tinted)
	for child in node.get_children():_hero_livery(child)
