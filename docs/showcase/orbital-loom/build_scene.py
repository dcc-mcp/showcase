import bpy, math, os, json
from mathutils import Vector
OUT=os.path.dirname(os.path.abspath(__file__))
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
s=bpy.context.scene;s.frame_start=1;s.frame_end=360;s.render.fps=24

def mat(name,c,metal=0,rough=.3):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough;return m
brass=mat('Satin champagne brass',(.57,.36,.12),.78,.24)
teal=mat('Deep petrol enamel',(.015,.078,.083),.58,.24)
ivory=mat('Porcelain ivory',(.85,.8,.64),.12,.22)
black=mat('Graphite rubber',(.013,.019,.02),.15,.42)
floor=mat('Warm gallery stone',(.19,.205,.195),.1,.52)

def finish(o,name,m):
 o.name=name;o.data.materials.append(m)
 if o.type=='MESH':
  for p in o.data.polygons:p.use_smooth=True
 return o

def cyl(name,r,d,loc,m):
 bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=r,depth=d,location=loc);o=finish(bpy.context.object,name,m);b=o.modifiers.new('Machined rounded edge','BEVEL');b.width=.025;b.segments=3;o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');return o

def ball(name,r,loc,m):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=r,location=loc);return finish(bpy.context.object,name,m)
def torus(name,r,t,loc,m,rot=(0,0,0)):
 bpy.ops.mesh.primitive_torus_add(major_radius=r,minor_radius=t,major_segments=128,minor_segments=12,location=loc,rotation=rot);return finish(bpy.context.object,name,m)
def bar(name,a,b,r,m):
 a,b=Vector(a),Vector(b);o=cyl(name,r,(b-a).length,(a+b)/2,m);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return o

def empty(name,loc):
 o=bpy.data.objects.new(name,None);s.collection.objects.link(o);o.location=loc;return o

def parent(o,p):
 bpy.context.view_layer.update();mw=o.matrix_world.copy();o.parent=p;o.matrix_world=mw

cyl('Floating plinth / petrol',2.05,.26,(0,0,.27),teal)
cyl('Brass lower reveal',2.0,.055,(0,0,.115),brass)
cyl('Inset precision dial',1.88,.034,(0,0,.42),black)
for a in range(0,360,5):
 rad=math.radians(a);ra=1.69 if a%30==0 else 1.77
 bar('Engraved dial mark %03d'%a,(ra*math.cos(rad),ra*math.sin(rad),.446),(1.85*math.cos(rad),1.85*math.sin(rad),.446),.009,brass)
for x in (-1.1,1.1):
 for y in (-.9,.9):cyl('Isolation foot',.18,.1,(x,y,.05),black)
# Outer ring rests on two visible bearing columns.
Z=2.4
for x in (-1.75,1.75):
 cyl('Pedestal bearing support',.115,1.96,(x,0,1.43),teal)
 ball('Polished spherical bearing',.19,(x,0,Z),brass)
 side=1 if x>0 else -1
 bar('Outer horizontal shaft',(x-side*.3,0,Z),(x+side*.13,0,Z),.075,black)

gimbals=[]
for i,(r,thick,col) in enumerate([(1.52,.052,brass),(1.19,.06,teal),(.84,.045,brass)]):
 p=empty('Gimbal_%d_driver'%i,(0,0,Z));gimbals.append(p)
 ring=torus('Precision hoop %d'%i,r,thick,(0,0,Z),col,(math.pi/2,0,0));parent(ring,p)
 # Add contrasting narrow inner inlay.
 ring=torus('Hoop ivory inlay %d'%i,r-.02,.011,(0,-.054,Z),ivory,(math.pi/2,0,0));parent(ring,p)
 for side in (-1,1):
  o=ball('Pivot jewel %d %d'%(i,side),.085,((side*r,0,Z) if i%2==0 else (0,0,Z+side*r)),brass);parent(o,p)
 if i:
  parent(p,gimbals[i-1])
 axis=0 if i%2==0 else 2
 p.driver_add('rotation_euler',axis).driver.expression=f'{(-1 if i==1 else 1)*(i+1)} * (frame-1) * 6.28318530718 / 360'
 # Small balanced counterweights live entirely inside each hoop shell.
 for side in (-1,1):
  o=ball('Balanced weight %d %d'%(i,side),.09,(0,0,Z+side*(r-.13)),ivory);parent(o,p)
for i in (1,2):
 for side in (-1,1):
  r0,r1=([1.52,1.19,.84][i-1],[1.52,1.19,.84][i])
  a=(0,0,Z+side*r1) if i==1 else (side*r1,0,Z)
  b=(0,0,Z+side*r0) if i==1 else (side*r0,0,Z)
  o=bar('Inter-gimbal shaft %d %d'%(i,side),a,b,.032,brass);parent(o,gimbals[i-1])
core=ball('Porcelain heart',.25,(0,0,Z),ivory);parent(core,gimbals[2])
for a in (0,math.pi/2):
 o=torus('Heart cage',.36,.016,(0,0,Z),brass,(a,math.pi/2,0));parent(o,gimbals[2])
for side in (-1,1):
 o=bar('Core suspension', (side*.26,0,Z),(side*.81,0,Z),.028,brass);parent(o,gimbals[2])
# Clear authorship label is native editable type.
bpy.ops.object.text_add(location=(0,-1.23,.451));label=bpy.context.object;label.name='Engraved ORBITAL LOOM';label.data.body='O R B I T A L   L O O M';label.data.align_x='CENTER';label.data.size=.105;label.data.extrude=.001;label.data.materials.append(brass)
bpy.ops.mesh.primitive_plane_add(size=200);finish(bpy.context.object,'Gallery cyclorama',floor)

focus=empty('Camera focus',(0,0,1.85))
bpy.ops.object.camera_add(location=(6,-8,5));cam=bpy.context.object;cam.name='Cinematic orbit camera';s.camera=cam;cam.data.lens=51
con=cam.constraints.new('TRACK_TO');con.target=focus;con.track_axis='TRACK_NEGATIVE_Z';con.up_axis='UP_Y'
for frame,ang,dist,z,lens in [(1,-1.12,13.5,5.8,51),(120,-.9,12.7,5.4,51),(240,-.65,13.2,6.2,53),(360,-.38,14.4,6.8,54)]:
 cam.location=(dist*math.cos(ang),dist*math.sin(ang),z);cam.keyframe_insert(data_path='location',frame=frame);cam.data.lens=lens;cam.data.keyframe_insert(data_path='lens',frame=frame)
for fc in cam.animation_data.action.fcurves:
 for k in fc.keyframe_points:k.interpolation='BEZIER'
def light(name,loc,power,size,color):
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.data.color=color;o.rotation_euler=(Vector((0,0,2))-o.location).to_track_quat('-Z','Y').to_euler()
light('Large warm key',(1,-4,7),1200,5,(1,.85,.65));light('Cool rim',(-4,2,5),1500,4,(.57,.82,1));light('Ivory frontal softbox',(5,2,6),1100,3,(1,.94,.8))
s.world.color=(.12,.12,.12);s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=20;s.cycles.use_denoising=True;s.cycles.max_bounces=6;s.render.threads_mode='FIXED';s.render.threads=4
s.render.resolution_x=960;s.render.resolution_y=540;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='AgX'
s['showcase']='Orbital Loom';s['motion_description']='Three nested driven gimbals plus continuous constrained camera move; native procedural 360-frame animation.'
s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'orbital-loom.blend'))
print(json.dumps({'objects':len(s.objects),'frames':s.frame_end,'drivers':sum(len(o.animation_data.drivers) for o in s.objects if o.animation_data),'blend':os.path.join(OUT,'orbital-loom.blend')}))
