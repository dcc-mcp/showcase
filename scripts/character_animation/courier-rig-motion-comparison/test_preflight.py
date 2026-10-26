"""CLI refusal checks using synthetic bytes; no host or generated asset required."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
SCRIPTS = ("prepare_neutral_mesh.py", "audit_existing_motion.py")


class PreflightRefusals(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic.glb"
        self.payload = b"Synthetic wrong-hash input; never a real character asset.\n"
        self.source.write_bytes(self.payload)

    def run_cli(self, script, optimized, output):
        return subprocess.run(
            [sys.executable, *(["-O"] if optimized else []), str(ROOT / script),
             "--input", str(self.source), "--output-dir", str(output)],
            capture_output=True, text=True, check=False,
        )

    def test_wrong_hash_is_refused_before_output_creation(self):
        for script in SCRIPTS:
            for optimized in (False, True):
                with self.subTest(script=script, optimized=optimized):
                    output = self.root / "absent-output"
                    result = self.run_cli(script, optimized, output)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("source differs from the selected hash-bound derivative", result.stderr)
                    self.assertFalse(output.exists())
                    self.assertEqual(self.source.read_bytes(), self.payload)

    def test_nonempty_output_is_preserved(self):
        output = self.root / "existing-output"
        output.mkdir()
        marker = output / "keep.bin"
        marker.write_bytes(b"Previous evidence must stay unchanged.\n")
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        for script in SCRIPTS:
            for optimized in (False, True):
                with self.subTest(script=script, optimized=optimized):
                    result = self.run_cli(script, optimized, output)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("preserve", result.stderr)
                    self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)
                    self.assertEqual(self.source.read_bytes(), self.payload)


if __name__ == "__main__":
    unittest.main()
