#!/usr/bin/env python3
"""Full D015 GIMP composition. Schema/check modes never launch a native host.

Portable public derivation of production-gimp-v3. Exact source snapshot, wheel,
installed module, package and native input bytes are required. No Git checkout is required.
Private raw runtime receipts are written only to the explicitly chosen fresh run root.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import asyncio
import copy
import datetime
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from lifecycle import (BUDGET, DEADLINE, FREE_FLOOR, Run, canonical_image,
                       close_checkpoint_arguments, exception_tree, field,
                       has_failure, image_from_result, port_closed, require,
                       sha, unwrap, unused_loopback_port, verify_clean_checkpoint)
from png_readback import crop_rgba, decode_png, rgba_sha
from xcf_metadata_readback import metadata_privacy_categories, verify_native_text_parasites

PREP = Path(__file__).resolve().parent
PLAN = PREP / 'production-plan.json'
COMMIT = '5602aa523d58a2c685966a06c90b71279a0bcfab'
TREE = 'abfd40f62533cf652d767c00781605725c0ce98b'
PLUGIN_SHA = '927d2d262f4aafccac23dec3b4f37d5d68900434eefdce374fb4b759de10444c'


def no_symlinks(path):
    path = Path(path).absolute()
    for part in [path, *path.parents]:
        require(not part.is_symlink(), 'Symlink paths are not admitted: ' + str(part))
    return path


def verify_installed_inventory(package, files):
    """Reject import shadowing, links and special nodes; verify allowed bytecode."""
    import marshal
    import types
    expected = {item['path'] for item in files}
    actual = set()
    caches = 0
    for entry in package.rglob('*'):
        require(not entry.is_symlink() and (entry.is_file() or entry.is_dir()), 'Installed package contains a symlink/special node')
        if entry.is_dir():
            continue
        relative = str(entry.relative_to(package))
        if '__pycache__' in entry.parts:
            require(entry.parent.name == '__pycache__' and entry.suffix == '.pyc', 'Unexpected installed cache entry')
            try:
                source = Path(importlib.util.source_from_cache(str(entry)))
            except ValueError as exc:
                raise RuntimeError('Unrecognized installed bytecode cache') from exc
            require(str(source.relative_to(package)) in expected and source.suffix == '.py', 'Cache has no bound source file')
            data = entry.read_bytes()
            require(16 <= len(data) <= 4*1024**2 and data[:4] == importlib.util.MAGIC_NUMBER, 'Unrecognized bytecode format')
            match = re.search(r'\.opt-([012])\.pyc$', entry.name)
            optimize = int(match.group(1)) if match else 0
            cached = marshal.loads(data[16:])
            require(isinstance(cached, types.CodeType) and cached == compile(source.read_bytes(), str(source), 'exec', dont_inherit=True, optimize=optimize), 'Installed bytecode differs from bound source')
            caches += 1
        else:
            actual.add(relative)
    require(actual == expected, 'Installed package inventory differs; possible import shadowing')
    return caches


def bound_source_check(source_root, receipt_path, wheel_path):
    import yaml
    import jsonschema
    source_root = no_symlinks(source_root)
    receipt_path = no_symlinks(receipt_path)
    require(receipt_path.is_file() and receipt_path.stat().st_size < 1024**2, 'Binding receipt must be a bounded regular file')
    snapshot_path = PREP / 'adapter-source-files.json'
    require(sha(receipt_path) == '06124ba1f6ebac36821fd36bdb65f20c920348feab842562cfbc920f1535f50b', 'Pinned adapter binding receipt differs')
    binding_data = json.loads(receipt_path.read_text())
    require(sha(snapshot_path) == binding_data['source_snapshot_manifest_sha256'], 'Source snapshot manifest mismatch')
    snapshot = json.loads(snapshot_path.read_text())
    require(snapshot['candidate_commit'] == COMMIT and snapshot['candidate_tree'] == TREE, 'Source snapshot identity mismatch')
    expected = {row['path'] for row in snapshot['files']}
    require(all((source_root / name).is_file() for name in expected), 'Source snapshot inventory incomplete')
    for row in snapshot['files']:
        path = no_symlinks(source_root / row['path'])
        require(path.is_relative_to(source_root) and path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], 'Source snapshot bytes mismatch: ' + row['path'])
    versions = {n: importlib.metadata.version(n) for n in ['dcc-mcp-core', 'dcc-mcp-server', 'dcc-mcp-cli', 'dcc-mcp-gimp', 'mcp', 'httpx']}
    require(all(versions[n] == '0.20.41' for n in ('dcc-mcp-core', 'dcc-mcp-server', 'dcc-mcp-cli')), 'Core version mismatch')
    require(versions['dcc-mcp-gimp'] == '0.4.1' and versions['mcp'] == '1.30.0', 'Adapter/SDK version mismatch')
    spec = importlib.util.find_spec('dcc_mcp_gimp')
    require(spec is not None and spec.origin is not None, 'Installed official GIMP module missing')
    package = no_symlinks(Path(spec.origin).parent)
    require(package.is_relative_to(Path(sys.prefix)), 'GIMP adapter origin is outside this interpreter environment')
    receipt = json.loads(receipt_path.read_text())
    binding = next(row for row in receipt['adapters'] if row['adapter'] == 'gimp')
    require(binding['commit'] == COMMIT and binding['tree'] == TREE and len(binding['files']) == 41, 'Wrong module binding receipt')
    import zipfile
    wheel = no_symlinks(wheel_path)
    require(wheel.is_file() and wheel.stat().st_size < 64*1024**2, 'Wheel must be a bounded regular file')
    require(sha(wheel) == binding['wheel_sha256'] == '80833767f5ff1fe754bff0de67143f053f60bb5443153c21c96d678265560853', 'Candidate wheel SHA mismatch')
    with zipfile.ZipFile(wheel) as archive:
        for item in binding['files']:
            data = archive.read('dcc_mcp_gimp/' + item['path'])
            require(hashlib.sha256(data).hexdigest() == item['sha256'] and len(data) == item['bytes'], 'Wheel module bytes mismatch')
    for item in binding['files']:
        installed = no_symlinks(package / item['path'])
        require(installed.is_file(), 'Expected installed module must be a regular file')
        source = (source_root / 'bridge/gimp-plugin/dcc_mcp_gimp.py' if item['path'] == 'gimp_plugin/dcc_mcp_gimp.py'
                  else source_root / 'src/dcc_mcp_gimp' / item['path'])
        require(sha(installed) == sha(source) == item['sha256'], 'Source/installed byte mismatch: ' + item['path'])
    cache_count = verify_installed_inventory(package, binding['files'])
    plugin = package / 'gimp_plugin/dcc_mcp_gimp.py'
    require(sha(plugin) == PLUGIN_SHA, 'Official plugin mismatch')
    plan = json.loads(PLAN.read_text())
    ops = plan['ordered_operations']
    schemas = {row['name']: row['input_schema'] for row in yaml.safe_load((package/'skills/gimp-session/tools.yaml').read_text())['tools']}
    require(len(ops) == plan['expected']['planned_operations'], 'Plan operation count mismatch')
    require(sum(op['logical_tool'] == 'create_text' for op in ops) == plan['expected']['editable_text_layers'], 'Plan text count mismatch')
    for op in ops:
        args = {key: (1 if isinstance(value, str) and value.startswith('$') else value) for key, value in op['arguments'].items()}
        jsonschema.validate(args, schemas[op['logical_tool']])
        if op['logical_tool'] == 'place_layer':
            require(op['arguments']['parent_id'].startswith('$GROUP_') and op['arguments']['position'] == 0, 'Placement must retain its named native group')
    width, height = plan['canvas']
    rectangles = []
    for panel in plan['panels']:
        x, y = panel['canvas_origin']; w, h = panel['render_size']
        require(0 <= x and 0 <= y and x+w <= width and y+h <= height, 'Planned native panel falls outside canvas')
        rectangle = [x, y, w, h]
        require(all(not overlaps(rectangle, other) for other in rectangles), 'Planned panel rectangles overlap')
        rectangles.append(rectangle)
    return {'status': 'SCHEMA_READY_INPUT_BINDING_AND_NATIVE_EXECUTION_PENDING', 'versions': versions,
            'package': str(package), 'plugin': str(plugin), 'source_commit': COMMIT, 'source_tree': TREE,
            'matched_package_files': 41, 'verified_bytecode_caches': cache_count, 'plan_sha256': sha(PLAN), 'plan_version': plan['version'],
            'canvas': plan['canvas'], 'expected': plan['expected'], 'native_launched': False}, plan


def overlaps(first, second):
    x, y, w, h = first; a, b, c, d = second
    return x < a+c and a < x+w and y < b+d and b < y+h


def read_input_manifest(path, plan, source_vti):
    path = no_symlinks(path)
    require(path.is_file(), 'Final PV input manifest does not exist yet')
    require(path.stat().st_size < 1024**2, 'Manifest exceeds bounded size')
    require(sha(path) == sha(PREP.parent / 'inputs/input-manifest.json'), 'Relocated input manifest must match the exact packaged manifest, including formulas and units')
    manifest = json.loads(path.read_text())
    require(manifest.get('status') == 'PASS_NATIVE_FIVE_PANEL_AUTHORING', 'Input manifest is not the final native PV pass')
    digest = manifest.get('source_vti_sha256')
    require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest), 'Missing source VTI identity')
    vti_name = manifest.get('source_vti_path')
    require(isinstance(vti_name, str) and not Path(vti_name).is_absolute() and '..' not in Path(vti_name).parts, 'VTI must be a relative manifest dependency')
    vti_path = no_symlinks(source_vti)
    require(vti_path.is_file() and vti_path.suffix == '.vti' and vti_path.stat().st_size <= 64*1024**2, 'VTI dependency must be a bounded regular .vti file')
    require(sha(vti_path) == digest, 'Source VTI bytes do not match manifest')
    grid = manifest.get('grid_dimensions')
    require(isinstance(grid, list) and len(grid) == 3 and all(type(v) is int and 2 <= v <= 1024 for v in grid) and math.prod(grid) <= 1_000_000, 'Invalid or oversized manifest grid')
    image_data = ET.fromstring(vti_path.read_bytes()).find('ImageData')
    require(image_data is not None, 'Expected VTI ImageData')
    extent = [int(v) for v in image_data.attrib['WholeExtent'].split()]
    require(len(extent) == 6 and [extent[2*i+1]-extent[2*i]+1 for i in range(3)] == grid, 'Actual VTI grid differs from manifest')
    require(all(extent[2*i] == 0 for i in range(3)), 'Recipe requires zero-based VTI grid extents')
    origin = [float(v) for v in image_data.attrib['Origin'].split()]
    spacing = [float(v) for v in image_data.attrib['Spacing'].split()]
    require(len(origin) == len(spacing) == 3 and all(math.isfinite(v) for v in origin+spacing) and all(v > 0 for v in spacing), 'Invalid VTI geometry')
    for name in ('origin', 'spacing'):
        actual = origin if name == 'origin' else spacing
        require(isinstance(manifest.get(name), list) and len(manifest[name]) == 3 and all(type(v) in (int, float) and abs(v-a) <= 1e-9 for v,a in zip(manifest[name],actual)), 'Manifest VTI ' + name + ' differs')
    for name in ('formula_q', 'formula_delay', 'formula_time', 'spatial_units', 'time_units'):
        text = manifest.get(name)
        require(isinstance(text, str) and 1 <= len(text) <= 512 and all(ord(c) >= 32 for c in text), 'Missing/bounded footer value: ' + name)
    require(manifest.get('delay_levels_ms') == [80,150], 'This layout requires the declared 80/150 ms isolines')
    native_receipt = path.parent / 'production-manifest.json'
    require(isinstance(manifest.get('native_receipt_sha256'), str) and sha(no_symlinks(native_receipt)) == manifest['native_receipt_sha256'], 'Projected composition manifest is not bound to the native receipt')
    native = json.loads(native_receipt.read_text())
    require(native.get('projection_schema') == 'd015-pv-selected-receipt-v1' and native.get('source_receipt_sha256') == manifest.get('original_native_receipt_sha256'), 'Selected receipt provenance mismatch')
    require(native.get('source_vti_sha256') == manifest['source_vti_sha256']
            and native.get('shared_native_time_range_s') == manifest.get('shared_native_time_range_s'),
            'Composition data identity/range differs from native receipt')
    span = manifest.get('shared_native_time_range_s')
    require(isinstance(span, list) and len(span) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in span) and span[0] < span[1], 'Missing finite shared native time range')
    rows = manifest.get('panels')
    require(isinstance(rows, list) and len(rows) == len(plan['panels']), 'Manifest must contain exactly five panels')
    names = [row.get('name') for row in rows]
    require(len(set(names)) == len(names) and set(names) == {p['name'] for p in plan['panels']}, 'Manifest panel names differ')
    by_name = {row['name']: row for row in rows}
    native_panels = {row['name']: row for row in native['panels']}
    decoded = {}
    bound = []
    for expected in plan['panels']:
        row = by_name[expected['name']]
        require(all(row.get(key) == native_panels[expected['name']].get(key) for key in ('path', 'sha256', 'dimensions')),
                'Composition panel identity differs from native receipt')
        require(row.get('path') == expected['filename'], 'Manifest path must be the exact agreed relative filename')
        require(row.get('dimensions') == expected['render_size'], 'Manifest dimensions differ from planned native placement')
        digest = row.get('sha256')
        require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest), 'Missing final native panel SHA256')
        image = no_symlinks(path.parent / row['path'])
        require(image.parent == path.parent and image.is_file(), 'Panel must be an unchanged file beside the manifest')
        require(sha(image) == digest, 'Native panel bytes do not match the final manifest')
        pixels = decode_png(image)
        require(list(pixels[:2]) == expected['render_size'], 'Actual decoded panel dimensions differ')
        require(len(set(pixels[2][i:i+4] for i in range(0, len(pixels[2]), 4))) > 1, 'Native panel is unexpectedly flat')
        decoded[expected['name']] = pixels
        bound.append({'name': row['name'], 'filename': row['path'], 'sha256': digest,
                      'dimensions': row['dimensions'], 'rgba_sha256': rgba_sha(pixels)})
    return manifest, decoded, {'manifest_sha256': sha(path), 'native_receipt_sha256': manifest['native_receipt_sha256'],
                               'source_vti_sha256': manifest['source_vti_sha256'], 'grid_dimensions': grid,
                               'origin': origin, 'spacing': spacing, 'shared_native_time_range_s': span,
                               'formula_q': manifest['formula_q'], 'formula_delay': manifest['formula_delay'],
                               'formula_time': manifest['formula_time'], 'spatial_units': manifest['spatial_units'],
                               'time_units': manifest['time_units'], 'panels': bound,
                               'visual_quality': manifest.get('visual_quality', 'UNREVIEWED')}


def effective_operations(plan, manifest):
    ops = copy.deepcopy(plan['ordered_operations'])
    low, high = manifest['shared_native_time_range_s']
    values = {'native_time_min': format(low, '.3f'), 'native_time_max': format(high, '.3f'),
              **{name: manifest[name] for name in ('formula_q', 'formula_delay', 'formula_time', 'spatial_units', 'time_units')},
              **{name: value for name,value in zip(('grid_x','grid_y','grid_z'), manifest['grid_dimensions'])}}
    for i, axis in enumerate('xyz'):
        values[axis+'_min'] = format(manifest['origin'][i], '.9g')
        values[axis+'_max'] = format(manifest['origin'][i] + manifest['spacing'][i]*(manifest['grid_dimensions'][i]-1), '.9g')
    for op in ops:
        if op['logical_tool'] == 'create_text':
            op['arguments']['text'] = op['arguments']['text'].format_map(values)
    return ops


def verify_structure(info, ops, font, plan):
    require([info['width'], info['height']] == plan['canvas'] and info['bridge_owned_display'] is True, 'Wrong owned native master canvas')
    rows = info['layers']; by_name = {row['name']: row for row in rows}
    require(len(by_name) == len(rows) == plan['expected']['total_layer_nodes'], 'Native layer names/count mismatch')
    texts = [row for row in rows if row['is_text']]
    expected = {op['arguments']['name']: op['arguments'] for op in ops if op['logical_tool'] == 'create_text'}
    require(len(texts) == len(expected) == plan['expected']['editable_text_layers'], 'Native editable text count mismatch')
    require(sum(row['is_group'] for row in rows) == plan['expected']['groups'], 'Expected five separate editable panel groups')
    panel_rectangles = [panel['canvas_origin']+panel['render_size'] for panel in plan['panels']]
    text_rectangles = []
    for row in texts:
        wanted = expected[row['name']]
        require(row['text'] == wanted['text'] and row['text_font'] == font, 'Native text/font differs: ' + row['name'])
        require(row['offsets'] == [wanted['x'], wanted['y']] and row['visible'] is True and row['opacity'] == 100.0, 'Native text placement/visibility differs')
        x, y = row['offsets']; w, h = row['width'], row['height']
        require(0 <= x and 0 <= y and x+w <= info['width'] and y+h <= info['height'], 'Native text clips canvas: ' + row['name'])
        rectangle = [x, y, w, h]
        require(all(not overlaps(rectangle, p) for p in panel_rectangles), 'Native text overlaps an imported panel: ' + row['name'])
        require(all(not overlaps(rectangle, p) for _, p in text_rectangles), 'Native editable text rectangles overlap: ' + row['name'])
        text_rectangles.append((row['name'], rectangle))
        if 'parent_id' not in wanted:
            require(row['parent_id'] is None and row['depth'] == 0, 'Root text was unexpectedly reparented')
    renders = {}
    for panel in plan['panels']:
        group = by_name[panel['group_name']]; render = by_name[panel['render_layer_name']]
        require(group['is_group'] and group['parent_id'] is None and group['child_count'] == 3, 'Panel group is not independent with its three editable children')
        require(render['parent_id'] == group['layer_id'] and render['depth'] == 1, 'Render lost its explicit panel group')
        require([render['width'], render['height']] == panel['render_size'] and render['offsets'] == panel['canvas_origin'], 'Render native dimensions/placement changed')
        require(render['visible'] and render['opacity'] == 100.0, 'Render visibility/opacity changed')
        for name in (panel['label_name'], panel['axis_name']):
            require(by_name[name]['parent_id'] == group['layer_id'] and by_name[name]['depth'] == 1, 'Panel annotation is not inside its named group')
        renders[panel['name']] = render
    return renders


async def workflow(run, ops, inputs, status, plan):
    import httpx
    import jsonschema
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    catalog = {}; native_results = []; identifiers = {}; saved_ids = set(); closed_ids = set()
    font = before = xcf_sha = None
    dirty_checkpoints = []; checks = {}; panel_checks = {}
    parasite_checks = {}; privacy_checks = {}
    def record_metadata(stage, info, xcf_path):
        parasite_checks[stage] = verify_native_text_parasites(xcf_path, info)
        privacy_checks[stage] = metadata_privacy_categories(info, run.privacy_markers)
        run.write('native-parasite-byte-checks.json', parasite_checks)
        run.write('metadata-privacy-categories.json', privacy_checks)
    imports = {panel['filename']: panel for panel in plan['panels']}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, read=180)) as http:
        async with streamable_http_client(run.server.mcp_url, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                run.trace({'kind':'initialize','response':(await session.initialize()).model_dump(mode='json')})
                async def discover():
                    found, cursor, pages = {}, None, 0
                    while True:
                        run.budget(); page = await session.list_tools(cursor=cursor)
                        run.trace({'kind':'tools/list','request_cursor':cursor,'response':page.model_dump(mode='json')})
                        found.update({tool.name:tool.model_dump(mode='json') for tool in page.tools})
                        cursor=page.nextCursor; pages+=1
                        require(pages<=32,'Unexpected tools pagination length')
                        if not cursor: break
                    return found
                def actual(logical):
                    names=[name for name in catalog if name==logical or name.endswith('__'+logical)]
                    require(len(names)==1,'Missing/ambiguous discovered tool: '+logical)
                    return names[0]
                async def call(logical,args):
                    run.budget(); name=actual(logical)
                    jsonschema.validate(args,catalog[name]['inputSchema'])
                    raw=(await session.call_tool(name,args)).model_dump(mode='json')
                    run.trace({'kind':'tools/call','tool':name,'arguments':args,'response':raw})
                    require(not raw.get('isError'),'MCP tool error: '+name)
                    payload=unwrap(raw); require(not has_failure(payload),'Tool returned failure: '+name)
                    return payload
                async def complete(logical,args):
                    result=await call(logical,args); job=field(result,'job_id')
                    if job is None:return result
                    began=time.monotonic()
                    while time.monotonic()-began<180:
                        state=await call('jobs_get_status',{'job_id':job,'include_result':True})
                        terminal=field(state,'status')
                        if terminal=='completed':
                            require(not has_failure(state),'Failed result inside completed native job');return state
                        require(terminal not in ('failed','cancelled','interrupted'),'Native job terminal failure: '+str(terminal))
                        await asyncio.sleep(.2)
                    raise TimeoutError('Existing native job exceeded deadline; no mutation replay')
                catalog=await discover()
                await call('search_skills',{'query':'gimp'});await call('get_skill_info',{'skill_name':'gimp-session'});await call('load_skill',{'skill_name':'gimp-session'})
                catalog=await discover();run.write('discovered-tool-catalog.json',catalog)
                for logical in {op['logical_tool'] for op in ops}|{'export_layer','list_images'}:actual(logical)
                for index,op in enumerate(ops):
                    logical=op['logical_tool'];args=copy.deepcopy(op['arguments'])
                    for name,value in list(args.items()):
                        if name in ('image_id','layer_id','parent_id') and isinstance(value,str) and value.startswith('$'):
                            require(value in identifiers,'Unbound native ID');args[name]=identifiers[value]
                        if name=='path':args[name]=str(run.root/('inputs' if value in imports else '')/value)
                    if logical=='create_text':require(font is not None,'Font not discovered');args['font']=font
                    if logical=='close_image':
                        require(args['image_id'] in saved_ids and args['image_id'] not in closed_ids,'Refuse close of unsaved/unowned image')
                        preclose=image_from_result(await complete('inspect_image',{'image_id':args['image_id'],'include_metadata':True}))
                        checkpoint=close_checkpoint_arguments(preclose,before,identifiers,saved_ids,run.root)
                        if checkpoint is not None:
                            result=await complete('save_image',checkpoint);path=Path(checkpoint['path'])
                            require(path.read_bytes().startswith(b'gimp xcf'),'Checkpoint lacks native XCF header')
                            digest=sha(path);require(field(result,'sha256')==digest,'Native checkpoint digest differs')
                            after=image_from_result(await complete('inspect_image',{'image_id':args['image_id'],'include_metadata':True}))
                            verify_clean_checkpoint(preclose,after,before)
                            checkpoint_stage = ('checkpoint_original' if args['image_id']==identifiers['$IMAGE'] else 'checkpoint_reopened')
                            record_metadata(checkpoint_stage, after, path)
                            require(sha(run.root/'seismic-lens-master.xcf')==xcf_sha,'First master XCF changed')
                            dirty_checkpoints.append({'image_id':args['image_id'],'arguments':checkpoint,'checkpoint_sha256':digest,'checkpoint_bytes':path.stat().st_size,'before_save':preclose,'after_save':after,'canonical_structure_equal':True,'dirty_after_save':False,'metadata_unchanged_claimed':False})
                            run.write('preclose-checkpoints.json',dirty_checkpoints);preclose=after
                        require(preclose['bridge_owned_display'] and preclose['dirty'] is False,'Refuse close of dirty/foreign image')
                    result=await complete(logical,args)
                    native_results.append({'index':index,'operation':logical,'arguments':args,'result':result});run.write('operation-results.json',native_results)
                    for key,alias in op.get('bind_from_actual_result',{}).items():
                        value=field(result,key);require(type(value) is int and value>0,'Invalid native dynamic ID');identifiers[alias]=value
                    if logical=='get_status':
                        for key in ('gimp_pid','plugin_pid','main_thread_id','plugin_module_path','allowed_roots','gimp_version'):require(field(result,key)==status[key],'Native identity changed: '+key)
                    elif logical=='list_fonts':
                        available=field(result,'fonts');require(isinstance(available,list),'No native font list')
                        font=next((x for x in ('DejaVu Sans Book','DejaVu Sans') if x in available),None);require(font is not None,'No exact preferred native font')
                        run.write('font-selection.json',{'exact_discovered_font':font,'returned_fonts':available})
                    elif logical=='create_text':
                        require(field(result,'text')==args['text'] and field(result,'font')==font and field(result,'font_size')==args['size'],'Text creation readback differs')
                    elif logical=='place_layer':
                        require(field(result,'parent_id')==args['parent_id'] and field(result,'depth')==1 and field(result,'offsets')==[args['x'],args['y']],'Panel placement lost group or offsets')
                    elif logical=='inspect_image':
                        info=image_from_result(result);renders=verify_structure(info,ops,font,plan)
                        if before is None:
                            before=canonical_image(info);run.write('native-image-before-save.json',info)
                            for panel in plan['panels']:
                                name=panel['name'];image=run.root/('readback-'+name+'.png')
                                exported=await complete('export_layer',{'image_id':identifiers['$IMAGE'],'layer_id':renders[name]['layer_id'],'path':str(image),'overwrite':False})
                                require(field(exported,'source_image_mutated') is False,'Native isolated export mutated source')
                                isolated=decode_png(image);require(list(isolated[:2])==plan['canvas'],'Isolated export canvas differs')
                                x,y=panel['canvas_origin'];w,h=panel['render_size']
                                require(crop_rgba(isolated,x,y,w,h)==inputs[name][2],'Native imported pixels differ: '+name)
                                require(all(isolated[2][(yy*isolated[0]+xx)*4+3]==0 for yy in (0,isolated[1]-1) for xx in (0,isolated[0]-1)),'Isolated render corners are not transparent')
                                panel_checks[name]={'isolated_native_rgba_exact':True,'readback_file':image.name,'rgba_sha256':rgba_sha(inputs[name])}
                            unchanged=image_from_result(await complete('inspect_image',{'image_id':identifiers['$IMAGE'],'include_metadata':True}))
                            require(canonical_image(unchanged)==before,'Isolated panel exports changed native tree')
                            run.write('panel-readback-checks.json',panel_checks);checks['all_five_imported_native_rgba_exact']=True
                        else:
                            require(canonical_image(info)==before,'Reopened XCF hierarchy/text/font/offset/opacity/visibility differs')
                            run.write('native-image-reopened.json',info);checks['native_xcf_structure_equal']=True
                            record_metadata('reopened_after_load', info, run.root/'seismic-lens-master.xcf')
                            checks['native_reopened_parasite_bytes_equal']=True
                    elif logical=='save_image':
                        path=run.root/'seismic-lens-master.xcf';require(path.read_bytes().startswith(b'gimp xcf'),'Native master XCF missing');xcf_sha=sha(path);saved_ids.add(identifiers['$IMAGE'])
                        saved_info=image_from_result(await complete('inspect_image',{'image_id':identifiers['$IMAGE'],'include_metadata':True}))
                        require(canonical_image(saved_info)==before,'XCF save changed editable native structure')
                        record_metadata('original_after_save', saved_info, path)
                        checks['native_saved_parasite_bytes_equal']=True
                    elif logical=='open_image':
                        saved_ids.add(identifiers['$REOPENED']);require(sha(run.root/'seismic-lens-master.xcf')==xcf_sha,'Master XCF bytes changed at reopen')
                    elif logical=='export_image':
                        decoded=decode_png(args['path']);require(list(decoded[:2])==plan['canvas'],'Native master PNG dimensions differ')
                        for panel in plan['panels']:
                            x,y=panel['canvas_origin'];w,h=panel['render_size']
                            require(crop_rgba(decoded,x,y,w,h)==inputs[panel['name']][2],'Master panel pixels differ: '+panel['name'])
                        if args['image_id']==identifiers['$IMAGE']:
                            after=image_from_result(await complete('inspect_image',{'image_id':identifiers['$IMAGE'],'include_metadata':True}));require(canonical_image(after)==before,'PNG export changed editable native structure')
                            record_metadata('original_after_export', after, run.root/'seismic-lens-master.xcf')
                        else:
                            original=decode_png(run.root/'seismic-lens-master.png');require(decoded==original,'Full reopened PNG decoded RGBA differs')
                            checks['full_plate_rgba_equal_after_xcf_reopen']=True;checks['master_rgba_sha256']=rgba_sha(decoded)
                    elif logical=='close_image':
                        require(field(result,'closed') is True and field(result,'discarded_changes') is False,'Owned saved close failed');closed_ids.add(args['image_id'])
                remaining=await complete('list_images',{});run.write('images-after-owned-close.json',remaining);images=field(remaining,'images')
                require(isinstance(images,list) and not (saved_ids & {x['image_id'] for x in images}),'Closed owned image remains')
                require(closed_ids==saved_ids and len(saved_ids)==2,'Owned images not all closed')
                require(len(native_results)==plan['expected']['planned_operations'] and all(checks.get(k) is True for k in ('all_five_imported_native_rgba_exact','native_xcf_structure_equal','full_plate_rgba_equal_after_xcf_reopen','native_saved_parasite_bytes_equal','native_reopened_parasite_bytes_equal')),'Native master proof incomplete')
                return {'status':'PASS_NATIVE_FULL_D015_GIMP_COMPOSITION','scope':'2560x1600 five-panel synthetic analytic exhibition plate; publication/visual/privacy review remain separate','planned_gimp_operations_completed':len(ops),'editable_text_layers':plan['expected']['editable_text_layers'],'independent_panel_groups':5,'exact_native_font':font,'baseline_additional_native_verification_calls':11,'additional_preclose_save_calls':len(dirty_checkpoints),'additional_post_save_inspection_calls':len(dirty_checkpoints),'preclose_checkpoint_artifacts':[{'path':Path(row['arguments']['path']).name,'bytes':row['checkpoint_bytes'],'sha256':row['checkpoint_sha256']} for row in dirty_checkpoints],'panel_checks':panel_checks,'checks':checks,'xcf_sha256':xcf_sha,'real_mcp_events':run.events,'metadata_unchanged_claimed':False,'PNG_byte_equality_claimed':False,'stopping_budget_bytes':BUDGET,'stopping_budget_is_not_filesystem_quota':True}


def execute(check, ops, input_decoded, plan, manifest, manifest_root, root):
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
    (root / 'inputs').mkdir()
    for panel in plan['panels']:
        shutil.copyfile(manifest_root / panel['filename'], root / 'inputs' / panel['filename'])
        bound = next(row for row in check['inputs']['panels'] if row['name'] == panel['name'])
        require(sha(root / 'inputs' / panel['filename']) == bound['sha256'], 'Copied input changed')
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
    run.privacy_markers = (str(root), str(manifest_root), str(sys.prefix), str(PREP), str(check['package']))
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
        run.write('effective-plan.json', {'version': plan['version'], 'ordered_operations': ops})
        run.write('input-binding.json', check['inputs'])
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
        result = asyncio.run(asyncio.wait_for(workflow(run, ops, input_decoded, status, plan), timeout=DEADLINE - (time.monotonic() - run.started)))
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
        result['input_visual_quality'] = manifest.get('visual_quality', 'UNREVIEWED')
        result['visual_review_required'] = True
        result['input_binding'] = check['inputs']
        artifact_paths = [root / 'seismic-lens-master.xcf', root / 'seismic-lens-master.png', root / 'seismic-lens-master-reopened.png']
        artifact_paths.extend(root / ('readback-' + panel['name'] + '.png') for panel in plan['panels'])
        artifact_paths.extend(root / row['path'] for row in result['preclose_checkpoint_artifacts'])
        result['artifacts'] = [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in artifact_paths]
        run.write('qualification.json', result)
        print(json.dumps({'run_root': str(root), 'status': result['status'], 'operations': plan['expected']['planned_operations'], 'editable_text_layers': plan['expected']['editable_text_layers'], 'full_D015_acceptance': False, 'MCP_events': run.events}), flush=True)
        return 0
    brief_error = None if error is None else {key: error[key] for key in ('type', 'message', 'mutations_replayed')}
    print(json.dumps({'run_root': str(root), 'status': 'FAIL_OR_BLOCKED_NO_NATIVE_PASS_CLAIM',
                      'error': brief_error, 'private_failure_receipt': str(root / 'failure.json'), 'cleanup': cleanup}), flush=True)
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--schema-check', action='store_true', help='Validate source bindings and full plan without requiring finished inputs')
    mode.add_argument('--check', action='store_true', help='Read-only full input/plan readiness check (default)')
    mode.add_argument('--run', action='store_true', help='Explicitly launch one owned native GIMP composition session')
    parser.add_argument('--source-root', type=Path, required=True, help='Explicit official candidate source snapshot/check-out; all bound bytes are verified')
    parser.add_argument('--wheel', type=Path, required=True, help='Explicit exact candidate wheel; SHA and all 41 modules are verified')
    parser.add_argument('--source-vti', type=Path, help='Exact analytic VTI from the ParaView native package')
    parser.add_argument('--binding-receipt', type=Path, default=PREP / 'adapter-package-bindings.json')
    parser.add_argument('--input-manifest', type=Path, default=PREP.parent / 'inputs/input-manifest.json')
    parser.add_argument('--run-root', type=Path)
    args = parser.parse_args()
    from package_integrity import verify_package
    verify_package(PREP.parent)
    check, plan = bound_source_check(args.source_root, args.binding_receipt, args.wheel)
    if args.schema_check:
        print(json.dumps(check, indent=2)); return 0
    require(args.input_manifest is not None, '--input-manifest is required for a full readiness check or native run')
    manifest_path = no_symlinks(args.input_manifest)
    require(args.source_vti is not None, '--source-vti from the ParaView package is required')
    manifest, inputs, binding = read_input_manifest(manifest_path, plan, args.source_vti)
    ops = effective_operations(plan, manifest)
    check.update(status='BOUND_FULL_LAYOUT_PREVIEW_READY_NATIVE_NOT_EXECUTED', inputs=binding,
                 full_D015_acceptance=False, native_font_bounds_pending=True)
    if not args.run:
        print(json.dumps(check, indent=2)); return 0
    require(args.run_root is not None, '--run-root must explicitly name a fresh output directory')
    return execute(check, ops, inputs, plan, manifest, manifest_path.parent, args.run_root)


if __name__ == '__main__':
    raise SystemExit(main())
