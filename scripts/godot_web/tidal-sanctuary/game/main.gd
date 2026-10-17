extends Node3D

const SAVE_PATH = "user://tidal-sanctuary-v1.json"
var rng := RandomNumberGenerator.new()
var noise := FastNoiseLite.new()
var terrain_mesh: MeshInstance3D
var player: CharacterBody3D
var avatar: Node3D
var camera: Camera3D
var lanterns: Array[Node3D] = []
var lantern_lights: Array[OmniLight3D] = []
var activated: Array[bool] = [false,false,false]
var lantern_points := [Vector3(3.8,0,6.1),Vector3(-4.7,0,0.2),Vector3(2.5,0,-6.7)]
var sky_env: WorldEnvironment
var beacon: Node3D
var beam: MeshInstance3D
var ui: CanvasLayer
var objective: Label
var prompt: Label
var progress: Label
var title: Label
var message: Label
var timer := 0.0
var game_time := 0.0
var save_time := 0.0
var completed := false
var beacon_awakened := false
var capture := false
var demo := false
var demo_phase := 0
var demo_wait := 0.0
var ui_visible := true
var language := "en"
var material_stone: StandardMaterial3D
var material_dark: StandardMaterial3D
var material_gold: StandardMaterial3D
var material_leaves: Array[StandardMaterial3D] = []
var grass: Array[MeshInstance3D] = []
var birds: Array[Node3D] = []
var pulse_rings: Array[MeshInstance3D] = []
var touch_move := Vector2.ZERO
var touch_origin := Vector2.ZERO
var touch_active := false
var touch_index := -1
var tip_until := 0.0
var sea: MeshInstance3D
var screenshot_index := 0
var game_font:Font
var subtitle:Label
var action_button:Button

func mat(c: Color, roughness: float = .9) -> StandardMaterial3D:
 var m := StandardMaterial3D.new()
 m.albedo_color = c
 m.roughness = roughness
 return m

func _ready() -> void:
 var font_file:=FontFile.new()
 font_file.load_dynamic_font("res://sanctuary-font.otf")
 game_font=font_file
 rng.seed=834217
 noise.seed=428
 noise.frequency=.17
 noise.noise_type=FastNoiseLite.TYPE_SIMPLEX_SMOOTH
 capture="--capture" in OS.get_cmdline_user_args()
 demo="--demo" in OS.get_cmdline_user_args()
 material_stone=mat(Color("d6c7a6"))
 material_dark=mat(Color("718580"))
 material_gold=mat(Color("c89043"),.4)
 for c in ["325e50","416c54","587c56","6a875c"]: material_leaves.append(mat(Color(c)))
 make_environment()
 make_terrain()
 make_shore()
 make_rocks()
 make_ruins()
 make_nature()
 make_player()
 make_lanterns()
 make_beacon()
 make_birds()
 make_ui()
 load_game()
 if demo:
  activated=[false,false,false]
  player.position=Vector3(1.3,height_at(1.3,10.0)+.95,10)
 update_state()
 if "--audit" in OS.get_cmdline_user_args(): audit.call_deferred()
 print("TIDAL_READY ",JSON.stringify({"nodes":count_nodes(self),"renderer":RenderingServer.get_current_rendering_method(),"player":str(player.position),"saved":activated}))

func make_environment() -> void:
 sky_env=WorldEnvironment.new()
 var env := Environment.new()
 env.background_mode=Environment.BG_SKY
 var sky := Sky.new()
 var sm := ProceduralSkyMaterial.new()
 sm.sky_top_color=Color("83adb8")
 sm.sky_horizon_color=Color("d9e3d2")
 sm.ground_horizon_color=Color("d9e3d2")
 sm.ground_bottom_color=Color("729f9b")
 sky.sky_material=sm
 env.sky=sky
 env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
 env.ambient_light_color=Color("a7c0bc")
 env.ambient_light_energy=.65
 env.tonemap_mode=Environment.TONE_MAPPER_FILMIC
 env.tonemap_exposure=1.0
 env.fog_enabled=true
 env.fog_light_color=Color("a6cbc7")
 env.fog_light_energy=.6
 env.fog_density=.006
 env.fog_sky_affect=.25
 sky_env.environment=env
 add_child(sky_env)
 var sun := DirectionalLight3D.new()
 sun.name="LateAfternoonSun"
 sun.rotation_degrees=Vector3(-43,-32,0)
 sun.light_color=Color("ffe4b6")
 sun.light_energy=1.55
 sun.shadow_enabled=true
 sun.directional_shadow_max_distance=65
 sun.directional_shadow_mode=DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
 add_child(sun)
 sea=MeshInstance3D.new()
 var plane := PlaneMesh.new()
 plane.size=Vector2(320,320)
 plane.subdivide_width=100
 plane.subdivide_depth=100
 sea.mesh=plane
 var water := ShaderMaterial.new()
 water.shader=load("res://water.gdshader")
 sea.material_override=water
 sea.position.y=-.15
 add_child(sea)

func shore_radius(a: float) -> float:
 return 1.0+.075*sin(a*3.0+.6)+.055*sin(a*7.0)+.025*cos(a*11.0)

func island_radius(x: float,z: float) -> float:
 var a:=atan2(z/16.5,x/12.0)
 return Vector2(x/12.0,z/16.5).length()/shore_radius(a)

func height_at(x: float,z: float) -> float:
 var r:=island_radius(x,z)
 var base:=1.4+1.45*clampf((-z+5.0)/18.0,0,1)
 var shore:=smoothstep(1.05,.67,r)
 return -.6+shore*base + noise.get_noise_2d(x,z)*.36*shore + .33*sin(x*.21)*sin(z*.16)*shore

func path_x(z:float) -> float:
 return 1.7*sin(z*.4)

func terrain_color(p: Vector3) -> Color:
 var r:=island_radius(p.x,p.z)
 var variation:=noise.get_noise_2d(p.x*3,p.z*3)*.08
 var c:=Color("afbd80")
 if r>.80: c=Color("d9ceab")
 elif r>.71: c=Color("b9bb8a")
 if abs(p.x-path_x(p.z))<1.2 and p.z<12 and p.z> -10: c=Color("d7cba6")
 if p.z< -7 and abs(p.x)<5.5: c=Color("c2c49a")
 return Color(c.r+variation,c.g+variation,c.b+variation)

func triangle(st: SurfaceTool,a:Vector3,b:Vector3,c:Vector3,ca:Color,cb:Color,cc:Color) -> void:
 var normal:Vector3=(b-a).cross(c-a).normalized()
 st.set_normal(normal)
 st.set_color(ca);st.add_vertex(a)
 st.set_color(cc);st.add_vertex(c)
 st.set_color(cb);st.add_vertex(b)

func make_terrain() -> void:
 var st:=SurfaceTool.new()
 st.begin(Mesh.PRIMITIVE_TRIANGLES)
 var step:=.65
 for iz in range(56):
  for ix in range(44):
   var x:float=-14.3+ix*step
   var z:float=-18.2+iz*step
   var a:=Vector3(x,height_at(x,z),z)
   var b:=Vector3(x+step,height_at(x+step,z),z)
   var c:=Vector3(x,height_at(x,z+step),z+step)
   var d:=Vector3(x+step,height_at(x+step,z+step),z+step)
   if minf(minf(a.y,b.y),minf(c.y,d.y))<-.58: continue
   triangle(st,a,c,b,terrain_color(a),terrain_color(c),terrain_color(b))
   triangle(st,b,c,d,terrain_color(b),terrain_color(c),terrain_color(d))
 terrain_mesh=MeshInstance3D.new()
 terrain_mesh.name="SculptedIsland"
 terrain_mesh.mesh=st.commit()
 var m:=mat(Color.WHITE)
 m.vertex_color_use_as_albedo=true
 terrain_mesh.material_override=m
 add_child(terrain_mesh)
 terrain_mesh.create_trimesh_collision()
 # The distant silhouettes use the same palette, never crowding the playable path.
 for j in range(4):
  var p:=Vector3(-50+j*32,-1,-67-rng.randf_range(0,18))
  rock(p,Vector3(10+rng.randf()*8,6+rng.randf()*8,8+rng.randf()*5),mat(Color("7b9d96")),j+200)

func mesh_node(mesh: Mesh, p: Vector3, m: Material, parent: Node = self) -> MeshInstance3D:
 var n:=MeshInstance3D.new()
 n.mesh=mesh;n.position=p;n.material_override=m;parent.add_child(n)
 return n

func box(p:Vector3,sz:Vector3,m:Material,parent:Node=self) -> MeshInstance3D:
 var b:=BoxMesh.new();b.size=sz
 return mesh_node(b,p,m,parent)

func cylinder(p:Vector3,r:float,h:float,m:Material,parent:Node=self,top:float=-1.0) -> MeshInstance3D:
 var c:=CylinderMesh.new();c.top_radius=r if top<0 else top;c.bottom_radius=r;c.height=h;c.radial_segments=12;c.rings=1
 return mesh_node(c,p,m,parent)

func rock(p:Vector3,sz:Vector3,m:Material,seed_value:int) -> MeshInstance3D:
 var rr:=RandomNumberGenerator.new();rr.seed=seed_value
 var st:=SurfaceTool.new();st.begin(Mesh.PRIMITIVE_TRIANGLES)
 var rings:Array=[]
 for iy in range(5):
  var latitude:=float(iy)/4.0*PI
  var ring:Array[Vector3]=[]
  for j in range(10):
   var a:=j*TAU/10.0
   var perturb:=rr.randf_range(.81,1.17)
   ring.append(Vector3(sin(latitude)*cos(a)*sz.x*.5*perturb,cos(latitude)*sz.y*.5+rr.randf_range(-.035,.035)*sz.y,sin(latitude)*sin(a)*sz.z*.5*perturb))
  rings.append(ring)
 for iy in range(4):
  for j in range(10):
   var a:Vector3=rings[iy][j];var b:Vector3=rings[iy][(j+1)%10];var c:Vector3=rings[iy+1][j];var d:Vector3=rings[iy+1][(j+1)%10]
   var tint:=Color(1,1,1).darkened(rr.randf_range(0,.09))
   triangle(st,a,b,c,tint,tint,tint);triangle(st,b,d,c,tint,tint,tint)
 var n:=mesh_node(st.commit(),p,m)
 n.rotation.y=rr.randf_range(0,TAU)
 return n

func make_shore() -> void:
 var foam_mat:=mat(Color("bfe6d8"))
 foam_mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
 for band in range(3):
  var st:=SurfaceTool.new();st.begin(Mesh.PRIMITIVE_TRIANGLES)
  for i in range(192):
   var a:=float(i)/192*TAU;var b:=float(i+1)/192*TAU
   var r:=.967+band*.028
   var width:=.011 if band==0 else .004
   var p:=Vector3(cos(a)*12*shore_radius(a)*r,-.04,sin(a)*16.5*shore_radius(a)*r)
   var q:=Vector3(cos(b)*12*shore_radius(b)*r,-.04,sin(b)*16.5*shore_radius(b)*r)
   var p2:=Vector3(p.x*(1+width),p.y,p.z*(1+width));var q2:=Vector3(q.x*(1+width),q.y,q.z*(1+width))
   if i%19<14: triangle(st,p,q,p2,Color.WHITE,Color.WHITE,Color.WHITE);triangle(st,p2,q,q2,Color.WHITE,Color.WHITE,Color.WHITE)
  var n:=mesh_node(st.commit(),Vector3.ZERO,foam_mat)
  pulse_rings.append(n)

func make_rocks() -> void:
 for i in range(65):
  var a:=rng.randf()*TAU
  var r:=rng.randf_range(.80,1.05)
  var x:=cos(a)*12*shore_radius(a)*r
  var z:=sin(a)*16.5*shore_radius(a)*r
  if z>7 and abs(x)<4: continue
  var s:=rng.randf_range(.65,2.3)
  var stone:=mat(Color("c4baa0").lightened(rng.randf_range(-.15,.12)))
  rock(Vector3(x,height_at(x,z)+s*.18,z),Vector3(s*1.6,s*.9,s),stone,i+600)
 # Layered sea stacks frame the horizon.
 for i in range(3):
  rock(Vector3(19+i*2,-.2,-15-i*5),Vector3(4,4+i*2,3.5),material_stone,750+i)

func make_ruins() -> void:
  # Ancient processional path, each slab slightly sunk and individually weathered.
 for i in range(28):
  var z:=10.7-i*.74
  var x:=path_x(z)+rng.randf_range(-.16,.16)
  var slab:=rock(Vector3(x,height_at(x,z)+.06,z),Vector3(1.36,.20,.69),mat(Color("e0d4b9").darkened(rng.randf_range(0,.08))),i+1000)
  slab.rotation.y=rng.randf_range(-.13,.13)
 # Ruined courtyard at the destination.
 var h:=height_at(0,-8.0)
 for i in range(5):
  for j in range(4):
   var tile:=box(Vector3(-2.9+i*1.45,h-.06,-6.2-j*1.45),Vector3(1.4,.2,1.4),material_stone)
   tile.rotation.y=rng.randf_range(-.018,.018)
 for side in [-1,1]:
  for j in range(3):
   var x:float=side*3.7;var z:float=-6.4-j*2.0;var base:=height_at(x,z)
   var intact:bool=(j==2 or side==-1)
   var height:=3.8 if intact else 1.2+j*.45
   cylinder(Vector3(x,base+.18,z),.64,.32,material_stone)
   var column:=cylinder(Vector3(x,base+height*.5+.34,z),.36,height,material_stone,self,.31)
   column.create_trimesh_collision()
   cylinder(Vector3(x,base+height+.38,z),.52,.22,material_stone)
   # Dark seams and shallow fluting make the columns read as carved stone.
   for ring in range(3): cylinder(Vector3(x,base+.6+ring*1.0,z),.365,.035,mat(Color("a59e88")))
   if intact: box(Vector3(x,base+height+.58,z),Vector3(.95,.22,.85),material_stone)
 # A curved portal made of individual wedge stones.
 var center:=Vector3(0,h+2.9,-10.0)
 for side in [-1,1]:
  for layer in range(5):
   var n:=box(Vector3(side*1.65,h+.27+layer*.52,-10),Vector3(.66,.50,.85),material_stone)
   n.rotation.y=rng.randf_range(-.025,.025)
   n.create_trimesh_collision()
 for i in range(11):
  var a:=float(i)/10.0*PI
  var n:=box(center+Vector3(cos(a)*1.65,sin(a)*1.65,0),Vector3(.63,.70,.83),material_stone)
  n.rotation.z=a-PI/2
 # Deliberately broken lintel and fallen pieces.
 var lintel:=box(Vector3(-3.7,h+4.4,-8.4),Vector3(.85,.4,4.8),material_stone)
 lintel.rotation.z=.025
 for i in range(11):
  var x:=rng.randf_range(-5.6,5.6);var z:=rng.randf_range(-11.8,-5.0)
  if abs(x)<2.2: continue
  var b:=box(Vector3(x,height_at(x,z)+.16,z),Vector3(rng.randf_range(.35,.9),.3,rng.randf_range(.4,.9)),material_stone)
  b.rotation=Vector3(rng.randf_range(-.12,.12),rng.randf()*TAU,rng.randf_range(-.15,.15))

func branch_between(a:Vector3,b:Vector3,r:float,m:Material,parent:Node=self) -> void:
 var n:=cylinder((a+b)*.5,r,a.distance_to(b),m,parent,r*.48)
 n.quaternion=Quaternion(Vector3.UP,(b-a).normalized())

func tree(x:float,z:float,s:float,seed_value:int) -> void:
 var origin:=Vector3(x,height_at(x,z),z)
 var trunkmat:=mat(Color("675c47"))
 var trunk_top:=origin+Vector3(-.3*s,3.4*s,.12*s)
 branch_between(origin,trunk_top,.16*s,trunkmat)
 for j in range(5):
  var a:=j*2.4+seed_value
  var endpoint:=trunk_top+Vector3(cos(a)*1.3*s,-.4*s+j*.23*s,sin(a)*.9*s)
  branch_between(origin+Vector3(-.12*s,(1.7+j*.23)*s,0),endpoint,.075*s,trunkmat)
  var leaf:=rock(endpoint,Vector3(2.4*s,.75*s,1.65*s),material_leaves[j%4],seed_value*10+j)
  leaf.rotation.z=rng.randf_range(-.1,.1)

func make_nature() -> void:
 for t in [Vector3(-7,1.15,8),Vector3(7.3,1.25,5.5),Vector3(-7.8,1.4,-4),Vector3(7.4,.9,-8),Vector3(-5.8,1,-12),Vector3(6.5,.8,10.5),Vector3(-5,1.4,10.5)]: tree(t.x,t.z,t.y,2000+int(t.x*10+t.z))
 # Small layered bushes, not uniformly scattered noise.
 for i in range(34):
  var x:=rng.randf_range(-10,10);var z:=rng.randf_range(-12,11)
  if island_radius(x,z)>.76 or abs(x-path_x(z))<2.0 or (z< -5 and abs(x)<5): continue
  rock(Vector3(x,height_at(x,z)+.22,z),Vector3(1.2,.7,.95),material_leaves[i%4],3000+i)
 var st:=SurfaceTool.new();st.begin(Mesh.PRIMITIVE_TRIANGLES)
 for i in range(650):
  var x:=rng.randf_range(-11,11);var z:=rng.randf_range(-14,12)
  if island_radius(x,z)>.78 or abs(x-path_x(z))<1.7 or (z< -5 and abs(x)<5.3):continue
  var y:=height_at(x,z)+.03
  var a:=rng.randf()*TAU;var w:=rng.randf_range(.06,.14);var h:=rng.randf_range(.20,.47)
  var base:=Vector3(x,y,z);var dir:=Vector3(cos(a),0,sin(a))
  var c:=Color("7b9460").lightened(rng.randf_range(-.12,.15))
  triangle(st,base-dir*w,base+dir*w,base+Vector3(.13,h,0),c,c,c)
  triangle(st,base+dir*w,base-dir*w,base+Vector3(.13,h,0),c,c,c)
 var gm:=mat(Color.WHITE);gm.vertex_color_use_as_albedo=true;gm.cull_mode=BaseMaterial3D.CULL_DISABLED
 grass.append(mesh_node(st.commit(),Vector3.ZERO,gm))

func make_player() -> void:
 player=CharacterBody3D.new();player.name="Wayfarer";add_child(player)
 player.position=Vector3(1.3,height_at(1.3,10)+.9,10)
 var col:=CollisionShape3D.new();var shape:=CapsuleShape3D.new();shape.radius=.22;shape.height=.95;col.shape=shape;col.position.y=.48;player.add_child(col)
 avatar=Node3D.new();player.add_child(avatar)
 var coat:=mat(Color("c56443"))
 var body:=CylinderMesh.new();body.top_radius=.14;body.bottom_radius=.26;body.height=.55;body.radial_segments=10
 mesh_node(body,Vector3(0,.5,0),coat,avatar)
 var head:=SphereMesh.new();head.radius=.14;head.height=.28;head.radial_segments=12;head.rings=6
 mesh_node(head,Vector3(0,.89,0),mat(Color("e7d4ad")),avatar)
 cylinder(Vector3(0,.97,0),.23,.06,mat(Color("ddbf85")),avatar)
 cylinder(Vector3(0,1.02,0),.13,.08,mat(Color("ddbf85")),avatar)
 box(Vector3(0,.57,.17),Vector3(.21,.28,.14),mat(Color("665e45")),avatar)
 for side in [-1,1]: box(Vector3(side*.1,.14,0),Vector3(.12,.28,.14),mat(Color("4a5650")),avatar)
 camera=Camera3D.new();camera.name="FollowCamera";camera.fov=52;camera.near=.18;camera.far=190;add_child(camera)
 camera.position=player.position+Vector3(-10,12,15)
 camera.look_at(player.position+Vector3(0,.4,-2.0))

func make_lanterns() -> void:
 for i in range(3):
  var p:Vector3=lantern_points[i];p.y=height_at(p.x,p.z);lantern_points[i]=p
  var root:=Node3D.new();root.position=p;add_child(root);lanterns.append(root)
  cylinder(Vector3(0,.12,0),.57,.24,material_stone,root)
  cylinder(Vector3(0,.54,0),.20,.65,material_stone,root)
  cylinder(Vector3(0,.9,0),.34,.10,material_gold,root)
  var crystal:=SphereMesh.new();crystal.radius=.17;crystal.height=.38;crystal.radial_segments=8;crystal.rings=4
  var cmat:=mat(Color("73c5b1"),.25);cmat.emission_enabled=true;cmat.emission=Color("a2efce");cmat.emission_energy_multiplier=.5
  var gem:=mesh_node(crystal,Vector3(0,1.2,0),cmat,root);gem.name="Gem"
  var light:=OmniLight3D.new();light.position=Vector3(0,1.3,0);light.light_color=Color("a4ffdb");light.omni_range=3;light.light_energy=0;root.add_child(light);lantern_lights.append(light)
  var label:=Label3D.new();label.text=["I","II","III"][i];label.position=Vector3(0,1.8,0);label.font_size=32;label.pixel_size=.009;label.modulate=Color("f2e3be");label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;root.add_child(label)

func make_beacon() -> void:
 beacon=Node3D.new();beacon.position=Vector3(0,height_at(0,-11.7),-11.7);add_child(beacon)
 cylinder(Vector3(0,.17,0),1.15,.34,material_stone,beacon)
 cylinder(Vector3(0,.5,0),.80,.35,material_stone,beacon)
 var torus:=TorusMesh.new();torus.inner_radius=.60;torus.outer_radius=.76;torus.rings=24;torus.ring_segments=12
 var ring:=mesh_node(torus,Vector3(0,1.55,0),material_gold,beacon);ring.rotation.x=PI/2
 cylinder(Vector3(-.65,1.0,0),.08,1.0,material_gold,beacon)
 cylinder(Vector3(.65,1.0,0),.08,1.0,material_gold,beacon)
 var bmat:=mat(Color("fff2b3"));bmat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;bmat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;bmat.albedo_color.a=.28
 beam=cylinder(Vector3(0,5,0),.18,9,bmat,beacon,.07);beam.visible=false

func make_birds() -> void:
 var m:=mat(Color("ecedda"))
 for i in range(5):
  var n:=Node3D.new();add_child(n);birds.append(n)
  for side in [-1,1]:
   var wing:=box(Vector3(side*.19,0,0),Vector3(.42,.025,.08),m,n);wing.rotation.z=side*.25

func label_at(text_value:String,size:int,color:Color) -> Label:
 var l:=Label.new();l.text=text_value;l.add_theme_font_size_override("font_size",size);l.add_theme_font_override("font",game_font);l.add_theme_color_override("font_color",color);l.add_theme_color_override("font_shadow_color",Color(0,0,0,.4));l.add_theme_constant_override("shadow_offset_x",1);l.add_theme_constant_override("shadow_offset_y",2);return l

func make_ui() -> void:
 ui=CanvasLayer.new();add_child(ui)
 var root:=Control.new();root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);root.mouse_filter=Control.MOUSE_FILTER_IGNORE;ui.add_child(root)
 title=label_at("TIDAL  SANCTUARY",21,Color("fff2d2"));title.position=Vector2(34,28);root.add_child(title)
 subtitle=label_at("A quiet voyage · playable study",12,Color("e2e2c9"));subtitle.position=Vector2(36,57);root.add_child(subtitle)
 objective=label_at("Wake the three tide lanterns",24,Color("fff4d7"));objective.position=Vector2(34,91);root.add_child(objective)
 progress=label_at("○  ○  ○",22,Color("cce5ce"));progress.position=Vector2(36,126);root.add_child(progress)
 prompt=label_at("",19,Color("fff1ce"));prompt.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;prompt.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM);prompt.position=Vector2(-300,-106);prompt.size=Vector2(600,40);root.add_child(prompt)
 message=label_at("W A S D / arrows  ·  E interact  ·  R restart  ·  L language",13,Color("e2e7d2"));message.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT);message.position=Vector2(34,-38);root.add_child(message)
 action_button=Button.new();var action:=action_button;action.add_theme_font_override("font",game_font);action.text="E  ·  LIGHT";action.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT);action.position=Vector2(-160,-75);action.size=Vector2(130,48);action.pressed.connect(interact);root.add_child(action)

func update_state() -> void:
 var count:=0
 for i in range(3):
  if activated[i]:count+=1
  lantern_lights[i].light_energy=1.2 if activated[i] else .0
  var gem:MeshInstance3D=lanterns[i].get_node("Gem")
  var m:StandardMaterial3D=gem.material_override
  m.emission_energy_multiplier=2.5 if activated[i] else .3
 progress.text="%s  %s  %s" % ["●" if activated[0] else "○","●" if activated[1] else "○","●" if activated[2] else "○"]
 completed=count==3
 beam.visible=completed
 objective.text=("The sanctuary remembers" if completed else "Wake the three tide lanterns") if language=="en" else ("圣所已苏醒" if completed else "点亮三座潮汐灯")
 title.text="TIDAL  SANCTUARY" if language=="en" else "潮 汐 圣 所"
 subtitle.text="A quiet voyage · playable study" if language=="en" else "一段宁静旅程 · 可玩原型"
 message.text="W A S D / arrows  ·  E interact  ·  R restart  ·  L language" if language=="en" else "方向键移动 · E 互动 · R 重新开始 · L 语言"
 action_button.text="E · LIGHT" if language=="en" else "E · 点亮"
 if completed:prompt.text="Return to the ring of light" if language=="en" else "返回光之环"

func interact() -> void:
 for i in range(3):
  if player.position.distance_to(lantern_points[i])<2.1 and not activated[i]:
   activated[i]=true;update_state();save_game();tip_until=game_time+3.0
   prompt.text="A memory returns to the sea" if language=="en" else "海的记忆正在苏醒"
   print("TIDAL_LANTERN ",i)
   return
 if completed and player.position.distance_to(beacon.position)<2.7:
  beacon_awakened=true
  save_game()
  objective.text="You brought the light home" if language=="en" else "你带回了光"
  prompt.text="R  ·  Begin another quiet voyage" if language=="en" else "R · 再启一段宁静旅程"

func _unhandled_input(event: InputEvent) -> void:
 if event is InputEventKey and event.pressed and not event.echo:
  if event.keycode==KEY_E or event.keycode==KEY_SPACE:interact()
  if event.keycode==KEY_R:reset_game()
  if event.keycode==KEY_L:language="zh" if language=="en" else "en";update_state()
  if event.keycode==KEY_H:ui_visible=not ui_visible;ui.visible=ui_visible
 if event is InputEventScreenTouch and event.pressed and not touch_active:
  if event.position.x<get_viewport().get_visible_rect().size.x*.65:
   touch_active=true;touch_origin=event.position;touch_index=event.index

func _input(event:InputEvent) -> void:
 if event is InputEventScreenTouch and not event.pressed and event.index==touch_index:
  touch_active=false;touch_move=Vector2.ZERO;touch_index=-1
 elif event is InputEventScreenDrag and touch_active and event.index==touch_index:
  touch_move=(event.position-touch_origin).limit_length(70)/70

func _notification(what:int) -> void:
 if what==NOTIFICATION_APPLICATION_FOCUS_OUT:
  touch_active=false;touch_move=Vector2.ZERO;touch_index=-1

func _physics_process(delta:float) -> void:
 if player==null:return
 game_time+=delta
 var input:=Vector2.ZERO
 if Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT): input.x-=1
 if Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT):input.x+=1
 if Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP):input.y-=1
 if Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN):input.y+=1
 input+=touch_move
 input=input.limit_length()
 var right:=camera.global_basis.x
 right.y=0;right=right.normalized()
 var forward:=-camera.global_basis.z
 forward.y=0;forward=forward.normalized()
 var move:Vector3=(right*input.x-forward*input.y).normalized()*input.length()
 if demo:
  var target:Vector3=lantern_points[mini(demo_phase,2)] if demo_phase<3 else beacon.position
  var flat:=Vector3(target.x-player.position.x,0,target.z-player.position.z)
  if flat.length()>.85:move=flat.normalized()*.72
  else:
   move=Vector3.ZERO;demo_wait+=delta
   if demo_wait>1.2 and demo_phase<3:interact();demo_phase+=1;demo_wait=0
   elif demo_phase==3 and demo_wait>2:interact();demo_phase=4
  if demo_phase>=4:move=Vector3.ZERO
 var speed:=3.3
 player.velocity.x=move_toward(player.velocity.x,move.x*speed,delta*10)
 player.velocity.z=move_toward(player.velocity.z,move.z*speed,delta*10)
 player.velocity.y-=delta*18
 var next:=player.position+Vector3(player.velocity.x,0,player.velocity.z)*delta
 if island_radius(next.x,next.z)>.86:player.velocity.x=0;player.velocity.z=0
 player.move_and_slide()
 if player.position.y<-.7:player.position=Vector3(1.3,height_at(1.3,10)+1,10)
 if move.length()>.1:
  avatar.rotation.y=lerp_angle(avatar.rotation.y,atan2(-move.x,-move.z),delta*12)
  avatar.position.y=sin(game_time*12)*.025
 else:avatar.position.y=lerpf(avatar.position.y,0,delta*8)
 save_time+=delta
 if save_time>4:save_game();save_time=0
 # A high, collision-free diorama camera keeps the destination visible without orbit surprises.
 var aim:=player.position+Vector3(0,.5,-2.0)
 var desired:=player.position+Vector3(-9.5,12.5,15)
 var portrait:=get_viewport().get_visible_rect().size.x/get_viewport().get_visible_rect().size.y<.85
 if portrait:desired=player.position+Vector3(-7.8,15,17)
 var ray:=PhysicsRayQueryParameters3D.create(aim,desired)
 ray.exclude=[player.get_rid()]
 var hit:=get_world_3d().direct_space_state.intersect_ray(ray)
 if not hit.is_empty():desired=hit.position+hit.normal*.55
 camera.position=camera.position.lerp(desired,1-exp(-delta*3.5))
 camera.look_at(aim)
 if game_time>tip_until and completed:
  if beacon_awakened:
   objective.text="You brought the light home" if language=="en" else "你带回了光"
   prompt.text="R · Begin another quiet voyage" if language=="en" else "R · 再启一段宁静旅程"
  else:
   prompt.text=("E · Return the light" if player.position.distance_to(beacon.position)<2.7 else "Return to the ring of light") if language=="en" else ("E · 归还光芒" if player.position.distance_to(beacon.position)<2.7 else "返回光之环")
 elif game_time>tip_until:
  prompt.text=""
  for i in range(3):
   if not activated[i] and player.position.distance_to(lantern_points[i])<2.1:prompt.text="E  ·  Wake the tide lantern" if language=="en" else "E · 点亮潮汐灯"

func _process(delta:float) -> void:
 timer+=delta
 if objective:
  var width:=get_viewport().get_visible_rect().size.x
  message.offset_top=-24 if width<600 else -38
  message.offset_bottom=-2 if width<600 else -15
  objective.add_theme_font_size_override("font_size",19 if width<600 else 24)
  message.text=("Drag to move · Tap LIGHT" if language=="en" else "左侧拖动移动 · 轻触点亮") if width<600 else ("W A S D / arrows · E interact · R restart · L language" if language=="en" else "方向键移动 · E 互动 · R 重新开始 · L 语言")
  prompt.add_theme_font_size_override("font_size",15 if width<600 else 19)
 for i in range(lanterns.size()):
  var gem:MeshInstance3D=lanterns[i].get_node("Gem");gem.position.y=1.22+sin(timer*1.7+i)*.09;gem.rotation.y=timer*.45
 for i in range(birds.size()):
  var a:=timer*.11+i*1.2
  birds[i].position=Vector3(cos(a)*16,9+sin(a*1.7+i),-6+sin(a)*12)
  birds[i].rotation.y=-a
 for i in range(pulse_rings.size()):pulse_rings[i].position.y=sin(timer*.7+i)*.018
 if capture and timer>1.5+screenshot_index*6:
  screenshot_index+=1
  capture_frame.call_deferred(screenshot_index)
  if screenshot_index>=5:capture=false

func capture_frame(index:int) -> void:
 await RenderingServer.frame_post_draw
 var image:=get_viewport().get_texture().get_image()
 var output:=OS.get_environment("TIDAL_CAPTURE_DIR")
 if output.is_empty():output="user://"
 var path:=output.path_join("tidal-%02d.png"%index)
 print("TIDAL_CAPTURE ",path," ",image.save_png(path))
 if index>=5:get_tree().quit()

func save_game() -> void:
 if capture or demo:return
 var file:=FileAccess.open(SAVE_PATH,FileAccess.WRITE)
 if file:file.store_string(JSON.stringify({"schema":1,"activated":activated,"player":[player.position.x,player.position.y,player.position.z],"language":language,"beacon_awakened":beacon_awakened}))

func load_game() -> void:
 if not FileAccess.file_exists(SAVE_PATH):return
 var data=JSON.parse_string(FileAccess.get_file_as_string(SAVE_PATH))
 if not data is Dictionary or data.get("schema")!=1:return
 var a=data.get("activated",[])
 if a is Array and a.size()==3:
  for i in range(3):activated[i]=bool(a[i])
 var p=data.get("player",[])
 if p is Array and p.size()==3 and island_radius(float(p[0]),float(p[2]))<.86:
  player.position=Vector3(float(p[0]),maxf(float(p[1]),height_at(float(p[0]),float(p[2]))+.1),float(p[2]))
 language="zh" if data.get("language","en")=="zh" else "en"
 beacon_awakened=bool(data.get("beacon_awakened",false)) and activated==[true,true,true]

func reset_game() -> void:
 activated=[false,false,false];completed=false;beacon_awakened=false;player.position=Vector3(1.3,height_at(1.3,10)+.9,10);update_state();save_game()

func count_nodes(node:Node) -> int:
 var count:=1
 for child in node.get_children():count+=count_nodes(child)
 return count

func audit() -> void:
 await get_tree().process_frame
 await get_tree().physics_frame
 print("TIDAL_AUDIT ",JSON.stringify({"scene_nodes":count_nodes(self),"terrain_surfaces":terrain_mesh.mesh.get_surface_count(),"lanterns":lanterns.size(),"camera_fov":camera.fov,"camera_distance":camera.position.distance_to(player.position),"renderer":RenderingServer.get_current_rendering_method(),"save_exists":FileAccess.file_exists(SAVE_PATH),"active":activated}))
 get_tree().quit()

func _exit_tree() -> void:
 if is_instance_valid(player):print("TIDAL_FINAL ",JSON.stringify({"time":game_time,"position":str(player.position),"activated":activated,"demo_phase":demo_phase,"velocity":str(player.velocity),"floor":player.is_on_floor(),"wall":player.is_on_wall(),"ceiling":player.is_on_ceiling(),"height_expected":height_at(player.position.x,player.position.z),"collisions":player.get_slide_collision_count()}))
 if is_instance_valid(player):
  for i in range(player.get_slide_collision_count()):print("TIDAL_COLLISION ",player.get_slide_collision(i).get_normal()," ",player.get_slide_collision(i).get_collider().get_parent().name," ",player.get_slide_collision(i).get_position())
