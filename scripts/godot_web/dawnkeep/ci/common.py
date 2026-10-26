"""Isolated, manifest-bound Dawnkeep acceptance helpers."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

GODOT_VERSION = '4.6.3.stable.official.7d41c59c4'
GODOT_BINARY_SHA256 = 'f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3'
WEB_TEMPLATE_SHA256 = '1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9'
WEB_DEBUG_SHA256 = '4a8a8ef7519637f7898fad25f09d3e466965e99c04e441682e1bc2d97a548922'
REQUIRED_FILES = ('project.godot', 'start.tscn', 'gameplay.gd', 'visuals.gd', 'hud.gd', 'main.gd')
SCRIPT_ORDER = ('gameplay.gd', 'visuals.gd', 'hud.gd', 'main.gd')
ALLOWED_SUFFIXES = {'.gd', '.gdshader', '.tscn', '.tres', '.res', '.godot', '.png', '.jpg', '.jpeg', '.webp', '.svg', '.bin', '.otf', '.ttf', '.wav', '.ogg', '.mp3', '.json', '.txt', '.md', '.glb', '.gltf', '.obj', '.mtl', '.uid'}
EXCLUDED_DIRS = {'.godot', '.git', '__pycache__'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def source_inventory(source):
    """Generate an explicit hash inventory; fail on symlinks/unrecognized assets."""
    source = Path(source).resolve()
    entries = []
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError('Source symlinks are not packaged: ' + relative.as_posix())
        if not path.is_file() or path.suffix == '.import':
            continue
        if any(part.startswith('.') for part in relative.parts) or path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError('Unrecognized source inventory member: ' + relative.as_posix())
        entries.append({'path': relative.as_posix(), 'sha256': sha256(path), 'bytes': path.stat().st_size})
    missing = set(REQUIRED_FILES) - {entry['path'] for entry in entries}
    if missing:
        raise ValueError('Missing required game sources: ' + ', '.join(sorted(missing)))
    return {'schema': 1, 'files': entries}


def verify_inventory(source, inventory):
    actual = source_inventory(source)
    if actual != inventory:
        raise ValueError('Source bytes/inventory changed during this acceptance run')


def copy_game(source, destination, inventory=None):
    source, destination = Path(source), Path(destination)
    inventory = inventory or source_inventory(source)
    destination.mkdir(parents=True, exist_ok=True)
    for entry in inventory['files']:
        name = entry['path']
        if sha256(source / name) != entry['sha256']:
            raise ValueError('Input file changed after inventory: ' + name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    return inventory


def isolated_output(path, source=None):
    path = Path(path).resolve()
    recipe = Path(__file__).resolve().parent.parent
    if path == recipe or recipe in path.parents:
        raise ValueError('Generated output must be outside the checked-out recipe')
    if source is not None:
        source = Path(source).resolve()
        if path == source or source in path.parents or path in source.parents:
            raise ValueError('Source and output must be separate directories')
    if path.exists() and any(path.iterdir()):
        raise ValueError('Output must be a new empty task-owned directory')
    path.mkdir(parents=True, exist_ok=True)
    return path


def isolated_env(root):
    env = os.environ.copy()
    for key, name in (('HOME','home'),('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')):
        directory = Path(root) / name
        directory.mkdir(parents=True, exist_ok=True)
        env[key] = str(directory)
    env['LIBGL_ALWAYS_SOFTWARE'] = '1'
    return env


def checked_godot(command):
    binary = Path(shutil.which(command) or command).resolve()
    if sha256(binary) != GODOT_BINARY_SHA256:
        raise ValueError('Godot executable SHA-256 differs from pinned official 4.6.3 host')
    return str(binary)


def stop_process(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def check_engine_log(text):
    tokens = ('ERROR:', 'SCRIPT ERROR:', 'Parse Error:', 'Shader compilation failed', 'Failed to load script', 'handle_crash:', 'Program crashed with signal')
    failures = [line for line in text.splitlines() if any(token in line for token in tokens)]
    if failures:
        raise RuntimeError('Godot engine failures: ' + ' | '.join(failures[:8]))


def receipts(text, prefix='DAWNKEEP_STATE'):
    values = []
    for line in text.splitlines():
        if line.startswith(prefix + ' '):
            value = json.loads(line[len(prefix) + 1:])
            if not isinstance(value, dict):
                raise ValueError('Observer must return an object')
            values.append(value)
    return values
