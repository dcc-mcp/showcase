"""Pure smoke packaging/deadline fixtures. They never launch Chrome or render PCM."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import check_audio_observer_browser as smoke


class AudioObserverSmokeFixtures(unittest.TestCase):
    def source(self, root):
        source = root / "source"
        (source / "assets/audio").mkdir(parents=True)
        (source / "web_audio.js").write_bytes(b"// original backend fixture\n")
        for name in smoke.AUDIO_FILES.values():
            (source / "assets/audio" / name).write_bytes(("original bytes: " + name).encode())
        return source

    def test_served_backend_and_all_five_assets_keep_exact_original_bytes_and_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.source(Path(temporary))
            resources, hashes = smoke.fixture_resources(source)
            self.assertEqual(len(resources), 7)
            for url, (body, _) in resources.items():
                if url == "/":
                    continue
                self.assertEqual(body, (source / url.lstrip("/")).read_bytes())
                self.assertEqual(hashes[url.lstrip("/")]["sha256"], hashlib.sha256(body).hexdigest())
            html = resources["/"][0].decode()
            self.assertIn("TidalWebAudio.initialize(", html)
            self.assertIn("onclick=\"TidalWebAudio.start('observer_fixture_button')\"", html)
            self.assertNotIn("AudioContext", html)
            self.assertNotIn("createBuffer", html)
            self.assertNotIn("resume(", html)
            self.assertEqual(html.count("<button "), 4)

    def test_missing_lfs_empty_and_escaped_sources_fail_without_fallback(self):
        for failure in ("missing", "lfs", "empty", "escape"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source = self.source(root)
                target = source / "assets/audio/chart_read.wav"
                if failure == "missing": target.unlink()
                if failure == "empty": target.write_bytes(b"")
                if failure == "lfs": target.write_text("version https://git-lfs.github.com/spec/v1\n")
                if failure == "escape":
                    outside = root / "unrelated.wav"; outside.write_bytes(b"not original")
                    target.unlink(); target.symlink_to(outside)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    smoke.fixture_resources(source)

    def test_optional_graphics_fixture_is_real_webgl2_not_audio_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            source=self.source(Path(temporary))
            resources,_=smoke.fixture_resources(source, graphics_probe=True)
            html=resources["/"][0].decode()
            self.assertIn("getContext('webgl2')",html)
            self.assertIn("gl.readPixels(0,0,1,1",html)
            self.assertNotIn("AudioContext",html)
            self.assertNotIn("resume(",html)
            self.assertEqual(html.count("<button "),4)

    def test_webgl2_probe_requires_actual_valid_pixel_and_context(self):
        good={"available":True,"version":"WebGL 2.0 fixture","pixel":[51,102,153,255],"error":0,"context_lost":False}
        self.assertEqual(smoke.validate_graphics_probe(good),good)
        for bad in ({}, {**good,"available":False}, {**good,"pixel":[0,0,0,0]},
                {**good,"version":"WebGL 1.0"}, {**good,"error":1280}, {**good,"context_lost":True},
                {**good,"pixel":[True,102,153,255]}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                smoke.validate_graphics_probe(bad)

    def test_report_write_is_complete_and_does_not_leave_a_partial_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            value = {"passed": False, "error": "original failure", "stage": "cue"}
            smoke.save_report(output, value)
            self.assertEqual(json.loads((output / "receipt.json").read_text()), value)
            self.assertFalse((output / ".receipt.json.tmp").exists())

    def supervised(self, output, process, result=None, headed=False):
        def finish(*args, **kwargs):
            smoke.save_report(output, result or {"passed": True, "status": "passed", "scope": smoke.SCOPE})
            return 0 if result is None or result["passed"] else 1
        process.wait.side_effect = finish
        with patch.object(smoke.subprocess, "Popen", return_value=process) as launch, contextlib.redirect_stdout(io.StringIO()):
            code = smoke.supervise(Path("/verified/chrome"), Path("/selected/source"), output, headed=headed)
        return code, launch

    def test_success_requires_real_worker_success_and_preserves_explicit_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); process = Mock(pid=1234)
            code, launch = self.supervised(output, process)
            self.assertEqual(code, 0)
            command = launch.call_args.args[0]
            self.assertIn("--observer-worker", command)
            self.assertEqual(command[command.index("--chromium") + 1], "/verified/chrome")
            self.assertEqual(command[command.index("--source") + 1], "/selected/source")
            self.assertTrue(launch.call_args.kwargs["start_new_session"])
            report = json.loads((output / "receipt.json").read_text())
            self.assertTrue(report["passed"])
            self.assertEqual(report["maximum_seconds"], 30)
            self.assertIn("no Godot gameplay", report["scope"])

    def test_explicit_headed_flag_survives_supervision_without_default_fallback(self):
        for headed in (False,True):
            with self.subTest(headed=headed), tempfile.TemporaryDirectory() as temporary:
                code,launch=self.supervised(Path(temporary),Mock(pid=1234),headed=headed)
                self.assertEqual(code,0)
                self.assertEqual('--headed' in launch.call_args.args[0],headed)

    def test_no_defaults_probe_propagates_and_reaps_its_owned_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            process = Mock(pid=1234)
            def finish(**kwargs):
                smoke.save_report(output, {"passed": True, "status": "passed"})
                return 0
            process.wait.side_effect = finish
            with patch.object(smoke.subprocess, "Popen", return_value=process) as launch, \
                    patch.object(smoke.os, "killpg") as kill, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(smoke.supervise(Path("/chrome"), Path("/source"), output,
                    standard_headless=True, no_defaults=True, require_webgl2=True), 0)
            self.assertIn("--no-defaults", launch.call_args.args[0])
            self.assertIn("--standard-headless", launch.call_args.args[0])
            self.assertIn("--require-webgl2", launch.call_args.args[0])
            self.assertNotIn("--headed", launch.call_args.args[0])
            kill.assert_called_once_with(1234, signal.SIGKILL)

    def test_failed_owned_descendant_cleanup_cannot_qualify_probe(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            process = Mock(pid=1234)
            def finish(**kwargs):
                smoke.save_report(output, {"passed": True, "status": "passed"})
                return 0
            process.wait.side_effect = finish
            with patch.object(smoke.subprocess, "Popen", return_value=process), \
                    patch.object(smoke.os, "killpg", side_effect=OSError("cleanup failed")), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(smoke.supervise(Path("/chrome"), Path("/source"), output,
                    headed=True, no_defaults=True), 1)
            self.assertFalse(json.loads((output / "receipt.json").read_text())["passed"])

    def test_worker_validation_failure_retains_exact_stage_and_reason(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); process = Mock(pid=1234)
            result = {"passed": False, "status": "failed", "stage": "real-cue-and-source-bound-pcm", "error": "missing actual channel"}
            code, _ = self.supervised(output, process, result)
            report = json.loads((output / "receipt.json").read_text())
            self.assertEqual(code, 1); self.assertEqual(report["error"], result["error"])
            self.assertEqual(report["stage"], result["stage"]); self.assertEqual(report["worker_exit_code"], 1)

    def test_global_deadline_kills_only_owned_group_and_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            process = Mock(pid=4321)
            process.wait.side_effect = [subprocess.TimeoutExpired("owned fixture", 27), -9]
            with patch.object(smoke.subprocess, "Popen", return_value=process), patch.object(smoke.os, "killpg") as kill, contextlib.redirect_stdout(io.StringIO()):
                code = smoke.supervise(Path("/verified/chrome"), Path("/source"), output)
            kill.assert_called_once_with(4321, signal.SIGKILL)
            self.assertLessEqual(process.wait.call_args_list[0].kwargs["timeout"], 27)
            self.assertEqual(process.wait.call_args_list[1].kwargs["timeout"], 2)
            report = json.loads((output / "receipt.json").read_text())
            self.assertEqual(code, 1); self.assertFalse(report["passed"])
            self.assertIn("work budget", report["deadline_error"])

    def test_launcher_failure_is_a_saved_failure_not_an_unfinished_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with patch.object(smoke.subprocess, "Popen", side_effect=OSError("driver unavailable")), contextlib.redirect_stdout(io.StringIO()):
                code = smoke.supervise(Path("/verified/chrome"), Path("/source"), output)
            report = json.loads((output / "receipt.json").read_text())
            self.assertEqual(code, 1); self.assertEqual(report["status"], "failed")
            self.assertIn("driver unavailable", report["launcher_error"])

    def test_late_success_cannot_exceed_total_time_ceiling(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary); process = Mock(pid=1234)
            with patch.object(smoke.time, "monotonic", side_effect=[0, 0, 31]):
                code, _ = self.supervised(output, process)
            report = json.loads((output / "receipt.json").read_text())
            self.assertEqual(code, 1); self.assertFalse(report["passed"])
            self.assertIn("total 30-second", report["deadline_error"])




class RealTargetFocusFixtures(unittest.TestCase):
    def snapshot(self, active, records=None):
        return {'focused':active,'visible':active,'overflow':False,'records':records or [],'document_url':'http://127.0.0.1/fixture','time_origin':1000}

    def events(self, active, trusted=True):
        return [{'type':'focus' if active else 'blur','trusted':trusted,'visible':active},
                {'type':'visibilitychange','trusted':trusted,'visible':active}]

    def test_only_real_target_events_and_matching_dom_state_qualify(self):
        from focus_lifecycle import validate_focus_transition
        for active in (False, True):
            before = self.snapshot(not active)
            after = self.snapshot(active, self.events(active))
            self.assertEqual(validate_focus_transition(before, after, active)['active'], active)
            for failure in ('synthetic','wrong_state','missing_window','mismatched_visibility','overflow','lost_history'):
                import copy
                broken = copy.deepcopy(after); old = copy.deepcopy(before)
                if failure == 'synthetic': broken['records'][0]['trusted'] = False
                if failure == 'wrong_state': broken['focused'] = not active
                if failure == 'missing_window': broken['records'] = broken['records'][1:]
                if failure == 'mismatched_visibility': broken['records'][-1]['visible'] = not active
                if failure == 'overflow': broken['overflow'] = True
                if failure == 'lost_history': old['records'] = [{'type':'previous'}]
                with self.subTest(active=active, failure=failure), self.assertRaises(ValueError):
                    validate_focus_transition(old, broken, active)

    def test_real_visible_window_blur_qualifies_without_claiming_hidden_tab(self):
        from focus_lifecycle import validate_focus_transition,wait_focus_state
        before=self.snapshot(True)
        after=self.snapshot(False,[{'type':'blur','trusted':True,'visible':True}])
        after['visible']=True
        result=validate_focus_transition(before,after,False)
        self.assertTrue(result['visible']);self.assertFalse(result['focused'])
        self.assertIn('hidden-tab and OS focus not established',result['scope'])
        self.assertIs(wait_focus_state(Mock(),Mock(return_value=after),False),after)
        restored=self.snapshot(True,after['records']+[{'type':'focus','trusted':True,'visible':True}])
        self.assertTrue(validate_focus_transition(after,restored,True)['focused'])
        for field,value in (('focused',False),('visible',False),('visible',1),('visible',None)):
            broken=dict(restored);broken[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                validate_focus_transition(after,broken,True)

    def test_optional_visibility_events_must_reconcile_with_actual_snapshot(self):
        from focus_lifecycle import validate_focus_transition
        before=self.snapshot(True)
        for visible in (False,True):
            after=self.snapshot(False,self.events(False));after['visible']=visible
            after['records'][-1]['visible']=visible
            self.assertEqual(validate_focus_transition(before,after,False)['visible'],visible)
            for invalid in (not visible,None,1):
                after['records'][-1]['visible']=invalid
                with self.subTest(visible=visible,invalid=invalid),self.assertRaises(ValueError):
                    validate_focus_transition(before,after,False)

    def test_invalid_setup_budget_never_consumes_or_executes_emulation_attempt(self):
        from focus_lifecycle import RealTargetFocus
        for value in (0,-1,31,float('nan'),float('inf'),True,'3',None):
            bounded=Mock();probe=RealTargetFocus(Mock(),bounded,Mock(return_value=self.snapshot(True)))
            with self.subTest(value=value),self.assertRaises(ValueError):probe.settle_after_navigation(timeout=value)
            self.assertFalse(probe._settle_attempted);bounded.assert_not_called()

    def test_prepare_removes_override_once_and_retains_session_without_event_dispatch(self):
        from focus_lifecycle import prepare_real_focus, FOCUS_INIT
        page = Mock(); call = Mock()
        session = prepare_real_focus(page, call)
        self.assertIs(session, page.context.new_cdp_session.return_value)
        call.assert_not_called()
        page.add_init_script.assert_called_once_with(script=FOCUS_INIT)
        session.detach.assert_not_called()
        self.assertNotIn('dispatchEvent', FOCUS_INIT)
        self.assertNotIn('.focus()', FOCUS_INIT)
        self.assertIn('event.isTrusted', FOCUS_INIT)

    def test_wait_rejects_overflow_and_times_out_without_faking_state(self):
        from focus_lifecycle import wait_focus_state
        page = Mock(); passive = Mock(return_value=self.snapshot(True))
        self.assertEqual(wait_focus_state(page, passive, True)['focused'], True)
        passive.return_value['overflow'] = True
        with self.assertRaises(ValueError): wait_focus_state(page, passive, True)
        passive.return_value = self.snapshot(False)
        with patch('focus_lifecycle.time.monotonic', side_effect=[0,4]), self.assertRaises(TimeoutError):
            wait_focus_state(page, passive, True, timeout=3)
        page.bring_to_front.assert_not_called()

    def test_late_success_is_rejected_and_remaining_budget_reaches_passive_call(self):
        from focus_lifecycle import wait_focus_state
        page = Mock(); passive = Mock(return_value=self.snapshot(True))
        with patch('focus_lifecycle.time.monotonic',side_effect=[0,1,4]), self.assertRaises(TimeoutError):
            wait_focus_state(page,passive,True,timeout=3)
        self.assertEqual(passive.call_args.kwargs['timeout'],2)

    def test_switch_invokes_only_real_browser_activation_and_retains_failure_diagnostic(self):
        from focus_lifecycle import RealTargetFocus
        page = Mock(); bounded = Mock(); passive = Mock()
        probe = RealTargetFocus(page,bounded,passive); other = Mock()
        passive.return_value = self.snapshot(True)
        probe.settle_after_navigation()
        passive.side_effect = [self.snapshot(True),self.snapshot(False,self.events(False))]
        probe.switch_to(other,False)
        self.assertEqual(bounded.call_args.args[1], 'Page.bringToFront')
        other.bring_to_front.assert_not_called()
        self.assertTrue(probe.report['transitions'][0]['passed'])
        passive.side_effect = [self.snapshot(False),self.snapshot(True,self.events(True,False))]
        with patch('focus_lifecycle.time.monotonic',side_effect=[0,0,0,0,0,0,4]),self.assertRaises(TimeoutError):
            probe.switch_to(page,True)
        self.assertFalse(probe.report['transitions'][1]['passed'])
        self.assertIn('after',probe.report['transitions'][1])

    def test_settle_occurs_once_after_navigation_and_never_during_switch(self):
        from focus_lifecycle import RealTargetFocus
        page=Mock(); bounded=Mock(); passive=Mock(return_value=self.snapshot(True))
        probe=RealTargetFocus(page,bounded,passive)
        bounded.assert_not_called()
        with self.assertRaises(ValueError): probe.switch_to(Mock(),False)
        bounded.assert_not_called()
        probe.settle_after_navigation()
        self.assertEqual(bounded.call_args.args[1:3],('Emulation.setFocusEmulationEnabled',{'enabled':False}))
        self.assertTrue(probe.report['emulation_disabled_after_navigation'])
        with self.assertRaises(ValueError): probe.settle_after_navigation()
        self.assertEqual(bounded.call_count,1)
        for field,value in (('time_origin',1001),('document_url','http://127.0.0.1/other')):
            state=self.snapshot(True);state[field]=value;passive.return_value=state
            with self.assertRaises(ValueError): probe.switch_to(Mock(),False)
            self.assertEqual(bounded.call_count,1)

    def test_navigation_during_settle_fails_and_cannot_retry_toggle(self):
        from focus_lifecycle import RealTargetFocus
        old=self.snapshot(True);new=self.snapshot(True);new['time_origin']=2000
        page=Mock();bounded=Mock();passive=Mock(side_effect=[old,new])
        probe=RealTargetFocus(page,bounded,passive)
        with self.assertRaises(ValueError):probe.settle_after_navigation()
        with self.assertRaises(ValueError):probe.settle_after_navigation()
        self.assertEqual(bounded.call_count,1)
        self.assertFalse(probe.report['emulation_disabled_after_navigation'])

    def test_headed_hidden_lifecycle_adds_real_visibility_without_erasing_visible_blur(self):
        from focus_lifecycle import validate_focus_transition
        for active in (False,True):
            before=self.snapshot(not active);after=self.snapshot(active,self.events(active))
            result=validate_focus_transition(before,after,active,require_hidden_lifecycle=True)
            self.assertIn('hidden/visible',result['scope'])
            after['records']=after['records'][:1]
            with self.assertRaises(ValueError):validate_focus_transition(before,after,active,True)
        after=self.snapshot(False,[{'type':'blur','trusted':True,'visible':True}]);after['visible']=True
        self.assertFalse(validate_focus_transition(self.snapshot(True),after,False)['focused'])
        with self.assertRaises(ValueError):validate_focus_transition(self.snapshot(True),after,False,True)

    def test_genuine_same_window_tabs_required_and_no_window_mutation_used(self):
        from focus_lifecycle import RealTargetFocus
        for other_id in (7,8):
            page=Mock();other=Mock();bounded=Mock();passive=Mock(return_value=self.snapshot(True))
            probe=RealTargetFocus(page,bounded,passive);companion=RealTargetFocus(other,bounded,passive)
            probe.settle_after_navigation();companion.settle_after_navigation();bounded.reset_mock()
            bounded.side_effect=[{'targetInfo':{'targetId':'game','url':'http://127.0.0.1/fixture'}},{'windowId':7,'bounds':{'windowState':'normal'}},
                {'targetInfo':{'targetId':'other','url':'http://127.0.0.1/fixture'}},{'windowId':other_id,'bounds':{'windowState':'normal'}}]
            reads_before=passive.call_count
            if other_id==7:self.assertTrue(probe.verify_same_window_tabs(companion)['passed'])
            else:
                with self.assertRaises(ValueError):probe.verify_same_window_tabs(companion)
            self.assertEqual(passive.call_count,reads_before)
            self.assertEqual([x.args[1] for x in bounded.call_args_list],
                ['Target.getTargetInfo','Browser.getWindowForTarget','Target.getTargetInfo','Browser.getWindowForTarget'])
        probe=RealTargetFocus(Mock(),Mock(),Mock())
        with self.assertRaises(ValueError):probe.switch_to(Mock(),False,require_hidden_lifecycle=True)

    def test_constructor_hidden_gate_cannot_be_downgraded_or_target_replaced(self):
        from focus_lifecycle import RealTargetFocus
        page=Mock();other=Mock();bounded=Mock();passive=Mock(return_value=self.snapshot(True))
        probe=RealTargetFocus(page,bounded,passive,require_hidden=True)
        companion=RealTargetFocus(other,bounded,passive,require_hidden=True)
        probe.settle_after_navigation();companion.settle_after_navigation()
        with self.assertRaises(ValueError):probe.switch_to(other,False,require_hidden_lifecycle=False)
        bounded.side_effect=[{'targetInfo':{'targetId':'game','url':'http://127.0.0.1/fixture'}},{'windowId':7,'bounds':{}},
            {'targetInfo':{'targetId':'other','url':'http://127.0.0.1/fixture'}},{'windowId':7,'bounds':{}}]
        probe.verify_same_window_tabs(companion);bounded.reset_mock();bounded.side_effect=None
        with self.assertRaises(ValueError):probe.switch_to(Mock(),False)
        bounded.assert_not_called()
        passive.side_effect=[self.snapshot(True),self.snapshot(False,self.events(False))]
        with patch.object(probe,'verify_same_window_tabs',return_value={'passed':True}) as verify:
            probe.switch_to(other,False,require_hidden_lifecycle=False)
            verify.assert_called_once()
        self.assertTrue(probe.report['transitions'][-1]['require_hidden_lifecycle'])

    def test_smoke_preserves_ceiling_and_uses_real_target_with_strict_audio_proofs(self):
        source = Path(smoke.__file__).read_text()
        self.assertEqual(smoke.MAX_SECONDS,30); self.assertEqual(smoke.WORK_SECONDS,27)
        self.assertIn('hidden_required = headed or standard_headless',source)
        self.assertIn('focus.switch_to(other, False, require_hidden_lifecycle=hidden_required)',source)
        self.assertIn('focus.switch_to(page, True, require_hidden_lifecycle=hidden_required)',source)
        self.assertIn('validate_focus_suspension(focus_before, away, returned',source)
        self.assertIn('resume_mark["wall_ms"], returned["wall_ms"], 1.2, True',source)
        self.assertNotIn('dispatchEvent(',source)
        self.assertIn('pw.chromium.launch(headless=not headed',source)
        self.assertIn('focus.verify_same_window_tabs(other_focus)',source)
        self.assertIn('if headed and not os.environ.get("DISPLAY")',source)


if __name__ == "__main__":
    unittest.main()
