import pathlib,sys,json,threading,argparse,subprocess
from functools import partial
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from localization_browser_smoke import MountHandler
parser=argparse.ArgumentParser(description='Browser acceptance of partial crate evidence, not full-film quality.')
parser.add_argument('--site',type=pathlib.Path,required=True)
parser.add_argument('--output',type=pathlib.Path,required=True)
parser.add_argument('--expected-head',required=True)
args=parser.parse_args()
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
if head!=args.expected_head:raise ValueError('Candidate head does not match requested revision')
O=args.output;O.mkdir(parents=True,exist_ok=True)
server=ThreadingHTTPServer(('127.0.0.1',0),partial(MountHandler,directory=str(args.site)));threading.Thread(target=server.serve_forever,daemon=True).start();origin=f'http://127.0.0.1:{server.server_port}'
report={'scope':'Chromium acceptance of the partial excerpt only; not full-film quality approval','head_sha':head,'pages':[]}
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch();report['browser']=browser.version
  for layout,w,h in [('desktop',1440,1000),('mobile',390,844)]:
   for locale,prefix in [('en',''),('zh','zh/')]:
    context=browser.new_context(viewport={'width':w,'height':h},service_workers='block')
    context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    path=f'/showcase/{prefix}cases/crate-lookdev/';page.goto(origin+path,wait_until='networkidle');page.set_default_timeout(15000)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    note=page.locator('.evidence-note');assert ('partial stage evidence' if locale=='en' else '未完成阶段证据') in note.inner_text()
    note.screenshot(path=str(O/f'{layout}-{locale}-boundary.png'))
    video=page.locator('video').first;video.scroll_into_view_if_needed();video.evaluate('(v)=>v.load()');page.wait_for_function('document.querySelector("video").readyState>=2')
    meta=video.evaluate('(v)=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,autoplay:v.autoplay,controls:v.controls})')
    assert abs(meta['duration']-50/24)<.001 and meta['width']==960 and meta['height']==540 and meta['controls'] and not meta['autoplay'],meta
    video.evaluate('(v)=>v.play()');page.wait_for_function('document.querySelector("video").ended',timeout=10000)
    quality=video.evaluate('(v)=>{let q=v.getVideoPlaybackQuality();return {totalVideoFrames:q.totalVideoFrames,droppedVideoFrames:q.droppedVideoFrames}}')
    video.evaluate('(v)=>v.currentTime=1.1');page.wait_for_function('Math.abs(document.querySelector("video").currentTime-1.1)<0.05 && !document.querySelector("video").seeking')
    video.locator('..').screenshot(path=str(O/f'{layout}-{locale}-excerpt.png'))
    links=page.locator(f'a[href$="film-2026-10-12/replay.py"]');assert links.count()==1
    response=context.request.get(links.get_attribute('href') if links.get_attribute('href').startswith('http') else page.evaluate('(h)=>new URL(h,location.href).href',links.get_attribute('href')));assert response.status==200
    assert not errors,errors
    report['pages'].append({'layout':layout,'locale':locale,'partial_boundary_visible':True,'no_horizontal_overflow':True,'media':meta,'played_to_end':True,'seek_pass':True,'playback_quality':quality,'replay_link_http_status':response.status})
    context.close()
  browser.close()
 report['status']='pass'
finally:
 server.shutdown();(O/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report.get('status'),'pages':len(report['pages'])}))
