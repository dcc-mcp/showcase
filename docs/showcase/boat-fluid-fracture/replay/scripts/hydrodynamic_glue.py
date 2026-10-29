"""Native Script Solver module: solve-pass-only fluid-load failure rule."""

import hou
import math

ALLOW_RELEASE = True
FAILURE_LOAD_G = 1.3
GRAVITY = 9.80665


def solveForObjects(solver_data, new_dop_objects, existing_dop_objects, time, timestep):
    assert hou.dop.isScriptSolverRunning(), "DOP state edits require a running Script Solver"
    solver_time = time
    assert math.isfinite(timestep) and timestep >= 0
    water = hou.dop.scriptSolverSimulation().findObject("boat_water")
    assert water is not None, "Expected the task's native FLIP water object"
    water_id = water.objid()
    # New bodies receive volume-derived mass from the native RBD solve after this stage.
    objects = tuple(existing_dop_objects)
    for obj in objects:
        if obj.name() in ("boat_water", "boat_glue_root") or timestep == 0:
            continue
        position = obj.findSubData("Position").options()
        if position.field("computemass"):
            continue
        mass = float(position.field("mass"))
        assert math.isfinite(mass) and mass > 0, obj.name()
        feedback = obj.findSubData("Feedback")
        records = tuple(record for record in feedback.records("Impacts")
                        if record.field("otherobjid") == water_id) if feedback is not None else ()
        impulse_vector = hou.Vector3((0.0, 0.0, 0.0))
        for record in records:
            impulse = record.field("impulse")
            normal = record.field("normal")
            assert isinstance(impulse, (int, float)) and math.isfinite(impulse), "Expected scalar native impulse"
            assert normal is not None and len(normal) == 3 and all(math.isfinite(value) for value in normal)
            impulse_vector += hou.Vector3(normal) * impulse
        force_vector = impulse_vector / timestep
        ratio = force_vector.length() / (mass * GRAVITY)
        assert math.isfinite(ratio), obj.name()
        state = obj.findSubData("BoatFluidStress")
        if state is None:
            state = obj.createSubData("BoatFluidStress", "SIM_EmptyData")
        options = state.options()
        options.setField("method", "native_feedback_vector_impulse")
        options.setField("force_vector", force_vector)
        options.setField("load_ratio_g", ratio)
        options.setField("peak_load_ratio_g", max(float(options.field("peak_load_ratio_g") or 0), ratio))
        options.setField("feedback_record_count", len(records))
        options.setField("fluid_object_id", water_id)
        options.setField("sample_time", solver_time)
        options.setField("timestep", timestep)
        options.setField("threshold_g", FAILURE_LOAD_G)
        options.setField("mass_used", mass)
        options.setField("release_enabled", int(ALLOW_RELEASE))
        if records:
            options.setField("record_fields", " ".join(records[0].fieldNames()))
        if ALLOW_RELEASE and ratio > FAILURE_LOAD_G and position.field("glueobject"):
            position.setField("glueobject", "")
            options.setField("released", 1)
            options.setField("release_time", solver_time)
            options.setField("release_load_ratio_g", ratio)
