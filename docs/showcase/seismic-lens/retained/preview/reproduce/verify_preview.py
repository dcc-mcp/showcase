#!/usr/bin/env python3
"""Pinned candidate preview fixture. Default --check is file-only; --run owns one GIMP host.

The launch, budget, SDK, and normal shutdown lifecycle is adapted from the audited
copied-XCF recipe. It never launches on import and never force-kills a process.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import asyncio
import fcntl
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit
from binding import PREP, PLUGIN_SHA, no_symlinks, check_delivery
from lifecycle import (
    BUDGET, DEADLINE, FREE_FLOOR, Run, canonical_image, exception_tree, field, has_failure,
    image_from_result, port_closed, require, sha, unwrap, unused_loopback_port,
)
from png_readback import decode_png, rgba_sha
from xcf_metadata_readback import verify_native_text_parasites


def assert_absent(paths):
    require(paths == [], 'Preview fixture does not consume an absence plan')


def require_active_image_id(completed_result, intended_image_id):
    """Read the explicit completed-job image envelope and fail closed on absent IDs."""
    require(type(intended_image_id) is int and intended_image_id > 0,
            'Intended source image ID must be a positive integer')
    completed = unwrap(completed_result)
    require(isinstance(completed, dict), 'Active-image completed result must be an object')
    native_result = completed.get('result')
    require(isinstance(native_result, dict), 'Active-image native result is missing')
    context = native_result.get('context')
    require(isinstance(context, dict), 'Active-image context is missing')
    image = context.get('image')
    require(isinstance(image, dict), 'Active-image object is missing')
    image_id = image.get('image_id')
    require(type(image_id) is int and image_id > 0,
            'Active-image ID must be a positive integer')
    require(image_id == intended_image_id, 'Active image differs from intended preview source')
    return image_id


async def workflow(run, baseline, expected_pixels, status, absent_paths):
    import httpx
    import jsonschema
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    catalog = {}
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
                for logical in ('get_status','open_image','inspect_image','export_image','export_preview','save_image','close_image','list_images','create_image','get_active_image'): actual(logical)
                native_status=await complete('get_status',{})
                for key in ('gimp_pid','plugin_pid','main_thread_id','plugin_module_path','allowed_roots','gimp_version'):
                    require(field(native_status,key)==status[key],'Native identity changed: '+key)

                require(field(native_status,'command_count') == 25, 'Candidate catalog count differs')

                async def inspect(image_id):
                    result = await complete('inspect_image', {'image_id':image_id, 'include_metadata':True})
                    info = image_from_result(result)
                    for key in ('name','file_name','file_path_allowed','selected_layer_ids'):
                        info[key] = field(result,key)
                    return info

                async def image_ids():
                    rows = field(await complete('list_images',{}), 'images')
                    require(isinstance(rows,list), 'Missing native image inventory')
                    return [row['image_id'] for row in rows]

                async def preview_and_verify(image_id, name, bounds, expected_dimensions):
                    before = await inspect(image_id)
                    ids_before = await image_ids()
                    active_before = require_active_image_id(
                        await complete('get_active_image',{}), image_id)
                    destination = run.root / name
                    result = await complete('export_preview', {'image_id':image_id,
                        'path':str(destination), 'max_width':bounds[0], 'max_height':bounds[1]})
                    require(field(result,'output_dimensions') == expected_dimensions,
                            'Preview response dimensions differ')
                    require(field(result,'published') is True and field(result,'interpolation') == 'nohalo',
                            'Preview publication or native interpolation was not attested')
                    for flag in ('temporary_image_deleted','context_restored'):
                        require(field(result,flag) is True, 'Preview native cleanup not attested')
                    require(field(result,'source_image_mutated') is False
                            and field(result,'upscaled') is False, 'Preview preservation contract failed')
                    fingerprint = field(result,'source_state_sha256')
                    require(isinstance(fingerprint,str) and re.fullmatch(r'[0-9a-f]{64}',fingerprint),
                            'Missing bounded native source-state fingerprint')
                    require(field(result,'sha256') == sha(destination), 'Preview digest differs')
                    after = await inspect(image_id)
                    require(after == before, 'Preview changed hierarchy/text/metadata/selection/dirty state')
                    require(await image_ids() == ids_before, 'Temporary image remains or image order changed')
                    active_after = require_active_image_id(
                        await complete('get_active_image',{}), image_id)
                    require(active_after == active_before, 'Preview changed active-image readback')
                    require(not list(run.root.glob('.dcc-preview-*')), 'Preview staging was retained')
                    pixels = decode_png(destination)
                    require(list(pixels[:2]) == expected_dimensions, 'Native PNG decoded dimensions differ')
                    run.write(name + '.proof.json', {'before':before,'after':after,
                        'native_source_state_sha256':fingerprint,'source_and_active_state_equal':True,
                        'intended_source_image_id':image_id,
                        'active_image_id_before':active_before,'active_image_id_after':active_after,
                        'images_before_after':ids_before,'output_rgba_sha256':rgba_sha(pixels),
                        'temporary_images_and_staging_absent':True})
                    return pixels

                async def expect_native_rejection(image_id, name):
                    before = await inspect(image_id)
                    ids_before = await image_ids()
                    target = run.root / name
                    args = {'image_id':image_id, 'path':str(target),
                            'max_width':1600, 'max_height':1600}
                    raw = (await session.call_tool(actual('export_preview'),args)).model_dump(mode='json')
                    run.trace({'kind':'tools/call','tool':actual('export_preview'),
                               'arguments':args,'response':raw,'expected_rejection':True})
                    result = unwrap(raw)
                    job = field(result,'job_id')
                    rejected = raw.get('isError') is True or has_failure(result)
                    if job is not None:
                        began = time.monotonic()
                        while time.monotonic()-began < 180:
                            poll_args = {'job_id':job,'include_result':True}
                            raw = (await session.call_tool(actual('jobs_get_status'),poll_args)).model_dump(mode='json')
                            run.trace({'kind':'tools/call','tool':actual('jobs_get_status'),
                                       'arguments':poll_args,'response':raw,'expected_rejection':True})
                            result = unwrap(raw)
                            terminal = field(result,'status')
                            if terminal in ('failed','completed','cancelled','interrupted'):
                                rejected = terminal == 'failed' or has_failure(result)
                                break
                            run.budget()
                            await asyncio.sleep(.2)
                        else:
                            raise TimeoutError('Expected-rejection job did not terminate; no replay')
                    require(rejected, 'Invalid preview was not rejected')
                    require(not target.exists() and (await inspect(image_id)) == before
                            and await image_ids() == ids_before, 'Rejected preview changed source or output')
                    require(not list(run.root.glob('.dcc-preview-*')), 'Rejected preview retained staging')

                async def save_clean(image_id, name):
                    path = run.root / name
                    result = await complete('save_image', {'image_id':image_id,'path':str(path)})
                    require(field(result,'sha256') == sha(path) and path.read_bytes().startswith(b'gimp xcf'),
                            'Native checkpoint is not hash-bound XCF')
                    require((await inspect(image_id))['dirty'] is False, 'Checkpoint did not clean image')
                    return path

                async def close_clean(image_id):
                    info = await inspect(image_id)
                    require(info['bridge_owned_display'] is True and info['dirty'] is False,
                            'Refuse dirty/foreign close')
                    closed = await complete('close_image', {'image_id':image_id,'discard_changes':False})
                    require(field(closed,'closed') is True and field(closed,'discarded_changes') is False,
                            'Owned clean close failed')

                opened = await complete('open_image', {'path':str(copied)})
                image_id = field(opened,'image_id')
                require(type(image_id) is int and image_id > 0, 'Missing copied-master image ID')
                info = await inspect(image_id)
                require(canonical_image(info) == canonical and info['metadata'] == baseline['metadata'],
                        'Copied XCF hierarchy or complete load-time metadata differs')
                metadata_checks['after_load'] = verify_native_text_parasites(copied,info)
                run.write('copied-master-loaded.json',info)
                await complete('export_image', {'image_id':image_id,'path':str(export)})
                before_pixels = decode_png(export)
                require(before_pixels == expected_pixels, 'Copied master full source pixels differ')
                await save_clean(image_id,'master-before-preview.xcf')
                await expect_native_rejection(image_id,'unsupported-preview.jpg')
                preview = await preview_and_verify(image_id,'seismic-lens-preview-1600.png',
                                                   [1600,1600],[1600,1000])
                require(all(alpha == 255 for alpha in preview[2][3::4]), 'Opaque master alpha changed')
                require(len(set(preview[2])) > 32, 'Master preview has implausibly flat pixel content')
                after_export = run.root / 'master-after-preview.png'
                await complete('export_image', {'image_id':image_id,'path':str(after_export)})
                require(decode_png(after_export) == before_pixels == expected_pixels,
                        'Preview changed any source RGBA pixel')
                checkpoint = await save_clean(image_id,'master-after-preview.xcf')
                after = await inspect(image_id)
                require(canonical_image(after) == canonical, 'Preview altered native text/hierarchy')
                metadata_checks['after_preview'] = verify_native_text_parasites(checkpoint,after)
                require(sha(copied) == baseline['xcf']['sha256'], 'Input XCF was overwritten')
                await close_clean(image_id)

                # Reopen the native preview, verify its actual dimensions/alpha, export
                # it natively again, and compare all decoded pixels with the preview.
                reopened = await complete('open_image',{'path':str(run.root/'seismic-lens-preview-1600.png')})
                preview_id = field(reopened,'image_id')
                native_preview = await inspect(preview_id)
                require([native_preview['width'],native_preview['height']] == [1600,1000],
                        'GIMP preview reopen dimensions differ')
                reopen_export = run.root/'preview-reopened.png'
                await complete('export_image', {'image_id':preview_id,'path':str(reopen_export)})
                require(decode_png(reopen_export) == preview, 'Native preview reopen pixels/alpha differ')
                await save_clean(preview_id,'preview-reopened.xcf')
                await close_clean(preview_id)

                # A tiny native RGBA image proves no-upscale and actual alpha readback.
                made = await complete('create_image', {'width':7,'height':13,'name':'Preview alpha fixture',
                                                       'background_color':[80,120,220,128]})
                fixture_id = field(made,'image_id')
                fixture_before = await inspect(fixture_id)
                require(fixture_before['dirty'] is True, 'Fixture must exercise preservation of dirty state')
                alpha_full = await preview_and_verify(fixture_id,'alpha-no-upscale.png',[2048,2048],[7,13])
                require(all(a == 128 for a in alpha_full[2][3::4]), 'No-upscale PNG lost half alpha')
                alpha_small = await preview_and_verify(fixture_id,'alpha-downscaled.png',[5,6],[3,6])
                require(all(a == 128 for a in alpha_small[2][3::4]), 'Scaled PNG lost half alpha')
                require((await inspect(fixture_id)) == fixture_before, 'Dirty RGBA source state changed')
                await save_clean(fixture_id,'alpha-source.xcf')
                await close_clean(fixture_id)
                require(await image_ids() == [], 'Fixture left native images open')
                require(sha(copied) == baseline['xcf']['sha256'], 'Copied native input bytes changed')
                run.write('native-text-parasite-checks.json',metadata_checks)
                return {'status':'PASS_NATIVE_PREVIEW_EXPORT', 'schema':'gimp-native-preview-v1',
                        'output_dimensions':[1600,1000], 'native_MCP_events':run.events,
                        'master_source_rgba_before_after_equal':True,
                        'master_input_xcf_sha256':sha(copied),
                        'native_reopen_preview_rgba_equal':True,
                        'source_hierarchy_text_metadata_selection_dirty_active_preserved':True,
                        'no_upscale_dimensions':[7,13], 'rounded_aspect_dimensions':[3,6],
                        'native_rgba_alpha_preserved':True,
                        'temporary_images_and_staging_absent':True,
                        'preclose_checkpoint_artifacts':[],
                        'artifact_names':['copied-master.xcf','copied-master-export.png',
                            'seismic-lens-preview-1600.png','master-before-preview.xcf',
                            'master-after-preview.xcf','master-after-preview.png','preview-reopened.png',
                            'preview-reopened.xcf','alpha-source.xcf','alpha-no-upscale.png',
                            'alpha-downscaled.png'],
                        'full_D015_acceptance':False}


def finalize_cleanup(run, cleanup, previous_handlers, lock_handle):
    """Evidence failures never prevent release of process-local lifecycle state."""
    errors=cleanup.setdefault('cleanup_errors',[])
    def record(stage, exc):
        errors.append({'stage':stage,'type':type(exc).__name__,
                       'message':run.clean(str(exc))[:512]})
        cleanup['normal_owned_shutdown_pass']=False
    try:
        cleanup['peak_observed_run_bytes']=run.max_bytes
        cleanup['budget_is_stopping_threshold_not_quota']=True
        try:
            cleanup['run_bytes_at_cleanup']=run.usage()
            cleanup['free_bytes_at_cleanup']=shutil.disk_usage(run.root).free
        except BaseException as exc:
            record('cleanup_metrics',exc)
    finally:
        run.guard_done.set()
        os.environ.pop('DCC_MCP_GIMP_BRIDGE_TOKEN',None)
        cleanup['ephemeral_environment_token_removed']=True
        for sig,previous in previous_handlers.items():
            try:
                signal.signal(sig,previous)
            except BaseException as exc:
                record('signal_handler_restore',exc)
        try:
            fcntl.flock(lock_handle,fcntl.LOCK_UN)
        except BaseException as exc:
            record('lane_unlock',exc)
        finally:
            try:
                lock_handle.close()
            except BaseException as exc:
                record('lane_handle_close',exc)
    try:
        run.emergency_receipt('cleanup.json',cleanup)
    except BaseException as exc:
        record('cleanup_receipt',exc)



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
    require(sha(plugin) == PLUGIN_SHA, 'Staged candidate plugin mismatch')
    copied = root / 'copied-master.xcf'
    shutil.copyfile(package_root / 'inputs/seismic-lens-master.xcf', copied)
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
        try:
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
        except BaseException as exc:
            cleanup['normal_owned_shutdown_pass']=False
            cleanup['cleanup_exception']=exception_tree(exc,run.clean)
        finally:
            finalize_cleanup(run,cleanup,previous_handlers,lock_handle)
    if result is not None and cleanup['normal_owned_shutdown_pass'] and error is None and not run.halt_reason:
        require(run.usage() < BUDGET and shutil.disk_usage(root).free > FREE_FLOOR, 'Final budget gate failed')
        result['cleanup'] = cleanup
        result['full_D015_acceptance'] = False
        assert_absent(absent_paths)
        result['package_binding'] = check['package_integrity']
        artifact_paths = [root / name for name in result['artifact_names']]
        artifact_paths.extend(root / row['path'] for row in result['preclose_checkpoint_artifacts'])
        result['artifacts'] = [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in artifact_paths]
        run.write('qualification.json', result)
        print(json.dumps({'run_root': str(root), 'status': result['status'], 'output_dimensions': result['output_dimensions'], 'full_D015_acceptance': False, 'MCP_events': run.events}), flush=True)
        return 0
    brief_error = None if error is None else {key: error[key] for key in ('type', 'message', 'mutations_replayed')}
    print(json.dumps({'run_root': str(root), 'status': 'FAIL_OR_BLOCKED_NO_NATIVE_PASS_CLAIM',
                      'error': brief_error, 'private_failure_receipt': str(root / 'failure.json'), 'cleanup': cleanup}), flush=True)
    return 1



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='File-only source/wheel/runtime check; default')
    mode.add_argument('--run', action='store_true', help='Explicitly launch one native GIMP host')
    parser.add_argument('--run-root', type=Path)
    args = parser.parse_args()
    package_root = no_symlinks(PREP.parent)
    check, baseline, pixels = check_delivery()
    if not args.run:
        print(json.dumps({**check, 'status': 'PREVIEW_STATIC_READY_NATIVE_NOT_EXECUTED'}, indent=2))
        return 0
    require(args.run_root is not None, '--run-root must name a fresh output directory')
    return execute(check, baseline, pixels, package_root, no_symlinks(args.run_root), [])


if __name__ == '__main__':
    raise SystemExit(main())
