"""Author compact tropical foliage in Blender; external input is CC0 KayKit data."""
import argparse, sys, math, random, json, hashlib
from pathlib import Path
import bpy
from mathutils import Vector
args=argparse.ArgumentParser();args.add_argument('--source',type=Path,required=True);args.add_argument('--out',type=Path,required=True)
a=args.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
def material(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=.85
 return m
bark=[material('Trunk warm umber',(.19,.105,.052)),material('Trunk ring shade',(.14,.074,.038)),material('Trunk sun face',(.24,.14,.073))]
leaves=[material('Palm jade',(.068,.235,.135)),material('Palm sunlit',(.125,.32,.16)),material('Palm young leaf',(.24,.40,.145))]
stone=material('Coastal stone',(.30,.36,.31))
stem=material('Frond rib',(.18,.27,.085));nut=material('Coconut',(.12,.073,.033))
collections={}
def collection(name):
 c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);collections[name]=c;return c
def move_to(o,c):
 for old in list(o.users_collection):old.objects.unlink(o)
 c.objects.link(o)
def mesh(name,verts,faces,mats,indices,c):
 m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.materials.clear()
 for mat in mats:m.materials.append(mat)
 m.update();o=bpy.data.objects.new(name,m);c.objects.link(o)
 for i,p in enumerate(m.polygons):p.material_index=indices[i%len(indices)] if indices else 0;p.use_smooth=False
 return o
def tube(name,points,radii,mats,c,sides=7):
 verts=[];faces=[];inds=[]
 for j,p in enumerate(points):
  tangent=points[min(j+1,len(points)-1)]-points[max(0,j-1)]
  tangent.normalize();u=tangent.cross(Vector((0,1,0))).normalized();v=tangent.cross(u).normalized()
  for k in range(sides):verts.append(p+(u*math.cos(k*math.tau/sides)+v*math.sin(k*math.tau/sides))*radii[j])
 for j in range(len(points)-1):
  for k in range(sides):faces.append((j*sides+k,j*sides+(k+1)%sides,(j+1)*sides+(k+1)%sides,(j+1)*sides+k));inds.append((j%5==0)+int(k==2 and len(mats)>2))
 faces.extend([tuple(reversed(range(sides))),tuple((len(points)-1)*sides+k for k in range(sides))]);inds.extend([0,0])
 return mesh(name,verts,faces,mats,[i%len(mats) for i in inds],c)
def palm(name,seed,height,lean):
 r=random.Random(seed);c=collection(name)
 points=[Vector((lean*(t:=i/15)**1.7,.14*math.sin(t*math.pi),height*t)) for i in range(16)]
 radii=[(.21-.105*i/15)*(1.0+.08*math.sin(i*3.1))+.075*math.exp(-i*.9) for i in range(16)]
 tube(name+' curved trunk',points,radii,bark,c,9);crown=points[-1]
 for j in range(8):
  az=j*math.tau/8+r.uniform(-.16,.16);length=r.uniform(2.0,2.7);rise=r.uniform(.30,.65);drop=r.uniform(.7,1.2)
  direct=Vector((math.cos(az),math.sin(az),0));side=Vector((-math.sin(az),math.cos(az),0));origin=crown+Vector((0,0,r.uniform(-.10,.09)))
  def spine(t):return origin+direct*(length*t)+Vector((0,0,rise*math.sin(math.pi*t)-drop*t*t))
  pp=[spine(i/12) for i in range(13)];tube(name+' frond rib '+str(j),pp,[.026*(1-i/13) for i in range(13)],[stem],c,5)
  verts=[];faces=[];indices=[]
  for k in range(10):
   t=.12+k*.079;leaflen=.97*math.sin(math.pi*t)**.52*r.uniform(.86,1.12);width=.12*(1-t*.35)
   for sign in [-1,1]:
    base=spine(t);direction=(side*sign+direct*.29).normalized();across=Vector((-direction.y,direction.x,0))
    ids=[]
    for q in range(4):
     u=q/3;center=base+direction*(leaflen*u)+direct*(.12*u*u)+Vector((0,0,.07*math.sin(math.pi*u)-(.18+.13*t)*u*u))
     half=width*math.sin(math.pi*u)**.7
     ids.append(len(verts));verts.extend([center-across*half,center+Vector((0,0,.025*math.sin(math.pi*u))),center+across*half])
    for q in range(3):
     b0=ids[q];b1=ids[q+1];faces.extend([(b0,b1,b1+1,b0+1),(b0+1,b1+1,b1+2,b0+2)]);indices.extend([(j+k)%2,(j+k+1)%2])
  o=mesh(name+' pinnate frond '+str(j),verts,faces,leaves,indices,c)
  # Leaves have real thickness and top/bottom normals, not alpha cards.
  mod=o.modifiers.new('Thin leaf thickness','SOLIDIFY');mod.thickness=.008;mod.offset=0
  bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.modifier_apply(modifier=mod.name);o.select_set(False)
 for j in range(3):
  az=j*2.2;bpy.ops.mesh.primitive_uv_sphere_add(segments=8,ring_count=5,radius=.12,location=crown+Vector((.16*math.cos(az),.16*math.sin(az),-.18)));o=bpy.context.object;o.name=name+' coconut '+str(j);o.scale=(.9,.9,1.15);o.data.materials.append(nut);move_to(o,c)
 return c
palm('palm-a',913,4.1,.8);palm('palm-b',119,3.4,-.65)

def broadleaf(name,seed):
 r=random.Random(seed);c=collection(name);verts=[];faces=[];indices=[]
 for j in range(7):
  az=j*math.tau/7+r.uniform(-.22,.22);length=r.uniform(.40,.68);rise=r.uniform(.20,.48)
  direct=Vector((math.cos(az),math.sin(az),0));side=Vector((-math.sin(az),math.cos(az),0))
  ids=[]
  for q in range(7):
   t=q/6;center=direct*(length*t)+Vector((0,0,.06+rise*math.sin(math.pi*t*.86)))
   half=.145*math.sin(math.pi*t)**.68;ridge=.048*math.sin(math.pi*t)
   ids.append(len(verts));verts.extend([center-side*half,center+Vector((0,0,ridge)),center+side*half])
  for q in range(6):
   b0=ids[q];b1=ids[q+1];faces.extend([(b0,b1,b1+1,b0+1),(b0+1,b1+1,b1+2,b0+2)]);indices.extend([j%2,(j+1)%2])
 o=mesh(name+' curled leaves',verts,faces,leaves,indices,c)
 mod=o.modifiers.new('Leaf thickness','SOLIDIFY');mod.thickness=.006
 bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.modifier_apply(modifier=mod.name);o.select_set(False)
 return c
broadleaf('understory-a',211);broadleaf('understory-b',721)

# CC0 author assets are imported as mesh data only, then packed into standalone GLBs.
selected={'bush-a':'Bush_3_A_Color1','bush-b':'Bush_4_A_Color1','shore-stone-a':'Rock_3_A_Color1','shore-stone-b':'Rock_2_C_Color1'}
source_records=[]
for alias,name in selected.items():
 p=a.source/(name+'.gltf');d=json.loads(p.read_text())
 for item in d.get('buffers',[])+d.get('images',[]):
  uri=item.get('uri','');assert uri and not uri.startswith(('http:','https:','file:')) and '..' not in Path(uri).parts
 before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(p));new=list(set(bpy.data.objects)-before);c=collection(alias)
 for o in new:
  move_to(o,c);o.name=alias+' '+o.name
  if o.type=='MESH':
   o.data.materials.clear();o.data.materials.append(leaves[0] if alias.startswith('bush') else stone)
   for polygon in o.data.polygons:polygon.material_index=0
 source_records.append({'output':alias+'.glb','source':p.name,'gltf_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'license':'CC0-1.0','author':'Kay Lousberg','modifications':'geometry retained; shared matte island material replaces original palette texture'})
for img in bpy.data.images:
 if img.source=='FILE':img.pack();img.filepath='//'+Path(img.filepath).name
# One mesh per asset keeps imported node/draw-call overhead bounded.
for name,c in collections.items():
 obs=[o for o in c.objects if o.type=='MESH']
 if len(obs)>1:
  bpy.ops.object.select_all(action='DESELECT')
  for o in obs:o.select_set(True)
  bpy.context.view_layer.objects.active=obs[0];bpy.ops.object.join();bpy.context.object.name=name
exports=[]
for name,c in collections.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in c.objects:o.select_set(True)
 coords=[o.matrix_world@Vector(v) for o in c.objects if o.type=='MESH' for v in o.bound_box]
 lo=[min(v[k] for v in coords) for k in range(3)];hi=[max(v[k] for v in coords) for k in range(3)]
 bpy.ops.export_scene.gltf(filepath=str(a.out/(name+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_animations=False)
 exports.append({'name':name,'objects':len(c.objects),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in c.objects if o.type=='MESH'),'blender_bounds':[lo,hi],'bytes':(a.out/(name+'.glb')).stat().st_size,'sha256':hashlib.sha256((a.out/(name+'.glb')).read_bytes()).hexdigest()})
# Native editable collection library. Selection/export paths are cleared from scene metadata.
bpy.ops.object.select_all(action='DESELECT');bpy.context.scene.render.filepath="//preview.png"
bpy.data.libraries.write(str(a.out/'tropical-nature.blend'),{bpy.context.scene},path_remap="RELATIVE",fake_user=True,compress=False)
(a.out/'authoring.json').write_text(json.dumps({'blender':bpy.app.version_string,'production':'actual headless Blender data import, original palm modelling, native save and GLB export','third_party':source_records,'original':['palm-a','palm-b','understory-a','understory-b'],'assets':exports},indent=2)+'\n')
