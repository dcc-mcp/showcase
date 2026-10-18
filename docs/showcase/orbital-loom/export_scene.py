import bpy,os,json
P=os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=P+'/orbital-loom.blend')
s=bpy.context.scene;names=['Gimbal_%d_driver'%i for i in range(3)];sample={name:[] for name in names}
for f in range(1,361):
 s.frame_set(f)
 for name in names:sample[name].append(tuple(bpy.data.objects[name].rotation_euler))
for i,name in enumerate(names):
 o=bpy.data.objects[name];o.driver_remove('rotation_euler',0 if i%2==0 else 2)
 for f,v in enumerate(sample[name],1):o.rotation_euler=v;o.keyframe_insert(data_path='rotation_euler',frame=f)
 for fc in o.animation_data.action.fcurves:
  for k in fc.keyframe_points:k.interpolation='LINEAR'
s.frame_set(1)
bpy.ops.object.select_all(action='DESELECT')
for o in s.objects:
 if o.type in ('MESH','EMPTY') and o.name not in ('Gallery cyclorama','Camera focus'):o.select_set(True)
bpy.ops.export_scene.gltf(filepath=P+'/orbital-loom-animated.glb',export_format='GLB',use_selection=True,export_animations=True,export_frame_range=True,export_force_sampling=True,export_cameras=False,export_lights=False)
size=os.path.getsize(P+'/orbital-loom-animated.glb')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=P+'/orbital-loom-animated.glb')
anim=[o for o in bpy.context.scene.objects if o.animation_data and (o.animation_data.action or len(o.animation_data.nla_tracks))]
r={'export':'GLB','bytes':size,'reimport_objects':len(bpy.context.scene.objects),'animated_objects':[o.name for o in anim],'baked_driver_frames':360,'excluded':['studio plane','lights','camera','native text'],'native_blend_preserves_live_drivers':True}
pose_samples={}
for frame in (1,90,180,270,360):
 bpy.context.scene.frame_set(frame)
 pose_samples[str(frame)]={o.name:[round(v,6) for row in o.matrix_world for v in row] for o in anim}
r['reimport_pose_samples']=pose_samples
r['reimport_animation_changes']=pose_samples['1']!=pose_samples['90']
expected_names = set(names)
observed_names = {o.name for o in anim}
assert len(anim) == len(expected_names) and observed_names == expected_names, {
    "expected_animated_objects": sorted(expected_names),
    "observed_animated_objects": sorted(observed_names),
}
assert size > 100000 and r["reimport_animation_changes"], r
open(P+'/export-validation.json','w').write(json.dumps(r,indent=2));print(json.dumps(r))
