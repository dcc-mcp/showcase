"""Validate an atlas and render each asset without overwriting prior outputs."""

import copy
import hashlib
import json
import wave
from pathlib import Path

from dcc_mcp_core.skill import skill_entry, skill_error, skill_success
from reapy_boost import reascript_api as R

SAMPLE_RATE = 48000
MAX_ASSETS = 64
MAX_ASSET_FRAMES = SAMPLE_RATE * 120


def _wav_name(value):
    if (
        not isinstance(value, str)
        or not value
        or Path(value).name != value
        or any(char in value for char in ("$", "\\", ":"))
        or any(ord(char) < 32 for char in value)
        or Path(value).suffix.lower() != ".wav"
    ):
        raise ValueError("Unsafe asset target or source filename")
    return value


def _asset_map(assets):
    if not isinstance(assets, list) or not 1 <= len(assets) <= MAX_ASSETS:
        raise ValueError("An atlas and its source manifest require 1-64 assets")
    result = {}
    for asset in assets:
        identifier = asset.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in result:
            raise ValueError("Asset IDs must be nonempty and unique")
        result[identifier] = asset
    return result


def _validate(atlas, metadata):
    if atlas.get("sample_rate") != SAMPLE_RATE or metadata.get("sample_rate") != SAMPLE_RATE:
        raise ValueError("Atlas and source manifest must use 48 kHz")
    assets = atlas["assets"]
    atlas_by_id = _asset_map(assets)
    source_by_id = _asset_map(metadata["assets"])
    if set(atlas_by_id) != set(source_by_id):
        raise ValueError("Atlas/source asset counts and IDs must match")
    targets = set()
    for asset in assets:
        target = _wav_name(asset["target"])
        if target.casefold() in targets:
            raise ValueError("Asset targets must be unique")
        targets.add(target.casefold())
        if any(type(asset[key]) is not int for key in ("frames", "start_frame", "end_frame", "channels")):
            raise ValueError("Atlas frame bounds and channels must be integers")
        if (
            asset["channels"] not in (1, 2)
            or not 1 <= asset["frames"] <= MAX_ASSET_FRAMES
            or asset["start_frame"] < 0
            or asset["end_frame"] > SAMPLE_RATE * 86400
            or asset["end_frame"] - asset["start_frame"] != asset["frames"]
        ):
            raise ValueError("Invalid atlas bounds")
        source = source_by_id[asset["id"]]
        for key in ("native_export_target_name", "native_export_target"):
            if _wav_name(source[key]) != target:
                raise ValueError("Atlas/source asset targets must match by ID")
        _wav_name(source["wav_path"])
        if "path" in source and _wav_name(source["path"]) != source["wav_path"]:
            raise ValueError("Source manifest paths disagree")
        if any(type(source[key]) is not int for key in ("frames", "channels", "sample_rate", "bit_depth")):
            raise ValueError("Source asset format values must be integers")
        if (
            source["frames"] != asset["frames"]
            or source["channels"] != asset["channels"]
            or source["sample_rate"] != SAMPLE_RATE
            or source["bit_depth"] != 24
        ):
            raise ValueError("Atlas/source sample formats and frame counts must match")
        digest = source.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Source asset hash must be a SHA-256 digest")
    ordered = sorted(assets, key=lambda asset: asset["start_frame"])
    if any(left["end_frame"] > right["start_frame"] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("Atlas asset regions must not overlap")
    if "tracks" in metadata:
        aliases = _asset_map(metadata["tracks"])
        if aliases != source_by_id:
            raise ValueError("Source manifest assets and tracks must describe the same assets")
    return assets


def _render_one(project, output, asset):
    target = output / asset["target"]
    if target.exists() or target.is_symlink():
        raise FileExistsError("Will not overwrite an existing asset render")
    for key, value in [
        ("RENDER_SETTINGS", 0),
        ("RENDER_BOUNDSFLAG", 0),
        ("RENDER_STARTPOS", asset["start_frame"] / SAMPLE_RATE),
        ("RENDER_ENDPOS", asset["end_frame"] / SAMPLE_RATE),
        ("RENDER_CHANNELS", asset["channels"]),
        ("RENDER_SRATE", SAMPLE_RATE),
        ("RENDER_TAILFLAG", 0),
        ("RENDER_ADDTOPROJ", 0),
        ("RENDER_NORMALIZE", 0),
        ("RENDER_DITHER", 16),
    ]:
        R.GetSetProjectInfo(project, key, value, True)
    for key, value in [
        ("RENDER_FILE", str(output)),
        ("RENDER_PATTERN", target.stem),
        ("RENDER_FORMAT", "evaw"),
        ("RENDER_FORMAT2", ""),
    ]:
        R.GetSetProjectInfo_String(project, key, value, True)
    R.Main_OnCommand(42230, 0)
    with wave.open(str(target), "rb") as audio:
        if (
            audio.getframerate() != SAMPLE_RATE
            or audio.getnchannels() != asset["channels"]
            or audio.getnframes() != asset["frames"]
            or audio.getsampwidth() != 3
        ):
            raise RuntimeError("Native render sample format/duration mismatch for " + asset["id"])
        pcm = audio.readframes(audio.getnframes())
    return {
        "id": asset["id"],
        "file": asset["target"],
        "frames": asset["frames"],
        "channels": asset["channels"],
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
    }


def _write_journal(path, report):
    # Replace atomically so an interrupted update retains the last checkpoint.
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temporary.replace(path)


@skill_entry
def main(project_dir: str):
    root = Path(project_dir).resolve()
    project = root / "Trail-and-Air.rpp"
    pointer, _, current, _ = R.EnumProjects(-1, "", 4096)
    if not project.is_file() or Path(current).resolve() != project:
        raise ValueError("Active REAPER project must match the audio atlas")
    if R.IsProjectDirty(pointer):
        raise RuntimeError("Save the active audio atlas before rendering")
    atlas = json.loads((root / "atlas.json").read_text(encoding="utf-8"))
    metadata = json.loads((root / "media/manifest.json").read_text(encoding="utf-8"))
    output = root / "renders"
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise FileExistsError("Render directory must be empty and must not be a symlink")
    assets = _validate(atlas, metadata)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    journal = root / "native-render-validation.json"
    report = {
        "host": "REAPER " + R.GetAppVersion(),
        "method": "Native REAPER offline region rendering through typed DCC-MCP",
        "status": "in_progress",
        "assets": results,
        "completed_count": 0,
        "total_count": len(assets),
        "failed_asset_id": None,
        "subjective_listening": "pending",
    }
    _write_journal(journal, report)
    failed_asset = None
    stage = "render"
    try:
        for asset in assets:
            failed_asset = asset["id"]
            results.append(_render_one(pointer, output, asset))
            report["completed_count"] = len(results)
            _write_journal(journal, report)
        failed_asset = None
        stage = "save_project"
        R.GetSetProjectInfo_String(pointer, "RENDER_FILE", "renders", True)
        R.Main_SaveProjectEx(pointer, str(project), 8)
        if R.IsProjectDirty(pointer) or Path(R.EnumProjects(-1, "", 4096)[2]).resolve() != project:
            raise RuntimeError("Native atlas save could not be verified")
        stage = "write_manifest"
        delivered = copy.deepcopy(metadata)
        rendered_by_id = {result["id"]: result for result in results}
        delivered["source_provenance"] = (
            "Original procedural sources generated by typed DCC-MCP; "
            "these delivery WAVs exported by native REAPER renderer"
        )
        for asset in delivered["assets"]:
            rendered = rendered_by_id[asset["id"]]
            asset["source_sha256"] = asset["sha256"]
            asset["sha256"] = rendered["sha256"]
            asset["native_pcm_sha256"] = rendered["pcm_sha256"]
            asset["wav_path"] = rendered["file"]
            asset["path"] = rendered["file"]
        if "tracks" in delivered:
            delivered["tracks"] = copy.deepcopy(delivered["assets"])
        (output / "manifest.json").write_text(json.dumps(delivered, indent=2), encoding="utf-8")
        report["status"] = "completed"
        _write_journal(journal, report)
    except Exception as exc:
        report.update(status="failed", failed_asset_id=failed_asset, stage=stage, error=str(exc))
        try:
            _write_journal(journal, report)
        except OSError as journal_error:
            report["journal_error"] = str(journal_error)
        return skill_error(
            "Native asset rendering failed: " + str(exc),
            "partial_render_failure",
            prompt="Inspect the journal and preserved outputs before retrying. Existing renders will not be overwritten.",
            project=str(project),
            output_dir=str(output),
            journal=str(journal),
            completed_count=len(results),
            failed_asset_id=failed_asset,
            stage=stage,
            results=results,
            remaining_asset_ids=[asset["id"] for asset in assets if asset["id"] not in {r["id"] for r in results}],
        )
    return skill_success(
        "All game audio assets exported by native REAPER",
        project=str(project),
        asset_count=len(results),
        sample_rate=SAMPLE_RATE,
        bit_depth=24,
        results=results,
        journal=str(journal),
    )
