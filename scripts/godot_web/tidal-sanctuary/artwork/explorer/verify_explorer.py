"""Run in a separate Blender process to reopen, verify, and render the authored explorer."""
import bpy,sys,argparse,json,math
from pathlib import Path
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=a.blend)
rig=bpy.data.objects['ExplorerRig'];root=bpy.data.objects['Explorer'];scene=bpy.context.scene
for tr in rig.animation_data.nla_tracks:tr.mute=True
meshes=[o for o in scene.objects if o.type=='MESH']
report={'blender_version':bpy.app.version_string,'opened_in_fresh_process':True,'armatures':len([o for o in scene.objects if o.type=='ARMATURE']),'bones':len(rig.data.bones),'mesh_count':len(meshes),'images':[{'name':im.name,'packed':bool(im.packed_file),'filepath':im.filepath} for im in bpy.data.images if im.source=='FILE'],'actions':{},'warnings':[]}
def bounds():
 deps=bpy.context.evaluated_depsgraph_get();verts=[]
 for obj in meshes:
  ev=obj.evaluated_get(deps);m=ev.to_mesh();verts.extend(ev.matrix_world@v.co for v in m.vertices);ev.to_mesh_clear()
 return {'min':[min(v[k] for v in verts) for k in range(3)],'max':[max(v[k] for v in verts) for k in range(3)]}
for name in ['Idle','Walk','Swim']:
 act=bpy.data.actions[name];rig.animation_data.action=act
 samples=[]
 for f in [act.frame_range[0],sum(act.frame_range)/2,act.frame_range[1]]:
  scene.frame_set(int(f),subframe=f-int(f));bpy.context.view_layer.update();samples.append({'frame':f,'bounds_blender':bounds(),'left_hand_world':list(root.matrix_world@rig.pose.bones['hand.l'].matrix.translation),'right_hand_world':list(root.matrix_world@rig.pose.bones['hand.r'].matrix.translation)})
 report['actions'][name]={'fcurves':len(act.fcurves),'keyframes':sum(len(fc.keyframe_points) for fc in act.fcurves),'frame_range':list(act.frame_range),'samples':samples}
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1);bpy.context.view_layer.update();report['idle_bounds_blender']=bounds()
report['absolute_image_paths']=any((im.filepath.startswith('/') and not im.filepath.startswith('//')) for im in bpy.data.images if im.source=='FILE')
report['source_path_hygiene_passed']=not any(token in Path(a.blend).read_bytes() for token in [b'/workspace/',b'asset-research',b'/home/agent'])
(out/'reopen-check.json').write_text(json.dumps(report,indent=2))
# CPU Cycles render requires no display server or external adapter.
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=False;scene.render.resolution_x=700;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.69,.76,.72,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
# Do not embed the opened native file's absolute path in render metadata.
scene.render.use_stamp_filename=False
scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
bpy.ops.object.camera_add(location=(-2.3,3.5,2.1));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.60))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.66;scene.camera=cam
for loc,power,size in [((-3,4,5),450,4),((3,-2,4),300,3)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(Vector((0,0,.6))-o.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(out/'preview-idle.png');bpy.ops.render.render(write_still=True)
rig.animation_data.action=bpy.data.actions['Swim'];scene.frame_set(7)
# The game-space X=-90 pitch is equivalent to Blender X=-90 on a new wrapper above the baked Y-facing asset.
pivot=bpy.data.objects.new('Preview_Game_Swim_Pivot',None);scene.collection.objects.link(pivot);root.parent=pivot;pivot.rotation_euler.x=-math.pi/2;pivot.location=(0,-.6,.55)
cam.location=(-2.3,3,2.8);cam.rotation_euler=(Vector((0,0,.55))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.9
scene.render.filepath=str(out/'preview-swim.png');bpy.ops.render.render(write_still=True)
print('REOPEN_CHECK_COMPLETE',out/'reopen-check.json')

# Remove text/EXIF metadata losslessly; all compressed pixel data stays unchanged.
import struct
for image_path in [out/'preview-idle.png',out/'preview-swim.png']:
 raw=image_path.read_bytes();clean=raw[:8];pos=8
 while pos<len(raw):
  size=struct.unpack_from('>I',raw,pos)[0];kind=raw[pos+4:pos+8]
  if kind not in (b'tEXt',b'zTXt',b'iTXt',b'eXIf'):clean+=raw[pos:pos+12+size]
  pos+=12+size
 assert pos==len(raw)
 image_path.write_bytes(clean)
