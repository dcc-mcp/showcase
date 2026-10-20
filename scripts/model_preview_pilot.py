#!/usr/bin/env python3
"""Generate a LOCAL ONLY viewer harness. Never a publication or gate bypass.

Requires an explicitly selected, hash-verified asset and scoped license file.
No fixture or pilot output is copied into the public site by build_site.py.
"""
import argparse
import hashlib
import html
from pathlib import Path
import shutil
import model_previews


def generate(asset, sha256, license_path, out):
    root = Path(__file__).resolve().parents[1]
    out = Path(out).resolve()
    # A dedicated ignored directory, never the public build or selected case tree.
    if out != root / '_model-preview-pilot':
        raise ValueError('local pilot output must be _model-preview-pilot in this checkout')
    content = model_previews.validate_glb(asset)
    if hashlib.sha256(content).hexdigest() != sha256:
        raise ValueError('pilot asset hash mismatch')
    license_text = Path(license_path).read_text()
    out.mkdir(exist_ok=True)
    for rel in ('assets/model-preview.js', 'assets/model-preview.css',
                'assets/vendor/model-viewer/model-viewer.min.js', 'assets/vendor/model-viewer/LICENSE'):
        target = out / rel; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(root / rel, target)
    (out / 'asset.glb').write_bytes(content)
    (out / 'LICENSE.txt').write_text(license_text)
    entry = {'src': 'asset.glb', 'alt': 'Development-only model preview', 'bytes': len(content), 'license_path': 'LICENSE.txt'}
    section = model_previews.section(entry).replace('../../', '')
    for lang in ('en', 'zh'):
        markup = '<!doctype html><html lang="' + lang + '"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta name="robots" content="noindex,nofollow"><title>Local viewer pilot</title><link rel="stylesheet" href="assets/model-preview.css"><script src="assets/model-preview.js" defer></script><body><main><h1>Development-only viewer pilot</h1><p>Not a published showcase or accepted benchmark. Viewer testing does not establish full case ecosystem acceptance.</p>' + section + '</main></body></html>'
        if lang == 'en':
            import json
            translations = json.loads((root / 'locales/en/ui.json').read_text())
            for source in sorted(translations, key=len, reverse=True):
                markup = markup.replace(source, translations[source])
        (out / (lang + '.html')).write_text(markup)
    return out

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset', required=True); parser.add_argument('--sha256', required=True)
    parser.add_argument('--license', required=True); parser.add_argument('--out', default='_model-preview-pilot')
    args = parser.parse_args()
    print(generate(args.asset, args.sha256, args.license, args.out))
