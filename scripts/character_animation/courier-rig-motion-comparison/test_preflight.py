"""CLI refusal checks using synthetic bytes; no host or generated asset required."""
from pathlib import Path
import hashlib
import json
import struct
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

    def run_cli(self, script, optimized, output, expected_sha256=None):
        return subprocess.run(
            [sys.executable, *(["-O"] if optimized else []), str(ROOT / script),
             "--input", str(self.source), "--output-dir", str(output),
             *(["--expected-sha256", expected_sha256] if expected_sha256 else [])],
            capture_output=True, text=True, check=False,
        )

    def triangle_fixture(self):
        binary = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
        document = {"asset": {"version": "2.0"}, "scene": 0,
                    "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
                    "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
                    "buffers": [{"byteLength": len(binary)}],
                    "bufferViews": [{"buffer": 0, "byteLength": len(binary)}],
                    "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
                    "skins": [], "animations": []}
        encoded = json.dumps(document).encode("utf-8")
        encoded += b" " * (-len(encoded) % 4)
        chunks = struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
        chunks += struct.pack("<II", len(binary), 0x004E4942) + binary
        self.payload = struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks
        self.source.write_bytes(self.payload)
        return hashlib.sha256(self.payload).hexdigest()

    def test_matching_triangle_runs_with_runtime_validation(self):
        expected = self.triangle_fixture()
        for script in SCRIPTS:
            with self.subTest(script=script):
                output = self.root / script
                result = self.run_cli(script, False, output, expected)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(output.is_dir())
                if script == "prepare_neutral_mesh.py":
                    report = json.loads((output / "transfer-manifest.json").read_text(encoding="utf-8"))
                    self.assertEqual(report["counts"], {"vertices": 3, "uv_entries": 0,
                                                      "normal_entries": 0, "triangles": 1, "objects": 1})
                else:
                    report = json.loads((output / "motion-audit.json").read_text(encoding="utf-8"))
                    self.assertEqual(report["sha256"], expected)
                    self.assertEqual(report["clips"], [])
                    self.assertEqual(report["skin_weight_audit"], [])
                self.assertEqual(self.source.read_bytes(), self.payload)

    def test_optimized_matching_triangle_is_refused_before_output(self):
        expected = self.triangle_fixture()
        for script in SCRIPTS:
            with self.subTest(script=script):
                output = self.root / script
                result = self.run_cli(script, True, output, expected)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("optimized Python is unsupported; runtime validation requires assertions", result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(self.source.read_bytes(), self.payload)

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
