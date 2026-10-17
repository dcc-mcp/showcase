#!/usr/bin/env python3
"""Capture genuine X11-rendered native gameplay and independently test physical W/E."""
from __future__ import annotations
import argparse
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from common import checked_godot, check_engine_log, copy_game, isolated_env, isolated_output, sha256, stop_process, write_json


def require_running(process, message):
    status = process.poll()
    if status is not None:
        raise RuntimeError(f"Native runtime exited with status {status} before {message}")


def wait_for(process, predicate, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # Stale readiness/save evidence cannot make an exited process pass.
        require_running(process, message)
        if predicate():
            require_running(process, message)
            return
        time.sleep(.1)
    raise TimeoutError(message)


def stop_input_runtime(process):
    # The input test has no self-quit path. Establish liveness before our own stop.
    require_running(process, "deliberate input-test shutdown")
    stop_process(process)
    # Detect a crash racing with shutdown too. Only a normal exit or our SIGTERM
    # is expected; a forced kill or any other signal must not be a green check.
    if process.returncode not in (0, -signal.SIGTERM):
        raise RuntimeError(f"Native input runtime ended with unexpected status {process.returncode}")


def collect_composition_studies(frames, native_log):
    """Keep fixed-camera visual studies separate from all gameplay/input evidence."""
    names = ("hero-composition.png", "hero-wide.png")
    fifth_frame = next((index for index, line in enumerate(native_log.splitlines())
                        if re.fullmatch(r"TIDAL_CAPTURE .*tidal-05[.]png 0", line)), None)
    if fifth_frame is None:
        raise RuntimeError("Hero studies require the successful fifth regular capture first")
    receipts = {}
    for index, line in enumerate(native_log.splitlines()):
        if not line.startswith("TIDAL_HERO_CAPTURE "):
            continue
        try:
            receipt = json.loads(line.split(" ", 1)[1])
        except (ValueError, TypeError) as error:
            raise RuntimeError("Malformed actual Godot hero capture receipt") from error
        if not isinstance(receipt, dict) or receipt.get("file") not in names:
            raise RuntimeError("Unexpected hero capture receipt")
        name = receipt["file"]
        if index <= fifth_frame or name in receipts:
            raise RuntimeError("Hero captures must each occur once after the five regular frames")
        if type(receipt.get("error")) is not int or receipt["error"] != 0:
            raise RuntimeError("Actual Godot hero PNG save failed: " + name)
        if receipt.get("kind") != "fixed-camera-study":
            raise RuntimeError("Hero capture lacks the explicit fixed-camera-study label")
        receipts[name] = receipt
    if set(receipts) != set(names):
        raise RuntimeError("Both actual Godot fixed-camera study receipts are required")
    studies = []
    for name in names:
        path = frames / name
        if not path.is_file():
            raise RuntimeError("Actual fixed-camera PNG is missing: " + name)
        data = path.read_bytes()
        if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise RuntimeError("Fixed-camera output is not a PNG: " + name)
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        if (width, height) != (1280, 720):
            raise RuntimeError("Fixed-camera PNG differs from the actual 1280x720 viewport: " + name)
        studies.append({"name": name, "kind": "fixed-camera-study", "width": width, "height": height,
                        "bytes": len(data), "sha256": sha256(path), "receipt": receipts[name]})
    return studies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--godot", default="godot")
    args = parser.parse_args()
    out = isolated_output(args.output, args.native)
    godot = checked_godot(args.godot)
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Native capture requires an actual Xvfb X11 display")
    project = out / "runtime-project"
    copy_game(args.native, project)
    report = {"passed": False, "input_route": "actual X11/XTest keyboard input via xdotool",
              "movie_route": "continuous ffmpeg x11grab of the actual native Godot window",
              "movie_label": "Scripted traversal (--demo); not manual-input or completion proof",
              "composition_label": "Actual Godot fixed-camera composition studies after the five regular traversal frames; not physical-input screenshots",
              "audio": "No audio stream; this prototype currently has no audio",
              "checks": [], "limitations": ["CI software OpenGL under Xvfb, not physical hardware performance."]}
    runtime = recorder = None
    pressed = set()

    def launch(log_name, env, extra=()):
        log = (out / log_name).open("w")
        process = subprocess.Popen([godot, "--path", str(project), "--rendering-method", "gl_compatibility", "--rendering-driver", "opengl3",
            "--audio-driver", "Dummy", "--resolution", "1280x720", "--position", "0,0", "--single-window",
            "--fullscreen", *(["--", *extra] if extra else [])], env=env, stdout=log, stderr=log)
        log.close()
        try:
            # _ready() precedes costly first-frame shader compilation on llvmpipe.
            wait_for(process, lambda: "TIDAL_FRAME_READY" in (out / log_name).read_text(),
                     150, "TIDAL_FRAME_READY after actual frame_post_draw")
            report.setdefault("readiness", []).append({"log": log_name, "boundary": "TIDAL_FRAME_READY"})
            time.sleep(.5)
            return process
        except Exception:
            stop_process(process)
            raise

    def key(name, down):
        subprocess.run(["xdotool", "keydown" if down else "keyup", name], check=True, timeout=10)
        if down:
            pressed.add(name)
        else:
            pressed.discard(name)

    def tap(name):
        key(name, True)
        time.sleep(.07)
        key(name, False)

    def screenshot(name):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "x11grab",
            "-video_size", "1280x720", "-i", os.environ["DISPLAY"] + "+0,0", "-frames:v", "1",
            str(out / name)], check=True, timeout=30)

    try:
        # Audit isolated copy and isolated persistent storage; no checkout mutation or real saves.
        env = isolated_env(out / "audit-session")
        audit = subprocess.run([godot, "--headless", "--path", str(project), "--", "--audit"],
            env=env, capture_output=True, text=True, timeout=90)
        log = audit.stdout + audit.stderr
        (out / "audit.log").write_text(log)
        check_engine_log(log)
        if audit.returncode != 0:
            raise RuntimeError("Native --audit exited nonzero")
        audit_lines = [line.split("TIDAL_AUDIT ", 1)[1] for line in log.splitlines() if "TIDAL_AUDIT " in line]
        if len(audit_lines) != 1:
            raise RuntimeError("Native audit did not report exactly one structured result")
        facts = json.loads(audit_lines[0])
        if facts.get("lanterns") != 3 or facts.get("terrain_surfaces", 0) < 1 or facts.get("scene_nodes", 0) < 100:
            raise RuntimeError("Native scene audit was incomplete")
        report["checks"].append({"name": "actual headless scene audit", "passed": True, "facts": facts})

        # New isolated save area makes the scripted recording reproducible.
        demo_env = isolated_env(out / "demo-session")
        frames = out / "scripted-traversal-frames"
        frames.mkdir()
        demo_env["TIDAL_CAPTURE_DIR"] = str(frames)
        runtime = launch("scripted-traversal.log", demo_env, ("--demo", "--capture"))
        movie = out / "scripted-traversal-18s.mp4"
        with (out / "ffmpeg.log").open("w") as log:
            recorder = subprocess.Popen(["ffmpeg", "-hide_banner", "-y", "-f", "x11grab", "-draw_mouse", "0",
                "-framerate", "24", "-video_size", "1280x720", "-i", os.environ["DISPLAY"] + "+0,0",
                "-t", "18", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(movie)], stdout=log, stderr=log)
            if recorder.wait(timeout=90) != 0:
                raise RuntimeError("ffmpeg X11 recording failed; inspect ffmpeg.log")
        recorder = None
        runtime.wait(timeout=100)
        if runtime.returncode != 0:
            raise RuntimeError("Scripted capture runtime exited nonzero")
        runtime = None
        check_engine_log((out / "scripted-traversal.log").read_text())
        captures = sorted(frames.glob("tidal-*.png"))
        report["actual_captures"] = [{"name": item.name, "bytes": item.stat().st_size, "sha256": sha256(item)} for item in captures]
        if len(captures) != 5:
            raise RuntimeError(f"Expected five actual runtime PNG captures, observed {len(captures)}")
        studies = collect_composition_studies(frames, (out / "scripted-traversal.log").read_text())
        report["composition_studies"] = studies
        for study in studies:
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(frames / study["name"]),
                            "-f", "null", "-"], check=True, timeout=30)
        report["checks"].append({"name": "two separately labeled actual Godot fixed-camera PNGs fully decode", "passed": True})
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(movie)], text=True))
        video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
        duration = float(probe["format"]["duration"])
        if not (17.5 <= duration <= 19 and video["width"] == 1280 and video["height"] == 720):
            raise RuntimeError("Native movie dimensions/duration differ from the advertised recording")
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "-"], check=True, timeout=90)
        report.update({"movie_seconds": duration, "movie_sha256": sha256(movie), "media_probe": probe})
        report["checks"].append({"name": "18-second actual X11 capture fully decodes", "passed": True})

        # This process has no --demo flag. No positions/properties/save files are injected.
        input_env = isolated_env(out / "input-session")
        runtime = launch("native-input.log", input_env)
        window_ids = subprocess.check_output(["xdotool", "search", "--sync", "--onlyvisible", "--pid", str(runtime.pid)],
                                               text=True, timeout=20).split()
        if not window_ids:
            raise RuntimeError("Could not identify the actual native game window")
        subprocess.run(["xdotool", "windowfocus", "--sync", window_ids[-1]], check=True, timeout=10)
        screenshot("native-input-before.png")
        # From the declared start, W approaches lantern I along the camera-relative path.
        # Tap E during this real walk until the runtime itself prints activation evidence.
        key("w", True)
        activated = False
        start = time.monotonic()
        while time.monotonic() - start < 15:
            tap("e")
            if "TIDAL_LANTERN 0" in (out / "native-input.log").read_text():
                activated = True
                break
            time.sleep(.08)
        key("w", False)
        if not activated:
            raise RuntimeError("Physical W/E smoke did not activate lantern I; inspect native-input.log and before screenshot")
        screenshot("native-input-after.png")
        save_file = Path(input_env["XDG_DATA_HOME"]) / "godot/app_userdata/Tidal Sanctuary/tidal-sanctuary-v1.json"
        def read_saved():
            try:
                return json.loads(save_file.read_text())
            except (OSError, ValueError):
                return {}
        wait_for(runtime, lambda: read_saved().get("activated") == [True, False, False],
                 20, "real game save after E interaction")
        saved = read_saved()
        position = saved.get("player", [])
        if saved.get("activated") != [True, False, False] or len(position) != 3:
            raise RuntimeError("Runtime save did not confirm exactly lantern I activated")
        displacement = ((position[0] - 1.3) ** 2 + (position[2] - 10.0) ** 2) ** .5
        if displacement <= .5:
            raise RuntimeError("Physical W input did not produce verified player movement")
        report["checks"].append({"name": "physical W moves and E activates lantern I", "passed": True,
            "horizontal_displacement": displacement, "actual_saved_state": saved,
            "no_demo_no_state_injection": True})
        tap("r")
        wait_for(runtime, lambda: read_saved().get("activated") == [False, False, False],
                 15, "real game save after physical R reset")
        reset = read_saved()
        if reset.get("activated") != [False, False, False]:
            raise RuntimeError("Physical R did not reset the actual game state")
        report["checks"].append({"name": "physical R resets lantern progress", "passed": True})
        stop_input_runtime(runtime)
        check_engine_log((out / "native-input.log").read_text())
        runtime = None

        report["passed"] = True
    except Exception as error:
        report["blocker"] = str(error)
        # Useful failure evidence must not turn a failing smoke test into a pass.
        try:
            screenshot("native-failure.png")
        except Exception:
            pass
        raise
    finally:
        for name in list(pressed):
            try:
                key(name, False)
            except Exception:
                pass
        stop_process(recorder)
        stop_process(runtime)
        # Preserve engine errors even if input already failed for another reason.
        engine_errors = []
        for log_name in ("audit.log", "scripted-traversal.log", "native-input.log"):
            log_path = out / log_name
            if log_path.exists():
                try:
                    check_engine_log(log_path.read_text())
                except RuntimeError as error:
                    engine_errors.append({"log": log_name, "error": str(error)})
        report["engine_errors"] = engine_errors
        if engine_errors:
            report["passed"] = False
        write_json(out / "native-validation.json", report)
        if engine_errors:
            raise RuntimeError("Native engine ERROR diagnostics recorded; inspect native-validation.json")


if __name__ == "__main__":
    main()
