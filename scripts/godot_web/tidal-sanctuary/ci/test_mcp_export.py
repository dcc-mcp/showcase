"""Offline guards only; real export still requires hosted official MCP."""
import struct,tempfile,unittest,hashlib
from pathlib import Path
from mcp_export import validate_export_result,inspect_clean_pck
class ExportContract(unittest.TestCase):
 def test_complete_export_result(self):
  value={'exported':True,'exit_code':0,'path':'res://web-output/index.html','output':'Export complete'}
  self.assertEqual(validate_export_result(value),value)
 def test_failures_and_truncated_logs_rejected(self):
  base={'exported':True,'exit_code':0,'path':'res://web-output/index.html','output':'Export complete'}
  for delta in ({'exported':False},{'exit_code':1},{'exit_code':False},{'path':'res://unexpected.pck'},{'output':'x'*20000},{'output':'ERROR: failed'},{'output':None}):
   with self.subTest(delta=delta),self.assertRaises(RuntimeError):validate_export_result({**base,**delta})
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
