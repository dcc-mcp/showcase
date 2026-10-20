import ast, hashlib, json, pathlib, unittest, tempfile, io, urllib.error
from unittest.mock import patch
from run_preflight import parse_rpc, durable_new, capture_http_error
ROOT=pathlib.Path(__file__).parent
class Caller(unittest.TestCase):
 def test_json_and_sse(self):
  payload=b'{"jsonrpc":"2.0","result":{"ok":true}}'
  self.assertEqual(parse_rpc(payload),{'ok':True})
  self.assertEqual(parse_rpc(b'event: message\ndata: '+payload+b'\n\n'),{'ok':True})
 def test_errors_empty_truncated(self):
  for raw in [b'',b'{"result":',b'{"error":{}}',b'{"result":{"isError":true}}',b'event: message\n',b'[]']:
   with self.assertRaises((ValueError,KeyError)):parse_rpc(raw)
 def test_exclusive_durable_request(self):
  with tempfile.TemporaryDirectory() as td,patch('run_preflight.os.fsync',wraps=__import__('os').fsync) as sync:
   p=pathlib.Path(td)/'request.json';durable_new(p,b'original')
   self.assertEqual(sync.call_count,2)
   with self.assertRaises(FileExistsError):durable_new(p,b'replay')
   self.assertEqual(p.read_bytes(),b'original')
 def test_http_error_raw_body(self):
  with tempfile.TemporaryDirectory() as td:
   e=urllib.error.HTTPError('http://127.0.0.1',503,'unavailable',{},io.BytesIO(b'original error'))
   p=pathlib.Path(td)/'error.response';r=capture_http_error(e,p)
   self.assertEqual(r['http_status'],503);self.assertEqual(p.read_bytes(),b'original error')
   self.assertEqual(r['response_sha256'],hashlib.sha256(p.read_bytes()).hexdigest());self.assertFalse(r['response_truncated'])
 def test_frozen_inputs(self):
  pins=json.loads((ROOT/'caller-pins.json').read_text())
  for name,digest in pins['local'].items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)
 def test_no_native_at_import(self):
  tree=ast.parse((ROOT/'run_preflight.py').read_text())
  calls=[n for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)]
  self.assertEqual(calls,[])
 def test_before_native_audit_and_failure_retention(self):
  text=(ROOT/'run_preflight.py').read_text()
  self.assertLess(text.index('prepare(args)\n'),text.index('import dcc_mcp_godot'))
  self.assertLess(text.index(".response',raw)"),text.index('value=parse_rpc(raw)'))
  self.assertIn("report['passed']=report.get('business_checks_passed') is True and not errors",text)
  self.assertNotIn('save_scene',text);self.assertNotIn('render_scene_preview',text)
if __name__=='__main__':unittest.main()
