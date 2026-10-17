#!/usr/bin/env python3
"""Export only the task-owned native candidate with the pinned official no-threads template."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from common import GAME_FILES, WEB_TEMPLATE_SHA256, checked_godot, check_engine_log, copy_game, isolated_env, isolated_output, sha256, write_json


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
include_filter="*.otf"
exclude_filter=""
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
    preset += 'custom_template/release=' + json.dumps(str(args.template.resolve())) + '\n'
    (project / "export_presets.cfg").write_text(preset)
    report = {"passed": False, "threads": False, "renderer": "gl_compatibility",
              "official_template_sha256": WEB_TEMPLATE_SHA256,
              "native_sha256": {name: sha256(args.native / name) for name in GAME_FILES}}
    try:
        for name, extra in (("import", ["--editor", "--import", "--quit"]),
                            ("export", ["--export-release", "Web", str(site / "index.html")])):
            process = subprocess.run([godot, "--headless", "--path", str(project), *extra],
                                      env=env, capture_output=True, text=True, timeout=240)
            output = process.stdout + process.stderr
            (out / (name + ".log")).write_text(output)
            check_engine_log(output)
            if process.returncode != 0 or "ERROR:" in output:
                raise RuntimeError(f"Official Godot {name} failed; inspect {name}.log")
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
        page = page[:match.start(1)] + json.dumps(config) + page[match.end(1):]
        (site / "index.html").write_text(page)
        for name in ("LICENSE.txt", "COPYRIGHT.txt"):
            shutil.copyfile(args.license_dir / name, site / name)
        shutil.copyfile(args.native / "FONT-LICENSE.txt", site / "FONT-LICENSE.txt")
        notices = site / "assets"
        notices.mkdir()
        for name in ("KENNEY-LICENSE.txt", "SOURCE.json"):
            shutil.copyfile(args.native / "assets" / name, notices / name)
        for name in ("index.html", "index.js", "index.wasm", "index.pck"):
            if not (site / name).is_file() or (site / name).stat().st_size == 0:
                raise RuntimeError(f"Expected official Web export file is missing: {name}")
        (site / "README.txt").write_text(
            "Tidal Sanctuary: unpublished original 3D playable prototype\n\n"
            "Keep this folder together. Run: python -m http.server 8000\n"
            "Open http://localhost:8000/ in a WebGL 2-capable browser.\n\n"
            "WASD / arrows: walk. E: interact. R: restart. L: language. H: hide UI.\n"
            "Touch: drag on the left to move; use the LIGHT button to interact.\n\n"
            "This is CI staging, not a public deployment.\n"
            "The native movie is an explicitly scripted traversal of the real game.\n"
            "Browser portrait evidence is emulation, not a physical-phone test.\n"
            "Godot runtime notices: LICENSE.txt and COPYRIGHT.txt.\n"
            "Subset font: SIL Open Font License, see FONT-LICENSE.txt.\n"
            "Kenney models: CC0, see assets/KENNEY-LICENSE.txt and assets/SOURCE.json.\n")
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
