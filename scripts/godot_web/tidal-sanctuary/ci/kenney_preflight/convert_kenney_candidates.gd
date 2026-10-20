@tool
extends "res://inspect_kenney_sources.gd"
# FROZEN OFFLINE REVIEW CANDIDATE. No native execution has been performed. Produces new files from fixed original GLB sources.
# Does not overwrite source/baseline scenes or open a scene in the editor.

var material_records: Dictionary = {}

func material_info(material: Material) -> Dictionary:
 var info := super.material_info(material)
 if material == null:
  return info
 assert(material.get_script() == null)
 var properties: Dictionary = {}
 for property in material.get_property_list():
  var name := str(property["name"])
  if (int(property["usage"]) & PROPERTY_USAGE_STORAGE) == 0 or name in ["resource_path", "resource_scene_unique_id", "script"]:
   continue
  var value: Variant = material.get(name)
  # These fixed untextured Kenney materials must not introduce nested resource
  # graphs, shaders, textures, next_pass materials or scripts.
  assert(typeof(value) != TYPE_OBJECT or value == null)
  properties[name] = {"type":typeof(value),"stored_variant_sha256":bytes_hash(value)}
 var serialized := JSON.stringify(properties)
 var key := serialized.sha256_text()
 if material_records.has(key):
  assert(material_records[key] == serialized)
 else:
  material_records[key] = serialized
 info["stored_properties_ref"] = key
 return info

func transform_from_values(values: Array) -> Transform3D:
 assert(values.size() == 12)
 return Transform3D(Basis(Vector3(values[0],values[1],values[2]),Vector3(values[3],values[4],values[5]),Vector3(values[6],values[7],values[8])),Vector3(values[9],values[10],values[11]))

func graph(root: Node) -> Array:
 node_count = 0
 vertex_count = 0
 var rows: Array = []
 inspect_node(root,str(root.name),Transform3D.IDENTITY,rows)
 return rows

func comparable(value: Variant) -> Variant:
 # Resource/scene paths identify the separately saved container, not mesh data.
 if value is Dictionary:
  var result: Dictionary = {}
  for key in value:
   if key not in ["resource_path","scene_file_path","mesh_representation"]:
    result[key] = comparable(value[key])
  return result
 if value is Array:
  var result: Array = []
  for item in value:
   result.append(comparable(item))
  return result
 return value

func assert_graph_equal(expected: Array, actual: Array) -> void:
 assert(expected.size() == actual.size())
 for i in range(expected.size()):
  var a: Dictionary = comparable(expected[i])
  var b: Dictionary = comparable(actual[i])
  for field in ["transform","computed_world_transform"]:
   if a.has(field):
    assert(b.has(field) and a[field].size() == 12 and b[field].size() == 12)
    for j in range(12):
     assert(is_finite(float(a[field][j])) and is_finite(float(b[field][j])))
     assert(abs(float(a[field][j])-float(b[field][j])) <= 0.0000001)
    a.erase(field)
    b.erase(field)
  assert(a == b) # Immutable arrays/material values/names/classes remain exact.

func convert(arguments: Dictionary) -> Dictionary:
 var scene_before := editor_scene_signature()
 var plan_path := "res://kenney-preflight/plan.json"
 assert(FileAccess.get_sha256(plan_path) == str(arguments["plan_sha256"]))
 var plan: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(plan_path))
 assert(plan["assets"].size() == 4)
 var witness_path := "res://kenney-preflight/conversion-witness.json"
 assert(not FileAccess.file_exists(witness_path))
 var destination := "res://kenney-preflight/candidates"
 assert(not DirAccess.dir_exists_absolute(destination))
 # Read-only sizing pass before the first ResourceSaver mutation. Predict all
 # repeated graph copies using actual imports/baselines and the shared table.
 # Reserve 64 KiB for output hashes, paths, metadata and container differences.
 material_records.clear()
 var projected: Array = []
 for asset in plan["assets"]:
  var source := "res://kenney-preflight/source/"+str(asset["source_file"])
  var baseline := "res://kenney-preflight/baseline/"+str(asset["output"])
  assert(FileAccess.get_sha256(source) == str(asset["source_sha256"]))
  assert(FileAccess.get_sha256(baseline) == str(asset["baseline_sha256"]))
  var document := GLTFDocument.new()
  var state := GLTFState.new()
  assert(document.append_from_file(source,state) == OK)
  var imported := document.generate_scene(state)
  assert(imported != null)
  var source_graph := graph(imported)
  imported.free()
  var packed := ResourceLoader.load(baseline,"PackedScene",ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
  assert(packed != null)
  var old := packed.instantiate()
  var old_graph := graph(old)
  old.free()
  projected.append({"source_graph":source_graph,"baseline_graph":old_graph,"before_save_graph":old_graph,"reopened_graph":old_graph})
 assert(JSON.stringify({"outputs":projected,"material_records":material_records},"  ").to_utf8_buffer().size() <= 1024*1024-65536)
 assert(DirAccess.make_dir_absolute(destination) == OK)
 var outputs: Array = []
 for asset in plan["assets"]:
  var source := "res://kenney-preflight/source/"+str(asset["source_file"])
  var baseline := "res://kenney-preflight/baseline/"+str(asset["output"])
  assert(FileAccess.get_sha256(source) == str(asset["source_sha256"]))
  assert(FileAccess.get_sha256(baseline) == str(asset["baseline_sha256"]))
  var document := GLTFDocument.new()
  var state := GLTFState.new()
  assert(document.append_from_file(source,state) == OK)
  var imported := document.generate_scene(state)
  assert(imported is Node3D and imported.get_script() == null and imported.get_child_count() == 1)
  assert(imported.transform == Transform3D.IDENTITY)
  var imported_mesh := imported.get_child(0) as ImporterMeshInstance3D
  assert(imported_mesh != null and imported_mesh.get_script() == null and imported_mesh.get_child_count() == 0)
  assert(imported_mesh.mesh != null and imported_mesh.skin == null and imported_mesh.skeleton_path.is_empty())
  var source_graph := graph(imported)
  var old_packed := ResourceLoader.load(baseline,"PackedScene",ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
  assert(old_packed != null)
  var old := old_packed.instantiate()
  var baseline_graph := graph(old)
  old.free()
  assert(source_graph.size() == 2 and baseline_graph.size() == 3)
  var root := Node3D.new()
  root.name = "CoastalAsset"
  var model := Node3D.new()
  model.name = imported.name
  model.transform = transform_from_values(asset["wrapper_transform"])
  root.add_child(model)
  model.owner = root
  var mesh_node := MeshInstance3D.new()
  mesh_node.name = imported_mesh.name
  mesh_node.transform = imported_mesh.transform
  mesh_node.mesh = imported_mesh.mesh.get_mesh()
  model.add_child(mesh_node)
  mesh_node.owner = root
  assert(mesh_node.mesh.get_surface_count() == asset["surface_overrides"].size())
  for index in range(mesh_node.mesh.get_surface_count()):
   var spec: Dictionary = asset["surface_overrides"][index]
   var material := StandardMaterial3D.new()
   material.resource_name = str(spec["name"])
   var color: Array = spec["albedo_rgba"]
   assert(color.size() == 4 and float(spec["metallic"]) == 0.0)
   material.albedo_color = Color(color[0],color[1],color[2],color[3])
   material.metallic = 0.0
   material.roughness = 1.0
   mesh_node.set_surface_override_material(index,material)
  imported.free()
  var before_save := graph(root)
  assert_graph_equal(baseline_graph,before_save)
  var output := destination+"/"+str(asset["output"])
  assert(not FileAccess.file_exists(output))
  var packed := PackedScene.new()
  assert(packed.pack(root) == OK)
  var save_error := ResourceSaver.save(packed,output,ResourceSaver.FLAG_BUNDLE_RESOURCES)
  # Persist the actual Error even if the following assertion fails. The caller
  # never retries this mutation after a null/unknown tool result.
  var receipt_path := "res://kenney-preflight/"+str(asset["output"])+".save-result.json"
  assert(not FileAccess.file_exists(receipt_path))
  var receipt := FileAccess.open(receipt_path,FileAccess.WRITE)
  assert(receipt != null)
  receipt.store_string(JSON.stringify({"output":output,"save_error":save_error,"exists":FileAccess.file_exists(output),"before_save_graph":before_save,"material_records":material_records}))
  receipt.flush()
  var receipt_error := receipt.get_error()
  receipt.close()
  assert(receipt_error == OK)
  assert(save_error == OK and FileAccess.file_exists(output))
  root.free()
  var fresh := ResourceLoader.load(output,"PackedScene",ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
  assert(fresh != null)
  var reopened := fresh.instantiate()
  var reopened_graph := graph(reopened)
  reopened.free()
  assert_graph_equal(baseline_graph,reopened_graph)
  outputs.append({"source":asset["source_file"],"source_sha256":asset["source_sha256"],"output":output,"output_sha256":FileAccess.get_sha256(output),"output_bytes":FileAccess.get_file_as_bytes(output).size(),"save_error":save_error,"source_graph":source_graph,"baseline_graph":baseline_graph,"before_save_graph":before_save,"reopened_graph":reopened_graph})
 var scene_after := editor_scene_signature()
 assert(scene_before == scene_after)
 var witness := {"schema":1,"stage":"candidate conversion and same-session cache-ignore reopen","independent_session_reopen":false,"engine":Engine.get_version_info(),"scene_before":scene_before,"scene_after":scene_after,"outputs":outputs,"material_records":material_records}
 var text := JSON.stringify(witness,"  ")
 assert(text.to_utf8_buffer().size() <= 1024*1024)
 var file := FileAccess.open(witness_path,FileAccess.WRITE)
 assert(file != null)
 file.store_string(text)
 file.flush()
 var error := file.get_error()
 file.close()
 assert(error == OK)
 return {"schema":1,"converted":4,"saved_native_asset":true,"independent_session_reopen":false,"witness_path":witness_path,"witness_sha256":FileAccess.get_sha256(witness_path),"witness_bytes":text.to_utf8_buffer().size()}

func reopen_candidates(arguments: Dictionary) -> Dictionary:
 # Called only by the caller's second, fresh owned editor process, after the
 # first editor/server/display have actually terminated. This function alone
 # does not claim process independence; the caller must prove that lifecycle.
 material_records.clear()
 var before := editor_scene_signature()
 var plan_path := "res://kenney-preflight/plan.json"
 assert(FileAccess.get_sha256(plan_path) == str(arguments["plan_sha256"]))
 var plan: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(plan_path))
 var expected: Dictionary = arguments["output_sha256"]
 assert(expected.size() == 4 and plan["assets"].size() == 4)
 var rows: Array = []
 for asset in plan["assets"]:
  var name := str(asset["output"])
  var output := "res://kenney-preflight/candidates/"+name
  var baseline := "res://kenney-preflight/baseline/"+name
  assert(expected.has(name) and FileAccess.get_sha256(output) == str(expected[name]))
  assert(FileAccess.get_sha256(baseline) == str(asset["baseline_sha256"]))
  var baseline_packed := ResourceLoader.load(baseline,"PackedScene",ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
  var candidate_packed := ResourceLoader.load(output,"PackedScene",ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
  assert(baseline_packed != null and candidate_packed != null)
  var baseline_root := baseline_packed.instantiate()
  var candidate_root := candidate_packed.instantiate()
  var old_graph := graph(baseline_root)
  var new_graph := graph(candidate_root)
  baseline_root.free()
  candidate_root.free()
  assert_graph_equal(old_graph,new_graph)
  rows.append({"output":name,"sha256":expected[name],"baseline_graph":old_graph,"reopened_graph":new_graph})
 var after := editor_scene_signature()
 assert(before == after)
 var path := "res://kenney-preflight/independent-reopen-witness.json"
 assert(not FileAccess.file_exists(path))
 var text := JSON.stringify({"schema":1,"stage":"candidate reopen in caller-owned separate editor","engine":Engine.get_version_info(),"scene_before":before,"scene_after":after,"outputs":rows,"material_records":material_records},"  ")
 assert(text.to_utf8_buffer().size() <= 1024*1024)
 var file := FileAccess.open(path,FileAccess.WRITE)
 assert(file != null)
 file.store_string(text)
 file.flush()
 var error := file.get_error()
 file.close()
 assert(error == OK)
 return {"schema":1,"reopened":4,"converted":false,"saved_native_asset":false,"witness_path":path,"witness_bytes":text.to_utf8_buffer().size(),"witness_sha256":FileAccess.get_sha256(path)}
