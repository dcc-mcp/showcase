"""Utilities for isolated, artifact-only Tidal Sanctuary CI."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

GODOT_VERSION = "4.6.3.stable.official.7d41c59c4"
GODOT_BINARY_SHA256 = "f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3"
WEB_TEMPLATE_SHA256 = "1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9"
GAME_FILES = ("main.gd", "water.gdshader", "start.tscn", "project.godot",
              "sanctuary-font.otf", "FONT-LICENSE.txt")

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

def isolated_output(path: Path, source: Path | None = None) -> Path:
    """Never write generated output into the checked-out recipe or source project."""
    path = path.resolve()
    recipe = Path(__file__).resolve().parent.parent
    if path == recipe or recipe in path.parents:
        raise ValueError("Output must be outside the checked-out recipe")
    if source is not None:
        source = source.resolve()
        if path == source or source in path.parents or path in source.parents:
            raise ValueError("Output and source must be separate directories")
    if path.exists() and any(path.iterdir()):
        raise ValueError("Output must be a new, empty task-owned directory")
    path.mkdir(parents=True, exist_ok=True)
    return path

def isolated_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key, name in (("HOME", "home"), ("XDG_DATA_HOME", "data"),
                      ("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache")):
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        env[key] = str(directory)
    env["LIBGL_ALWAYS_SOFTWARE"] = "1"
    return env

def checked_godot(command: str) -> str:
    binary = Path(shutil.which(command) or command).resolve()
    if sha256(binary) != GODOT_BINARY_SHA256:
        raise ValueError("Godot executable SHA-256 differs from pinned official 4.6.3 host")
    return str(binary)

def copy_game(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in GAME_FILES:
        shutil.copyfile(source / name, destination / name)

def stop_process(process: subprocess.Popen | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

def check_engine_log(text: str) -> None:
    failures = [line for line in text.splitlines() if any(token in line for token in (
        "ERROR:", "Parse Error:", "Shader compilation failed", "Failed to load script",
        "handle_crash:", "Program crashed with signal"))]
    if failures:
        raise RuntimeError("Godot reported engine failures: " + " | ".join(failures[:8]))
