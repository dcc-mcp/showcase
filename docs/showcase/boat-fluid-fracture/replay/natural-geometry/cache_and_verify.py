"""Bounded rest-geometry cache/audit inside Houdini; no simulation or scene clearing."""

from array import array
import hashlib
import json
import math
from pathlib import Path
import re
import runpy
import time


HELPERS = runpy.run_path(str(Path(__file__).with_name("mass_properties.py")))
mass_properties = HELPERS["mass_properties"]
outside_attribute_samples = HELPERS["outside_attribute_samples"]
ROLES = {"REST_RENDER": "render_pieces.bgeo.sc", "REST_FULL_SDF": "native_proxy.bgeo.sc",
         "REST_PROXY": "collision_proxy.bgeo.sc", "REST_CONSTRAINTS": "constraints_raw.bgeo.sc"}


def inventory(path):
    return {"path": path.name, "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def topology(geometry):
    values = array("I")
    for primitive in geometry.prims():
        points = primitive.points()
        values.append(len(points))
        values.extend(point.number() for point in points)
    return hashlib.sha256(values.tobytes()).hexdigest()


def privacy(geometry, hou):
    tables, unsafe = [], []
    pattern = re.compile(r"[A-Za-z]:[\\/]|\\\\|/(?:Users|home)/|https?://|api[_-]?key|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
    for owner, attributes in (("point", geometry.pointAttribs()), ("vertex", geometry.vertexAttribs()),
                              ("primitive", geometry.primAttribs()), ("detail", geometry.globalAttribs())):
        for attribute in attributes:
            if attribute.dataType() != hou.attribData.String:
                continue
            values = sorted(attribute.strings())
            matches = [value for value in values if pattern.search(value)]
            if matches:
                unsafe.append({"owner": owner, "attribute": attribute.name(), "matches": len(matches)})
            tables.append({"owner": owner, "attribute": attribute.name(), "unique_values": len(values),
                           "table_sha256": hashlib.sha256(json.dumps(values).encode()).hexdigest()})
    assert not unsafe, f"Private string-attribute candidates: {unsafe}"
    return {"all_string_attribute_tables_checked": True, "unsafe_candidates": unsafe, "tables": tables}


def compare(geometry, reference):
    checks = {"point_count": len(geometry.points()) == len(reference.points()),
              "primitive_count": len(geometry.prims()) == len(reference.prims()),
              "P_exact": geometry.pointFloatAttribValues("P") == reference.pointFloatAttribValues("P"),
              "topology_exact": topology(geometry) == topology(reference)}
    for name in ("name", "path", "surface_role"):
        if geometry.findPrimAttrib(name) or reference.findPrimAttrib(name):
            checks[name + "_exact"] = bool(geometry.findPrimAttrib(name) and reference.findPrimAttrib(name)) and geometry.primStringAttribValues(name) == reference.primStringAttribValues(name)
    for name in ("sourceprim", "is_cutface"):
        if geometry.findPrimAttrib(name) or reference.findPrimAttrib(name):
            checks[name + "_exact"] = bool(geometry.findPrimAttrib(name) and reference.findPrimAttrib(name)) and geometry.primIntAttribValues(name) == reference.primIntAttribValues(name)
    for name in ("uv", "N"):
        if geometry.findVertexAttrib(name) or reference.findVertexAttrib(name):
            checks[name + "_exact"] = bool(geometry.findVertexAttrib(name) and reference.findVertexAttrib(name)) and geometry.vertexFloatAttribValues(name) == reference.vertexFloatAttribValues(name)
    assert all(checks.values()), checks
    return checks


def execute(hou, config):
    started = time.monotonic()
    output = Path(config["out_dir"]).resolve()
    phase = config.get("phase", "cache")
    assert phase in ("cache", "reopened")
    target = output / "geometry" / "rest"
    report_file = output / ("cold-rebuild.json" if phase == "cache" else "reopened.json")
    assert not report_file.exists(), "Never overwrite acceptance evidence"
    if phase == "cache":
        target.mkdir(parents=True, exist_ok=False)
    else:
        assert target.is_dir()
    parent = hou.node("/obj/natural_v2_source")
    assert parent and [node.name() for node in hou.node("/obj").children()] == [parent.name()]
    source = parent.node("SOURCE_SI").geometry()
    assert len(source.prims()) == 500000 and len(source.points()) == 249960
    assert source.findVertexAttrib("uv") and source.findVertexAttrib("N")
    geometries, files, comparisons, privacy_checks = {}, {}, {}, {}
    reference_root = Path(config["reference_rest"]) if config.get("reference_rest") else None
    for node_name, filename in ROLES.items():
        node = parent.node(node_name)
        node.cook(force=False)
        assert not node.errors(), (node_name, node.errors())
        geometry = node.geometry()
        assert all(math.isfinite(value) for value in geometry.pointFloatAttribValues("P"))
        geometries[node_name] = geometry
        privacy_checks[node_name] = {"fresh": privacy(geometry, hou)}
        path = target / filename
        if phase == "cache":
            assert not path.exists()
            geometry.saveToFile(str(path))
        cached = hou.Geometry()
        cached.loadFromFile(str(path))
        comparisons[node_name] = {"saved_cache": compare(geometry, cached)}
        if reference_root:
            reference = hou.Geometry()
            reference.loadFromFile(str(reference_root / filename))
            comparisons[node_name]["original_accepted_rest"] = compare(geometry, reference)
            privacy_checks[node_name]["original"] = privacy(reference, hou)
        files[node_name] = dict(inventory(path), points=len(geometry.points()), primitives=len(geometry.prims()))
    render, full = geometries["REST_RENDER"], geometries["REST_FULL_SDF"]
    full_equals_render = compare(full, render)
    names = set(render.primStringAttribValues("name"))
    assert len(names) == 71 and "naturalwood-intact_hull-8-10" not in names
    assert set(geometries["REST_PROXY"].primStringAttribValues("name")) == names
    assert len(geometries["REST_PROXY"].prims()) == 20000
    constraints = geometries["REST_CONSTRAINTS"]
    assert len(constraints.prims()) == 171 and set(constraints.pointStringAttribValues("name")) == names
    for primitive in constraints.prims():
        endpoints = primitive.points()
        assert len(endpoints) == 2 and endpoints[0].stringAttribValue("name") != endpoints[1].stringAttribValue("name")
    native_integral = sum(row["wood_volume_m3"] for row in mass_properties(source, density=1).values())
    orientation = 1 if native_integral > 0 else -1
    pieces = mass_properties(render, density=400, orientation_sign=orientation)
    assert all(row["volume_valid"] for row in pieces.values())
    volume = sum(row["wood_volume_m3"] for row in pieces.values())
    source_volume = abs(native_integral)
    relative_error = abs(volume - source_volume) / source_volume
    assert relative_error < 1e-6
    samples = outside_attribute_samples(render, source)
    assert samples["sampled_uv_normal_preservation_pass"]
    if reference_root:
        old = json.loads((reference_root / "piece-audit.json").read_text())
        assert set(old["pieces"]) == names
        for name in names:
            assert abs(pieces[name]["mass_kg"] - old["pieces"][name]["mass_kg"]) < 1e-7
            assert max(abs(a - b) for a, b in zip(pieces[name]["center_of_mass_m"], old["pieces"][name]["center_of_mass_m"])) < 1e-7
    report = {"schema_version": 1, "scope": "native wood rest geometry only",
              "phase": phase, "houdini_version": hou.applicationVersionString(),
              "native_fracture_type": parent.node("native_wood_fracture").type().name(),
              "piece_count": len(names), "constraint_count": len(constraints.prims()),
              "files": files, "comparisons": comparisons, "privacy": privacy_checks,
              "full_sdf_source_equals_render": full_equals_render, "density_kg_m3": 400,
              "orientation_factor": orientation, "total_wood_volume_m3": volume,
              "source_wood_volume_m3": source_volume, "volume_relative_error": relative_error,
              "total_mass_kg": sum(row["mass_kg"] for row in pieces.values()),
              "all_closed_positive_volume": all(row["volume_valid"] for row in pieces.values()),
              "outside_attribute_samples": samples,
              "elapsed_seconds": time.monotonic() - started,
              "not_claimed": ["71 independent FLIP solids or actors", "blast fracture or flotation",
                              "contact/inertia/shrink qualification of collision proxies",
                              "native full inertia tensor override", "self intersection or minimum thickness certification"]}
    report_file.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {key: value for key, value in report.items() if key not in ("comparisons", "privacy")}


if "hou" in globals():
    result = execute(hou, context)
