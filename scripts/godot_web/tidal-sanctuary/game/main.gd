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
var beacon_ring: MeshInstance3D
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
var language_button:Button
var title_panel:Panel
var footer_panel:Panel
var prompt_panel:Panel
var touch_start_position:=Vector3.ZERO
var touch_start_frame:=0
var touch_drag_events:=0
var touch_gesture_id:=0
var language_change_id:=0

func mat(c: Color, roughness: float = .9) -> StandardMaterial3D:
 var m := StandardMaterial3D.new()
 m.albedo_color = c
 m.roughness = roughness
 return m

func _ready() -> void:
 if OS.has_feature("web"):
  game_font=load("res://sanctuary-font.otf")
 else:
  var font_file:=FontFile.new()
  var font_error:=font_file.load_dynamic_font("res://sanctuary-font.otf")
  assert(font_error==OK,"Font failed to load")
  game_font=font_file
 rng.seed=834217
 noise.seed=428
 noise.frequency=.17
 noise.noise_type=FastNoiseLite.TYPE_SIMPLEX_SMOOTH
 capture="--capture" in OS.get_cmdline_user_args()
 demo="--demo" in OS.get_cmdline_user_args()
 material_stone=mat(Color("959f98"))
 material_dark=mat(Color("405851"))
 material_gold=mat(Color("c89043"),.4)
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
 mark_frame_ready.call_deferred()
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
 env.ambient_light_color=Color("a7b8c0")
 env.ambient_light_energy=.35
 env.tonemap_mode=Environment.TONE_MAPPER_ACES
 env.tonemap_exposure=.95
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
 sun.light_color=Color("fff5e9")
 sun.light_energy=.52
 sun.shadow_enabled=true
 sun.shadow_bias=.35
 sun.shadow_normal_bias=4.0
 sun.directional_shadow_max_distance=38
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
 var north:=smoothstep(7.0,-10.0,z)
 var base:=1.45+3.25*north
 var shoulder:=.65*exp(-pow((x+5.0)/3.2,2.0)-pow((z+1.5)/6.5,2.0))
 var shore:=smoothstep(1.04,.83,r)
 var variation:=noise.get_noise_2d(x,z)*.30
 var plateau:=smoothstep(-4.5,-7.0,z)*(1.0-smoothstep(4.2,6.0,abs(x)))
 var land:=base+shoulder+variation
 land=lerpf(land,4.55,plateau)
 return -.60+shore*land

func path_x(z:float) -> float:
 return 1.7*sin(z*.4)

func terrain_color(p: Vector3) -> Color:
 var r:=island_radius(p.x,p.z)
 var patch:=noise.get_noise_2d(p.x*.65+35,p.z*.65-50)*.5+.5
 var c:=Color("62795e").lerp(Color("84916d"),smoothstep(.30,.72,patch))
 var path_width:=1.10+noise.get_noise_2d(p.x*2,p.z*.8)*.18
 var path_blend:=1.0-smoothstep(path_width,path_width+.45,abs(p.x-path_x(p.z)))
 if p.z<12 and p.z> -9:c=c.lerp(Color("9b8b6d"),path_blend*.9)
 if r>.79:
  var strata:=sin(p.y*5.0+noise.get_noise_2d(p.x*2,p.z*2)*1.2)*.5+.5
  c=Color("596a66").lerp(Color("849083"),strata*.55)
  if p.z>5.5:c=c.lerp(Color("afa184"),smoothstep(.78,.97,r)*.75)
 if p.y<.08:c=Color("355c59")
 if p.z< -6.5 and abs(p.x)<4.9:c=c.lerp(Color("7d8b7c"),.6)
 return c

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
 m.vertex_color_is_srgb=true
 terrain_mesh.material_override=m
 add_child(terrain_mesh)
 terrain_mesh.create_trimesh_collision()
 # Low, overlapping distant islets retain a dark water contact.
 var far_mat:=mat(Color("416a6b"));far_mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
 rock(Vector3(-29,-1.1,-44),Vector3(23,5.5,11),far_mat,201)
 rock(Vector3(-19,-1.4,-47),Vector3(15,4.2,9),far_mat,202)
 rock(Vector3(30,-1.6,-39),Vector3(19,5.0,12),far_mat,203)

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
 # Short, translucent swash patches, never a continuous contour around the island.
 var foam_mat:=mat(Color.WHITE)
 foam_mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
 foam_mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
 foam_mat.vertex_color_use_as_albedo=true
 foam_mat.cull_mode=BaseMaterial3D.CULL_DISABLED
 var st:=SurfaceTool.new();st.begin(Mesh.PRIMITIVE_TRIANGLES)
 for patch in range(11):
  var center:=rng.randf()*TAU
  var span:=rng.randf_range(.06,.17)
  for i in range(9):
   var a:=center-span*.5+span*i/9.0
   var b:=center-span*.5+span*(i+1)/9.0
   var r:=1.005+rng.randf_range(-.003,.003)
   var p:=Vector3(cos(a)*12*shore_radius(a)*r,-.025,sin(a)*16.5*shore_radius(a)*r)
   var q:=Vector3(cos(b)*12*shore_radius(b)*r,-.025,sin(b)*16.5*shore_radius(b)*r)
   var p2:=Vector3(p.x*1.013,p.y,p.z*1.013);var q2:=Vector3(q.x*1.013,q.y,q.z*1.013)
   var alpha:=sin(float(i)/9.0*PI)*.20
   var edge:=Color(.67,.80,.73,0);var mid:=Color(.67,.80,.73,alpha)
   triangle(st,p,q,p2,edge,edge,mid);triangle(st,p2,q,q2,mid,edge,mid)
 var n:=mesh_node(st.commit(),Vector3.ZERO,foam_mat);pulse_rings.append(n)

func make_rocks() -> void:
 for i in range(28):
  var a:=rng.randf()*TAU
  var r:=rng.randf_range(.91,1.035)
  var x:=cos(a)*12*shore_radius(a)*r
  var z:=sin(a)*16.5*shore_radius(a)*r
  if z>7 and abs(x)<5:continue
  var s:=rng.randf_range(1.25,2.65)
  var path:="res://assets/shore-rock-a.tscn" if i%3==0 else "res://assets/shore-rock-d.tscn"
  place_asset(path,Vector3(x,height_at(x,z)-.24,z),Vector3(s,s*rng.randf_range(.70,1.1),s*rng.randf_range(.85,1.3)),rng.randf()*TAU)
 # One clustered offshore formation rather than three regular bright peaks.
 for i in range(3):
  place_asset("res://assets/shore-rock-d.tscn",Vector3(20+i*1.4,-.7,-17-i*1.7),Vector3(5.0-i*.6,5.0-i*.7,5.2),i*.7)

func place_asset(path:String,p:Vector3,sz:Vector3,yaw:float) -> Node3D:
 var node:Node3D=load(path).instantiate()
 node.position=p;node.scale=sz;node.rotation.y=yaw;add_child(node)
 return node

func make_ruins() -> void:
  # Ancient processional path, each slab slightly sunk and individually weathered.
 for i in range(28):
  var z:=10.7-i*.74
  var x:=path_x(z)+rng.randf_range(-.16,.16)
  var slab:=rock(Vector3(x,height_at(x,z)+.06,z),Vector3(1.36,.20,.69),mat(Color("9ca394").darkened(rng.randf_range(0,.1))),i+1000)
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

func make_nature() -> void:
 # Authored CC0 silhouettes: open branching trees with a few thin conifers behind.
 for t in [Vector3(-7.6,4.8,6.8),Vector3(7.7,4.0,3.0),Vector3(-8.0,4.4,-3.5),Vector3(7.4,3.6,-8.0),Vector3(-6.1,3.4,-12.0)]:
  place_asset("res://assets/coastal-tree.tscn",Vector3(t.x,height_at(t.x,t.z)-.08,t.z),Vector3(t.y*.95,t.y,t.y*.85),rng.randf()*TAU)
 for t in [Vector3(-8.8,3.8,-6.0),Vector3(6.7,3.2,-11.7),Vector3(-6.8,3.1,-10.2)]:
  place_asset("res://assets/needle-pine.tscn",Vector3(t.x,height_at(t.x,t.z)-.08,t.z),Vector3.ONE*t.y,rng.randf()*TAU)
 var st:=SurfaceTool.new();st.begin(Mesh.PRIMITIVE_TRIANGLES)
 for i in range(230):
  var x:=rng.randf_range(-11,11);var z:=rng.randf_range(-14,12)
  if island_radius(x,z)>.76 or abs(x-path_x(z))<2.0 or (z< -5 and abs(x)<5.3):continue
  if noise.get_noise_2d(x*1.4+55,z*1.4)<.06:continue
  var y:=height_at(x,z)+.02
  var a:=rng.randf()*TAU;var w:=rng.randf_range(.045,.09);var h:=rng.randf_range(.13,.30)
  var base:=Vector3(x,y,z);var dir:=Vector3(cos(a),0,sin(a))
  var c:=Color("526f50").lightened(rng.randf_range(-.07,.10))
  triangle(st,base-dir*w,base+dir*w,base+Vector3(.10,h,0),c,c,c)
  triangle(st,base+dir*w,base-dir*w,base+Vector3(.10,h,0),c,c,c)
 var gm:=mat(Color.WHITE);gm.vertex_color_use_as_albedo=true;gm.vertex_color_is_srgb=true;gm.cull_mode=BaseMaterial3D.CULL_DISABLED
 grass.append(mesh_node(st.commit(),Vector3.ZERO,gm))

func make_player() -> void:
 player=CharacterBody3D.new();player.name="Wayfarer";add_child(player)
 player.position=Vector3(1.3,height_at(1.3,10)+.9,10)
 var col:=CollisionShape3D.new();var shape:=CapsuleShape3D.new();shape.radius=.22;shape.height=.95;col.shape=shape;col.position.y=.48;player.add_child(col)
 avatar=Node3D.new();avatar.scale=Vector3.ONE*1.3;player.add_child(avatar)
 var coat:=mat(Color("294b5d"))
 var body:=CylinderMesh.new();body.top_radius=.14;body.bottom_radius=.26;body.height=.55;body.radial_segments=10
 mesh_node(body,Vector3(0,.5,0),coat,avatar)
 var head:=SphereMesh.new();head.radius=.14;head.height=.28;head.radial_segments=12;head.rings=6
 mesh_node(head,Vector3(0,.89,-.10),mat(Color("d1b58e")),avatar)
 var hood:=SphereMesh.new();hood.radius=.19;hood.height=.37;hood.radial_segments=12;hood.rings=6
 mesh_node(hood,Vector3(0,.94,.035),coat,avatar)
 for side in [-1,1]:cylinder(Vector3(side*.21,.57,0),.055,.30,coat,avatar)
 box(Vector3(0,.57,.17),Vector3(.21,.28,.14),mat(Color("985b43")),avatar)
 for side in [-1,1]: box(Vector3(side*.1,.14,0),Vector3(.12,.28,.14),mat(Color("4a5650")),avatar)
 camera=Camera3D.new();camera.name="FollowCamera";camera.fov=55;camera.near=.18;camera.far=190;add_child(camera)
 camera.position=player.position+Vector3(-3.4,8.5,12)
 camera.look_at(player.position+Vector3(0,1.5,-2.0))

func make_lanterns() -> void:
 for i in range(3):
  var p:Vector3=lantern_points[i];p.y=height_at(p.x,p.z);lantern_points[i]=p
  var root:=Node3D.new();root.position=p;add_child(root);lanterns.append(root)
  cylinder(Vector3(0,.12,0),.57,.24,material_dark,root)
  cylinder(Vector3(0,.54,0),.20,.65,material_dark,root)
  cylinder(Vector3(0,.9,0),.34,.10,material_gold,root)
  var crystal:=SphereMesh.new();crystal.radius=.17;crystal.height=.38;crystal.radial_segments=8;crystal.rings=4
  var cmat:=mat(Color("eeb95f"),.25);cmat.emission_enabled=true;cmat.emission=Color("ffc771");cmat.emission_energy_multiplier=.5
  var gem:=mesh_node(crystal,Vector3(0,1.2,0),cmat,root);gem.name="Gem"
  var light:=OmniLight3D.new();light.position=Vector3(0,1.3,0);light.light_color=Color("ffc771");light.omni_range=3;light.light_energy=0;root.add_child(light);lantern_lights.append(light)

func make_beacon() -> void:
 beacon=Node3D.new();beacon.position=Vector3(0,height_at(0,-11.7),-11.7);add_child(beacon)
 cylinder(Vector3(0,.17,0),1.15,.34,material_stone,beacon)
 cylinder(Vector3(0,.5,0),.80,.35,material_stone,beacon)
 var torus:=TorusMesh.new();torus.inner_radius=.60;torus.outer_radius=.76;torus.rings=24;torus.ring_segments=12
 var ring_mat:=mat(Color("b18a48"),.5);ring_mat.emission_enabled=true;ring_mat.emission=Color("ffc771");ring_mat.emission_energy_multiplier=0
 beacon_ring=mesh_node(torus,Vector3(0,1.55,0),ring_mat,beacon);beacon_ring.rotation.x=PI/2
 cylinder(Vector3(-.65,1.0,0),.08,1.0,material_gold,beacon)
 cylinder(Vector3(.65,1.0,0),.08,1.0,material_gold,beacon)
 var glow:=GradientTexture2D.new();glow.width=64;glow.height=64;glow.fill=GradientTexture2D.FILL_RADIAL;glow.fill_from=Vector2(.5,.5);glow.fill_to=Vector2(1,.5)
 var gradient:=Gradient.new();gradient.set_color(0,Color(1,.72,.28,.55));gradient.set_color(1,Color(1,.72,.28,0));glow.gradient=gradient
 var bmat:=mat(Color.WHITE);bmat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;bmat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;bmat.albedo_texture=glow;bmat.billboard_mode=BaseMaterial3D.BILLBOARD_ENABLED;bmat.no_depth_test=false
 var quad:=QuadMesh.new();quad.size=Vector2(2.3,2.3)
 beam=mesh_node(quad,Vector3(0,1.55,.06),bmat,beacon);beam.visible=false

func make_birds() -> void:
 var m:=mat(Color("ecedda"))
 for i in range(5):
  var n:=Node3D.new();add_child(n);birds.append(n)
  for side in [-1,1]:
   var wing:=box(Vector3(side*.19,0,0),Vector3(.42,.025,.08),m,n);wing.rotation.z=side*.25

func ui_panel(p:Vector2,sz:Vector2,color:Color,parent:Node) -> Panel:
 var panel:=Panel.new();panel.position=p;panel.size=sz;panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
 var style:=StyleBoxFlat.new();style.bg_color=color;style.set_corner_radius_all(9)
 panel.add_theme_stylebox_override("panel",style);parent.add_child(panel);return panel

func label_at(text_value:String,size:int,color:Color) -> Label:
 var l:=Label.new();l.text=text_value;l.add_theme_font_size_override("font_size",size);l.add_theme_font_override("font",game_font);l.add_theme_color_override("font_color",color);l.add_theme_color_override("font_shadow_color",Color(0,0,0,.4));l.add_theme_constant_override("shadow_offset_x",1);l.add_theme_constant_override("shadow_offset_y",2);return l

func make_ui() -> void:
 ui=CanvasLayer.new();add_child(ui)
 var root:=Control.new();root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);root.mouse_filter=Control.MOUSE_FILTER_IGNORE;ui.add_child(root)
 title_panel=ui_panel(Vector2(16,16),Vector2(304,94),Color(.025,.075,.065,.72),root)
 footer_panel=ui_panel(Vector2(20,0),Vector2(460,30),Color(.025,.075,.065,.68),root)
 title=label_at("TIDAL  SANCTUARY",16,Color("fff2d2"));title.position=Vector2(28,23);root.add_child(title)
 subtitle=label_at("A quiet voyage · playable study",12,Color("e2e2c9"));subtitle.position=Vector2(36,57);root.add_child(subtitle);subtitle.visible=false
 objective=label_at("Wake three tide lanterns",17,Color("fff4d7"));objective.position=Vector2(28,48);root.add_child(objective)
 progress=label_at("○  ○  ○",18,Color("cce5ce"));progress.position=Vector2(28,76);root.add_child(progress)
 prompt_panel=ui_panel(Vector2.ZERO,Vector2(440,36),Color(.025,.075,.065,.76),root)
 prompt=label_at("",17,Color("fff1ce"));prompt.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;prompt.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM);prompt.position=Vector2(-300,-106);prompt.size=Vector2(600,40);root.add_child(prompt)
 message=label_at("W A S D / arrows  ·  E interact  ·  R restart  ·  L language",13,Color("e2e7d2"));message.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT);message.position=Vector2(34,-38);root.add_child(message)
 action_button=Button.new();var action:=action_button;action.add_theme_font_override("font",game_font);action.text="E  ·  LIGHT";action.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT);action.position=Vector2(-160,-75);action.size=Vector2(130,48);
 var button_style:=StyleBoxFlat.new();button_style.bg_color=Color(.05,.16,.14,.94);button_style.border_color=Color("cfba87");button_style.set_border_width_all(1);button_style.set_corner_radius_all(8)
 action.add_theme_stylebox_override("normal",button_style);action.add_theme_color_override("font_color",Color("fff1d2"));action.add_theme_font_size_override("font_size",16)
 action.pressed.connect(on_action_pressed);root.add_child(action)
 language_button=Button.new();language_button.text="EN";language_button.add_theme_font_override("font",game_font);language_button.add_theme_font_size_override("font_size",12);language_button.add_theme_stylebox_override("normal",button_style);language_button.add_theme_color_override("font_color",Color("fff1d2"));language_button.size=Vector2(40,28);language_button.pressed.connect(change_language.bind("button"));root.add_child(language_button)

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
 var ring_material:StandardMaterial3D=beacon_ring.material_override
 ring_material.emission_energy_multiplier=1.5 if beacon_awakened else (.6 if completed else .0)
 action_button.visible=true
 language_button.text="EN" if language=="en" else "ZH"
 objective.text=("The sanctuary remembers" if completed else "Wake three tide lanterns") if language=="en" else ("圣所已苏醒" if completed else "点亮三座潮汐灯")
 title.text="TIDAL  SANCTUARY" if language=="en" else "潮 汐 圣 所"
 subtitle.text="A quiet voyage · playable study" if language=="en" else "一段宁静旅程 · 可玩原型"
 message.text="W A S D / arrows  ·  E interact  ·  R restart  ·  L language" if language=="en" else "方向键移动 · E 互动 · R 重新开始 · L 语言"
 action_button.text=("R · RESTART" if beacon_awakened else ("E · RETURN" if completed else "E · LIGHT")) if language=="en" else ("R · 重新开始" if beacon_awakened else ("E · 归还" if completed else "E · 点亮"))
 if beacon_awakened:
  objective.text="You brought the light home" if language=="en" else "你带回了光"
  prompt.text="R · Begin another quiet voyage" if language=="en" else "R · 再启一段宁静旅程"
 elif game_time<tip_until:prompt.text="A memory returns to the sea" if language=="en" else "海的记忆正在苏醒"
 elif completed:prompt.text="Return to the ring of light" if language=="en" else "返回光之环"

func interact() -> void:
 for i in range(3):
  if player.position.distance_to(lantern_points[i])<2.1 and not activated[i]:
   activated[i]=true;update_state();save_game();tip_until=game_time+3.0
   prompt.text="A memory returns to the sea" if language=="en" else "海的记忆正在苏醒"
   print("TIDAL_LANTERN ",i)
   return
 if completed and player.position.distance_to(beacon.position)<2.7:
  beacon_awakened=true
  update_state()
  save_game()
  objective.text="You brought the light home" if language=="en" else "你带回了光"
  prompt.text="R  ·  Begin another quiet voyage" if language=="en" else "R · 再启一段宁静旅程"

func _unhandled_input(event: InputEvent) -> void:
 if event is InputEventKey and event.pressed and not event.echo:
  if event.keycode==KEY_E or event.keycode==KEY_SPACE:interact()
  if event.keycode==KEY_R:reset_game()
  if event.keycode==KEY_L:change_language("key_L")
  if event.keycode==KEY_H:ui_visible=not ui_visible;ui.visible=ui_visible
 if event is InputEventScreenTouch and event.pressed and not touch_active:
  if event.position.x<get_viewport().get_visible_rect().size.x*.65:
   touch_active=true;touch_origin=event.position;touch_index=event.index
   touch_start_position=player.position;touch_start_frame=Engine.get_physics_frames();touch_drag_events=0;touch_gesture_id+=1

func _input(event:InputEvent) -> void:
 if event is InputEventScreenTouch and not event.pressed and event.index==touch_index:
  touch_active=false;touch_move=Vector2.ZERO;touch_index=-1
  print("TIDAL_TOUCH_RELEASE ",JSON.stringify({"schema":1,"gesture_id":touch_gesture_id,"touch_index":event.index,"before":[touch_start_position.x,touch_start_position.y,touch_start_position.z],"after":[player.position.x,player.position.y,player.position.z],"physics_frames_elapsed":Engine.get_physics_frames()-touch_start_frame,"drag_events":touch_drag_events,"canceled":event.canceled,"demo":demo,"active_after":touch_active,"move_after":[touch_move.x,touch_move.y]}))
 elif event is InputEventScreenDrag and touch_active and event.index==touch_index:
  touch_move=(event.position-touch_origin).limit_length(70)/70
  touch_drag_events+=1

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
 if island_radius(next.x,next.z)>.86 and island_radius(next.x,next.z)>island_radius(player.position.x,player.position.z):player.velocity.x=0;player.velocity.z=0
 player.move_and_slide()
 if player.position.y<-.7:player.position=Vector3(1.3,height_at(1.3,10)+1,10)
 if move.length()>.1:
  avatar.rotation.y=lerp_angle(avatar.rotation.y,atan2(-move.x,-move.z),delta*12)
  avatar.position.y=sin(game_time*12)*.025
 else:avatar.position.y=lerpf(avatar.position.y,0,delta*8)
 save_time+=delta
 if save_time>4:save_game();save_time=0
 # A high, collision-free diorama camera keeps the destination visible without orbit surprises.
 var aim:=player.position+Vector3(0,1.5,-2.0)
 var desired:=player.position+Vector3(-3.4,8.5,12)
 var portrait:=get_viewport().get_visible_rect().size.x/get_viewport().get_visible_rect().size.y<.85
 if portrait:desired=player.position+Vector3(-1.7,10.5,15)
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
  var view_size:=get_viewport().get_visible_rect().size
  var width:=view_size.x
  title_panel.size.x=minf(304,width-32)
  language_button.position=Vector2(width-60,20)
  prompt_panel.size=Vector2(minf(440,width-32),36)
  prompt_panel.position=Vector2((width-prompt_panel.size.x)*.5,view_size.y-106)
  prompt_panel.visible=not prompt.text.is_empty()
  footer_panel.position=Vector2(20,view_size.y-(31 if width<600 else 44))
  footer_panel.size=Vector2(minf(460,width-40),30)
  message.offset_top=-24 if width<600 else -38
  message.offset_bottom=-2 if width<600 else -15
  objective.add_theme_font_size_override("font_size",16 if width<600 else 17)
  message.text=("Drag to move · Tap action" if language=="en" else "左侧拖动移动 · 轻触互动") if width<600 else ("W A S D / arrows · E interact · R restart · L language" if language=="en" else "方向键移动 · E 互动 · R 重新开始 · L 语言")
  prompt.add_theme_font_size_override("font_size",15 if width<600 else 17)
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
 if index>=5:
  # Explicitly labeled rendering diagnostic; not an alternate gameplay screenshot.
  var sun:DirectionalLight3D=get_node("LateAfternoonSun")
  sun.shadow_enabled=false
  await RenderingServer.frame_post_draw
  var diagnostic:=get_viewport().get_texture().get_image()
  print("TIDAL_SHADOW_DIAGNOSTIC ",diagnostic.save_png(output.path_join("diagnostic-no-shadows.png")))
  sun.shadow_enabled=true
  get_tree().quit()

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

func mark_frame_ready() -> void:
 if DisplayServer.get_name()=="headless":return
 await RenderingServer.frame_post_draw
 await get_tree().physics_frame
 await get_tree().physics_frame
 print("TIDAL_FRAME_READY ",JSON.stringify({"time":game_time,"viewport":str(get_viewport().get_visible_rect().size),"font_ascii":game_font.has_char(65)}))

func on_action_pressed() -> void:
 if beacon_awakened:reset_game()
 else:interact()

func change_language(trigger:String) -> void:
 var previous:=language
 language="zh" if language=="en" else "en";update_state();save_game()
 language_change_id+=1
 capture_language_frame.call_deferred(previous,language_change_id,trigger)

func capture_language_frame(previous:String,change_id:int,trigger:String) -> void:
 if DisplayServer.get_name()=="headless":await get_tree().process_frame
 else:await RenderingServer.frame_post_draw
 var labels:={"title":title.text,"subtitle":subtitle.text,"objective":objective.text,"footer":message.text,"action":action_button.text,"prompt":prompt.text}
 var missing:Array[int]=[]
 for text_value:String in labels.values():
  for i in range(text_value.length()):
   var cp:=text_value.unicode_at(i)
   if cp>32 and not game_font.has_char(cp) and cp not in missing:missing.append(cp)
 print("TIDAL_LANGUAGE_FRAME ",JSON.stringify({"schema":1,"change_id":change_id,"previous":previous,"language":language,"trigger":trigger,"labels":labels,"missing_codepoints":missing}))
