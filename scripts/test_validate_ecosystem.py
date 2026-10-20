#!/usr/bin/env python3
"""Synthetic boundary tests; fixtures never represent real host acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_site
import validate_ecosystem as gate

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.base = self.root / 'docs/showcase/fixture'; self.base.mkdir(parents=True)
        self.case = {'slug': 'fixture'}
        self.write('collection.json', {'cases': [self.case]})
        self.write('docs/showcase/fixture/manifest.json', {'files': [{'path': 'image.png'}]})
        self.output = self.write('docs/showcase/fixture/image.png', {'synthetic': 'not real image bytes'})
        request = self.write('docs/showcase/fixture/request.json', {'synthetic': 'never executed'})
        response = self.write('docs/showcase/fixture/response.json', {'synthetic': 'never executed'})
        measurement = self.write('docs/showcase/fixture/measurement.json', {'request_sha256': request['sha256'], 'response_sha256': response['sha256'], 'outputs': [self.output], 'status': 'succeeded'})
        self.record = {'schema': gate.SCHEMA, 'case_slug': 'fixture', 'phases': {p: {'status': 'not-applicable', 'reason': 'Synthetic fixture'} for p in gate.PHASES}, 'external_sources': [], 'stages': [{'id': 'fixture', 'phase': 'authoring', 'status': 'succeeded', 'route': 'ecosystem-cli', 'component': {'version': 'synthetic', 'source': 'https://github.com/dcc-mcp/example/commit/' + 'a'*40}, 'request': request, 'response': response, 'artifact_measurement': measurement, 'inputs': [], 'outputs': [self.output]}]}
        self.record['phases']['authoring'] = {'status': 'performed'}
        self.refresh()
    def write(self, path, value):
        target = self.root / path; target.write_text(json.dumps(value)); return {'path': path, 'sha256': gate.digest(target)}
    def refresh(self):
        graph = {key: self.record.get(key) for key in ('schema', 'case_slug', 'phases', 'stages', 'external_sources', 'downloads', 'reports', 'external_links')}
        graph['selected_outputs'] = [self.output]
        review = self.write('docs/showcase/fixture/review.json', {'production_graph_sha256': gate.canonical_hash(graph), 'raw_calls_verified': True, 'all_production_steps_covered': True, 'reviewer': 'synthetic test, not an actual reviewer', 'reviewed_at': '2026-10-20'})
        self.record['review'] = {'status': 'verified', 'evidence': review}
        self.write('docs/showcase/fixture/ecosystem-production.json', self.record)
        files = [{'path': f.name, 'sha256': gate.digest(f)} for f in self.base.iterdir() if f.name != 'manifest.json']
        self.write('docs/showcase/fixture/manifest.json', {'files': files})
    def test_complete_structural_fixture(self): self.assertEqual(gate.validate(self.root), [])
    def test_build_gate_preserves_existing_output(self):
        (self.base/'ecosystem-production.json').unlink()
        output = self.root/'_site'; output.mkdir(); (output/'keep.txt').write_text('keep')
        with patch('validate_collection.validate', return_value=[]):
            published, errors, _ = build_site.build(str(self.root), '_site')
        self.assertEqual(published, []); self.assertTrue(errors)
        self.assertEqual((output/'keep.txt').read_text(), 'keep')
    def test_pages_gate_runs_before_upload(self):
        workflow = (Path(__file__).resolve().parents[1]/'.github/workflows/pages.yml').read_text()
        self.assertLess(workflow.index('python scripts/validate_ecosystem.py'), workflow.index('actions/upload-pages-artifact'))
        self.assertNotIn('continue-on-error', workflow)
    def test_missing_record_blocks_legacy_too(self):
        (self.base/'ecosystem-production.json').unlink(); self.assertTrue(gate.validate(self.root))
    def test_each_native_route_blocks(self):
        for route in ('native-cli', 'bpy', 'direct-script', 'unknown', ''):
            self.record['stages'][0]['route'] = route; self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_official_cli_and_skill_are_not_blanket_banned(self):
        for route in gate.ROUTES:
            self.record['stages'][0]['route'] = route; self.refresh(); self.assertEqual(gate.validate(self.root), [])
    def test_tampered_output_blocks(self):
        (self.base/'image.png').write_text('changed'); self.assertTrue(gate.validate(self.root))
    def test_absent_phase_blocks(self):
        del self.record['phases']['export']; self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_unbound_output_blocks(self):
        self.write('docs/showcase/fixture/extra.glb', {})
        self.write('docs/showcase/fixture/manifest.json', {'files': [{'path':'image.png'}, {'path':'extra.glb'}]})
        self.assertTrue(gate.validate(self.root))
    def test_stale_review_blocks(self):
        self.record['stages'][0]['component']['version'] = 'changed'
        self.write('docs/showcase/fixture/ecosystem-production.json', self.record)
        self.assertTrue(gate.validate(self.root))
    def test_measurement_cannot_belong_to_other_call(self):
        self.record['stages'][0]['request'] = self.write('docs/showcase/fixture/other.json', {})
        self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_unpinned_or_unofficial_component_blocks(self):
        for source in ('https://github.com/dcc-mcp/foo/tree/main', 'https://github.com/other/foo/commit/' + 'a'*40):
            self.record['stages'][0]['component']['source'] = source; self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_official_pypi_release_is_a_valid_pin(self):
        # Published official release identity; the call/output fixture remains synthetic.
        self.record['stages'][0]['component'] = {'version': '0.2.22', 'source': 'https://pypi.org/project/dcc-mcp-blender/0.2.22/'}
        self.refresh(); self.assertEqual(gate.validate(self.root), [])
    def test_pypi_spoof_unpinned_and_version_mismatch_block(self):
        for source in ('https://pypi.org/project/dcc-mcp-impostor/0.2.22/',
                       'https://pypi.org/project/dcc-mcp-blender/0.2.21/',
                       'https://pypi.org/project/dcc-mcp-blender/',
                       'https://pypi.org.evil.test/project/dcc-mcp-blender/0.2.22/',
                       'https://pypi.org/project/dcc-mcp-blender/0.2.22/?override=1'):
            self.record['stages'][0]['component'] = {'version': '0.2.22', 'source': source}
            self.refresh(); self.assertTrue(gate.validate(self.root), source)
    def test_missing_raw_response_blocks(self):
        del self.record['stages'][0]['response']; self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_path_escape_blocks(self):
        self.record['stages'][0]['outputs'][0]['path'] = '../escape'; self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_self_cycle_blocks(self):
        self.record['stages'][0]['inputs'] = [self.output]; self.refresh()
        self.assertTrue(gate.validate(self.root))
    def test_local_resource_outside_manifest_blocks(self):
        self.write('docs/showcase/fixture/unbound.zip', {})
        self.case['resources'] = [{'url': 'docs/showcase/fixture/unbound.zip'}]
        self.write('collection.json', {'cases': [self.case]})
        self.assertTrue(gate.validate(self.root))
    def test_nested_step_poster_blocks(self):
        self.write('docs/showcase/fixture/unbound.png', {})
        self.case['steps'] = [{'image': {'poster': 'docs/showcase/fixture/unbound.png'}}]
        self.write('collection.json', {'cases': [self.case]})
        self.assertTrue(gate.validate(self.root))
    def test_other_play_directory_blocks(self):
        (self.root/'play/custom').mkdir(parents=True)
        self.write('play/custom/index.html', {})
        self.write('play/manifest.json', {'demos': [{'case_slug': 'fixture', 'url': 'play/custom/index.html'}], 'files': [{'path': 'play/custom/index.html'}]})
        self.assertTrue(gate.validate(self.root))
    def test_unpublished_evidence_blocks(self):
        self.write('docs/showcase/fixture/manifest.json', {'files': [{'path': 'image.png'}]})
        self.assertTrue(gate.validate(self.root))
    def test_source_and_producer_overlap_blocks(self):
        self.record['external_sources'] = [dict(self.output, origin='fixture', license='fixture')]
        self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_unknown_native_extension_blocks(self):
        self.write('docs/showcase/fixture/hidden.kra', {})
        self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_shared_play_asset_blocks(self):
        (self.root/'play/shared').mkdir(parents=True)
        self.write('play/shared/hidden.wasm', {})
        self.write('play/manifest.json', {'demos': [], 'files': [{'path': 'play/shared/hidden.wasm'}]})
        self.assertTrue(gate.validate(self.root))
    def test_materialized_download_is_bound(self):
        self.case['resources'] = [{'url': 'https://example.com/image.png'}]
        self.write('collection.json', {'cases': [self.case]})
        self.record['downloads'] = [{'url': 'https://example.com/image.png', 'local': self.output}]
        self.refresh(); self.assertEqual(gate.validate(self.root), [])
        self.record['downloads'][0]['local'] = dict(self.output, sha256='0'*64)
        self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_native_json_not_implicitly_exempt(self):
        self.write('docs/showcase/fixture/scene.json', {})
        self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_selected_binary_cannot_be_raw_evidence(self):
        self.record['stages'][0]['request'] = self.output
        self.refresh(); self.assertTrue(gate.validate(self.root))
    def test_external_download_does_not_depend_on_extension(self):
        for url in ('https://example.com/a.zip?download=1', 'https://example.com/a.kra', 'https://example.com/download'):
            self.case['resources'] = [{'url': url}]
            self.write('collection.json', {'cases': [self.case]})
            self.assertTrue(gate.validate(self.root))
    def test_external_reference_requires_explicit_reviewed_classification(self):
        url = 'https://example.com/docs'
        self.case['resources'] = [{'url': url}]
        self.write('collection.json', {'cases': [self.case]})
        self.record['external_links'] = [{'url': url, 'kind': 'reference', 'reason': 'Synthetic documentation link, not production bytes'}]
        self.refresh(); self.assertEqual(gate.validate(self.root), [])
    def test_unreviewed_is_not_accepted(self):
        self.record['review']['status'] = 'pending'; self.write('docs/showcase/fixture/ecosystem-production.json', self.record)
        self.assertTrue(gate.validate(self.root))

if __name__ == '__main__': unittest.main()
