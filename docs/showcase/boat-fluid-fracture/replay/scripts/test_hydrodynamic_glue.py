"""Offline contract checks; these do not validate Houdini physics."""

import math
import inspect
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class Vector(tuple):
    def __new__(cls, values):
        return tuple.__new__(cls, values)

    def __add__(self, other):
        return Vector(a + b for a, b in zip(self, other))

    def __mul__(self, scale):
        return Vector(value * scale for value in self)

    def __truediv__(self, scale):
        return self * (1 / scale)

    def length(self):
        return math.sqrt(sum(value * value for value in self))


class Record(dict):
    def field(self, key):
        return self.get(key)

    def setField(self, key, value):
        self[key] = value

    def fieldNames(self):
        return tuple(self)


class Data:
    def __init__(self, values=None, records=()):
        self.values = Record(values or {})
        self.impact_records = records

    def options(self):
        return self.values

    def records(self, kind):
        assert kind == "Impacts"
        return self.impact_records


class Body:
    def __init__(self, records):
        self.data = {"Position": Data({"mass": 10.0, "glueobject": "boat_glue_root"}),
                     "Feedback": Data(records=records)}

    def name(self):
        return "piece_0"

    def findSubData(self, name):
        return self.data.get(name)

    def createSubData(self, name, kind):
        assert kind == "SIM_EmptyData"
        self.data[name] = Data()
        return self.data[name]


def run(records, release, new_only=False, pending_mass=False):
    body = Body(records)
    if pending_mass:
        body.data["Position"].values["computemass"] = True
    simulation = SimpleNamespace(findObject=lambda name: SimpleNamespace(objid=lambda: 19))
    dop = SimpleNamespace(isScriptSolverRunning=lambda: True,
                          scriptSolverSimulation=lambda: simulation)
    source = Path(__file__).with_name("hydrodynamic_glue.py").read_text()
    source = source.replace("ALLOW_RELEASE = True", "ALLOW_RELEASE = " + str(release))
    namespace = {}
    with patch.dict(sys.modules, {"hou": SimpleNamespace(dop=dop, Vector3=Vector)}):
        exec(compile(source, "hydrodynamic_glue.py", "exec"), namespace)
    namespace["solveForObjects"](Data(), (body,) if new_only else (), () if new_only else (body,), 0.5, 0.02)
    state = body.data.get("BoatFluidStress")
    return body.data["Position"].values, state.values if state is not None else None


def impact(g_ratio, object_id=19):
    return Record(impulse=1.0, normal=Vector((0, g_ratio * 10 * 9.80665 * 0.02, 0)), otherobjid=object_id)


class HydrodynamicGlueTest(unittest.TestCase):
    def test_module_import_does_not_touch_hom_and_callback_matches_native(self):
        class UnavailableHou:
            def __getattr__(self, name):
                raise AssertionError("HOM accessed during module import: " + name)

        namespace = {}
        source = Path(__file__).with_name("hydrodynamic_glue.py").read_text()
        with patch.dict(sys.modules, {"hou": UnavailableHou()}):
            exec(compile(source, "hydrodynamic_glue.py", "exec"), namespace)
        self.assertEqual(list(inspect.signature(namespace["solveForObjects"]).parameters),
                         ["solver_data", "new_dop_objects", "existing_dop_objects", "time", "timestep"])

    def test_diagnostic_never_releases(self):
        position, state = run((impact(2),), False)
        self.assertEqual(position["glueobject"], "boat_glue_root")
        self.assertAlmostEqual(state["load_ratio_g"], 2)

    def test_net_fluid_overload_releases_without_changing_motion(self):
        position, state = run((impact(2),), True)
        self.assertEqual(position, {"mass": 10.0, "glueobject": ""})
        self.assertEqual(state["released"], 1)
        self.assertEqual(state["mass_used"], 10)

    def test_new_objects_wait_for_native_mass_initialization(self):
        position, state = run((impact(10000),), True, new_only=True)
        self.assertEqual(position["glueobject"], "boat_glue_root")
        self.assertIsNone(state)

    def test_existing_objects_with_pending_native_mass_are_skipped(self):
        position, state = run((impact(10000),), True, pending_mass=True)
        self.assertEqual(position["glueobject"], "boat_glue_root")
        self.assertIsNone(state)

    def test_opposing_impulses_cancel(self):
        position, state = run((impact(100), impact(-100)), True)
        self.assertEqual(position["glueobject"], "boat_glue_root")
        self.assertEqual(state["load_ratio_g"], 0)

    def test_other_actor_excluded_and_quiet_support_survives(self):
        position, state = run((impact(100, 42), impact(1)), True)
        self.assertEqual(position["glueobject"], "boat_glue_root")
        self.assertAlmostEqual(state["load_ratio_g"], 1)
        self.assertEqual(state["feedback_record_count"], 1)

    def test_no_feedback_never_releases(self):
        position, state = run((), True)
        self.assertEqual(position["glueobject"], "boat_glue_root")
        self.assertEqual(state["load_ratio_g"], 0)


if __name__ == "__main__":
    unittest.main()
