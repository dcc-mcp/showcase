#!/usr/bin/env python3
"""Check that a showcase entry is structurally complete.

Usage:
    python scripts/validate_entry.py docs/showcase/<slug> [...]

Exit code 0 means the three mandatory files are present, the manifest covers
exactly the artifacts on disk with matching hashes, and the validation file
carries its required keys. It does not check that the numbers are correct --
only that they are present and traceable.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

MANDATORY = ("README.md", "manifest.json", "validation.json")
REQUIRED_VALIDATION_KEYS = ("schema_version", "environment", "checks")
VALID_RESULTS = ("pass", "fail")

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm")
MAX_IMAGE_WIDTH = 1600
MAX_IMAGE_BYTES = 400 * 1024


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(entry_dir: str) -> list[str]:
    """Return a list of problems; empty means the entry is complete."""
    problems: list[str] = []
    name = os.path.basename(entry_dir.rstrip(os.sep))

    if not os.path.isdir(entry_dir):
        return ["%s: not a directory" % entry_dir]

    # 1. mandatory files
    for rel in MANDATORY:
        if not os.path.isfile(os.path.join(entry_dir, rel)):
            problems.append("%s: missing mandatory file %s" % (name, rel))
    if any(p.endswith(rel) for p in problems for rel in MANDATORY):
        return problems

    # 2. manifest parses
    with open(os.path.join(entry_dir, "manifest.json"), encoding="utf-8") as fh:
        try:
            manifest = json.load(fh)
        except json.JSONDecodeError as exc:
            return ["%s: manifest.json is not valid JSON (%s)" % (name, exc)]

    listed = []
    for rec in manifest.get("files", []):
        rel = rec.get("path")
        if not rel:
            problems.append("%s: manifest entry without 'path'" % name)
            continue
        listed.append(rel)
        path = os.path.join(entry_dir, rel)
        if not os.path.isfile(path):
            problems.append("%s: manifest lists %s but it is missing" % (name, rel))
            continue
        if "sha256" not in rec:
            problems.append("%s: %s has no sha256" % (name, rel))
        elif sha256_of(path) != rec["sha256"]:
            problems.append("%s: %s sha256 mismatch" % (name, rel))
        if "bytes" not in rec:
            problems.append("%s: %s has no byte count" % (name, rel))
        elif os.path.getsize(path) != rec["bytes"]:
            problems.append("%s: %s byte count mismatch" % (name, rel))

        # artifact specs
        if rel.lower().endswith((".png", ".jpg", ".jpeg")):
            width = rec.get("width")
            if width is None:
                problems.append("%s: %s image without width" % (name, rel))
            elif width > MAX_IMAGE_WIDTH:
                problems.append("%s: %s is %dpx wide (max %d)"
                                % (name, rel, width, MAX_IMAGE_WIDTH))
            if os.path.getsize(path) > MAX_IMAGE_BYTES and not rel.lower().endswith((".jpg", ".jpeg")):
                problems.append("%s: %s is over %d bytes and is not JPEG (convert at q82)"
                                % (name, rel, MAX_IMAGE_BYTES))

    # 3. no orphan artifacts
    on_disk = {f for f in os.listdir(entry_dir)
               if os.path.isfile(os.path.join(entry_dir, f))
               and f not in MANDATORY and not f.startswith(".")}
    orphans = sorted(on_disk - set(listed))
    for rel in orphans:
        problems.append("%s: %s is on disk but not in manifest.json" % (name, rel))

    # 4. validation shape
    with open(os.path.join(entry_dir, "validation.json"), encoding="utf-8") as fh:
        try:
            validation = json.load(fh)
        except json.JSONDecodeError as exc:
            return problems + ["%s: validation.json is not valid JSON (%s)" % (name, exc)]

    for key in REQUIRED_VALIDATION_KEYS:
        if key not in validation:
            problems.append("%s: validation.json missing '%s'" % (name, key))

    checks = validation.get("checks", [])
    if not isinstance(checks, list) or not checks:
        problems.append("%s: validation.json has no checks[]" % name)
    for chk in checks if isinstance(checks, list) else []:
        if "name" not in chk:
            problems.append("%s: a check has no name" % name)
        if chk.get("result") not in VALID_RESULTS:
            problems.append("%s: check '%s' has result %r (expected pass/fail)"
                            % (name, chk.get("name"), chk.get("result")))

    if not validation.get("not_claimed"):
        problems.append("%s: validation.json has no not_claimed[] -- say what the entry does not prove"
                        % name)

    return problems


def main(argv: list[str]) -> int:
    targets = argv[1:] or ["docs/showcase"]
    total = 0
    for target in targets:
        if os.path.isfile(os.path.join(target, "manifest.json")):
            entries = [target]
        else:
            entries = [os.path.join(target, d) for d in sorted(os.listdir(target))
                       if os.path.isdir(os.path.join(target, d))]
        if not entries:
            print("no entries under %s" % target)
            continue
        for entry in entries:
            problems = validate(entry)
            if problems:
                total += len(problems)
                print("FAIL %s" % os.path.basename(entry.rstrip(os.sep)))
                for p in problems:
                    print("     - %s" % p)
            else:
                print("PASS %s" % os.path.basename(entry.rstrip(os.sep)))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
