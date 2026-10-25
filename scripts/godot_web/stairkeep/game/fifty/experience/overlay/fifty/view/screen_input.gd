extends RefCounted
## Pure screen-intent policy. This helper neither queries nor invokes game rules.
## screen is the projected NEIGHBOR center minus the projected CURRENT center.
## Supply all four cardinal neighbors, including walls and outside-map cells.
## D4 is already reflected in runtime coordinates; do not rotate deltas again.

const DOT_EPSILON: float = 0.0001


static func resolve(intent: Vector2, options: Array) -> Dictionary:
	if not _finite_vector(intent):
		return _blocked("invalid_intent")
	var direction: Vector2 = _unit(intent)
	if direction == Vector2.ZERO:
		return {"status": "idle", "cells": [], "options": []}
	# Missing geometric neighbors could silently turn a wall into a fallback.
	if options.size() != 4:
		return _blocked("invalid_options")
	var seen: Dictionary = {}
	var origin: Vector2i = Vector2i.ZERO
	var origin_known: bool = false
	var scored: Array[Dictionary] = []
	var highest: float = -INF
	for raw: Variant in options:
		if not (raw is Dictionary) or not _grid_pair(raw.get("cell")) or not _grid_pair(raw.get("delta")):
			return _blocked("invalid_options")
		if not (raw.get("screen") is Vector2) or not (raw.get("walkable") is bool):
			return _blocked("invalid_options")
		var cell: Array = [int(raw["cell"][0]), int(raw["cell"][1])]
		var delta: Array = [int(raw["delta"][0]), int(raw["delta"][1])]
		var axis: Vector2i = Vector2i(delta[0], delta[1])
		if absi(axis.x) + absi(axis.y) != 1 or seen.has(axis):
			return _blocked("invalid_options")
		seen[axis] = true
		var candidate_origin: Vector2i = Vector2i(cell[0] - delta[0], cell[1] - delta[1])
		if origin_known and candidate_origin != origin:
			return _blocked("invalid_options")
		origin = candidate_origin
		origin_known = true
		var screen: Vector2 = raw["screen"]
		if not _finite_vector(screen) or screen == Vector2.ZERO:
			return _blocked("invalid_options")
		var score: float = direction.dot(_unit(screen))
		var option: Dictionary = {"cell": cell, "delta": delta, "screen": screen, "walkable": raw["walkable"]}
		scored.append({"option": option, "score": score})
		highest = maxf(highest, score)
	if highest <= DOT_EPSILON:
		return _blocked("no_forward_neighbor")
	# Score ALL geometry first. Walkability is intentionally inspected only here.
	var candidates: Array[Dictionary] = []
	for entry: Dictionary in scored:
		if absf(float(entry["score"]) - highest) <= DOT_EPSILON and bool(entry["option"]["walkable"]):
			candidates.append(entry["option"])
	if candidates.is_empty():
		return _blocked("forward_blocked")
	if candidates.size() == 1:
		var choice: Dictionary = candidates[0]
		return {"status": "step", "cell": choice["cell"].duplicate(), "delta": choice["delta"].duplicate(), "options": candidates, "score": highest}
	if candidates.size() == 2:
		return {"status": "choose", "cells": [candidates[0]["cell"].duplicate(), candidates[1]["cell"].duplicate()], "options": candidates, "score": highest}
	# A nondegenerate projection of four cardinal neighbors has at most two ties.
	return _blocked("invalid_geometry")


static func _blocked(reason: String) -> Dictionary:
	return {"status": "blocked", "reason": reason, "cells": [], "options": []}


static func _finite_vector(value: Vector2) -> bool:
	return is_finite(value.x) and is_finite(value.y)


static func _unit(value: Vector2) -> Vector2:
	# Scale before normalizing to avoid overflow/underflow for finite vectors.
	var scale: float = maxf(absf(value.x), absf(value.y))
	return (value / scale).normalized() if scale > 0.0 else Vector2.ZERO


static func _grid_pair(value: Variant) -> bool:
	if not (value is Array) or value.size() != 2:
		return false
	for part: Variant in value:
		if not (part is int or part is float):
			return false
		var number: float = float(part)
		if not is_finite(number) or number != floorf(number) or absf(number) > 2147483647.0:
			return false
	return true
