# Portable parameterized copy of the executed recipe.
# Invoke through the official in-host MCP script tool with explicit context paths.
# Path-only adaptation is not represented as a new executed run.
"""Read-only inspection after a separate typed open_scene call; never mutates bpy."""
import bpy,json,hashlib,math
from pathlib import Path
ROOT=Path(evidence_directory)
raw=(ROOT/'recipe-data.json').read_bytes();assert hashlib.sha256(raw).hexdigest()=='7e26853dd601e62a9462d77e4a13960fc6322d92365f5b6ccba5a5d2fa302391'
data=json.loads(raw);expected=[o for g in data['groups'].values() for o in g]
assert set(o.name for o in bpy.context.scene.objects)==set(o['name'] for o in expected)
result={'passed':False,'scope':'read-only saved native nine-asset geometry/material inspection','objects':0,'vertices':0,'faces':0,'groups':{},'materials':{}}
for group,items in data['groups'].items():
 points=[];expected_points=[];error=0
 for target in items:
  obj=bpy.data.objects[target['name']];assert obj.type=='MESH'
  assert len(obj.data.vertices)==len(target['vertices']) and len(obj.data.polygons)==len(target['faces'])
  assert [tuple(p.vertices) for p in obj.data.polygons]==[tuple(f) for f in target['faces']]
  assert [m.name for m in obj.data.materials]==target['materials']
  assert [p.material_index for p in obj.data.polygons]==target['material_indices']
  offset=data['display_offsets'][group]
  assert obj.parent is None
  assert max(abs(a-b) for a,b in zip(obj.location,offset))<1e-6
  expected_matrix=[[float(i==j) for j in range(4)] for i in range(4)]
  for axis in range(3):expected_matrix[axis][3]=offset[axis]
  assert max(abs(obj.matrix_world[i][j]-expected_matrix[i][j]) for i in range(4) for j in range(4))<1e-6
  for actual,vertex in zip(obj.data.vertices,target['vertices']):
   error=max(error,max(abs(a-b) for a,b in zip(actual.co,vertex)));points.append(tuple(obj.matrix_world@actual.co));expected_points.append(tuple(vertex[i]+offset[i] for i in range(3)))
  result['objects']+=1;result['vertices']+=len(obj.data.vertices);result['faces']+=len(obj.data.polygons)
 assert error<1e-6
 actual_bounds=[[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]]
 expected_bounds=[[min(p[i] for p in expected_points) for i in range(3)],[max(p[i] for p in expected_points) for i in range(3)]]
 assert max(abs(actual_bounds[j][i]-expected_bounds[j][i]) for j in range(2) for i in range(3))<2e-5
 result['groups'][group]={'objects':len(items),'max_coordinate_error':error,'bounds':[[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]]}
for name,expected in data['materials'].items():
 m=bpy.data.materials[name];assert m.use_nodes;bsdf=m.node_tree.nodes['Principled BSDF']
 assert max(abs(a-b) for a,b in zip(m.diffuse_color,expected['color']))<1e-6
 assert max(abs(a-b) for a,b in zip(bsdf.inputs['Base Color'].default_value,expected['color']))<1e-6
 for key,field in [('Roughness','roughness'),('Metallic','metallic')]:assert abs(bsdf.inputs[key].default_value-expected[field])<1e-6
 if expected['emission_strength']:
  assert abs(bsdf.inputs['Emission Strength'].default_value-expected['emission_strength'])<1e-6
  assert max(abs(a-b) for a,b in zip(bsdf.inputs['Emission Color'].default_value,expected['color']))<1e-6
 else:
  # Original recipe leaves non-emissive sockets at defaults. White × zero is zero emission.
  assert abs(bsdf.inputs['Emission Strength'].default_value)<1e-6
 result['materials'][name]={'checked':True}
assert (result['objects'],result['vertices'],result['faces'])==(64,3674,2655)
result['passed']=True
(ROOT/'rebuilt-native-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
