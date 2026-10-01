#!/usr/bin/env python3
"""Publication contract for an optional, independently selected brand gallery.

Missing catalog or enabled=false selects no files. Enabled catalogs require
verified items, asset hashes/dimensions, explicit per-file source and rights,
and local request/response evidence matching declared MCP tools. This verifies
record consistency, not artistic quality or that a supplied trace is authentic.
Review provenance and visual quality before enabling publication. No networking.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zlib

import validate_collection as common

SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
COMMIT = re.compile(r"[0-9a-fA-F]{40}\Z")
SVG_TAGS = {"svg", "g", "defs", "path", "rect", "circle", "ellipse", "line",
            "polyline", "polygon", "linearGradient", "radialGradient", "stop",
            "clipPath", "mask", "use", "title", "desc"}
MAX_METADATA = 1024 * 1024
DEFAULT = {"schema_version": 1, "enabled": False, "items": []}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def require(obj, fields, where, problems):
    for key in fields:
        if not nonempty(obj.get(key)):
            problems.append(f"{where}.{key}: nonempty string required")


def rows(obj, field, where, problems):
    value = obj.get(field)
    if not isinstance(value, list) or not value:
        problems.append(f"{where}.{field}: nonempty array required")
        return []
    result = []
    for i, row in enumerate(value):
        if not isinstance(row, dict):
            problems.append(f"{where}.{field}[{i}]: object required")
        else:
            result.append(row)
    return result


def select(raw, root, selected, where, problems, local_only=False):
    problems.extend(common.link_problems(raw, root, where, external=not local_only))
    target = common.local_file(raw, root)
    if target:
        selected.add(target.relative_to(root).as_posix())
    return target


def source_check(source, root, selected, where, problems):
    if not isinstance(source, dict):
        problems.append(f"{where}: per-file source object or source_id required")
        return
    select(source.get("url"), root, selected, where + ".url", problems)
    commit = source.get("commit")
    digest = source.get("sha256", source.get("original_source_sha256"))
    if commit is not None:
        if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
            problems.append(f"{where}.commit: full 40-digit commit required")
        elif commit.lower() not in str(source.get("url", "")).lower():
            problems.append(f"{where}.url: source URL must pin recorded commit")
    elif not isinstance(digest, str) or not SHA256.fullmatch(digest):
        problems.append(f"{where}: immutable commit or original source SHA-256 required")
    target = common.local_file(source.get("url"), root)
    if target and digest and hashlib.sha256(target.read_bytes()).hexdigest() != str(digest).lower():
        problems.append(f"{where}: original source SHA-256 mismatch")


def metadata_text(data, where):
    # Metadata can store ASCII/UTF-8 or TIFF UTF-16 descriptions. Diagnostics
    # contain only categories, never the possibly private value.
    result = common.sensitive_issues(data.decode("utf-8", "replace"), where)
    result.extend(common.sensitive_issues(data.decode("latin-1"), where))
    if len(data) > 1:
        for encoding in ("utf-16-le", "utf-16-be"):
            result.extend(common.sensitive_issues(data.decode(encoding, "ignore"), where))
    return result


def inflate(data):
    decoder = zlib.decompressobj()
    value = decoder.decompress(data, MAX_METADATA + 1)
    if len(value) > MAX_METADATA or decoder.unconsumed_tail or not decoder.eof:
        raise ValueError("oversized or invalid compressed metadata")
    return value


def png_check(data, where):
    problems = []
    dims = None
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None, [f"{where}: invalid PNG signature"]
    offset, ended, image_data = 8, False, False
    try:
        while offset < len(data):
            length = struct.unpack_from(">I", data, offset)[0]
            tag = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + length]
            if len(tag) != 4 or len(payload) != length or offset + length + 12 > len(data):
                raise ValueError("truncated chunk")
            crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
            if zlib.crc32(tag + payload) & 0xffffffff != crc:
                raise ValueError("CRC mismatch")
            if offset == 8 and tag != b"IHDR":
                raise ValueError("IHDR must be first")
            if tag == b"IHDR":
                if dims is not None or length != 13:
                    raise ValueError("invalid IHDR")
                dims = struct.unpack_from(">II", payload)
                if not all(dims):
                    raise ValueError("zero dimensions")
            elif tag == b"IDAT":
                image_data = True
            elif tag == b"tEXt":
                problems.extend(metadata_text(payload, where + ".PNG metadata"))
            elif tag == b"zTXt":
                keyword, value = payload.split(b"\0", 1)
                if not value or value[0] != 0:
                    raise ValueError("invalid zTXt")
                problems.extend(metadata_text(keyword + b" " + inflate(value[1:]), where + ".PNG metadata"))
            elif tag == b"iTXt":
                keyword, rest = payload.split(b"\0", 1)
                flag, method = rest[0], rest[1]
                language, translated, value = rest[2:].split(b"\0", 2)
                if flag not in (0, 1) or method != 0:
                    raise ValueError("invalid iTXt")
                value = inflate(value) if flag else value
                problems.extend(metadata_text(keyword + b" " + language + b" " + translated + b" " + value,
                                              where + ".PNG metadata"))
            elif tag == b"eXIf":
                problems.extend(metadata_text(payload, where + ".EXIF metadata"))
                # Reject explicit GPS metadata, which is unnecessary for logos.
                order = "<" if payload[:2] == b"II" else ">" if payload[:2] == b"MM" else None
                if not order or len(payload) < 8:
                    raise ValueError("invalid EXIF")
                pos = struct.unpack_from(order + "I", payload, 4)[0]
                count = struct.unpack_from(order + "H", payload, pos)[0]
                if pos + 2 + count * 12 > len(payload):
                    raise ValueError("invalid EXIF IFD")
                if any(struct.unpack_from(order + "H", payload, pos + 2 + i * 12)[0] == 0x8825
                       for i in range(count)):
                    problems.append(f"{where}: EXIF GPS metadata forbidden")
            elif tag == b"IEND":
                if length or offset + 12 != len(data):
                    raise ValueError("invalid end or trailing bytes")
                ended = True
            offset += length + 12
        if not ended or not image_data or dims is None:
            raise ValueError("missing PNG structural chunks")
    except (ValueError, IndexError, struct.error, zlib.error):
        problems.append(f"{where}: malformed PNG or metadata")
    return dims, problems


def svg_check(data, where):
    problems = []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        return None, [f"{where}: SVG must be UTF-8"]
    problems.extend(common.sensitive_issues(text, where))
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I) or re.search(r"<\?(?!xml\s)", text, re.I):
        return None, problems + [f"{where}: DTD, entities or processing instructions forbidden"]
    try:
        doc = ET.fromstring(text)
    except ET.ParseError:
        return None, problems + [f"{where}: invalid SVG XML"]
    if doc.tag != "{http://www.w3.org/2000/svg}svg":
        problems.append(f"{where}: SVG namespace/root required")
    ids = {element.get("id") for element in doc.iter() if element.get("id")}
    if len(ids) != sum(bool(element.get("id")) for element in doc.iter()):
        problems.append(f"{where}: duplicate SVG id")
    for element in doc.iter():
        tag = element.tag.split("}")[-1]
        if tag not in SVG_TAGS or (element.tag.startswith("{") and
                                  not element.tag.startswith("{http://www.w3.org/2000/svg}")):
            problems.append(f"{where}: SVG contains unsupported or active element")
        for raw_key, value in element.attrib.items():
            key = raw_key.split("}")[-1].lower()
            if raw_key == "{http://www.w3.org/XML/1998/namespace}base":
                problems.append(f"{where}: SVG xml:base forbidden")
            if key.startswith("on"):
                problems.append(f"{where}: SVG event attribute forbidden")
            if key in ("href", "src"):
                if not value.startswith("#") or value[1:] not in ids:
                    problems.append(f"{where}: SVG reference must resolve to an internal id")
            if key in ("style", "class") and ("\\" in value or "/*" in value or "@" in value):
                problems.append(f"{where}: escaped or external SVG style forbidden")
            if re.search(r"(?:javascript|data|https?|file)\s*:|//|@import|expression\s*\(", value, re.I):
                problems.append(f"{where}: external or active SVG attribute forbidden")
            for match in re.finditer(r"url\s*\(([^)]*)\)", value, re.I):
                ref = match.group(1).strip().strip("\"'")
                if not ref.startswith("#") or ref[1:] not in ids:
                    problems.append(f"{where}: SVG paint reference must resolve to an internal id")
    try:
        viewbox = [float(v) for v in re.split(r"[\s,]+", doc.attrib["viewBox"].strip())]
        if len(viewbox) != 4 or not all(math.isfinite(v) for v in viewbox) or min(viewbox[2:]) <= 0:
            raise ValueError("invalid viewBox")
    except (KeyError, ValueError):
        problems.append(f"{where}: finite positive SVG viewBox required")
        viewbox = None
    return viewbox, sorted(set(problems))


def observed_tools(value):
    found = set()
    if isinstance(value, list):
        for row in value:
            found.update(observed_tools(row))
    elif isinstance(value, dict):
        name = value.get("tool", value.get("tool_name", value.get("name", value.get("method"))))
        response = value.get("response", value.get("result"))
        request = any(key in value for key in ("request", "arguments", "args", "input", "params"))
        success = (isinstance(response, (dict, list)) and bool(response) and value.get("success") is not False)
        if isinstance(response, dict):
            success = success and response.get("success") is not False and response.get("isError") is not True
            success = success and response.get("status") not in ("error", "failed", "failure")
        if nonempty(name) and request and success:
            found.add(name)
        for child in value.values():
            if isinstance(child, (dict, list)):
                found.update(observed_tools(child))
    return found


def _read_and_validate(root, catalog_path=None):
    """Return (catalog, selected repo-relative paths, problems), fail closed."""
    root = Path(root).resolve()
    path = Path(catalog_path).resolve() if catalog_path else root / "brand-gallery.json"
    selected, problems = set(), []
    if not path.exists():
        return dict(DEFAULT), selected, []
    if not path.resolve().is_relative_to(root):
        return {}, selected, ["brands: catalog must remain within public root"]
    catalog = common.read_json(path, "brands", problems)
    if not isinstance(catalog, dict):
        return {}, selected, problems + ["brands: object required"]
    if type(catalog.get("schema_version")) is not int or catalog["schema_version"] != 1:
        problems.append("brands.schema_version: integer 1 required")
    if type(catalog.get("enabled")) is not bool:
        return catalog, selected, problems + ["brands.enabled: boolean required"]
    if not catalog["enabled"]:
        return catalog, selected, problems
    problems.extend(common.scan_values(catalog, "brands"))
    require(catalog, ("title", "description", "updated_at"), "brands", problems)
    seen = set()
    for index, item in enumerate(rows(catalog, "items", "brands", problems)):
        where = f"brands.items[{index}]"
        slug = item.get("slug")
        if not nonempty(slug) or not common.SLUG.fullmatch(slug) or slug in seen:
            problems.append(f"{where}.slug: safe unique slug required")
        seen.add(slug if isinstance(slug, str) else str(index))
        require(item, ("title", "family", "summary", "verified_at"), where, problems)
        if item.get("status") != "verified":
            problems.append(f"{where}.status: only verified items may publish")
        try:
            verified = item["verified_at"]
            date.fromisoformat(verified) if "T" not in verified else datetime.fromisoformat(verified.replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            problems.append(f"{where}.verified_at: ISO date required")
        for field in ("software", "contributors", "limitations"):
            value = item.get(field)
            if not isinstance(value, list) or not value or not all(nonempty(v) for v in value):
                problems.append(f"{where}.{field}: nonempty string array required")
        prompt = item.get("prompt")
        if not isinstance(prompt, dict):
            problems.append(f"{where}.prompt: object required")
        else:
            require(prompt, ("text", "note"), where + ".prompt", problems)
            if prompt.get("kind") not in ("original", "reusable"):
                problems.append(f"{where}.prompt.kind: original or reusable required")
        for field, required in (("environment", ("label", "value")), ("tools", ("name", "description")),
                                ("steps", ("title", "description")), ("checks", ("name", "result", "observed"))):
            for row in rows(item, field, where, problems):
                require(row, required, where + "." + field, problems)
                if field == "checks" and row.get("result") not in ("pass", "fail", "unknown", "not_run"):
                    problems.append(f"{where}.checks: invalid result")
                if field == "steps" and row.get("image"):
                    image = row["image"]
                    if not isinstance(image, dict):
                        problems.append(f"{where}.steps.image: image object with src and alt required")
                    else:
                        require(image, ("src", "alt"), where + ".steps.image", problems)
                        select(image.get("src"), root, selected, where + ".steps.image", problems, local_only=True)
        environment = [row for row in item.get("environment", []) if isinstance(row, dict)] if isinstance(item.get("environment"), list) else []
        def recorded_version(label):
            matching = [row for row in environment if re.search(label, str(row.get("label", "")), re.I)]
            return any(re.search(r"\d+(?:\.\d+)+", str(row.get("value", ""))) and
                       not common.UNKNOWN.search(str(row.get("value", ""))) for row in matching)
        for software in item.get("software", []) if isinstance(item.get("software"), list) else []:
            if isinstance(software, str) and not recorded_version(re.escape(software)):
                problems.append(f"{where}.environment: actual software version required")
        for label in (r"adapter|适配器", r"core|核心"):
            if not recorded_version(label):
                problems.append(f"{where}.environment: actual adapter and Core versions required")
        rights = {}
        for row in rows(item, "rights", where, problems):
            require(row, ("id", "holder", "license", "scope", "url", "notice"), where + ".rights", problems)
            if not isinstance(row.get("id"), str) or not common.SLUG.fullmatch(row["id"]):
                problems.append(f"{where}.rights.id: safe lowercase slug required")
            if isinstance(row.get("id"), str) and row["id"] in rights:
                problems.append(f"{where}.rights: duplicate id")
            if isinstance(row.get("id"), str):
                rights[row["id"]] = row
            select(row.get("url"), root, selected, where + ".rights.url", problems)
        source_map = {}
        for row in rows(item, "sources", where, problems):
            require(row, ("label", "url"), where + ".sources", problems)
            source_check(row, root, selected, where + ".sources", problems)
            if nonempty(row.get("id")):
                if row["id"] in source_map:
                    problems.append(f"{where}.sources: duplicate id")
                source_map[row["id"]] = row
        variant_paths = set()
        for i, variant in enumerate(rows(item, "variants", where, problems)):
            loc = f"{where}.variants[{i}]"
            require(variant, ("label", "url", "format", "sha256"), loc, problems)
            ids = variant.get("rights_ids", [variant["rights_id"]] if "rights_id" in variant else [])
            if not isinstance(ids, list) or not ids or any(not isinstance(v, str) or v not in rights for v in ids):
                problems.append(f"{loc}: every asset requires known rights_ids")
            source_id = variant.get("source_id")
            source = variant.get("source", source_map.get(source_id) if isinstance(source_id, str) else None)
            source_check(source, root, selected, loc + ".source", problems)
            target = select(variant.get("url"), root, selected, loc + ".url", problems, local_only=True)
            if not target:
                continue
            variant_paths.add(target)
            data = target.read_bytes()
            if type(variant.get("bytes")) is not int or variant["bytes"] != len(data):
                problems.append(f"{loc}: actual asset byte count mismatch")
            if not SHA256.fullmatch(str(variant.get("sha256", ""))) or hashlib.sha256(data).hexdigest() != str(variant.get("sha256")).lower():
                problems.append(f"{loc}: actual asset SHA-256 mismatch")
            fmt = str(variant.get("format", "")).lower()
            if fmt != target.suffix[1:].lower() or fmt not in ("svg", "png"):
                problems.append(f"{loc}: supported SVG/PNG extension must match format")
            elif fmt == "png":
                dims, issues = png_check(data, loc)
                problems.extend(issues)
                if (type(variant.get("width")) is not int or type(variant.get("height")) is not int
                        or dims != (variant.get("width"), variant.get("height"))):
                    problems.append(f"{loc}: actual PNG dimensions mismatch")
            else:
                viewbox, issues = svg_check(data, loc)
                problems.extend(issues)
                supplied = variant.get("viewBox", variant.get("viewbox"))
                if not isinstance(supplied, list) or viewbox != supplied:
                    problems.append(f"{loc}: declared SVG viewBox must match parsed asset")
        previews = item.get("previews")
        if not isinstance(previews, dict):
            problems.append(f"{where}.previews: light and dark previews required")
        else:
            for theme in ("light", "dark"):
                preview = previews.get(theme)
                if not isinstance(preview, dict):
                    problems.append(f"{where}.previews.{theme}: preview required")
                    continue
                require(preview, ("src", "alt"), where + ".previews." + theme, problems)
                target = select(preview.get("src"), root, selected, where + ".previews." + theme, problems, local_only=True)
                if target and target not in variant_paths:
                    problems.append(f"{where}.previews.{theme}: preview must be a validated variant asset")
        observed, scoped = set(), nonempty(item.get("evidence_scope"))
        for evidence in rows(item, "evidence", where, problems):
            require(evidence, ("label", "url"), where + ".evidence", problems)
            target = select(evidence.get("url"), root, selected, where + ".evidence.url", problems)
            if target and target.suffix.lower() == ".json":
                value = common.read_json(target, where + ".evidence.JSON", problems)
                observed.update(observed_tools(value))
                if isinstance(value, dict):
                    scoped = scoped or nonempty(value.get("evidence_scope", value.get("scope")))
        declared = {row.get("name") for row in item.get("tools", []) if isinstance(row, dict) and nonempty(row.get("name"))}
        if not scoped or not declared or not declared.issubset(observed):
            problems.append(f"{where}.evidence: explicit scope and local successful MCP request/response records matching all tools required")
    for rel in sorted(selected):
        target = root / rel
        problems.extend(common.scan_text_file(target, root))
        problems.extend(common.document_link_problems(target, root))
        # Sources, process images and license/evidence links are publication
        # selections too. None can bypass binary metadata or SVG activity checks
        # simply by being outside variants. Original unsafe sources stay remote.
        if target.suffix.lower() == ".svg":
            problems.extend(svg_check(target.read_bytes(), "brands selected SVG")[1])
        elif target.suffix.lower() == ".png":
            problems.extend(png_check(target.read_bytes(), "brands selected PNG")[1])
    return catalog, selected, sorted(set(problems))


def read_and_validate(root, catalog_path=None):
    """Public fail-closed wrapper; malformed records never escape as exceptions."""
    try:
        return _read_and_validate(root, catalog_path)
    except (OSError, ValueError, TypeError, RecursionError, OverflowError):
        return {}, set(), ["brands: malformed or unreadable publication record"]


def validate(catalog_path, root=None):
    path = Path(catalog_path).resolve()
    return read_and_validate(root or path.parent, path)[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", nargs="?", default="brand-gallery.json")
    args = parser.parse_args()
    catalog, selected, problems = read_and_validate(Path(args.catalog).resolve().parent, Path(args.catalog).resolve())
    if problems:
        print("FAIL brand gallery publication contract")
        for problem in problems:
            print("  - " + problem)
        return 1
    print("PASS brand gallery publication contract" if catalog["enabled"] else "SKIP disabled brand gallery (zero public files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
