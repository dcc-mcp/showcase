"""Duration metadata, streaming WebM and corrupt-media regression coverage."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from media_duration import media_duration


class DurationTests(unittest.TestCase):
    @patch('media_duration.subprocess.run')
    @patch('media_duration.subprocess.check_output', return_value='{"format":{"duration":"12.5"}}')
    def test_container_duration(self, probe, decode):
        self.assertEqual(media_duration('capture.webm'), 12.5)
        decode.assert_not_called()

    def test_missing_or_invalid_duration_requires_complete_decode(self):
        decoded = subprocess.CompletedProcess([], 0, 'out_time_us=12500000\nprogress=end\n', '')
        for value in [None, 'N/A', 'nan', 'inf', '0', '-1']:
            metadata = {'format': {} if value is None else {'duration': value}}
            with self.subTest(value=value), patch('media_duration.subprocess.check_output', return_value=json.dumps(metadata)), patch('media_duration.subprocess.run', return_value=decoded) as decode:
                self.assertEqual(media_duration('capture.webm'), 12.5)
                self.assertIn('-xerror', decode.call_args.args[0])
                self.assertTrue(decode.call_args.kwargs['check'])

    def test_bad_or_incomplete_decode_is_rejected(self):
        for stdout, stderr in [
            ('out_time_us=12500000\nprogress=continue\n', ''),
            ('out_time_us=0\nprogress=end\n', ''),
            ('out_time_us=N/A\nprogress=end\n', ''),
            ('progress=end\n', ''),
            ('out_time_us=12500000\nprogress=end\n', 'decode error'),
        ]:
            with self.subTest(stdout=stdout, stderr=stderr), patch('media_duration.subprocess.check_output', return_value='{"format":{}}'), patch('media_duration.subprocess.run', return_value=subprocess.CompletedProcess([], 0, stdout, stderr)):
                with self.assertRaises(ValueError):
                    media_duration('capture.webm')

    @patch('media_duration.subprocess.check_output', return_value='{"format":{}}')
    @patch('media_duration.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'ffmpeg'))
    def test_failed_decode_is_rejected(self, decode, probe):
        with self.assertRaises(subprocess.CalledProcessError):
            media_duration('capture.webm')


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg tools required')
class RealMediaTests(unittest.TestCase):
    def test_real_webm_with_and_without_duration_and_corrupt_input(self):
        with tempfile.TemporaryDirectory() as directory:
            for live in [False, True]:
                source = Path(directory) / f'capture-{live}.webm'
                command = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=64x64:rate=10',
                           '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '0.5',
                           '-c:v', 'libvpx-vp9', '-threads', '1', '-c:a', 'libopus']
                if live:
                    command += ['-live', '1']
                source.write_bytes(subprocess.check_output(command + ['-f', 'webm', 'pipe:1']))
                metadata = json.loads(subprocess.check_output(
                    ['ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(source)], text=True))
                self.assertEqual('duration' not in metadata['format'], live)
                self.assertAlmostEqual(media_duration(source), 0.5, delta=0.05)
            corrupt = Path(directory) / 'corrupt.webm'
            corrupt.write_bytes(b'not a media container')
            with self.assertRaises(subprocess.CalledProcessError):
                media_duration(corrupt)
            # A truncated stream still probes, but decoding must reject it.
            corrupt.write_bytes(source.read_bytes()[:-1000])
            with self.assertRaises((subprocess.CalledProcessError, ValueError)):
                media_duration(corrupt)


if __name__ == '__main__':
    unittest.main()
