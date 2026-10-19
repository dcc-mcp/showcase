#!/usr/bin/env python3
"""Real Chromium clicks/keys/emulated touch against the official exported Godot."""
from __future__ import annotations
import argparse
import math
import os
import re
import subprocess
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from common import check_engine_log, isolated_output, receipts, sha256, stop_process, write_json
from interaction import InputPlan
from capture_native import image_stats
from media import inspect_audio, inspect_video


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


# Keep browser security defaults. Missing WebGL2 is a capability blocker,
# never a reason to opt into an unsafe fallback renderer.
BROWSER_ARGS=['--disable-dev-shm-usage']
# The pinned Playwright version injects this unsafe renderer opt-in by default.
# Exclude it explicitly, even when it is absent from our own args.
BROWSER_IGNORED_DEFAULT_ARGS=['--mute-audio','--enable-unsafe-swiftshader']


def canvas_point(geometry,x,y):
    """Map engine canvas pixels to real browser CSS coordinates, not window pixels."""
    values=[geometry.get(k) for k in ('x','y','width','height','pixel_width','pixel_height')]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
        raise ValueError('Missing finite actual canvas geometry')
    left,top,width,height,pixels_w,pixels_h=values
    if min(width,height,pixels_w,pixels_h)<=0 or not(0<=x<pixels_w and 0<=y<pixels_h):
        raise ValueError('Input is outside the actual engine canvas')
    return left+x*width/pixels_w,top+y*height/pixels_h


class RequiredPayloadOutage:
    """Keep a required download unavailable until the test explicitly removes it."""
    def __init__(self):self.attempts=0

    def __call__(self,route):
        route.abort('failed')
        self.attempts+=1


def browser_executable(value):
    """Validate an explicitly selected installed browser, with no fallback."""
    path=Path(value).resolve(strict=True)
    if not path.is_file() or not os.access(path,os.X_OK):
        raise ValueError('Explicit browser is not an executable file: '+str(path))
    result=subprocess.run([str(path),'--version'],check=True,capture_output=True,text=True,timeout=10)
    version=result.stdout.strip()
    if not re.fullmatch(r'(?:Google Chrome(?: for Testing)?|Chromium) [0-9]+(?:\.[0-9]+){3}(?: .*)?',version):
        raise ValueError('Unrecognized explicit browser version: '+version)
    return {'executable_path':str(path),'executable_version':version}


def main():
    from playwright.sync_api import sync_playwright
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--full',action='store_true');p.add_argument('--chromium',help='Optional explicit existing Chromium executable')
    args=p.parse_args();out=isolated_output(args.output,args.site)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(args.site.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/index.html'
    report={'schema':1,'passed':False,'mode':'full' if args.full else 'preview','engine':'actual official Godot Web export',
            'pck_sha256':sha256(args.site/'index.pck'),'viewports':[],
            'browser_launch':{'args':BROWSER_ARGS,'chromium_sandbox':True,
                              'ignore_default_args':BROWSER_IGNORED_DEFAULT_ARGS,
                              'requested_executable':args.chromium},
            'limitations':['Portrait touch is Chromium device emulation, not a physical phone.','Numerical audio checks do not replace listening.','No deployed-site claim.']}
    try:
        selected=browser_executable(args.chromium) if args.chromium else None
        if selected:report['browser_launch'].update(selected)
        with sync_playwright() as pw:
            options={'headless':True,'args':BROWSER_ARGS,'chromium_sandbox':True,'ignore_default_args':BROWSER_IGNORED_DEFAULT_ARGS}
            if selected:options['executable_path']=selected['executable_path']
            browser=pw.chromium.launch(**options);report['browser_version']=browser.version
            try:
                for width,height,mobile in ((1280,720,False),(390,844,True)):
                    label='portrait' if mobile else 'desktop';directory=out/label;directory.mkdir()
                    result={'name':label,'passed':False,'checks':[],'touch_emulation':mobile};report['viewports'].append(result)
                    console=[];failures=[];recorder=None;page=None;context=None;video=None
                    try:
                        context=pw_context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1,
                            is_mobile=mobile,has_touch=mobile,**({'record_video_dir':str(directory/'video'),'record_video_size':{'width':width,'height':height}} if args.full else {}))
                        page=context.new_page();page.on('console',lambda msg:console.append(msg.text));page.on('pageerror',lambda error:failures.append(str(error)))
                        def wait_line(prefix,start=0,seconds=120):
                            deadline=time.monotonic()+seconds
                            while time.monotonic()<deadline:
                                if page.is_closed():raise RuntimeError('Actual browser page closed early')
                                if failures:raise RuntimeError('Browser JavaScript error: '+str(failures))
                                values=receipts('\n'.join(console[start:]),prefix)
                                if values:return values[-1]
                                page.wait_for_timeout(100)
                            raise TimeoutError('No actual '+prefix+' receipt')
                        page.goto(url,wait_until='domcontentloaded');wait_line('DAWNKEEP_FRAME_READY');wait_line('DAWNKEEP_STATE')
                        def observe():
                            if page.is_closed():raise RuntimeError('Actual browser page closed')
                            if failures:raise RuntimeError('Browser JavaScript failure: '+str(failures))
                            check_engine_log('\n'.join(console));values=receipts('\n'.join(console))
                            if not values:raise ValueError('No actual runtime state')
                            return values[-1]
                        def canvas_geometry():
                            geometry=page.locator('#canvas').evaluate('''canvas => {
                                const r=canvas.getBoundingClientRect(),t=document.querySelector('#dawnkeep-web-tools').getBoundingClientRect();
                                return {x:r.x,y:r.y,width:r.width,height:r.height,pixel_width:canvas.width,pixel_height:canvas.height,
                                        toolbar_bottom:t.bottom,window_width:innerWidth,window_height:innerHeight};
                            }''')
                            if geometry['toolbar_bottom']>geometry['y']+.5 or geometry['y']+geometry['height']>geometry['window_height']+.5:
                                raise RuntimeError('Web toolbar overlaps the engine canvas or canvas is clipped')
                            return geometry
                        initial_canvas=canvas_geometry();result['canvas_geometry']=initial_canvas
                        def click(x,y):
                            css_x,css_y=canvas_point(canvas_geometry(),x,y)
                            if not page.evaluate('p => document.elementFromPoint(p.x,p.y) === document.querySelector("#canvas")',{'x':css_x,'y':css_y}):
                                raise RuntimeError('Actual game pointer target is occluded by the Web wrapper')
                            if mobile:page.touchscreen.tap(css_x,css_y)
                            else:page.mouse.click(css_x,css_y)
                            result.setdefault('events',[]).append({'type':'touchscreen.tap' if mobile else 'mouse.click','x':css_x,'y':css_y,'engine_x':x,'engine_y':y})
                        def key(name,down):
                            (page.keyboard.down if down else page.keyboard.up)(name)
                            result.setdefault('events',[]).append({'type':'keyboard.down' if down else 'keyboard.up','key':name})
                        def screenshot(name):
                            path=directory/(name+'.png');page.screenshot(path=str(path),timeout=45000)
                            result.setdefault('screenshots',[]).append({'name':path.name,**image_stats(path),'state':observe()})
                        pause=lambda seconds:page.wait_for_timeout(seconds*1000)
                        plan=InputPlan(observe,click,key,pause,(initial_canvas['pixel_width'],initial_canvas['pixel_height']),screenshot,result)
                        screenshot('intro-zh')
                        plan.gate(touch=mobile);write_json(directory/'browser.json',result)
                        # The wrapper must not cover either native Close button.
                        # Exercise these before any expensive combat recording.
                        for button,shop in (('equipment','equipment'),('build','build')):
                            before=plan.tap(button)
                            plan.wait(lambda s:s['ui'].get('shop')==shop,'actual '+shop+' panel opened',before['sample_id'])
                            screenshot(shop+'-panel')
                            before=plan.tap('close')
                            plan.wait(lambda s:s['ui'].get('shop')=='','actual '+shop+' panel closed',before['sample_id'])
                        # Browser gesture and bus signal are read-only evidence.
                        music=observe().get('music',{})
                        result['music_after_real_gesture']=music
                        if args.full:
                            if not music.get('unlocked') or not music.get('playing') or music.get('muted'):
                                raise RuntimeError('Music did not unlock/play after actual user gesture')
                            recorder=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','pulse','-i','default','-c:a','pcm_s16le',str(directory/'runtime-audio.wav')])
                            if mobile:plan.combat()
                            # Software Web rendering measured ~0.41 simulated
                            # seconds/wall second during AFK capture. Retain the
                            # same natural-defeat/restart assertions with a
                            # bounded 900s capture budget (native remains 600s).
                            else:plan.full_desktop(max_afk_wall_seconds=900)
                            stop_process(recorder);recorder=None
                            result['captured_audio']=inspect_audio(directory/'runtime-audio.wav')
                        def shell_click(selector):
                            locator=page.locator(selector)
                            (locator.tap if mobile else locator.click)()
                        # Real fullscreen click must report a browser fullscreen transition.
                        boundary=len(console);shell_click('#dawnkeep-web-fullscreen')
                        event=wait_line('DAWNKEEP_WEB_FULLSCREEN',boundary,15)
                        if event.get('active') is not True or event.get('trusted') is not True:raise RuntimeError('Actual fullscreen did not engage')
                        shell_click('#dawnkeep-web-fullscreen')
                        boundary=len(console);shell_click('#dawnkeep-web-quit');event=wait_line('DAWNKEEP_WEB_EXIT',boundary,30)
                        if event.get('ok') is not True or event.get('code')!=0:raise RuntimeError('Official Engine.requestQuit/onExit path failed')
                        page.screenshot(path=str(directory/'engine-exited.png'))
                        boundary=len(console);shell_click('#dawnkeep-web-restart');wait_line('DAWNKEEP_FRAME_READY',boundary)
                        result['lifecycle']={'fullscreen':True,'actual_engine_quit':True,'fresh_engine_restart':True}
                        # Godot retries transient downloads internally. Hold the required
                        # payload unavailable until its actual failure UI appears.
                        outage=RequiredPayloadOutage()
                        page.route('**/index.pck',outage)
                        boundary=len(console);page.reload(wait_until='domcontentloaded');wait_line('DAWNKEEP_WEB_LOAD_ERROR',boundary)
                        page.screenshot(path=str(directory/'loading-retry.png'))
                        if outage.attempts<1:raise RuntimeError('Required PCK outage was not exercised')
                        result['loading_outage']={'aborted_pck_requests':outage.attempts}
                        page.unroute('**/index.pck',outage);boundary=len(console)
                        shell_click('#dawnkeep-web-retry');wait_line('DAWNKEEP_FRAME_READY',boundary)
                        result['lifecycle']['loading_retry']=True
                        check_engine_log('\n'.join(console));result['passed']=True
                        if page.video:video=page.video
                    except Exception as error:
                        result['blocker']=str(error)
                        if page and not page.is_closed():
                            try:page.screenshot(path=str(directory/'failure.png'),timeout=15000)
                            except Exception:pass
                        # Preserve the failed viewport and inspect the other independent
                        # context too. The aggregate below still fails the entire job.
                    finally:
                        stop_process(recorder)
                        if context:context.close()
                        if video:
                            try:result['movie']=inspect_video(video.path())
                            except Exception as error:result['movie_error']=str(error);result['passed']=False
                        (directory/'console.log').write_text('\n'.join(console)+'\n');write_json(directory/'browser.json',result)
                        write_json(out/'browser.json',report)
                report['passed']=all(item['passed'] for item in report['viewports'])
                if not report['passed']:raise RuntimeError('One or more actual viewport checks failed')
            finally:browser.close()
    except Exception as error:report['blocker']=str(error);raise
    finally:server.shutdown();write_json(out/'browser.json',report)


if __name__=='__main__':main()
