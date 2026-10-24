extends RefCounted

const STEP_DISTANCE := 0.70
const MIN_INTERVAL := 0.28
const MAX_FRAME_DISTANCE := 1.5
var _last_distance := 0.0
var _travel := 0.0
var _elapsed := 0.0

func reset(total_distance := 0.0) -> void:
	_last_distance = total_distance if is_finite(total_distance) and total_distance >= 0.0 else 0.0
	_travel = 0.0
	_elapsed = 0.0

func advance(total_distance: float, delta: float, walking: bool) -> bool:
	if not is_finite(total_distance) or total_distance < 0.0 or not is_finite(delta) or delta <= 0.0:
		reset(total_distance)
		return false
	var moved := total_distance - _last_distance
	_last_distance = total_distance
	if not walking or moved < 0.0 or moved > MAX_FRAME_DISTANCE:
		reset(total_distance)
		return false
	_elapsed = minf(_elapsed + delta, MIN_INTERVAL)
	_travel += moved
	if _travel < STEP_DISTANCE or _elapsed < MIN_INTERVAL:
		return false
	# Drop missed contacts after a slow frame instead of playing a catch-up burst.
	_travel = fmod(_travel, STEP_DISTANCE)
	_elapsed = 0.0
	return true
