"""No clean-filter result can hide a real candidate-byte modification."""
from pathlib import Path
import hashlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from check_tracked_bytes import verify


class TrackedBytesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'core.autocrlf', 'false')
        (self.root / 'raw.png').write_bytes(b'\x89PNG\r\n\x00original')
        (self.root / 'text.txt').write_bytes(b'original\r\n')
        self.git('add', '.')
        self.ref = self.git('write-tree').strip()
        # A clean filter would replace the real bytes with an unrelated pointer.
        # Install it only in this disposable fixture; verification must not run it.
        (self.root / '.gitattributes').write_text('*.png filter=fixture\n')
        self.git('config', 'filter.fixture.clean', 'printf pointer')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def test_unfiltered_original_bytes_pass(self):
        self.assertEqual(verify(self.root, self.ref), 2)

    def test_changed_bytes_and_missing_file_fail(self):
        for data in [b'changed', b'pointer', b'']:
            (self.root / 'raw.png').write_bytes(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                verify(self.root, self.ref)
        (self.root / 'raw.png').unlink()
        with self.assertRaises(ValueError):
            verify(self.root, self.ref)

    def test_staged_changes_cannot_change_baseline(self):
        (self.root / 'text.txt').write_text('changed')
        self.git('add', 'text.txt')
        with self.assertRaises(ValueError):
            verify(self.root, self.ref)

    def lfs_tree(self, pointer):
        path = self.root / 'payload.bin'
        path.write_bytes(pointer)
        self.git('add', 'payload.bin')
        return path, self.git('write-tree').strip()

    def test_exact_committed_lfs_pointer_and_hydrated_content_pass(self):
        data = b'original LFS payload'
        pointer = (f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(data).hexdigest()}\nsize {len(data)}\n').encode()
        path, ref = self.lfs_tree(pointer)
        self.assertEqual(verify(self.root, ref), 3)
        path.write_bytes(data)
        self.assertEqual(verify(self.root, ref), 3)

    def test_hydrated_lfs_wrong_size_and_hash_fail(self):
        data = b'original LFS payload'
        pointer = (f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(data).hexdigest()}\nsize {len(data)}\n').encode()
        path, ref = self.lfs_tree(pointer)
        for changed in [data + b'!', data[:-1], b'x' * len(data)]:
            path.write_bytes(changed)
            with self.subTest(data=changed), self.assertRaisesRegex(ValueError, 'payload[.]bin'):
                verify(self.root, ref)

    def test_malformed_committed_lfs_pointers_do_not_allow_hydration(self):
        data = b'original LFS payload'
        pointer = (f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(data).hexdigest()}\nsize {len(data)}\n').encode()
        malformed = [pointer.replace(b'\n', b'\r\n'), pointer.rstrip(b'\n'),
                     pointer + b'extra\n', pointer.replace(b'spec/v1', b'spec/v2'),
                     pointer.replace(b'oid sha256:', b'oid sha1:'),
                     pointer.replace(b'size ', b'size 0'),
                     pointer.replace(hashlib.sha256(data).hexdigest().encode(), b'g' * 64),
                     b'x' * 257]
        for candidate in malformed:
            path, ref = self.lfs_tree(candidate)
            path.write_bytes(data)
            with self.subTest(pointer=candidate), self.assertRaisesRegex(ValueError, 'payload[.]bin'):
                verify(self.root, ref)

    def test_large_committed_nonpointer_blob_is_not_loaded(self):
        path, ref = self.lfs_tree(b'x' * 257)
        path.write_bytes(b'changed')
        with patch('check_tracked_bytes.subprocess.check_output', wraps=subprocess.check_output) as calls:
            with self.assertRaisesRegex(ValueError, 'payload[.]bin'):
                verify(self.root, ref)
        self.assertFalse(any(call.args[0][:3] == ['git', 'cat-file', 'blob']
                             for call in calls.call_args_list))

    def test_file_type_change_fails(self):
        (self.root / 'raw.png').unlink()
        (self.root / 'raw.png').symlink_to('text.txt')
        with self.assertRaises(ValueError):
            verify(self.root, self.ref)

    def test_executable_mode_flip_fails(self):
        path = self.root / 'text.txt'
        path.chmod(path.stat().st_mode | 0o100)
        ref = self.ref
        if not path.stat().st_mode & 0o111:
            # Windows cannot set executable bits: commit the opposite mode instead.
            self.git('update-index', '--chmod=+x', 'text.txt')
            ref = self.git('write-tree').strip()
        with self.assertRaises(ValueError):
            verify(self.root, ref)

    def test_symlink_target_change_fails(self):
        link = self.root / 'link'
        link.symlink_to('text.txt')
        self.git('add', 'link')
        ref = self.git('write-tree').strip()
        self.assertEqual(verify(self.root, ref), 3)
        link.unlink()
        link.symlink_to('raw.png')
        with self.assertRaises(ValueError):
            verify(self.root, ref)


if __name__ == '__main__':
    unittest.main()
