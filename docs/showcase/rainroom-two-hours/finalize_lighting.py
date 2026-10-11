import bpy
s=bpy.context.scene
for n in ['Left plaster return','Right plaster return']:
 o=bpy.data.objects[n];o.dimensions.x=5;o.location.x=-4 if n.startswith('Left') else 4
bpy.data.objects['Plaster header'].dimensions.x=13
bg=s.world.node_tree.nodes.get('Background')
for f,c,e in [(1,(.12,.18,.28,1),.12),(2,(.55,.70,.85,1),.70)]:
 bg.inputs[0].default_value=c;bg.inputs[0].keyframe_insert('default_value',frame=f);bg.inputs[1].default_value=e;bg.inputs[1].keyframe_insert('default_value',frame=f)
for m in bpy.data.materials:
 if m.name.startswith('Distant lit window'):
  p=m.node_tree.nodes.get('Principled BSDF');v=p.inputs['Emission Strength'].default_value
  for f,e in [(1,v),(2,.025)]:p.inputs['Emission Strength'].default_value=e;p.inputs['Emission Strength'].keyframe_insert('default_value',frame=f)
s.frame_set(1)
print('Final wall coverage and morning city/world light state updated.')
