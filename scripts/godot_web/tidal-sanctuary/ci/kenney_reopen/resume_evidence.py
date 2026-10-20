"""Read-only admission of the fixed, already-saved run 39515704533 artifacts.
Never rewrites historical results, relabels the failed run, or repeats a save.
"""
import hashlib
import json
import pathlib
from conversion_contract import compare, expand_material_records, validate
from preflight_contract import audit_baseline
ROOT=pathlib.Path(__file__).resolve().parent

def sha(data):return hashlib.sha256(data).hexdigest()

def prepare_inputs(args):
    pins=json.loads((ROOT/'caller-pins.json').read_text())
    for directory,files in [(ROOT,pins['local']),(args.ci,pins['ci'])]:
        for name,h in files.items():
            if sha((directory/name).read_bytes()) != h:raise ValueError('Pinned dependency changed: '+name)
    raw=(ROOT/'plan.json').read_bytes();plan=json.loads(raw);baselines={}
    for asset in plan['assets']:
        data=(args.baseline/asset['output']).read_bytes()
        if len(data)!=asset['baseline_bytes']:raise ValueError('Baseline size changed')
        audit_baseline(data,asset['baseline_sha256']);baselines[asset['output']]=data
    return plan,raw,{},baselines,pins

def load_evidence(artifact,plan):
    pins=json.loads((ROOT/'original-evidence-pins.json').read_text())
    root=artifact/pins['artifact_subdirectory']
    raw={}
    for name,spec in pins['files'].items():
        path=root/name
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=artifact.parent):
            raise ValueError('Symlink in original evidence path')
        if not path.is_file() or path.stat().st_size != spec['bytes']:
            raise ValueError('Missing/changed original evidence: '+name)
        raw[name]=path.read_bytes()
        if sha(raw[name]) != spec['sha256']:raise ValueError('Original evidence SHA changed: '+name)
    get=lambda name:json.loads(raw[name])
    original=json.loads((ROOT/'original-conversion-freeze.json').read_text())
    if sha((ROOT/'original-conversion-freeze.json').read_bytes()) != pins['original_freeze_sha256']:
        raise ValueError('Original review freeze changed')
    for number,name in [('015','inspect_kenney_sources.gd'),('018','convert_kenney_candidates.gd')]:
        request=get('convert/rpc-'+number+'.request.json')
        args=request['params']['arguments']
        if request['method']!='tools/call' or request['params']['name']!='create_script' or args['path']!='res://'+name or args.get('overwrite') is not False or sha(args['source'].encode())!=original['files'][name]:
            raise ValueError('Original native script publication differs from review')
    request=get('convert/rpc-021.request.json')
    if request != {'jsonrpc':'2.0','id':21,'method':'tools/call','params':{'name':'execute_editor_script','arguments':{'path':'res://convert_kenney_candidates.gd','method':'convert','arguments':{'plan_sha256':sha((ROOT/'plan.json').read_bytes())},'budget_ms':50,'chunked':False}}}:
        raise ValueError('Unexpected original save request')
    response=get('convert/rpc-021.response')
    if response.get('id')!=21 or 'error' in response or response['result'].get('isError') is not False:
        raise ValueError('Original native request failed')
    envelope=response['result']['structuredContent']
    if envelope != json.loads(response['result']['content'][0]['text']) or envelope.get('success') is not True:
        raise ValueError('Original native response envelope mismatch')
    record=get('convert/rpc-021.json')
    if record.get('outcome')!='returned' or record.get('response_sha256')!=sha(raw['convert/rpc-021.response']):
        raise ValueError('Original save outcome is uncertain')
    result=get('convert/result.json')
    if result.get('passed') is not False or result.get('error')!="ValueError('Candidate external path or instance')" or result.get('cleanup_errors')!=[]:
        raise ValueError('Original failure was not the reviewed header-UID audit rejection')
    for name,exit_code in [('editor',-15),('xvfb',0)]:
        if result.get(name+'_pre_shutdown_exit_code') is not None or result.get(name+'_exit_code')!=exit_code or result.get(name+'_shutdown_actions')!=['terminate']:
            raise ValueError('Original native termination not established')
    lifecycle=get('conversion-result.json')
    wait=get('convert-wait.json')
    if lifecycle.get('passed') is not False or lifecycle.get('cancelled') is not False or lifecycle.get('lifecycle')!=[wait] or wait.get('phase')!='convert' or wait.get('exit_code')!=1 or wait.get('terminal_exit_code')!=1 or wait.get('pid')!=result['caller_pid'] or wait['end_monotonic_ns']<=wait['start_monotonic_ns']:
        raise ValueError('Original caller termination not established')
    files={a['output']:raw['convert/project/kenney-preflight/candidates/'+a['output']] for a in plan['assets']}
    witness_raw=raw['convert/project/kenney-preflight/conversion-witness.json']
    # This revalidates the unchanged old witness with the sole corrected UID
    # grammar. The historical failure/result files remain unchanged.
    witness=validate(envelope,witness_raw,plan,files,'convert')
    for asset,row in zip(plan['assets'],witness['outputs']):
        receipt=expand_material_records(get('convert/project/kenney-preflight/'+asset['output']+'.save-result.json'))
        if receipt.get('save_error')!=0 or receipt.get('exists') is not True or receipt.get('output')!=row['output']:
            raise ValueError('Original successful save receipt missing')
        compare(row['before_save_graph'],receipt['before_save_graph'])
    receipt={'schema':1,'origin_run':pins['run_id'],'origin_head':pins['head_sha'],'original_run_still_failed':True,'original_witness_sha256':sha(witness_raw),'candidate_sha256':{n:sha(b) for n,b in files.items()},'admission':'existing four native saves validated; independent reopen only; no conversion replay'}
    return witness,files,receipt
