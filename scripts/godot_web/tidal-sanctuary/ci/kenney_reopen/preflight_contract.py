"""Host-free fail-closed checks for the candidate-only native inspection caller."""
import hashlib
import json
import re


def audit_baseline(data, expected_sha256):
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('Baseline SHA mismatch')
    text = data.decode('utf-8')
    if '[ext_resource' in text or 'ExtResource(' in text or 'instance=' in text:
        raise ValueError('Baseline has external or nested instance references')
    if re.search(r'^\s*script\s*=', text, re.M):
        raise ValueError('Baseline script would run before post-instantiation inspection')
    for line in text.splitlines():
        if line.startswith('[sub_resource '):
            match = re.search(r'type="([^"]+)"', line)
            if match is None or match[1] not in {'ArrayMesh', 'StandardMaterial3D'}:
                raise ValueError('Unsupported baseline resource class')
        elif line.startswith('[node '):
            match = re.search(r'type="([^"]+)"', line)
            if match is None or match[1] not in {'Node3D', 'MeshInstance3D'}:
                raise ValueError('Unsupported baseline node class')
    return {'sha256': expected_sha256, 'no_scripts_or_external_resources': True}


def validate_response(body, witness_bytes, plan):
    context = body.get('context', body) if isinstance(body, dict) else None
    if not isinstance(context, dict) or context.get('executed') is not True:
        raise ValueError('Official script did not execute')
    result = context.get('result')
    if (not isinstance(result, dict) or result.get('schema') != 1
            or type(result.get('inspected')) is not int or result['inspected'] != 4
            or result.get('converted') is not False or result.get('saved_native_asset') is not False):
        raise ValueError('Missing or invalid native preflight result, including assertion failure')
    if result.get('witness_path') != 'res://kenney-preflight/preflight-witness.json':
        raise ValueError('Unexpected witness path')
    if (not 0 < len(witness_bytes) <= 1024*1024
            or result.get('witness_bytes') != len(witness_bytes)
            or result.get('witness_sha256') != hashlib.sha256(witness_bytes).hexdigest()):
        raise ValueError('Witness byte count or SHA mismatch')
    witness = json.loads(witness_bytes)
    if (witness.get('schema') != 1 or len(witness.get('assets', [])) != 4
            or not 0 < witness.get('nodes', 0) <= 128
            or not 0 < witness.get('vertices', 0) <= 20000):
        raise ValueError('Incomplete or unbounded native witness')
    engine = witness.get('engine', {})
    if [engine.get(k) for k in ('major', 'minor', 'patch')] != [4, 6, 3]:
        raise ValueError('Unexpected native engine version')
    empty_scene = {'edited_scene_root': None, 'open_scenes': []}
    if witness.get('scene_before') != empty_scene or witness.get('scene_after') != empty_scene:
        raise ValueError('Owned empty editor scene signature changed or was not empty')
    expected = {(a['source_file'], a['output'], a['source_sha256'], a['baseline_sha256']) for a in plan['assets']}
    actual = set()
    for row in witness['assets']:
        if row.get('import_error') != 0 or not row.get('source_graph') or not row.get('baseline_graph'):
            raise ValueError('Native import or graph inspection incomplete')
        for graph_key in ('source_graph', 'baseline_graph'):
            meshes = [node for node in row[graph_key] if node.get('surfaces')]
            if not meshes:
                raise ValueError('Graph lacks actual mesh surface inspection')
            for node in meshes:
                if node.get('class') not in {'ImporterMeshInstance3D', 'MeshInstance3D'}:
                    raise ValueError('Unexpected inspected mesh class')
                for surface in node['surfaces']:
                    channels = surface.get('channels', [])
                    if (type(surface.get('vertex_count')) is not int or surface['vertex_count'] <= 0
                            or len(channels) != 13 or [c.get('channel') for c in channels] != list(range(13))
                            or any(not re.fullmatch('[0-9a-f]{64}', c.get('stored_variant_sha256', '')) for c in channels)):
                        raise ValueError('Incomplete mesh array witness')
        actual.add((row['source'], row['baseline'], row['source_sha256'], row['baseline_sha256']))
    if len(actual) != 4 or actual != expected:
        raise ValueError('Witness sources differ from fixed production inputs')
    return witness
