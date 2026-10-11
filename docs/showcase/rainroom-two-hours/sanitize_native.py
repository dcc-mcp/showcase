import bpy,json,pathlib
for screen in bpy.data.screens:
 for area in screen.areas:
  for space in area.spaces:
   if space.type=='FILE_BROWSER' and space.params:
    space.params.directory=b'.'*1023
    space.params.directory=b'//'
for im in bpy.data.images:
 if im.packed_file:im.filepath='//textures/postcard.png'
bpy.context.scene.render.filepath='//rainroom.png'
bpy.context.preferences.filepaths.save_version=0
p=pathlib.Path(bpy.data.filepath)
bpy.ops.wm.save_as_mainfile(filepath=str(p),compress=False)
b=p.read_bytes();patterns=['/'+name+'/' for name in ('workspace','home','tmp')]+['ghp_','github_pat_','BEGIN PRIVATE KEY']
counts={k:b.count(k.encode()) for k in patterns}
print(json.dumps({'native_uncompressed_private_pattern_counts':counts}))
if any(counts.values()):raise RuntimeError('Privacy audit requires investigation')
bpy.ops.wm.save_as_mainfile(filepath=str(p),compress=True)
