#!/usr/bin/env python3
"""Promote the verified 957c1d3 Web bytes; no engine export or game mutation."""
import argparse,hashlib,json,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/godot_web'))
from resource_budget import ADDITIONAL,LEGACY_RAW,LEGACY_GZIP,measure,validate
HEAD='957c1d3928d4d7382535a5b50ae2990aa4cf5854'
RUN='https://github.com/dcc-mcp/showcase/actions/runs/39285690349'
PCK='649ccf7ed6a762fb00315c07fe6253d35a626fe907f0cb23a238537bb0c3b29b'
SLUG='dawnkeep-defense'
PACK='dawnkeep-'+PCK[:12]+'.pck'
ENGINE={'index.js':'godot-4.6.3.js','index.wasm':'godot-4.6.3.wasm','index.audio.worklet.js':'godot-4.6.3.audio.worklet.js','index.audio.position.worklet.js':'godot-4.6.3.audio.position.worklet.js'}
def sha(data):return hashlib.sha256(data).hexdigest()
def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def public_html(text,pack_sha=PCK):
    match=re.search(r'const GODOT_CONFIG = (\{.*?\});',text)
    if not match:raise ValueError('Missing official export configuration')
    config=json.loads(match[1])
    if config['ensureCrossOriginIsolationHeaders'] or config['emscriptenPoolSize'] or config['godotPoolSize']:raise ValueError('Expected single-thread export')
    config['executable']='../runtime/godot-4.6.3';config['mainPack']=PACK
    config['fileSizes']={'../runtime/godot-4.6.3.wasm':config['fileSizes']['index.wasm'],PACK:config['fileSizes']['index.pck']}
    config['showcasePackSha256']=pack_sha
    text=text[:match.start(1)]+json.dumps(config)+text[match.end(1):]
    bridge_sha=sha((Path(__file__).parent/'ci/publication_shell.js').read_bytes())[:12]
    shell_sha=sha((Path(__file__).parent/'ci/web_shell.js').read_bytes())[:12]
    replacements={
      '<script src="index.js"></script>':'<script src="../runtime/godot-4.6.3.js"></script>\n<script src="publication-shell.js?v='+bridge_sha+'"></script>',
      '<script src="dawnkeep-shell.js"></script>':'<script src="dawnkeep-shell.js?v='+shell_sha+'"></script>',
      'const dawnkeepShell = window.DawnkeepShell.attach':'const dawnkeepPublication = window.DawnkeepPublication.attach(GODOT_CONFIG);\nconst dawnkeepShell = window.DawnkeepShell.attach',
      ' dawnkeepShell.failed(err);':' dawnkeepPublication.failed();\n dawnkeepShell.failed(err);',
    }
    for old,new in replacements.items():
        if text.count(old)!=1:raise ValueError('Official shell marker changed: '+old)
        text=text.replace(old,new)
    return text,config

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);a=p.parse_args()
    candidate=a.candidate.resolve();site=candidate/'dawnkeep-web/site'
    for rel in ('dawnkeep-author/authoring.json','dawnkeep-native-full/native.json','dawnkeep-browser/browser.json'):
        if json.loads((candidate/rel).read_text()).get('passed') is not True:raise ValueError('Missing passed acceptance: '+rel)
    source_manifest=json.loads((candidate/'dawnkeep-author/source-manifest.json').read_text())
    for record in source_manifest['files']:
        path='scripts/godot_web/dawnkeep/game/'+record['path']
        for revision in (HEAD,'HEAD'):
            data=subprocess.check_output(['git','show',revision+':'+path],cwd=ROOT)
            if sha(data)!=record['sha256'] or len(data)!=record['bytes']:
                raise ValueError('Frozen/current game source differs: '+path)
    export=json.loads((candidate/'dawnkeep-web/export.json').read_text())
    if export.get('passed') is not True or sha((site/'index.pck').read_bytes())!=PCK:raise ValueError('Wrong verified pack')
    manifest=json.loads((ROOT/'play/manifest.json').read_text());existing={x['path']:x for x in manifest['files']}
    for name,record in export['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Unsafe export path')
        data=(site/name).read_bytes()
        if len(data)!=record['bytes'] or sha(data)!=record['sha256']:raise ValueError('Export changed: '+name)
    dest=ROOT/'play'/SLUG;dest.mkdir(parents=True,exist_ok=True)
    public=[]
    def put(name,data):
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);public.append(target)
    for name,record in export['files'].items():
        if name in ENGINE:
            shared='play/runtime/'+ENGINE[name];expected=existing[shared]
            if expected['sha256']!=record['sha256'] or expected['bytes']!=record['bytes']:raise ValueError('Shared engine differs: '+name)
            # Official bytes are not committed again. Materialize locally only
            # if absent so the normal site validator can check the whole tree.
            target=ROOT/shared
            if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(site/name,target)
            if sha(target.read_bytes())!=record['sha256']:raise ValueError('Local engine differs')
        elif name not in ('index.html','README.txt','dawnkeep-shell.js'):
            put(PACK if name=='index.pck' else name,(site/name).read_bytes())
    page,config=public_html((site/'index.html').read_text());put('index.html',page.encode())
    put('publication-shell.js',(Path(__file__).parent/'ci/publication_shell.js').read_bytes())
    put('dawnkeep-shell.js',(Path(__file__).parent/'ci/web_shell.js').read_bytes())
    put('README.txt',('Dawnkeep / 曙光守誓\nOfficial Godot 4.6.3 single-thread Web export. Requires WebGL 2.\n'+
        'WASD/arrows move; Q/E/R skills; Space next wave; L language; M music; Escape pause.\n'+
        'The initial native screen is Chinese. Use EN or L for English. Native Reset starts a fresh run; outer Reset reloads the engine.\n'+
        '初始原生界面为中文，EN 或 L 切换语言。WASD/方向键移动，Q/E/R 技能，空格迎战，M 音乐，Esc 暂停。\n'+
        'This game has no saved progress. Portrait evidence is emulated touch, not physical-phone acceptance.\n'+
        'Godot and asset/music/font notices retain their original paths. See the case page for source, provenance and limitations.\n').encode())
    provenance={'schema_version':1,'source_commit':HEAD,'full_acceptance_run':RUN,'engine':'Godot 4.6.3','threads':False,'renderer':'gl_compatibility','native_pck_sha256':PCK,'pack_name':PACK,
        'source_export_html_sha256':export['files']['index.html']['sha256'],'source_shell_sha256':export['files']['dawnkeep-shell.js']['sha256'],
        'template_sha256':export['template_sha256'],'game_source_manifest':json.loads((candidate/'dawnkeep-author/source-manifest.json').read_text()),
        'promotion':['PCK and native gameplay bytes unchanged from passed full acceptance.','Official runtime files reused byte for byte from existing same-origin shared engine.','Official HTML references relocated to shared engine and immutable hash-named PCK.','Small same-origin parent-page readiness/error/reset bridge added; reset reloads the real engine rather than injecting state.','Lifecycle shell now initializes pre-engine loading/retry labels from the page lang query, falling back to document language then English. Real native language receipts remain authoritative once running.','Native EN/ZH controls retained; initial native language remains Chinese.'],
        'native_controls':'L or EN/中文 switches language; native music button or M controls sound.','not_claimed':['Physical-phone/multitouch acceptance','Subjective music listening','Physical-GPU performance','Manual native OS-window-close acceptance'],
        'published_files':[{ 'path':str(x.relative_to(dest)),'bytes':x.stat().st_size,'sha256':sha(x.read_bytes())} for x in sorted(public)]}
    put('export-provenance.json',(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n').encode())
    # Replace only this case's allowlisted assets; other games remain unchanged.
    manifest['files']=[x for x in manifest['files'] if not x['path'].startswith('play/'+SLUG+'/')]
    manifest['files'] += [{'path':str(x.relative_to(ROOT)),'bytes':x.stat().st_size,'sha256':sha(x.read_bytes())} for x in sorted(public)]
    manifest['demos']=[x for x in manifest['demos'] if x['case_slug']!=SLUG]
    manifest['demos'].append({'case_slug':SLUG,'url':'play/'+SLUG+'/index.html','title':'Dawnkeep / 曙光守誓','engine':'Godot 4.6.3','renderer':'gl_compatibility','threads':False,'localeSupport':['en','zh'],'nativeTextLanguage':'en-zh',
      'controls':{'en':'WASD/arrows move, Q/E/R skills, Space next wave, Escape pause. Use the native equipment and defense buttons. The initial screen is Chinese: press L or EN for English. On phones use the visible touch controls.','zh':'WASD/方向键移动，Q/E/R 技能，空格迎战，Esc 暂停；点击原生装备与防御按钮。L 或 EN/中文切换语言，手机使用画面中的触控按钮。'},
      'notes':{'en':'Eight-wave hero defense. Click/tap the game to unlock audio; M or the native music button mutes it. No saved progress. Outer Reset reloads the real engine. Native and Web victory/defeat/reset passed on the recorded source; physical phones, subjective listening and physical-GPU performance remain unverified.','zh':'八波英雄守卫战。点击/轻触游戏后启用声音，M 或原生音乐按钮静音。没有存档，外层重开将重新加载真实引擎。记录版本的原生与 Web 胜败及重开通过；实体手机、主观听评和真实显卡性能仍未验证。'}})
    # Inventory measurements exclude this self-describing manifest; the export
    # verifier also includes the document itself when enforcing legacy limits.
    groups=validate(measure(ROOT,[x['path'] for x in manifest['files']]))
    manifest['budget']={'raw_bytes':sum(x[0] for x in groups.values()),'gzip_equivalent_bytes':sum(x[1] for x in groups.values()),
      'raw_limit_bytes':LEGACY_RAW+sum(x[0] for x in ADDITIONAL.values()),'gzip_equivalent_limit_bytes':LEGACY_GZIP+sum(x[1] for x in ADDITIONAL.values()),
      'groups':{k:{'raw_bytes':v[0],'gzip_equivalent_bytes':v[1]} for k,v in groups.items()},
      'measurement_scope':'Manifest-listed assets, excluding this manifest document. The verification ceiling additionally includes the manifest.',
      'note':'Original shared-runtime/demo envelope remains 40 MiB raw/11 MiB gzip. Dawnkeep adds a separate 6 MiB raw/5 MiB gzip allowance; actual Pages encoding is checked after deployment.'}
    write_json(ROOT/'play/manifest.json',manifest)
    print(json.dumps(manifest['budget'],indent=2))
if __name__=='__main__':main()
