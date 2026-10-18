#!/usr/bin/env python3
"""Fast provenance, file type and budget gates; real playability is a browser test."""
import gzip,hashlib,json,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import playable
cases=json.loads((ROOT/'collection.json').read_text())['cases']
_,assets=playable.read_and_validate(str(ROOT),cases)
provenance=json.loads((ROOT/'play/export-provenance.json').read_text())
assert provenance['engine']=='4.6.3.stable.official.7d41c59c4'
assert provenance['editor_sha256']=='f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3'
assert provenance['threads'] is False and provenance['pwa'] is False
for project in provenance['projects']:
    assert hashlib.sha256((ROOT/project['source_archive']).read_bytes()).hexdigest()==project['source_archive_sha256']
    for entry in project['project_files']:
        assert hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
for case in ['sonic-loom','prism-tide']:
    assert (ROOT/f'play/{case}/game.pck').read_bytes().startswith(b'GDPC')
    assert (ROOT/f'play/{case}/game.pck').stat().st_size < 32*1024
    config=json.loads(re.search(r'id="export-config" type="application/json">(.*?)<', (ROOT/f'play/{case}/index.html').read_text()).group(1))
    assert config['ensureCrossOriginIsolationHeaders'] is False
    assert config['emscriptenPoolSize']==0 and config['godotPoolSize']==0
wasm=ROOT/'play/runtime/godot-4.6.3.wasm'
assert wasm.read_bytes()[:4]==b'\0asm'
assert sum((ROOT/p).stat().st_size for p in assets)<=40*1024*1024
assert sum(len(gzip.compress((ROOT/p).read_bytes(),mtime=0)) for p in assets)<=11*1024*1024
assert not any('service.worker' in p for p in assets)
print('Source provenance, native PCK/WASM signatures, allowlist, hashes and budgets passed.')
