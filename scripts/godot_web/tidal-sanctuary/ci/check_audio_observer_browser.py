#!/usr/bin/env python3
"""Bounded hosted Chrome audio-observer smoke, not gameplay/FPS acceptance."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from common import isolated_output

MAX_SECONDS = 30
WORK_SECONDS = 27
AUDIO_FILES = {
    "music": "tidekeeper-loop.ogg", "chart_read": "chart_read.wav", "key_pickup": "key_pickup.wav",
    "pearl_pickup": "pearl_pickup.wav", "beacon_resolve": "beacon_resolve.wav",
}
SCOPE = ("Real sandboxed Chrome, original Web audio backend/assets, real browser mouse events and actual "
         "same-context AudioWorklet PCM. Audio-only observer smoke; no Godot gameplay, FPS, full-loop, "
         "physical-speaker or subjective listening acceptance.")


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_report(output, report):
    temporary = output / ".receipt.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temporary.replace(output / "receipt.json")


def fixture_resources(source):
    """Serve only the unchanged backend and five explicitly owned audio files."""
    source = source.resolve(strict=True)
    paths = {"/web_audio.js": source / "web_audio.js"}
    paths.update({"/assets/audio/" + name: source / "assets/audio" / name for name in AUDIO_FILES.values()})
    resources, hashes = {}, {}
    for url, path in paths.items():
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(source) or not resolved.is_file():
            raise ValueError("Audio fixture source escaped its selected directory: " + url)
        data = resolved.read_bytes()
        if not data or len(data) > 8 * 1024 * 1024 or data.startswith(b"version https://git-lfs.github.com/spec/"):
            raise ValueError("Missing, oversized or unmaterialized original audio source: " + url)
        content_type = "application/javascript" if url.endswith(".js") else "audio/ogg" if url.endswith(".ogg") else "audio/wav"
        resources[url] = (data, content_type)
        hashes[url.lstrip("/")] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    assets = {name: "/assets/audio/" + filename for name, filename in AUDIO_FILES.items()}
    html = ("<!doctype html><html><head><meta charset='utf-8'><title>Audio observer smoke</title></head><body>"
            "<button id='begin' onclick=\"TidalWebAudio.start('observer_fixture_button')\">Begin</button>"
            "<button id='mute' onclick='TidalWebAudio.setMuted(true)'>Mute</button>"
            "<button id='unmute' onclick='TidalWebAudio.setMuted(false)'>Unmute</button>"
            "<button id='cue' onclick='TidalWebAudio.playCue(0)'>Chart cue</button>"
            "<script src='/web_audio.js'></script><script>window.prepared=TidalWebAudio.initialize("
            + json.dumps(assets) + ");</script></body></html>").encode()
    resources["/"] = (html, "text/html; charset=utf-8")
    hashes["fixture.html"] = {"sha256": hashlib.sha256(html).hexdigest(), "bytes": len(html)}
    return resources, hashes


def handler_for(resources):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/favicon.ico":
                self.send_response(204); self.end_headers(); return
            resource = resources.get(path)
            if resource is None:
                self.send_error(404); return
            body, content_type = resource
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    return Handler


def worker(chromium, source, output):
    # Imports and browser work run inside the supervising process's 27-second
    # budget. A stuck CDP/native call cannot extend the total 30-second ceiling.
    report = {"schema": 1, "scope": SCOPE, "passed": False, "status": "running", "stage": "imports", "checks": []}
    save_report(output, report)
    server = browser = page = None
    started = time.monotonic()
    failures, events = [], []
    try:
        from playwright.sync_api import sync_playwright
        from capture_browser import (audio_probe_init_script, capture_audio_snapshot, passive_evaluate,
            audio_window, validate_audio_baseline, browser_executable, validate_browser_arguments,
            bounded_cdp, BROWSER_ARGS, IGNORED_DEFAULT_ARGS)
        from audio_source_contract import validate_cue_pcm
        from audio_thread import meter_stream

        def stage(name):
            report["stage"] = name
            report["elapsed_seconds"] = time.monotonic() - started
            save_report(output, report)

        def retain(name, value):
            path = output / (name + ".json.gz")
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                json.dump(value, stream, allow_nan=False)
            report.setdefault("snapshots", {})[name] = {"path": path.name, "sha256": file_hash(path), "bytes": path.stat().st_size}
            save_report(output, report)
            return value

        def snapshot(name):
            return retain(name, capture_audio_snapshot(page))

        def inspect_state():
            state = json.loads(passive_evaluate(page, "() => TidalWebAudio.getState()"))
            if state.get("status") == "error":
                raise RuntimeError("Original audio backend failed: " + str(state.get("error")))
            return state

        def click(selector):
            page.locator(selector).click(timeout=3000)
            report.setdefault("mouse_inputs", []).append({"selector": selector, "method": "Playwright browser mouse click"})

        stage("verify-original-source-and-browser")
        resources, report["original_source"] = fixture_resources(source)
        report["browser"] = browser_executable(chromium)
        if not report["browser"]["executable_version"].startswith("Google Chrome"):
            raise ValueError("Hosted smoke requires the explicitly selected standard Google Chrome")
        report["browser"]["sha256"] = file_hash(report["browser"]["executable_path"])
        ci = Path(__file__).resolve().parent
        report["observer_source_sha256"] = {name: file_hash(ci / name) for name in (
            "check_audio_observer_browser.py", "audio_probe.js", "audio_meter_worklet.js",
            "audio_thread.py", "audio_source_contract.py", "capture_browser.py")}
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(resources))
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True).start()
        with sync_playwright() as pw:
            stage("launch-sandboxed-chrome")
            browser = pw.chromium.launch(headless=True, executable_path=report["browser"]["executable_path"],
                chromium_sandbox=True, args=BROWSER_ARGS, ignore_default_args=IGNORED_DEFAULT_ARGS, timeout=5000)
            report["browser"]["runtime_version"] = browser.version
            context = browser.new_context()
            context.add_init_script(script=audio_probe_init_script())
            page = context.new_page()
            page.set_default_timeout(3000)
            session = context.new_cdp_session(page)
            try:
                actual_args = bounded_cdp(session, "Browser.getBrowserCommandLine", timeout=3)["arguments"]
                validate_browser_arguments(actual_args)
                report["browser"]["arguments"] = actual_args
            finally:
                bounded_cdp(session, "detach", timeout=2)
            page.on("pageerror", lambda error: failures.append(str(error)))
            def console(message):
                if len(events) >= 256:
                    if "Browser console evidence overflow" not in failures:
                        failures.append("Browser console evidence overflow")
                    return
                events.append({"type": message.type, "text": message.text})
                if message.type == "error":
                    failures.append(message.text)
            page.on("console", console)
            try:
                stage("prepare-before-real-input")
                response = page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded", timeout=5000)
                if response is None or response.status != 200:
                    raise RuntimeError("Original audio fixture did not return HTTP 200")
                ready = passive_evaluate(page, "async () => { if (!await prepared) throw Error(TidalWebAudio.getState()); return __tidalAudio.ready(); }")
                if len(ready.get("streams", [])) != 3 or sorted(item.get("role") for item in ready["streams"]) != ["bus", "bus", "mix"]:
                    raise ValueError("Original graph did not pre-arm exactly one mix and two bus observers")
                report["observer_ready"] = ready
                mark = passive_evaluate(page, "() => __tidalAudio.mark('smoke-baseline')")
                page.wait_for_timeout(2100)
                before = snapshot("baseline")
                report["checks"].append({"name": "no-input baseline", "result": validate_audio_baseline(before, mark["wall_ms"])})

                stage("real-begin-and-audible-pcm")
                click("#begin")
                start_deadline = time.monotonic() + 3
                while True:
                    state = inspect_state()
                    if state.get("started") and state.get("music_playing"):
                        break
                    if time.monotonic() >= start_deadline:
                        raise TimeoutError("Real Begin did not start the original music")
                    page.wait_for_timeout(50)
                if state.get("start_count") != 1 or state.get("trigger") != "observer_fixture_button":
                    raise ValueError("Original music did not retain the real fixture Begin trigger")
                page.wait_for_timeout(1700)  # Original 1.5-second authored fade.
                mark = passive_evaluate(page, "() => __tidalAudio.mark('smoke-audible')")
                page.wait_for_timeout(1600)
                active = snapshot("audible")
                report["checks"].append({"name": "audible PCM", "result": audio_window(active, mark["wall_ms"], active["wall_ms"], 1.2, True)})

                stage("real-mute-and-quiet-pcm")
                click("#mute")
                if inspect_state().get("muted") is not True:
                    raise ValueError("Real Mute did not change the original backend")
                page.wait_for_timeout(250)
                mark = passive_evaluate(page, "() => __tidalAudio.mark('smoke-muted')")
                page.wait_for_timeout(1400)
                quiet = snapshot("muted")
                report["checks"].append({"name": "muted PCM", "result": audio_window(quiet, mark["wall_ms"], quiet["wall_ms"], 1.1)})

                stage("real-unmute-and-audible-pcm")
                click("#unmute")
                if inspect_state().get("muted") is not False:
                    raise ValueError("Real Unmute did not change the original backend")
                page.wait_for_timeout(250)
                mark = passive_evaluate(page, "() => __tidalAudio.mark('smoke-unmuted')")
                page.wait_for_timeout(1600)
                unmuted = snapshot("unmuted")
                report["checks"].append({"name": "unmuted PCM", "result": audio_window(unmuted, mark["wall_ms"], unmuted["wall_ms"], 1.2, True)})

                stage("real-cue-and-source-bound-pcm")
                click("#cue")
                page.wait_for_timeout(1100)
                cue = snapshot("cue")
                sources = [item for item in cue["starts"] if item["name"] == "chart_read"]
                if len(sources) != 1 or len(cue["starts"]) != 2:
                    raise ValueError("Real chart cue did not retain exactly one cue and one music source")
                report["checks"].append({"name": "isolated chart cue and post-master PCM",
                    "result": validate_cue_pcm(cue, sources[0], cue["contexts"][0])})
                for stream in cue["contexts"][0]["audio_thread"]["streams"]:
                    meter_stream(cue["contexts"][0], stream["source"])
                if len([item for item in cue["gestures"] if item["type"] == "pointerdown" and item["trusted"] is True]) != 4:
                    raise ValueError("Fixture inputs lack four genuine trusted pointer-down events")
                if failures:
                    raise RuntimeError("Browser errors: " + " | ".join(failures))
                report["status"] = "passed"
                report["passed"] = True
                stage("complete")
            except Exception as error:
                # Preserve diagnostic bytes while the page/browser is still alive.
                # The original stage snapshots were already saved before validation.
                report.update(passed=False, status="failed", error=repr(error))
                save_report(output, report)
                try:
                    retain("failure", passive_evaluate(page, "() => ({audio:globalThis.__tidalAudio ? __tidalAudio.snapshot() : null, state:globalThis.TidalWebAudio ? TidalWebAudio.getState() : null})"))
                except Exception as diagnostic:
                    report["diagnostic_error"] = repr(diagnostic)
                raise
            finally:
                browser.close()
                browser = None
    except Exception as error:
        report.update(passed=False, status="failed", error=repr(error))
    finally:
        if server is not None:
            server.shutdown(); server.server_close()
        report["elapsed_seconds"] = time.monotonic() - started
        report["browser_console"] = events
        report["browser_errors"] = failures
        save_report(output, report)
    return 0 if report["passed"] else 1


def supervise(chromium, source, output):
    """A separate process group bounds even an unresponsive browser/driver."""
    started = time.monotonic()
    report = {"schema": 1, "scope": SCOPE, "passed": False, "status": "starting", "checks": [], "maximum_seconds": MAX_SECONDS}
    save_report(output, report)
    command = [sys.executable, str(Path(__file__).resolve()), "--observer-worker", "--chromium", str(chromium),
               "--source", str(source), "--output", str(output)]
    timed_out, launch_error, cleanup_error, code = False, None, None, None
    with (output / "worker.log").open("wb") as log:
        try:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=max(.1, WORK_SECONDS - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                timed_out = True
                # Kill only this smoke's explicitly-owned group, including Chrome
                # and the driver. Do not interrupt a sync Playwright dispatcher.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    code = process.wait(timeout=2)
                except subprocess.TimeoutExpired as error:
                    cleanup_error = repr(error)
        except Exception as error:
            launch_error = repr(error)
    try:
        report = json.loads((output / "receipt.json").read_text())
    except (OSError, ValueError) as error:
        report = {"schema": 1, "scope": SCOPE, "passed": False, "checks": [], "receipt_error": repr(error)}
    if timed_out or code != 0 or report.get("passed") is not True or report.get("status") != "passed":
        report["passed"] = False
        report["status"] = "failed"
        if timed_out:
            report["deadline_error"] = f"Audio-only smoke exceeded its {WORK_SECONDS}-second work budget; owned browser group terminated"
        elif code != 0:
            report["worker_exit_code"] = code
    if launch_error:
        report["launcher_error"] = launch_error
    if cleanup_error:
        report["cleanup_error"] = cleanup_error
    report["total_elapsed_seconds"] = time.monotonic() - started
    report["maximum_seconds"] = MAX_SECONDS
    if report["total_elapsed_seconds"] > MAX_SECONDS:
        report.update(passed=False, status="failed", deadline_error="Audio-only smoke exceeded the total 30-second ceiling")
    save_report(output, report)
    print(json.dumps(report, allow_nan=False))
    return 0 if report["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--observer-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.observer_worker:
        return worker(args.chromium, args.source, args.output)
    output = isolated_output(args.output, args.source)
    return supervise(args.chromium, args.source, output)


if __name__ == "__main__":
    raise SystemExit(main())
