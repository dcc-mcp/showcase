"""Bounded offline checks for payload dependencies and asset parsing; no host calls."""

import sys

sys.dont_write_bytecode = True

import ast
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_unordered_inputs(payload):
    connections = payload.get("connections", [])
    for node in payload["nodes"]:
        if node["node_type"] not in ("merge", "multisolver"):
            continue
        positions = [i for i, connection in enumerate(connections) if connection["input"] == node["node_name"]]
        indices = [connections[i].get("input_index", 0) for i in positions]
        assert indices == list(range(len(indices))), "Connect unordered inputs from slot 0 upwards"
        assert not positions or positions == list(range(positions[0], positions[0] + len(positions))), "Keep unordered inputs contiguous"


def check():
    known = {"/obj", "/mat", "/out"}
    edges = {}
    count = 0
    for path in sorted((ROOT / "recipes").glob("[0-9][0-9]-*.json")):
        payload = load(path)
        check_unordered_inputs(payload)
        parent = payload["parent_path"]
        assert parent in known, (path.name, parent)
        names = [node["node_name"] for node in payload["nodes"]]
        assert len(names) == len(set(names)), path.name
        for node in payload["nodes"]:
            absolute = parent + "/" + node["node_name"]
            assert absolute not in known, absolute
            known.add(absolute)
            if node["node_type"] == "dopnet":
                known.add(absolute + "/file_output")  # Native dopnet creation script.
            count += 1
        for node in payload["nodes"]:
            for key, value in node.get("parameters", {}).items():
                if key in ("soppath", "doppath", "objpath1", "camera", "lookatpath") or key.startswith("shop_materialpath"):
                    assert value in known, (path.name, node["node_name"], key, value)
        for connection in payload.get("connections", []):
            target, source = (parent + "/" + connection[key] for key in ("input", "output"))
            assert target in known and source in known, (path.name, connection)
            edges[target, connection.get("input_index", 0)] = source
    upstream = {}
    for (target, _), source in edges.items():
        upstream.setdefault(target, []).append(source)

    def walk(node, stack):
        assert node not in stack, "Node cycle: " + node
        for source in upstream.get(node, []):
            walk(source, stack + (node,))

    for node in upstream:
        walk(node, ())
    dop = load(ROOT / "recipes/03-coupled-physics.json")
    nodes = {node["node_name"]: node for node in dop["nodes"]}
    assert nodes["boat_pieces"]["parameters"]["soppath"].endswith("/SIM_PARTS_4K")
    assert nodes["boat_water"]["parameters"]["gridscale"] == 1.25
    assert nodes["water_solver"]["parameters"]["partpervoxel"] == 4
    assert edges["/obj/boat_fluid_dop/ship_with_material_failure", 1].endswith("/fluid_load_failure")
    assert edges["/obj/boat_fluid_dop/ship_with_material_failure", 2].endswith("/ship_rbd_stress")
    module = (ROOT / "scripts/hydrodynamic_glue.py").read_text(encoding="utf-8")
    assert module.index('position.field("computemass")') < module.index('obj.findSubData("Feedback")')
    assert module.count('position.setField(') == 1 and 'position.setField("glueobject", "")' in module
    for path in ROOT.rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".py", ".md"):
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"[A-Za-z]:[/\\]", text), "Machine-specific drive path: " + path.name
            assert not re.search(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", text), path.name
    assets = load(ROOT / "assets.json")
    archive = (ROOT / assets["archive"]).resolve()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == assets["archive_sha256"]
    with zipfile.ZipFile(archive) as source:
        assert set(source.namelist()) == set(assets["members"])
        obj = source.read("boat.obj").decode("utf-8")
        objects = [line[2:] for line in obj.splitlines() if line.startswith("o ")]
        assert len(objects) == len(set(objects)) == 17
        assert sum(line.startswith("f ") for line in obj.splitlines()) == 150000
        assert "map_Kd textures/texture_diffuse.png" in source.read("boat.mtl").decode("utf-8")
    # Exercise real token expansion/extraction and prove default preparation cannot contact a host.
    prepare = runpy.run_path(str(ROOT / "prepare.py"))["prepare"]
    with tempfile.TemporaryDirectory(prefix="boat-replay-check-") as temporary:
        directory = Path(temporary)
        config = directory / "config.json"
        config.write_text(json.dumps({"asset_dir": "assets", "output_root": "output",
            "run_name": "short-check", "end_frame": 2, "release_enabled": True}), encoding="utf-8")
        prepared = prepare(config, archive)
        assert prepared["host_calls_performed"] == 0
        assert prepared["simulation_frames_if_explicitly_called"] == 2
        plan = load(directory / "output/call-plan.json")
        assert [step["phase"] for step in plan].count("simulate") == 1
        for path in (directory / "output/calls").glob("*.json"):
            assert not re.search(r"@[A-Z_]+@", path.read_text(encoding="utf-8"))
        try:
            prepare(config, archive)
        except AssertionError:
            pass
        else:
            raise AssertionError("Preparing over previous outputs must fail")
    subprocess.run([sys.executable, str(ROOT / "scripts/test_hydrodynamic_glue.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/check_flotation.py")], check=True)
    return {"recipe_nodes": count, "dependency_order_and_cycles_checked": True,
            "archive_object_count": 17, "archive_triangles": 150000,
            "default_end_frame": 2, "host_calls_performed": 0,
            "native_blank_scene_rebuild": "not_run_by_this_check"}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
