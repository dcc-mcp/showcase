"""Resolve local paths and emit CLI inputs; never contacts or clears a DCC host."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_assets(directory):
    for name, expected in load(ROOT / "assets.json")["members"].items():
        path = directory / name
        assert path.is_file(), "Missing extracted asset: " + name
        assert path.stat().st_size == expected["bytes"], name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"], name


def extract_assets(archive, directory):
    expected = load(ROOT / "assets.json")
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected["archive_sha256"]
    assert not directory.exists(), "Extraction requires a fresh asset directory"
    with zipfile.ZipFile(archive) as source:
        assert len(source.namelist()) == len(set(source.namelist()))
        assert set(source.namelist()) == set(expected["members"])
        for name in source.namelist():
            relative = PurePosixPath(name)
            assert not relative.is_absolute() and ".." not in relative.parts and "\\" not in name
            assert directory in (directory / name).resolve().parents
        directory.mkdir(parents=True)
        source.extractall(directory)
    verify_assets(directory)


def expand(value, replacements):
    if isinstance(value, dict):
        return {key: expand(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [expand(item, replacements) for item in value]
    if isinstance(value, str):
        for token, replacement in replacements.items():
            value = value.replace(token, replacement)
        assert not re.search(r"@[A-Z_]+@", value), "Unresolved recipe token"
    return value


def prepare(config_path, archive=None):
    config_path = config_path.resolve()
    config = load(config_path)
    asset_dir = (config_path.parent / config["asset_dir"]).resolve()
    output_root = (config_path.parent / config["output_root"]).resolve()
    run_name = config["run_name"]
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", run_name), "Use a simple fresh run name"
    frames = config["end_frame"]
    assert isinstance(frames, int) and not isinstance(frames, bool) and 1 <= frames <= 96
    assert isinstance(config["release_enabled"], bool)
    assert not output_root.exists(), "Choose a fresh output_root; previous trials are preserved"
    if archive is not None:
        extract_assets(archive.resolve(), asset_dir)
    verify_assets(asset_dir)
    module = (ROOT / "scripts/hydrodynamic_glue.py").read_text(encoding="utf-8")
    assert module.count("ALLOW_RELEASE = True") == 1
    module = module.replace("ALLOW_RELEASE = True", "ALLOW_RELEASE = " + str(config["release_enabled"]))
    run_dir = output_root / run_name
    replacements = {"@ASSET_DIR@": asset_dir.as_posix(), "@RUN_DIR@": run_dir.as_posix(),
                    "@HYDRODYNAMIC_GLUE@": module}
    calls = output_root / "calls"
    calls.mkdir(parents=True)
    plan = []

    def emit(name, tool, arguments, phase="build"):
        (calls / name).write_text(json.dumps(arguments, indent=2) + "\n", encoding="utf-8")
        plan.append({"file": name, "tool": tool, "phase": phase})

    def script(name, filename, context, phase="build"):
        emit(name, "houdini_automation__run_python_file",
             {"file_path": (ROOT / "scripts" / filename).as_posix(), "context": context,
              "output_mode": "structured", "max_result_chars": 12000}, phase)

    script("00-blank-scene-check.json", "finish_scene.py", {"stage": "blank"})
    for source in sorted((ROOT / "recipes").glob("[0-9][0-9]-*.json")):
        arguments = expand(load(source), replacements)
        emit(source.name, "houdini_automation__build_node_chain", arguments)
        dry_run = dict(arguments, dry_run=True)
        (calls / (source.stem + ".dry-run.json")).write_text(
            json.dumps(dry_run, indent=2) + "\n", encoding="utf-8")
    script("10-finish-scene.json", "finish_scene.py", {"stage": "finish"})
    script("11-validate-rest.json", "validate_sim_proxy.py", {"check_hires": True})
    script("12-cache-short-or-explicit-run.json", "cache_and_measure.py",
           {"output_dir": run_dir.as_posix(), "output_root": output_root.as_posix(),
            "end_frame": frames, "pieces_sop_path": "/obj/boat_fluid_output/solved_hires_pieces"}, "simulate")
    script("13-check-flotation.json", "check_flotation.py",
           {"output_dir": run_dir.as_posix(),
            "water_surface_path": "/obj/boat_fluid_output/cached_water_surface",
            "water_cache_path": "/obj/boat_fluid_output/cached_water_particles",
            "piece_cache_path": "/obj/boat_fluid_output/cached_pieces", "window_frames": 12}, "analyze")
    emit("14-render-cached-frame.json", "houdini_render__render_rop",
         {"rop_path": "/out/boat_fluid_beauty", "frame_range": [1, 1], "background": True}, "render")
    for filename in ("control-feedback-off.json", "control-feedback-on.json"):
        (calls / filename).write_text(json.dumps(load(ROOT / "recipes" / filename), indent=2) + "\n",
                                      encoding="utf-8")
    (output_root / "call-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    (output_root / "resolved-config.json").write_text(json.dumps(dict(config, asset_dir=asset_dir.as_posix(),
        output_root=output_root.as_posix(), run_dir=run_dir.as_posix()), indent=2) + "\n", encoding="utf-8")
    return {"calls": str(calls), "build_steps": sum(step["phase"] == "build" for step in plan),
            "simulation_frames_if_explicitly_called": frames, "host_calls_performed": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--extract", type=Path, help="Verify and extract source-model.zip into a fresh asset_dir")
    options = parser.parse_args()
    print(json.dumps(prepare(options.config, options.extract), indent=2))
