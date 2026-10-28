"""Prepare hash-pinned Hyper3D LFS data files; never execute downloaded bytes."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
PINS = {
    'scripts/godot_web/hyper3d-relic-room/game/assets/courier-character.glb':
        (11962060, '82a7b7456137eb133753650e2d9cda4f016ea810df68adcbfdc267f83ab29cd2'),
    'scripts/godot_web/hyper3d-relic-room/game/assets/guardian-character.glb':
        (17455464, '9735ae377cd9cccbfa3bbc75f53f12874158bc71a5b0fed3fc2f6ae4a6b14a60'),
    'docs/showcase/hyper3d-relic-room/showcase.mp4':
        (20157741, '134579f9e7995f038764b7a27989e6bd073eb62ec2b8d8b75054ceeba1059634'),
    'play/hyper3d-relic-room/relic-bc6af9db60ea.pck':
        (41192572, 'bc6af9db60ea88bb87c6c1adaaace410fb0fcdbb1a13f522b99b17fd73fae5ea'),
    'docs/showcase/hyper3d-relic-room/RelicCourier-native.zip':
        (44273997, '8822a8da38a23c2ab4194d82fa49b97c0d99d5b13533b7bc1164a24498b64b79'),
    'docs/showcase/godot-mage-vfx/demo.mp4':
        (12539585, 'db0bb94905f830799ed6e91d8e15f64ceb6c624f1d938d1ab15ab8d300ee27bd'),
    'docs/showcase/godot-mage-vfx/godot-mage-vfx.zip':
        (484267, 'a634b8061b5860ab75a2ea2626d60e5db1c7d1e957b68c5c9a5f0aa4c58f4dec'),
    'docs/showcase/godot-mage-vfx/hero.jpg':
        (172512, '103d44109dfbc327e00100f31fc8ff2293012157b7ef2d49271a2ca042de2cd7'),
    'docs/showcase/godot-mage-vfx/manual-images/godot-layered-contact.jpg':
        (113801, '9c94b2eaf577a88197a0cf1d2a454b2b8a80b6279348ddd58acc77d84e68334e'),
    'docs/showcase/godot-mage-vfx/manual-images/godot-layered-release.jpg':
        (141150, 'ffb1da9b39b350b4bc7ae6dbc2acf67f42c91d33603b9f205e0d74c2c8a4d0d8'),
    'docs/showcase/godot-mage-vfx/manual-images/godot-layered-sigil.jpg':
        (172512, '103d44109dfbc327e00100f31fc8ff2293012157b7ef2d49271a2ca042de2cd7'),
}
SHA = re.compile(r'[0-9a-fA-F]{40}\Z')
POINTER = re.compile(rb'version https://git-lfs.github.com/spec/v1\r?\n'
                     rb'oid sha256:([0-9a-f]{64})\r?\nsize ([1-9][0-9]*)\r?\n')
GITHUB_HOSTS = {'media.githubusercontent.com', 'raw.githubusercontent.com',
                'objects.githubusercontent.com', 'github.com'}


def target(root, relative):
    path = PurePosixPath(relative)
    if (path.is_absolute() or path.as_posix() != relative or '\\' in relative
            or ':' in relative or any(p in ('.', '..') for p in path.parts)):
        raise ValueError('Unsafe fixed asset path')
    dest = root / relative
    if not dest.resolve().is_relative_to(root.resolve()):
        raise ValueError('Asset path escapes checkout')
    for parent in (dest, *dest.parents):
        if parent.is_symlink():
            raise ValueError('Asset path contains a symlink')
        if parent == root:
            break
    return dest


def state(dest, size, digest):
    if not dest.exists():
        return 'missing'
    if not dest.is_file():
        raise ValueError('Asset destination is not a file')
    if dest.stat().st_size == size:
        with dest.open('rb') as stream:
            observed = hashlib.file_digest(stream, 'sha256').hexdigest()
        if observed == digest:
            return 'cached'
    if dest.stat().st_size <= 1024:
        match = POINTER.fullmatch(dest.read_bytes())
        if match and match[1].decode() == digest and int(match[2]) == size:
            return 'pointer'
    raise ValueError('Unexpected existing asset bytes; refusing replacement')


def immutable_ref(root):
    if (root / '.git').exists():
        ref = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                      text=True, timeout=10).strip()
    else:
        ref = os.environ.get('GITHUB_SHA', '')
        event = os.environ.get('GITHUB_EVENT_PATH')
        if event:
            with open(event, 'rb') as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError('CI event exceeds size limit')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('CI event must be an object')
            if 'pull_request' in data:
                head = data['pull_request'].get('head') if isinstance(data['pull_request'], dict) else None
                ref = head.get('sha') if isinstance(head, dict) else None
    if not isinstance(ref, str) or not SHA.fullmatch(ref):
        raise ValueError('An immutable full Git commit SHA is required')
    return ref.lower()


def github_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in GITHUB_HOSTS
            or parsed.port not in (None, 443) or parsed.username is not None
            or parsed.password is not None or parsed.fragment):
        raise ValueError('LFS response must stay on public GitHub HTTPS hosts')


class GithubRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        github_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(root, relative, size, digest, ref, opener):
    if PINS.get(relative) != (size, digest) or not SHA.fullmatch(ref):
        raise ValueError('Unknown asset pin or mutable Git ref')
    dest = target(root, relative)
    url = 'https://media.githubusercontent.com/media/dcc-mcp/showcase/' + ref + '/' + relative
    temporary = None
    deadline = time.monotonic() + 180
    try:
        with opener.open(url, timeout=60) as response:
            github_url(response.geturl())
            if response.status != 200:
                raise ValueError('Unexpected LFS HTTP status')
            length = response.headers.get('Content-Length')
            if length is not None and int(length) != size:
                raise ValueError('LFS Content-Length differs from pin')
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise ValueError('Unexpected LFS content encoding')
            target(root, relative)
            dest.parent.mkdir(parents=True, exist_ok=True)
            count, observed = 0, hashlib.sha256()
            with tempfile.NamedTemporaryFile(dir=dest.parent, prefix='.hyper3d-lfs-',
                                             delete=False) as stream:
                temporary = Path(stream.name)
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError('LFS transfer exceeded time limit')
                    chunk = response.read(min(1024 * 1024, size - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > size:
                        raise ValueError('LFS download exceeds pinned size')
                    observed.update(chunk)
                    stream.write(chunk)
            if count != size or observed.hexdigest() != digest:
                raise ValueError('LFS download size or SHA-256 mismatch')
        dest = target(root, relative)
        if state(dest, size, digest) != 'cached':
            os.chmod(temporary, 0o644)
            os.replace(temporary, dest)
            temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def materialize(root=ROOT):
    root = Path(root).absolute()
    pending = []
    for relative, (size, digest) in PINS.items():
        if state(target(root, relative), size, digest) != 'cached':
            pending.append((relative, size, digest))
    if pending:
        ref = immutable_ref(root)
        opener = urllib.request.build_opener(GithubRedirect())
        for relative, size, digest in pending:
            download(root, relative, size, digest, ref, opener)
    result = {'verified': len(PINS), 'fetched': len(pending)}
    print('Verified pinned Hyper3D LFS assets: ' + json.dumps(result))
    return result


if __name__ == '__main__':
    materialize()
