#!/usr/bin/env python3
"""Compare supported physics backends and preserve the known Group defect repro."""
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
CASES = ('baseline', 'explicit-group', 'empty-world', 'godot-world', 'jolt-world')
PHYSICS_CASES = ('godot-world', 'jolt-world')


def write_project(root, case):
    if case not in CASES:
        raise ValueError('Unknown isolation case: ' + case)
    root.mkdir(parents=True)
    physics = ('Jolt Physics' if case == 'jolt-world' else 'GodotPhysics3D'
               if case in ('empty-world', 'godot-world') else 'Dummy')
    node = 'Node3D' if case in ('empty-world', *PHYSICS_CASES) else 'Node'
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
    bodies = '''\tvar wall := StaticBody3D.new()
\tvar wall_shape := CollisionShape3D.new()
\tvar box := BoxShape3D.new()
\tbox.size = Vector3(1,3,3)
\twall_shape.shape = box
\twall.add_child(wall_shape)
\tadd_child(wall)
\thero = CharacterBody3D.new()
\thero.motion_mode = CharacterBody3D.MOTION_MODE_FLOATING
\thero.position = Vector3(-3,0,0)
\thero.collision_layer = 2
\thero.collision_mask = 1
\tvar hero_shape := CollisionShape3D.new()
\tvar capsule := CapsuleShape3D.new()
\tcapsule.radius = 0.35
\tcapsule.height = 1.5
\thero_shape.shape = capsule
\thero.add_child(hero_shape)
\tadd_child(hero)
''' if case in PHYSICS_CASES else ''
    physics_check = '''\tvar hit := get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(-3,0,0),Vector3(3,0,0),1))
\tvar blocked: bool = hero.position.x > -1.2 and hero.position.x < -0.7
\tprint("GROUP_REPRO_PHYSICS ", JSON.stringify({"blocked":blocked,"ray_hit":not hit.is_empty(),"backend":ProjectSettings.get_setting("physics/3d/physics_engine")}))
''' if case in PHYSICS_CASES else ''
    movement = '''
func _physics_process(_delta: float) -> void:
\tif is_instance_valid(hero):
\t\thero.velocity = Vector3(2,0,0)
\t\thero.move_and_slide()
''' if case in PHYSICS_CASES else ''
    (root / 'main.gd').write_text('extends ' + node + '''
var hero: CharacterBody3D
func _ready() -> void:
''' + group + bodies + '\tfor _frame in range(' + ('120' if case in PHYSICS_CASES else '10') + '''):
\t\tawait get_tree().physics_frame
''' + physics_check + '''
\tprint("GROUP_REPRO_READY ", JSON.stringify(Engine.get_version_info()))
func _noop(_index: int) -> void:
\tpass
''' + movement)


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
    expected = [GROUP_ERROR] if case in ('explicit-group', 'godot-world') else []
    physics = [json.loads(line.removeprefix('GROUP_REPRO_PHYSICS ')) for line in console
               if line.startswith('GROUP_REPRO_PHYSICS ')]
    physics_passed = (len(physics) == 1 and physics[0].get('blocked') is True
                      and physics[0].get('ray_hit') is True
                      and physics[0].get('backend') == ('Jolt Physics' if case == 'jolt-world' else 'GodotPhysics3D')) if case in PHYSICS_CASES else True
    # A diagnostic match is not a clean-exit pass: preserve both explicitly.
    match = (ready and ended and not page_errors and errors == expected
             and (case != 'explicit-group' or group_completed) and physics_passed)
    return {'case': case, 'diagnostic_expectation_matched': match,
            'ready': ready, 'actual_engine_exit_code_zero': ended,
            'explicit_group_completed': group_completed, 'engine_errors': errors,
            'clean_engine_exit': ready and ended and not errors and not page_errors,
            'physics_collision_checks_passed': physics_passed, 'physics': physics,
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
              'diagnosis_confirmed': False, 'template_sha256': sha256(args.template), 'cases': [],
              'scope': 'Known-bug cases retain expected errors; candidate Jolt must collide and quit cleanly. Actual game has its own strict error gate.'}
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
        report['diagnosis_confirmed'] = len(report['cases']) == len(CASES) and all(
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
