#!/usr/bin/env python3
"""Host-free guards for the browser smoke's local public-resource checks.

Run with: python scripts/test_browser_preview.py
No Playwright installation or browser is required for these contract tests.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import inspect
import io
import unittest
from unittest.mock import Mock, call

import browser_preview


ORIGIN = "http://127.0.0.1:8765"
ENTRY = "docs/showcase/trail-and-air/"


class MediaNavigationTests(unittest.TestCase):
    def test_case_navigation_does_not_wait_for_media_network_idle(self):
        tree = ast.parse(inspect.getsource(browser_preview.run))
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "goto" and node.args
                 and any(isinstance(part, ast.Name) and part.id == "path" for part in ast.walk(node.args[0]))]
        self.assertEqual(len(calls), 1)
        waits = [keyword.value.value for keyword in calls[0].keywords if keyword.arg == "wait_until"]
        self.assertEqual(waits, ["domcontentloaded"])


class NativeAudioSeekTests(unittest.TestCase):
    def test_tabs_into_native_controls_until_real_small_seek_is_observed(self):
        page, audio = Mock(), Mock()
        audio.evaluate.side_effect = [0.2, 0.4]
        page.wait_for_function.side_effect = [TimeoutError(), None]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(browser_preview.keyboard_seek_audio(page, audio, TimeoutError), 0.4)
        audio.focus.assert_called_once_with()
        self.assertEqual(page.keyboard.press.call_args_list,
                         [call("Tab"), call("ArrowRight"), call("Tab"), call("ArrowRight")])
        for arguments in audio.evaluate.call_args_list:
            self.assertEqual(arguments.args, ("a => a.currentTime",))
        expression = page.wait_for_function.call_args.args[0]
        self.assertIn("a.paused && !a.seeking", expression)
        self.assertIn("before + 0.05", expression)

    def test_keyboard_traversal_is_bounded_and_does_not_fake_success(self):
        page, audio = Mock(), Mock()
        audio.evaluate.return_value = 0.2
        page.wait_for_function.side_effect = TimeoutError()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(AssertionError, "bounded Tab"):
            browser_preview.keyboard_seek_audio(page, audio, TimeoutError, max_tabs=3)
        self.assertEqual(page.keyboard.press.call_count, 6)
        self.assertEqual(page.wait_for_function.call_count, 3)

    def test_non_timeout_browser_errors_are_not_hidden(self):
        page, audio = Mock(), Mock()
        audio.evaluate.return_value = 0.2
        page.wait_for_function.side_effect = RuntimeError("Browser closed")
        with self.assertRaisesRegex(RuntimeError, "Browser closed"):
            browser_preview.keyboard_seek_audio(page, audio, TimeoutError)


def fixture():
    payloads = {
        "hero.jpg": b"public cover",
        "audition.mp3": b"public audio",
        "pack.zip": b"public archive",
        "README.md": b"public documentation",
        "unselected.mp4": b"not a selected reference",
    }
    manifest = {"files": [{"path": path, "bytes": len(payload),
                           "sha256": hashlib.sha256(payload).hexdigest()}
                          for path, payload in payloads.items()]}
    case = {"slug": "trail-and-air", "cover": {"src": ENTRY + "hero.jpg"},
            "results": [{"src": ENTRY + "audition.mp3"}],
            "resources": [{"url": ENTRY + "pack.zip"}, {"url": ENTRY + "README.md"},
                          {"url": ENTRY + "audition.mp3"},
                          {"url": "https://example.com/source"}]}
    return case, manifest, payloads


class PublicFileUrlTests(unittest.TestCase):
    def test_quotes_safe_relative_paths(self):
        self.assertEqual(browser_preview.public_file_url(ORIGIN, ENTRY + "audio file.mp3"),
                         ORIGIN + "/" + ENTRY + "audio%20file.mp3")

    def test_external_or_ambiguous_paths_are_rejected(self):
        for path in ("", "/root.mp3", "https://example.com/a", "//example.com/a",
                     "file:///private", "../a", "a/../b", "a/./b", "a//b", "a/",
                     "a\\b", "%2e%2e/a", "a%2fb", "a?b", "a#b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                browser_preview.public_file_url(ORIGIN, path)


class SelectedManifestTests(unittest.TestCase):
    def test_exact_selected_local_files_only_and_deduplicated(self):
        case, manifest, _ = fixture()
        files = browser_preview.selected_public_files(case, manifest)
        self.assertEqual(list(files), sorted(ENTRY + name for name in (
            "hero.jpg", "audition.mp3", "pack.zip", "README.md")))

    def test_missing_selected_file_fails(self):
        case, manifest, _ = fixture()
        manifest["files"] = [row for row in manifest["files"] if row["path"] != "pack.zip"]
        with self.assertRaisesRegex(ValueError, "absent"):
            browser_preview.selected_public_files(case, manifest)

    def test_resource_outside_selected_entry_fails(self):
        case, manifest, _ = fixture()
        case["resources"].append({"url": "docs/showcase/other-case/public.zip"})
        with self.assertRaisesRegex(ValueError, "absent"):
            browser_preview.selected_public_files(case, manifest)

    def test_protocol_relative_resource_fails(self):
        case, manifest, _ = fixture()
        case["resources"].append({"url": "//example.com/archive.zip"})
        with self.assertRaises(ValueError):
            browser_preview.selected_public_files(case, manifest)

    def test_duplicate_manifest_file_fails(self):
        case, manifest, _ = fixture()
        manifest["files"].append(copy.deepcopy(manifest["files"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            browser_preview.selected_public_files(case, manifest)

    def test_manifest_path_escape_fails(self):
        case, manifest, _ = fixture()
        manifest["files"].append({"path": "../private.txt"})
        with self.assertRaises(ValueError):
            browser_preview.selected_public_files(case, manifest)

    def test_selected_hash_and_size_are_required(self):
        case, base, _ = fixture()
        for key, bad_value in (("bytes", None), ("bytes", 0), ("bytes", True),
                               ("bytes", "12"), ("sha256", None), ("sha256", "a" * 63),
                               ("sha256", "g" * 64)):
            with self.subTest(key=key, bad_value=bad_value):
                manifest = copy.deepcopy(base)
                manifest["files"][0][key] = bad_value
                with self.assertRaisesRegex(ValueError, "byte count and SHA-256"):
                    browser_preview.selected_public_files(case, manifest)

    def test_fetched_bytes_are_checked_against_manifest(self):
        _, manifest, payloads = fixture()
        row = manifest["files"][0]
        actual = browser_preview.check_public_payload(ENTRY + row["path"],
                                                       payloads[row["path"]], row)
        self.assertEqual(actual, {"path": ENTRY + row["path"], "bytes": row["bytes"],
                                  "sha256": row["sha256"]})

    def test_changed_bytes_or_digest_fail(self):
        _, manifest, payloads = fixture()
        row = manifest["files"][0]
        for payload in (payloads[row["path"]] + b"x", b"x" * row["bytes"]):
            with self.subTest(payload=payload), self.assertRaises(AssertionError):
                browser_preview.check_public_payload(ENTRY + row["path"], payload, row)


class FetchPublicFileTests(unittest.TestCase):
    def response(self, status=200, url=None):
        response = Mock(status=status, url=url or ORIGIN + "/" + ENTRY + "audition.mp3")
        response.body.return_value = b"public audio"
        request = Mock()
        request.get.return_value = response
        return request, response

    def test_local_request_has_no_redirects_and_releases_response(self):
        request, response = self.response()
        self.assertEqual(browser_preview.fetch_public_file(request, ORIGIN, ENTRY + "audition.mp3"),
                         b"public audio")
        request.get.assert_called_once_with(ORIGIN + "/" + ENTRY + "audition.mp3", max_redirects=0)
        response.dispose.assert_called_once_with()

    def test_external_input_never_reaches_request(self):
        request, _ = self.response()
        with self.assertRaises(ValueError):
            browser_preview.fetch_public_file(request, ORIGIN, "https://example.com/audio.mp3")
        request.get.assert_not_called()

    def test_redirect_and_http_error_fail_without_reading_body(self):
        for status in (302, 404, 500):
            with self.subTest(status=status):
                request, response = self.response(status=status)
                with self.assertRaises(AssertionError):
                    browser_preview.fetch_public_file(request, ORIGIN, ENTRY + "audition.mp3")
                response.body.assert_not_called()
                response.dispose.assert_called_once_with()

    def test_response_origin_or_path_change_fails(self):
        request, response = self.response(url="https://example.com/audio.mp3")
        with self.assertRaises(AssertionError):
            browser_preview.fetch_public_file(request, ORIGIN, ENTRY + "audition.mp3")
        response.body.assert_not_called()
        response.dispose.assert_called_once_with()


if __name__ == "__main__":
    unittest.main(verbosity=2)
