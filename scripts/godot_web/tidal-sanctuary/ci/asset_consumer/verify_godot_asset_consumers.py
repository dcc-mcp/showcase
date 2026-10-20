"""Owned real Godot/MCP visual fixture. No full game, no bare-CLI scene generation."""
import os,sys,json,time,hashlib,shutil,socket,subprocess,urllib.request,importlib.metadata,math
import numpy as np
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--godot',required=True)
parser.add_argument('--xvfb',default='Xvfb')
args=parser.parse_args()
ROOT=Path(__file__).parent.resolve();OUT=args.output.resolve();assert not OUT.exists()
CI=ROOT.parent
INPUT_SHA256={'../common.py': 'cb0dadf8545123c8475401ef4c9dfc220530c397e1f5ae2595f95f30a32b775f', '../author_native.py': '998d174d8a61611217e03a41110a16ede323c7194f438fbbca1d07690e58bf2f', 'baseline-assets/explorer.glb': 'eae7218d3ca960b10710216a2cda6c9ddd7eab088ee98854381099f5cabd36b3', 'baseline-assets/palm-a.glb': 'fb11d7daafed2c56bd3d973b8cec0041aa0cfed76b3a3328f796f283d293a3cb', 'baseline-assets/palm-b.glb': 'e0b9795379607da157b033c49249b22208cd01dcdbba64ef1e8cdf3ca0b97f62', 'baseline-assets/understory-a.glb': '455305525f0f8bf2bc1c0d7864c23f01fbb48dd1ab5839e819ade540cea14141', 'baseline-assets/understory-b.glb': '08c917d52a3583ffd73d671619ee0398f439deebe4a39d2205f9eb68eddd624d', 'candidate-assets/explorer.glb': '055acf10abbfd9e8c57c4144c4bbdb2fae9676d0bb0b09a18342a77c142b17a8', 'candidate-assets/palm-a.glb': 'a3624b45b4a54a1887421147e3087a7abcfb2a564a5d0e158e13a91b88521916', 'candidate-assets/palm-b.glb': '07dfcff46724f50bed2e130a0d4aaa1fef8d82850ffbe461bc80d6a6a1c8c27c', 'candidate-assets/understory-a.glb': '65241bd4f33a5feb5426adce71fcf87fb94cc39ce41262fc0ef2d8369b0694dc', 'candidate-assets/understory-b.glb': 'f45c204d837bee5a0ad8b3cd6b885f43defb7fb558d7472c82ea4442b149622a'}
for path,digest in INPUT_SHA256.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
sys.path.insert(0,str(CI));from common import checked_godot,isolated_env,stop_process,check_engine_log
from author_native import envelope,EDITOR_PROBE_SOURCE,editor_idle_sample
SCRIPT_SHA='d971acd7a472b623241b0a7c516121dadb1482bebd9a1422df47ecd73807282c'
assert hashlib.sha256((ROOT/'godot_asset_consumer.gd').read_bytes()).hexdigest()==SCRIPT_SHA
for pkg,version in [('dcc-mcp-godot','0.9.6'),('dcc-mcp-core','0.20.42')]:assert importlib.metadata.version(pkg)==version
mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))/1024
assert mem>=2800 and shutil.disk_usage(OUT.parent).free>1000*2**20 and shutil.disk_usage('/tmp').free>600*2**20
OUT.mkdir();os.environ.update(isolated_env(OUT/'session'))
# No security or renderer overrides beyond the established project software-GL path.
with socket.socket() as s:s.bind(('127.0.0.1',0));bridge_port=s.getsockname()[1]
os.environ.update(DCC_MCP_GODOT_BRIDGE_PORT=str(bridge_port),DCC_MCP_GODOT_BRIDGE_URL=f'ws://127.0.0.1:{bridge_port}',DCC_MCP_REGISTRY_DIR=str(OUT/'session/registry'),DCC_MCP_CLI_NO_AUTO_GATEWAY='true')
import dcc_mcp_godot
from dcc_mcp_godot.bridge import get_bridge
from dcc_mcp_godot.server import GodotMcpServer
from PIL import Image
project=OUT/'project';project.mkdir();(project/'previews').mkdir()
shutil.copytree(Path(dcc_mcp_godot.__file__).parent/'godot_addon/addons',project/'addons')
(project/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Tidal actual asset consumer"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n[editor_plugins]\nenabled=PackedStringArray("res://addons/dcc_mcp_godot/plugin.cfg")\n')
# Read-only scan helper, not an authored production asset.
(project/'scan_probe.gd').write_text(EDITOR_PROBE_SOURCE)
old=ROOT/'baseline-assets';names=['explorer','palm-a','palm-b','understory-a','understory-b']
manifest={}
for variant,base in [('old',old),('new',ROOT/'candidate-assets')]:
    dest=project/'assets'/variant;dest.mkdir(parents=True)
    for name in names:
        src=base/(name+'.glb');shutil.copyfile(src,dest/src.name);manifest[f'{variant}/{name}']=hashlib.sha256(src.read_bytes()).hexdigest()
(OUT/'inputs.json').write_text(json.dumps({'assets':manifest,'input_pins':INPUT_SHA256,'script':SCRIPT_SHA,'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'adapter':'0.9.6','core':'0.20.42','server_package':importlib.metadata.version('dcc-mcp-server'),'resources':{'mem_available_mib':mem}},indent=2))
receipts=[];schemas={};server=None;editor=None;xvfb=None
log=(OUT/'editor.log').open('w');xlog=(OUT/'xvfb.log').open('w')
def rpc(method,params):
    request={'jsonrpc':'2.0','id':len(receipts)+1,'method':method,'params':params}
    req=urllib.request.Request(server.mcp_url,data=json.dumps(request).encode(),headers={'Content-Type':'application/json','Accept':'application/json,text/event-stream'})
    with urllib.request.urlopen(req,timeout=120) as response:raw=response.read().decode()
    if raw.startswith(('event:','data:')):result=json.loads([line[6:] for line in raw.splitlines() if line.startswith('data: ')][-1])
    else:result=json.loads(raw)
    receipts.append({'request':request,'response':result});(OUT/'mcp-raw.json').write_text(json.dumps(receipts,indent=2))
    assert 'error' not in result and not result.get('result',{}).get('isError'),result
    return result.get('result',{})
def inventory():
    cursor=None
    for _ in range(30):
        page=rpc('tools/list',{'cursor':cursor} if cursor else {});schemas.update({t['name']:t for t in page['tools']});cursor=page.get('nextCursor')
        if not cursor:return
    raise RuntimeError('Unterminated tool inventory')
def call(name,args):
    found=[n for n in schemas if n==name or n.endswith('__'+name)];assert len(found)==1,(name,found)
    body=envelope(rpc('tools/call',{'name':found[0],'arguments':args}))
    assert not body.get('job_id'),'Unexpected async job: preserve receipt, do not replay'
    assert body.get('success') is not False and body.get('valid') is not False,body
    context=body.get('context',body);assert context.get('valid') is not False,body
    return context

def execute(method,args):
    result=call('execute_editor_script',{'path':'res://asset_consumer.gd','method':method,'arguments':args,'budget_ms':50,'chunked':False})
    assert result['executed'] is True and isinstance(result['result'],dict),result
    value=result['result'];assert 'error' not in value,value
    return value

def finite(value):
    if isinstance(value,float):assert math.isfinite(value)
    elif isinstance(value,dict):
        for v in value.values():finite(v)
    elif isinstance(value,list):
        for v in value:finite(v)
def wait_import_idle(boundary,types):
    deadline=time.monotonic()+90;previous=None
    while True:
        sample,idle=editor_idle_sample(call('execute_editor_script',{'path':'res://scan_probe.gd','method':'inspect','arguments':{'paths':list(types)},'budget_ms':50,'chunked':False}),types)
        if idle and previous is not None and sample['process_frame']>=previous['process_frame']+2:
            (OUT/(boundary+'-import-idle.json')).write_text(json.dumps({'expected_types':types,'samples':[previous,sample]},indent=2))
            return
        if not idle:previous=None
        elif previous is None:previous=sample
        assert editor.poll() is None and time.monotonic()<deadline,'Import scan timeout: '+boundary
        time.sleep(.3)

try:
    # Exact owned virtual display allocation, no global display or existing window mutation.
    readfd,writefd=os.pipe()
    xvfb=subprocess.Popen([args.xvfb,'-displayfd',str(writefd),'-screen','0','1024x768x24','-nolisten','tcp'],pass_fds=(writefd,),stdout=xlog,stderr=xlog)
    os.close(writefd)
    import select
    assert select.select([readfd],[],[],10)[0],'Xvfb display allocation timed out'
    number=os.read(readfd,32).decode().strip();os.close(readfd);assert number.isdigit() and xvfb.poll() is None
    os.environ['DISPLAY']=':'+number
    server=GodotMcpServer(port=0,gateway_port=0,registry_dir=str(OUT/'session/registry'),enable_gateway_failover=False,enable_telemetry=False,enable_checkpoint_persistence=False)
    server.register_builtin_actions();server.start()
    editor=subprocess.Popen([checked_godot(args.godot),'--editor','--audio-driver','Dummy','--path',str(project),'--rendering-method','gl_compatibility','--rendering-driver','opengl3'],stdout=log,stderr=log)
    deadline=time.monotonic()+90
    while not get_bridge().is_connected():
        assert editor.poll() is None and time.monotonic()<deadline,'Editor bridge not ready';time.sleep(.25)
    inventory();call('load_skill',{'skill_names':['godot-script','godot-editor']});inventory()
    initial_types={'res://scan_probe.gd':'GDScript',**{f'res://assets/{v}/{n}.glb':'PackedScene' for v in ['old','new'] for n in names}}
    wait_import_idle('before-create-script',initial_types)
    call('create_script',{'path':'res://asset_consumer.gd','source':(ROOT/'godot_asset_consumer.gd').read_text(),'overwrite':False})
    types={'res://asset_consumer.gd':'GDScript',**{f'res://assets/{v}/{n}.glb':'PackedScene' for v in ['old','new'] for n in names}}
    wait_import_idle('after-create-script',types)
    samples=[];bounds={}
    for variant in ['old','new']:
        for clip in ['Idle','Walk','Swim']:
            for t in [0.,.25,.5,.75,1.]:
                value=execute('inspect',{'path':f'res://assets/{variant}/explorer.glb','clip':clip,'time':t});finite(value)
                assert value['mesh_count']==36 and len(value['bones'])==23 and abs(value['length']-1)<1e-6
                samples.append(value);bounds[f'{variant}/explorer']=value['rest_mesh_world_aabb']
                (OUT/'actual-consumer-samples.json').write_text(json.dumps(samples,indent=2))
        for name in names[1:]:
            value=execute('inspect',{'path':f'res://assets/{variant}/{name}.glb'});finite(value);assert value['mesh_count']>0
            bounds[f'{variant}/{name}']=value['rest_mesh_world_aabb'];(OUT/f'{variant}-{name}-import.json').write_text(json.dumps(value,indent=2))
    comparisons=[]
    for clip in ['Idle','Walk','Swim']:
        old_samples=[x for x in samples if x['asset'].endswith('/old/explorer.glb') and x['clip'].split('/')[-1]==clip]
        new_samples=[x for x in samples if x['asset'].endswith('/new/explorer.glb') and x['clip'].split('/')[-1]==clip]
        assert len(old_samples)==len(new_samples)==5
        motion=0.;difference=0.
        for a,b in zip(old_samples,new_samples):
            assert a['sample_time']==b['sample_time']
            for old_bone,new_bone,initial in zip(a['bones'],b['bones'],new_samples[0]['bones']):
                assert old_bone['name']==new_bone['name']==initial['name'] and old_bone['parent']==new_bone['parent']
                for field in ['rest','global_pose']:
                    difference=max(difference,float(np.max(np.abs(np.array(old_bone[field])-np.array(new_bone[field])))))
                motion=max(motion,float(np.max(np.abs(np.array(initial['global_pose'])-np.array(new_bone['global_pose'])))))
        assert motion>1e-5,(clip,'No actual sampled motion')
        comparisons.append({'clip':clip,'actual_new_motion_max':motion,'old_new_rest_and_pose_max_abs_difference':difference,'difference_is_diagnostic_not_visual_acceptance':True})
    (OUT/'old-new-pose-comparison.json').write_text(json.dumps(comparisons,indent=2))
    previews=[]
    for name,clip,game_swim in [('explorer','Idle',False),('explorer','Walk',False),('explorer','Swim',False),('explorer','Swim',True),*[(n,None,False) for n in names[1:]]]:
        a=bounds['old/'+name];b=bounds['new/'+name];height=max(a['size'][1],b['size'][1]);width=max(a['size'][0],b['size'][0]);spacing=width*.65
        size=max(height*1.4,(width+2*spacing)/ (640/360)*1.25);center=min(a['position'][1],b['position'][1])+height*.5
        if clip:
            # Fixed generous comparison framing; rest mesh AABBs are not skinned bounds.
            spacing=0.7;size=2.0;center=0.6
        label=name+('-'+clip.lower() if clip else '')+('-game-wrapper' if game_swim else '');scene=f'res://previews/{label}.tscn';output=f'res://previews/{label}.png'
        args={'output':scene,'paths':[f'res://assets/old/{name}.glb',f'res://assets/new/{name}.glb'],'spacing':spacing,'size':size,'height':center}
        if clip:args.update(clip=clip,time=.25,game_swim=game_swim)
        saved=execute('build_preview',args);assert saved['saved']==scene
        expected_witness=scene.removesuffix('.tscn')+'-pose-witness.json'
        assert saved['witness']==expected_witness
        witness_bytes=(project/expected_witness.removeprefix('res://')).read_bytes()
        assert hashlib.sha256(witness_bytes).hexdigest()==saved['witness_sha256']
        built=json.loads(witness_bytes);assert built['saved']==scene
        assert built['nested_scene_instances']==0 and built['mesh_count']>0
        if clip:
            assert built['mesh_count']==73  # 2 x 36 imported meshes plus the fixture ground.
            assert len(built['models'])==len(built['reopened_bones'])==2
            for original,reopened in zip(built['models'],built['reopened_bones']):
                assert len(original['bones'])==len(reopened)==23
                for a,b in zip(original['bones'],reopened):
                    assert a['name']==b['name'] and a['parent']==b['parent']
                    for field in ['position','rotation','scale','rest','global_pose']:
                        assert np.max(np.abs(np.array(a[field])-np.array(b[field])))<=2e-6,(label,a['name'],field)
        (OUT/(label+'-native-pose-save-reopen.json')).write_text(json.dumps(built,indent=2))
        rendered=call('render_scene_preview',{'scene_path':scene,'camera_path':'SameCamera','path':output,'width':640,'height':360,'frame_count':4,'rendering_method':'gl_compatibility'})
        path=project/output.removeprefix('res://')
        with Image.open(path) as im:im.load();assert im.size==(640,360)
        previews.append({'label':label,'source_scene':scene,'actual_response':rendered,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'visual_review_pending':True})
        (OUT/'previews.json').write_text(json.dumps(previews,indent=2))
    assert len(samples)==30 and len(previews)==8
    check_engine_log((OUT/'editor.log').read_text())
    (OUT/'result.json').write_text(json.dumps({'actual_import_sampling_and_native_preview_completed':True,'visual_review_pending':True,'full_game_pending':True,'samples':len(samples),'previews':len(previews)},indent=2))
    print('ACTUAL_GODOT_CONSUMER_SAMPLES_AND_PREVIEWS_COMPLETE_VISUAL_REVIEW_PENDING',flush=True)
finally:
    try:
        stop_process(editor)
    finally:
        try:
            if server is not None:server.stop()
        finally:
            stop_process(xvfb);log.close();xlog.close()
