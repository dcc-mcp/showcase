@tool
extends RefCounted
# Candidate-only inspection. No scene is saved, no geometry or formal asset is edited.
var node_count := 0
var vertex_count := 0

func matrix(value: Transform3D) -> Array:
 return [value.basis.x.x,value.basis.x.y,value.basis.x.z,value.basis.y.x,value.basis.y.y,value.basis.y.z,value.basis.z.x,value.basis.z.y,value.basis.z.z,value.origin.x,value.origin.y,value.origin.z]

func bytes_hash(value: Variant) -> String:
 var context := HashingContext.new()
 assert(context.start(HashingContext.HASH_SHA256) == OK)
 assert(context.update(var_to_bytes(value)) == OK)
 return context.finish().hex_encode()

func material_info(material: Material) -> Dictionary:
 if material == null:
  return {"present":false}
 assert(material is StandardMaterial3D)
 var m := material as StandardMaterial3D
 return {"present":true,"name":m.resource_name,"resource_path":m.resource_path,
         "albedo":[m.albedo_color.r,m.albedo_color.g,m.albedo_color.b,m.albedo_color.a],
         "metallic":m.metallic,"roughness":m.roughness,
         "albedo_texture":m.albedo_texture.resource_path if m.albedo_texture != null else "",
         "normal_texture":m.normal_texture.resource_path if m.normal_texture != null else ""}

func inspect_node(node: Node, path: String, parent_transform: Transform3D, rows: Array) -> void:
 node_count += 1
 assert(node_count <= 128 and node.get_script() == null)
 var world := parent_transform
 var row := {"path":path,"class":node.get_class(),"scene_file_path":node.scene_file_path}
 if node is Node3D:
  row["transform"] = matrix(node.transform)
  world = parent_transform * node.transform
  row["computed_world_transform"] = matrix(world)
 if node is MeshInstance3D or node is ImporterMeshInstance3D:
  var mesh: ArrayMesh
  if node is ImporterMeshInstance3D:
   assert(node.mesh != null)
   # Official cached ArrayMesh representation of this detached importer resource.
   # No node replacement, asset save, mesh edit, or source-file mutation.
   mesh = node.mesh.get_mesh()
   row["mesh_representation"] = "ImporterMesh.get_mesh ArrayMesh"
  else:
   mesh = node.mesh as ArrayMesh
   row["mesh_representation"] = "stored ArrayMesh"
  assert(mesh != null and mesh.get_surface_count() > 0 and mesh.get_surface_count() <= 16)
  var surfaces: Array = []
  for index in range(mesh.get_surface_count()):
   var arrays := mesh.surface_get_arrays(index)
   assert(arrays.size() == Mesh.ARRAY_MAX)
   vertex_count += arrays[Mesh.ARRAY_VERTEX].size()
   assert(vertex_count <= 20000)
   var channels: Array = []
   for channel in range(arrays.size()):
    channels.append({"channel":channel,"type":typeof(arrays[channel]),"stored_variant_sha256":bytes_hash(arrays[channel])})
   surfaces.append({"index":index,"name":mesh.surface_get_name(index),
                    "primitive":mesh.surface_get_primitive_type(index),
                    "vertex_count":arrays[Mesh.ARRAY_VERTEX].size(),
                    "index_count":arrays[Mesh.ARRAY_INDEX].size() if arrays[Mesh.ARRAY_INDEX] != null else 0,
                    "channels":channels,"source_material":material_info(mesh.surface_get_material(index)),
                    "effective_material":material_info(node.get_active_material(index) if node is MeshInstance3D else mesh.surface_get_material(index))})
  row["surfaces"] = surfaces
  row["material_override"] = material_info(node.material_override) if node is MeshInstance3D else {"applicable":false}
 rows.append(row)
 for child in node.get_children():
  inspect_node(child,path+"/"+str(child.name),world,rows)

func editor_scene_signature() -> Dictionary:
 # This preflight is admitted only in its own empty editor project. Refuse an
 # existing scene rather than clearing somebody else's work to meet a guard.
 var root := EditorInterface.get_edited_scene_root()
 var opened := EditorInterface.get_open_scenes()
 assert(root == null and opened.is_empty())
 return {"edited_scene_root":null,"open_scenes":Array(opened)}

func run(arguments: Dictionary) -> Dictionary:
 var scene_before := editor_scene_signature()
 var plan_path := "res://kenney-preflight/plan.json"
 assert(FileAccess.get_sha256(plan_path) == str(arguments["plan_sha256"]))
 var plan: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(plan_path))
 assert(plan["assets"].size() == 4)
 var output := "res://kenney-preflight/preflight-witness.json"
 assert(not FileAccess.file_exists(output))
 var results: Array = []
 for asset in plan["assets"]:
  var filename := str(asset["source_file"])
  var target := str(asset["output"])
  assert(filename == filename.get_file() and filename.ends_with(".glb"))
  assert(target == target.get_file() and target.ends_with(".tscn"))
  var source := "res://kenney-preflight/source/"+filename
  var baseline := "res://kenney-preflight/baseline/"+target
  assert(FileAccess.get_sha256(source) == str(asset["source_sha256"]))
  assert(FileAccess.get_sha256(baseline) == str(asset["baseline_sha256"]))
  var document := GLTFDocument.new()
  var state := GLTFState.new()
  var imported_error := document.append_from_file(source,state)
  assert(imported_error == OK)
  var imported := document.generate_scene(state)
  assert(imported != null)
  var imported_rows: Array = []
  inspect_node(imported,str(imported.name),Transform3D.IDENTITY,imported_rows)
  imported.free()
  var packed := ResourceLoader.load(baseline,"PackedScene",ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
  assert(packed != null)
  var old := packed.instantiate()
  assert(old != null)
  var baseline_rows: Array = []
  inspect_node(old,str(old.name),Transform3D.IDENTITY,baseline_rows)
  old.free()
  results.append({"source":filename,"source_sha256":asset["source_sha256"],
                  "baseline":target,"baseline_sha256":asset["baseline_sha256"],
                  "import_error":imported_error,"source_graph":imported_rows,"baseline_graph":baseline_rows})
 var scene_after := editor_scene_signature()
 assert(scene_after == scene_before)
 var witness := {"schema":1,"scope":"native source and baseline inspection, not converted output or acceptance",
                 "engine":Engine.get_version_info(),"scene_before":scene_before,"scene_after":scene_after,"assets":results,"nodes":node_count,"vertices":vertex_count}
 var text := JSON.stringify(witness,"  ")
 assert(text.to_utf8_buffer().size() <= 1024*1024)
 var file := FileAccess.open(output,FileAccess.WRITE)
 assert(file != null)
 file.store_string(text)
 file.flush()
 var write_error := file.get_error()
 file.close()
 assert(write_error == OK)
 return {"schema":1,"inspected":results.size(),"witness_path":output,
         "witness_bytes":text.to_utf8_buffer().size(),"witness_sha256":FileAccess.get_sha256(output),
         "converted":false,"saved_native_asset":false}
