"""Fast tests of isolation/failure guards. These do not claim native/browser acceptance."""
import tempfile
import unittest
from pathlib import Path
from author_native import envelope
from common import check_engine_log, isolated_env, isolated_output


class HarnessTests(unittest.TestCase):
    def test_structured_mcp_result_is_preserved(self):
        result = {"success": True, "context": {"valid": True}}
        self.assertEqual(envelope({"structuredContent": result}), result)

    def test_text_mcp_result_is_parsed(self):
        self.assertEqual(envelope({"content": [{"type": "text", "text": '{"success":false}'}]}), {"success": False})

    def test_nested_source_output_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source"
            source.mkdir()
            for output in (source, source / "generated", Path(root)):
                with self.assertRaises(ValueError):
                    isolated_output(output, source)

    def test_existing_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "out"
            path.mkdir()
            (path / "receipt.json").write_text("{}")
            with self.assertRaises(ValueError):
                isolated_output(path)
            self.assertEqual((path / "receipt.json").read_text(), "{}")

    def test_task_session_isolated(self):
        with tempfile.TemporaryDirectory() as root:
            env = isolated_env(Path(root))
            for key in ("HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
                self.assertTrue(Path(env[key]).is_relative_to(root))
                self.assertTrue(Path(env[key]).is_dir())

    def test_runtime_errors_fail(self):
        for message in ("SCRIPT ERROR: Invalid call", "Parse Error: Unexpected token", "Shader compilation failed"):
            with self.assertRaises(RuntimeError):
                check_engine_log(message)
        check_engine_log("TIDAL_READY {}")


if __name__ == "__main__":
    unittest.main()
