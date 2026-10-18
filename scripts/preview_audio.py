"""Optional, hash-bound audio-stream facts. Unknown never means silent."""
import hashlib
import json
from pathlib import Path


def read(root):
    import build_site as site
    catalog = Path(root) / 'assets/preview-audio.json'
    if not catalog.exists():
        return {}
    data = json.loads(catalog.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('files'), list):
        raise ValueError('invalid preview audio catalog')
    result = {}
    for item in data['files']:
        source = site.resolve_public(root, item['src'])
        with open(source, 'rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        if digest != item['sha256'] or item['src'] in result:
            raise ValueError('stale or duplicate preview audio evidence: ' + item['src'])
        value = item.get('has_audio')
        if value is not None and type(value) is not bool:
            raise ValueError('audio presence must be true, false or unknown')
        result[item['src']] = 'true' if value is True else 'false' if value is False else 'unknown'
    return result
