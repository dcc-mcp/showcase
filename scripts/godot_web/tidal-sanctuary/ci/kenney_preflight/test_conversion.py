"""Lightweight offline contracts. Synthetic witnesses are tests, not native evidence."""
import copy
import json
import pathlib
import unittest
import tempfile
from types import SimpleNamespace
from unittest import mock
import run_conversion
import run_conversion_session
import signal
from conversion_contract import audit_candidate, compare, digest, validate
ROOT=pathlib.Path(__file__).resolve().parent
IDENTITY=[1,0,0,0,1,0,0,0,1,0,0,0]
TSCN=b'''[gd_scene format=4]
[sub_resource type="StandardMaterial3D" id="M"]
[sub_resource type="ArrayMesh" id="A"]
[node name="CoastalAsset" type="Node3D"]
[node name="source" type="Node3D" parent="."]
[node name="mesh" type="MeshInstance3D" parent="source"]
mesh = SubResource("A")
'''

def fixture():
    plan=json.loads((ROOT/'plan.json').read_text());rows=[];files={}
    for a in plan['assets']:
        surfaces=[{'index':i,'vertex_count':1,'channels':[{'channel':j,'type':0,'stored_variant_sha256':'a'*64} for j in range(13)],'source_material':{'present':True,'name':'source'},'effective_material':{'present':True,'name':s['name']}} for i,s in enumerate(a['surface_overrides'])]
        for surf in surfaces:
            for key in ('source_material','effective_material'):
                surf[key]['stored_properties']={p:{'type':3,'stored_variant_sha256':'c'*64} for p in ('resource_name','albedo_color','metallic','roughness')}
        graph=[{'class':c,'transform':IDENTITY[:],'computed_world_transform':IDENTITY[:]} for c in ['Node3D','Node3D','MeshInstance3D']]
        graph[1]['transform']=a['wrapper_transform'][:];graph[2]['transform']=a['expected_source_mesh_transform'][:];graph[2]['surfaces']=surfaces
        source=[copy.deepcopy(graph[0]),copy.deepcopy(graph[2])];source[1]['class']='ImporterMeshInstance3D'
        for s in source[1]['surfaces']: s['effective_material']=s['source_material']
        files[a['output']]=TSCN
        rows.append({'source':a['source_file'],'source_sha256':a['source_sha256'],'output':'res://kenney-preflight/candidates/'+a['output'],'output_sha256':digest(TSCN),'output_bytes':len(TSCN),'save_error':0,'source_graph':source,'baseline_graph':graph,'before_save_graph':copy.deepcopy(graph),'reopened_graph':copy.deepcopy(graph)})
    empty={'edited_scene_root':None,'open_scenes':[]}
    return plan,files,{'schema':1,'engine':{'major':4,'minor':6,'patch':3},'scene_before':empty,'scene_after':empty,'outputs':rows}

def body(w,phase='convert'):
    w=copy.deepcopy(w)
    records={}
    def compact(item):
        if isinstance(item,list):return [compact(v) for v in item]
        if isinstance(item,dict):
            item={k:compact(v) for k,v in item.items()}
            if 'stored_properties' in item:
                serialized=json.dumps(item.pop('stored_properties'),sort_keys=True,separators=(',',':'))
                key=digest(serialized.encode());records[key]=serialized;item['stored_properties_ref']=key
            return item
        return item
    w=compact(w);w['material_records']=records
    raw=json.dumps(w).encode()
    r={'schema':1,'witness_sha256':digest(raw),'witness_bytes':len(raw),'witness_path':'res://kenney-preflight/'+('conversion-witness.json' if phase=='convert' else 'independent-reopen-witness.json')}
    r.update({'converted':4,'saved_native_asset':True,'independent_session_reopen':False} if phase=='convert' else {'reopened':4,'converted':False,'saved_native_asset':False})
    return {'executed':True,'result':r},raw

class Contracts(unittest.TestCase):
    def test_candidate(self): audit_candidate(TSCN,digest(TSCN))
    def test_candidate_rejects_unsafe(self):
        for payload in [b'\nscript = null',b'\n [ext_resource path="x"]',b'\n[connection signal="ready"]',b'\n[editable path="x"]',b'\nx = "res://x"',b'\nx = ExtResource("x")',b'\n[node name="bad" type="Timer"]',b'\nmetadata/x = 1',b'\nmesh = SubResource("unknown")',b'\nvisible = false',b'\ncast_shadow = 0',b'\nmesh = Object("Resource")',b'\ntransform = Transform3D(1, 2)']:
            d=TSCN+payload
            with self.subTest(payload=payload),self.assertRaises(ValueError): audit_candidate(d,digest(d))
    def test_sha_and_size(self):
        for d,h in [(TSCN,'0'*64),(b'',digest(b'')),(b'x'*(1024*1024+1),digest(b'x'*(1024*1024+1)))]:
            with self.assertRaises(ValueError):audit_candidate(d,h)
    def test_conversion(self):
        p,f,w=fixture();b,r=body(w);validate(b,r,p,f,'convert')
    def test_transform_only_tolerance(self):
        compare({'transform':IDENTITY},{'transform':[1+5e-8,*IDENTITY[1:]]})
        for v in [1+2e-7,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):compare({'transform':IDENTITY},{'transform':[v,*IDENTITY[1:]]})
        with self.assertRaises(ValueError):compare({'roughness':1.0},{'roughness':1.00000001})
    def test_conversion_mutations(self):
        mutations=[lambda w:w['outputs'].pop(),lambda w:w['outputs'][0].update(save_error=1),lambda w:w['outputs'][0].update(output_sha256='0'*64),lambda w:w['outputs'][0]['source_graph'][1]['surfaces'][0]['channels'][0].update(stored_variant_sha256='b'*64),lambda w:w.update(scene_after={'edited_scene_root':'x','open_scenes':[]}),lambda w:w['outputs'][0]['reopened_graph'][2]['surfaces'][0]['effective_material'].update(name='changed')]
        for mutate in mutations:
            p,f,w=fixture();mutate(w);b,r=body(w)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):validate(b,r,p,f,'convert')
    def test_independent_reopen(self):
        p,f,prior=fixture();w=copy.deepcopy(prior)
        w['outputs']=[{'output':a['output'],'sha256':row['output_sha256'],'baseline_graph':row['baseline_graph'],'reopened_graph':row['reopened_graph']} for a,row in zip(p['assets'],w['outputs'])]
        b,r=body(w,'reopen');validate(b,r,p,f,'reopen',prior)
        prior['outputs'][0]['output_sha256']='0'*64
        with self.assertRaises(ValueError): validate(b,r,p,f,'reopen',prior)
    def test_assertion_failure_is_not_success(self):
        p,f,w=fixture();b,r=body(w);b['result']=None
        with self.assertRaises((ValueError,AttributeError)):validate(b,r,p,f,'convert')
    def test_native_acquisition_defers_cancellation(self):
        gate=run_conversion_session.CancellationGate();gate.acquiring=True
        gate.interrupted(signal.SIGTERM,None)
        self.assertEqual(gate.pending,signal.SIGTERM)
        gate.acquiring=False
        with self.assertRaises(TimeoutError):gate.check_pending()
        gate.cleaning=True
        gate.interrupted(signal.SIGTERM,None)
        gate.interrupted(signal.SIGALRM,None)

    def test_owned_exit_codes(self):
        for initial,terminal,expected_error in [(None,-signal.SIGTERM,False),(None,-signal.SIGSEGV,True),(-signal.SIGSEGV,-signal.SIGSEGV,True),(0,0,True),(None,-signal.SIGKILL,True)]:
            with self.subTest(initial=initial,terminal=terminal):
                state={'code':initial};report={};errors=[]
                process=SimpleNamespace(poll=lambda:state['code'],terminate=lambda:state.update(code=terminal),wait=lambda **kw:state['code'])
                def stop(p):
                    if p.poll() is None:p.terminate();p.wait()
                run_conversion_session.stop_owned_process('editor',process,stop,report,errors)
                self.assertEqual(bool(errors),expected_error)
                self.assertEqual(report['editor_pre_shutdown_exit_code'],initial)

    def test_cancellation_at_process_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(output=pathlib.Path(tmp)/'out',ci=ROOT,archive=ROOT/'archive.zip',baseline=ROOT,godot='NOT-EXECUTED',xvfb='NOT-EXECUTED')
            handlers={};events=[];state={'done':False}
            def set_handler(sig,handler):
                old=handlers.get(sig);handlers[sig]=handler;return old
            def mask(how,mask):
                events.append(('mask',how))
                if how==signal.SIG_SETMASK:handlers[signal.SIGTERM](signal.SIGTERM,None)
                return set()
            def fake_process(command,**kwargs):
                events.append('launch');session=pathlib.Path(command[command.index('--output')+1]);session.mkdir()
                def wait():
                    events.append('wait');state['done']=True
                    (session/'result.json').write_text(json.dumps({'cleanup_errors':[],'editor_exit_code':0,'xvfb_exit_code':0}))
                    return 1
                return SimpleNamespace(pid=123,poll=lambda:1 if state['done'] else None,wait=wait,send_signal=lambda sig:events.append('forward'))
            with mock.patch.object(run_conversion,'verify_freeze'),mock.patch.object(run_conversion.signal,'signal',side_effect=set_handler),mock.patch.object(run_conversion.signal,'pthread_sigmask',side_effect=mask),mock.patch.object(run_conversion.subprocess,'Popen',side_effect=fake_process):
                with self.assertRaises(InterruptedError):run_conversion.run(args)
            self.assertEqual(events,[('mask',signal.SIG_BLOCK),'launch',('mask',signal.SIG_SETMASK),'forward','wait'])
            report=json.loads((args.output/'conversion-result.json').read_text())
            self.assertFalse(report['passed']);self.assertEqual(report['lifecycle'][0]['terminal_exit_code'],1)

    def test_closed_log_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'editor.log';other=pathlib.Path(tmp)/'xvfb.log'
            log=path.open('w');xlog=other.open('w');log.write('ERROR: emitted during shutdown\n')
            errors=[]
            def checker(text):
                self.assertTrue(log.closed);self.assertTrue(xlog.closed)
                if 'ERROR:' in text:raise RuntimeError('late failure')
            run_conversion_session.close_and_check_logs(log,xlog,path,checker,errors)
            self.assertEqual(errors[0]['component'],'closed_editor_log')

    def test_material_table_budget_and_integrity(self):
        p,f,w=fixture()
        for row_index,row in enumerate(w['outputs']):
            for graphkey in ('source_graph','baseline_graph','before_save_graph','reopened_graph'):
                for surface_index,surf in enumerate(row[graphkey][-1]['surfaces']):
                    for key in ('source_material','effective_material'):
                        tag='source_material' if graphkey=='source_graph' else key
                        unique=digest(f'{row_index}:{surface_index}:{tag}'.encode())
                        surf[key]['stored_properties'].update({f'property_{i}':{'type':3,'stored_variant_sha256':unique} for i in range(150)})
        b,r=body(w);self.assertEqual(len(json.loads(r)['material_records']),18);self.assertLess(len(r),1024*1024);validate(b,r,p,f,'convert')
        bad=json.loads(r);key=next(iter(bad['material_records']));bad['material_records'][key]+=' '
        raw=json.dumps(bad).encode();b['result'].update(witness_bytes=len(raw),witness_sha256=digest(raw))
        with self.assertRaises(ValueError):validate(b,raw,p,f,'convert')

    def test_coordinator_cancellation_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(output=pathlib.Path(tmp)/'out',ci=ROOT,archive=ROOT/'archive.zip',baseline=ROOT,godot='NOT-EXECUTED',xvfb='NOT-EXECUTED')
            handlers={};events=[]
            def set_handler(sig,handler):
                previous=handlers.get(sig);handlers[sig]=handler;return previous
            def fake_process(command,**kwargs):
                session=pathlib.Path(command[command.index('--output')+1]);session.mkdir()
                def wait():
                    events.append('wait')
                    if len(events)==1:handlers[signal.SIGTERM](signal.SIGTERM,None)
                    (session/'result.json').write_text(json.dumps({'passed':False,'cleanup_errors':[],'editor_exit_code':0,'xvfb_exit_code':0}))
                    return 1
                return SimpleNamespace(pid=123,wait=wait,poll=lambda:1 if events.count('wait')>1 else None,send_signal=lambda sig:events.append(('signal',sig)))
            with mock.patch.object(run_conversion,'verify_freeze'),mock.patch.object(run_conversion.signal,'signal',side_effect=set_handler),mock.patch.object(run_conversion.subprocess,'Popen',side_effect=fake_process):
                with self.assertRaises(InterruptedError):run_conversion.run(args)
            report=json.loads((args.output/'conversion-result.json').read_text())
            self.assertEqual(events,['wait',('signal',signal.SIGTERM),'wait'])
            self.assertTrue(report['cancelled']);self.assertFalse(report['passed'])
            self.assertEqual(len(report['lifecycle']),1)
            self.assertEqual(report['lifecycle'][0]['cancellation_cleanup']['cleanup_errors'],[])

    def test_coordinator_lifecycle(self):
        for mode in ('success','first-exit-error','first-cleanup-error'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                calls=[]
                args=SimpleNamespace(output=pathlib.Path(tmp)/'out',ci=ROOT,archive=ROOT/'archive.zip',baseline=ROOT,godot='NOT-EXECUTED',xvfb='NOT-EXECUTED')
                def fake_process(command,**kwargs):
                    calls.append(command);out=pathlib.Path(command[command.index('--output')+1]);out.mkdir()
                    result={'passed':True,'cleanup_errors':[],'editor_exit_code':0,'xvfb_exit_code':0}
                    if mode == 'first-cleanup-error':result['cleanup_errors']=['failed']
                    (out/'result.json').write_text(json.dumps(result))
                    code=1 if mode=='first-exit-error' else 0
                    return SimpleNamespace(pid=100+len(calls),wait=lambda:code,poll=lambda:code)
                with mock.patch.object(run_conversion,'verify_freeze'),mock.patch.object(run_conversion.subprocess,'Popen',side_effect=fake_process):
                    if mode == 'success':run_conversion.run(args)
                    else:
                        with self.assertRaises(RuntimeError):run_conversion.run(args)
                result=json.loads((args.output/'conversion-result.json').read_text())
                self.assertEqual(len(calls),2 if mode=='success' else 1)
                self.assertEqual(result['passed'],mode=='success')
                if mode=='success':
                    self.assertLess(result['lifecycle'][0]['end_monotonic_ns'],result['lifecycle'][1]['start_monotonic_ns'])
                    self.assertIn('--previous',calls[1])

    def test_lifecycle_and_routes_static(self):
        coordinator=(ROOT/'run_conversion.py').read_text();session=(ROOT/'run_conversion_session.py').read_text();gd=(ROOT/'convert_kenney_candidates.gd').read_text()
        self.assertIn("record['exit_code']=child.wait()",coordinator)
        self.assertIn("for phase in ('convert','reopen')",coordinator)
        self.assertIn("previous_result.get('cleanup_errors') != []",session)
        self.assertIn("call('create_script'",session);self.assertIn("call('execute_editor_script'",session)
        self.assertNotIn('godot --headless',session)
        self.assertIn('ResourceSaver.save(packed,output,ResourceSaver.FLAG_BUNDLE_RESOURCES)',gd)
        self.assertIn('PROPERTY_USAGE_STORAGE',gd)
        self.assertIn('assert(a == b)',gd)

if __name__=='__main__':unittest.main()
