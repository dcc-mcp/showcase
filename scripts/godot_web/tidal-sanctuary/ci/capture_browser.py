#!/usr/bin/env python3
"""Capture each real Web viewport independently; then aggregate strict acceptance."""
from __future__ import annotations
import argparse
import array
import base64
import contextlib
import importlib.metadata
import json
import math
import os
import re
import subprocess
import sys
import threading
import tempfile
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from audio_thread import marked_pcm_window, meter_stream, pcm_interval, pcm_signal
from audio_source_contract import validate_source_bus, validate_cue_pcm
from focus_lifecycle import RealTargetFocus, wait_focus_state
from external_chrome import OwnedChromeProfile, external_chrome
from common import check_engine_log, isolated_output, sha256, write_json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from gameplay import (BROWSER_ABSOLUTE_WALL_LIMIT_SECONDS, BROWSER_PHYSICS_LIMIT_SECONDS,
                      RouteDriver, complete, keyboard_direction, validate_restored)
from observers import finite_vector, observer_receipts, positive_integer, validate_language_frame, validate_touch_release


def bounded_cdp(session, method, params=None, timeout=120):
    """Pinned Playwright 1.63 CDP bridge with its normal driver-side deadline.

    Public sync CDPSession.send omits a timeout calculator. This isolated adapter
    supplies it to the same Channel.send path used by generated methods, so the
    driver races the CDP response against its deadline. No signals or asyncio
    cancellation may interrupt the sync dispatcher. Hosted smoke checks verify
    both timeout and the subsequent passive call on every run.
    https://github.com/microsoft/playwright-python/blob/v1.63.0/playwright/_impl/_connection.py
    https://github.com/microsoft/playwright/blob/v1.63.0/packages/playwright-core/src/server/chromium/crConnection.ts
    """
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("CDP timeout must be a positive finite number")
    channel = getattr(getattr(session, "_impl_obj", None), "_channel", None)
    if not callable(getattr(session, "_sync", None)) or not callable(getattr(channel, "send", None)):
        raise RuntimeError("Pinned Playwright CDP timeout adapter is unavailable")
    command = "detach" if method == "detach" else "send"
    payload = {} if method == "detach" else {"method": method, "params": params or {}}
    return session._sync(channel.send(command, lambda _: timeout * 1000, payload))


def detach_cdp(session):
    original = sys.exception()
    try:
        bounded_cdp(session, "detach", timeout=5)
    except Exception as cleanup:
        if original is not None:
            raise RuntimeError(f"{original}; CDP cleanup also failed: {cleanup}") from original
        raise


def passive_evaluate(page, function, *arguments, timeout=120):
    """Inspect/record only; Playwright evaluate uses userGesture:true in Chromium.

    https://github.com/microsoft/playwright/blob/v1.63.0/packages/playwright-core/src/server/chromium/crExecutionContext.ts
    No context resume, source start, game mutation or synthetic input is added.
    """
    expression = "(" + function + ")(" + ",".join(json.dumps(value, allow_nan=False) for value in arguments) + ")"
    session = page.context.new_cdp_session(page)
    try:
        response = bounded_cdp(session, "Runtime.evaluate", {"expression": expression, "userGesture": False,
            "awaitPromise": True, "returnByValue": True, "timeout": timeout * 1000}, timeout=timeout)
        if response.get("exceptionDetails"):
            raise RuntimeError("Passive browser observation failed: " + json.dumps(response["exceptionDetails"]))
        result = response.get("result", {})
        if "value" not in result:
            raise RuntimeError("Passive browser observation did not return a JSON value")
        return result["value"]
    finally:
        detach_cdp(session)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def route_diagnostics(driver):
    return {"budget_policy": driver.budget_policy, "waypoint_budgets": driver.budgets,
            "current_waypoint": driver.current_waypoint, "physical_stops": driver.stops,
            "current_stop": driver.stop_boundary, "physical_actions": driver.actions,
            "chart_corridor": driver.corridor_receipt, "snapshot_stops": driver.snapshot_stops}


def last_observer_id(console, prefix, field):
    return max((positive_integer(item.get(field), field) for item in observer_receipts(console, prefix)), default=0)


def wait_observer(page, console, prefix, start, timeout=15, allow_runtime_exit=False):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.is_closed():
            raise RuntimeError(f"Browser page closed before {prefix}")
        if not allow_runtime_exit and any(item.get("text", "").startswith("TIDAL_FINAL ") for item in console[start:]):
            raise RuntimeError(f"Game exited before {prefix} could be accepted")
        receipts = observer_receipts(console, prefix, start)
        if receipts:
            if len(receipts) != 1:
                raise RuntimeError(f"Expected exactly one fresh {prefix} receipt")
            return receipts[0]
        page.wait_for_timeout(100)
    raise TimeoutError(f"Actual game did not emit a fresh {prefix} receipt")


# Preserve browser security defaults and its supported renderer selection.
# Playwright injects both mute and an unsafe renderer opt-in by default.
IGNORED_DEFAULT_ARGS = ["--mute-audio", "--enable-unsafe-swiftshader"]
# Chrome requires this diagnostic flag for Browser.getBrowserCommandLine.
# Supply it explicitly: persistent contexts do not necessarily inherit it.
BROWSER_ARGS = ["--disable-dev-shm-usage", "--enable-automation"]


def browser_executable(value):
    """Select one installed browser explicitly; never silently substitute it."""
    path = Path(value).resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("Explicit browser is not an executable file: " + str(path))
    result = subprocess.run([str(path), "--version"], check=True, capture_output=True, text=True, timeout=10)
    version = result.stdout.strip()
    if not re.fullmatch(r"(?:Google Chrome(?: for Testing)?|Chromium) [0-9]+(?:\.[0-9]+){3}(?: .*)?", version):
        raise ValueError("Unrecognized explicit browser version: " + version)
    return {"executable_path": str(path), "executable_version": version}


def validate_browser_arguments(arguments):
    forbidden = ("--mute-audio", "--no-sandbox", "--disable-setuid-sandbox", "--disable-web-security",
                 "--enable-unsafe-swiftshader", "--ignore-certificate-errors")
    if any(arg.split("=", 1)[0] in forbidden or "autoplay-policy" in arg for arg in arguments):
        raise RuntimeError("Acceptance browser contains an audio or security override")



AUDIO_CUES = (("chart_read", .72), ("key_pickup", 1.05), ("pearl_pickup", 1.65), ("beacon_resolve", 4.8))
QUIET_RMS = 1e-5
AUDIBLE_RMS = 1e-4


def validate_journey(receipt, trigger):
    if (type(receipt.get("schema")) is not int or receipt["schema"] != 1 or receipt.get("started") is not True
            or receipt.get("demo") is not False or receipt.get("trigger") != trigger):
        raise ValueError("Journey did not start through the expected actual input")


def audio_probe_init_script():
    source = Path(__file__).with_name("audio_meter_worklet.js").read_text()
    # One init script establishes source before installing hooks. Playwright
    # does not promise ordering among separate add_init_script calls.
    return ("Object.defineProperty(globalThis, '__tidalAudioWorkletSource', {value:" + json.dumps(source)
            + ", writable:false, configurable:false});\n" + Path(__file__).with_name("audio_probe.js").read_text())


def capture_audio_snapshot(page, timeout=120):
    return passive_evaluate(page, """async () => {
        const cutoff = __tidalAudio.mark('pcm-cutoff');
        const before = __tidalAudio.snapshot();
        const running = before.contexts.length === 1 && before.contexts[0].state === 'running';
        const barriers = running ? await __tidalAudio.flush() : [];
        const result = __tidalAudio.snapshot();
        result.pcm_cutoff = cutoff;
        result.pcm_barriers = barriers;
        return result;
    }""", timeout=timeout)


def audio_graph(snapshot):
    if type(snapshot.get("schema")) is not int or snapshot["schema"] != 1 or snapshot.get("errors") != [] or len(snapshot.get("contexts", [])) != 1:
        raise ValueError("Audio graph observation is missing, unknown or failed")
    context = snapshot["contexts"][0]
    terminals = [item for item in context.get("terminals", []) if item.get("active")]
    if (not terminals or not any(item.get("kind") == "GainNode" for item in terminals)
            or any(item.get("mirror_count") != 1 for item in terminals)
            or len({item.get("key") for item in terminals}) != len(terminals)):
        raise ValueError("Audio capture requires deduplicated genuine terminal edges including the post-mute gain")
    return context


def audio_window(snapshot, begin_ms, end_ms, minimum_seconds, audible=False, evidence_path=None):
    if evidence_path is not None:
        # Preserve this exact observed window before validation can reject it.
        # A later failure screenshot/snapshot has a different timing boundary.
        write_json(evidence_path, {"begin_ms": begin_ms, "end_ms": end_ms,
            "minimum_seconds": minimum_seconds, "audible": audible, "snapshot": snapshot})
    context = audio_graph(snapshot)
    # Source/graph metadata remains an independent main-thread observation.
    # It is never copied onto historical audio-thread PCM windows.
    for item in context.get("samples", []):
        if (type(item.get("active_music")) is not int or item["active_music"] > 1
                or any(type(item.get(key)) not in (int, float) or not math.isfinite(item[key])
                       for key in ("rms", "peak", "context_time"))
                or item.get("clipped_fraction", 1) > .001 or item["peak"] > 1.01):
            raise ValueError("Independent main-thread audio metadata is invalid or shows overlap/clipping")
    return marked_pcm_window(snapshot, context, begin_ms, end_ms, minimum_seconds, audible)


def validate_audio_baseline(snapshot, begin_ms):
    if snapshot.get("starts") or snapshot.get("gestures") or snapshot.get("user_activation", {}).get("has_been_active") is not False:
        raise ValueError("Fresh audio baseline must precede every real gesture and source start")
    context = audio_graph(snapshot)
    # A never-advanced suspended clock proves no sample was rendered, even when
    # software rendering starves the main-thread timer. This exact-zero invariant
    # is ONLY for first load; running/muted audio retains the strict dense meter.
    mark = next((item for item in snapshot.get("marks", []) if item.get("wall_ms") == begin_ms), None)
    clocks = (mark or {}).get("context_times", [])
    if (type(begin_ms) not in (int, float) or not math.isfinite(begin_ms) or begin_ms < 0
            or type(snapshot.get("wall_ms")) not in (int, float) or not math.isfinite(snapshot["wall_ms"])
            or snapshot["wall_ms"] - begin_ms < 2000
            or len(clocks) != 1 or clocks[0].get("id") != context.get("id")
            or type(clocks[0].get("time")) not in (int, float) or clocks[0]["time"] != 0
            or context.get("state") != "suspended" or type(context.get("context_time")) not in (int, float)
            or context["context_time"] != 0):
        raise ValueError("Fresh audio baseline must retain the same suspended zero clock for two seconds")
    samples = context.get("samples", [])
    terminals = [item for item in context.get("terminals", []) if item.get("active")]
    if (not samples or any(type(item.get("connected_ms")) not in (int, float)
                or not math.isfinite(item["connected_ms"]) or not 0 <= item["connected_ms"] <= begin_ms for item in terminals)
            or any(item.get("disconnected_ms") is not None for item in terminals)
            or any(item.get("state") != "suspended" or type(item.get("context_time")) not in (int, float)
                or item["context_time"] != 0 or any(type(item.get(key)) not in (int, float) or item[key] != 0
                for key in ("rms", "peak", "clipped_fraction")) or type(item.get("active_music")) is not int
                or item["active_music"] != 0 or item.get("active_cues") != [] for item in samples)):
        raise ValueError("Fresh suspended baseline contains a running clock, signal or changed terminal")
    return {"proof": "same never-advanced suspended AudioContext; no source or activation",
            "wall_seconds": (snapshot["wall_ms"] - begin_ms) / 1000, "context_id": context["id"],
            "context_time": 0, "samples": len(samples), "maximum_rms": 0, "audible": False}



def validate_muted_restore_audio(before, after, receipts):
    """Unmute the same real muted-Begin voice without replaying quest cues."""
    starts = [item for item in receipts if item.get("event") == "start"]
    if (len(starts) != 1 or type(starts[0].get("start_count")) is not int
            or starts[0]["start_count"] != 1 or starts[0].get("started") is not True
            or starts[0].get("muted") is not True
            or any(item.get("event") == "cue" for item in receipts)):
        raise ValueError("Restored muted Begin must start once without replaying story cues")
    prior, current = before.get("starts", []), after.get("starts", [])
    if not prior or len(current) < len(prior) or [item.get("id") for item in current[:len(prior)]] != [item.get("id") for item in prior]:
        raise ValueError("Unmute lost the original muted-Begin source history")
    first = current[0].get("scheduled_start")
    if type(first) not in (int, float) or not math.isfinite(first):
        raise ValueError("Restored music lacks a valid initial audio clock")
    for index, source in enumerate(current):
        clock = source.get("scheduled_start")
        if (source.get("name") != "music" or type(clock) not in (int, float) or not math.isfinite(clock)
                or abs(clock - first - 32 * index) > .02 or source.get("rate") != 1 or source.get("offset") != 0):
            raise ValueError("Unmute replayed a cue or restarted the authored music loop")
    return {"logical_starts": 1, "source_count": len(current), "replayed_cues": 0}


def source_end(source, fallback):
    values = [source.get(key) for key in ("planned_end", "stopped_context_time", "ended_context_time")]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values if value is not None):
        raise ValueError("Audio source lifetime contains invalid clock values")
    return min([value for value in values if value is not None] or [fallback])


def first_loop_cutoff_ready(snapshot, music):
    """Wait for the frozen PCM window, never its later delivery-time clock."""
    context = audio_graph(snapshot)
    clocks = [item.get("time") for item in snapshot.get("pcm_cutoff", {}).get("context_times", [])
              if item.get("id") == context["id"]]
    if (len(clocks) != 1 or type(clocks[0]) not in (int, float) or not math.isfinite(clocks[0])
            or clocks[0] < 0 or clocks[0] > context["context_time"]):
        raise ValueError("First loop wait lacks a genuine frozen PCM cutoff")
    # Keep the original first-boundary + 1.2 s observation margin. The full
    # unchanged validator still checks exact decoded seam, sources and PCM.
    return bool(music) and clocks[0] >= music[0]["scheduled_start"] + 33.2


def validate_loop_boundary(snapshot, music, receipts):
    context = audio_graph(snapshot)
    first = music[0]
    if abs(first["duration"] - 32) >= .005 or abs(first["offset"]) > .0001 or first["rate"] != 1:
        raise ValueError("Music did not begin at the authored 32-second loop origin")
    # Native WebAudio clamps loopEnd to the real decoded buffer duration.
    # The original Ogg decodes to 1,411,199 frames, one frame short of 32 s.
    boundary = first["scheduled_start"] + (min(first["duration"], first.get("loop_end", 32)) if first.get("looping") is True else 32)
    audible = next((item for item in snapshot.get("marks", []) if item.get("name") == "after-begin"), None)
    audible_clock = next((item.get("time") for item in (audible or {}).get("context_times", []) if item.get("id") == context["id"]), None)
    if (type(audible_clock) not in (int, float) or not math.isfinite(audible_clock)
            or not first["scheduled_start"] <= audible_clock <= boundary - 1.15):
        raise ValueError("First loop boundary lacks an established audible Begin interval")
    if first.get("looping") is True:
        if (first.get("detune") != 0 or first.get("loop_start") != 0 or first.get("loop_end") != 32
                or first.get("requested_duration") is not None or first.get("mutations") != []
                or first.get("parameter_automation") != []):
            raise ValueError("Native music loop must retain the unchanged full authored buffer and pitch")
        continuation = first
    else:
        continuation = next((item for item in music[1:] if
            abs(item["scheduled_start"] - boundary) <= .1 and abs(item["offset"]) <= .0001 and item["rate"] == 1), None)
    if (source_end(first, context["context_time"]) < boundary - .006 or continuation is None
            or source_end(continuation, context["context_time"]) < boundary + 1):
        raise ValueError("Music source does not genuinely continue across its first loop boundary")
    begin, end = boundary - 1.15, boundary + 1.15
    if continuation is first:
        path_proofs = [validate_source_bus(snapshot, first, context, begin, end, check_bus_gain=False)]
    else:
        path_proofs = [validate_source_bus(snapshot, first, context, begin, boundary, check_bus_gain=False),
                       validate_source_bus(snapshot, continuation, context, boundary, end, check_bus_gain=False)]
    buses = {proof["bus_id"] for proof in path_proofs}
    if len(buses) != 1:
        raise ValueError("Loop continuation changed its genuine music bus")
    reports = {}
    for name, bus in (("music_bus", next(iter(buses))), ("post_master", None)):
        windows = pcm_interval(context, begin, end, 2, source=bus, minimum_windows=16, edge_seconds=.15)
        rate = context["sample_rate"]
        if (sum(item["end_frame"] / rate <= boundary for item in windows) < 8
                or sum(item["start_frame"] / rate >= boundary for item in windows) < 8
                or any((right["start_frame"] - left["start_frame"]) / rate > .25 for left, right in zip(windows, windows[1:]))):
            raise ValueError("Loop seam lacks two seconds of dense actual PCM coverage")
        reports[name] = pcm_signal(windows, True, minimum_fraction=1)
    samples = reports["post_master"]
    return {"boundary_context_time": boundary, "continuing_source_id": continuation["id"],
            "first_context_time": samples["first_frame"] / context["sample_rate"],
            "last_context_time": samples["last_frame"] / context["sample_rate"],
            "meter_samples": samples["pcm_windows"], "pcm": reports, "source_paths": path_proofs}


def validate_audio_sources(snapshot, receipts, actions):
    context = audio_graph(snapshot)
    starts = snapshot.get("starts", [])
    music = [item for item in starts if item.get("name") == "music"]
    cues = [item for item in starts if item.get("name") != "music"]
    if not music or len(cues) != 4 or len(starts) != len(music) + 4:
        raise ValueError("Real source starts did not contain the loop and exactly four cues")
    first_gesture = min((item["wall_ms"] for item in snapshot.get("gestures", []) if item.get("trusted")), default=math.inf)
    for item in starts:
        for key in ("wall_ms", "duration", "pcm_peak", "scheduled_start", "context_time", "rate", "offset"):
            if type(item.get(key)) not in (int, float) or not math.isfinite(item[key]):
                raise ValueError("Audio source contains invalid numeric evidence")
        if (item.get("wall_ms", -1) < first_gesture or not item.get("path_at_start") or item["path_at_start"][-1] != context["destination"]
                or not item.get("nonzero_gain_path_at_start") or item["nonzero_gain_path_at_start"][-1] != context["destination"]
                or not item.get("pcm_fingerprint") or item.get("pcm_peak", 0) < AUDIBLE_RMS):
            raise ValueError("Audio source lacks a gesture, nonzero PCM or genuine destination path")
    if len({item["pcm_fingerprint"] for item in music}) != 1:
        raise ValueError("Music loop recreation changed its observed PCM fingerprint")
    # Godot Sample loops legitimately recreate sources. Reject overlapping voices,
    # rather than requiring a single source object over the entire traversal.
    intervals = []
    for item in music:
        end = min([value for value in (item.get("planned_end"), item.get("stopped_context_time"), item.get("ended_context_time")) if value is not None] or [context["context_time"]])
        intervals.append((item["scheduled_start"], end))
    intervals.sort()
    if any(right[0] < left[1] - .006 for left, right in zip(intervals, intervals[1:])):
        raise ValueError("Music sources overlap beyond two audio rendering quanta")
    if [item.get("muted") for item in receipts if item.get("event") == "mute"] != [True, False]:
        raise ValueError("Actual route must contain exactly one mute and unmute")
    loop_boundary = validate_loop_boundary(snapshot, music, receipts)
    if context["context_time"] - music[0]["scheduled_start"] < 32:
        raise ValueError("Live route did not cover one complete 32-second music loop")
    if any(item.get("active_music", 0) > 1 for item in context["samples"]):
        raise ValueError("Observed duplicate music voices")
    cue_receipts = [item for item in receipts if item.get("event") == "cue"]
    start_receipts = [item for item in receipts if item.get("event") == "start"]
    if (len(start_receipts) != 1 or type(start_receipts[0].get("start_count")) is not int or start_receipts[0]["start_count"] != 1
            or start_receipts[0].get("started") is not True or len(cue_receipts) != 4 or len(actions) != 4):
        raise ValueError("Audio receipts lack one real start and four physical-route cues")
    if any(type(item.get("schema")) is not int or item["schema"] != 1 for item in receipts):
        raise ValueError("Invalid audio receipt schema")
    fingerprints = set()
    pairs = []
    marks = {item["name"]: item["wall_ms"] for item in snapshot.get("marks", [])}
    for stage, ((name, duration), source, receipt, action) in enumerate(zip(AUDIO_CUES, cues, cue_receipts, actions)):
        if type(receipt.get("duration")) not in (int, float) or not math.isfinite(receipt["duration"]):
            raise ValueError("Cue receipt duration is not finite")
        if (source.get("name") != name or abs(source.get("duration", -1) - duration) >= .005
                or receipt.get("name") != name or type(receipt.get("stage")) is not int or receipt["stage"] != stage
                or type(receipt.get("count")) is not int or receipt["count"] != 1
                or abs(receipt.get("duration", -1) - duration) >= .005 or receipt.get("started") is not True
                or receipt.get("muted") is not False or action.get("from_stage") != stage
                or action.get("target_stage") != stage + 1 or not action.get("accepted_sample_id")
                or not marks.get("action-" + str(stage), math.inf) <= source["wall_ms"] < marks.get("action-" + str(stage + 1), math.inf)):
            raise ValueError("Cue PCM/source start does not match its exact physical action and stage receipt")
        lifetime = validate_cue_pcm(snapshot, source, context)
        fingerprints.add(source["pcm_fingerprint"])
        pairs.append({"stage": stage, "name": name, "source_id": source["id"], "pcm_fingerprint": source["pcm_fingerprint"],
                      "source_start_ms": source["wall_ms"], "physical_action": action, "receipt": receipt, "lifetime": lifetime})
    if len(fingerprints) != 4:
        raise ValueError("Cue fingerprints are not distinct")
    return {"music_source_count": len(music), "music_fingerprint": music[0]["pcm_fingerprint"],
            "music_observed_context_seconds": context["context_time"] - music[0]["scheduled_start"],
            "first_loop_boundary": loop_boundary, "cue_pairs": pairs}


def real_button(page, state, field, mobile, width, height, native_touch=False):
    x, y, w, h = finite_vector(state.get(field), 4, field)
    if w <= 0 or h <= 0 or not (0 <= x < x + w <= width and 0 <= y < y + h <= height):
        raise ValueError("Actual " + field + " is outside the rendered viewport")
    if mobile and native_touch:
        session = page.context.new_cdp_session(page)
        try:
            try:
                bounded_cdp(session, "Input.dispatchTouchEvent", {"type": "touchStart",
                    "touchPoints": [{"id": 0, "x": x + w / 2, "y": y + h / 2}]}, timeout=15)
            finally:
                bounded_cdp(session, "Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}, timeout=15)
        finally:
            detach_cdp(session)
    elif mobile:
        page.touchscreen.tap(x + w / 2, y + h / 2)
    else:
        page.mouse.click(x + w / 2, y + h / 2)
    return {"field": field, "kind": ("CDP native touch" if native_touch else "touchscreen.tap") if mobile else "mouse.click", "x": x + w / 2, "y": y + h / 2}


def native_save_return_touch(page, width, height):
    """Read the shipped control's hit target, then use the existing real touch path."""
    rect = passive_evaluate(page, """() => {
      const matches = document.querySelectorAll('#tidal-save-return');
      if (matches.length !== 1) return null;
      const button = matches[0], style = getComputedStyle(button);
      if (!button.isConnected || button.disabled || style.visibility !== 'visible' ||
          style.display === 'none' || Number(style.opacity) === 0) return null;
      const r = button.getBoundingClientRect();
      const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      if (!hit || !(hit === button || button.contains(hit))) return null;
      return [r.x, r.y, r.width, r.height];
    }""")
    return real_button(page, {"save_return_rect": rect}, "save_return_rect", True,
                       width, height, native_touch=True)


def configure_native_viewport(page, width, height, mobile):
    """Retained protocol session configures browser emulation, never game state."""
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0 or type(mobile) is not bool:
        raise ValueError("Invalid explicit browser viewport")
    session = page.context.new_cdp_session(page)
    try:
        bounded_cdp(session, "Emulation.setDeviceMetricsOverride", {"width": width, "height": height,
            "deviceScaleFactor": 1, "mobile": mobile, "screenWidth": width, "screenHeight": height}, timeout=15)
        bounded_cdp(session, "Emulation.setTouchEmulationEnabled", {"enabled": mobile,
            "maxTouchPoints": 5 if mobile else 1}, timeout=15)
    except Exception:
        detach_cdp(session)
        raise
    return session


def verify_native_viewport(page, width, height, mobile):
    value = passive_evaluate(page, "() => ({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,touch_points:navigator.maxTouchPoints})")
    if (value.get("width") != width or value.get("height") != height or value.get("dpr") != 1
            or value.get("touch_points") != (5 if mobile else 0)):
        raise ValueError("Actual browser viewport/DPR/touch capability differs from requested route: " + repr(value))
    return value


def wait_state(page, console, after_sample=0, predicate=lambda state: True, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        samples = observer_receipts(console, "TIDAL_STATE")
        if samples and samples[-1].get("sample_id", 0) > after_sample and predicate(samples[-1]):
            return samples[-1]
        page.wait_for_timeout(100)
    raise TimeoutError("No fresh actual state for the requested input boundary")


def audio_prepared(state):
    if state.get("audio_status") == "error":
        raise RuntimeError("Actual Web audio preparation failed: " + str(state.get("audio_error", "unreported error")))
    return state.get("audio_ready") is True



def validate_recorded_pcm(pcm, sample_rate):
    # Analyze only decoded live MediaRecorder bytes, never generate or mux audio.
    if not pcm or any(not math.isfinite(value) for value in pcm):
        raise ValueError("Recorded audio PCM is empty or invalid")
    size = sample_rate // 10
    rms = [math.sqrt(sum(value * value for value in pcm[offset:offset + size]) / size)
           for offset in range(0, len(pcm) - size + 1, size)]
    quiet_run = audible_run = longest_quiet = longest_audible = 0
    for value in rms:
        quiet_run = quiet_run + 1 if value <= QUIET_RMS else 0
        audible_run = audible_run + 1 if value >= AUDIBLE_RMS else 0
        longest_quiet, longest_audible = max(longest_quiet, quiet_run), max(longest_audible, audible_run)
    if longest_quiet < 10 or sum(value >= AUDIBLE_RMS for value in rms) < 320:
        raise ValueError("Actual recorded bytes lack one-second mute or 32 seconds of nonzero signal")
    return {"sample_rate": sample_rate, "seconds": len(pcm) / sample_rate, "maximum_rms": max(rms),
            "longest_quiet_seconds": longest_quiet / 10, "longest_audible_seconds": longest_audible / 10,
            "nonzero_seconds": sum(value >= AUDIBLE_RMS for value in rms) / 10,
            "source": "ffmpeg decoding of the original live browser WebM; mono meter analysis only"}


def save_live_audio(page, out, label):
    captured = passive_evaluate(page, "() => __tidalAudio.finishRecording()")
    encoded = captured.pop("base64")
    path = out / (label + "-live-audio.webm")
    data = base64.b64decode(encoded, validate=True)
    if len(data) != captured["bytes"] or len(data) < 1024:
        raise ValueError("Live browser audio byte transfer was incomplete")
    path.write_bytes(data)
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-show_packets",
        "-show_entries", "stream=codec_type,codec_name,sample_rate,channels:format=duration:packet=pts_time,duration_time", "-of", "json", str(path)], text=True, timeout=30))
    streams = probe.get("streams", [])
    packets = probe.pop("packets", [])
    if not packets:
        raise ValueError("Recorded live WebM contains no decoded audio packets")
    timestamps = [(float(item["pts_time"]), float(item.get("duration_time", 0))) for item in packets]
    packet_seconds = max(pts + duration for pts, duration in timestamps) - min(pts for pts, duration in timestamps)
    probe["audio_packet_span_seconds"] = packet_seconds
    probe["audio_packet_count"] = len(packets)
    if (len(streams) != 1 or streams[0].get("codec_type") != "audio" or streams[0].get("codec_name") != "opus"
            or not math.isfinite(packet_seconds) or packet_seconds < 32):
        raise ValueError("Recorded live browser WebM lacks a complete 32-second Opus audio stream")
    decoded = subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-vn", "-ac", "1",
        "-ar", "8000", "-f", "f32le", "pipe:1"], timeout=180)
    pcm = array.array("f")
    pcm.frombytes(decoded)
    decoded_signal = validate_recorded_pcm(pcm, 8000)
    captured.update({"file": path.name, "sha256": sha256(path), "media_probe": probe, "decoded_signal": decoded_signal,
        "claim": "browser-rendered live graph recording; no physical speaker or subjective listening claim"})
    return captured


def secondary_touch_tap(send_touch, primary_points, action, pause):
    if len(primary_points) != 1 or primary_points[0].get("id") != 0 or action.get("id") != 1:
        raise ValueError("Second-finger tap requires the original held primary finger")
    # The default Chromium DispatchWebTouchEvent path takes CHANGED points,
    # unlike its optional SyntheticPointerActions active-set path. End only ID 1;
    # sending ID 0 ends steering, while omitting ID 1 in touchMove never ends it.
    # https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/content/browser/devtools/protocol/input_handler.cc
    send_touch("touchStart", [action])
    pause(.09)
    send_touch("touchEnd", [action])


def completed_route_save(console, start, expected):
    """Select a real save after this physical route's actual completion receipt."""
    completed_index = None
    for index in range(start, len(console)):
        receipts = observer_receipts(console[index:index + 1], "TIDAL_COMPLETE")
        if receipts:
            receipt = receipts[0]
            if receipt.get("demo") is not False or type(receipt.get("stage")) is not int or receipt["stage"] != 4:
                raise ValueError("Save boundary lacks an actual physical-route completion")
            completed_index = index
            break
    if completed_index is None:
        return None
    saves = observer_receipts(console, "TIDAL_SAVE", completed_index + 1)
    if not saves:
        return None
    saved = saves[-1]
    if type(saved.get("schema")) is not int or saved["schema"] != 1 or not complete(saved):
        raise ValueError("Actual completion save is malformed or incomplete")
    before = finite_vector(expected.get("position"), 3, "completed route position")
    after = finite_vector(saved.get("position"), 3, "actual saved position")
    if saved.get("language") != expected.get("language") or math.hypot(before[0] - after[0], before[2] - after[2]) > .35:
        raise ValueError("Actual completion save differs from the completed route")
    return saved


def wait_completed_route_save(page, console, start, expected, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.is_closed():
            raise RuntimeError("Browser closed before the actual completion save")
        saved = completed_route_save(console, start, expected)
        if saved is not None:
            return saved
        page.wait_for_timeout(100)
    raise TimeoutError("No actual save after the physical-route completion")



def validate_web_exit(receipt, expected):
    if (type(receipt.get("schema")) is not int or receipt["schema"] != 1 or
            type(receipt.get("code")) is not int or receipt["code"] != 0 or
            any(receipt.get(key) is not True for key in ("requested", "trusted", "ok", "save_after_request", "audio_closed"))):
        raise ValueError("Save/return lacks a successful real-input final-sync exit")
    saved = receipt.get("saved")
    if (not isinstance(saved, dict) or type(saved.get("schema")) is not int or saved["schema"] != 1 or
            saved.get("persistent") is not True or saved.get("reason") != "exit" or not complete(saved)):
        raise ValueError("Save/return lacks the actual completed final save")
    before = finite_vector(expected.get("position"), 3, "completed route position")
    after = finite_vector(saved.get("position"), 3, "final saved position")
    if (saved.get("language") != expected.get("language") or
            type(expected.get("audio_muted")) is not bool or
            type(saved.get("audio_muted")) is not bool or
            saved["audio_muted"] is not expected["audio_muted"] or
            math.hypot(before[0] - after[0], before[2] - after[2]) > .35):
        raise ValueError("Final save differs from the completed route")
    return saved


def validate_audio_closed(before, after):
    """Observe real context/source closure separately from the engine receipt."""
    prior = audio_graph(before)
    contexts = after.get("contexts", [])
    if (after.get("errors") != [] or len(contexts) != 1 or contexts[0].get("id") != prior.get("id")
            or contexts[0].get("state") != "closed"
            or any(item.get("active") for item in contexts[0].get("terminals", []))):
        raise ValueError("Normal exit did not close the same sole real audio graph")
    if [item.get("id") for item in before.get("starts", [])] != [item.get("id") for item in after.get("starts", [])]:
        raise ValueError("Exit created or replaced an audio source")
    samples = contexts[0].get("samples", [])
    if not samples or samples[-1].get("active_music") != 0 or samples[-1].get("active_cues") != []:
        raise ValueError("Closed graph retains a connected live voice")
    return {"context_id": prior["id"], "state": "closed", "connected_voices": 0}


def validate_focus_suspension(before, suspended, returned, begin_ms, end_ms):
    """Fresh actual meters and a frozen clock, not focus intent receipts alone."""
    original, away, restored = audio_graph(before), audio_graph(suspended), audio_graph(returned)
    if original["id"] != away["id"] or original["id"] != restored["id"]:
        raise ValueError("Focus transition replaced the original audio context")
    ids = [item.get("id") for item in before.get("starts", [])]
    if any([item.get("id") for item in value.get("starts", [])] != ids for value in (suspended, returned)):
        raise ValueError("Focus transition restarted a source or replayed a cue")
    samples = [item for item in away["samples"] if begin_ms <= item.get("wall_ms", -1) <= end_ms]
    # Web Audio explicitly freezes AnalyserNode data during suspension. Keep
    # those real samples unchanged: old nonzero PCM is not current output.
    # https://www.w3.org/TR/webaudio-1.1/#dom-audiocontext-suspend
    if (len(samples) < 5 or samples[-1]["wall_ms"] - samples[0]["wall_ms"] < 1100
            or any(b["wall_ms"] - a["wall_ms"] > 1000 for a, b in zip(samples, samples[1:]))):
        raise ValueError("Focus suspension lacks sustained fresh wall-time observations")
    clocks = [item.get("context_time") for item in samples]
    gains = {item["source"] for item in away["terminals"] if item.get("active") and item.get("kind") == "GainNode"}
    for item in samples:
        raw_gains = item.get("terminal_gain_values", [])
        if (not gains or {value.get("source") for value in raw_gains} != gains
                or len(raw_gains) != len(gains)
                or any(type(value.get("value")) not in (int, float) or value["value"] != 0 for value in raw_gains)
                or item.get("active_music") != 1 or item.get("active_cues") != []
                or any(type(item.get(key)) not in (int, float) or not math.isfinite(item[key]) for key in ("rms", "peak", "context_time"))):
            raise ValueError("Suspended focus lacks its original voice and genuinely muted terminal")
    if any(item.get("state") != "suspended" for item in samples) or max(clocks) - min(clocks) > .006:
        raise ValueError("Background audio clock was not genuinely suspended")
    if restored.get("state") != "running" or restored.get("context_time", 0) <= max(clocks):
        raise ValueError("Returning focus did not resume the same audio clock")
    return {"context_id": original["id"], "same_source_ids": ids, "fresh_samples": len(samples),
            "suspended_clock": clocks[0], "terminal_gain": 0,
            "analyser_scope": "frozen pre-suspend PCM retained; silence follows the stopped rendering clock and muted genuine terminal"}


def capture_png(page, path, diagnostic=False):
    started = time.monotonic()
    timeout = 30 if diagnostic else 120
    session = page.context.new_cdp_session(page)
    try:
        result = bounded_cdp(session, "Page.captureScreenshot", {"format": "png", "fromSurface": True,
            "captureBeyondViewport": False}, timeout=timeout)
        png = base64.b64decode(result["data"], validate=True)
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Passive browser capture did not produce PNG bytes")
        path.write_bytes(png)
    finally:
        detach_cdp(session)
    return {"name": path.name, "wall_seconds": time.monotonic() - started,
            "timeout_seconds": timeout, "diagnostic": diagnostic, "method": "CDP Page.captureScreenshot; no evaluation preflight"}


def verify_passive_protocol(pw, out, launch_options):
    """A fresh blank browser verifies real timeout recovery, never game state."""
    browser = pw.chromium.launch(**launch_options)
    try:
        context = browser.new_context()
        page = context.new_page()
        page.goto("data:text/html,<body>Passive protocol smoke fixture</body>")
        session = context.new_cdp_session(page)
        timed_out = False
        try:
            try:
                bounded_cdp(session, "Runtime.evaluate", {"expression": "new Promise(() => {})",
                    "awaitPromise": True, "returnByValue": True, "userGesture": False}, timeout=.1)
            except PlaywrightTimeoutError:
                timed_out = True
        finally:
            detach_cdp(session)
        if not timed_out:
            raise RuntimeError("CDP adapter did not enforce the real driver timeout")
        value = passive_evaluate(page, "() => ({active:navigator.userActivation.hasBeenActive, value:7})")
        if value != {"active": False, "value": 7}:
            raise RuntimeError("Passive observation manufactured activation after timeout recovery")
        capture_png(page, out / "passive-protocol-smoke.png", diagnostic=True)
        if passive_evaluate(page, "() => navigator.userActivation.hasBeenActive") is not False:
            raise RuntimeError("Passive screenshot manufactured user activation")
        try:
            passive_evaluate(page, "() => Promise.reject(new Error('expected smoke rejection'))")
        except RuntimeError as error:
            if "expected smoke rejection" not in str(error):
                raise
        else:
            raise RuntimeError("Passive observation ignored a rejected Promise")
        return {"passed": True, "driver_timeout_seconds": .1, "post_timeout_call": True,
                "screenshot_preserves_no_activation": True, "rejected_promise_propagates": True}
    finally:
        browser.close()


def wait_ready(page, console, failures):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline and not any(item["text"].startswith("TIDAL_FRAME_READY ") for item in console):
        if failures:
            raise RuntimeError("Browser failed before frame readiness: " + json.dumps(failures))
        if page.is_closed():
            raise RuntimeError("Browser page closed before actual first frame")
        page.wait_for_timeout(100)
    if not any(item["text"].startswith("TIDAL_FRAME_READY ") for item in console):
        raise RuntimeError("Actual exported Godot did not emit TIDAL_FRAME_READY after frame_post_draw")
    passive_evaluate(page, "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chromium", required=True, help="Explicit installed Chrome/Chromium executable; no fallback")
    parser.add_argument("--headed", action="store_true", help="Real visible Chrome tabs; requires an X11 display, no headless fallback")
    parser.add_argument("--no-defaults", action="store_true", help="Official default-context attach; requires explicit browser mode, no fallback")
    parser.add_argument("--standard-headless", action="store_true", help="Standard Chrome headless with no-defaults; no GPU overrides")
    args = parser.parse_args()
    if args.standard_headless and (args.headed or not args.no_defaults):
        parser.error("--standard-headless requires --no-defaults and excludes --headed")
    if args.no_defaults and not (args.headed or args.standard_headless):
        parser.error("--no-defaults requires an explicit browser mode")
    hidden_required = args.headed or args.standard_headless
    out = isolated_output(args.output, args.site)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(args.site.resolve())))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/index.html"
    report = {"passed": False, "browser": "Chromium", "checks": [], "viewports": [],
              "limitations": ["Portrait uses Chromium device emulation, not a physical phone.",
                  "Rendered screenshots are not subjective visual acceptance.",
                  "Input uses real browser keyboard/touch events with passive state observations; no scripted demo.",
                  "No multiplayer, deployment, accessibility, or broad device compatibility claim.",
                  "Audio is browser-rendered capture, not physical speaker output or subjective audition.",
                  "Audio-thread continuity is independent of game frame rate; it does not establish responsive or playable rendering.",
                  "Explicit headed and standard-headless no-defaults modes require actual hidden-tab transitions; legacy headless covers target focus only. Visible-unfocused desktop density remains runtime-limited in run39365593281; OS/application focus and physical-device behavior remain unverified."],
              "playwright_version": importlib.metadata.version("playwright"),
              "browser_launch": {"args": BROWSER_ARGS, "ignored_default_args": IGNORED_DEFAULT_ARGS,
                                 "chromium_sandbox": True, "headless": not args.headed, "no_defaults": args.no_defaults, "requested_executable": args.chromium,
                                 "args_scope": "Playwright passive protocol preflight and legacy route; no-defaults actual arguments are in each viewport browser_processes receipt"},
              "pack_sha256": sha256(args.site / "index.pck"),
              "observer_sha256": {name:sha256(Path(__file__).with_name(name)) for name in
                  ("audio_probe.js", "audio_meter_worklet.js", "audio_thread.py", "audio_source_contract.py", "capture_browser.py", "focus_lifecycle.py", "external_chrome.py")}}
    try:
        if report["playwright_version"] != "1.63.0":
            raise RuntimeError("This acceptance lane requires pinned Playwright 1.63.0")
        selected = browser_executable(args.chromium)
        report["browser_launch"].update(selected)
        launch_options = {"headless": not args.headed, "args": BROWSER_ARGS, "ignore_default_args": IGNORED_DEFAULT_ARGS,
                          "chromium_sandbox": True, "executable_path": selected["executable_path"]}
        with sync_playwright() as pw:
            report["passive_protocol"] = verify_passive_protocol(pw, out, launch_options)
            for width, height, mobile in ((1280, 720, False), (390, 844, True)):
                label = "portrait-390x844" if mobile else "desktop-1280x720"
                result = {"name": label, "width": width, "height": height, "passed": False, "rendered": False,
                          "audio": {"status": "not_run"}, "input": {"status": "not_run"}, "language": {"status": "not_run"}, "restore": {"status": "not_run"}}
                report["viewports"].append(result)
                console, failures, requests, events, screenshots = [], [], [], [], []
                restored_console, restored_failures = [], []
                context = page = None
                pressed = set()
                touch_points = []
                driver = None
                focus_probe = None
                focus_companion = None
                profile_owner = contextlib.ExitStack()
                profile = profile_owner.enter_context(OwnedChromeProfile()) if args.no_defaults else tempfile.TemporaryDirectory(prefix="tidal-" + label + "-profile-")
                external_manager = None
                viewport_session = None
                result["browser_processes"] = []

                def launch():
                    nonlocal external_manager
                    if args.no_defaults:
                        process_report = {}
                        result["browser_processes"].append(process_report)
                        external_manager = external_chrome(pw, selected["executable_path"], report=process_report,
                            profile=profile, timeout=15, headed=args.headed)
                        _, default_context = external_manager.__enter__()
                        if len(default_context.pages) != 1 or default_context.pages[0].url != "about:blank":
                            raise RuntimeError("Fresh owned Chrome did not start with exactly its requested blank page")
                        return default_context
                    return pw.chromium.launch_persistent_context(profile.name, **launch_options,
                        viewport={"width": width, "height": height}, device_scale_factor=1,
                        is_mobile=mobile, has_touch=mobile)

                def close_current(normal=False):
                    nonlocal external_manager
                    if external_manager is not None:
                        try:
                            if normal:
                                profile.close_normally(bounded_cdp, timeout=15)
                        finally:
                            external_manager.__exit__(None, None, None)
                            external_manager = None
                    elif context is not None:
                        context.close()

                def attach(target_page, target_console, target_failures):
                    target_page.on("console", lambda event: target_console.append({"type": event.type, "text": event.text}))
                    target_page.on("pageerror", lambda error: target_failures.append(str(error)))
                    target_page.on("requestfailed", lambda request: target_failures.append(request.url + ": " + str(request.failure)))
                    target_page.on("request", lambda request: requests.append(request.url))

                def send_touch(kind, points):
                    session.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": points})
                    events.append({"time": time.monotonic(), "kind": kind, "touchPoints": [dict(item) for item in points]})

                def move(direction):
                    nonlocal touch_points
                    if mobile:
                        x, y = direction
                        wanted = [{"id": 0, "x": origin[0] + x * 65, "y": origin[1] + y * 65}]
                        if wanted != touch_points:
                            send_touch("touchMove", wanted)
                            touch_points = wanted
                    else:
                        wanted = keyboard_direction(direction)
                        for key in sorted(pressed - wanted):
                            page.keyboard.up(key)
                            events.append({"time": time.monotonic(), "kind": "keyup", "key": key})
                            pressed.remove(key)
                        for key in sorted(wanted - pressed):
                            page.keyboard.down(key)
                            events.append({"time": time.monotonic(), "kind": "keydown", "key": key})
                            pressed.add(key)

                def interact(state):
                    passive_evaluate(page, "name => __tidalAudio.mark(name)", "action-" + str(state["quest_stage"]))
                    if mobile:
                        x, y, w, h = state["action_rect"]
                        action = {"id": 1, "x": x + w / 2, "y": y + h / 2}
                        if not 0 <= action["x"] <= width or not 0 <= action["y"] <= height:
                            raise RuntimeError("Actual touch action button is outside the rendered viewport")
                        secondary_touch_tap(send_touch, touch_points, action,
                                            lambda seconds: page.wait_for_timeout(seconds * 1000))
                    else:
                        page.keyboard.press("e", delay=80)
                        events.append({"time": time.monotonic(), "kind": "keypress", "key": "e"})

                def states():
                    if page.is_closed() or any(item["text"].startswith("TIDAL_FINAL ") for item in console):
                        raise RuntimeError("Game exited during actual browser-input route")
                    if failures:
                        raise RuntimeError("Browser errors during actual input: " + json.dumps(failures))
                    if mobile and observer_receipts(console, "TIDAL_TOUCH_RELEASE", touch_boundary):
                        raise RuntimeError("Primary steering finger was released before the continuous route finished")
                    return observer_receipts(console, "TIDAL_STATE")

                def capture(name, diagnostic=False):
                    receipt = capture_png(page, out / name, diagnostic)
                    result.setdefault("captures", []).append(receipt)
                    return receipt

                def screenshot(name, state):
                    file = out / (label + "-" + name)
                    receipt = capture(file.name)
                    screenshots.append({"name": file.name, "kind": "physical-input-route", "state": state,
                                        "state_timing": "passive sample before screenshot request",
                                        "capture_wall_seconds": receipt["wall_seconds"],
                                        "sha256": sha256(file), "bytes": file.stat().st_size})

                try:
                    context = launch()
                    page = context.pages[0]
                    if args.no_defaults:
                        viewport_session = configure_native_viewport(page, width, height, mobile)
                    focus_probe = RealTargetFocus(page, bounded_cdp, passive_evaluate, require_hidden=hidden_required, defaults_disabled=args.no_defaults)
                    # Create the companion BEFORE the real journey and all audio
                    # baselines. Its automatic activation must not introduce an
                    # unrequested mid-route focus/suspend transition.
                    other_tab = context.new_page()
                    focus_companion = RealTargetFocus(other_tab, bounded_cdp, passive_evaluate, require_hidden=hidden_required, defaults_disabled=args.no_defaults)
                    other_tab.goto("about:blank")
                    focus_companion.settle_after_navigation(timeout=15)
                    bounded_cdp(focus_probe.session, "Page.bringToFront", {}, timeout=3)
                    report["browser_version"] = context.browser.version if context.browser else passive_evaluate(page, "() => navigator.userAgent")
                    context.add_init_script(script=audio_probe_init_script())
                    command_session = context.new_cdp_session(page)
                    actual_args = command_session.send("Browser.getBrowserCommandLine")["arguments"]
                    result["browser_arguments"] = actual_args
                    validate_browser_arguments(actual_args)
                    command_session.detach()
                    attach(page, console, failures)
                    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    if response is None or response.status != 200:
                        raise RuntimeError("Staged Web entry did not return HTTP 200")
                    focus_probe.settle_after_navigation(timeout=15)
                    if hidden_required:
                        focus_probe.verify_same_window_tabs(focus_companion, timeout=15)
                    wait_focus_state(page, passive_evaluate, True, timeout=15)
                    wait_ready(page, console, failures)
                    if args.no_defaults:
                        result["viewport"] = verify_native_viewport(page, width, height, mobile)
                    # Read the game's existing context after its actual first draw.
                    # This identity is diagnostic, never an alternate pass condition.
                    result["graphics"] = passive_evaluate(page, """() => {
                        const gl = document.querySelector('#canvas').getContext('webgl2');
                        if (!gl) return {available:false};
                        const debug = gl.getExtension('WEBGL_debug_renderer_info');
                        return {available:true, version:gl.getParameter(gl.VERSION),
                            vendor:gl.getParameter(gl.VENDOR), renderer:gl.getParameter(gl.RENDERER),
                            unmasked_vendor:debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null,
                            unmasked_renderer:debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null};
                    }""")
                    bounds = passive_evaluate(page, "() => {const box = document.querySelector('#canvas')?.getBoundingClientRect(); return box ? {width:box.width,height:box.height} : null;}")
                    if not bounds or bounds["width"] < width - 2 or bounds["height"] < height - 2:
                        raise RuntimeError("Actual Web game canvas did not fill requested viewport")
                    if not passive_evaluate(page, "() => document.documentElement.scrollWidth <= innerWidth + 1"):
                        raise RuntimeError("Web shell overflows horizontally at requested viewport")
                    result["audio"] = {"status": "running", "scope": "fresh-profile real-input browser audio"}
                    ready_audio = wait_state(page, console, predicate=audio_prepared)
                    if ready_audio.get("audio_driver") != "Dummy":
                        raise ValueError("Official Web export did not select its declared Dummy audio driver")
                    result["audio"]["backend"] = observer_receipts(console, "TIDAL_AUDIO_BACKEND")
                    result["audio"]["observer_ready"] = passive_evaluate(page, "() => __tidalAudio.ready()")
                    recording = passive_evaluate(page, "() => __tidalAudio.startRecording()")
                    baseline_mark = passive_evaluate(page, "() => __tidalAudio.mark('no-input-baseline')")
                    page.wait_for_timeout(2300)
                    baseline = capture_audio_snapshot(page)
                    result["audio"]["baseline"] = validate_audio_baseline(baseline, baseline_mark["wall_ms"])
                    write_json(out / (label + "-audio-baseline.json"), baseline)
                    initial_state = wait_state(page, console)
                    if initial_state.get("journey_started") is not False:
                        raise RuntimeError("Fresh journey started before its actual Begin gesture")
                    capture(label + ".png")
                    post_capture = capture_audio_snapshot(page)
                    result["audio"]["before_begin"] = validate_audio_baseline(post_capture, baseline_mark["wall_ms"])
                    write_json(out / (label + "-audio-before-begin.json"), post_capture)
                    boundary = len(console)
                    begin_input = real_button(page, initial_state, "begin_rect", mobile, width, height, native_touch=args.no_defaults)
                    events.append({"time": time.monotonic(), "kind": "begin", **begin_input})
                    journey = wait_observer(page, console, "TIDAL_JOURNEY", boundary)
                    validate_journey(journey, "touch_begin" if mobile else "begin_button")
                    wait_state(page, console, initial_state["sample_id"], lambda state: state.get("journey_started") is True)
                    result["journey"] = {"input": begin_input, "receipt": journey}
                    page.wait_for_timeout(2100)  # Actual authored 1.5-second music fade.
                    audible_mark = passive_evaluate(page, "() => __tidalAudio.mark('after-begin')")
                    page.wait_for_timeout(1500)
                    audible = capture_audio_snapshot(page)
                    result["audio"]["after_begin"] = audio_window(audible, audible_mark["wall_ms"], audible["wall_ms"], 1.2, audible=True,
                        evidence_path=out / (label + "-audio-after-begin-window.json"))
                    # Observe the FIRST authored seam before deliberately muting.
                    # On slow software rendering, input and passive observations can
                    # consume more than one loop. Never substitute a later seam or
                    # expect an intentionally muted first seam to be audible.
                    first_loop_deadline = time.monotonic() + 45
                    while True:
                        remaining = first_loop_deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError("Actual audio clock did not reach its first loop seam")
                        first_loop_audio = capture_audio_snapshot(page, timeout=remaining)
                        if time.monotonic() >= first_loop_deadline:
                            raise TimeoutError("First loop observation exceeded its bounded deadline")
                        first_music = [item for item in first_loop_audio["starts"] if item["name"] == "music"]
                        if first_loop_cutoff_ready(first_loop_audio, first_music):
                            break
                        if time.monotonic() >= first_loop_deadline:
                            raise TimeoutError("Actual audio clock did not reach its first loop seam")
                        page.wait_for_timeout(200)
                    # Retain the actual evidence even if its strict validation fails.
                    write_json(out / (label + "-audio-first-loop.json"), first_loop_audio)
                    result["audio"]["first_loop_before_mute"] = validate_loop_boundary(
                        first_loop_audio, first_music, observer_receipts(console, "TIDAL_AUDIO"))
                    # Toggle the same visible shipped button with actual input.
                    mute_state = wait_state(page, console)
                    boundary = len(console)
                    mute_input = real_button(page, mute_state, "audio_rect", mobile, width, height, native_touch=args.no_defaults)
                    muted = wait_observer(page, console, "TIDAL_AUDIO", boundary)
                    if muted.get("event") != "mute" or muted.get("muted") is not True or muted.get("started") is not True:
                        raise ValueError("Actual mute input did not mute the live game")
                    wait_state(page, console, mute_state["sample_id"], lambda state: state.get("audio_muted") is True)
                    page.wait_for_timeout(500)  # Bounded meter/history tail; never wait indefinitely for silence.
                    quiet_mark = passive_evaluate(page, "() => __tidalAudio.mark('muted')")
                    page.wait_for_timeout(1400)
                    quiet = capture_audio_snapshot(page)
                    result["audio"]["muted"] = {"input": mute_input, "receipt": muted, "tail_allowance_seconds": .5,
                        "window": audio_window(quiet, quiet_mark["wall_ms"], quiet["wall_ms"], 1.1)}
                    unmute_state = wait_state(page, console)
                    boundary = len(console)
                    unmute_input = real_button(page, unmute_state, "audio_rect", mobile, width, height, native_touch=args.no_defaults)
                    unmuted = wait_observer(page, console, "TIDAL_AUDIO", boundary)
                    if unmuted.get("event") != "mute" or unmuted.get("muted") is not False or unmuted.get("started") is not True:
                        raise ValueError("Actual unmute input did not restore the live game")
                    wait_state(page, console, unmute_state["sample_id"], lambda state: state.get("audio_muted") is False)
                    page.wait_for_timeout(250)
                    unmute_mark = passive_evaluate(page, "() => __tidalAudio.mark('unmuted')")
                    page.wait_for_timeout(1500)
                    unmute_snapshot = capture_audio_snapshot(page)
                    result["audio"]["unmuted"] = {"input": unmute_input, "receipt": unmuted,
                        "window": audio_window(unmute_snapshot, unmute_mark["wall_ms"], unmute_snapshot["wall_ms"], 1.2, audible=True)}
                    result["audio"]["recording"] = recording
                    page.locator("#canvas").focus()
                    if not mobile:
                        blocked_state = wait_state(page, console)
                        if blocked_state.get("interaction_available") is not False or blocked_state.get("quest_stage") != 0:
                            raise ValueError("Fresh spawn cannot provide the required out-of-range interaction probe")
                        blocked_boundary = len(console)
                        blocked_before = capture_audio_snapshot(page)
                        page.keyboard.press("e", delay=80)
                        events.append({"time": time.monotonic(), "kind": "blocked-keypress", "key": "e"})
                        blocked_receipt = wait_observer(page, console, "TIDAL_INTERACTION_BLOCKED", blocked_boundary)
                        if (blocked_receipt.get("stage") != 0 or blocked_receipt.get("demo") is not False
                                or blocked_receipt.get("reason") in (None, "ready")):
                            raise ValueError("Actual blocked E lacks the in-game rejection receipt")
                        blocked_after_state = wait_state(page, console, blocked_state["sample_id"])
                        page.wait_for_timeout(1200)
                        blocked_after = capture_audio_snapshot(page)
                        if (blocked_after_state.get("quest_stage") != 0 or
                                any(item.get("event") == "cue" for item in observer_receipts(console, "TIDAL_AUDIO", blocked_boundary)) or
                                len([item for item in blocked_after["starts"] if item["name"] != "music"]) !=
                                len([item for item in blocked_before["starts"] if item["name"] != "music"])):
                            raise ValueError("Blocked actual E advanced progress or started a cue")
                        result["audio"]["blocked_action"] = {"trigger": "key_E", "receipt": blocked_receipt, "before": blocked_state,
                            "after": blocked_after_state, "passed": True}
                    result.update({"canvas": bounds, "rendered": True,
                        "ready_log": next(item["text"] for item in console if item["text"].startswith("TIDAL_FRAME_READY ")),
                        "loaded_wasm": any(url.endswith(".wasm") for url in requests),
                        "loaded_pack": any(url.endswith(".pck") for url in requests)})
                    if not result["loaded_wasm"] or not result["loaded_pack"]:
                        raise RuntimeError("Screenshot lacked actual runtime/pack requests")
                    report["checks"].append({"name": label + " actual WebGL 2 Godot scene", "passed": True})
                    if not mobile:
                        result["language"] = {"status": "running", "route": "physical browser L at fresh quest start"}
                        previous_change = last_observer_id(console, "TIDAL_LANGUAGE_FRAME", "change_id")
                        boundary = len(console)
                        page.keyboard.press("l", delay=80)
                        language = wait_observer(page, console, "TIDAL_LANGUAGE_FRAME", boundary)
                        validate_language_frame(language, previous_change)
                        result["language"].update({"status": "passed", "receipt": language})
                        capture("desktop-zh.png")
                        # The real second keypress restores English; never edit UI/state directly.
                        boundary = len(console)
                        page.keyboard.press("l", delay=80)
                        reverted = wait_observer(page, console, "TIDAL_LANGUAGE_FRAME", boundary)
                        if reverted.get("language") != "en" or reverted.get("trigger") != "key_L":
                            raise RuntimeError("Second actual L key did not restore English")
                    else:
                        result["language"] = {"status": "not_requested", "reason": "Desktop independently checks the actual Chinese UI"}
                    result["input"] = {"status": "running", "route": "uninterrupted Chromium touch drag with second-finger action taps" if mobile else "physical browser WASD/E"}
                    if mobile:
                        session = context.new_cdp_session(page)
                        origin = (width * .22, height * .72)
                        previous_gesture = last_observer_id(console, "TIDAL_TOUCH_RELEASE", "gesture_id")
                        touch_boundary = len(console)
                        touch_points = [{"id": 0, "x": origin[0], "y": origin[1]}]
                        send_touch("touchStart", touch_points)
                    route_console_boundary = len(console)
                    driver = RouteDriver(states, move, interact, lambda seconds: page.wait_for_timeout(seconds * 1000), screenshot,
                        physics_timeout=BROWSER_PHYSICS_LIMIT_SECONDS,
                        absolute_wall_timeout=BROWSER_ABSOLUTE_WALL_LIMIT_SECONDS)
                    result["input"]["budget_policy"] = driver.budget_policy
                    try:
                        route = driver.run()
                    finally:
                        if mobile and touch_points:
                            send_touch("touchEnd", [])
                            touch_points = []
                        for key in list(pressed):
                            page.keyboard.up(key)
                            pressed.remove(key)
                    if mobile:
                        receipt = wait_observer(page, console, "TIDAL_TOUCH_RELEASE", touch_boundary)
                        distance = validate_touch_release(receipt, previous_gesture, expected_touch_index=0)
                        result["input"]["touch_release"] = receipt
                        result["input"]["horizontal_displacement"] = distance
                    result["input"].update({"status": "passed", "route_receipt": route, "screenshots": screenshots})
                    if len(screenshots) != 5:
                        raise RuntimeError("Actual browser route did not capture its five playable milestones")
                    report["checks"].append({"name": label + " actual input completes treasure loop and walks/wades/swims/returns to shore", "passed": True})

                    # Repeated action after completion must not restart progress or emit a fifth cue.
                    negative_before = capture_audio_snapshot(page)
                    negative_state = wait_state(page, console)
                    negative_receipts = len([item for item in observer_receipts(console, "TIDAL_AUDIO") if item.get("event") == "cue"])
                    if mobile:
                        real_button(page, negative_state, "action_rect", True, width, height, native_touch=args.no_defaults)
                    else:
                        page.keyboard.press("e", delay=80)
                    negative_after_state = wait_state(page, console, negative_state["sample_id"])
                    page.wait_for_timeout(1200)
                    negative_after = capture_audio_snapshot(page)
                    if (not complete(negative_after_state) or
                            len([item for item in negative_before["starts"] if item["name"] != "music"]) !=
                            len([item for item in negative_after["starts"] if item["name"] != "music"]) or
                            negative_receipts != len([item for item in observer_receipts(console, "TIDAL_AUDIO") if item.get("event") == "cue"])):
                        raise ValueError("Repeated completed action changed progress or played an extra cue")
                    result["audio"]["repeated_action"] = {"trigger": "touch" if mobile else "key_E", "before": negative_state,
                        "after": negative_after_state, "cue_count": negative_receipts, "passed": True}
                    # The real route normally lasts far more than a loop. If unusually
                    # fast, remain idle in the actual game until the bounded 32s span.
                    loop_deadline = time.monotonic() + 40
                    while True:
                        current_audio = capture_audio_snapshot(page)
                        music_starts = [item for item in current_audio["starts"] if item["name"] == "music"]
                        cue_starts = [item for item in current_audio["starts"] if item["name"] != "music"]
                        audio_time = audio_graph(current_audio)["context_time"]
                        cue_end = max((item["scheduled_start"] + item["duration"] for item in cue_starts), default=math.inf)
                        if music_starts and audio_time - music_starts[0]["scheduled_start"] >= 33 and len(cue_starts) == 4 and audio_time >= cue_end + .15:
                            break
                        if time.monotonic() >= loop_deadline:
                            raise TimeoutError("Real audio clock did not cover a complete loop and the ending cue tail")
                        page.wait_for_timeout(200)
                    audio_snapshot = capture_audio_snapshot(page)
                    result["audio"]["sources"] = validate_audio_sources(audio_snapshot, observer_receipts(console, "TIDAL_AUDIO"), driver.actions)
                    # Keep recording through actual tab focus and normal exit.
                    wait_focus_state(page, passive_evaluate, True, timeout=15)
                    focus_before = capture_audio_snapshot(page)
                    focus_console_boundary = len(console)
                    focus_probe.switch_to(other_tab, False, timeout=15)
                    page.wait_for_timeout(800)
                    focus_mark = passive_evaluate(page, "() => __tidalAudio.mark('focus-away')")
                    page.wait_for_timeout(1400)
                    focus_away = capture_audio_snapshot(page)
                    focus_probe.switch_to(page, True, timeout=15)
                    page.wait_for_timeout(500)
                    resume_mark = passive_evaluate(page, "() => __tidalAudio.mark('focus-returned')")
                    page.wait_for_timeout(1500)
                    focus_returned = capture_audio_snapshot(page)
                    other_tab.close()
                    result["audio"]["focus_target_activation"] = focus_probe.report
                    focus_events = [item for item in observer_receipts(console, "TIDAL_AUDIO", focus_console_boundary)
                                    if item.get("event") == "focus"]
                    write_json(out / (label + "-audio-focus.json"), {"before": focus_before,
                        "away": focus_away, "returned": focus_returned, "receipts": focus_events})
                    if [item.get("active") for item in focus_events] != [False, True]:
                        raise ValueError("Actual browser tab activation did not deliver focus loss and return")
                    result["audio"]["focus"] = validate_focus_suspension(focus_before, focus_away,
                        focus_returned, focus_mark["wall_ms"], focus_away["wall_ms"])
                    result["audio"]["focus"]["resumed_window"] = audio_window(focus_returned,
                        resume_mark["wall_ms"], focus_returned["wall_ms"], 1.2, audible=True)
                    write_json(out / (label + "-audio-observations.json"), audio_snapshot)
                    report["checks"].append({"name": label + " real gesture, live post-mute audio, four cues and loop", "passed": True})

                    # Completion saves immediately. Screenshots can take longer than
                    # the auto-save interval; retain that real receipt, not a new
                    # wall-clock window unrelated to the game's simulation time.
                    saved = wait_completed_route_save(page, console, route_console_boundary, route["completed_state"])
                    # Persist the actual muted preference, then test it in the new OS process.
                    mute_state = wait_state(page, console)
                    boundary = len(console)
                    saved_mute_input = real_button(page, mute_state, "audio_rect", mobile, width, height, native_touch=args.no_defaults)
                    saved_mute = wait_observer(page, console, "TIDAL_AUDIO", boundary)
                    if saved_mute.get("event") != "mute" or saved_mute.get("muted") is not True:
                        raise ValueError("Pre-exit real input did not set the saved mute preference")
                    exit_expected = wait_state(page, console, mute_state["sample_id"], lambda state: state.get("audio_muted") is True)
                    result["audio"]["saved_mute"] = {"input": saved_mute_input, "receipt": saved_mute}
                    # Exercise the shipped Save & return control through actual input.
                    # Godot's public normal-exit API awaits final FS synchronization.
                    # This does not certify abrupt tab-close persistence.
                    boundary = len(console)
                    exit_button = page.locator("#tidal-save-return")
                    exit_input = {"kind": "touchscreen.tap" if mobile else "mouse.click"}
                    if mobile and args.no_defaults:
                        exit_input = native_save_return_touch(page, width, height)
                    elif mobile:
                        exit_button.tap()
                    else:
                        exit_button.click()
                    exited = wait_observer(page, console, "TIDAL_WEB_EXIT", boundary,
                                           timeout=120, allow_runtime_exit=True)
                    saved = validate_web_exit(exited, exit_expected)
                    if page.locator("#tidal-exit-panel").get_attribute("data-saved") != "true":
                        raise RuntimeError("Actual Save & return UI did not confirm completion")
                    captured_audio = save_live_audio(page, out, label)
                    closed_audio = captured_audio.pop("snapshot")
                    result["audio"]["closed"] = validate_audio_closed(audio_snapshot, closed_audio)
                    write_json(out / (label + "-audio-after-exit.json"), closed_audio)
                    result["audio"].update({"status": "passed", "capture": captured_audio})
                    capture(label + "-saved-return.png")
                    result["save_return"] = {"status": "passed", "trigger": "touch" if mobile else "mouse", "input": exit_input, "receipt": exited}
                    # A new Chromium OS process must restore the untouched IndexedDB.
                    check_engine_log("\n".join(item["text"] for item in console))
                    result["restore"] = {"status": "running", "saved": saved, "fresh_browser_process": True, "shutdown": "actual Save & return control; official normal exit"}
                    close_current(normal=args.no_defaults)
                    context = None
                    context = launch()
                    page = context.pages[0]
                    if args.no_defaults:
                        viewport_session = configure_native_viewport(page, width, height, mobile)
                    restored_focus = RealTargetFocus(page, bounded_cdp, passive_evaluate, require_hidden=hidden_required, defaults_disabled=args.no_defaults)
                    bounded_cdp(restored_focus.session, "Page.bringToFront", {}, timeout=3)
                    context.add_init_script(script=audio_probe_init_script())
                    attach(page, restored_console, restored_failures)
                    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    if response is None or response.status != 200:
                        raise RuntimeError("Fresh Chromium process could not load staged Web entry")
                    restored_focus.settle_after_navigation(timeout=15)
                    wait_focus_state(page, passive_evaluate, True, timeout=15)
                    wait_ready(page, restored_console, restored_failures)
                    if args.no_defaults:
                        result["restored_viewport"] = verify_native_viewport(page, width, height, mobile)
                    loads = observer_receipts(restored_console, "TIDAL_LOAD")
                    if len(loads) != 1:
                        raise RuntimeError("Fresh Chromium process must emit exactly one load receipt")
                    validate_restored(loads[0], saved)
                    wait_state(page, restored_console, predicate=lambda state: state.get("audio_ready") is True
                               and state.get("audio_driver") == "Dummy")
                    result["audio"]["restored_observer_ready"] = passive_evaluate(page, "() => __tidalAudio.ready()")
                    restored_mark = passive_evaluate(page, "() => __tidalAudio.mark('restored-no-input')")
                    page.wait_for_timeout(2300)
                    restored_audio = capture_audio_snapshot(page)
                    result["audio"]["restored_before_gesture"] = validate_audio_baseline(restored_audio, restored_mark["wall_ms"])
                    write_json(out / (label + "-restored-audio-baseline.json"), restored_audio)
                    capture(label + "-restored.png")
                    post_capture = capture_audio_snapshot(page)
                    result["audio"]["restored_before_begin"] = validate_audio_baseline(post_capture, restored_mark["wall_ms"])
                    write_json(out / (label + "-restored-audio-before-begin.json"), post_capture)
                    # A restored mute must survive Begin; only a later real unmute makes sound.
                    restored_state = wait_state(page, restored_console)
                    if restored_state.get("audio_muted") is not True or restored_state.get("journey_started") is not False:
                        raise ValueError("Fresh process lost mute or began before a real gesture")
                    boundary = len(restored_console)
                    restored_begin = real_button(page, restored_state, "begin_rect", mobile, width, height, native_touch=args.no_defaults)
                    restored_journey = wait_observer(page, restored_console, "TIDAL_JOURNEY", boundary)
                    validate_journey(restored_journey, "touch_begin" if mobile else "begin_button")
                    wait_state(page, restored_console, restored_state["sample_id"],
                               lambda state: state.get("journey_started") is True and state.get("audio_muted") is True)
                    page.wait_for_timeout(2100)
                    quiet_mark = passive_evaluate(page, "() => __tidalAudio.mark('restored-muted-begin')")
                    page.wait_for_timeout(1400)
                    quiet = capture_audio_snapshot(page)
                    result["audio"]["restored_muted_begin"] = {"input": restored_begin, "receipt": restored_journey,
                        "window": audio_window(quiet, quiet_mark["wall_ms"], quiet["wall_ms"], 1.1)}
                    unmute_state = wait_state(page, restored_console)
                    boundary = len(restored_console)
                    restored_unmute = real_button(page, unmute_state, "audio_rect", mobile, width, height, native_touch=args.no_defaults)
                    unmuted = wait_observer(page, restored_console, "TIDAL_AUDIO", boundary)
                    if unmuted.get("event") != "mute" or unmuted.get("muted") is not False or unmuted.get("started") is not True:
                        raise ValueError("Restored real unmute did not enable the running journey")
                    wait_state(page, restored_console, unmute_state["sample_id"], lambda state: state.get("audio_muted") is False)
                    page.wait_for_timeout(500)
                    audible_mark = passive_evaluate(page, "() => __tidalAudio.mark('restored-unmuted')")
                    page.wait_for_timeout(1500)
                    audible = capture_audio_snapshot(page)
                    result["audio"]["restored_unmuted"] = {"input": restored_unmute, "receipt": unmuted,
                        "window": audio_window(audible, audible_mark["wall_ms"], audible["wall_ms"], 1.2, audible=True),
                        "voices": validate_muted_restore_audio(quiet, audible, observer_receipts(restored_console, "TIDAL_AUDIO"))}
                    write_json(out / (label + "-restored-audio-after-input.json"), audible)
                    result["restore"].update({"status": "passed", "loaded": loads[0]})
                    report["checks"].append({"name": label + " fresh Chromium process restores completed treasure quest", "passed": True})
                    result["passed"] = True
                except Exception as error:
                    result["blocker"] = str(error)
                    for stage in ("audio", "input", "language", "restore"):
                        if result[stage]["status"] == "running":
                            result[stage]["status"] = "failed"
                    try:
                        if page is not None:
                            capture(label + "-failure.png", diagnostic=True)
                    except Exception as screenshot_error:
                        result["failure_screenshot_error"] = str(screenshot_error)
                    try:
                        if page is not None and not page.is_closed():
                            write_json(out / (label + "-audio-failure.json"), passive_evaluate(page, "() => __tidalAudio ? __tidalAudio.snapshot() : {missing_probe:true}"))
                    except Exception as audio_error:
                        result["audio_diagnostic_error"] = str(audio_error)
                    # Portrait evidence is independent of desktop input/language success.
                finally:
                    if focus_probe is not None:
                        result["focus_target_activation"] = focus_probe.report
                        write_json(out / (label + "-focus-target.json"), focus_probe.report)
                    try:
                        close_current()
                    except Exception as cleanup_error:
                        result["browser_cleanup_error"] = repr(cleanup_error)
                        result["passed"] = False
                    try:
                        if args.no_defaults:
                            profile_owner.close()
                        else:
                            profile.cleanup()
                    except Exception as cleanup_error:
                        result["profile_cleanup_error"] = repr(cleanup_error)
                        result["passed"] = False
                    for name, lines, errors in (("initial", console, failures), ("restored", restored_console, restored_failures)):
                        try:
                            check_engine_log("\n".join(item["text"] for item in lines))
                        except RuntimeError as error:
                            result[name + "_engine_error"] = str(error)
                            result["passed"] = False
                        if errors:
                            result[name + "_browser_errors"] = errors
                            result["passed"] = False
                        write_json(out / (label + "-" + name + "-console.json"), {"console": lines, "failures": errors})
                    diagnostics = route_diagnostics(driver) if driver else {}
                    if driver:
                        result["input"]["diagnostics"] = diagnostics
                    write_json(out / (label + "-input-route.json"), {"input_events": events,
                        "samples": driver.samples if driver else [], "milestones": driver.milestones if driver else [],
                        "physical_actions": driver.actions if driver else [], "screenshots": screenshots, **diagnostics})
                    write_json(out / (label + "-result.json"), result)
        failed = [item["name"] for item in report["viewports"] if not item["passed"]]
        if failed:
            raise RuntimeError("Viewport acceptance failed: " + ", ".join(failed) + "; inspect independent result JSON files")
        report["passed"] = True
    except Exception as error:
        report["blocker"] = str(error)
        raise
    finally:
        server.shutdown()
        server.server_close()
        write_json(out / "browser-validation.json", report)


if __name__ == "__main__":
    main()
