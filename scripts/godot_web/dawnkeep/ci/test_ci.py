import ast
import copy
import re
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from common import REQUIRED_FILES, copy_game, isolated_output, receipts, source_inventory, verify_inventory
from interaction import InputPlan, control_center, validate_state, support_pad
from author_native import editor_idle_sample, initial_copy_files
from export_web import patch_shell
from capture_native import mouse_location, pointer_click
from capture_browser import RequiredPayloadOutage, browser_executable, canvas_point


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
        names=REQUIRED_FILES+('verify_gameplay.gd','verify_shutdown.gd','assets/athena.glb','audio/theme.ogg')
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


class BrowserSelectionTests(unittest.TestCase):
    def test_canvas_mapping_respects_reserved_toolbar_and_scaling(self):
        geometry={'x':0,'y':44,'width':390,'height':800,'pixel_width':390,'pixel_height':800}
        self.assertEqual(canvas_point(geometry,195,200),(195,244))
        geometry.update(pixel_width=780,pixel_height=1600)
        self.assertEqual(canvas_point(geometry,390,400),(195,244))
        for x,y in [(-1,0),(780,0),(0,1600)]:
            with self.assertRaises(ValueError):canvas_point(geometry,x,y)
        geometry['height']=float('nan')
        with self.assertRaises(ValueError):canvas_point(geometry,0,0)

    def test_failed_viewport_is_preserved_and_fails_the_aggregate(self):
        tree=ast.parse((Path(__file__).parent/'capture_browser.py').read_text())
        loops=[node for node in ast.walk(tree) if isinstance(node,ast.For) and isinstance(node.target,ast.Tuple)
               and [getattr(item,'id',None) for item in node.target.elts]==['width','height','mobile']]
        self.assertEqual(len(loops),1)
        viewport_handlers=[h for node in ast.walk(loops[0]) if isinstance(node,ast.Try) for h in node.handlers if isinstance(h.name,str) and h.name=='error']
        outer=viewport_handlers[0]
        self.assertTrue(any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Constant) and t.slice.value=='blocker' for t in n.targets) for n in outer.body))
        self.assertFalse(any(isinstance(n,ast.Raise) for n in ast.walk(outer)))
        aggregates=[node for node in ast.walk(tree) if isinstance(node,ast.If) and ast.unparse(node.test)=="not report['passed']"]
        self.assertEqual(len(aggregates),1);self.assertIsInstance(aggregates[0].body[0],ast.Raise)

    def test_required_payload_stays_unavailable_across_loader_retries(self):
        outage=RequiredPayloadOutage();routes=[Mock() for _ in range(5)]
        for index,route in enumerate(routes,1):
            outage(route)
            route.abort.assert_called_once_with('failed');route.continue_.assert_not_called()
            self.assertEqual(outage.attempts,index)

    def test_payload_abort_failure_is_not_counted_or_ignored(self):
        outage=RequiredPayloadOutage();route=Mock();route.abort.side_effect=RuntimeError('route closed')
        with self.assertRaises(RuntimeError):outage(route)
        self.assertEqual(outage.attempts,0);route.continue_.assert_not_called()

    def test_explicit_browser_records_canonical_path_and_actual_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            browser=Path(tmp)/'chrome';browser.write_text('fixture');browser.chmod(0o700)
            with patch('capture_browser.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout='Google Chrome 155.0.8059.39\n')) as run:
                self.assertEqual(browser_executable(browser),{'executable_path':str(browser.resolve()),'executable_version':'Google Chrome 155.0.8059.39'})
                run.assert_called_once_with([str(browser.resolve()),'--version'],check=True,capture_output=True,text=True,timeout=10)

    def test_missing_or_nonexecutable_browser_fails_without_fallback(self):
        with tempfile.TemporaryDirectory() as tmp,patch('capture_browser.subprocess.run') as run:
            with self.assertRaises(FileNotFoundError):browser_executable(Path(tmp)/'missing')
            with self.assertRaises(ValueError):browser_executable(tmp)
            browser=Path(tmp)/'chrome';browser.write_text('fixture')
            with self.assertRaises(ValueError):browser_executable(browser)
            run.assert_not_called()

    def test_browser_version_failure_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            browser=Path(tmp)/'chrome';browser.write_text('fixture');browser.chmod(0o700)
            for error in (subprocess.TimeoutExpired([],10),subprocess.CalledProcessError(1,[])):
                with self.subTest(error=type(error).__name__),patch('capture_browser.subprocess.run',side_effect=error) as run:
                    with self.assertRaises(type(error)):browser_executable(browser)
                    self.assertEqual(run.call_count,1)
            with patch('capture_browser.subprocess.run',return_value=subprocess.CompletedProcess([],0,stdout='unknown browser')):
                with self.assertRaises(ValueError):browser_executable(browser)

    def test_workflow_strictly_selects_preinstalled_stable_chrome(self):
        text=(Path(__file__).resolve().parents[4]/'.github/workflows/dawnkeep-preview.yml').read_text()
        self.assertIn('CHROME=/opt/google/chrome/chrome',text)
        self.assertIn('test -f "$CHROME" && test -x "$CHROME"',text)
        self.assertIn('test "$(readlink -f "$CHROME")" = "$CHROME"',text)
        self.assertIn('"$CHROME" --version',text)
        self.assertIn('capture_browser.py" --chromium "$CHROME"',text)
        self.assertIn('python -m playwright install ffmpeg',text)
        self.assertNotIn('--no-sandbox',text)
        self.assertNotIn('sysctl',text)
        self.assertNotIn('aa-disable',text)



class AbilityObservationTests(unittest.TestCase):
    def state(self, sample=1, phase='wave', cooldown=0.0, dead=False):
        return {'schema':1,'sample_id':sample,'physics_frame':sample+1,'language':'en','paused':False,
                'phase':phase,'hero':{'position':[0,0,0],'dead':dead},'skills':{'e':{'cooldown':cooldown}},
                'ui':{'controls':{'skill_2':{'x':10,'y':20,'w':80,'h':40,'enabled':True}}}}

    def plan(self, states):
        observe=Mock(side_effect=states);click=Mock();report={}
        return InputPlan(observe,click,Mock(),Mock(),(1280,720),Mock(),report),click,report

    def test_fresh_cooldown_is_required_for_activation_credit(self):
        plan,click,report=self.plan([self.state(),self.state(2,cooldown=12)])
        self.assertTrue(plan.cast_observed('e'));click.assert_called_once_with(50,40)
        self.assertTrue(report['skill_attempts'][0]['activated'])
        self.assertIn('actual E ability activation',[x['name'] for x in report['checks']])

    def test_terminal_or_death_between_click_and_receipt_is_not_a_cast(self):
        for phase,dead in [('victory',False),('defeat',False),('wave',True)]:
            with self.subTest(phase=phase,dead=dead):
                plan,click,report=self.plan([self.state(),self.state(2,phase=phase,dead=dead)])
                self.assertFalse(plan.cast_observed('e'));click.assert_called_once()
                self.assertFalse(report['skill_attempts'][0]['activated'])
                self.assertNotIn('actual E ability activation',[x['name'] for x in report['checks']])

    def test_active_missed_click_and_stale_cooldown_still_timeout(self):
        for sample,cooldown in [(2,0),(1,12)]:
            with self.subTest(sample=sample,cooldown=cooldown):
                plan,click,report=self.plan([self.state(),self.state(sample,cooldown=cooldown)])
                with patch('interaction.time.monotonic',side_effect=[0,0,13]):
                    with self.assertRaises(TimeoutError):plan.cast_observed('e')
                click.assert_called_once();self.assertNotIn('skill_attempts',report)

    def test_unavailable_button_does_not_get_an_attempt_or_credit(self):
        state=self.state();state['ui']['controls']={}
        plan,click,report=self.plan([state])
        self.assertFalse(plan.cast_observed('e'));click.assert_not_called();self.assertEqual(report,{})

    def test_victory_still_requires_every_observed_ability(self):
        source=(Path(__file__).parent/'interaction.py').read_text()
        self.assertIn("if cast_skills!={'q','e','r'}:raise RuntimeError",source)


class ObserverTests(unittest.TestCase):
    def test_support_pad_keeps_hero_construction_exclusion(self):
        state=self.sample();state['hero']['position']=[-5,0,-1]
        state['pads']=[{'id':2,'position':{'x':-5,'y':0,'z':-1}}, {'id':0,'position':[-11,0,-4]}]
        state['ui']['pads']=[{'id':2,'x':570,'y':300},{'id':0,'x':490,'y':225}]
        self.assertEqual(support_pad(state,(1280,720))['id'],0)
        state['hero']['position']=[5,0,5]
        self.assertEqual(support_pad(state,(1280,720))['id'],2)
        with self.assertRaises(RuntimeError):support_pad(state,(100,100))

    def test_portrait_movement_projects_actual_empty_terrain(self):
        state=self.sample()
        state['ui']['pads']=[{'id':0,'x':120.666175842285,'y':290.921966552734},
                             {'id':1,'x':355.128479003906,'y':306.757080078125},
                             {'id':3,'x':37.3017997741699,'y':487.277801513672}]
        state['pads']=[{'id':0,'position':{'x':-11,'z':-4}},
                       {'id':1,'position':{'x':-5,'z':-7}},
                       {'id':3,'position':{'x':-8,'z':5}}]
        click=Mock();plan=InputPlan(lambda:state,click,Mock(),Mock(),(390,844),Mock(),{})
        self.assertTrue(plan.world_click(-8,2));click.assert_called_once()
        x,y=click.call_args.args
        self.assertGreater(x,5);self.assertLess(x,385);self.assertGreater(y,120);self.assertLess(y,594)
        self.assertGreater(((x-240.502471923828)**2+(y-414.436065673828)**2)**.5,40,
                           'Movement must not hit the support pad selected by the old fixed screen fraction')
        self.assertFalse(plan.world_click(1000,1000));self.assertEqual(click.call_count,1)


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
        self.assertEqual(ast.literal_eval(assignments['BROWSER_IGNORED_DEFAULT_ARGS']),
                         ['--mute-audio','--enable-unsafe-swiftshader'])
        options=assignments['options'];self.assertIsInstance(options,ast.Dict)
        values={key.value:value for key,value in zip(options.keys,options.values) if isinstance(key,ast.Constant)}
        self.assertTrue(ast.literal_eval(values['chromium_sandbox']))
        self.assertIsInstance(values['ignore_default_args'],ast.Name)
        self.assertEqual(values['ignore_default_args'].id,'BROWSER_IGNORED_DEFAULT_ARGS')

    def test_official_shell_patch_requires_all_markers(self):
        html='<script src="index.js"></script>\nconst GODOT_CONFIG = {"extensionLibs":[]};\nconst engine = new Engine(GODOT_CONFIG);\nfunction displayFailureNotice(err) {}'
        patched,config=patch_shell(html)
        self.assertIn('dawnkeepShell.failed(err)',patched);self.assertFalse(config['ensureCrossOriginIsolationHeaders'])
        self.assertEqual(config['canvasResizePolicy'],0)
        with self.assertRaises(RuntimeError):patch_shell(html.replace('function displayFailureNotice','function otherName'))


if __name__=='__main__':unittest.main()
