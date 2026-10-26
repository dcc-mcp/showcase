# Portable parameterized copy of the executed recipe.
# Invoke through the official in-host MCP script tool with explicit context paths.
# Path-only adaptation is not represented as a new executed run.
"""Only the confirmed typed per-face material-index gap (Blender issue #316).
All names, face counts, slots and indices are validated before any mutation.
This does not create geometry/materials, export, save, render or spawn processes.
"""
import bpy, json, hashlib
from pathlib import Path
SOURCE=Path(recipe_data_path)
raw=SOURCE.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='7e26853dd601e62a9462d77e4a13960fc6322d92365f5b6ccba5a5d2fa302391'
data=json.loads(raw);targets=[o for group in data['groups'].values() for o in group]
assert {o.name for o in bpy.context.scene.objects}=={o['name'] for o in targets}
validated=[]
for target in targets:
    obj=bpy.data.objects[target['name']]
    assert obj.type=='MESH' and len(obj.data.polygons)==len(target['faces'])
    assert [tuple(p.vertices) for p in obj.data.polygons]==[tuple(f) for f in target['faces']]
    assert [m.name for m in obj.data.materials]==target['materials']
    indices=target['material_indices']
    assert len(indices)==len(obj.data.polygons) and all(type(i) is int and 0<=i<len(obj.data.materials) for i in indices)
    validated.append((obj,indices,[p.material_index for p in obj.data.polygons]))
try:
    for obj,indices,_ in validated:
        for polygon,index in zip(obj.data.polygons,indices):polygon.material_index=index
    assert all([p.material_index for p in obj.data.polygons]==indices for obj,indices,_ in validated)
except Exception:
    for obj,_,before in validated:
        for polygon,index in zip(obj.data.polygons,before):polygon.material_index=index
    assert all([p.material_index for p in obj.data.polygons]==before for obj,_,before in validated), 'Material-index rollback failed'
    raise
print(json.dumps({'scope':'explicit polygon material indices only','objects':len(validated),
                  'faces':sum(len(indices) for _,indices,_ in validated),'readback_equal':True}))
