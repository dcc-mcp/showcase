"""Real official Godot export capability in an isolated, owned editor session."""
from pathlib import Path
import hashlib, importlib.metadata, json, os, shutil, socket, subprocess, time, urllib.request
from common import check_engine_log, stop_process, write_json
from author_native import envelope, EDITOR_PROBE_SOURCE, editor_idle_sample

PROBE = EDITOR_PROBE_SOURCE + '''
func prepare_export(arguments: Dictionary) -> Dictionary:
 var source := String(arguments.source)
 if not source.begins_with("; Engine configuration file.") and not source.contains("config_version=5"):
  return {"error": "Expected original project configuration"}
 if source.contains("dcc_mcp_godot") or source.contains("DccMcpRuntimePeer"):
  return {"error": "Control addon must not enter exported configuration"}
 var file := FileAccess.open("res://project.godot", FileAccess.WRITE)
 if file == null: return {"error": "Cannot restore clean export configuration"}
 file.store_string(source)
 file.close()
 return {"written": true, "sha256": FileAccess.get_sha256("res://project.godot")}
'''


def validate_export_result(body):
    value = body.get('context', body)
    if value.get('exported') is not True or type(value.get('exit_code')) is not int or value['exit_code'] != 0:
        raise RuntimeError('Official export did not complete successfully: '+json.dumps(body))
    if value.get('path') != 'res://web-output/index.html':
        raise RuntimeError('Unexpected official export target')
    output = value.get('output')
    if not isinstance(output, str) or len(output) >= 20000:
        raise RuntimeError('Official export log missing or possibly truncated; cannot accept')
    check_engine_log(output)
    return value


def export_through_mcp(godot, project, out, env, native_hashes):
    for package, version in [('dcc-mcp-godot','0.9.6'),('dcc-mcp-core','0.20.42')]:
        assert importlib.metadata.version(package) == version
    original = (project/'project.godot').read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    assert b'dcc_mcp_godot' not in original and b'DccMcpRuntimePeer' not in original
    assert not (project/'addons').exists() and not (project/'web-output').exists()
    os.environ.update(env)
    with socket.socket() as port:port.bind(('127.0.0.1',0)); bridge_port=port.getsockname()[1]
    os.environ.update(DCC_MCP_GODOT_BRIDGE_PORT=str(bridge_port),DCC_MCP_GODOT_BRIDGE_URL=f'ws://127.0.0.1:{bridge_port}',DCC_MCP_REGISTRY_DIR=str(out/'session/registry'),DCC_MCP_CLI_NO_AUTO_GATEWAY='true')
    import dcc_mcp_godot
    from dcc_mcp_godot.bridge import get_bridge
    from dcc_mcp_godot.server import GodotMcpServer
    shutil.copytree(Path(dcc_mcp_godot.__file__).parent/'godot_addon/addons',project/'addons')
    (project/'project.godot').write_bytes(original+b'\n[editor_plugins]\nenabled=PackedStringArray("res://addons/dcc_mcp_godot/plugin.cfg")\n')
    (project/'tidal_export_scan.gd').write_text(EDITOR_PROBE_SOURCE)  # Read-only import diagnostic, never exported.
    server=None;editor=None;receipts=[];schemas={};log=(out/'export-editor.log').open('w')
    report={'passed':False,'route':'official godot-export.export_project','adapter':'0.9.6','core':'0.20.42','clean_project_sha256':original_hash,'native_sha256':native_hashes}
    def rpc(method, params):
        request={'jsonrpc':'2.0','id':len(receipts)+1,'method':method,'params':params}
        req=urllib.request.Request(server.mcp_url,data=json.dumps(request).encode(),headers={'Content-Type':'application/json','Accept':'application/json,text/event-stream'})
        with urllib.request.urlopen(req,timeout=90) as response:raw=response.read().decode()
        body=json.loads([line[6:] for line in raw.splitlines() if line.startswith('data: ')][-1]) if raw.startswith(('data:','event:')) else json.loads(raw)
        receipts.append({'request':request,'response':body});write_json(out/'export-mcp-raw.json',receipts)
        if 'error' in body or body.get('result',{}).get('isError'):raise RuntimeError('Official export MCP failed: '+json.dumps(body))
        return body.get('result',{})
    def inventory():
        cursor=None
        for _ in range(30):
            page=rpc('tools/list',{'cursor':cursor} if cursor else {});schemas.update({x['name']:x for x in page['tools']});cursor=page.get('nextCursor')
            if not cursor:return
        raise RuntimeError('Tool inventory did not terminate')
    def call(name, params):
        found=[n for n in schemas if n==name or n.endswith('__'+name)];assert len(found)==1,(name,found)
        body=envelope(rpc('tools/call',{'name':found[0],'arguments':params}));context=body.get('context',body)
        if body.get('success') is False or body.get('valid') is False or context.get('valid') is False or body.get('job_id'):
            raise RuntimeError('Unexpected failure/async outcome; preserve receipt, never replay: '+json.dumps(body))
        return context
    try:
        server=GodotMcpServer(port=0,gateway_port=0,registry_dir=str(out/'session/registry'),enable_gateway_failover=False,enable_telemetry=False,enable_checkpoint_persistence=False)
        server.register_builtin_actions();server.start()
        editor=subprocess.Popen([godot,'--editor','--audio-driver','Dummy','--path',str(project),'--rendering-method','gl_compatibility','--rendering-driver','opengl3'],stdout=log,stderr=log)
        deadline=time.monotonic()+90
        while not get_bridge().is_connected():
            assert editor.poll() is None and time.monotonic()<deadline,'Export editor did not connect'
            time.sleep(.2)
        inventory();call('load_skill',{'skill_names':['godot-export','godot-script','godot-editor']});inventory()
        report['import_idle_boundaries']=[]
        for boundary in ('initial scan','typed export helper'):
            if boundary=='typed export helper':
                call('create_script',{'path':'res://tidal_export_probe.gd','source':PROBE,'overwrite':False})
            deadline=time.monotonic()+90;previous=None
            types={'res://tidal_export_scan.gd':'GDScript','res://start.tscn':'PackedScene'}
            if boundary=='typed export helper':types['res://tidal_export_probe.gd']='GDScript'
            while True:
                sample,idle=editor_idle_sample(call('execute_editor_script',{'path':'res://tidal_export_scan.gd','method':'inspect','arguments':{'paths':list(types)},'budget_ms':50,'chunked':False}),types)
                log.flush();check_engine_log((out/'export-editor.log').read_text())
                if idle and previous is not None and sample['process_frame']>=previous['process_frame']+2:break
                if not idle:previous=None
                elif previous is None:previous=sample
                assert editor.poll() is None and time.monotonic()<deadline,'Export imports not ready: '+boundary
                time.sleep(.2)
            report['import_idle_boundaries'].append({'boundary':boundary,'samples':[previous,sample]})
        info=call('list_export_presets',{});assert any(x['name']=='Web' and x['platform']=='Web' for x in info['presets'])
        (project/'web-output').mkdir()
        prepared=call('execute_editor_script',{'path':'res://tidal_export_probe.gd','method':'prepare_export','arguments':{'source':original.decode()},'budget_ms':50,'chunked':False})
        assert prepared.get('executed') is True and prepared['result']=={'written':True,'sha256':original_hash}
        assert (project/'project.godot').read_bytes()==original
        result=validate_export_result(call('export_project',{'preset':'Web','path':'web-output/index.html','debug':False}))
        (out/'export.log').write_text(result['output']);assert (project/'project.godot').read_bytes()==original
        log.flush();check_engine_log((out/'export-editor.log').read_text())
        report.update(passed=True,result=result,preset_sha256=hashlib.sha256((project/'export_presets.cfg').read_bytes()).hexdigest())
        return project/'web-output'
    except Exception as error:
        report['blocker']=str(error);raise
    finally:
        try:stop_process(editor)
        finally:
            try:
                if server is not None:server.stop()
            finally:log.close();write_json(out/'export-mcp.json',report)


def inspect_clean_pck(path):
    """Read v2/v3 standalone PCK index per Godot 4.6.3 file_access_pack.cpp."""
    import struct
    entries=[];total=path.stat().st_size
    with path.open('rb') as stream:
        def take(n):
            b=stream.read(n)
            if len(b)!=n:raise ValueError('Truncated PCK index')
            return b
        def u32():return struct.unpack('<I',take(4))[0]
        def u64():return struct.unpack('<Q',take(8))[0]
        if take(4)!=b'GDPC':raise ValueError('Not standalone Godot PCK')
        version=u32();engine=(u32(),u32(),u32());flags=u32();base=u64()
        if version not in (2,3) or engine!=(4,6,3) or flags not in (0,2):raise ValueError('Unexpected PCK format/engine/flags')
        if version==3:
            offset=u64()
            if not 40<=offset<total:raise ValueError('Invalid PCK directory offset')
            stream.seek(offset)
        else:take(64)
        count=u32()
        if not 1<=count<=10000:raise ValueError('Unexpected PCK entry count')
        for _ in range(count):
            n=u32()
            if not 1<=n<=4096:raise ValueError('Invalid PCK path size')
            name=take(n).rstrip(b'\0').decode('utf-8');offset=u64()+base;size=u64();digest=take(16);entry_flags=u32()
            if entry_flags!=0 or offset+size>total:raise ValueError('Unsupported or out-of-bounds PCK entry')
            if any(x in name.lower() for x in ('addons/','dcc_mcp','tidal_export_','web-output/')):raise ValueError('Control/export artifact entered PCK: '+name)
            entries.append((name,offset,size,digest))
        configs=[x for x in entries if x[0] in ('res://project.binary','project.binary','res://project.godot','project.godot')]
        if len(configs)!=1:raise ValueError('Expected one exported project configuration')
        name,offset,size,digest=configs[0]
        if size>1024*1024:raise ValueError('Unexpected configuration size')
        stream.seek(offset);config=take(size)
        if hashlib.md5(config).digest()!=digest:raise ValueError('PCK project configuration digest mismatch')
        if any(x in config.lower() for x in (b'dcc_mcp',b'dccmcpruntimepeer',b'tidal_export_',b'addons/')):raise ValueError('Control addon/autoload entered PCK configuration')
    return {'format':version,'engine':engine,'entries':[x[0] for x in entries],'project_configuration':name,'project_configuration_sha256':hashlib.sha256(config).hexdigest(),'pck_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
