"""The standalone browser CLI's user-input helper, without launching a browser."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock


class ExcerptStartTests(unittest.TestCase):
    @staticmethod
    def helper():
        source = Path(__file__).with_name('crate_checkpoint_browser_smoke.py')
        tree = ast.parse(source.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'start_excerpt')
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        return namespace['start_excerpt']

    def test_real_space_precedes_wait_for_loaded_playing_video(self):
        events = []
        video = Mock()
        video.evaluate.side_effect = lambda expression: events.append(('check', expression)) or 0
        video.press.side_effect = lambda key: events.append(('press', key))
        page = Mock()
        page.wait_for_function.side_effect = lambda condition: events.append(('wait', condition))
        self.helper()(page, video)
        self.assertEqual([kind for kind, _ in events], ['check', 'press', 'wait'])
        self.assertEqual(events[1], ('press', 'Space'))
        self.assertIn('readyState>=2', events[2][1])
        self.assertIn('.paused', events[2][1])
        self.assertNotIn('play()', events[0][1])

    def test_prior_playback_is_rejected_before_input(self):
        video, page = Mock(), Mock()
        video.evaluate.return_value = 1
        with self.assertRaisesRegex(AssertionError, 'before user input'):
            self.helper()(page, video)
        video.press.assert_not_called()
        page.wait_for_function.assert_not_called()


if __name__ == '__main__':
    unittest.main()
