#!/usr/bin/env python3
"""Export only the task-owned native candidate with the pinned official no-threads template."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from mcp_export import export_through_mcp, inspect_clean_pck
from common import ASSET_NOTICE_FILES, GAME_FILES, RAW_IMAGE_FILES, RAW_STORY_FILES, WEB_TEMPLATE_SHA256, checked_godot, check_engine_log, copy_game, isolated_env, isolated_output, sha256, write_json


def raw_include_filter():
    # Godot imports ordinary resources normally. Static image byte buffers are
    # retained by exact manifest path, never a blanket binary-file inclusion.
    return ",".join(("*.otf", *RAW_IMAGE_FILES, *RAW_STORY_FILES))


def copy_asset_notices(native, site):
    for name in ASSET_NOTICE_FILES:
        destination = site / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(native / name, destination)


WEB_AUDIO_FILES = ("assets/audio/tidekeeper-loop.ogg", "assets/audio/chart_read.wav",
                   "assets/audio/key_pickup.wav", "assets/audio/pearl_pickup.wav",
                   "assets/audio/beacon_resolve.wav")


def prepare_audio_before_game(page):
    """Use the pinned shell's existing boot flow, before its first 3D frame.

    The bounded preload never resumes the context or creates a source. On a
    loading error the native opening still owns Retry; no automatic retry or
    false playing state is introduced by the shell.
    """
    scope = "(function () {"
    start = "engine.startGame({"
    if page.count(scope) != 1 or page.count(start) != 1:
        raise RuntimeError("Official shell boot scope changed")
    urls = dict(zip(("music", "chart_read", "key_pickup", "pearl_pickup", "beacon_resolve"), WEB_AUDIO_FILES))
    page = page.replace(scope, "(async function () {")
    return page.replace(start, "await window.TidalWebAudio.initialize(" + json.dumps(urls) + ");\n\t\t" + start)


def copy_web_audio(native, site):
    """Publish only exact manifest-owned original audio bytes, never substitutes."""
    for name in ("web_audio.js", *WEB_AUDIO_FILES):
        if name not in GAME_FILES:
            raise ValueError("Browser audio is outside the source manifest: " + name)
        destination = site / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(native / name, destination)
        if sha256(destination) != sha256(native / name):
            raise ValueError("Browser audio changed while copying: " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--license-dir", type=Path, required=True)
    parser.add_argument("--godot", default="godot")
    args = parser.parse_args()
    out = isolated_output(args.output, args.native)
    godot = checked_godot(args.godot)
    if sha256(args.template) != WEB_TEMPLATE_SHA256:
        raise ValueError("Official single-threaded Web release template SHA-256 mismatch")
    project = out / "export-project"
    copy_game(args.native, project)
    site = out / "site"
    site.mkdir()
    env = isolated_env(out / "session")
    templates = Path(env["XDG_DATA_HOME"]) / "godot/export_templates/4.6.3.stable"
    templates.mkdir(parents=True)
    shutil.copyfile(args.template, templates / "web_nothreads_release.zip")
    debug = args.template.parent / "web_nothreads_debug.zip"
    if debug.exists():
        if sha256(debug) != "4a8a8ef7519637f7898fad25f09d3e466965e99c04e441682e1bc2d97a548922":
            raise ValueError("Official single-threaded Web debug template SHA-256 mismatch")
        shutil.copyfile(debug, templates / debug.name)
    preset = '''[preset.0]
name="Web"
platform="Web"
runnable=true
export_filter="all_resources"
include_filter="__RAW_INCLUDE_FILTER__"
exclude_filter="addons/*,tidal_export_*,web-output/*"
export_path=""
script_export_mode=2

[preset.0.options]
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
progressive_web_app/enabled=false
'''
    preset = preset.replace('__RAW_INCLUDE_FILTER__', raw_include_filter())
    preset += 'custom_template/release=' + json.dumps(str(args.template.resolve())) + '\n'
    (project / "export_presets.cfg").write_text(preset)
    report = {"passed": False, "threads": False, "renderer": "gl_compatibility",
              "official_template_sha256": WEB_TEMPLATE_SHA256,
              "raw_image_files": list(RAW_IMAGE_FILES), "include_filter": raw_include_filter(),
              "native_sha256": {name: sha256(args.native / name) for name in GAME_FILES}}
    try:
        native_hashes = {name: sha256(args.native / name) for name in GAME_FILES}
        exported = export_through_mcp(godot, project, out, env, native_hashes)
        report["ecosystem_export"] = json.loads((out / "export-mcp.json").read_text())
        report["pack_inspection"] = inspect_clean_pck(exported / "index.pck")
        for item in exported.iterdir():
            if not item.is_file():
                raise RuntimeError("Unexpected directory in owned Web export")
            shutil.copyfile(item, site / item.name)
        page = (site / "index.html").read_text()
        match = re.search(r'const GODOT_CONFIG = (\{.*?\});', page)
        if not match:
            raise RuntimeError("Official Web shell did not expose its export configuration")
        config = json.loads(match[1])
        if config.get("extensionLibs"):
            raise RuntimeError("Unexpected Web extension library in this procedural prototype")
        # Single-threaded export does not require cross-origin-isolation or a service worker.
        # Do not invent a second engine shell or rewrite gameplay code.
        config["ensureCrossOriginIsolationHeaders"] = False
        config["emscriptenPoolSize"] = 0
        config["godotPoolSize"] = 0
        # Public engine CLI selection, Web export only. The owned browser graph
        # handles ALL five sounds; no silent second Godot AudioContext is allowed.
        config["args"] = [*config.get("args", []), "--audio-driver", "Dummy"]
        page = page[:match.start(1)] + json.dumps(config) + page[match.end(1):]
        marker = "const engine = new Engine(GODOT_CONFIG);"
        if page.count(marker) != 1:
            raise RuntimeError("Official shell engine marker changed")
        page = page.replace(marker, "const tidalExit = window.TidalSaveExit.attach(GODOT_CONFIG, () => engine.requestQuit());\n" + marker)
        page = page.replace('<script src="index.js"></script>', '<script src="index.js"></script>\n<script src="web_audio.js"></script>\n<script src="save-exit.js"></script>')
        if 'src="save-exit.js"' not in page:
            raise RuntimeError("Official shell script marker changed")
        page = prepare_audio_before_game(page)
        (site / "index.html").write_text(page)
        shutil.copyfile(Path(__file__).with_name("web_exit.js"), site / "save-exit.js")
        shutil.copyfile(args.native / "sanctuary-font.otf", site / "sanctuary-font.otf")
        for name in ("LICENSE.txt", "COPYRIGHT.txt"):
            shutil.copyfile(args.license_dir / name, site / name)
        for name in ("FONT-LICENSE.txt", "FONT-NOTICE.txt", "FONT-SOURCE.json"):
            shutil.copyfile(args.native / name, site / name)
        copy_asset_notices(args.native, site)
        copy_web_audio(args.native, site)
        for name in ("index.html", "index.js", "index.wasm", "index.pck"):
            if not (site / name).is_file() or (site / name).stat().st_size == 0:
                raise RuntimeError(f"Expected official Web export file is missing: {name}")
        (site / "README.txt").write_text(
            "Tidal Sanctuary: unpublished original 3D playable prototype\n\n"
            "Keep this folder together. Run: python -m http.server 8000\n"
            "Open http://localhost:8000/ in a WebGL 2-capable browser.\n\n"
            "Choose Begin / Continue before playing or enabling music.\n"
            "WASD / arrows: move/swim. E: interact. J: journal. M: sound. R: request restart. L: language.\n"
            "Touch: drag left to move; tap action to interact. Journal includes confirmed restart.\n"
            "Read the beach map, recover the inland and sea treasures, then return to the ring.\n\n"
            "Web: use Save & return and wait for Saved before leaving. Immediate tab close can interrupt storage.\n"
            "This is CI staging, not a public deployment.\n"
            "The native movie is an explicitly scripted traversal of the real game.\n"
            "Browser portrait evidence is emulation, not a physical-phone test.\n"
            "Web audio: one browser-native looping graph via Godot JavaScriptBridge; desktop uses Godot audio.\n"
            "If audio preparation fails, use the native Retry audio action before Begin.\n"
            "Godot runtime notices: LICENSE.txt and COPYRIGHT.txt.\n"
            "Subset font: SIL Open Font License, see FONT-LICENSE.txt.\n"
            "Kenney models: CC0, see assets/KENNEY-LICENSE.txt and assets/SOURCE.json.\n"
            "Poly Haven models/textures: CC0, see assets/POLYHAVEN-LICENSE.txt and assets/POLYHAVEN-SOURCE.json.\n")
        report.update({"passed": True, "godot": subprocess.check_output([godot, "--version"], text=True).strip(),
            "web_config": config, "files": {item.relative_to(site).as_posix(): {"sha256": sha256(item), "bytes": item.stat().st_size}
            for item in site.rglob("*") if item.is_file()}})
    except Exception as error:
        report["blocker"] = str(error)
        raise
    finally:
        write_json(out / "export.json", report)


if __name__ == "__main__":
    main()
