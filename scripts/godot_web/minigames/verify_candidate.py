#!/usr/bin/env python3
"""Check that the review artifact includes every required playable dependency."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def verify_candidate(site):
    site = Path(site).resolve()
    game = site / 'play/signal-garden'
    page = (game / 'index.html').read_text()
    match = re.search(r'<script type="application/json" id="game-config">(.*?)</script>', page, re.S)
    if not match:
        raise ValueError('Missing game configuration')
    config = json.loads(match[1])['export']
    required = ['README.txt', 'export.json', 'play/signal-garden/FONT-LICENSE.txt',
                'play/runtime/LICENSE.txt', 'play/runtime/COPYRIGHT.txt']
    references = re.findall(r'(?:src|href)="([^"]+)"', page)
    # The gallery link is optional review navigation; only executable dependencies are required.
    references = [ref for ref in references if ref.endswith(('.js', '.css'))]
    executable = config['executable']
    references += [executable + suffix for suffix in
                   ['.js', '.wasm', '.audio.worklet.js', '.audio.position.worklet.js']]
    references += list(config['fileSizes'])
    for ref in references:
        path = (game / ref).resolve()
        if not path.is_relative_to(site):
            raise ValueError('Candidate dependency escapes its artifact: ' + ref)
        required.append(str(path.relative_to(site)))
    for name in required:
        path = site / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing candidate dependency: ' + name)
    for ref, expected in config['fileSizes'].items():
        if (game / ref).stat().st_size != expected:
            raise ValueError('Candidate dependency size mismatch: ' + ref)
    report = json.loads((site / 'export.json').read_text())
    if hashlib.sha256((game / 'game.pck').read_bytes()).hexdigest() != report['pack_sha256']:
        raise ValueError('Candidate pack hash mismatch')
    return sorted(set(required))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'verified_dependencies': verify_candidate(args.site)}, indent=2))
