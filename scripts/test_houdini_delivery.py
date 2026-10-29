"""Regress actual public representations against retained native execution receipts."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
import validate_ecosystem as gate

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/showcase/houdini-procedural-study'


def verify_execution_mapping(record):
    stages = {s['id']: s for s in record['stages']}
    render = stages['new-blender-cross-dcc-lighting']
    denoise = stages['official-cli-independent-oidn']
    relation = render['delivery_representations'][0]
    execution = denoise['execution_inputs'][0]
    assert render['native_outputs'][0]['sha256'] == relation['native_sha256']
    assert execution['sha256'] == relation['native_sha256']
    assert execution['public_representation'] == relation['public_artifact']
    assert execution['relationship'] == relation
    assert render['outputs'] == denoise['inputs'] == [relation['public_artifact']]
    assert relation['native_sha256'] != relation['public_artifact']['sha256']
    for field in ('public_artifact', 'metadata_evidence', 'decoded_equality_evidence'):
        gate.ref(ROOT, relation[field])
    metadata = json.loads((ROOT/relation['metadata_evidence']['path']).read_text())['records'][0]['record']
    decoded = json.loads((ROOT/relation['decoded_equality_evidence']['path']).read_text())['records'][0]['record']
    assert metadata['original_sha256'] == relation['native_sha256']
    assert metadata['public_sha256'] == relation['public_artifact']['sha256']
    assert metadata['all_bytes_outside_attribute_identical'] is True
    assert decoded['passed'] is True
    assert decoded['results'][0]['file_sha256'] == relation['native_sha256']
    assert decoded['results'][1]['file_sha256'] == relation['public_artifact']['sha256']
    assert decoded['results'][0]['channels'] == decoded['results'][1]['channels']
    assert len(decoded['results'][0]['channels']) == 11
    response = json.loads((ROOT/denoise['response']['path']).read_text())['records'][0]['record']
    assert response['source_sha256'] == execution['sha256']
    assert response['source_unchanged'] is True and response['success'] is True
    assert response['output_sha256'] == denoise['outputs'][0]['sha256']
    for stage in (render, denoise):
        measurement = json.loads((ROOT/stage['artifact_measurement']['path']).read_text())
        for field in ('native_outputs', 'delivery_representations', 'execution_inputs'):
            if field in stage:
                assert measurement[field] == stage[field]


class ActualHoudiniDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((BASE/'ecosystem-production.json').read_text())

    def test_actual_native_and_public_hashes_are_distinct_and_bound(self):
        verify_execution_mapping(self.record)

    def test_public_copy_cannot_masquerade_as_executed_input(self):
        changed = copy.deepcopy(self.record)
        stage = next(s for s in changed['stages'] if s['id']=='official-cli-independent-oidn')
        stage['execution_inputs'][0]['sha256'] = stage['inputs'][0]['sha256']
        with self.assertRaises(AssertionError):
            verify_execution_mapping(changed)

    def test_actual_zip_members_and_current_download_match(self):
        produced = {o['path']:o['sha256'] for s in self.record['stages'] for o in s['outputs']}
        sources = {s['path'] for s in self.record['external_sources']}
        gate.delivery_packages(ROOT, self.record['delivery_packages'], produced, sources)
        package = self.record['delivery_packages'][0]
        download = json.loads((BASE/'downloads.json').read_text())['package']
        assert download['sha256'] == package['archive']['sha256']
        assert download['archive_member_count'] == len(package['members'])
        assert download['download_url'] == package['archive']['path']
        members = {m['member']:m for m in package['members']}
        for name in ('hero.jpg','preview.jpg','lighting-study.jpg'):
            assert members[name]['source']['sha256'] == hashlib.sha256((BASE/name).read_bytes()).hexdigest()


if __name__ == '__main__':
    unittest.main()
