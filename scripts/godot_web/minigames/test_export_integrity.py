"""Pinned-tool checks must remain active in optimized Python runs."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from export_candidate import require_sha256


class ExportIntegrityTests(unittest.TestCase):
    def test_matching_file_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tool'
            path.write_bytes(b'pinned fixture')
            require_sha256(path, hashlib.sha256(path.read_bytes()).hexdigest(), 'Fixture')

    def test_mismatch_is_rejected_with_and_without_optimization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tool'
            path.write_bytes(b'changed bytes')
            for optimized in [False, True]:
                for label in ['Godot editor', 'Godot Web template']:
                    with self.subTest(optimized=optimized, label=label):
                        code = ('from export_candidate import require_sha256; '
                                f'require_sha256({str(path)!r}, {"0" * 64!r}, {label!r})')
                        command = [sys.executable, *(['-O'] if optimized else []), '-c', code]
                        result = subprocess.run(command, cwd=Path(__file__).parent,
                                                capture_output=True, text=True)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(label + ' SHA-256 mismatch', result.stderr)


if __name__ == '__main__':
    unittest.main()
