"""Observe released parts against local cached water surfaces; no scene rebuild."""

import json
import math
from pathlib import Path
import statistics


BOUNDARY_CLEARANCE_M = 0.2
CONTAINER_INNER_PLANES_M = {"x_min": -4.05, "x_max": 4.05, "z_min": -5.05,
                            "z_max": 5.05, "floor_y": -1.3}


def boundary_clearance(low, high):
    planes = CONTAINER_INNER_PLANES_M
    return min(low[0] - planes["x_min"], planes["x_max"] - high[0],
               low[2] - planes["z_min"], planes["z_max"] - high[2], low[1] - planes["floor_y"])


def bounds_from_positions(positions):
    positions = iter(positions)
    first = tuple(next(positions))
    assert len(first) == 3 and all(math.isfinite(value) for value in first)
    low, high = list(first), list(first)
    for position in positions:
        assert len(position) == 3 and all(math.isfinite(value) for value in position)
        for axis in range(3):
            low[axis] = min(low[axis], position[axis])
            high[axis] = max(high[axis], position[axis])
    return {"min": low, "max": high, "center": [(a + b) / 2 for a, b in zip(low, high)]}


def visible_part_bounds(geometry):
    assert geometry.findPrimAttrib("name") is not None, "Visible cache must retain primitive part names"
    groups = {}
    for primitive, name in zip(geometry.prims(), geometry.primStringAttribValues("name")):
        assert name, "Visible cache contains an unnamed primitive"
        points = groups.setdefault(name, {})
        for vertex in primitive.vertices():
            point = vertex.point()
            number = point.number()
            if number not in points:
                points[number] = tuple(point.position())
    return {name: bounds_from_positions(points.values()) for name, points in groups.items()}


def physical_release_events(frames):
    initially_glued = {body["name"] for body in frames[0]["pieces"] if body["glueobject"]}
    events = {}
    for frame in frames:
        for body in frame["pieces"]:
            name = body["name"]
            if name in initially_glued and name not in events and not body["glueobject"]:
                marked = body.get("hydrodynamic_load", {}).get("released") == 1
                events[name] = {"first_release_frame": frame["frame"],
                                "release_origin": "fluid_load_rule" if marked else "native_glue_dynamics"}
    return initially_glued, events


def classify(samples, expected_count, tolerance=0.2):
    if len(samples) < expected_count:
        return "insufficient_window"
    if any(sample.get("error") for sample in samples):
        return "sample_failed"
    if any(sample["glueobject"] for sample in samples):
        return "reattached"
    if any(sample.get("boundary_clearance_m") is None or sample["boundary_clearance_m"] < BOUNDARY_CLEARANCE_M
           for sample in samples):
        return "boundary_contact_possible"
    if any(sample["waterline"] is None or not sample["center_hit"] or sample["ray_hits"] < 3
           for sample in samples):
        return "local_waterline_missing"
    if any(sample["bbox_max_y"] < sample["waterline"] - tolerance for sample in samples):
        return "submerged_in_window"
    if any(sample["bbox_min_y"] > sample["waterline"] + tolerance for sample in samples):
        return "airborne_in_window"
    speeds = [sample["vertical_speed"] for sample in samples]
    heights = [sample["center_y"] for sample in samples]
    if max(abs(speed) for speed in speeds) > 0.75 or abs(statistics.mean(speeds)) > 0.2:
        return "vertical_motion_not_settled"
    if max(heights) - min(heights) > 0.4:
        return "vertical_motion_not_settled"
    return "floating_observed"


def check_flotation(hou, output_dir, water_surface_path, water_cache_path, piece_cache_path,
                   window_frames=12, report_name="flotation-report.json"):
    target = Path(output_dir).resolve()
    report_path = target / report_name
    assert report_path.parent == target and report_path.suffix == ".json" and not report_path.exists()
    assert isinstance(window_frames, int) and not isinstance(window_frames, bool) and window_frames >= 8
    metrics = json.loads((target / "metrics.json").read_text())
    assert metrics["status"] in ("cached", "stopped"), "Analyze a finished or explicitly stopped run"
    frames = metrics["frames"]
    assert frames and all(frames[i]["frame"] + 1 == frames[i + 1]["frame"] for i in range(len(frames) - 1))
    initially_glued, release_events = physical_release_events(frames)
    release_frames = {name: event["first_release_frame"] for name, event in release_events.items()}
    water_surface = hou.node(water_surface_path)
    water_cache = hou.node(water_cache_path)
    piece_cache = hou.node(piece_cache_path)
    assert all(node is not None for node in (water_surface, water_cache, piece_cache))
    ancestors = water_surface.inputAncestors()
    assert water_cache in ancestors and piece_cache not in ancestors, "Use a water-only cached surface"
    assert not any(node.type().name().split("::")[0] == "dopimport" for node in ancestors)
    selected = frames[-window_frames:]
    samples = {name: [] for name in release_frames}
    report = {"scope": "coarse_vfx_proxy_observed_window", "flotation_verified": False,
              "piece_bounds_source": "cached_visible_mesh", "vertical_speed_source": "native_position_velocity",
              "release_detection": "initial native glue attachment became empty",
              "initially_glued_piece_count": len(initially_glued),
              "direct_fluid_rule_release_count": sum(event["release_origin"] == "fluid_load_rule" for event in release_events.values()),
              "native_glue_dynamics_release_count": sum(event["release_origin"] == "native_glue_dynamics" for event in release_events.values()),
              "minimum_solid_boundary_clearance_m": BOUNDARY_CLEARANCE_M,
              "container_inner_planes_m": CONTAINER_INNER_PLANES_M, "ceiling": "open",
              "boundary_geometry_basis": "recipes/02-sources-and-proxy.json: box inner wall faces and floor top",
              "boundary_test_basis": "minimum signed clearance of both visible and proxy bounds; 0.2m covers 0.08m body offset plus 0.08m static voxel approximation",
              "window_frames_required": window_frames, "waterline_tolerance_m": 0.2,
              "max_vertical_speed_m_s": 0.75, "max_mean_vertical_speed_m_s": 0.2,
              "max_vertical_excursion_m": 0.4, "metrics_status": metrics["status"],
              "mass_sample_frame": frames[-1]["frame"],
              "total_native_body_mass_kg": sum(body["mass"] for body in frames[-1]["pieces"]),
              "collision_surface_offset_m": metrics.get("collision_surface_offset"),
              "engineering_mass_verified": False,
              "proxy_limit": "Inflated collision SDFs also change native body mass; this is a VFX proxy",
              "first_frame": selected[0]["frame"], "last_frame": selected[-1]["frame"],
              "water_surface_path": water_surface_path, "pieces": {}, "cache_checks": []}
    previous_frame = hou.frame()
    try:
        for frame in selected:
            number = frame["frame"]
            hou.setFrame(number)
            checks = []
            visible_bounds = None
            for node, prefix in ((water_cache, "water_particles."), (piece_cache, "pieces.")):
                receipt = next(item for item in frame["cache"] if Path(item["path"]).name.startswith(prefix))
                actual = Path(node.parm("file").evalAtFrame(number)).resolve()
                assert actual == Path(receipt["path"]).resolve() and actual.stat().st_size == receipt["bytes"]
                geometry = node.geometry()
                assert all(math.isfinite(value) for value in geometry.pointFloatAttribValues("P"))
                if node == piece_cache:
                    visible_bounds = visible_part_bounds(geometry)
                checks.append({"path": str(actual), "bytes": actual.stat().st_size, "finite_positions": True})
            report["cache_checks"].append({"frame": number, "files": checks})
            geometry = water_surface.geometry()
            assert len(geometry.prims()) > 0, "Empty cached water surface"
            for body in frame["pieces"]:
                name = body["name"]
                if name not in samples or number < release_frames[name]:
                    continue
                row = {"frame": number, "glueobject": body["glueobject"], "source": "cached_visible_mesh",
                       "proxy_bbox_min_m": body["bbox_min"], "proxy_bbox_max_m": body["bbox_max"],
                       "proxy_center_m": body["center"]}
                try:
                    assert all(math.isfinite(value) for key in ("center", "bbox_min", "bbox_max", "velocity")
                               for value in body[key]), "Nonfinite recorded rigid state"
                    bounds = visible_bounds[name]
                    low, high, center = bounds["min"], bounds["max"], bounds["center"]
                    visible_clearance = boundary_clearance(low, high)
                    proxy_clearance = boundary_clearance(body["bbox_min"], body["bbox_max"])
                    xz = [(center[0], center[2])] + [(x, z) for x in (low[0], high[0])
                                                   for z in (low[2], high[2])]
                    top = max(high[1], geometry.boundingBox().maxvec()[1]) + 1
                    rays = []
                    for x, z in xz:
                        hit, normal, uvw = hou.Vector3(), hou.Vector3(), hou.Vector3()
                        primitive = geometry.intersect(hou.Vector3((x, top, z)), hou.Vector3((0, -1, 0)),
                                                       hit, normal, uvw)
                        rays.append(float(hit[1]) if primitive >= 0 else None)
                    valid = [height for height in rays if height is not None and math.isfinite(height)]
                    row.update(center_y=center[1], bbox_min_y=low[1], bbox_max_y=high[1],
                               bbox_min_m=low, bbox_max_m=high, center_m=center,
                               visible_boundary_clearance_m=visible_clearance,
                               proxy_boundary_clearance_m=proxy_clearance,
                               boundary_clearance_m=min(visible_clearance, proxy_clearance),
                               vertical_speed=body["velocity"][1], local_rays_y=rays,
                               center_hit=rays[0] is not None, ray_hits=len(valid),
                               waterline=statistics.median(valid) if valid else None)
                except Exception as exc:
                    row["error"] = "{}: {}".format(type(exc).__name__, exc)
                samples[name].append(row)
    finally:
        hou.setFrame(previous_frame)
    for name, rows in samples.items():
        verdict = classify(rows, window_frames)
        speeds = [row["vertical_speed"] for row in rows if "vertical_speed" in row]
        report["pieces"][name] = {"verdict": verdict, "first_release_frame": release_frames[name],
            "release_origin": release_events[name]["release_origin"],
            "max_abs_vertical_speed": max((abs(speed) for speed in speeds), default=None),
            "mean_vertical_speed": statistics.mean(speeds) if speeds else None, "samples": rows}
    passing = sum(piece["verdict"] == "floating_observed" for piece in report["pieces"].values())
    report["released_piece_count"] = len(samples)
    report["floating_piece_count"] = passing
    report["flotation_verified"] = bool(samples) and passing == len(samples)
    report["verdict"] = ("released_pieces_float_in_observed_window" if report["flotation_verified"] else
                         "partial_flotation" if passing else "flotation_not_verified")
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return {key: value for key, value in report.items() if key not in ("pieces", "cache_checks")}


if "hou" in globals():
    result = check_flotation(hou, **context)
elif __name__ == "__main__":
    initial, events = physical_release_events([
        {"frame": 1, "pieces": [{"name": "native", "glueobject": "root"},
                                 {"name": "direct", "glueobject": "root"},
                                 {"name": "never_glued", "glueobject": ""}]},
        {"frame": 2, "pieces": [{"name": "native", "glueobject": ""},
                                 {"name": "direct", "glueobject": "", "hydrodynamic_load": {"released": 1}},
                                 {"name": "never_glued", "glueobject": ""}]}])
    assert initial == {"native", "direct"} and set(events) == initial
    assert events["native"] == {"first_release_frame": 2, "release_origin": "native_glue_dynamics"}
    assert events["direct"]["release_origin"] == "fluid_load_rule"
    assert bounds_from_positions(((4, 5, 6), (7, 8, 9))) == {
        "min": [4, 5, 6], "max": [7, 8, 9], "center": [5.5, 6.5, 7.5]}
    assert bounds_from_positions(((-5, -4, -3), (-2, -1, -0.5))) == {
        "min": [-5, -4, -3], "max": [-2, -1, -0.5], "center": [-3.5, -2.5, -1.75]}
    row = {"glueobject": "", "waterline": 0, "center_hit": True, "ray_hits": 5,
           "bbox_min_y": -0.1, "bbox_max_y": 0.2, "center_y": 0.05, "vertical_speed": 0.02,
           "boundary_clearance_m": 0.5}
    assert classify([dict(row) for _ in range(12)], 12) == "floating_observed"
    assert classify([dict(row, bbox_min_y=-1, bbox_max_y=-0.5) for _ in range(12)], 12) == "submerged_in_window"
    assert classify([dict(row, bbox_min_y=2, bbox_max_y=3) for _ in range(12)], 12) == "airborne_in_window"
    assert classify([dict(row, vertical_speed=2) for _ in range(12)], 12) == "vertical_motion_not_settled"
    assert classify([dict(row) for _ in range(3)], 12) == "insufficient_window"
    grounded = boundary_clearance((-0.2, -1.28, -0.2), (0.2, 0.1, 0.2))
    wall_supported = boundary_clearance((3.6, -0.1, -0.2), (4.0, 0.2, 0.2))
    assert classify([dict(row, boundary_clearance_m=grounded) for _ in range(12)], 12) == "boundary_contact_possible"
    assert classify([dict(row, boundary_clearance_m=wall_supported) for _ in range(12)], 12) == "boundary_contact_possible"
    print("PASS: physical release origins, visible bounds and flotation/boundary classifier math; no host")
