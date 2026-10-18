"""The stop guard must still reject every newly observed media request."""

import unittest

from video_browser_smoke import assert_no_media_requests_since


class MediaReleaseGuardTests(unittest.TestCase):
    def test_completed_seek_requests_precede_the_stop_baseline(self):
        requests = ['film.mp4', 'film.mp4']
        before_stop = len(requests)
        assert_no_media_requests_since(requests, before_stop)

    def test_refetch_of_same_media_after_stop_fails(self):
        requests = ['film.mp4', 'film.mp4']
        before_stop = len(requests)
        requests.append('film.mp4')
        with self.assertRaisesRegex(AssertionError, 'Media refetched after stop'):
            assert_no_media_requests_since(requests, before_stop)

    def test_other_media_after_stop_fails(self):
        requests = ['film.mp4']
        before_stop = len(requests)
        requests.append('other.webm')
        with self.assertRaisesRegex(AssertionError, 'other.webm'):
            assert_no_media_requests_since(requests, before_stop)


if __name__ == '__main__':
    unittest.main()
