"""Generate an ordered tool-call plan; execute with your connected official MCP client.
This module does not connect, start Blender, or execute any native operation.
Review results after every call; validation failures must stop execution.
"""
import hashlib,json,pathlib,sys

def build_plan(root):
 ROOT=pathlib.Path(root).resolve()
 raw=(ROOT/'recipes'/'recipe-data.json').read_bytes()
 assert hashlib.sha256(raw).hexdigest()=='7e26853dd601e62a9462d77e4a13960fc6322d92365f5b6ccba5a5d2fa302391'
 data=json.loads(raw);out=ROOT/'output';events=[]
 def invoke(tool,args):
  events.append({'name':tool,'arguments':args})
 invoke('blender_scene__new_scene',{})
 invoke('blender_scene__get_scene_info',{})
 for name,m in data['materials'].items():
  invoke('blender_materials__create_material',{'name':name,'color':m['color'],'metallic':m['metallic'],'roughness':m['roughness']})
  invoke('blender_material_library__set_material_attribute',{'material_name':name,'attribute':'diffuse_color','value':m['color']})
  if m['emission_strength']:
   invoke('blender_shader_nodes__set_principled_inputs',{'material_name':name,'inputs':{'Emission Color':m['color'],'Emission Strength':m['emission_strength']}})
 for group,objects in data['groups'].items():
  for obj in objects:
   invoke('blender_data_geometry__create_mesh_from_data',{k:obj[k] for k in ['name','vertices','faces']})
   for i,name in enumerate(obj['materials']):
    invoke('blender_materials__assign_material',{'object_name':obj['name'],'material_name':name,'slot_index':i})
 invoke('blender_scripting__execute_python',{'code':(ROOT/'recipes'/'set_recipe_face_indices.py').read_text(),'context':{'recipe_data_path':str(ROOT/'recipes'/'recipe-data.json')}})
 all_names=[o['name'] for group in data['groups'].values() for o in group]
 invoke('blender_validation__validate_materials',{'object_names':all_names,'rules':{'require_materials':True,'require_nodes':True}})
 for group,objects in data['groups'].items():
  names=[o['name'] for o in objects]
  invoke('blender_validation__validate_export_readiness',{'object_names':names,'target_format':'glb'})
  invoke('blender_interchange__export_gltf',{'path':str(out/(group+'.glb')),'object_names':names,
    'options':{'export_format':'GLB','export_yup':True,'export_apply':True,'export_animations':False}})
 for group,objects in data['groups'].items():
  for obj in objects:
   if data['display_offsets'][group]!=[0,0,0]:
    invoke('blender_objects__move_object',{'name':obj['name'],'location':data['display_offsets'][group]})
 invoke('blender_scene__save_scene',{'filepath':str(out/'dawnkeep-ecosystem.blend')})
 invoke('blender_scene__get_scene_info',{})
 return events

if __name__=='__main__':
 print(json.dumps(build_plan(sys.argv[1]),indent=2))
