#!/usr/bin/env python3
"""Windows-only portable owner for the original-engine first-chapter probes.

Explicit executable/project/preparation inputs; no install, browser, shared user
data, timeout or kill. The immutable PCK receipt records the real Popen argv.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--phase", choices=("native", "pck"), required=True)
    args = parser.parse_args()
    if os.name != "nt": raise ValueError("This measured-priority launcher is Windows-only")
    recipe_path = Path(__file__).with_name("prepare_firstchapter_export.py")
    spec = importlib.util.spec_from_file_location("firstchapter_export_recipe", recipe_path)
    recipe = importlib.util.module_from_spec(spec); spec.loader.exec_module(recipe)
    need, sha, dump = recipe.need, recipe.sha, recipe.dump
    editor, project, prepared = (p.resolve() for p in (args.godot, args.project, args.prepared))
    need(editor.is_file() and project.is_dir() and prepared.is_dir(), "Explicit existing engine, project and preparation required")
    manifest_path = prepared / "preparation-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inputs = json.loads((prepared / "private/inputs.json").read_text(encoding="utf-8"))
    need(Path(inputs["original_project"]).resolve() == project, "Explicit project differs from prepared source")
    probe = Path(__file__).with_name("probe_firstchapter_pck.gd").resolve()
    rows = {r["path"]: r for r in manifest["source_archive_files"]}
    for path, name in ((probe, "probe_firstchapter_pck.gd"), (recipe_path, "prepare_firstchapter_export.py"), (Path(__file__), "agent_launch_firstchapter_probe.py")):
        need(sha(path) == rows["recipe/" + name]["sha256"], "Prepared reproduction source changed: " + name)
    def unchanged():
        for row in manifest["sources_before"]: need(sha(project / row["path"]) == row["sha256"], "Original source changed")
        for row in inputs["protected"]: need(sha(Path(row["path"])) == row["sha256"], "Protected file changed")
        return True
    unchanged()
    phase = args.phase
    report = prepared / (phase + "-identity-probe.json")
    owner_path = prepared / ("private/" + phase + "-probe.owner.json")
    stdout_path = prepared / ("private/" + phase + "-probe.stdout.log")
    stderr_path = prepared / ("private/" + phase + "-probe.stderr.log")
    launch_path = prepared / "private/pck-launch.json"
    need(not any(p.exists() for p in (report, owner_path, stdout_path, stderr_path)), "Previous phase evidence is never overwritten")
    cwd = prepared / ("private/" + phase + "-probe-cwd")
    cwd.mkdir(exist_ok=True); need(not any(cwd.iterdir()), "Probe cwd must be owned and empty")
    env = os.environ.copy()
    for key in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        directory = prepared / ("private/" + phase + "-probe-user") / key
        directory.mkdir(parents=True, exist_ok=True); env[key] = str(directory)
    command = [str(editor), "--headless"]
    if phase == "native": command += ["--path", str(project)]
    else:
        need((prepared / "web/index.pck").is_file(), "Exported PCK is required")
        reference = json.loads((prepared / "native-identity-probe.json").read_text(encoding="utf-8"))
        need(reference.get("passed") is True and not launch_path.exists(), "Passed native reference and new launch receipt required")
        command += ["--main-pack", str(prepared / "web/index.pck")]
    command += ["--script", probe.as_posix(), "--", "--phase=" + phase, "--manifest=" + manifest_path.as_posix(), "--report=" + report.as_posix()]
    if phase == "pck":
        pack = prepared / "web/index.pck"
        command += ["--native-reference=" + (prepared / "native-identity-probe.json").as_posix(), "--pack=" + pack.as_posix(), "--launch-receipt=" + launch_path.as_posix()]
        launch = {"schema_version": 1, "phase": "pck", "argv": command, "cwd": str(cwd), "cwd_empty_before": not any(cwd.iterdir()),
            "source_project_path_supplied": "--path" in command, "pack_path": str(pack), "pack_sha256": sha(pack), "probe_sha256": sha(probe),
            "manifest_sha256": sha(manifest_path), "wrapper_sha256": sha(Path(__file__))}
        dump(launch_path, launch)
    flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
    owner = {"phase": phase, "started_utc": datetime.now(timezone.utc).isoformat(), "complete": False, "creation_flags": flags,
        "automatic_timeout_or_kill": False, "source_project_fallback": phase == "native", "browser_or_gui_claimed": False,
        "script_sha256": sha(probe), "wrapper_sha256": sha(Path(__file__)), "recipe_sha256": sha(recipe_path),
        "manifest_sha256": sha(manifest_path), "engine_sha256": sha(editor)}
    if phase == "pck": owner["immutable_launch_sha256"] = sha(launch_path)
    dump(owner_path, owner); started = time.monotonic()
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL, creationflags=flags)
        owner["owned_pid"] = process.pid; owner["initial_resources"] = recipe.windows_resources(process); dump(owner_path, owner)
        while process.poll() is None:
            owner["resources"] = recipe.windows_resources(process); owner["elapsed_seconds"] = round(time.monotonic() - started, 3); dump(owner_path, owner); time.sleep(5)
        code = process.wait(); owner["final_resources"] = recipe.windows_resources(process)
    owner.update({"complete": True, "ended_utc": datetime.now(timezone.utc).isoformat(), "exit_code": code,
        "elapsed_seconds": round(time.monotonic() - started, 3), "stderr_bytes": stderr_path.stat().st_size,
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
        "below_normal_verified": owner["initial_resources"].get("actual_below_normal") is True,
        "process_times_verified": owner["initial_resources"].get("process_times_available") is True,
        "wrapper_unchanged": sha(Path(__file__)) == owner["wrapper_sha256"], "script_unchanged": sha(probe) == owner["script_sha256"],
        "recipe_unchanged": sha(recipe_path) == owner["recipe_sha256"], "manifest_unchanged": sha(manifest_path) == owner["manifest_sha256"],
        "engine_unchanged": sha(editor) == owner["engine_sha256"], "empty_cwd_still_without_project": not (cwd / "project.godot").exists()})
    try: owner["sources_unchanged"] = unchanged()
    except Exception as error: owner["sources_unchanged"] = False; owner["postcheck_error"] = str(error)
    if phase == "pck": owner["immutable_launch_unchanged"] = sha(launch_path) == owner["immutable_launch_sha256"]
    measured = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    owner["report_sha256"] = sha(report) if report.is_file() else None
    owner["accepted"] = bool(code == 0 and owner["stderr_bytes"] == 0 and owner["below_normal_verified"] and owner["process_times_verified"]
        and owner["sources_unchanged"] and owner["wrapper_unchanged"] and owner["script_unchanged"] and owner["recipe_unchanged"]
        and owner["manifest_unchanged"] and owner["engine_unchanged"] and owner["empty_cwd_still_without_project"] and owner.get("immutable_launch_unchanged", True) and measured.get("passed") is True)
    dump(owner_path, owner)
    print(json.dumps({k: owner[k] for k in ("phase", "accepted", "exit_code", "stderr_bytes", "elapsed_seconds", "below_normal_verified", "sources_unchanged", "report_sha256")}))
    raise SystemExit(0 if owner["accepted"] else 1)


if __name__ == "__main__": main()
