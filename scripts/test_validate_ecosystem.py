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
        graph = gate.review_graph_fields(self.record)
        graph['selected_outputs'] = sorted([o for s in self.record['stages'] for o in s['outputs']] + [c['artifact'] for c in self.record.get('verification_captures', [])], key=lambda r:r['path'])
        review = self.write('docs/showcase/fixture/review.json', {'production_graph_sha256': gate.canonical_hash(graph), 'raw_calls_verified': True, 'all_production_steps_covered': True, 'verification_captures_verified': True, 'reviewer': 'synthetic test, not an actual reviewer', 'reviewed_at': '2026-10-20'})
        self.record['review'] = {'status': 'verified', 'evidence': review}
        self.write('docs/showcase/fixture/ecosystem-production.json', self.record)
        files = [{'path': f.name, 'sha256': gate.digest(f)} for f in self.base.iterdir() if f.name != 'manifest.json']
        self.write('docs/showcase/fixture/manifest.json', {'files': files})
    def add_capture(self):
        artifact=self.write('docs/showcase/fixture/observation.mp4', {'synthetic':'not actual video or acceptance'})
        evidence=self.write('docs/showcase/fixture/capture-evidence.json', {'synthetic':'never executed native observation'})
        decode=self.write('docs/showcase/fixture/capture-decode.json', {'artifact':artifact,'full_decode':True,'decoded_frames':120})
        capture={'artifact':artifact,'source_artifacts':[self.output], 'kind':'continuous-native-window-observation','route':'Synthetic window capture fixture, not actual execution','constraints':{'task_owned_window':True,'continuous':True,'cuts':False,'retiming':False,'compositing':False,'synthetic_ui':False},'native_actions_evidence':evidence,'capture_evidence':evidence,'decode_evidence':decode}
        self.record['verification_captures']=[capture];self.refresh();return capture
    def test_reviewed_observation_is_not_fake_production(self):
        self.add_capture();self.assertEqual(gate.validate(self.root),[])
    def test_capture_cannot_be_edited_media_or_artwork(self):
        capture=self.add_capture()
        for field,value in [('cuts',True),('retiming',True),('compositing',True),('synthetic_ui',True),('continuous',False),('task_owned_window',False)]:
            original=capture['constraints'][field];capture['constraints'][field]=value;self.refresh()
            with self.subTest(field=field):self.assertTrue(gate.validate(self.root))
            capture['constraints'][field]=original
        capture['artifact']=self.output;self.refresh();self.assertTrue(gate.validate(self.root))
    def test_capture_requires_independent_review_not_only_claims(self):
        self.add_capture()
        review_path=self.record['review']['evidence']['path'];review=json.loads((self.root/review_path).read_text())
        review['verification_captures_verified']=False
        self.record['review']['evidence']=self.write(review_path,review)
        self.write('docs/showcase/fixture/ecosystem-production.json',self.record)
        self.assertIn('continuous native-window observation needs independent capture review',gate.validate_case(self.root,self.case))
    def test_capture_binds_decode_and_source_provenance(self):
        capture=self.add_capture();capture['source_artifacts']=[];self.refresh();self.assertTrue(gate.validate(self.root))
        capture['source_artifacts']=[self.output]
        capture['decode_evidence']=self.write('docs/showcase/fixture/capture-decode.json',{'artifact':self.output,'full_decode':True,'decoded_frames':120})
        self.refresh();self.assertTrue(gate.validate(self.root))
    def test_capture_is_review_graph_bound_without_changing_legacy_hashes(self):
        before=gate.review_graph_fields(self.record);self.assertNotIn('verification_captures',before)
        self.add_capture();after=gate.review_graph_fields(self.record)
        self.assertNotEqual(gate.canonical_hash(before),gate.canonical_hash(after))

    def add_capture_poster(self):
        capture=self.add_capture()
        output=self.write('docs/showcase/fixture/poster.png',{'synthetic':'native poster fixture, not executed'})
        stage=dict(self.record['stages'][0]);stage.update(id='poster',phase='export',inputs=[capture['artifact']],outputs=[output])
        stage['artifact_measurement']=self.write('docs/showcase/fixture/poster-measurement.json',{'request_sha256':stage['request']['sha256'],'response_sha256':stage['response']['sha256'],'outputs':[output],'status':'succeeded'})
        self.record['stages'].append(stage);self.record['phases']['export']={'status':'performed'};self.refresh()
        return capture,stage
    def test_native_poster_can_consume_verified_capture(self):
        self.add_capture_poster();self.assertEqual(gate.validate(self.root),[])
    def test_capture_poster_cycle_is_rejected(self):
        capture,poster=self.add_capture_poster();capture['source_artifacts']=poster['outputs'];self.refresh()
        self.assertTrue(any('capture source must precede' in x for x in gate.validate(self.root)))
    def test_capture_cannot_hide_forward_source_dependency(self):
        self.add_capture_poster();self.record['stages'].reverse();self.refresh()
        self.assertTrue(any('capture source must precede' in x for x in gate.validate(self.root)))

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
    def test_pages_materializes_pinned_runtime_before_provenance(self):
        workflow = (Path(__file__).resolve().parents[1]/'.github/workflows/pages.yml').read_text()
        self.assertLess(workflow.index('python scripts/godot_web/materialize_runtime.py'), workflow.index('python scripts/validate_ecosystem.py'))
        self.assertLess(workflow.index('python scripts/validate_ecosystem.py'), workflow.index('python scripts/build_site.py'))
    def test_repeated_slash_rejected_as_same_file_alias(self):
        alias = {**self.output, 'path': self.output['path'].replace('/fixture/', '//fixture/')}
        with self.assertRaises(ValueError): gate.ref(self.root, alias)
    def test_alias_cannot_hide_self_input_as_external_source(self):
        alias = {**self.output, 'path': self.output['path'].replace('/fixture/', '//fixture/')}
        self.record['external_sources'] = [{**alias, 'origin': 'synthetic adversarial alias', 'license': 'synthetic'}]
        self.record['stages'][0]['inputs'] = [alias]
        self.refresh(); self.assertTrue(gate.validate(self.root))
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

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        import zipfile
        self.zipfile = zipfile
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'image.png').write_bytes(b'synthetic production fixture, not a real image')
        (self.root/'README.md').write_text('Only reproducibility documentation')
        self.image = {'path':'image.png', 'sha256':gate.digest(self.root/'image.png')}
        self.doc = {'path':'README.md', 'sha256':gate.digest(self.root/'README.md')}
    def package(self, members=None, entries=None):
        members = members if members is not None else [{'member':'assets/image.png','source':self.image,'kind':'production'}]
        entries = entries if entries is not None else [('assets/image.png',(self.root/'image.png').read_bytes())]
        with self.zipfile.ZipFile(self.root/'delivery.zip','w') as z:
            for name,data in entries:z.writestr(name,data)
        return [{'archive':{'path':'delivery.zip','sha256':gate.digest(self.root/'delivery.zip')},'members':members}]
    def test_byte_preserving_delivery_needs_no_fake_mcp_zip_call(self):
        self.assertEqual(gate.delivery_packages(self.root,self.package(),{'image.png':'hash'},set()),{'delivery.zip'})
    def test_native_download_budget_requires_exact_package_and_producer(self):
        base = self.root / 'docs/showcase/fixture'
        base.mkdir(parents=True)
        path = base / 'ecosystem-production.json'
        record = {'stages': [{'outputs': [self.image]}], 'delivery_packages': self.package()}
        path.write_text(json.dumps(record))
        self.assertEqual(gate.native_download_paths(self.root, {'slug': 'fixture'}), {'image.png'})
        record['downloads'] = [{'url': 'https://example.com/image.png', 'local': self.image}]
        path.write_text(json.dumps(record))
        cases = [{'slug': 'fixture'}, {'slug': 'other', 'cover': {'src': 'https://example.com/image.png'}}]
        self.assertEqual(gate.native_download_paths(self.root, cases[0], cases), set())
        record['stages'] = []
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            gate.native_download_paths(self.root, {'slug': 'fixture'})
        record['stages'] = [{'outputs': [self.image]}]
        path.write_text(json.dumps(record))
        (self.root / 'image.png').write_bytes(b'altered')
        with self.assertRaises(ValueError):
            gate.native_download_paths(self.root, {'slug': 'fixture'})
    def test_missing_production_lineage_blocks(self):
        with self.assertRaises(ValueError):gate.delivery_packages(self.root,self.package(),{},set())
    def test_known_artwork_cannot_be_documentation(self):
        members=[{'member':'image.png','source':self.image,'kind':'support','reason':'attempted escape'}]
        with self.assertRaises(ValueError):gate.delivery_packages(self.root,self.package(members,[('image.png',b'x')]),{},set())
    def test_missing_extra_duplicate_and_altered_member_block(self):
        for entries in [[],[('assets/image.png',b'changed')],[('other.png',b'x')],[('assets/image.png',b'x'),('assets/image.png',b'x')]]:
            with self.subTest(entries=entries),self.assertRaises(ValueError):
                gate.delivery_packages(self.root,self.package(entries=entries),{'image.png':'hash'},set())
    def test_unsafe_member_paths_block(self):
        for name in ('../image.png','/image.png','x//image.png','x/./image.png','x\\image.png'):
            members=[{'member':name,'source':self.image,'kind':'production'}]
            with self.subTest(name=name),self.assertRaises(ValueError):
                gate.delivery_packages(self.root,self.package(members,[(name,b'x')]),{'image.png':'hash'},set())
    def test_explicit_documentation_is_not_claimed_executed(self):
        members=[{'member':'README.md','source':self.doc,'kind':'support','reason':'Reproducibility instructions only; not executed'}]
        package=self.package(members,[('README.md',(self.root/'README.md').read_bytes())])
        self.assertEqual(gate.delivery_packages(self.root,package,{},set()),{'delivery.zip'})

    def test_powershell_reproduction_is_support_not_production(self):
        data=b"param([string]$InstanceId)\n# Reproduction source, not executed by this test.\n"
        path=self.root/'replay.ps1';path.write_bytes(data)
        source={'path':'replay.ps1','sha256':gate.digest(path)}
        members=[{'member':'replay.ps1','source':source,'kind':'support','reason':'Reviewed textual reproduction source only, no execution claim'}]
        self.assertEqual(gate.delivery_packages(self.root,self.package(members,[('replay.ps1',data)]),{},set()),{'delivery.zip'})
        for data in (b'\x89PNG\r\n', b'<svg xmlns="http://www.w3.org/2000/svg"/>', b'bad\xff'):
            path.write_bytes(data);source['sha256']=gate.digest(path)
            with self.subTest(data=data),self.assertRaises(ValueError):
                gate.delivery_packages(self.root,self.package(members,[('replay.ps1',data)]),{},set())

    def test_software_diff_is_support_not_production(self):
        data=b"--- a/fixture.py\n+++ b/fixture.py\n@@ -1 +1 @@\n-old\n+new\n"
        path=self.root/'source.patch';path.write_bytes(data)
        source={'path':'source.patch','sha256':gate.digest(path)}
        members=[{'member':'source.patch','source':source,'kind':'support','reason':'Reviewed textual reproduction source only, no execution claim'}]
        self.assertEqual(gate.delivery_packages(self.root,self.package(members,[('source.patch',data)]),{},set()),{'delivery.zip'})
        for data in (b'\x89PNG\r\n', b'<svg xmlns="http://www.w3.org/2000/svg"/>', b'bad\xff'):
            path.write_bytes(data);source['sha256']=gate.digest(path)
            with self.subTest(data=data),self.assertRaises(ValueError):
                gate.delivery_packages(self.root,self.package(members,[('source.patch',data)]),{},set())

    def test_binary_and_svg_cannot_be_renamed_to_text_support(self):
        for data in (b'\x89PNG\r\n\x1a\n',b'RIFF1234WAVE',b'glTF1234',b'\xff\xfe\xff',b'<?xml version="1.0"?><!-- x --><svg xmlns="urn:test"/>',b'<REAPER_PROJECT 1>', b'<svg/>'):
            (self.root/'fake.txt').write_bytes(data)
            source={'path':'fake.txt','sha256':gate.digest(self.root/'fake.txt')}
            members=[{'member':'fake.txt','source':source,'kind':'support','reason':'Attempted rename escape'}]
            with self.subTest(data=data),self.assertRaises(ValueError):
                gate.delivery_packages(self.root,self.package(members,[('fake.txt',data)]),{},set())
    def test_documentation_mentioning_svg_is_text_support(self):
        data=b'How to generate SVG: use <svg> markup in your renderer.'
        (self.root/'README.md').write_bytes(data);self.doc['sha256']=gate.digest(self.root/'README.md')
        members=[{'member':'README.md','source':self.doc,'kind':'support','reason':'Prose only'}]
        self.assertEqual(gate.delivery_packages(self.root,self.package(members,[('README.md',data)]),{},set()),{'delivery.zip'})
    def test_symlink_and_encrypted_member_block(self):
        import struct
        for kind in ('symlink','encrypted'):
            package=self.package()
            if kind=='symlink':
                info=self.zipfile.ZipInfo('assets/image.png');info.create_system=3;info.external_attr=0o120777<<16
                with self.zipfile.ZipFile(self.root/'delivery.zip','w') as z:z.writestr(info,(self.root/'image.png').read_bytes())
            else:
                data=bytearray((self.root/'delivery.zip').read_bytes())
                local=data.index(b'PK\x03\x04');central=data.index(b'PK\x01\x02')
                struct.pack_into('<H',data,local+6,1);struct.pack_into('<H',data,central+8,1)
                (self.root/'delivery.zip').write_bytes(data)
            package[0]['archive']['sha256']=gate.digest(self.root/'delivery.zip')
            with self.subTest(kind=kind),self.assertRaises(ValueError):gate.delivery_packages(self.root,package,{'image.png':'hash'},set())
    def test_bad_zip_blocks(self):
        package=self.package();(self.root/'delivery.zip').write_bytes(b'not a zip')
        package[0]['archive']['sha256']=gate.digest(self.root/'delivery.zip')
        with self.assertRaises(self.zipfile.BadZipFile):gate.delivery_packages(self.root,package,{'image.png':'hash'},set())

class RealTrailEvidenceTests(unittest.TestCase):
    def test_retained_actual_trail_case_is_complete(self):
        root = Path(__file__).resolve().parents[1]
        case = next(c for c in json.loads((root / "collection.json").read_text())["cases"] if c["slug"] == "trail-and-air")
        self.assertEqual(gate.validate_case(root, case), [])
        record = json.loads((root / "docs/showcase/trail-and-air/ecosystem-production.json").read_text())
        self.assertEqual(len(record["stages"]), 5)
        self.assertEqual(sum(len(p["members"]) for p in record["delivery_packages"]), 59)

if __name__ == '__main__': unittest.main()
