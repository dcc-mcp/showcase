#!/usr/bin/env python3
"""Capture each real Web viewport independently; then aggregate strict acceptance."""
from __future__ import annotations
import argparse
import json
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from common import check_engine_log, isolated_output, sha256, write_json
from playwright.sync_api import sync_playwright
from observers import observer_receipts, positive_integer, validate_language_frame, validate_touch_release


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = isolated_output(args.output, args.site)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(args.site.resolve())))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {"passed": False, "browser": "Chromium", "checks": [], "viewports": [],
              "limitations": ["Portrait uses Chromium device emulation, not a physical phone.",
                  "Rendered screenshots are not subjective visual acceptance.",
                  "Desktop input is physical browser key events; scripted demo is not used.",
                  "No multiplayer, deployment, accessibility, or broad device compatibility claim."],
              "pack_sha256": sha256(args.site / "index.pck")}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--use-gl=angle", "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader", "--disable-dev-shm-usage"])
            report["browser_version"] = browser.version
            for width, height, mobile in ((1280, 720, False), (390, 844, True)):
                label = "portrait-390x844" if mobile else "desktop-1280x720"
                result = {"name": label, "width": width, "height": height,
                          "passed": False, "rendered": False, "input": {"status": "not_run"},
                          "language": {"status": "not_run"}}
                report["viewports"].append(result)
                context = browser.new_context(viewport={"width": width, "height": height},
                    device_scale_factor=1, is_mobile=mobile, has_touch=mobile)
                page = context.new_page()
                console, failures, requests = [], [], []
                page.on("console", lambda event: console.append({"type": event.type, "text": event.text}))
                page.on("pageerror", lambda error: failures.append(str(error)))
                page.on("requestfailed", lambda request: failures.append(request.url + ": " + str(request.failure)))
                page.on("request", lambda request: requests.append(request.url))
                try:
                    response = page.goto(f"http://127.0.0.1:{server.server_port}/index.html", wait_until="domcontentloaded", timeout=60000)
                    if response is None or response.status != 200:
                        raise RuntimeError("Staged Web entry did not return HTTP 200")
                    deadline = time.monotonic() + 150
                    while time.monotonic() < deadline and not any("TIDAL_FRAME_READY" in line["text"] for line in console):
                        if failures:
                            raise RuntimeError("Browser failed before frame readiness: " + json.dumps(failures))
                        page.wait_for_timeout(100)
                    if not any("TIDAL_FRAME_READY" in line["text"] for line in console):
                        raise RuntimeError("Actual exported Godot did not emit TIDAL_FRAME_READY after frame_post_draw")
                    # Observe a browser compositor turn too; no invented loading-delay heuristic.
                    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                    canvas = page.locator("#canvas")
                    canvas.focus()
                    bounds = canvas.bounding_box()
                    if not bounds or bounds["width"] < width - 2 or bounds["height"] < height - 2:
                        raise RuntimeError("Actual Web game canvas did not fill requested viewport")
                    if not page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"):
                        raise RuntimeError("Web shell overflows horizontally at requested viewport")
                    page.screenshot(path=str(out / (label + ".png")))
                    result.update({"canvas": bounds, "rendered": True,
                        "ready_log": next(line["text"] for line in console if "TIDAL_FRAME_READY" in line["text"]),
                        "loaded_wasm": any(url.endswith(".wasm") for url in requests),
                        "loaded_pack": any(url.endswith(".pck") for url in requests)})
                    if not result["loaded_wasm"] or not result["loaded_pack"]:
                        raise RuntimeError("Screenshot lacked actual runtime/pack requests")
                    report["checks"].append({"name": label + " actual WebGL 2 Godot scene", "passed": True})
                    if not mobile:
                        result["input"] = {"status": "running", "route": "physical browser W/E", "timeout_seconds": 15}
                        page.keyboard.down("w")
                        started = time.monotonic()
                        try:
                            deadline = started + 15
                            while time.monotonic() < deadline and not any("TIDAL_LANTERN 0" in line["text"] for line in console):
                                # Distinct keydown/up events feed the real Godot _unhandled_input.
                                page.keyboard.press("e", delay=80)
                                page.wait_for_timeout(100)
                        finally:
                            page.keyboard.up("w")
                        result["input"]["elapsed_seconds"] = round(time.monotonic() - started, 3)
                        if not any("TIDAL_LANTERN 0" in line["text"] for line in console):
                            result["input"]["status"] = "failed"
                            raise RuntimeError("Browser W/E input did not activate actual lantern I after 15 seconds")
                        page.screenshot(path=str(out / "desktop-after-w-e.png"))
                        result["input"]["status"] = "passed"
                        report["checks"].append({"name": "browser W/E activates actual lantern I", "passed": True})
                        result["language"] = {"status": "running", "route": "physical browser L"}
                        previous_change = last_observer_id(console, "TIDAL_LANGUAGE_FRAME", "change_id")
                        language_boundary = len(console)
                        canvas.focus()
                        page.keyboard.press("l", delay=80)
                        language_receipt = wait_observer(page, console, "TIDAL_LANGUAGE_FRAME", language_boundary)
                        result["language"]["receipt"] = language_receipt
                        validate_language_frame(language_receipt, previous_change)
                        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                        page.screenshot(path=str(out / "desktop-zh.png"))
                        result["language"]["status"] = "passed"
                        report["checks"].append({"name": "physical L changes sampled rendered desktop UI from English to Chinese", "passed": True})
                    else:
                        result["input"] = {"status": "running", "route": "actual Chromium-emulated touch drag",
                                           "hold_seconds": 2, "receipt_timeout_seconds": 15}
                        previous_gesture = last_observer_id(console, "TIDAL_TOUCH_RELEASE", "gesture_id")
                        touch_boundary = len(console)
                        session = context.new_cdp_session(page)
                        session.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"id": 0, "x": 80, "y": 600}]})
                        try:
                            session.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"id": 0, "x": 80, "y": 540}]})
                            page.wait_for_timeout(2000)
                        finally:
                            session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                        touch_receipt = wait_observer(page, console, "TIDAL_TOUCH_RELEASE", touch_boundary)
                        result["input"]["receipt"] = touch_receipt
                        displacement = validate_touch_release(touch_receipt, previous_gesture, expected_touch_index=0)
                        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                        page.screenshot(path=str(out / "portrait-after-touch.png"))
                        result["input"].update({"status": "passed", "horizontal_displacement": displacement,
                            "limitation": "One emulated gesture; not a physical-phone compatibility test"})
                        report["checks"].append({"name": "one portrait touch gesture moves the actual player more than 0.25 horizontally", "passed": True,
                                                "horizontal_displacement": displacement})
                    result["passed"] = True
                except Exception as error:
                    result["blocker"] = str(error)
                    for stage in ("input", "language"):
                        if result[stage]["status"] == "running":
                            result[stage]["status"] = "failed"
                    try:
                        page.screenshot(path=str(out / (label + "-failure.png")))
                    except Exception as screenshot_error:
                        result["failure_screenshot_error"] = str(screenshot_error)
                    # Keep going: portrait evidence does not depend on desktop input success.
                finally:
                    try:
                        check_engine_log("\n".join(line["text"] for line in console))
                    except RuntimeError as error:
                        result["engine_error"] = str(error)
                        result["passed"] = False
                    if failures:
                        result["browser_errors"] = failures
                        result["passed"] = False
                    write_json(out / (label + "-console.json"), {"console": console, "failures": failures})
                    write_json(out / (label + "-result.json"), result)
                    context.close()
            browser.close()
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
