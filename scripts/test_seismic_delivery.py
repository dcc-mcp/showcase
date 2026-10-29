"""Current byte-preserving Seismic delivery, without executing production recipes."""
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile
import copy

from PIL import Image
import build_site
import validate_ecosystem as gate

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/showcase/seismic-lens'
SHA = lambda data: hashlib.sha256(data).hexdigest()


def verify_inventory(members, prefix, manifest_name):
    manifest = json.loads(members[prefix + manifest_name])
    expected = {prefix + manifest_name}
    for item in manifest['files']:
        path = item['path']
        assert not Path(path).is_absolute() and '..' not in Path(path).parts
        name = prefix + path
        assert name not in expected
        expected.add(name)
        data = members[name]
        assert len(data) == item['bytes'] and SHA(data) == item['sha256']
    actual = {name for name in members if name.startswith(prefix)}
    assert actual == expected


class SeismicDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((BASE / 'ecosystem-production.json').read_text())
        cls.package = cls.graph['delivery_packages'][0]
        cls.archive = (ROOT / cls.package['archive']['path']).read_bytes()
        with zipfile.ZipFile(io.BytesIO(cls.archive)) as z:
            cls.names = z.namelist()
            cls.members = {name: z.read(name) for name in cls.names}

    def test_exact_members_and_source_bytes(self):
        self.assertEqual(SHA(self.archive), self.package['archive']['sha256'])
        self.assertEqual(len(self.names), len(set(self.names)))
        self.assertEqual(set(self.names), {m['member'] for m in self.package['members']})
        for item in self.package['members']:
            data = self.members[item['member']]
            self.assertEqual(data, (ROOT / item['source']['path']).read_bytes())
            self.assertEqual(SHA(data), item['source']['sha256'])

    def test_original_closed_inventories_and_all_77_bytes(self):
        with zipfile.ZipFile(ROOT / 'archives/showcase/seismic-lens/pre-ecosystem-2026-10-20/editable-source.zip') as original:
            self.assertEqual(len(original.namelist()), 77)
            for name in original.namelist():
                self.assertEqual(original.read(name), self.members['qualified-source/' + name])
        verify_inventory(self.members, 'qualified-source/', 'manifest.json')
        verify_inventory(self.members, 'qualified-source/gimp/', 'package-manifest.json')

    def test_corrupt_manifest_alias_is_rejected(self):
        bad = dict(self.members)
        name = 'qualified-source/manifest.json'
        record = json.loads(bad[name])
        record['files'][0]['sha256'] = '0' * 64
        bad[name] = json.dumps(record).encode()
        with self.assertRaises(AssertionError):
            verify_inventory(bad, 'qualified-source/', 'manifest.json')

    def test_current_images_and_historical_boundaries(self):
        case = next(c for c in json.loads((ROOT / 'collection.json').read_text())['cases']
                    if c['slug'] == 'seismic-lens')
        selected = json.dumps(case)
        self.assertNotIn('earlier-coarse-section-y.png', selected)
        self.assertNotIn('seismic-lens-native-poster.png', selected)
        self.assertIn('new-coarse-section-y.png', selected)
        self.assertIn('native-observation-poster.png', selected)
        self.assertFalse(any('earlier-coarse' in name for name in self.names))
        for name, size in [('new-coarse-section-y.png', (720, 480)),
                           ('native-observation-poster.png', (1178, 814))]:
            with Image.open(BASE / name) as image:
                image.load()
                self.assertEqual(image.size, size)
        stages = {stage['id']: stage for stage in self.graph['stages']}
        self.assertIn('NOT authenticate', stages['new-typed-full-vti-byte-identical']['scope'])
        self.assertEqual(stages['actual-paraview-panels-and-states']
                         ['input_identity_relationship']['historical_input_sha256'],
                         SHA((BASE / 'retained/paraview/native/paraview/data/synthetic-lens.vti').read_bytes()))

    def test_native_master_is_download_not_page_media(self):
        case = next(c for c in json.loads((ROOT / 'collection.json').read_text())['cases']
                    if c['slug'] == 'seismic-lens')
        master = 'docs/showcase/seismic-lens/retained/gimp/native/gimp/seismic-lens-master.png'
        permitted = gate.native_download_paths(ROOT, case)
        self.assertIn(master, permitted)
        self.assertTrue(build_site.check_media(master, str(ROOT / master)))
        self.assertEqual(build_site.check_media(master, str(ROOT / master), native_download=True), [])
        for selection in ('cover', 'results', 'steps'):
            changed = copy.deepcopy(case)
            if selection == 'cover':
                changed['cover'] = {'src': master}
            elif selection == 'steps':
                changed['steps'] = [{'image': {'src': master}}]
            else:
                changed['results'] = [{'src': master}]
            self.assertNotIn(master, gate.native_download_paths(ROOT, changed))
        other = {'slug': 'other-case', 'cover': {'src': master}}
        self.assertNotIn(master, gate.native_download_paths(ROOT, case, [case, other]))

    def test_unselected_history_is_outside_public_tree(self):
        manifest = json.loads((BASE / 'manifest.json').read_text())
        selected = {row['path'] for row in manifest['files']}
        for name in ('earlier-coarse-section-y.png', 'editable-source.zip',
                     'seismic-lens-native-poster.png'):
            self.assertNotIn(name, selected)
            self.assertFalse((BASE / name).exists())
            self.assertTrue((ROOT / 'archives/showcase/seismic-lens/pre-ecosystem-2026-10-20' / name).is_file())
        self.assertFalse(any('archives/' in row['path'] for row in manifest['files']))


if __name__ == '__main__':
    unittest.main()
