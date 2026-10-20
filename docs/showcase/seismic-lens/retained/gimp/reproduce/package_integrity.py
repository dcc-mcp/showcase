"""Read-only full package verification. Trust the release manifest hash out of band."""
import hashlib
import json
from pathlib import Path


def verify_package(root, expected_manifest_sha256=None):
    root = Path(root).absolute()
    manifest_path = root / 'package-manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RuntimeError('Missing regular package manifest')
    raw = manifest_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_manifest_sha256 is not None and digest != expected_manifest_sha256:
        raise RuntimeError('Package manifest hash mismatch')
    manifest = json.loads(raw)
    expected = set()
    for row in manifest['files']:
        rel = Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts or str(rel) in expected:
            raise RuntimeError('Unsafe/duplicate package path')
        expected.add(str(rel))
        path = root / rel
        if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file():
            raise RuntimeError('Missing regular package file: ' + str(rel))
        if path.stat().st_size != row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise RuntimeError('Package byte mismatch: ' + str(rel))
    actual = set()
    for entry in root.rglob('*'):
        if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
            raise RuntimeError('Symlink or special node in package: ' + str(entry.relative_to(root)))
        if entry.is_file():
            actual.add(str(entry.relative_to(root)))
    if actual != expected | {'package-manifest.json'}:
        raise RuntimeError('Package inventory mismatch')
    return {'manifest_sha256': digest, 'matched_files': len(expected), 'bytes': sum(r['bytes'] for r in manifest['files'])}
