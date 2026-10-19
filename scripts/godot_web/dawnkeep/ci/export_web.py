#!/usr/bin/env python3
"""Official hash-pinned single-thread Godot Web export, retaining its engine shell."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from common import WEB_TEMPLATE_SHA256, WEB_DEBUG_SHA256, checked_godot, check_engine_log, copy_game, isolated_env, isolated_output, sha256, write_json


def patch_shell(page):
    match=re.search(r'const GODOT_CONFIG = (\{.*?\});',page)
    if not match:raise RuntimeError('Official Godot Web configuration marker changed')
    config=json.loads(match[1]);config['ensureCrossOriginIsolationHeaders']=False;config['emscriptenPoolSize']=0;config['godotPoolSize']=0
    # Documented policy 0 lets the shell size the canvas below its own toolbar.
    config['canvasResizePolicy']=0
    if config.get('extensionLibs'):raise RuntimeError('Unexpected Web extension libraries')
    page=page[:match.start(1)]+json.dumps(config)+page[match.end(1):]
    marker='const engine = new Engine(GODOT_CONFIG);'
    if page.count(marker)!=1:raise RuntimeError('Official engine marker changed')
    page=page.replace(marker,'const dawnkeepShell = window.DawnkeepShell.attach(GODOT_CONFIG, () => engine.requestQuit());\n'+marker)
    marker='<script src="index.js"></script>'
    if page.count(marker)!=1:raise RuntimeError('Official engine script marker changed')
    page=page.replace(marker,marker+'\n<script src="dawnkeep-shell.js"></script>')
    marker='function displayFailureNotice(err) {'
    if page.count(marker)!=1:raise RuntimeError('Official loading failure marker changed')
    page=page.replace(marker,marker+'\n dawnkeepShell.failed(err);')
    return page,config


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('native','output','template','license-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--godot',default='godot');args=p.parse_args()
    out=isolated_output(args.output,args.native);godot=checked_godot(args.godot)
    report={'schema':1,'passed':False,'template_sha256':WEB_TEMPLATE_SHA256,'thread_support':False}
    try:
        if sha256(args.template)!=WEB_TEMPLATE_SHA256:raise ValueError('Official Web template hash mismatch')
        project=out/'export-project';manifest=copy_game(args.native,project);write_json(out/'source-manifest.json',manifest)
        site=out/'site';site.mkdir();env=isolated_env(out/'session')
        templates=Path(env['XDG_DATA_HOME'])/'godot/export_templates/4.6.3.stable';templates.mkdir(parents=True)
        shutil.copyfile(args.template,templates/'web_nothreads_release.zip')
        debug=args.template.parent/'web_nothreads_debug.zip'
        if debug.exists():
            if sha256(debug)!=WEB_DEBUG_SHA256:raise ValueError('Official debug template hash mismatch')
            shutil.copyfile(debug,templates/debug.name)
        raw=[e['path'] for e in manifest['files'] if Path(e['path']).suffix in ('.bin','.otf','.ttf','.json','.txt')]
        preset='''[preset.0]
name="Web"
platform="Web"
runnable=true
export_filter="all_resources"
include_filter=__RAW__
exclude_filter="verify_*.gd,tests/*"
export_path=""
script_export_mode=2
[preset.0.options]
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
progressive_web_app/enabled=false
'''.replace('__RAW__',json.dumps(','.join(raw)))
        preset+='custom_template/release='+json.dumps(str(args.template.resolve()))+'\n'
        (project/'export_presets.cfg').write_text(preset)
        for name,extra in (('import',['--editor','--import','--quit']),('export',['--export-release','Web',str(site/'index.html')])):
            result=subprocess.run([godot,'--headless','--path',str(project),*extra],env=env,capture_output=True,text=True,timeout=240)
            log=result.stdout+result.stderr;(out/(name+'.log')).write_text(log);check_engine_log(log)
            if result.returncode:raise RuntimeError('Official Godot '+name+' returned '+str(result.returncode))
        page,config=patch_shell((site/'index.html').read_text());(site/'index.html').write_text(page)
        shutil.copyfile(Path(__file__).with_name('web_shell.js'),site/'dawnkeep-shell.js')
        for name in ('LICENSE.txt','COPYRIGHT.txt'):shutil.copyfile(args.license_dir/name,site/name)
        for entry in manifest['files']:
            name=entry['path'];base=Path(name).name.lower()
            if 'license' in base or base.endswith('source.json'):
                target=site/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(args.native/name,target)
        for name in ('index.html','index.js','index.wasm','index.pck'):
            if not (site/name).is_file() or (site/name).stat().st_size==0:raise RuntimeError('Missing official export artifact: '+name)
        (site/'README.txt').write_text('Dawnkeep: unpublished original Godot 3D hero-defense candidate.\nServe this complete directory over HTTP.\nWASD/arrows move. Q/E/R abilities. Space starts a wave. L language. M music. Escape pause.\nUse the visible restart control to reset. The shell Quit button exits the actual engine; Open again reloads it.\nThis export is not a deployment or a physical-phone compatibility claim.\nGodot notices are LICENSE.txt and COPYRIGHT.txt. Asset notices retain their original paths.\n')
        report.update({'passed':True,'web_config':config,'include_filter':raw,
                       'files':{f.relative_to(site).as_posix():{'sha256':sha256(f),'bytes':f.stat().st_size} for f in site.rglob('*') if f.is_file()}})
    except Exception as error:report['blocker']=str(error);raise
    finally:write_json(out/'export.json',report)


if __name__=='__main__':main()
