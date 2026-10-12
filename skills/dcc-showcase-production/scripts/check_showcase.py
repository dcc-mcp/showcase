#!/usr/bin/env python3
"""Read-only evidence inventory. Never a visual, rights, or publication approval."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

SCHEMA = "dcc-showcase-production/v1"
STATUSES = {"passed", "failed", "not-tested", "blocked"}
STAGES = (
    "research", "reuse_discovery", "rights", "real_mcp", "save_reopen",
    "export_reopen", "recipe_rebuild", "continuous_frames", "visual_review",
    "audio_review", "browser_playback", "privacy", "locales",
)
INTERACTIVE = ("native_interaction", "web_playable")
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local_path(root, value):
    """Only repository-relative regular files; reject URL, traversal and symlink escape."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("expected a repository-relative POSIX file path")
    p = PurePosixPath(value)
    if p.is_absolute() or ".." in p.parts or urlsplit(value).scheme:
        raise ValueError("external or escaping file path")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("missing file or symlink escape")
    return path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def check_ref(root, ref, label, errors):
    if not isinstance(ref, dict) or not valid_hash(ref.get("sha256")):
        errors.append(f"{label}: expected path and lowercase SHA-256")
        return
    try:
        path = local_path(root, ref.get("path"))
        if digest(path) != ref["sha256"]:
            errors.append(f"{label}: SHA-256 mismatch")
    except (ValueError, OSError) as exc:
        errors.append(f"{label}: {exc}")


def inventory(root, case):
    slug = case.get("slug")
    if not isinstance(slug, str) or not slug or PurePosixPath(slug).name != slug or slug in {".", ".."} or "\\" in slug:
        raise ValueError("invalid case slug")
    entry = root / "docs" / "showcase" / slug
    errors, videos = [], set()
    for name in ("README.md", "manifest.json", "validation.json"):
        local_path(root, f"docs/showcase/{slug}/{name}")
    manifest = read_json(entry / "manifest.json")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise ValueError("manifest files must be an array")
    seen = set()
    for index, item in enumerate(manifest["files"]):
        label = f"manifest.files[{index}]"
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append(f"{label}: invalid file record")
            continue
        rel = item["path"]
        if rel in seen:
            errors.append(f"{label}: duplicate artifact")
        seen.add(rel)
        if PurePosixPath(rel).is_absolute() or ".." in PurePosixPath(rel).parts or "\\" in rel or urlsplit(rel).scheme:
            errors.append(f"{label}: escaping artifact path")
            continue
        ref = {"path": f"docs/showcase/{slug}/{rel}", "sha256": item.get("sha256")}
        check_ref(root, ref, label, errors)
        try:
            path = local_path(root, ref["path"])
            if type(item.get("bytes")) is not int or path.stat().st_size != item["bytes"]:
                errors.append(f"{label}: byte count mismatch")
        except (ValueError, OSError):
            pass
        if PurePosixPath(rel).suffix.lower() in VIDEO_EXTENSIONS:
            videos.add(ref["path"])
    # Include selected media outside the entry manifest, but never fetch remote URLs.
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"src", "url"} and isinstance(child, str) and PurePosixPath(urlsplit(child).path).suffix.lower() in VIDEO_EXTENSIONS:
                    videos.add(child)
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(case)
    attribution = [{key: row.get(key) for key in ("stage_id", "model", "reasoning_effort", "record_status", "basis", "scope")}
                   for row in case.get("model_attribution", []) if isinstance(row, dict)]
    return {"slug": slug, "software": case.get("software", []), "manifest_errors": errors,
            "artifact_count": len(seen), "video_paths": sorted(videos), "model_attribution": attribution,
            "unknown_model_stages": [r["stage_id"] for r in attribution if r["record_status"] == "unknown"]}


def decode_video(root, rel, threads=1):
    if type(threads) is not int or not 1 <= threads <= 8:
        raise ValueError("decoder threads must be between 1 and 8")
    result = {"path": rel, "status": "blocked", "threads": threads}
    try:
        path = local_path(root, rel)
    except (ValueError, OSError) as exc:
        return dict(result, reason=str(exc))
    with path.open("rb") as stream:
        if stream.read(128).startswith(b"version https://git-lfs.github.com/spec/"):
            return dict(result, reason="Git LFS pointer; media bytes are not materialized")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        return dict(result, reason="ffprobe and ffmpeg are required for local decode")
    result["sha256"] = digest(path)
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-threads", str(threads), "-protocol_whitelist", "file,pipe", "-count_frames",
             "-show_entries", "stream=codec_type,codec_name,width,height,nb_read_frames,duration:format=duration",
             "-of", "json", str(path)], capture_output=True, text=True, timeout=120, check=False)
        if probe.returncode:
            return dict(result, status="failed", reason="ffprobe could not parse/count the video")
        data = json.loads(probe.stdout)
        video = next(s for s in data.get("streams", []) if s.get("codec_type") == "video")
        duration = float(video.get("duration", data.get("format", {}).get("duration", 0)))
        frames = int(video.get("nb_read_frames", 0))
        if not math.isfinite(duration) or duration <= 0 or frames <= 1:
            return dict(result, status="failed", reason="video needs positive duration and multiple decoded frames")
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-threads", str(threads),
             "-filter_threads", str(threads), "-filter_complex_threads", str(threads), "-protocol_whitelist", "file,pipe",
             "-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120, check=False)
        if decode.returncode:
            return dict(result, status="failed", reason="full audiovisual decode failed")
        return dict(result, status="passed", duration_seconds=duration, decoded_frames=frames,
                    width=video.get("width"), height=video.get("height"), codec=video.get("codec_name"),
                    audio_streams=sum(s.get("codec_type") == "audio" for s in data.get("streams", [])),
                    scope="Byte decode only; native origin, continuity, aesthetics and listening are not established")
    except subprocess.TimeoutExpired:
        return dict(result, reason="local decode exceeded 120 seconds; outcome unverified")
    except (ValueError, KeyError, StopIteration, OSError):
        return dict(result, status="failed", reason="invalid video probe data or decoder execution failure")


def existing_evidence(root, case):
    """Locate existing records without turning historic claims into current passes."""
    refs = {f"docs/showcase/{case['slug']}/validation.json"}
    for resource in case.get("resources", []):
        if isinstance(resource, dict) and isinstance(resource.get("url"), str):
            url = resource["url"]
            if not urlsplit(url).scheme and PurePosixPath(url).suffix.lower() in {".json", ".md", ".txt"}:
                refs.add(url)
    playable = []
    manifest_path = root / "play/manifest.json"
    if manifest_path.is_file():
        manifest = read_json(local_path(root, "play/manifest.json"))
        for demo in manifest.get("demos", []):
            if isinstance(demo, dict) and demo.get("case_slug") == case["slug"]:
                playable.append({"url": demo.get("url"), "source": "play/manifest.json", "status_this_run": "not-tested"})
                refs.add("play/manifest.json")
                refs.update(item["path"] for item in manifest.get("files", []) if isinstance(item, dict)
                            and isinstance(item.get("path"), str) and item["path"].endswith(".json"))
    pointers = []
    for rel in sorted(refs):
        try:
            path = local_path(root, rel)
        except (ValueError, OSError):
            continue
        pointers.append({"path": rel, "sha256": digest(path), "status_this_run": "not-tested"})
    return {"existing_evidence_pointers": pointers, "declared_playables": playable,
            "existing_evidence_scope": "Located and hashed only; read dated records and reconcile later revisions before describing historical coverage"}


def default_usage_rights():
    return {purpose: {"status": "unknown" if purpose == "display" else "not-granted", "evidence": []}
            for purpose in ("display", "training", "evaluation")}


def selected_output_refs(root, slug):
    """Case-owned inventory, plus that case's explicitly selected Web payloads."""
    entry = f"docs/showcase/{slug}"
    manifest = read_json(local_path(root, entry + "/manifest.json"))
    refs = {entry + "/" + row["path"]: row.get("sha256") for row in manifest.get("files", [])
            if isinstance(row, dict) and isinstance(row.get("path"), str)
            and row["path"] not in {"manifest.json", "production-evidence.json"}}
    if (root / "play/manifest.json").is_file():
        play = read_json(local_path(root, "play/manifest.json"))
        prefix = f"play/{slug}/"
        selected = any(isinstance(d, dict) and d.get("case_slug") == slug and
                       isinstance(d.get("url"), str) and d["url"].startswith(prefix)
                       for d in play.get("demos", []))
        if selected:
            refs.update({row["path"]: row.get("sha256") for row in play.get("files", [])
                         if isinstance(row, dict) and isinstance(row.get("path"), str)
                         and row["path"].startswith(prefix)})
    return refs


def validate_agent_fields(root, record, errors, incomplete, slug):
    try:
        selected_outputs = selected_output_refs(root, slug)
    except (ValueError, OSError, TypeError):
        selected_outputs = {}
        errors.append("outputs: case inventory unavailable")
    task = record.get("task")
    if not isinstance(task, dict) or not isinstance(task.get("goal"), str) or not task["goal"].strip():
        errors.append("task.goal is required")
        task = {}
    capabilities = task.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities or not all(isinstance(c, str) and c.strip() for c in capabilities):
        errors.append("task.capabilities needs nonempty capability labels")
    for name, values, allow_empty in (("task.inputs", task.get("inputs"), True), ("outputs", record.get("outputs"), False)):
        if not isinstance(values, list) or (not values and not allow_empty):
            errors.append(f"{name} must be an array of hashed files")
            continue
        for i, ref in enumerate(values):
            check_ref(root, ref, f"{name}[{i}]", errors)
            if name == "outputs" and (not isinstance(ref, dict) or ref.get("path") not in selected_outputs or selected_outputs[ref["path"]] != ref.get("sha256")):
                errors.append(f"outputs[{i}]: not bound to this case selected artifact inventory")
    budget = task.get("reproduction_budget")
    if not isinstance(budget, dict):
        errors.append("task.reproduction_budget must record known limits/measurements or null")
    else:
        for name in ("estimated_seconds", "measured_seconds"):
            value = budget.get(name)
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                errors.append(f"reproduction_budget.{name} must be nonnegative or null")
        ceiling = budget.get("cost_ceiling")
        if ceiling is not None and (not isinstance(ceiling, dict) or type(ceiling.get("amount")) not in (int, float) or not math.isfinite(ceiling["amount"]) or ceiling["amount"] < 0 or not isinstance(ceiling.get("currency"), str) or not ceiling["currency"].strip()):
            errors.append("reproduction_budget.cost_ceiling needs amount/currency or null")
        if budget.get("measured_seconds") is not None:
            check_ref(root, budget.get("evidence"), "reproduction_budget.evidence", errors)
    rights = record.get("usage_rights", default_usage_rights())
    if not isinstance(rights, dict):
        errors.append("usage_rights must be an object")
        rights = {}
    for purpose in ("display", "training", "evaluation"):
        row = rights.get(purpose, default_usage_rights()[purpose])
        if not isinstance(row, dict) or row.get("status") not in {"granted", "not-granted", "unknown"}:
            errors.append(f"usage_rights.{purpose}: invalid explicit status")
            continue
        refs = row.get("evidence", [])
        if not isinstance(refs, list) or (row["status"] == "granted" and not refs):
            errors.append(f"usage_rights.{purpose}: a grant needs hashed terms/permission evidence")
            refs = []
        for i, ref in enumerate(refs):
            check_ref(root, ref, f"usage_rights.{purpose}.evidence[{i}]", errors)
        if purpose == "display" and row["status"] != "granted":
            incomplete.append("display_rights")
    recovery = record.get("failure_recovery", [])
    if not isinstance(recovery, list):
        errors.append("failure_recovery must be an array")
        recovery = []
    for i, row in enumerate(recovery):
        if not isinstance(row, dict) or row.get("status") not in STATUSES or not row.get("stage"):
            errors.append(f"failure_recovery[{i}]: stage/status required")
            continue
        if row["status"] == "passed":
            for name in ("minimal_reproducer", "real_regression"):
                check_ref(root, row.get(name), f"failure_recovery[{i}].{name}", errors)
        else:
            incomplete.append(f"failure_recovery:{i}")


def validate_record(root, record, slug, interactive):
    errors, incomplete = [], []
    required = STAGES + (INTERACTIVE if interactive else ())
    if not isinstance(record, dict):
        return ["production record must be an object"], list(required)
    if record.get("schema") != SCHEMA or record.get("case_slug") != slug:
        errors.append("production record schema/case_slug mismatch")
    try:
        timestamp = datetime.fromisoformat(record.get("recorded_at", "").replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("timezone required")
    except (ValueError, AttributeError, TypeError):
        errors.append("recorded_at must be an ISO-8601 timestamp with timezone")
    for name in ("recorded_at", "recipe", "environment", "sources", "checks"):
        if not record.get(name):
            errors.append(f"production record missing {name}")
    validate_agent_fields(root, record, errors, incomplete, slug)
    # References bind recorded claims to bytes; they do not authenticate the claims.
    check_ref(root, record.get("recipe"), "recipe", errors)
    environment = record.get("environment", [])
    roles = set()
    if not isinstance(environment, list):
        errors.append("environment must be an array")
        environment = []
    for index, row in enumerate(environment):
        if not isinstance(row, dict) or not isinstance(row.get("component"), str) or not row.get("version"):
            errors.append(f"environment[{index}]: component/version required")
            continue
        if isinstance(row.get("role"), str):
            roles.add(row["role"])
        if row["version"] == "unknown":
            incomplete.append(f"environment:{row['component']}")
            if not row.get("reason"):
                errors.append(f"environment[{index}]: unknown version needs reason")
        else:
            check_ref(root, row.get("evidence"), f"environment[{index}].evidence", errors)
    if not {"host", "adapter", "core"}.issubset(roles):
        errors.append("environment must record host, adapter and core roles")
    sources = record.get("sources", [])
    if not isinstance(sources, list):
        errors.append("sources must be an array")
        sources = []
    for index, ref in enumerate(sources):
        check_ref(root, ref, f"sources[{index}]", errors)
    checks = record.get("checks", {})
    if not isinstance(checks, dict):
        errors.append("checks must be an object")
        checks = {}
    for stage in required:
        if stage not in checks:
            incomplete.append(stage)
    for stage, row in checks.items():
        if not isinstance(row, dict) or row.get("status") not in STATUSES or not isinstance(row.get("summary"), str) or not row["summary"].strip():
            errors.append(f"checks.{stage}: explicit status and summary required")
            incomplete.append(stage)
            continue
        if row.get("evidence_origin") not in {"current-run", "historical", "not-run"} or not isinstance(row.get("scope"), str) or not row["scope"].strip():
            errors.append(f"checks.{stage}: evidence_origin and scope required")
        if row["status"] in {"passed", "failed"} and row.get("evidence_origin") == "not-run":
            errors.append(f"checks.{stage}: an unrun test cannot pass or fail")
        refs = row.get("evidence", [])
        if not isinstance(refs, list):
            errors.append(f"checks.{stage}.evidence must be an array")
            refs = []
        if row["status"] == "passed" and not refs:
            errors.append(f"checks.{stage}: passed needs hashed evidence")
        if row["status"] != "passed":
            incomplete.append(stage)
        for index, ref in enumerate(refs):
            check_ref(root, ref, f"checks.{stage}.evidence[{index}]", errors)
    return errors, sorted(set(incomplete))


def inspect_case(root, case, decode=False, evidence_path=None, threads=1):
    report = inventory(root, case)
    report.update(existing_evidence(root, case))
    report["usage_rights"] = default_usage_rights()
    report["rights_verified"] = False
    report["usage_rights_scope"] = "Declared grants/evidence only, not legal verification; missing grants are not inferred from repository licenses"
    report["unresolved_stages_scope"] = "Stages not verified in this checker run or not imported into its optional index; this does not mean historical evidence is absent"
    report["record_status_scope"] = "Optional index format/hash status only; not a verdict on case quality or historical acceptance"
    report["scope_decision"] = "Keep untested/inapplicable stages explicit; a human may narrow the claim (for example intentional silence or historical display), without inventing a passed test"
    interactive = any(str(host).lower() == "godot" for host in case.get("software", []))
    report["interactive_requirements"] = interactive
    default = f"docs/showcase/{report['slug']}/production-evidence.json"
    record_path = evidence_path or default
    try:
        path = local_path(root, record_path)
    except ValueError:
        if evidence_path or (root / default).exists():
            raise
        report["record_status"] = "not-tested"
        report["optional_record_present"] = False
        report["record_errors"] = []
        report["unresolved_stages"] = list(STAGES + (INTERACTIVE if interactive else ()))
        report["legacy_note"] = "No production record: historical evidence is retained, not upgraded or rejected"
    else:
        record = read_json(path)
        report["optional_record_present"] = True
        if isinstance(record, dict):
            raw_rights = record.get("usage_rights")
            if isinstance(raw_rights, dict):
                report["usage_rights"] = dict(default_usage_rights(), **raw_rights)
        if isinstance(record, dict) and record.get("interactive") is True:
            interactive = True
            report["interactive_requirements"] = True
        errors, missing = validate_record(root, record, report["slug"], interactive)
        report["record_errors"] = errors
        report["unresolved_stages"] = missing
        report["record_status"] = "failed" if errors else "passed"
        report["declared_stage_evidence_origin"] = {key: row.get("evidence_origin") for key, row in record.get("checks", {}).items() if isinstance(row, dict)} if isinstance(record, dict) and isinstance(record.get("checks"), dict) else {}
        report["declared_stage_status"] = {key: row.get("status") for key, row in record.get("checks", {}).items() if isinstance(row, dict)} if isinstance(record, dict) and isinstance(record.get("checks"), dict) else {}
    report["video_decode"] = [decode_video(root, p, threads) if decode else {"path": p, "status": "not-tested"} for p in report["video_paths"]]
    if not report["video_paths"]:
        report["unresolved_stages"].append("missing_video")
    if not report["video_decode"] or any(r["status"] != "passed" for r in report["video_decode"]):
        report["unresolved_stages"].append("video_decode")
    report["ready_for_human_decision"] = not (report["manifest_errors"] or report["record_errors"] or report["unresolved_stages"])
    report["quality_approval"] = "not-assessed-by-this-tool"
    report["model_identity_verified"] = False
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--case", help="selected case slug; omit for all selected cases")
    parser.add_argument("--evidence", help="optional repository-relative production record for one case")
    parser.add_argument("--decode-video", action="store_true", help="locally decode complete video; no downloads")
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=1, help="decoder thread limit (default 1)")
    parser.add_argument("--require-ready", action="store_true", help="exit 1 when evidence is incomplete; still not quality approval")
    args = parser.parse_args(argv)
    root = args.repo.resolve()
    try:
        if args.evidence and not args.case:
            raise ValueError("--evidence requires --case")
        collection = read_json(local_path(root, "collection.json"))
        cases = collection["cases"]
        if not isinstance(cases, list) or not all(isinstance(c, dict) for c in cases):
            raise ValueError("collection cases must be an array of objects")
        if args.case:
            cases = [c for c in cases if c.get("slug") == args.case]
        if not cases:
            raise ValueError("case not found in collection")
        reports = [inspect_case(root, case, args.decode_video, args.evidence, args.threads) for case in cases]
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"error": str(exc), "quality_approval": "not-assessed-by-this-tool"}))
        return 2
    print(json.dumps({"scope": "Read-only inventory and byte checks; recorded claims still require independent review",
                      "cases": reports}, ensure_ascii=False, indent=2))
    return int(args.require_ready and any(not r["ready_for_human_decision"] for r in reports))


if __name__ == "__main__":
    sys.exit(main())
