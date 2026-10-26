"""Prepare an offline default-mesh OBJ bridge without starting a DCC host.

Reads an explicitly selected, hash-bound courier GLB and writes an explicitly
selected output directory. The output contains no skin, skeleton, clips or rig.
"""
import argparse
import hashlib
import json
import math
import pathlib
import struct
from datetime import datetime, timezone

EXPECTED_SHA256 = "82a7b7456137eb133753650e2d9cda4f016ea810df68adcbfdc267f83ab29cd2"
COMPONENTS = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def identity():
    return [[float(r == c) for c in range(4)] for r in range(4)]

def mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]

def trs(node):
    if "matrix" in node:
        return [[node["matrix"][c*4 + r] for c in range(4)] for r in range(4)]
    translation = node.get("translation", [0, 0, 0])
    q = node.get("rotation", [0, 0, 0, 1])
    length = math.sqrt(sum(v*v for v in q))
    assert length > 1e-12
    x, y, z, w = [v / length for v in q]
    scale = node.get("scale", [1, 1, 1])
    rotation = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    out = identity()
    for r in range(3):
        for c in range(3):
            out[r][c] = rotation[r][c]*scale[c]
        out[r][3] = translation[r]
    return out

def point(matrix, p):
    return tuple(sum(matrix[r][c] * p[c] for c in range(3)) + matrix[r][3] for r in range(3))

def inverse_transpose_linear(matrix):
    a, b, c = matrix[0][:3]
    d, e, f = matrix[1][:3]
    g, h, i = matrix[2][:3]
    determinant = a*(e*i-f*h) - b*(d*i-f*g) + c*(d*h-e*g)
    assert abs(determinant) > 1e-12, "singular default scene transform"
    cofactors = [[e*i-f*h, f*g-d*i, d*h-e*g], [c*h-b*i, a*i-c*g, b*g-a*h], [b*f-c*e, c*d-a*f, a*e-b*d]]
    return [[v / determinant for v in row] for row in cofactors], determinant

def normal(matrix, n):
    transformed = tuple(sum(matrix[r][c]*n[c] for c in range(3)) for r in range(3))
    length = math.sqrt(sum(v*v for v in transformed))
    assert length > 1e-12
    return tuple(v / length for v in transformed)

def bbox(points):
    return {"min": [min(p[i] for p in points) for i in range(3)], "max": [max(p[i] for p in points) for i in range(3)]}

def safe_name(value):
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in str(value)) or "unnamed"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    parser.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    args = parser.parse_args()
    source = args.input.resolve()
    output = args.output_dir.resolve()
    if output.exists() and not output.is_dir():
        parser.error("output-dir must be a directory")
    if output.exists() and any(output.iterdir()):
        parser.error("refusing a nonempty output-dir; select a new or empty directory to preserve prior evidence")
    raw = source.read_bytes()
    if sha(raw) != args.expected_sha256:
        raise ValueError("source differs from the selected hash-bound derivative")
    assert struct.unpack_from("<4sII", raw) == (b"glTF", 2, len(raw))
    chunks, offset = [], 12
    while offset < len(raw):
        size, kind = struct.unpack_from("<II", raw, offset)
        chunks.append((kind, raw[offset + 8:offset + 8 + size]))
        offset += size + 8
    doc = json.loads(next(data for kind, data in chunks if kind == 0x4E4F534A))
    binary = next(data for kind, data in chunks if kind == 0x004E4942)
    cache = {}

    def accessor(index):
        if index in cache:
            return cache[index]
        a = doc["accessors"][index]
        assert "sparse" not in a, "unsupported sparse accessor"
        view = doc["bufferViews"][a["bufferView"]]
        assert view.get("buffer", 0) == 0
        fmt, size = COMPONENTS[a["componentType"]]
        width = WIDTHS[a["type"]]
        start = view.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = view.get("byteStride", width*size)
        values = [struct.unpack_from("<" + fmt*width, binary, start + i*stride) for i in range(a["count"])]
        if a.get("normalized") and a["componentType"] != 5126:
            maximum = {5120: 127, 5121: 255, 5122: 32767, 5123: 65535, 5125: 4294967295}[a["componentType"]]
            values = [tuple(max(-1.0, v / maximum) for v in row) for row in values]
        cache[index] = values
        return values

    nodes = doc.get("nodes", [])
    selected_scene = doc.get("scene", 0)
    assert doc.get("scenes"), "no scene: default scene semantics unavailable"
    worlds, parents = {}, {}
    def visit(index, parent):
        assert index not in worlds, "shared or cyclic scene node"
        worlds[index] = mul(parent, trs(nodes[index]))
        for child in nodes[index].get("children", []):
            parents[child] = index
            visit(child, worlds[index])
    for root in doc["scenes"][selected_scene].get("nodes", []):
        visit(root, identity())

    output.mkdir(parents=True, exist_ok=True)
    texture_dir = output / "textures"
    texture_dir.mkdir(exist_ok=True)
    images, image_paths = [], {}
    for index, img in enumerate(doc.get("images", [])):
        assert "uri" not in img and "bufferView" in img, "external/data URI image requires explicit extension"
        view = doc["bufferViews"][img["bufferView"]]
        assert view.get("buffer", 0) == 0
        start = view.get("byteOffset", 0)
        data = binary[start:start + view["byteLength"]]
        mime = img.get("mimeType")
        extensions = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
        assert mime in extensions, "unsupported embedded image type"
        if mime == "image/png":
            assert data.startswith(b"\x89PNG\r\n\x1a\n")
        elif mime == "image/jpeg":
            assert data.startswith(b"\xff\xd8")
        filename = f"courier-image-{index:02d}" + extensions[mime]
        (texture_dir / filename).write_bytes(data)
        assert sha((texture_dir / filename).read_bytes()) == sha(data)
        image_paths[index] = "textures/" + filename
        images.append({"image_index": index, "source_name": img.get("name"), "mime_type": mime, "path": image_paths[index], "bytes": len(data), "sha256": sha(data), "source_embedded_bytes_exact": True})

    mtl = ["# Neutral default mesh transfer; no skin, skeleton, clips or control rig.", "# Only base color and standard OBJ material properties are mapped automatically.", "# Original glTF PBR images/bindings are retained in transfer-manifest.json."]
    material_names = {}
    materials = []
    def texture_binding(info):
        if not info:
            return None
        texture = doc["textures"][info["index"]]
        assert "source" in texture, "texture extension-only source unsupported"
        return {"texture_index": info["index"], "image_index": texture["source"], "path": image_paths[texture["source"]], "texcoord": info.get("texCoord", 0), "source_binding": info}
    for index, material in enumerate(doc.get("materials", [])):
        name = f"material_{index:02d}_" + safe_name(material.get("name", "courier"))
        material_names[index] = name
        pbr = material.get("pbrMetallicRoughness", {})
        color = pbr.get("baseColorFactor", [1, 1, 1, 1])
        base_color = texture_binding(pbr.get("baseColorTexture"))
        normal_binding = texture_binding(material.get("normalTexture"))
        metallic_binding = texture_binding(pbr.get("metallicRoughnessTexture"))
        mtl += ["", "newmtl " + name, "Ka 0 0 0", "Kd " + " ".join(format(v, ".12g") for v in color[:3]), "d " + format(color[3], ".12g"), "illum 2"]
        if base_color:
            assert base_color["texcoord"] == 0 and "extensions" not in base_color["source_binding"], "MTL mapping needs unsupported UV transform"
            mtl.append("map_Kd " + base_color["path"])
        materials.append({"index": index, "obj_name": name, "gltf_material": material, "base_color": base_color, "normal": normal_binding, "metallic_roughness": metallic_binding, "mtl_mapping": "baseColorFactor Kd/d and baseColorTexture map_Kd only; no automatic normal/metallic/roughness shader claim"})

    obj = ["# Offline neutral default mesh in centimetres, +Y up, original Z sign.", "# UV: glTF upper-left origin (u,v) -> conventional OBJ lower-left origin (u,1-v).", "# Original PNG bytes unchanged; no image flip.", "# Skin, joints, clips, morphs and control rigs are deliberately excluded.", "mtllib courier-neutral-maya-cm.mtl"]
    all_points, exported_points, objects, bind_checks = [], [], [], []
    source_gltf_uvs, expected_uvs, expected_normals, expected_triangle_indices = [], [], [], []
    vertex_offset = uv_offset = normal_offset = triangle_count = 0
    for node_index, world in worlds.items():
        node = nodes[node_index]
        if "mesh" not in node:
            continue
        assert not node.get("weights"), "default morph weights require explicit handling"
        mesh = doc["meshes"][node["mesh"]]
        assert not mesh.get("weights"), "default morph weights require explicit handling"
        normal_matrix, determinant = inverse_transpose_linear(world)
        assert determinant > 0, "negative scale requires an explicitly reviewed winding policy"
        if "skin" in node:
            skin = doc["skins"][node["skin"]]
            if "inverseBindMatrices" in skin:
                residuals = []
                for joint, ib in zip(skin["joints"], accessor(skin["inverseBindMatrices"])):
                    assert joint in worlds, "skin joint outside the selected default scene"
                    matrix = [[ib[c*4 + r] for c in range(4)] for r in range(4)]
                    check = mul(worlds[joint], matrix)
                    residuals.append(max(abs(check[r][c] - world[r][c]) for r in range(4) for c in range(4)))
                residual = max(residuals)
                bind_checks.append({"mesh_node": node.get("name"), "max_abs_component_residual": residual, "tolerance": 1e-5, "consistent_with_stored_default_trs_within_tolerance": residual <= 1e-5, "meaning": "world_default_joint * inverseBind versus world_default_mesh; numerical check only, not host bind-pose verification"})
        for primitive_index, primitive in enumerate(mesh["primitives"]):
            assert primitive.get("mode", 4) == 4, "only triangle primitives supported"
            assert not primitive.get("targets"), "morph targets excluded; explicit review required"
            attrs = primitive["attributes"]
            positions = accessor(attrs["POSITION"])
            normals = accessor(attrs["NORMAL"]) if "NORMAL" in attrs else None
            uvs = accessor(attrs["TEXCOORD_0"]) if "TEXCOORD_0" in attrs else None
            assert normals is None or len(normals) == len(positions)
            assert uvs is None or len(uvs) == len(positions)
            indices = [row[0] for row in accessor(primitive["indices"])] if "indices" in primitive else list(range(len(positions)))
            assert len(indices) % 3 == 0 and all(0 <= i < len(positions) for i in indices)
            object_name = safe_name(node.get("name", f"node_{node_index}")) + f"_primitive_{primitive_index}"
            obj += ["", "o " + object_name]
            world_positions = [point(world, p) for p in positions]
            for p in world_positions:
                centimetres = [v*100 for v in p]
                strings = [format(v, ".12g") for v in centimetres]
                obj.append("v " + " ".join(strings))
                all_points.append(p)
                exported_points.append(tuple(float(s) for s in strings))
            if uvs:
                converted_uvs = [(uv[0], 1.0 - uv[1]) for uv in uvs]
                obj += ["vt " + " ".join(format(v, ".12g") for v in uv) for uv in converted_uvs]
                source_gltf_uvs.extend(uv[:2] for uv in uvs)
                expected_uvs.extend(converted_uvs)
            if normals:
                transformed_normals = [normal(normal_matrix, n) for n in normals]
                obj += ["vn " + " ".join(format(v, ".12g") for v in n) for n in transformed_normals]
                expected_normals.extend(transformed_normals)
            if "material" in primitive:
                obj.append("usemtl " + material_names[primitive["material"]])
            for i in range(0, len(indices), 3):
                corners = []
                for j in indices[i:i+3]:
                    v = vertex_offset + j + 1
                    t = uv_offset + j + 1 if uvs else ""
                    n = normal_offset + j + 1 if normals else ""
                    corners.append(f"{v}/{t}/{n}" if normals or uvs else str(v))
                obj.append("f " + " ".join(corners))
            expected_triangle_indices.extend(vertex_offset + j + 1 for j in indices)
            ntri = len(indices)//3
            objects.append({"obj_name": object_name, "source_node_index": node_index, "source_mesh_index": node["mesh"], "source_primitive_index": primitive_index, "vertices": len(positions), "uv_entries": len(uvs) if uvs else 0, "normal_entries": len(normals) if normals else 0, "triangles": ntri, "world_default_matrix_row_major": world, "linear_determinant": determinant, "triangle_order_and_winding": "source index order unchanged", "source_skin_index_discarded": node.get("skin")})
            vertex_offset += len(positions)
            uv_offset += len(uvs) if uvs else 0
            normal_offset += len(normals) if normals else 0
            triangle_count += ntri
    assert all_points, "default scene has no mesh"
    obj_path = output / "courier-neutral-maya-cm.obj"
    mtl_path = output / "courier-neutral-maya-cm.mtl"
    obj_path.write_text("\n".join(obj) + "\n", encoding="utf-8", newline="\n")
    mtl_path.write_text("\n".join(mtl) + "\n", encoding="utf-8", newline="\n")
    # Independent textual readback of OBJ counts and positions proves the written
    # representation, not only the pre-serialization calculation.
    lines = obj_path.read_text(encoding="utf-8").splitlines()
    read_positions = [tuple(map(float, line.split()[1:])) for line in lines if line.startswith("v ")]
    read_uvs = [tuple(map(float, line.split()[1:])) for line in lines if line.startswith("vt ")]
    read_normals = [tuple(map(float, line.split()[1:])) for line in lines if line.startswith("vn ")]
    read_faces = [line.split()[1:] for line in lines if line.startswith("f ")]
    assert read_positions == exported_points
    assert len(read_positions) == vertex_offset and len(read_faces) == triangle_count
    assert all(len(face) == 3 for face in read_faces)
    assert all(1 <= int(corner.split("/")[0]) <= vertex_offset for face in read_faces for corner in face)
    read_triangle_indices = [int(corner.split("/")[0]) for face in read_faces for corner in face]
    assert read_triangle_indices == expected_triangle_indices, "triangle ordering changed"
    assert len(read_uvs) == len(expected_uvs) and len(read_normals) == len(expected_normals)
    uv_error = max((abs(a[i] - b[i]) for a, b in zip(read_uvs, expected_uvs) for i in range(2)), default=0)
    inverse_uv_error = max((max(abs(written[0] - source_uv[0]), abs((1.0 - written[1]) - source_uv[1])) for written, source_uv in zip(read_uvs, source_gltf_uvs)), default=0)
    normal_error = max((abs(a[i] - b[i]) for a, b in zip(read_normals, expected_normals) for i in range(3)), default=0)
    assert uv_error < 1e-9 and inverse_uv_error < 1e-9 and normal_error < 1e-9
    inverse_scale_error = max(abs(p[i] - q[i]/100) for p, q in zip(all_points, read_positions) for i in range(3))
    assert inverse_scale_error < 1e-9
    assert sha(source.read_bytes()) == args.expected_sha256, "source changed during conversion"
    files = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "transfer-manifest.json":
            data = path.read_bytes()
            files.append({"path": path.relative_to(output).as_posix(), "bytes": len(data), "sha256": sha(data)})
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "OFFLINE_NEUTRAL_DEFAULT_MESH_BRIDGE_ONLY_NOT_HOST_VALIDATED",
        "source": {"path": str(source), "bytes": len(raw), "sha256": args.expected_sha256, "unchanged_after_conversion": True, "generator_metadata": doc.get("asset", {}).get("generator")},
        "definition": "Stored mesh POSITION/NORMAL arrays under the selected glTF default scene's stored node matrices/TRS, and TEXCOORD_0 converted from glTF upper-left origin to conventional OBJ lower-left origin with (u,1-v). Skins, clips and morphs are omitted. Neutral default mesh is a transfer label, not an artist-approved pose or host-verified bind pose.",
        "selected_scene": {"index": selected_scene, "name": doc["scenes"][selected_scene].get("name"), "roots": doc["scenes"][selected_scene].get("nodes", [])},
        "coordinates": {"source": "glTF +Y up, metres, right-handed", "output": "OBJ +Y up, centimetres, right-handed", "position_scale": 100, "z_sign_change": False, "axis_rotation": "none", "host_axis_or_unit_conversion_executed": False},
        "normals": "Applied inverse transpose of default mesh-node world linear transform, then normalized; positive determinant only. No normal-map green-channel flip or tangent-space shader reconstruction performed.",
        "uv_origin_conversion": {"source": "glTF TEXCOORD_0 with upper-left image origin", "output": "conventional OBJ/MTL vt with lower-left image origin", "forward": "obj_u = gltf_u; obj_v = 1 - gltf_v", "inverse": "gltf_u = obj_u; gltf_v = 1 - obj_v", "image_bytes_flipped": False, "scope": "Base-color lookup convention bridge; target importer behavior and full PBR reconstruction require actual host validation"},
        "counts": {"vertices": vertex_offset, "uv_entries": uv_offset, "normal_entries": normal_offset, "triangles": triangle_count, "objects": len(objects)},
        "bbox_source_default_world_m": bbox(all_points), "bbox_obj_cm": bbox(read_positions),
        "inverse_scale_max_abs_error_m": inverse_scale_error,
        "uv_max_abs_serialization_error": uv_error,
        "uv_inverse_origin_conversion_max_abs_error": inverse_uv_error,
        "transformed_normal_max_abs_serialization_error": normal_error,
        "rest_inverse_bind_consistency": bind_checks,
        "bind_pose_naming_allowed": False,
        "discarded": {"skins": len(doc.get("skins", [])), "joint_references": sum(len(s.get("joints", [])) for s in doc.get("skins", [])), "animation_clips": [a.get("name") for a in doc.get("animations", [])], "control_rig": "not represented or claimed"},
        "objects": objects, "images": images, "materials": materials,
        "files": files,
        "checks": {"source_hash_matches_audited_asset": True, "source_readback_unchanged": True, "obj_text_counts_and_face_indices_valid": True, "triangle_sequence_and_winding_preserved": True, "obj_converted_uv_and_transformed_normal_serialization_error_below_1e_9": True, "uv_inverse_origin_conversion_error_below_1e_9": True, "inverse_unit_scaling_error_below_1e_9_m": True, "embedded_image_byte_preservation": True, "nonempty_output_directory_refused_before_writes": True},
        "rights": {"scope": "Private workspace preparation only; no upload/public redistribution", "notice": "Source generated asset remains governed by Hyper3D Terms and account/plan conditions; not MIT-relicensed", "source_notice": str(source.parents[1] / "notices/ASSET-RIGHTS.md")},
        "limitations": ["No Maya/Blender host launched; no import, shader reconstruction, save/reopen, rig, skinning, foot contact, deformation, animation export or visual acceptance.", "OBJ/MTL base color mapping cannot faithfully encode the full glTF PBR shader. Original normal and packed metallic/roughness images are preserved as bytes and in bindings, but require correct host material wiring.", "This bridge is static mesh geometry only. The previous 17-joint skin and five clips are deliberately omitted to permit independent rig comparisons.", "Default TRS/inverse-bind consistency is a numerical source audit, not evidence that mGear/AdvancedSkeleton/Rigify can fit or build this character."]
    }
    (output / "transfer-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "counts": manifest["counts"], "bbox_obj_cm": manifest["bbox_obj_cm"], "inverse_scale_max_abs_error_m": inverse_scale_error, "rest_inverse_bind_consistency": bind_checks, "files": files}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
