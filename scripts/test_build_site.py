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

import os
import struct
import sys
import tempfile
import zlib

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
    check("drops refs escaping the site",
          build_site.refs_of("[up](../outside.png)", "index.html"), [])
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

    if FAILURES:
        print("\n%d failing case(s): %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("\nall build guards verified")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
