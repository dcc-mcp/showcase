"""Candidate owned empty-editor inspection only; no conversion/export/render. Not executed."""
import argparse, hashlib, importlib.metadata, json, os, pathlib, select, shutil, socket, signal, subprocess, sys, time, urllib.request, urllib.error
from preflight_contract import audit_baseline, validate_response
from source_contract import read_sources
ROOT = pathlib.Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def durable_new(path, data):
    # Exclusive write; fsync contents and directory before any request is sent.
    with path.open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def durable_status(path, record):
    temporary=path.with_name(path.name+'.next')
    durable_new(temporary,json.dumps(record,indent=2).encode())
    os.replace(temporary,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def capture_http_error(error, path):
    raw=error.read(2*1024*1024+1)
    durable_new(path,raw)
    return {'http_status':error.code,'response_sha256':sha(raw),
            'response_bytes':len(raw),'response_truncated':len(raw)>2*1024*1024}

def parse_rpc(raw):
    text = raw.decode('utf-8')
    if text.startswith(('event:', 'data:')):
        lines = [line[6:] for line in text.splitlines() if line.startswith('data: ')]
        if not lines: raise ValueError('Missing SSE response')
        text = lines[-1]
    result = json.loads(text)
    if not isinstance(result, dict) or 'error' in result or result.get('result', {}).get('isError'):
        raise ValueError('Official MCP returned error')
    return result['result']

def prepare(args):
    pins = json.loads((ROOT/'caller-pins.json').read_text())
    for name, digest in pins['local'].items():
        if sha((ROOT/name).read_bytes()) != digest: raise ValueError('Local input changed: '+name)
    for name, digest in pins['ci'].items():
        if sha((args.ci/name).read_bytes()) != digest: raise ValueError('Bootstrap input changed: '+name)
    plan_bytes = (ROOT/'plan.json').read_bytes(); plan = json.loads(plan_bytes)
    sources = read_sources(args.archive, plan)
    baselines = {}
    for item in plan['assets']:
        data = (args.baseline/item['output']).read_bytes()
        if len(data) != item['baseline_bytes']: raise ValueError('Baseline size mismatch')
        audit_baseline(data, item['baseline_sha256']); baselines[item['output']] = data
    return plan, plan_bytes, sources, baselines, pins

def run(args):
    if args.output.exists(): raise FileExistsError('Fresh output required; never replay an unknown inspection')
    plan, plan_bytes, sources, baselines, pins = prepare(args)
    for pkg, version in [('dcc-mcp-godot','0.9.6'),('dcc-mcp-core','0.20.42')]:
        if importlib.metadata.version(pkg) != version: raise ValueError('Unexpected '+pkg)
    mem = int(next(x.split()[1] for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))/1024
    if not (mem >= 2800 and shutil.disk_usage(args.output.parent).free > 1000*2**20 and shutil.disk_usage('/tmp').free > 600*2**20): raise RuntimeError('Resource guard failed before native startup')
    sys.path.insert(0, str(args.ci))
    from common import checked_godot, isolated_env, stop_process, check_engine_log
    from author_native import envelope, EDITOR_PROBE_SOURCE, editor_idle_sample
    godot = checked_godot(args.godot)
    args.output.mkdir(); out=args.output
    os.environ.update(isolated_env(out/'session'))
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    os.environ.update(DCC_MCP_GODOT_BRIDGE_PORT=str(port),DCC_MCP_GODOT_BRIDGE_URL=f'ws://127.0.0.1:{port}',DCC_MCP_REGISTRY_DIR=str(out/'session/registry'),DCC_MCP_CLI_NO_AUTO_GATEWAY='true')
    import dcc_mcp_godot
    from dcc_mcp_godot.server import GodotMcpServer
    from dcc_mcp_godot.bridge import get_bridge
    project=out/'project'; project.mkdir(); base=project/'kenney-preflight';base.mkdir()
    shutil.copytree(pathlib.Path(dcc_mcp_godot.__file__).parent/'godot_addon/addons',project/'addons')
    (project/'project.godot').write_text('config_version=5\n[application]\nconfig/name="Kenney readonly source inspection"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n[editor_plugins]\nenabled=PackedStringArray("res://addons/dcc_mcp_godot/plugin.cfg")\n')
    (project/'scan_probe.gd').write_text(EDITOR_PROBE_SOURCE)
    (base/'plan.json').write_bytes(plan_bytes)
    for directory in ['source','baseline']: (base/directory).mkdir()
    for item in plan['assets']:
        (base/'source'/item['source_file']).write_bytes(sources[item['output']]['bytes'])
        (base/'baseline'/item['output']).write_bytes(baselines[item['output']])
    (out/'inputs.json').write_text(json.dumps({'pins':pins,'plan_sha256':sha(plan_bytes),'source_archive_sha256':plan['archive_sha256'],'runner_sha256':sha(pathlib.Path(__file__).read_bytes()),'mem_available_mib':mem,'adapter':'0.9.6','core':'0.20.42'},indent=2))
    server=editor=xvfb=None; schemas={}; sequence=0; report={'passed':False,'converted':False,'saved_native_asset':False,'scope':'source/baseline inspection only'}
    log=(out/'editor.log').open('w');xlog=(out/'xvfb.log').open('w')
    def rpc(method, params):
        nonlocal sequence
        sequence+=1; request={'jsonrpc':'2.0','id':sequence,'method':method,'params':params}
        record={'request':request,'outcome':'unknown'};dest=out/f'rpc-{sequence:03d}.json'
        durable_new(out/f'rpc-{sequence:03d}.request.json',json.dumps(request,indent=2).encode())
        durable_new(dest,json.dumps(record,indent=2).encode())
        req=urllib.request.Request(server.mcp_url,data=json.dumps(request).encode(),headers={'Content-Type':'application/json','Accept':'application/json,text/event-stream'})
        try:
            with urllib.request.urlopen(req,timeout=120) as response: raw=response.read(2*1024*1024+1)
            durable_new(out/f'rpc-{sequence:03d}.response',raw)
            if len(raw)>2*1024*1024: raise ValueError('Response over bounded transport budget')
            value=parse_rpc(raw);record.update(outcome='returned',response_sha256=sha(raw));return value
        except urllib.error.HTTPError as exc:
            record.update(capture_http_error(exc,out/f'rpc-{sequence:03d}.http-error.response'));record['error']=repr(exc);raise
        except BaseException as exc:
            record['error']=repr(exc);raise
        finally: durable_status(dest,record)
    def inventory():
        cursor=None
        for _ in range(30):
            page=rpc('tools/list',{'cursor':cursor} if cursor else {});schemas.update({t['name']:t for t in page['tools']});cursor=page.get('nextCursor')
            if not cursor:return
        raise RuntimeError('Unterminated inventory')
    def call(name, arguments):
        names=[n for n in schemas if n==name or n.endswith('__'+name)]
        if len(names)!=1:raise ValueError('Ambiguous/missing official tool '+name)
        body=envelope(rpc('tools/call',{'name':names[0],'arguments':arguments}))
        if body.get('job_id') or body.get('success') is False or body.get('valid') is False:raise ValueError('Unexpected official result; do not replay')
        context=body.get('context',body)
        if context.get('valid') is False:raise ValueError('Invalid official context')
        return context
    def idle(label, types):
        deadline=time.monotonic()+90;previous=None
        while True:
            sample,ready=editor_idle_sample(call('execute_editor_script',{'path':'res://scan_probe.gd','method':'inspect','arguments':{'paths':list(types)},'budget_ms':50,'chunked':False}),types)
            if ready and previous is not None and sample['process_frame']>=previous['process_frame']+2:
                (out/(label+'-idle.json')).write_text(json.dumps([previous,sample],indent=2));return
            if not ready:previous=None
            elif previous is None:previous=sample
            if editor.poll() is not None or time.monotonic()>=deadline:raise RuntimeError('Editor readiness timed out')
            time.sleep(.3)
    def interrupted(signum, frame):
        raise TimeoutError('Owned preflight deadline/cancellation; preserve partial evidence')
    prior_alarm=signal.signal(signal.SIGALRM,interrupted);prior_term=signal.signal(signal.SIGTERM,interrupted)
    try:
        signal.alarm(240)
        readfd,writefd=os.pipe()
        try:
            xvfb=subprocess.Popen([args.xvfb,'-displayfd',str(writefd),'-screen','0','1024x768x24','-nolisten','tcp'],pass_fds=(writefd,),stdout=xlog,stderr=xlog)
            os.close(writefd);writefd=None
            if not select.select([readfd],[],[],10)[0]:raise RuntimeError('Display startup timeout')
            number=os.read(readfd,32).decode().strip()
            if not number.isdigit() or xvfb.poll() is not None:raise RuntimeError('Invalid owned display')
            os.environ['DISPLAY']=':'+number
        finally:
            os.close(readfd)
            if writefd is not None:os.close(writefd)
        server=GodotMcpServer(port=0,gateway_port=0,registry_dir=str(out/'session/registry'),enable_gateway_failover=False,enable_telemetry=False,enable_checkpoint_persistence=False)
        server.register_builtin_actions();server.start()
        editor=subprocess.Popen([godot,'--editor','--audio-driver','Dummy','--path',str(project),'--rendering-method','gl_compatibility','--rendering-driver','opengl3'],stdout=log,stderr=log)
        deadline=time.monotonic()+90
        while not get_bridge().is_connected():
            if editor.poll() is not None or time.monotonic()>=deadline:raise RuntimeError('Editor bridge not ready')
            time.sleep(.25)
        inventory();call('load_skill',{'skill_names':['godot-script','godot-editor']});inventory()
        types={'res://scan_probe.gd':'GDScript'}
        for item in plan['assets']:
            types['res://kenney-preflight/source/'+item['source_file']]='PackedScene'
            types['res://kenney-preflight/baseline/'+item['output']]='PackedScene'
        idle('before-script',types)
        call('create_script',{'path':'res://inspect_kenney_sources.gd','source':(ROOT/'inspect_kenney_sources.gd').read_text(),'overwrite':False})
        idle('after-script',{**types,'res://inspect_kenney_sources.gd':'GDScript'})
        body=call('execute_editor_script',{'path':'res://inspect_kenney_sources.gd','method':'run','arguments':{'plan_sha256':sha(plan_bytes)},'budget_ms':50,'chunked':False})
        witness_path=base/'preflight-witness.json'
        if not witness_path.is_file() or witness_path.stat().st_size>1024*1024:raise ValueError('Missing/oversize witness')
        witness=validate_response(body,witness_path.read_bytes(),plan)
        check_engine_log((out/'editor.log').read_text())
        report.update(inspected=4,witness_sha256=sha(witness_path.read_bytes()),scene_before=witness['scene_before'],scene_after=witness['scene_after'],business_checks_passed=True)
    except BaseException as exc:
        report['error']=repr(exc);raise
    finally:
        signal.alarm(0)
        errors=[]
        for name, obj, shutdown in [('editor',editor,stop_process),('server',server,lambda x:x.stop()),('xvfb',xvfb,stop_process)]:
            if obj is None:continue
            try:
                shutdown(obj)
                if name!='server':
                    report[name+'_exit_code']=obj.poll()
                    if obj.poll() is None:raise RuntimeError('Owned process remains live')
            except BaseException as exc: errors.append({'component':name,'error':repr(exc)})
        log.close();xlog.close();report['cleanup_errors']=errors
        report['passed']=report.get('business_checks_passed') is True and not errors and 'error' not in report
        (out/'result.json').write_text(json.dumps(report,indent=2))
        signal.signal(signal.SIGALRM,prior_alarm);signal.signal(signal.SIGTERM,prior_term)
        if errors:raise RuntimeError('Owned cleanup incomplete; see retained result')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['output','ci','archive','baseline']:p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--godot',required=True);p.add_argument('--xvfb',default='Xvfb')
    args=p.parse_args()
    for name in ['output','ci','archive','baseline']:setattr(args,name,getattr(args,name).resolve())
    run(args)
if __name__=='__main__':main()
