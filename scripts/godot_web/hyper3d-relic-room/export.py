"""Export an isolated Godot 4.6.3 candidate and compare its official shared runtime."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

TEMPLATE_SHA = '1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9'
UNUSED_HISTORICAL = frozenset(('assets/chest.glb', 'assets/guardian.glb'))
RUNTIME = {'index.js': 'godot-4.6.3.js', 'index.wasm': 'godot-4.6.3.wasm',
           'index.audio.worklet.js': 'godot-4.6.3.audio.worklet.js',
           'index.audio.position.worklet.js': 'godot-4.6.3.audio.position.worklet.js'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def without_editor_bridge(source):
    sections = re.split(r'(?m)(?=^\[)', source)
    return ''.join(part for part in sections if not part.startswith(('[autoload]', '[editor_plugins]')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('godot', 'template', 'showcase-repo', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--omit-unused-historical', action='store_true',
                        help='Omit the old closed chest and block guardian from the isolated Web copy only.')
    args = parser.parse_args()
    project = Path(__file__).resolve().parent / 'game'
    output = args.output.resolve()
    if output == project or project in output.parents:
        raise ValueError('Export outside the native source directory')
    template = args.template.resolve()
    if sha(template.read_bytes()) != TEMPLATE_SHA:
        raise ValueError('The official 4.6.3 single-thread release template hash differs')
    version = subprocess.check_output([str(args.godot), '--version'], text=True).strip()
    if version != '4.6.3.stable.official.7d41c59c4':
        raise ValueError('Use official Godot 4.6.3; received ' + version)
    output.mkdir(parents=True, exist_ok=False)
    stage = output / 'export-project'
    stage.mkdir()
    source_manifest = []
    omitted_source_assets = []
    for file in sorted(project.rglob('*')):
        relative = file.relative_to(project)
        if not file.is_file() or relative.parts[0] in ('.godot', '.dcc-mcp', 'addons', 'tests'):
            continue
        if relative.suffix == '.import' or (relative.parts[0] == 'assets' and relative.suffix == '.png'):
            continue
        data = file.read_bytes()
        if args.omit_unused_historical and relative.as_posix() in UNUSED_HISTORICAL:
            omitted_source_assets.append({'path': relative.as_posix(), 'bytes': len(data), 'sha256': sha(data)})
            continue
        source_manifest.append({'path': relative.as_posix(), 'bytes': len(data), 'sha256': sha(data)})
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.as_posix() == 'project.godot':
            data = without_editor_bridge(data.decode('utf-8')).encode('utf-8')
        target.write_bytes(data)
    preset = stage / 'export_presets.cfg'
    preset.write_text(preset.read_text(encoding='utf-8') + '\ncustom_template/release=' + json.dumps(template.as_posix()) + '\n', encoding='utf-8')
    site = output / 'site'
    site.mkdir()
    report = {'schema_version': 1, 'passed': False, 'scope': 'official export and file identity; browser and input not tested',
              'engine': version, 'editor_sha256': sha(args.godot.read_bytes()), 'template_sha256': TEMPLATE_SHA,
              'showcase_comparison_commit': subprocess.check_output(['git', '-C', str(args.showcase_repo), 'rev-parse', 'HEAD'], text=True).strip(),
              'threads': False, 'renderer': 'gl_compatibility', 'source_files': source_manifest,
              'omitted_source_assets': omitted_source_assets,
              'source_transformations': ['Omit editor plugin and debug autoload sections from the isolated export copy.',
                                         'Omit addons, tests and local adapter metadata from the exported candidate.']}
    if omitted_source_assets:
        report['source_transformations'].append('Omit only the unused historical assets/chest.glb and assets/guardian.glb before import; current interactive chest, generated characters and their textures are unchanged.')
    try:
        for name, flags in [('import', ['--editor', '--import', '--quit']),
                            ('export', ['--export-release', 'Web', str(site / 'index.html')])]:
            result = subprocess.run([str(args.godot), '--headless', '--path', str(stage), *flags],
                                    capture_output=True, text=True, timeout=300)
            log = result.stdout + result.stderr
            (output / (name + '.log')).write_text(log, encoding='utf-8')
            if result.returncode or re.search(r'SCRIPT ERROR|Parse Error|ERROR:', log):
                raise RuntimeError('Godot ' + name + ' failed; see its retained log')
        html_path = site / 'index.html'
        html = html_path.read_text(encoding='utf-8')
        match = re.search(r'const GODOT_CONFIG = (\{.*?\});', html)
        if not match:
            raise ValueError('Official Godot HTML configuration marker changed')
        config = json.loads(match[1])
        if config.get('extensionLibs') or config.get('threadPoolSize') not in (None, 0):
            raise ValueError('Unexpected extension or threaded runtime')
        config.update(ensureCrossOriginIsolationHeaders=False, emscriptenPoolSize=0, godotPoolSize=0)
        html_path.write_text(html[:match.start(1)] + json.dumps(config) + html[match.end(1):], encoding='utf-8')
        manifest = json.loads(subprocess.check_output(['git', '-C', str(args.showcase_repo), 'show', 'HEAD:play/manifest.json'], text=True))
        expected = {Path(item['path']).name: item for item in manifest['files'] if item['path'].startswith('play/runtime/godot-4.6.3.')}
        comparison = {}
        with zipfile.ZipFile(template) as archive:
            for name, shared_name in RUNTIME.items():
                data = (site / name).read_bytes()
                official = archive.read(shared_name.replace('godot-4.6.3.', 'godot.', 1))
                item = expected[shared_name]
                matches = data == official and sha(data) == item['sha256'] and len(data) == item['bytes']
                comparison[name] = {'shared_path': 'play/runtime/' + shared_name, 'bytes': len(data), 'sha256': sha(data), 'matches_official_and_showcase': matches}
                if not matches:
                    raise ValueError('Shared runtime differs: ' + name)
        report.update(passed=True, web_config=config, shared_runtime_comparison=comparison,
                      pck_bytes=(site / 'index.pck').stat().st_size,
                      pck_gzip_bytes=len(gzip.compress((site / 'index.pck').read_bytes(), mtime=0)),
                      files={file.relative_to(site).as_posix(): {'bytes': file.stat().st_size, 'sha256': sha(file.read_bytes())}
                             for file in sorted(site.rglob('*')) if file.is_file()})
    except Exception as error:
        report['blocker'] = str(error)
        raise
    finally:
        (output / 'export.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'output': str(output), 'pck_bytes': report['pck_bytes'], 'pck_gzip_bytes': report['pck_gzip_bytes'], 'shared_runtime_identical': True}))


if __name__ == '__main__':
    assert '[autoload]' not in without_editor_bridge('[application]\na=1\n[autoload]\nx=2\n[display]\ny=3\n')
    assert '[display]\ny=3\n' in without_editor_bridge('[application]\na=1\n[autoload]\nx=2\n[display]\ny=3\n')
    main()
