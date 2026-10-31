#!/usr/bin/env python3
"""Independent pure-Python reference for the agreed keyboard timing policy.

Run: python -B keyboard_reference.py -v

The hand-authored JSON goldens were written before this implementation. No
production controller is imported, read, translated or executed. Passing these
tests is reference/policy validation, not GDScript or native feel acceptance.

Time is supplied in integer milliseconds. A poll returns at most one of step,
choose or blocked. A single dict holds the latest accepted pending intent;
there is no action queue. The caller supplies currently available grid edges.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

UP, DOWN, LEFT, RIGHT = 1, 2, 4, 8
BITS = (UP, DOWN, LEFT, RIGHT)
ALL_BITS = 15
CHORD_MS = 70
INITIAL_REPEAT_MS = 240
REPEAT_MS = 180
GEOMETRY = (
    ((-1, 0), (-128, -64)),
    ((0, -1), (128, -64)),
    ((0, 1), (-128, 64)),
    ((1, 0), (128, 64)),
)


def logical_mask(mask: int) -> int:
    """Opposite axes cancel direction, never physical all-up state."""
    horizontal = bool(mask & RIGHT) - bool(mask & LEFT)
    vertical = bool(mask & DOWN) - bool(mask & UP)
    return ((RIGHT if horizontal > 0 else LEFT if horizontal < 0 else 0)
            | (DOWN if vertical > 0 else UP if vertical < 0 else 0))


class KeyboardReference:
    """Reference API only; it is not the production GDScript implementation."""

    def __init__(self):
        self.physical_mask = 0
        self.accepted_mask = 0
        self.need_all_up = False
        self.pending: dict | None = None
        self._continuous = False
        self._repeat_due: int | None = None
        self._latch_mask = 0
        self._latch_grid: tuple[int, int] | None = None
        self._last_step_grid: tuple[int, int] | None = None
        self._time = 0

    def _at(self, now_ms: int):
        if not isinstance(now_ms, int) or now_ms < self._time:
            raise ValueError("Monotonic integer milliseconds required")
        self._time = now_ms

    @staticmethod
    def _bit(bit: int):
        if bit not in BITS:
            raise ValueError("One physical key-down bit required")

    @staticmethod
    def _mask(mask: int):
        if not isinstance(mask, int) or mask < 0 or mask & ~ALL_BITS:
            raise ValueError("Physical mask must contain only UP/DOWN/LEFT/RIGHT")

    def _clear_latch(self):
        self._latch_mask = 0
        self._latch_grid = None

    def _stop_continuous(self):
        self._continuous = False
        self._repeat_due = None

    @staticmethod
    def _compatible(grid: tuple[int, int] | None, mask: int) -> bool:
        """A remaining cardinal can retain a previously selected diagonal."""
        if grid is None or not mask:
            return False
        horizontal = bool(mask & RIGHT) - bool(mask & LEFT)
        vertical = bool(mask & DOWN) - bool(mask & UP)
        scores = {
            edge: (horizontal * screen[0] + vertical * screen[1]) / math.hypot(*screen)
            for edge, screen in GEOMETRY
        }
        return scores[grid] > 0 and abs(scores[grid] - max(scores.values())) < 1e-12

    def press(self, bit: int, now_ms: int, repeat: bool = False):
        self._at(now_ms)
        self._bit(bit)
        self.physical_mask |= bit
        if repeat or self.need_all_up or self.accepted_mask & bit:
            return
        previous_logical = logical_mask(self.accepted_mask)
        was_continuous = self._continuous
        self.accepted_mask |= bit
        current = logical_mask(self.accepted_mask & self.physical_mask)
        if not current:
            self.pending = None
            self._stop_continuous()
            self._clear_latch()
            return
        if not previous_logical:
            self._clear_latch()
        ready = now_ms + CHORD_MS
        # Initial collection stays anchored to its first accepted down, even
        # when a busy adapter polls later. In an established held segment a new
        # real press is an immediately eligible turn, not another 70ms delay.
        # A completed tap never contributes released bits to a new chord.
        if (self.pending is not None and not self.pending["completed"]
                and previous_logical):
            ready = self.pending["ready_at"]
        elif previous_logical:
            ready = now_ms
        self.pending = {
            "kind": "press",
            "mask": current,
            "accepted_at": now_ms,
            "ready_at": ready,
            "completed": False,
            "held_modifier": bool(was_continuous and previous_logical),
        }

    def release(self, bit: int, now_ms: int):
        self._at(now_ms)
        self._bit(bit)
        self._apply_physical_release(self.physical_mask & ~bit, now_ms)

    def _apply_physical_release(self, physical_mask: int, now_ms: int):
        previous_physical = self.physical_mask
        previous_logical = logical_mask(self.accepted_mask & previous_physical)
        self.physical_mask = physical_mask
        self.accepted_mask &= physical_mask
        remaining = logical_mask(self.accepted_mask & physical_mask)
        if previous_physical & ~physical_mask:
            # Partial key-up preserves an accepted chord/turn unchanged. A tap
            # becomes immediately ready only when all physical keys are up.
            if self.pending is not None:
                if self.pending["kind"] == "release_resume":
                    if remaining != self.pending["mask"] or physical_mask == 0:
                        self.pending = None
                elif physical_mask == 0:
                    self.pending["completed"] = True
            if self._continuous and self._compatible(self._latch_grid, remaining):
                self._latch_mask = remaining
            else:
                self._stop_continuous()
            if (previous_logical == 0 and remaining and self.pending is None
                    and not self.need_all_up):
                # Releasing one opposed key is not a fresh accepted press tap.
                # It may resume only after a stable 70ms hold, and full release
                # cancels it rather than converting it to a completed tap.
                self.pending = {
                    "kind": "release_resume", "mask": remaining,
                    "accepted_at": now_ms, "ready_at": now_ms + CHORD_MS,
                    "completed": False, "held_modifier": False,
                }
        if self.physical_mask == 0:
            self.need_all_up = False
        if self.pending is None and not self._continuous:
            self._clear_latch()

    def sync_physical(self, physical_mask: int, now_ms: int):
        self._at(now_ms)
        self._mask(physical_mask)
        # Apply the entire observation atomically, never synthetic intermediate
        # single-key releases. Newly observed downs are not accepted/armed.
        self._apply_physical_release(physical_mask, now_ms)

    def cancel(self, reason: str, physical_mask: int, now_ms: int):
        self._at(now_ms)
        self._mask(physical_mask)
        if not reason:
            raise ValueError("Cancellation reason required")
        self.physical_mask = physical_mask
        self.accepted_mask = 0
        self.pending = None
        self._stop_continuous()
        self._clear_latch()
        self._last_step_grid = None
        self.need_all_up = physical_mask != 0

    def _resolve(self, mask: int, options) -> dict:
        available = {tuple(value) for value in options}
        known = {grid for grid, _screen in GEOMETRY}
        if not available <= known:
            raise ValueError("Options must use the agreed isometric geometry")
        if self._latch_mask != mask:
            self._clear_latch()
            self._latch_mask = mask
        if self._latch_grid is not None:
            return {"kind": "step" if self._latch_grid in available else "blocked",
                    "grid": list(self._latch_grid)}
        horizontal = bool(mask & RIGHT) - bool(mask & LEFT)
        vertical = bool(mask & DOWN) - bool(mask & UP)
        length = math.hypot(horizontal, vertical)
        scored = []
        for grid, screen in GEOMETRY:
            score = ((horizontal * screen[0] + vertical * screen[1])
                     / (length * math.hypot(*screen)))
            if score > 0:
                scored.append((grid, score))
        if not scored:
            return {"kind": "blocked", "grid": None}
        best = max(score for _grid, score in scored)
        preferred = [grid for grid, score in scored if abs(score - best) < 1e-12]
        # Geometry defines intent before collision availability is considered.
        # A wall cannot turn an intended diagonal into a lower-angle edge.
        winners = [grid for grid in preferred if grid in available]
        if not winners:
            return {"kind": "blocked", "grid": list(preferred[0]) if len(preferred) == 1 else None}
        if len(winners) != 1:
            return {"kind": "choose", "choices": [list(grid) for grid in winners]}
        self._latch_grid = winners[0]
        return {"kind": "step", "grid": list(winners[0])}

    def _repeat_if_due(self, now_ms: int, options) -> list[dict]:
        if not self._continuous or self._repeat_due is None or now_ms < self._repeat_due:
            return []
        mask = logical_mask(self.accepted_mask & self.physical_mask)
        if not mask:
            self._stop_continuous()
            return []
        result = self._resolve(mask, options)
        if result["kind"] in ("choose", "blocked"):
            self._stop_continuous()
            if result["kind"] == "blocked":
                # The returned grid is the diagnostic captured before stopping;
                # a stopped controller does not retain an active movement latch.
                self._clear_latch()
        else:
            # Schedule relative to this actual poll, never an overdue deadline.
            self._repeat_due = now_ms + REPEAT_MS
            if result["kind"] == "step":
                self._last_step_grid = tuple(result["grid"])
        return [result]

    def poll(self, now_ms: int, busy: bool, options) -> list[dict]:
        self._at(now_ms)
        if busy or self.need_all_up:
            return []
        if self.pending is None:
            return self._repeat_if_due(now_ms, options)
        intent = self.pending
        if not intent["completed"] and now_ms < intent["ready_at"]:
            return []
        self.pending = None
        result = self._resolve(intent["mask"], options)
        if (result["kind"] == "step" and intent["held_modifier"]
                and tuple(result["grid"]) == self._last_step_grid):
            # A held modifier resolving to the same edge is not a bonus step.
            # Key-up may already have stopped repetition; do not resurrect it.
            return self._repeat_if_due(now_ms, options)
        if result["kind"] in ("choose", "blocked"):
            # Consume this intent once. A new accepted input can resolve it;
            # frame polls and OS echoes cannot repeatedly emit choose/blocked.
            self._stop_continuous()
            if result["kind"] == "blocked":
                self._clear_latch()
        else:
            live = logical_mask(self.accepted_mask & self.physical_mask)
            self._continuous = bool(live and (
                result["grid"] is None or self._compatible(tuple(result["grid"]), live)))
            self._repeat_due = now_ms + INITIAL_REPEAT_MS if self._continuous else None
            if self._continuous and self._latch_grid is not None:
                self._latch_mask = live
            if result["kind"] == "step":
                self._last_step_grid = tuple(result["grid"])
        return [result]

    def debug_state(self) -> dict:
        return {
            "physical_mask": self.physical_mask,
            "accepted_mask": self.accepted_mask,
            "logical_mask": logical_mask(self.accepted_mask & self.physical_mask),
            "need_all_up": self.need_all_up,
            "pending_count": int(self.pending is not None),
            "pending_mask": None if self.pending is None else self.pending["mask"],
            "pending_kind": None if self.pending is None else self.pending["kind"],
            "pending_completed": False if self.pending is None else self.pending["completed"],
            "continuous": self._continuous,
            "repeat_due": self._repeat_due,
            "latch": None if self._latch_grid is None else list(self._latch_grid),
        }


GOLDENS = json.loads(Path(__file__).with_name("keyboard_traces.json").read_text(encoding="utf-8"))


class KeyboardPolicyGoldens(unittest.TestCase):
    """JSON expectations are independent, explicit action traces."""

    def run_golden(self, case, reason=None):
        model = KeyboardReference()
        options = case["options"]
        for index, event in enumerate(case["events"]):
            with self.subTest(trace=case["name"], reason=reason, event=index, t=event["t"]):
                now = event["t"]
                operation = event["op"]
                if operation == "press":
                    model.press(event["bit"], now, event.get("repeat", False))
                elif operation == "release":
                    model.release(event["bit"], now)
                elif operation == "sync":
                    model.sync_physical(event["physical"], now)
                elif operation == "cancel":
                    label = reason if event["reason"] == "$reason" else event["reason"]
                    model.cancel(label, event["physical"], now)
                elif operation == "options":
                    options = event["value"]
                elif operation == "poll":
                    actual = model.poll(now, event.get("busy", False), options)
                    self.assertEqual(event["expect"], actual)
                    self.assertLessEqual(sum(row["kind"] == "step" for row in actual), 1)
                else:
                    self.fail("Unknown golden operation: " + operation)
                state = model.debug_state()
                self.assertLessEqual(state["pending_count"], 1)
                self.assertTrue(model.pending is None or isinstance(model.pending, dict))
                for key, expected in event.get("state", {}).items():
                    self.assertEqual(expected, state[key], key)

    def test_fixed_geometry_matches_contract(self):
        self.assertEqual(GOLDENS["geometry"], [
            {"grid": list(grid), "screen": list(screen)} for grid, screen in GEOMETRY
        ])

    def test_invalid_input_and_time_rejected(self):
        model = KeyboardReference()
        for bit in (0, 3, 16):
            with self.assertRaises(ValueError):
                model.press(bit, 0)
        with self.assertRaises(ValueError):
            model.sync_physical(16, 0)
        model.press(UP, 10)
        with self.assertRaises(ValueError):
            model.poll(9, False, [[-1, 0]])


def golden_test(case, reason):
    def test(self):
        self.run_golden(case, reason)
    return test


for _case in GOLDENS["cases"]:
    for _reason in _case.get("repeat_for_reasons", [None]):
        _suffix = "_" + _reason if _reason is not None else ""
        setattr(KeyboardPolicyGoldens, "test_" + _case["name"] + _suffix,
                golden_test(_case, _reason))


if __name__ == "__main__":
    print("REFERENCE_POLICY_ONLY: no production GDScript, engine, UI or native feel acceptance", flush=True)
    unittest.main()
