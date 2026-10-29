"""Real package semantic checks; these do not execute REAPER or create audio."""
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import wave
import zipfile

BASE = Path(__file__).resolve().parents[1] / 'docs/showcase/trail-and-air'
PREFIX = 'Trail-and-Air-UE-Audio/'


def load_packages():
    members = {}
    for path in sorted(BASE.glob('*.zip')):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                data = archive.read(name)
                if name in members:
                    assert members[name] == data, 'Conflicting shared package member'
                members[name] = data
    return members


def validate_delivery(metadata, members):
    assets = metadata['assets']
    assert len({a['id'] for a in assets}) == len(assets)
    if 'tracks' in metadata:
        assert {a['id']: a for a in metadata['tracks']} == {a['id']: a for a in assets}
    for asset in assets:
        name = asset['wav_path']
        assert Path(name).name == name and asset['path'] == name
        data = members[PREFIX + 'Audio/' + name]
        assert hashlib.sha256(data).hexdigest() == asset['sha256'] == asset['source_sha256']
        with wave.open(io.BytesIO(data), 'rb') as audio:
            assert audio.getframerate() == asset['sample_rate'] == 48000
            assert audio.getsampwidth() * 8 == asset['bit_depth'] == 24
            assert audio.getnchannels() == asset['channels']
            assert audio.getnframes() == asset['frames']
            pcm = audio.readframes(audio.getnframes())
        assert hashlib.sha256(pcm).hexdigest() == asset['native_pcm_sha256']


def package_validator(members):
    # Extract only three reviewed pure functions, never import host entrypoints.
    source = members[PREFIX + 'Skills/reaper-game-audio/scripts/render_assets.py']
    tree = ast.parse(source)
    names = {'_wav_name', '_asset_map', '_validate'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    namespace = {'Path': Path, 'SAMPLE_RATE': 48000, 'MAX_ASSETS': 64,
                 'MAX_ASSET_FRAMES': 48000 * 120}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<package pure validator>', 'exec'), namespace)
    return namespace['_validate']


def atlas_for(metadata):
    cursor = 0
    assets = []
    for source in metadata['assets']:
        frames = source['frames']
        assets.append({'id': source['id'], 'target': source['wav_path'],
                       'frames': frames, 'start_frame': cursor,
                       'end_frame': cursor + frames, 'channels': source['channels']})
        cursor += frames
    return {'sample_rate': 48000, 'assets': assets}


def package_opener(members, api, observed):
    # Exercise the delivered function with a stub host, without importing REAPER.
    source = members[PREFIX + 'Skills/reaper-stem-session/scripts/open_project.py']
    tree = ast.parse(source)
    nodes = [n for n in tree.body if (isinstance(n, ast.ImportFrom) and n.module == 'pathlib')
             or (isinstance(n, ast.FunctionDef) and n.name == 'main')]
    namespace = {'R': api, 'active_project': lambda: 'stub-project',
                 'resolve_rpp': lambda value: Path(value).resolve(),
                 'audit': lambda: {'project': str(observed), 'dirty': False},
                 'skill_entry': lambda function: function,
                 'skill_success': lambda message, **context: {'success': True, 'context': context}}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<packaged reopen>', 'exec'), namespace)
    return namespace['main']


class TrailDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.members = load_packages()
        cls.metadata = json.loads(cls.members[PREFIX + 'Audio/manifest.json'])

    def test_actual_four_packages_and_root_manifest(self):
        self.assertEqual(len(list(BASE.glob('*.zip'))), 4)
        self.assertEqual(json.loads((BASE / 'audio-manifest.json').read_text()), self.metadata)
        self.assertEqual(len(self.metadata['assets']), 17)
        graph = json.loads((BASE / 'ecosystem-production.json').read_text())
        repo = BASE.parents[2]
        for package in graph['delivery_packages']:
            archive = repo / package['archive']['path']
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), package['archive']['sha256'])
            with zipfile.ZipFile(archive) as z:
                self.assertCountEqual(z.namelist(), [m['member'] for m in package['members']])
                for member in package['members']:
                    payload = z.read(member['member'])
                    self.assertEqual(payload, (repo / member['source']['path']).read_bytes())
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), member['source']['sha256'])
        validate_delivery(self.metadata, self.members)
        self.assertEqual(len(package_validator(self.members)(atlas_for(self.metadata), self.metadata)), 17)
        master = {a['id']: a for a in self.metadata['assets']}
        seen = []
        for name, data in self.members.items():
            if name.startswith(PREFIX + 'Audio/manifest-') and name.endswith('.json'):
                subset = json.loads(data)
                validate_delivery(subset, self.members)
                for asset in subset['assets']:
                    # Native lineage added to the master may be absent from older split indexes.
                    self.assertEqual(asset, {k: master[asset['id']][k] for k in asset})
                    seen.append(asset['id'])
        self.assertCountEqual(seen, master)

    def test_stale_native_hash_alias_is_rejected_by_actual_packaged_validator(self):
        bad = copy.deepcopy(self.metadata)
        bad['tracks'][0]['sha256'] = bad['assets'][0]['native_file_sha256']
        with self.assertRaisesRegex(ValueError, 'assets and tracks'):
            package_validator(self.members)(atlas_for(bad), bad)
        with self.assertRaises(AssertionError):
            validate_delivery(bad, self.members)

    def test_wrong_delivery_hash_format_and_frames_fail(self):
        for key, value in [('sha256', '0' * 64), ('frames', 1), ('channels', 2), ('bit_depth', 16)]:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.metadata)
                bad['assets'][0][key] = value
                bad['tracks'] = copy.deepcopy(bad['assets'])
                with self.assertRaises(AssertionError):
                    validate_delivery(bad, self.members)

    def test_packaged_reopen_accepts_native_path_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'session.rpp'; target.write_text('stub project')
            child = Path(directory) / 'child'; child.mkdir()
            observed = child / '..' / target.name
            api = Mock(); api.IsProjectDirty.return_value = False
            result = package_opener(self.members, api, observed)(project_path=str(target))
            self.assertTrue(result['success'])
            self.assertEqual(result['context']['project'], str(observed))
            api.Main_openProject.assert_called_once_with(str(target.resolve()))

    def test_packaged_reopen_still_rejects_different_project_and_dirty_host(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'session.rpp'; target.write_text('stub project')
            api = Mock(); api.IsProjectDirty.return_value = True
            reopen = package_opener(self.members, api, target.with_name('other.rpp'))
            with self.assertRaisesRegex(RuntimeError, 'Save the active project'):
                reopen(project_path=str(target))
            api.Main_openProject.assert_not_called()
            api.IsProjectDirty.return_value = False
            with self.assertRaisesRegex(RuntimeError, 'did not open requested project'):
                reopen(project_path=str(target))


if __name__ == '__main__':
    unittest.main()
