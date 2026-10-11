#!/usr/bin/env python3
"""Socket-free HTTP range checks: python scripts/test_media_ranges.py."""
from __future__ import annotations

from email.message import Message
import io
import os
import unittest
from unittest.mock import patch

import browser_preview


class ByteRangeTests(unittest.TestCase):
    def test_supported_ranges(self):
        for value, expected in (
                ("bytes=0-0", (0, 0)), ("bytes=2-5", (2, 5)),
                ("bytes=2-", (2, 9)), ("bytes=-3", (7, 9)),
                ("bytes=-99", (0, 9)), ("bytes=2-99", (2, 9)),
                (" bytes=0-9 ", (0, 9))):
            with self.subTest(value=value):
                self.assertEqual(browser_preview.parse_byte_range(value, 10), expected)

    def test_invalid_and_unsatisfiable_ranges(self):
        for value in ("", "bytes=", "bytes=-", "bytes=-0", "bytes=10-",
                      "bytes=8-7", "bytes=0-1,4-5", "items=0-1", "bytes=+1-2",
                      "bytes=1.0-2", "bytes=1--2", "bytes=１-２", "bytes=0-1\nX:y"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                browser_preview.parse_byte_range(value, 10)

    def test_empty_files_have_no_satisfiable_range(self):
        for value in ("bytes=0-", "bytes=0-0", "bytes=-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                browser_preview.parse_byte_range(value, 0)


class TrackingFile(io.BytesIO):
    def __init__(self, payload):
        super().__init__(payload)
        self.read_sizes = []

    def fileno(self):
        return 42

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class RangeResponseTests(unittest.TestCase):
    def respond(self, range_value=None, method="GET", payload=b"0123456789", extra=()):
        handler = browser_preview.QuietHandler.__new__(browser_preview.QuietHandler)
        handler.path = "/audio.mp3"
        handler.command = method
        handler.request_version = "HTTP/1.1"
        handler.requestline = f"{method} /audio.mp3 HTTP/1.1"
        handler.wfile = io.BytesIO()
        handler.headers = Message()
        if range_value is not None:
            handler.headers["Range"] = range_value
        for key, value in extra:
            handler.headers[key] = value
        source = TrackingFile(payload)
        stat = os.stat_result((0, 0, 0, 0, 0, 0, len(payload), 0, 1700000000, 0))
        with patch.object(handler, "translate_path", return_value="/public/audio.mp3"), \
                patch.object(browser_preview.os.path, "isdir", return_value=False), \
                patch.object(browser_preview.os, "fstat", return_value=stat), \
                patch("builtins.open", return_value=source):
            getattr(handler, "do_" + method)()
        head, _, body = handler.wfile.getvalue().partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        status = int(lines[0].split()[1])
        headers = dict(line.split(": ", 1) for line in lines[1:])
        self.assertTrue(source.closed)
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        return status, headers, body, source

    def test_partial_responses_have_exact_bytes_and_headers(self):
        for value, expected, content_range in (
                ("bytes=0-0", b"0", "bytes 0-0/10"),
                ("bytes=2-5", b"2345", "bytes 2-5/10"),
                ("bytes=7-", b"789", "bytes 7-9/10"),
                ("bytes=-3", b"789", "bytes 7-9/10"),
                ("bytes=-99", b"0123456789", "bytes 0-9/10"),
                ("bytes=7-99", b"789", "bytes 7-9/10")):
            with self.subTest(value=value):
                status, headers, body, _ = self.respond(value)
                self.assertEqual(status, 206)
                self.assertEqual(body, expected)
                self.assertEqual(headers["Content-Range"], content_range)
                self.assertEqual(headers["Content-Length"], str(len(expected)))
                self.assertEqual(headers["Content-type"], "audio/mpeg")
                self.assertIn("Last-Modified", headers)

    def test_bad_ranges_return_empty_416_with_file_size(self):
        for value in ("bytes=10-", "bytes=8-7", "bytes=-0", "bytes=0-1,4-5", "bad"):
            with self.subTest(value=value):
                status, headers, body, source = self.respond(value)
                self.assertEqual(status, 416)
                self.assertEqual(headers["Content-Range"], "bytes */10")
                self.assertEqual(headers["Content-Length"], "0")
                self.assertEqual(body, b"")
                self.assertEqual(source.read_sizes, [])

    def test_repeated_range_headers_are_rejected(self):
        status, _, body, _ = self.respond("bytes=0-1", extra=(("Range", "bytes=4-5"),))
        self.assertEqual((status, body), (416, b""))

    def test_empty_file_range_returns_416(self):
        status, headers, body, _ = self.respond("bytes=0-", payload=b"")
        self.assertEqual((status, body), (416, b""))
        self.assertEqual(headers["Content-Range"], "bytes */0")

    def test_full_file_response_is_unchanged(self):
        status, headers, body, _ = self.respond()
        self.assertEqual((status, body), (200, b"0123456789"))
        self.assertEqual(headers["Content-Length"], "10")
        self.assertNotIn("Content-Range", headers)

    def test_head_ignores_range_and_never_reads_body(self):
        for value in (None, "bytes=2-5", "invalid"):
            with self.subTest(value=value):
                status, headers, body, source = self.respond(value, method="HEAD")
                self.assertEqual((status, body), (200, b""))
                self.assertEqual(headers["Content-Length"], "10")
                self.assertNotIn("Content-Range", headers)
                self.assertEqual(source.read_sizes, [])

    def test_if_range_is_safely_served_in_full(self):
        status, headers, body, _ = self.respond("bytes=2-5", extra=(("If-Range", '"old"'),))
        self.assertEqual((status, body), (200, b"0123456789"))
        self.assertNotIn("Content-Range", headers)

    def test_cache_validation_preserves_not_modified(self):
        status, headers, body, source = self.respond(
            "bytes=2-5", extra=(("If-Modified-Since", "Wed, 15 Nov 2023 00:00:00 GMT"),))
        self.assertEqual((status, body), (304, b""))
        self.assertNotIn("Content-Range", headers)
        self.assertEqual(source.read_sizes, [])

    def test_large_ranges_are_copied_in_bounded_chunks(self):
        payload = bytes(range(256)) * 1000
        status, headers, body, source = self.respond("bytes=3-200003", payload=payload)
        self.assertEqual(status, 206)
        self.assertEqual(headers["Content-Length"], "200001")
        self.assertEqual(body, payload[3:200004])
        self.assertEqual(source.read_sizes, [65536, 65536, 65536, 3393])


if __name__ == "__main__":
    unittest.main()
