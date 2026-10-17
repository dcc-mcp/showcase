#!/usr/bin/env python3
"""Run real exported Godot in Chromium and capture desktop + portrait viewports."""
from __future__ import annotations
import argparse
import json
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from common import isolated_output, sha256, write_json
from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = isolated_output(args.output, args.site)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(args.site.resolve())))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
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
                    deadline = time.monotonic() + 120
                    while time.monotonic() < deadline and not any("TIDAL_READY " in line["text"] for line in console):
                        if failures:
                            raise RuntimeError("Browser failed before game readiness: " + json.dumps(failures))
                        page.wait_for_timeout(100)
                    if not any("TIDAL_READY " in line["text"] for line in console):
                        raise RuntimeError("Actual exported Godot did not emit TIDAL_READY")
                    page.wait_for_timeout(1500)
                    canvas = page.locator("#canvas")
                    canvas.focus()
                    bounds = canvas.bounding_box()
                    if not bounds or bounds["width"] < width - 2 or bounds["height"] < height - 2:
                        raise RuntimeError("Actual Web game canvas did not fill requested viewport")
                    if not page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"):
                        raise RuntimeError("Web shell overflows horizontally at requested viewport")
                    page.screenshot(path=str(out / (label + ".png")))
                    record = {"name": label, "width": width, "height": height, "canvas": bounds,
                        "ready_log": next(line["text"] for line in console if "TIDAL_READY " in line["text"]),
                        "loaded_wasm": any(url.endswith(".wasm") for url in requests),
                        "loaded_pack": any(url.endswith(".pck") for url in requests)}
                    if not record["loaded_wasm"] or not record["loaded_pack"]:
                        raise RuntimeError("Screenshot lacked actual runtime/pack requests")
                    report["viewports"].append(record)
                    report["checks"].append({"name": label + " actual WebGL 2 Godot scene", "passed": True})
                    if not mobile:
                        page.keyboard.down("w")
                        try:
                            deadline = time.monotonic() + 2.2
                            while time.monotonic() < deadline and not any("TIDAL_LANTERN 0" in line["text"] for line in console):
                                page.keyboard.press("e")
                                page.wait_for_timeout(100)
                        finally:
                            page.keyboard.up("w")
                        if not any("TIDAL_LANTERN 0" in line["text"] for line in console):
                            raise RuntimeError("Browser W/E input did not activate actual lantern I")
                        page.wait_for_timeout(300)
                        page.screenshot(path=str(out / "desktop-after-w-e.png"))
                        report["checks"].append({"name": "browser W/E activates actual lantern I", "passed": True})
                    else:
                        # Screenshot includes real native portrait layout; touch action is delivered,
                        # but no gameplay effect is claimed without an independent state readback.
                        session = context.new_cdp_session(page)
                        session.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 80, "y": 600}]})
                        session.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 80, "y": 540}]})
                        page.wait_for_timeout(650)
                        session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                        page.wait_for_timeout(300)
                        page.screenshot(path=str(out / "portrait-after-touch.png"))
                        report["touch_delivery"] = "Emulated touch drag sent; movement is not separately asserted"
                    fatal_console = [line for line in console if any(token in line["text"] for token in (
                        "SCRIPT ERROR:", "Parse Error:", "Shader compilation failed", "Failed to load script"))]
                    if failures or fatal_console:
                        raise RuntimeError("Browser reported engine/page failures: " + json.dumps(failures + fatal_console))
                except Exception:
                    page.screenshot(path=str(out / (label + "-failure.png")))
                    raise
                finally:
                    write_json(out / (label + "-console.json"), {"console": console, "failures": failures})
                    context.close()
            browser.close()
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
