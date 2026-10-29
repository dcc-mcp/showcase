"""Author five original scientific panels through the real typed ParaView MCP API."""
import argparse
import asyncio
import datetime
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

BASE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True, help='New empty output directory; never overwritten')
parser.add_argument('--input', type=Path, default=BASE.parent / 'native/paraview/data/synthetic-lens.vti')
parser.add_argument('--wheel', type=Path, required=True, help='Exact locally built public-source wheel; its hash is verified before native launch')
opts = parser.parse_args()
ROOT = opts.output.resolve()
EXPECTED_COMMIT = '4c4939b1a6ee6785d86f74461ea97ff2a34815a9'
EXPECTED_TREE = '75f8aa79611f97bdbee4c6337f713dbb7e6c7049'
WHEEL_SHA = '167b1c73796746853c348a03e4918a96eed4a24b7328587217bad0a45b516077'
INPUT_SHA = '43ade20b1f2b78149e7d948894568b599db55f5aa8f9a5ceb62050e970e93d9d'
ROOT.mkdir(exist_ok=False)
for name in ('data', 'logs', 'tmp', 'cache', 'registry'):
    (ROOT / name).mkdir()
assert os.environ.get('DISPLAY') and shutil.disk_usage(ROOT).free > 1024**3
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
os.environ.update(DCC_MCP_GATEWAY_PORT='0', DCC_MCP_DISABLE_DEFAULT_SKILL_PATHS='1',
    DCC_MCP_LOG_DIR=str(ROOT / 'logs'), TMPDIR=str(ROOT / 'tmp'),
    XDG_CACHE_HOME=str(ROOT / 'cache'), OMP_NUM_THREADS='2',
    OPENBLAS_NUM_THREADS='2', VTK_SMP_MAX_THREADS='2')
import dcc_mcp_paraview
from dcc_mcp_paraview.server import ParaViewMcpServer
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import jsonschema
import psutil

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

package = Path(dcc_mcp_paraview.__file__).parent
bindings = json.loads((BASE / 'paraview-package-bindings.json').read_text())
assert bindings['source_commit'] == EXPECTED_COMMIT and bindings['source_tree'] == EXPECTED_TREE
assert bindings['wheel_sha256'] == WHEEL_SHA and sha(opts.wheel.resolve()) == WHEEL_SHA
assert bindings['package_file_count'] == len(bindings['package_sha256']) == 24
RECIPE_SHA = sha(Path(__file__))
BINDINGS_SHA = sha(BASE / 'paraview-package-bindings.json')
for relative, expected in bindings['package_sha256'].items():
    assert sha(package / relative) == expected, 'Installed adapter bytes differ: ' + relative
for distribution in ('dcc-mcp-core','dcc-mcp-server','dcc-mcp-cli'):
    assert importlib.metadata.version(distribution) == '0.20.41'
assert importlib.metadata.version('mcp') == '1.30.0'
fixture = opts.input.resolve()
assert sha(fixture) == INPUT_SHA
shutil.copyfile(fixture, ROOT / 'data/synthetic-lens.vti')
arrays = {a.attrib['Name']: list(map(float, a.text.split())) for a in ET.fromstring(fixture.read_bytes()).iter('DataArray')}
trace, catalog, results = [], {}, []
server = ParaViewMcpServer(port=0, workspace=ROOT, registry_dir=str(ROOT / 'registry'),
    gateway_port=0, enable_gateway_failover=False, enable_telemetry=False,
    enable_file_logging=True, enable_job_persistence=True, enable_checkpoint_persistence=True,
    checkpoint_path=str(ROOT / 'checkpoints.json'))
assert server._options.gateway.port == 0 and not server._options.gateway.enable_failover

def budget():
    size = sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
    assert size < 256 * 1024**2 and shutil.disk_usage(ROOT).free > 1024**3
    return size

def save(name, obj):
    budget()
    (ROOT / name).write_text(json.dumps(obj, indent=2) + '\n')

def unwrap(raw):
    if raw.get('structuredContent') is not None:
        return raw['structuredContent']
    for c in raw.get('content', []):
        if c.get('type') == 'text':
            return json.loads(c['text'])
    return raw

def context(value):
    while isinstance(value, dict):
        assert value.get('success') is not False and not value.get('isError'), value
        if 'context' in value:
            return value['context']
        if 'result' in value:
            value = value['result']
        else:
            return value
    raise TypeError(type(value))

def close_numbers(actual, expected):
    assert len(actual) == len(expected)
    assert all(math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-7) for a, b in zip(actual, expected)), (actual, expected)

def png_pixels(path, size):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'rawvideo',
        '-pix_fmt', 'rgba', '-threads', '1', '-'], timeout=30)
    assert len(raw) == size[0] * size[1] * 4
    assert len(set(raw[i:i+4] for i in range(0, len(raw), 4))) > 32
    return hashlib.sha256(raw).hexdigest()

sections = [
    {'name': 'SectionX', 'file': 'panel-x', 'normal': [1,0,0], 'camera': [-5.8,-.1,1.2],
     'up': [0,0,-1], 'scale': 1.65, 'axis': 0, 'index': 44, 'counts': [6305,12288], 'bounds': [.2,.2,-1.6,1.6,0,2.4]},
    {'name': 'SectionY', 'file': 'panel-y', 'normal': [0,1,0], 'camera': [.2,5.9,1.2],
     'up': [0,0,-1], 'scale': 1.8, 'axis': 1, 'index': 30, 'counts': [7857,15360], 'bounds': [-2,2,-.1,-.1,0,2.4]},
    {'name': 'SectionZ', 'file': 'panel-z', 'normal': [0,0,1], 'camera': [.2,-.1,7.2],
     'up': [0,1,0], 'scale': 2.0, 'axis': 2, 'index': 48, 'counts': [5265,10240], 'bounds': [-2,2,-1.6,1.6,1.2,1.2]},
]

async def main():
    global catalog
    server.start()
    assert urllib.parse.urlsplit(server.mcp_url).hostname == '127.0.0.1'
    async with streamable_http_client(server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            trace.append({'initialize': (await session.initialize()).model_dump(mode='json')})
            async def discover():
                found, cursor = {}, None
                while True:
                    page = await session.list_tools(cursor=cursor)
                    found.update({t.name: t.model_dump(mode='json') for t in page.tools})
                    cursor = page.nextCursor
                    if cursor is None: break
                trace.append({'tools/list': list(found.values())})
                save('mcp-trace.json', trace)
                return found
            async def call(name, args):
                matches = [n for n in catalog if n == name or n.endswith('__'+name)]
                assert len(matches) == 1, (name, matches)
                actual = matches[0]
                jsonschema.validate(args, catalog[actual]['inputSchema'])
                raw = (await session.call_tool(actual, args)).model_dump(mode='json')
                trace.append({'tool': actual, 'arguments': args, 'response': raw})
                save('mcp-trace.json', trace)
                assert not raw.get('isError'), raw
                value = unwrap(raw)
                assert value.get('success') is not False, value
                return value
            async def operation(name, args):
                value = await call(name, args)
                if 'job_id' in value:
                    deadline = time.monotonic()+180
                    while True:
                        assert time.monotonic() < deadline
                        value = await call('jobs_get_status', {'job_id': value['job_id'], 'include_result': True})
                        if value['status'] == 'completed': break
                        assert value['status'] not in ['failed','cancelled','interrupted'], value
                        await asyncio.sleep(.2)
                result = context(value)
                results.append({'tool': name, 'arguments': args, 'context': result})
                save('operation-results.json', results)
                return result
            catalog = await discover()
            await call('search_skills', {'query':'paraview'})
            await call('get_skill_info', {'skill_name':'paraview-pipeline'})
            await call('load_skill', {'skill_name':'paraview-pipeline'})
            catalog = await discover()
            before = await operation('inspect_pipeline', {})
            assert before['sources'] == []
            host = before['host']
            assert host['version'] == '5.13.2' and host['pid'] == server.host_session.process.pid
            assert host['thread_id'] == host['main_thread_id'] and host['render_available']
            original = (await operation('open_dataset', {'name':'SyntheticLens','path':'data/synthetic-lens.vti'}))['source']
            assert [original['points'],original['cells']] == [510705,491520]
            native_arrays = {a['name']:a for a in original['point_arrays']}
            for name, values in arrays.items():
                close_numbers(native_arrays[name]['range'], [min(values),max(values)])
            for s in sections:
                section = (await operation('slice_plane', {'name':s['name'],'input_name':'SyntheticLens',
                    'origin':[.2,-.1,1.2],'normal':s['normal']}))['source']
                assert [section['points'],section['cells']] == s['counts'], section
                assert section['type']=='Cut' and section['triangulate'] and not section['crinkle']
                close_numbers(section['bounds'],s['bounds'])
                ids = [z*65*81+y*81+x for z in range(97) for y in range(65) for x in range(81)
                    if [x,y,z][s['axis']]==s['index']]
                sliced_arrays = {a['name']:a for a in section['point_arrays']}
                for name, values in arrays.items():
                    selected = [values[i] for i in ids]
                    close_numbers(sliced_arrays[name]['range'], [min(selected),max(selected)])
            for level in (80,150):
                result = (await operation('contour', {'name':'Delay'+str(level),'input_name':'SectionY',
                    'scalar':'SyntheticDelay_ms','values':[level]}))['source']
                assert 16 < result['points'] < 10000 and 16 < result['cells'] < 10000
                assert abs(result['bounds'][2]+.1)<1e-6 and abs(result['bounds'][3]+.1)<1e-6
                values = next(a['range'] for a in result['point_arrays'] if a['name']=='SyntheticDelay_ms')
                close_numbers(values,[level,level])
            panels=[]
            for s in sections + [
                {'name':'Delay80','file':'isoline-80','camera':[.2,5.9,1.2],'up':[0,0,-1],'scale':.5,'color':[59/255,196/255,219/255]},
                {'name':'Delay150','file':'isoline-150','camera':[.2,5.9,1.2],'up':[0,0,-1],'scale':.5,'color':[232/255,181/255,68/255]}]:
                is_section=s['name'].startswith('Section'); size=[720,480] if is_section else [1060,340]
                args={'name':s['name'],'path':s['file']+'.png','width':size[0],'height':size[1],
                    'camera_position':s['camera'],'camera_target':[.2,-.1,1.2],'camera_view_up':s['up'],
                    'camera_parallel_scale':s['scale'],'background':[11/255,16/255,23/255],
                    'show_scalar_bar':is_section,'show_orientation_axes':False,'ambient':1,'diffuse':0,'specular':0}
                if is_section: args.update(scalar='SyntheticTime_s',color_range=native_arrays['SyntheticTime_s']['range'],preset='Viridis (matplotlib)',scalar_bar_title='Time (s)',scalar_bar_position=[.85,.16],scalar_bar_length=.60,scalar_bar_thickness=12,scalar_bar_title_font_size=16,scalar_bar_label_font_size=14)
                else: args.update(solid_color=s['color'],line_width=2.5)
                await operation('render_preview',args)
                presentation=await operation('inspect_presentation',{})
                await operation('save_state',{'path':s['file']+'.pvsm','data_directory':'data'})
                await operation('reopen_state',{'path':s['file']+'.pvsm','data_directory':'data'})
                assert await operation('inspect_presentation',{}) == presentation
                await operation('capture_current_view',{'path':s['file']+'-reopened.png'})
                original_path=ROOT/(s['file']+'.png'); reopened=ROOT/(s['file']+'-reopened.png')
                assert sha(original_path)==sha(reopened)
                pixels=png_pixels(original_path,size)
                panels.append({'name':s['name'],'path':original_path.name,'bytes':original_path.stat().st_size,
                    'sha256':sha(original_path),'RGBA_sha256':pixels,'dimensions':size,'state':s['file']+'.pvsm',
                    'state_sha256':sha(ROOT/(s['file']+'.pvsm')),'loaded_measured_presentation_equal':True,
                    'reopened_capture_png_identical':True,'presentation':presentation})
                save('panels-in-progress.json',panels)
            # Copy only authored state/data, then remove the original task input path.
            # No XML rewriting and no fresh arbitrary-state trust is introduced.
            relocated = ROOT / 'relocated-native'
            (relocated / 'data').mkdir(parents=True, exist_ok=False)
            shutil.copyfile(ROOT / 'data/synthetic-lens.vti', relocated / 'data/synthetic-lens.vti')
            for p in panels:
                shutil.copyfile(ROOT / p['state'], relocated / p['state'])
                assert sha(relocated / p['state']) == p['state_sha256']
            held = ROOT / 'data-original-held'
            (ROOT / 'data').rename(held)
            relocation_checks = []
            try:
                assert not (ROOT / 'data/synthetic-lens.vti').exists()
                for p in panels:
                    loaded = await operation('reopen_state', {'path': 'relocated-native/' + p['state'], 'data_directory': 'relocated-native/data'})
                    assert loaded['relocation_verified'] is True
                    assert loaded['reader_paths'] == {'SyntheticLens': str(relocated / 'data/synthetic-lens.vti')}
                    assert await operation('inspect_presentation', {}) == p['presentation']
                    name = Path(p['path']).stem + '-relocated.png'
                    await operation('capture_current_view', {'path': 'relocated-native/' + name})
                    assert sha(relocated / name) == p['sha256']
                    relocation_checks.append({'name': p['name'], 'state_sha256': sha(relocated / p['state']), 'PNG_sha256': sha(relocated / name), 'presentation_equal_without_reapplication': True, 'original_input_path_absent': True, 'only_verified_relocated_data_used': True})
                    save('relocation-checks.json', relocation_checks)
            finally:
                assert not (ROOT / 'data').exists()
                held.rename(ROOT / 'data')
            assert len(relocation_checks) == 5
            assert sha(ROOT/'data/synthetic-lens.vti')==INPUT_SHA
            return {'status':'PASS_NATIVE_FIVE_PANEL_AUTHORING','not_final_D015_acceptance':True,
                'source_vti_sha256':INPUT_SHA,'grid_dimensions':[81,65,97],'spacing':[.05,.05,.025],'origin':[-2,-1.6,0],'synthetic_disclaimer':'Analytic illustration; illustrative units, no measured seismic data, no PDE or physics validation.',
                'source_commit':EXPECTED_COMMIT,'source_candidate_tree':EXPECTED_TREE,'wheel_sha256':WHEEL_SHA,
                'recipe_sha256':RECIPE_SHA,'package_bindings_sha256':BINDINGS_SHA,'adapter_package_sha256':bindings['package_sha256'],'panels':panels,
                'shared_native_time_range_s':native_arrays['SyntheticTime_s']['range'],'delay_levels_ms':[80,150],
                'native_host':host,'MCP_events':len(trace),'completed_adapter_operations':len(results),
                'presentation_limit':'Measured properties and pixels only; CameraClippingRange unavailable on5.13.2',
                'native_relocation_checks':relocation_checks,'GIMP_full_plate':'PENDING','visual_review':'PENDING','artifact_bytes':budget()}

save('launch.json', {'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':os.getpid(),
    'created_time':psutil.Process().create_time(),'CPU_count':len(os.sched_getaffinity(0)),
    'source_commit':EXPECTED_COMMIT,'source_tree':EXPECTED_TREE,'wheel_sha256':WHEEL_SHA,
    'recipe_sha256':RECIPE_SHA,'package_bindings_sha256':BINDINGS_SHA,'versions':{n:importlib.metadata.version(n) for n in ['dcc-mcp-core','dcc-mcp-server','dcc-mcp-cli','mcp']},
    'stopping_budget_bytes':256*1024**2,'minimum_free_bytes':1024**3,'budget_is_not_a_filesystem_quota':True})
result=None
try:
    result=asyncio.run(main())
finally:
    process=server.host_session.process
    server.stop()
    cleanup={'server_stopped':not server.is_running,'host_returncode':None if process is None else process.poll(),
        'pump_stopped':not server.ipc_dispatcher._thread.is_alive(),'gateway_port':0,'failover':False}
    save('cleanup.json',cleanup)
if result:
    assert cleanup['server_stopped'] and cleanup['host_returncode'] is not None and cleanup['pump_stopped']
    result['cleanup']=cleanup
    save('production-manifest.json',result)
    print(json.dumps({'status':result['status'],'panels':len(result['panels']),'MCP_events':len(trace)}),flush=True)
