"""Offline integrity/plan tests only. Not a new Blender acceptance run."""
import hashlib,importlib.util,json,pathlib,unittest
ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('plan',ROOT/'recipes/build_tool_plan.py');plan=importlib.util.module_from_spec(spec);spec.loader.exec_module(plan)
class PackageTests(unittest.TestCase):
 def setUp(self):self.e=json.loads((ROOT/'stage-evidence.json').read_text())
 def test_asset_integrity(self):
  self.assertEqual(len(self.e['assets']),9)
  for r in self.e['assets']:self.assertEqual(hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest(),r['sha256'])
 def test_evidence_integrity(self):
  for stage in self.e['stages']:
   for r in stage['evidence']:self.assertEqual(hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest(),r['sha256'])
 def test_original_source(self):self.assertEqual(hashlib.sha256((ROOT/self.e['source_recipe']['path']).read_bytes()).hexdigest(),self.e['source_recipe']['sha256'])
 def test_not_whole_case(self):
  s={s['id']:s['status'] for s in self.e['stages']}
  for k in ['visual_render_review','runtime_integration','browser_interaction','whole_case_ecosystem_graph']:self.assertEqual(s[k],'not-tested')
  self.assertFalse(self.e['native_scene']['included'])
 def test_plan_shape(self):
  p=plan.build_plan(ROOT);self.assertEqual(len(p),341);self.assertEqual(p[0]['name'],'blender_scene__new_scene')
  self.assertEqual(sum(x['name']=='blender_data_geometry__create_mesh_from_data' for x in p),64)
  self.assertEqual(sum(x['name']=='blender_interchange__export_gltf' for x in p),9)
  self.assertEqual(sum(x['name']=='blender_scripting__execute_python' for x in p),1)
  self.assertFalse(any('render' in x['name'] for x in p))
 def test_portable_script_integrity(self):
  for r in self.e['scripts']['portable_copies']:self.assertEqual(hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest(),r['sha256'])
 def test_no_private_paths(self):
  for p in ROOT.rglob('*'):
   if p.suffix in ['.json','.md','.py'] and p.name!='test_package.py':
    s=p.read_text();self.assertNotIn('/workspace/',s);self.assertNotIn('127.0.0.1',s);self.assertNotIn('/home/agent/',s)
if __name__=='__main__':unittest.main()
