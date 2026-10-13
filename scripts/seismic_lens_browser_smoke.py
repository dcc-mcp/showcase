#!/usr/bin/env python3
"""Real Chromium playback of the new Seismic Lens clip, both locales/viewports."""
from functools import partial
import argparse
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.sync_api import expect, sync_playwright
from browser_preview import QuietHandler, safe_error_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    site, out = args.site.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    report = {'passed': False, 'scope': 'isolated Chromium desktop and touch-viewport preview, not deployment or physical mobile',
              'input': 'Native video keyboard Space for play/pause/resume/replay; HTML media API for seek',
              'audio': 'not-applicable: intentionally silent', 'checks': []}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            report['browser'] = browser.version
            for locale, prefix in [('en', ''), ('zh', '/zh')]:
                for view, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
                    label = f'{locale}-{view}'
                    context = browser.new_context(viewport={'width': width, 'height': height},
                        is_mobile=view == 'mobile', has_touch=view == 'mobile',
                        reduced_motion='reduce', accept_downloads=True)
                    media_requests = []
                    context.on('request', lambda request: media_requests.append(request.url)
                               if request.url.split('?')[0].endswith('.mp4') else None)
                    context.route('**/*', lambda route: route.continue_()
                                  if route.request.url.startswith(origin + '/') else route.abort())
                    page = context.new_page()
                    page.goto(origin + prefix + '/cases/seismic-lens/', wait_until='networkidle')
                    assert page.locator('html').get_attribute('lang') == ('en' if locale == 'en' else 'zh-CN')
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    video = page.locator('video')
                    expect(video).to_have_count(1)
                    video.scroll_into_view_if_needed()
                    expect(video).to_have_js_property('controls', True)
                    expect(video).to_have_js_property('autoplay', False)
                    assert not media_requests, 'Video requested before user activation'
                    expect(video).to_have_js_property('paused', True)
                    expect(video).to_have_attribute('data-preview-audio', 'false')
                    expect(page.locator('.video-audio-note')).to_have_text('No audio track' if locale == 'en' else '无音轨')
                    video.focus()
                    expect(video).to_be_focused()
                    page.keyboard.press('Space')
                    page.wait_for_function('!document.querySelector("video").paused && document.querySelector("video").currentTime > .3')
                    assert abs(video.evaluate('v => v.duration') - 8) < .05
                    assert video.evaluate('v => [v.videoWidth, v.videoHeight]') == [1178, 814]
                    expect(video).to_have_js_property('muted', True)
                    page.keyboard.press('Space')
                    expect(video).to_have_js_property('paused', True)
                    video.evaluate('v => { v.currentTime = 4; }')
                    page.wait_for_function('!document.querySelector("video").seeking && Math.abs(document.querySelector("video").currentTime - 4) < .1')
                    page.screenshot(path=str(out / (label + '-middle.png')))
                    video.focus()
                    page.keyboard.press('Space')
                    page.wait_for_function('document.querySelector("video").currentTime > 4.4')
                    page.keyboard.press('Space')
                    expect(video).to_have_js_property('paused', True)
                    video.evaluate('v => { v.currentTime = 0; }')
                    page.wait_for_function('!document.querySelector("video").seeking')
                    video.focus()
                    page.keyboard.press('Space')
                    page.wait_for_function('document.querySelector("video").ended', timeout=15000)
                    frames = video.evaluate('v => v.getVideoPlaybackQuality().totalVideoFrames')
                    assert frames >= 100
                    page.screenshot(path=str(out / (label + '-end.png')))
                    page.keyboard.press('Space')
                    page.wait_for_function('!document.querySelector("video").ended && document.querySelector("video").currentTime > .2 && document.querySelector("video").currentTime < 3')
                    page.keyboard.press('Space')
                    expect(video).to_have_js_property('paused', True)
                    resource = page.locator('a[href$="editable-source.zip"]').first
                    with page.expect_download() as pending:
                        resource.click()
                    download = pending.value
                    assert download.failure() is None
                    archive_hash = hashlib.sha256(Path(download.path()).read_bytes()).hexdigest()
                    assert archive_hash == '6e6aaf6197ccc0c7ad245bb6f4a7e8fbbb16255b4de99a17b24019f521d0b439'
                    src = video.locator('source').get_attribute('src')
                    response = context.request.get(origin + '/docs/showcase/seismic-lens/seismic-lens-native-layers.mp4')
                    expected = (site / 'docs/showcase/seismic-lens/seismic-lens-native-layers.mp4').read_bytes()
                    assert response.ok and response.body() == expected
                    report['checks'].append({'locale': locale, 'viewport': view, 'passed': True,
                        'duration_seconds': 8, 'native_keyboard_play_pause_resume_replay': True,
                        'api_seek': True, 'whole_clip_played_to_end': True, 'decoded_browser_frames': frames,
                        'source_download_sha256': archive_hash, 'video_sha256': hashlib.sha256(expected).hexdigest(),
                        'video_source_present': bool(src), 'no_horizontal_overflow': True,
                        'no_video_request_before_activation': True, 'verified_silent_label': True,
                        'touch_viewport_emulation': view == 'mobile'})
                    context.close()
            browser.close()
        report['passed'] = len(report['checks']) == 4
    except Exception as error:
        report['error'] = safe_error_text(error, origin)
        raise
    finally:
        server.shutdown()
        (out / 'browser-verification.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))


if __name__ == '__main__':
    main()
