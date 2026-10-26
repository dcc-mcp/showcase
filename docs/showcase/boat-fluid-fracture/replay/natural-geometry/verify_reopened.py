"""Recover/reopen the completed geometry audit using exact cached files; no recook."""

import hashlib
import json
from pathlib import Path
import time


FILES = {"REST_RENDER": ("READY_RENDER", "render_pieces.bgeo.sc"),
         "REST_FULL_SDF": ("READY_FULL_SDF", "native_proxy.bgeo.sc"),
         "REST_PROXY": ("READY_PROXY", "collision_proxy.bgeo.sc"),
         "REST_CONSTRAINTS": ("READY_CONSTRAINTS", "constraints_raw.bgeo.sc")}


def execute(hou, config):
    started = time.monotonic()
    output = Path(config["out_dir"]).resolve()
    phase = config.get("phase", "reopened")
    assert phase in ("recovered", "reopened")
    report_path = output / (phase + ".json")
    assert not report_path.exists(), "Preserve existing receipt"
    original_report = output / "cold-rebuild.json"
    baseline = json.loads(original_report.read_text())
    assert baseline["piece_count"] == 71 and baseline["constraint_count"] == 171
    assert baseline["all_closed_positive_volume"]
    assert all(all(checks.values()) for row in baseline["comparisons"].values() for checks in row.values())
    assert all(not row["unsafe_candidates"] for owners in baseline["privacy"].values() for row in owners.values())
    if phase == "reopened":
        assert Path(hou.hipFile.path()).name == "native-wood-rest.hip"
    parent = hou.node("/obj/natural_v2_source")
    files, checks = {}, {}
    for role, (node_name, filename) in FILES.items():
        path = output / "geometry" / "rest" / filename
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        assert checksum == baseline["files"][role]["sha256"]
        node = parent.node(node_name)
        assert node.type().name() == "file" and Path(node.evalParm("file")).resolve() == path
        current = node.geometry()
        disk = hou.Geometry()
        disk.loadFromFile(str(path))
        row = {"file_sha256_unchanged": True, "raw_file_sop": True,
               "point_count": len(current.points()) == baseline["files"][role]["points"],
               "primitive_count": len(current.prims()) == baseline["files"][role]["primitives"],
               "P_exact": current.pointFloatAttribValues("P") == disk.pointFloatAttribValues("P")}
        for name in ("name", "path", "surface_role"):
            if disk.findPrimAttrib(name):
                row[name + "_exact"] = current.primStringAttribValues(name) == disk.primStringAttribValues(name)
        if disk.findPointAttrib("name"):
            row["endpoint_names_exact"] = current.pointStringAttribValues("name") == disk.pointStringAttribValues("name")
        for name in ("uv", "N"):
            if disk.findVertexAttrib(name):
                row[name + "_exact"] = current.vertexFloatAttribValues(name) == disk.vertexFloatAttribValues(name)
        assert all(row.values()), (role, row)
        checks[role] = row
        files[role] = {"path": filename, "sha256": checksum, "bytes": path.stat().st_size}
    if config.get("reference_rest"):
        reference = hou.Geometry()
        reference.loadFromFile(str(Path(config["reference_rest"]) / "constraints_raw.bgeo.sc"))
        current = parent.node("READY_CONSTRAINTS").geometry()
        endpoint_names_exact = current.pointStringAttribValues("name") == reference.pointStringAttribValues("name")
        restlength_exact = current.primFloatAttribValues("restlength") == reference.primFloatAttribValues("restlength")
        groups_exact = {group.name(): [p.number() for p in group.prims()] for group in current.primGroups()} == {group.name(): [p.number() for p in group.prims()] for group in reference.primGroups()}
        assert endpoint_names_exact and restlength_exact and groups_exact
    else:
        endpoint_names_exact = restlength_exact = groups_exact = None
    report = {"schema_version": 1, "phase": phase, "scope": "native rest cache reader/save/reopen only",
              "houdini_version": hou.applicationVersionString(), "piece_count": 71, "constraint_count": 171,
              "cold_report_sha256": hashlib.sha256(original_report.read_bytes()).hexdigest(),
              "files": files, "checks": checks,
              "original_constraint_endpoint_names_exact": endpoint_names_exact,
              "original_constraint_restlength_exact": restlength_exact,
              "original_constraint_groups_exact": groups_exact,
              "closed_mass_audit_bound_by_unchanged_file_hashes": True,
              "reopened": phase == "reopened", "elapsed_seconds": time.monotonic() - started,
              "not_claimed": baseline["not_claimed"]}
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if "hou" in globals():
    result = execute(hou, context)
