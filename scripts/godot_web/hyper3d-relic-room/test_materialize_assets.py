import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.request

SPEC = importlib.util.spec_from_file_location('relic_lfs', Path(__file__).with_name('materialize_assets.py'))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
REF = 'a' * 40
RELATIVE = 'play/hyper3d-relic-room/fixed.pck'
DATA = b'approved payload'
DIGEST = hashlib.sha256(DATA).hexdigest()
URL = 'https://media.githubusercontent.com/media/dcc-mcp/showcase/' + REF + '/' + RELATIVE
POINTER = ('version https://git-lfs.github.com/spec/v1\noid sha256:' + DIGEST
           + '\nsize ' + str(len(DATA)) + '\n').encode()


class Response(io.BytesIO):
    status = 200

    def __init__(self, data=DATA, url=URL, headers=None):
        super().__init__(data)
        self.url, self.headers = url, headers or {}

    def geturl(self):
        return self.url


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.dest = self.root / RELATIVE
        self.dest.parent.mkdir(parents=True)
        self.pin = patch.object(module, 'PINS', {RELATIVE: (len(DATA), DIGEST)})
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def prepare(self, response):
        opener = Mock()
        opener.open.return_value = response
        return patch.object(module.urllib.request, 'build_opener', return_value=opener), opener

    def test_cached_payload_uses_neither_network_nor_git_or_ci_ref(self):
        self.dest.write_bytes(DATA)
        with patch.object(module, 'immutable_ref', side_effect=AssertionError('no ref needed')), \
                patch.object(module.urllib.request, 'build_opener') as network:
            self.assertEqual(module.materialize(self.root), {'verified': 1, 'fetched': 0})
            network.assert_not_called()

    def test_matching_pointer_is_replaced_only_after_full_verified_read(self):
        self.dest.write_bytes(POINTER)
        response = Response()
        original_read = response.read
        def read(length):
            self.assertEqual(self.dest.read_bytes(), POINTER)
            return original_read(length)
        response.read = read
        prepare, opener = self.prepare(response)
        with prepare, patch.object(module, 'immutable_ref', return_value=REF):
            self.assertEqual(module.materialize(self.root)['fetched'], 1)
        opener.open.assert_called_once_with(URL, timeout=60)
        self.assertEqual(self.dest.read_bytes(), DATA)
        self.assertFalse(list(self.dest.parent.glob('.hyper3d-lfs-*')))

    def test_missing_file_uses_exact_immutable_github_url(self):
        prepare, opener = self.prepare(Response())
        with prepare, patch.object(module, 'immutable_ref', return_value=REF):
            module.materialize(self.root)
        opener.open.assert_called_once_with(URL, timeout=60)
        self.assertEqual(self.dest.read_bytes(), DATA)

    def test_malformed_or_mismatched_pointer_never_requests_or_overwrites(self):
        variants = [b'unexpected data', POINTER.replace(DIGEST.encode(), b'0' * 64),
                    POINTER.replace(b'size ' + str(len(DATA)).encode(), b'size 99'),
                    POINTER + b'not a pointer field\n', POINTER.rstrip(b'\n')]
        for data in variants:
            with self.subTest(data=data):
                self.dest.write_bytes(data)
                with patch.object(module.urllib.request, 'build_opener') as network:
                    with self.assertRaisesRegex(ValueError, 'Unexpected existing'):
                        module.materialize(self.root)
                    network.assert_not_called()
                self.assertEqual(self.dest.read_bytes(), data)

    def test_all_existing_files_are_checked_before_any_request(self):
        other = 'docs/showcase/hyper3d-relic-room/showcase.mp4'
        file = self.root / other
        file.parent.mkdir(parents=True)
        file.write_bytes(b'unexpected')
        with patch.object(module, 'PINS', {RELATIVE: (len(DATA), DIGEST), other: (len(DATA), DIGEST)}), \
                patch.object(module.urllib.request, 'build_opener') as network:
            with self.assertRaises(ValueError):
                module.materialize(self.root)
            network.assert_not_called()
        self.assertFalse(self.dest.exists())

    def test_bad_downloads_preserve_pointer_and_remove_temporary_file(self):
        cases = [(DATA[:-1], None), (DATA + b'X', None), (b'x' * len(DATA), None),
                 (DATA, {'Content-Length': str(len(DATA) + 1)}),
                 (DATA, {'Content-Encoding': 'gzip'})]
        for payload, headers in cases:
            with self.subTest(payload=payload, headers=headers):
                self.dest.write_bytes(POINTER)
                prepare, _ = self.prepare(Response(payload, headers=headers))
                with prepare, patch.object(module, 'immutable_ref', return_value=REF):
                    with self.assertRaises(ValueError):
                        module.materialize(self.root)
                self.assertEqual(self.dest.read_bytes(), POINTER)
                self.assertFalse(list(self.dest.parent.glob('.hyper3d-lfs-*')))

    def test_final_non_github_response_is_rejected_before_writing(self):
        self.dest.write_bytes(POINTER)
        prepare, _ = self.prepare(Response(url='https://example.com/payload'))
        with prepare, patch.object(module, 'immutable_ref', return_value=REF):
            with self.assertRaisesRegex(ValueError, 'GitHub HTTPS'):
                module.materialize(self.root)
        self.assertEqual(self.dest.read_bytes(), POINTER)
        self.assertFalse(list(self.dest.parent.glob('.hyper3d-lfs-*')))

    def test_redirect_handler_blocks_non_github_downgrade_and_credentials(self):
        handler = module.GithubRedirect()
        req = urllib.request.Request(URL)
        for url in ['https://example.com/file', 'https://github.com.evil.test/file',
                    'http://media.githubusercontent.com/file',
                    'https://user:pass@github.com/file', 'https://github.com:8443/file']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(req, None, 302, 'Moved', {}, url)

    def test_unsafe_paths_and_symlink_ancestors_are_rejected(self):
        for relative in ['../escape', '/absolute', 'play/../escape', 'play\\escape', 'C:/escape']:
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                module.target(self.root, relative)
        link = self.root / 'linked'
        try:
            link.symlink_to(self.dest.parent, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation unavailable on this host')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            module.target(self.root, 'linked/file')

    def test_timeout_and_concurrent_unexpected_bytes_preserve_destination(self):
        self.dest.write_bytes(POINTER)
        prepare, _ = self.prepare(Response())
        with prepare, patch.object(module, 'immutable_ref', return_value=REF), \
                patch.object(module.time, 'monotonic', side_effect=[0, 181]):
            with self.assertRaises(TimeoutError):
                module.materialize(self.root)
        self.assertEqual(self.dest.read_bytes(), POINTER)
        self.assertFalse(list(self.dest.parent.glob('.hyper3d-lfs-*')))
        response = Response()
        read = response.read
        def changed(length):
            self.dest.write_bytes(b'other writer')
            return read(length)
        response.read = changed
        prepare, _ = self.prepare(response)
        with prepare, patch.object(module, 'immutable_ref', return_value=REF):
            with self.assertRaisesRegex(ValueError, 'Unexpected existing'):
                module.materialize(self.root)
        self.assertEqual(self.dest.read_bytes(), b'other writer')

    def test_ref_uses_git_head_before_ci_environment(self):
        (self.root / '.git').mkdir()
        with patch.dict(os.environ, {'GITHUB_SHA': 'b' * 40}), \
                patch.object(module.subprocess, 'check_output', return_value=REF + '\n') as git:
            self.assertEqual(module.immutable_ref(self.root), REF)
            git.assert_called_once_with(['git', '-C', str(self.root), 'rev-parse', 'HEAD'],
                                        text=True, timeout=10)

    def test_archive_ref_prefers_pr_head_and_rejects_mutable_refs(self):
        event = self.root / 'event.json'
        event.write_text(json.dumps({'pull_request': {'head': {'sha': REF}}}))
        with patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event), 'GITHUB_SHA': 'b' * 40}):
            self.assertEqual(module.immutable_ref(self.root), REF)
            event.write_text(json.dumps({'pull_request': {'head': {'sha': 'main'}}}))
            with self.assertRaisesRegex(ValueError, 'immutable'):
                module.immutable_ref(self.root)
        for ref in ['main', 'a' * 7, '../main', 'a' * 40 + '/file', '']:
            with self.subTest(ref=ref), patch.dict(os.environ, {'GITHUB_SHA': ref}, clear=True):
                with self.assertRaises(ValueError):
                    module.immutable_ref(self.root)
        with patch.dict(os.environ, {'GITHUB_SHA': REF}, clear=True):
            self.assertEqual(module.immutable_ref(self.root), REF)

    def test_archive_event_is_bounded_and_malformed_pr_cannot_fall_back(self):
        event = self.root / 'event.json'
        for data in [[], {'pull_request': None}, {'pull_request': {'head': {}}}]:
            with self.subTest(data=data):
                event.write_text(json.dumps(data))
                with patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event), 'GITHUB_SHA': REF}):
                    with self.assertRaises(ValueError):
                        module.immutable_ref(self.root)
        event.write_bytes(b' ' * (1024 * 1024 + 1))
        with patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event), 'GITHUB_SHA': REF}):
            with self.assertRaisesRegex(ValueError, 'size limit'):
                module.immutable_ref(self.root)


if __name__ == '__main__':
    unittest.main()
