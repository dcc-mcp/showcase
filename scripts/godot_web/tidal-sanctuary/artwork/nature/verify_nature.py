"""Reopen the saved native foliage library in a separate Blender process."""
import argparse, json, sys, hashlib
from pathlib import Path
import bpy
from mathutils import Vector
args=argparse.ArgumentParser();args.add_argument('--blend',type=Path,required=True);args.add_argument('--output',type=Path,required=True)
a=args.parse_args(sys.argv[sys.argv.index('--')+1:]);bpy.ops.wm.open_mainfile(filepath=str(a.blend));a.output.parent.mkdir(parents=True,exist_ok=True)
assert not bpy.data.libraries,'Unexpected linked native library'
images=[]
for image in bpy.data.images:
 if image.source=='FILE':
  assert image.packed_file and image.filepath.startswith('//'), 'Texture must be packed and relative'
  images.append({'name':image.name,'packed':True,'filepath':image.filepath})
assets=[]
for c in bpy.data.collections:
 if not c.objects:continue
 assert len(c.objects)==1 and c.objects[0].type=='MESH', 'One standalone mesh per nature asset'
 o=c.objects[0];coords=[o.matrix_world@Vector(v) for v in o.bound_box]
 assets.append({'name':c.name,'mesh':o.name,'triangles':sum(len(p.vertices)-2 for p in o.data.polygons),'bounds':[[min(v[k] for v in coords) for k in range(3)],[max(v[k] for v in coords) for k in range(3)]]})
assert {'palm-a','palm-b','understory-a','understory-b','bush-a','shore-stone-a','shore-stone-b'}.issubset({x['name'] for x in assets})
a.output.write_text(json.dumps({'source':a.blend.name,'sha256':hashlib.sha256(a.blend.read_bytes()).hexdigest(),'blender':bpy.app.version_string,'separate_process_native_reopen':True,'linked_libraries':0,'images':images,'assets':assets},indent=2)+'\n')
