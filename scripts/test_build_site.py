#!/usr/bin/env python3
"""Self-test for the site build guards.

Usage:
    python scripts/test_build_site.py

The build is only useful if it actually fails on a broken page, so the checks
are exercised against synthetic fixtures here: images built in memory at known
sizes and frame rates, plus reference resolution cases. Standard library only,
so it runs on a bare CI runner in under a second.
"""

from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import zlib
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_site

FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    if actual == expected:
        print("PASS %s" % name)
    else:
        print("FAIL %s\n       expected %r\n       actual   %r" % (name, expected, actual))
        FAILURES.append(name)


def make_png(width: int, height: int, corrupt: bool = False) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    header = b"\x89PNG\r\n\x1a\n" if not corrupt else b"\x00PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x40" * (width * 3) for _ in range(height))
    return header + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def make_gif(width: int, height: int, delay_cs: int) -> bytes:
    """Smallest GIF that still carries one Graphic Control Extension."""
    out = bytearray(b"GIF89a")
    out += struct.pack("<HH", width, height) + bytes([0x80, 0x00, 0x00])
    out += bytes([0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF])
    out += bytes([0x21, 0xF9, 0x04, 0x00]) + struct.pack("<H", delay_cs) + bytes([0x00, 0x00])
    out += bytes([0x2C]) + struct.pack("<HHHH", 0, 0, width, height) + bytes([0x00])
    out += bytes([0x02, 0x03, 0x08, 0x0B, 0x00])
    out += bytes([0x3B])
    return bytes(out)


def problems_for(filename: str, payload: bytes) -> list[str]:
    tmp = tempfile.mkdtemp(prefix="showcase-build-test-")
    path = os.path.join(tmp, filename)
    if payload is not None:
        with open(path, "wb") as fh:
            fh.write(payload)
    return build_site.check_media(filename, path)



def rejects(name: str, action) -> None:
    try:
        action()
    except ValueError:
        check(name, True, True)
    else:
        check(name, False, True)


def fixture_case() -> dict:
    return {
        "slug": "sample-case", "title": '<script>alert("x")</script>',
        "subtitle": "A reusable case", "software": ["Test Host"],
        "capabilities": ["Render"], "summary": "A real artifact",
        "goal": "Verify the output", "cover": {
            "src": "docs/showcase/sample-case/cover.png", "alt": 'A "quoted" image'},
        "evidence_label": "Published evidence", "evidence_scope": "Not rerun",
        "prompt": {"kind": "reusable", "text": "<tool>& content",
                   "note": "Original prompt not published"},
        "environment": [{"label": "Host", "value": "1.0"}],
        "tools": [{"name": "host.render", "description": "Public record"}],
        "steps": [{"title": "Render", "description": "Run the host"}],
        "results": [{"src": "docs/showcase/sample-case/cover.png",
                     "alt": "Result", "caption": "<b>not HTML</b>"}],
        "checks": [{"name": "Artifact", "result": "pass",
                    "observed": {"size": [120, 80]}}],
        "limitations": ["Not rerun"], "resources": [
            {"label": "Report", "url": "docs/showcase/sample-case/README.md"}],
        "credits": {"author": "Artist", "license": "MIT", "note": "Public"},
        "source": {"url": "https://example.com/source", "commit": "a" * 40},
        "verified_at": "2026-10-01"
    }


def integration_guards() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        case_dir = os.path.join(tmp, "docs", "showcase", "sample-case")
        os.makedirs(case_dir)
        case = fixture_case()
        with open(os.path.join(case_dir, "cover.png"), "wb") as fh:
            fh.write(make_png(120, 80))
        for name in ("README.md", "validation.json"):
            with open(os.path.join(case_dir, name), "w", encoding="utf-8") as fh:
                fh.write("{}" if name.endswith(".json") else "# A case")
        with open(os.path.join(case_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"files": [{"path": "cover.png"}]}, fh)
        os.makedirs(os.path.join(tmp, "assets"))
        for name in ("site.css", "gallery.js", "detail.js"):
            with open(os.path.join(tmp, "assets", name), "w", encoding="utf-8") as fh:
                fh.write("/* local UI */")
        with open(os.path.join(tmp, "index.html"), "w", encoding="utf-8") as fh:
            fh.write('<html><a href="cases/sample-case/">Detail</a>{{CASE_COUNT}}{{CASE_CARDS}}</html>')
        collection = os.path.join(tmp, "collection.json")

        def save():
            with open(collection, "w", encoding="utf-8") as fh:
                json.dump({"schema_version": 1, "cases": [case]}, fh)

        save()
        with open(os.path.join(tmp, "private.txt"), "w", encoding="utf-8") as fh:
            fh.write("not selected")
        # Evidence contracts are tested by test_validate_collection.py. This
        # fixture isolates the publishing, HTML and deletion safety contracts.
        with patch("validate_collection.validate", return_value=[]):
            published, problems, _ = build_site.build(tmp, "_site")
            check("complete fixture builds", problems, [])
            check("static detail is generated", "cases/sample-case/index.html" in published, True)
            check("unselected files stay private", "private.txt" in published, False)
            check("collection input is not accidentally published", "collection.json" in published, False)
            detail_path = os.path.join(tmp, "_site", "cases", "sample-case", "index.html")
            with open(detail_path, encoding="utf-8") as fh:
                detail = fh.read()
            check("case title HTML is escaped", "<script>" in detail, False)
            check("prompt HTML is escaped", "&lt;tool&gt;&amp; content" in detail, True)
            check("caption HTML is escaped", "&lt;b&gt;not HTML&lt;/b&gt;" in detail, True)
            check("image dimensions reserve layout space", 'width="120" height="80"' in detail, True)
            check("video controls are supported", "controls playsinline" in build_site.media_markup(
                {"src": "docs/showcase/sample-case/demo.mp4", "alt": "demo"}, tmp), True)
            for value in (".", "docs", "../outside", "/tmp/out", "_site/../docs"):
                rejects("destructive output rejected: " + value, lambda v=value: build_site.output_path(tmp, v))
            rejects("encoded traversal rejected", lambda: build_site.safe_rel("%2e%2e/private.txt"))
            rejects("private metadata rejected", lambda: build_site.safe_rel(".git/config"))
            rejects("Windows rooted path rejected", lambda: build_site.safe_rel("C:/private.txt"))
            rejects("active resource URL rejected", lambda: build_site.resource_url("javascript:alert(1)"))
            check("relative directory refs use generated index",
                  build_site.refs_of('<a href="../../#works"><a href="../other/">',
                                     "cases/sample/index.html"),
                  ["index.html", "cases/other/index.html"])
            with open(os.path.join(tmp, "_site", "sentinel.txt"), "w", encoding="utf-8") as fh:
                fh.write("keep prior output on failed validation")
            case["resources"].append({"label": "Unsafe", "url": "../private.txt"})
            save()
            _, problems, _ = build_site.build(tmp, "_site")
            check("unsafe resource stops publishing", bool(problems), True)
            check("failed build preserves prior output",
                  os.path.isfile(os.path.join(tmp, "_site", "sentinel.txt")), True)
            case["resources"].pop()
            case["cover"]["src"] = "docs/showcase/sample-case/missing.png"
            save()
            _, problems, _ = build_site.build(tmp, "_site")
            check("missing selected artifact stops publishing",
                  any("missing" in item for item in problems), True)

def main(argv: list[str]) -> int:
    page = "docs/showcase/entry/README.md"
    text = ('![a](../other/pic.png) ![b](/root.png) ![c](#anchor)\n'
            '<img src="https://cdn.example/x.png"> <img src="//cdn.example/y.png">\n'
            '[escape](../../outside.png) [self](README.md)')
    refs = build_site.refs_of(text, page)
    check("resolves sibling page ref", "docs/showcase/other/pic.png" in refs, True)
    check("resolves site-root ref", "root.png" in refs, True)
    check("drops anchors", "#anchor" in refs, False)
    check("drops https links", any("https://" in r for r in refs), False)
    check("drops protocol-relative links", any(r.startswith("//") for r in refs), False)
    check("nested ../ resolves back inside the site", "docs/outside.png" in refs, True)
    rejects("refs escaping the site fail closed",
            lambda: build_site.refs_of("[up](../outside.png)", "index.html"))
    check("drops self references", "docs/showcase/entry/README.md" in refs, False)

    check("oversized still is rejected",
          any("still max" in p for p in problems_for("wide.png", make_png(2000, 10))), True)
    check("compliant still is accepted",
          problems_for("ok.png", make_png(1200, 10)), [])
    check("unreadable still is rejected",
          any("not a readable image" in p for p in problems_for("bad.png", make_png(80, 10, corrupt=True))), True)

    check("fast gif is rejected",
          any("fps" in p for p in problems_for("fast.gif", make_gif(480, 270, 2))), True)
    check("compliant gif is accepted",
          problems_for("ok.gif", make_gif(480, 270, 10)), [])
    check("oversized gif is rejected",
          any("gif max" in p for p in problems_for("wide.gif", make_gif(1000, 270, 10))), True)

    with tempfile.TemporaryDirectory() as tmp:
        payload = os.path.join(tmp, "cal_asset.obj")
        with open(payload, "w", encoding="utf-8") as fh:
            fh.write("v 0 0 0\n")
        check("non-media payloads skip the media contract",
              build_site.check_media("cal_asset.obj", payload), [])

    integration_guards()

    if FAILURES:
        print("\n%d failing case(s): %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("\nall build guards verified")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
