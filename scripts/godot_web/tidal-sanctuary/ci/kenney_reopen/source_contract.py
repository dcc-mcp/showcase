"""Validate a fixed source archive before native production; never converts assets."""
import hashlib
import zipfile
from pathlib import Path, PurePosixPath


def read_sources(path, plan):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != plan['archive_sha256']:
        raise ValueError('Source archive SHA mismatch')
    result = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        for item in members:
            name = PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in item.filename:
                raise ValueError('Unsafe source archive path')
        for expected in plan['assets']:
            candidates = [item for item in members if not item.is_dir()
                          and PurePosixPath(item.filename).name == expected['source_file']]
            if len(candidates) != 1:
                raise ValueError('Source filename missing or ambiguous')
            item = candidates[0]
            if item.file_size != expected['source_bytes']:
                raise ValueError('Source byte count mismatch')
            # A matching stored size bounds the selected member read; ZipFile
            # checks CRC too. No archive entry is extracted to a filesystem path.
            data = archive.read(item)
            if hashlib.sha256(data).hexdigest() != expected['source_sha256']:
                raise ValueError('Source GLB SHA mismatch')
            result[expected['output']] = {'archive_member': item.filename,
                                         'source_sha256': expected['source_sha256'], 'bytes': data}
    if len(result) != len(plan['assets']):
        raise ValueError('Duplicate output plan')
    return result
