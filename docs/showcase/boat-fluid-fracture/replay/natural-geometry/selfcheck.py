"""Analytic mass/inertia and source/recipe checks, independent of the host."""

import sys
sys.dont_write_bytecode = True

import ast
import io
import json
from pathlib import Path
import runpy
import zipfile
from types import SimpleNamespace


BASE = Path(__file__).resolve().parent
for path in BASE.glob("*.py"):
    ast.parse(path.read_text(), filename=path.name)
mass_properties = runpy.run_path(str(BASE / "mass_properties.py"))["mass_properties"]


class Geometry:
    def __init__(self, positions, faces):
        self.positions, self.faces = positions, faces

    def pointFloatAttribValues(self, name):
        assert name == "P"
        return [value for position in self.positions for value in position]

    def primStringAttribValues(self, name):
        assert name == "name"
        return ["solid"] * len(self.faces)

    def prims(self):
        return [SimpleNamespace(vertices=lambda face=face: [SimpleNamespace(
            point=lambda index=index: SimpleNamespace(number=lambda: index)) for index in face]) for face in self.faces]


tetra_faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
for shift in ((0, 0, 0), (2, -3, -4)):
    points = [tuple(a + b for a, b in zip(point, shift)) for point in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))]
    p = mass_properties(Geometry(points, tetra_faces), density=1)["solid"]
    assert p["volume_valid"] and abs(p["wood_volume_m3"] - 1 / 6) < 1e-12
    assert all(abs(a - b - 0.25) < 1e-12 for a, b in zip(p["center_of_mass_m"], shift))
    assert all(abs(p["full_inertia_tensor_com_kg_m2"][i][i] - 1 / 80) < 1e-11 for i in range(3))
    assert abs(p["full_inertia_tensor_com_kg_m2"][0][1] - 1 / 480) < 1e-11
cube_points = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
cube_faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
for sign in (1, -1):
    faces = cube_faces if sign == 1 else [tuple(reversed(face)) for face in cube_faces]
    p = mass_properties(Geometry(cube_points, faces), density=1, orientation_sign=sign)["solid"]
    assert p["volume_valid"] and abs(p["wood_volume_m3"] - 8) < 1e-12
    assert all(abs(p["full_inertia_tensor_com_kg_m2"][i][i] - 16 / 3) < 1e-12 for i in range(3))
mixed = list(cube_faces)
mixed[0] = tuple(reversed(mixed[0]))
assert not mass_properties(Geometry(cube_points, mixed))["solid"]["volume_valid"]
zero = Geometry([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2), (2, 1, 0)])
assert not mass_properties(zero)["solid"]["volume_valid"]
recipe = json.loads((BASE / "02-wood-fracture.json").read_text())
parameters = recipe["nodes"][0]["parameters"]
assert parameters["materialtype"] == "wood" and parameters["wood_randomdetach"] == 0
assert parameters["wood_clustertype"] == "groupconstraints" and parameters["wood_applyconstraints"] == 0
assert parameters["wood_graindirvector"] == [1, 0, 0] and parameters["wood_cutdirvector"] == [0, 0, 1]
assert sorted(connection.get("output_index", 0) for connection in recipe["connections"] if connection["output"] == "native_wood_fracture") == [0, 1, 2]
safe_members = runpy.run_path(str(BASE / "prepare.py"))["safe_members"]
for member, accepted in (("boat.obj", True), ("../boat.obj", False), ("/boat.obj", False), ("C" + ":" + "/boat.obj", False), ("..\\boat.obj", False)):
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("boat.obj", "safe source") if member != "boat.obj" else None
        archive.writestr(member, "fixture")
    archive_bytes.seek(0)
    with zipfile.ZipFile(archive_bytes) as archive:
        try:
            safe_members(archive)
            assert accepted
        except ValueError:
            assert not accepted
print("PASS: analytic tetra/cube mass+COM+inertia, global winding, mixed-winding/zero-solid rejection, native3output WOOD contract; no host")
