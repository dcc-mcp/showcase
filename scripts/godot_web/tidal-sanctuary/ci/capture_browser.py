#!/usr/bin/env python3
"""Capture each real Web viewport independently; then aggregate strict acceptance."""
from __future__ import annotations
import argparse
import json
import math
import threading
import tempfile
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from common import check_engine_log, isolated_output, sha256, write_json
from playwright.sync_api import sync_playwright
from gameplay import RouteDriver, complete, keyboard_direction, validate_restored
from observers import finite_vector, observer_receipts, positive_integer, validate_language_frame, validate_touch_release


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def last_observer_id(console, prefix, field):
    return max((positive_integer(item.get(field), field) for item in observer_receipts(console, prefix)), default=0)


def wait_observer(page, console, prefix, start, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.is_closed():
            raise RuntimeError(f"Browser page closed before {prefix}")
        if any(item.get("text", "").startswith("TIDAL_FINAL ") for item in console[start:]):
            raise RuntimeError(f"Game exited before {prefix} could be accepted")
        receipts = observer_receipts(console, prefix, start)
        if receipts:
            if len(receipts) != 1:
                raise RuntimeError(f"Expected exactly one fresh {prefix} receipt")
            return receipts[0]
        page.wait_for_timeout(100)
    raise TimeoutError(f"Actual game did not emit a fresh {prefix} receipt")


BROWSER_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--disable-dev-shm-usage"]


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


def capture_png(page, path, diagnostic=False):
    started = time.monotonic()
    page.screenshot(path=str(path), timeout=30000 if diagnostic else 120000)
    return {"name": path.name, "wall_seconds": time.monotonic() - started,
            "timeout_seconds": 30 if diagnostic else 120, "diagnostic": diagnostic}


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
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = isolated_output(args.output, args.site)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(args.site.resolve())))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/index.html"
    report = {"passed": False, "browser": "Chromium", "checks": [], "viewports": [],
              "limitations": ["Portrait uses Chromium device emulation, not a physical phone.",
                  "Rendered screenshots are not subjective visual acceptance.",
                  "Input uses real browser keyboard/touch events with passive state observations; no scripted demo.",
                  "No multiplayer, deployment, accessibility, or broad device compatibility claim."],
              "pack_sha256": sha256(args.site / "index.pck")}
    try:
        with sync_playwright() as pw:
            for width, height, mobile in ((1280, 720, False), (390, 844, True)):
                label = "portrait-390x844" if mobile else "desktop-1280x720"
                result = {"name": label, "width": width, "height": height, "passed": False, "rendered": False,
                          "input": {"status": "not_run"}, "language": {"status": "not_run"}, "restore": {"status": "not_run"}}
                report["viewports"].append(result)
                console, failures, requests, events, screenshots = [], [], [], [], []
                restored_console, restored_failures = [], []
                context = page = None
                pressed = set()
                touch_points = []
                driver = None
                profile = tempfile.TemporaryDirectory(prefix="tidal-" + label + "-profile-")

                def launch():
                    return pw.chromium.launch_persistent_context(profile.name, headless=True,
                        args=BROWSER_ARGS, viewport={"width": width, "height": height}, device_scale_factor=1,
                        is_mobile=mobile, has_touch=mobile)

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
                    report["browser_version"] = context.browser.version if context.browser else page.evaluate("navigator.userAgent")
                    attach(page, console, failures)
                    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    if response is None or response.status != 200:
                        raise RuntimeError("Staged Web entry did not return HTTP 200")
                    wait_ready(page, console, failures)
                    canvas = page.locator("#canvas")
                    canvas.focus()
                    bounds = canvas.bounding_box()
                    if not bounds or bounds["width"] < width - 2 or bounds["height"] < height - 2:
                        raise RuntimeError("Actual Web game canvas did not fill requested viewport")
                    if not page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"):
                        raise RuntimeError("Web shell overflows horizontally at requested viewport")
                    capture(label + ".png")
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
                    driver = RouteDriver(states, move, interact, lambda seconds: page.wait_for_timeout(seconds * 1000), screenshot)
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

                    # Completion saves immediately. Screenshots can take longer than
                    # the auto-save interval; retain that real receipt, not a new
                    # wall-clock window unrelated to the game's simulation time.
                    saved = wait_completed_route_save(page, console, route_console_boundary, route["completed_state"])
                    # A new Chromium OS process must restore the untouched IndexedDB.
                    page.wait_for_timeout(2500)
                    check_engine_log("\n".join(item["text"] for item in console))
                    result["restore"] = {"status": "running", "saved": saved, "fresh_browser_process": True}
                    context.close()
                    context = None
                    context = launch()
                    page = context.pages[0]
                    attach(page, restored_console, restored_failures)
                    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    if response is None or response.status != 200:
                        raise RuntimeError("Fresh Chromium process could not load staged Web entry")
                    wait_ready(page, restored_console, restored_failures)
                    loads = observer_receipts(restored_console, "TIDAL_LOAD")
                    if len(loads) != 1:
                        raise RuntimeError("Fresh Chromium process must emit exactly one load receipt")
                    validate_restored(loads[0], saved)
                    capture(label + "-restored.png")
                    result["restore"].update({"status": "passed", "loaded": loads[0]})
                    report["checks"].append({"name": label + " fresh Chromium process restores completed treasure quest", "passed": True})
                    result["passed"] = True
                except Exception as error:
                    result["blocker"] = str(error)
                    for stage in ("input", "language", "restore"):
                        if result[stage]["status"] == "running":
                            result[stage]["status"] = "failed"
                    try:
                        if page is not None:
                            capture(label + "-failure.png", diagnostic=True)
                    except Exception as screenshot_error:
                        result["failure_screenshot_error"] = str(screenshot_error)
                    # Portrait evidence is independent of desktop input/language success.
                finally:
                    if context is not None:
                        context.close()
                    profile.cleanup()
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
                    write_json(out / (label + "-input-route.json"), {"input_events": events,
                        "samples": driver.samples if driver else [], "milestones": driver.milestones if driver else [],
                        "physical_actions": driver.actions if driver else [], "screenshots": screenshots})
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
