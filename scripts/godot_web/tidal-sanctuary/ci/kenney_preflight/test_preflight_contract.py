import copy,hashlib,json,unittest
from preflight_contract import audit_baseline,validate_response

class PreflightTests(unittest.TestCase):
 def fixture(self):
  plan={'assets':[{'source_file':str(i)+'.glb','output':str(i)+'.tscn','source_sha256':str(i)*64,'baseline_sha256':'f'*64} for i in range(4)]}
  witness={'schema':1,'nodes':24,'vertices':100,'engine':{'major':4,'minor':6,'patch':3},
           'scene_before':{'edited_scene_root':None,'open_scenes':[]},'scene_after':{'edited_scene_root':None,'open_scenes':[]},
           'assets':[{'source':a['source_file'],'baseline':a['output'],'source_sha256':a['source_sha256'],
                      'baseline_sha256':a['baseline_sha256'],'import_error':0,'source_graph':[{}],'baseline_graph':[{}]} for a in plan['assets']]}
  data=json.dumps(witness).encode();body={'context':{'executed':True,'result':{'schema':1,'inspected':4,'converted':False,'saved_native_asset':False,'witness_path':'res://kenney-preflight/preflight-witness.json','witness_bytes':len(data),'witness_sha256':hashlib.sha256(data).hexdigest()}}}
  return plan,witness,data,body
 def test_exact_bounded_native_result(self):
  plan,witness,data,body=self.fixture();self.assertEqual(validate_response(body,data,plan),witness)
 def test_assertion_empty_result_is_failure(self):
  plan,_,data,body=self.fixture();body['context']['result']=None
  with self.assertRaisesRegex(ValueError,'assertion failure'):validate_response(body,data,plan)
 def test_wrong_result_fields_or_tampered_bytes_fail(self):
  for key,value in [('inspected',3),('inspected',True),('converted',True),('saved_native_asset',True),('witness_path','res://other.json'),('witness_sha256','0'*64)]:
   plan,_,data,body=self.fixture();body['context']['result'][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):validate_response(body,data,plan)
 def test_current_scene_or_fixed_source_mismatch_fails(self):
  for kind in ('scene','source','engine'):
   plan,witness,_,body=self.fixture()
   if kind=='scene':witness['scene_after']['open_scenes']=['res://unexpected.tscn']
   elif kind=='source':witness['assets'][0]['source_sha256']='e'*64
   else:witness['engine']['patch']=2
   data=json.dumps(witness).encode();body['context']['result'].update(witness_bytes=len(data),witness_sha256=hashlib.sha256(data).hexdigest())
   with self.subTest(kind=kind),self.assertRaises(ValueError):validate_response(body,data,plan)
 def test_baseline_preinstantiate_rejects_scripts_external_and_other_classes(self):
  for text in ['[node type="Node3D"]\nscript = SubResource("Script")','[ext_resource path="res://evil.gd"]','[node type="Node3D" instance=SubResource("x")]','[sub_resource type="GDScript"]','[node type="AnimationPlayer"]']:
   data=text.encode()
   with self.subTest(text=text),self.assertRaises(ValueError):audit_baseline(data,hashlib.sha256(data).hexdigest())

if __name__=='__main__':unittest.main()
