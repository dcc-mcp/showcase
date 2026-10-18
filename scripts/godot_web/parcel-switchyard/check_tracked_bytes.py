"""Read-only comparison to Git objects, without invoking clean/smudge filters."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess


def verify(root: Path, ref='HEAD'):
    records = subprocess.check_output(['git', 'ls-tree', '-r', '-z', ref], cwd=root)
    checked = 0
    for record in records.split(b'\0'):
        if not record:
            continue
        metadata, name = record.split(b'\t', 1)
        mode, kind, expected = metadata.decode().split()
        path = root / os.fsdecode(name)
        if kind != 'blob' or mode not in {'100644', '100755', '120000'}:
            raise ValueError(f'Unsupported tracked entry: {path}')
        if mode == '120000':
            if not path.is_symlink():
                raise ValueError(f'Tracked symlink changed type: {path}')
            data = os.fsencode(os.readlink(path))
        else:
            if path.is_symlink() or not path.is_file():
                raise ValueError(f'Tracked file missing or changed type: {path}')
            if bool(path.stat().st_mode & 0o111) != (mode == '100755'):
                raise ValueError(f'Tracked executable mode changed: {path}')
            data = path.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if actual != expected:
            raise ValueError(f'Tracked bytes changed: {path}')
        checked += 1
    if not checked:
        raise ValueError('No tracked files checked')
    return checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    args = parser.parse_args()
    print(f'Exact raw Git bytes and modes match for {verify(Path.cwd(), args.ref)} tracked files.')
