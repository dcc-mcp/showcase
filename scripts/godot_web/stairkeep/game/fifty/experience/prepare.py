#!/usr/bin/env python3
"""Apply this presentation overlay to the frozen delivered first-chapter source.

Files only: no Godot launch, download, server, UI, save migration or deployment.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

BASELINE_SHA256 = "544ea650aeed6a57e206526aa5d0fda7df1ed69cd47e521de3715811c893ec42"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(baseline, output):
    here = Path(__file__).resolve().parent
    baseline, output = baseline.resolve(), output.resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("Use a new output with an existing parent; nothing is overwritten")
    if sha(baseline) != BASELINE_SHA256:
        raise ValueError("This overlay requires the exact delivered first-chapter source")
    manifest = json.loads((here / "manifest.json").read_text(encoding="utf-8"))
    expected = {row["path"]: row for row in manifest["overlay"]}
    actual = {p.relative_to(here / "overlay").as_posix(): p
              for p in (here / "overlay").rglob("*") if p.is_file()}
    if actual.keys() != expected.keys():
        raise ValueError("Overlay inventory differs")
    for name, source in actual.items():
        relative = PurePosixPath(name)
        if source.is_symlink() or relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe overlay member")
        if sha(source) != expected[name]["sha256"] or source.stat().st_size != expected[name]["bytes"]:
            raise ValueError("Overlay bytes differ: " + name)
    original = {}
    with zipfile.ZipFile(baseline) as archive:
        if archive.testzip() is not None:
            raise ValueError("Baseline ZIP CRC failed")
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe baseline member")
            if member.filename.startswith("project/") and not member.is_dir():
                original[member.filename.removeprefix("project/")] = archive.read(member)
    if not original:
        raise ValueError("No baseline project")
    overwritten = sorted(set(original) & set(actual))
    if overwritten != ["fifty/view/preview.gd"]:
        raise ValueError("Only the existing presentation entry may be overwritten")
    output.mkdir()
    project = output / "project"
    for name, data in original.items():
        destination = project / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    for name, source in actual.items():
        destination = project / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    conserved = []
    for name, data in original.items():
        if name in overwritten:
            continue
        if (project / name).read_bytes() != data:
            raise ValueError("Baseline changed outside presentation: " + name)
        conserved.append(name)
    receipt = {
        "status": "source-prepared-not-exported", "baseline_sha256": sha(baseline),
        "overlay_manifest_sha256": sha(here / "manifest.json"),
        "baseline_files_unchanged": conserved, "overwritten": overwritten,
        "added": sorted(set(actual) - set(original)),
        "engine_executed": False, "web_built": False, "browser_accepted": False,
        "server_changed": False, "save_migration": False,
    }
    (output / "overlay-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_prepared": True, "output": str(project), "engine_executed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.baseline, args.output)
