"""Host-free lifecycle contract tests. Not Godot production qualification."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('prism_candidate',Path(__file__).with_name('run_godot_repair.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class LifecycleTests(unittest.TestCase):
    def test_empty_native_result_is_not_success(self):
        for method in ('inspect','snapshot','configure','restore','pack_sources'):
            with self.assertRaises(AssertionError): module.validate_script_result(method,{})

    def test_configuration_requires_explicit_success(self):
        row={'configured':False,'before':{},'expected_args':'x','configured_frame':1}
        with self.assertRaises(AssertionError): module.validate_script_result('configure',row)
        row['configured']=True
        self.assertEqual(module.validate_script_result('configure',row),row)

    def test_actual_self_identity(self):
        row=module.process_identity(os.getpid())
        self.assertEqual(row['status'],'live')
        self.assertEqual(row['exe'],str(Path(sys.executable).resolve()))
        self.assertEqual(row['ppid'],os.getppid())

    def test_missing_is_gone(self):
        with patch.object(module,'process_identity',return_value={'status':'missing'}):
            self.assertTrue(module.original_gone({'pid':123,'starttime':4}))

    def test_unknown_is_not_gone(self):
        with patch.object(module,'process_identity',return_value={'status':'unknown'}):
            self.assertFalse(module.original_gone({'pid':123,'starttime':4}))

    def test_reused_pid_is_original_gone(self):
        with patch.object(module,'process_identity',return_value={'status':'live','starttime':5}):
            self.assertTrue(module.original_gone({'pid':123,'starttime':4}))

    def test_same_zombie_is_not_reaped(self):
        with patch.object(module,'process_identity',return_value={'status':'zombie','starttime':4}):
            self.assertFalse(module.original_gone({'pid':123,'starttime':4}))

    def test_census_permission_is_unknown(self):
        class Unreadable:
            def read_text(self): raise PermissionError('injected')
            def __str__(self): return '/proc/fixture/stat'
        with patch.object(module.Path,'glob',return_value=[Unreadable()]):
            result=module.group_census(123)
        self.assertTrue(result['inspection_errors'])

    def test_actual_owned_python_wait(self):
        process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)'],start_new_session=True)
        try:
            result=module.stop_owned(process)
            self.assertTrue(result['cleanup_confirmed'],result)
            self.assertIsNotNone(process.returncode)
        finally:
            if process.poll() is None: process.kill();process.wait()

    def test_unknown_census_never_confirms_cleanup(self):
        process=subprocess.Popen([sys.executable,'-c','pass'],start_new_session=True)
        process.wait()
        with patch.object(module,'group_census',return_value={'live_pids':[],'inspection_errors':['injected']}):
            result=module.stop_owned(process)
        self.assertFalse(result['cleanup_confirmed'])

    def test_reaped_leader_never_signals_reused_group(self):
        process=subprocess.Popen([sys.executable,'-c','pass'],start_new_session=True)
        process.wait()
        with patch.object(process,'send_signal') as signal_call,patch.object(module,'group_census',return_value={'live_pids':[999],'inspection_errors':[]}):
            result=module.stop_owned(process)
        signal_call.assert_not_called()
        self.assertFalse(result['cleanup_confirmed'])

if __name__=='__main__': unittest.main()
