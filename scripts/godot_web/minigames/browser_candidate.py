#!/usr/bin/env python3
"""Real Chromium game acceptance via mouse, keyboard and emulated touch only."""
import argparse,base64,hashlib,json,sys,threading,time
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from browser_test import AUDIO_PROBE
from playwright.sync_api import sync_playwright
CAPTURE_AUDIO = r"""(() => {
 window.__captureStreams=[];const previous=AudioNode.prototype.connect;const byDestination=new WeakMap();
 AudioNode.prototype.connect=function(destination,...args){
  if(destination instanceof AudioDestinationNode){let sink=byDestination.get(destination);if(!sink){sink=this.context.createMediaStreamDestination();byDestination.set(destination,sink);window.__captureStreams.push(sink.stream);}previous.call(this,sink,...args);}
  return previous.call(this,destination,...args);
 };
})();"""
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
PATHS=[[0,1,2,3,7,6,5,4,8,9,10,11,15,14,13,12],[0,4,8,12,13,9,5,1,2,6,10,14,15,11,7,3]]
EDGES3=[[0,1],[1,5],[5,4],[4,8],[8,12],[12,13],[13,14],[14,10],[10,9],[9,5],[5,6],[6,2],[2,3],[3,7],[7,11],[11,15]]
def solution(level):
 masks=[0]*16;edges=list(zip(PATHS[level],PATHS[level][1:])) if level<2 else EDGES3
 for a,b in edges:
  d=[-4,1,4,-1].index(b-a);masks[a]|=1<<d;masks[b]|=1<<((d+2)%4)
 return masks
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--site',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(args.site.resolve())));threading.Thread(target=server.serve_forever,daemon=True).start();origin=f'http://127.0.0.1:{server.server_port}'
 report={'checks':[],'diagnostics':[],'limitations':['Chromium only. Mobile is emulated touch, not a physical device.','Audio acceptance is sampled digital signal, not subjective listening.','Local/CI HTTP staging is not proof of public deployment.'],'started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 def check(name,**facts):report['checks'].append({'name':name,'passed':True,**facts});print(name,facts,flush=True)
 def state(p):return p.evaluate('window.__showcaseState')
 def wait(p,expr):
  try:p.wait_for_function(expr,timeout=30000)
  except Exception:
   report['failure']={'waiting_for':expr,'state':state(p)};raise
 def action(p,key):
  if p.locator('#alternate').get_attribute('open') is None:p.locator('#alternate-label').click()
  p.locator('[data-command="'+key+'"]').click()
 def native(p,index,touch=False):
  s=state(p);b=s['board'];canvas=p.locator('#canvas');canvas.scroll_into_view_if_needed();r=canvas.bounding_box();x=r['x']+(b['x']+(index%4+.5)*b['cell'])*r['width']/s['layout_width'];y=r['y']+(b['y']+(index//4+.5)*b['cell'])*r['height']/s['layout_height']
  if touch:p.touchscreen.tap(x,y)
  else:p.mouse.click(x,y)
 def native_control(p,key,touch=False):
  s=state(p);target=s['native_targets'][key];canvas=p.locator('#canvas');canvas.scroll_into_view_if_needed();r=canvas.bounding_box();x=r['x']+(target['x']+target['width']/2)*r['width']/s['layout_width'];y=r['y']+(target['y']+target['height']/2)*r['height']/s['layout_height']
  if touch:p.touchscreen.tap(x,y)
  else:p.mouse.click(x,y)
 def solve(p,touch=False):
  desired=solution(state(p)['level']-1)
  for i in range(16):
   for _ in range(4):
    if state(p)['masks'][i]==desired[i]:break
    before=state(p)['moves'];native(p,i,touch);wait(p,f'window.__showcaseState.moves > {before} || window.__showcaseState.won')
  wait(p,'window.__showcaseState.won');assert state(p)['lit']==16
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage'])
   report['browser']=browser.version
   for mobile in [False,True]:
    context=browser.new_context(viewport={'width':420 if mobile else 1280,'height':900},is_mobile=mobile,has_touch=mobile,record_video_dir=str(out/'videos'),record_video_size={'width':720 if mobile else 1280,'height':900 if mobile else 800})
    context.add_init_script(AUDIO_PROBE);context.add_init_script(CAPTURE_AUDIO);p=context.new_page();p.on('console',lambda m:report['diagnostics'].append({'type':m.type,'text':m.text}) if m.type in ['error','warning'] else None)
    requests=[];p.on('request',lambda req:requests.append(req.url))
    lang='zh' if mobile else 'en';p.goto(origin+'/play/signal-garden/index.html?lang='+lang);assert not any(x.endswith('.wasm') or x.endswith('.pck') for x in requests);check(f'{lang}: deferred engine loading')
    p.locator('#start').click();wait(p,'window.__showcaseState && document.body.dataset.state === "running"');assert state(p)['language']==lang
    check(f'{lang}: real Godot startup',state=state(p));assert p.evaluate('document.documentElement.scrollWidth <= innerWidth + 1');p.screenshot(path=str(out/f'{lang}-full-page.png'),full_page=True);p.locator('#canvas').screenshot(path=str(out/f'{lang}-start.png'))
    before=state(p)['masks'];native(p,0,mobile);wait(p,'window.__showcaseState.moves === 1');assert state(p)['masks']!=before
    action(p,'undo');wait(p,'window.__showcaseState.moves === 0');assert state(p)['masks']==before;check(f'{lang}: native tap and undo')
    if mobile:
     for width in [420,320]:
      p.set_viewport_size({'width':width,'height':900});p.wait_for_timeout(250);ss=state(p);r=p.locator('#canvas').bounding_box();scale=r['width']/ss['layout_width'];sizes={k:[round(v['width']*scale,2),round(v['height']*scale,2)] for k,v in ss['native_targets'].items()};assert all(min(v)>=44 for v in sizes.values()),sizes;check(f'mobile {width}: native touch targets at least 44 CSS pixels',sizes=sizes)
      if width==320:p.screenshot(path=str(out/'zh-narrow-full-page.png'),full_page=True)
     p.set_viewport_size({'width':420,'height':900});native_control(p,'language',True);wait(p,'window.__showcaseState.language === "en"');native_control(p,'language',True);wait(p,'window.__showcaseState.language === "zh"');check('mobile: visible native bilingual switch')
    if not mobile:
     p.locator('#canvas').focus();p.keyboard.press('ArrowRight');p.keyboard.press('Space');wait(p,'window.__showcaseState.moves === 1');check('desktop: real arrow/Space keyboard action')
    action(p,'reset');wait(p,'window.__showcaseState.moves === 0')
    p.evaluate('''() => {const video=document.getElementById('canvas').captureStream(30);const audio=window.__captureStreams.flatMap(s=>s.getAudioTracks());if(!audio.length)throw new Error('Actual game audio stream missing');window.__nativeRecordingChunks=[];window.__nativeRecorder=new MediaRecorder(new MediaStream([...video.getVideoTracks(),...audio]),{mimeType:'video/webm;codecs=vp8,opus',videoBitsPerSecond:900000,audioBitsPerSecond:96000});window.__nativeRecorder.ondataavailable=e=>{if(e.data.size)window.__nativeRecordingChunks.push(e.data);};window.__nativeRecorder.start(250);}''')
    p.wait_for_timeout(700)
    native(p,2,mobile);wait(p,'window.__showcaseState.moves === 1');action(p,'save');wait(p,'window.__showcaseState.status === "saved"');saved=state(p)['masks'];action(p,'reset');wait(p,'window.__showcaseState.moves === 0');action(p,'load');wait(p,'window.__showcaseState.status === "loaded"');assert state(p)['masks']==saved;check(f'{lang}: save/reset/load')
    action(p,'toggle');wait(p,'window.__showcaseState.paused');moves=state(p)['moves'];native(p,0,mobile);p.wait_for_timeout(150);assert state(p)['moves']==moves;action(p,'toggle');wait(p,'!window.__showcaseState.paused');check(f'{lang}: paused game ignores board input')
    action(p,'reset');wait(p,'window.__showcaseState.moves === 0')
    for level in range(3):
     solve(p,mobile);p.wait_for_timeout(700);p.screenshot(path=str(out/f'{lang}-garden-{level+1}-won.png'));check(f'{lang}: garden {level+1} won by actual input',moves=state(p)['moves'])
     if level<2:action(p,'next');wait(p,f'window.__showcaseState.level === {level+2} && !window.__showcaseState.won')
    audio=p.evaluate('({peak:window.__audioPeak,samples:window.__audioSamples,nonzero:window.__audioNonzero,over:window.__audioOver,channels:window.__audioChannelPeaks})');assert audio['nonzero']>0 and audio['peak']<1 and audio['over']==0;check(f'{lang}: unlocked audio measured without autoplay bypass',**audio)
    p.locator('#controls button').last.click();wait(p,'window.__showcaseState.muted');check(f'{lang}: mute state')
    recorded=p.evaluate('''() => new Promise(resolve=>{window.__nativeRecorder.onstop=()=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.readAsDataURL(new Blob(window.__nativeRecordingChunks,{type:'video/webm'}));};window.__nativeRecorder.stop();})''')
    (out/f'{lang}-native-gameplay-with-audio.webm').write_bytes(base64.b64decode(recorded));check(f'{lang}: consecutive native canvas and actual game audio recorded')
    p.locator('#exit').click();p.wait_for_load_state('load');p.wait_for_selector('#start:visible');check(f'{lang}: exit returns to unloaded start');context.close()
   host=args.site/'embed-acceptance.html'
   host.write_text('<!doctype html><meta charset="utf-8"><button id="play">Play</button><button id="sound">Sound</button><button id="reset">Reset</button><button id="exit">Exit</button><iframe id="game" src="play/signal-garden/index.html?embed=1&lang=zh" width="1120" height="780"></iframe><script>const frame=document.getElementById("game");window.messages=[];addEventListener("message",e=>{if(e.source===frame.contentWindow&&e.origin===location.origin)messages.push(e.data)});for(const [id,type] of [["play","start"],["sound","sound-on"],["reset","reset"]])document.getElementById(id).onclick=()=>frame.contentWindow.postMessage({type:"showcase:"+type},location.origin);document.getElementById("exit").onclick=()=>frame.remove();</script>')
   context=browser.new_context(viewport={'width':1280,'height':950});context.add_init_script(AUDIO_PROBE);p=context.new_page();p.goto(origin+'/embed-acceptance.html');p.wait_for_function('messages.some(m=>m.type==="showcase:ready")');frame=p.frames[1];assert not frame.evaluate('typeof Engine !== "undefined"');p.locator('#play').click();frame.wait_for_function('window.__showcaseState && document.body.dataset.state==="running"');wait(frame,'window.__showcaseState.muted');assert frame.evaluate('window.__audioNonzero')==0;check('embedded: parent start handshake and strict default mute')
   # Native canvas user input must not reopen muted output; observe real destination samples.
   rect=frame.locator('#canvas').bounding_box();ss=state(frame);b=ss['board'];x=rect['x']+(b['x']+b['cell']/2)*rect['width']/ss['layout_width'];y=rect['y']+(b['y']+b['cell']/2)*rect['height']/ss['layout_height'];p.mouse.click(x,y);frame.wait_for_function('window.__showcaseState.moves===1');p.wait_for_timeout(400);assert frame.evaluate('window.__audioNonzero')==0;check('embedded: canvas interaction cannot bypass audio gate')
   p.locator('#sound').click();frame.wait_for_function('!window.__showcaseState.muted');p.mouse.click(x,y);frame.wait_for_function('window.__audioNonzero>0');check('embedded: explicit sound gesture enables real audio')
   p.locator('#reset').click();frame.wait_for_function('window.__showcaseState.moves===0');p.locator('#exit').click();assert p.locator('iframe').count()==0;check('embedded: parent reset and exit release frame');context.close()
   context=browser.new_context(viewport={'width':1280,'height':800});p=context.new_page();p.route('**/*.wasm',lambda route:route.abort());p.goto(origin+'/play/signal-garden/index.html');p.locator('#start').click();p.wait_for_function('document.body.dataset.state === "error"');p.screenshot(path=str(out/'load-error.png'));check('blocked WASM displays visible retry');p.unroute('**/*.wasm');p.locator('#start').click();p.wait_for_load_state('load');p.wait_for_selector('#start:visible');p.locator('#start').click();wait(p,'window.__showcaseState && document.body.dataset.state === \"running\"');check('failed load can retry and run the real engine');context.close();browser.close()
  report['passed']=True
 finally:
  server.shutdown();report['pack_sha256']=hashlib.sha256((args.site/'play/signal-garden/game.pck').read_bytes()).hexdigest() if (args.site/'play/signal-garden/game.pck').exists() else None;(out/'verification.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
