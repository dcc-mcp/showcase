#!/usr/bin/env python3
"""Validate the curated public collection and only its selected case files.

Usage: python scripts/validate_collection.py [collection.json] [--site _site]

This is a publication contract, not proof that a DCC run happened. It checks
traceable artifacts, explicit evidence boundaries, provenance and common public
data leaks. Screenshots still require a human review; remote URLs are not fetched.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import validate_entry


CASE_FIELDS = (
    "slug", "title", "subtitle", "software", "capabilities", "cover",
    "evidence_label", "evidence_scope", "summary", "goal", "prompt",
    "environment", "tools", "steps", "results", "checks", "limitations",
    "resources", "credits", "source", "verified_at", "model_attribution", "revision_notes",
)
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm"}
TEXT_EXT = {".md", ".json", ".txt", ".html", ".htm", ".css", ".js", ".py", ".ps1", ".sh",
            ".xml", ".csv", ".yaml", ".yml", ".svg", ".obj", ".mtl"}
UNKNOWN = re.compile(r"unknown|unrecorded|not (?:recorded|published|disclosed)|"
                     r"未(?:公开|记录|知)|未知|无法核实", re.I)
PRIVATE_PATTERNS = (
    ("private filesystem path", re.compile(r"\b[A-Z]:[\\/]|\\\\[\w.-]+[\\/]|"
                                          r"/(?:Users|home)/[^/\s]+|file:///", re.I)),
    ("private execution path", re.compile(
        r"(?<![\w./-])/(?:workspace|tmp|root)(?=/|$|[\s\"'<>),;])", re.I)),
    ("private host name", re.compile(r"\bHALLONG(?:-[A-Z0-9_-]+)?\b|"
                                    r"\b(?:localhost|[\w.-]+\.(?:local|internal|lan))\b", re.I)),
    ("credential token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|"
                                   r"github_pat_[A-Za-z0-9_]{20,}|"
                                   r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|"
                                   r"AKIA[A-Z0-9]{16})\b|"
                                   r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("credential assignment", re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[=:]\s*[\"']?"
        r"(?!unknown\b|unrecorded\b|redacted\b|none\b|null\b|false\b|true\b)"
        r"[A-Za-z0-9_+/=-]{12,}", re.I)),
    ("bearer credential", re.compile(r"\bBearer\s+[A-Za-z0-9_.+/=-]{16,}", re.I)),
)
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)")
PAGE_LINK = re.compile(r"\b(?:href|src|poster)\s*=\s*[\"']([^\"']+)[\"']", re.I)
MD_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?")


def sensitive_issues(text: str, location: str) -> list[str]:
    """Report categories and locations, never echo a potential secret."""
    problems = [f"{location}: contains {label}" for label, pattern in PRIVATE_PATTERNS
                if pattern.search(text)]
    for candidate in IPV4.findall(text):
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        # RFC1918 and loopback literals are private even outside a URL. Other
        # non-global four-part strings may be software versions, so require
        # an endpoint context for those.
        internal = address.is_loopback or any(address in ipaddress.ip_network(net)
                    for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
        if internal or (not address.is_global and re.search(
                r"(?:https?://|\b(?:host|server|ip)\s*[=:]\s*)" + re.escape(candidate), text, re.I)):
            problems.append(f"{location}: contains private network address")
            break
    return problems


def scan_values(value, location: str) -> list[str]:
    if isinstance(value, str):
        return sensitive_issues(value, location)
    if isinstance(value, list):
        return [problem for i, item in enumerate(value)
                for problem in scan_values(item, f"{location}[{i}]")]
    if isinstance(value, dict):
        found = []
        for key, item in value.items():
            found.extend(sensitive_issues(str(key), f"{location} key"))
            # Use a generic position for an unsafe key to avoid exposing it.
            name = key if not sensitive_issues(str(key), "key") else "[unsafe key]"
            found.extend(scan_values(item, f"{location}.{name}"))
        return found
    return []


def local_file(raw: str, root: Path) -> Path | None:
    """Resolve a repo-relative file without traversal, drive, or symlink escapes."""
    if not isinstance(raw, str) or not raw or any(ord(c) < 32 for c in raw):
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc:
        return None
    path = parsed.path
    for _ in range(4):
        decoded = unquote(path)
        if decoded == path:
            break
        path = decoded
    if (not path or "%" in path or "\\" in path or ":" in path
            or path.startswith("/") or any(not part or part.startswith(".") for part in path.split("/"))):
        return None
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        return None
    return target


def link_problems(raw, root: Path, location: str, external: bool = True) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        return [f"{location}: must be a nonempty link"]
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname
    except ValueError:
        return [f"{location}: malformed link"]
    if parsed.scheme or parsed.netloc:
        if (not external or parsed.scheme != "https" or not host
                or parsed.username is not None or parsed.password is not None
                or "." not in host or host.lower().endswith((".local", ".internal", ".lan"))):
            return [f"{location}: only public HTTPS or safe local files are allowed"]
        try:
            if not ipaddress.ip_address(host).is_global:
                return [f"{location}: private network endpoint is forbidden"]
        except ValueError:
            pass
        return sensitive_issues(raw, location)
    if local_file(raw, root) is None:
        return [f"{location}: local file is missing or path is unsafe"]
    return []


def read_json(path: Path, location: str, problems: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        problems.append(f"{location}: missing or unreadable JSON")
        return None


def nonempty_string(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def require_strings(obj: dict, fields: tuple[str, ...], location: str, problems: list[str]) -> None:
    for field in fields:
        if not nonempty_string(obj.get(field)):
            problems.append(f"{location}.{field}: must be a nonempty string")


def object_rows(case: dict, field: str, fields: tuple[str, ...], location: str,
                problems: list[str]) -> list[dict]:
    rows = case.get(field)
    if not isinstance(rows, list) or not rows:
        problems.append(f"{location}.{field}: must be a nonempty array")
        return []
    valid = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(f"{location}.{field}[{i}]: must be an object")
            continue
        require_strings(row, fields, f"{location}.{field}[{i}]", problems)
        valid.append(row)
    return valid


def selected_manifest(entry: Path, location: str, root: Path,
                      problems: list[str]) -> set[Path]:
    """Check safety before invoking the existing artifact/hash validator."""
    manifest = read_json(entry / "manifest.json", f"{location}.manifest", problems)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list) or not manifest["files"]:
        problems.append(f"{location}.manifest: requires a nonempty files array")
        return set()
    assets = set()
    safe = True
    for i, row in enumerate(manifest["files"]):
        where = f"{location}.manifest.files[{i}]"
        if not isinstance(row, dict):
            problems.append(f"{where}: must be an object")
            safe = False
            continue
        raw = row.get("path")
        target = local_file(raw, entry)
        if target is None or not target.is_relative_to(root.resolve()):
            problems.append(f"{where}: missing file or unsafe artifact path")
            safe = False
            continue
        assets.add(target)
        if not isinstance(row.get("bytes"), int) or isinstance(row.get("bytes"), bool) or row["bytes"] < 0:
            problems.append(f"{where}: bytes must be a nonnegative integer")
            safe = False
        if not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", row["sha256"]):
            problems.append(f"{where}: sha256 must be a full 64-digit hash")
            safe = False
        if target.suffix.lower() in {".png", ".jpg", ".jpeg"} and not isinstance(row.get("width"), int):
            problems.append(f"{where}: image width must be an integer")
            safe = False
    if safe:
        try:
            for problem in validate_entry.validate(str(entry)):
                # The legacy checker includes artifact paths in diagnostics.
                # Do not echo an unsafe value if a malicious fixture adds one.
                if sensitive_issues(problem, location):
                    problems.append(f"{location}: existing entry contract contains unsafe metadata")
                else:
                    problems.append(problem)
        except (OSError, TypeError, ValueError, AttributeError):
            problems.append(f"{location}: existing entry validation could not read the case contract")
    return assets


def scan_text_file(path: Path, root: Path) -> list[str]:
    if path.suffix.lower() not in TEXT_EXT and path.name != "LICENSE":
        return []
    location = path.relative_to(root).as_posix()
    try:
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return [f"{location}: public text must be readable UTF-8"]
    return sensitive_issues(content, location)


def document_link_problems(path: Path, root: Path) -> list[str]:
    """Resolve a document's legitimate sibling links within the public root."""
    if path.suffix.lower() not in {".md", ".html", ".htm"}:
        return []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return []  # The text audit already reports unreadable public files.
    links = PAGE_LINK.findall(text)
    if path.suffix.lower() == ".md":
        links.extend(MD_LINK.findall(text))
    problems = []
    for i, raw in enumerate(links):
        location = f"{path.relative_to(root).as_posix()}.link[{i}]"
        if raw.startswith("#"):
            continue
        try:
            parsed = urlsplit(raw)
        except ValueError:
            problems.append(f"{location}: malformed link")
            continue
        if parsed.scheme or parsed.netloc:
            problems.extend(link_problems(raw, root, location))
            continue
        # Reports can reference a selected sibling case via ../, but never
        # escape the public root or use encoded path tricks or Windows paths.
        if (not parsed.path or parsed.path.startswith("/") or "%" in parsed.path
                or "\\" in parsed.path or ":" in parsed.path
                or any(part.startswith(".") and part not in (".", "..") for part in parsed.path.split("/"))
                or any(ord(c) < 32 for c in raw)):
            problems.append(f"{location}: unsafe local document link")
            continue
        target = (path.parent / parsed.path).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.is_relative_to(root) or not target.is_file():
            problems.append(f"{location}: local document file is missing or escapes the public root")
    return problems


def validate(collection_path: str | Path, root: str | Path | None = None) -> list[str]:
    """Return publication-contract problems without scanning unselected cases."""
    collection_path = Path(collection_path).resolve()
    root = Path(root).resolve() if root is not None else collection_path.parent
    problems: list[str] = []
    collection = read_json(collection_path, "collection", problems)
    if not isinstance(collection, dict):
        return problems + ["collection: must be an object"]
    problems.extend(scan_values(collection, "collection"))
    if collection.get("schema_version") != 1 or isinstance(collection.get("schema_version"), bool):
        problems.append("collection.schema_version: expected integer 1")
    cases = collection.get("cases")
    if not isinstance(cases, list) or not cases:
        return problems + ["collection.cases: must be a nonempty array"]
    seen = set()
    media: list[tuple[Path, str]] = []
    inventoried: set[Path] = set()
    text_files: set[Path] = set()
    for i, case in enumerate(cases):
        where = f"cases[{i}]"
        if not isinstance(case, dict):
            problems.append(f"{where}: must be an object")
            continue
        for key in CASE_FIELDS:
            if key not in case:
                problems.append(f"{where}: missing required field {key}")
        require_strings(case, ("title", "subtitle", "evidence_label", "evidence_scope",
                               "summary", "goal", "verified_at"), where, problems)
        slug = case.get("slug")
        if not isinstance(slug, str) or not SLUG.fullmatch(slug) or len(slug) > 80:
            problems.append(f"{where}.slug: expected a safe lowercase slug")
        elif slug in seen:
            problems.append(f"{where}.slug: duplicate slug")
        else:
            seen.add(slug)
            entry = (root / "docs" / "showcase" / slug).resolve()
            if not entry.is_relative_to(root) or not entry.is_dir():
                problems.append(f"{where}: selected case directory is missing or unsafe")
            else:
                inventoried.update(selected_manifest(entry, where, root, problems))
                # Only this case can be deployed by the curated collection.
                for path in entry.rglob("*"):
                    if path.is_file():
                        if not path.resolve().is_relative_to(entry):
                            problems.append(f"{where}: selected case contains a symlink escape")
                        else:
                            text_files.add(path.resolve())
        for field in ("software", "capabilities", "limitations"):
            value = case.get(field)
            if not isinstance(value, list) or not value or any(not nonempty_string(v) for v in value):
                problems.append(f"{where}.{field}: requires a nonempty array of strings")
        prompt = case.get("prompt")
        if not isinstance(prompt, dict):
            problems.append(f"{where}.prompt: must be an object")
        else:
            require_strings(prompt, ("kind", "text", "note"), f"{where}.prompt", problems)
            kind = prompt.get("kind")
            if kind not in ("original", "reusable"):
                problems.append(f"{where}.prompt.kind: expected original or reusable")
            elif nonempty_string(prompt.get("note")):
                label = r"原始|原话|original|verbatim" if kind == "original" else r"复用|复现|改写|reusable|adapted"
                if not re.search(label, prompt["note"], re.I):
                    problems.append(f"{where}.prompt.note: must explicitly label the prompt kind")
        if "model_attribution" in case:
            attribution = object_rows(case, "model_attribution",
                                      ("stage", "model", "reasoning_effort", "record_status", "basis", "scope"),
                                      where, problems)
            stages = set()
            for row in attribution:
                stage = row.get("stage")
                if isinstance(stage, str):
                    if stage in stages:
                        problems.append(f"{where}.model_attribution: duplicate stage")
                    stages.add(stage)
                status = row.get("record_status")
                # No receipt binding format is implemented. Reject the status
                # rather than accepting a free-text claim as result-bound proof.
                if status not in ("unknown", "configured"):
                    problems.append(f"{where}.model_attribution: invalid record_status")
                if status == "unknown" and any(not UNKNOWN.search(str(row.get(field, "")))
                                               for field in ("model", "reasoning_effort")):
                    problems.append(f"{where}.model_attribution: unknown record requires unknown model and effort")
                if status == "configured" and any(UNKNOWN.search(str(row.get(field, "")))
                                                                   for field in ("model", "reasoning_effort")):
                    problems.append(f"{where}.model_attribution: attributed record requires explicit model and effort")
        if "revision_notes" in case:
            revision_notes = object_rows(case, "revision_notes", ("version", "date", "change"), where, problems)
            for row in revision_notes:
                try:
                    date.fromisoformat(row.get("date", ""))
                except (ValueError, TypeError):
                    problems.append(f"{where}.revision_notes: invalid date")
        environment = object_rows(case, "environment", ("label", "value"), where, problems)
        for software in case.get("software", []) if isinstance(case.get("software"), list) else []:
            if not isinstance(software, str):
                continue
            matching = [row for row in environment if software.casefold() in
                        (str(row.get("label", "")) + " " + str(row.get("value", ""))).casefold()]
            if not matching or not any(UNKNOWN.search(str(row.get("value", ""))) or
                                       re.search(r"\b\d+(?:\.\d+)*\b", re.sub(
                                           re.escape(software), "", str(row.get("value", "")), flags=re.I))
                                       for row in matching):
                problems.append(f"{where}.environment: each software requires a version or explicit unknown value")
        for label in (r"adapter|适配器", r"core|核心"):
            rows = [row for row in environment if re.search(label, str(row.get("label", "")), re.I)]
            if not rows or not any(UNKNOWN.search(str(row.get("value", ""))) or
                                   re.search(r"\d", str(row.get("value", ""))) for row in rows):
                problems.append(f"{where}.environment: adapter and core versions require recorded or explicit unknown values")
        object_rows(case, "tools", ("name", "description"), where, problems)
        steps = object_rows(case, "steps", ("title", "description"), where, problems)
        results = object_rows(case, "results", ("src", "alt", "caption"), where, problems)
        images = [(case.get("cover"), f"{where}.cover")]
        images.extend((step["image"], f"{where}.steps[{n}].image")
                      for n, step in enumerate(steps) if "image" in step)
        images.extend((result, f"{where}.results[{n}]") for n, result in enumerate(results))
        for image, location in images:
            if not isinstance(image, dict):
                problems.append(f"{location}: must be an image object")
                continue
            require_strings(image, ("src", "alt"), location, problems)
            problems.extend(link_problems(image.get("src"), root, f"{location}.src", external=False))
            target = local_file(image.get("src"), root)
            if target is not None:
                if target.suffix.lower() not in MEDIA_EXT:
                    problems.append(f"{location}.src: expected a supported media file")
                media.append((target, location))
        checks = object_rows(case, "checks", ("name", "result", "observed"), where, problems)
        for n, check in enumerate(checks):
            if check.get("result") not in ("pass", "fail", "unknown", "not_run"):
                problems.append(f"{where}.checks[{n}].result: expected pass, fail, unknown or not_run")
        for n, resource in enumerate(object_rows(case, "resources", ("label", "url"), where, problems)):
            problems.extend(link_problems(resource.get("url"), root, f"{where}.resources[{n}].url"))
            path = local_file(resource.get("url"), root)
            if path is not None:
                text_files.add(path)
        credits = case.get("credits")
        if not isinstance(credits, dict):
            problems.append(f"{where}.credits: must be an object")
        else:
            require_strings(credits, ("author", "license", "note"), f"{where}.credits", problems)
        source = case.get("source")
        if not isinstance(source, dict):
            problems.append(f"{where}.source: must be an object")
        else:
            require_strings(source, ("url", "commit"), f"{where}.source", problems)
            problems.extend(link_problems(source.get("url"), root, f"{where}.source.url"))
            commit = source.get("commit")
            if not isinstance(commit, str) or not SHA.fullmatch(commit):
                problems.append(f"{where}.source.commit: expected an immutable full 40-digit commit SHA")
            elif commit.lower() not in str(source.get("url", "")).lower():
                problems.append(f"{where}.source.url: must pin the recorded commit")
            if not str(source.get("url", "")).startswith("https://"):
                problems.append(f"{where}.source.url: provenance must use public HTTPS")
        if nonempty_string(case.get("verified_at")):
            try:
                value = case["verified_at"]
                date.fromisoformat(value) if "T" not in value else datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                problems.append(f"{where}.verified_at: expected an ISO date or timestamp")
    for target, location in media:
        if target not in inventoried:
            problems.append(f"{location}.src: media is absent from selected case artifact manifests")
    for path in sorted(text_files):
        problems.extend(scan_text_file(path, root))
        problems.extend(document_link_problems(path, root))
    return sorted(set(problems))


def validate_site(site_path: str | Path) -> list[str]:
    """Audit generated public text and links, without reading unused repo files."""
    root = Path(site_path).resolve()
    if not root.is_dir():
        return ["site: output directory is missing"]
    problems = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(root):
            problems.append("site: output contains a symlink escape")
            continue
        problems.extend(scan_text_file(path, root))
        problems.extend(document_link_problems(path, root))
    return sorted(set(problems))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collection", nargs="?", default="collection.json")
    parser.add_argument("--site", help="also audit the generated site directory")
    args = parser.parse_args(argv)
    problems = validate(args.collection)
    if args.site:
        problems.extend(validate_site(args.site))
    if problems:
        print("FAIL public collection contract")
        for problem in sorted(set(problems)):
            print(f"  - {problem}")
        return 1
    print("PASS public collection contract (selected cases, evidence boundaries, hashes, paths and privacy)")
    if args.site:
        print("PASS generated public site text and links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
