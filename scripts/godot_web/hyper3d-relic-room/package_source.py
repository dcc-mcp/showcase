"""Package only the clean editable native project and verify its ZIP inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def selected(relative):
    return (not any(part.startswith('.') or part == '__pycache__' for part in relative.parts)
            and relative.suffix != '.import'
            and not (relative.parts[0] == 'assets' and relative.suffix == '.png')
            and relative.as_posix() != 'tests/layout-results.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).parent / 'game'
    output = args.output.resolve()
    if output == project or project in output.parents:
        raise ValueError('Package outside the editable project')
    output.mkdir(parents=True, exist_ok=False)
    archive = output / 'RelicCourier-native.zip'
    records = []
    with zipfile.ZipFile(archive, mode='x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for file in sorted(project.rglob('*')):
            relative = file.relative_to(project)
            if not file.is_file() or not selected(relative):
                continue
            if file.is_symlink():
                raise ValueError('Source packages cannot contain symlinks')
            data = file.read_bytes()
            name = 'RelicCourier/' + relative.as_posix()
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, data, compresslevel=9)
            records.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None or len(package.namelist()) != len(records):
            raise ValueError('Source archive failed ZIP integrity or inventory')
        for record in records:
            data = package.read(record['path'])
            if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
                raise ValueError('Source ZIP bytes differ: ' + record['path'])
        if b'[autoload]' in package.read('RelicCourier/project.godot'):
            raise ValueError('Public project must not ship its inspection/debug autoload')
    report = {'schema_version': 1, 'archive': archive.name, 'bytes': archive.stat().st_size,
              'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'file_count': len(records),
              'integrity': 'passed', 'files': records,
              'excluded': ['editor caches', 'adapter and debugger', 'logs', 'original provider downloads', 'extracted texture sidecars'],
              'acceptance': 'Packaging only; native and Web input are separate gates.'}
    (output / 'native-package.public.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('archive', 'bytes', 'sha256', 'file_count', 'integrity')}))


if __name__ == '__main__':
    assert not selected(Path('.godot/imported/test.ctex'))
    assert not selected(Path('tests/__pycache__/test.pyc'))
    assert not selected(Path('assets/chest_texture_diffuse.png'))
    assert selected(Path('assets/chest.glb')) and selected(Path('scripts/main.gd.uid'))
    main()
