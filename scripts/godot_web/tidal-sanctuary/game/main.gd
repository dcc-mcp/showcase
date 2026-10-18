extends Node3D

const SAVE_PATH = "user://tidal-sanctuary-v2.json"
const SwimController = preload("res://swim_controller.gd")
const TideInterface = preload("res://tide_interface.gd")
const TideAudio = preload("res://tide_audio.gd")
const SEA_LEVEL := -0.15
const WORLD_LAYER := 1
const PLAYER_LAYER := 2
const INTERACTION_RADIUS := 1.55
const INTERACTION_HEIGHT := 1.2
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
var explorer_animation:AnimationPlayer
var explorer_clip:StringName=&""
var swim_wake:MeshInstance3D
var compass:Label
var state_clock:=0.0
var sample_id:=0
var hint_text:=""
var chest_lids:Array[Node3D]=[]
var route_points:Array[Vector3]=[]
var route_phase:=0
var demo_captures:Dictionary={}
var loaded_found:=false
var last_move:=Vector3.ZERO
var story:Dictionary={}
var interface:CanvasLayer
var tide_audio:Node
var journey_started:=false
var audio_muted:=false
var restart_pending:=false


func mat(c: Color, roughness: float = .9) -> StandardMaterial3D:
 var m := StandardMaterial3D.new()
 m.albedo_color = c
 m.roughness = roughness
 return m

func _ready() -> void:
 var story_data=JSON.parse_string(FileAccess.get_file_as_string("res://assets/story/story.en-zh.json"))
 assert(story_data is Dictionary and story_data.get("schema")==1,"Story source failed to load")
 story=story_data
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
 tide_audio=TideAudio.new();add_child(tide_audio)
 make_ui()
 if OS.has_feature("web"):get_tree().auto_accept_quit=false
 load_game()
 if demo:
  activated=[false,false,false]
  beacon_awakened=false
  player.position=Vector3(1.3,height_at(1.3,10.0)+.08,10)
 route_points=[lantern_points[0],lantern_points[1],Vector3(1.5,0,6.2),lantern_points[2],Vector3(7,0,.5),Vector3(2,0,-3),Vector3(0,beacon.position.y,-10.25)]
 journey_started=demo
 update_state()
 if not demo:show_opening()
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
 sea.set_meta("collision_intent","query-only");sea.set_meta("collision_reason","Depth controller detects water; surface never blocks swimming")

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
 var c:=Color("6c855f").lerp(Color("8b9d74"),smoothstep(.25,.77,patch))
 var sand:=Color("c9bd97").lerp(Color("b5b38d"),patch*.32)
 var grove:=maxf(exp(-pow((p.x+6.0)/3.5,2.0)-pow((p.z-4.5)/5.0,2.0)),exp(-pow((p.x-7.0)/2.7,2.0)-pow((p.z+3.0)/4.0,2.0)))
 c=c.lerp(sand,1.0-smoothstep(.40,1.5,p.y))
 c=c.lerp(Color("617c58"),grove*.22)
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
 m.albedo_texture=surface_noise(Color("efefdf"),Color("ffffff"),.14)
 m.uv1_triplanar=true;m.uv1_world_triplanar=true;m.uv1_scale=Vector3.ONE*.7
 terrain_mesh.material_override=m;add_child(terrain_mesh);terrain_mesh.create_trimesh_collision()
 terrain_mesh.set_meta("collision_intent","solid");terrain_mesh.set_meta("collision_reason","Walkable island and seabed, matching visual triangles")
 for child in terrain_mesh.get_children():
  if child is StaticBody3D:child.collision_layer=WORLD_LAYER;child.collision_mask=PLAYER_LAYER

func terrain_triangle(st:SurfaceTool,a:Vector3,b:Vector3,c:Vector3) -> void:
 for p in [a,b,c]:
  var dx:=height_at(p.x+.12,p.z)-height_at(p.x-.12,p.z)
  var dz:=height_at(p.x,p.z+.12)-height_at(p.x,p.z-.12)
  st.set_normal(Vector3(-dx,.24,-dz).normalized());st.set_color(terrain_color(p));st.add_vertex(p)

func mesh_node(mesh: Mesh, p: Vector3, m: Material, parent: Node = self) -> MeshInstance3D:
 var n:=MeshInstance3D.new()
 n.mesh=mesh;n.position=p;n.material_override=m;parent.add_child(n)
 n.set_meta("collision_intent","none");n.set_meta("collision_reason","Small decoration or nonblocking visual; solid call sites opt in explicitly")
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
   var boulder:=place_asset(path,Vector3(x,height_at(x,z)-.20,z),Vector3(size,size*rng.randf_range(.7,1.3),size*.9),rng.randf()*TAU)
   solid_asset(boulder,"Large shoreline rock blocks walkers and swimmers")
 for i in range(4):
  var x:float=12.6+i*.75;var z:float=5.2-i*.65
  var boulder:=place_asset("res://assets/shore-rock-d.tscn",Vector3(x,-1.35,z),Vector3(2.3-i*.22,2.5-i*.3,2.2),i*.82)
  solid_asset(boulder,"Exposed reef rock blocks swimmers")

func place_asset(path:String,p:Vector3,sz:Vector3,yaw:float) -> Node3D:
 var node:Node3D=load(path).instantiate()
 node.position=p;node.scale=sz;node.rotation.y=yaw;add_child(node)
 mark_soft_asset(node)
 return node

func solid_mesh(mesh:MeshInstance3D,reason:String,target_stage:int=-1,trunk_only:bool=false,exact_faces:bool=false) -> StaticBody3D:
 # Bake the visible world-space basis into the shape. Nonuniform imported scales
 # must not scale a PhysicsBody, and fronds must never become invisible walls.
 var points:=PackedVector3Array()
 var faces:=PackedVector3Array()
 for surface in range(mesh.mesh.get_surface_count()):
  var material:=mesh.mesh.surface_get_material(surface)
  if trunk_only and (material==null or not material.resource_name.begins_with("Trunk ")):continue
  var arrays:=mesh.mesh.surface_get_arrays(surface)
  var vertices:PackedVector3Array=arrays[Mesh.ARRAY_VERTEX]
  for vertex in vertices:points.append(mesh.global_basis*vertex)
  var indices=arrays[Mesh.ARRAY_INDEX]
  if indices!=null and indices.size()>0:
   for index in indices:faces.append(mesh.global_basis*vertices[index])
  else:
   for vertex in vertices:faces.append(mesh.global_basis*vertex)
 if points.size()<4:return null
 var body:=StaticBody3D.new();body.name="Solid_"+str(mesh.get_instance_id())
 body.collision_layer=WORLD_LAYER;body.collision_mask=PLAYER_LAYER
 body.set_meta("collision_intent","solid");body.set_meta("collision_reason",reason)
 body.set_meta("interaction_target",target_stage)
 add_child(body);body.global_position=mesh.global_position
 var collider:=CollisionShape3D.new()
 if exact_faces:
  var shape:=ConcavePolygonShape3D.new();shape.set_faces(faces);collider.shape=shape
 else:
  var shape:=ConvexPolygonShape3D.new();shape.points=points;collider.shape=shape
 body.add_child(collider)
 mesh.set_meta("collision_intent","solid");mesh.set_meta("collision_reason",reason)
 mesh.set_meta("solid_body",body.get_path())
 return body

func solid_asset(node:Node,reason:String,trunk_only:bool=false) -> void:
 if node is MeshInstance3D and node.mesh:solid_mesh(node,reason,-1,trunk_only,true)
 for child in node.get_children():solid_asset(child,reason,trunk_only)

func mark_soft_asset(node:Node) -> void:
 node.set_meta("collision_intent","none")
 node.set_meta("collision_reason","Soft leaves or low decorative pebble; no movement barrier")
 for child in node.get_children():mark_soft_asset(child)

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
 for tint in [Color("b1b5a7"),Color("a1aca1"),Color("babba9"),Color("a6b1a5")]:
  var material:=mat(tint)
  material.albedo_texture=surface_noise(Color("e0e3d6"),Color("fffbed"),.28)
  material.normal_enabled=true;material.normal_texture=normal;material.normal_scale=.07
  material.roughness_texture=rough
  material.uv1_triplanar=true;material.uv1_world_triplanar=true;material.uv1_scale=Vector3.ONE*.58
  material.texture_filter=BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
  stone_materials.append(material)

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

func terrain_surface_height(x:float,z:float) -> float:
 # Interpolate the exact triangles used by make_terrain, not the analytic
 # height function between its samples. Paving is a thin surface treatment.
 var step:=.48
 var x0:=floorf((x+24.0)/step)*step-24.0
 var z0:=floorf((z+24.0)/step)*step-24.0
 var u:=(x-x0)/step;var v:=(z-z0)/step
 var a:=height_at(x0,z0);var b:=height_at(x0+step,z0)
 var c:=height_at(x0,z0+step);var d:=height_at(x0+step,z0+step)
 if u+v<=1.0:return a+(b-a)*u+(c-a)*v
 return d+(c-d)*(1.0-u)+(b-d)*(1.0-v)

func conform_paving(mesh:MeshInstance3D) -> void:
 # Subdivide before projection: projecting just four corners bridges the
 # terrain inside a broad stone. The existing terrain remains the sole support.
 var surface:=SurfaceTool.new();surface.begin(Mesh.PRIMITIVE_TRIANGLES)
 var faces:=mesh.mesh.get_faces()
 var center_floor:=height_at(mesh.global_position.x,mesh.global_position.z)
 for i in range(0,faces.size(),3):
  paving_triangle(surface,faces[i],faces[i+1],faces[i+2],mesh.global_transform,center_floor,0)
 surface.generate_normals();mesh.mesh=surface.commit()
 mesh.set_meta("collision_intent","none")
 mesh.set_meta("collision_reason","Buried paving surface follows the existing solid terrain; no raised barrier")
 mesh.set_meta("support_body",terrain_mesh.get_child(0).get_path())

func paving_triangle(surface:SurfaceTool,a:Vector3,b:Vector3,c:Vector3,placement:Transform3D,center_floor:float,depth:int) -> void:
 var ab:=Vector2(a.x-b.x,a.z-b.z).length()
 var bc:=Vector2(b.x-c.x,b.z-c.z).length()
 var ca:=Vector2(c.x-a.x,c.z-a.z).length()
 if maxf(ab,maxf(bc,ca))>.24 and depth<8:
  if ab>=bc and ab>=ca:
   var middle:=(a+b)*.5
   paving_triangle(surface,a,middle,c,placement,center_floor,depth+1)
   paving_triangle(surface,middle,b,c,placement,center_floor,depth+1)
  elif bc>=ca:
   var middle:=(b+c)*.5
   paving_triangle(surface,a,b,middle,placement,center_floor,depth+1)
   paving_triangle(surface,a,middle,c,placement,center_floor,depth+1)
  else:
   var middle:=(c+a)*.5
   paving_triangle(surface,a,b,middle,placement,center_floor,depth+1)
   paving_triangle(surface,middle,b,c,placement,center_floor,depth+1)
  return
 for local:Vector3 in [a,b,c]:
  var world:=placement*local
  world.y=terrain_surface_height(world.x,world.z)+(placement.origin.y-center_floor)+local.y
  surface.set_color(Color.WHITE);surface.add_vertex(placement.affine_inverse()*world)

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
   var slab:=beveled_block(Vector3(x,height_at(x,z)-.052,z),Vector3(rng.randf_range(.58,1.05),.12,rng.randf_range(.43,.7)),stone_materials[i%4],1000+i+int(group_z*10),.32)
   slab.rotation=Vector3(rng.randf_range(-.06,.06),rng.randf_range(-.6,.6),rng.randf_range(-.04,.04))
   conform_paving(slab)
 # Broad, uneven threshold steps follow the existing walkable terrain.
 for row in range(4):
  var z:float=-4.2-row*.63
  var x:=path_x(z)*.5
  for side in [-1,1]:
   var px:float=x+side*.75+rng.randf_range(-.08,.08)
   var slab:=beveled_block(Vector3(px,height_at(px,z)-.042,z),Vector3(1.5,.10,rng.randf_range(.60,.76)),stone_materials[row%4],1210+row*3+side,.38)
   slab.rotation.y=rng.randf_range(-.09,.09)
   conform_paving(slab)
   slab.set_meta("threshold_step",true)
 var h:=height_at(0,-8.0)
 for row in range(4):
  for col in range(5):
   if (row==0 and col==0) or (row==2 and col==4) or (row==3 and col==0):continue
   var x:float=-2.65+col*1.32+rng.randf_range(-.10,.10)
   var z:float=-6.5-row*1.30+rng.randf_range(-.11,.11)
   var tile:=beveled_block(Vector3(x,height_at(x,z)-.102+rng.randf_range(-.003,.003),z),Vector3(rng.randf_range(1.12,1.28),.22,rng.randf_range(1.11,1.3)),stone_materials[(row+col)%4],1500+row*5+col,.40)
   tile.rotation.y=rng.randf_range(-.05,.05)
   conform_paving(tile)
 # Four survivors, different heights and broken caps, replace the clean colonnade.
 for info in [Vector3(-3.8,1.0,-5.9),Vector3(-3.65,3.5,-9.3),Vector3(3.7,.75,-6.2),Vector3(3.8,2.55,-10.1)]:
  var base:=height_at(info.x,info.z)
  var material:=stone_materials[rng.randi_range(0,3)]
  var foot:=beveled_block(Vector3(info.x,base+.13,info.z),Vector3(1.0,.30,1.0),material,rng.randi(),.3)
  foot.rotation.y=.12
  solid_mesh(foot,"Column footing blocks and supports the player")
  var column:=cylinder(Vector3(info.x,base+info.y*.5+.23,info.z),.37,info.y,material,self,.32)
  solid_mesh(column,"Stone column blocks the player")
  var cap:=beveled_block(Vector3(info.x,base+info.y+.23,info.z),Vector3(.82,.22,.75),material,rng.randi(),.34)
  cap.rotation=Vector3(.045,-.09,.07)
  solid_mesh(cap,"Broken column cap is physical stone")
 # Worn arch stones: narrow dark joints and chipped edges, no smooth white facade.
 var center:=Vector3(0,h+2.68,-10.0)
 for side in [-1,1]:
  for layer in range(5):
   var n:=beveled_block(Vector3(side*1.65,h+.25+layer*.49,-10),Vector3(.66,.48,.92),stone_materials[(layer+2)%4],2000+layer*3+side,.24)
   n.rotation.y=rng.randf_range(-.035,.035)
   solid_mesh(n,"Ruin arch pier blocks the player")
 for i in range(11):
  var a:=float(i)/10.0*PI
  var n:=beveled_block(center+Vector3(cos(a)*1.65,sin(a)*1.65,0),Vector3(.62,.69,.94),stone_materials[i%4],2100+i,.20)
  n.rotation.z=a-PI/2
  solid_mesh(n,"Overhead arch stone blocks camera and tall probes")
 # Broken return wall, tapering irregularly toward the entrance.
 for row in range(4):
  for column in range(5-row):
   var z:float=-8.65+column*.87
   var x:float=-4.25+rng.randf_range(-.045,.045)
   var wall:=beveled_block(Vector3(x,height_at(x,z)+.24+row*.43,z),Vector3(.67,.44,.87),stone_materials[(row+column)%4],2300+row*8+column,.29)
   wall.rotation.y=rng.randf_range(-.04,.04)
   solid_mesh(wall,"Broken return wall blocks movement and interaction sight")
 for i in range(19):
  var x:=rng.randf_range(-5.1,5.2);var z:=rng.randf_range(-11.5,-4.1)
  if abs(x)<2.6:continue
  var slab:=beveled_block(Vector3(x,height_at(x,z)+.08,z),Vector3(rng.randf_range(.20,.65),rng.randf_range(.12,.3),rng.randf_range(.24,.61)),stone_materials[i%4],2500+i,.55)
  slab.rotation=Vector3(rng.randf_range(-.25,.25),rng.randf()*TAU,rng.randf_range(-.2,.2))

func make_sanctuary_details() -> void:
 # Stylized broad-leaf pockets soften broken walls without blocking the walk line.
 for center in [Vector3(-3.0,0,-4.6),Vector3(-4.9,0,-6.0),Vector3(-4.5,0,-9.5),Vector3(3.5,0,-5.1),Vector3(4.9,0,-8.4),Vector3(2.7,0,-11.6)]:
  for i in range(4):
   var x:float=center.x+rng.randf_range(-.65,.65);var z:float=center.z+rng.randf_range(-.45,.45)
   var variant:="a" if i%2==0 else "b"
   place_asset("res://assets/tropical/understory-%s.glb"%variant,Vector3(x,height_at(x,z)-.01,z),Vector3.ONE*rng.randf_range(.62,1.05),rng.randf()*TAU)
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
 # Hand-authored leaning palms frame the cache and cove; the chart route stays open.
 var palm_index:=0
 for info in [Vector3(-7.4,.86,5.9),Vector3(-8.6,.76,4.2),Vector3(-7.1,.62,7.3),Vector3(-7.3,1.0,-3.0),Vector3(-8.9,.75,-5),Vector3(7.7,.91,-2.2),Vector3(9.3,.73,-3.8)]:
  var variant:="a" if palm_index%2==0 else "b"
  var palm:=place_asset("res://assets/tropical/palm-%s.glb"%variant,Vector3(info.x,height_at(info.x,info.z)-.04,info.z),Vector3.ONE*info.y,rng.randf()*TAU)
  solid_asset(palm,"Palm trunk blocks movement; leaves remain nonblocking",true)
  palm_index+=1
 for center in [Vector3(-5.6,0,4.5),Vector3(-6.9,0,6.2),Vector3(-7.7,0,-2.7),Vector3(6.5,0,-2.0),Vector3(7.8,0,-4),Vector3(-5.4,0,1.7)]:
  for i in range(6):
   var x:float=center.x+rng.randf_range(-1.0,1.0);var z:float=center.z+rng.randf_range(-.9,.9)
   if height_at(x,z)<.5:continue
   var kind:="understory-a" if i%3!=0 else "bush-a"
   var size:=rng.randf_range(.8,1.25)
   place_asset("res://assets/tropical/%s.glb"%kind,Vector3(x,height_at(x,z)-.03,z),Vector3(size,size*.85,size),rng.randf()*TAU)
 for center in [Vector3(-5.4,0,7.7),Vector3(-8,0,1.8),Vector3(6.2,0,-1.3),Vector3(-5.9,0,-5.5)]:
  for i in range(4):
   var x:float=center.x+rng.randf_range(-.9,.9);var z:float=center.z+rng.randf_range(-.7,.7)
   var size:=rng.randf_range(.30,.65)
   var variant:="a" if i%2==0 else "b"
   place_asset("res://assets/tropical/shore-stone-%s.glb"%variant,Vector3(x,height_at(x,z)-.08,z),Vector3(size,size*.65,size),rng.randf()*TAU)

func make_player() -> void:
 player=CharacterBody3D.new();player.name="Wayfarer";add_child(player)
 player.collision_layer=PLAYER_LAYER;player.collision_mask=WORLD_LAYER
 player.position=Vector3(1.3,height_at(1.3,10)+.08,10)
 var col:=CollisionShape3D.new();var shape:=CapsuleShape3D.new();shape.radius=.22;shape.height=.95;col.shape=shape;col.position.y=.48;player.add_child(col)
 avatar=Node3D.new();player.add_child(avatar)
 avatar_body=Node3D.new();avatar_body.position.y=.6;avatar.add_child(avatar_body)
 var explorer:Node3D=load("res://assets/tropical/explorer.glb").instantiate()
 explorer.position.y=-.6;avatar_body.add_child(explorer)
 explorer_animation=explorer.find_child("AnimationPlayer",true,false) as AnimationPlayer
 assert(explorer_animation!=null,"Explorer animation player is required")
 for clip in ["Idle","Walk","Swim"]:
  assert(explorer_animation.has_animation(clip),"Missing explorer clip: "+clip)
  explorer_animation.get_animation(clip).loop_mode=Animation.LOOP_LINEAR
 explorer_animation.play("Idle");explorer_clip=&"Idle"
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
   var pedestal:=beveled_block(p+Vector3(0,.35,0),Vector3(.85,.7,.7),stone_materials[0],5100,.4)
   solid_mesh(pedestal,"Chart pedestal is solid; chart is query-only",0)
   box(Vector3(0,.73,0),Vector3(.64,.035,.47),mat(Color("e4d9b1")),root)
   for j in range(3):box(Vector3(-.2+j*.18,.756,0),Vector3(.055,.007,.30-j*.055),mat(Color("817b61")),root)
  else:
   var wood:=mat(Color("735b42"));var band:=mat(Color("bca36d"),.55)
   if i==2:
    cylinder(Vector3(0,.16,0),.42,.22,mat(Color("bd7150")),root)
    cylinder(Vector3(0,.7,0),.032,.98,band,root)
    var flag:=box(Vector3(.20,1.12,0),Vector3(.4,.26,.025),mat(Color("c95f4f")),root);flag.rotation.z=-.10
   else:
    var chest:=box(Vector3(0,.24,0),Vector3(.82,.45,.55),wood,root)
    solid_mesh(chest,"Grove chest body blocks movement; treasure is query-only",1)
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
 var base:=cylinder(Vector3(0,.17,0),1.15,.34,material_stone,beacon)
 solid_mesh(base,"Beacon stone base blocks movement",3)
 var plinth:=cylinder(Vector3(0,.5,0),.80,.35,material_stone,beacon)
 solid_mesh(plinth,"Beacon plinth is solid",3)
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

func tr_text(value:Dictionary) -> String:
 return str(value.get(language,value.get("en","")))

func make_ui() -> void:
 interface=TideInterface.new();add_child(interface);interface.setup(game_font);ui=interface
 title=interface.title;objective=interface.objective;progress=interface.progress;subtitle=interface.subtitle
 compass=interface.compass;prompt=interface.prompt;message=interface.message
 action_button=interface.action_button;language_button=interface.language_button
 title_panel=interface.title_panel;footer_panel=interface.footer_panel;prompt_panel=interface.prompt_panel
 interface.action_requested.connect(on_action_pressed)
 interface.language_requested.connect(change_language.bind("button"))
 interface.audio_requested.connect(toggle_audio.bind("button"))
 interface.journal_requested.connect(show_journal)
 interface.card_primary_requested.connect(card_primary)
 interface.card_secondary_requested.connect(card_secondary)

func show_opening() -> void:
 var opening:Dictionary=story.opening
 var heading:=tr_text(story.title) if loaded_found else tr_text(opening.title)
 var body:=tr_text(story.ending.clue) if quest_stage()==4 else tr_text(opening.body)
 body+="\n\n"+("WASD / arrows · Move and swim\nE · Interact     J · Journal     M · Sound" if language=="en" else "方向键行走或游泳\nE 互动 · J 手记 · M 声音")
 interface.show_card("opening",heading,body,tr_text(story.ui.continue) if loaded_found else tr_text(opening.button))

func begin_journey(trigger:String) -> void:
 if journey_started:return
 journey_started=true;interface.hide_card()
 tide_audio.start_from_gesture(trigger)
 print("TIDAL_JOURNEY ",JSON.stringify({"schema":1,"started":true,"trigger":trigger,"demo":demo,"stage":quest_stage()}))
 update_state()

func show_journal() -> void:
 if not journey_started:return
 var body:=tr_text(story.opening.body)
 for i in range(mini(quest_stage(),4)):
  var entry:Dictionary=story.stages[i]
  body+="\n\n"+tr_text(entry.story_title)+"\n"+tr_text(entry.story_body)
 interface.show_card("journal",tr_text(story.ui.journal),body,tr_text(story.ui.continue),tr_text(story.ending.secondary))
 touch_move=Vector2.ZERO

func request_restart() -> void:
 if not journey_started:return
 restart_pending=true
 interface.show_card("restart",tr_text(story.ending.secondary),tr_text(story.ui.restart_prompt),tr_text(story.ending.secondary),tr_text(story.ui.cancel))
 print("TIDAL_RESTART_REQUEST ",JSON.stringify({"schema":1,"pending":true,"demo":demo}))

func card_primary() -> void:
 if interface.card_mode=="opening":begin_journey("begin_button")
 elif interface.card_mode=="restart":
  restart_pending=false;interface.hide_card();reset_game()
 else:interface.hide_card()

func card_secondary() -> void:
 if interface.card_mode=="journal":request_restart();return
 restart_pending=false;interface.hide_card()

func toggle_audio(trigger:String) -> void:
 audio_muted=not audio_muted;tide_audio.set_muted(audio_muted,trigger)
 interface.set_status(quest_stage(),language,audio_muted);save_game()

func update_state() -> void:
 completed=activated==[true,true,true]
 for i in range(3):
  lantern_lights[i].light_energy=.35 if activated[i] else 0.0
  var gem:MeshInstance3D=lanterns[i].get_node("Gem");gem.visible=not activated[i] and i>0
 for i in range(chest_lids.size()):chest_lids[i].rotation.x=-1.1 if activated[i+1] else 0.0
 beam.visible=beacon_awakened
 beacon.get_node("RingLight").light_energy=.65 if beacon_awakened else (.2 if completed else 0.0)
 var ring_material:StandardMaterial3D=beacon_ring.material_override
 ring_material.emission_energy_multiplier=.65 if beacon_awakened else (.18 if completed else 0.0)
 var stage:=quest_stage()
 var entry:Dictionary=story.stages[stage] if stage<4 else story.ending
 objective.text=tr_text(entry.objective)
 title.text="TIDAL SANCTUARY" if language=="en" else "潮 汐 圣 所"
 progress.text="%d / 4"%stage
 subtitle.text=tr_text(entry.clue)
 interface.set_status(stage,language,audio_muted)
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

func interaction_status() -> Dictionary:
 var stage:=quest_stage()
 var focus:=mini(stage,3)
 var points:Array[Vector3]=[lantern_points[0],lantern_points[1],lantern_points[2],beacon.position]
 var nearest:=2.8
 for i in range(4):
  var distance:=flat_distance(player.position,points[i])
  if distance<nearest:focus=i;nearest=distance
 var target:Vector3=points[focus]
 var result:={"available":false,"reason":"too_far","target":target,"target_index":focus,"distance":flat_distance(player.position,target)}
 if result.distance>=INTERACTION_RADIUS:return result
 if absf(player.position.y-target.y)>INTERACTION_HEIGHT:result.reason="too_high";return result
 var anchors:=[.65,.35,.55,1.20]
 var ray:=PhysicsRayQueryParameters3D.create(player.position+Vector3(0,.65,0),target+Vector3(0,anchors[focus],0),WORLD_LAYER)
 ray.exclude=[player.get_rid()]
 var hit:=get_world_3d().direct_space_state.intersect_ray(ray)
 if not hit.is_empty() and hit.collider.get_meta("interaction_target",-1)!=focus:
  result.reason="occluded";return result
 if focus<stage:
  result.reason="already_read" if focus==0 else ("complete" if focus==3 else "already_open")
  return result
 if focus>stage:
  result.reason="missing_key" if focus==2 else ("missing_pearl" if focus==3 else "read_chart_first")
  return result
 if not journey_started or not interface.card_mode.is_empty():result.reason="reading";return result
 result.available=true;result.reason="ready"
 return result

func blocked_prompt(reason:String) -> String:
 var keys:={"too_far":"out_of_range","too_high":"too_high","occluded":"blocked","already_read":"already_read","already_open":"already_open","missing_key":"missing_key","missing_pearl":"missing_pearl"}
 if reason=="complete":return tr_text(story.ending.objective)
 if reason=="read_chart_first":return tr_text(story.stages[0].clue)
 return tr_text(story.ui[keys[reason]]) if keys.has(reason) else ""

func update_prompt() -> void:
 var reach:=interaction_status()
 var stage:=quest_stage()
 action_button.disabled=not reach.available and not beacon_awakened
 var verb:=tr_text(story.stages[stage].action) if stage<4 else tr_text(story.ending.primary)
 action_button.text=verb
 if game_time<tip_until:
  prompt.text=hint_text;return
 if reach.distance<2.8:
  prompt.text=("E · "+verb) if reach.available else blocked_prompt(reach.reason)
 elif swim.is_swimming():prompt.text=tr_text(story.ui.swim_hint)
 else:prompt.text=""

func progress_data() -> Dictionary:
 return {"quest_stage":quest_stage(),"treasures":[activated[1],activated[2]],"completed":beacon_awakened,"position":[player.position.x,player.position.y,player.position.z],"language":language,"audio_muted":audio_muted}

func emit_load_receipt() -> void:
 var data:=progress_data();data["schema"]=1;data["found"]=loaded_found
 print("TIDAL_LOAD ",JSON.stringify(data))

func emit_state() -> void:
 sample_id+=1
 var data:=progress_data();data["schema"]=1;data["sample_id"]=sample_id;data["physics_frame"]=Engine.get_physics_frames();data["demo"]=demo
 data["locomotion"]=str(swim.state);data["water_depth"]=swim.water_depth
 data["movement_input"]=[last_move.x,last_move.z];data["velocity"]=[player.velocity.x,player.velocity.y,player.velocity.z]
 var reach:=interaction_status()
 data["interaction_available"]=reach.available;data["interaction_reason"]=reach.reason;data["interaction_target"]=reach.target_index
 data["journey_started"]=journey_started;data["audio_muted"]=audio_muted
 for field in ["begin_rect","audio_rect","journal_rect"]:
  var control:Control=interface.card_primary if field=="begin_rect" else (interface.audio_button if field=="audio_rect" else interface.journal_button)
  var bounds:=control.get_global_rect();data[field]=[bounds.position.x,bounds.position.y,bounds.size.x,bounds.size.y]
 data["steering_touch_active"]=touch_active;data["steering_touch_index"]=touch_index
 var right:=camera.global_basis.x;right.y=0;right=right.normalized()
 var forward:=-camera.global_basis.z;forward.y=0;forward=forward.normalized()
 data["camera_right"]=[right.x,right.z];data["camera_forward"]=[forward.x,forward.z]
 var rect:=action_button.get_global_rect();data["action_rect"]=[rect.position.x,rect.position.y,rect.size.x,rect.size.y]
 print("TIDAL_STATE ",JSON.stringify(data))

func interact() -> void:
 if not journey_started or not interface.card_mode.is_empty():return
 if beacon_awakened:return
 var stage:=quest_stage()
 var reach:=interaction_status()
 if not reach.available:
  hint_text=blocked_prompt(reach.reason);tip_until=game_time+1.8;update_prompt()
  print("TIDAL_INTERACTION_BLOCKED ",JSON.stringify({"stage":stage,"reason":reach.reason,"distance":reach.distance,"demo":demo}))
  return
 if stage<3:
  # The map reveals the grove key; the key opens the cache tied to the reef buoy.
  activated[stage]=true
  hint_text=tr_text(story.stages[stage].receipt)
  print("TIDAL_TREASURE ",JSON.stringify({"stage":stage+1,"item":["chart","brass_key","tide_pearl"][stage],"demo":demo}))
 else:
  beacon_awakened=true
  restart_available_time=game_time+3.0
  hint_text=tr_text(story.stages[3].receipt)
  print("TIDAL_COMPLETE ",JSON.stringify({"demo":demo,"stage":4}))
 tide_audio.play_stage_cue(stage)
 tip_until=game_time+3.0;update_state();save_game()

func _unhandled_input(event: InputEvent) -> void:
 if event is InputEventKey and event.pressed and not event.echo:
  if event.keycode==KEY_E or event.keycode==KEY_SPACE:interact()
  if event.keycode==KEY_R:request_restart()
  if event.keycode==KEY_J:show_journal()
  if event.keycode==KEY_M:toggle_audio("key_M")
  if event.keycode==KEY_L:change_language("key_L")
  if event.keycode==KEY_H:ui_visible=not ui_visible;ui.visible=ui_visible
 if event is InputEventScreenTouch and event.pressed and journey_started and interface.card_mode.is_empty() and not touch_active:
  if event.position.x<get_viewport().get_visible_rect().size.x*.65:
   touch_active=true;touch_origin=event.position;touch_index=event.index
   touch_start_position=player.position;touch_start_frame=Engine.get_physics_frames();touch_drag_events=0;touch_gesture_id+=1

func _input(event:InputEvent) -> void:
 if event is InputEventScreenTouch and not event.pressed and event.index==touch_index:
  touch_active=false;touch_move=Vector2.ZERO;touch_index=-1
  print("TIDAL_TOUCH_RELEASE ",JSON.stringify({"schema":1,"gesture_id":touch_gesture_id,"touch_index":event.index,"before":[touch_start_position.x,touch_start_position.y,touch_start_position.z],"after":[player.position.x,player.position.y,player.position.z],"physics_frames_elapsed":Engine.get_physics_frames()-touch_start_frame,"drag_events":touch_drag_events,"canceled":event.canceled,"demo":demo,"active_after":touch_active,"move_after":[touch_move.x,touch_move.y]}))

  return
 if not journey_started:
  if event is InputEventKey and event.pressed and not event.echo and event.keycode in [KEY_ENTER,KEY_KP_ENTER,KEY_E,KEY_SPACE]:
   begin_journey("key_enter" if event.keycode in [KEY_ENTER,KEY_KP_ENTER] else "key_begin")
   get_viewport().set_input_as_handled();return
  if event is InputEventScreenTouch and event.pressed and interface.card_primary.get_global_rect().has_point(event.position):
   begin_journey("touch_begin");get_viewport().set_input_as_handled();return
  return
 if not interface.card_mode.is_empty():
  if event is InputEventKey and event.pressed and not event.echo:
   if event.keycode in [KEY_ENTER,KEY_KP_ENTER]:card_primary();get_viewport().set_input_as_handled();return
   if event.keycode in [KEY_ESCAPE,KEY_J] or (event.keycode in [KEY_E,KEY_SPACE] and not restart_pending):
    restart_pending=false;interface.hide_card();get_viewport().set_input_as_handled();return
  return
 # Button uses primary-pointer mouse emulation; a second finger must remain a
 # real touch action while finger one continues steering the swimmer.
 if event is InputEventScreenTouch and event.pressed and touch_active and event.index!=touch_index:
  if action_button.get_global_rect().has_point(event.position):
   var before:=quest_stage();on_action_pressed()
   print("TIDAL_ACTION_TOUCH ",JSON.stringify({"schema":1,"touch_index":event.index,"steering_index":touch_index,"before":before,"after":quest_stage(),"demo":demo}))
   get_viewport().set_input_as_handled();return
  if interface.audio_button.get_global_rect().has_point(event.position):
   toggle_audio("touch_button");get_viewport().set_input_as_handled();return
  if interface.journal_button.get_global_rect().has_point(event.position):
   show_journal();get_viewport().set_input_as_handled();return
  if language_button.get_global_rect().has_point(event.position):
   change_language("touch_button");get_viewport().set_input_as_handled();return
 if event is InputEventScreenDrag and touch_active and event.index==touch_index:
  touch_move=(event.position-touch_origin).limit_length(70)/70
  touch_drag_events+=1

func _notification(what:int) -> void:
 if what==NOTIFICATION_WM_CLOSE_REQUEST and OS.has_feature("web"):
  save_game("exit");get_tree().quit();return
 if what==NOTIFICATION_APPLICATION_FOCUS_OUT:
  touch_active=false;touch_move=Vector2.ZERO;touch_index=-1
  if is_instance_valid(tide_audio):tide_audio.set_focus_active(false)
 if what==NOTIFICATION_APPLICATION_FOCUS_IN and is_instance_valid(tide_audio):tide_audio.set_focus_active(true)

func _physics_process(delta:float) -> void:
 if player==null:return
 game_time+=delta
 var input:=Vector2.ZERO
 if Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT):input.x-=1
 if Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT):input.x+=1
 if Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP):input.y-=1
 if Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN):input.y+=1
 input=(input+touch_move).limit_length()
 if not journey_started or not interface.card_mode.is_empty():input=Vector2.ZERO
 var right:=camera.global_basis.x;right.y=0;right=right.normalized()
 var forward:=-camera.global_basis.z;forward.y=0;forward=forward.normalized()
 var move:Vector3=(right*input.x-forward*input.y).normalized()*input.length()
 if demo:
  move=Vector3.ZERO
  if route_phase<route_points.size():
   var target:=route_points[route_phase]
   var flat:=Vector3(target.x-player.position.x,0,target.z-player.position.z)
   if flat.length()>(.22 if route_phase==6 else .65):move=flat.normalized()*.92;demo_wait=0.0
   else:
    demo_wait+=delta
    if demo_wait>.75:
     if route_phase in [0,1,3,6]:interact()
     route_phase+=1;demo_wait=0.0;demo_phase=quest_stage()
 swim.step(player,move,delta,height_at(player.position.x,player.position.z))
 last_move=move
 if move.length()>.1:avatar.rotation.y=lerp_angle(avatar.rotation.y,atan2(-move.x,-move.z),1.0-exp(-delta*10))
 var afloat:=swim.is_swimming()
 avatar_body.rotation.x=lerpf(avatar_body.rotation.x,-PI*.5 if afloat else 0.0,1-exp(-delta*7))
 avatar_body.position.y=lerpf(avatar_body.position.y,.70 if afloat else .6,1-exp(-delta*7))
 avatar.position.y=sin(game_time*(4.4 if afloat else 10))* (.018 if move.length()>.1 else .006)
 var desired_clip:StringName=&"Swim" if afloat else (&"Walk" if move.length()>.1 else &"Idle")
 if desired_clip!=explorer_clip:
  explorer_animation.play(desired_clip,.22);explorer_clip=desired_clip
 explorer_animation.speed_scale=(.60+.40*move.length()) if afloat else (1.15 if swim.state==&"walk" else .8)
 swim_wake.visible=swim.state!=&"walk"
 swim_wake.position=Vector3(player.position.x,SEA_LEVEL+.035,player.position.z)
 swim_wake.rotation.y=avatar.rotation.y;swim_wake.scale=Vector3(1.25+move.length()*.2,1,1.5+move.length()*.5)
 save_time+=delta
 if save_time>3:save_game();save_time=0
 var aim:=player.position+Vector3(0,1.0,-1.2)
 var desired:=player.position+Vector3(-3.4,7.3,10.0)
 var portrait:=get_viewport().get_visible_rect().size.x/get_viewport().get_visible_rect().size.y<.85
 if portrait:desired=player.position+Vector3(-2.0,9.3,12.5)
 var camera_pivot:=player.position+Vector3(0,.85,0)
 var ray:=PhysicsRayQueryParameters3D.create(camera_pivot,desired,WORLD_LAYER);ray.exclude=[player.get_rid()]
 var hit:=get_world_3d().direct_space_state.intersect_ray(ray)
 if not hit.is_empty():desired=hit.position+hit.normal*.55
 var smoothed:=camera.position.lerp(desired,1-exp(-delta*4.5))
 ray.to=smoothed;hit=get_world_3d().direct_space_state.intersect_ray(ray)
 camera.position=hit.position+hit.normal*.55 if not hit.is_empty() else smoothed
 camera.look_at(aim)
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
  interface.layout()
  var narrow:=get_viewport().get_visible_rect().size.x<600
  message.text=("Left drag · Move / swim" if language=="en" else "左侧拖动 · 行走或游泳") if narrow else ("WASD · Move / swim     E · Act     J · Journal     M · Sound" if language=="en" else "方向键行走或游泳 · E 互动 · J 手记 · M 声音")
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

func load_game() -> void:
 if demo or not FileAccess.file_exists(SAVE_PATH):return
 var parser:=JSON.new()
 if parser.parse(FileAccess.get_file_as_string(SAVE_PATH))!=OK:return
 var data=parser.data
 if not data is Dictionary or data.get("schema")!=2:return
 var a=data.get("activated",[])
 if a is Array and a.size()==3:
  activated=[bool(a[0]),bool(a[1]) and bool(a[0]),bool(a[2]) and bool(a[1]) and bool(a[0])]
 var p=data.get("player",[])
 if p is Array and p.size()==3:
  var saved:=Vector3(float(p[0]),float(p[1]),float(p[2]))
  var ground:=height_at(saved.x,saved.z) if saved.is_finite() else NAN
  player.position=swim.restored_position(saved,ground,swim.safe_spawn_position)
 language="zh" if data.get("language","en")=="zh" else "en"
 audio_muted=data.get("audio_muted",false)==true;tide_audio.set_muted(audio_muted,"load")
 beacon_awakened=bool(data.get("beacon_awakened",false)) and activated==[true,true,true]
 loaded_found=true

func reset_game() -> void:
 restart_pending=false;interface.hide_card();tide_audio.reset_cues()
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
 if beacon_awakened:interface.hide_card()
 else:interact()

func change_language(trigger:String) -> void:
 var previous:=language
 language="zh" if language=="en" else "en";hint_text="";tip_until=0.0;update_state();save_game()
 if interface.card_mode=="opening":show_opening()
 elif interface.card_mode=="journal":show_journal()
 elif interface.card_mode=="restart":request_restart()
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
