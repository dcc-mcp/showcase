"""Read-only candidate source, wheel, installed bytes and input verification."""
import hashlib
import importlib.metadata
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path
from lifecycle import require, sha
from png_readback import decode_png, rgba_sha
PREP = Path(__file__).resolve().parent
ROOT = PREP.parent
PLUGIN_SHA = '8bcec953df8fa072ec26c24a0576803634d234d638a0f18f9a57ca6b8ae51065'


def no_symlinks(path):
    path = Path(path).absolute()
    for part in [path, *path.parents]:
        require(not part.is_symlink(), 'Symlink paths are not admitted')
    return path


def verify_installed_inventory(package, files):
    """Reject import shadowing, links and special nodes; verify allowed bytecode."""
    import marshal
    import types
    expected = {item['path'] for item in files}
    actual = set()
    caches = 0
    for entry in package.rglob('*'):
        require(not entry.is_symlink() and (entry.is_file() or entry.is_dir()), 'Installed package contains a symlink/special node')
        if entry.is_dir():
            continue
        relative = str(entry.relative_to(package))
        if '__pycache__' in entry.parts:
            require(entry.parent.name == '__pycache__' and entry.suffix == '.pyc', 'Unexpected installed cache entry')
            try:
                source = Path(importlib.util.source_from_cache(str(entry)))
            except ValueError as exc:
                raise RuntimeError('Unrecognized installed bytecode cache') from exc
            require(str(source.relative_to(package)) in expected and source.suffix == '.py', 'Cache has no bound source file')
            data = entry.read_bytes()
            require(16 <= len(data) <= 4*1024**2 and data[:4] == importlib.util.MAGIC_NUMBER, 'Unrecognized bytecode format')
            match = re.search(r'\.opt-([012])\.pyc$', entry.name)
            optimize = int(match.group(1)) if match else 0
            cached = marshal.loads(data[16:])
            require(isinstance(cached, types.CodeType) and cached == compile(source.read_bytes(), str(source), 'exec', dont_inherit=True, optimize=optimize), 'Installed bytecode differs from bound source')
            caches += 1
        else:
            actual.add(relative)
    require(actual == expected, 'Installed package inventory differs; possible import shadowing')
    return caches


def check_delivery():
    import jsonschema
    import yaml
    receipt_path = no_symlinks(ROOT / 'candidate-binding.json')
    require(receipt_path.is_file() and receipt_path.stat().st_size < 1024**2,
            'Candidate binding must be a bounded regular file')
    receipt = json.loads(receipt_path.read_text())
    require(receipt['base_commit'] == 'ea9270a82bd0821993f0c611d9cad2d36e06405d',
            'Wrong stacked base')
    require(receipt['base_tree'] == 'abfd40f62533cf652d767c00781605725c0ce98b',
            'Wrong stacked base tree')
    for row in receipt['source_files']:
        path = no_symlinks(ROOT / 'source' / row['path'])
        require(path.is_relative_to(ROOT / 'source') and path.is_file()
                and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                'Candidate source bytes differ')
    for row in receipt['input_files'] + receipt['recipe_files']:
        path = no_symlinks(ROOT / row['path'])
        require(path.is_relative_to(ROOT) and path.is_file()
                and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                'Native recipe or input bytes differ')
    versions = {n: importlib.metadata.version(n) for n in
                ['dcc-mcp-core','dcc-mcp-server','dcc-mcp-cli','dcc-mcp-gimp','mcp','httpx']}
    require(all(versions[n] == '0.20.41' for n in
                ('dcc-mcp-core','dcc-mcp-server','dcc-mcp-cli')), 'Wrong Core versions')
    require(versions['mcp'] == '1.30.0' and versions['dcc-mcp-gimp'] == '0.4.1'
            and versions['httpx'] == '0.28.1', 'Wrong SDK/adapter/HTTPX versions')
    spec = importlib.util.find_spec('dcc_mcp_gimp')
    require(spec is not None and spec.origin is not None, 'Adapter not installed')
    package = no_symlinks(Path(spec.origin).parent)
    require(package.is_relative_to(Path(sys.prefix)), 'Adapter import is outside isolated venv')
    wheel = no_symlinks(ROOT / receipt['wheel']['path'])
    require(wheel.is_file() and sha(wheel) == receipt['wheel']['sha256'], 'Wheel bytes differ')
    files = receipt['installed_files']
    with zipfile.ZipFile(wheel) as archive:
        expected_names = {'dcc_mcp_gimp/' + item['path'] for item in files}
        require({n for n in archive.namelist() if n.startswith('dcc_mcp_gimp/')}
                == expected_names, 'Wheel package inventory differs')
        for item in files:
            data = archive.read('dcc_mcp_gimp/' + item['path'])
            require(hashlib.sha256(data).hexdigest() == item['sha256']
                    and len(data) == item['bytes'], 'Wheel package file differs')
            installed = no_symlinks(package / item['path'])
            source = ROOT / 'source' / ('bridge/gimp-plugin/dcc_mcp_gimp.py'
                if item['path'] == 'gimp_plugin/dcc_mcp_gimp.py'
                else 'src/dcc_mcp_gimp/' + item['path'])
            require(sha(installed) == sha(source) == item['sha256'],
                    'Installed/source/wheel mismatch')
    caches = verify_installed_inventory(package, files)
    plugin = package / 'gimp_plugin/dcc_mcp_gimp.py'
    require(sha(plugin) == PLUGIN_SHA, 'Native plug-in identity differs')
    schemas = {t['name']: t['input_schema'] for t in
               yaml.safe_load((package/'skills/gimp-session/tools.yaml').read_text())['tools']}
    require(len(schemas) == 25 and 'export_preview' in schemas, 'Wrong candidate tool catalog')
    schema = schemas['export_preview']
    require(schema.get('additionalProperties') is False and set(schema['properties']) ==
            {'image_id','path','max_width','max_height','overwrite'}, 'Preview schema is not closed')
    jsonschema.validate({'image_id':1,'path':'preview.png','max_width':1600,'max_height':1600}, schema)
    baseline = json.loads((ROOT/'inputs/qualified-master-baseline.json').read_text())
    xcf = ROOT/'inputs/seismic-lens-master.xcf'; png = ROOT/'inputs/seismic-lens-master.png'
    require(sha(xcf) == baseline['xcf']['sha256'] ==
            '8efc1515de37d6e917d0b55bdfa24a8c9faae087f2cbe63b60d0f1aa1c7c09e5', 'XCF differs')
    require(sha(png) == baseline['png']['sha256'] ==
            '43962deba479131f476baaa7c33854292f5d36404420e0c5804c72fbad288594', 'PNG differs')
    pixels = decode_png(png)
    require(pixels[:2] == (2560,1600) and rgba_sha(pixels) == baseline['rgba_sha256'],
            'Master reference decoded RGBA differs')
    return {'versions':versions, 'package':str(package),'plugin':str(plugin),
            'source_commit':receipt['candidate_commit'],'source_tree':receipt['candidate_tree'],
            'matched_package_files':len(files), 'verified_bytecode_caches':caches,
            'package_integrity':{'binding_sha256':sha(receipt_path),
                                 'wheel_sha256':sha(wheel),'source_files':len(receipt['source_files'])},
            'native_launched':False}, baseline, pixels
