#!/usr/bin/env python3
"""Real-engine and audio-state acceptance for the opt-in game gallery."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from localization_browser_smoke import MountHandler


def run(site, output):
    from playwright.sync_api import sync_playwright, expect
    from godot_web.browser_test import AUDIO_PROBE
    output.mkdir(parents=True, exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(MountHandler,directory=str(site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/showcase/'
    report={'checks':[], 'screenshots':[], 'passed':False,
            'scope':'Chromium real Godot Web and touch-viewport emulation; no subjective listening or physical-device acceptance'}
    def check(name):
        report['checks'].append(name);print('PASS '+name,flush=True)
    def shot(page,name):
        page.screenshot(path=str(output/name));report['screenshots'].append(name)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=['--enable-unsafe-swiftshader'],ignore_default_args=['--mute-audio'])
            report['browser']=browser.version
            for mobile in [False,True]:
                context=browser.new_context(viewport={'width':390 if mobile else 1486,'height':844 if mobile else 1059},
                                           has_touch=mobile,is_mobile=mobile,service_workers='block')
                context.add_init_script(AUDIO_PROBE)
                requests=[]
                context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base) else r.abort())
                context.on('request',lambda r:requests.append(r.url))
                page=context.new_page();page.set_default_timeout(30000)
                for prefix,locale in [('','en'),('zh/','zh')]:
                    page.goto(base+prefix,wait_until='networkidle');requests.clear()
                    expect(page.locator('.games-shelf')).to_be_visible()
                    assert page.locator('iframe').count()==0
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                    shot(page,f'{locale}-'+('mobile' if mobile else 'desktop')+'-games-gallery.png')
                    # Real exported videos: one verified audio track and one silent.
                    sonic=page.locator('.case-card[data-case="sonic-loom"]')
                    sonic.scroll_into_view_if_needed()
                    if mobile:sonic.locator('.preview-toggle').click()
                    else:sonic.locator('.card-title').hover()
                    expect(sonic).to_have_attribute('data-preview-state','playing')
                    assert sonic.locator('video').evaluate('(v)=>v.muted && v.videoWidth>0')
                    sonic.locator('.preview-sound').click()
                    assert not sonic.locator('video').evaluate('(v)=>v.muted')
                    assert page.url==base+prefix
                    shot(page,f'{locale}-'+('mobile' if mobile else 'desktop')+'-sound-on.png')
                    page.locator('#search').fill('Prism Tide')
                    assert sonic.locator('video').evaluate('(v)=>v.muted && v.paused && !v.hasAttribute("src")')
                    prism=page.locator('.case-card[data-case="prism-tide"]');prism.scroll_into_view_if_needed()
                    if mobile:prism.locator('.preview-toggle').click()
                    else:prism.hover()
                    expect(prism).to_have_attribute('data-preview-state','playing')
                    expect(prism.locator('.preview-sound')).to_be_hidden()
                    expect(prism.locator('.preview-audio-note')).to_have_text('无音轨' if locale=='zh' else 'No audio track')
                    assert not any(url.endswith(('.wasm','.pck')) for url in requests)
                    check(f'{locale}/{mobile}: actual audio/silent video, explicit sound, filter resets, no engine on hover')
                    page.locator('#reset-filters').click()
                    page.locator('[data-filter="media"] [data-value="interactive"]').click()
                    expect(page.locator('.games-shelf')).to_be_visible()
                    # A direct game URL does not start; the gallery Start link does.
                    page.goto(base+prefix+'games/sonic-loom/',wait_until='networkidle')
                    expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','idle')
                    assert page.locator('iframe').count()==0
                    page.goto(base+prefix)
                    page.locator('[data-game-launch="sonic-loom"]').click()
                    expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','running',timeout=120000)
                    frame=page.frames[1]
                    frame.wait_for_function('window.__showcaseState?.pattern?.length===4')
                    assert frame.locator('canvas').evaluate('(c)=>c.width>0 && c.height>0')
                    if mobile:expect(frame.locator('body')).to_have_attribute('data-layout','mobile')
                    expect(page.locator('[data-game-sound]')).to_be_visible()
                    frame.locator('canvas').press('Space')
                    frame.wait_for_function('window.__showcaseState.playing===true')
                    frame.wait_for_function('window.__audioSamples>0')
                    assert frame.evaluate('window.__audioPeak')==0
                    page.locator('[data-game-sound]').click()
                    expect(page.locator('[data-game-sound]')).to_have_attribute('aria-pressed','true')
                    frame.wait_for_function('window.__audioPeak>0.001')
                    page.locator('[data-game-sound]').click()
                    frame.wait_for_function('window.__audioContexts.every(c=>c.state==="suspended")')
                    page.locator('[data-game-sound]').click()
                    frame.wait_for_function('window.__audioContexts.some(c=>c.state==="running")')
                    page.locator('[data-game-reset]').click()
                    frame.wait_for_function('window.__showcaseState.playing===false')
                    if not mobile:
                        page.locator('[data-game-fullscreen]').click()
                        page.wait_for_function('!!document.fullscreenElement')
                        page.keyboard.press('Escape')
                        page.wait_for_function('!document.fullscreenElement')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                    shot(page,f'{locale}-'+('mobile' if mobile else 'desktop')+'-sonic-running.png')
                    page.locator('[data-game-exit]').click()
                    expect(page.locator('iframe')).to_have_count(0)
                    expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','idle')
                    page.locator('[data-game-start]').click()
                    expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','running',timeout=120000)
                    page.locator('[data-game-exit]').click()
                    check(f'{locale}/{mobile}: real Godot starts once, reset, sound action, exit releases and restart succeeds')
                    # More games navigates without auto-start unless explicitly Start.
                    page.locator('.more-games [data-game-launch="prism-tide"]').click()
                    expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','running',timeout=120000)
                    expect(page.locator('[data-game-sound]')).to_be_hidden()
                    frame=page.frames[1];frame.wait_for_function('window.__showcaseState')
                    shot(page,f'{locale}-'+('mobile' if mobile else 'desktop')+'-prism-running.png')
                    page.locator('[data-game-exit]').click()
                    opposite='en' if locale=='zh' else 'zh'
                    page.locator('.language-switcher a[lang="'+('en' if opposite=='en' else 'zh-CN')+'"]').click()
                    assert '/games/prism-tide/' in page.url
                    assert page.locator('iframe').count()==0
                    check(f'{locale}/{mobile}: more games, silent game UI, equivalent language navigation')
                context.close()
            # A failed engine request is visible and retry creates a fresh session.
            context=browser.new_context();context.route('**/*.wasm',lambda route:route.abort())
            page=context.new_page();page.goto(base+'games/sonic-loom/')
            page.locator('[data-game-start]').click()
            expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','error',timeout=125000)
            expect(page.locator('iframe')).to_have_count(0)
            shot(page,'load-error-retry.png')
            context.unroute('**/*.wasm')
            page.locator('[data-game-start]').click()
            expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','running',timeout=120000)
            page.locator('[data-game-exit]').click();check('failed engine request gives retry; retry runs the real game')
            context.close();browser.close()
        report['passed']=True
    except Exception as exc:
        report['error']=str(exc)
        raise
    finally:
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        server.shutdown()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(args.site,args.output)
