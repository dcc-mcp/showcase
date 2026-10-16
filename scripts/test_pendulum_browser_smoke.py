#!/usr/bin/env python3
"""Lightweight reference-contract checks; no browser, render or media decode."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from pendulum_browser_smoke import ENTRY, load_references, tracked_bytes_receipt


class TrackedBytesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q')
        self.original = b'\x00actual binary media\xff\n'
        self.file = self.repo / 'sample.bin'
        self.file.write_bytes(self.original)
        (self.repo / '.gitattributes').write_text('sample.bin filter=fixture -text\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '-qm', 'fixture raw blob')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, stderr=subprocess.PIPE)

    def receipt(self):
        return tracked_bytes_receipt(self.repo)

    def test_exact_raw_bytes_pass(self):
        receipt = self.receipt()
        self.assertTrue(receipt['passed'], receipt)
        self.assertEqual(receipt['raw_hashes_matched'], 2)

    def test_clean_filter_false_dirty_keeps_status_and_requires_exact_raw_bytes(self):
        code = "import sys; sys.stdin.buffer.read(); sys.stdout.write('synthetic pointer\\n')"
        self.git('config', 'filter.fixture.clean', shlex.quote(sys.executable) + ' -c ' + shlex.quote(code))
        self.file.write_bytes(self.original)
        os.utime(self.file, (self.file.stat().st_atime, self.file.stat().st_mtime + 5))
        receipt = self.receipt()
        self.assertIn(' M sample.bin', receipt['git_status_porcelain'])
        self.assertTrue(receipt['passed'], receipt)
        self.file.write_bytes(b'changed real bytes')
        self.assertFalse(self.receipt()['passed'])

    def test_unstaged_byte_change_fails(self):
        self.file.write_bytes(b'wrong picture')
        self.assertFalse(self.receipt()['passed'])

    def test_missing_tracked_file_fails(self):
        self.file.unlink()
        self.assertFalse(self.receipt()['passed'])

    def test_extra_index_entry_fails_even_if_all_head_bytes_match(self):
        (self.repo / 'extra.txt').write_text('staged addition')
        self.git('add', 'extra.txt')
        receipt = self.receipt()
        self.assertEqual(receipt['raw_hashes_matched'], 2)
        self.assertFalse(receipt['passed'])

    def test_index_change_fails_after_worktree_bytes_restored(self):
        self.file.write_bytes(b'staged replacement')
        self.git('add', 'sample.bin')
        self.file.write_bytes(self.original)
        receipt = self.receipt()
        self.assertEqual(receipt['raw_hashes_matched'], 2)
        self.assertFalse(receipt['passed'])

    def test_index_deletion_fails_even_with_worktree_file_preserved(self):
        self.git('rm', '--cached', 'sample.bin')
        self.assertFalse(self.receipt()['passed'])

    def test_executable_mode_change_fails(self):
        self.file.chmod(0o755)
        self.assertFalse(self.receipt()['passed'])

    def test_symlink_substitution_fails_even_with_identical_target_bytes(self):
        (self.repo / 'copy.bin').write_bytes(self.original)
        self.file.unlink()
        self.file.symlink_to('copy.bin')
        self.assertFalse(self.receipt()['passed'])

    def test_tracked_symlink_target_is_hashed_without_following(self):
        link = self.repo / 'link'
        link.symlink_to('sample.bin')
        self.git('add', 'link')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'link')
        self.assertTrue(self.receipt()['passed'])
        link.unlink()
        link.symlink_to('missing-target')
        self.assertFalse(self.receipt()['passed'])


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
