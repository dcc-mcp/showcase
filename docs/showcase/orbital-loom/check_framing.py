import bpy,json,os,numpy as np
P=os.path.dirname(os.path.abspath(__file__));bpy.ops.wm.open_mainfile(filepath=P+'/orbital-loom.blend');s=bpy.context.scene
objects=[o for o in s.objects if o.type in ('MESH','FONT') and o.name!='Gallery cyclorama'];s.frame_set(1);dg=bpy.context.evaluated_depsgraph_get();vertices={}
for o in objects:
 eo=o.evaluated_get(dg);m=eo.to_mesh();a=np.ones((len(m.vertices),4));a[:,:3]=[tuple(v.co) for v in m.vertices];vertices[o.name]=a;eo.to_mesh_clear()
bounds=[1.,1.,0.,0.];worst=[];minimum={'pixels':9999}
for f in range(1,361):
 s.frame_set(f);dg=bpy.context.evaluated_depsgraph_get();bpy.context.view_layer.update();cam=s.camera.evaluated_get(dg)
 proj=np.array(cam.calc_matrix_camera(dg,x=960,y=540));view=np.array(cam.matrix_world.inverted())
 for o in objects:
  m=proj@view@np.array(o.evaluated_get(dg).matrix_world);clip=vertices[o.name]@m.T;uv=clip[:,:2]/clip[:,3,None]*.5+.5
  b=[float(uv[:,0].min()),float(uv[:,1].min()),float(uv[:,0].max()),float(uv[:,1].max())]
  bounds=[min(bounds[0],b[0]),min(bounds[1],b[1]),max(bounds[2],b[2]),max(bounds[3],b[3])]
  margin=min(b[0]*960,b[1]*540,(1-b[2])*960,(1-b[3])*540)
  if margin<minimum['pixels']:minimum={'pixels':margin,'frame':f,'object':o.name}
  if margin<0:worst.append({'frame':f,'object':o.name,'bounds':b})
r={'method':'All evaluated mesh vertices (fixed topology) projected through the evaluated constrained camera on each of 360 frames; studio plane and lights excluded. Initial conservative bounding-box corners produced false positives on the round plinth, so actual surface vertices were tested.','normalized_bounds':bounds,'minimum_canvas_margin':minimum,'frames_outside_canvas':worst}
open(P+'/framing-validation.json','w').write(json.dumps(r,indent=2));print(json.dumps(r));assert not worst,r
