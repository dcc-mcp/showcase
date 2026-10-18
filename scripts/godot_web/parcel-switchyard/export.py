#!/usr/bin/env python3
"""Additive, pinned standard Godot Web export for Parcel Switchyard only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROJECT = ROOT / 'scripts/godot_web/projects/parcel-switchyard'
DEST = ROOT / 'play/parcel-switchyard'
VERSION = '4.6.3'
EDITOR_SHA = 'f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3'
TEMPLATES = {
    'web_nothreads_release.zip': '1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9',
    'web_nothreads_debug.zip': '4a8a8ef7519637f7898fad25f09d3e466965e99c04e441682e1bc2d97a548922',
}
ORIGINAL_COMMIT = '943ee722deeec46d64890370fd813498eeebb01c'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'bytes': path.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', default='godot')
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT / 'play/runtime', help='Existing official shared runtime; verified but never overwritten')
    args = parser.parse_args()
    editor = Path(shutil.which(args.godot) or args.godot).resolve()
    if sha(editor) != EDITOR_SHA:
        raise SystemExit('Use the pinned official Linux x86_64 Godot 4.6.3 editor')
    for name, expected in TEMPLATES.items():
        if sha(args.template.parent / name) != expected:
            raise SystemExit('Official template hash mismatch: ' + name)
    baseline = json.loads((HERE / 'original-baseline.json').read_text())
    if baseline['original_commit'] != ORIGINAL_COMMIT:
        raise SystemExit('Original baseline commit mismatch')
    for entry in baseline['files']:
        # Publication metadata may gain a separately dated additive review.
        # Native assets, old evidence, media, source ZIP and rights stay immutable.
        if Path(entry['path']).name in ['README.md', 'manifest.json', 'validation.json']:
            continue
        path = ROOT / entry['path']
        if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
            raise SystemExit('Historical artifact changed: ' + entry['path'])
    original = ROOT / 'docs/showcase/parcel-switchyard/native/parcel_game.gd'
    if (PROJECT / 'parcel_game.gd').read_bytes() != original.read_bytes():
        raise SystemExit('Original game source has changed; review source provenance first')
    runtime_records = []
    with zipfile.ZipFile(args.template) as archive:
        for name in ['godot.js', 'godot.wasm', 'godot.audio.worklet.js', 'godot.audio.position.worklet.js']:
            target = args.runtime / name.replace('godot.', 'godot-4.6.3.', 1)
            if not target.is_file() or target.read_bytes() != archive.read(name):
                raise SystemExit('Shared runtime must match official template bytes: ' + target.name)
            runtime_records.append({'path': 'play/runtime/' + target.name, 'sha256': sha(target), 'bytes': target.stat().st_size})
    with tempfile.TemporaryDirectory(prefix='parcel-web-export-') as temporary:
        tmp = Path(temporary)
        env = os.environ.copy()
        for name, folder in [('HOME', 'home'), ('XDG_DATA_HOME', 'data'), ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache')]:
            env[name] = str(tmp / folder)
            (tmp / folder).mkdir()
        template_dir = tmp / 'data/godot/export_templates/4.6.3.stable'
        template_dir.mkdir(parents=True)
        for name in TEMPLATES:
            shutil.copyfile(args.template.parent / name, template_dir / name)
        project = tmp / 'project'
        shutil.copytree(PROJECT, project, ignore=shutil.ignore_patterns('.godot'))
        output = tmp / 'export'
        output.mkdir()
        version = subprocess.check_output([str(editor), '--version'], text=True, env=env).strip()
        if not version.startswith('4.6.3.stable.official.'):
            raise SystemExit('Unexpected Godot version')
        commands = [('--editor', '--import', '--quit'), ('--', '--web-test'), ('--export-release', 'Web', str(output / 'game.html'))]
        native_report = None
        for flags in commands:
            result = subprocess.run([str(editor), '--headless', '--path', str(project), *flags], env=env, capture_output=True, text=True, timeout=120)
            log = result.stdout + result.stderr
            if result.returncode or any(word in log for word in ['SCRIPT ERROR', 'Parse Error', 'ERROR:']):
                raise SystemExit(log)
            for line in log.splitlines():
                if line.startswith('PARCEL_WEB_TEST_REPORT '):
                    native_report = json.loads(line.partition(' ')[2])
        page = (output / 'game.html').read_text()
        reopened = subprocess.run([str(editor), '--headless', '--main-pack', str(output / 'game.pck'),
                                   '--', '--web-test', '--lang=zh'], env=env, capture_output=True, text=True, timeout=120)
        replay_log = reopened.stdout + reopened.stderr
        if reopened.returncode or any(word in replay_log for word in ['SCRIPT ERROR', 'Parse Error', 'ERROR:']):
            raise SystemExit(replay_log)
        replay = [json.loads(line.partition(' ')[2]) for line in replay_log.splitlines() if line.startswith('PARCEL_WEB_TEST_REPORT ')]
        if len(replay) != 1 or not replay[0]['passed'] or len(replay[0]['checks']) != len(native_report['checks']):
            raise SystemExit('Exported PCK failed actual Chinese/font/rule reopening checks')
        match = re.search(r'const GODOT_CONFIG = (\{.*?\});', page)
        if not match:
            raise SystemExit('Official export configuration missing')
        config = json.loads(match.group(1))
        if config.get('threadPoolSize') not in (None, 0):
            raise SystemExit('Threaded export rejected')
        config.update(executable='../runtime/godot-4.6.3', ensureCrossOriginIsolationHeaders=False, emscriptenPoolSize=0, godotPoolSize=0,
                      showcasePackSha256=sha(output / 'game.pck'), fileSizes={'../runtime/godot-4.6.3.wasm': (args.runtime / 'godot-4.6.3.wasm').stat().st_size, 'game.pck': (output / 'game.pck').stat().st_size})
        DEST.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output / 'game.pck', DEST / 'game.pck')
        shell_version = hashlib.sha256((DEST / 'shell.js').read_bytes() + (DEST / 'shell.css').read_bytes()).hexdigest()[:12]
        html = (HERE / 'shell.html').read_text().replace('__CONFIG__', json.dumps(config, separators=(',', ':'))).replace('__SHELL_VERSION__', shell_version)
        (DEST / 'index.html').write_text(html)
        sources = [record(p) for p in sorted(PROJECT.rglob('*')) if p.is_file() and '.godot' not in p.parts]
        provenance = {'schema_version': 1, 'case': 'parcel-switchyard', 'recorded_at': '2026-10-18', 'original_commit': ORIGINAL_COMMIT,
                      'original_native_source': record(original), 'original_source_archive': record(ROOT / 'docs/showcase/parcel-switchyard/Parcel-Switchyard-Source.zip'),
                      'engine': version, 'editor_sha256': EDITOR_SHA, 'official_release': 'https://godotengine.org/download/archive/4.6.3-stable/',
                      'template_sha256': TEMPLATES[args.template.name], 'threads': False, 'renderer': 'gl_compatibility', 'pwa': False,
                      'source_files': sources, 'runtime_files': runtime_records, 'export_files': [record(DEST / name) for name in ['game.pck', 'index.html', 'shell.js', 'shell.css']],
                      'native_tests': native_report, 'exported_pack_reopened_tests': replay[0], 'browser_acceptance': {'status': 'not-tested', 'reason': 'A standard export and headless regressions do not establish real browser input.'},
                      'mcp_boundary': 'New adapter authored and exported directly with Godot CLI. Historical MCP evidence covers the original case only.',
                      'not_claimed': ['Physical phones', 'Safari/Firefox', 'Production deployment', 'New MCP authoring acceptance', 'Subjective visual acceptance', 'Byte-reproducible PCK output']}
        (DEST / 'export-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps({'exported': True, 'pack': record(DEST / 'game.pck'), 'native_checks': len(native_report['checks']), 'browser_acceptance': 'not-tested'}, indent=2))


if __name__ == '__main__':
    main()
