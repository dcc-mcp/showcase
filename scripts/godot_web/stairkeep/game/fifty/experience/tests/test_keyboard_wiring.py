"""Static architecture guards; these do not parse or execute GDScript."""
import json
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
VIEW = HERE.parent / 'overlay/fifty/view'
PREVIEW = (VIEW / 'preview.gd').read_text(encoding='utf-8')
CONTROLLER = (VIEW / 'keyboard_controller.gd').read_text(encoding='utf-8')


def body(name):
    found = re.search(r'^func ' + re.escape(name) + r'\([^\n]*\).*?:\n(.*?)(?=^func |\Z)', PREVIEW, re.M | re.S)
    if not found:
        raise AssertionError('Missing preview method: ' + name)
    return found.group(1)


class KeyboardWiring(unittest.TestCase):
    def test_one_accepted_edge_producer(self):
        self.assertEqual(PREVIEW.count('_keyboard.press('), 1)
        self.assertIn('_keyboard.press(', body('_unhandled_key_input'))
        self.assertIn('event.echo', body('_unhandled_key_input'))

    def test_old_delayed_fallback_removed(self):
        for old in ('_direction_serial', '_queue_screen_step', '_held_screen_intent'):
            self.assertNotIn(old, PREVIEW)

    def test_one_poll_owner(self):
        self.assertEqual(PREVIEW.count('_keyboard.poll('), 1)
        self.assertIn('_keyboard.poll(', body('_pump_keyboard'))
        self.assertNotIn('Callable(rules', body('_process'))

    def test_release_is_observed_without_consuming_gui(self):
        value = body('_input')
        self.assertIn('not event.pressed', value)
        self.assertIn('_keyboard.sync_physical(', value)
        self.assertNotIn('set_input_as_handled', value)
        self.assertNotIn('_pump_keyboard()', value)

    def test_focus_gate_separate_from_generic_button_lock(self):
        gate = body('_keyboard_context_allowed')
        self.assertIn('gui_get_focus_owner() == null', gate)
        self.assertIn('get_window().has_focus()', gate)
        self.assertNotIn('focus', body('_input_locked'))
        self.assertIn('gui_focus_changed.connect', PREVIEW)
        self.assertIn('focus_exited.connect', PREVIEW)

    def test_cancel_does_not_unlock_inflight_driver(self):
        value = body('_cancel_keyboard')
        self.assertIn('_keyboard.cancel(', value)
        self.assertNotIn('_keyboard_driver_busy', value)
        self.assertNotIn('_keyboard_dispatch_active', value)

    def test_frame_gate_precedes_poll(self):
        value = body('_pump_keyboard')
        self.assertLess(value.index('_keyboard_last_dispatch_frame'), value.index('_keyboard.poll('))
        self.assertIn('_keyboard_last_dispatch_frame = Engine.get_process_frames()', value)

    def test_inflight_completion_is_independent_of_cancel_epoch(self):
        value = body('_pump_keyboard')
        start = value.index('_keyboard_driver_busy = true')
        await_at = value.index('await _step', start)
        end = value.index('_keyboard_driver_busy = false', await_at)
        self.assertLess(start, await_at)
        self.assertLess(await_at, end)
        self.assertNotIn('epoch', value[await_at:end].replace('# A cancellation epoch never skips completion of the in-flight cell.', ''))

    def test_objects_stop_before_a_movement_commit(self):
        value = body('_pump_keyboard')
        self.assertLess(value.index('rules.object_at(target)'), value.index('_keyboard_driver_busy = true'))
        self.assertIn('_cancel_keyboard("object_preview")', value)
        step = body('_step')
        self.assertLess(step.index('rules.object_at(target)'), step.index('Callable(rules,"move")'))
        self.assertEqual(PREVIEW.count('Callable(rules,"move")'), 1)

    def test_confirmation_not_in_direction_bits(self):
        value = body('_direction_bit')
        for key in ('KEY_E,', 'KEY_SPACE', 'KEY_ENTER'):
            self.assertNotIn(key, value)
        self.assertIn('"confirm_edge"', body('_unhandled_key_input'))
        self.assertIn('"explicit_confirm"', body('_confirm_target'))

    def test_world_transition_cancels_keyboard(self):
        self.assertIn('_cancel_keyboard("world_transition")', body('_commit'))
        for name in ('_open_modal', '_close_modal', '_load_slot', '_save_slot', '_use_stairs', '_buy'):
            self.assertIn('_cancel_keyboard(', body(name), name)

    def test_no_engine_or_rule_access_in_pure_controller(self):
        code = '\n'.join(line.split('#', 1)[0] for line in CONTROLLER.splitlines())
        for singleton in ('Input', 'Time', 'Runtime'):
            self.assertNotRegex(code, r'\b' + singleton + r'\s*\.')
        for forbidden in ('get_tree(', 'Callable(rules', 'await '):
            self.assertNotIn(forbidden, code)
        self.assertIn('extends RefCounted', code)
        self.assertRegex(code, r'var _pending:\s*Dictionary')

    def test_clock_parameters_match_the_independent_trace_contract(self):
        contract = json.loads((HERE / 'keyboard_traces.json').read_text())['timing_contract']
        parameters = {
            'CHORD_MS': contract['chord_window_ms'],
            'FIRST_REPEAT_MS': contract['first_repeat_after_dispatched_step_ms'],
            'REPEAT_MS': contract['subsequent_repeat_after_dispatched_step_ms'],
        }
        constants = dict(re.findall(r'^const (CHORD_MS|FIRST_REPEAT_MS|REPEAT_MS): int = (\d+)', CONTROLLER, re.M))
        self.assertEqual({key: int(value) for key, value in constants.items()}, parameters)


if __name__ == '__main__':
    unittest.main()
