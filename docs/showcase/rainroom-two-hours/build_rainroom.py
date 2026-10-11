"""Original Rainroom geometry. Execute via official Blender MCP scripting skill."""
import bpy, math, random
from mathutils import Vector
random.seed(29)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for d in list(bpy.data.materials): bpy.data.materials.remove(d)
s=bpy.context.scene;s.name='Rainroom | two hours';s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=72;s.cycles.use_denoising=True;s.cycles.max_bounces=10;s.cycles.transmission_bounces=8
s.render.threads_mode='FIXED';s.render.threads=6;s.render.resolution_x=1400;s.render.resolution_y=1400;s.render.resolution_percentage=100
s.view_settings.view_transform='AgX';s.render.image_settings.file_format='PNG';s.render.film_transparent=False
s.world.use_nodes=True; bg=s.world.node_tree.nodes.get('Background');bg.inputs[0].default_value=(.12,.18,.28,1)
def mat(n,c,r=.4,metal=0):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=r;p.inputs['Metallic'].default_value=metal;return m
walnut=mat('Smoked walnut | anisotropic grain',(.085,.035,.019),.32)
p=walnut.node_tree.nodes.get('Principled BSDF');n=walnut.node_tree.nodes;lk=walnut.node_tree.links;tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=5;tex.inputs['Detail'].default_value=3;co=n.new('ShaderNodeTexCoord');mp=n.new('ShaderNodeVectorMath');mp.operation='MULTIPLY';mp.inputs[1].default_value=(2,35,30);lk.new(co.outputs['Generated'],mp.inputs[0]);lk.new(mp.outputs[0],tex.inputs[0]);r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].color=(.018,.009,.005,1);r.color_ramp.elements[1].color=(.18,.075,.025,1);lk.new(tex.outputs['Fac'],r.inputs[0]);lk.new(r.outputs[0],p.inputs['Base Color'])
cream=mat('Ivory glazed stoneware',(.63,.56,.42),.22); dark=mat('Ink green painted joinery',(.025,.055,.049),.34);brass=mat('Patinated brushed brass',(.33,.19,.07),.27,.78);paper=mat('Uncoated warm paper',(.62,.56,.43),.7);linen=mat('Oat linen weave',(.39,.36,.29),.85);blue=mat('Deep petrol linen cover',(.025,.12,.14),.6);red=mat('Oxide cloth cover',(.28,.062,.028),.7)
glass=mat('Window glass | faint unevenness',(.86,.95,1),.055);pg=glass.node_tree.nodes.get('Principled BSDF');pg.inputs['Transmission Weight'].default_value=1;pg.inputs['IOR'].default_value=1.45
water=mat('Water beads | optical IOR 1.333',(.93,.98,1),.035);pw=water.node_tree.nodes.get('Principled BSDF');pw.inputs['Transmission Weight'].default_value=1;pw.inputs['IOR'].default_value=1.333
tea=mat('Dark amber tea',(.09,.029,.005),.12);leafmat=mat('Dried eucalyptus',(.13,.20,.13),.68)
def smooth(o):
 if o.type=='MESH':
  for f in o.data.polygons:f.use_smooth=True
 return o
def assign(o,m):o.data.materials.append(m);return o
def cube(n,loc,dim,m,bevel=.02):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=n;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);assign(o,m)
 if bevel:mod=o.modifiers.new('Soft worked edges','BEVEL');mod.width=bevel;mod.segments=3;o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL')
 return o
def uv(n,loc,scale,m):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,location=loc);o=bpy.context.object;o.name=n;o.scale=scale;assign(o,m);return smooth(o)
def curve(n,pts,r,m):
 d=bpy.data.curves.new(n,'CURVE');d.dimensions='3D';d.bevel_depth=r;d.bevel_resolution=3;sp=d.splines.new('BEZIER');sp.bezier_points.add(len(pts)-1)
 for p,co in zip(sp.bezier_points,pts):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
 o=bpy.data.objects.new(n,d);s.collection.objects.link(o);assign(o,m);return o
def lathe(n,profile,loc,m):
 verts=[];faces=[];N=96
 for r,z in profile:
  verts.extend([(loc[0]+r*math.cos(a*2*math.pi/N),loc[1]+r*math.sin(a*2*math.pi/N),loc[2]+z) for a in range(N)])
 for j in range(len(profile)-1):
  for a in range(N):b=j*N+a;c=j*N+(a+1)%N;faces.append((b,c,c+N,b+N))
 me=bpy.data.meshes.new(n);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(n,me);s.collection.objects.link(o);assign(o,m);return smooth(o)
def area(n,loc,target,color,power,size):
 d=bpy.data.lights.new(n,'AREA');d.energy=power;d.color=color;d.shape='DISK';d.size=size;o=bpy.data.objects.new(n,d);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o
def camera(n,loc,target,lens):
 d=bpy.data.cameras.new(n);o=bpy.data.objects.new(n,d);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();d.lens=lens;return o
# Window and wide desk, camera faces into the rainy street.
cube('Walnut writing ledge',(0,0,.79),(3.5,1.65,.13),walnut,.04)
cube('Wall below sill',(0,1.13,.35),(3.6,.25,.7),dark)
for x in [-1.59,1.59]:cube('Deep window jamb',(x,1.12,1.9),(.16,.30,2.4),dark)
for z in [.92,3.0]:cube('Horizontal sash',(0,1.12,z),(3.3,.30,.10),dark)
cube('Central slender mullion',(.35,1.10,1.95),(.07,.18,2.05),dark,.01)
cube('Rain glass pane',(0,1.19,1.94),(3.08,.014,1.99),glass,.002)
cube('Crossbar',(0,1.10,2.40),(3.1,.16,.055),dark,.009)
# Original variable water beads and gravity streaks on room-facing glass surface.
for i in range(330):
 x=random.uniform(-1.49,1.49);z=random.uniform(1.00,2.95);r=random.uniform(.006,.018)
 uv('Water bead %03d'%i,(x,1.165,z),(r,.009,r*random.uniform(1,2.4)),water)
 if i%13==0:curve('Gravity rivulet %03d'%i,[(x+.005*math.sin(k),1.167,z-k*.039) for k in range(5)],.0025,water)
# Curtains woven as editable mesh pleats, slightly drawn to the edges.
for side in [-1,1]:
 verts=[];faces=[];nx=28;nz=25
 for j in range(nz):
  z=.93+2.2*j/(nz-1)
  for i in range(nx):
   x=side*(1.37+.44*i/(nx-1));y=.73+.055*math.sin(i*math.pi*2/7)+.035*math.sin(j*.18);verts.append((x,y,z))
 for j in range(nz-1):
  for i in range(nx-1):a=j*nx+i;faces.append((a,a+1,a+nx+1,a+nx))
 me=bpy.data.meshes.new('Linen pleats');me.from_pydata(verts,[],faces);o=bpy.data.objects.new('Curtain left' if side<0 else 'Curtain right',me);s.collection.objects.link(o);assign(o,linen);smooth(o);o.modifiers.new('Fabric thickness','SOLIDIFY').thickness=.002
# Books, quietly imperfect placement.
for i,(x,y,z,w,d,h,m) in enumerate([(-.28,.12,.90,1.03,.65,.09,blue),(-.23,.12,1.005,.93,.62,.075,red)]):
 for off in [-h/2,h/2]:cube('Cloth book cover',(x,y,z+off),(w+.03,d+.03,.018),m,.008)
 cube('Book page block',(x,y,z),(w,d,h-.017),paper,.005)
 for k in range(9):cube('Fine page edge',(x,y-d/2-.002,z-h*.38+k*h*.08),(w-.025,.002,.001),linen,0)
# Bowl/cup with visible rim, tea and curved handle.
lathe('Ceramic tea cup',[(.0,0),(.11,0),(.125,.025),(.16,.18),(.164,.23),(.155,.24),(.143,.225),(.14,.18),(.105,.035),(.0,.035)],(-.72,-.25,.86),cream)
lathe('Tea surface',[(0,0),(.142,0)],(-.72,-.25,1.051),tea)
curve('Tea cup handle',[(-.86,-.25,1.05),(-1.02,-.25,1.04),(-1.04,-.25,.92),(-.87,-.25,.91)],.018,cream)
lathe('Tea saucer',[(0,0),(.12,0),(.235,.018),(.25,.029),(.245,.035),(.12,.008),(0,.008)],(-.72,-.25,.855),cream)
# Clear bottle, filled water and stem silhouettes.
lathe('Clear fluted bottle',[(0,0),(.14,0),(.165,.035),(.16,.39),(.065,.51),(.060,.65),(.052,.65),(.053,.51),(.149,.39),(.15,.035),(0,.016)],(.72,.48,.86),glass)
lathe('Bottle water',[(0,0),(.145,0),(.146,.29),(0,.29)],(.72,.48,.877),water)
for j in range(3):
 pts=[(.72,.48,.94),(.72+.05*j,.48,1.44),(.61+.18*j,.46,1.99+.09*j)];curve('Eucalyptus branch',pts,.006,walnut)
 for k in range(5):
  z=1.45+k*.10;sgn=(-1)**k;x=.72+.04*j+(z-1.44)*(.30*j-.20)
  l=uv('Eucalyptus dried leaf',(x+sgn*.085,.45,z),(.095,.017,.045),leafmat);l.rotation_euler[1]=sgn*.5
# A brass task lamp with shallow conical hood, independent warm source.
lathe('Task lamp weighted base',[(0,0),(.20,0),(.21,.025),(.18,.06),(0,.06)],(1.0,-.24,.86),brass)
curve('Task lamp gooseneck',[(1,-.24,.91),(1.05,-.20,1.30),(.99,-.20,1.65),(.79,-.22,1.78)],.018,brass)
lathe('Task lamp brass shade',[(.07,.0),(.24,-.17),(.245,-.185),(.232,-.186),(.06,-.016)],(.79,-.22,1.79),brass)
em=mat('Lamp opal diffuser',(1,.66,.26),.25);ep=em.node_tree.nodes.get('Principled BSDF');ep.inputs['Emission Color'].default_value=(1,.43,.12,1);ep.inputs['Emission Strength'].default_value=2
lathe('Lamp opal disk',[(0,0),(.221,0)],(.79,-.22,1.614),em)
# Personal detail: a fountain pen and folded correspondence.
cube('Correspondence',(.12,-.49,.87),(.60,.30,.012),paper,.002)
pen=curve('Fountain pen',[(-.01,-.54,.898),(.40,-.40,.898)],.012,dark);uv('Pen brass cap',(.39,-.405,.898),(.022,.012,.013),brass)
# Abstract distant building facades, no third-party imagery.
city=mat('Rain distant facades',(.018,.038,.060),.85)
for i in range(12):
 x=-4+i*.73;h=random.uniform(2,5);cube('Distant city mass',(x,4.8,h/2),(random.uniform(.4,.7),.5,h),city,.015)
 for k in range(4):
  warm=mat('Distant lit window %d %d'%(i,k),(.38,.20,.08),.8);p=warm.node_tree.nodes.get('Principled BSDF');p.inputs['Emission Color'].default_value=(1,.46,.16,1);p.inputs['Emission Strength'].default_value=random.uniform(.5,3)
  cube('Distant window',(x,4.52,.7+k*.6),(.12,.015,.17),warm,.002)
# Two keyed moods, saved as frames 1 and 2, no rendering substitution.
night=area('Warm reading pool',(.80,-.22,1.61),(.55,-.1,.87),(1,.50,.22),24,.32)
fill=area('Soft room fill',(-2,-2.5,3),(0,0,1.3),(.52,.66,1),36,3)
sky=area('Sky through rain',(0,2.8,3.2),(0,0,1),(.23,.47,1),170,3)
for f,energy,col in [(1,170,(.23,.47,1)),(2,520,(.75,.87,1))]:sky.data.energy=energy;sky.data.color=col;sky.data.keyframe_insert('energy',frame=f);sky.data.keyframe_insert('color',frame=f)
for f,e in [(1,24),(2,0)]:night.data.energy=e;night.data.keyframe_insert('energy',frame=f)
for f,e in [(1,36),(2,90)]:fill.data.energy=e;fill.data.keyframe_insert('energy',frame=f)
for f,e in [(1,.12),(2,.40)]:bg.inputs['Strength'].default_value=e;bg.inputs['Strength'].keyframe_insert('default_value',frame=f)
for f,e in [(1,2),(2,0)]:ep.inputs['Emission Strength'].default_value=e;ep.inputs['Emission Strength'].keyframe_insert('default_value',frame=f)
camera('01_Window still life',(2.95,-4.6,2.72),(-.04,.45,1.65),56)
camera('02_Rain and tea',(-2.45,-3.3,2.0),(-.05,.55,1.65),58)
s.camera=bpy.data.objects['01_Window still life'];s.frame_start=1;s.frame_end=2;s.frame_set(1)
# Small original bitmap inside a textured postcard, packed by typed MCP afterwards.
im=bpy.data.images.new('Rainroom postcard original ink',width=128,height=128)
pix=[]
for y in range(128):
 for x in range(128):
  line=(abs(y-(38+17*math.sin(x/18)))<2 or abs(y-(65+10*math.sin(x/25)))<1.5);c=(.045,.15,.18) if line else (.65,.59,.46);pix.extend((*c,1))
im.pixels.foreach_set(pix);im.update()
pm=mat('Postcard original ink print',(.65,.59,.46),.7);nt=pm.node_tree;it=nt.nodes.new('ShaderNodeTexImage');it.image=im;nt.links.new(it.outputs['Color'],nt.nodes.get('Principled BSDF').inputs['Base Color']);cube('Printed postcard',(.05,-.46,.88),(.26,.21,.003),pm,.001)
for m in bpy.data.materials:
 if m.name in ['Ivory glazed stoneware','Oat linen weave']:
  nt=m.node_tree;t=nt.nodes.new('ShaderNodeTexNoise');t.inputs['Scale'].default_value=180;b=nt.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.16;b.inputs['Distance'].default_value=.015;nt.links.new(t.outputs['Fac'],b.inputs['Height']);nt.links.new(b.outputs[0],nt.nodes.get('Principled BSDF').inputs['Normal'])
s['Mood guide']='Frame 1: warm lamp / rain night. Frame 2: cool morning / lamp off.'
s.render.filepath='//rainroom.png';bpy.context.preferences.filepaths.save_version=0
print('Rainroom built',len(s.objects),'objects; two keyed moods; original postcard image awaits typed pack.')
