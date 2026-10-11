"""Read raw CAD mesh transfer, before presentation bevel evaluation. MIT."""
import bpy,json
from pathlib import Path
out=Path(__file__).resolve().parent
source=json.loads((out/'cad_meshes.json').read_text());names={o['name'] for o in source};parts=[o for o in bpy.context.scene.objects if o.name in names]
coords=[o.matrix_world@v.co for o in parts for v in o.data.vertices]
val={'cad_mesh_objects':len(parts),'raw_mesh_vertices':sum(len(o.data.vertices) for o in parts),'raw_mesh_triangles':sum(len(o.data.polygons) for o in parts),'bbox_min_m':[min(v[k] for v in coords) for k in range(3)],'bbox_max_m':[max(v[k] for v in coords) for k in range(3)],'source_vertices':sum(len(o['vertices_mm']) for o in source),'source_triangles':sum(len(o['faces']) for o in source),'scope':'Raw mesh transfer only; presentation bevel modifiers are not evaluated.'}
assert val['cad_mesh_objects']==len(source)
assert val['raw_mesh_vertices']==val['source_vertices']
assert val['raw_mesh_triangles']==val['source_triangles']
(out/'render-transfer.json').write_text(json.dumps(val,indent=2));print(json.dumps(val))
