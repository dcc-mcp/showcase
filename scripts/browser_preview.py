#!/usr/bin/env python3
"""Capture and check built public pages on an isolated GitHub-hosted browser."""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import threading

from playwright.sync_api import expect, sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def git_value(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def run(site: Path, output: Path, expected_head: str) -> int:
    head = git_value("rev-parse", "HEAD")
    if head != expected_head:
        raise ValueError("Checkout does not match the requested head")
    if not (site / "index.html").is_file():
        raise ValueError("Build the public site first")
    output.mkdir(parents=True, exist_ok=False)
    collection = json.loads(Path("collection.json").read_text(encoding="utf-8"))
    cases = collection["cases"]
    report = {"source_head": head, "source_tree": git_value("rev-parse", "HEAD^{tree}"),
              "playwright": version("playwright"), "status": "running", "pages": []}
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(site)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://127.0.0.1:%d" % server.server_address[1]
    active_context = {"stage": "browser_launch"}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            report["browser"] = browser.version
            try:
                for layout, viewport in (("desktop", {"width": 1440, "height": 1080}),
                                         ("mobile", {"width": 390, "height": 844})):
                    context = browser.new_context(viewport=viewport, device_scale_factor=1,
                                                  reduced_motion="reduce", locale="zh-CN",
                                                  service_workers="block")
                    errors = []
                    def route(request_route):
                        if request_route.request.url.startswith(origin + "/"):
                            request_route.continue_()
                        else:
                            errors.append("unexpected_external_resource")
                            request_route.abort()
                    context.route("**/*", route)
                    page = context.new_page()
                    page.set_default_timeout(15000)
                    page.on("pageerror", lambda error: errors.append("page_javascript_error"))
                    page.on("response", lambda response: errors.append("http_error") if response.status >= 400 else None)
                    try:
                        active_context = {"stage": "gallery_search_reset", "layout": layout}
                        page.goto(origin + "/", wait_until="networkidle")
                        page.evaluate("document.fonts.ready")
                        expect(page.locator(".case-card:visible")).to_have_count(len(cases))
                        page.locator("#search").fill(cases[0]["title"])
                        expect(page.locator(".case-card:visible")).to_have_count(1)
                        page.locator("#reset-filters").click()
                        expect(page.locator(".case-card:visible")).to_have_count(len(cases))
                        if not page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"):
                            raise AssertionError("Homepage horizontal overflow")
                        page.screenshot(path=str(output / (layout + "-gallery.png")), full_page=True)
                        for case in cases:
                            active_context = {"stage": "models_navigation", "layout": layout,
                                              "case_slug": case["slug"]}
                            path = "/cases/%s/" % case["slug"]
                            page.goto(origin + path, wait_until="networkidle")
                            page.evaluate("document.fonts.ready")
                            expect(page.locator("h1")).to_have_text(case["title"])
                            page.get_by_role("link", name="模型与版本", exact=True).click()
                            page.wait_for_url("**/#models")
                            section = page.locator("#models")
                            expect(section).to_be_in_viewport()
                            expect(section.locator("dt")).to_have_count(len(case["model_attribution"]))
                            active_context["stage"] = "model_fields"
                            for index, row in enumerate(case["model_attribution"]):
                                stage = section.locator("dt").nth(index)
                                expect(stage).to_have_text(row["stage"])
                                expect(stage).to_be_visible()
                                cell = section.locator("dd").nth(index)
                                expect(cell.locator("strong").nth(0)).to_have_text(row["model"])
                                expect(cell.locator("strong").nth(0)).to_be_visible()
                                expect(cell.locator("strong").nth(1)).to_have_text(row["reasoning_effort"])
                                expect(cell.locator("strong").nth(1)).to_be_visible()
                            no_overflow = page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                            if not no_overflow:
                                raise AssertionError("Case page horizontal overflow")
                            image_name = layout + "-" + case["slug"] + "-models.png"
                            active_context["stage"] = "screenshot"
                            section.screenshot(path=str(output / image_name), animations="disabled")
                            report["pages"].append({"layout": layout, "path": path + "#models",
                                "viewport": viewport, "attribution_rows": len(case["model_attribution"]),
                                "anchor_visible": True, "horizontal_overflow": False,
                                "screenshot": image_name,
                                "sha256": hashlib.sha256((output / image_name).read_bytes()).hexdigest()})
                        if errors:
                            raise AssertionError("Browser reported resource or script errors")
                    finally:
                        context.close()
            finally:
                browser.close()
        report["status"] = "passed"
        return 0
    except Exception as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        report["failure_context"] = active_context
        return 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": report["status"], "source_head": head, "page_checks": len(report["pages"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("_site"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.site.resolve(), args.output.resolve(), args.expected_head))
