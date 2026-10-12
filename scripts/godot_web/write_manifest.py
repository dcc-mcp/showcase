#!/usr/bin/env python3
"""Hash an explicit publication allowlist; unlisted scratch files never publish."""
import hashlib,json,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FILES=['play/verification-portrait.json', 'play/evidence/portrait-sonic-loom-desktop-edited.png', 'play/evidence/portrait-prism-tide-desktop-solved.png', 'play/evidence/portrait-sonic-loom-portrait-canvas.png', 'play/evidence/portrait-prism-tide-portrait-canvas.png', 'play/evidence/portrait-prism-tide-portrait-level3.png', 'play/evidence/portrait-sonic-loom-en-phone-embedded-viewport.png', 'play/evidence/portrait-sonic-loom-zh-phone-embedded-viewport.png', 'play/evidence/portrait-prism-tide-en-phone-embedded-viewport.png', 'play/evidence/portrait-prism-tide-zh-phone-embedded-viewport.png', 'play/evidence/portrait-prism-tide-touch-board-viewport.png', 'play/evidence/portrait-prism-tide-touch-controls-viewport.png']+['play/shell.css','play/shell.js','play/export-provenance.json','play/README.md','play/LICENSES.md','play/verification.json','play/evidence/sonic-loom-desktop-edited.png','play/evidence/sonic-loom-touch-edited.png','play/evidence/prism-tide-desktop-solved.png','play/evidence/prism-tide-touch-solved.png','play/evidence/loading-error.png',
       'play/runtime/LICENSE.txt','play/runtime/COPYRIGHT.txt','play/runtime/godot-4.6.3.js','play/runtime/godot-4.6.3.wasm','play/runtime/godot-4.6.3.audio.worklet.js','play/runtime/godot-4.6.3.audio.position.worklet.js',
       'play/sonic-loom/index.html','play/sonic-loom/game.pck','play/prism-tide/index.html','play/prism-tide/game.pck']
controls={
 'sonic-loom':{'en':'Tap steps to edit. On phones, select a voice, then use Mute for that voice. Space: play/pause; arrows: tempo; S/L/R: save/load/reset. Native portrait controls scroll vertically.','zh':'轻触步进编辑；手机先选择声部，再用 Mute 切换该声部静音。空格播放/暂停，上下键调速，S/L/R 保存、读取、重置。原生竖屏控件可上下滚动。'},
 'prism-tide':{'en':'On phones, tap a mirror or shutter to select it, then use Turn/Toggle below the scrolling board. Tab: select; Space/Enter: turn; R: reset; N: next after winning.','zh':'手机先轻触镜子或闸门选中，再使用滚动棋盘下方的 Turn/Toggle 操作。Tab 选择，空格或回车转动，R 重置，过关后 N 下一关。'}}
notes={
 'sonic-loom':{'en':'Audio starts after a click or tap. Saves stay in this browser. The native instrument artwork remains in English. Web adaptation/review, 2026-10-12: requested and accepted configuration gpt-6-astra / ultra; backend routing was not independently verified. Review covers desktop/phone screenshots and 40 browser checks. No subjective listening, physical-phone, Safari or Firefox acceptance.','zh':'点击或轻触后启用声音，存档保留在当前浏览器，原生乐器画面保留英文。2026-10-12 Web 适配与复审请求并接受的配置为 gpt-6-astra / ultra；未独立核验后台路由。复审覆盖桌面与手机截图及40项浏览器检查，未作主观听评、实体手机、Safari 或 Firefox 验收。'},
 'prism-tide':{'en':'The original puzzle is silent. Explicit Save/Load stores a local checkpoint in this browser. Native puzzle artwork remains in English. Web adaptation/review, 2026-10-12: requested and accepted configuration gpt-6-astra / ultra; backend routing was not independently verified. Review covers desktop/phone screenshots and 40 browser checks. No subjective listening, physical-phone, Safari or Firefox acceptance.','zh':'原作没有音轨。保存与读取按钮用于当前浏览器的本地关卡存档，原生谜题画面保留英文。2026-10-12 Web 适配与复审请求并接受的配置为 gpt-6-astra / ultra；未独立核验后台路由。复审覆盖桌面与手机截图及40项浏览器检查，未作主观听评、实体手机、Safari 或 Firefox 验收。'}}
items=[]
for rel in FILES:
 data=(ROOT/rel).read_bytes();items.append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
demos=[{'case_slug':s,'url':f'play/{s}/index.html','title':title,'engine':'Godot 4.6.3','renderer':'gl_compatibility','threads':False,'localeSupport':['en','zh'],'nativeTextLanguage':'en','controls':controls[s],'notes':notes[s]} for s,title in [('sonic-loom','Sonic Loom'),('prism-tide','Prism Tide')]]
raw=sum(x['bytes'] for x in items)
gz=sum(len(gzip.compress((ROOT/x['path']).read_bytes(),compresslevel=9,mtime=0)) for x in items)
assert raw<=40*1024*1024 and gz<=11*1024*1024,(raw,gz)
manifest={'schema_version':1,'files':items,'demos':demos,'budget':{'raw_bytes':raw,'gzip_equivalent_bytes':gz,'raw_limit_bytes':40*1024*1024,'gzip_equivalent_limit_bytes':11*1024*1024,'note':'Gzip equivalent is measured locally; actual Pages Content-Encoding must be verified after an authorized deployment.'}}
(ROOT/'play/manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(manifest['budget']))
