#!/usr/bin/env python3
"""Export native candidates to isolated staging with the existing pinned runtime."""
import argparse,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
EDITOR_SHA='f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3'
def main():
 p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--godot',default='godot');p.add_argument('--template',type=Path,required=True);a=p.parse_args()
 editor=Path(shutil.which(a.godot) or a.godot)
 assert hashlib.sha256(editor.read_bytes()).hexdigest()==EDITOR_SHA
 assert hashlib.sha256(a.template.read_bytes()).hexdigest()=='1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9'
 project=a.native.resolve();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
 export=output/'play/signal-garden';export.mkdir(parents=True,exist_ok=True)
 preset=project/'export_presets.cfg';original_preset=preset.read_text();s=original_preset;s+='\ncustom_template/release="'+str(a.template.resolve())+'"\n';preset.write_text(s)
 env=os.environ.copy()
 template_dir=output/'data/godot/export_templates/4.6.3.stable';template_dir.mkdir(parents=True)
 env['XDG_DATA_HOME']=str(output/'data');env['XDG_CONFIG_HOME']=str(output/'config');env['XDG_CACHE_HOME']=str(output/'cache');env['HOME']=str(output/'home')
 for name in ['web_nothreads_release.zip','web_nothreads_debug.zip']:shutil.copyfile(a.template.parent/name,template_dir/name)
 def run(extra):
  r=subprocess.run([a.godot,'--headless','--path',str(project),*extra],capture_output=True,text=True,env=env,timeout=180)
  text=r.stdout+r.stderr;print(text)
  if r.returncode or 'SCRIPT ERROR' in text or 'Parse Error' in text or 'ERROR:' in text:raise RuntimeError(text)
 try:
  run(['--editor','--import','--quit']);run(['--','--logic-test']);run(['--export-release','Web',str(export/'game.html')])
 finally:preset.write_text(original_preset)
 page=(export/'game.html').read_text();cfg=json.loads(re.search(r'const GODOT_CONFIG = (\{.*?\});',page)[1]);cfg['executable']='../runtime/godot-4.6.3';cfg['ensureCrossOriginIsolationHeaders']=False;cfg['emscriptenPoolSize']=0;cfg['godotPoolSize']=0
 runtime=output/'play/runtime';runtime.mkdir()
 for source,dest in [('game.js','godot-4.6.3.js'),('game.wasm','godot-4.6.3.wasm'),('game.audio.worklet.js','godot-4.6.3.audio.worklet.js'),('game.audio.position.worklet.js','godot-4.6.3.audio.position.worklet.js')]:shutil.move(str(export/source),runtime/dest)
 cfg['fileSizes']={'../runtime/godot-4.6.3.wasm':(runtime/'godot-4.6.3.wasm').stat().st_size,'game.pck':(export/'game.pck').stat().st_size}
 game={'slug':'signal-garden','title':{'en':'Signal Garden','zh':'信号花园'},'instructions':{'en':'Rotate branches until all sixteen tiles glow. Click or tap to turn. Arrows select, Space turns, Z undoes, R resets. No time limit.','zh':'转动枝条，让十六块花圃全部亮起。点击或轻触转动，方向键选择，空格转动，Z 撤销，R 重置。没有倒计时。'},'desktopSize':[1120,780],'mobileSize':[720,1100],'export':cfg}
 html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal Garden</title><link rel="stylesheet" href="../minigame-shell.css"></head><body data-state="ready"><main><header><h1 id="title">Signal Garden</h1><a href="../../">Showcase</a></header><div class="toolbar" id="main-toolbar"><button id="start">Start</button><button id="cancel" hidden>Cancel</button><button id="exit" hidden>Exit</button><button id="fullscreen" hidden>Fullscreen</button></div><p id="status" role="status"></p><progress id="progress" hidden></progress><div id="stage" hidden><canvas id="canvas" tabindex="0" aria-label="Signal Garden game"></canvas></div><details id="alternate" hidden><summary id="alternate-label"></summary><div class="toolbar" id="controls"></div><p id="save-status" role="status"></p></details><p id="instructions"></p><p id="note"></p></main><script type="application/json" id="game-config">__CONFIG__</script><script src="../minigame-shell.js"></script></body></html>'''
 (export/'index.html').write_text(html.replace('__CONFIG__',json.dumps(game,ensure_ascii=False)))
 for name in ['minigame-shell.js','minigame-shell.css']:shutil.copyfile(ROOT/'play'/name,output/'play'/name)
 report={'engine':subprocess.check_output([a.godot,'--version'],text=True).strip(),'threads':False,'renderer':'gl_compatibility','source_files':{str(f.relative_to(project)):hashlib.sha256(f.read_bytes()).hexdigest() for f in project.iterdir() if f.is_file()},'pack_sha256':hashlib.sha256((export/'game.pck').read_bytes()).hexdigest(),'pack_bytes':(export/'game.pck').stat().st_size}
 (output/'export.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
