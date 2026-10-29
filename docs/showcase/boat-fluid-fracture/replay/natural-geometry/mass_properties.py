"""Audit cached full-piece mass properties and native adjacency; no fracture recook."""

from collections import Counter
import json
import math
from pathlib import Path
import time




def mass_properties(geometry, density=400, orientation_sign=1):
    coordinates = geometry.pointFloatAttribValues("P")
    assert all(math.isfinite(value) for value in coordinates)
    def point(index):
        return coordinates[index * 3:index * 3 + 3]
    pieces = {}
    names = geometry.primStringAttribValues("name")
    for primitive, name in zip(geometry.prims(), names):
        record = pieces.setdefault(name, {"points": set(), "edges": {}, "triangles": 0,
            "volume": 0.0, "first": [0.0] * 3, "second": [[0.0] * 3 for _ in range(3)], "area": 0.0})
        indices = [vertex.point().number() for vertex in primitive.vertices()]
        record["points"].update(indices)
        for i in range(len(indices)):
            a, b = indices[i], indices[(i + 1) % len(indices)]
            key = (min(a, b), max(a, b))
            edge = record["edges"].setdefault(key, [0, 0])
            edge[0] += 1
            edge[1] += 1 if a < b else -1
        for i in range(1, len(indices) - 1):
            a, b, c = (point(index) for index in (indices[0], indices[i], indices[i + 1]))
            volume = (a[0] * (b[1] * c[2] - b[2] * c[1]) + a[1] * (b[2] * c[0] - b[0] * c[2]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
            volume *= orientation_sign
            record["triangles"] += 1
            record["volume"] += volume
            for axis in range(3):
                record["first"][axis] += volume * (a[axis] + b[axis] + c[axis]) / 4
                for other in range(3):
                    record["second"][axis][other] += volume / 20 * (
                        (a[axis] + b[axis] + c[axis]) * (a[other] + b[other] + c[other])
                        + a[axis] * a[other] + b[axis] * b[other] + c[axis] * c[other])
            ab, ac = [b[j] - a[j] for j in range(3)], [c[j] - a[j] for j in range(3)]
            cross = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
            record["area"] += math.sqrt(sum(value * value for value in cross)) / 2
    result = {}
    for name, record in pieces.items():
        low = [min(point(index)[axis] for index in record["points"]) for axis in range(3)]
        high = [max(point(index)[axis] for index in record["points"]) for axis in range(3)]
        boundary = sum(count == 1 for count, _ in record["edges"].values())
        nonmanifold = sum(count > 2 for count, _ in record["edges"].values())
        orientation = sum(count == 2 and balance != 0 for count, balance in record["edges"].values())
        volume = record["volume"]
        center = [value / volume for value in record["first"]] if volume else None
        mass = density * volume
        tensor = None
        if center:
            second = record["second"]
            trace = sum(second[i][i] for i in range(3))
            distance2 = sum(value * value for value in center)
            tensor = [[density * ((trace if i == j else 0) - second[i][j])
                       - mass * ((distance2 if i == j else 0) - center[i] * center[j]) for j in range(3)] for i in range(3)]
        valid = volume > 1e-10 and not (boundary or nonmanifold or orientation)
        result[name] = {"triangles": record["triangles"], "points": len(record["points"]),
            "wood_volume_m3": volume, "density_kg_m3": density, "mass_kg": mass,
            "raw_signed_volume_m3": volume / orientation_sign,
            "center_of_mass_m": center, "full_inertia_tensor_com_kg_m2": tensor,
            "inertia_scope": "closed-full-geometry signed tetrahedron reference; not a native Bullet tensor override",
            "volume_valid": valid, "closed_oriented_topology": not (boundary or nonmanifold or orientation),
            "boundary_edges": boundary, "nonmanifold_edges": nonmanifold, "orientation_conflicts": orientation,
            "bbox_min_m": low, "bbox_max_m": high, "bbox_size_m": [b - a for a, b in zip(low, high)],
            "bbox_min_extent_m": min(b - a for a, b in zip(low, high)),
            "surface_area_m2": record["area"],
            "mean_slab_thickness_proxy_m": 2 * volume / record["area"] if record["area"] else None,
            "minimum_physical_thickness_verified": False, "self_intersections_verified": False}
    return result


def outside_attribute_samples(geometry, source, maximum=256):
    outside = [i for i, flag in enumerate(geometry.primIntAttribValues("is_cutface")) if not flag]
    stride = max(1, math.ceil(len(outside) / maximum))
    uv_error, position_error, min_cosine, count = 0.0, 0.0, 1.0, 0
    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))
    for number in outside[::stride]:
        primitive = geometry.prim(number)
        original = source.prim(primitive.intAttribValue("sourceprim"))
        vertices = original.vertices()
        assert len(vertices) == 3
        a, b, c = (tuple(vertex.point().position()) for vertex in vertices)
        ab, ac = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        denominator = dot(ab, ab) * dot(ac, ac) - dot(ab, ac) ** 2
        if denominator < 1e-20:
            continue
        for vertex in primitive.vertices():
            point = tuple(vertex.point().position())
            ap = [point[i] - a[i] for i in range(3)]
            u = (dot(ac, ac) * dot(ap, ab) - dot(ab, ac) * dot(ap, ac)) / denominator
            v = (dot(ab, ab) * dot(ap, ac) - dot(ab, ac) * dot(ap, ab)) / denominator
            weights = (1 - u - v, u, v)
            projected = [sum(weight * p[i] for weight, p in zip(weights, (a, b, c))) for i in range(3)]
            position_error = max(position_error, max(abs(x - y) for x, y in zip(point, projected)))
            for attribute in ("uv", "N"):
                expected = [sum(weight * source_vertex.attribValue(attribute)[i] for weight, source_vertex in zip(weights, vertices)) for i in range(3)]
                actual = vertex.attribValue(attribute)
                if attribute == "uv":
                    uv_error = max(uv_error, max(abs(x - y) for x, y in zip(expected, actual)))
                else:
                    denominator_n = math.sqrt(dot(expected, expected) * dot(actual, actual))
                    min_cosine = min(min_cosine, dot(expected, actual) / denominator_n if denominator_n else 0)
            count += 1
    return {"sampled_outside_vertices": count, "max_uv_component_error": uv_error,
            "max_source_triangle_projection_error_m": position_error, "min_normal_cosine": min_cosine,
            "uv_tolerance": 1e-4, "normal_cosine_minimum": 0.999,
            "sampled_uv_normal_preservation_pass": uv_error < 1e-4 and min_cosine > 0.999 and position_error < 1e-4,
            "inside_uv_scope": "new cut faces labeled for separate procedural cutwood shader; original texture UV meaning is not claimed for inside"}


