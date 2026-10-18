extends Node3D

const SAVE_PATH = "user://tidal-sanctuary-v2.json"
const SwimController = preload("res://swim_controller.gd")
const SEA_LEVEL := -0.15
var rng := RandomNumberGenerator.new()
var noise := FastNoiseLite.new()
var terrain_mesh: MeshInstance3D
var player: CharacterBody3D
var avatar: Node3D
var camera: Camera3D
var lanterns: Array[Node3D] = []
var lantern_lights: Array[OmniLight3D] = []
var activated: Array[bool] = [false,false,false]
var lantern_points := [Vector3(1.3,0,7.8),Vector3(-3.8,0,3.4),Vector3(8.2,0,5.5)]
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
var restart_available_time := 0.0
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
var hero_camera_locked:=false
var stone_materials:Array[StandardMaterial3D]=[]
var swim := SwimController.new()
var avatar_body:Node3D
var arms:Array[Node3D]=[]
var legs:Array[Node3D]=[]
var swim_wake:MeshInstance3D
var compass:Label
var state_clock:=0.0
var sample_id:=0
var presentation_pending:=false
var presentation_id:=0
var hint_text:=""
var chest_lids:Array[Node3D]=[]
var route_points:Array[Vector3]=[]
var route_phase:=0
var demo_captures:Dictionary={}
var loaded_found:=false
var last_move:=Vector3.ZERO
var fern_material:StandardMaterial3D
var fern_meshes:Array[Mesh]=[]

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
 prepare_surface_assets()
 material_stone=stone_materials[0]
 material_dark=mat(Color("405851"))
 material_gold=mat(Color("c89043"),.4)
 make_environment()
 make_terrain()
 make_shore()
 make_rocks()
 make_ruins()
 make_nature()
 make_sanctuary_details()
 make_player()
 make_lanterns()
 make_beacon()
 make_birds()
 make_ui()
 if OS.has_feature("web"):get_tree().auto_accept_quit=false
 load_game()
 if demo:
  activated=[false,false,false]
  beacon_awakened=false
  player.position=Vector3(1.3,height_at(1.3,10.0)+.08,10)
 route_points=[lantern_points[0],lantern_points[1],Vector3(1.5,0,6.2),lantern_points[2],Vector3(7,0,.5),Vector3(2,0,-3),beacon.position]
 update_state()
 emit_load_receipt()
 if "--audit" in OS.get_cmdline_user_args(): audit.call_deferred()
 mark_frame_ready.call_deferred()
 print("TIDAL_READY ",JSON.stringify({"nodes":count_nodes(self),"renderer":RenderingServer.get_current_rendering_method(),"player":str(player.position),"saved":activated}))

func make_environment() -> void:
 sky_env=WorldEnvironment.new()
 var env := Environment.new()
 env.background_mode=Environment.BG_SKY
 var sky := Sky.new()
 var sm := ProceduralSkyMaterial.new()
 sm.sky_top_color=Color("7397ad")
 sm.sky_horizon_color=Color("d2d8cc")
 sm.ground_horizon_color=Color("d2d8cc")
 sm.ground_bottom_color=Color("729f9b")
 sky.sky_material=sm
 env.sky=sky
 env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
 env.ambient_light_color=Color("8faec5")
 env.ambient_light_energy=.34
 env.tonemap_mode=Environment.TONE_MAPPER_ACES
 env.tonemap_exposure=.95
 env.fog_enabled=true
 env.fog_light_color=Color("a6cbc7")
 env.fog_light_energy=.6
 env.fog_density=.008
 env.fog_sky_affect=.25
 sky_env.environment=env
 add_child(sky_env)
 var sun := DirectionalLight3D.new()
 sun.name="LateAfternoonSun"
 sun.rotation_degrees=Vector3(-43,-32,0)
 sun.light_color=Color("ffe4c3")
 sun.light_energy=.82
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
 sea.position.y=SEA_LEVEL
 sea.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
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
 var variation:=noise.get_noise_2d(x,z)*.17
 var plateau:=smoothstep(-4.5,-7.0,z)*(1.0-smoothstep(4.2,6.0,abs(x)))
 var land:=lerpf(base+shoulder+variation,4.55,plateau)
 # Eroded cove: continuous sand ramp, never an invisible coastal wall.
 var cove:=2.9*exp(-pow((x-8.0)/5.1,2.0)-pow((z-5.0)/4.5,2.0))
 return -.60+shore*land-2.7*smoothstep(.98,1.36,r)-cove

func path_x(z:float) -> float:
 return 1.7*sin(z*.4)

func terrain_color(p: Vector3) -> Color:
 var patch:=noise.get_noise_2d(p.x*.72+35,p.z*.72-50)*.5+.5
 var c:=Color("6a8064").lerp(Color("87916e"),smoothstep(.30,.72,patch))
 var sand:=Color("b9b496").lerp(Color("a7aa8f"),patch*.35)
 c=c.lerp(sand,1.0-smoothstep(.35,1.3,p.y))
 var trail:=1.0-smoothstep(.55,1.7,abs(p.x-path_x(p.z)))
 if p.z<3 and p.z> -8:c=c.lerp(Color("a1a18a"),trail*.55)
 if p.y<.0:c=c.lerp(Color("718c7c"),smoothstep(0.0,-1.6,p.y)*.6)
 if p.z< -6.5 and abs(p.x)<4.9:c=c.lerp(Color("969d8b"),.32)
 return c

func triangle(st: SurfaceTool,a:Vector3,b:Vector3,c:Vector3,ca:Color,cb:Color,cc:Color) -> void:
 var normal:Vector3=(b-a).cross(c-a).normalized()
 st.set_normal(normal)
 st.set_color(ca);st.add_vertex(a)
 st.set_color(cc);st.add_vertex(c)
 st.set_color(cb);st.add_vertex(b)

func make_terrain() -> void:
 var st:=SurfaceTool.new();st.begin(Mesh.PRIMITIVE_TRIANGLES)
 var step:=.48
 for iz in range(100):
  for ix in range(100):
   var x:float=-24.0+ix*step;var z:float=-24.0+iz*step
   var a:=Vector3(x,height_at(x,z),z);var b:=Vector3(x+step,height_at(x+step,z),z)
   var c:=Vector3(x,height_at(x,z+step),z+step);var d:=Vector3(x+step,height_at(x+step,z+step),z+step)
   terrain_triangle(st,a,b,c)
   terrain_triangle(st,b,d,c)
 st.index()
 terrain_mesh=MeshInstance3D.new();terrain_mesh.name="SculptedCove";terrain_mesh.mesh=st.commit()
 var m:=mat(Color.WHITE);m.vertex_color_use_as_albedo=true;m.vertex_color_is_srgb=true
 m.albedo_texture=surface_noise(Color("d6d7cd"),Color("ffffff"),.8)
 m.uv1_triplanar=true;m.uv1_world_triplanar=true;m.uv1_scale=Vector3.ONE*.7
 terrain_mesh.material_override=m;add_child(terrain_mesh);terrain_mesh.create_trimesh_collision()

func terrain_triangle(st:SurfaceTool,a:Vector3,b:Vector3,c:Vector3) -> void:
 for p in [a,b,c]:
  var dx:=height_at(p.x+.12,p.z)-height_at(p.x-.12,p.z)
  var dz:=height_at(p.x,p.z+.12)-height_at(p.x,p.z-.12)
  st.set_normal(Vector3(-dx,.24,-dz).normalized());st.set_color(terrain_color(p));st.add_vertex(p)

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
 # Wet sand and submerged stones give the cove its readable shore boundary.
 for i in range(26):
  var x:=rng.randf_range(.8,12.0);var z:=rng.randf_range(1.0,10.6)
  var h:=height_at(x,z)
  if h<-.55 or h>.38:continue
  var size:=rng.randf_range(.10,.35)
  var p:=rock(Vector3(x,h+.015,z),Vector3(size,size*.35,size*.72),stone_materials[i%4],4100+i)
  p.rotation.y=rng.randf()*TAU

func make_rocks() -> void:
 for center in [Vector3(-9,0,6),Vector3(-10,0,-2),Vector3(-7,0,-12),Vector3(8,0,-8),Vector3(11,0,-1.6)]:
  for i in range(4):
   var x:float=center.x+rng.randf_range(-1.4,1.4);var z:float=center.z+rng.randf_range(-1.3,1.3)
   var size:=rng.randf_range(1.1,2.8)
   var path:="res://assets/shore-rock-a.tscn" if i%3==0 else "res://assets/shore-rock-d.tscn"
   place_asset(path,Vector3(x,height_at(x,z)-.20,z),Vector3(size,size*rng.randf_range(.7,1.3),size*.9),rng.randf()*TAU)
 for i in range(4):
  var x:float=12.6+i*.75;var z:float=5.2-i*.65
  place_asset("res://assets/shore-rock-d.tscn",Vector3(x,-1.35,z),Vector3(2.3-i*.22,2.5-i*.3,2.2),i*.82)

func place_asset(path:String,p:Vector3,sz:Vector3,yaw:float) -> Node3D:
 var node:Node3D=load(path).instantiate()
 node.position=p;node.scale=sz;node.rotation.y=yaw;add_child(node)
 return node

func encoded_texture(path:String) -> ImageTexture:
 var image:=Image.new()
 var buffer:=FileAccess.get_file_as_bytes(path)
 var error:=image.load_png_from_buffer(buffer) if path.ends_with(".png.bin") else image.load_jpg_from_buffer(buffer)
 assert(error==OK,"Static surface texture could not be decoded")
 image.generate_mipmaps()
 return ImageTexture.create_from_image(image)

func prepare_surface_assets() -> void:
 var normal:=encoded_texture("res://assets/polyhaven/stone-normal.png.bin")
 var rough:=encoded_texture("res://assets/polyhaven/stone-rough.jpg.bin")
 for tint in [Color("a7afa4"),Color("919f95"),Color("b2b5a6"),Color("96a59a")]:
  var material:=mat(tint)
  material.albedo_texture=surface_noise(Color("b7bdb1"),Color("f3f0de"),1.1)
  material.normal_enabled=true;material.normal_texture=normal;material.normal_scale=.25
  material.roughness_texture=rough
  material.uv1_triplanar=true;material.uv1_world_triplanar=true;material.uv1_scale=Vector3.ONE*.58
  material.texture_filter=BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
  stone_materials.append(material)
 fern_material=mat(Color("a3b59a"))
 fern_material.albedo_texture=encoded_texture("res://assets/polyhaven/fern-albedo.png.bin")
 fern_material.normal_enabled=true;fern_material.normal_texture=encoded_texture("res://assets/polyhaven/fern-normal.jpg.bin");fern_material.normal_scale=.3
 fern_material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR;fern_material.alpha_scissor_threshold=.38
 fern_material.cull_mode=BaseMaterial3D.CULL_DISABLED;fern_material.texture_filter=BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
 for i in range(4):fern_meshes.append(load("res://assets/polyhaven/fern-%d.res"%i))

func surface_noise(dark:Color,light:Color,frequency:float) -> NoiseTexture2D:
 var field:=FastNoiseLite.new();field.seed=713;field.frequency=.028*frequency;field.fractal_octaves=4
 var tex:=NoiseTexture2D.new();tex.width=256;tex.height=256;tex.seamless=true;tex.generate_mipmaps=true;tex.noise=field
 var gradient:=Gradient.new();gradient.set_color(0,dark);gradient.set_color(1,light);tex.color_ramp=gradient
 return tex

func beveled_block(p:Vector3,sz:Vector3,m:Material,seed_value:int,wear:float=.08) -> MeshInstance3D:
 var rr:=RandomNumberGenerator.new();rr.seed=seed_value
 var h:=sz*.5
 var bevel:=minf(minf(h.x,h.y),h.z)*wear
 var points:Dictionary={}
 for x in [-1,1]:
  for y in [-1,1]:
   for z in [-1,1]:
    var cut:=bevel*rr.randf_range(.7,1.8)
    points[Vector3i(x,y,z)]=[Vector3(x*h.x,y*(h.y-cut),z*(h.z-cut)),Vector3(x*(h.x-cut),y*h.y,z*(h.z-cut)),Vector3(x*(h.x-cut),y*(h.y-cut),z*h.z)]
 var st:=SurfaceTool.new();st.begin(Mesh.PRIMITIVE_TRIANGLES)
 for axis in range(3):
  for side in [-1,1]:
   var face:Array[Vector3]=[]
   for uv in [Vector2i(-1,-1),Vector2i(1,-1),Vector2i(1,1),Vector2i(-1,1)]:
    var key:=Vector3i.ZERO;key[axis]=side;key[(axis+1)%3]=uv.x;key[(axis+2)%3]=uv.y
    face.append(points[key][axis])
   stone_face(st,face)
 for axis in range(3):
  for side_a in [-1,1]:
   for side_b in [-1,1]:
    var a:=Vector3i.ZERO;a[axis]=-1;a[(axis+1)%3]=side_a;a[(axis+2)%3]=side_b
    var b:=a;b[axis]=1
    stone_face(st,[points[a][(axis+1)%3],points[b][(axis+1)%3],points[b][(axis+2)%3],points[a][(axis+2)%3]])
 for key in points:stone_face(st,points[key])
 return mesh_node(st.commit(),p,m)

func stone_face(st:SurfaceTool,points:Array) -> void:
 var center:=Vector3.ZERO
 for p:Vector3 in points:center+=p
 center/=points.size()
 for i in range(1,points.size()-1):
  var a:Vector3=points[0];var b:Vector3=points[i];var c:Vector3=points[i+1]
  if (b-a).cross(c-a).dot(center)<0:triangle(st,a,c,b,Color.WHITE,Color.WHITE,Color.WHITE)
  else:triangle(st,a,b,c,Color.WHITE,Color.WHITE,Color.WHITE)

func make_ruins() -> void:
 # Sparse buried remnants, with earth between groups instead of an even zipper path.
 for group_z in [8.8,5.5,2.2,-1.2]:
  for i in range(3):
   var z:float=group_z+rng.randf_range(-.6,.6)
   var x:=path_x(z)+rng.randf_range(-.7,.7)
   var slab:=beveled_block(Vector3(x,height_at(x,z)+.005,z),Vector3(rng.randf_range(.58,1.05),.14,rng.randf_range(.43,.7)),stone_materials[i%4],1000+i+int(group_z*10),.32)
   slab.rotation=Vector3(rng.randf_range(-.06,.06),rng.randf_range(-.6,.6),rng.randf_range(-.04,.04))
 # Broad, uneven threshold steps follow the existing walkable terrain.
 for row in range(4):
  var z:float=-4.2-row*.63
  var x:=path_x(z)*.5
  for side in [-1,1]:
   var px:float=x+side*.75+rng.randf_range(-.08,.08)
   var slab:=beveled_block(Vector3(px,height_at(px,z)+.015,z),Vector3(1.5,.22,rng.randf_range(.60,.76)),stone_materials[row%4],1210+row*3+side,.38)
   slab.rotation.y=rng.randf_range(-.09,.09)
 var h:=height_at(0,-8.0)
 for row in range(4):
  for col in range(5):
   if (row==0 and col==0) or (row==2 and col==4) or (row==3 and col==0):continue
   var x:float=-2.65+col*1.32+rng.randf_range(-.10,.10)
   var z:float=-6.5-row*1.30+rng.randf_range(-.11,.11)
   var tile:=beveled_block(Vector3(x,h-.06+rng.randf_range(-.04,.025),z),Vector3(rng.randf_range(1.12,1.28),.22,rng.randf_range(1.11,1.3)),stone_materials[(row+col)%4],1500+row*5+col,.40)
   tile.rotation.y=rng.randf_range(-.05,.05)
 # Four survivors, different heights and broken caps, replace the clean colonnade.
 for info in [Vector3(-3.8,1.0,-5.9),Vector3(-3.65,3.5,-9.3),Vector3(3.7,.75,-6.2),Vector3(3.8,2.55,-10.1)]:
  var base:=height_at(info.x,info.z)
  var material:=stone_materials[rng.randi_range(0,3)]
  var foot:=beveled_block(Vector3(info.x,base+.13,info.z),Vector3(1.0,.30,1.0),material,rng.randi(),.3)
  foot.rotation.y=.12
  var column:=cylinder(Vector3(info.x,base+info.y*.5+.23,info.z),.37,info.y,material,self,.32)
  column.create_trimesh_collision()
  var cap:=beveled_block(Vector3(info.x,base+info.y+.23,info.z),Vector3(.82,.22,.75),material,rng.randi(),.34)
  cap.rotation=Vector3(.045,-.09,.07)
 # Worn arch stones: narrow dark joints and chipped edges, no smooth white facade.
 var center:=Vector3(0,h+2.68,-10.0)
 for side in [-1,1]:
  for layer in range(5):
   var n:=beveled_block(Vector3(side*1.65,h+.25+layer*.49,-10),Vector3(.66,.48,.92),stone_materials[(layer+2)%4],2000+layer*3+side,.24)
   n.rotation.y=rng.randf_range(-.035,.035)
   n.create_trimesh_collision()
 for i in range(11):
  var a:=float(i)/10.0*PI
  var n:=beveled_block(center+Vector3(cos(a)*1.65,sin(a)*1.65,0),Vector3(.62,.69,.94),stone_materials[i%4],2100+i,.20)
  n.rotation.z=a-PI/2
 # Broken return wall, tapering irregularly toward the entrance.
 for row in range(4):
  for column in range(5-row):
   var z:float=-8.65+column*.87
   var x:float=-4.25+rng.randf_range(-.045,.045)
   var wall:=beveled_block(Vector3(x,height_at(x,z)+.24+row*.43,z),Vector3(.67,.44,.87),stone_materials[(row+column)%4],2300+row*8+column,.29)
   wall.rotation.y=rng.randf_range(-.04,.04)
 for i in range(19):
  var x:=rng.randf_range(-5.1,5.2);var z:=rng.randf_range(-11.5,-4.1)
  if abs(x)<2.6:continue
  var slab:=beveled_block(Vector3(x,height_at(x,z)+.08,z),Vector3(rng.randf_range(.20,.65),rng.randf_range(.12,.3),rng.randf_range(.24,.61)),stone_materials[i%4],2500+i,.55)
  slab.rotation=Vector3(rng.randf_range(-.25,.25),rng.randf()*TAU,rng.randf_range(-.2,.2))

func make_sanctuary_details() -> void:
 # Ferns grow in clustered damp seams; the central walking line stays open.
 for center in [Vector3(-3.0,0,-4.6),Vector3(-4.9,0,-6.0),Vector3(-4.5,0,-9.5),Vector3(3.5,0,-5.1),Vector3(4.9,0,-8.4),Vector3(2.7,0,-11.6)]:
  for i in range(7):
   var x:float=center.x+rng.randf_range(-.7,.7);var z:float=center.z+rng.randf_range(-.55,.55)
   var variant:=2+i%2 if i>1 else i
   var fern:=mesh_node(fern_meshes[variant],Vector3(x,height_at(x,z)+.01,z),fern_material)
   fern.scale=Vector3.ONE*rng.randf_range(.85,1.65)
   fern.rotation.y=rng.randf()*TAU
 # Small stone/moss pockets ground the wall and leave larger quiet areas intact.
 for i in range(48):
  var side:float=-1 if i%2==0 else 1
  var x:float=side*rng.randf_range(2.75,5.8)
  var z:=rng.randf_range(-12.4,-3.6)
  if noise.get_noise_2d(x*2,z*2)<-.1:continue
  var size:=rng.randf_range(.12,.42)
  var pebble:=rock(Vector3(x,height_at(x,z)+size*.12,z),Vector3(size,size*.42,size*.7),stone_materials[i%4],3000+i)
  pebble.rotation.y=rng.randf()*TAU

func make_nature() -> void:
 for info in [Vector3(-6.8,4.5,5.7),Vector3(-8.1,3.2,4.4),Vector3(-6.1,2.5,7.0),Vector3(-7.3,4.1,-3.0),Vector3(-8.9,3.1,-5),Vector3(7.7,3.8,-2.2),Vector3(9.3,2.8,-3.8)]:
  var n:=place_asset("res://assets/coastal-tree.tscn",Vector3(info.x,height_at(info.x,info.z)-.08,info.z),Vector3(info.y*.95,info.y,info.y*.85),rng.randf()*TAU)
  n.rotation.z=rng.randf_range(-.07,.07)
 for center in [Vector3(-5.6,0,4.5),Vector3(-6.9,0,6.2),Vector3(-7.7,0,-2.7),Vector3(6.5,0,-2.0),Vector3(7.8,0,-4),Vector3(-3.6,0,2.0)]:
  for i in range(10):
   var x:float=center.x+rng.randf_range(-1.0,1.0);var z:float=center.z+rng.randf_range(-.9,.9)
   if height_at(x,z)<.5:continue
   var fern:=mesh_node(fern_meshes[2+i%2],Vector3(x,height_at(x,z)+.01,z),fern_material)
   fern.scale=Vector3.ONE*rng.randf_range(1.1,2.3);fern.rotation.y=rng.randf()*TAU
 for center in [Vector3(-5.4,0,7.7),Vector3(-8,0,1.8),Vector3(6.2,0,-1.3),Vector3(-5.9,0,-5.5)]:
  for i in range(6):
   var x:float=center.x+rng.randf_range(-.9,.9);var z:float=center.z+rng.randf_range(-.7,.7)
   var size:=rng.randf_range(.4,.8)
   rock(Vector3(x,height_at(x,z)+size*.16,z),Vector3(size,size*.65,size*.9),mat(Color("4a705e").lightened(i*.018)),4900+i)

func make_player() -> void:
 player=CharacterBody3D.new();player.name="Wayfarer";add_child(player)
 player.position=Vector3(1.3,height_at(1.3,10)+.08,10)
 var col:=CollisionShape3D.new();var shape:=CapsuleShape3D.new();shape.radius=.22;shape.height=.95;col.shape=shape;col.position.y=.48;player.add_child(col)
 avatar=Node3D.new();player.add_child(avatar)
 avatar_body=Node3D.new();avatar_body.position.y=.6;avatar.add_child(avatar_body)
 var cloth:=mat(Color("315e72"));var skin:=mat(Color("d4b486"));var trousers:=mat(Color("405664"))
 var torso:=CapsuleMesh.new();torso.radius=.20;torso.height=.55;torso.radial_segments=12;torso.rings=4
 mesh_node(torso,Vector3.ZERO,cloth,avatar_body)
 var head:=SphereMesh.new();head.radius=.16;head.height=.32;head.radial_segments=16;head.rings=8
 mesh_node(head,Vector3(0,.4,-.035),skin,avatar_body)
 cylinder(Vector3(0,.52,0),.20,.13,mat(Color("b8925b")),avatar_body)
 cylinder(Vector3(0,.48,-.015),.28,.035,mat(Color("c9ab70")),avatar_body)
 box(Vector3(0,.03,.19),Vector3(.25,.31,.16),mat(Color("a8603d")),avatar_body)
 for side in [-1,1]:
  var arm:=Node3D.new();arm.position=Vector3(side*.23,.13,0);avatar_body.add_child(arm);arms.append(arm)
  cylinder(Vector3(0,-.17,0),.065,.34,cloth,arm);cylinder(Vector3(0,-.36,0),.053,.13,skin,arm)
  var leg:=Node3D.new();leg.position=Vector3(side*.105,-.19,0);avatar_body.add_child(leg);legs.append(leg)
  cylinder(Vector3(0,-.16,0),.075,.32,trousers,leg);box(Vector3(0,-.34,-.04),Vector3(.15,.12,.23),mat(Color("394e50")),leg)
 var wake_mesh:=TorusMesh.new();wake_mesh.inner_radius=.27;wake_mesh.outer_radius=.32;wake_mesh.rings=24;wake_mesh.ring_segments=4
 var wm:=mat(Color(.65,.86,.83,.45));wm.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;wm.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
 swim_wake=mesh_node(wake_mesh,Vector3.ZERO,wm);swim_wake.visible=false
 swim.safe_spawn_position=player.position
 camera=Camera3D.new();camera.name="FollowCamera";camera.fov=55;camera.near=.18;camera.far=150;add_child(camera)
 camera.position=player.position+Vector3(-3.4,7.3,10)
 camera.look_at(player.position+Vector3(0,.9,-1.4))

func make_lanterns() -> void:
 for i in range(3):
  var p:Vector3=lantern_points[i];p.y=height_at(p.x,p.z) if i<2 else SEA_LEVEL-.12;lantern_points[i]=p
  var root:=Node3D.new();root.position=p;root.name=["MarinersChart","GroveCache","ReefCache"][i];add_child(root);lanterns.append(root)
  if i==0:
   beveled_block(p+Vector3(0,.35,0),Vector3(.85,.7,.7),stone_materials[0],5100,.4)
   box(Vector3(0,.73,0),Vector3(.64,.035,.47),mat(Color("e4d9b1")),root)
   for j in range(3):box(Vector3(-.2+j*.18,.756,0),Vector3(.055,.007,.30-j*.055),mat(Color("817b61")),root)
  else:
   var wood:=mat(Color("735b42"));var band:=mat(Color("bca36d"),.55)
   if i==2:
    cylinder(Vector3(0,.16,0),.42,.22,mat(Color("bd7150")),root)
    cylinder(Vector3(0,.7,0),.032,.98,band,root)
    var flag:=box(Vector3(.20,1.12,0),Vector3(.4,.26,.025),mat(Color("d5b57c")),root);flag.rotation.z=-.10
   else:
    box(Vector3(0,.24,0),Vector3(.82,.45,.55),wood,root)
    for side in [-1,1]:box(Vector3(side*.27,.25,0),Vector3(.065,.48,.58),band,root)
   var lid:=Node3D.new();lid.position=Vector3(0,.46,.27);root.add_child(lid);chest_lids.append(lid)
   box(Vector3(0,.025,-.27),Vector3(.86,.12,.59),wood,lid)
   if i==2:lid.visible=false
  var crystal:=SphereMesh.new();crystal.radius=.11;crystal.height=.22;crystal.radial_segments=12;crystal.rings=6
  var cmat:=mat(Color("efc878"),.4);cmat.emission_enabled=true;cmat.emission=Color("e7b966");cmat.emission_energy_multiplier=.18
  var gem:=mesh_node(crystal,Vector3(0,1.0,0),cmat,root);gem.name="Gem";gem.visible=false
  var light:=OmniLight3D.new();light.position=Vector3(0,.85,0);light.light_color=Color("ffcb88");light.omni_range=2;light.light_energy=0;root.add_child(light);lantern_lights.append(light)

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
 var lamp:=OmniLight3D.new();lamp.name="RingLight";lamp.position=Vector3(0,1.65,.4);lamp.light_color=Color("ffbf70");lamp.light_energy=0;lamp.omni_range=4.8;beacon.add_child(lamp)

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
 title_panel=ui_panel(Vector2(16,16),Vector2(350,120),Color(.035,.10,.12,.84),root)
 footer_panel=ui_panel(Vector2(20,0),Vector2(460,30),Color(.035,.10,.12,.72),root)
 title=label_at("TIDAL SANCTUARY",13,Color("b7d6d0"));title.position=Vector2(28,25);root.add_child(title)
 objective=label_at("Find the mariner's chart",18,Color("f4e9cb"));objective.position=Vector2(28,49);root.add_child(objective)
 progress=label_at("",13,Color("dfca94"));progress.position=Vector2(28,78);root.add_child(progress)
 subtitle=label_at("",12,Color("bdd1ca"));subtitle.position=Vector2(28,102);root.add_child(subtitle)
 compass=label_at("",13,Color("e8dcae"));compass.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;root.add_child(compass)
 prompt_panel=ui_panel(Vector2.ZERO,Vector2(440,38),Color(.035,.10,.12,.86),root)
 prompt=label_at("",16,Color("fff1ce"));prompt.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;root.add_child(prompt)
 message=label_at("",12,Color("d2e2d9"));root.add_child(message)
 action_button=Button.new();action_button.add_theme_font_override("font",game_font);action_button.size=Vector2(132,50)
 var style:=StyleBoxFlat.new();style.bg_color=Color(.055,.17,.19,.95);style.border_color=Color("cdb887");style.set_border_width_all(1);style.set_corner_radius_all(12)
 action_button.add_theme_stylebox_override("normal",style);action_button.add_theme_color_override("font_color",Color("fff1d2"));action_button.add_theme_font_size_override("font_size",15);action_button.pressed.connect(on_action_pressed);root.add_child(action_button)
 language_button=Button.new();language_button.text="EN";language_button.add_theme_font_override("font",game_font);language_button.add_theme_font_size_override("font_size",12);language_button.add_theme_stylebox_override("normal",style);language_button.add_theme_color_override("font_color",Color("fff1d2"));language_button.size=Vector2(40,28);language_button.pressed.connect(change_language.bind("button"));root.add_child(language_button)

func update_state() -> void:
 completed=activated==[true,true,true]
 for i in range(3):
  lantern_lights[i].light_energy=.35 if activated[i] else 0.0
  var gem:MeshInstance3D=lanterns[i].get_node("Gem");gem.visible=activated[i] and i>0
 if chest_lids.size()>0:chest_lids[0].rotation.x=-1.1 if activated[1] else 0.0
 beam.visible=beacon_awakened
 beacon.get_node("RingLight").light_energy=.65 if beacon_awakened else (.2 if completed else 0.0)
 var ring_material:StandardMaterial3D=beacon_ring.material_override
 ring_material.emission_energy_multiplier=.65 if beacon_awakened else (.18 if completed else 0.0)
 var stage:=quest_stage()
 var english:=["Find the mariner's chart","Search beneath the grove","Swim to the red reef buoy","Bring the pearl to the ruins","Treasure recovered"]
 var chinese:=["寻找航海图","搜寻树林下的宝箱","游向红色浮标","将珍珠带回遗迹","寻宝完成"]
 objective.text=english[stage] if language=="en" else chinese[stage]
 title.text="TIDAL SANCTUARY" if language=="en" else "潮 汐 圣 所"
 progress.text=("Chart  %s    Key  %s    Pearl  %s" % ["●" if activated[0] else "○","●" if activated[1] else "○","●" if activated[2] else "○"]) if language=="en" else ("海图 %s   钥匙 %s   珍珠 %s" % ["●" if activated[0] else "○","●" if activated[1] else "○","●" if activated[2] else "○"])
 var clues:=["A weathered chart waits on the shore.","Look between the leaning trees.","A red flag marks the sheltered cove.","Leave the water by the northern beach.","The sea's story is yours."]
 var zh:=["岸边的石台上留着一张海图","线索藏在倾斜的树木之间","红旗标记着海湾里的宝藏","从北侧沙滩上岸，返回遗迹","海的故事属于你"]
 subtitle.text=clues[stage] if language=="en" else zh[stage]
 language_button.text="EN" if language=="en" else "ZH"
 action_button.text=("RESTART" if beacon_awakened else "E · INTERACT") if language=="en" else ("重新开始" if beacon_awakened else "E · 互动")
 update_prompt()

func quest_stage() -> int:
 if beacon_awakened:return 4
 for i in range(3):
  if not activated[i]:return i
 return 3

func target_point() -> Vector3:
 return beacon.position if quest_stage()>=3 else lantern_points[quest_stage()]

func flat_distance(a:Vector3,b:Vector3) -> float:
 return Vector2(a.x-b.x,a.z-b.z).length()

func update_prompt() -> void:
 if game_time<tip_until:
  prompt.text=hint_text;return
 if beacon_awakened:
  prompt.text="Treasure recovered" if language=="en" else "寻宝完成";return
 var stage:=quest_stage()
 if flat_distance(player.position,target_point())<1.55:
  var en:=["E · Read the chart","E · Open the grove chest","E · Recover the tide pearl","E · Place the pearl"]
  var zh:=["E · 阅读海图","E · 打开林间宝箱","E · 取回潮汐珍珠","E · 放入珍珠"]
  prompt.text=en[stage] if language=="en" else zh[stage]
 elif swim.is_swimming():prompt.text="Swim with the same controls · no breath limit" if language=="en" else "方向键游泳 · 可自由停留水面"
 else:prompt.text=""

func progress_data() -> Dictionary:
 return {"quest_stage":quest_stage(),"treasures":[activated[1],activated[2]],"completed":beacon_awakened,"position":[player.position.x,player.position.y,player.position.z],"language":language}

func emit_load_receipt() -> void:
 var data:=progress_data();data["schema"]=1;data["found"]=loaded_found
 print("TIDAL_LOAD ",JSON.stringify(data))

func observed_state() -> Dictionary:
 var data:=progress_data();data["schema"]=1;data["sample_id"]=sample_id;data["physics_frame"]=Engine.get_physics_frames();data["demo"]=demo
 data["locomotion"]=str(swim.state);data["water_depth"]=swim.water_depth
 data["movement_input"]=[last_move.x,last_move.z];data["velocity"]=[player.velocity.x,player.velocity.y,player.velocity.z]
 data["steering_touch_active"]=touch_active;data["steering_touch_index"]=touch_index
 var right:=camera.global_basis.x;right.y=0;right=right.normalized()
 var forward:=-camera.global_basis.z;forward.y=0;forward=forward.normalized()
 data["camera_right"]=[right.x,right.z];data["camera_forward"]=[forward.x,forward.z]
 var rect:=action_button.get_global_rect();data["action_rect"]=[rect.position.x,rect.position.y,rect.size.x,rect.size.y]
 return data

func emit_state() -> void:
 sample_id+=1
 print("TIDAL_STATE ",JSON.stringify(observed_state()))
 if not presentation_pending and DisplayServer.get_name()!="headless" and not OS.has_feature("web"):
  emit_presented_state()

func emit_presented_state() -> void:
 # Passive native capture receipt. Observe two real draws, then bind the state
 # and labels sampled before the second draw to its completed frame. No input,
 # quest progress, camera, timing, or render output is changed by this observer.
 presentation_pending=true
 await RenderingServer.frame_post_draw
 var first_draw_frame:=Engine.get_frames_drawn()
 await RenderingServer.frame_pre_draw
 var data:=observed_state()
 var labels:={"objective":objective.text,"compass":compass.text,"progress":progress.text}
 await RenderingServer.frame_post_draw
 presentation_id+=1
 print("TIDAL_PRESENTED ",JSON.stringify({"schema":1,"presentation_id":presentation_id,"first_draw_frame":first_draw_frame,"draw_frame":Engine.get_frames_drawn(),"post_draw_count":2,"state":data,"labels":labels}))
 presentation_pending=false

func interact() -> void:
 if beacon_awakened:return
 var stage:=quest_stage()
 if flat_distance(player.position,target_point())>=1.55:return
 if stage<3:
  # The map reveals the grove key; the key opens the cache tied to the reef buoy.
  activated[stage]=true
  var en:=["Chart found · search the leaning grove","Brass key found · follow the red buoy","Tide pearl recovered · return ashore"]
  var zh:=["找到海图 · 前往倾斜的树林","找到铜钥匙 · 寻找红色浮标","取回潮汐珍珠 · 返回岸边"]
  hint_text=en[stage] if language=="en" else zh[stage]
  print("TIDAL_TREASURE ",JSON.stringify({"stage":stage+1,"item":["chart","brass_key","tide_pearl"][stage],"demo":demo}))
 else:
  beacon_awakened=true
  restart_available_time=game_time+3.0
  hint_text="Treasure recovered · the sanctuary glows" if language=="en" else "寻宝完成 · 圣所重现光芒"
  print("TIDAL_COMPLETE ",JSON.stringify({"demo":demo,"stage":4}))
 tip_until=game_time+3.0;update_state();save_game()

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
 # Button uses primary-pointer mouse emulation; a second finger must remain a
 # real touch action while finger one continues steering the swimmer.
 if event is InputEventScreenTouch and event.pressed and touch_active and event.index!=touch_index:
  if action_button.get_global_rect().has_point(event.position):
   var before:=quest_stage();on_action_pressed()
   print("TIDAL_ACTION_TOUCH ",JSON.stringify({"schema":1,"touch_index":event.index,"steering_index":touch_index,"before":before,"after":quest_stage(),"demo":demo}))
   get_viewport().set_input_as_handled();return
  if language_button.get_global_rect().has_point(event.position):
   change_language("touch_button");get_viewport().set_input_as_handled();return
 if event is InputEventScreenTouch and not event.pressed and event.index==touch_index:
  touch_active=false;touch_move=Vector2.ZERO;touch_index=-1
  print("TIDAL_TOUCH_RELEASE ",JSON.stringify({"schema":1,"gesture_id":touch_gesture_id,"touch_index":event.index,"before":[touch_start_position.x,touch_start_position.y,touch_start_position.z],"after":[player.position.x,player.position.y,player.position.z],"physics_frames_elapsed":Engine.get_physics_frames()-touch_start_frame,"drag_events":touch_drag_events,"canceled":event.canceled,"demo":demo,"active_after":touch_active,"move_after":[touch_move.x,touch_move.y]}))
 elif event is InputEventScreenDrag and touch_active and event.index==touch_index:
  touch_move=(event.position-touch_origin).limit_length(70)/70
  touch_drag_events+=1

func _notification(what:int) -> void:
 if what==NOTIFICATION_WM_CLOSE_REQUEST and OS.has_feature("web"):
  save_game("exit");get_tree().quit();return
 if what==NOTIFICATION_APPLICATION_FOCUS_OUT:
  touch_active=false;touch_move=Vector2.ZERO;touch_index=-1

func _physics_process(delta:float) -> void:
 if player==null:return
 game_time+=delta
 action_button.disabled=beacon_awakened and game_time<restart_available_time
 var input:=Vector2.ZERO
 if Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT):input.x-=1
 if Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT):input.x+=1
 if Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP):input.y-=1
 if Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN):input.y+=1
 input=(input+touch_move).limit_length()
 var right:=camera.global_basis.x;right.y=0;right=right.normalized()
 var forward:=-camera.global_basis.z;forward.y=0;forward=forward.normalized()
 var move:Vector3=(right*input.x-forward*input.y).normalized()*input.length()
 if demo:
  move=Vector3.ZERO
  if route_phase<route_points.size():
   var target:=route_points[route_phase]
   var flat:=Vector3(target.x-player.position.x,0,target.z-player.position.z)
   if flat.length()>.65:move=flat.normalized()*.92;demo_wait=0.0
   else:
    demo_wait+=delta
    if demo_wait>.75:
     if route_phase in [0,1,3,6]:interact()
     route_phase+=1;demo_wait=0.0;demo_phase=quest_stage()
 swim.step(player,move,delta,height_at(player.position.x,player.position.z))
 last_move=move
 if move.length()>.1:avatar.rotation.y=lerp_angle(avatar.rotation.y,atan2(-move.x,-move.z),1.0-exp(-delta*10))
 var afloat:=swim.is_swimming()
 avatar_body.rotation.x=lerpf(avatar_body.rotation.x,-PI*.43 if afloat else 0.0,1-exp(-delta*7))
 avatar_body.position.y=lerpf(avatar_body.position.y,.65 if afloat else .6,1-exp(-delta*7))
 avatar.position.y=sin(game_time*(4.4 if afloat else 10))* (.025 if move.length()>.1 else .006)
 for i in range(2):
  var phase:=game_time*(4.2 if afloat else 9.0)+i*PI
  arms[i].rotation.x=sin(phase)*(.9 if afloat else .5)*move.length()
  arms[i].rotation.z=sin(phase)*.38+(-.4 if i==0 else .4) if afloat else 0.0
  legs[i].rotation.x=sin(phase+PI)*(.32 if afloat else .55)*move.length()
 swim_wake.visible=swim.state!=&"walk"
 swim_wake.position=Vector3(player.position.x,SEA_LEVEL+.035,player.position.z)
 swim_wake.rotation.y=avatar.rotation.y;swim_wake.scale=Vector3(1.25+move.length()*.2,1,1.5+move.length()*.5)
 save_time+=delta
 if save_time>3:save_game();save_time=0
 var aim:=player.position+Vector3(0,1.0,-1.2)
 var desired:=player.position+Vector3(-3.4,7.3,10.0)
 var portrait:=get_viewport().get_visible_rect().size.x/get_viewport().get_visible_rect().size.y<.85
 if portrait:desired=player.position+Vector3(-2.0,9.3,12.5)
 var ray:=PhysicsRayQueryParameters3D.create(aim,desired);ray.exclude=[player.get_rid()]
 var hit:=get_world_3d().direct_space_state.intersect_ray(ray)
 if not hit.is_empty():desired=hit.position+hit.normal*.55
 camera.position=camera.position.lerp(desired,1-exp(-delta*4.5));camera.look_at(aim)
 update_prompt()
 var dist:=flat_distance(player.position,target_point())
 var dir:=Vector3(target_point().x-player.position.x,0,target_point().z-player.position.z).normalized()
 var side:=right.dot(dir);var front:=forward.dot(dir)
 var arrow:="↑" if front>.45 else ("↓" if front<-.45 else ("→" if side>0 else "←"))
 compass.text=("%s  %dm  ·  %s" % [arrow,int(dist),str(swim.state).to_upper()]) if language=="en" else ("%s  %d米  ·  %s" % [arrow,int(dist),{"walk":"行走","wade":"涉水","swim":"游泳"}[str(swim.state)]])
 state_clock+=delta
 if state_clock>=.2:state_clock=0;emit_state()

func _process(delta:float) -> void:
 timer+=delta
 if objective:
  var view_size:=get_viewport().get_visible_rect().size;var width:=view_size.x;var height:=view_size.y
  var narrow:=width<600
  title_panel.size.x=minf(350,width-32);title_panel.size.y=120
  language_button.position=Vector2(width-60,20)
  title.position=Vector2(28,25);objective.position=Vector2(28,49);progress.position=Vector2(28,78);subtitle.position=Vector2(28,103)
  objective.add_theme_font_size_override("font_size",16 if narrow else 18)
  subtitle.add_theme_font_size_override("font_size",11 if narrow else 12)
  compass.position=Vector2(width*.5-120,150 if narrow else 22);compass.size=Vector2(240,28)
  prompt_panel.size=Vector2(minf(440,width-32),38);prompt_panel.position=Vector2((width-prompt_panel.size.x)*.5,height-130)
  prompt.position=prompt_panel.position+Vector2(8,6);prompt.size=prompt_panel.size-Vector2(16,8);prompt_panel.visible=not prompt.text.is_empty()
  prompt.add_theme_font_size_override("font_size",12 if narrow else 16)
  action_button.position=Vector2(width-152,height-82)
  footer_panel.position=Vector2(16,height-29);footer_panel.size=Vector2(minf(480,width-32),25)
  message.position=Vector2(26,height-25);message.add_theme_font_size_override("font_size",10 if narrow else 12)
  message.text=("Left drag · Move / Swim   Right button · Interact" if language=="en" else "左侧拖动行走或游泳 · 右侧按钮互动") if narrow else ("WASD / arrows · Move & swim     E · Interact     R · Restart     L · Language" if language=="en" else "方向键行走或游泳 · E 互动 · R 重来 · L 语言")
 for i in range(lanterns.size()):
  var gem:MeshInstance3D=lanterns[i].get_node("Gem");gem.position.y=1.0+sin(timer*1.7+i)*.06;gem.rotation.y=timer*.45
 if lanterns.size()>2:lanterns[2].position.y=SEA_LEVEL-.12+sin(timer*1.4)*.035
 for i in range(birds.size()):
  var a:=timer*.11+i*1.2;birds[i].position=Vector3(cos(a)*16,9+sin(a*1.7+i),-6+sin(a)*12);birds[i].rotation.y=-a
 if capture:
  var index:=0
  if timer>1.0 and not demo_captures.has(1):index=1
  elif quest_stage()>=2 and not demo_captures.has(2):index=2
  elif swim.state==&"wade" and not demo_captures.has(3):index=3
  elif swim.is_swimming() and not demo_captures.has(4):index=4
  elif beacon_awakened and not demo_captures.has(5):index=5
  if index>0:demo_captures[index]=true;capture_frame.call_deferred(index)
 # Capture processes remain alive for the recorder; CI performs deliberate shutdown.

func capture_frame(index:int) -> void:
 await RenderingServer.frame_post_draw
 var image:=get_viewport().get_texture().get_image()
 var output:=OS.get_environment("TIDAL_CAPTURE_DIR")
 if output.is_empty():output="user://"
 var path:=output.path_join("tidal-%02d.png"%index)
 print("TIDAL_CAPTURE ",path," ",image.save_png(path))

func save_game(reason:String="auto") -> void:
 if capture or demo:return
 var data:=progress_data();data["schema"]=2;data["activated"]=activated;data["player"]=data["position"];data["beacon_awakened"]=beacon_awakened
 var file:=FileAccess.open(SAVE_PATH,FileAccess.WRITE)
 if file:
  file.store_string(JSON.stringify(data));file.flush()
  var saved_ok:=file.get_error()==OK
  file.close()
  if saved_ok:
   var receipt:=progress_data();receipt["schema"]=1;receipt["persistent"]=OS.is_userfs_persistent();receipt["reason"]=reason;print("TIDAL_SAVE ",JSON.stringify(receipt))

func save_flag(value: Variant) -> bool:
 if value is bool:return value
 if value is int or value is float:return is_finite(float(value)) and value != 0
 return false

func load_game() -> void:
 if demo or not FileAccess.file_exists(SAVE_PATH):return
 var parser:=JSON.new()
 if parser.parse(FileAccess.get_file_as_string(SAVE_PATH))!=OK:return
 var data=parser.data
 if not data is Dictionary or data.get("schema")!=2:return
 var a=data.get("activated",[])
 if a is Array and a.size()==3:
  var chart:=save_flag(a[0]);var key:=save_flag(a[1]) and chart;var pearl:=save_flag(a[2]) and key
  activated=[chart,key,pearl]
 var p=data.get("player",[])
 if p is Array and p.size()==3 and p.all(func(value:Variant)->bool:return value is int or value is float):
  var saved:=Vector3(float(p[0]),float(p[1]),float(p[2]))
  var ground:=height_at(saved.x,saved.z) if saved.is_finite() else NAN
  player.position=swim.restored_position(saved,ground,swim.safe_spawn_position)
 language="zh" if data.get("language","en")=="zh" else "en"
 beacon_awakened=save_flag(data.get("beacon_awakened",false)) and activated==[true,true,true]
 loaded_found=true

func reset_game() -> void:
 activated=[false,false,false];completed=false;beacon_awakened=false;tip_until=0.0;restart_available_time=0.0
 player.position=swim.safe_spawn_position;player.velocity=Vector3.ZERO;swim=SwimController.new();swim.safe_spawn_position=player.position
 update_state();save_game()

func count_nodes(node:Node) -> int:
 var count:=1
 for child in node.get_children():count+=count_nodes(child)
 return count

func scene_stats(node:Node,stats:Dictionary) -> void:
 if node is MeshInstance3D and node.mesh:
  stats["mesh_instances"]+=1
  for surface in range(node.mesh.get_surface_count()):
   var arrays:Array=node.mesh.surface_get_arrays(surface)
   var indices=arrays[Mesh.ARRAY_INDEX]
   stats["triangles"]+=indices.size()/3 if indices!=null and indices.size()>0 else arrays[Mesh.ARRAY_VERTEX].size()/3
 for child in node.get_children():scene_stats(child,stats)

func audit() -> void:
 await get_tree().process_frame
 await get_tree().physics_frame
 var stats:={"mesh_instances":0,"triangles":0};scene_stats(self,stats)
 stats.merge({"scene_nodes":count_nodes(self),"terrain_surfaces":terrain_mesh.mesh.get_surface_count(),"lanterns":lanterns.size(),"camera_fov":camera.fov,"camera_distance":camera.position.distance_to(player.position),"renderer":RenderingServer.get_current_rendering_method(),"save_exists":FileAccess.file_exists(SAVE_PATH),"active":activated})
 print("TIDAL_AUDIT ",JSON.stringify(stats))
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
 if beacon_awakened:
  if game_time>=restart_available_time:reset_game()
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
