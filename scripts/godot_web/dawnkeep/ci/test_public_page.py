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


class PublicMatrixTests(unittest.TestCase):
    def test_default_and_four_single_pair_selections_cover_identical_required_matrix(self):
        expected = [('en', False), ('en', True), ('zh', False), ('zh', True)]
        self.assertEqual(gate.selected_pairs(), expected)
        actual = []
        for locale in ('en', 'zh'):
            for viewport in ('desktop', 'portrait'):
                selected = gate.selected_pairs(locale, viewport)
                self.assertEqual(len(selected), 1)
                actual.extend(selected)
        self.assertEqual(actual, expected)
        with self.assertRaises(ValueError):
            gate.selected_pairs('fr', 'portrait')

    def test_workflow_runs_all_four_without_skipping_failures_and_separate_artifacts(self):
        workflow = (gate.ROOT / '.github/workflows/dawnkeep-public-page.yml').read_text()
        for required in ('runs-on: ubuntu-24.04', 'timeout-minutes: 20', 'fail-fast: false',
                         'locale: [en, zh]', 'viewport: [desktop, portrait]'):
            self.assertIn(required, workflow)
        self.assertEqual(workflow.count('--locale "$ACCEPTANCE_LOCALE" --viewport "$ACCEPTANCE_VIEWPORT"'), 2)
        self.assertIn('-${{ matrix.locale }}-${{ matrix.viewport }}', workflow)
        self.assertNotIn('continue-on-error', workflow)
        source = Path(gate.__file__).read_text()
        self.assertIn("'complete_four_pair_matrix': len(pairs) == 4", source)
        self.assertIn("len(report['viewports']) == len(pairs)", source)
        self.assertIn('publication needs all four workflow matrix jobs', source)


class PublicMediaRangeTests(unittest.TestCase):
    def test_server_reuses_real_range_handler_and_its_partial_response(self):
        import browser_preview
        import test_media_ranges
        self.assertIs(gate.RangeHTTPHandler, browser_preview.QuietHandler)
        source = Path(gate.__file__).read_text()
        self.assertIn('partial(RangeHTTPHandler, directory=', source)
        # Initialize MIME lookup before the shared helper mocks open().
        import mimetypes
        mimetypes.init()
        checker = test_media_ranges.RangeResponseTests()
        status, headers, body, _ = checker.respond('bytes=2-5')
        self.assertEqual((status, headers['Content-Range'], body), (206, 'bytes 2-5/10', b'2345'))

    def response(self, status=206, content_range='bytes 2048-3071/4096', body=None):
        response = Mock(status=status, url=gate.OFFICIAL_BASE + 'film.mp4')
        response.headers = {'content-range': content_range, 'content-length': '1024', 'accept-ranges': 'bytes'}
        response.body.return_value = bytes(range(256)) * 4 if body is None else body
        request = Mock()
        request.get.return_value = response
        return request, response

    def test_local_and_live_media_require_actual_exact_partial_bytes(self):
        data = bytes(range(256)) * 16
        for base in (gate.OFFICIAL_BASE, 'http://127.0.0.1:1234/'):
            request, response = self.response()
            response.url = base + 'film.mp4'
            result = gate.verify_media_range(request, base, 'film.mp4', data)
            self.assertEqual(result['status'], 206)
            self.assertTrue(result['matches_verified_film_slice'])
            self.assertEqual(request.get.call_args.kwargs['headers']['Range'], 'bytes=2048-3071')
            self.assertEqual(request.get.call_args.kwargs['max_redirects'], 0)
            response.dispose.assert_called_once()

    def test_ignored_ranges_bad_headers_and_wrong_partial_bytes_are_fatal(self):
        for parameters in ({'status': 200}, {'content_range': 'bytes 0-1023/4096'}, {'body': b'x' * 1024}):
            request, response = self.response(**parameters)
            with self.assertRaises(RuntimeError):
                gate.verify_media_range(request, gate.OFFICIAL_BASE, 'film.mp4', bytes(range(256)) * 16)
            response.dispose.assert_called_once()

    def test_browser_must_expose_nonempty_seekable_range_covering_click_target(self):
        self.assertTrue(gate.midpoint_seekable({'duration': 58, 'seekable': [[0, 58]]}))
        for state in ({'duration': 58, 'seekable': [[0, 0]]},
                      {'duration': 58, 'seekable': [[0, 4]]},
                      {'duration': float('nan'), 'seekable': [[0, 58]]},
                      {'duration': 58, 'seekable': [[0, '58']]}):
            self.assertFalse(gate.midpoint_seekable(state))
        source = Path(gate.__file__).read_text()
        self.assertIn('self.wait(lambda: midpoint_seekable(self.media_state(video))', source)
        self.assertIn("result[name]['http_range'] = verify_media_range(request, base, name, data)", source)

    def test_shared_server_hash_and_workflow_guards_are_bound(self):
        source = Path(gate.__file__).read_text()
        self.assertIn("ROOT / 'scripts/browser_preview.py'", source)
        workflow = (gate.ROOT / '.github/workflows/dawnkeep-public-page.yml').read_text()
        self.assertIn("- 'scripts/browser_preview.py'", workflow)
        self.assertIn("- 'scripts/test_media_ranges.py'", workflow)
        self.assertIn('python scripts/test_media_ranges.py', workflow)


class NativeMediaAndProgressTests(unittest.TestCase):
    def test_native_timeline_and_play_controls_match_reviewed_capture_geometry(self):
        desktop = {'x': 316, 'y': 285, 'width': 960, 'height': 540}
        portrait = {'x': 20, 'y': 338, 'width': 350, 'height': 197}
        self.assertEqual(gate.native_media_point(desktop, 'timeline'), (796, 803))
        self.assertEqual(gate.native_media_point(portrait, 'timeline'), (195, 513))
        self.assertEqual(gate.native_media_point(desktop, 'play-pause'), (340, 775))
        self.assertEqual(gate.native_media_point(portrait, 'play-pause'), (44, 485))

    def test_invalid_native_video_geometry_fails_before_input(self):
        box = {'x': 0, 'y': 0, 'width': 350, 'height': 197}
        for invalid in ({**box, 'x': float('nan')}, {**box, 'height': 40},
                        {**box, 'width': 190}, {**box, 'width': '350'}):
            with self.assertRaises(ValueError):
                gate.native_media_point(invalid, 'timeline')
        with self.assertRaises(ValueError):
            gate.native_media_point(box, 'unknown')

    def test_seek_is_physical_and_preserves_paused_advance_and_resumed_frame_assertions(self):
        tree = ast.parse(Path(gate.__file__).read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'case_page')
        source = ast.unparse(method)
        self.assertIn("self.media_control(video, 'timeline')", source)
        self.assertIn("['time'] > before['time'] + 1", source)
        self.assertIn('!v.seeking && v.readyState>=2 && v.paused', source)
        self.assertIn("resumed['last'] > after['time']", source)
        self.assertIn("'seek_before': before", source)
        self.assertIn("'seek_after': after", source)
        self.assertIn("self.shot('case-film-before-seek')", source)
        self.assertIn("self.shot('case-film-after-seek')", source)
        self.assertNotIn('ArrowRight', source)
        self.assertNotIn('currentTime =', source)

    def test_progress_is_flushed_and_viewport_identified(self):
        with patch('builtins.print') as output:
            result = gate.progress_event('case-media', 'started', locale='zh', viewport='portrait')
        self.assertTrue(output.call_args.kwargs['flush'])
        self.assertIn('DAWNKEEP_PUBLIC_PROGRESS ', output.call_args.args[0])
        self.assertEqual(result['locale'], 'zh')
        self.assertEqual(result['viewport'], 'portrait')
        self.assertIn('utc', result)

    def test_reordering_keeps_every_stage_required_and_runs_media_before_heavy_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = gate.Session.__new__(gate.Session)
            session.result = {'passed': False}
            session.output = Path(tmp)
            session.context = Mock()
            session.progress = Mock()
            session.healthy = Mock()
            session.console, session.requests, session.responses = [], [], []
            session.network_failures, session.errors = [], []
            order = []
            session.gallery = lambda: order.append('gallery')
            session.case_page = lambda: order.append('case')
            session.game_page = lambda: order.append('game')
            session.standalone_page = lambda: order.append('standalone')
            result = session.run()
        self.assertEqual(order, ['gallery', 'case', 'game', 'standalone'])
        self.assertTrue(result['passed'])
        self.assertEqual(session.progress.call_args_list[0].args, ('viewport', 'started'))
        self.assertEqual(session.progress.call_args_list[-1].args, ('viewport', 'passed'))
        session.context.close.assert_called_once()


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
        self.assertIn("self.media_control(video, 'timeline')", source)
        self.assertIn("self.media_control(video, 'play-pause')", source)
        self.assertNotIn("self.keyboard_press('ArrowRight')", source)
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
