#!/usr/bin/env python3
"""Isolate the pinned single-thread Web Group leak; not game acceptance."""
from __future__ import annotations
import argparse
import json
import subprocess
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from capture_browser import BROWSER_ARGS, BROWSER_IGNORED_DEFAULT_ARGS, QuietHandler, browser_executable
from common import WEB_TEMPLATE_SHA256, checked_godot, check_engine_log, isolated_env, isolated_output, sha256, write_json

GROUP_ERROR = 'ERROR: Pages in use exist at exit in PagedAllocator: N16WorkerThreadPool5GroupE'
CASES = ('baseline', 'explicit-group', 'physics-world')


def write_project(root, case):
    if case not in CASES:
        raise ValueError('Unknown isolation case: ' + case)
    root.mkdir(parents=True)
    physics = 'GodotPhysics3D' if case == 'physics-world' else 'Dummy'
    node = 'Node3D' if case == 'physics-world' else 'Node'
    (root / 'project.godot').write_text('''config_version=5
[application]
config/name="Single-thread Group isolation"
run/main_scene="res://start.tscn"
config/features=PackedStringArray("4.6", "GL Compatibility")
[display]
window/size/viewport_width=640
window/size/viewport_height=360
[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
[physics]
2d/physics_engine="Dummy"
3d/physics_engine="''' + physics + '"\n')
    (root / 'start.tscn').write_text('''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://main.gd" id="1"]
[node name="Isolation" type="''' + node + '''"]
script = ExtResource("1")
''')
    group = '''\tvar id := WorkerThreadPool.add_group_task(_noop, 1)
\tWorkerThreadPool.wait_for_group_task_completion(id)
\tprint("GROUP_REPRO_COMPLETED")
''' if case == 'explicit-group' else ''
    (root / 'main.gd').write_text('extends ' + node + '''
func _ready() -> void:
''' + group + '''\tfor _frame in range(10):
\t\tawait get_tree().physics_frame
\tprint("GROUP_REPRO_READY ", JSON.stringify(Engine.get_version_info()))
func _noop(_index: int) -> void:
\tpass
''')


def patch_diagnostic_shell(page):
    """Preserve the official engine/loader, add only a real quit button and receipt."""
    marker = 'const engine = new Engine(GODOT_CONFIG);'
    start = 'engine.startGame({'
    if page.count(marker) != 1 or page.count(start) != 1:
        raise RuntimeError('Official diagnostic shell markers changed')
    page = page.replace(marker, marker + '''
const quit = document.createElement('button');
quit.id = 'group-repro-quit'; quit.textContent = 'Quit isolation test';
quit.style.cssText = 'position:fixed;top:10px;left:10px;z-index:100';
quit.addEventListener('click', () => engine.requestQuit());
document.body.appendChild(quit);
''')
    return page.replace(start, start + "\n'onExit': (code) => console.log('GROUP_REPRO_EXIT ' + code),")


def classify(case, console, page_errors):
    errors = [line for line in console if 'ERROR:' in line]
    ready = any(line.startswith('GROUP_REPRO_READY ') for line in console)
    ended = 'GROUP_REPRO_EXIT 0' in console
    group_completed = 'GROUP_REPRO_COMPLETED' in console
    expected = [] if case == 'baseline' else [GROUP_ERROR]
    # A diagnostic match is not a clean-exit pass: preserve both explicitly.
    match = (ready and ended and not page_errors and errors == expected
             and (case != 'explicit-group' or group_completed))
    return {'case': case, 'diagnostic_expectation_matched': match,
            'ready': ready, 'actual_engine_exit_code_zero': ended,
            'explicit_group_completed': group_completed, 'engine_errors': errors,
            'clean_engine_exit': ready and ended and not errors and not page_errors,
            'javascript_errors': page_errors}


def main():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--chromium', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = isolated_output(args.output)
    report = {'schema': 1, 'purpose': 'Engine defect isolation; not game acceptance',
              'diagnosis_confirmed': False, 'template_sha256': sha256(args.template), 'cases': []}
    server = None
    try:
        if report['template_sha256'] != WEB_TEMPLATE_SHA256:
            raise ValueError('Isolation requires the exact game Web template')
        godot = checked_godot(args.godot)
        report['host_binary_sha256'] = sha256(godot)
        for case in CASES:
            root = out / case
            project = root / 'project'
            write_project(project, case)
            site = root / 'site'
            site.mkdir()
            (project / 'export_presets.cfg').write_text('''[preset.0]
name="Web"
platform="Web"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path=""
script_export_mode=2
[preset.0.options]
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/canvas_resize_policy=2
progressive_web_app/enabled=false
custom_template/release=''' + json.dumps(str(args.template.resolve())) + '\n')
            env = isolated_env(root / 'session')
            for name, extra in (('import', ['--editor', '--import', '--quit']),
                                ('export', ['--export-release', 'Web', str(site / 'index.html')])):
                result = subprocess.run([godot, '--headless', '--path', str(project), *extra],
                                        env=env, capture_output=True, text=True, timeout=120)
                log = result.stdout + result.stderr
                (root / (name + '.log')).write_text(log)
                check_engine_log(log)
                if result.returncode:
                    raise RuntimeError(case + ' ' + name + ' failed')
            page = site / 'index.html'
            page.write_text(patch_diagnostic_shell(page.read_text()))
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(out)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        selected = browser_executable(args.chromium)
        report['browser'] = {**selected, 'chromium_sandbox': True, 'args': BROWSER_ARGS,
                             'ignore_default_args': BROWSER_IGNORED_DEFAULT_ARGS}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=selected['executable_path'], headless=True,
                                         chromium_sandbox=True, args=BROWSER_ARGS,
                                         ignore_default_args=BROWSER_IGNORED_DEFAULT_ARGS)
            try:
                for case in CASES:
                    console, page_errors = [], []
                    context = browser.new_context(viewport={'width': 640, 'height': 360})
                    page = context.new_page()
                    page.on('console', lambda message: console.append(message.text))
                    page.on('pageerror', lambda error: page_errors.append(str(error)))
                    try:
                        page.goto(f'http://127.0.0.1:{server.server_port}/{case}/site/index.html', wait_until='domcontentloaded')
                        for prefix, timeout in (('GROUP_REPRO_READY ', 60), ('GROUP_REPRO_EXIT ', 30)):
                            if prefix.startswith('GROUP_REPRO_EXIT'):
                                page.locator('#group-repro-quit').click()
                            deadline = time.monotonic() + timeout
                            while time.monotonic() < deadline and not any(line.startswith(prefix) for line in console):
                                if page_errors:
                                    break
                                page.wait_for_timeout(100)
                            if not any(line.startswith(prefix) for line in console):
                                raise TimeoutError('Missing actual ' + case + ' ' + prefix)
                        page.screenshot(path=str(out / case / 'after-quit.png'))
                    finally:
                        context.close()
                        (out / case / 'console.log').write_text('\n'.join(console) + '\n')
                        report['cases'].append(classify(case, console, page_errors))
                        write_json(out / 'diagnosis.json', report)
            finally:
                browser.close()
        report['diagnosis_confirmed'] = len(report['cases']) == 3 and all(
            item['diagnostic_expectation_matched'] for item in report['cases'])
        if not report['diagnosis_confirmed']:
            raise RuntimeError('Observed isolation outcomes differ; inspect unsuppressed logs')
    except Exception as error:
        report['blocker'] = str(error)
        raise
    finally:
        if server:
            server.shutdown()
        write_json(out / 'diagnosis.json', report)


if __name__ == '__main__':
    main()
