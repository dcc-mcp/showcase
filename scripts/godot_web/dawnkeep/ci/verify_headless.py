#!/usr/bin/env python3
"""Run exact-source mechanics, layout, integration and balance fixtures."""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
from common import checked_godot, check_engine_log, copy_game, isolated_env, isolated_output, sha256, verify_inventory, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--godot', default='godot')
    args = parser.parse_args()
    out = isolated_output(args.output, args.source)
    godot = checked_godot(args.godot)
    project = out / 'test-project'
    manifest = copy_game(args.source, project)
    write_json(out / 'source-manifest.json', manifest)
    env = isolated_env(out / 'session')
    report = {'schema': 1, 'passed': False, 'scope': 'Headless fixtures and synthetic public-command balance; not real-input, visual, audio or difficulty acceptance', 'runs': {}}
    jobs = [('import', ['--editor', '--import', '--quit'], None)]
    for name, script, prefix in (
        ('gameplay', 'verify_gameplay.gd', 'DAWNKEEP_GAMEPLAY_CHECKS'),
        ('ui', 'verify_ui.gd', 'DAWNKEEP_UI_CHECKS'),
        ('runtime', 'verify_runtime.gd', 'DAWNKEEP_RUNTIME_CHECKS'),
    ):
        jobs.append((name, ['--script', script], prefix))
    for controller in ('active', 'afk'):
        jobs.append(('balance-' + controller, ['--script', 'verify_gameplay.gd', '--', '--balance-' + controller], 'DAWNKEEP_BALANCE'))
    try:
        for name, options, prefix in jobs:
            result = subprocess.run([godot, '--headless', '--fixed-fps', '60', '--path', str(project), *options], env=env, capture_output=True, text=True, timeout=240)
            log = result.stdout + result.stderr
            (out / (name + '.log')).write_text(log)
            check_engine_log(log)
            if result.returncode:
                raise RuntimeError(name + ' returned ' + str(result.returncode))
            if prefix:
                values = [json.loads(line[len(prefix)+1:]) for line in log.splitlines() if line.startswith(prefix+' ')]
                if len(values) != 1 or values[0].get('passed') is not True:
                    raise RuntimeError(name + ' did not produce exactly one passing receipt')
                report['runs'][name] = values[0]
            else:
                report['runs'][name] = {'passed': True}
        verify_inventory(args.source, manifest)
        for entry in manifest['files']:
            if sha256(project / entry['path']) != entry['sha256']:
                raise RuntimeError('Host changed source: ' + entry['path'])
        report['passed'] = True
    except Exception as error:
        report['blocker'] = str(error)
        raise
    finally:
        write_json(out / 'headless.json', report)


if __name__ == '__main__':
    main()
