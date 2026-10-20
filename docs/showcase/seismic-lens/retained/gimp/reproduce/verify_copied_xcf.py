#!/usr/bin/env python3
"""Version 1: typed-MCP verification of copied final XCF bytes. Default is read-only.

The operator may hold the original task master and inputs aside first. This helper
never renames originals. An optional operator file lists original paths that must
remain absent before native launch, during each MCP call and after native work.
No source or input from those paths is consumed. A copy of the packaged XCF is
opened under the fresh run root, with the exact qualified canonical tree, complete
load-time metadata and all 2560x1600 decoded RGBA pixels independently compared.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import asyncio
import json
from pathlib import Path
from reproduce_gimp import (
    PREP, PLUGIN_SHA, no_symlinks, bound_source_check,
    fcntl, re, shutil, os, secrets, threading, signal, subprocess, time,
    asdict, urlsplit,
)
from lifecycle import (
    BUDGET, DEADLINE, FREE_FLOOR, Run, canonical_image,
    close_checkpoint_arguments, exception_tree, field, has_failure,
    image_from_result, port_closed, require, sha, unwrap,
    unused_loopback_port, verify_clean_checkpoint,
)
from png_readback import decode_png, rgba_sha
from xcf_metadata_readback import verify_native_text_parasites, metadata_privacy_categories
from package_integrity import verify_package


def assert_absent(paths):
    for path in paths:
        require(not path.exists() and not path.is_symlink(), 'Original path is still available: ' + str(path))


def read_absence_plan(path, package_root, run_root):
    if path is None:
        return []
    path = no_symlinks(path)
    require(path.is_file() and path.stat().st_size < 65536, 'Absence plan must be a bounded regular file')
    values = json.loads(path.read_text())
    require(isinstance(values, list) and 1 <= len(values) <= 32 and all(isinstance(x, str) for x in values), 'Expected 1..32 original paths')
    paths = [Path(x) for x in values]
    for item in paths:
        require(item.is_absolute() and '..' not in item.parts and item != Path('/'), 'Unsafe original-path assertion')
        require(not package_root.is_relative_to(item) and not run_root.is_relative_to(item), 'Package/run root is inside a required-absent path')
    assert_absent(paths)
    return paths


def check_delivery(package_root, source_root, wheel):
    integrity = verify_package(package_root)
    baseline = json.loads((package_root / 'evidence/qualified-master-baseline.json').read_text())
    xcf = package_root / 'native/gimp/seismic-lens-master.xcf'
    png = package_root / 'native/gimp/seismic-lens-master.png'
    require(sha(xcf) == baseline['xcf']['sha256'] == '8efc1515de37d6e917d0b55bdfa24a8c9faae087f2cbe63b60d0f1aa1c7c09e5', 'Packaged native XCF differs from qualification')
    require(sha(png) == baseline['png']['sha256'] == '43962deba479131f476baaa7c33854292f5d36404420e0c5804c72fbad288594', 'Packaged reference PNG differs from qualification')
    pixels = decode_png(png)
    require(list(pixels[:2]) == [2560, 1600] and rgba_sha(pixels) == baseline['rgba_sha256'], 'Qualified RGBA identity mismatch')
    check, _ = bound_source_check(source_root, PREP / 'adapter-package-bindings.json', wheel)
    check.update(package_integrity=integrity, source_xcf_sha256=sha(xcf), source_png_sha256=sha(png),
                 baseline_sha256=sha(package_root / 'evidence/qualified-master-baseline.json'))
    return check, baseline, pixels


async def workflow(run, baseline, expected_pixels, status, absent_paths):
    import httpx
    import jsonschema
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    catalog = {}
    checkpoints = []
    canonical = baseline['canonical_image']
    copied = run.root / 'copied-master.xcf'
    export = run.root / 'copied-master-export.png'
    metadata_checks = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, read=180)) as http:
        async with streamable_http_client(run.server.mcp_url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                assert_absent(absent_paths)
                run.trace({'kind':'initialize','response':(await session.initialize()).model_dump(mode='json')})
                async def discover():
                    found, cursor, pages = {}, None, 0
                    while True:
                        run.budget(); assert_absent(absent_paths)
                        page = await session.list_tools(cursor=cursor)
                        run.trace({'kind':'tools/list','request_cursor':cursor,'response':page.model_dump(mode='json')})
                        found.update({tool.name:tool.model_dump(mode='json') for tool in page.tools})
                        cursor=page.nextCursor; pages+=1
                        require(pages <= 32, 'Unexpected tools pagination length')
                        if not cursor: return found
                def actual(logical):
                    names=[name for name in catalog if name==logical or name.endswith('__'+logical)]
                    require(len(names)==1, 'Missing/ambiguous discovered tool: '+logical)
                    return names[0]
                async def call(logical,args):
                    run.budget(); assert_absent(absent_paths); name=actual(logical)
                    jsonschema.validate(args,catalog[name]['inputSchema'])
                    raw=(await session.call_tool(name,args)).model_dump(mode='json')
                    run.trace({'kind':'tools/call','tool':name,'arguments':args,'response':raw})
                    require(not raw.get('isError'), 'MCP tool error: '+name)
                    payload=unwrap(raw); require(not has_failure(payload), 'Tool returned failure: '+name)
                    return payload
                async def complete(logical,args):
                    result=await call(logical,args); job=field(result,'job_id')
                    if job is None: return result
                    began=time.monotonic()
                    while time.monotonic()-began < 180:
                        state=await call('jobs_get_status',{'job_id':job,'include_result':True})
                        terminal=field(state,'status')
                        if terminal=='completed':
                            require(not has_failure(state),'Failed result inside completed native job'); return state
                        require(terminal not in ('failed','cancelled','interrupted'),'Native job terminal failure: '+str(terminal))
                        await asyncio.sleep(.2)
                    raise TimeoutError('Native job deadline reached; no mutation replay')
                catalog=await discover()
                await call('search_skills',{'query':'gimp'})
                await call('get_skill_info',{'skill_name':'gimp-session'})
                await call('load_skill',{'skill_name':'gimp-session'})
                catalog=await discover(); run.write('discovered-tool-catalog.json',catalog)
                for logical in ('get_status','open_image','inspect_image','export_image','save_image','close_image','list_images'): actual(logical)
                native_status=await complete('get_status',{})
                for key in ('gimp_pid','plugin_pid','main_thread_id','plugin_module_path','allowed_roots','gimp_version'):
                    require(field(native_status,key)==status[key],'Native identity changed: '+key)
                opened=await complete('open_image',{'path':str(copied)})
                image_id=field(opened,'image_id'); require(type(image_id) is int and image_id>0,'No owned open-image ID')
                info=image_from_result(await complete('inspect_image',{'image_id':image_id,'include_metadata':True}))
                require(info['bridge_owned_display'] is True and info['image_id']==image_id,'Opened image is not owned')
                require(canonical_image(info)==canonical,'Copied XCF canonical hierarchy/text/font/geometry differs')
                require(info['metadata']==baseline['metadata'],'Copied XCF complete load-time metadata differs')
                metadata_checks['after_load']=verify_native_text_parasites(copied,info)
                run.write('native-image-loaded.json',info)
                await complete('export_image',{'image_id':image_id,'path':str(export),'overwrite':False})
                pixels=decode_png(export); require(pixels==expected_pixels,'Copied XCF full exported RGBA differs')
                after=image_from_result(await complete('inspect_image',{'image_id':image_id,'include_metadata':True}))
                require(canonical_image(after)==canonical,'Export changed canonical tree')
                metadata_checks['after_export']=verify_native_text_parasites(copied,after)
                args=close_checkpoint_arguments(after,canonical,{'$REOPENED':image_id},{image_id},run.root)
                if args is not None:
                    result=await complete('save_image',args); saved=Path(args['path'])
                    require(saved.read_bytes().startswith(b'gimp xcf') and field(result,'sha256')==sha(saved),'Checkpoint is not hash-bound native XCF')
                    clean=image_from_result(await complete('inspect_image',{'image_id':image_id,'include_metadata':True}))
                    verify_clean_checkpoint(after,clean,canonical)
                    metadata_checks['checkpoint']=verify_native_text_parasites(saved,clean)
                    checkpoints.append({'path':saved.name,'bytes':saved.stat().st_size,'sha256':sha(saved)})
                    after=clean
                require(after['bridge_owned_display'] is True and after['dirty'] is False,'Refuse close of dirty/foreign image')
                closed=await complete('close_image',{'image_id':image_id,'discard_changes':False})
                require(field(closed,'closed') is True and field(closed,'discarded_changes') is False,'Owned clean close failed')
                remaining=await complete('list_images',{}); run.write('images-after-owned-close.json',remaining)
                images=field(remaining,'images'); require(isinstance(images,list) and all(row['image_id']!=image_id for row in images),'Owned copied image remains open')
                require(sha(copied)==baseline['xcf']['sha256'],'Original copied XCF was overwritten')
                assert_absent(absent_paths)
                run.write('native-parasite-byte-checks.json',metadata_checks)
                run.write('metadata-privacy-categories.json',metadata_privacy_categories(info,run.privacy_markers))
                return {'status':'PASS_NATIVE_COPIED_XCF_PORTABILITY','schema':'d015-copied-xcf-proof-v1',
                        'copied_xcf_sha256':sha(copied),'canonical_tree_equal':True,
                        'complete_load_time_metadata_equal':True,'all_2560x1600_rgba_equal':True,
                        'rgba_sha256':rgba_sha(pixels),'native_text_parasites':metadata_checks['after_load']['matched_text_parasites'],
                        'preclose_checkpoint_artifacts':checkpoints,'original_absence_assertion_count':len(absent_paths),
                        'originals_held_aside_claimed':bool(absent_paths),'original_paths_renamed_by_runner':False,
                        'native_MCP_events':run.events,'PNG_byte_equality_claimed':False,
                        'final_binary_privacy_audit':'SEPARATE_REQUIRED','full_D015_acceptance':False}


def execute(check, baseline, expected_pixels, package_root, root, absent_paths):
    import psutil
    require(os.environ.get('DISPLAY'), 'A working ordinary DISPLAY is required; no headless fallback')
    root = no_symlinks(root)
    require(root.parent.is_dir() and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,95}', root.name), 'Invalid fresh run-root parent/name')
    require(not root.exists() and not root.is_symlink(), 'Run root must be new')
    require(shutil.disk_usage(root.parent).free > FREE_FLOOR + BUDGET, 'Insufficient admission reserve')
    lock_handle = (root.parent / 'gimp-native-lane.lock').open('a')
    fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    root.mkdir()
    for name in ('profile', 'config', 'cache', 'data-home', 'tmp', 'logs', 'registry', 'checkpoints'):
        (root / name).mkdir()
    for name in ('brushes', 'dynamics', 'fonts', 'gradients', 'palettes', 'patterns', 'plug-ins', 'scripts', 'tool-presets'):
        (root / 'profile' / name).mkdir()
    plugin = root / 'profile/plug-ins/dcc-mcp-gimp/dcc-mcp-gimp.py'
    plugin.parent.mkdir()
    shutil.copyfile(check['plugin'], plugin)
    plugin.chmod(0o755)
    require(sha(plugin) == PLUGIN_SHA, 'Staged official plugin mismatch')
    copied = root / 'copied-master.xcf'
    shutil.copyfile(package_root / 'native/gimp/seismic-lens-master.xcf', copied)
    require(sha(copied) == baseline['xcf']['sha256'], 'Copied packaged XCF changed')
    assert_absent(absent_paths)
    cpus = sorted(os.sched_getaffinity(0))[:2]
    require(len(cpus) == 2, 'Two allowed CPUs required')
    os.sched_setaffinity(0, cpus)
    bridge_port = unused_loopback_port()
    token = secrets.token_urlsafe(48)  # Ephemeral memory/environment only; never a file/argument/trace.
    os.environ.pop('DCC_MCP_GIMP_BRIDGE_TOKEN_FILE', None)
    os.environ.pop('PYTHONPATH', None)
    os.environ.pop('PYTHONHOME', None)
    os.environ.update({
        'DCC_MCP_GIMP_BRIDGE_TOKEN': token, 'DCC_MCP_GIMP_BRIDGE_HOST': '127.0.0.1',
        'DCC_MCP_GIMP_BRIDGE_PORT': str(bridge_port), 'DCC_MCP_GIMP_BRIDGE_TIMEOUT': '120',
        'DCC_MCP_GIMP_ALLOWED_ROOTS': str(root), 'GIMP3_DIRECTORY': str(root / 'profile'),
        'DCC_MCP_GATEWAY_PORT': '0', 'DCC_MCP_DISABLE_DEFAULT_SKILL_PATHS': '1',
        'DCC_MCP_DISABLE_TELEMETRY': '1', 'DCC_MCP_LOG_DIR': str(root / 'logs'),
        'DCC_MCP_JOB_STORAGE_PATH': str(root / 'jobs.sqlite'), 'DCC_MCP_CHECKPOINT_DIR': str(root / 'checkpoints'),
        'DCC_MCP_REGISTRY_DIR': str(root / 'registry'), 'DCC_MCP_GIMP_BOOTSTRAP_ERRORS': str(root / 'bootstrap-errors.jsonl'),
        'TMPDIR': str(root / 'tmp'), 'XDG_CONFIG_HOME': str(root / 'config'),
        'XDG_CACHE_HOME': str(root / 'cache'), 'XDG_DATA_HOME': str(root / 'data-home'),
        'OMP_NUM_THREADS': '2', 'GEGL_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
        'VTK_SMP_MAX_THREADS': '2', 'PYTHONDONTWRITEBYTECODE': '1',
        'PATH': '/usr/bin:/bin:' + os.environ.get('PATH', '')})
    # All adapter/Core imports follow explicit task-local environment setup.
    # -B prevents writes, not reads. Use a fresh empty lookup prefix so
    # validated adapter/Core imports cannot load the frozen environment's caches.
    require(not any(name.startswith(('dcc_mcp_gimp', 'dcc_mcp_core')) for name in sys.modules), 'Adapter/Core must not be preimported before source-bound execution')
    fresh_cache_prefix = root / 'unused-bytecode-cache'
    require(not fresh_cache_prefix.exists() and not fresh_cache_prefix.is_symlink(), 'Bytecode lookup prefix must be fresh')
    sys.pycache_prefix = str(fresh_cache_prefix)
    sys.dont_write_bytecode = True
    from dcc_mcp_gimp.bridge import GimpBridge
    from dcc_mcp_gimp.server import GimpMcpServer
    run = Run(root, token)
    run.privacy_markers = (str(root), str(package_root), str(sys.prefix), str(PREP), str(check['package']))
    run.ports.add(bridge_port)
    result, error, host_identity = None, None, None
    log_thread = None
    guard = threading.Thread(target=run.watch, daemon=True, name='owned-budget-watch')
    previous_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in previous_handlers:
        signal.signal(sig, lambda signum, frame: run.halt('Operator signal ' + str(signum)))
    try:
        run.write('launch.json', {**check, 'root': str(root), 'cpu_affinity': cpus, 'host_executable': '/usr/bin/gimp',
                  'host_binary_sha256': sha('/usr/bin/gimp'), 'profile_selector': str(root / 'profile'),
                  'allowed_roots': [str(root)], 'ephemeral_token_policy': 'Environment/in-memory only; no token file, argv or logs',
                  'aggregate_stopping_budget_bytes': BUDGET, 'minimum_free_bytes': FREE_FLOOR, 'deadline_seconds': DEADLINE})
        run.write('package-binding.json', check)
        run.write('original-absence-assertions.json', {'paths': [str(p) for p in absent_paths], 'renamed_by_runner': False})
        assert_absent(absent_paths)
        run.host = subprocess.Popen(['/usr/bin/gimp', '--new-instance', '--no-splash', '--console-messages'],
                                    cwd=root, env=dict(os.environ), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        host_identity = {'pid': run.host.pid, 'created': psutil.Process(run.host.pid).create_time(), 'owned_process_group': os.getpgid(run.host.pid)}
        run.write('owned-host.json', host_identity)
        log_thread = threading.Thread(target=run.collect_log, daemon=True, name='owned-native-log')
        log_thread.start()
        guard.start()
        bridge = GimpBridge(host='127.0.0.1', port=bridge_port, token=token, timeout=1)
        ready_deadline = time.monotonic() + 75
        status = None
        while time.monotonic() < ready_deadline:
            run.budget()
            require(run.host.poll() is None, 'Owned GIMP exited during startup; inspect native.log')
            run.bridge_attempts += 1
            try:
                status = bridge.call('gimp.get_status')
                break
            except Exception:
                time.sleep(0.5)
        require(isinstance(status, dict), 'Owned GIMP bridge did not become ready in 75 seconds')
        require(status.get('ready') is True and status.get('authenticated') is True and status.get('gimp_version') == '3.0.4', 'Native readiness/version/auth mismatch')
        require(status.get('gimp_pid') == run.host.pid and status.get('bridge_host') == '127.0.0.1' and status.get('bridge_port') == bridge_port, 'Native ownership/loopback mismatch')
        require(status.get('allowed_roots') == [str(root)] and status.get('plugin_module_path') == str(plugin), 'Native profile/plugin/root mismatch')
        require(type(status.get('main_thread_id')) is int and status.get('arbitrary_script_input') is False, 'Main-thread/typed native status unavailable')
        plugin_process = psutil.Process(status['plugin_pid'])
        require(plugin_process.ppid() == run.host.pid, 'Plugin is not child of owned host')
        run.plugin_identity = {'pid': plugin_process.pid, 'created': plugin_process.create_time()}
        listeners = [c for c in plugin_process.net_connections(kind='inet') if c.status == psutil.CONN_LISTEN and c.laddr.port == bridge_port]
        require(len(listeners) == 1 and listeners[0].laddr.ip == '127.0.0.1', 'Actual bridge listener is not owned loopback')
        run.write('native-status.json', status)
        run.server = GimpMcpServer(port=0, gateway_port=0, enable_gateway_failover=False,
                                   registry_dir=str(root / 'registry'), enable_file_logging=True,
                                   enable_job_persistence=True, enable_telemetry=False, enable_checkpoint_persistence=True,
                                   checkpoint_path=str(root / 'checkpoints/checkpoints.json'))
        require(run.server._options.gateway.port == 0 and run.server._options.gateway.enable_failover is False, 'Gateway/failover not disabled')
        require(run.server._options.observability.enable_checkpoint_persistence is True
                and run.server._options.observability.checkpoint_path == str(root / 'checkpoints/checkpoints.json'),
                'Checkpoint persistence is not explicitly task-local')
        run.write('resolved-options.json', asdict(run.server._options))
        run.server.register_builtin_actions()
        run.server.start(install_atexit_hook=False)
        endpoint = urlsplit(run.server.mcp_url)
        require(endpoint.hostname in ('127.0.0.1', 'localhost') and endpoint.port is not None, 'MCP endpoint is not loopback')
        run.ports.add(endpoint.port)
        current_listeners = [c for c in psutil.Process().net_connections(kind='inet') if c.status == psutil.CONN_LISTEN and c.laddr.port == endpoint.port]
        require(len(current_listeners) == 1 and current_listeners[0].laddr.ip in ('127.0.0.1', '::1'), 'Actual MCP listener is not owned loopback')
        result = asyncio.run(asyncio.wait_for(workflow(run, baseline, expected_pixels, status, absent_paths), timeout=DEADLINE - (time.monotonic() - run.started)))
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': run.clean(str(exc))[:1024],
                 'exception_tree': exception_tree(exc, run.clean), 'mutations_replayed': False}
        run.emergency_receipt('failure.json', error)
    finally:
        cleanup = {'owned_sigterm_requested': False, 'force_kill_used': False, 'server_stopped': False, 'host_exited': False}
        cleanup['owned_host_start_provenance'] = host_identity
        cleanup['owned_plugin_start_provenance'] = run.plugin_identity
        if run.host is not None:
            if run.host.poll() is None:
                run.host.terminate()
                cleanup['owned_sigterm_requested'] = True
            try:
                run.host.wait(timeout=15)
            except subprocess.TimeoutExpired:
                cleanup['normal_sigterm_wait_timed_out'] = True
                cleanup['remaining_owned_host_pid'] = run.host.pid
                cleanup['remaining_owned_host_start_provenance'] = host_identity
                cleanup['required_action'] = 'Parent must inspect the retained owned process; no force-kill or alternate route attempted'
            cleanup['host_returncode'] = run.host.returncode
            cleanup['host_exited'] = run.host.poll() is not None
        # Stop Core after the host wait so an in-flight bridge request can unblock.
        # Bound the stop observation and preserve any uncertain shutdown result.
        if run.server is not None:
            def stop_server():
                try:
                    run.server.stop()
                    cleanup['server_stopped'] = not run.server.is_running
                except BaseException as exc:
                    cleanup['server_stop_error'] = run.clean(str(exc))
            stop_thread = threading.Thread(target=stop_server, daemon=True, name='owned-core-stop')
            stop_thread.start()
            stop_thread.join(timeout=15)
            if stop_thread.is_alive():
                cleanup['core_stop_observation_timed_out'] = True
        else:
            cleanup['server_stopped'] = True
        deadline = time.monotonic() + 10
        while True:
            active_plugin = False
            if run.plugin_identity is not None:
                try:
                    p = psutil.Process(run.plugin_identity['pid'])
                    if p.create_time() == run.plugin_identity['created']:
                        cleanup['plugin_status'] = p.status()
                        active_plugin = p.status() != psutil.STATUS_ZOMBIE
                except psutil.NoSuchProcess:
                    cleanup['plugin_status'] = 'absent'
            cleanup['owned_plugin_exited'] = not active_plugin
            cleanup['listeners_closed'] = all(port_closed(port) for port in run.ports)
            if cleanup['owned_plugin_exited'] and cleanup['listeners_closed'] or time.monotonic() > deadline:
                break
            time.sleep(0.2)
        if log_thread is not None:
            log_thread.join(timeout=2)
        run.guard_done.set()
        if guard.ident is not None:
            guard.join(timeout=2)
        cleanup['native_log_collector_stopped'] = log_thread is None or not log_thread.is_alive()
        cleanup['normal_owned_shutdown_pass'] = all(cleanup.get(k) is True for k in ('server_stopped', 'host_exited', 'owned_plugin_exited', 'listeners_closed', 'native_log_collector_stopped'))
        cleanup['shutdown_method'] = 'Owned Popen SIGTERM then bounded wait; not an unexposed GIMP quit tool'
        cleanup['peak_observed_run_bytes'] = run.max_bytes
        cleanup['run_bytes_at_cleanup'] = run.usage()
        cleanup['free_bytes_at_cleanup'] = shutil.disk_usage(root).free
        cleanup['budget_is_stopping_threshold_not_quota'] = True
        run.emergency_receipt('cleanup.json', cleanup)
        os.environ.pop('DCC_MCP_GIMP_BRIDGE_TOKEN', None)
        for sig, previous in previous_handlers.items():
            signal.signal(sig, previous)
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
        lock_handle.close()
    if result is not None and cleanup['normal_owned_shutdown_pass'] and error is None and not run.halt_reason:
        require(run.usage() < BUDGET and shutil.disk_usage(root).free > FREE_FLOOR, 'Final budget gate failed')
        result['cleanup'] = cleanup
        result['full_D015_acceptance'] = False
        assert_absent(absent_paths)
        result['package_binding'] = check['package_integrity']
        artifact_paths = [root / 'copied-master.xcf', root / 'copied-master-export.png']
        artifact_paths.extend(root / row['path'] for row in result['preclose_checkpoint_artifacts'])
        result['artifacts'] = [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in artifact_paths]
        run.write('qualification.json', result)
        print(json.dumps({'run_root': str(root), 'status': result['status'], 'native_text_parasites': result['native_text_parasites'], 'full_D015_acceptance': False, 'MCP_events': run.events}), flush=True)
        return 0
    brief_error = None if error is None else {key: error[key] for key in ('type', 'message', 'mutations_replayed')}
    print(json.dumps({'run_root': str(root), 'status': 'FAIL_OR_BLOCKED_NO_NATIVE_PASS_CLAIM',
                      'error': brief_error, 'private_failure_receipt': str(root / 'failure.json'), 'cleanup': cleanup}), flush=True)
    return 1



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Read-only package/runtime check; default')
    mode.add_argument('--run', action='store_true', help='Launch one owned native GIMP and verify copied bytes')
    parser.add_argument('--run-root', type=Path)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--originals-absent-json', type=Path,
                        help='Operator-owned JSON array of absolute original paths already held aside')
    args = parser.parse_args()
    package_root = no_symlinks(PREP.parent)
    check, baseline, pixels = check_delivery(package_root, args.source_root, args.wheel)
    if not args.run:
        print(json.dumps({**check, 'status':'COPIED_XCF_STATIC_CHECK_READY_NATIVE_NOT_EXECUTED'}, indent=2)); return 0
    require(args.run_root is not None, '--run-root must name a fresh output directory')
    root = no_symlinks(args.run_root)
    absent = read_absence_plan(args.originals_absent_json, package_root, root)
    return execute(check, baseline, pixels, package_root, root, absent)


if __name__ == '__main__':
    raise SystemExit(main())
