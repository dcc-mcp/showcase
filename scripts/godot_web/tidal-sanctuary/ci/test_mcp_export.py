"""Offline guards only; real export still requires hosted official MCP."""
import struct,tempfile,unittest,hashlib,json,base64,io
from unittest.mock import Mock,patch
from pathlib import Path
from mcp_export import validate_export_result,inspect_clean_pck,partial_output_index,record_rpc_response,cleanup_export
class ExportContract(unittest.TestCase):
 def test_complete_export_result(self):
  value={'exported':True,'exit_code':0,'path':'res://web-output/index.html','output':'Export complete'}
  self.assertEqual(validate_export_result(value),value)
 def test_failures_and_truncated_logs_rejected(self):
  base={'exported':True,'exit_code':0,'path':'res://web-output/index.html','output':'Export complete'}
  for delta in ({'exported':False},{'exit_code':1},{'exit_code':False},{'path':'res://unexpected.pck'},{'output':'x'*20000},{'output':'ERROR: failed'},{'output':None}):
   with self.subTest(delta=delta),self.assertRaises(RuntimeError):validate_export_result({**base,**delta})
 def test_partial_outputs_preserved_without_success_claim(self):
  with tempfile.TemporaryDirectory() as directory:
   project=Path(directory);root=project/'web-output';root.mkdir();(root/'partial.pck').write_bytes(b'partial')
   result=partial_output_index(project)
   self.assertFalse(result['accepted'])
   self.assertEqual(result['files'],[{'path':'partial.pck','bytes':7,'sha256':hashlib.sha256(b'partial').hexdigest()}])
 def test_async_export_wiring_keeps_failure_evidence(self):
  source=Path(__file__).with_name('mcp_export.py').read_text()
  self.assertIn("call('start_export_job'",source)
  self.assertEqual(source.count("call('start_export_job'"),1)
  self.assertNotIn("call('export_project'",source)
  self.assertIn("'transport_error':repr(error),'outcome':'unknown'",source)
  self.assertIn("finally:write_json(out/'export-mcp.json',report)",source)
  self.assertIn('ProjectSettings.save()',source)
  self.assertNotIn('FileAccess.WRITE',source)
  self.assertIn("'child_reaped','descendant_cleanup_confirmed','log_complete'",source)
 def test_failure_upload_retains_export_receipts_and_partial_outputs(self):
  workflow=(Path(__file__).resolve().parents[4]/'.github/workflows/tidal-sanctuary-preview.yml').read_text()
  upload=workflow.split('name: Preserve unpublished source, receipts and actual runtime media',1)[1].split('  audio-only-no-defaults:',1)[0]
  self.assertIn("if: always()",upload)
  self.assertIn('include-hidden-files: true',upload)
  for path in ('tidal-web/*.json','tidal-web/*.log','tidal-web/export-configuration',
               'tidal-web/session/registry/godot-export-jobs','tidal-web/export-project/web-output'):
   self.assertIn(path,upload)
  self.assertIn('"$RUNNER_TEMP/tidal-export-venv/bin/python" "$RECIPE/ci/export_web.py"',workflow)
  self.assertIn("python -m pip install 'dcc-mcp-godot==0.9.6' 'dcc-mcp-core==0.20.42'",workflow)
 def test_malformed_start_response_preserves_exact_unknown_receipt(self):
  with tempfile.TemporaryDirectory() as directory:
   for raw in (b'{"result":', b'data: {"result":', b'\xff', b'[]'):
    receipts=[];path=Path(directory)/'raw.json'
    request={'id':36,'method':'tools/call','params':{'name':'start_export_job','arguments':{'request_id':'b'*32}}}
    with self.subTest(raw=raw),self.assertRaises((ValueError,IndexError)):
     record_rpc_response(receipts,request,raw,200,path)
    saved=json.loads(path.read_text())
    self.assertEqual(len(saved),1)
    self.assertEqual(saved[0]['request'],request)
    self.assertEqual(base64.b64decode(saved[0]['raw_base64']),raw)
    self.assertEqual(saved[0]['raw_sha256'],hashlib.sha256(raw).hexdigest())
    self.assertEqual(saved[0]['http_status'],200)
    self.assertEqual(saved[0]['outcome'],'unknown')
 def test_valid_sse_response_keeps_raw_and_parsed_receipt(self):
  with tempfile.TemporaryDirectory() as directory:
   raw=b'data: {"result":{"job_id":"abc"}}\n\n';path=Path(directory)/'raw.json'
   body=record_rpc_response([],{'id':1},raw,200,path)
   self.assertEqual(body['result']['job_id'],'abc')
   self.assertEqual(base64.b64decode(json.loads(path.read_text())[0]['raw_base64']),raw)
 def test_cleanup_exceptions_cannot_preserve_passed_receipt(self):
  for where in ('editor','server'):
   with tempfile.TemporaryDirectory() as directory:
    out=Path(directory);report={'passed':True};server=Mock();log=io.StringIO()
    if where=='server':server.stop.side_effect=RuntimeError('server cleanup uncertain')
    with patch('mcp_export.stop_process',side_effect=RuntimeError('editor cleanup uncertain') if where=='editor' else None):
     with self.assertRaises(RuntimeError):cleanup_export(object(),server,log,report,out,out)
    self.assertFalse(json.loads((out/'export-mcp.json').read_text())['passed'])
    self.assertIn(where+'_cleanup_error',report)
    server.stop.assert_called_once()
    self.assertTrue(log.closed)
 def pck(self,directory,version=3,name='res://project.binary',config=b'ECFG-clean-game',flags=0):
  raw=bytearray(512+len(config));raw[:32]=struct.pack('<4sIIIIIQ',b'GDPC',version,4,6,3,flags,0)
  if version==3:struct.pack_into('<Q',raw,32,128);pos=128
  else:pos=96
  path=name.encode();entry=struct.pack('<II',1,len(path))+path+struct.pack('<QQ',512,len(config))+hashlib.md5(config).digest()+struct.pack('<I',0)
  raw[pos:pos+len(entry)]=entry;raw[512:]=config;p=Path(directory)/'test.pck';p.write_bytes(raw);return p
 def test_clean_standalone_v2_and_v3(self):
  with tempfile.TemporaryDirectory() as directory:
   for version in (2,3):
    result=inspect_clean_pck(self.pck(directory,version));self.assertEqual(result['entries'],['res://project.binary'])
 def test_control_config_and_entries_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   for args in ({'config':b'autoload/DccMcpRuntimePeer'},{'name':'res://addons/control.gd'},{'name':'res://tidal_export_scan.gd'},{'name':'res://web-output/index.pck'},{'flags':1}):
    with self.subTest(args=args),self.assertRaises(ValueError):inspect_clean_pck(self.pck(directory,**args))
 def test_truncated_pck_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   p=self.pck(directory);p.write_bytes(p.read_bytes()[:150])
   with self.assertRaises(ValueError):inspect_clean_pck(p)
if __name__=='__main__':unittest.main()
