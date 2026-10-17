from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright,expect
import threading,json,hashlib,argparse
from browser_preview import QuietHandler
parser=argparse.ArgumentParser();parser.add_argument('--site',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
site=a.site;out=a.output;out.mkdir(parents=True,exist_ok=True)
server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(site)))
threading.Thread(target=server.serve_forever,daemon=True).start();origin=f'http://127.0.0.1:{server.server_port}'
report={'subjective_listening':'not_run','checks':[]}
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch()
  report['browser']=browser.version
  for name,width,height in [('desktop',1440,1000),('mobile',390,844)]:
   context=browser.new_context(viewport={'width':width,'height':height},accept_downloads=True,reduced_motion='reduce')
   context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(origin+'/') else r.abort())
   page=context.new_page();page.goto(origin+'/cases/sonic-loom/',wait_until='networkidle')
   assert page.locator('h1').inner_text().startswith('Sonic Loom')
   assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
   page.screenshot(path=str(out/(name+'-top.png')))
   for tag in ['video','audio']:
    el=page.locator(tag).first;el.scroll_into_view_if_needed()
    expect(el).to_have_js_property('controls',True)
    expect(el).to_have_js_property('paused',True)
    assert el.evaluate('(v)=>!v.autoplay && v.played.length===0')
    # Real keyboard activation, with no autoplay-policy bypass, loads an
    # on-demand video and exercises the same native controls as the user.
    el.press('Space')
    page.wait_for_function(f'document.querySelector("{tag}").readyState>=2 && !document.querySelector("{tag}").paused && document.querySelector("{tag}").currentTime>.3')
    before=el.evaluate('(v)=>({duration:v.duration,muted:v.muted,autoplay:v.autoplay})')
    assert 12.8<before['duration']<13.2 and not before['muted'] and not before['autoplay'],before
    assert el.evaluate('(v)=>v.currentTime')>.3
    el.press('Space')
    expect(el).to_have_js_property('paused',True)
    el.evaluate('(v)=>v.currentTime=5')
    page.wait_for_timeout(150)
    assert abs(el.evaluate('(v)=>v.currentTime')-5)<.3
    report['checks'].append({'layout':name,'media':tag,'pass':True,'duration_s':before['duration'],'not_muted':not before['muted'],'playback_advanced':True,'seek_pause':True})
   audio=page.locator('audio').first;audio.scroll_into_view_if_needed();page.screenshot(path=str(out/(name+'-audio.png')))
   link=page.locator('a[href$="Sonic-Loom-Source.zip"]').first
   with page.expect_download() as pending:link.click()
   downloaded=pending.value;path=out/(name+'-source.zip');downloaded.save_as(path)
   expected=site/'docs/showcase/sonic-loom/Sonic-Loom-Source.zip'
   assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(expected.read_bytes()).digest()
   report['checks'].append({'layout':name,'download_hash_matches':True,'no_horizontal_overflow':True,'pass':True})
   context.close()
  browser.close()
 report['passed']=all(x['pass'] for x in report['checks'])
 (out/'browser-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:server.shutdown()
