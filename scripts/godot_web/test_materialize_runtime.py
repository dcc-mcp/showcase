import io
import unittest
import zipfile
from contextlib import contextmanager
from unittest.mock import call, patch

import materialize_runtime as module


class Response(io.BytesIO):
    def __init__(self, data=b'', status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


class BrokenResponse(Response):
    def read(self, length=-1):
        raise module.http.client.IncompleteRead(b'ab', 2)


def partial(data, start=10, end=14, size=100):
    return Response(data, 206, {'Content-Range': f'bytes {start}-{end-1}/{size}'})


class RangeContractTests(unittest.TestCase):
    @contextmanager
    def remote(self, responses, size=100, start=10):
        with patch.object(module.urllib.request, 'urlopen', side_effect=[
            Response(headers={'Content-Length': str(size)}), *responses
        ]) as opener, patch.object(module.time, 'sleep') as sleep:
            archive = module.RemoteZip()
            archive.seek(start)
            yield archive, opener, sleep

    def assert_ranges(self, opener, ranges):
        requests = [entry.args[0] for entry in opener.call_args_list]
        self.assertEqual(requests[0].get_method(), 'HEAD')
        self.assertEqual([request.get_header('Range') for request in requests[1:]], ranges)
        self.assertTrue(all(request.full_url == module.URL for request in requests))

    def test_exact_partial_response(self):
        with self.remote([partial(b'abcd')]) as (archive, opener, sleep):
            self.assertEqual(archive.read(4), b'abcd')
            self.assertEqual(archive.tell(), 14)
            self.assert_ranges(opener, ['bytes=10-13'])
            sleep.assert_not_called()

    def test_chunked_response_reassembles_exact_bytes_and_tail(self):
        self.assertLessEqual(module.RANGE_CHUNK_SIZE, 1024 * 1024)
        limit = module.RANGE_CHUNK_SIZE
        data = b'a' * limit + b'b' * limit + b'last123'
        end = 10 + len(data)
        responses = [partial(data[offset:offset+limit], 10+offset,
                             min(10+offset+limit, end), end)
                     for offset in range(0, len(data), limit)]
        with self.remote(responses, size=end) as (archive, opener, sleep):
            self.assertEqual(archive.read(len(data)), data)
            self.assertEqual(archive.tell(), end)
            self.assert_ranges(opener, [f'bytes=10-{10+limit-1}',
                                       f'bytes={10+limit}-{10+2*limit-1}',
                                       f'bytes={10+2*limit}-{end-1}'])
            sleep.assert_not_called()

    def test_short_read_retries_same_range_without_partial_bytes(self):
        with self.remote([partial(b'ab'), partial(b'abcd')]) as (archive, opener, sleep):
            self.assertEqual(archive.read(4), b'abcd')
            self.assertEqual(archive.tell(), 14)
            self.assert_ranges(opener, ['bytes=10-13'] * 2)
            sleep.assert_called_once_with(.25)

    def test_short_read_exhaustion_rejects_after_three_attempts(self):
        with self.remote([partial(b'ab') for _ in range(3)]) as (archive, opener, sleep):
            with self.assertRaisesRegex(ValueError, 'Truncated.*10-13/100.*expected 4, received 2'):
                archive.read(4)
            self.assertEqual(archive.tell(), 10)
            self.assert_ranges(opener, ['bytes=10-13'] * 3)
            self.assertEqual(sleep.call_args_list, [call(.25), call(.5)])

    def test_transport_errors_retry_same_range(self):
        errors = [TimeoutError('timeout'), ConnectionResetError('reset'),
                  module.urllib.error.URLError('connection lost')]
        for error in errors:
            with self.subTest(error=type(error).__name__), self.remote([
                error, partial(b'abcd')
            ]) as (archive, opener, sleep):
                self.assertEqual(archive.read(4), b'abcd')
                self.assertEqual(archive.tell(), 14)
                self.assert_ranges(opener, ['bytes=10-13'] * 2)
                sleep.assert_called_once_with(.25)

    def test_incomplete_response_read_retries_without_partial_bytes(self):
        with self.remote([BrokenResponse(status=206, headers={'Content-Range': 'bytes 10-13/100'}),
                          partial(b'abcd')]) as (archive, opener, sleep):
            self.assertEqual(archive.read(4), b'abcd')
            self.assert_ranges(opener, ['bytes=10-13'] * 2)
            sleep.assert_called_once_with(.25)

    def test_transport_exhaustion_preserves_position(self):
        errors = [TimeoutError('first'), ConnectionResetError('second'), TimeoutError('last')]
        with self.remote(errors) as (archive, opener, sleep):
            with self.assertRaisesRegex(TimeoutError, 'last'):
                archive.read(4)
            self.assertEqual(archive.tell(), 10)
            self.assert_ranges(opener, ['bytes=10-13'] * 3)
            self.assertEqual(sleep.call_count, 2)

    def test_failed_later_chunk_does_not_advance_entire_read(self):
        limit = module.RANGE_CHUNK_SIZE
        end = 10 + limit + 4
        with self.remote([partial(b'a' * limit, 10, 10+limit, end),
                          *[partial(b'ab', 10+limit, end, end) for _ in range(3)]],
                         size=end) as (archive, opener, sleep):
            with self.assertRaisesRegex(ValueError, 'Truncated'):
                archive.read(limit + 4)
            self.assertEqual(archive.tell(), 10)
            self.assert_ranges(opener, [f'bytes=10-{10+limit-1}',
                                       *[f'bytes={10+limit}-{end-1}'] * 3])
            self.assertEqual(sleep.call_count, 2)

    def test_protocol_violations_do_not_retry(self):
        cases = [
            (Response(b'abcd', 200), 'honor HTTP range'),
            (Response(b'abcd', 206), 'Content-Range'),
            (partial(b'abcd', 0, 4), 'Content-Range'),
            (partial(b'abcd', size=101), 'Content-Range'),
            (partial(b'abcde'), 'Excess.*expected 4, received 5'),
        ]
        for response, message in cases:
            with self.subTest(message=message), self.remote([response]) as (archive, opener, sleep):
                with self.assertRaisesRegex(ValueError, message):
                    archive.read(4)
                self.assertEqual(archive.tell(), 10)
                self.assert_ranges(opener, ['bytes=10-13'])
                sleep.assert_not_called()

    def test_http_errors_do_not_retry(self):
        for status in [403, 416, 500, 503]:
            error = module.urllib.error.HTTPError(module.URL, status, 'failure', {}, None)
            with self.subTest(status=status), self.remote([error]) as (archive, opener, sleep):
                with self.assertRaises(module.urllib.error.HTTPError) as caught:
                    archive.read(4)
                self.assertIs(caught.exception, error)
                self.assertEqual(archive.tell(), 10)
                self.assert_ranges(opener, ['bytes=10-13'])
                sleep.assert_not_called()

    def test_unrelated_exception_does_not_retry(self):
        with self.remote([RuntimeError('unexpected')]) as (archive, opener, sleep):
            with self.assertRaisesRegex(RuntimeError, 'unexpected'):
                archive.read(4)
            self.assertEqual(archive.tell(), 10)
            self.assert_ranges(opener, ['bytes=10-13'])
            sleep.assert_not_called()

    def test_empty_reads_do_not_request_or_advance(self):
        with self.remote([]) as (archive, opener, sleep):
            self.assertEqual(archive.read(0), b'')
            self.assertEqual(archive.tell(), 10)
            archive.seek(100)
            self.assertEqual(archive.read(), b'')
            self.assertEqual(archive.tell(), 100)
            self.assert_ranges(opener, [])
            sleep.assert_not_called()

    def test_reads_stop_at_archive_end(self):
        for length in [-1, 20]:
            with self.subTest(length=length), self.remote([
                partial(b'abcd', size=14)
            ], size=14) as (archive, opener, sleep):
                self.assertEqual(archive.read(length), b'abcd')
                self.assertEqual(archive.tell(), 14)
                self.assert_ranges(opener, ['bytes=10-13'])

    def test_zip_member_is_read_and_crc_remains_enforced(self):
        data = b'known member bytes'
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('member.txt', data)
        original = buffer.getvalue()
        for corrupted in [False, True]:
            payload = original.replace(data, b'x' + data[1:]) if corrupted else original
            def serve(request, **kwargs):
                if request.get_method() == 'HEAD':
                    return Response(headers={'Content-Length': str(len(payload))})
                start, end = map(int, request.get_header('Range').removeprefix('bytes=').split('-'))
                self.assertLessEqual(end-start+1, 1024 * 1024)
                return partial(payload[start:end+1], start, end+1, len(payload))
            with self.subTest(corrupted=corrupted), patch.object(module.urllib.request, 'urlopen', side_effect=serve):
                with zipfile.ZipFile(module.RemoteZip()) as archive:
                    if corrupted:
                        with self.assertRaisesRegex(zipfile.BadZipFile, 'CRC'):
                            archive.read('member.txt')
                    else:
                        self.assertEqual(archive.read('member.txt'), data)

    def test_oversized_archive_rejected(self):
        with patch.object(module.urllib.request, 'urlopen', return_value=Response(
            headers={'Content-Length': '3000000000'}
        )):
            with self.assertRaisesRegex(ValueError, 'size'):
                module.RemoteZip()


if __name__ == '__main__':
    unittest.main()
