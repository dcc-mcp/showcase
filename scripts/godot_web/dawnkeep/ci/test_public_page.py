"""Guard tests, not substitutes for actual hosted-browser publication acceptance."""
import ast
import hashlib
import json
import os
import shlex
import stat
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import public_page as gate


class PublicBoundaryTests(unittest.TestCase):
    def test_only_exact_official_deployed_url_is_accepted(self):
        self.assertEqual(gate.deployed_base(gate.OFFICIAL_BASE), gate.OFFICIAL_BASE)
        for url in ('https://example.com/', 'http://dcc-mcp.github.io/showcase/',
                    'https://dcc-mcp.github.io/', 'https://dcc-mcp.github.io/showcase',
                    'https://dcc-mcp.github.io/showcase/?override=1',
                    'https://dcc-mcp.github.io.evil.example/showcase/',
                    'https://user@dcc-mcp.github.io/showcase/'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                gate.deployed_base(url)

    def test_same_origin_and_project_path_boundary(self):
        base = gate.OFFICIAL_BASE
        self.assertTrue(gate.in_site(base + 'games/dawnkeep-defense/?lang=en', base))
        for url in ('http://dcc-mcp.github.io/showcase/a', 'https://dcc-mcp.github.io/elsewhere/',
                    'https://dcc-mcp.github.io/showcase-evil/', 'https://evil.example/showcase/',
                    'https://dcc-mcp.github.io:444/showcase/',
                    'https://dcc-mcp.github.io/showcase/../private',
                    'https://dcc-mcp.github.io/showcase/%2e%2e/private'):
            with self.subTest(url=url):
                self.assertFalse(gate.in_site(url, base))

    def test_canonical_artifact_paths_only(self):
        self.assertEqual(gate.public_path('play/dawnkeep-defense/index.html'),
                         'play/dawnkeep-defense/index.html')
        for value in ('', '../x', '/x', 'a/../x', 'a/./x', 'a//x', 'a\\x',
                      'https://example.com/a', 'a?query', 'a#fragment', 'a/%2e%2e/x'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                gate.public_path(value)

    def test_engine_request_detection_includes_query_hash_named_pck_and_shared_runtime(self):
        for url in ('https://h/play/dawnkeep-defense/' + gate.PCK_NAME + '?v=2',
                    'https://h/play/runtime/godot-4.6.3.js', 'https://h/runtime.wasm'):
            self.assertTrue(gate.engine_request(url))
        for url in ('https://h/poster.jpg', 'https://h/movie.mp4', 'https://h/assets/games.js'):
            self.assertFalse(gate.engine_request(url))

    def test_hash_and_size_both_required(self):
        data = b'frozen actual bytes'
        entry = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        self.assertEqual(gate.verify_bytes(data, entry, 'pck'), entry)
        for bad in ({**entry, 'bytes': len(data) + 1}, {**entry, 'sha256': '0' * 64}):
            with self.assertRaises(ValueError):
                gate.verify_bytes(data, bad, 'pck')

    def test_cross_origin_redirect_and_wrong_http_status_fail_closed(self):
        for status, url in ((302, gate.OFFICIAL_BASE + 'redirect'), (200, 'https://evil.example/pck')):
            response = Mock(status=status, url=url)
            request = Mock()
            request.get.return_value = response
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(RuntimeError):
                gate.fetch_artifacts(request, gate.OFFICIAL_BASE,
                                     {'assets': {'play/a.pck': {}}, 'films': [], 'pck': 'play/a.pck'},
                                     Path(tmp), {})
            response.body.assert_not_called()
            self.assertEqual(request.get.call_args.kwargs['max_redirects'], 0)


class SourceBindingTests(unittest.TestCase):
    def test_expected_source_is_full_sha_and_matches_checkout(self):
        for value in (None, '957c1d3', 'A' * 40, 'x' * 40):
            with self.subTest(value=value), self.assertRaises(ValueError):
                gate.source_receipt(Path('.'), value)
        with patch.object(gate.subprocess, 'check_output', return_value='b' * 40 + '\n'):
            with self.assertRaises(ValueError):
                gate.source_receipt(Path('.'), 'a' * 40)

    def test_dirty_tracked_checkout_is_rejected(self):
        with patch.object(gate.subprocess, 'check_output', return_value='a' * 40 + '\n'), \
                patch.object(gate.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['git'])):
            with self.assertRaisesRegex(RuntimeError, 'Tracked index differs'):
                gate.source_receipt(Path('.'), 'a' * 40)

    def test_receipt_binds_exact_scripts_and_expected_head(self):
        with patch.object(gate.subprocess, 'check_output', return_value='a' * 40 + '\n'), \
                patch.object(gate.subprocess, 'run'), \
                patch.object(gate, 'verify_tracked_bytes', return_value={'tracked_blobs_checked': 3}):
            result = gate.source_receipt(Path('.'), 'a' * 40)
        self.assertEqual(result['expected_head_sha'], result['checkout_head_sha'])
        self.assertIn('public_page.py', {row['name'] for row in result['acceptance_scripts']})
        self.assertTrue(all(len(row['sha256']) == 64 for row in result['acceptance_scripts']))

    def test_frozen_publication_requires_known_pck_and_one_source_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'play').mkdir()
            (root / gate.CASE_ROOT).mkdir(parents=True)
            play = {'schema_version': 1,
                    'files': [{'path': gate.PLAY_ROOT + gate.PCK_NAME, 'sha256': '0' * 64, 'bytes': 1}],
                    'demos': [{'case_slug': gate.SLUG, 'url': gate.PLAY_ROOT + 'index.html'}]}
            (root / 'play/manifest.json').write_text(json.dumps(play))
            (root / gate.CASE_ROOT / 'manifest.json').write_text(json.dumps({'schema_version': 1, 'files': []}))
            with self.assertRaisesRegex(RuntimeError, 'frozen PCK'):
                gate.artifact_inventory(root)
            play['files'][0]['sha256'] = gate.PCK_SHA256
            (root / 'play/manifest.json').write_text(json.dumps(play))
            with self.assertRaisesRegex(RuntimeError, 'source ZIP'):
                gate.artifact_inventory(root)


class RawTrackedSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitattributes').write_text('*.bin filter=fixture\n')
        (self.root / 'image.bin').write_bytes(b'actual committed image bytes\x00\xff')
        self.git('add', '.gitattributes', 'image.bin')
        self.git('-c', 'user.name=Acceptance fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'Raw fixture')
        self.head = self.git('rev-parse', 'HEAD').stdout.strip()

    def git(self, *arguments, check=True):
        return subprocess.run(['git', '-C', str(self.root), *arguments],
                              check=check, capture_output=True, text=True)

    def filtered_diff(self):
        # Simulate the exact clean-filter mismatch without changing any Git
        # config or disabling filters. The fixture command applies to one diff.
        command = (shlex.quote(sys.executable) + ' -c ' + shlex.quote(
            'import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b"synthetic pointer\\n")'))
        path = self.root / 'image.bin'
        info = path.stat()
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 10_000_000_000))
        return self.git('-c', 'filter.fixture.clean=' + command,
                        'diff', '--exit-code', 'HEAD', '--', check=False)

    def test_raw_committed_media_passes_even_when_clean_filter_reports_pointer_diff(self):
        filtered = self.filtered_diff()
        self.assertEqual(filtered.returncode, 1)
        self.assertIn('image.bin', filtered.stdout)
        result = gate.source_receipt(self.root, self.head)
        self.assertTrue(result['tracked_checkout_matches_head_bytes_and_modes'])
        self.assertEqual(result['tracked_source']['tracked_blobs_checked'], 2)

    def test_actual_byte_mutation_remains_fatal_under_that_same_filter(self):
        (self.root / 'image.bin').write_bytes(b'actually changed bytes')
        self.assertEqual(self.filtered_diff().returncode, 1)
        with self.assertRaisesRegex(RuntimeError, 'image.bin: raw tracked bytes differ'):
            gate.source_receipt(self.root, self.head)

    def test_executable_mode_mutation_is_fatal(self):
        path = self.root / 'image.bin'
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        with self.assertRaisesRegex(RuntimeError, 'image.bin: tracked executable mode differs'):
            gate.verify_tracked_bytes(self.root)

    def test_missing_tracked_file_is_fatal_with_named_diagnostic(self):
        (self.root / 'image.bin').unlink()
        with self.assertRaisesRegex(RuntimeError, 'Tracked source differs.*image.bin'):
            gate.verify_tracked_bytes(self.root)

    def test_staged_changes_remain_fatal_even_when_worktree_bytes_match_head(self):
        path = self.root / 'image.bin'
        original = path.read_bytes()
        path.write_bytes(b'changed staged blob')
        self.git('add', 'image.bin')
        path.write_bytes(original)
        gate.verify_tracked_bytes(self.root)
        with self.assertRaisesRegex(RuntimeError, 'Tracked index differs.*image.bin'):
            gate.source_receipt(self.root, self.head)


class BrowserPolicyTests(unittest.TestCase):
    def test_launch_keeps_browser_security_and_no_fallback_binary(self):
        self.assertEqual(gate.BROWSER_ARGS, ['--disable-dev-shm-usage'])
        self.assertEqual(gate.BROWSER_IGNORED_DEFAULT_ARGS, ['--mute-audio', '--enable-unsafe-swiftshader'])
        source = Path(gate.__file__).read_text()
        tree = ast.parse(source)
        launches = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == 'launch']
        self.assertEqual(len(launches), 1)
        options = {item.arg: ast.unparse(item.value) for item in launches[0].keywords}
        self.assertEqual(options['chromium_sandbox'], 'True')
        self.assertEqual(options['executable_path'], "selected['executable_path']")
        self.assertNotIn('--no-sandbox', source)
        self.assertNotIn('--disable-web-security', source)

    def test_missing_canonical_chrome_fails_without_fallback(self):
        with patch.object(gate.Path, 'is_file', return_value=False), \
                patch.object(gate, 'browser_executable') as lookup:
            with self.assertRaises(ValueError):
                gate.installed_chrome()
            lookup.assert_not_called()

    def test_native_inputs_reuse_passive_input_plan_and_real_coordinates(self):
        source = Path(gate.__file__).read_text()
        self.assertIn('return InputPlan(', source)
        self.assertIn('canvas_point(geo, x, y)', source)
        self.assertIn('self.page.touchscreen.tap', source)
        self.assertIn('DAWNKEEP_FRAME_READY', source)
        self.assertIn('DAWNKEEP_STATE', source)
        for forbidden in ('execute_script', 'evaluate("engine.', 'send_command',
                          'currentTime =', 'currentTime=', 'localStorage.setItem',
                          'sessionStorage.setItem', '.dispatch_event(', '.dispatchEvent('):
            self.assertNotIn(forbidden, source)

    def test_real_reload_new_frames_and_native_quit_are_required(self):
        source = Path(gate.__file__).read_text()
        self.assertIn('with frame.expect_navigation(', source)
        self.assertIn("self.line('DAWNKEEP_WEB_EXIT'", source)
        self.assertIn('requestVideoFrameCallback', source)
        self.assertIn("self.keyboard_press('ArrowRight')", source)
        self.assertIn('self.page.expect_download()', source)
        self.assertNotIn('plan.full_desktop(', source)
        self.assertNotIn('plan.combat(', source)

    def test_outage_requires_visible_parent_failure_and_retry_not_teardown_console(self):
        tree = ast.parse(Path(gate.__file__).read_text())
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == 'game_page')
        source = ast.unparse(method)
        self.assertNotIn("self.line('DAWNKEEP_WEB_LOAD_ERROR'", source)
        self.assertIn("get_attribute('data-state') == 'error'", source)
        self.assertIn("locator('[data-game-frame] iframe')).to_have_count(0)", source)
        self.assertIn("require(outage.attempts > 0", source)
        self.assertIn("self.native_plan(frame, boundary, 'outer-load-retry')", source)
        self.assertIn("'DAWNKEEP_WEB_LOAD_ERROR'", source)
        self.assertIn("'load_error_receipts': load_error_logs", source)
        self.assertIn('self.healthy()', source)

    def test_workflow_has_separate_exact_head_build_and_live_without_rebuild(self):
        workflow = (gate.ROOT / '.github/workflows/dawnkeep-public-page.yml').read_text()
        self.assertIn('git archive "$EXPECTED_HEAD_SHA"', workflow)
        self.assertIn('python scripts/godot_web/materialize_runtime.py', workflow)
        self.assertIn('actions/workflows/pages.yml/runs', workflow)
        self.assertIn("r['head_branch'] == 'main'", workflow)
        live = workflow.split('- name: Accept the actual deployed pages', 1)[1].split('- name:', 1)[0]
        self.assertIn('--base-url "$PUBLIC_BASE_URL"', live)
        self.assertNotIn('build_site.py', live)
        self.assertNotIn('export_web.py', workflow)
        self.assertNotIn('playwright install chromium', workflow)
        self.assertIn('test "$(readlink -f "$CHROME")" = "$CHROME"', workflow)


if __name__ == '__main__':
    unittest.main()
