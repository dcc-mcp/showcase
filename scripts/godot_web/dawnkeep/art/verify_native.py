"""Read-only native reopen audit. Emits geometry statistics and privacy/relink checks."""
import bpy,json,hashlib,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
path=HERE/'dawnkeep-original.blend';bpy.ops.wm.open_mainfile(filepath=str(path))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];points=[]
for o in meshes:
 for v in o.data.vertices:points.append(tuple(round(c,5) for c in o.matrix_world@v.co))
points.sort();geometry_hash=hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest()
missing=[x.filepath for x in bpy.data.images if x.source=='FILE' and not x.packed_file and not Path(bpy.path.abspath(x.filepath)).exists()]
raw=path.read_bytes()
r={'native_reopen':'passed','blender_version':bpy.app.version_string,'mesh_count':len(meshes),'vertices':sum(len(o.data.vertices) for o in meshes),'polygons':sum(len(o.data.polygons) for o in meshes),'world_vertex_fingerprint_5dp':geometry_hash,'bounds':[[min(p[a] for p in points) for a in range(3)],[max(p[a] for p in points) for a in range(3)]],'materials':sorted([{'name':m.name,'color':[round(c,6) for c in m.diffuse_color]} for m in bpy.data.materials],key=lambda x:x['name']),'missing_external_dependencies':missing,'native_render_path':bpy.context.scene.render.filepath,'absolute_workspace_path_strings_present':any(n in raw for n in [b'/workspace/',b'/tmp/',b'/home/']),'method':'Actual Blender reopen; no MCP attribution'}
(HERE/'evidence/native-reopen.json').write_text(json.dumps(r,indent=2));print('NATIVE_REOPEN',json.dumps(r))
