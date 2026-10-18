#!/usr/bin/env python3
"""Rebuild real single-threaded Godot exports; requires official matching templates."""
import argparse, hashlib, json, os, re, shutil, subprocess, tempfile, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
VERSION = '4.6.3'
TEMPLATE_SHA256 = '1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9'
EDITOR_SHA256 = 'f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3'
EDITOR_ARCHIVE_SHA256 = 'd0bc2113065e481c9c2c2b2c37daa4e8be3fe9e27f0ab9ab0b6096e9a37907f3'
CASES = [('sonic-loom', 'Sonic Loom'), ('prism-tide', 'Prism Tide')]

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--godot',default='godot')
    ap.add_argument('--template',type=Path,required=True,help='Official web_nothreads_release.zip from 4.6.3-stable export templates')
    ap.add_argument('--case',action='append',choices=[slug for slug,_ in CASES],help='Re-export only selected cases, preserving other pack bytes/provenance')
    args=ap.parse_args()
    editor=Path(shutil.which(args.godot) or args.godot).resolve()
    if digest(editor) != EDITOR_SHA256: raise SystemExit("Use the pinned official Linux x86_64 Godot 4.6.3 editor")
    if digest(args.template)!=TEMPLATE_SHA256: raise SystemExit('Release template SHA-256 mismatch')
    with tempfile.TemporaryDirectory(prefix='godot-web-') as temp:
        tmp=Path(temp);env=os.environ.copy()
        for var,d in [('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
            env[var]=str(tmp/d);(tmp/d).mkdir()
        version=subprocess.check_output([args.godot,'--version'],env=env,text=True).strip()
        if not version.startswith(VERSION+'.stable.official.'): raise SystemExit('Use official Godot '+VERSION+' stable; got '+version)
        templates=tmp/'data/godot/export_templates'/f'{VERSION}.stable';templates.mkdir(parents=True)
        shutil.copyfile(args.template,templates/'web_nothreads_release.zip')
        debug=args.template.with_name('web_nothreads_debug.zip')
        if digest(debug) != '4a8a8ef7519637f7898fad25f09d3e466965e99c04e441682e1bc2d97a548922': raise SystemExit('Debug template SHA-256 mismatch')
        shutil.copyfile(debug,templates/'web_nothreads_debug.zip')
        # Godot validates both official template paths, even for release exports.
        runtime=ROOT/'play/runtime';runtime.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(args.template) as z:
            for name in ('godot.js','godot.wasm','godot.audio.worklet.js','godot.audio.position.worklet.js'):
                (runtime/name.replace('godot.',f'godot-{VERSION}.',1)).write_bytes(z.read(name))
        selected=args.case or [slug for slug,_ in CASES]
        records=[]
        if args.case:
            records=[r for r in json.loads((ROOT/'play/export-provenance.json').read_text())['projects'] if r['case'] not in selected]
        for slug,title in CASES:
            if slug not in selected: continue
            src=ROOT/'scripts/godot_web/projects'/slug;project=tmp/slug
            shutil.copytree(src,project,ignore=shutil.ignore_patterns('.godot'))
            preset=project/'export_presets.cfg'
            preset.write_text(preset.read_text()+f'\ncustom_template/release="{args.template.resolve()}"\n')
            out=tmp/(slug+'-export');out.mkdir()
            for flags in [('--editor','--import','--quit'),('--export-release','Web',str(out/'game.html'))]:
                print(slug, flags, flush=True)
                result=subprocess.run([args.godot,'--headless','--path',str(project),*flags],env=env,capture_output=True,text=True,timeout=120)
                log=result.stdout+result.stderr
                if result.returncode or 'SCRIPT ERROR' in log or 'Parse Error' in log or 'ERROR:' in log:
                    raise SystemExit(log)
            page=(out/'game.html').read_text()
            match=re.search(r'const GODOT_CONFIG = (\{.*?\});',page)
            if not match: raise SystemExit('Export config missing from official HTML')
            config=json.loads(match.group(1))
            if config.get('threadPoolSize') not in (None,0): raise SystemExit('Threaded export rejected')
            config['executable']='../runtime/godot-'+VERSION
            config['showcasePackSha256']=digest(out/'game.pck')
            config['ensureCrossOriginIsolationHeaders']=False
            config['emscriptenPoolSize']=0
            config['godotPoolSize']=0
            config['fileSizes']={'../runtime/godot-'+VERSION+'.wasm':(runtime/f'godot-{VERSION}.wasm').stat().st_size,'game.pck':(out/'game.pck').stat().st_size}
            dest=ROOT/'play'/slug;dest.mkdir(exist_ok=True)
            shutil.copyfile(out/'game.pck',dest/'game.pck')
            shell=(ROOT/'scripts/godot_web/shell.html').read_text().replace('__SLUG__',slug).replace('__TITLE__',title).replace('__CONFIG__',json.dumps(config,separators=(',',':'))).replace('__SHELL_VERSION__',hashlib.sha256((ROOT/'play/shell.js').read_bytes()+(ROOT/'play/shell.css').read_bytes()).hexdigest()[:12])
            (dest/'index.html').write_text(shell)
            records.append({'case':slug,'source_archive':f'docs/showcase/{slug}/'+('Sonic-Loom-Source.zip' if slug=='sonic-loom' else 'Prism-Tide-Source.zip'),'source_archive_sha256':digest(ROOT/f'docs/showcase/{slug}'/('Sonic-Loom-Source.zip' if slug=='sonic-loom' else 'Prism-Tide-Source.zip')),'project_files':[{ 'path':str(f.relative_to(ROOT)), 'sha256':digest(f)} for f in sorted(src.rglob('*')) if f.is_file() and '.godot' not in f.parts]})
        (ROOT/'play/export-provenance.json').write_text(json.dumps({'engine':version,'editor_sha256':EDITOR_SHA256,'editor_archive_sha256':EDITOR_ARCHIVE_SHA256,'editor_archive_url':'https://github.com/godotengine/godot-builds/releases/download/4.6.3-stable/Godot_v4.6.3-stable_linux.x86_64.zip','template_sha256':TEMPLATE_SHA256,'official_release':'https://godotengine.org/download/archive/4.6.3-stable/','threads':False,'pwa':False,'renderer':'gl_compatibility','projects':sorted(records,key=lambda r:[slug for slug,_ in CASES].index(r['case']))},indent=2)+'\n')
    print('Exported selected native Godot projects: '+', '.join(selected))
if __name__=='__main__':main()
