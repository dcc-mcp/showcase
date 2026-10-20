"""Bounded read-only XCF parasite verification; never decodes or changes pixels.

Structure reference: https://developer.gimp.org/core/standards/xcf/
Native inspection remains the authority for the editable image/tree.
"""
import hashlib
import json
import re
import struct
from pathlib import Path

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_PROPERTY_BYTES = 1024 * 1024
MAX_LAYERS = 512
FORMULA_LAYERS = ("Analytic formula q", "Analytic formula delay", "Analytic formula time")


def require(value, message):
    if not value:
        raise RuntimeError(message)


class Reader:
    def __init__(self, data, start=0, end=None):
        self.data = data
        self.pos = start
        self.end = len(data) if end is None else end
        require(0 <= start <= self.end <= len(data), "Invalid XCF reader bounds")

    def take(self, size):
        require(0 <= size <= self.end - self.pos, "Truncated XCF metadata structure")
        out = self.data[self.pos:self.pos + size]
        self.pos += size
        return out

    def u32(self):
        return struct.unpack(">I", self.take(4))[0]

    def u64(self):
        return struct.unpack(">Q", self.take(8))[0]

    def string(self):
        size = self.u32()
        require(1 <= size <= 4096, "Invalid bounded XCF string size")
        raw = self.take(size)
        require(raw[-1:] == b"\0", "XCF string lacks terminator")
        return raw[:-1].decode("utf-8", errors="strict")

    def properties(self):
        parasites = {}
        for _ in range(128):
            kind, size = self.u32(), self.u32()
            require(size <= MAX_PROPERTY_BYTES, "XCF property exceeds readback bound")
            payload = self.take(size)
            if kind == 0:
                require(size == 0, "Invalid XCF property terminator")
                return parasites
            if kind != 21:
                continue
            reader = Reader(payload)
            while reader.pos < reader.end:
                require(len(parasites) < 256, "XCF parasite count exceeds bound")
                name, flags = reader.string(), reader.u32()
                require(name not in parasites, "Duplicate XCF parasite identity")
                parasites[name] = {"flags": flags, "data": reader.take(reader.u32())}
        raise RuntimeError("XCF property count exceeds bound")


def read_xcf_text_parasites(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "XCF readback requires a regular file")
    require(30 <= path.stat().st_size <= MAX_FILE_BYTES, "XCF exceeds readback size bound")
    data = path.read_bytes()
    reader = Reader(data)
    header = reader.take(14)
    require(header[:9] == b"gimp xcf " and header[-1:] == b"\0", "Invalid XCF header")
    require(header[9:10] == b"v" and header[10:13].isdigit(), "Unsupported XCF version tag")
    version = int(header[10:13])
    require(11 <= version <= 23, "Unsupported XCF version for bounded metadata readback")
    width, height, base, precision = [reader.u32() for _ in range(4)]
    reader.properties()
    offsets = []
    for _ in range(MAX_LAYERS + 1):
        offset = reader.u64()
        if offset == 0:
            break
        require(offset not in offsets and 30 <= offset < len(data), "Invalid XCF layer offset")
        offsets.append(offset)
    else:
        raise RuntimeError("XCF layer count exceeds bound")
    layers = {}
    for offset in offsets:
        layer = Reader(data, offset)
        layer.take(12)
        name = layer.string()
        require(name not in layers, "Duplicate XCF layer name prevents exact mapping")
        layers[name] = layer.properties()
    return {"version": version, "canvas": [width, height], "base_type": base,
            "precision": precision, "sha256": hashlib.sha256(data).hexdigest(), "layers": layers}


def verify_native_text_parasites(path, native_info):
    """Compare actual native bytes reports with independently read saved bytes."""
    saved = read_xcf_text_parasites(path)
    require(saved["canvas"] == [native_info["width"], native_info["height"]], "XCF canvas differs")
    metadata = native_info.get("metadata")
    require(isinstance(metadata, dict), "Native metadata inspection is required")
    entries = metadata.get("layer_parasites")
    require(isinstance(entries, list), "Native layer parasite inspection missing")
    native = {row["name"]: row["parasites"] for row in entries}
    require(len(native) == len(entries), "Native parasite layer names are ambiguous")
    matches = []
    for name, parasites in saved["layers"].items():
        expected = parasites.get("gimp-text-layer")
        if expected is None:
            continue
        found = [row for row in native.get(name, []) if row["name"] == "gimp-text-layer"]
        require(len(found) == 1, "Native saved text parasite missing: " + name)
        actual, raw = found[0], expected["data"]
        digest = hashlib.sha256(raw).hexdigest()
        require(actual["flags"] == expected["flags"] and actual["bytes"] == len(raw)
                and actual["sha256"] == digest, "Native parasite bytes differ: " + name)
        require(actual["text"] == raw[:16384].decode("utf-8", errors="replace")
                and actual["truncated"] is (len(raw) > 16384), "Native parasite preview differs: " + name)
        matches.append({"layer_name": name, "parasite_name": "gimp-text-layer", "bytes": len(raw),
                        "sha256": digest, "high_bit_byte_count": sum(value >= 128 for value in raw)})
    require(len(matches) == sum(row["is_text"] for row in native_info["layers"]),
            "Saved/native editable text parasite count differs")
    by_name = {row["layer_name"]: row for row in matches}
    require(all(name in by_name and by_name[name]["high_bit_byte_count"] > 0 for name in FORMULA_LAYERS),
            "Actual native formula parasites must exercise high-bit Unicode bytes")
    return {"status": "PASS_NATIVE_METADATA_EQUALS_SAVED_XCF_BYTES", "xcf_sha256": saved["sha256"],
            "matched_text_parasites": len(matches), "required_high_bit_formula_layers": list(FORMULA_LAYERS),
            "payloads": matches, "raw_payloads_in_public_receipt": False,
            "arbitrary_non_utf8_native_coverage_claimed": False}


def metadata_privacy_categories(native_info, private_markers=()):
    """Report categories/counts only; do not copy private values into a summary."""
    metadata = native_info.get("metadata")
    require(isinstance(metadata, dict), "Metadata is required for privacy review")
    text = json.dumps(metadata, ensure_ascii=False)
    patterns = {
        "filesystem_path_like_values": r"(?:/workspace/|/home/|/tmp/|file://|[A-Za-z]:\\)",
        "uuid_like_identifiers": r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b",
        "timestamp_fields": r"(?i)(?:CreateDate|ModifyDate|DateTime|MetadataDate|history.*when)",
        "author_or_contact_fields": r"(?i)(?:dc:creator|Artist|Author|OwnerName|CreatorContactInfo|email)",
        "source_filename_fields": r"(?i)(?:DocumentName|FileName|DerivedFrom|SourceFile|OriginalDocumentID)",
        "document_identifier_fields": r"(?i)(?:DocumentID|InstanceID|ImageUniqueID)",
        "software_fields": r"(?i)(?:CreatorTool|Software)",
        "font_hash_fields": r"\(fonthash\s",
    }
    counts = {name: len(re.findall(pattern, text)) for name, pattern in patterns.items()}
    counts["known_private_path_values"] = sum(text.count(marker) for marker in private_markers if marker)
    parasites = list(metadata.get("image_parasites", []))
    for layer in metadata.get("layer_parasites", []):
        parasites.extend(layer["parasites"])
    complete = not metadata.get("metadata_xml_truncated", True) and not any(
        row.get("truncated", True) for row in parasites
    )
    return {"status": "CATEGORIES_RECORDED_REVIEW_REQUIRED", "category_counts": counts,
            "detected_categories": [name for name, count in counts.items() if count],
            "returned_metadata_untruncated": complete, "raw_private_values_in_summary": False,
            "metadata_cleared": False, "publication_privacy_qualified": False}
