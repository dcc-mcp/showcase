#!/usr/bin/env python3
"""Capture actual X11 gameplay and verify the complete physical-input treasure/swim route."""
from __future__ import annotations
import argparse
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from gameplay import RouteDriver, complete, keyboard_direction, validate_restored, validate_state
from observers import observer_receipts
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
              "movie_label": "Scripted traversal (--demo); not physical-input or completion proof",
              "screenshot_label": "Five actual X11 captures of the uninterrupted physical-input treasure route",
              "audio": "No audio stream; this prototype currently has no audio", "checks": [],
              "limitations": ["CI software OpenGL under Xvfb, not physical hardware performance."]}
    runtime = recorder = None
    pressed, events, screenshots = set(), [], []

    def launch(log_name, env, extra=()):
        log = (out / log_name).open("w")
        process = subprocess.Popen([godot, "--path", str(project), "--rendering-method", "gl_compatibility", "--rendering-driver", "opengl3",
            "--audio-driver", "Dummy", "--resolution", "1280x720", "--position", "0,0", "--single-window",
            "--fullscreen", *(["--", *extra] if extra else [])], env=env, stdout=log, stderr=log)
        log.close()
        try:
            wait_for(process, lambda: "TIDAL_FRAME_READY" in (out / log_name).read_text(),
                     150, "TIDAL_FRAME_READY after actual frame_post_draw")
            report.setdefault("readiness", []).append({"log": log_name, "boundary": "TIDAL_FRAME_READY"})
            time.sleep(.5)
            return process
        except Exception:
            stop_process(process)
            raise

    def records(log_name, prefix):
        require_running(runtime, "passive route observation")
        return observer_receipts([{"text": line} for line in (out / log_name).read_text().splitlines()], prefix)

    def key(name, down):
        subprocess.run(["xdotool", "keydown" if down else "keyup", name], check=True, timeout=10)
        events.append({"time": time.monotonic(), "kind": "keydown" if down else "keyup", "key": name})
        if down:
            pressed.add(name)
        else:
            pressed.discard(name)

    def tap(name):
        key(name, True)
        time.sleep(.07)
        key(name, False)

    def move(direction):
        wanted = keyboard_direction(direction)
        for name in sorted(pressed - wanted):
            key(name, False)
        for name in sorted(wanted - pressed):
            key(name, True)

    def screenshot(name, state=None):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "x11grab",
            "-video_size", "1280x720", "-i", os.environ["DISPLAY"] + "+0,0", "-frames:v", "1",
            str(out / name)], check=True, timeout=30)
        if state is not None:
            screenshots.append({"name": name, "kind": "physical-input-route", "state": state,
                                "bytes": (out / name).stat().st_size, "sha256": sha256(out / name)})

    def focus():
        windows = subprocess.check_output(["xdotool", "search", "--sync", "--onlyvisible", "--pid", str(runtime.pid)],
                                           text=True, timeout=20).split()
        if not windows:
            raise RuntimeError("Could not identify the actual native game window")
        subprocess.run(["xdotool", "windowfocus", "--sync", windows[-1]], check=True, timeout=10)

    try:
        for script, prefix in (("verify_swimming.gd", "TIDAL_SWIMMING_CHECK"),
                               ("verify_treasure.gd", "TIDAL_TREASURE_CHECK")):
            regression = subprocess.run([godot, "--headless", "--path", str(project), "--script", "res://" + script,
                                         "--fixed-fps", "240"], env=isolated_env(out / (script + "-session")),
                                        capture_output=True, text=True, timeout=180)
            output = regression.stdout + regression.stderr
            (out / (script + ".log")).write_text(output)
            check_engine_log(output)
            receipts = observer_receipts([{"text": line} for line in output.splitlines()], prefix)
            if regression.returncode != 0 or len(receipts) != 1:
                raise RuntimeError("Actual headless regression failed: " + script)
            receipt = receipts[0]
            if type(receipt.get("schema")) is not int or receipt["schema"] != 1 or receipt.get("passed") is not True or receipt.get("failures") != [] or not receipt.get("checks"):
                raise RuntimeError("Actual headless regression receipt is incomplete: " + script)
            report["checks"].append({"name": script + " actual headless regression (not physical-input proof)", "passed": True, "receipt": receipt})
        audit = subprocess.run([godot, "--headless", "--path", str(project), "--", "--audit"],
            env=isolated_env(out / "audit-session"), capture_output=True, text=True, timeout=90)
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

        # Scripted media stays separate. The recorder never changes actor/camera state.
        runtime = launch("scripted-traversal.log", isolated_env(out / "demo-session"), ("--demo",))
        before_movie = records("scripted-traversal.log", "TIDAL_STATE")
        first_movie_id = max((item["sample_id"] for item in before_movie), default=0)
        movie = out / "scripted-treasure-swim.mp4"
        with (out / "ffmpeg.log").open("w") as log:
            recorder = subprocess.Popen(["ffmpeg", "-hide_banner", "-y", "-f", "x11grab", "-draw_mouse", "0",
                "-framerate", "24", "-video_size", "1280x720", "-i", os.environ["DISPLAY"] + "+0,0",
                "-t", "120", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(movie)], stdin=subprocess.PIPE, stdout=log, stderr=log)
            recording_started = time.monotonic()
            first_swim_at = None
            while time.monotonic() - recording_started < 120:
                require_running(recorder, "completion of scripted sea movie")
                observed = records("scripted-traversal.log", "TIDAL_STATE")
                if first_swim_at is None and any(item["sample_id"] > first_movie_id and item["locomotion"] == "swim" for item in observed):
                    first_swim_at = time.monotonic()
                now = time.monotonic()
                if now - recording_started >= 36 and first_swim_at is not None and now - first_swim_at >= 4:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError("Actual sea swimming plus four recorded seconds was not established within 120 seconds")
            # ffmpeg's own quit command finalizes MP4 cleanly; never kill a passing recording.
            recorder.stdin.write(b"q\n")
            recorder.stdin.flush()
            if recorder.wait(timeout=30) != 0:
                raise RuntimeError("ffmpeg X11 recording failed; inspect ffmpeg.log")
            report["movie_stop_condition"] = {"minimum_wall_seconds": 36, "post_swim_wall_seconds": 4,
                "maximum_wall_seconds": 120, "first_swim_wall_seconds": first_swim_at - recording_started}
        recorder = None
        movie_states = [item for item in records("scripted-traversal.log", "TIDAL_STATE") if item["sample_id"] > first_movie_id]
        previous = None
        for state in movie_states:
            validate_state(state, previous, expected_demo=True)
            previous = state
        if not any(item["locomotion"] == "swim" for item in movie_states):
            raise RuntimeError("Actual scripted movie interval did not include sea swimming")
        report["movie_observations"] = movie_states
        stop_input_runtime(runtime)
        runtime = None
        check_engine_log((out / "scripted-traversal.log").read_text())
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(movie)], text=True))
        video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
        duration = float(probe["format"]["duration"])
        if not (35.0 <= duration <= 121 and video["width"] == 1280 and video["height"] == 720):
            raise RuntimeError("Native movie dimensions/duration differ from the advertised recording")
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "-"], check=True, timeout=120)
        report.update({"movie_seconds": duration, "movie_sha256": sha256(movie), "media_probe": probe})
        report["checks"].append({"name": "actual X11 scripted sea capture includes observed swimming and fully decodes", "passed": True})

        # No --demo, game-property writes, position injection or synthesized save.
        input_env = isolated_env(out / "input-session")
        runtime = launch("native-input.log", input_env)
        focus()
        driver = RouteDriver(lambda: records("native-input.log", "TIDAL_STATE"), move,
                             lambda state: tap("e"), time.sleep, screenshot)
        try:
            route = driver.run()
        finally:
            write_json(out / "native-input-route.json", {"input_events": events, "samples": driver.samples,
                                                        "milestones": driver.milestones, "screenshots": screenshots})
        report["physical_route"] = route
        report["actual_captures"] = screenshots
        if {item["name"] for item in screenshots} != {f"tidal-{index:02d}.png" for index in range(1, 6)}:
            raise RuntimeError("Actual input route did not capture all five playable milestones")
        for item in screenshots:
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(out / item["name"]), "-f", "null", "-"], check=True, timeout=30)
        report["checks"].append({"name": "physical WASD/E completes treasure loop and walk/wade/swim/shore traversal", "passed": True})
        save_file = Path(input_env["XDG_DATA_HOME"]) / "godot/app_userdata/Tidal Sanctuary/tidal-sanctuary-v2.json"
        def read_saved():
            try:
                return json.loads(save_file.read_text())
            except (OSError, ValueError):
                return {}
        wait_for(runtime, lambda: read_saved().get("schema") == 2 and complete(read_saved()), 20, "actual completed treasure save")
        saved = read_saved()
        report["actual_saved_state"] = saved
        stop_input_runtime(runtime)
        check_engine_log((out / "native-input.log").read_text())
        runtime = None

        # A different OS process must load the actual previous process's untouched file.
        runtime = launch("native-reopened.log", input_env)
        focus()
        loads = records("native-reopened.log", "TIDAL_LOAD")
        if len(loads) != 1:
            raise RuntimeError("Fresh native process must emit exactly one load receipt")
        validate_restored(loads[0], saved)
        screenshot("native-restored.png")
        report["restored"] = loads[0]
        report["checks"].append({"name": "fresh native process restores completed quest and saved position", "passed": True})
        tap("r")
        wait_for(runtime, lambda: read_saved().get("quest_stage") == 0 and read_saved().get("treasures") == [False, False]
                 and read_saved().get("completed") is False, 15, "actual cleared treasure save after physical R")
        report["checks"].append({"name": "physical R resets actual treasure progress after restoration", "passed": True})
        stop_input_runtime(runtime)
        runtime = None
        check_engine_log((out / "native-reopened.log").read_text())
        report["passed"] = True
    except Exception as error:
        report["blocker"] = str(error)
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
        engine_errors = []
        for log_name in ("verify_swimming.gd.log", "verify_treasure.gd.log", "audit.log", "scripted-traversal.log", "native-input.log", "native-reopened.log"):
            path = out / log_name
            if path.exists():
                try:
                    check_engine_log(path.read_text())
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
