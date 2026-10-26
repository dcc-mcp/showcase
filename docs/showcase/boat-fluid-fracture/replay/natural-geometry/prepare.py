"""Prepare fresh local payloads from the exact source archive; makes no DCC calls."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


ARCHIVE_SHA256 = "0a8583b3f25cfcf40d1b1df5f91369310bb1a35f6a5b010de1f87946dc3caef3"
OBJ_SHA256 = "c728f8aa93f934c8339fe9f47543eea99103ac0d5a098f30ffe595a905a783fc"
BASE = Path(__file__).resolve().parent


def safe_members(archive):
    members = archive.infolist()
    assert members and len({member.filename for member in members}) == len(members)
    for member in members:
        name = PurePosixPath(member.filename)
        if name.is_absolute() or ".." in name.parts or "\\" in member.filename or ":" in member.filename:
            raise ValueError("Unsafe archive member")
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Archive symlinks are not supported")
    assert "boat.obj" in {member.filename for member in members}
    return members


def prepare(archive_path, output):
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == ARCHIVE_SHA256
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    model = output / "model"
    model.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(model, members=safe_members(archive))
    assert hashlib.sha256((model / "boat.obj").read_bytes()).hexdigest() == OBJ_SHA256
    calls = output / "calls"
    calls.mkdir()
    for name in ("00-container.json", "01-source.json", "02-wood-fracture.json", "03-filter-native-artifact.json"):
        value = json.loads((BASE / name).read_text())
        if name == "01-source.json":
            assert value["nodes"][0]["parameters"]["file"] == "{{MODEL_ROOT}}/boat.obj"
            value["nodes"][0]["parameters"]["file"] = (model / "boat.obj").as_posix()
        for dry_run in (True, False):
            value["dry_run"] = dry_run
            filename = name.replace(".json", ".dry-run.json") if dry_run else name
            (calls / filename).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    cache = {"file_path": (BASE / "cache_and_verify.py").as_posix(), "context": {
        "out_dir": output.as_posix(), "phase": "cache"}, "output_mode": "structured"}
    (calls / "04-cache-and-verify.json").write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    readers = json.loads((BASE / "05-ready-readers.json").read_text())
    for node in readers["nodes"]:
        filename = PurePosixPath(node["parameters"]["file"]).name
        node["parameters"]["file"] = (output / "geometry" / "rest" / filename).as_posix()
    for dry_run in (True, False):
        readers["dry_run"] = dry_run
        filename = "05-ready-readers.dry-run.json" if dry_run else "05-ready-readers.json"
        (calls / filename).write_text(json.dumps(readers, indent=2) + "\n", encoding="utf-8")
    verify = {"file_path": (BASE / "verify_reopened.py").as_posix(), "context": {
        "out_dir": output.as_posix(), "phase": "recovered"}, "output_mode": "structured"}
    (calls / "06-recover-audit.json").write_text(json.dumps(verify, indent=2) + "\n", encoding="utf-8")
    hip = (output / "native-wood-rest.hip").as_posix()
    (calls / "07-save.json").write_text(json.dumps({"file_path": hip}), encoding="utf-8")
    (calls / "08-reopen.json").write_text(json.dumps({"file_path": hip, "suppress_save_prompt": True}), encoding="utf-8")
    verify["context"]["phase"] = "reopened"
    (calls / "09-verify-reopened.json").write_text(json.dumps(verify, indent=2) + "\n", encoding="utf-8")
    return {"prepared": True, "source_archive_sha256": ARCHIVE_SHA256, "output": str(output), "host_calls": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_archive, args.out)))
