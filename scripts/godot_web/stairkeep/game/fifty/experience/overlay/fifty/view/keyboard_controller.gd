extends RefCounted
## Pure keyboard intent state. The adapter supplies accepted key edges and ms.
## No rule calls, engine input, clock, scene tree or movement execution here.
## poll emits at most one neighbor request. The driver owns its busy ticket.

const ScreenInput = preload("res://fifty/view/screen_input.gd")
const UP: int = 1
const DOWN: int = 2
const LEFT: int = 4
const RIGHT: int = 8
const ALL: int = UP | DOWN | LEFT | RIGHT
const CHORD_MS: int = 70
const FIRST_REPEAT_MS: int = 240
const REPEAT_MS: int = 180

var _held: int = 0
var _physical: int = 0
var _need_all_up: bool = false
var _epoch: int = 0
var _now: int = 0
var _pending: Dictionary = {} # Only a screen intent; never a cell or callable.
var _pending_ready_at: int = -1
var _pending_completed: bool = false
var _pending_kind: String = ""
var _chord_deadline: int = -1
var _has_stepped: bool = false
var _hold_active: bool = false
var _stopped: bool = false
var _waiting_choice: bool = false
var _latched: Array = []
var _next_repeat_at: int = -1
var _reason: String = "idle"
var _basis: Array = [] # Screen geometry at synthetic origin, not world targets.


func press(bit: int, now: int) -> void:
	var stamp: int = _clock(now)
	if not _single_bit(bit): return
	_physical |= bit
	if _need_all_up or (_held & bit) != 0: return
	if _held == 0 or _intent(_held) == Vector2.ZERO:
		_chord_deadline = stamp + CHORD_MS
		_has_stepped = false
	_held |= bit
	_epoch += 1
	var was_stopped: bool = _stopped
	_stopped = false
	_waiting_choice = false
	var intent: Vector2 = _intent(_held)
	if intent == Vector2.ZERO:
		_clear_pending()
		_clear_hold()
		_chord_deadline = -1
		_has_stepped = false
		_reason = "opposed"
		return
	# A compatible held modifier must not become an extra immediate step.
	if not was_stopped and _hold_active and _pending.is_empty() and _compatible(intent):
		_reason = "compatible_modifier"
		return
	if not _compatible(intent): _latched.clear()
	_set_pending(intent, stamp if _has_stepped else maxi(stamp, _chord_deadline), "press")
	_hold_active = false
	_next_repeat_at = -1
	_reason = "accepted_press"


func release(bit: int, now: int) -> void:
	var stamp: int = _clock(now)
	if not _single_bit(bit): return
	_physical &= ALL ^ bit
	if _need_all_up:
		if _physical == 0:
			_need_all_up = false
			_reason = "neutral"
		return
	if (_held & bit) == 0: return
	_release_to(_held & (ALL ^ bit), stamp)


func _release_to(remaining: int, stamp: int) -> void:
	_held = remaining
	_epoch += 1
	_waiting_choice = false
	# A real accepted tap/turn is retained once, including an overlapping chord.
	# A later non-overlapping press replaces this one slot rather than combining.
	if not _pending.is_empty() and _pending_kind == "press":
		_hold_active = false
		_next_repeat_at = -1
		if _held == 0:
			_pending_completed = true
			_pending_ready_at = stamp
			_clear_hold()
			_chord_deadline = -1
			_has_stepped = false
			_reason = "completed_tap"
		else:
			# Partial key-up preserves the accepted chord and its original deadline.
			_reason = "chord_partial_release"
		return
	if _held == 0:
		_clear_pending() # A derived release-resume is not a completed press tap.
		_clear_hold()
		_chord_deadline = -1
		_has_stepped = false
		_stopped = false
		_reason = "released"
		return
	if _stopped:
		_reason = "stopped"
		return
	var intent: Vector2 = _intent(_held)
	if intent == Vector2.ZERO:
		_clear_pending()
		_clear_hold()
		_reason = "opposed"
		return
	if _hold_active and _compatible(intent):
		_reason = "compatible_release"
		return
	# A held change may resolve a previous choice, but cannot resurrect new keys.
	_latched.clear()
	_chord_deadline = stamp + CHORD_MS
	_set_pending(intent, _chord_deadline, "release_resume")
	_hold_active = false
	_next_repeat_at = -1
	_reason = "held_changed"


func sync_physical(mask: int, now: int) -> void:
	var stamp: int = _clock(now)
	_physical = mask & ALL
	if _need_all_up:
		if _physical == 0:
			_need_all_up = false
			_reason = "neutral"
		return
	# Observe lost key-up edges only. Physical polling never adds accepted keys.
	var remaining: int = _held & _physical
	if remaining != _held: _release_to(remaining, stamp)


func cancel(reason: String, physical_mask: int = 0) -> void:
	_epoch += 1
	_held = 0
	_physical = physical_mask & ALL
	_need_all_up = _physical != 0
	_clear_pending()
	_clear_hold()
	_chord_deadline = -1
	_has_stepped = false
	_basis.clear()
	_stopped = false
	_waiting_choice = false
	_reason = reason


func poll(now: int, busy: bool, options: Array) -> Dictionary:
	var stamp: int = _clock(now)
	if _need_all_up: return _idle("need_all_up")
	if busy: return _idle("busy")
	if not _pending.is_empty():
		if stamp < _pending_ready_at: return _idle("chord_wait")
		var intent: Vector2 = _pending["intent"]
		return _attempt(intent, options, stamp, false)
	if _waiting_choice: return _idle("awaiting_choice")
	if _stopped: return _idle("stopped")
	if not _hold_active or _held == 0: return _idle("idle")
	var intent: Vector2 = _intent(_held)
	if intent == Vector2.ZERO:
		_clear_hold()
		return _idle("opposed")
	if stamp < _next_repeat_at: return _idle("repeat_wait")
	return _attempt(intent, options, stamp, true)


func debug_state() -> Dictionary:
	return {"held_mask": _held, "physical_mask": _physical, "pending_count": 0 if _pending.is_empty() else 1, "pending_intent": _pending.get("intent", Vector2.ZERO), "pending_kind": _pending_kind, "pending_completed": _pending_completed, "pending_ready_at": _pending_ready_at, "need_all_up": _need_all_up, "waiting_choice": _waiting_choice, "latched_delta": _latched.duplicate(), "epoch": _epoch, "next_repeat_at": _next_repeat_at, "hold_active": _hold_active, "stopped": _stopped, "reason": _reason}


func _attempt(intent: Vector2, options: Array, stamp: int, repeated: bool) -> Dictionary:
	var ranked: Dictionary = ScreenInput.resolve(intent, options)
	var status: String = str(ranked.get("status", "blocked"))
	if status == "blocked" and str(ranked.get("reason", "")) in ["invalid_options", "invalid_intent", "invalid_geometry"]:
		return _block(str(ranked["reason"]))
	_cache_basis(options)
	var choice: Dictionary = {}
	if _compatible(intent):
		for option: Dictionary in options:
			if option.get("delta", []) == _latched:
				if not bool(option.get("walkable", false)):
					return _block("latched_wall")
				choice = {"cell": option["cell"].duplicate(), "delta": _latched.duplicate()}
				break
	else:
		_latched.clear()
	if choice.is_empty():
		if status == "blocked": return _block(str(ranked.get("reason", "blocked")))
		if status == "choose":
			_clear_pending()
			_clear_hold()
			_waiting_choice = true
			_reason = "choose"
			return {"status": "choose", "cells": ranked["cells"].duplicate(true), "options": ranked["options"].duplicate(true), "epoch": _epoch}
		if status != "step":
			_clear_pending()
			_clear_hold()
			return _idle("idle")
		choice = {"cell": ranked["cell"].duplicate(), "delta": ranked["delta"].duplicate()}
	_clear_pending()
	_latched = choice["delta"].duplicate()
	_has_stepped = true
	_hold_active = _held != 0 and _intent(_held) != Vector2.ZERO
	_stopped = false
	_waiting_choice = false
	_reason = "repeat" if repeated else "step"
	_next_repeat_at = stamp + (REPEAT_MS if repeated else FIRST_REPEAT_MS) if _hold_active else -1
	if not _hold_active or not _compatible(_intent(_held)): _latched.clear()
	return {"status": "step", "cell": choice["cell"].duplicate(), "delta": choice["delta"].duplicate(), "repeat": repeated, "epoch": _epoch}


func _compatible(intent: Vector2) -> bool:
	if _latched.size() != 2 or _basis.size() != 4 or intent == Vector2.ZERO: return false
	var geometric: Dictionary = ScreenInput.resolve(intent, _basis)
	for option: Dictionary in geometric.get("options", []):
		if option.get("delta", []) == _latched: return true
	return false


func _cache_basis(options: Array) -> void:
	_basis.clear()
	for option: Dictionary in options:
		var delta: Array = option["delta"].duplicate()
		# A synthetic origin avoids storing absolute world cells between polls.
		_basis.append({"cell": delta.duplicate(), "delta": delta, "screen": option["screen"], "walkable": true})


func _block(reason: String) -> Dictionary:
	_clear_pending()
	_clear_hold()
	_stopped = true
	_waiting_choice = false
	_reason = reason
	return {"status": "blocked", "reason": reason, "epoch": _epoch}


func _idle(reason: String) -> Dictionary:
	return {"status": "idle", "reason": reason, "epoch": _epoch}


func _set_pending(intent: Vector2, ready_at: int, kind: String) -> void:
	_pending = {"intent": intent}
	_pending_ready_at = ready_at
	_pending_completed = false
	_pending_kind = kind


func _clear_pending() -> void:
	_pending.clear()
	_pending_ready_at = -1
	_pending_completed = false
	_pending_kind = ""


func _clear_hold() -> void:
	_hold_active = false
	_next_repeat_at = -1
	_latched.clear()


func _clock(value: int) -> int:
	_now = maxi(_now, maxi(0, value))
	return _now


static func _single_bit(bit: int) -> bool:
	return bit in [UP, DOWN, LEFT, RIGHT]


static func _intent(mask: int) -> Vector2:
	return Vector2(int((mask & RIGHT) != 0) - int((mask & LEFT) != 0), int((mask & DOWN) != 0) - int((mask & UP) != 0))
