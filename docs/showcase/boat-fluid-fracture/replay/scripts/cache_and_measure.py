"""Cache one coupled native simulation and retain actual per-piece state."""

import json
import math
from pathlib import Path
import time


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def cache_and_measure(hou, output_dir, output_root, end_frame=2,
                      pieces_sop_path="/obj/boat_fluid_output/solved_hires_pieces"):
    target = Path(output_dir).resolve()
    base = Path(output_root).resolve()
    assert target.parent == base, "Output must be one fresh named run under output_root"
    assert isinstance(end_frame, int) and not isinstance(end_frame, bool) and 1 <= end_frame <= 96
    assert abs(hou.fps() - 24) < 1e-6, "Scene must use the intended 24 fps"
    assert not target.exists(), "Preserve previous trials; choose a new run directory"
    dopnet = hou.node("/obj/boat_fluid_dop")
    source = hou.node("/obj/boat_fluid_source/SHIP_PARTS")
    pieces_sop = hou.node(pieces_sop_path)
    water_sop = hou.node("/obj/boat_fluid_output/water_particles")
    assert all(node is not None for node in (dopnet, source, pieces_sop, water_sop))
    source_geo = source.geometry()
    paths = set(source_geo.primStringAttribValues("path"))
    names = set(source_geo.primStringAttribValues("name"))
    assert len(paths) == len(names) == 17 and "" not in names, "Expected 17 unique Hyper3D parts"
    assert source_geo.findVertexAttrib("uv") is not None, "Preserve original vertex UVs"
    assert abs(source_geo.boundingBox().sizevec()[2] - 6) < 0.01
    assert abs(source_geo.boundingBox().minvec()[1] + 0.25) < 0.01
    target.mkdir()
    cache_dir = target / "cache"
    cache_dir.mkdir()
    (target / "renders").mkdir()
    body_setup = dopnet.node("boat_pieces")
    water_setup = dopnet.node("boat_water")
    water_solver = dopnet.node("water_solver")
    report = {"status": "running", "source_part_count": len(names), "frames": [],
              "piece_cache_source": pieces_sop.path(),
              "source_paths": sorted(paths), "source_names": sorted(names),
              "collision_sdf_divsize": body_setup.evalParm("divsize"),
              "collision_surface_offset": body_setup.evalParm("offset"),
              "particle_separation": water_setup.evalParm("particlesep"),
              "grid_scale": water_setup.evalParm("gridscale"),
              "feedback_scale": water_solver.evalParm("feedbackscale"),
              "particles_per_voxel": water_solver.evalParm("partpervoxel"),
              "fracture_verified": False, "flotation_verified": False}
    started = time.monotonic()
    initial_attached = set()
    try:
        hou.setFrame(1)
        hou.hipFile.save(str(target / "boat-fluid.hip"))
        for frame in range(1, end_frame + 1):
            if (target / "STOP").exists():
                report["status"] = "stopped"
                break
            hou.setFrame(frame)
            # Preserve DOP caches while time advances.
            dopnet.cook(force=False)
            simulation = dopnet.simulation()
            assert abs(simulation.time() - (frame - 1) / 24) < 1e-6, "Native simulation time does not match the requested frame"
            water = simulation.findObject("boat_water")
            assert water is not None
            fluid_geo = water.geometry()
            assert fluid_geo is not None and len(fluid_geo.points()) > 0, "Empty fluid"
            bodies = []
            for obj in simulation.objects():
                if obj.name() not in names:
                    continue
                geometry = obj.geometry()
                assert geometry is not None and len(geometry.points()) > 0, obj.name()
                matrix = obj.transform()
                assert all(math.isfinite(value) for value in matrix.asTuple()), obj.name()
                bounds = geometry.boundingBox() * matrix
                position = obj.findSubData("Position").options()
                glue_to = position.field("glueobject")
                impulse = float(position.field("glueimpulse"))
                feedback = obj.findSubData("Feedback")
                stress = obj.findSubData("BoatFluidStress")
                stress_values = {}
                if stress is not None:
                    stress_options = stress.options()
                    for field in ("method", "load_ratio_g", "peak_load_ratio_g", "feedback_record_count", "fluid_object_id",
                                  "sample_time", "timestep", "threshold_g", "mass_used", "release_enabled",
                                  "released", "release_time", "release_load_ratio_g", "record_fields"):
                        stress_values[field] = stress_options.field(field)
                    stress_values["force_vector"] = list(stress_options.field("force_vector"))
                bodies.append({"name": obj.name(), "center": list(bounds.center()),
                               "bbox_min": list(bounds.minvec()), "bbox_max": list(bounds.maxvec()),
                               "glueobject": glue_to, "glueimpulse": impulse,
                               "mass": float(position.field("mass")),
                               "velocity": list(position.field("vel")),
                               "hydrodynamic_load": stress_values,
                               "feedback_records": {kind: len(feedback.records(kind))
                                                    for kind in feedback.recordTypes()} if feedback else {}})
            assert len(bodies) == 17, "Expected 17 solved part bodies; got {}".format(len(bodies))
            attached = {body["name"] for body in bodies if body["glueobject"]}
            if frame == 1:
                initial_attached = attached
                assert initial_attached, "The ship must start with native glue attachments"
            pieces_geo = pieces_sop.geometry()
            particle_geo = water_sop.geometry()
            assert len(pieces_geo.prims()) > 0 and len(particle_geo.points()) > 0
            assert pieces_geo.findVertexAttrib("uv") is not None, "Solved cache lost vertex UVs"
            files = [cache_dir / "pieces.{:04d}.bgeo.sc".format(frame),
                     cache_dir / "water_particles.{:04d}.bgeo.sc".format(frame)]
            for geometry, path in zip((pieces_geo, particle_geo), files):
                assert not path.exists()
                geometry.saveToFile(str(path))
                assert path.is_file() and path.stat().st_size > 0
            pressure_geo = water.fieldGeometry("pressure")
            pressure_max = None
            if pressure_geo is not None and pressure_geo.prims():
                pressure_max = max(pressure_geo.prims()[0].allVoxels())
            report["frames"].append({"frame": frame, "sim_time": simulation.time(),
                "fluid_points": len(fluid_geo.points()),
                "fluid_bbox_min": list(fluid_geo.boundingBox().minvec()),
                "fluid_bbox_max": list(fluid_geo.boundingBox().maxvec()),
                "pressure_max": pressure_max, "pieces": bodies,
                "attached_count": len(attached), "released_names": sorted(initial_attached - attached),
                "cache": [{"path": str(path), "bytes": path.stat().st_size} for path in files],
                "errors": list(dopnet.errors()), "warnings": list(dopnet.warnings())})
            save_json(target / "metrics.json", report)
            assert not dopnet.errors(), dopnet.errors()
        if report["status"] != "stopped":
            report["status"] = "cached"
        report["fracture_verified"] = any(frame["released_names"] for frame in report["frames"])
        report["feedback_observed"] = any(body["feedback_records"] for frame in report["frames"]
                                          for body in frame["pieces"])
        report["max_glueimpulse"] = max((body["glueimpulse"] for frame in report["frames"]
                                        for body in frame["pieces"]), default=0)
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = "{}: {}".format(type(exc).__name__, exc)
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        save_json(target / "metrics.json", report)
    return {key: value for key, value in report.items() if key != "frames"}


if "hou" in globals():
    result = cache_and_measure(hou, context["output_dir"], context["output_root"], context.get("end_frame", 2),
                               context.get("pieces_sop_path", "/obj/boat_fluid_output/solved_hires_pieces"))
