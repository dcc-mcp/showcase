#!/usr/bin/env python3
"""Author the candidate through real DCC-MCP calls in a task-owned Godot editor.
No published manifest is altered. The native source and receipts are CI artifacts.
"""
import argparse, hashlib, importlib.metadata, json, os, re, shutil, socket, subprocess, time, urllib.request
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--godot',default='godot');ap.add_argument('--headless',action='store_true');args=ap.parse_args()
 out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);recipe=Path(__file__).resolve().parent
 for k,v in [('HOME','home'),('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
  d=out/'session'/v;d.mkdir(parents=True,exist_ok=True);os.environ[k]=str(d)
 with socket.socket() as s:s.bind(('127.0.0.1',0));bridge_port=s.getsockname()[1]
 os.environ['DCC_MCP_GODOT_BRIDGE_PORT']=str(bridge_port);os.environ['DCC_MCP_GODOT_BRIDGE_URL']=f'ws://127.0.0.1:{bridge_port}'
 os.environ['DCC_MCP_REGISTRY_DIR']=str(out/'session/registry');os.environ['DCC_MCP_CLI_NO_AUTO_GATEWAY']='true'
 import dcc_mcp_godot
 from dcc_mcp_godot.server import GodotMcpServer
 from dcc_mcp_godot.bridge import get_bridge
 project=out/'authoring-project';project.mkdir(exist_ok=True)
 shutil.copytree(Path(dcc_mcp_godot.__file__).parent/'godot_addon/addons',project/'addons',dirs_exist_ok=True)
 shutil.copyfile(recipe/'garden-font.otf',project/'garden-font.otf')
 (project/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Signal Garden"\n[editor_plugins]\nenabled=PackedStringArray("res://addons/dcc_mcp_godot/plugin.cfg")\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
 server=GodotMcpServer(port=0,gateway_port=0,registry_dir=str(out/'session/registry'),enable_gateway_failover=False,enable_telemetry=False,enable_checkpoint_persistence=False)
 server.register_builtin_actions();server.start();receipts=[];seq=0
 log=open(out/'editor.log','w');editor=None
 def launch():
  return subprocess.Popen([args.godot,*(['--headless'] if args.headless else []),'--editor','--audio-driver','Dummy','--path',str(project),'--rendering-method','gl_compatibility'],stdout=log,stderr=log)
 def wait_ready():
  for _ in range(300):
   if editor.poll() is not None:raise RuntimeError('Godot editor exited; inspect editor.log')
   if get_bridge().is_connected():time.sleep(1);return
   time.sleep(.1)
  raise TimeoutError('Godot plugin did not connect')
 def rpc(method,params):
  nonlocal seq
  seq+=1;request={'jsonrpc':'2.0','id':seq,'method':method,'params':params}
  req=urllib.request.Request(server.mcp_url,data=json.dumps(request).encode(),headers={'Content-Type':'application/json','Accept':'application/json,text/event-stream'})
  with urllib.request.urlopen(req,timeout=60) as r:text=r.read().decode()
  if text.startswith('event:') or text.startswith('data:'):text='\n'.join(l[6:] for l in text.splitlines() if l.startswith('data: '))
  result=json.loads(text);receipts.append({'sequence':seq,'method':method,'params':params,'response':result})
  (out/'mcp-raw.json').write_text(json.dumps(receipts,indent=2))
  if 'error' in result or result.get('result',{}).get('isError'):raise RuntimeError(str(result))
  return result.get('result',{})
 schemas={}
 def inventory():
  cursor=None
  for _ in range(20):
   page=rpc('tools/list',{'cursor':cursor} if cursor else {})
   schemas.update({t['name']:t for t in page['tools']});cursor=page.get('nextCursor')
   if not cursor:return
  raise RuntimeError('Unbounded tool inventory')
 def envelope(r):
  if isinstance(r.get('structuredContent'),dict):return r['structuredContent']
  for block in r.get('content',[]):
   if block.get('type')=='text':
    try:return json.loads(block['text'])
    except json.JSONDecodeError:pass
  return {}
 def call(name,arguments):
  if name not in schemas:
   matches=[n for n in schemas if n==name.split('__')[-1] or n.endswith('__'+name) or n.endswith('__'+name.split('__')[-1])]
   if len(matches)!=1:raise RuntimeError('Undiscovered or ambiguous tool: '+name+' '+str(matches))
   name=matches[0]
  r=rpc('tools/call',{'name':name,'arguments':arguments});body=envelope(r)
  if isinstance(body,dict) and body.get('job_id'):
   for _ in range(600):
    r=rpc('tools/call',{'name':'jobs_get_status','arguments':{'job_id':body['job_id'],'include_result':True}})
    status=envelope(r)
    if status.get('status')=='completed':body=status.get('result',{});break
    if status.get('status') in ['failed','cancelled','interrupted']:raise RuntimeError(status)
    time.sleep(.1)
   else:raise TimeoutError('MCP job timeout')
  if isinstance(body,dict):
   if body.get('success') is False or body.get('valid') is False or body.get('context',{}).get('valid') is False:raise RuntimeError(body)
  return r

 try:
  editor=launch();wait_ready()
  inventory()
  if 'search_skills' in schemas:call('search_skills',{'query':'Godot scene script project'})
  call('load_skill',{'skill_names':['godot-project-management','godot-scene-management','godot-script']})
  inventory()
  call('godot_project_management__get_project_info',{})
  call('godot_script__create_script',{'path':'res://game.gd','source':(recipe/'signal-garden.gd').read_text(),'overwrite':True})
  call('godot_script__validate_script',{'path':'res://game.gd'})
  call('godot_scene_management__create_scene',{'path':'res://main.tscn','root_type':'Node2D','root_name':'SignalGarden','open':True})
  call('godot_script__attach_script',{'node_path':'.','script_path':'res://game.gd'})
  call('godot_scene_management__save_scene',{'path':'res://main.tscn'})
  for k,v in {'application/run/main_scene':'res://main.tscn','display/window/size/viewport_width':1120,'display/window/size/viewport_height':780,'display/window/stretch/mode':'canvas_items','input_devices/pointing/emulate_mouse_from_touch':True}.items():call('godot_project_management__set_project_setting',{'key':k,'value':v})
  # Close the actual editor, start a fresh process, reopen the saved scene, inspect it.
  editor.terminate();editor.wait(timeout=20);time.sleep(1);editor=launch();wait_ready()
  call('godot_scene_management__open_scene',{'path':'res://main.tscn'})
  call('godot_scene_management__get_scene_tree',{'path':'res://main.tscn'})
  call('load_skill',{'skill_names':['godot-input','godot-runtime','godot-editor']});inventory()
  def context(r):
   b=envelope(r)
   if b.get('status')=='completed':b=b.get('result',{})
   return b.get('context',b)
  call('godot_scene_management__play_scene',{'mode':'main'})
  for _ in range(120):
   if context(call('godot_runtime__get_runtime_status',{})).get('connected'):break
   time.sleep(.25)
  else:raise TimeoutError('Native game did not attach')
  def props():return context(call('godot_runtime__get_game_node_properties',{'node_path':'.','properties':['turns','paused','won','masks']}))['properties']
  def key(code):
   call('godot_input__simulate_key',{'keycode':code,'pressed':True});call('godot_input__simulate_key',{'keycode':code,'pressed':False});time.sleep(.1)
  assert props()['turns']==0
  key(32);assert props()['turns']==1
  key(90);assert props()['turns']==0
  call('godot_input__simulate_mouse_click',{'position':[389,229],'button':1,'pressed':True})
  call('godot_input__simulate_mouse_click',{'position':[389,229],'button':1,'pressed':False});time.sleep(.1)
  assert props()['turns']==1
  key(80);assert props()['paused'] is True
  key(32);assert props()['turns']==1
  key(80);key(82);assert props()['turns']==0 and props()['paused'] is False
  call('godot_editor__get_game_screenshot',{'path':'res://native-game.png'})
  shutil.copyfile(project/'native-game.png',out/'native-game.png')
  (out/'native-input.json').write_text(json.dumps({'route':'real native InputEvent key/mouse through DCC-MCP game peer','checks':['Space rotates','Z undoes','Mouse rotates','Pause ignores board input','Resume and R reset'],'passed':True},indent=2))
  call('godot_scene_management__stop_scene',{})
  dest=out/'native/signal-garden';dest.mkdir(parents=True)
  for name in ['game.gd','main.tscn','garden-font.otf']:shutil.copyfile(project/name,dest/name)
  shutil.copyfile(recipe/'FONT-LICENSE.txt',dest/'FONT-LICENSE.txt')
  cfg=(project/'project.godot').read_text()
  for section in ['autoload','editor_plugins']:cfg=re.sub(r'\n\['+section+r'\].*?(?=\n\[|\Z)','',cfg,flags=re.S)
  (dest/'project.godot').write_text(cfg)
  shutil.copyfile(recipe.parent/'projects/prism-tide/export_presets.cfg',dest/'export_presets.cfg')
  report={'date':time.strftime('%Y-%m-%d',time.gmtime()),'route':'direct MCP HTTP to task-owned Godot adapter; typed tools','editor_mode':'headless' if args.headless else 'real window under CI Xvfb','godot':subprocess.check_output([args.godot,'--version'],text=True).strip(),'adapter':importlib.metadata.version('dcc-mcp-godot'),'core':importlib.metadata.version('dcc-mcp-core'),'editor_restarted':True,'native_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir()},'tool_calls':[{'name':r['params']['name'],'arguments':{k:hashlib.sha256(v.encode()).hexdigest() if k=='source' else v for k,v in r['params']['arguments'].items()},'returned_without_error':True} for r in receipts if r['method']=='tools/call']}
  (out/'authoring.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
 finally:
  if editor is not None and editor.poll() is None:editor.terminate();editor.wait(timeout=20)
  server.stop();log.close()
if __name__=='__main__':main()
