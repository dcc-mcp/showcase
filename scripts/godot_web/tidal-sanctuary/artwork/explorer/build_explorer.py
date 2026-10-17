"""Create an island explorer from vetted KayKit CC0 Ranger head/rig + original clothes and swim.
Run: blender --background --python build_explorer.py -- --source PATH_TO_KAYKIT_FREE --output OUTPUT_DIR
No network, add-on installation or UI service is used.
"""
import bpy, math, json, sys, argparse, hashlib, shutil
from pathlib import Path
from mathutils import Vector, Quaternion
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args(args)
source=Path(a.source).resolve();out=Path(a.output).resolve();(out/'export').mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for datablock in list(bpy.data.actions):bpy.data.actions.remove(datablock)
bpy.ops.import_scene.gltf(filepath=str(source/'Characters/gltf/Ranger.glb'))
rig=next(o for o in bpy.context.selected_objects if o.type=='ARMATURE');rig.name='ExplorerRig';rig.data.name='ExplorerSkeleton'
head=bpy.data.objects['Ranger_Head'];head.name='Explorer_Head_KayKit'
for obj in list(bpy.data.objects):
 if obj not in [rig,head]:bpy.data.objects.remove(obj,do_unlink=True)
rig.animation_data_clear()
# Palette values are authored in sRGB and converted for Blender's linear material inputs.
def linear(x):return x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4
def mat(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=tuple(linear(c) for c in color)+(1,);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=m.diffuse_color;bs.inputs['Roughness'].default_value=.83
 return m
coral=mat('Coral cotton | shirt',(1,.40,.26));cream=mat('Warm canvas | hat',(.94,.84,.62));teal=mat('Lagoon teal | shorts',(.11,.45,.44));skin=mat('Warm skin',(.88,.68,.50));sand=mat('Sandstone | sandals',(.60,.42,.25));darkteal=mat('Deep lagoon | seams',(.075,.29,.29));gold=mat('Compass brass',(.94,.70,.28))
created=[]
def bind(obj,bone=None,weights=None):
 bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);obj.select_set(False)
 if weights:
  for bn in weights:obj.vertex_groups.new(name=bn)
  for v in obj.data.vertices:
   for bn,w in weights.items():
    wt=w(v.co)
    if wt>0:obj.vertex_groups[bn].add([v.index],wt,'REPLACE')
 else:
  g=obj.vertex_groups.new(name=bone);g.add(list(range(len(obj.data.vertices))),1,'REPLACE')
 mod=obj.modifiers.new('Explorer skin','ARMATURE');mod.object=rig;obj.parent=rig;created.append(obj);return obj

def bevel_box(name,center,half,material,bone,bevel=.05,weights=None):
 bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_cube_add(size=2,location=center);o=bpy.context.object;o.name=name;o.scale=half
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 mod=o.modifiers.new('Soft low-poly edge','BEVEL');mod.width=bevel;mod.segments=2;bpy.ops.object.modifier_apply(modifier=mod.name)
 o.data.materials.append(material);return bind(o,bone,weights)

def ellipsoid(name,center,scale,material,bone):
 bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=1,location=center);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(material)
 for f in o.data.polygons:f.use_smooth=True
 return bind(o,bone)

def tube(name,start,end,radius,material,bone,vertices=12,r2=None):
 start,end=Vector(start),Vector(end);bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_cone_add(vertices=vertices,radius1=radius,radius2=radius if r2 is None else r2,depth=(end-start).length,location=(start+end)*.5)
 o=bpy.context.object;o.name=name;o.rotation_euler=(end-start).to_track_quat('Z','Y').to_euler();o.data.materials.append(material)
 mod=o.modifiers.new('Soft rim','BEVEL');mod.width=min(radius*.18,.025);mod.segments=2;bpy.ops.object.modifier_apply(modifier=mod.name)
 return bind(o,bone)
# Original beach clothing. Torso weights bridge the source spine and chest.
w=lambda co:max(0,min(1,(co.z-.83)/.3))
bevel_box('Explorer_Coral_Shirt',(0,0,.91),(.325,.255,.325),coral,'spine',.105,{'spine':lambda c:1-w(c),'chest':w})
tube('Explorer_Neck',(0,0,1.14),(0,0,1.32),.16,skin,'head')
bevel_box('Explorer_Shorts_Waist',(0,0,.51),(.315,.235,.105),teal,'hips',.075)
bevel_box('Explorer_Shorts_Drawstring',(0,-.246,.55),(.055,.014,.013),cream,'hips',.009)
for side,s in [('l',1),('r',-1)]:
 x=.170945*s
 tube('Explorer_Shorts_'+side,(x,0,.31),(x,0,.55),.159,teal,'upperleg.'+side)
 tube('Explorer_Shorts_Hem_'+side,(x,0,.31),(x,0,.355),.162,darkteal,'upperleg.'+side)
 tube('Explorer_Calf_'+side,(x,.015,.13),(x,-.008,.33),.098,skin,'lowerleg.'+side)
 ellipsoid('Explorer_Knee_'+side,(x,-.008,.30),(.104,.104,.105),skin,'lowerleg.'+side)
 bevel_box('Explorer_Sandal_'+side,(x,-.08,.045),(.115,.187,.045),sand,'foot.'+side,.035)
 ellipsoid('Explorer_Foot_'+side,(x,-.09,.102),(.104,.17,.072),skin,'foot.'+side)
 bevel_box('Explorer_Sandal_Strap_'+side,(x,-.10,.142),(.108,.048,.018),teal,'foot.'+side,.015)
 tube('Explorer_UpperArm_'+side,(.25*s,0,1.1068),(.465*s,.0138,1.1068),.112,skin,'upperarm.'+side)
 tube('Explorer_ShortSleeve_'+side,(.22*s,0,1.1068),(.407*s,.008,1.1068),.142,coral,'upperarm.'+side)
 tube('Explorer_Forearm_'+side,(.452*s,.0138,1.1068),(.744*s,0,1.1068),.10,skin,'lowerarm.'+side,r2=.081)
 ellipsoid('Explorer_Elbow_'+side,(.453*s,.014,1.1068),(.108,.106,.106),skin,'lowerarm.'+side)
 tube('Explorer_Wrist_'+side,(.713*s,0,1.1068),(.805*s,0,1.1068),.079,skin,'wrist.'+side)
 ellipsoid('Explorer_Hand_'+side,(.847*s,-.014,1.105),(.115,.105,.09),skin,'hand.'+side)
# Shallow low-poly sun hat, fixed to head bone, all texture-free.
tube('Explorer_Hat_Brim',(0,0,2.08),(0,0,2.145),.70,cream,'head',vertices=20,r2=.69)
tube('Explorer_Hat_Crown',(0,0,2.10),(0,0,2.43),.58,cream,'head',vertices=16,r2=.45)
tube('Explorer_Hat_Band',(0,0,2.145),(0,0,2.225),.575,teal,'head',vertices=16,r2=.547)
bevel_box('Explorer_Hat_Badge',(0,-.567,2.18),(.055,.015,.048),gold,'head',.018)
# Attach one small compass badge to the coral shirt.
ellipsoid('Explorer_Shirt_Compass',(-.16,-.258,.98),(.047,.019,.047),gold,'chest')
# Collect the two compatible KayKit animation clips, discarding imported mannequins.
clips={}
for filename,want,newname in [('Rig_Medium_General.glb','Idle_A','Idle'),('Rig_Medium_MovementBasic.glb','Walking_A','Walk')]:
 before=set(bpy.data.objects);old_actions=set(bpy.data.actions)
 bpy.ops.import_scene.gltf(filepath=str(source/'Animations/gltf/Rig_Medium'/filename))
 new_actions=[act for act in bpy.data.actions if act not in old_actions]
 print('IMPORTED_ACTIONS',[act.name for act in new_actions])
 chosen=next(act for act in new_actions if act.name==want or act.name.endswith('|'+want) or act.name.startswith(want+'_') or act.name.startswith(want+'.'))
 chosen.name=newname;chosen.use_fake_user=True;clips[newname]=chosen
 # Normalize each compatible source loop to exactly one second at 24 fps.
 begin,end=chosen.frame_range;factor=24/(end-begin)
 for fc in chosen.fcurves:
  for kp in fc.keyframe_points:
   kp.co.x=(kp.co.x-begin)*factor;kp.handle_left.x=(kp.handle_left.x-begin)*factor;kp.handle_right.x=(kp.handle_right.x-begin)*factor
 for obj in set(bpy.data.objects)-before:bpy.data.objects.remove(obj,do_unlink=True)
 for act in new_actions:
  if act!=chosen:bpy.data.actions.remove(act)
# The original swim is keyed on the source upright skeleton. Game wrapper performs the ONLY prone pitch.
for pb in rig.pose.bones:pb.rotation_mode='QUATERNION';pb.location=(0,0,0);pb.rotation_quaternion=(1,0,0,0);pb.scale=(1,1,1)
rig.animation_data_create();swim=bpy.data.actions.new('Swim');rig.animation_data.action=swim;swim.use_fake_user=True
# Breaststroke-like 1 second loop: reach -> open pull -> recover; flutter kicks alternate.
def point_bone(name,direction):
 pb=rig.pose.bones[name];rest=pb.bone.matrix_local.to_quaternion();rest_dir=rest@Vector((0,1,0));delta=rest_dir.rotation_difference(Vector(direction).normalized());pb.rotation_quaternion=rest.inverted()@delta@rest
for frame in range(1,26):
 t=(frame-1)/24;phase=2*math.pi*t;bpy.context.scene.frame_set(frame)
 for pb in rig.pose.bones:pb.location=(0,0,0);pb.rotation_quaternion=(1,0,0,0);pb.scale=(1,1,1)
 # Symmetric broad strokes, readable even at gameplay scale.
 reach=.5+.5*math.cos(phase);spread=math.sin(math.pi*reach)
 for side,s in [('l',1),('r',-1)]:
  angle=math.radians(-58+135*reach)
  point_bone('upperarm.'+side,(s*math.cos(angle),-.18,math.sin(angle)))
  # Mild elbow bend with the arms' local rest rotation: segmented shape remains smooth.
  rig.pose.bones['lowerarm.'+side].rotation_quaternion=Quaternion((1,0,0),math.radians(14+21*(1-reach)))
  rig.pose.bones['upperleg.'+side].rotation_quaternion=Quaternion((1,0,0),math.radians(12*math.sin(phase+(0 if s==1 else math.pi))))
  rig.pose.bones['lowerleg.'+side].rotation_quaternion=Quaternion((1,0,0),math.radians(10+13*max(0,math.sin(phase+(0 if s==1 else math.pi)))))
  rig.pose.bones['foot.'+side].rotation_quaternion=Quaternion((1,0,0),math.radians(-18))
 rig.pose.bones['head'].rotation_quaternion=Quaternion((1,0,0),math.radians(-13))
 rig.pose.bones['chest'].rotation_quaternion=Quaternion((1,0,0),math.radians(3*math.sin(phase)))
 for pb in rig.pose.bones:
  pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name)
  pb.keyframe_insert(data_path='location',frame=frame,group=pb.name)
for fc in swim.fcurves:
 for kp in fc.keyframe_points:kp.interpolation='LINEAR'
clips['Swim']=swim
# Export three NLA tracks only. Loop metadata is explicit for importers that honor extras.
rig.animation_data.action=None
for tr in list(rig.animation_data.nla_tracks):rig.animation_data.nla_tracks.remove(tr)
for name,act in clips.items():
 act['loop']=True;act['description']='Original Blender-keyed 1 s swim, upright local baseline; pitch game wrapper -90 degrees X once.' if name=='Swim' else 'KayKit CC0 compatible medium-rig loop.'
 track=rig.animation_data.nla_tracks.new();track.name=name;strip=track.strips.new(name,0,act);strip.action_frame_start=act.frame_range[0];strip.action_frame_end=act.frame_range[1]
 track.mute=True
# Conversion wrapper: source Blender -Y facing becomes Godot -Z after 180-degree Blender Z rotation.
root=bpy.data.objects.new('Explorer',None);bpy.context.scene.collection.objects.link(root);rig.parent=root
root.rotation_euler=(0,0,math.pi);scale=1.2/2.43;root.scale=(scale,scale,scale)
root['asset']='Tidal Sanctuary beach explorer';root['forward']='Godot -Z';root['up']='Godot +Y';root['height_m']=1.2;root['swim_wrapper_pitch_degrees']=-90.0;root['feet_origin']=True
# Embedded head image, relative basename only; no absolute work paths in the .blend.
for im in bpy.data.images:
 if im.source=='FILE':
  packed_bytes=bytes(im.packed_file.data) if im.packed_file else Path(im.filepath).read_bytes()
  im.filepath_raw='//'+(Path(im.filepath).name or im.name+'.png')
  im.pack(data=packed_bytes,data_len=len(packed_bytes))
  assert im.packed_file is not None
for o in bpy.data.objects:
 for key in list(o.keys()):
  if isinstance(o[key],str) and ('/workspace/' in o[key] or 'asset-research' in o[key]):del o[key]
# Make saved file open with friendly Idle pose; exporter reads all NLA clips.
rig.animation_data.action=clips['Idle'];bpy.context.scene.frame_set(int(clips['Idle'].frame_range[0]))
bpy.context.scene.render.fps=24;bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=25
bpy.context.scene.world.color=(.45,.45,.45)
bpy.ops.object.select_all(action='DESELECT')
for o in [root,rig,head]+created:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.data.libraries.write(str(out/'explorer.blend'),{bpy.context.scene,*clips.values()},path_remap='RELATIVE',fake_user=True,compress=False)
rig.animation_data.action=None
for tr in rig.animation_data.nla_tracks:tr.mute=False
bpy.ops.export_scene.gltf(filepath=str(out/'export/explorer.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_force_sampling=True,export_nla_strips=True,export_extras=True,export_yup=True,export_skins=True,export_all_influences=False,export_materials='EXPORT')
# Preserve saved Idle state and muted tracks; the export is independent.
for tr in rig.animation_data.nla_tracks:tr.mute=True
rig.animation_data.action=clips['Idle'];bpy.context.scene.frame_set(1)
bpy.data.libraries.write(str(out/'explorer.blend'),{bpy.context.scene,*clips.values()},path_remap='RELATIVE',fake_user=True,compress=False)
files=['Characters/gltf/Ranger.glb','Animations/gltf/Rig_Medium/Rig_Medium_General.glb','Animations/gltf/Rig_Medium/Rig_Medium_MovementBasic.glb']
manifest={'source':'KayKit Adventurers 2.0 FREE','source_license':'CC0-1.0','source_url':'https://kaylousberg.itch.io/kaykit-adventurers','source_official_url':'https://kaylousberg.com/game-assets/characters-adventurers','source_archive':{'name':'adventurers-free-2.zip','sha256':'abe48f4763fba0896bab486ee9e6d08ca6b5b3884b9601f235c8847ae94dc479','bytes':13024345},'source_files':[{'path':f,'sha256':hashlib.sha256((source/f).read_bytes()).hexdigest()} for f in files],'created_with':'Blender '+bpy.app.version_string,'original_additions':['Coral short-sleeved shirt','Teal shorts and hems','Skin limbs and sandals','Canvas sun hat and compass details','Swim action with 24 fps keyframes'],'rig_bones':len(rig.data.bones),'animations':{n:{'frames':list(ac.frame_range),'duration_seconds':(ac.frame_range[1]-ac.frame_range[0])/24} for n,ac in clips.items()},'orientation':{'godot_forward':[0,0,-1],'godot_up':[0,1,0],'feet_origin':[0,0,0],'height_m':1.2,'swim_game_wrapper_rotation_x_degrees':-90,'swim_action_contains_prone_rotation':False}}
(out/'SOURCE.json').write_text(json.dumps(manifest,indent=2))
license_files=list(source.glob('*License*'))+list(source.glob('*license*'))
if license_files:shutil.copyfile(license_files[0],out/'LICENSE-KayKit.txt')
print('EXPLORER_BUILD_COMPLETE',json.dumps(manifest))
