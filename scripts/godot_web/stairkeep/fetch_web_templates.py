#!/usr/bin/env python3
"""Fetch known official Godot 4.7.2 data, verify whole archive, extract Web only.

This does not install or execute Godot or downloaded binaries. Parallel HTTP
ranges are bound to an exact official archive size and SHA-512. Existing good
parts can be resumed; extracted members are never trusted before the archive
matches the official published SHA512-SUMS.txt.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

VERSION = "4.7.2"
URL = "https://godot-releases.nbg1.your-objectstorage.com/4.7.2-stable/Godot_v4.7.2-stable_export_templates.tpz"
CHECKSUMS_URL = "https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/SHA512-SUMS.txt"
ARCHIVE_SIZE = 1281349702
ARCHIVE_SHA512 = "ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5f40980c9adc28d23e1b92e732ee7bf3461997aa804af74ec2fcd7a93ccb84079"
MEMBERS = ("web_nothreads_release.zip", "web_nothreads_debug.zip", "version.txt")
EXPECTED_MEMBERS = {
    "web_nothreads_release.zip": "d3ee2f08cef0cf3cf6678a6355a92a8db48ccdd35cbd2e8bfd5f0e8a0b4032a0",
    "web_nothreads_debug.zip": "08962aefef811b603541d7951ac67ef00413aad2d978855183c28adee98f626a",
    "version.txt": "38885c88f75abbc797a1db7559719800279a00cfb9fa8b2e2868a7f6f84bad2e",
}
LICENSES = {
    "LICENSE.txt": "b0435e3b3e4e55238f05f4b306f30524a1b2e20147810d436eaa554fa6855c80",
    "COPYRIGHT.txt": "cb1980c88089573bcacd7221d777c689bb8bbd778799f24c27fca0fe5f774d6d",
}
CHUNK = 16 * 1024 * 1024


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fetch_part(out: Path, index: int) -> Path:
    start = index * CHUNK
    end = min(start + CHUNK, ARCHIVE_SIZE)
    path = out / f"{index:04d}.part"
    if path.is_file() and path.stat().st_size == end - start:
        return path
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL, headers={"Range": f"bytes={start}-{end - 1}"})
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.status != 206:
                    raise ValueError("Official server did not honor requested HTTP range")
                expected = f"bytes {start}-{end - 1}/{ARCHIVE_SIZE}"
                if response.headers.get("Content-Range") != expected:
                    raise ValueError("Content-Range differs from the exact archive range")
                data = response.read(end - start + 1)
            if len(data) != end - start:
                raise ValueError("Truncated or oversized range response")
            path.write_bytes(data)
            return path
        except urllib.error.HTTPError:
            # Permission/status responses are not transient transport failures.
            raise
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(0.3 * (attempt + 1))
    raise AssertionError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=6)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(CHECKSUMS_URL, timeout=30) as response:
        checksums = response.read(30000)
    expected_line = ARCHIVE_SHA512 + "  Godot_v4.7.2-stable_export_templates.tpz"
    if expected_line not in checksums.decode("utf-8").splitlines():
        raise SystemExit("Pinned archive checksum is absent from official checksums")
    (out / "SHA512-SUMS.txt").write_bytes(checksums)
    archive = out / "Godot_v4.7.2-stable_export_templates.tpz"
    if not archive.is_file() or archive.stat().st_size != ARCHIVE_SIZE or digest(archive, "sha512") != ARCHIVE_SHA512:
        parts = out / "parts"
        parts.mkdir(exist_ok=True)
        count = (ARCHIVE_SIZE + CHUNK - 1) // CHUNK
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for done, _ in enumerate(pool.map(lambda i: fetch_part(parts, i), range(count)), 1):
                if done % 8 == 0 or done == count:
                    print(f"Downloaded {done}/{count} exact archive ranges", flush=True)
        with archive.open("wb") as target:
            for index in range(count):
                with (parts / f"{index:04d}.part").open("rb") as part:
                    shutil.copyfileobj(part, target, 4 * 1024 * 1024)
        if digest(archive, "sha512") != ARCHIVE_SHA512:
            raise SystemExit("Whole official archive SHA-512 mismatch; no template extracted")
    rows = []
    with zipfile.ZipFile(archive) as z:
        for member in MEMBERS:
            info = z.getinfo("templates/" + member)
            if info.file_size > 64 * 1024 * 1024:
                raise ValueError("Unexpected Web template member size")
            data = z.read(info)
            if hashlib.sha256(data).hexdigest() != EXPECTED_MEMBERS[member]:
                raise SystemExit("Pinned official Web template member mismatch: " + member)
            (out / member).write_bytes(data)
            rows.append({"name": member, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "crc32": info.CRC})
    if (out / "version.txt").read_text().strip() != "4.7.2.stable":
        raise SystemExit("Extracted template version does not match")
    license_rows = []
    for name, expected_sha in LICENSES.items():
        url = "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/" + name
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(1024 * 1024)
        if hashlib.sha256(data).hexdigest() != expected_sha:
            raise SystemExit("Official Godot license-source hash mismatch: " + name)
        (out / name).write_bytes(data)
        license_rows.append({"name": name, "url": url, "bytes": len(data), "sha256": expected_sha})
    record = {"observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "version": VERSION, "official_release": "https://godotengine.org/download/archive/4.7.2-stable/", "url": URL, "checksums_url": CHECKSUMS_URL, "archive_bytes": ARCHIVE_SIZE, "archive_sha512": ARCHIVE_SHA512, "whole_archive_verified": True, "files": rows, "licenses": license_rows, "executed_downloaded_code": False}
    (out / "template-provenance.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
