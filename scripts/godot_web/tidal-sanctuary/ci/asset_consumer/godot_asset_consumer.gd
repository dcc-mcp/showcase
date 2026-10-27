@tool
extends RefCounted

func _meshes(node: Node, out: Array) -> void:
 if node is MeshInstance3D:
  out.append(node)
 for child in node.get_children():
  _meshes(child, out)

func _find(node: Node, type_name: String) -> Node:
 if node.is_class(type_name):
  return node
 for child in node.get_children():
  var found := _find(child, type_name)
  if found != null:
   return found
 return null

func _own(node: Node, root: Node) -> void:
 for child in node.get_children():
  # This preview serializes a full frozen copy, not inherited GLB overrides.
  child.scene_file_path = ""
  child.owner = root
  _own(child, root)

func _floats(v: Vector3) -> Array:
 return [v.x, v.y, v.z]

func _matrix(t: Transform3D) -> Array:
 return [_floats(t.basis.x), _floats(t.basis.y), _floats(t.basis.z), _floats(t.origin)]

func _pose(model: Node3D, clip: String, time: float) -> Dictionary:
 var player := _find(model, "AnimationPlayer") as AnimationPlayer
 var skeleton := _find(model, "Skeleton3D") as Skeleton3D
 if player == null or skeleton == null:
  return {"error": "Missing actual AnimationPlayer or Skeleton3D"}
 var chosen := ""
 for name in player.get_animation_list():
  if name == clip or String(name).ends_with("/" + clip):
   if not chosen.is_empty():
    return {"error": "Ambiguous clip"}
   chosen = name
 if chosen.is_empty():
  return {"error": "Missing clip", "available": player.get_animation_list()}
 var animation := player.get_animation(chosen)
 if abs(animation.length - 1.0) > 0.000001:
  return {"error": "Unexpected duration", "length": animation.length}
 player.play(chosen)
 player.seek(time, true)
 player.advance(0.0)
 player.stop(true)
 skeleton.force_update_all_bone_transforms()
 return {"clip": chosen, "length": animation.length, "tracks": animation.get_track_count(), "sample_time": time, "bones": _bones(skeleton)}

func _bones(skeleton: Skeleton3D) -> Array:
 var bones: Array = []
 for index in range(skeleton.get_bone_count()):
  var rotation := skeleton.get_bone_pose_rotation(index)
  bones.append({"name": skeleton.get_bone_name(index), "parent": skeleton.get_bone_parent(index),
   "position": _floats(skeleton.get_bone_pose_position(index)), "rotation": [rotation.x, rotation.y, rotation.z, rotation.w],
   "scale": _floats(skeleton.get_bone_pose_scale(index)), "rest": _matrix(skeleton.get_bone_rest(index)),
   "global_pose": _matrix(skeleton.get_bone_global_pose(index))})
 return bones

func inspect(arguments: Dictionary) -> Dictionary:
 var path := String(arguments.path)
 if not path.begins_with("res://assets/") or not path.ends_with(".glb"):
  return {"error": "Unexpected asset path"}
 var packed := load(path) as PackedScene
 if packed == null:
  return {"error": "Actual Godot import unavailable"}
 var model := packed.instantiate() as Node3D
 if model == null:
  return {"error": "Import is not Node3D"}
 EditorInterface.get_base_control().get_tree().root.add_child(model)
 var result := _pose(model, String(arguments.clip), float(arguments.time)) if arguments.has("clip") else {}
 var meshes: Array = []
 _meshes(model, meshes)
 var mesh_info: Array = []
 var bounds := AABB()
 var have_bounds := false
 for mesh: MeshInstance3D in meshes:
  var transformed: AABB = mesh.global_transform * mesh.get_aabb()
  bounds = bounds.merge(transformed) if have_bounds else transformed
  have_bounds = true
  var surfaces: Array = []
  for index in range(mesh.mesh.get_surface_count()):
   var material := mesh.get_active_material(index)
   surfaces.append({"material": material.resource_name if material != null else "", "class": material.get_class() if material != null else "", "vertices": mesh.mesh.surface_get_array_len(index), "indices": mesh.mesh.surface_get_array_index_len(index)})
  mesh_info.append({"name": mesh.name, "transform": _matrix(mesh.global_transform), "aabb_position": _floats(mesh.get_aabb().position), "aabb_size": _floats(mesh.get_aabb().size), "surfaces": surfaces, "skin_binds": mesh.skin.get_bind_count() if mesh.skin != null else 0})
 result["rest_mesh_world_aabb"] = {"position": _floats(bounds.position), "size": _floats(bounds.size)}
 result["asset"] = path
 result["mesh_count"] = meshes.size()
 result["meshes"] = mesh_info
 model.free()
 return result

func build_preview(arguments: Dictionary) -> Dictionary:
 var output := String(arguments.output)
 if not output.begins_with("res://previews/") or not output.ends_with(".tscn") or FileAccess.file_exists(output):
  return {"error": "Expected fresh preview path"}
 var root := Node3D.new()
 root.name = "AssetConsumerPreview"
 EditorInterface.get_base_control().get_tree().root.add_child(root)
 var records: Array = []
 for index in range(2):
  var path := String(arguments.paths[index])
  if not path.begins_with("res://assets/") or not path.ends_with(".glb"):
   root.free()
   return {"error": "Unexpected preview input"}
  var packed := load(path) as PackedScene
  if packed == null:
   root.free()
   return {"error": "Actual import missing"}
  var model := packed.instantiate() as Node3D
  var game_wrapper := Node3D.new()
  game_wrapper.name = "Old" if index == 0 else "New"
  root.add_child(game_wrapper)
  model.name = "ImportedAsset"
  game_wrapper.add_child(model)
  game_wrapper.position.x = -float(arguments.spacing) if index == 0 else float(arguments.spacing)
  if bool(arguments.get("game_swim", false)):
   # Simplified consumer fixture using game-local wrapper parameters, not full gameplay.
   game_wrapper.rotation.x = -PI * 0.5
   game_wrapper.position.y = 0.70
   # main.gd make_player centers the imported explorer at local y=-.6.
   # A dedicated fixture container preserves every stored imported-asset transform.
   var origin_offset := Node3D.new()
   origin_offset.name = "GameExplorerOrigin"
   origin_offset.position.y = -0.6
   game_wrapper.add_child(origin_offset)
   game_wrapper.remove_child(model)
   origin_offset.add_child(model)
  if arguments.has("clip"):
   var record := _pose(model, String(arguments.clip), float(arguments.get("time", 0.25)))
   if record.has("error"):
    root.free()
    return record
   records.append({"clip": record.clip, "length": record.length, "bones": record.bones})
   var player := _find(model, "AnimationPlayer") as AnimationPlayer
   player.active = false
  model.process_mode = Node.PROCESS_MODE_DISABLED
 var light := DirectionalLight3D.new()
 light.name = "SameLight"
 light.rotation_degrees = Vector3(-45, -28, 0)
 light.light_energy = 1.5
 light.shadow_enabled = true
 root.add_child(light)
 var environment := WorldEnvironment.new()
 environment.name = "SameEnvironment"
 environment.environment = Environment.new()
 environment.environment.background_mode = Environment.BG_COLOR
 environment.environment.background_color = Color(0.10, 0.16, 0.18)
 environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
 environment.environment.ambient_light_color = Color(0.8, 0.9, 1.0)
 environment.environment.ambient_light_energy = 0.45
 root.add_child(environment)
 var floor_mesh := MeshInstance3D.new()
 floor_mesh.name = "Ground"
 var plane := PlaneMesh.new()
 plane.size = Vector2(float(arguments.size) * 2, float(arguments.size) * 2)
 floor_mesh.mesh = plane
 floor_mesh.position.y = -0.03
 var ground_material := StandardMaterial3D.new()
 ground_material.albedo_color = Color(0.3, 0.35, 0.32)
 ground_material.roughness = 1.0
 floor_mesh.material_override = ground_material
 root.add_child(floor_mesh)
 var camera := Camera3D.new()
 camera.name = "SameCamera"
 camera.projection = Camera3D.PROJECTION_ORTHOGONAL
 camera.size = float(arguments.size)
 root.add_child(camera)
 var height := float(arguments.height)
 camera.position = Vector3(0, height + float(arguments.size) * 0.22, -float(arguments.size) * 1.5)
 if bool(arguments.get("game_swim", false)):
  camera.position = Vector3(float(arguments.size) * 0.45, 1.8, -float(arguments.size) * 0.9)
  height = 0.70
 camera.look_at(Vector3(0, height, 0), Vector3.UP)
 camera.current = true
 _own(root, root)
 var expected_meshes: Array = []
 _meshes(root, expected_meshes)
 var expected_mesh_count := expected_meshes.size()
 var saved := PackedScene.new()
 var pack_error := saved.pack(root)
 if pack_error == OK:
  var state := saved.get_state()
  for index in range(state.get_node_count()):
   if state.get_node_instance(index) != null:
    root.free()
    return {"error": "Frozen preview unexpectedly retains a scene instance"}
 var save_error := ResourceSaver.save(saved, output) if pack_error == OK else pack_error
 root.free()
 if save_error != OK:
  return {"error": "Native PackedScene save failed", "code": save_error}
 var reopened := ResourceLoader.load(output, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
 if reopened == null:
  return {"error": "Saved preview cannot reopen"}
 var actual := reopened.instantiate() as Node3D
 EditorInterface.get_base_control().get_tree().root.add_child(actual)
 var actual_meshes: Array = []
 _meshes(actual, actual_meshes)
 if actual_meshes.size() != expected_mesh_count:
  actual.free()
  return {"error": "Saved preview mesh count changed"}
 var readback: Array = []
 if arguments.has("clip"):
  for label in ["Old", "New"]:
   var skeleton := _find(actual.get_node(label), "Skeleton3D") as Skeleton3D
   if skeleton == null:
    actual.free()
    return {"error": "Reopened preview lost skeleton"}
   skeleton.force_update_all_bone_transforms()
   readback.append(_bones(skeleton))
 actual.free()
 var witness_path := output.trim_suffix(".tscn") + "-pose-witness.json"
 if FileAccess.file_exists(witness_path):
  return {"error": "Expected fresh pose witness"}
 var witness := FileAccess.open(witness_path, FileAccess.WRITE)
 if witness == null:
  return {"error": "Cannot save full pose witness"}
 witness.store_string(JSON.stringify({"saved": output, "mesh_count": expected_mesh_count, "nested_scene_instances": 0, "models": records, "reopened_bones": readback, "camera": "SameCamera", "render_pending": true}))
 witness.close()
 # Keep the complete native values, without exceeding the official bridge frame budget.
 return {"saved": output, "witness": witness_path, "witness_sha256": FileAccess.get_sha256(witness_path)}
