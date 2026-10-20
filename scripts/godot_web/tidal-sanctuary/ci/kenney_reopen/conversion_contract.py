"""Offline acceptance guards. Never launches Godot, writes assets, or calls a service."""
import hashlib
import json
import math
import re
from tscn_grammar import audit_bodies

EMPTY = {'edited_scene_root': None, 'open_scenes': []}
IGNORED = {'resource_path', 'scene_file_path', 'mesh_representation'}
MAX_FILE = 1024 * 1024

def digest(data):
    return hashlib.sha256(data).hexdigest()

def audit_candidate(data, expected_sha256):
    if not 0 < len(data) <= MAX_FILE or digest(data) != expected_sha256:
        raise ValueError('Candidate size or SHA mismatch')
    text = data.decode('utf-8')
    header,separator,body=text.partition('\n')
    if not separator or not re.fullmatch(r'\[gd_scene (?:load_steps=\d+ )?format=4(?: uid="uid://[a-z0-9]{1,20}")?\]',header):
        raise ValueError('Unsupported scene header')
    # A scene-header UID identifies this saved scene. It is not an external
    # resource reference. No URI is permitted anywhere in the body.
    if any(token in body for token in ('ExtResource', '[ext_resource', 'res://', 'user://', 'uid://', 'instance=', 'instance =')):
        raise ValueError('Candidate external path or instance')
    if re.search(r'"(?:[A-Za-z][A-Za-z0-9+.-]*://|/|[A-Za-z]:[\\/])', body):
        raise ValueError('Candidate external absolute path')
    if re.search(r'^\s*(?:script|metadata/[^=]+)\s*=', text, re.M):
        raise ValueError('Candidate script or unexpected metadata')
    sections = []
    for line in text.splitlines():
        if line.lstrip().startswith('['):
            if line != line.lstrip():
                raise ValueError('Noncanonical section')
            sections.append(line)
    if not sections or not re.fullmatch(r'\[gd_scene (?:load_steps=\d+ )?format=4(?: uid="uid://[a-z0-9]{1,20}")?\]', sections[0]):
        raise ValueError('Missing scene header')
    kinds = []
    ids = []
    for section in sections[1:]:
        m = re.fullmatch(r'\[sub_resource type="(ArrayMesh|StandardMaterial3D)" id="([A-Za-z0-9_]+)"\]', section)
        if m:
            ids.append(m[2]); continue
        m = re.fullmatch(r'\[node name="[^"/]+" type="(Node3D|MeshInstance3D)"(?: parent="[^"\\]+")?(?: unique_id=\d+)?\]', section)
        if m:
            kinds.append(m[1]); continue
        raise ValueError('Unexpected candidate section')
    if kinds != ['Node3D', 'Node3D', 'MeshInstance3D'] or len(ids) != len(set(ids)):
        raise ValueError('Unexpected graph or duplicate resource')
    if sum('type="ArrayMesh"' in s for s in sections) != 1:
        raise ValueError('Expected one ArrayMesh')
    refs = re.findall(r'SubResource\("([A-Za-z0-9_]+)"\)', text)
    if any(ref not in ids for ref in refs):
        raise ValueError('Unresolved subresource')
    audit_bodies(text)
    return {'sha256': expected_sha256, 'bytes': len(data), 'no_scripts_or_external_resources': True}

def compare(expected, actual, key=''):
    if key in ('transform', 'computed_world_transform'):
        if not isinstance(expected, list) or not isinstance(actual, list) or len(expected) != 12 or len(actual) != 12:
            raise ValueError('Invalid transform')
        if any(type(a) not in (int, float) or type(b) not in (int, float) or not math.isfinite(a) or not math.isfinite(b) or abs(a-b) > 1e-7 for a,b in zip(expected,actual)):
            raise ValueError('Transform mismatch')
    elif isinstance(expected, dict) and isinstance(actual, dict):
        a = {k:v for k,v in expected.items() if k not in IGNORED}
        b = {k:v for k,v in actual.items() if k not in IGNORED}
        if a.keys() != b.keys(): raise ValueError('Graph field mismatch')
        for k in a: compare(a[k],b[k],k)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual): raise ValueError('Array size mismatch')
        for a,b in zip(expected,actual): compare(a,b)
    elif type(expected) != type(actual) or expected != actual:
        # JSON Godot may encode an exact integral real as integer; value equality
        # is appropriate for material numerics, never tolerance or string coercion.
        if not (type(expected) in (int,float) and type(actual) in (int,float) and expected == actual):
            raise ValueError('Immutable field mismatch: '+key)

def graph_valid(graph, count):
    if not isinstance(graph, list) or len(graph) != count:
        raise ValueError('Wrong graph count')
    if [n.get('class') for n in graph] != (['Node3D','ImporterMeshInstance3D'] if count == 2 else ['Node3D','Node3D','MeshInstance3D']):
        raise ValueError('Unexpected graph shape')
    for n in graph:
        for k in ('transform','computed_world_transform'): compare(n.get(k),n.get(k),k)
    surfaces = graph[-1].get('surfaces', [])
    if not 1 <= len(surfaces) <= 16: raise ValueError('Missing surfaces')
    for i,s in enumerate(surfaces):
        channels=s.get('channels', [])
        if s.get('index') != i or not 0 < s.get('vertex_count',0) <= 20000 or len(channels) != 13 or [c.get('channel') for c in channels] != list(range(13)):
            raise ValueError('Invalid surface witness')
        if any(not re.fullmatch('[a-f0-9]{64}',c.get('stored_variant_sha256','')) for c in channels):
            raise ValueError('Missing immutable array hash')
        for key in ('source_material','effective_material'):
            material=s.get(key,{})
            properties=material.get('stored_properties',{})
            if material.get('present') is not True or not isinstance(material.get('name'),str) or not {'resource_name','albedo_color','metallic','roughness'}.issubset(properties):
                raise ValueError('Incomplete material storage witness')
            if any(type(v.get('type')) is not int or not re.fullmatch('[a-f0-9]{64}',v.get('stored_variant_sha256','')) for v in properties.values()):
                raise ValueError('Invalid material storage hash')
    return surfaces

def expand_material_records(witness):
    records=witness.get('material_records')
    if not isinstance(records,dict) or not records or len(records)>36:
        raise ValueError('Missing or unbounded deduplicated material table')
    decoded={}
    for key,serialized in records.items():
        if not isinstance(serialized,str) or digest(serialized.encode()) != key:
            raise ValueError('Material table content hash mismatch')
        decoded[key]=json.loads(serialized)
        if not isinstance(decoded[key],dict):raise ValueError('Invalid material table record')
    def expand(item):
        if isinstance(item,list):return [expand(v) for v in item]
        if isinstance(item,dict):
            result={k:expand(v) for k,v in item.items() if k!='material_records'}
            if 'stored_properties_ref' in result:
                key=result.pop('stored_properties_ref')
                if key not in decoded or 'stored_properties' in result:raise ValueError('Unknown/ambiguous material reference')
                result['stored_properties']=decoded[key]
            return result
        return item
    return expand(witness)


def validate(body, raw, plan, files, phase, prior=None):
    context=body.get('context',body)
    if not isinstance(context,dict): raise ValueError('Missing native context')
    result=context.get('result',{})
    if not isinstance(result,dict): raise ValueError('Missing native result')
    path='conversion-witness.json' if phase == 'convert' else 'independent-reopen-witness.json'
    if context.get('executed') is not True or result.get('schema') != 1 or result.get('witness_path') != 'res://kenney-preflight/'+path:
        raise ValueError('Native method failed or unexpected result')
    if not 0 < len(raw) <= MAX_FILE or result.get('witness_bytes') != len(raw) or result.get('witness_sha256') != digest(raw):
        raise ValueError('Witness size/SHA mismatch')
    if phase == 'convert':
        if result.get('converted') != 4 or result.get('saved_native_asset') is not True or result.get('independent_session_reopen') is not False:
            raise ValueError('Invalid conversion result')
    elif result.get('reopened') != 4 or result.get('converted') is not False or result.get('saved_native_asset') is not False or prior is None:
        raise ValueError('Invalid independent reopen result')
    witness=expand_material_records(json.loads(raw))
    if prior is not None and "material_records" in prior:prior=expand_material_records(prior)
    if witness.get('schema') != 1 or witness.get('scene_before') != EMPTY or witness.get('scene_after') != EMPTY:
        raise ValueError('Empty scene guard failed')
    if [witness.get('engine',{}).get(k) for k in ('major','minor','patch')] != [4,6,3]:
        raise ValueError('Wrong native version')
    rows=witness.get('outputs',[])
    if len(rows) != 4 or len(files) != 4: raise ValueError('Expected four outputs')
    if set(files) != {a['output'] for a in plan['assets']}: raise ValueError('Unexpected output set')
    for index,(asset,row) in enumerate(zip(plan['assets'],rows)):
        name=asset['output']; data=files[name]; h=digest(data)
        audit_candidate(data,h)
        if row.get('output') != ('res://kenney-preflight/candidates/'+name if phase == 'convert' else name):
            raise ValueError('Wrong output identity/order')
        if row.get('output_sha256' if phase == 'convert' else 'sha256') != h:
            raise ValueError('Output SHA changed')
        baseline=row.get('baseline_graph'); reopened=row.get('reopened_graph')
        graph_valid(baseline,3); surfaces=graph_valid(reopened,3)
        compare(baseline,reopened)
        if len(surfaces) != len(asset['surface_overrides']): raise ValueError('Override count changed')
        if phase == 'convert':
            if row.get('source') != asset['source_file'] or row.get('source_sha256') != asset['source_sha256'] or row.get('save_error') != 0 or row.get('output_bytes') != len(data):
                raise ValueError('Import/save identity failed')
            source=graph_valid(row.get('source_graph'),2)
            if len(source) != len(surfaces): raise ValueError('Source surface count changed')
            graph_valid(row.get('before_save_graph'),3); compare(baseline,row['before_save_graph'])
            compare(asset['expected_source_mesh_transform'],row['source_graph'][1]['transform'],'transform')
            compare(asset['wrapper_transform'],reopened[1]['transform'],'transform')
            for s,t in zip(source,surfaces):
                compare({k:v for k,v in s.items() if k != 'effective_material'},{k:v for k,v in t.items() if k != 'effective_material'})
        else:
            previous=prior['outputs'][index]
            compare(previous['reopened_graph'],reopened)
            if previous['output_sha256'] != h: raise ValueError('Independent candidate changed')
    if sum(len(r['reopened_graph'][-1]['surfaces']) for r in rows) != 9:
        raise ValueError('Expected exactly nine surfaces')
    return witness
