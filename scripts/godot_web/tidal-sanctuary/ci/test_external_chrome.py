"""Offline lifecycle fixtures. Does not launch Chrome or a renderer."""
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from external_chrome import external_chrome, OwnedChromeProfile, _budget, _read_endpoint, _stop_owned_process
import subprocess


class ExternalChromeTests(unittest.TestCase):
    def test_invalid_budgets(self):
        for value in (0, -1, 31, True, float('nan'), float('inf'), '5'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _budget(value)

    def test_endpoint_is_loopback_and_rejects_injection(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'DevToolsActivePort'
            self.assertIsNone(_read_endpoint(path))
            path.write_text('12345\n/devtools/browser/abc-123\n')
            self.assertEqual(_read_endpoint(path), 'ws://127.0.0.1:12345/devtools/browser/abc-123')
            for text in ('65536\n/devtools/browser/a', '0\n/devtools/browser/a', '123\n//evil/x', '123\n/devtools/browser/a?evil=1'):
                path.write_text(text)
                with self.assertRaises(RuntimeError):
                    _read_endpoint(path)

    def test_standard_headless_needs_no_display_and_adds_only_mode_flag(self):
        browser = SimpleNamespace(contexts=[object()])
        pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=Mock(return_value=browser)))
        report = {}
        with patch.dict(os.environ, {}, clear=True), patch('external_chrome.subprocess.Popen', side_effect=self.fake_process):
            with external_chrome(pw, '/bin/true', report=report, headed=False):
                pass
        self.assertEqual(self.arguments.count('--headless'), 1)
        self.assertEqual(report['mode'], 'standard-headless')
        self.assertFalse(report['headed'])
        for forbidden in ('--use-gl', '--use-angle', '--enable-gpu', '--disable-gpu',
                          '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--ozone-platform',
                          '--no-sandbox', '--disable-web-security'):
            self.assertFalse(any(arg.split('=')[0] == forbidden for arg in self.arguments))
        allowed = {'--headless', '--user-data-dir', '--remote-debugging-address', '--remote-debugging-port',
                   '--no-first-run', '--no-default-browser-check', '--enable-automation',
                   '--disable-dev-shm-usage', '--disable-background-timer-throttling', '--window-size'}
        self.assertEqual({arg.split('=')[0] for arg in self.arguments if arg.startswith('--')}, allowed)

    def test_headed_mode_requires_explicit_boolean_before_spawn(self):
        for value in (None, 0, 1, 'false'):
            with patch('external_chrome.subprocess.Popen') as spawn:
                with self.assertRaises(ValueError):
                    with external_chrome(None, '/bin/true', report={}, headed=value):
                        pass
                spawn.assert_not_called()

    def test_no_display_fails_before_spawn(self):
        with patch.dict(os.environ, {}, clear=True), patch('external_chrome.subprocess.Popen') as spawn:
            with self.assertRaises(RuntimeError):
                with external_chrome(None, '/bin/true', report={}):
                    pass
            spawn.assert_not_called()

    def fake_process(self, arguments, **kwargs):
        self.arguments = arguments
        self.spawn_kwargs = kwargs
        self.profile = Path(next(a.split('=', 1)[1] for a in arguments if a.startswith('--user-data-dir=')))
        (self.profile / 'DevToolsActivePort').write_text('12345\n/devtools/browser/test-id\n')
        process = Mock(pid=1234)
        process.poll.return_value = None
        process.wait.side_effect = lambda **kw: setattr(process.poll, 'return_value', 0)
        self.process = process
        return process

    def test_fresh_default_context_and_group_cleanup(self):
        context = object()
        browser = SimpleNamespace(contexts=[context])
        connect = Mock(return_value=browser)
        pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))
        report = {}
        with patch.dict(os.environ, {'DISPLAY': ':99'}), patch('external_chrome.subprocess.Popen', side_effect=self.fake_process):
            with external_chrome(pw, '/bin/true', report=report) as (got_browser, got_context):
                self.assertIs(got_browser, browser)
                self.assertIs(got_context, context)
                self.assertTrue(self.profile.exists())
        self.assertFalse(self.profile.exists())
        self.assertFalse(self.spawn_kwargs['start_new_session'])
        self.assertNotIn('--headless', self.arguments)
        self.assertEqual(report['mode'], 'headed')
        self.assertTrue(report['headed'])
        self.assertTrue(connect.call_args.kwargs['no_defaults'])
        self.assertGreater(connect.call_args.kwargs['timeout'], 0)
        self.assertIn('--remote-debugging-address=127.0.0.1', self.arguments)
        self.assertIn('--remote-debugging-port=0', self.arguments)
        self.assertFalse(any('no-sandbox' in arg or 'disable-web-security' in arg for arg in self.arguments))
        self.process.terminate.assert_called_once()
        self.assertTrue(report['owned_process_stopped'])

    def test_connect_failure_still_stops_owned_process(self):
        pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=Mock(side_effect=RuntimeError('attach failed'))))
        with patch.dict(os.environ, {'DISPLAY': ':99'}), patch('external_chrome.subprocess.Popen', side_effect=self.fake_process):
            with self.assertRaisesRegex(RuntimeError, 'attach failed'):
                with external_chrome(pw, '/bin/true', report={}):
                    pass
        self.process.terminate.assert_called_once()
        self.assertFalse(self.profile.exists())

    def test_profile_reopens_only_after_protocol_close_and_actual_exit(self):
        browser = Mock(contexts=[object()])
        pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=Mock(return_value=browser)))
        reports = []
        processes = []
        paths = []
        def spawn(arguments, **kwargs):
            path = Path(next(a.split('=', 1)[1] for a in arguments if a.startswith('--user-data-dir=')))
            self.assertFalse((path / 'DevToolsActivePort').exists())
            process = self.fake_process(arguments, **kwargs)
            process.pid = 1234 + len(processes)
            process.returncode = None
            def wait(**kwargs):
                process.poll.return_value = process.returncode = 0
                return 0
            process.wait.side_effect = wait
            processes.append(process); paths.append(path)
            return process
        bounded = Mock()
        with patch.dict(os.environ, {'DISPLAY': ':99'}), patch('external_chrome.subprocess.Popen', side_effect=spawn):
            with OwnedChromeProfile() as owned:
                for index in range(2):
                    report = {}; reports.append(report)
                    with external_chrome(pw, '/bin/true', report=report, profile=owned):
                        owned.close_normally(bounded)
                        with self.assertRaises(ValueError):
                            owned.close_normally(bounded)
                    self.assertTrue(Path(owned.name).exists())
        self.assertEqual(paths[0], paths[1])
        self.assertFalse(paths[0].exists())
        self.assertNotEqual(reports[0]['owned_pid'], reports[1]['owned_pid'])
        for report, process in zip(reports, processes):
            self.assertTrue(report['normal_close_completed'])
            self.assertFalse(report['fallback_cleanup_required'])
            process.terminate.assert_not_called()
        self.assertEqual(bounded.call_count, 2)
        self.assertTrue(all(call.args[1] == 'Browser.close' for call in bounded.call_args_list))

    def test_fallback_cleanup_cannot_authorize_profile_reuse(self):
        pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=Mock(return_value=SimpleNamespace(contexts=[object()]))))
        with patch.dict(os.environ, {'DISPLAY': ':99'}), patch('external_chrome.subprocess.Popen', side_effect=self.fake_process):
            with OwnedChromeProfile() as owned:
                report = {}
                with external_chrome(pw, '/bin/true', report=report, profile=owned):
                    pass
                self.assertFalse(report['normal_close_completed'])
                self.assertTrue(report['fallback_cleanup_required'])
                with self.assertRaises(ValueError):
                    with external_chrome(pw, '/bin/true', report={}, profile=owned):
                        pass

    def test_close_error_or_bad_exit_never_counts_as_normal(self):
        for failure in ('protocol', 'nonzero', 'timeout', 'already_exited'):
            with self.subTest(failure=failure):
                browser = Mock(contexts=[object()])
                pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=Mock(return_value=browser)))
                bounded = Mock(side_effect=RuntimeError('protocol failed') if failure == 'protocol' else None)
                with patch.dict(os.environ, {'DISPLAY': ':99'}), patch('external_chrome.subprocess.Popen', side_effect=self.fake_process):
                    with OwnedChromeProfile() as owned:
                        report = {}
                        with external_chrome(pw, '/bin/true', report=report, profile=owned):
                            if failure == 'nonzero':
                                def exit_bad(**kwargs):
                                    self.process.poll.return_value = self.process.returncode = 9
                                self.process.wait.side_effect = exit_bad
                            elif failure == 'timeout':
                                self.process.wait.side_effect = [subprocess.TimeoutExpired('chrome', 15), 0]
                            elif failure == 'already_exited':
                                self.process.poll.return_value = 0
                            with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                                owned.close_normally(bounded)
                            self.assertFalse(report['normal_close_completed'])
                            # Restore a terminal process for bounded fake cleanup.
                            self.process.poll.return_value = 0
                        with self.assertRaises(ValueError):
                            with external_chrome(pw, '/bin/true', report={}, profile=owned):
                                pass

    def test_arbitrary_profile_path_is_rejected(self):
        with patch.dict(os.environ, {'DISPLAY': ':99'}), patch('external_chrome.subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):
                with external_chrome(None, '/bin/true', report={}, profile='/tmp/existing'):
                    pass
            spawn.assert_not_called()

    def test_no_defaults_focus_setup_never_overrides_emulation(self):
        from focus_lifecycle import RealTargetFocus
        page = Mock()
        bounded = Mock()
        snapshot = {'focused': True, 'visible': True, 'overflow': False,
                    'records': [], 'document_url': 'http://127.0.0.1/', 'time_origin': 1000}
        passive = Mock(return_value=snapshot)
        probe = RealTargetFocus(page, bounded, passive, defaults_disabled=True)
        probe.settle_after_navigation()
        bounded.assert_not_called()
        self.assertTrue(probe.report['defaults_disabled'])
        self.assertFalse(probe.report['emulation_disabled_after_navigation'])
        self.assertTrue(probe.report['post_navigation_identity_verified'])
        with self.assertRaises(ValueError):
            probe.settle_after_navigation()
        passive.return_value = dict(snapshot, time_origin=2000)
        with self.assertRaises(ValueError):
            probe.snapshot()
        bounded.assert_not_called()

    def test_defaults_disabled_requires_explicit_boolean(self):
        from focus_lifecycle import RealTargetFocus
        for value in (1, 'true', None):
            with self.assertRaises(ValueError):
                RealTargetFocus(Mock(), Mock(), Mock(), defaults_disabled=value)

    def test_terminate_timeout_kills_only_owned_pid(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('chrome', 2), 0]
        _stop_owned_process(process)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)


if __name__ == '__main__':
    unittest.main()
