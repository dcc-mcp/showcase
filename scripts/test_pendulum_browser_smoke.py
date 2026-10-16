#!/usr/bin/env python3
"""Lightweight reference-contract checks; no browser, render or media decode."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pendulum_browser_smoke import ENTRY, load_references


class ReferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.site = Path(self.temp.name)
        folder = self.site / ENTRY
        folder.mkdir(parents=True)

        def record(name):
            data = b'synthetic contract bytes: ' + name.encode()
            (folder / name).write_bytes(data)
            return {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

        self.spec = {'schema_version': 1, 'width': 960, 'height': 720,
            'frame_count': 144, 'frame_rate': '24000/1001',
            'video': record('pendulum-oidn.mp4'),
            'atlas': {**record('playback-atlas.jpg'), 'columns': 8, 'rows': 18,
                      'tile_width': 160, 'tile_height': 120},
            'keyframes': [dict(frame=frame, **record(f'playback-frame-{frame:04d}.png')) for frame in (1, 73, 144)],
            'reference_basis': 'Independent decode of the exact final H.264 delivery; not a source-render quality reference.'}
        self.save()

    def save(self):
        (self.site / ENTRY / 'playback-reference.json').write_text(json.dumps(self.spec))

    def test_all_reference_bytes_are_bound_to_exact_delivery(self):
        self.assertEqual(load_references(self.site), self.spec)

    def test_missing_atlas_blocks(self):
        (self.site / ENTRY / 'playback-atlas.jpg').unlink()
        with self.assertRaises(FileNotFoundError):
            load_references(self.site)

    def test_stale_or_swapped_media_blocks(self):
        for record in [self.spec['video'], self.spec['atlas'], *self.spec['keyframes']]:
            original = record['sha256']
            record['sha256'] = '0' * 64
            self.save()
            with self.assertRaisesRegex(AssertionError, 'digest differs'):
                load_references(self.site)
            record['sha256'] = original

    def test_missing_endpoint_or_legacy_format_blocks(self):
        self.spec['keyframes'][-1]['frame'] = 143
        self.save()
        with self.assertRaises(AssertionError):
            load_references(self.site)
        self.spec['keyframes'][-1]['frame'] = 144
        self.spec['width'] = 640
        self.save()
        with self.assertRaises(AssertionError):
            load_references(self.site)

    def test_external_or_parent_reference_paths_block(self):
        for name in ['../outside.png', '/absolute.png', 'https://example.test/image.png']:
            self.spec['atlas']['path'] = name
            self.save()
            with self.assertRaisesRegex(AssertionError, 'Unsafe'):
                load_references(self.site)


if __name__ == '__main__':
    unittest.main()
