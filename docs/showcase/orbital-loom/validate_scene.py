import bpy,json,os,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
P=os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=P+'/orbital-loom.blend')
s=bpy.context.scene
hoops=[bpy.data.objects['Precision hoop '+str(i)] for i in range(3)]
posts=[o for o in s.objects if o.name.startswith('Pedestal bearing support')]
collisions=[];zmin=99;xmax=0;transforms={}
def tree(o,dg):
 eo=o.evaluated_get(dg);m=eo.to_mesh();v=[eo.matrix_world@x.co for x in m.vertices];f=[list(p.vertices) for p in m.polygons];t=BVHTree.FromPolygons(v,f);eo.to_mesh_clear();return t,v
for frame in range(1,361):
 s.frame_set(frame);dg=bpy.context.evaluated_depsgraph_get();h=[tree(o,dg) for o in hoops]
 zmin=min(zmin,*[v.z for _,vs in h for v in vs]);xmax=max(xmax,*[abs(v.x) for _,vs in h for v in vs])
 if frame%5==1:
  for i in range(3):
   for j in range(i):
    if h[i][0].overlap(h[j][0]):collisions.append([frame,hoops[i].name,hoops[j].name])
   for p in posts:
    if h[i][0].overlap(tree(p,dg)[0]):collisions.append([frame,hoops[i].name,p.name])
 if frame in (1,90,180,270,360):transforms[str(frame)]={o.name:[round(x,5) for row in o.matrix_world for x in row] for o in hoops}
drivers=[{'object':o.name,'valid':f.driver.is_valid,'expression':f.driver.expression} for o in s.objects if o.animation_data for f in o.animation_data.drivers]
r={'blender':bpy.app.version_string,'objects':len(s.objects),'frame_range':[1,360],'fps':24,'duration_seconds':15,'minimum_animated_hoop_z':zmin,'plinth_top_z':.446,'minimum_hoop_to_plinth_vertical_clearance':zmin-.446,'maximum_absolute_hoop_x':xmax,'pillar_inner_x':1.75-.115,'minimum_hoop_to_pillar_horizontal_clearance':1.75-.115-xmax,'bvh_test_sample_step':5,'bvh_hoop_pair_and_hoop_pillar_intersections':collisions,'drivers':drivers,'sample_world_transforms':transforms}
assert not collisions,collisions
assert zmin>.446
assert all(x['valid'] for x in drivers)
assert transforms['1']!=transforms['90']
open(P+'/scene-validation.json','w').write(json.dumps(r,indent=2))
s.frame_set(1)
print(json.dumps({k:v for k,v in r.items() if k!='sample_world_transforms'}))
