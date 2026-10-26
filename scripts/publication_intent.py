#!/usr/bin/env python3
"""Require an explicit gallery decision for every complete showcase entry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_collection import SLUG, nonempty_string, scan_values


def validate(root: str | Path, cases: list[dict]) -> tuple[list[str], list[str]]:
    root = Path(root).resolve()
    entries = root / "docs" / "showcase"
    problems: list[str] = []
    complete: set[str] = set()
    if (entries.is_symlink() or not entries.is_dir()
            or not entries.resolve().is_relative_to(root)):
        return ["publication intent: showcase directory is missing or unsafe"], []
    for entry in sorted(entries.iterdir()):
        if entry.is_symlink() or not entry.resolve().is_relative_to(entries.resolve()):
            problems.append("publication intent: showcase entries must not be symlinks")
            continue
        if not entry.is_dir():
            continue
        required = [entry / name for name in ("README.md", "manifest.json", "validation.json")]
        if any(path.is_symlink() for path in required):
            problems.append("publication intent: entry metadata must not be symlinks")
            continue
        if all(path.is_file() for path in required):
            if not SLUG.fullmatch(entry.name) or len(entry.name) > 80:
                problems.append("publication intent: complete entry has an unsafe slug")
            else:
                complete.add(entry.name)

    selected: set[str] = set()
    if not isinstance(cases, list):
        return problems + ["publication intent: collection.cases must be an array"], []
    for case in cases:
        slug = case.get("slug") if isinstance(case, dict) else None
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or len(slug) > 80:
            problems.append("publication intent: selected case has an unsafe slug")
        elif slug in selected:
            problems.append(f"publication intent: duplicate selected slug {slug}")
        else:
            selected.add(slug)

    path = root / "unlisted-cases.json"
    registry = {"schema_version": 1, "cases": []}
    if path.is_symlink():
        return problems + ["unlisted-cases.json must not be a symlink"], []
    if path.exists():
        try:
            registry = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return problems + ["unlisted-cases.json: unreadable JSON"], []
    if (not isinstance(registry, dict) or type(registry.get("schema_version")) is not int
            or registry.get("schema_version") != 1
            or not isinstance(registry.get("cases"), list)):
        return problems + ["unlisted-cases.json: expected schema_version 1 and cases array"], []
    problems.extend(scan_values(registry, "unlisted-cases.json"))
    unlisted: dict[str, dict] = {}
    for row in registry["cases"]:
        if not isinstance(row, dict) or set(row) != {"slug", "status", "reason"}:
            problems.append("unlisted-cases.json: each decision requires only slug, status and reason")
            continue
        slug = row["slug"]
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or len(slug) > 80:
            problems.append("unlisted-cases.json: unsafe slug")
            continue
        if slug in unlisted:
            problems.append(f"unlisted-cases.json: duplicate slug {slug}")
        unlisted[slug] = row
        if row["status"] not in ("review", "unlisted") or not nonempty_string(row["reason"]):
            problems.append(f"unlisted-cases.json: {slug} requires review/unlisted status and a reason")

    for slug in sorted(selected - complete):
        problems.append(f"publication intent: selected entry {slug} is missing or incomplete")
    for slug in sorted(set(unlisted) - complete):
        problems.append(f"publication intent: stale unlisted decision {slug}")
    for slug in sorted(selected & set(unlisted)):
        problems.append(f"publication intent: {slug} is both selected and unlisted")
    for slug in sorted(complete - selected - set(unlisted)):
        problems.append(f"publication intent: {slug} needs a collection.json entry or an explicit unlisted decision")
    if problems:
        return problems, []
    notes = [f"Publication intent: {len(selected)} selected; {len(unlisted)} deliberately unlisted complete cases."]
    notes.extend(f"Unlisted {slug} ({row['status']}): {row['reason']}"
                 for slug, row in sorted(unlisted.items()))
    return [], notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        collection = json.loads((args.root / "collection.json").read_text(encoding="utf-8-sig"))
        problems, notes = validate(args.root, collection.get("cases"))
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
        problems, notes = ["collection.json: missing or unreadable collection"], []
    for note in notes:
        print(note)
    for problem in problems:
        print("FAIL " + problem)
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
