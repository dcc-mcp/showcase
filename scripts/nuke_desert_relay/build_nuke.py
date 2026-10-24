"""Offline preflight and deferred Nuke 16.1v2 graph construction.

Preflight uses only the standard library. Build is for an explicitly granted,
empty, task-owned Nuke host through its discovered official scripting tool.
It saves a graph but never renders, launches Nuke, installs, or contacts a host.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sys


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local_path(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("a nonempty project-relative path is required")
    target = (root / value).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path leaves the project directory")
    return target


def native_path(root, value):
    """Keep the native file beside its relative assets and config."""
    if (not isinstance(value, str) or not value.lower().endswith(".nk") or
            Path(value).name != value or any(char in value for char in '<>:"/\\|?*')):
        raise ValueError("native_output must be one .nk basename in the config directory")
    return local_path(root, value)


def validate_runtime_bindings(binding):
    """Reject missing bindings before importing Nuke or reading build inputs."""
    for key in ("runtime_session_id", "expected_owner_id", "expected_grant_id"):
        if not isinstance(binding.get(key), str) or not binding[key].strip():
            raise RuntimeError("Missing trusted runtime binding: " + key)
    for key in ("expected_process_id", "expected_window_handle"):
        if type(binding.get(key)) is not int or binding[key] <= 0:
            raise RuntimeError("Missing exact trusted runtime binding: " + key)
    if binding["expected_process_id"] != os.getpid():
        raise RuntimeError("The granted process is not the executing process")


def validate_host_grant(cfg, binding, actual_version=None):
    """Check a private grant against trusted caller bindings; perform no mutation.

    The official runtime must validate current coordinator authorization before
    injecting binding values. Reading those values back from this config is not
    authorization. This local guard is defense in depth, not a grant issuer.
    """
    validate_runtime_bindings(binding)
    grant = cfg.get("host_grant", {})
    if grant.get("state") != "granted":
        raise RuntimeError("No active private host grant")
    identities = {
        "grant_id": "expected_grant_id", "owner_id": "expected_owner_id",
        "runtime_session_id": "runtime_session_id", "process_id": "expected_process_id",
        "window_handle": "expected_window_handle",
    }
    for grant_key, binding_key in identities.items():
        if grant.get(grant_key) != binding[binding_key]:
            raise RuntimeError("Private grant does not match trusted " + grant_key)
    if grant.get("nuke_version") != "16.1v2":
        raise RuntimeError("Private grant must name exact Nuke 16.1v2")
    if actual_version is not None and actual_version != grant["nuke_version"]:
        raise RuntimeError("Executing Nuke version does not match the private grant")
    moments = []
    for key in ("starts_at_utc", "ends_at_utc"):
        try:
            moment = datetime.datetime.fromisoformat(grant[key].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError, AttributeError):
            raise RuntimeError("Private grant needs valid UTC " + key) from None
        if moment.tzinfo is None or moment.utcoffset() != datetime.timedelta(0):
            raise RuntimeError("Private grant time must explicitly be UTC: " + key)
        moments.append(moment)
    now = datetime.datetime.now(datetime.timezone.utc)
    if not moments[0] <= now < moments[1]:
        raise RuntimeError("Private host grant is pending, expired, or has an invalid interval")
    actions = grant.get("allowed_actions", [])
    if not isinstance(actions, list) or not {"build_graph", "save_native"}.issubset(actions):
        raise RuntimeError("Private grant lacks build_graph/save_native scope")


def validate_live_window(binding):
    """Verify the exact native HWND still belongs to this bound process."""
    if os.name != "nt":
        raise RuntimeError("This grant route requires a Windows Nuke GUI host")
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    handle = wintypes.HWND(binding["expected_window_handle"])
    if not user32.IsWindow(handle):
        raise RuntimeError("Granted HWND is no longer a live native window")
    process = wintypes.DWORD()
    if not user32.GetWindowThreadProcessId(handle, ctypes.byref(process)):
        raise RuntimeError("Could not read granted HWND process identity")
    if process.value != binding["expected_process_id"] or process.value != os.getpid():
        raise RuntimeError("Granted HWND belongs to a different process")


def preflight(config_path):
    """Return blockers; success permits a build attempt, not host acceptance."""
    config_path = Path(config_path).resolve()
    errors = []
    if not config_path.is_file():
        return None, {"status": "blocked", "blockers": ["Missing build-config.json"]}
    root = config_path.parent
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, {"status": "blocked", "blockers": ["Invalid config: " + str(exc)]}

    def require(condition, message):
        if not condition:
            errors.append(message)

    def ref(record, name):
        if not isinstance(record, dict):
            errors.append(name + ": missing file reference")
            return
        try:
            path = local_path(root, record.get("path"))
        except ValueError as exc:
            errors.append(name + ": " + str(exc))
            return
        if not path.is_file():
            errors.append(name + ": file not available")
        elif not record.get("sha256") or digest(path) != record["sha256"]:
            errors.append(name + ": missing or mismatched SHA-256")

    require(cfg.get("schema_version") == 1, "schema_version must be 1")
    frame = cfg.get("frame", {})
    require(frame == {"width": 1280, "height": 720, "fps": 30, "first": 1, "last": 240},
            "Frame contract must be 1280x720, 30 fps, frames 1..240")
    inputs = cfg.get("inputs", {})
    for name in ("plate", "sky", "ruins"):
        ref(inputs.get(name), "inputs." + name)
    cleanup = cfg.get("ruins_edge_cleanup", {})
    require(cfg.get("ruins_edge_cleanup_verified") is True and cleanup.get("verified") is True,
            "Observed raw ruin color fringe requires a separately verified edge cleanup")
    raw_ruins = cleanup.get("raw_input", {})
    cleaned_ruins = cleanup.get("cleaned_input", {})
    ref(raw_ruins, "ruins_edge_cleanup.raw_input")
    ref(cleaned_ruins, "ruins_edge_cleanup.cleaned_input")
    ref(cleanup.get("evidence"), "ruins_edge_cleanup.evidence")
    require(cleaned_ruins == inputs.get("ruins") and
            raw_ruins.get("path") != cleaned_ruins.get("path") and
            raw_ruins.get("sha256") != cleaned_ruins.get("sha256"),
            "Read input must be a distinct hashed cleaned layer; preserve the original raw layer")
    require(isinstance(cleanup.get("method"), str) and bool(cleanup["method"].strip()),
            "Describe the actual edge cleanup method")
    try:
        edge_review = json.loads(local_path(root, cleanup.get("evidence", {}).get("path")).read_text(encoding="utf-8-sig"))
        require(edge_review.get("status") == "passed" and
                edge_review.get("scope") == "rgba-edge-cleanup" and
                edge_review.get("raw_sha256") == raw_ruins.get("sha256") and
                edge_review.get("cleaned_sha256") == cleaned_ruins.get("sha256") and
                {"light", "dark"}.issubset(edge_review.get("reviewed_backgrounds", [])),
                "Edge review must bind raw/cleaned hashes and inspected light/dark backgrounds")
    except (OSError, ValueError, TypeError, AttributeError):
        errors.append("No readable hash-bound ruin edge-cleanup review")
    plate_check = cfg.get("plate_check", {})
    require(plate_check.get("verified") is True and
            plate_check.get("sha256") == inputs.get("plate", {}).get("sha256") and
            plate_check.get("frames") == 240 and plate_check.get("fps") == 30 and
            plate_check.get("width") == 1280 and plate_check.get("height") == 720,
            "Plate decode/cut/format checks must be verified against the delivered clip")
    colors = cfg.get("colorspaces", {})
    require(all(isinstance(colors.get(key), str) and colors[key]
                for key in ("plate", "sky", "ruins", "cg", "output")),
            "Provide exact installed Nuke colorspace enum values for all inputs/output")
    require(cfg.get("color_pipeline_verified") is True,
            "Color interpretation and premultiplication must be checked in the owned host")
    for name in ("sky", "holdout"):
        mask = cfg.get("masks", {}).get(name, {})
        require(mask.get("verified") is True and mask.get("first") == 1 and
                mask.get("last") == 240 and mask.get("coordinate_system") == "nuke-bottom-left",
                name + " Roto must be calibrated and checked across frames 1..240")
        ref(mask.get("curves_script"), "masks." + name + ".curves_script")
    motion = cfg.get("motion", {})
    require(motion.get("verified") is True, "Motion strategy is not verified")
    ref(motion.get("evidence"), "motion.evidence")
    if motion.get("mode") == "lockoff":
        residual = motion.get("max_residual_px")
        require(isinstance(residual, (int, float)) and math.isfinite(residual) and
                0 <= residual <= 0.5, "Lockoff requires measured residual <= 0.5 px")
    elif motion.get("mode") == "similarity":
        samples = motion.get("samples", [])
        require(len(samples) == 240 and all(
            isinstance(row, dict) and row.get("frame") == index and
            all(isinstance(row.get(key), (int, float)) and math.isfinite(row[key])
                for key in ("tx", "ty", "rotation", "scale")) and row.get("scale", 0) > 0
            for index, row in enumerate(samples, 1)),
            "Similarity motion needs one verified finite sample per output frame")
        require(motion.get("perspective_and_parallax_checked") is True,
                "A similarity transform cannot establish a perspective/parallax match")
    else:
        errors.append("motion.mode must explicitly be lockoff or similarity")
    cg = cfg.get("cg", {})
    require(cg.get("linear_verified") is True and cg.get("alpha_verified") is True and
            cg.get("premultiplied") is True and cg.get("shadow_white_is_unshadowed") is True,
            "CG must be verified scene-linear premultiplied beauty and white-neutral shadow")
    for name in ("beauty", "shadow"):
        media = cg.get(name, {})
        if cg.get("mode") == "still":
            ref(media, "cg." + name)
        elif cg.get("mode") == "sequence":
            files = media.get("files", [])
            pattern = media.get("pattern", "")
            require("%04d" in pattern and len(files) == 240,
                    "cg." + name + ": explicit 240-frame sequence and %04d pattern required")
            for index, item in enumerate(files, 1):
                require(item.get("path") == pattern.replace("%04d", "%04d" % index),
                        "cg." + name + ": sequence order/path mismatch")
                ref(item, "cg." + name + " frame " + str(index))
        else:
            errors.append("cg.mode must explicitly be still or sequence; no automatic hold fallback")
    for name in ("sky", "ruins", "prop"):
        pose = cfg.get("placement", {}).get(name, {})
        require(pose.get("verified") is True, name + " placement has not been reviewed")
        for key in ("translate", "center"):
            value = pose.get(key)
            require(isinstance(value, list) and len(value) == 2 and
                    all(isinstance(v, (int, float)) and math.isfinite(v) for v in value),
                    name + "." + key + " must contain two finite values")
        require(isinstance(pose.get("scale"), (int, float)) and pose.get("scale", 0) > 0,
                name + ".scale must be positive")
        require(isinstance(pose.get("rotate"), (int, float)) and math.isfinite(pose["rotate"]),
                name + ".rotate must be finite")
    amplitude = cfg.get("grade", {}).get("prop_gain_amplitude", 0)
    require(isinstance(amplitude, (int, float)) and 0 <= amplitude <= 0.05,
            "Prop gain animation amplitude must be in [0, 0.05]")
    gain = cfg.get("grade", {}).get("multiply", [1, 1, 1])
    require(isinstance(gain, list) and len(gain) == 3 and
            all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in gain),
            "Final RGB multiply requires three finite positive values")
    try:
        native = native_path(root, cfg.get("native_output", "nuke-desert-relay.nk"))
        require(not native.exists(), "Native output already exists; choose a versioned filename")
    except ValueError as exc:
        errors.append("native_output: " + str(exc))
    return cfg, {"status": "blocked" if errors else "ready-for-owned-host-build",
                 "blockers": errors, "host_executed": False, "render_executed": False,
                 "trusted_runtime_binding_required": True, "host_grant_checked": False,
                 "static_3d_insert": cg.get("mode") == "still"}


def build(config_path, *, runtime_session_id=None, expected_owner_id=None,
          expected_grant_id=None, expected_process_id=None, expected_window_handle=None):
    """Run only inside the freshly granted task-owned Nuke process."""
    binding = {"runtime_session_id": runtime_session_id, "expected_owner_id": expected_owner_id,
               "expected_grant_id": expected_grant_id, "expected_process_id": expected_process_id,
               "expected_window_handle": expected_window_handle}
    # Refuse unbound calls before even importing Nuke or evaluating asset files.
    validate_runtime_bindings(binding)
    cfg, report = preflight(config_path)
    if report["blockers"]:
        raise RuntimeError(json.dumps(report, indent=2))
    config_sha256 = digest(Path(config_path))
    validate_host_grant(cfg, binding)
    import nuke  # Deferred: offline preflight must never import or launch a host.

    validate_host_grant(cfg, binding, nuke.NUKE_VERSION_STRING)
    validate_live_window(binding)
    if [node for node in nuke.allNodes(recurseGroups=True) if node.Class() != "Viewer"]:
        raise RuntimeError("Build requires a freshly granted empty task-owned graph")
    root_dir = Path(config_path).resolve().parent

    def enum(node, name, value):
        knob = node.knob(name)
        if knob is None or value not in list(knob.values()):
            raise RuntimeError(node.name() + "." + name + " lacks exact enum " + value)
        knob.setValue(value)

    def read(name, record, colorspace, mode="still"):
        node = nuke.nodes.Read(name=name)
        node["file"].setValue(record["pattern"] if mode == "sequence" else record["path"])
        enum(node, "colorspace", colorspace)
        for knob in ("first", "origfirst"):
            node[knob].setValue(1)
        for knob in ("last", "origlast"):
            node[knob].setValue(240 if mode in ("sequence", "movie") else 1)
        if mode == "still":
            enum(node, "before", "hold")
            enum(node, "after", "hold")
        return node

    def reformat(node, name):
        out = nuke.nodes.Reformat(name=name, inputs=[node])
        out["format"].setValue(nuke.root()["format"].value())
        enum(out, "resize", "fit")
        return out

    def roto(name, record):
        node = nuke.nodes.Roto(name=name)
        curves = local_path(root_dir, record["curves_script"]["path"]).read_text(encoding="utf-8")
        node["curves"].fromScript(curves)
        return node

    def pose(node, name, key):
        settings = cfg["placement"][key]
        out = nuke.nodes.Transform(name=name, inputs=[node])
        out["translate"].setValue(settings["translate"])
        out["center"].setValue(settings["center"])
        out["scale"].setValue(settings["scale"])
        out["rotate"].setValue(settings["rotate"])
        motion = cfg["motion"]
        if motion["mode"] == "lockoff":
            return out
        tracked = nuke.nodes.Transform(name=name + "_MatchMove", inputs=[out])
        tracked["center"].setValue([640, 360])
        for row in motion["samples"]:
            frame = row["frame"]
            tracked["translate"].setValueAt(row["tx"], frame, 0)
            tracked["translate"].setValueAt(row["ty"], frame, 1)
            tracked["rotate"].setValueAt(row["rotation"], frame)
            for axis in (0, 1):
                tracked["scale"].setValueAt(row["scale"], frame, axis)
        return tracked

    def merge(name, operation, background, foreground, mask=None):
        node = nuke.nodes.Merge2(name=name, operation=operation)
        node.setInput(0, background)
        node.setInput(1, foreground)
        if mask is not None:
            node.setInput(2, mask)
        return node

    def write(name, node, filename, filetype, colorspace):
        output = nuke.nodes.Write(name=name, inputs=[node])
        output["file"].setValue("outputs/" + filename)
        enum(output, "file_type", filetype)
        enum(output, "colorspace", colorspace)
        return output

    undo = nuke.Undo()
    undo.begin("Build Desert Relay preflighted graph")
    try:
        # Recheck the fresh binding before the first Root/node mutation.
        validate_host_grant(cfg, binding, nuke.NUKE_VERSION_STRING)
        validate_live_window(binding)
        if digest(Path(config_path)) != config_sha256:
            raise RuntimeError("Private build config changed after preflight")
        root = nuke.root()
        enum(root, "colorManagement", "Nuke")
        enum(root, "workingSpaceLUT", "linear")
        root["format"].setValue(nuke.addFormat("1280 720 0 0 1280 720 1 DesertRelay_1280x720"))
        root["fps"].setValue(30)
        root["first_frame"].setValue(1)
        root["last_frame"].setValue(240)
        root["project_directory"].setValue("[file dirname [value root.name]]")
        colors = cfg["colorspaces"]
        # A movie has one literal path, despite covering the full frame range.
        plate = read("PLATE_Rec709", cfg["inputs"]["plate"], colors["plate"], "movie")
        sky = pose(reformat(read("SKY_sRGB", cfg["inputs"]["sky"], colors["sky"]),
                            "SKY_Fit"), "SKY_Placement", "sky")
        ruins = pose(read("RUINS_Cleaned_sRGB_PremultVerified", cfg["inputs"]["ruins"], colors["ruins"]),
                     "RUINS_Placement", "ruins")
        sky_mask = roto("ROTO_Sky_Calibrated", cfg["masks"]["sky"])
        holdout = roto("ROTO_PlateHoldout_Calibrated", cfg["masks"]["holdout"])
        sky_comp = merge("COMP_Sky", "over", plate, sky, sky_mask)
        ruins_comp = merge("COMP_DistantRuins", "over", sky_comp, ruins)
        cg_mode = cfg["cg"]["mode"]
        shadow = pose(read("CG_ContactShadow_Linear", cfg["cg"]["shadow"], colors["cg"], cg_mode),
                      "CG_ShadowPlacement", "prop")
        shadow_comp = merge("COMP_ContactShadow", "multiply", ruins_comp, shadow)
        prop = pose(read("CG_PropBeauty_Linear", cfg["cg"]["beauty"], colors["cg"], cg_mode),
                    "CG_PropPlacement", "prop")
        glint = nuke.nodes.Grade(name="CG_SubtleGainAnimation", inputs=[prop], channels="rgb")
        amplitude = cfg.get("grade", {}).get("prop_gain_amplitude", 0)
        for axis in (0, 1, 2):
            glint["multiply"].setExpression("1 + %.8f*sin(3.141592653589793*(frame-1)/239)" % amplitude, axis)
        prop_comp = merge("COMP_Prop", "over", shadow_comp, glint)
        holdout_comp = merge("COMP_PlateForegroundHoldout", "over", prop_comp, plate, holdout)
        final = nuke.nodes.Grade(name="FINAL_Grade", inputs=[holdout_comp], channels="rgb")
        final["multiply"].setValue(cfg.get("grade", {}).get("multiply", [1, 1, 1]) + [1])
        comparison = nuke.nodes.ContactSheet(name="REVIEW_BeforeAfter", rows=1, columns=2,
                                             width=1280, height=360)
        comparison.setInput(0, plate)
        comparison.setInput(1, final)
        breakdown = nuke.nodes.ContactSheet(name="REVIEW_Breakdown", rows=2, columns=3,
                                            width=1280, height=720)
        for index, node in enumerate((plate, sky_comp, ruins_comp, shadow_comp, prop_comp, final)):
            breakdown.setInput(index, node)
        writes = [
            write("WRITE_FinalLinear", final, "final-linear.%04d.exr", "exr", colors["cg"]),
            write("WRITE_FinalRec709", final, "final-rec709.%04d.png", "png", colors["output"]),
            write("WRITE_BeforeAfter", comparison, "before-after.%04d.png", "png", colors["output"]),
            write("WRITE_Breakdown", breakdown, "breakdown.%04d.png", "png", colors["output"]),
        ]
        for index, node in enumerate(nuke.allNodes()):
            node.setXYpos((index % 6) * 220, (index // 6) * 120)
        # Do not save after expiry, revocation/config change, or a stale window.
        if digest(Path(config_path)) != config_sha256:
            raise RuntimeError("Private build config/grant changed during graph construction")
        validate_host_grant(cfg, binding, nuke.NUKE_VERSION_STRING)
        validate_live_window(binding)
        native = native_path(root_dir, cfg.get("native_output", "nuke-desert-relay.nk"))
        native.parent.mkdir(parents=True, exist_ok=True)
        (root_dir / "outputs").mkdir(exist_ok=True)
        nuke.scriptSaveAs(str(native), overwrite=0)
        receipt = {"status": "graph-saved-not-rendered", "nuke_version": nuke.NUKE_VERSION_STRING,
                   "native_file": native.relative_to(root_dir).as_posix(),
                   "config_sha256": config_sha256, "native_sha256": digest(native),
                   "frame": cfg["frame"], "static_3d_insert": cg_mode == "still",
                   "render_executed": False, "save_reopen_tested": False,
                   "write_nodes": [node.name() for node in writes],
                   "privacy_reviewed": False, "typed_mcp_coverage": "not-established-by-this-script"}
        (root_dir / "build-readback.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return receipt
    finally:
        undo.end()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("build-config.json")))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        parser.error("Plain --build is disabled; the official call must inject trusted runtime/owner/grant/PID/HWND bindings")
    _, result = preflight(args.config)
    print(json.dumps(result, indent=2))
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    sys.exit(main())
