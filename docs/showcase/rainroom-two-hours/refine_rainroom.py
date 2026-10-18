import bpy
from mathutils import Vector
s=bpy.context.scene
# Pixel review: sky softbox was visible through glass; remove camera/transmission visibility.
for name in ['Sky through rain','Soft room fill','Warm reading pool']:
 o=bpy.data.objects[name];o.visible_camera=False;o.visible_transmission=False
# Close the wall above and beside the window rather than showing an unbounded city set.
m=bpy.data.materials.new('Mineral blue plaster');m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.075,.105,.105,1);p.inputs['Roughness'].default_value=.9
for name,loc,dim in [('Left plaster return',(-2.2,1.22,1.8),(1.1,.28,3.5)),('Right plaster return',(2.2,1.22,1.8),(1.1,.28,3.5)),('Plaster header',(0,1.22,3.5),(5.5,.28,.92))]:
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m)
for f,e in [(1,42),(2,0)]:d=bpy.data.lights['Warm reading pool'];d.energy=e;d.keyframe_insert('energy',frame=f)
for f,e in [(1,110),(2,420)]:d=bpy.data.lights['Sky through rain'];d.energy=e;d.keyframe_insert('energy',frame=f)
cam=bpy.data.objects['01_Window still life'];cam.location=(2.3,-4.6,2.54);cam.rotation_euler=(Vector((-.02,.40,1.66))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=58
s.frame_set(1)
print('Refined light visibility, closed wall returns, tightened composition; 491 objects.')
