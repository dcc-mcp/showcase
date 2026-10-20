# Portable parameterized copy of the executed recipe.
# Invoke through the official in-host MCP script tool with explicit context paths.
# Path-only adaptation is not represented as a new executed run.
"""Read-only verification of one already-imported GLB; group comes from MCP context."""
import bpy,json,hashlib
from pathlib import Path
from mathutils.kdtree import KDTree
ROOT=Path(evidence_directory)
raw=(ROOT/'recipe-data.json').read_bytes();assert hashlib.sha256(raw).hexdigest()=='7e26853dd601e62a9462d77e4a13960fc6322d92365f5b6ccba5a5d2fa302391'
data=json.loads(raw);assert group in data['groups'];expected=data['groups'][group]
assert {o.name for o in bpy.context.scene.objects}=={o['name'] for o in expected}
checks=[]
for target in expected:
 obj=bpy.data.objects[target['name']];assert obj.type=='MESH'
 actual=[tuple(obj.matrix_world@v.co) for v in obj.data.vertices];planned=target['vertices']
 def nearest_error(left,right):
  tree=KDTree(len(right))
  for i,v in enumerate(right):tree.insert(v,i)
  tree.balance();return max(tree.find(v)[2] for v in left)
 error=max(nearest_error(actual,planned),nearest_error(planned,actual));assert error<2e-5,(obj.name,error)
 # glTF may reorder slots and triangulate faces; every expected material remains.
 assert {m.name for m in obj.data.materials}==set(target['materials'])
 checks.append({'name':obj.name,'max_symmetric_point_error':error,'vertices_after_gltf_split':len(actual),'materials':len(obj.data.materials)})
r={'group':group,'passed':True,'scope':'actual native GLB reimport; world-space geometry and material-presence check','objects':checks}
(ROOT/('import-readback-'+group+'.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
