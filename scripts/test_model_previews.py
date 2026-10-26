"""Site-only tests. Temporary meshes are test fixtures, never production evidence."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import benchmark_records
import model_previews

ROOT = Path(__file__).resolve().parents[1]

def fixture_glb():
    vertices = struct.pack('<9f', -1, -1, 0, 1, -1, 0, 0, 1, 0)
    doc = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
           'nodes': [{'mesh': 0}], 'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'material': 0}]}],
           'materials': [{'doubleSided': True, 'pbrMetallicRoughness': {'baseColorFactor': [0.8, 0.3, 0.1, 1]}}],
           'buffers': [{'byteLength': len(vertices)}], 'bufferViews': [{'buffer': 0, 'byteLength': len(vertices)}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [-1, -1, 0], 'max': [1, 1, 0]}]}
    text = json.dumps(doc).encode(); text += b' ' * (-len(text) % 4)
    return struct.pack('<III', 0x46546c67, 2, 28 + len(text) + len(vertices)) + struct.pack('<II', len(text), 0x4e4f534a) + text + struct.pack('<II', len(vertices), 0x004e4942) + vertices

class PreviewTests(unittest.TestCase):
    def test_no_production_assets_activated(self):
        records, assets = model_previews.read_and_validate(ROOT, [])
        self.assertEqual(records, {}); self.assertEqual(assets, set())
    def test_run_publication_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'benchmark').mkdir()
            (root / 'benchmark/runs.json').write_text('{"schema_version":1,"runs":[{}]}')
            with self.assertRaisesRegex(ValueError, 'awaits protocol'):
                benchmark_records.read_runs(root, [])
    def test_unknown_not_zero(self):
        cases = json.loads((ROOT / 'collection.json').read_text())['cases']
        index = json.loads(benchmark_records.generate(ROOT, cases)['benchmark/index.json'])
        self.assertFalse(index['benchmark_accepted']); self.assertEqual(index['runs'], [])
        self.assertTrue(all(t['protocol_id'] is None and not t['runs'] for t in index['tasks']))
        self.assertNotIn('score', json.dumps(index))
    def test_glb_budgets_and_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fixture.glb'; path.write_bytes(fixture_glb())
            self.assertEqual(model_previews.validate_glb(path), fixture_glb())
            path.write_bytes(b'x' * (model_previews.MAX_BYTES + 1))
            with self.assertRaisesRegex(ValueError, 'budget'): model_previews.validate_glb(path)
            path.write_bytes(b'not a GLB document at all')
            with self.assertRaisesRegex(ValueError, 'header'): model_previews.validate_glb(path)
    def test_external_uri_and_extension_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fixture.glb'
            for doc in ({'buffers': [{'uri': 'https://example.com/private'}]}, {'extensionsUsed': ['KHR_draco_mesh_compression']}):
                data = json.dumps(doc).encode(); data += b' ' * (-len(data) % 4)
                path.write_bytes(struct.pack('<IIIII', 0x46546c67, 2, 20 + len(data), len(data), 0x4e4f534a) + data)
                with self.assertRaises(ValueError): model_previews.validate_glb(path)
    def test_control_copy_and_no_autoplay(self):
        text = model_previews.section({'src': 'fixture.glb', 'alt': 'Test', 'bytes': 100, 'license_path': 'LICENSE'})
        self.assertIn('data-model-start', text); self.assertIn('data-model-action="reset"', text)
        self.assertNotIn('autoplay', text)
    def test_schema_is_valid(self):
        schema = json.loads((ROOT / 'benchmark/run.schema.json').read_text())
        self.assertEqual(set(schema['required']), set(schema['properties']))
        self.assertFalse(schema['additionalProperties'])

if __name__ == '__main__': unittest.main()
