#!/usr/bin/env python3
"""Actual WASM/graphics/input/audio acceptance, with no autoplay bypass or test cheats."""
import argparse,json,time,threading,hashlib,sys,urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

AUDIO_PROBE=r'''(() => {
  window.__audioPeak=0; window.__audioSamples=0; window.__audioOver=0; window.__audioNonzero=0; window.__audioContexts=[];
  window.__audioMeters=[]; window.__audioChannelCount=0; window.__audioChannelPeaks=[];
  const Native=window.AudioContext||window.webkitAudioContext;
  if(!Native)return;
  window.AudioContext=new Proxy(Native,{construct(target,args){const context=new target(...args);window.__audioContexts.push(context);return context;}});
  const connect=AudioNode.prototype.connect;
  const meters=new WeakMap();
  AudioNode.prototype.connect=function(destination,...args){
    if(destination instanceof AudioDestinationNode){
      let tap=meters.get(destination);
      if(!tap){
        const context=this.context, channelCount=destination.channelCount;
        // Match the real destination's speaker conversion before metering. Godot's
        // six-channel merger otherwise gives an analyser a sqrt(2)-boosted mono
        // fold-down of identical L/R, not the actual stereo channel amplitudes.
        tap=context.createGain();tap.gain.value=1;tap.channelCount=channelCount;
        tap.channelCountMode='explicit';tap.channelInterpretation=destination.channelInterpretation;
        meters.set(destination,tap);connect.call(tap,destination);
        const splitter=context.createChannelSplitter(channelCount);
        connect.call(tap,splitter);
        // This zero-gain branch keeps analysis nodes pulled without adding any
        // signal to the destination. The separate audible path above stays unity.
        const silent=context.createGain();silent.gain.value=0;
        connect.call(silent,destination);
        const metadata={channelCount,sampleRate:context.sampleRate,channelCountMode:tap.channelCountMode,channelInterpretation:tap.channelInterpretation,mainPathGain:tap.gain.value,channelPeaks:Array(channelCount).fill(0)};
        window.__audioMeters.push(metadata);
        window.__audioChannelCount=Math.max(window.__audioChannelCount,channelCount);
        while(window.__audioChannelPeaks.length<channelCount)window.__audioChannelPeaks.push(0);
        const channels=Array.from({length:channelCount},(_,channel)=>{
          const analyser=context.createAnalyser();analyser.fftSize=2048;
          analyser.channelCount=1;analyser.channelCountMode='explicit';analyser.channelInterpretation='discrete';
          connect.call(splitter,analyser,channel,0);connect.call(analyser,silent);
          return {analyser,data:new Float32Array(analyser.fftSize)};
        });
        setInterval(()=>{
          // Preserve the existing scalar reset interface used between patterns.
          if(window.__audioSamples===0){window.__audioChannelPeaks.fill(0);for(const meter of window.__audioMeters)meter.channelPeaks.fill(0);}
          channels.forEach(({analyser,data},channel)=>{
            analyser.getFloatTimeDomainData(data);
            for(const value of data){
              const magnitude=Math.abs(value);
              window.__audioPeak=Math.max(window.__audioPeak,magnitude);
              metadata.channelPeaks[channel]=Math.max(metadata.channelPeaks[channel],magnitude);
              window.__audioChannelPeaks[channel]=Math.max(window.__audioChannelPeaks[channel],magnitude);
              if(magnitude>=1)window.__audioOver++;
              if(magnitude>0.00001)window.__audioNonzero++;
            }
            window.__audioSamples+=data.length;
          });
        },25);
      }
      return connect.call(this,tap,...args);
    }
    return connect.call(this,destination,...args);
  };
})();'''
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def run(site,out,executable=None):
    out.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(site)))
    threading.Thread(target=server.serve_forever,daemon=True).start();origin=f'http://127.0.0.1:{server.server_port}'
    report={'checks':[],'console_diagnostics':[],'limitations':['Subjective listening and physical audio-device latency are not tested.','Mobile checks use Chromium touch emulation, not physical iOS/Android hardware.','GitHub Pages response headers and caching need a separate check after authorized deployment.','Firefox and Safari are not covered by this run.'],'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    def console_message(message):
        if message.type in ['error','warning']:
            item={'type':message.type,'text':message.text}
            if item not in report['console_diagnostics']:report['console_diagnostics'].append(item)
            print('BROWSER',message.type,message.text,flush=True)
    def check(name,**evidence):report['checks'].append({'name':name,'pass':True,**evidence});print(name,json.dumps(evidence),flush=True)
    def state(p):return p.evaluate('window.__showcaseState')
    def wait(p,expression):p.wait_for_function(expression,timeout=30000)
    def native_target(p,name):
        targets=state(p)['native_targets']
        if name.startswith('object:'):return targets['objects'][int(name.split(':')[1])]
        return targets[name]
    def tap_native(p,name):
        target=native_target(p,name)
        if isinstance(target,list):x,y,w,h=target
        else:x,y,w,h=[target[k] for k in ['x','y','width','height']]
        point(p,x+w/2,y+h/2,True)
    def action(p,command,touch=False):
        if touch and command in state(p).get('native_targets',{}):
            tap_native(p,command);return
        alternate=p.locator('#alternate');was_open=alternate.get_attribute('open') is not None
        if not was_open:p.locator('#alternate-label').click()
        button=p.locator(f'[data-command="{command}"]')
        button.tap() if touch else button.click()
        if not was_open:p.locator('#alternate-label').click()
    def start(p):
        begin=time.perf_counter();p.locator('#start').click()
        p.wait_for_function("document.body.dataset.state === 'running' && !!window.__showcaseState",timeout=120000)
        return round(time.perf_counter()-begin,3)
    def point(p,x,y,touch=False):
        width,height=state(p).get('layout_size',[1280,800])
        canvas=p.locator('#canvas');box=canvas.bounding_box()
        px=box['x']+x*box['width']/width;py=box['y']+y*box['height']/height
        viewport=p.evaluate('innerHeight');owner=p.page if hasattr(p,'page') else p
        frame_top=p.frame_element().bounding_box()['y'] if hasattr(p,'frame_element') else 0
        local_y=py-frame_top
        if local_y<60 or local_y>viewport-60:
            p.evaluate('dy=>window.scrollBy(0,dy)',local_y-viewport/2);p.wait_for_timeout(80)
            box=canvas.bounding_box();px=box['x']+x*box['width']/width;py=box['y']+y*box['height']/height
        if touch:owner.touchscreen.tap(px,py)
        else:owner.mouse.click(px,py)
    try:
      with sync_playwright() as pw:
        launch={'args':['--enable-unsafe-swiftshader'],'ignore_default_args':['--mute-audio']}
        if executable:launch['executable_path']=executable
        browser=pw.chromium.launch(**launch);report['browser']=browser.version
        for path,mime in [('/play/runtime/godot-4.6.3.wasm','application/wasm'),('/play/sonic-loom/game.pck','application/octet-stream')]:
          with urllib.request.urlopen(urllib.request.Request(origin+path,method='HEAD')) as response: assert response.headers.get_content_type()==mime
        check('local_wasm_and_pck_mime')
        for mobile,width,height in [(False,1440,1100),(True,390,844)]:
          label='touch' if mobile else 'desktop'
          context=browser.new_context(viewport={'width':width,'height':height},has_touch=mobile,is_mobile=mobile,device_scale_factor=1,record_video_dir=str(out/'videos'),record_video_size={'width':width,'height':height})
          context.add_init_script(AUDIO_PROBE)
          context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(origin+'/') else r.abort())
          page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',console_message)
          for slug in ['sonic-loom','prism-tide']:
            requests=[];page.on('request',lambda r:requests.append(r.url))
            response=page.goto(origin+f'/play/{slug}/?lang='+('zh' if mobile else 'en'))
            assert not response.headers.get('cross-origin-opener-policy') and not response.headers.get('cross-origin-embedder-policy')
            assert not any(u.endswith(('.wasm','.pck')) for u in requests)
            seconds=start(page);check(f'{slug}/{label}/real_wasm_start',seconds=seconds,cross_origin_isolated=page.evaluate('crossOriginIsolated'))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert page.evaluate('window.__audioPeak')==0
            before=state(page)
            if mobile:
              assert before['mobile_layout'] is True
              page.evaluate('scrollTo(0,0)');page.wait_for_timeout(80);page.screenshot(path=str(out/f'{slug}-touch-first-viewport.png'))
              box=page.locator('#canvas').bounding_box();scale=box['width']/before['layout_size'][0]
              assert before['minimum_text_size']*scale>=16
              targets=before['native_targets'];rects=list(targets.values()) if slug=='sonic-loom' else list(targets['objects'])+[targets[k] for k in ['select','turn','reset','next']]
              for rect in rects:
                w,h=(rect[2],rect[3]) if isinstance(rect,list) else (rect['width'],rect['height'])
                assert min(w,h)*scale>=44
              assert page.locator('#alternate').get_attribute('open') is None
              # Real finger drag over the game must scroll the page, not trap it.
              page.evaluate('scrollTo(0,0)');page.wait_for_timeout(80)
              box=page.locator('#canvas').bounding_box();x=box['x']+box['width']/2;y=min(box['y']+220,height-100)
              session=context.new_cdp_session(page)
              session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
              for dy in [35,75,120,170]:
                session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y-dy}]});page.wait_for_timeout(30)
              session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(160)
              assert page.evaluate('scrollY')>40
              check(f'{slug}/touch/portrait_readability_targets_and_pan',minimum_text_css=round(before['minimum_text_size']*scale,2),minimum_target_css=round(min(min((r[2],r[3]) if isinstance(r,list) else (r['width'],r['height'])) for r in rects)*scale,2),layout_size=before['layout_size'])
            if slug=='sonic-loom':
              assert before['master_gain_db']==-6.0
              action(page,'toggle',mobile);wait(page,'window.__showcaseState.playing === true')
              wait(page,'window.__audioPeak > 0.001')
              check(f'{slug}/{label}/user_gesture_audio_unlock',peak=page.evaluate('window.__audioPeak'))
              action(page,'toggle',mobile);wait(page,'window.__showcaseState.playing === false')
              if mobile:tap_native(page,'cell:0:1')
              else:point(page,358,333)
              wait(page,f'window.__showcaseState.pattern[0][1] === {1-int(before["pattern"][0][1])}')
              check(f'{slug}/{label}/native_canvas_input',cell_before=before['pattern'][0][1],cell_after=state(page)['pattern'][0][1])
              if mobile:action(page,'toggle',True)
              else:page.locator('#canvas').focus();page.keyboard.press('Space')
              wait(page,'window.__showcaseState.playing === true && window.__showcaseState.step >= 1')
              wait(page,'window.__audioPeak > 0.001')
              audio=page.evaluate('({peak:__audioPeak,samples:__audioSamples,contexts:__audioContexts.map(c=>c.state),channel_count:__audioChannelCount,channel_peaks:__audioChannelPeaks,meters:__audioMeters})')
              assert 'running' in audio['contexts'];assert audio['peak'] < 0.98,audio;check(f'{slug}/{label}/real_web_audio_nonzero',**audio)
              action(page,'toggle',mobile);wait(page,'window.__showcaseState.playing === false')
              if mobile:
                tap_native(page,'voice:2');wait(page,'window.__showcaseState.mobile_lane === 2');tap_native(page,'cell:2:1')
              else:
                if page.locator('#pads').get_attribute('open') is None:page.locator('#pads summary').click()
                page.locator('[data-cell="2:1"]').click()
              wait(page,'window.__showcaseState.pattern[2][1] === 1')
              action(page,'faster',mobile);wait(page,'window.__showcaseState.bpm === 108')
              action(page,'save',mobile);wait(page,"window.__showcaseState.status === 'PATTERN SAVED / LOCAL DEVICE'")
              page.screenshot(path=str(out/f'{slug}-{label}-edited.png'),full_page=True)
              action(page,'reset',mobile);wait(page,'window.__showcaseState.bpm === 104 && window.__showcaseState.pattern[2][1] === 0')
              action(page,'load',mobile);wait(page,'window.__showcaseState.bpm === 108 && window.__showcaseState.pattern[2][1] === 1')
            else:
              if mobile:tap_native(page,'object:0');action(page,'turn',True)
              else:point(page,609,476)
              wait(page,'window.__showcaseState.moves === 1 && window.__showcaseState.mirrors[0] === true')
              # Use another real native pointer event to connect the first puzzle.
              if mobile:tap_native(page,'object:1');action(page,'turn',True)
              else:point(page,609,324)
              wait(page,'window.__showcaseState.won === true')
              check(f'{slug}/{label}/native_input_solved_level',state=state(page))
              action(page,'next',mobile);wait(page,'window.__showcaseState.level === 2 && window.__showcaseState.moves === 0')
              # Large touch/keyboard-accessible controls invoke the same GDScript state.
              for command in ['turn','select','turn','select','select','select','turn']:action(page,command,mobile)
              wait(page,'window.__showcaseState.won === true')
              action(page,'save',mobile);wait(page,"window.__showcaseState.status === 'saved'")
              page.screenshot(path=str(out/f'{slug}-{label}-solved.png'),full_page=True)
              action(page,'reset',mobile);wait(page,'window.__showcaseState.moves === 0 && !window.__showcaseState.won')
              action(page,'load',mobile);wait(page,'window.__showcaseState.level === 2 && window.__showcaseState.won')
            if mobile:
              page.screenshot(path=str(out/f'{slug}-touch-controls-viewport.png'))
              page.locator('#canvas').screenshot(path=str(out/f'{slug}-portrait-canvas.png'))
              box=page.locator('#canvas').bounding_box();page.evaluate('dy=>window.scrollBy(0,dy)',box['y']+180);page.wait_for_timeout(80)
              page.screenshot(path=str(out/f'{slug}-touch-board-viewport.png'))
            check(f'{slug}/{label}/reset_and_load',state=state(page))
            # Exit follows Godot's real requestQuit / filesystem sync before reloading.
            page.locator('#exit').click();wait(page,"document.querySelector('#start') && !document.body.dataset.state")
            assert page.evaluate('typeof window.__showcaseState')=='undefined'
            start(page)
            if slug=='sonic-loom':wait(page,'window.__showcaseState.bpm === 108 && window.__showcaseState.pattern[2][1] === 1')
            else:action(page,'load',mobile);wait(page,'window.__showcaseState.level === 2 && window.__showcaseState.won')
            check(f'{slug}/{label}/save_survives_exit_and_restart',state=state(page))
            if not mobile and slug=='sonic-loom':
              # Fill every native voice through the actual accessible UI, never
              # by assigning game state, then meter the final destination mix.
              if page.locator('#pads').get_attribute('open') is None:page.locator('#pads summary').click()
              snapshot=state(page)
              for lane in range(4):
                for index in range(16):
                  if not snapshot['pattern'][lane][index]:page.locator(f'[data-cell="{lane}:{index}"]').click()
              wait(page,'window.__showcaseState.pattern.every(row=>row.every(v=>v===1))')
              for _ in range(13):action(page,'faster')
              wait(page,'window.__showcaseState.bpm === 160')
              def meter_case(name,seconds,active):
                current=state(page)
                if current['playing']:action(page,'toggle');wait(page,'!window.__showcaseState.playing')
                for lane in range(4):
                  if state(page)['muted'][lane] != (lane not in active):page.locator('#pad-grid .mute').nth(lane).click()
                page.wait_for_timeout(800)
                page.evaluate('window.__audioPeak=0;window.__audioOver=0;window.__audioNonzero=0;window.__audioSamples=0')
                action(page,'toggle');wait(page,'window.__showcaseState.playing')
                page.wait_for_timeout(int(seconds*1000))
                measurement=page.evaluate('({peak:__audioPeak,over_range_samples:__audioOver,nonzero_samples:__audioNonzero,sampled_values:__audioSamples,channel_count:__audioChannelCount,channel_peaks:__audioChannelPeaks,meters:__audioMeters})')
                assert measurement['channel_count']==2 and len(measurement['channel_peaks'])==2,measurement
                assert all(m['mainPathGain']==1 and m['channelCountMode']=='explicit' and m['channelInterpretation']=='speakers' for m in measurement['meters']),measurement
                assert 0.001<measurement['peak']<0.98 and measurement['over_range_samples']==0 and measurement['nonzero_samples']>0,measurement
                check('sonic-loom/final_output_headroom/'+name,**measurement)
                action(page,'toggle');wait(page,'!window.__showcaseState.playing')
              for lane in range(4):meter_case('solo_voice_'+str(lane),2,[lane])
              meter_case('all_64_steps_160_bpm',4,[0,1,2,3])
              for _ in range(25):action(page,'slower')
              wait(page,'window.__showcaseState.bpm === 60')
              meter_case('all_64_steps_60_bpm',8,[0,1,2,3])
            if mobile and slug=='prism-tide':
              action(page,'next',True);wait(page,'window.__showcaseState.level === 3 && !window.__showcaseState.won')
              for index in [0,1,2,3,6,7]:tap_native(page,f'object:{index}');action(page,'turn',True)
              wait(page,'window.__showcaseState.won === true')
              page.locator('#canvas').screenshot(path=str(out/'prism-tide-portrait-level3.png'))
              check('prism-tide/touch/all_three_rotated_native_levels',state=state(page))
            action(page,'reset',mobile);action(page,'reset',mobile)
            page.screenshot(path=str(out/f'{slug}-{label}-reset.png'),full_page=True)
            assert not errors,errors
          context.close()
        # Embedded launch, native keyboard focus, unload, and reopening.
        context=browser.new_context(viewport={'width':1440,'height':1100});page=context.new_page();page.goto(origin+'/cases/sonic-loom/')
        assert page.locator('video').count()>0
        page.locator('[data-play-start]').click();frame=page.frame_locator('[data-play-frame] iframe')
        frame.locator('#start').click();page.wait_for_function("document.querySelector('iframe').contentWindow.__showcaseState",timeout=120000)
        frame.locator('#canvas').focus();page.keyboard.press('Space')
        page.wait_for_function("document.querySelector('iframe').contentWindow.__showcaseState.playing === true")
        page.screenshot(path=str(out/'embedded-sonic.png'),full_page=True)
        page.locator('[data-play-exit]').click();assert page.locator('[data-play-frame] iframe').count()==0
        page.locator('[data-play-start]').click();assert page.locator('[data-play-frame] iframe').count()==1
        check('iframe_keyboard_focus_unload_reopen_video_retained');context.close()
        # Both localized phone case pages must retain native label/touch size.
        for lang,prefix in [('en',''),('zh','zh/')]:
          context=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True)
          page=context.new_page()
          for slug in ['sonic-loom','prism-tide']:
            page.goto(origin+f'/{prefix}cases/{slug}/')
            assert page.locator('video').count()>0
            page.locator('[data-play-start]').click();iframe=page.locator('[data-play-frame] iframe')
            iframe.scroll_into_view_if_needed();frame=page.frames[1];start(frame)
            assert frame.evaluate('document.documentElement.lang')==lang
            current=state(frame);assert current['mobile_layout']
            width=frame.locator('#canvas').bounding_box()['width'];scale=width/current['layout_size'][0]
            assert current['minimum_text_size']*scale>=16
            if slug=='sonic-loom':tap_native(frame,'cell:0:1');wait(frame,'window.__showcaseState.pattern[0][1]===1')
            else:tap_native(frame,'object:0');action(frame,'turn',True);wait(frame,'window.__showcaseState.moves===1')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            assert frame.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(out/f'{slug}-{lang}-phone-embedded-viewport.png'))
            frame.locator('#canvas').screenshot(path=str(out/f'{slug}-{lang}-embedded-canvas.png'))
            check(f'{slug}/{lang}/phone_iframe_native_input_and_readability',canvas_css_width=width,minimum_text_css=round(current['minimum_text_size']*scale,2))
            page.locator('[data-play-exit]').click();assert page.locator('[data-play-frame] iframe').count()==0
          context.close()
        # Loading can be cancelled without waiting for the download or an engine.
        context=browser.new_context();page=context.new_page();page.route('**/*.wasm',lambda r:None);page.goto(origin+'/play/sonic-loom/');page.locator('#start').click();page.locator('#cancel').click();page.wait_for_load_state('load');assert not page.locator('#start').is_disabled();check('cancel_pending_load');context.close()
        # A missing WASM must show a recoverable error, never a blank success.
        context=browser.new_context();page=context.new_page();page.route('**/*.wasm',lambda r:r.abort());page.goto(origin+'/play/sonic-loom/');page.locator('#start').click()
        page.wait_for_function("document.body.dataset.state === 'error'",timeout=120000)
        assert page.locator('#start').is_enabled();page.screenshot(path=str(out/'loading-error.png'));check('network_failure_visible_retry');page.unroute('**/*.wasm');page.locator('#start').click();page.wait_for_load_state('load');start(page);check('network_failure_recovery_restart');context.close()
        # Denied IndexedDB is a playable memory-only session, never a false save.
        context=browser.new_context();context.add_init_script("IDBFactory.prototype.open = function(){ throw new DOMException('Storage denied for test', 'SecurityError'); }");page=context.new_page()
        for slug in ['sonic-loom','prism-tide']:
            page.goto(origin+f'/play/{slug}/');start(page)
            assert state(page)['persistent'] is False
            action(page,'save');wait(page,"['save_failed','SAVE FAILED / STORAGE UNAVAILABLE'].includes(window.__showcaseState.status)")
            assert 'Saving failed' in page.locator('#status').inner_text()
            if slug=='sonic-loom':
                page.locator('#canvas').focus();page.keyboard.press('KeyS');wait(page,"window.__showcaseState.status === 'SAVE FAILED / STORAGE UNAVAILABLE'")
            check(f'{slug}/denied_storage_reports_failure')
        context.close()
        browser.close()
      report['passed']=True
    except Exception as exc:
      report['passed']=False;report['failure']=str(exc);raise
    finally:
      (out/'browser-verification.json').write_text(json.dumps(report,indent=2)+'\n');server.shutdown()

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--site',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--chromium');args=a.parse_args();run(args.site.resolve(),args.output.resolve(),args.chromium)
