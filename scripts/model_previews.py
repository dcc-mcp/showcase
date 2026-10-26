"""Fail-closed GLB allowlist; does not promote historical assets or bypass production gates."""
import hashlib
import json
from pathlib import Path
import struct

MAX_BYTES = 8 * 1024 * 1024

def validate_glb(path):
    data = Path(path).read_bytes()
    if len(data) > MAX_BYTES or len(data) < 20:
        raise ValueError('model preview: GLB outside 20-byte to 8-MiB budget')
    magic, version, length = struct.unpack_from('<III', data)
    if (magic, version, length) != (0x46546c67, 2, len(data)):
        raise ValueError('model preview: invalid GLB header')
    size, kind = struct.unpack_from('<II', data, 12)
    if kind != 0x4e4f534a or 20 + size > len(data):
        raise ValueError('model preview: missing JSON chunk')
    doc = json.loads(data[20:20 + size])
    # No external resources/decoders: bounded single-file transfer, no third-party calls.
    allowed_extensions = {'KHR_materials_emissive_strength'}  # numeric material scalar; no network/decoder
    if (set(doc.get('extensionsUsed', [])) | set(doc.get('extensionsRequired', []))) - allowed_extensions:
        raise ValueError('model preview: extensions require separate review')
    for item in doc.get('buffers', []) + doc.get('images', []):
        if 'uri' in item:
            raise ValueError('model preview: GLB must embed every buffer and image')
    return data

def read_and_validate(root, cases):
    import build_site as site
    root = Path(root)
    data = json.loads((root / 'benchmark/model-previews.json').read_text())
    if set(data) != {'schema_version', 'previews'} or data['schema_version'] != 1 or not isinstance(data['previews'], list):
        raise ValueError('model preview: invalid allowlist')
    records, assets = {}, set()
    known = {c['slug']: c for c in cases}
    for entry in data['previews']:
        slug = entry['case_slug']
        if slug not in known or slug in records:
            raise ValueError('model preview: unknown or duplicate case')
        # PR #46 is intentionally required for activation, not reimplemented or weakened here.
        try:
            import validate_ecosystem
        except ImportError as exc:
            raise ValueError('model preview: ecosystem production gate must be present before activation') from exc
        errors = validate_ecosystem.validate_case(root, known[slug])
        if errors:
            raise ValueError('model preview: case ecosystem gate failed: ' + '; '.join(errors))
        path = entry['src']
        if not path.endswith('.glb'):
            raise ValueError('model preview: only GLB is supported')
        content = validate_glb(site.resolve_public(str(root), path))
        if entry['bytes'] != len(content) or entry['sha256'] != hashlib.sha256(content).hexdigest():
            raise ValueError('model preview: bytes or SHA-256 mismatch')
        manifest = json.loads((root / ('docs/showcase/' + slug + '/manifest.json')).read_text())
        matches = [f for f in manifest['files'] if 'docs/showcase/' + slug + '/' + f['path'] == path]
        if len(matches) != 1 or any(matches[0][k] != entry[k] for k in ('bytes', 'sha256')):
            raise ValueError('model preview: asset must be bound to the selected case inventory')
        license_path = entry['license_path']
        site.resolve_public(str(root), license_path)
        if not entry.get('display_permission') or not entry.get('alt'):
            raise ValueError('model preview: explicit scoped display permission and alt text required')
        records[slug] = entry
        assets.update({path, license_path})
    if records:
        assets.update({'assets/model-preview.js', 'assets/model-preview.css',
                       'assets/vendor/model-viewer/model-viewer.min.js', 'assets/vendor/model-viewer/LICENSE',
                       'assets/vendor/model-viewer/VENDOR.json'})
    return records, assets

def section(entry):
    from build_site import esc
    actions = [('left', '向左'), ('right', '向右'), ('up', '向上'), ('down', '向下'),
               ('in', '放大'), ('out', '缩小'), ('reset', '重置视角')]
    controls = ''.join('<button type="button" data-model-action="%s">%s</button>' % (key, label) for key, label in actions)
    return '''<section class="detail-section model-preview" id="model-preview" data-model-preview data-model-src="../../%s" data-model-alt="%s">
<h2>交互模型预览</h2><p>模型仅在点击后加载。预览不等同于原生工程验收；材质和灯光可能与渲染图不同。</p>
<p><button type="button" data-model-start>加载模型</button><button type="button" data-model-stop hidden>关闭模型</button> · %.2f MiB</p>
<div data-model-mount hidden></div><div data-model-controls hidden>%s</div><p role="status" aria-live="polite">模型仅在点击后加载。</p>
<p><a href="../../%s">GLB 源文件</a> · <a href="../../%s">资产许可</a></p></section>''' % (esc(entry['src']), esc(entry['alt']), entry['bytes'] / 1048576, controls, esc(entry['src']), esc(entry['license_path']))
