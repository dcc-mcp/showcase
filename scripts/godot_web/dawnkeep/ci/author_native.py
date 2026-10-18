#!/usr/bin/env python3
"""Author Node3D through real typed MCP; save, restart, reopen and preserve receipts."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from common import SCRIPT_ORDER, source_inventory, verify_inventory, checked_godot, check_engine_log, isolated_env, isolated_output, sha256, stop_process, write_json


def envelope(response):
    if isinstance(response.get("structuredContent"), dict):
        return response["structuredContent"]
    for item in response.get("content", []):
        if item.get("type") == "text":
            try:
                return json.loads(item["text"])
            except (ValueError, TypeError):
                pass
    return response



DEFERRED_TEST_FILES = ("verify_gameplay.gd",)
EDITOR_PROBE_PATH = "res://dawnkeep_ci_editor_probe.gd"
EDITOR_PROBE_SOURCE = """@tool
extends RefCounted

func inspect(arguments: Dictionary) -> Dictionary:
 var filesystem := EditorInterface.get_resource_filesystem()
 var scanning := filesystem.is_scanning()
 var types: Dictionary = {}
 if not scanning:
  for path: String in arguments.get("paths", []):
   types[path] = filesystem.get_file_type(path)
 return {"schema": 1, "scanning": scanning, "process_frame": Engine.get_process_frames(), "types": types}
"""


def initial_copy_files(names):
    excluded = {*SCRIPT_ORDER, "start.tscn", "project.godot", *DEFERRED_TEST_FILES}
    return tuple(name for name in names if name not in excluded)


def editor_idle_sample(body, expected_types):
    """Validate the actual v0.9.6 execute_editor_script envelope, fail closed."""
    if not isinstance(body, dict):
        raise ValueError("Editor probe response must be an object")
    context = body.get("context", body)
    if not isinstance(context, dict) or context.get("executed") is not True:
        raise ValueError("Official editor probe was not executed")
    sample = context.get("result")
    if not isinstance(sample, dict) or type(sample.get("schema")) is not int or sample["schema"] != 1:
        raise ValueError("Unsupported editor probe result")
    if type(sample.get("scanning")) is not bool or type(sample.get("process_frame")) is not int or sample["process_frame"] <= 0:
        raise ValueError("Editor probe did not establish real scan/frame state")
    types = sample.get("types")
    if not isinstance(types, dict):
        raise ValueError("Editor probe lacks filesystem file-type readback")
    idle = sample["scanning"] is False and all(types.get(path) == kind for path, kind in expected_types.items())
    return sample, idle

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--godot", default="godot")
    parser.add_argument("--headless", action="store_true", help="Typed editor authoring only, never native rendering acceptance")
    args = parser.parse_args()
    source = args.source.resolve()
    out = isolated_output(args.output, source)
    godot = checked_godot(args.godot)
    manifest = source_inventory(source)
    GAME_FILES = tuple(entry["path"] for entry in manifest["files"])
    write_json(out / "source-manifest.json", manifest)
    for package, expected in (("dcc-mcp-godot", "0.9.6"), ("dcc-mcp-core", "0.20.42")):
        if importlib.metadata.version(package) != expected:
            raise RuntimeError(f"{package} must be pinned to {expected}")
    os.environ.update(isolated_env(out / "session"))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    os.environ.update({"DCC_MCP_GODOT_BRIDGE_PORT": str(port),
                       "DCC_MCP_GODOT_BRIDGE_URL": f"ws://127.0.0.1:{port}",
                       "DCC_MCP_REGISTRY_DIR": str(out / "session/registry"),
                       "DCC_MCP_CLI_NO_AUTO_GATEWAY": "true"})
    import dcc_mcp_godot
    from dcc_mcp_godot.bridge import get_bridge
    from dcc_mcp_godot.server import GodotMcpServer
    project = out / "authoring-project"
    project.mkdir()
    shutil.copytree(Path(dcc_mcp_godot.__file__).parent / "godot_addon/addons", project / "addons")
    for name in initial_copy_files(GAME_FILES):
        (project / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, project / name)
    # Read-only diagnostic method, invoked only through the official adapter.
    # It is never copied to the playable package or added as an editor plugin.
    (project / EDITOR_PROBE_PATH.removeprefix("res://")).write_text(EDITOR_PROBE_SOURCE)
    config = (source / "project.godot").read_text()
    config = re.sub(r'^run/main_scene=.*\n', '', config, flags=re.M)
    config += '\n[editor_plugins]\nenabled=PackedStringArray("res://addons/dcc_mcp_godot/plugin.cfg")\n'
    (project / "project.godot").write_text(config)
    server = GodotMcpServer(port=0, gateway_port=0, registry_dir=str(out / "session/registry"),
                            enable_gateway_failover=False, enable_telemetry=False,
                            enable_checkpoint_persistence=False)
    server.register_builtin_actions()
    server.start()
    receipts, schemas = [], {}
    editor = None
    log = (out / "editor.log").open("w")
    report = {"passed": False, "route": "real typed MCP HTTP to actual Godot editor; display or headless explicitly recorded",
              "source_sha256": {name: sha256(source / name) for name in GAME_FILES},
              "headless_editor": args.headless, "adapter": "0.9.6", "core": "0.20.42", "editor_restarted": False,
              "deferred_test_files": list(DEFERRED_TEST_FILES),
              "installed_packages": {name: importlib.metadata.version(name) for name in ("dcc-mcp-godot", "dcc-mcp-core", "dcc-mcp-server", "Pillow", "websockets")},
              "editor_probe_sha256": hashlib.sha256(EDITOR_PROBE_SOURCE.encode()).hexdigest(),
              "editor_probe_source": EDITOR_PROBE_SOURCE}

    def launch():
        return subprocess.Popen([godot, *(["--headless"] if args.headless else []), "--editor", "--audio-driver", "Dummy", "--path", str(project),
                                 "--rendering-method", "gl_compatibility", "--rendering-driver", "opengl3"], stdout=log, stderr=log)

    def ready():
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if editor.poll() is not None:
                raise RuntimeError("Godot editor exited; inspect editor.log")
            if get_bridge().is_connected():
                time.sleep(1)
                return
            time.sleep(.2)
        raise TimeoutError("The DCC-MCP editor plugin did not connect within 90 seconds")

    def rpc(method, params):
        request = {"jsonrpc": "2.0", "id": len(receipts) + 1, "method": method, "params": params}
        req = urllib.request.Request(server.mcp_url, data=json.dumps(request).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json,text/event-stream"})
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read().decode()
        if raw.startswith(("event:", "data:")):
            data = [line[6:] for line in raw.splitlines() if line.startswith("data: ")]
            response = next((json.loads(item) for item in reversed(data) if item.strip()), {})
        else:
            response = json.loads(raw)
        receipts.append({"request": request, "response": response})
        write_json(out / "mcp-raw.json", receipts)
        if "error" in response or response.get("result", {}).get("isError"):
            raise RuntimeError("MCP request failed: " + json.dumps(response))
        return response.get("result", {})

    def inventory():
        cursor = None
        for _ in range(30):
            page = rpc("tools/list", {"cursor": cursor} if cursor else {})
            schemas.update({tool["name"]: tool for tool in page["tools"]})
            cursor = page.get("nextCursor")
            if not cursor:
                write_json(out / "mcp-tool-schemas.json", schemas)
                return
        raise RuntimeError("MCP tool inventory pagination did not terminate")

    def resolve(name):
        if name in schemas:
            return name
        suffix = name.split("__")[-1]
        found = [item for item in schemas if item == suffix or item.endswith("__" + suffix)]
        if len(found) != 1:
            raise RuntimeError(f"Required typed tool unavailable or ambiguous: {name}: {found}")
        return found[0]

    def call(name, arguments):
        body = envelope(rpc("tools/call", {"name": resolve(name), "arguments": arguments}))
        if isinstance(body, dict) and body.get("job_id"):
            job_id = body["job_id"]
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                status = envelope(rpc("tools/call", {"name": resolve("jobs_get_status"),
                    "arguments": {"job_id": job_id, "include_result": True}}))
                if status.get("status") == "completed":
                    body = status.get("result", {})
                    break
                if status.get("status") in ("failed", "cancelled", "interrupted"):
                    raise RuntimeError("MCP job failed: " + json.dumps(status))
                time.sleep(.2)
            else:
                raise TimeoutError("Typed MCP job did not complete within 120 seconds")
        if isinstance(body, dict) and (body.get("success") is False or body.get("valid") is False
                                      or body.get("context", {}).get("valid") is False):
            raise RuntimeError("Typed MCP validation failed: " + json.dumps(body))
        return body

    def wait_editor_idle(boundary, expected_types):
        deadline = time.monotonic() + 90
        previous = None
        expected_types = {EDITOR_PROBE_PATH: "GDScript", **expected_types}
        while time.monotonic() < deadline:
            if editor.poll() is not None:
                raise RuntimeError("Godot editor exited before " + boundary)
            log.flush()
            check_engine_log((out / "editor.log").read_text())
            response = call("godot_editor__execute_editor_script", {
                "path": EDITOR_PROBE_PATH, "method": "inspect", "arguments": {"paths": list(expected_types)},
                "budget_ms": 50, "chunked": False})
            sample, idle = editor_idle_sample(response, expected_types)
            if editor.poll() is not None:
                raise RuntimeError("Godot editor exited during " + boundary)
            log.flush()
            check_engine_log((out / "editor.log").read_text())
            if idle:
                if previous is not None and sample["process_frame"] >= previous["process_frame"] + 2:
                    report.setdefault("editor_idle_boundaries", []).append({"boundary": boundary,
                        "expected_types": expected_types, "samples": [previous, sample]})
                    return
                if previous is None:
                    previous = sample
            else:
                previous = None
            time.sleep(.1)
        raise TimeoutError("Editor did not establish scan-idle file readback at " + boundary)

    try:
        editor = launch()
        ready()
        inventory()
        call("load_skill", {"skill_names": ["godot-project-management", "godot-scene-management", "godot-script", "godot-editor"]})
        inventory()
        wait_editor_idle("initial dependency-free project", {})
        call("godot_project_management__get_project_info", {})
        scripts = {}
        for name in SCRIPT_ORDER:
            path = "res://" + name
            call("godot_script__create_script", {"path": path, "source": (source / name).read_text(), "overwrite": True})
            scripts[path] = "GDScript"
            wait_editor_idle("after script creation: " + name, scripts)
            call("godot_script__validate_script", {"path": path})
        wait_editor_idle("before scene creation", scripts)
        call("godot_scene_management__create_scene", {"path": "res://start.tscn", "root_type": "Node3D", "root_name": "Dawnkeep", "open": True})
        wait_editor_idle("after scene creation before attachment", {**scripts, "res://start.tscn": "PackedScene"})
        call("godot_script__attach_script", {"node_path": ".", "script_path": "res://main.gd"})
        call("godot_scene_management__save_scene", {"path": "res://start.tscn"})
        call("godot_project_management__set_project_setting", {"key": "application/run/main_scene", "value": "res://start.tscn"})
        wait_editor_idle("before saved-scene editor shutdown", {**scripts, "res://start.tscn": "PackedScene"})
        before = sha256(project / "start.tscn")
        stop_process(editor)
        deadline = time.monotonic() + 15
        while get_bridge().is_connected() and time.monotonic() < deadline:
            time.sleep(.1)
        if get_bridge().is_connected():
            raise RuntimeError("Old editor bridge did not disconnect; restart is not established")
        editor = launch()
        ready()
        wait_editor_idle("fresh editor before scene reopen", {**scripts, "res://start.tscn": "PackedScene"})
        call("godot_scene_management__open_scene", {"path": "res://start.tscn"})
        wait_editor_idle("after saved-scene reopen", {**scripts, "res://start.tscn": "PackedScene"})
        tree = call("godot_scene_management__get_scene_tree", {"path": "res://start.tscn"})
        if "Node3D" not in json.dumps(tree) or "Dawnkeep" not in json.dumps(tree):
            raise RuntimeError("Reopened MCP scene tree did not identify the original Node3D scene")
        if sha256(project / "start.tscn") != before:
            raise RuntimeError("Saved scene changed across editor restart")
        report["editor_restarted"] = True
        stop_process(editor)
        native = out / "native"
        native.mkdir()
        for name in GAME_FILES:
            if name == "project.godot":
                continue
            (native / name).parent.mkdir(parents=True, exist_ok=True)
            origin = source if name in DEFERRED_TEST_FILES else project
            shutil.copyfile(origin / name, native / name)
        # Preserve the original playable project settings, without shipping an editor addon.
        shutil.copyfile(source / "project.godot", native / "project.godot")
        for name in GAME_FILES:
            if name == "start.tscn":
                continue
            if sha256(native / name) != sha256(source / name):
                raise RuntimeError(f"Native source mismatch: {name}")
        log.flush()
        check_engine_log((out / "editor.log").read_text())
        verify_inventory(source, manifest)
        write_json(out / "native-manifest.json", source_inventory(native))
        report.update({"passed": True, "scene_created_saved_reopened": True,
                       "native_sha256": {name: sha256(native / name) for name in GAME_FILES},
                       "godot": subprocess.check_output([godot, "--version"], text=True).strip()})
    except Exception as error:
        report["blocker"] = str(error)
        raise
    finally:
        stop_process(editor)
        server.stop()
        log.close()
        report["typed_calls"] = [{"name": item["request"]["params"]["name"],
            "arguments": {key: {"sha256": hashlib.sha256(value.encode()).hexdigest()} if key == "source" else value
                for key, value in item["request"]["params"]["arguments"].items()}}
            for item in receipts if item["request"]["method"] == "tools/call"]
        write_json(out / "authoring.json", report)


if __name__ == "__main__":
    main()
