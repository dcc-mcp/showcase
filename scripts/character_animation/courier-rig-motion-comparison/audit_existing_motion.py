"""Read-only glTF animation/skin numerical audit using Python's standard library."""
import argparse
import bisect
import hashlib
import json
import math
import pathlib
import struct
from datetime import datetime, timezone

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=pathlib.Path, required=True)
parser.add_argument("--output-dir", type=pathlib.Path, required=True)
parser.add_argument("--expected-sha256", default="82a7b7456137eb133753650e2d9cda4f016ea810df68adcbfdc267f83ab29cd2")
args = parser.parse_args()
PATH = args.input.resolve()
OUTPUT_DIR = args.output_dir.resolve()
if OUTPUT_DIR.exists() and (not OUTPUT_DIR.is_dir() or any(OUTPUT_DIR.iterdir())):
    raise ValueError("output directory must be absent or empty; preserve previous audit evidence")
raw = PATH.read_bytes()
if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
    raise ValueError("source differs from the selected hash-bound derivative")
if not __debug__:
    raise ValueError("optimized Python is unsupported; runtime validation requires assertions")
assert struct.unpack_from("<4sII", raw) == (b"glTF", 2, len(raw))
chunks = []
offset = 12
while offset < len(raw):
    size, kind = struct.unpack_from("<II", raw, offset)
    chunks.append((kind, raw[offset + 8:offset + 8 + size]))
    offset += size + 8
doc = json.loads(next(data for kind, data in chunks if kind == 0x4E4F534A))
binary = next(data for kind, data in chunks if kind == 0x004E4942)
FORMATS = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
accessor_cache = {}

def accessor(index):
    if index in accessor_cache:
        return accessor_cache[index]
    item = doc["accessors"][index]
    assert "sparse" not in item, "sparse accessors require an explicit audit extension"
    fmt, size = FORMATS[item["componentType"]]
    width = WIDTHS[item["type"]]
    view = doc["bufferViews"][item["bufferView"]]
    assert view.get("buffer", 0) == 0
    start = view.get("byteOffset", 0) + item.get("byteOffset", 0)
    stride = view.get("byteStride", width * size)
    values = [struct.unpack_from("<" + fmt * width, binary, start + i * stride) for i in range(item["count"])]
    if item.get("normalized") and item["componentType"] != 5126:
        positive_max = {5120: 127, 5121: 255, 5122: 32767, 5123: 65535, 5125: 4294967295}[item["componentType"]]
        values = [tuple(max(-1.0, v / positive_max) for v in row) for row in values]
    accessor_cache[index] = values
    return values

def norm(q):
    length = math.sqrt(sum(v * v for v in q))
    assert length > 1e-12
    return tuple(v / length for v in q)

def slerp(a, b, t):
    a, b = norm(a), norm(b)
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0:
        b, dot = tuple(-v for v in b), -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return norm(tuple(x + t * (y - x) for x, y in zip(a, b)))
    angle = math.acos(dot)
    scale = math.sin(angle)
    return tuple((math.sin((1 - t) * angle) * x + math.sin(t * angle) * y) / scale for x, y in zip(a, b))

def identity():
    return [[float(r == c) for c in range(4)] for r in range(4)]

def multiply(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]

def compose(translation, quaternion, scale):
    x, y, z, w = norm(quaternion)
    rotation = [
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ]
    matrix = identity()
    for r in range(3):
        for c in range(3):
            matrix[r][c] = rotation[r][c] * scale[c]
        matrix[r][3] = translation[r]
    return matrix

def transform(matrix, vector):
    return tuple(sum(matrix[r][c] * vector[c] for c in range(3)) + matrix[r][3] for r in range(3))

def distance(a, b):
    return math.sqrt(sum((x - y)**2 for x, y in zip(a, b)))

nodes = doc.get("nodes", [])
parents = {}
for i, node in enumerate(nodes):
    for child in node.get("children", []):
        assert child not in parents, "node has multiple parents"
        parents[child] = i
names = {n.get("name"): i for i, n in enumerate(nodes)}
targets = [name for name in ("Root", "Hips", "Foot.L", "Foot.R") if name in names]

def sample_sampler(sampler, path, time):
    times = [v[0] for v in accessor(sampler["input"])]
    values = accessor(sampler["output"])
    method = sampler.get("interpolation", "LINEAR")
    assert method in ("LINEAR", "STEP", "CUBICSPLINE")
    if time <= times[0]:
        return values[1 if method == "CUBICSPLINE" else 0]
    if time >= times[-1]:
        return values[-2 if method == "CUBICSPLINE" else -1]
    i = bisect.bisect_right(times, time) - 1
    if method == "STEP":
        return values[i]
    interval = times[i + 1] - times[i]
    t = (time - times[i]) / interval
    if method == "CUBICSPLINE":
        a, out_tangent = values[3*i + 1], values[3*i + 2]
        in_tangent, b = values[3*(i + 1)], values[3*(i + 1) + 1]
        value = tuple((2*t**3 - 3*t*t + 1)*x + (t**3 - 2*t*t + t)*interval*tx + (-2*t**3 + 3*t*t)*y + (t**3 - t*t)*interval*ty for x, tx, y, ty in zip(a, out_tangent, b, in_tangent))
        return norm(value) if path == "rotation" else value
    a, b = values[i], values[i + 1]
    return slerp(a, b, t) if path == "rotation" else tuple(x + (y - x)*t for x, y in zip(a, b))

def world_matrices(animation=None, time=0.0):
    trs = [{"translation": n.get("translation", [0, 0, 0]), "rotation": n.get("rotation", [0, 0, 0, 1]), "scale": n.get("scale", [1, 1, 1])} for n in nodes]
    animated = set()
    if animation:
        for channel in animation["channels"]:
            target = channel["target"]
            assert target["path"] in ("translation", "rotation", "scale"), "unsupported animation path"
            index = target["node"]
            animated.add(index)
            trs[index][target["path"]] = sample_sampler(animation["samplers"][channel["sampler"]], target["path"], time)
    local = []
    for i, n in enumerate(nodes):
        if "matrix" in n:
            assert i not in animated
            local.append([[n["matrix"][c*4 + r] for c in range(4)] for r in range(4)])
        else:
            local.append(compose(**{"translation": trs[i]["translation"], "quaternion": trs[i]["rotation"], "scale": trs[i]["scale"]}))
    world = {}
    def calculate(i):
        if i not in world:
            world[i] = multiply(calculate(parents[i]), local[i]) if i in parents else local[i]
        return world[i]
    return [calculate(i) for i in range(len(nodes))]

rest_world = world_matrices()
bind_reports = []
for ni, node in enumerate(nodes):
    if "skin" not in node:
        continue
    skin = doc["skins"][node["skin"]]
    if "inverseBindMatrices" not in skin:
        continue
    inverse_binds = accessor(skin["inverseBindMatrices"])
    residuals = []
    for ji, node_joint in enumerate(skin["joints"]):
        column_major = inverse_binds[ji]
        inverse_bind = [[column_major[c*4 + r] for c in range(4)] for r in range(4)]
        combined = multiply(rest_world[node_joint], inverse_bind)
        residuals.append(max(abs(combined[r][c] - rest_world[ni][r][c]) for r in range(4) for c in range(4)))
    bind_reports.append({
        "skinned_node": node.get("name"),
        "check": "world_rest_joint * inverse_bind versus world_rest_skinned_node",
        "max_abs_component_residual": max(residuals),
        "per_joint_residuals": {nodes[j].get("name"): r for j, r in zip(skin["joints"], residuals)},
        "scope": "Numeric consistency check at stored rest TRS; does not establish deformed surface quality.",
    })
weight_reports = []
for node_index, node in enumerate(nodes):
    if "skin" not in node or "mesh" not in node:
        continue
    skin = doc["skins"][node["skin"]]
    for primitive_index, primitive in enumerate(doc["meshes"][node["mesh"]]["primitives"]):
        attributes = primitive["attributes"]
        joints = accessor(attributes["JOINTS_0"])
        weights = accessor(attributes["WEIGHTS_0"])
        assert len(joints) == len(weights)
        sums = [sum(v) for v in weights]
        weighted = set()
        for js, ws in zip(joints, weights):
            weighted.update(j for j, w in zip(js, ws) if w > 1e-8)
        weight_reports.append({
            "node": nodes[node_index].get("name"), "primitive": primitive_index,
            "vertex_count": len(weights), "skin_joint_count": len(skin["joints"]),
            "weight_sum_min": min(sums), "weight_sum_max": max(sums),
            "max_abs_weight_sum_error": max(abs(v - 1) for v in sums),
            "vertices_outside_sum_tolerance_1e_5": sum(abs(v - 1) > 1e-5 for v in sums),
            "zero_total_weight_vertices": sum(v <= 1e-8 for v in sums),
            "negative_weight_components": sum(v < 0 for row in weights for v in row),
            "nonfinite_weight_components": sum(not math.isfinite(v) for row in weights for v in row),
            "illegal_joint_components_any_weight": sum(j >= len(skin["joints"]) or j < 0 for row in joints for j in row),
            "illegal_joint_components_positive_weight": sum((j >= len(skin["joints"]) or j < 0) and w > 1e-8 for js, ws in zip(joints, weights) for j, w in zip(js, ws)),
            "weighted_joint_names": [nodes[skin["joints"][j]].get("name") for j in sorted(weighted) if 0 <= j < len(skin["joints"])],
        })

clips = []
trajectories = {}
joint_nodes = sorted({j for skin in doc["skins"] for j in skin["joints"]})
for animation in doc.get("animations", []):
    keys = sorted({row[0] for sampler in animation["samplers"] for row in accessor(sampler["input"])})
    start, end = keys[0], keys[-1]
    count = max(1, math.ceil((end - start)*120))
    times = sorted(set(keys + [start + (end - start)*i/count for i in range(count + 1)]))
    samples = []
    for t in times:
        matrices = world_matrices(animation, t)
        samples.append({"time_seconds": t, **{name: [matrices[names[name]][r][3] for r in range(3)] for name in targets}})
    trajectories[animation.get("name", "unnamed")] = samples
    first, last = world_matrices(animation, start), world_matrices(animation, end)
    endpoint_errors = {nodes[i].get("name", str(i)): distance([first[i][r][3] for r in range(3)], [last[i][r][3] for r in range(3)]) for i in joint_nodes}
    matrix_error = max(abs(first[i][r][c] - last[i][r][c]) for i in joint_nodes for r in range(4) for c in range(4))
    trajectory_summary = {}
    for name in targets:
        positions = [sample[name] for sample in samples]
        path_length = sum(distance(a, b) for a, b in zip(positions, positions[1:]))
        summary = {
            "start_xyz": positions[0], "end_xyz": positions[-1],
            "net_displacement_xyz": [positions[-1][i] - positions[0][i] for i in range(3)],
            "sampled_path_length": path_length,
            "xyz_min": [min(p[i] for p in positions) for i in range(3)],
            "xyz_max": [max(p[i] for p in positions) for i in range(3)],
        }
        if name.startswith("Foot"):
            min_y = min(p[1] for p in positions)
            low_segments = [(a, b) for a, b in zip(samples, samples[1:]) if a[name][1] <= min_y + 0.01 and b[name][1] <= min_y + 0.01]
            speeds = [math.hypot(b[name][0] - a[name][0], b[name][2] - a[name][2])/(b["time_seconds"] - a["time_seconds"]) for a, b in low_segments]
            summary["low_foot_proxy_within_0_01_of_observed_min_y"] = {
                "definition": "Foot joint origin, not sole contact. World horizontal motion without locomotion root or floor inference.",
                "segment_count": len(low_segments),
                "duration_seconds": sum(b["time_seconds"] - a["time_seconds"] for a, b in low_segments),
                "max_horizontal_speed": max(speeds) if speeds else None,
                "horizontal_path_length": sum(math.hypot(b[name][0] - a[name][0], b[name][2] - a[name][2]) for a, b in low_segments),
            }
        trajectory_summary[name] = summary
    clips.append({
        "name": animation.get("name"), "start_seconds": start, "end_seconds": end,
        "uniform_sample_rate_hz_minimum": 120, "sample_count_including_all_key_times": len(samples),
        "interpolation_methods": sorted({s.get("interpolation", "LINEAR") for s in animation["samplers"]}),
        "joint_world_origin_endpoint_max_distance": max(endpoint_errors.values()),
        "joint_world_origin_endpoint_distances": endpoint_errors,
        "joint_world_matrix_endpoint_max_abs_component_error": matrix_error,
        "trajectories": trajectory_summary,
    })

report = {
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "operation": "read_only_standard_library_gltf_sampler_hierarchy_and_skin_audit",
    "path": str(PATH), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    "coordinates": "glTF world coordinates, +Y up, metres by specification; no host/unit conversion performed",
    "rest_inverse_bind_audit": bind_reports,
    "skin_weight_audit": weight_reports, "clips": clips,
    "limitations": [
        "No host, plugin, renderer, export or reopen execution.",
        "Joint trajectories describe origins, not actual foot soles or skinned mesh contacts.",
        "Low-foot proxy is a numeric motion flag, not a grounding or foot-slide acceptance result.",
        "In-place clips require separately authored actor locomotion; zero Root displacement is not a defect by itself.",
        "Loop endpoint similarity is numerical continuity only; Attack/Cast are intentionally nonloop in source metadata.",
        "Endpoint checks do not test velocity or angular-velocity continuity across a loop seam.",
        "No visible joint deformation, intersections, silhouette or natural-speed motion review is established.",
        "Blender generator metadata and prior authored rig attribution do not establish a live compatible host or controller rig.",
    ],
}
out = OUTPUT_DIR / "motion-audit.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
trajectory_out = OUTPUT_DIR / "motion-trajectories.json"
trajectory_out.write_text(json.dumps({"sha256": report["sha256"], "coordinates": report["coordinates"], "samples": trajectories}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print(json.dumps({"report": str(out), "trajectories": str(trajectory_out), "skin_weight_audit": weight_reports, "clips": [{"name": c["name"], "samples": c["sample_count_including_all_key_times"], "endpoint_max_distance": c["joint_world_origin_endpoint_max_distance"], "root_displacement": c["trajectories"].get("Root", {}).get("net_displacement_xyz"), "feet": {k: v for k, v in c["trajectories"].items() if k.startswith("Foot")}} for c in clips]}, ensure_ascii=False, indent=2))
