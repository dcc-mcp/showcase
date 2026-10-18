"""No clean-filter result can hide a real candidate-byte modification."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from check_tracked_bytes import verify


class TrackedBytesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
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

    def test_file_type_change_fails(self):
        (self.root / 'raw.png').unlink()
        (self.root / 'raw.png').symlink_to('text.txt')
        with self.assertRaises(ValueError):
            verify(self.root, self.ref)

    def test_executable_mode_flip_fails(self):
        path = self.root / 'text.txt'
        path.chmod(path.stat().st_mode | 0o100)
        with self.assertRaises(ValueError):
            verify(self.root, self.ref)

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
