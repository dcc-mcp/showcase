#!/usr/bin/env python3
"""Capture and check built public pages on an isolated GitHub-hosted browser."""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
import json
from pathlib import Path, PurePosixPath
import subprocess
import threading
from urllib.parse import quote, urlsplit


def public_file_url(origin: str, path: str) -> str:
    """Only construct URLs beneath the isolated local public-site origin."""
    parts = urlsplit(path)
    if (not path or parts.scheme or parts.netloc or parts.query or parts.fragment
            or path.startswith("/") or "\\" in path or "%" in path
            or any(part in ("", ".", "..") for part in path.split("/"))):
        raise ValueError("Expected a safe relative public file path")
    return origin + "/" + quote(path, safe="/")


def selected_public_files(case: dict, manifest: dict) -> dict[str, dict]:
    """Require hashes for the selected cover, result media and local resources."""
    entry = "docs/showcase/" + case["slug"] + "/"
    rows = {}
    for row in manifest["files"]:
        path = entry + row["path"]
        public_file_url("http://127.0.0.1", path)
        if path in rows:
            raise ValueError("Duplicate public manifest file")
        rows[path] = row
    paths = {case["cover"]["src"]}
    paths.update(result["src"] for result in case["results"])
    paths.update(item["url"] for item in case["resources"]
                 if not urlsplit(item["url"]).scheme)
    selected = {}
    for path in sorted(paths):
        public_file_url("http://127.0.0.1", path)
        if not path.startswith(entry) or path not in rows:
            raise ValueError("Selected public file is absent from its entry manifest")
        row = rows[path]
        if (type(row.get("bytes")) is not int or row["bytes"] <= 0
                or not isinstance(row.get("sha256"), str)
                or len(row["sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in row["sha256"])):
            raise ValueError("Selected public file requires a byte count and SHA-256")
        selected[path] = row
    return selected


def check_public_payload(path: str, payload: bytes, expected: dict) -> dict:
    digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != expected["bytes"] or digest != expected["sha256"]:
        raise AssertionError("Public file bytes or SHA-256 differ from manifest: " + path)
    return {"path": path, "bytes": len(payload), "sha256": digest}


def fetch_public_file(request, origin: str, path: str) -> bytes:
    # APIRequestContext does not use page routing. Validate before sending, and
    # forbid redirects so a public reference can never fetch an external URL.
    url = public_file_url(origin, path)
    response = request.get(url, max_redirects=0)
    try:
        if response.status != 200 or response.url != url:
            raise AssertionError("Public file did not return local HTTP 200: " + path)
        return response.body()
    finally:
        response.dispose()


def verify_audio_case(page, context, case: dict, site: Path, origin: str,
                      output: Path, layout: str, active_context: dict) -> dict:
    from playwright.sync_api import expect

    active_context["stage"] = "audio_controls_and_metadata"
    page.get_by_role("link", name="成果", exact=True).click()
    page.wait_for_url("**/#results")
    results = page.locator("#results")
    expect(results).to_be_in_viewport()
    audio = results.locator("audio")
    expect(audio).to_have_count(1)
    expect(audio).to_be_visible()
    media = next(item for item in case["results"] if item["src"].endswith(".mp3"))
    expected_url = public_file_url(origin, media["src"])
    expect(audio).to_have_js_property("controls", True)
    expect(audio).to_have_attribute("aria-label", media["alt"])
    expect(audio).to_have_attribute("preload", "metadata")
    expect(audio).to_have_attribute("tabindex", "0")
    expect(audio).to_have_js_property("autoplay", False)
    if audio.get_attribute("autoplay") is not None:
        raise AssertionError("Audio must not include any autoplay attribute")
    expect(audio.locator("source")).to_have_count(1)
    expect(audio.locator("source")).to_have_attribute("type", "audio/mpeg")
    expect(audio.locator("source")).to_have_js_property("src", expected_url)
    page.wait_for_function("""() => {
        const a = document.querySelector('#results audio');
        return a.readyState >= 1 && Number.isFinite(a.duration) && a.duration > 0;
    }""")
    expect(audio).to_have_js_property("currentSrc", expected_url)
    expect(audio).to_have_js_property("paused", True)
    expect(audio).to_have_js_property("currentTime", 0)
    if audio.evaluate("a => a.played.length") != 0:
        raise AssertionError("Audio played before a user gesture")
    duration = audio.evaluate("a => a.duration")
    if abs(duration - 28.6) > 0.15:
        raise AssertionError("Unexpected Trail & Air audio duration")

    active_context["stage"] = "audio_keyboard_play_pause_seek"
    audio.focus()
    expect(audio).to_be_focused()
    page.keyboard.press("Space")
    page.wait_for_function("""() => {
        const a = document.querySelector('#results audio');
        return !a.paused && a.currentTime >= 0.2;
    }""")
    page.keyboard.press("Space")
    expect(audio).to_have_js_property("paused", True)
    before_seek = audio.evaluate("a => a.currentTime")
    page.keyboard.press("ArrowRight")
    page.wait_for_function("""before => {
        const a = document.querySelector('#results audio');
        return !a.seeking && a.currentTime >= before + 4;
    }""", arg=before_seek)
    seek_time = audio.evaluate("a => a.currentTime")
    expect(audio).to_have_js_property("paused", True)

    active_context["stage"] = "audio_replay_after_end"
    # Seek near the end to exercise a genuine ended event without a 29-second
    # delay per viewport. Playback and replay themselves use native keyboard UI.
    audio.evaluate("a => { a.currentTime = a.duration - 0.2; }")
    page.wait_for_function("() => !document.querySelector('#results audio').seeking")
    page.keyboard.press("Space")
    page.wait_for_function("() => document.querySelector('#results audio').ended")
    expect(audio).to_have_js_property("paused", True)
    page.keyboard.press("Space")
    page.wait_for_function("""() => {
        const a = document.querySelector('#results audio');
        return !a.paused && !a.ended && a.currentTime >= 0.1 && a.currentTime < 3;
    }""")
    page.keyboard.press("Space")
    expect(audio).to_have_js_property("paused", True)

    active_context["stage"] = "audio_public_resource_integrity"
    manifest_path = "docs/showcase/" + case["slug"] + "/manifest.json"
    manifest_bytes = fetch_public_file(context.request, origin, manifest_path)
    if manifest_bytes != (site / manifest_path).read_bytes():
        raise AssertionError("Served entry manifest differs from the public build")
    manifest = json.loads(manifest_bytes)
    selected = selected_public_files(case, manifest)
    linked_resources = page.locator("#resources a, #downloads a").evaluate_all(
        "links => links.map(link => ({url: link.href, download: link.getAttribute('download')}))")
    for item in case["resources"]:
        if urlsplit(item["url"]).scheme:
            continue
        url = public_file_url(origin, item["url"])
        matches = [link for link in linked_resources if link["url"] == url]
        if not matches:
            raise AssertionError("Selected local resource link is missing")
        if item["url"].endswith(".zip") and not any(
                link["download"] == PurePosixPath(item["url"]).name for link in matches):
            raise AssertionError("ZIP resource requires its native download link")
    fetched = [check_public_payload(path, fetch_public_file(context.request, origin, path), row)
               for path, row in selected.items()]
    fallback = audio.locator("..").locator("a[download]")
    expect(fallback).to_have_count(1)
    expect(fallback).to_have_js_property("href", expected_url)
    expect(fallback).to_have_attribute("download", PurePosixPath(media["src"]).name)
    with page.expect_download() as download_info:
        fallback.click()
    download = download_info.value
    if download.failure() is not None or download.suggested_filename != PurePosixPath(media["src"]).name:
        raise AssertionError("Audio fallback download failed")
    downloaded = check_public_payload(media["src"], Path(download.path()).read_bytes(),
                                      selected[media["src"]])

    active_context["stage"] = "audio_results_screenshots"
    audio.scroll_into_view_if_needed()
    if not page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"):
        raise AssertionError("Audio case horizontal overflow")
    if not audio.evaluate("""a => {
        const r = a.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && r.left >= -1 && r.right <= innerWidth + 1;
    }"""):
        raise AssertionError("Audio controls overflow the viewport")
    screenshots = []
    for label, target in (("results", results), ("player", audio.locator(".."))):
        name = layout + "-" + case["slug"] + "-" + label + ".png"
        target.screenshot(path=str(output / name), animations="disabled")
        screenshots.append({"screenshot": name,
                            "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()})
    return {"layout": layout, "case_slug": case["slug"], "duration_seconds": duration,
            "native_controls": True, "accessible_label": media["alt"], "preload": "metadata",
            "autoplay": False, "keyboard_play_and_pause": True, "keyboard_seek": True,
            "seek_seconds": seek_time, "replay_after_end": True, "horizontal_overflow": False,
            "manifest": manifest_path, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "public_files": fetched, "fallback_download": downloaded, "screenshots": screenshots}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def git_value(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def run(site: Path, output: Path, expected_head: str) -> int:
    from playwright.sync_api import expect, sync_playwright

    head = git_value("rev-parse", "HEAD")
    if head != expected_head:
        raise ValueError("Checkout does not match the requested head")
    if not (site / "index.html").is_file():
        raise ValueError("Build the public site first")
    output.mkdir(parents=True, exist_ok=False)
    collection = json.loads(Path("collection.json").read_text(encoding="utf-8"))
    cases = collection["cases"]
    report = {"source_head": head, "source_tree": git_value("rev-parse", "HEAD^{tree}"),
              "playwright": version("playwright"), "status": "running", "pages": [], "galleries": [], "films": [], "audio": []}
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
                                                  service_workers="block", accept_downloads=True)
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
                        active_context["stage"] = "gallery_images"
                        covers = page.locator(".case-card img")
                        expect(covers).to_have_count(len(cases))
                        loaded_images = []
                        for index in range(len(cases)):
                            cover = covers.nth(index)
                            cover.scroll_into_view_if_needed()
                            expect(cover).to_have_js_property("complete", True)
                            dimensions = cover.evaluate("image => ({width: image.naturalWidth, height: image.naturalHeight})")
                            if dimensions["width"] <= 0 or dimensions["height"] <= 0:
                                raise AssertionError("Cover image did not load")
                            cover.evaluate("image => image.decode()")
                            loaded_images.append({"src": cover.get_attribute("src"), "loaded": True,
                                                  "naturalWidth": dimensions["width"],
                                                  "naturalHeight": dimensions["height"]})
                        page.locator("h1").click()
                        page.keyboard.press("Control+Home")
                        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                        page.screenshot(path=str(output / (layout + "-gallery.png")), full_page=True)
                        report["galleries"].append({"layout": layout, "covers": loaded_images,
                            "screenshot": layout + "-gallery.png",
                            "focused_element": page.evaluate("document.activeElement.tagName")})
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
                            if case["slug"] == "orbit-post-office":
                                active_context["stage"] = "orbit_film_controls"
                                page.get_by_role("link", name="成果", exact=True).click()
                                video = page.locator("#results video")
                                expect(video).to_have_count(1)
                                expect(video).to_be_visible()
                                expect(video).to_have_js_property("controls", True)
                                page.wait_for_function("() => { const v = document.querySelector('#results video'); return v.readyState >= 1 && v.videoWidth === 1280 && v.videoHeight === 720; }")
                                duration = video.evaluate("v => v.duration")
                                if abs(duration - 7.018) > 0.05:
                                    raise AssertionError("Unexpected Orbit film duration")
                                video.press("Space")
                                page.wait_for_function("() => { const v = document.querySelector('#results video'); return !v.paused && v.currentTime >= 0.2; }")
                                video.press("Space")
                                expect(video).to_have_js_property("paused", True)
                                film_name = layout + "-orbit-post-office-film.png"
                                video.locator("..").screenshot(path=str(output / film_name), animations="disabled")
                                report["films"].append({"layout": layout, "case_slug": case["slug"],
                                    "duration_seconds": duration, "width": 1280, "height": 720,
                                    "keyboard_play_and_pause": True, "screenshot": film_name,
                                    "sha256": hashlib.sha256((output / film_name).read_bytes()).hexdigest()})
                            if case["slug"] == "trail-and-air":
                                report["audio"].append(verify_audio_case(
                                    page, context, case, site, origin, output, layout, active_context))
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
