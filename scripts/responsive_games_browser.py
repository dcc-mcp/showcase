#!/usr/bin/env python3
"""Real-engine viewport/iframe resize regressions; no state-command test shortcuts."""
import argparse, json, threading
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
from localization_browser_smoke import MountHandler

def run(site, output):
    from playwright.sync_api import sync_playwright, expect
    output.mkdir(parents=True, exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(MountHandler,directory=str(site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/showcase/'
    report={'passed':False,'checks':[],'screenshots':[],'scope':'Actual Godot WASM in Chromium; touch emulation; CSS zoom plus layout viewport equivalents, not OS-level browser zoom or physical phones'}
    def check(name, **evidence):
        report['checks'].append({'name':name,**evidence});print('PASS',name,evidence,flush=True)
    def shot(page,name):
        page.screenshot(path=str(output/name));report['screenshots'].append(name)
    def native_point(page, frame, x, y, touch=False):
        logical=frame.evaluate('window.__showcaseState.layout_size')
        canvas=frame.locator('#canvas');box=canvas.bounding_box()
        px=box['x']+x*box['width']/logical[0];py=box['y']+y*box['height']/logical[1]
        viewport=page.evaluate('innerHeight')
        if py<40 or py>viewport-40:
            page.evaluate('dy=>window.scrollBy(0,dy)',py-viewport/2)
            page.wait_for_timeout(100);box=canvas.bounding_box()
            px=box['x']+x*box['width']/logical[0];py=box['y']+y*box['height']/logical[1]
        (page.touchscreen.tap if touch else page.mouse.click)(px,py)
    def saved_state(frame, slug):
        state=frame.evaluate('window.__showcaseState')
        keys=['pattern','bpm','muted'] if slug=='sonic-loom' else ['level','moves','selected','won','mirrors','gates']
        return {key:state[key] for key in keys}
    def geometry(frame):
        return frame.locator('#canvas').evaluate('''c=>{const r=c.getBoundingClientRect(),s=document.querySelector('#stage').getBoundingClientRect();return {w:r.width,h:r.height,ratio:c.width/c.height,contained:r.left>=s.left-1&&r.right<=s.right+1&&r.top>=s.top-1&&r.bottom<=s.bottom+1,overflow:document.documentElement.scrollWidth>innerWidth+1,bodyOverflow:document.documentElement.scrollHeight>innerHeight+1}}''')
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--enable-unsafe-swiftshader'])
        ctx=browser.new_context(viewport={'width':2048,'height':1016},has_touch=False,service_workers='block')
        ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base) else r.abort())
        page=ctx.new_page();page.set_default_timeout(30000)
        for slug in ['sonic-loom','prism-tide']:
            page.set_viewport_size({'width':2048,'height':1016})
            page.goto(base+'zh/games/'+slug+'/')
            assert page.locator('iframe').count()==0
            shot(page,slug+'-idle-wide.png')
            page.locator('[data-game-start]').click()
            expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','running',timeout=120000)
            frame=page.frames[1];frame.wait_for_function('!!window.__showcaseState')
            assert page.locator('.game-stage').bounding_box()['width']>1200
            # Change actual native state using keyboard, then retain it across every reflow.
            frame.locator('canvas').focus()
            if slug=='sonic-loom':
                page.keyboard.press('ArrowUp');frame.wait_for_function('window.__showcaseState.bpm===105')
            else:
                page.keyboard.press('Space');frame.wait_for_function('window.__showcaseState.moves===1')
            expected_state=saved_state(frame,slug)
            for width,height in [(2048,1016),(1366,768),(900,600),(390,844),(844,390),(320,640),(1024,768),(2048,1016)]:
                page.set_viewport_size({'width':width,'height':height})
                mobile=page.locator('.game-stage').evaluate('e=>e.clientWidth<720')
                frame.wait_for_function('(mobile)=>window.__showcaseState.mobile_layout===mobile',arg=mobile)
                frame.wait_for_function('''()=>{const c=document.querySelector('#canvas'),r=c.getBoundingClientRect();return r.width>0&&Math.abs(r.width/r.height-c.width/c.height)<.005}''')
                g=geometry(frame)
                assert g['contained'] and not g['overflow'] and not g['bodyOverflow'],g
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                assert saved_state(frame,slug)==expected_state,(saved_state(frame,slug),expected_state)
                # Actual native hit-testing after reflow, not just DOM geometry.
                if width in [900,390]:
                    page.wait_for_timeout(120)
                    state=frame.evaluate('window.__showcaseState')
                    if slug=='sonic-loom':
                        target=state['native_targets']['cell:0:1'] if mobile else [333,300,51,66]
                        native_point(page,frame,target[0]+target[2]/2,target[1]+target[3]/2)
                        frame.wait_for_function('(before)=>window.__showcaseState.pattern[0][1]!==before',arg=state['pattern'][0][1])
                    else:
                        if mobile:
                            target=state['native_targets']['objects'][1]
                            native_point(page,frame,target['center_x'],target['center_y'])
                            frame.wait_for_function('window.__showcaseState.selected===1')
                            frame.locator('canvas').press('Space')
                        else:native_point(page,frame,609,324)
                        frame.wait_for_function('(before)=>window.__showcaseState.moves===before+1',arg=state['moves'])
                    expected_state=saved_state(frame,slug)
                check(slug+f'/{width}x{height}',mobile=mobile,canvas=g)
                if width in [2048,390,844]:
                    page.locator('.game-stage').scroll_into_view_if_needed()
                    shot(page,f'{slug}-{width}x{height}.png')
                    if width==390:
                        name=slug+'-portrait-full-stage.png'
                        page.locator('.game-stage').screenshot(path=str(output/name))
                        report['screenshots'].append(name)
            # Zoom-induced CSS reflow: ratio stays exact, state survives, no clipping.
            page.evaluate("document.body.style.zoom='1.5'")
            page.wait_for_timeout(200)
            assert geometry(frame)['contained']
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            shot(page,slug+'-css-zoom150.png')
            page.evaluate("document.body.style.zoom='1'")
            page.locator('[data-game-fullscreen]').click()
            page.wait_for_function('!!document.fullscreenElement')
            page.wait_for_timeout(200)
            assert geometry(frame)['contained'] and not geometry(frame)['bodyOverflow']
            shot(page,slug+'-fullscreen.png')
            page.locator('[data-game-leave-full]').click()
            page.wait_for_function('!document.fullscreenElement')
            # Accessible fallback can open without covering/cropping the native canvas.
            frame.locator('#alternate-label').click()
            page.wait_for_timeout(100)
            assert geometry(frame)['contained'] and not geometry(frame)['bodyOverflow']
            frame.locator('[data-command=reset]').click()
            check(slug+'/zoom-fullscreen-accessible-controls')
            page.locator('[data-game-exit]').click()
            assert page.locator('iframe').count()==0
            # Existing detail page must also resize its full standalone shell naturally.
            page.set_viewport_size({'width':390,'height':844})
            page.goto(base+'zh/cases/'+slug+'/')
            page.locator('[data-play-start]').click()
            frame=page.frames[1];frame.locator('#start').click()
            frame.wait_for_function("document.body.dataset.state==='running'",timeout=120000)
            page.wait_for_function('''()=>{const f=document.querySelector('[data-play-frame] iframe');return f&&f.clientHeight>=f.contentDocument.querySelector('main').getBoundingClientRect().height-1}''')
            g=geometry(frame);assert g['contained'] and not g['overflow']
            assert not g['bodyOverflow'],g
            check(slug+'/legacy-detail-iframe-auto-height')
            page.locator('[data-play-exit]').click()
        ctx.close()
        # Actual touch contexts retain the readable native phone layout when
        # rotated; desktop's tiny 16-column HUD must never replace it on a phone.
        ctx=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,service_workers='block')
        page=ctx.new_page();page.set_default_timeout(30000)
        for slug in ['sonic-loom','prism-tide']:
            page.goto(base+'games/'+slug+'/')
            page.locator('[data-game-start]').click()
            expect(page.locator('[data-game-stage]')).to_have_attribute('data-state','running',timeout=120000)
            frame=page.frames[1]
            for width,height in [(390,844),(844,390),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                frame.wait_for_function('window.__showcaseState?.mobile_layout===true')
                page.wait_for_timeout(150)
                g=geometry(frame)
                assert g['contained'] and not g['bodyOverflow'] and not g['overflow'],g
                assert 32*g['w']/720>=16,g
                assert frame.locator('canvas').evaluate("c=>getComputedStyle(c).touchAction==='pan-y'")
                check(slug+f'/touch-orientation-{width}x{height}',canvas=g)
                if width==844:
                    shot(page,slug+'-touch-landscape.png')
                    # Element screenshots can expand the emulated viewport and
                    # temporarily change its pointer media query. Keep the real
                    # touch viewport and scroll the outer page to show the HUD.
                    frame.locator('#alternate-label').scroll_into_view_if_needed()
                    shot(page,slug+'-touch-landscape-controls.png')
                    assert frame.evaluate('window.__showcaseState.mobile_layout') is True
                    assert geometry(frame)['contained'] and not geometry(frame)['bodyOverflow']
                    assert frame.evaluate("matchMedia('(pointer:coarse)').matches")
                    check(slug+'/touch-landscape-visible-controls-after-scroll')
            page.locator('[data-game-exit]').click()
        ctx.close();browser.close();report['passed']=True
    except Exception as error:
        report['error']=str(error)
        try:
            report['last_native_state']=frame.evaluate('window.__showcaseState')
            shot(page,'failure.png')
        except Exception:
            pass
        raise
    finally:
        server.shutdown();(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,default=Path('_site'));p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.site,a.output)
