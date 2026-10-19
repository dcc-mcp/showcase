import ast
import copy
import tempfile
import unittest
from pathlib import Path
from common import REQUIRED_FILES, copy_game, isolated_output, receipts, source_inventory, verify_inventory
from interaction import control_center, validate_state
from author_native import editor_idle_sample, initial_copy_files
from export_web import patch_shell


class InventoryTests(unittest.TestCase):
    def source(self,root):
        for name in REQUIRED_FILES:(root/name).write_text('test '+name)
        return root

    def test_generated_inventory_includes_new_art_and_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.source(Path(tmp));(root/'assets').mkdir();(root/'assets/hero.glb').write_bytes(b'glTF')
            (root/'audio').mkdir();(root/'audio/music.ogg').write_bytes(b'OggS');(root/'audio/music.ogg.import').write_text('generated cache')
            manifest=source_inventory(root);paths={e['path'] for e in manifest['files']}
            self.assertIn('assets/hero.glb',paths);self.assertIn('audio/music.ogg',paths);self.assertNotIn('audio/music.ogg.import',paths)

    def test_missing_required_and_unknown_files_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(ValueError):source_inventory(root)
            self.source(root);(root/'credentials.pem').write_text('bad')
            with self.assertRaises(ValueError):source_inventory(root)

    def test_symlink_and_changed_bytes_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.source(Path(tmp));manifest=source_inventory(root);(root/'main.gd').write_text('changed')
            with self.assertRaises(ValueError):verify_inventory(root,manifest)
            (root/'assets.gd').symlink_to(root/'main.gd')
            with self.assertRaises(ValueError):source_inventory(root)

    def test_copy_manifest_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();self.source(source)
            manifest=source_inventory(source);copy_game(source,root/'output',manifest)
            verify_inventory(root/'output',manifest)

    def test_isolation_rejects_source_and_nonempty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();(source/'data.txt').write_text('x')
            with self.assertRaises(ValueError):isolated_output(source,source)
            with self.assertRaises(ValueError):isolated_output(source/'out',source)
            with self.assertRaises(ValueError):isolated_output(source)

    def test_mcp_scripts_are_not_precopied(self):
        names=REQUIRED_FILES+('verify_gameplay.gd','assets/athena.glb','audio/theme.ogg')
        self.assertEqual(initial_copy_files(names),('assets/athena.glb','audio/theme.ogg'))


class ObserverTests(unittest.TestCase):
    def sample(self):
        return {'schema':1,'sample_id':1,'physics_frame':2,'language':'en','paused':False,'hero':{'position':[1,0,2]},
                'ui':{'controls':{'pause':{'x':10,'y':20,'w':80,'h':40,'enabled':True}}}}

    def test_state_and_rect_validation(self):
        state=self.sample();validate_state(state);self.assertEqual(control_center(state,'pause',(1280,720)),(50,40))
        state['ui']['controls']['pause']['x']=1300
        with self.assertRaises(ValueError):control_center(state,'pause',(1280,720))
        state=self.sample();state['hero']['position'][0]=float('nan')
        with self.assertRaises(ValueError):validate_state(state)

    def test_disabled_control_needs_explicit_invalid_input_scope(self):
        state=self.sample();state['ui']['controls']['pause']['enabled']=False
        with self.assertRaises(ValueError):control_center(state,'pause',(1280,720))
        self.assertEqual(control_center(state,'pause',(1280,720),require_enabled=False),(50,40))

    def test_readonly_receipts_use_exact_prefix(self):
        self.assertEqual(receipts('prefix DAWNKEEP_STATE {"schema":1}'),[])
        self.assertEqual(receipts('DAWNKEEP_STATE {"schema":1}'),[{'schema':1}])
        with self.assertRaises(ValueError):receipts('DAWNKEEP_STATE []')

    def test_editor_probe_actual_context(self):
        value={'context':{'executed':True,'result':{'schema':1,'scanning':False,'process_frame':5,'types':{'res://main.gd':'GDScript'}}}}
        self.assertTrue(editor_idle_sample(value,{'res://main.gd':'GDScript'})[1])
        value['context']['executed']=False
        with self.assertRaises(ValueError):editor_idle_sample(value,{})

    def test_browser_launch_preserves_security_defaults(self):
        tree=ast.parse((Path(__file__).parent/'capture_browser.py').read_text())
        assignments={node.targets[0].id:node.value for node in ast.walk(tree)
                     if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)}
        self.assertEqual(ast.literal_eval(assignments['BROWSER_ARGS']),['--disable-dev-shm-usage'])
        options=assignments['options'];self.assertIsInstance(options,ast.Dict)
        values={key.value:value for key,value in zip(options.keys,options.values) if isinstance(key,ast.Constant)}
        self.assertTrue(ast.literal_eval(values['chromium_sandbox']))

    def test_official_shell_patch_requires_all_markers(self):
        html='<script src="index.js"></script>\nconst GODOT_CONFIG = {"extensionLibs":[]};\nconst engine = new Engine(GODOT_CONFIG);\nfunction displayFailureNotice(err) {}'
        patched,config=patch_shell(html)
        self.assertIn('dawnkeepShell.failed(err)',patched);self.assertFalse(config['ensureCrossOriginIsolationHeaders'])
        with self.assertRaises(RuntimeError):patch_shell(html.replace('function displayFailureNotice','function otherName'))


if __name__=='__main__':unittest.main()
