import bpy
# Eliminate coplanar overlapping wall slabs; four abutting rectangular returns.
for n in ['Left plaster return','Right plaster return']:
 o=bpy.data.objects[n];o.dimensions=(5,.28,4.06);o.location=( -4.15 if n.startswith('Left') else 4.15,1.22,1.03)
o=bpy.data.objects['Plaster header'];o.dimensions=(13,.28,3.0);o.location=(0,1.22,4.56)
bpy.context.scene.frame_set(1)
print('Window wall rebuilt as non-overlapping header and side returns; no coplanar overlap.')
o=bpy.data.objects['Wall below sill'];o.dimensions=(3.3,.28,3.0);o.location=(0,1.22,-.56)
print('Closed under-sill strip and extended opaque wall below desk.')
