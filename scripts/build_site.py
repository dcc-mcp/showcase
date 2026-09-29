#!/usr/bin/env python3
"""Assemble the showcase gallery into a static site ready for GitHub Pages.

Usage:
    python scripts/build_site.py [--out _site]

Starts at index.html, follows every local reference it makes, and keeps
following references inside the Markdown reports it reaches, so each "Read the
full report" page lands with its own images and payloads beside it. Anything
referenced but absent fails the build, as does an artifact outside the gallery
media contract -- a card that would render broken or oversized is caught here
rather than on the published page.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

MAX_STILL_WIDTH = 1600
MAX_GIF_WIDTH = 900
MAX_GIF_BYTES = 8 * 1024 * 1024
MAX_GIF_FPS = 12

ATTR_REF = re.compile(r'(?:src|href)="([^"]+)"')
MD_LINK = re.compile(r'\]\(([^)\s]+)\)')
EXTERNAL = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|//|#)')
FOLLOW = (".html", ".htm", ".md")


def repo_root() -> str:
    """Directory that holds index.html -- the parent of scripts/."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def as_posix(path: str) -> str:
    return path.replace(os.sep, "/")


def refs_of(text: str, base_rel: str) -> list[str]:
    """Local paths a page points at, resolved against that page's directory."""
    found = []
    for pattern in (ATTR_REF, MD_LINK):
        found.extend(pattern.findall(text))
    resolved = []
    for raw in found:
        ref = raw.split("#")[0].split("?")[0]
        if not ref or EXTERNAL.match(ref):
            continue
        if ref.startswith("/"):
            rel = ref.lstrip("/")
        else:
            rel = os.path.normpath(os.path.join(os.path.dirname(base_rel), ref))
        rel = as_posix(rel)
        if rel == base_rel or rel.startswith("../"):
            continue
        resolved.append(rel)
    return resolved


def png_size(path: str):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def jpeg_size(path: str):
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            i += 2
            continue
        if marker == 0xFF:
            i += 1
            continue
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height = int.from_bytes(data[i + 5:i + 7], "big")
            width = int.from_bytes(data[i + 7:i + 9], "big")
            return width, height
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None


def gif_info(path: str):
    """Width, height, frame count and the shortest frame delay in 1/100 s."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 13 or data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    flags = data[10]
    i = 13
    if flags & 0x80:
        i += 3 * (2 ** ((flags & 0x07) + 1))
    frames = 0
    min_delay = None
    while i < len(data):
        block = data[i]
        if block == 0x21:
            if data[i + 1:i + 2] == b"\xf9" and data[i + 2:i + 3] == b"\x04":
                delay = int.from_bytes(data[i + 4:i + 6], "little")
                if delay:
                    min_delay = delay if min_delay is None else min(min_delay, delay)
                frames += 1
            i += 3
            while i < len(data) and data[i] != 0:
                i += 1 + data[i]
            i += 1
        elif block == 0x2C:
            local = data[i + 9] if i + 9 < len(data) else 0
            i += 10
            if local & 0x80:
                i += 3 * (2 ** ((local & 0x07) + 1))
            i += 1
            while i < len(data) and data[i] != 0:
                i += 1 + data[i]
            i += 1
        elif block == 0x3B:
            break
        else:
            i += 1
    return width, height, frames, min_delay


def check_media(rel: str, src: str) -> list[str]:
    """Gallery media contract, enforced on the files the page actually loads."""
    ext = os.path.splitext(rel)[1].lower()
    size = os.path.getsize(src)
    if ext == ".gif":
        info = gif_info(src)
        if info is None:
            return ["%s: not a readable GIF" % rel]
        width, height, frames, min_delay = info
        problems = []
        if width > MAX_GIF_WIDTH:
            problems.append("%s: %dpx wide (gif max %d)" % (rel, width, MAX_GIF_WIDTH))
        if size > MAX_GIF_BYTES:
            problems.append("%s: %d bytes (gif max %d)" % (rel, size, MAX_GIF_BYTES))
        if min_delay:
            fps = 100.0 / min_delay
            if fps > MAX_GIF_FPS + 0.01:
                problems.append("%s: %.1f fps (max %d)" % (rel, fps, MAX_GIF_FPS))
        return problems
    if ext in (".png", ".jpg", ".jpeg"):
        dims = png_size(src) if ext == ".png" else jpeg_size(src)
        if dims is None:
            return ["%s: not a readable image" % rel]
        width, height = dims
        if width > MAX_STILL_WIDTH:
            return ["%s: %dpx wide (still max %d)" % (rel, width, MAX_STILL_WIDTH)]
        return []
    return []


def build(root: str, out_dir: str) -> tuple[list[str], list[str], list[str]]:
    """Return (copied rel paths, problems, notes)."""
    out_abs = os.path.join(root, out_dir)
    if os.path.isdir(out_abs):
        shutil.rmtree(out_abs)
    os.makedirs(out_abs)

    copied: list[str] = []
    seen: set[str] = set()
    problems: list[str] = []
    notes: list[str] = []
    queue = ["index.html"]

    while queue:
        rel = queue.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        src = os.path.join(root, rel)
        if not os.path.isfile(src):
            if rel.endswith("/"):
                notes.append("%s: link points at a directory (no index on Pages)" % rel)
            else:
                problems.append("%s: referenced but missing" % rel)
            continue
        if not os.path.isdir(os.path.dirname(os.path.join(out_abs, rel))):
            os.makedirs(os.path.dirname(os.path.join(out_abs, rel)))
        shutil.copy2(src, os.path.join(out_abs, rel))
        copied.append(rel)
        problems.extend(check_media(rel, src))

        ext = os.path.splitext(rel)[1].lower()
        if ext not in FOLLOW:
            continue
        with open(src, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for child in refs_of(text, rel):
            if child not in seen:
                queue.append(child)

    with open(os.path.join(out_abs, ".nojekyll"), "w"):
        pass
    return copied, problems, notes


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="_site", help="output directory (default: _site)")
    args = parser.parse_args(argv[1:])

    root = repo_root()
    copied, problems, notes = build(root, args.out)
    total = sum(os.path.getsize(os.path.join(root, rel)) for rel in copied)

    media = [r for r in copied if os.path.splitext(r)[1].lower()
             in (".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm")]
    print("built %d files into %s/ (%s, %d media)"
          % (len(copied), args.out, "%0.1f MiB" % (total / 1048576.0), len(media)))
    for rel in sorted(copied):
        print("  + %s" % rel)
    for note in notes:
        print("NOTE %s" % note)
    if problems:
        for problem in problems:
            print("FAIL %s" % problem)
        print("%d problem(s) -- site not published" % len(problems))
        return 1
    print("OK every reference resolves and every artifact is inside the media contract")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
