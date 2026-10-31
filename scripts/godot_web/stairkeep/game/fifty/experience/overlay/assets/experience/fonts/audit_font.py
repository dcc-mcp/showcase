"""Recheck UTF-8 source and bundled font cmap without starting Godot.

This intentionally audits a superset of visible text: every printable codepoint
in the candidate's GDScript, JSON, scene and project files. It proves neither
font loading nor settled layout/clipping. Run again after presenter edits.
"""
from pathlib import Path
import datetime
import hashlib
import json
import fontTools
from fontTools.ttLib import TTFont


def main():
    directory = Path(__file__).resolve().parent
    project = directory.parents[2]
    font_path = directory / "cjk-ui.otf"
    required = set(range(32, 127))
    files = []
    errors = []
    replacement_chars = []
    cjk_samples = []
    for path in sorted(project.rglob("*")):
        if path.suffix.lower() not in {".gd", ".json", ".tscn", ".godot"}:
            continue
        relative = path.relative_to(project)
        if any(part in {".godot", "vendor", "experience"} for part in relative.parts):
            continue
        data = path.read_bytes()
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            errors.append({"path": relative.as_posix(), "error": str(error)})
            continue
        required.update(ord(char) for char in text if ord(char) >= 32)
        if "\ufffd" in text:
            replacement_chars.append(relative.as_posix())
        cjk = "".join(char for char in text if 0x3400 <= ord(char) <= 0x9FFF)
        if cjk:
            cjk_samples.append({"path": relative.as_posix(), "sample": cjk[:56]})
        files.append({"path": relative.as_posix(), "sha256": hashlib.sha256(data).hexdigest()})
    with TTFont(font_path) as font:
        cmap = font.getBestCmap()
        missing = sorted(required - set(cmap))
        cjk_required = sorted(code for code in required if 0x3400 <= code <= 0x9FFF)
        report = {
            "schema": 1,
            "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scope": "Static UTF-8 and FontTools cmap coverage; source text is a superset of visible content",
            "font": "res://assets/experience/fonts/cjk-ui.otf",
            "font_sha256": hashlib.sha256(font_path.read_bytes()).hexdigest(),
            "font_bytes": font_path.stat().st_size,
            "family": font["name"].getDebugName(1),
            "fonttools_version": fontTools.__version__,
            "cmap_count": len(cmap),
            "required_codepoints": len(required),
            "required_cjk_codepoints": len(cjk_required),
            "required_cjk_text": "".join(chr(code) for code in cjk_required),
            "ascii_32_126_covered": all(code in cmap for code in range(32, 127)),
            "missing_count": len(missing),
            "missing": [{"codepoint": f"U+{code:04X}", "character": chr(code)} for code in missing],
            "source_utf8_decode_errors": errors,
            "source_replacement_character_files": replacement_chars,
            "source_cjk_samples": cjk_samples,
            "files": files,
            "status": "passed" if not (missing or errors or replacement_chars) else "failed",
            "diagnosis": {
                "malformed_utf8": "none detected" if not errors else "see errors",
                "unicode_replacement_character": "none detected" if not replacement_chars else "see files",
                "earlier_candidate_font_binding": "Theme set only default_font_size; no bundled CJK default_font before this experience revision",
                "existing_house_subsets_initial_missing": {"Dawnkeep Sans": 209, "Parcel Interface": 255, "Sanctuary Sans": 260},
                "initial_required_codepoints": 408,
                "initial_required_cjk_codepoints": 300,
                "interpretation": "Source Chinese decodes, existing narrow subsets are insufficient, and explicit bundled font binding is required. This does not prove every observed issue came from glyph coverage rather than loading or clipping."
            },
            "not_tested": ["Godot font import/loading", "actual rendered Chinese", "long dialogue clipping", "Web export glyph rendering", "browser input"],
            "software_installs": 0,
            "host_starts": 0,
        }
    (directory / "cmap-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["status", "required_codepoints", "required_cjk_codepoints", "missing_count", "ascii_32_126_covered"]}, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
