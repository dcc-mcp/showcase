"""Real official Godot export capability in an isolated, owned editor session."""
from pathlib import Path
import base64, hashlib, importlib.metadata, json, os, shutil, socket, subprocess, time, urllib.request
from common import check_engine_log, stop_process, write_json
from author_native import envelope, EDITOR_PROBE_SOURCE, editor_idle_sample

CANDIDATE_COMMIT = "0c99ee85be38c4fce5e8a385c902d00a72207a29"
CANDIDATE_WHEEL_SHA256 = "b356c09bea87c8b3987e55e5ecee14a7fe706e04ac7bfb11c3c13a7137a30c33"
PROBE = EDITOR_PROBE_SOURCE + '''
func stored_settings() -> Dictionary:
 var result := {}
 for property in ProjectSettings.get_property_list():
  var key := String(property.name)
  if ProjectSettings.has_setting(key): result[key] = ProjectSettings.get_setting(key)
 return result
func prepare_export(arguments: Dictionary) -> Dictionary:
 var original := ConfigFile.new()
 if original.parse(String(arguments.source)) != OK: return {"error":"Cannot parse original settings"}
 for section in original.get_sections():
  for key in original.get_section_keys(section):
   if String(section).is_empty() and String(key) == "config_version":
    if original.get_value(section, key) != 5: return {"error":"Unexpected project format"}
    continue
   var setting := String(section) + "/" + String(key)
   if ProjectSettings.get_setting(setting) != original.get_value(section, key):
    return {"error":"Original game setting changed", "setting":setting}
 var before := stored_settings()
 var removed: Array[String] = []
 for key in ["autoload/DccMcpRuntimePeer", "editor_plugins/enabled"]:
  if not ProjectSettings.has_setting(key): return {"error":"Expected control setting absent"}
  ProjectSettings.set_setting(key, null)
  before.erase(key)
  removed.append(key)
 var save_error := ProjectSettings.save()
 if save_error != OK: return {"error":"Native settings save failed", "code":save_error}
 if before != stored_settings(): return {"error":"Unrelated settings changed"}
 return {"sha256":FileAccess.get_sha256("res://project.godot"),
  "preserved_settings":true, "removed":removed}
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


def record_rpc_response(receipts, request, raw, http_status, destination):
    """Retain exact response bytes even when decoding cannot establish the outcome."""
    receipt={'request':request,'http_status':http_status,'raw_base64':base64.b64encode(raw).decode('ascii'),
             'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest()}
    receipts.append(receipt)
    try:
        text=raw.decode('utf-8')
        body=json.loads([line[6:] for line in text.splitlines() if line.startswith('data: ')][-1]) if text.startswith(('data:','event:')) else json.loads(text)
        if not isinstance(body,dict):raise ValueError('Expected JSON-RPC response object')
        receipt['response']=body
        return body
    except Exception as error:
        receipt.update(outcome='unknown',parse_error=repr(error))
        raise
    finally:
        write_json(destination,receipts)


def partial_output_index(project):
    """Read actual remaining bytes after owned cleanup, never infer export success."""
    root=project/'web-output';items=[]
    if root.exists():
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                items.append({'path':path.relative_to(root).as_posix(),'symlink':True})
            elif path.is_file():
                digest=hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
                items.append({'path':path.relative_to(root).as_posix(),'bytes':path.stat().st_size,'sha256':digest.hexdigest()})
    return {'accepted':False,'purpose':'diagnostic snapshot, not a successful export claim','files':items}


def cleanup_export(editor, server, log, report, project, out):
    try:
        try:stop_process(editor)
        except Exception as error:
            report.update(passed=False,editor_cleanup_error=repr(error));raise
        finally:
            if server is not None:
                try:server.stop()
                except Exception as error:
                    report.update(passed=False,server_cleanup_error=repr(error));raise
    finally:
        log.close()
        try:write_json(out/'export-partial-index.json',partial_output_index(project))
        finally:write_json(out/'export-mcp.json',report)


def export_through_mcp(godot, project, out, env, native_hashes):
    for package, version in [('dcc-mcp-godot','0.9.9'),('dcc-mcp-core','0.20.46')]:
        assert importlib.metadata.version(package) == version
    provenance=json.loads(Path(os.environ['TIDAL_EXPORT_CANDIDATE_RECEIPT']).read_text())
    assert provenance=={'commit':CANDIDATE_COMMIT,'wheel_sha256':CANDIDATE_WHEEL_SHA256,'core':'0.20.46'}
    write_json(out/'export-candidate.json',provenance)
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
    report={'passed':False,'route':'official adapter candidate godot-export.start_export_job/get_export_job','adapter':'0.9.9','core':'0.20.46','candidate_commit':CANDIDATE_COMMIT,'candidate_wheel_sha256':CANDIDATE_WHEEL_SHA256,'clean_project_sha256':original_hash,'native_sha256':native_hashes}
    def rpc(method, params):
        request={'jsonrpc':'2.0','id':len(receipts)+1,'method':method,'params':params}
        req=urllib.request.Request(server.mcp_url,data=json.dumps(request).encode(),headers={'Content-Type':'application/json','Accept':'application/json,text/event-stream'})
        try:
            with urllib.request.urlopen(req,timeout=90) as response:
                raw=response.read();http_status=response.status
        except Exception as error:
            receipts.append({'request':request,'transport_error':repr(error),'outcome':'unknown'})
            write_json(out/'export-mcp-raw.json',receipts)
            raise
        body=record_rpc_response(receipts,request,raw,http_status,out/'export-mcp-raw.json')
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
        if body.get('success') is False or body.get('valid') is False or context.get('valid') is False:
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
        snapshot_dir = out/'export-configuration'
        def snapshot(label):
            folder=snapshot_dir/label;folder.mkdir(parents=True)
            hashes={}
            for name in ('project.godot','export_presets.cfg'):
                data=(project/name).read_bytes();(folder/name).write_bytes(data)
                hashes[name]=hashlib.sha256(data).hexdigest()
            write_json(folder/'hashes.json',hashes)
            return hashes
        snapshot('before-preparation')
        prepared=call('execute_editor_script',{'path':'res://tidal_export_probe.gd','method':'prepare_export','arguments':{'source':original.decode()},'budget_ms':50,'chunked':False})
        result=prepared.get('result',{})
        assert prepared.get('executed') is True and result.get('preserved_settings') is True
        assert result.get('removed')==['autoload/DccMcpRuntimePeer','editor_plugins/enabled']
        baseline=(project/'project.godot').read_bytes()
        assert b'dcc_mcp' not in baseline.lower() and b'dccmcpruntimepeer' not in baseline.lower()
        assert result['sha256']==hashlib.sha256(baseline).hexdigest()
        report['preparation']=result;expected=snapshot('prepared-before-start')
        previous=None;stable=0;deadline=time.monotonic()+30
        while stable<2:
            sample,idle=editor_idle_sample(call('execute_editor_script',{'path':'res://tidal_export_scan.gd','method':'inspect','arguments':{'paths':['res://start.tscn']},'budget_ms':50,'chunked':False}),{'res://start.tscn':'PackedScene'})
            assert all(hashlib.sha256((project/name).read_bytes()).hexdigest()==value for name,value in expected.items())
            if idle and previous is not None and sample['process_frame']>=previous['process_frame']+2:stable+=1
            elif not idle:stable=0
            previous=sample if idle else None
            assert editor.poll() is None and time.monotonic()<deadline,'Prepared export configuration did not stabilize'
            time.sleep(1)
        request_id='b'*32  # Fresh owned project/registry per run; never resubmit after an uncertain call.
        report['request_id']=request_id;write_json(out/'export-mcp.json',report)
        started=call('start_export_job',{'request_id':request_id,'preset':'Web','path':'web-output/index.html','debug':False,'timeout_seconds':600})
        assert started['job_id']==request_id
        deadline=time.monotonic()+630
        result=started
        while result['status'] in ('queued','running'):
            if time.monotonic()>=deadline:
                report['cancel_receipt']=call('cancel_export_job',{'job_id':request_id})
                raise TimeoutError('Known export job exceeded observation boundary; no resubmission')
            time.sleep(.25);result=call('get_export_job',{'job_id':request_id})
            assert result['job_id']==request_id
        report['result']=result
        assert result['status']=='completed' and result['exit_code']==0
        assert all(result.get(key) is True for key in ('artifacts_accepted','child_reaped','descendant_cleanup_confirmed','log_complete'))
        assert result['request']['configuration_sha256']==expected==result['configuration_after_sha256']
        assert snapshot('completed')==expected
        journal=out/'session/registry/godot-export-jobs'/request_id
        log_path=journal/'export.log';manifest_path=journal/'outputs.json'
        assert Path(result['log_path'])==log_path and Path(result['output_manifest_path'])==manifest_path
        assert hashlib.sha256(log_path.read_bytes()).hexdigest()==result['log_sha256']
        assert log_path.stat().st_size==result['log_bytes']
        assert hashlib.sha256(manifest_path.read_bytes()).hexdigest()==result['output_manifest_sha256']
        manifest=json.loads(manifest_path.read_text());actual=[]
        assert len(manifest['files'])==result['output_count']
        assert sum(item['bytes'] for item in manifest['files'])==manifest['bytes']==result['output_bytes']
        for item in manifest['files']+manifest['control_files']:
            relative=Path(item['path'])
            assert not relative.is_absolute() and '..' not in relative.parts
            path=project/'web-output'/relative
            assert path.is_file() and not path.is_symlink()
            assert path.stat().st_size==item['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
            actual.append(item['path'])
        assert sorted(actual)==sorted(p.relative_to(project/'web-output').as_posix() for p in (project/'web-output').rglob('*') if p.is_file())
        assert manifest['control_files']==[{'path':'.gdignore','bytes':0,'sha256':hashlib.sha256(b'').hexdigest()}]
        export_log=log_path.read_text();check_engine_log(export_log);(out/'export.log').write_text(export_log)
        log.flush();check_engine_log((out/'export-editor.log').read_text())
        report.update(passed=True,output_manifest=manifest,prepared_configuration_sha256=expected)
        return project/'web-output'
    except Exception as error:
        report['blocker']=str(error);raise
    finally:
        cleanup_export(editor,server,log,report,project,out)


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
