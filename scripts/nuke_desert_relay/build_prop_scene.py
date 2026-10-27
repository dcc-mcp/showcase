"""Prepare an isolated, editable prop scene inside a freshly granted Blender host.

OFFLINE RECIPE ONLY: this file has not been run in Blender. It does not launch a
host or render. After typed-tool discovery, an authorized official scripting tool
may import this module and call ``build(config, runtime_session_id=...)``. A local
config is a precondition check, not authorization. The grant must come from the
coordinator and identify the actual fresh PID/session/version.

Required private config: package_root, expected_owner_thread_id,
host_grant {state, grant_id, owner_thread_id,
session_id, process_id, blender_version_exact, starts_at_utc, expires_at_utc,
allowed_actions}, expected_baseline {scene_names, object_names}. Paths written
below stay inside package_root. Existing projects and outputs are refused.
"""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os


ASSET_SHA256 = "764336cee935dcb7bef4bdcf3b56ef23b5955a5699828c61c02fb39ce8001945"
ACTIONS = {"create_owned_scene", "import_verified_asset", "inspect_render_passes", "save_owned_project"}
SCENE_NAME = "NDR_Prop_Scene"
DESIGN = {
    "status": "design_not_camera_matched",
    "sword_axial_extent_m": 1.5,
    "burial_depth_m": 0.08,
    "camera_location_m": [0.0, -9.0, 1.9],
    "camera_target_m": [0.0, 0.0, 0.7],
    "camera_lens_mm": 70.0,
    "camera_sensor_width_mm": 36.0,
    "sun_location_m": [-4.0, -6.0, 8.0],
    "sun_color_linear_rgb": [1.0, 0.78, 0.53],
    "sun_energy": 3.0,
    "sun_angle_rad": 0.06,
    "world_color_linear_rgb": [0.40, 0.55, 1.0],
    "world_strength": 0.35,
    "ground_size_m": 30.0,
    "test": {"width_px": 640, "height_px": 360, "frames": 1, "samples": 16, "cpu_threads_max": 4},
    "film_plan": {"width_px": 1280, "height_px": 720, "fps": 30, "frames": 240, "duration_s": 8.0},
    "passes_requested": ["Combined", "Shadow Catcher", "Depth", "Normal"],
    "exr": {"container": "OPEN_EXR_MULTILAYER", "float_bits": 32, "codec": "ZIP", "color_space": "scene_linear"},
    "review_required": ["plate perspective", "sun direction", "contact shadow", "occlusion", "material response", "Nuke scene-linear round-trip"],
}


def _inside(root, relative):
    candidate = (root / relative).resolve()
    candidate.relative_to(root)
    return candidate


def _utc(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Grant timestamps require an explicit UTC offset")
    return result.astimezone(timezone.utc)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_grant(config, runtime_session_id, bpy):
    grant = config["host_grant"]
    now = datetime.now(timezone.utc)
    expected_owner = config.get("expected_owner_thread_id")
    if (not isinstance(expected_owner, str) or not expected_owner.strip()
            or expected_owner != expected_owner.strip()
            or grant.get("state") != "granted"
            or grant.get("owner_thread_id") != expected_owner):
        raise RuntimeError("A fresh coordinator grant for this owner is required")
    if not grant.get("grant_id") or not runtime_session_id or grant.get("session_id") != runtime_session_id:
        raise RuntimeError("Exact granted runtime session binding is missing")
    if grant.get("process_id") != os.getpid() or grant.get("blender_version_exact") != bpy.app.version_string:
        raise RuntimeError("PID or exact Blender version differs from the grant")
    if not (_utc(grant["starts_at_utc"]) <= now < _utc(grant["expires_at_utc"])):
        raise RuntimeError("The coordination window is not active")
    if not ACTIONS.issubset(set(grant.get("allowed_actions", []))):
        raise RuntimeError("Grant does not cover all build/save actions")
    if bpy.data.filepath:
        raise RuntimeError("Refusing a host with an already opened/saved project")
    baseline = config["expected_baseline"]
    scene_names = sorted(s.name for s in bpy.data.scenes)
    object_names = sorted(o.name for o in bpy.data.objects)
    if scene_names != sorted(baseline["scene_names"]) or object_names != sorted(baseline["object_names"]):
        raise RuntimeError("Fresh-host baseline differs from the coordinator-approved inventory")
    if not set(scene_names).issubset({"Scene"}) or not set(object_names).issubset({"Cube", "Camera", "Light"}):
        raise RuntimeError("Only an empty or unmodified default startup inventory is accepted")
    if bpy.data.libraries or any(i.name not in {"Render Result", "Viewer Node"} for i in bpy.data.images):
        raise RuntimeError("Unexpected linked project or image data in the fresh host")
    if SCENE_NAME in bpy.data.scenes:
        raise RuntimeError("Owned scene already exists; inspect the previous outcome, do not replay")


def _bounds(objects, Vector):
    points = [o.matrix_world @ Vector(corner) for o in objects for corner in o.bound_box]
    if not points:
        raise RuntimeError("Imported asset has no bounds")
    return ([min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)])


def _aim(obj, target, Vector):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def _pass_schema(bpy, scene, view_layer):
    """Inspect real RNA and sockets; missing passes stop the recipe."""
    for name in ("use_pass_z", "use_pass_normal"):
        if name not in view_layer.bl_rna.properties:
            raise RuntimeError("Required pass switch unavailable: " + name)
        setattr(view_layer, name, True)
    if not hasattr(view_layer, "cycles") or not hasattr(view_layer.cycles, "use_pass_shadow_catcher"):
        raise RuntimeError("Cycles Shadow Catcher pass switch is unavailable")
    view_layer.cycles.use_pass_shadow_catcher = True
    view_layer.update_render_passes()
    tree = bpy.data.node_groups.new("NDR_Pass_Inspection", "CompositorNodeTree")
    if hasattr(scene, "compositing_node_group"):
        scene.compositing_node_group = tree  # Blender 5.x official API.
    elif hasattr(scene, "use_nodes") and hasattr(scene, "node_tree"):
        bpy.data.node_groups.remove(tree)
        scene.use_nodes = True
        tree = scene.node_tree
    else:
        raise RuntimeError("No supported scene compositor node-tree API found")
    node = tree.nodes.new("CompositorNodeRLayers")
    node.name = "NDR_Inspect_Actual_Passes"
    node.scene = scene
    node.layer = view_layer.name
    sockets = [{"name": s.name, "identifier": s.identifier, "type": s.bl_idname,
                "available": not getattr(s, "is_unavailable", False)} for s in node.outputs]
    available = {s["name"] for s in sockets if s["available"]}
    requested = {"Image", "Depth", "Normal", "Shadow Catcher"}
    if not requested.issubset(available):
        raise RuntimeError("Pass sockets missing; observed schema: " + json.dumps(sockets))
    # Raw scene-linear multilayer output is written by the renderer itself.
    # The inspection tree is deliberately excluded from rendering.
    scene.render.use_compositing = False
    return sockets


def build(config, *, runtime_session_id):
    """Build/save only, in the already authorized host; never start a render."""
    root = Path(config["package_root"]).resolve(strict=True)
    asset = _inside(root, config.get("asset_path", "assets/bronze-edge.glb"))
    blend = _inside(root, "scene/prop_scene.blend")
    receipt = _inside(root, "scene/build-receipt.json")
    if not asset.is_file() or _sha(asset) != ASSET_SHA256:
        raise RuntimeError("CC0 asset bytes do not match the audited input")
    if blend.exists() or receipt.exists():
        raise RuntimeError("Refusing to overwrite an earlier scene or receipt")

    # Blender is imported only when the guarded entry point is explicitly called.
    import bpy
    from mathutils import Matrix, Vector

    _check_grant(config, runtime_session_id, bpy)
    original_members = {s.name: sorted(o.name for o in s.objects) for s in bpy.data.scenes}
    original_window_scene = bpy.context.window.scene if bpy.context.window else None
    scene = bpy.data.scenes.new(SCENE_NAME)
    collection = bpy.data.collections.new("NDR_Owned_Content")
    scene.collection.children.link(collection)
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = DESIGN["test"]["samples"]
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.frame_start = scene.frame_end = 1
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "ZIP"
    scene.render.filepath = "//../renderpasses/prop_test_"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    before = set(bpy.data.objects)
    with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0], collection=collection):
        result = bpy.ops.import_scene.gltf(filepath=str(asset))
    if "FINISHED" not in result:
        raise RuntimeError("glTF import did not finish: " + repr(result))
    imported = list(set(bpy.data.objects) - before)
    meshes = [o for o in imported if o.type == "MESH"]
    if len(imported) != 1 or len(meshes) != 1:
        raise RuntimeError("Audited single static-mesh input changed during import")
    if any(o.animation_data or o.type == "ARMATURE" for o in imported):
        raise RuntimeError("Unexpected animation/rig in the static asset")
    for obj in imported:
        if obj.name not in collection.objects:
            collection.objects.link(obj)
    for name, members in original_members.items():
        if sorted(o.name for o in bpy.data.scenes[name].objects) != members:
            raise RuntimeError("Importer changed a pre-existing scene; preserve failure and stop")

    lo, hi = _bounds(meshes, Vector)
    axis = max(range(3), key=lambda i: hi[i] - lo[i])
    direction = Vector(tuple(1.0 if i == axis else 0.0 for i in range(3)))
    rotation = direction.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
    original_matrices = {o: o.matrix_world.copy() for o in imported}
    for obj in imported:
        obj.matrix_world = rotation @ original_matrices[obj]
    lo, hi = _bounds(meshes, Vector)
    scale = DESIGN["sword_axial_extent_m"] / (hi[2] - lo[2])
    scaled = Matrix.Scale(scale, 4) @ rotation
    for obj in imported:
        obj.matrix_world = scaled @ original_matrices[obj]
    lo, hi = _bounds(meshes, Vector)
    translate = Matrix.Translation(Vector((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -0.08 - lo[2])))
    for obj in imported:
        obj.matrix_world = translate @ scaled @ original_matrices[obj]
    scene.view_layers[0].update()
    final_lo, final_hi = _bounds(meshes, Vector)

    ground_mesh = bpy.data.meshes.new("NDR_Ground_Mesh")
    half = DESIGN["ground_size_m"] / 2
    ground_mesh.from_pydata([(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("NDR_Shadow_Catcher", ground_mesh)
    collection.objects.link(ground)
    if not hasattr(ground, "is_shadow_catcher"):
        raise RuntimeError("Cycles shadow-catcher object property is unavailable")
    ground.is_shadow_catcher = True
    camera = bpy.data.objects.new("NDR_Camera_Design_Only", bpy.data.cameras.new("NDR_Camera_Data"))
    collection.objects.link(camera)
    camera.location = DESIGN["camera_location_m"]
    camera.data.lens = DESIGN["camera_lens_mm"]
    camera.data.sensor_width = DESIGN["camera_sensor_width_mm"]
    _aim(camera, DESIGN["camera_target_m"], Vector)
    scene.camera = camera
    sun = bpy.data.objects.new("NDR_Warm_Sun", bpy.data.lights.new("NDR_Sun_Data", "SUN"))
    collection.objects.link(sun)
    sun.location = DESIGN["sun_location_m"]
    sun.data.color = DESIGN["sun_color_linear_rgb"]
    sun.data.energy = DESIGN["sun_energy"]
    sun.data.angle = DESIGN["sun_angle_rad"]
    _aim(sun, (0, 0, 0), Vector)
    world = bpy.data.worlds.new("NDR_Cool_Fill")
    world.use_nodes = True
    background = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if background is None:
        raise RuntimeError("World Background shader was not discovered")
    background.inputs["Color"].default_value = (*DESIGN["world_color_linear_rgb"], 1.0)
    background.inputs["Strength"].default_value = DESIGN["world_strength"]
    scene.world = world
    pass_sockets = _pass_schema(bpy, scene, scene.view_layers[0])
    for image in bpy.data.images:
        if image.name not in {"Render Result", "Viewer Node"} and not image.packed_file:
            raise RuntimeError("Unexpected unpacked image; pack explicitly and review before saving")
    for name, members in original_members.items():
        if sorted(o.name for o in bpy.data.scenes[name].objects) != members:
            raise RuntimeError("A pre-existing scene was modified")

    blend.parent.mkdir(parents=True, exist_ok=True)
    try:
        if bpy.context.window:
            bpy.context.window.scene = scene
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            result = bpy.ops.wm.save_as_mainfile(filepath=str(blend), copy=True, check_existing=True)
        if "FINISHED" not in result or not blend.is_file():
            raise RuntimeError("Native project save did not complete")
    finally:
        if bpy.context.window and original_window_scene:
            bpy.context.window.scene = original_window_scene
    actual = {
        "schema_version": 1, "status": "built_not_rendered_not_reopened",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": {"application": "Blender", "version": bpy.app.version_string},
        "binding_digest": hashlib.sha256((config["host_grant"]["grant_id"] + runtime_session_id).encode()).hexdigest(),
        "planned": DESIGN,
        "observed_in_host": {
            "scene_name": scene.name, "source_long_axis_index": axis,
            "uniform_scale": scale, "bbox_min_m": final_lo, "bbox_max_m": final_hi,
            "asset_world_matrices": {o.name: [list(row) for row in o.matrix_world] for o in imported},
            "camera_world_matrix": [list(row) for row in camera.matrix_world],
            "sun_world_matrix": [list(row) for row in sun.matrix_world],
            "pass_sockets": pass_sockets,
            "render_settings_only": {"engine": scene.render.engine, "threads": scene.render.threads,
                                     "device": scene.cycles.device, "film_transparent": scene.render.film_transparent},
        },
        "files": [{"path": str(blend.relative_to(root)).replace("\\", "/"), "bytes": blend.stat().st_size, "sha256": _sha(blend)},
                  {"path": str(asset.relative_to(root)).replace("\\", "/"), "bytes": asset.stat().st_size, "sha256": _sha(asset)}],
        "not_claimed": ["rendered frames", "EXR channels in written bytes", "plate camera match", "native reopen", "Nuke import", "visual or temporal acceptance", "typed asset tools"],
    }
    receipt.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
    return actual
