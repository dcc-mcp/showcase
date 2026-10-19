import ast
import copy
import re
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from common import REQUIRED_FILES, copy_game, isolated_output, receipts, source_inventory, verify_inventory
from interaction import control_center, validate_state
from author_native import editor_idle_sample, initial_copy_files
from export_web import patch_shell
from capture_native import mouse_location, pointer_click


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


class NativePointerTests(unittest.TestCase):
    def test_location_readback_is_integer_data(self):
        self.assertEqual(mouse_location('X=1036\nY=54\nSCREEN=0\nWINDOW=123\n'),(1036,54))
        self.assertEqual(mouse_location('Y=-2\nX=0\n'),(0,-2))

    def test_malformed_readback_is_rejected(self):
        for value in ('','X=1\n','Y=2\n','X=1\nX=1\nY=2','X=1.0\nY=2',
                      'X=$(touch sentinel)\nY=2','X=1;echo bad\nY=2','X=1\nY=2\nEXTRA=3'):
            with self.subTest(value=value),self.assertRaises(ValueError):mouse_location(value)

    def test_repeated_identical_target_uses_readback_without_motion_wait(self):
        def result(command,**options):
            self.assertTrue(options['check']);self.assertGreater(options['timeout'],0)
            self.assertLessEqual(options['timeout'],10);self.assertNotIn('shell',options)
            return subprocess.CompletedProcess(command,0,stdout='X=1036\nY=54\nSCREEN=0\nWINDOW=123\n')
        with patch('capture_native.subprocess.run',side_effect=result) as run:
            for _ in range(2):self.assertEqual(pointer_click(1036,54),(1036,54))
        expected=[['xdotool','mousemove','1036','54'],['xdotool','getmouselocation','--shell'],['xdotool','click','1']]*2
        self.assertEqual([call.args[0] for call in run.call_args_list],expected)

    def test_bad_readback_prevents_click(self):
        for output,error in [('X=1035\nY=54\n',RuntimeError),('X=1036\nY=no\n',ValueError)]:
            with self.subTest(output=output),patch('capture_native.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout=output)) as run:
                with self.assertRaises(error):pointer_click(1036,54)
                self.assertEqual(run.call_count,2)
                self.assertFalse(any(call.args[0][1]=='click' for call in run.call_args_list))

    def test_command_failure_or_timeout_is_not_ignored(self):
        success=subprocess.CompletedProcess([],0,stdout='X=1036\nY=54\n')
        for failure in (subprocess.TimeoutExpired(['xdotool'],10),subprocess.CalledProcessError(1,['xdotool'])):
            for step in range(3):
                with self.subTest(error=type(failure).__name__,step=step),patch('capture_native.subprocess.run',side_effect=[success]*step+[failure]) as run:
                    with self.assertRaises(type(failure)):pointer_click(1036,54)
                    self.assertEqual(run.call_count,step+1)

    def test_click_keeps_one_ten_second_budget(self):
        with patch('capture_native.time.monotonic',side_effect=[100,100,104,110.1]),patch('capture_native.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout='X=1036\nY=54\n')) as run:
            with self.assertRaises(TimeoutError):pointer_click(1036,54)
            self.assertEqual(run.call_count,2)
            self.assertEqual([call.kwargs['timeout'] for call in run.call_args_list],[10,6])


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

    def test_headless_authoring_keeps_mandatory_rendered_native_gate(self):
        workflow=Path(__file__).resolve().parents[4]/'.github/workflows/dawnkeep-preview.yml'
        steps=re.split(r'(?=^      - name: )',workflow.read_text(),flags=re.M)
        def step(step_id):
            matches=[block for block in steps if re.search(r'^        id: '+step_id+r'$',block,re.M)]
            self.assertEqual(len(matches),1,'Expected exactly one workflow stage: '+step_id)
            return matches[0]
        author=step('author');native=step('native_gate')
        self.assertRegex(author,r'- name: [^\n]*headless')
        author_command=shlex.split(author.split('run: |',1)[1].replace('\\\n',' '))
        script=next(i for i,value in enumerate(author_command) if value.endswith('/ci/author_native.py'))
        self.assertIn('--headless',author_command[script+1:])
        native_command=shlex.split(native.split('run: |',1)[1].replace('\\\n',' '))
        self.assertIn('xvfb-run',native_command)
        self.assertTrue(any(value.endswith('/ci/capture_native.py') for value in native_command))
        self.assertNotIn('--headless',native_command)
        for block in (author,native):
            self.assertNotRegex(block,re.compile(r'^        (if|continue-on-error):',re.M))
            self.assertIn('set -euo pipefail',block)

    def test_workflow_mode_guard_rejects_missing_or_optional_evidence(self):
        workflow=Path(__file__).resolve().parents[4]/'.github/workflows/dawnkeep-preview.yml'
        text=workflow.read_text()
        mutations=[text.replace('author_native.py" --headless','author_native.py"'),
                   text.replace('xvfb-run','env'),
                   text.replace('/ci/capture_native.py','/ci/verify_headless.py'),
                   text.replace('id: native_gate','id: native_gate\n        if: false'),
                   text.replace('id: author','id: author\n        continue-on-error: true')]
        for index,mutated in enumerate(mutations):
            with self.subTest(mutation=index),patch.object(Path,'read_text',return_value=mutated):
                with self.assertRaises(AssertionError):
                    self.test_headless_authoring_keeps_mandatory_rendered_native_gate()

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
