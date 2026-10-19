import tempfile
import unittest
from pathlib import Path
from diagnose_web_groups import CASES, GROUP_ERROR, classify, patch_diagnostic_shell, write_project


class GroupIsolationTests(unittest.TestCase):
    def test_cases_isolate_physics_and_single_explicit_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            for case in CASES:
                root = Path(tmp) / case
                write_project(root, case)
                project = (root / 'project.godot').read_text()
                script = (root / 'main.gd').read_text()
                self.assertIn('2d/physics_engine="Dummy"', project)
                self.assertEqual('3d/physics_engine="GodotPhysics3D"' in project, case in ('empty-world','godot-world'))
                self.assertEqual('3d/physics_engine="Jolt Physics"' in project, case == 'jolt-world')
                self.assertEqual('StaticBody3D.new()' in script, case in ('godot-world','jolt-world'))
                self.assertEqual('move_and_slide()' in script, case in ('godot-world','jolt-world'))
                self.assertEqual('WorkerThreadPool.add_group_task' in script, case == 'explicit-group')
                self.assertEqual('WorkerThreadPool.wait_for_group_task_completion' in script, case == 'explicit-group')
            with self.assertRaises(ValueError):
                write_project(Path(tmp) / 'invalid', 'invalid')

    def test_reproducing_error_never_means_clean_exit(self):
        normal = ['GROUP_REPRO_READY {}', 'GROUP_REPRO_EXIT 0']
        baseline = classify('baseline', normal, [])
        self.assertTrue(baseline['diagnostic_expectation_matched'])
        self.assertTrue(baseline['clean_engine_exit'])
        log = normal + ['GROUP_REPRO_COMPLETED', GROUP_ERROR]
        reproduced = classify('explicit-group', log, [])
        self.assertTrue(reproduced['diagnostic_expectation_matched'])
        self.assertFalse(reproduced['clean_engine_exit'])
        self.assertEqual(reproduced['engine_errors'], [GROUP_ERROR])
        self.assertFalse(classify('baseline', log, [])['diagnostic_expectation_matched'])

    def test_jolt_requires_real_collision_receipt_and_zero_errors(self):
        normal = ['GROUP_REPRO_READY {}', 'GROUP_REPRO_EXIT 0']
        physical = 'GROUP_REPRO_PHYSICS {"blocked":true,"ray_hit":true,"backend":"Jolt Physics"}'
        for bad in (normal, normal+[physical.replace('true','false')],
                    normal+[physical.replace('Jolt Physics','GodotPhysics3D')], normal+[physical,GROUP_ERROR]):
            self.assertFalse(classify('jolt-world',bad,[])['diagnostic_expectation_matched'])
        result = classify('jolt-world',normal+[physical],[])
        self.assertTrue(result['diagnostic_expectation_matched'])
        self.assertTrue(result['clean_engine_exit'])
        self.assertTrue(classify('empty-world',normal,[])['diagnostic_expectation_matched'])
        self.assertFalse(classify('empty-world',normal+[GROUP_ERROR],[])['diagnostic_expectation_matched'])

    def test_godot_physics_repro_requires_active_collision_before_expected_error(self):
        log = ['GROUP_REPRO_READY {}','GROUP_REPRO_EXIT 0',GROUP_ERROR]
        self.assertFalse(classify('godot-world',log,[])['diagnostic_expectation_matched'])
        log.append('GROUP_REPRO_PHYSICS {"blocked":true,"ray_hit":true,"backend":"GodotPhysics3D"}')
        result = classify('godot-world',log,[])
        self.assertTrue(result['diagnostic_expectation_matched'])
        self.assertFalse(result['clean_engine_exit'])

    def test_missing_receipts_or_unexpected_errors_are_not_confirmation(self):
        normal = ['GROUP_REPRO_READY {}', 'GROUP_REPRO_COMPLETED', GROUP_ERROR, 'GROUP_REPRO_EXIT 0']
        for bad in (normal[:-1], normal[1:], [item for item in normal if item != 'GROUP_REPRO_COMPLETED'],
                    normal + ['SCRIPT ERROR: unexpected'], normal + [GROUP_ERROR]):
            self.assertFalse(classify('explicit-group', bad, [])['diagnostic_expectation_matched'])
        self.assertFalse(classify('explicit-group', normal, ['page crashed'])['diagnostic_expectation_matched'])

    def test_shell_uses_normal_quit_and_does_not_replace_engine(self):
        page = 'const engine = new Engine(GODOT_CONFIG);\nengine.startGame({});'
        result = patch_diagnostic_shell(page)
        self.assertIn("addEventListener('click', () => engine.requestQuit())", result)
        self.assertIn("'onExit': (code) => console.log('GROUP_REPRO_EXIT ' + code)", result)
        self.assertEqual(result.count('new Engine(GODOT_CONFIG)'), 1)
        for invalid in ('', page + page, page.replace('engine.startGame', 'different')):
            with self.assertRaises(RuntimeError):
                patch_diagnostic_shell(invalid)
