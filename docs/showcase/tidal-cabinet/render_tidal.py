"""Render measured FreeCAD tessellation; no replacement model. MIT."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
out=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
materials={}
def material(key,rgb):
 m=bpy.data.materials.new(key);m.diffuse_color=(*rgb,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Roughness'].default_value=.32
 if key=='wood':
  n=m.node_tree.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=6;n.inputs['Detail'].default_value=3
  tex=m.node_tree.nodes.new('ShaderNodeTexCoord');v=m.node_tree.nodes.new('ShaderNodeVectorMath');v.operation='MULTIPLY';v.inputs[1].default_value=(38,38,2)
  ramp=m.node_tree.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.18;ramp.color_ramp.elements[0].color=(.11,.042,.012,1);ramp.color_ramp.elements[1].position=.85;ramp.color_ramp.elements[1].color=(.47,.25,.095,1)
  l=m.node_tree.links;l.new(tex.outputs['Generated'],v.inputs[0]);l.new(v.outputs[0],n.inputs[0]);l.new(n.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],p.inputs['Base Color'])
 if key=='brass':p.inputs['Metallic'].default_value=.8;p.inputs['Roughness'].default_value=.26
 return m
for key,rgb in [('wood',(.52,.29,.13)),('teal',(.035,.16,.17)),('brass',(.68,.49,.20)),('felt',(.16,.20,.18)),('dark',(.02,.026,.029)),('glass',(.05,.19,.22))]:materials[key]=material(key,rgb)
parts=[]
for item in json.loads((out/'cad_meshes.json').read_text()):
 mesh=bpy.data.meshes.new(item['name']);mesh.from_pydata([[v/1000 for v in p] for p in item['vertices_mm']],[],item['faces']);mesh.update();obj=bpy.data.objects.new(item['name'],mesh);bpy.context.collection.objects.link(obj);parts.append(obj)
 rgb=item['rgb'];key='wood' if rgb[0]==.52 else 'teal' if rgb[0]==.07 and rgb[1]==.23 else 'brass' if rgb[0]==.68 else 'felt' if rgb[0]==.20 else 'glass' if rgb[0]==.10 else 'dark';mesh.materials.append(materials[key])
 if not any(s in obj.name for s in ['Lens','Reed','Flute','Foot','Shoe']):
  b=obj.modifiers.new('Micro edge finish','BEVEL');b.width=.0015;b.segments=3
 else:
  for f in mesh.polygons:f.use_smooth=True
floor=material('warm cyclorama',(.47,.43,.36));bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.003));bpy.context.object.name='Studio ground';bpy.context.object.data.materials.append(floor)
def area(name,loc,power,size):
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((.5,.15,.5))-o.location).to_track_quat('-Z','Y').to_euler()
area('Key softbox',(-2,-2,3.3),350,3);area('Rim softbox',(2,1.5,2.8),450,2);area('Front fill',(1,-3,1.4),110,2)
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=96;s.cycles.use_denoising=True;s.world.color=(.3,.3,.3);s.render.resolution_x=1600;s.render.resolution_y=1400;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX'
bpy.ops.object.camera_add(location=(1.85,-2.5,1.65));cam=bpy.context.object;cam.rotation_euler=(Vector((.53,.17,.53))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.62;s.camera=cam
s.render.image_settings.file_format='PNG';s.render.filepath=str(out/'hero.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'tidal-studio.blend'));bpy.ops.render.render(write_still=True)
cam.location=(1.12,-1.8,1.05);cam.rotation_euler=(Vector((.65,.05,.68))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.88;s.render.resolution_x=1400;s.render.resolution_y=1400;s.render.filepath=str(out/'detail.png');bpy.ops.render.render(write_still=True)
for o in parts:
 if 'Drawer' in o.name:o.location.y-=.20
 elif 'Shutter' in o.name:o.location+=Vector((-.15,-.14,0))
 elif o.name in ['Crown','ServiceTray']:o.location.z+=.16
 elif o.name=='LeftCheek':o.location.x-=.17
 elif o.name=='RightCheek':o.location.x+=.17
cam.location=(1.95,-2.8,1.9);cam.rotation_euler=(Vector((.5,.08,.58))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.95;s.render.resolution_x=1600;s.render.resolution_y=1400;s.render.filepath=str(out/'exploded.png');bpy.ops.render.render(write_still=True)
print('RENDER_COMPLETE')
