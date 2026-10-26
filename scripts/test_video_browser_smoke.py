"""Release guards use real event boundaries, never callback delivery order."""

from copy import deepcopy
import unittest

from video_browser_smoke import (
    assert_no_media_requests_after_stop,
    assert_paused_gallery_preview,
    media_release_observation,
    media_request_started,
)


class MediaReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.origin = 1800000000000
        self.before = {'timeOrigin': self.origin, 'armed_at_ms': self.origin + 2180,
                       'event_count': 1, 'event': 'click', 'target': 'video-watch', 'video_index': 1}
        self.intent = {'event': 'click', 'target': 'video-watch', 'video_index': 1,
                       'time': 2233.6, 'trusted': True, 'state': 'watching'}
        self.detached = {'event': 'emptied', 'target': 'video', 'video_index': 1,
                         'time': 2233.8, 'trusted': True, 'src': None, 'live_sources': 0,
                         'paused': True, 'state': 'idle'}
        self.snapshot = {'timeOrigin': self.origin, 'time': 2734,
                         'events': [{'event': 'earlier'}, self.intent, self.detached]}

    def request(self, time, url='film.mp4'):
        return media_request_started({'requestId': str(time), 'wallTime': (self.origin + time) / 1000,
                                      'request': {'url': url, 'headers': {'Range': 'bytes=137950-'}}})

    def observation(self, requests):
        return media_release_observation(requests, self.before, self.snapshot)

    def test_late_observed_range_started_before_actual_stop_passes(self):
        # The retained failure has a Range at 2201.2 and stop abort/emptied
        # at 2233.7/2233.8. This fixture places the preceding trusted click at
        # 2233.6 and guard at 2180; those two values are fixture data.
        # Reverse delivery order deliberately; completed resources are not needed.
        observation = self.observation([self.request(2201.2), self.request(2100)])
        assert_no_media_requests_after_stop(observation)
        self.assertEqual(len(observation['phases']['before_guard']), 1)
        self.assertEqual(len(observation['phases']['guard_to_stop']), 1)
        self.assertEqual(observation['source_detached_at_ms'], self.origin + 2233.8)

    def test_same_media_range_started_after_source_detach_fails(self):
        observation = self.observation([self.request(2234)])
        self.assertEqual(len(observation['phases']['after_release']), 1)
        with self.assertRaisesRegex(AssertionError, 'Media refetched after stop'):
            assert_no_media_requests_after_stop(observation)

    def test_new_range_started_inside_stop_handler_fails(self):
        observation = self.observation([self.request(2233.7)])
        self.assertEqual(len(observation['phases']['during_release']), 1)
        with self.assertRaisesRegex(AssertionError, 'Media refetched after stop'):
            assert_no_media_requests_after_stop(observation)

    def test_other_media_after_stop_fails(self):
        with self.assertRaisesRegex(AssertionError, 'other.webm'):
            assert_no_media_requests_after_stop(self.observation([self.request(2234, 'other.webm')]))

    def test_exact_stop_or_detach_boundary_fails(self):
        for time in [2233.6, 2233.8]:
            with self.subTest(time=time), self.assertRaisesRegex(AssertionError, 'Media refetched after stop'):
                # Avoid seconds-to-ms rounding in an exact boundary fixture.
                request = self.request(time)
                request['started_at_ms'] = self.origin + time
                assert_no_media_requests_after_stop(self.observation([request]))

    def test_real_pointerleave_boundary_is_supported(self):
        self.before.update(event='pointerleave', target='detail-host')
        self.intent.update(event='pointerleave', target='detail-host', state='preview')
        assert_no_media_requests_after_stop(self.observation([self.request(2201.2)]))

    def test_gallery_manual_stop_uses_the_same_native_release_guard(self):
        self.before['target'] = self.intent['target'] = 'preview-toggle'
        self.intent['state'] = 'playing'
        assert_no_media_requests_after_stop(self.observation([self.request(2201.2)]))
        with self.assertRaisesRegex(AssertionError, 'Media refetched after stop'):
            assert_no_media_requests_after_stop(self.observation([self.request(2234)]))

    def test_missing_untrusted_wrong_target_or_wrong_video_intent_fails(self):
        for changes in [{'trusted': False}, {'target': 'video'}, {'video_index': 0}, {'event': 'pointerleave'}]:
            with self.subTest(changes=changes):
                snapshot = deepcopy(self.snapshot)
                snapshot['events'][1].update(changes)
                with self.assertRaisesRegex(AssertionError, 'trusted stop intent'):
                    media_release_observation([], self.before, snapshot)

    def test_multiple_possible_stop_intents_fail(self):
        self.snapshot['events'].append(dict(self.intent))
        with self.assertRaisesRegex(AssertionError, 'ambiguous trusted stop intent'):
            self.observation([])

    def test_missing_or_still_attached_native_receipt_fails(self):
        for changes in [{'trusted': False}, {'src': 'film.mp4'}, {'live_sources': 1},
                        {'paused': False}, {'state': 'watching'}, {'video_index': 0}]:
            with self.subTest(changes=changes):
                snapshot = deepcopy(self.snapshot)
                snapshot['events'][2].update(changes)
                with self.assertRaisesRegex(AssertionError, 'source-detached release receipt'):
                    media_release_observation([], self.before, snapshot)

    def test_missing_receipt_does_not_pass_empty_network_log(self):
        self.snapshot['events'].pop()
        with self.assertRaisesRegex(AssertionError, 'source-detached release receipt'):
            self.observation([])

    def test_invalid_request_time_fails_closed(self):
        for value in [None, True, float('nan'), float('inf'), -1, '2201.2']:
            with self.subTest(value=value), self.assertRaisesRegex(AssertionError, 'invalid browser request/event time'):
                self.observation([{'url': 'film.mp4', 'started_at_ms': value}])

    def test_missing_cdp_start_time_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, 'invalid browser request/event time'):
            media_request_started({'requestId': 'missing', 'request': {'url': 'film.mp4'}})

    def test_empty_cdp_log_does_not_pass_decoded_playback(self):
        with self.assertRaisesRegex(AssertionError, 'No CDP media initiation evidence'):
            self.observation([])

    def test_zero_request_epoch_fails_closed(self):
        with self.assertRaisesRegex(AssertionError, 'positive request epoch'):
            self.observation([{'url': 'film.mp4', 'started_at_ms': 0}])
        with self.assertRaisesRegex(AssertionError, 'positive request epoch'):
            media_request_started({'requestId': 'zero', 'wallTime': 0, 'request': {'url': 'film.mp4'}})

    def test_changed_document_clock_fails_closed(self):
        self.snapshot['timeOrigin'] += 100
        with self.assertRaisesRegex(AssertionError, 'Document changed'):
            self.observation([])

    def test_invalid_event_order_fails_closed(self):
        self.detached['time'] = 2233.5
        with self.assertRaisesRegex(AssertionError, 'Invalid release event ordering'):
            self.observation([])

    def test_stop_must_follow_guard_and_target_active_player(self):
        self.intent['time'] = 2179
        with self.assertRaisesRegex(AssertionError, 'predates its guard'):
            self.observation([])
        self.intent.update(time=2233.6, state='idle')
        with self.assertRaisesRegex(AssertionError, 'active player'):
            self.observation([])

    def test_cdp_observes_range_request_start_without_response(self):
        request = self.request(2201.2, 'https://example.test/film.mp4?download=1')
        self.assertEqual(request['range'], 'bytes=137950-')
        self.assertAlmostEqual(request['started_at_ms'], self.origin + 2201.2, places=2)
        self.assertIsNone(media_request_started({'requestId': 'css', 'request': {'url': 'style.css'}}))


class GalleryPauseObservationTests(unittest.TestCase):
    def setUp(self):
        self.paused = {'state': 'paused', 'paused': True, 'src': 'film.mp4', 'currentSrc': 'https://example.test/film.mp4',
                       'currentTime': 0.2, 'readyState': 4, 'width': 960, 'height': 720, 'visible': True}

    def test_short_loop_pause_keeps_its_frame_without_requiring_time_progress(self):
        assert_paused_gallery_preview(self.paused, dict(self.paused))

    def test_two_zero_positions_do_not_prove_pause_retention(self):
        self.paused['currentTime'] = 0
        with self.assertRaisesRegex(AssertionError, 'never advanced'):
            assert_paused_gallery_preview(self.paused, dict(self.paused))

    def test_hover_cannot_restart_detach_seek_or_hide_the_paused_frame(self):
        for changes in [{'state': 'idle'}, {'state': 'playing', 'paused': False}, {'src': None},
                        {'currentSrc': ''}, {'src': 'other.mp4'}, {'currentTime': 0}, {'readyState': 0},
                        {'width': 0}, {'height': 0}, {'visible': False}, {'currentTime': float('nan')}]:
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                assert_paused_gallery_preview(self.paused, {**self.paused, **changes})


if __name__ == '__main__':
    unittest.main()
