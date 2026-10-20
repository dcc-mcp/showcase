"""Offline lifecycle fixtures. Does not launch Chrome or a renderer."""
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from external_chrome import external_chrome, _budget, _read_endpoint, _stop_owned_process
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
