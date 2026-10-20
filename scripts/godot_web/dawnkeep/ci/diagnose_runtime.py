#!/usr/bin/env python3
"""Read current host capabilities and execute a bounded actual headless probe."""
from __future__ import annotations
import argparse
import importlib.metadata
import os
import shutil
import subprocess
from pathlib import Path
from common import checked_godot, isolated_env, isolated_output, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--godot', default='godot')
    args = parser.parse_args()
    out = isolated_output(args.output)
    report = {'schema': 1, 'display': os.environ.get('DISPLAY'), 'wayland': os.environ.get('WAYLAND_DISPLAY'),
              'tools': {name: shutil.which(name) for name in ('godot','Xvfb','Xorg','xdotool','xwininfo','ffmpeg','ffprobe','chromium')},
              'packages': {}, 'native_rendering': 'not-tested', 'browser': 'not-tested'}
    for name in ('dcc-mcp-godot','dcc-mcp-core','playwright','Pillow'):
        try:
            report['packages'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report['packages'][name] = None
    project = out / 'probe-project'
    project.mkdir()
    (project / 'project.godot').write_text('[application]\nconfig/name="Dawnkeep capability probe"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    (project / 'probe.gd').write_text('extends SceneTree\nfunc _initialize():\n print("DAWNKEEP_HEADLESS_PROBE ", JSON.stringify({"version":Engine.get_version_info().string,"display":DisplayServer.get_name()}))\n quit(0)\n')
    try:
        godot = checked_godot(args.godot)
        process = subprocess.run([godot,'--headless','--path',str(project),'--script','res://probe.gd'],
                                 env=isolated_env(out / 'session'), capture_output=True, text=True, timeout=30)
        log = process.stdout + process.stderr
        (out / 'headless.log').write_text(log)
        report['headless'] = {'returncode': process.returncode, 'passed': process.returncode == 0 and 'DAWNKEEP_HEADLESS_PROBE ' in log,
                              'scope': 'Real engine script execution; headless proves no visual rendering or physical input'}
    finally:
        write_json(out / 'environment.json', report)
    print(report)


if __name__ == '__main__':
    main()
