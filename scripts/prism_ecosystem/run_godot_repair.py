"""Candidate hosted qualification. No direct movie CLI or native pack production CLI.

Production uses actual official MCP editor script + play_scene. Direct native
--main-pack below is independent read-only acceptance, never production.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
import threading
import urllib.request
import zipfile

EXPECTED = {"dcc-mcp-godot": "0.9.9", "dcc-mcp-core": "0.20.46", "Pillow": "13.0.0"}
CANDIDATE = "0c99ee85be38c4fce5e8a385c902d00a72207a29"
WHEEL_SHA = "b356c09bea87c8b3987e55e5ecee14a7fe706e04ac7bfb11c3c13a7137a30c33"
ROOT = Path(__file__).resolve().parent
CAP_BYTES = 2 * 1024**3


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n')


def envelope(result):
    if isinstance(result.get('structuredContent'), dict):
        return result['structuredContent']
    for item in result.get('content', []):
        if item.get('type') == 'text':
            try:
                return json.loads(item['text'])
            except (ValueError, TypeError):
                pass
    return result


def group_census(pgid):
    # Zombies cannot produce output; the owned leader still requires Popen.wait.
    rows, errors = [], []
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            text = path.read_text()
            fields = text[text.rfind(')') + 2:].split()
            if int(fields[2]) == pgid and fields[0] != 'Z':
                rows.append(int(path.parent.name))
        except FileNotFoundError:
            continue  # Process exited between enumeration and read.
        except (OSError, ValueError, IndexError) as error:
            errors.append({'path':str(path), 'error':repr(error)})
    return {'live_pids':rows, 'inspection_errors':errors}


def stop_owned(process):
    if process is None:
        return {'started':False}
    pgid=process.pid
    # Explicit movie children have their own sessions and cleanup above. These
    # immutable acceptance/editor entrypoints have no other production children.
    # Popen signals only its still-unreaped owned leader, never a recycled PGID.
    for sig,seconds in ((signal.SIGTERM,10),(signal.SIGKILL,5)):
        if process.poll() is None:
            process.send_signal(sig)
            try: process.wait(timeout=seconds)
            except subprocess.TimeoutExpired: continue
        break
    exit_code=process.wait(timeout=5)
    census=group_census(pgid)
    return {'pid':process.pid,'pgid':pgid,'exit_code':exit_code,
            'remaining_live_pids':census['live_pids'],
            'inspection_errors':census['inspection_errors'],
            'cleanup_confirmed':not census['live_pids'] and not census['inspection_errors']}


def process_identity(pid):
    root=Path('/proc')/str(pid)
    try:
        text=(root/'stat').read_text()
    except FileNotFoundError:
        return {'status':'missing','pid':pid}
    except OSError as error:
        return {'status':'unknown','pid':pid,'error':repr(error)}
    try:
        fields=text[text.rfind(')')+2:].split()
        row={'status':'zombie' if fields[0]=='Z' else 'live','pid':pid,'state':fields[0],
             'ppid':int(fields[1]),'pgid':int(fields[2]),'sid':int(fields[3]),'starttime':int(fields[19])}
        if row['status']=='zombie':
            return dict(row,exe=None,argv=[])
        row.update(exe=str((root/'exe').resolve(strict=True)),
                   argv=(root/'cmdline').read_bytes().decode().rstrip('\0').split('\0'))
        final=(root/'stat').read_text()
        final_fields=final[final.rfind(')')+2:].split()
        if (int(final_fields[19]),int(final_fields[1])) != (row['starttime'],row['ppid']):
            return {'status':'unknown','pid':pid,'error':'Identity changed during read'}
        return row
    except (OSError,ValueError,IndexError,UnicodeError) as error:
        # Reading an existing process failed. This is NOT evidence that it exited.
        return {'status':'unknown','pid':pid,'error':repr(error)}


def original_gone(row):
    current=process_identity(row['pid'])
    return current['status']=='missing' or (current['status'] in ('live','zombie') and current['starttime']!=row['starttime'])


def freeze_owned(process, expected_exe):
    if process.poll() is not None:
        return {'already_exited':True,'exit_code':process.returncode}
    row=process_identity(process.pid)
    assert row['status']=='live' and row['exe']==expected_exe
    fd=os.pidfd_open(process.pid)
    try:
        again=process_identity(process.pid)
        assert again['status']=='live' and again['starttime']==row['starttime']
        signal.pidfd_send_signal(fd,signal.SIGSTOP)
    finally:
        os.close(fd)
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        actual=process_identity(process.pid)
        if actual['status']=='live' and actual['starttime']==row['starttime'] and actual['state'] in ('T','t'):
            return {'frozen':True,'identity':actual}
        time.sleep(.02)
    raise RuntimeError('Owned editor freeze not confirmed')


class MovieChildren:
    """Track all actual editor Godot children, including incorrect/missing movie args."""
    def __init__(self, editor, godot, project, destination, frames):
        self.parent=process_identity(editor.pid)
        assert self.parent['status']=='live' and self.parent['exe']==str(godot)
        self.godot,self.project,self.destination,self.frames=str(godot),str(project),str(destination),frames
        self.records,self.errors={},[]
        self.normal_boundary=False
        self.stop=threading.Event()
        self.thread=threading.Thread(target=self._watch,daemon=False)
        self.thread.start()

    def scan_once(self):
        parent=process_identity(self.parent['pid'])
        if parent['status']!='live' or parent['starttime']!=self.parent['starttime']:
            self.errors.append('Cannot inspect matching live editor: '+repr(parent));return
        try:
            tasks=list((Path('/proc')/str(parent['pid'])/'task').iterdir())
            children=set()
            for task in tasks:
                try: children.update(map(int,(task/'children').read_text().split()))
                except FileNotFoundError: continue  # An individual editor thread ended.
            for pid in children:
                row=process_identity(pid)
                if row['status']=='unknown':
                    self.errors.append('Owned child inspection unknown: '+repr(row));continue
                if row['status']!='live' or row['ppid']!=parent['pid'] or row['exe']!=self.godot:
                    continue
                # Record provenance BEFORE checking argv. A broken launch is still owned.
                self.records[(row['pid'],row['starttime'])]=row
        except (OSError,ValueError) as error:
            self.errors.append('Child enumeration unknown: '+repr(error))

    def _watch(self):
        while not self.stop.is_set():
            try: self.scan_once()
            except BaseException as error: self.errors.append('Monitor exception: '+repr(error))
            self.stop.wait(.005)

    def parameters_match(self,row):
        args=row['argv']
        try:
            def argument(flag): return args[args.index(flag)+1]
            return (argument('--write-movie')==self.destination and argument('--fixed-fps')=='30' and
                    argument('--quit-after')==str(self.frames) and argument('--path')==self.project and
                    '--demo' in args and row['pid']==row['pgid']==row['sid'])
        except (ValueError,IndexError): return False

    def finish(self):
        self.stop.set();self.thread.join(timeout=3)
        assert not self.thread.is_alive()
        rows=list(self.records.values())
        return {'children':rows,'monitor_errors':self.errors,
                'parameters_valid':bool(rows) and all(self.parameters_match(row) for row in rows)}

    def cleanup(self):
        observed=self.finish()
        results=[]
        for row in observed['children']:
            result={'identity':row,'signals':[]}
            fd=None
            try:
                for sig,seconds in ((signal.SIGTERM,10),(signal.SIGKILL,5)):
                    if original_gone(row): break
                    current=process_identity(row['pid'])
                    if current['status']=='unknown': raise RuntimeError(repr(current))
                    assert current['starttime']==row['starttime']
                    if current['status']=='live':
                        assert current['exe']==row['exe']
                        if fd is None: fd=os.pidfd_open(row['pid'])
                        again=process_identity(row['pid'])
                        assert again['status']=='live' and again['starttime']==row['starttime']
                        signal.pidfd_send_signal(fd,sig);result['signals'].append(int(sig))
                    deadline=time.monotonic()+seconds
                    while not original_gone(row) and time.monotonic()<deadline: time.sleep(.05)
                result['exit_observed']=original_gone(row)
            except BaseException as error:
                result.update(exit_observed=False,error=repr(error))
            finally:
                if fd is not None: os.close(fd)
            results.append(result)
        return {'observed':observed,'children':results,
                'cleanup_confirmed':bool(results) and all(x['exit_observed'] for x in results) and not self.errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--godot', type=Path, required=True)
    parser.add_argument('--candidate-wheel', type=Path, required=True)
    parser.add_argument('--candidate-commit', required=True)
    parser.add_argument('--full-capture', action='store_true')
    args = parser.parse_args()
    source, out, godot = args.source.resolve(), args.output.resolve(), args.godot.resolve()
    assert args.candidate_commit == CANDIDATE and sha(args.candidate_wheel) == WHEEL_SHA
    assert godot.is_file() and not out.exists() and source.is_dir()
    assert shutil.disk_usage(out.parent).free >= 4 * 1024**3
    available_kib=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
    assert available_kib >= 2800*1024, 'Native qualification memory guard'
    for name, version in EXPECTED.items():
        assert importlib.metadata.version(name) == version
    frozen = json.loads((ROOT/'source-inputs.json').read_text())
    files = frozen['files']
    assert len(files) == 5
    for name, expected in files.items():
        assert (source/name).is_file() and not (source/name).is_symlink()
        assert sha(source/name) == expected['sha256'] and (source/name).stat().st_size == expected['bytes']
    out.mkdir()
    write(out/'source-inputs.json', frozen)
    home = out/'home'; home.mkdir()
    for name in ('config', 'cache', 'data', 'registry'):
        (out/name).mkdir()
    os.environ.update(HOME=str(home), XDG_CONFIG_HOME=str(out/'config'),
                      XDG_CACHE_HOME=str(out/'cache'), XDG_DATA_HOME=str(out/'data'),
                      DCC_MCP_REGISTRY_DIR=str(out/'registry'), DCC_MCP_CLI_NO_AUTO_GATEWAY='true')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    os.environ.update(DCC_MCP_GODOT_BRIDGE_PORT=str(port), DCC_MCP_GODOT_BRIDGE_URL=f'ws://127.0.0.1:{port}')
    import dcc_mcp_godot
    package_root=Path(dcc_mcp_godot.__file__).resolve().parent
    installed_members={}
    with zipfile.ZipFile(args.candidate_wheel) as wheel:
        for name in wheel.namelist():
            if not name.startswith('dcc_mcp_godot/') or name.endswith('/'):
                continue
            relative=Path(name).relative_to('dcc_mcp_godot')
            assert '..' not in relative.parts
            target=package_root/relative
            digest=hashlib.sha256(wheel.read(name)).hexdigest()
            assert target.is_file() and sha(target)==digest, 'Installed wheel payload mismatch: '+name
            installed_members[str(relative)]=digest
    assert installed_members and 'server.py' in installed_members
    extras=[str(p.relative_to(package_root)) for p in package_root.rglob('*') if p.is_file() and p.suffix in ('.py','.gd','.yaml') and str(p.relative_to(package_root)) not in installed_members]
    assert not extras, extras
    write(out/'installed-wheel-members.json',installed_members)
    from dcc_mcp_godot.bridge import get_bridge
    from dcc_mcp_godot.server import GodotMcpServer
    project = out/'control-project'; project.mkdir()
    for name in files:
        shutil.copyfile(source/name, project/name)
    original_project = (project/'project.godot').read_bytes()
    assert b'[editor_plugins]' not in original_project and b'DccMcpRuntimePeer' not in original_project
    shutil.copytree(Path(dcc_mcp_godot.__file__).parent/'godot_addon/addons', project/'addons')
    (project/'project.godot').write_bytes(original_project + b'\n[editor_plugins]\nenabled=PackedStringArray("res://addons/dcc_mcp_godot/plugin.cfg")\n')
    helper_source = (ROOT/'native_repair.gd').read_text()
    # Helper is sent by the actual typed create_script tool, not copied in as a claimed call.
    receipts, schemas = [], {}
    report = {'passed':False, 'candidate_commit':CANDIDATE, 'candidate_wheel_sha256':WHEEL_SHA,
              'versions':EXPECTED, 'source':frozen, 'helper_sha256':sha(ROOT/'native_repair.gd'),
              'route':'official typed MCP editor script / native Movie Maker / PCKPacker',
              'full_capture_requested':args.full_capture, 'captures':[], 'encoding_pending':True}
    server = editor = verification = None
    movie_watchers = []
    log = (out/'editor.log').open('w')

    def rpc(method, params):
        request = {'jsonrpc':'2.0', 'id':len(receipts)+1, 'method':method, 'params':params}
        row = {'request':request, 'outcome':'submitted_unknown', 'sent_monotonic':time.monotonic()}
        receipts.append(row); write(out/'mcp-raw.json', receipts)
        try:
            req = urllib.request.Request(server.mcp_url, data=json.dumps(request).encode(),
                headers={'Content-Type':'application/json','Accept':'application/json,text/event-stream'})
            with urllib.request.urlopen(req, timeout=90) as response:
                raw = response.read(); row['http_status'] = response.status
            row.update(raw_base64=base64.b64encode(raw).decode(), raw_sha256=hashlib.sha256(raw).hexdigest())
            text = raw.decode()
            body = json.loads([line[6:] for line in text.splitlines() if line.startswith('data: ')][-1]) if text.startswith(('data:', 'event:')) else json.loads(text)
            row.update(response=body, outcome='response_received')
            if 'error' in body or body.get('result',{}).get('isError'):
                raise RuntimeError('MCP error; no request replay: '+json.dumps(body))
            return body.get('result', {})
        except Exception as error:
            row['exception'] = repr(error)
            raise
        finally:
            write(out/'mcp-raw.json', receipts)

    def inventory():
        cursor = None
        for _ in range(30):
            page = rpc('tools/list', {'cursor':cursor} if cursor else {})
            schemas.update({t['name']:t for t in page['tools']})
            cursor = page.get('nextCursor')
            if not cursor:
                write(out/'tool-schemas.json', schemas); return
        raise RuntimeError('Tool inventory did not terminate')

    def call(name, params):
        matches = [key for key in schemas if key == name or key.endswith('__'+name)]
        assert len(matches) == 1, (name, matches)
        value = envelope(rpc('tools/call', {'name':matches[0], 'arguments':params}))
        assert isinstance(value, dict) and value.get('success') is not False
        if value.get('status') == 'completed' and isinstance(value.get('result'),dict):
            value = value['result']
        context = value.get('context', value)
        assert isinstance(context, dict) and context.get('valid') is not False
        return context

    def script(method, arguments=None):
        value = call('execute_editor_script', {'path':'res://prism_repair.gd','method':method,
            'arguments':arguments or {},'budget_ms':50,'chunked':False})
        assert value.get('executed') is True and isinstance(value.get('result'), dict), value
        assert value.get('budget_exceeded') is False, value
        return value['result']

    def wait_inspect(predicate, timeout=20):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            assert editor.poll() is None
            sample = script('inspect')
            if predicate(sample): return sample
            time.sleep(.2)
        raise TimeoutError('Native readback did not reach the required boundary')

    try:
        server = GodotMcpServer(port=0,gateway_port=0,registry_dir=str(out/'registry'),
            enable_gateway_failover=False,enable_telemetry=False,enable_checkpoint_persistence=False)
        server.register_builtin_actions(); server.start()
        editor = subprocess.Popen([str(godot),'--editor','--audio-driver','Dummy','--path',str(project),
            '--rendering-method','gl_compatibility','--rendering-driver','opengl3'],
            stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
        deadline = time.monotonic()+90
        while not get_bridge().is_connected():
            assert editor.poll() is None and time.monotonic()<deadline
            time.sleep(.2)
        rpc('initialize', {'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'prism-ecosystem-qualification','version':'1'}})
        inventory(); call('load_skill', {'skill_names':['godot-script','godot-editor','godot-scene-management']}); inventory()
        for required in ('create_script','validate_script','execute_editor_script','play_scene'):
            matches=[name for name in schemas if name==required or name.endswith('__'+required)]
            assert len(matches)==1 and isinstance(schemas[matches[0]].get('inputSchema'),dict), required
        written = call('create_script', {'path':'res://prism_repair.gd','source':helper_source,'overwrite':False})
        assert written.get('written') is True
        validated = call('validate_script', {'path':'res://prism_repair.gd'})
        assert validated.get('valid') is True
        native_identity=script('inspect')
        assert all(native_identity['engine'][k]==v for k,v in {'major':4,'minor':6,'patch':3,'status':'stable','build':'official'}.items()) and native_identity['display_driver'] != 'headless'
        assert native_identity['rendering_method']=='gl_compatibility' and native_identity['pid']==editor.pid
        report['native_identity']=native_identity
        for count in ([3,450] if args.full_capture else [3]):
            folder = out/f'frames-{count}'; folder.mkdir()
            before = script('snapshot'); write(out/f'before-{count}.json', before)
            try:
                configured = script('configure', {'frames':count,'movie_file':str(folder/'frame.png'),'before':before})
                actual = wait_inspect(lambda x: x['live']['process_frame']>configured['configured_frame'] and
                    x['live']['args']==configured['expected_args'] and x['live']['single'] and not x['live']['focused'] and
                    x['movie_enabled'] is True and x['fps']==30 and x['movie_file']==str(folder/'frame.png'))
                write(out/f'capture-ready-{count}.json', actual)
                log.flush(); log_start = (out/'editor.log').stat().st_size
                watcher = MovieChildren(editor,godot,project,folder/'frame.png',count)
                movie_watchers.append(watcher)
                started = call('play_scene', {'mode':'main'})
                assert started.get('playing') is True
                deadline = time.monotonic()+600
                observed_playing = False
                while time.monotonic()<deadline:
                    sample = script('inspect'); observed_playing |= sample['playing']
                    total = sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
                    assert total <= CAP_BYTES, 'Capture exceeded bounded staging cap'
                    if not sample['playing'] and len(list(folder.glob('frame*.png'))) >= count:
                        break
                    time.sleep(.2)
                else: raise TimeoutError('Capture did not end; no replay')
                child_receipt = watcher.finish()
                assert not child_receipt['monitor_errors'] and child_receipt['parameters_valid'] and len(child_receipt['children'])==1, child_receipt
                child = child_receipt['children'][0]
                deadline=time.monotonic()+10
                while not original_gone(child) and time.monotonic()<deadline:
                    time.sleep(.05)
                assert original_gone(child), 'Runtime exit/reap unconfirmed'
                write(out/f'native-child-{count}.json',child_receipt)
                log.flush()
                with (out/'editor.log').open('rb') as capture_log:
                    capture_log.seek(log_start); completed_log = capture_log.read().decode('utf-8', errors='replace')
                (out/f'capture-{count}.log').write_text(completed_log)
                assert 'Done recording movie at path:' in completed_log
                assert re.search(rf'(?m)^\s*{count} frames at 30 FPS', completed_log)
                assert 'SCRIPT ERROR:' not in completed_log and '\nERROR:' not in completed_log
                # Resolved play request, normal writer finalization, and the one
                # observed owned runtime has exited/reaped. A dead editor alone
                # never establishes this boundary.
                watcher.normal_boundary=True
                from PIL import Image
                frames = sorted(folder.glob('frame*.png'))
                assert [p.name for p in frames]==[f'frame{i:08d}.png' for i in range(count)]
                measured = []
                for path in frames:
                    with Image.open(path) as image:
                        image.load(); assert image.size==(1280,800)
                        rgba = image.convert('RGBA')
                        measured.append({'name':path.name,'sha256':sha(path),'rgba_sha256':hashlib.sha256(rgba.tobytes()).hexdigest(),'bytes':path.stat().st_size})
                assert len({x['rgba_sha256'] for x in measured}) > 1
                capture = {'frames':count,'fps':30,'size':[1280,800],'observed_playing':observed_playing,
                    'complete_decode':True,'normal_writer_finalization':True,'native_log_sha256':sha(out/f'capture-{count}.log'),'measurements':measured}
                report['captures'].append(capture); write(out/f'frames-{count}-validation.json',capture)
            finally:
                if editor.poll() is None:
                    # Never accept stop/F8 as successful movie completion.
                    state = script('inspect')
                    if not state['playing']:
                        script('restore', {'before':before})
                        restored = wait_inspect(lambda x: x['live']['args']==before['settings']['editor/run/main_run_args']['value'] and
                            x['movie_enabled']==before['movie_enabled'] and x['movie_file']==before['settings']['editor/movie_writer/movie_file']['value'] and
                            x['fps']==before['settings']['editor/movie_writer/fps']['value'] and x['project_sha256']==before['project_sha256'])
                        write(out/f'restored-{count}.json',restored)
        pack = out/'prism-tide.pck'
        result = script('pack_sources', {'source_root':str(source),'output_path':str(pack),
            'sha256':{name:row['sha256'] for name,row in files.items()}})
        assert result.get('packed') is True and result['output_sha256']==sha(pack)
        report['pack_creation']=result
        report['editor_cleanup']=stop_owned(editor); editor=None
        assert report['editor_cleanup']['cleanup_confirmed']
        server.stop(); server=None
        empty = out/'empty-verification'; empty.mkdir()
        with (out/'pack-verification.log').open('w') as verify_log:
            verification=subprocess.Popen([str(godot),'--headless','--path',str(empty),'--main-pack',str(pack),
                '--script',str(ROOT/'verify_pack.gd'),'--','--test',str(out/'source-inputs.json')],
                stdout=verify_log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
            assert verification.wait(timeout=60)==0
        native_log=(out/'pack-verification.log').read_text()
        members=[json.loads(x.removeprefix('PRISM_PACK_MEMBERS ')) for x in native_log.splitlines() if x.startswith('PRISM_PACK_MEMBERS ')]
        checks=[json.loads(x.removeprefix('PRISM_TEST ')) for x in native_log.splitlines() if x.startswith('PRISM_TEST ')]
        assert len(members)==len(checks)==1 and members[0]['passed'] is True
        assert members[0]['members']=={name:row['sha256'] for name,row in files.items()}
        assert checks[0]['passed'] is True and len(checks[0]['checks'])==17 and all(v is True for v in checks[0]['checks'].values())
        assert 'SCRIPT ERROR:' not in native_log and '\nERROR:' not in native_log
        for name,row in files.items(): assert sha(source/name)==row['sha256']
        for name in files:
            if name!='project.godot': assert sha(project/name)==files[name]['sha256']
        report.update(passed=True,pack_reopen={'members':members[0],'logic':checks[0]},
            note='Actual source-packed PCK and native frames only; MP4/hero/delivery review still pending.')
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        # Each cleanup is independent: one failure must not skip other owned resources.
        cleanup_errors=[]
        report['movie_children_cleanup']=[]
        if editor is not None and not report['passed']:
            try:
                boundary=freeze_owned(editor,str(godot));report['failure_quiescence']=boundary
                if boundary.get('frozen'):
                    if movie_watchers:
                        movie_watchers[-1].finish()
                        movie_watchers[-1].scan_once()  # Frozen parent cannot spawn a late child.
                    editor.kill();editor.wait(timeout=5)  # Failure only; never resume pending RPCs.
                elif movie_watchers and not all(w.normal_boundary for w in movie_watchers):
                    cleanup_errors.append('Editor exited before final child census; scope uncertain')
            except BaseException as error:
                cleanup_errors.append('Editor quiescence: '+repr(error))
        for watcher in movie_watchers:
            try:
                item=watcher.cleanup()
                report['movie_children_cleanup'].append(item)
                if not item['cleanup_confirmed']: cleanup_errors.append('Movie child cleanup unconfirmed')
            except BaseException as error:
                cleanup_errors.append('Movie cleanup: '+repr(error))
        for name,process in [('verification_cleanup',verification),('editor_cleanup',editor)]:
            if process is None and name in report:
                continue
            try:
                item=stop_owned(process);report[name]=item
                if item.get('cleanup_confirmed') is False: cleanup_errors.append(name+' unconfirmed')
            except BaseException as error:
                cleanup_errors.append(name+': '+repr(error))
        try:
            if server is not None: server.stop()
        except BaseException as error:
            cleanup_errors.append('Server cleanup: '+repr(error))
        if cleanup_errors:
            report.update(passed=False,cleanup_errors=cleanup_errors)
        try: log.close()
        finally: write(out/'summary.json',report)
    assert report['passed'] is True, 'Production/cleanup qualification incomplete'
    print(json.dumps(report, ensure_ascii=True))

if __name__=='__main__':
    main()
