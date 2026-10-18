"""Original Dawnkeep art recipe. Blender 4.3.2 native Python, no MCP claim.
Run: blender -b -t 2 --python art/build_dawnkeep.py -- --render
World convention in recipe: x right, y depth (Godot -z), z up. All gameplay
coordinates are converted by pos(), so road routes match the simulation.
"""
import bpy, math, random, os, sys, json, hashlib
from mathutils import Vector
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'game/assets/original'
random.seed(18026)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for x in list(bpy.data.materials): bpy.data.materials.remove(x)
M={}
def mat(name,hex,metal=0,emit=0):
    c=tuple(((int(hex[i:i+2],16)/255+.055)/1.055)**2.4 for i in (0,2,4))
    m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=.84;p.inputs['Metallic'].default_value=metal
    if emit: p.inputs['Emission Color'].default_value=(*c,1);p.inputs['Emission Strength'].default_value=emit
    M[name]=m;return m
for name,c in [('grass','214d47'),('grass_sun','2d6251'),('grass_dark','193e3e'),('moss','547b55'),('cliff','223642'),('cliff_light','355460'),('cliff_dark','142630'),('cliff_edge','537572'),('sand','9c9871'),('sand_light','bbb588'),('sand_dark','737c63'),('stone','b3c1b5'),('stone_light','d6d9bd'),('stone_dark','718d8b'),('gold','e1ab50'),('gold_dark','9b6537'),('wood','694c3d'),('blue','294c6a'),('red','ba5435'),('ivory','f1e3ae')]:mat(name,c)
mat('crystal','66ece0',.1,.65);mat('rune','a6fff1',0,1.4);mat('ember','ffab47',0,1.1);mat('amethyst','bd99ed',0,.5)
def pos(x,z,y=0):return (x,-z,y)
def mesh(name,verts,faces,materials,indices=None):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o)
    for m in materials:me.materials.append(M[m])
    if indices:
        for f,i in zip(me.polygons,indices):f.material_index=i
    return o

def ringmesh(name,center,rings,n=8,mats=['stone'],phase=math.pi/8):
    # Each ring: (height, x radius, y radius, phase offset); flexible bevel profile.
    x,y,z=(0,0,0);v=[]
    for h,rx,ry,ph in rings:
        v += [(x+rx*math.cos(i*2*math.pi/n+phase+ph),y+ry*math.sin(i*2*math.pi/n+phase+ph),z+h) for i in range(n)]
    f=[tuple(range(n-1,-1,-1))];idx=[min(1,len(mats)-1)]
    for j in range(len(rings)-1):
        for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i));idx.append((j+i%2)%len(mats))
    f.append(tuple(range((len(rings)-1)*n,len(rings)*n)));idx.append(0)
    o=mesh(name,v,f,mats,idx);o.location=center;return o
def beam(name,a,b,width,depth,material):
    # Beveled rectangular beam, authored 8-sided section.
    d=Vector(b)-Vector(a);o=ringmesh(name,(0,0,0),[(0,width,depth,0),(d.length,width,depth,0)],4,[material],math.pi/4)
    o.location=a;o.rotation_mode='QUATERNION';o.rotation_quaternion=d.to_track_quat('Z','Y');return o

def blade(name,center,points,depth,mats):
    x,y,z=(0,0,0);n=len(points);v=[(x+a,y-depth/2,z+b) for a,b in points]+[(x+a,y+depth/2,z+b) for a,b in points]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))];f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    o=mesh(name,v,f,mats,[0,0]+[min(1,len(mats)-1)]*n);o.location=center;return o

def torus_arc(name,c,r,tube,start=0,end=math.tau,n=32,material='gold',vertical=False):
    x,y,z=c;v=[];f=[]
    for j in range(n+1):
        a=start+(end-start)*j/n
        for k in range(4):
            b=k*math.pi/2+math.pi/4;rr=r+tube*math.cos(b)
            v.append((x+rr*math.cos(a),y+(tube*math.sin(b) if vertical else rr*math.sin(a)),z+(rr*math.sin(a) if vertical else tube*math.sin(b))))
    for j in range(n):
        for k in range(4):f.append((j*4+k,j*4+(k+1)%4,(j+1)*4+(k+1)%4,(j+1)*4+k))
    return mesh(name,v,f,[material])
def collection(name):
    c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c

def move_to(objs,c):
    for o in objs:
        for co in list(o.users_collection):co.objects.unlink(o)
        c.objects.link(o)
def save_group(name,start):
    objs=[o for o in bpy.context.scene.objects if o not in start];c=collection(name);move_to(objs,c)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_animations=False)
    return c
# === terrace: real contiguous mesh rather than a rectangular display plinth ===
start=set(bpy.context.scene.objects)
outline=[(-16.9,-9.3),(-12.2,-11.2),(-5.5,-10.8),(1.0,-11.7),(8.9,-10.9),(15.5,-8.6),(17.0,-3.2),(16.5,3.1),(16.9,8.2),(13.0,10.8),(5.2,11.4),(-2.7,10.9),(-9.3,11.6),(-15.6,10.0),(-17.2,4.7),(-17.0,-2.3)]
# Floating cliff rocks with independent strata but unified semantic mesh.
n=len(outline);v=[]
for j,(height,sc) in enumerate([(0,1),(-.38,1.02),(-1.3,1.01),(-2.35,.98),(-3.3,.94),(-4.5,.75)]):
    for i,(x,z) in enumerate(outline):v.append(pos(x*sc,z*sc,height + (0 if j==0 else .22*math.sin(i*2.2+j))))
f=[];inds=[]
for j in range(5):
    for i in range(n):
        a=j*n+i;b=j*n+(i+1)%n;c=(j+1)*n+(i+1)%n;d=(j+1)*n+i
        f.extend([(a,b,c),(a,c,d)]);inds.extend(([3,1] if j==0 else [int((i+j)%3),int((i+j+1)%3)]))
f.append(tuple(range(5*n,6*n)));inds.append(2)
mesh('Floating_cliff_strata',v,f,['cliff','cliff_light','cliff_dark','cliff_edge'],inds)
# Flat playable turf triangles with restrained color variation, slightly lower than road.
v=[pos(0,0,-.015)]+[pos(x,z,-.015) for x,z in outline]
mesh('Continuous_traversable_meadow',v,[(0,i+1,(i+1)%n+1) for i in range(n)],['grass','grass_sun','grass_dark'],[0,0,1,1,1,0,0,0,0,0,0,0,0,2,2,2])
lanes=[[(-15,-7),(-8,-7),(-8,2),(-2,2),(-2,-5),(7,-5),(7,5),(13,5)],[(-15,8),(-11,8),(-11,2),(-2,2)]]
# One non-overlapping tessellated road bed. Each quad is unique, including junctions.
segments=[(a,b) for lane in lanes for a,b in zip(lane,lane[1:])]
def distance_segment(x,z,a,b):
    dx=b[0]-a[0];dz=b[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(z-a[1])*dz)/(dx*dx+dz*dz)))
    return math.hypot(x-a[0]-dx*t,z-a[1]-dz*t)
v=[];f=[];ind=[]
for xi in range(-34,31):
 for zi in range(-18,20):
    x=xi*.5+.25;z=zi*.5+.25;d=min(distance_segment(x,z,a,b) for a,b in segments)
    if d>1.10:continue
    j=len(v);v.extend([pos(x-.25,z-.25,.013),pos(x+.25,z-.25,.013),pos(x+.25,z+.25,.013),pos(x-.25,z+.25,.013)])
    f.append((j,j+1,j+2,j+3));ind.append(1 if d>.9 else 0)
mesh('Connected_sandstone_road',v,f,['sand_dark','grass_dark'],ind)
# Sparse worn inset slabs, irregular spacing. Never duplicate crossing geometry.
seen=[]
for a,b in segments:
    dx=b[0]-a[0];dz=b[1]-a[1];length=math.hypot(dx,dz);steps=int(length/1.5)+1
    for j in range(steps+1):
      t=j/steps;x=a[0]+dx*t;z=a[1]+dz*t
      if any(math.hypot(x-q[0],z-q[1])<1.1 for q in seen):continue
      seen.append((x,z));theta=math.atan2(dz,dx)
      off=random.uniform(-.22,.22);x-=math.sin(theta)*off;z+=math.cos(theta)*off
      o=ringmesh('Worn_road_slab',pos(x,z,.03),[(0,.58,.76,0),(.035,.52,.70,0)],6,['sand_light' if random.random()<.26 else 'sand','sand_dark'],0)
      o.rotation_euler.z=-theta+random.uniform(-.14,.14)
# Edge inscriptions and root fragments outside playable roads.
for x,z,s in [(-13,-10,1),(-5,-10,1.2),(11,-9,1),(15,-2,.8),(15,9,1),(-7,10,.8),(-16,2,.7)]:
    ringmesh('Lichen_stone',pos(x,z,-.03),[(0,s,.7*s,0),(.25,.9*s,.6*s,.15),(.52,.5*s,.4*s,.3)],6,['cliff_light','cliff_edge','moss'])
# Northern ruins: original rib silhouette, low foreground ruin fragments.
for x,z,h in [(-12.7,-9.4,2.4),(-10,-9.8,3.2),(3.8,-9.3,2.3),(10,-8.6,2.6)]:
    ringmesh('Forgotten_watchstone',pos(x,z),[(0,.68,.6,0),(.3,.68,.6,0),(.4,.48,.42,0),(h-.4,.42,.35,.05),(h,.22,.26,.1)],5,['stone_dark','cliff_edge'])
    blade('Watchstone_gilded_rune',pos(x,z-.38,h*.55),[(-.08,0),(-.08,.55),(.08,.55),(.08,0)],.035,['gold'])
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.context.scene.objects:
 if o not in start:o.select_set(True)
bpy.context.view_layer.objects.active=[o for o in bpy.context.scene.objects if o not in start][0]
bpy.ops.object.join()
world=save_group('world',start)
# === shrine: four embracing ivory ribs, floating split crystal, compass inlay ===
start=set(bpy.context.scene.objects)
ringmesh('Shrine_dais',(0,0,0),[(0,2.15,2.15,0),(.18,2.15,2.15,0),(.3,1.95,1.95,0),(.35,1.95,1.95,0)],12,['stone_dark','stone'])
ringmesh('Shrine_upper_step',(0,0,.35),[(0,1.65,1.65,0),(.14,1.65,1.65,0),(.24,1.46,1.46,0)],12,['stone','stone_light'])
torus_arc('Shrine_inlay',(0,0,.602),1.28,.035,material='gold')
for i in range(8):
    a=i*math.pi/4;x=1.72*math.cos(a);y=1.72*math.sin(a)
    o=blade('Compass_inlay',(x,y,.352),[(-.12,0),(-.05,.35),(.05,.35),(.12,0)],.06,['gold']);o.rotation_euler=(math.pi/2,0,a)
for i in range(4):
    a=i*math.pi/2+math.pi/4
    # Each curved architectural rib is an extruded polygon, not stacked primitive columns.
    pts=[(-.37,0),(.38,0),(.29,.4),(.18,1.2),(.08,2.0),(-.25,2.65),(-.45,2.8),(-.12,1.75),(-.22,.85)]
    o=blade('Shrine_embracing_rib',(1.55*math.cos(a),1.55*math.sin(a),.45),pts,.34,['stone_light','stone_dark']);o.rotation_euler.z=a
    ringmesh('Rib_gilded_foot',(1.55*math.cos(a),1.55*math.sin(a),.5),[(0,.38,.38,0),(.16,.36,.36,0)],5,['gold','gold_dark'])
ringmesh('Crystal_socket',(0,0,.55),[(0,.82,.82,0),(.26,.75,.75,0),(.4,.92,.92,0)],8,['gold_dark','gold'])
ringmesh('Heart_main_crystal',(0,0,.95),[(0,0,0,0),(.65,.61,.52,0),(1.8,.48,.4,.12),(2.65,0,0,0)],6,['crystal','rune'])
for i in range(3):
    a=i*math.tau/3+.3;r=.87
    o=ringmesh('Heart_orbit_shard',(r*math.cos(a),r*math.sin(a),1.2+i*.14),[(0,0,0,0),(.25,.19,.19,0),(.8,.12,.12,.2),(1.04,0,0,0)],5,['crystal','rune']);o.rotation_euler[1]=.35
shrine=save_group('shrine',start)
# === four original defenses, common carved base + bespoke crown function ===
for kind in ['sunbow','ember','frost','storm']:
 start=set(bpy.context.scene.objects)
 ringmesh(kind+'_foundation',(0,0,0),[(0,.95,.95,0),(.16,.95,.95,0),(.25,.78,.78,0)],8,['stone_dark','stone'])
 ringmesh(kind+'_shaft',(0,0,.25),[(0,.58,.58,0),(.18,.62,.62,0),(1.15,.43,.43,.08),(1.42,.62,.62,0)],8,['stone','stone_dark'])
 ringmesh(kind+'_gold_collar',(0,0,1.55),[(0,.65,.65,0),(.16,.65,.65,0)],8,['gold','gold_dark'])
 if kind=='sunbow':
    beam('Sunbow_crossbar',(-.85,0,1.95),(.85,0,1.95),.14,.15,'wood')
    # Ceremonial longbow forms a deep swept wing-shaped crown.
    for s in [-1,1]:
      pts=[(0,0),(s*.68,.12),(s*1.04,.5),(s*.91,.68),(s*.55,.29),(s*.15,.2)]
      blade('Sunbow_wing',(0,0,1.9),pts,.2,['gold','gold_dark'])
    beam('Sunbow_string',(-1.0,.02,2.5),(1.0,.02,2.5),.018,.018,'ivory')
    beam('Sunbow_bolt',(0,-.55,2.1),(0,.8,2.1),.035,.035,'ivory')
    ringmesh('Sunbow_glass_eye',(0,0,2.05),[(0,.16,.16,0),(.45,.12,.12,0),(.6,0,0,0)],5,['crystal'])
 elif kind=='ember':
    # Open-barrel mortar with inside dark bore; stepped sculptural silhouette.
    ringmesh('Ember_bowl',(0,0,1.65),[(0,.5,.5,0),(.3,.72,.72,0),(.85,.9,.9,0),(.95,.84,.84,0),(.93,.62,.62,0),(.55,.48,.48,0)],10,['gold_dark','blue','gold'])
    ringmesh('Ember_fire',(0,0,2.25),[(0,.38,.38,0),(.35,.29,.29,0),(.7,0,0,0)],5,['ember','red'])
    for a in [0,math.pi/2,math.pi,math.pi*1.5]:
      blade('Ember_fin',(.66*math.cos(a),.66*math.sin(a),1.56),[(-.12,0),(-.12,.7),(.15,.5),(.2,0)],.12,['red','gold_dark']).rotation_euler.z=a
 elif kind=='frost':
    for i in range(3):
      a=i*math.tau/3
      o=blade('Frost_petal',(.48*math.cos(a),.48*math.sin(a),1.65),[(-.16,0),(-.22,.6),(-.05,1.25),(.13,.5),(.12,0)],.25,['stone_light','stone_dark']);o.rotation_euler.z=a
    ringmesh('Frost_heart',(0,0,1.88),[(0,0,0,0),(.4,.34,.34,0),(.95,.24,.24,.2),(1.4,0,0,0)],6,['crystal','rune'])
    torus_arc('Frost_halo',(0,0,2.3),.72,.06,material='gold')
 else:
    for s in [-1,1]:
      blade('Storm_fork',(0,0,1.68),[(s*.25,0),(s*.8,.65),(s*.65,1.15),(s*.46,.65),(s*.05,.25)],.25,['gold','gold_dark'])
    ringmesh('Storm_orb',(0,0,2.5),[(0,0,0,0),(.23,.3,.3,0),(.6,.23,.23,.12),(.8,0,0,0)],6,['amethyst','rune'])
    torus_arc('Storm_aperture',(0,0,2.5),.7,.06,material='blue',vertical=True)
 save_group('tower_'+kind,start)
# === original heraldic standard, not an external emblem ===
start=set(bpy.context.scene.objects)
beam('Standard_staff',(0,0,0),(0,0,3.2),.055,.055,'gold')
beam('Standard_crossbar',(-.65,0,2.75),(.65,0,2.75),.045,.045,'gold')
blade('Azure_swallowtail',(0,0,1.25),[(-.6,1.5),(.6,1.5),(.57,0),(0,.28),(-.57,0)],.04,['blue','gold_dark'])
blade('Dawn_sigil',(0,-.035,1.8),[(0,0),(.28,.42),(0,.78),(-.28,.42)],.015,['gold'])
save_group('standard',start)
# Native showcase layout (runtime assets remain origin-centred).
for c in [shrine]:
 for o in c.objects:o.location+=Vector(pos(13,5,0))
for i,k in enumerate(['sunbow','ember','frost','storm']):
 for o in bpy.data.collections['tower_'+k].objects:o.location+=Vector(pos(-5+i*4,7,0))
for o in bpy.data.collections['standard'].objects:o.location+=Vector(pos(11.2,7.9,0))
# Native render is inspection evidence, not a substituted final-game screenshot.
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=2
scene.world.color=(.17,.23,.29)
scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast';scene.view_settings.exposure=0;scene.view_settings.gamma=1
bpy.ops.object.light_add(type='AREA',location=(0,-5,19));bpy.context.object.data.energy=2100;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=18
bpy.ops.object.light_add(type='SUN',location=(-8,-15,20));bpy.context.object.rotation_euler=(.4,-.6,-.3);bpy.context.object.data.energy=2.;bpy.context.object.data.angle=.3
bpy.ops.object.camera_add(location=pos(23,32,30));cam=bpy.context.object;cam.rotation_euler=(Vector(pos(0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=44;scene.camera=cam
scene.render.resolution_x=1200;scene.render.resolution_y=820;scene.render.resolution_percentage=100
scene.render.filepath='//evidence/native-world.png'
for screen in bpy.data.screens:
 for area in screen.areas:
  for space in area.spaces:
   if space.type=='FILE_BROWSER' and space.params:space.params.directory=b'//'

bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'dawnkeep-original.blend'))
# Record geometry deterministically before optional render.
report={'blender':bpy.app.version_string,'seed':18026,'pipeline':'native Blender Python (not MCP)','object_count':len(scene.objects),'mesh_count':len([x for x in scene.objects if x.type=='MESH']),'vertices':sum(len(x.data.vertices) for x in scene.objects if x.type=='MESH'),'polygons':sum(len(x.data.polygons) for x in scene.objects if x.type=='MESH'),'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in OUT.glob('*.glb')}}
(HERE/'evidence/build.json').write_text(json.dumps(report,indent=2))
if '--render' in sys.argv:
 scene.render.filepath=str(HERE/'evidence/native-world.png');bpy.ops.render.render(write_still=True)
print('DAWNKEEP_ART_DONE',json.dumps(report))
