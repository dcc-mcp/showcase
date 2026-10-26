"""Stage a hash-verified export for review; this does not certify input acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
CASE = 'hyper3d-relic-room'
sys.path.insert(0, str(ROOT / 'scripts/godot_web'))
from resource_budget import ADDITIONAL, LEGACY_GZIP, LEGACY_RAW, measure, validate

RUNTIME = {'index.js': 'godot-4.6.3.js', 'index.wasm': 'godot-4.6.3.wasm',
           'index.audio.worklet.js': 'godot-4.6.3.audio.worklet.js',
           'index.audio.position.worklet.js': 'godot-4.6.3.audio.position.worklet.js'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def without_unused_template_images(html):
    html = re.sub(r'(?m)^[ \t]*<link\b[^>]*href="index(?:\.icon|\.apple-touch-icon)\.png"[^>]*>\s*\n?', '', html)
    return re.sub(r'(?m)^[ \t]*<img\b[^>]*id="status-splash"[^>]*>\s*\n?', '', html)


def public_html(html, pack, pack_sha, shell_version):
    match = re.search(r'const GODOT_CONFIG = (\{.*?\});', html)
    if not match:
        raise ValueError('Missing official Godot export configuration')
    config = json.loads(match[1])
    if config.get('ensureCrossOriginIsolationHeaders') or config.get('emscriptenPoolSize') or config.get('godotPoolSize'):
        raise ValueError('Expected the single-thread export with no isolation headers')
    config['executable'] = '../runtime/godot-4.6.3'
    config['mainPack'] = pack
    config['showcasePackSha256'] = pack_sha
    config['canvasResizePolicy'] = 0
    config['fileSizes'] = {'../runtime/godot-4.6.3.wasm': config['fileSizes']['index.wasm'], pack: config['fileSizes']['index.pck']}
    html = html[:match.start(1)] + json.dumps(config) + html[match.end(1):]
    replacements = {
        '<script src="index.js"></script>': '<script src="../runtime/godot-4.6.3.js"></script>\n<script src="publication-shell.js?v=' + shell_version + '"></script>\n<script src="relic-shell.js?v=' + shell_version + '"></script>',
        'const engine = new Engine(GODOT_CONFIG);': 'const relicPublication = window.RelicCourierPublication.attach(GODOT_CONFIG);\nconst relicShell = window.RelicCourierShell.attach(GODOT_CONFIG, () => engine.requestQuit());\nconst engine = new Engine(GODOT_CONFIG);',
        'function displayFailureNotice(err) {': 'function displayFailureNotice(err) {\n relicPublication.failed();\n relicShell.failed(err);',
    }
    for before, after in replacements.items():
        if html.count(before) != 1:
            raise ValueError('Official shell marker changed: ' + before)
        html = html.replace(before, after)
    return without_unused_template_images(html), config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads((args.candidate / 'export.json').read_text(encoding='utf-8'))
    if report.get('passed') is not True or report.get('threads') is not False:
        raise ValueError('A successful single-thread export receipt is required')
    site = args.candidate / 'site'
    for path, record in report['files'].items():
        if Path(path).is_absolute() or '..' in Path(path).parts:
            raise ValueError('Unsafe export path')
        data = (site / path).read_bytes()
        if len(data) != record['bytes'] or digest(data) != record['sha256']:
            raise ValueError('Export bytes changed: ' + path)
    manifest = json.loads((ROOT / 'play/manifest.json').read_text(encoding='utf-8'))
    existing = {item['path']: item for item in manifest['files']}
    for name, shared in RUNTIME.items():
        expected = existing['play/runtime/' + shared]
        data = (site / name).read_bytes()
        if len(data) != expected['bytes'] or digest(data) != expected['sha256']:
            raise ValueError('Existing official runtime differs: ' + shared)
        destination = ROOT / 'play/runtime' / shared
        if not destination.exists():
            destination.write_bytes(data)
        if digest(destination.read_bytes()) != expected['sha256']:
            raise ValueError('Materialized shared runtime differs: ' + shared)
    destination = ROOT / 'play' / CASE
    destination.mkdir(parents=True, exist_ok=True)
    public = []

    def put(name, data):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        public.append(path)

    pack_sha = report['files']['index.pck']['sha256']
    pack = 'relic-' + pack_sha[:12] + '.pck'
    source = Path(__file__).parent
    shell_version = digest((source / 'web_shell.js').read_bytes() + (source / 'publication_shell.js').read_bytes())[:12]
    html, config = public_html((site / 'index.html').read_text(encoding='utf-8'), pack, pack_sha, shell_version)
    put('index.html', html.encode('utf-8'))
    put(pack, (site / 'index.pck').read_bytes())
    put('relic-shell.js', (source / 'web_shell.js').read_bytes())
    put('publication-shell.js', (source / 'publication_shell.js').read_bytes())
    for relative in ('ui/FONT-LICENSE.txt', 'ui/FONT-SOURCE.json', 'notices/KENNEY-MIT.txt', 'notices/ASSET-RIGHTS.md'):
        put(relative, (source / 'game' / relative).read_bytes())
    put('README.txt', ('Relic Courier / 遗迹信使\nGodot 4.6.3 single-thread WebGL 2 export.\n'
        'WASD/arrows move; Space dash; F/left click melee; Q unlocked Arc; E interact; I bag; Escape pause. Fight, loot, equip and return to town.\n'
        'The hinged chest provides one-time loot. Native language follows the page query and can be changed in the header. CC0 effects and native SFX mute are included; subjective listening is not run.\n'
        'Landscape 960 x 600 and above; portrait and physical-phone support are not claimed.\n'
        'Current runtime ba6b22f5: save-failure engine/filesystem regression 57 checks, separate read 5 and native integration 25 passed. Latest clean native extraction/import passed, but partial window occlusion blocked input before any game action or IO-fault fixture. This PCK has no actual browser run.\n'
        'Historical ec13ca4d native OS course/fresh reopen, 15-action HiDPI Web smoke on PCK 22f7d1c3, and 59.033333 s film decode/sampled frames passed on their retained exact bytes. These do not accept the current save correction. Full Web combat/loot/save-reopen/quit/fullscreen/restart, natural-speed film playback and subjective listening remain unverified. See dated case receipts for separate scopes.\n'
        'Hyper3D outputs remain subject to its terms; they are not MIT model assets. Font/code/runtime notices retain their rights.\n').encode('utf-8'))
    provenance = {'schema_version': 1, 'acceptance': 'pending', 'case_slug': CASE,
        'engine': report['engine'], 'threads': False, 'renderer': 'gl_compatibility',
        'template_sha256': report['template_sha256'], 'pck_sha256': pack_sha, 'pack_name': pack,
        'source_files': report['source_files'], 'source_transformations': report['source_transformations'],
        'omitted_source_assets': report.get('omitted_source_assets', []),
        'shared_runtime_comparison': report['shared_runtime_comparison'],
        'runtime_aggregate_sha256': 'ba6b22f5eee335c41717dfa8989113e7e40494fe5a60ce177a73c95aa701248f',
        'verified_scopes': ['Current save correction: 57 staged engine/actual filesystem checks, separate process read 5 and native integration 25',
                            'Current clean native extraction and fresh resource import; zero game inputs'],
        'historical_accepted_scopes': ['ec13ca4d runtime: native OS complete course and fresh normal-process reopen',
                            '22f7d1c3 PCK: 15-action actual HiDPI Web continue/movement/pause/SFX/language smoke',
                            'ec13ca4d scripted native course: editorial film full decode and sampled-frame review'],
        'not_claimed': ['Current native Menu/Continue/failure pixels: partial occlusion and foreground=false blocked before input; no IO-fault fixture',
                        'Current PCK actual browser run',
                        'Full Web combat/loot/save-reopen/quit/fullscreen/restart acceptance',
                        'Portrait or physical-phone support', 'Natural-speed film playback and subjective audio listening'],
        'web_config': config}
    put('export-provenance.json', (json.dumps(provenance, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    manifest['files'] = [item for item in manifest['files'] if not item['path'].startswith('play/' + CASE + '/')]
    manifest['files'].extend({'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path.read_bytes())} for path in public)
    manifest['demos'] = [item for item in manifest['demos'] if item['case_slug'] != CASE]
    manifest['demos'].append({'case_slug': CASE, 'url': 'play/' + CASE + '/index.html', 'title': 'Relic Courier / 遗迹信使',
        'engine': 'Godot 4.6.3', 'renderer': 'gl_compatibility', 'threads': False, 'localeSupport': ['en', 'zh'], 'nativeTextLanguage': 'en-zh',
        'controls': {'en': 'WASD/arrows move, Space dash, F/left click melee, Q unlocked Arc, E interact, I bag, Escape pause. Fight in the grove, recover/equip loot and return to town. Native EN/ZH changes language; Touch enables directional controls.',
                     'zh': 'WASD/方向键移动，空格冲刺，F/鼠标左键近战，Q 使用已解锁奥术，E 交互，I 背包，Esc 暂停。进入林地战斗，收取并装备战利品后返回城镇。原生 EN/中文切换语言，触控按钮启用方向操作。'},
        'notes': {'en': 'Current ba6b22f5 save correction passed 57 engine/filesystem checks, separate read 5 and native integration 25. Latest clean native import passed; partial window occlusion blocked before any game input or IO-fault fixture. This PCK has no actual browser run. Historical ec13 native course/reopen, 15-action Web smoke on PCK22f and film decode/sampled pixels remain separate exact-byte evidence. Full Web course/lifecycle and natural-speed playback/listening are unverified. Landscape 960 × 600 and above; portrait/physical phones are untested. Reset reloads the engine.',
                  'zh': '当前 ba6b22f5 存档修复通过 57 项引擎/文件系统、独立重读 5 项与场景集成 25 项检查。最新干净原生导入通过，但窗口局部遮挡在游戏输入和 IO 故障夹具前阻塞；此 PCK 尚未实际运行浏览器。历史 ec13 原生路线/重开、PCK22f 上 15 次 Web 冒烟与影片解码/抽样画面分别保留精确版本证据。完整 Web 玩法/生命周期、正常速度播放和听评未验。仅支持 960 × 600 及以上横屏，竖屏/实体手机未测；外层重开加载引擎。'}})
    groups = validate(measure(ROOT, [item['path'] for item in manifest['files']]))
    manifest['budget'] = {'raw_bytes': sum(value[0] for value in groups.values()),
        'gzip_equivalent_bytes': sum(value[1] for value in groups.values()),
        'raw_limit_bytes': LEGACY_RAW + sum(value[0] for value in ADDITIONAL.values()),
        'gzip_equivalent_limit_bytes': LEGACY_GZIP + sum(value[1] for value in ADDITIONAL.values()),
        'groups': {key: {'raw_bytes': value[0], 'gzip_equivalent_bytes': value[1]} for key, value in groups.items()},
        'measurement_scope': 'Manifest-listed assets excluding this self-describing document; browser transfer encoding is untested.'}
    write_json(ROOT / 'play/manifest.json', manifest)
    print(json.dumps({'case': CASE, 'pack': pack, 'acceptance': 'pending', 'budget': manifest['budget']}))


if __name__ == '__main__':
    main()
