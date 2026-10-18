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
GAME_FILES = ("main.gd", "swim_controller.gd", "verify_swimming.gd", "verify_treasure.gd", "verify_collision.gd", "water.gdshader", "start.tscn", "project.godot",
              "sanctuary-font.otf", "FONT-LICENSE.txt", "FONT-NOTICE.txt", "FONT-SOURCE.json",
              "assets/shore-rock-a.tscn", "assets/shore-rock-d.tscn",
              "assets/coastal-tree.tscn", "assets/needle-pine.tscn",
              "assets/KENNEY-LICENSE.txt", "assets/SOURCE.json",
              "assets/polyhaven/fern-0.res", "assets/polyhaven/fern-1.res",
              "assets/polyhaven/fern-2.res", "assets/polyhaven/fern-3.res",
              "assets/polyhaven/fern-albedo.png.bin", "assets/polyhaven/fern-normal.jpg.bin",
              "assets/polyhaven/stone-diff.jpg.bin", "assets/polyhaven/stone-normal.png.bin",
              "assets/polyhaven/stone-rough.jpg.bin",
              "assets/POLYHAVEN-LICENSE.txt", "assets/POLYHAVEN-SOURCE.json")
ASSET_NOTICE_FILES = ("assets/KENNEY-LICENSE.txt", "assets/SOURCE.json",
                      "assets/POLYHAVEN-LICENSE.txt", "assets/POLYHAVEN-SOURCE.json")
TROPICAL_FILES = ("assets/tropical/palm-a.glb", "assets/tropical/palm-b.glb",
                  "assets/tropical/understory-a.glb", "assets/tropical/understory-b.glb",
                  "assets/tropical/bush-a.glb", "assets/tropical/shore-stone-a.glb",
                  "assets/tropical/shore-stone-b.glb", "assets/tropical/explorer.glb")
TROPICAL_NOTICES = ("assets/tropical/FOREST-LICENSE.txt", "assets/tropical/ADVENTURERS-LICENSE.txt",
                    "assets/tropical/SOURCE.json")
GAME_FILES += TROPICAL_FILES + TROPICAL_NOTICES
ASSET_NOTICE_FILES += TROPICAL_NOTICES
STORY_FILES = ("tide_interface.gd", "tide_audio.gd", "verify_audio.gd", "verify_story.gd",
               "assets/story/story.en-zh.json", "assets/story/chart.svg", "assets/story/key.svg",
               "assets/story/pearl.svg", "assets/story/beacon.svg", "assets/story/check.svg",
               "assets/story/audio-on.svg", "assets/story/audio-off.svg",
               "assets/audio/tidekeeper-loop.ogg", "assets/audio/chart_read.wav",
               "assets/audio/key_pickup.wav", "assets/audio/pearl_pickup.wav", "assets/audio/beacon_resolve.wav")
STORY_NOTICES = ("assets/audio/SOURCE.json", "assets/audio/NOTICE.txt", "assets/story/SOURCE.json", "assets/story/NOTICE.txt")
GAME_FILES += STORY_FILES + STORY_NOTICES
ASSET_NOTICE_FILES += STORY_NOTICES
RAW_STORY_FILES = ("assets/story/story.en-zh.json",)

# Only these manifest-owned static image buffers are copied/exported as raw bytes.
RAW_IMAGE_FILES = tuple(name for name in GAME_FILES if name.endswith(".bin"))


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
        (destination / name).parent.mkdir(parents=True, exist_ok=True)
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
        "handle_crash:", "Program crashed with signal", "Failed to save IDB file system", "Already syncing!"))]
    if failures:
        raise RuntimeError("Godot reported engine failures: " + " | ".join(failures[:8]))
