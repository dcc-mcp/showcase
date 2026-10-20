# Portable parameterized copy of the executed recipe.
# Invoke through the official in-host MCP script tool with explicit context paths.
# Path-only adaptation is not represented as a new executed run.
"""Run via the official in-host MCP script tool. Numerical calculation only.
No import of bpy, native object mutation, save, export, render or subprocess.
The original numerical recipe is retained, with six I/O helpers replaced by
in-memory data collectors. Blender mathutils supplies original tessellation and
matrix arithmetic; final native creation is a separate typed-tool stage.
"""
import ast, hashlib, json, math, random
from pathlib import Path
from types import SimpleNamespace
from mathutils import Vector, Euler, Matrix, Quaternion
from mathutils.geometry import tessellate_polygon
SOURCE = Path(source_recipe_path)
OUTPUT = Path(recipe_data_path)
EXPECTED_SOURCE_SHA = '3769bfe07a1d8b44a5ac796632a4e360a95a6b1e3b95c320f6e8ee5f49298dd4'
raw=SOURCE.read_bytes()
assert hashlib.sha256(raw).hexdigest()==EXPECTED_SOURCE_SHA
source=raw.decode().split('# Keep the editable source art presentation')[0]
# Ignore native imports/path setup/deletion; start at original material table.
source=source[source.index('M={}'):]
objects=[]; materials={}; groups={}; names={}
class DataObject:
    def __init__(self,name,vertices,faces,mats,indices):
        count=names.get(name,0);names[name]=count+1
        self.name=name if not count else f'{name}.{count:03d}'
        self.vertices=[tuple(v) for v in vertices];self.faces=[tuple(f) for f in faces]
        self.materials=list(mats);self.indices=list(indices) if indices else [0]*len(faces)
        assert len(self.indices)==len(self.faces)
        self._location=Vector((0,0,0));self._euler=Euler((0,0,0));self.rotation_mode='XYZ';self.rotation_quaternion=Quaternion()
        self.selected=False
    @property
    def location(self):return self._location
    @location.setter
    def location(self,value):self._location=Vector(value)
    @property
    def rotation_euler(self):return self._euler
    @rotation_euler.setter
    def rotation_euler(self,value):self._euler=Euler(value)
    def select_set(self,value):self.selected=bool(value)
    def transformed_vertices(self):
        rotation=self.rotation_quaternion.to_matrix() if self.rotation_mode=='QUATERNION' else self._euler.to_matrix()
        return [tuple(rotation@Vector(v)+self.location) for v in self.vertices]
def mat(name,hex,metal=0,emit=0):
    color=[((int(hex[i:i+2],16)/255+.055)/1.055)**2.4 for i in (0,2,4)]
    value={'name':name,'color':color+[1.0],'roughness':.84,'metallic':metal,'emission_strength':emit}
    materials[name]=value;namespace['M'][name]=value;return value
def mesh(name,verts,faces,material_names,indices=None):
    obj=DataObject(name,verts,faces,material_names,indices);objects.append(obj);return obj
def select_all(action):
    assert action in ('SELECT','DESELECT')
    for obj in objects:obj.selected=action=='SELECT'
def join():
    selected=[o for o in objects if o.selected];assert selected
    active=fake_bpy.context.view_layer.objects.active;assert active in selected
    assert tuple(active.location)==(0.0,0.0,0.0) and tuple(active.rotation_euler)==(0.0,0.0,0.0) and active.rotation_mode=='XYZ', 'Only fixed-recipe identity-active joins are supported'
    vertices=[];faces=[];mats=[];indices=[]
    for obj in selected:
        offset=len(vertices);vertices.extend(obj.transformed_vertices())
        faces.extend(tuple(i+offset for i in face) for face in obj.faces)
        for material in obj.materials:
            if material not in mats:mats.append(material)
        indices.extend(mats.index(obj.materials[i]) for i in obj.indices)
    # Original join retains active-object name. Bake transforms to group space.
    active.vertices=vertices;active.faces=faces;active.materials=mats;active.indices=indices
    active.location=(0,0,0);active.rotation_mode='XYZ';active.rotation_euler=(0,0,0)
    objects[:]=[o for o in objects if o not in selected or o is active]
def save_group(name,start):
    selected=[o for o in objects if o not in start];assert selected
    assert name not in groups
    groups[name]=[{'name':o.name,'vertices':o.transformed_vertices(),'faces':o.faces,
                   'materials':o.materials,'material_indices':o.indices} for o in selected]
    return SimpleNamespace(objects=selected)
fake_bpy=SimpleNamespace(context=SimpleNamespace(scene=SimpleNamespace(objects=objects),
    view_layer=SimpleNamespace(objects=SimpleNamespace(active=None))),
    ops=SimpleNamespace(object=SimpleNamespace(select_all=select_all,join=join)))
namespace={'__builtins__':__builtins__,'math':math,'random':random,'Vector':Vector,
           'tessellate_polygon':tessellate_polygon,'bpy':fake_bpy,
           'mat':mat,'mesh':mesh,'save_group':save_group}
tree=ast.parse(source)
replaced={'mat','mesh','collection','move_to','save_group'}
tree.body=[node for node in tree.body if not isinstance(node,ast.FunctionDef) or node.name not in replaced]
# Ensure no real native I/O survived the bounded source extraction.
filtered=ast.unparse(tree)
for forbidden in ['export_scene','save_as_mainfile','render.render','subprocess','bpy.data','bpy.ops.object.delete']:
    assert forbidden not in filtered,forbidden
random.seed(18026)
exec(compile(tree,str(SOURCE),'exec'),namespace)
assert set(groups)=={'world','shrine','tower_sunbow','tower_ember','tower_frost','tower_storm','standard','watchwood_tree','moonfern'}
for group,items in groups.items():
    for obj in items:
        assert all(math.isfinite(c) for v in obj['vertices'] for c in v)
        assert len(obj['vertices'])<=30000 and len(obj['faces'])<=50000
        assert all(3<=len(face)<=128 and len(set(face))==len(face) and all(0<=i<len(obj['vertices']) for i in face) for face in obj['faces'])
        assert len(obj['material_indices'])==len(obj['faces'])
        assert all(0<=i<len(obj['materials']) for i in obj['material_indices'])
result={'scope':'pure numerical source calculation; no actual bpy scene objects created',
        'source_sha256':EXPECTED_SOURCE_SHA,'seed':18026,'materials':materials,'groups':groups,
        'display_offsets':{'shrine':[13,-5,0],'tower_sunbow':[-5,-7,0],'tower_ember':[-1,-7,0],
          'tower_frost':[3,-7,0],'tower_storm':[7,-7,0],'standard':[11.2,-7.9,0],
          'watchwood_tree':[-15,9,0],'moonfern':[-14,-5,0],'world':[0,0,0]}}
encoded=json.dumps(result,sort_keys=True,indent=2).encode();OUTPUT.write_bytes(encoded)
print(json.dumps({'path':str(OUTPUT),'sha256':hashlib.sha256(encoded).hexdigest(),
      'groups':len(groups),'objects':sum(len(v) for v in groups.values()),
      'vertices':sum(len(o['vertices']) for g in groups.values() for o in g),
      'faces':sum(len(o['faces']) for g in groups.values() for o in g),
      'materials':len(materials),'native_scene_mutation':False}))
