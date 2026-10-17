"""Read-only route observations and real-input steering; never changes game state."""
from __future__ import annotations
import math
import time
from observers import finite_vector, positive_integer

# The authored public route is intentionally explicit. CI must physically reach each
# point through the same controller as a player. No game-state setter is exposed.
ROUTE = [
    {"name": "read the beach map", "target": [1.3, 7.8], "stage": 1},
    {"name": "open the inland cache", "target": [-3.8, 3.4], "stage": 2, "screenshot": "tidal-02.png"},
    {"name": "enter the sheltered bay", "target": [1.5, 6.2]},
    {"name": "recover the sea treasure", "target": [8.2, 5.5], "stage": 3},
    {"name": "swim back onto the beach", "target": [7.0, .5]},
    {"name": "follow the inner path", "target": [2.0, -3.0]},
    {"name": "return both treasures to the ring", "target": [0.0, -11.7],
     "approach": [0.0, -10.25], "radius": .25, "stage": 4},
]
FINAL_STAGE = 4
STATE_PREFIX = "TIDAL_STATE"
INTERACTION_RADIUS = 1.55
SETTLED_HORIZONTAL_SPEED = .08
BROWSER_PHYSICS_LIMIT_SECONDS = 15
BROWSER_ABSOLUTE_WALL_LIMIT_SECONDS = 240


def finite_seconds(value, name, maximum=None):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0 or (maximum is not None and value > maximum):
        raise ValueError(name + " must be a finite positive duration within its supported limit")
    return value


def validate_state(state, previous=None, expected_demo=False):
    if type(state.get("schema")) is not int or state["schema"] != 1:
        raise ValueError("Unsupported gameplay observer schema")
    sample = positive_integer(state.get("sample_id"), "sample_id")
    frame = positive_integer(state.get("physics_frame"), "physics_frame")
    position = finite_vector(state.get("position"), 3, "position")
    if state.get("demo") is not expected_demo:
        raise ValueError("Gameplay evidence came from the wrong input route")
    if state.get("locomotion") not in ("walk", "wade", "swim"):
        raise ValueError("Missing actual locomotion state")
    depth = state.get("water_depth")
    if type(depth) not in (int, float) or not math.isfinite(depth) or depth < 0:
        raise ValueError("Actual water depth must be finite and nonnegative")
    if state["locomotion"] == "swim" and depth < .60:
        raise ValueError("Swim mode lacks actual swimming-depth water")
    if state.get("language") not in ("en", "zh"):
        raise ValueError("Actual gameplay language is missing or invalid")
    for field in ("camera_right", "camera_forward"):
        axis = finite_vector(state.get(field), 2, field)
        if not .95 <= math.hypot(*axis) <= 1.05:
            raise ValueError("Camera steering axis must be normalized")
    if abs(sum(a * b for a, b in zip(state["camera_right"], state["camera_forward"]))) > .05:
        raise ValueError("Camera steering axes must be orthogonal")
    rect = finite_vector(state.get("action_rect"), 4, "action_rect")
    if rect[2] <= 0 or rect[3] <= 0:
        raise ValueError("Actual action button must have a nonempty rectangle")
    finite_vector(state.get("movement_input"), 2, "movement_input")
    finite_vector(state.get("velocity"), 3, "velocity")
    if type(state.get("interaction_available")) is not bool:
        raise ValueError("Actual interaction availability must be a boolean")
    if "interaction_reason" in state and not isinstance(state["interaction_reason"], str):
        raise ValueError("Actual interaction reason must be text")
    validate_progress(state)
    if previous is not None:
        if sample <= previous["sample_id"] or frame <= previous["physics_frame"]:
            raise ValueError("Gameplay observations must advance monotonically")
        # Physics is fixed at 60 Hz. A generous upper bound permits acceleration,
        # collision resolution and waves, but rejects reset/teleport shortcuts.
        elapsed = (frame - previous["physics_frame"]) / 60
        distance = math.hypot(position[0] - previous["position"][0], position[2] - previous["position"][2])
        if distance > elapsed * 8 + .35:
            raise ValueError("Physical route contains an impossible horizontal jump")
        advance = state["quest_stage"] - previous["quest_stage"]
        if advance < 0:
            raise ValueError("Quest progress regressed during physical-input route")
        if advance > 1:
            raise ValueError("Quest progress skipped an intermediate stage")
    return state


def validate_progress(state):
    stage = state.get("quest_stage")
    if type(stage) is not int or not 0 <= stage <= FINAL_STAGE:
        raise ValueError("Invalid actual quest stage")
    treasures = state.get("treasures")
    if not isinstance(treasures, list) or len(treasures) != 2 or any(type(x) is not bool for x in treasures):
        raise ValueError("Actual treasure flags must be two booleans")
    if type(state.get("completed")) is not bool:
        raise ValueError("Actual completion must be a boolean")
    expected_treasures = ([False, False], [False, False], [True, False], [True, True], [True, True])[stage]
    if treasures != expected_treasures or state["completed"] != (stage == FINAL_STAGE):
        raise ValueError("Quest stage, treasure flags and completion are inconsistent")
    return state


def complete(state):
    validate_progress(state)
    return state["quest_stage"] == FINAL_STAGE and state["treasures"] == [True, True] and state["completed"] is True


def validate_restored(receipt, expected):
    if type(receipt.get("schema")) is not int or receipt["schema"] != 1 or receipt.get("found") is not True:
        raise ValueError("Fresh process did not read an actual existing save")
    validate_progress(receipt)
    for field in ("quest_stage", "treasures", "completed", "language"):
        if field not in expected or receipt.get(field) != expected[field]:
            raise ValueError("Fresh-process save restoration mismatch: " + field)
    before = finite_vector(expected.get("position"), 3, "saved position")
    after = finite_vector(receipt.get("position"), 3, "loaded position")
    if math.hypot(before[0] - after[0], before[2] - after[2]) > .35:
        raise ValueError("Fresh-process restore changed horizontal saved position")
    if not complete(receipt):
        raise ValueError("Fresh-process restore lost completed treasure loop")
    return receipt


def direction_to(state, target):
    dx, dz = target[0] - state["position"][0], target[1] - state["position"][2]
    length = math.hypot(dx, dz)
    if length < 1e-9:
        return (0, 0)
    right, forward = state["camera_right"], state["camera_forward"]
    return ((dx * right[0] + dz * right[1]) / length,
            -(dx * forward[0] + dz * forward[1]) / length)


def keyboard_direction(direction):
    x, y = direction
    return {key for amount, key in ((x, "d"), (-x, "a"), (y, "s"), (-y, "w")) if amount > .36}


def horizontal_distance(state, target):
    return math.hypot(state["position"][0] - target[0], state["position"][2] - target[1])


def inside_approach(state, point):
    return horizontal_distance(state, point.get("approach", point["target"])) <= point.get("radius", .8)


def inside_interaction_region(state, point):
    # The approach point guides steering, not the game's usable pickup region.
    # Actual availability also establishes production height/line-of-sight checks.
    return (state.get("interaction_available") is True
            and horizontal_distance(state, point["target"]) < INTERACTION_RADIUS)


def mode_sequence(samples):
    result = []
    for sample in samples:
        mode = sample["locomotion"]
        if not result or result[-1] != mode:
            result.append(mode)
    return result


def validate_water_crossing(samples):
    expected = iter(("walk", "wade", "swim", "wade", "walk"))
    wanted = next(expected)
    for mode in mode_sequence(samples):
        if mode == wanted:
            wanted = next(expected, None)
            if wanted is None:
                break
    if wanted is not None:
        raise ValueError("Physical route did not establish walk → wade → swim → wade → shore")
    swimmers = [item for item in samples if item["locomotion"] == "swim"]
    longest, start = 0, None
    for item in samples:
        if item["locomotion"] == "swim":
            if start is None:
                start = item["physics_frame"]
            longest = max(longest, item["physics_frame"] - start)
        else:
            start = None
    if len(swimmers) < 3 or longest < 60:
        raise ValueError("Physical route did not sustain sea swimming for at least one physics second")
    return {"modes": mode_sequence(samples), "swim_samples": len(swimmers),
            "longest_continuous_swim_physics_frames": longest}


class RouteDriver:
    """Callbacks must send physical OS/browser input. Observations are passive logs."""
    def __init__(self, read_states, move, interact, pause, snapshot, timeout=75,
                 physics_timeout=None, absolute_wall_timeout=None):
        self.read_states, self.move, self.interact = read_states, move, interact
        self.pause, self.snapshot = pause, snapshot
        self.timeout = finite_seconds(timeout, "Legacy waypoint timeout")
        if (physics_timeout is None) != (absolute_wall_timeout is None):
            raise ValueError("Browser waypoint budgets require both physics and absolute wall limits")
        self.physics_timeout = None if physics_timeout is None else finite_seconds(
            physics_timeout, "Physics waypoint timeout", BROWSER_PHYSICS_LIMIT_SECONDS)
        self.absolute_wall_timeout = None if absolute_wall_timeout is None else finite_seconds(
            absolute_wall_timeout, "Absolute wall waypoint timeout", BROWSER_ABSOLUTE_WALL_LIMIT_SECONDS)
        self.samples, self.milestones, self.captured = [], [], set()
        self.last_action = 0
        self.last_action_sample_id = 0
        self.last_observation_time = time.monotonic()
        self.pending_action = None
        self.actions = []
        self.accepted_stage = 0
        self.capture_seconds = 0.0
        self.stop_boundary = None
        self.stops = []
        self.budgets = []
        self.active_budget = None
        self.current_waypoint = None

    @property
    def budget_policy(self):
        if self.physics_timeout is None:
            return {"kind": "legacy_active_wall", "active_wall_limit_seconds": self.timeout,
                    "excludes_measured_screenshots": True, "observation_silence_limit_seconds": 10}
        return {"kind": "physics_and_absolute_wall", "physics_limit_seconds": self.physics_timeout,
                "absolute_wall_limit_seconds": self.absolute_wall_timeout,
                "excludes_measured_screenshots": False, "observation_silence_limit_seconds": 10}

    def begin_waypoint_budget(self, point, state):
        started = time.monotonic()
        frame = positive_integer(state["physics_frame"], "budget baseline physics_frame")
        budget = {"schema": 1, "waypoint": point["name"], "policy": self.budget_policy,
                  "started_at": started, "baseline_sample_id": state["sample_id"],
                  "baseline_physics_frame": frame, "capture_seconds_before": self.capture_seconds,
                  "status": "running", "expired_budgets": []}
        if self.physics_timeout is not None:
            budget["absolute_wall_deadline"] = started + self.absolute_wall_timeout
            budget["physics_frame_deadline"] = frame + self.physics_timeout * 60
        else:
            budget["active_wall_limit_seconds"] = self.timeout
        self.active_budget = budget
        self.budgets.append(budget)
        self.update_waypoint_budget(state)
        return budget

    def update_waypoint_budget(self, state):
        budget = self.active_budget
        frame = positive_integer(state["physics_frame"], "budget physics_frame")
        sample = positive_integer(state["sample_id"], "budget sample_id")
        if frame < budget["baseline_physics_frame"] or sample < budget["baseline_sample_id"]:
            raise ValueError("Waypoint budget observations regressed")
        wall = time.monotonic() - budget["started_at"]
        captures = self.capture_seconds - budget["capture_seconds_before"]
        budget.update({"elapsed_wall_seconds": wall, "measured_capture_seconds": captures,
                       "elapsed_active_wall_seconds": wall - captures,
                       "elapsed_physics_frames": frame - budget["baseline_physics_frame"],
                       "elapsed_physics_seconds": (frame - budget["baseline_physics_frame"]) / 60,
                       "last_sample_id": sample, "last_physics_frame": frame})
        return budget

    def expired_waypoint_budgets(self, budget):
        if self.physics_timeout is None:
            return ["active_wall"] if budget["elapsed_active_wall_seconds"] >= budget["active_wall_limit_seconds"] else []
        expired = []
        if budget["last_physics_frame"] >= budget["physics_frame_deadline"]:
            expired.append("physics")
        if budget["elapsed_wall_seconds"] >= budget["absolute_wall_deadline"] - budget["started_at"]:
            expired.append("absolute_wall")
        return expired

    def check_waypoint_budget(self, state):
        budget = self.update_waypoint_budget(state)
        expired = self.expired_waypoint_budgets(budget)
        if expired:
            budget.update({"status": "expired", "expired_budgets": expired})
            error_type = RuntimeError if self.physics_timeout is None else TimeoutError
            raise error_type("Physical route could not reach/complete " + budget["waypoint"]
                             + ": waypoint budget expired " + str(budget) + "; last state: " + str(state))

    def capture(self, name, state):
        started = time.monotonic()
        self.snapshot(name, state)
        self.capture_seconds += time.monotonic() - started

    def milestone_reached(self, state, point):
        if "stage" not in point:
            return inside_approach(state, point)
        if state["quest_stage"] != point["stage"]:
            return False
        # The action's first advancing sample was already checked against the
        # actual 1.55 m interaction range. Callback latency may leave the latest
        # sample outside the tighter navigation radius; do not steer back or tap
        # again after a valid, exact, physically requested interaction.
        if self.accepted_stage != point["stage"] or not any(
                action.get("accepted_sample_id") and action["target_stage"] == point["stage"]
                and action["target"] == list(point["target"]) and action["waypoint"] == point["name"]
                for action in self.actions):
            raise ValueError("Milestone lacks its matching accepted physical action")
        return True

    def stop_for_action(self, state, point):
        if self.pending_action is not None:
            raise ValueError("Cannot begin another stop while a physical action is pending")
        self.move((0, 0))
        callback_returned_at = time.monotonic()
        # CDP/X11 delivery can take longer than a simulation second. Discard the
        # pre-stop position as an action basis, then establish a read-only sample
        # boundary after the real stop callback has returned. Even an already
        # neutral sample in that queue is not the required subsequent physics.
        baseline = self.observe()
        boundary = {"waypoint": point["name"], "target": list(point["target"]),
                    "approach": list(point.get("approach", point["target"])),
                    "requested_after_sample_id": state["sample_id"],
                    "after_sample_id": baseline["sample_id"],
                    "after_physics_frame": baseline["physics_frame"],
                    "callback_returned_at": callback_returned_at}
        self.stop_boundary = boundary
        self.stops.append(boundary)
        return baseline

    def settled_after_stop(self, state, point):
        boundary = self.stop_boundary
        if boundary is None or (boundary["waypoint"], boundary["target"], boundary["approach"]) != (
                point["name"], list(point["target"]), list(point.get("approach", point["target"]))):
            return False
        movement = finite_vector(state.get("movement_input"), 2, "movement_input")
        velocity = finite_vector(state.get("velocity"), 3, "velocity")
        return (state["sample_id"] > boundary["after_sample_id"]
                and state["physics_frame"] > boundary["after_physics_frame"]
                and all(abs(value) <= 1e-6 for value in movement)
                and math.hypot(velocity[0], velocity[2]) <= SETTLED_HORIZONTAL_SPEED)

    def request_action(self, state, point):
        """Record the physical callback request, never grant progress by itself."""
        validate_progress(state)
        target_stage = point.get("stage")
        if target_stage != self.accepted_stage + 1 or state["quest_stage"] != self.accepted_stage:
            raise ValueError("Physical action does not match the next exact quest milestone")
        if self.pending_action is not None:
            raise ValueError("A physical action is already pending for this milestone")
        if horizontal_distance(state, point["target"]) >= INTERACTION_RADIUS:
            raise ValueError("Physical action was requested outside the authored interaction range")
        if not self.settled_after_stop(state, point):
            raise ValueError("Physical action requires fresh neutral and settled physics after the stop callback")
        if state.get("interaction_available") is not True:
            raise ValueError("Actual interaction is unavailable after stopping: " + str(state.get("interaction_reason", "unknown")))
        self.stop_boundary["settled_sample_id"] = state["sample_id"]
        self.stop_boundary["settled_physics_frame"] = state["physics_frame"]
        action = {"from_stage": self.accepted_stage, "target_stage": target_stage,
                  "after_sample_id": state["sample_id"], "after_physics_frame": state["physics_frame"],
                  "target": list(point["target"]), "position": list(state["position"]),
                  "waypoint": point["name"], "requested_at": time.monotonic(), "callback_returned": False,
                  "stop": dict(self.stop_boundary), "movement_input": list(state["movement_input"]),
                  "velocity": list(state["velocity"]), "interaction_available": state["interaction_available"]}
        self.actions.append(action)
        self.pending_action = action
        self.stop_boundary = None
        self.interact(state)
        action["callback_returned"] = True
        self.last_action = time.monotonic()
        self.last_action_sample_id = state["sample_id"]

    def accept_progress(self, state, previous):
        if previous is None:
            if state["quest_stage"] != 0:
                raise ValueError("Physical route did not start at the fresh quest stage")
            return
        if state["quest_stage"] == previous["quest_stage"]:
            return
        action = self.pending_action
        if action is None or action["callback_returned"] is not True:
            raise ValueError("Quest advanced without a completed physical-action callback")
        if (previous["quest_stage"] != self.accepted_stage or
                action["from_stage"] != previous["quest_stage"] or
                action["target_stage"] != state["quest_stage"]):
            raise ValueError("Quest advance does not match the requested physical action")
        if state["sample_id"] <= action["after_sample_id"] or state["physics_frame"] <= action["after_physics_frame"]:
            raise ValueError("Quest advance predates the requested physical action")
        distance = math.hypot(state["position"][0] - action["target"][0], state["position"][2] - action["target"][1])
        if distance >= INTERACTION_RADIUS:
            raise ValueError("Quest advanced outside the requested interaction location")
        action["accepted_sample_id"] = state["sample_id"]
        action["accepted_physics_frame"] = state["physics_frame"]
        self.accepted_stage = state["quest_stage"]
        self.pending_action = None

    def observe(self):
        fresh = self.read_states()
        previous = self.samples[-1] if self.samples else None
        for item in fresh:
            if previous and item.get("sample_id", 0) <= previous["sample_id"]:
                continue
            validate_state(item, previous)
            self.accept_progress(item, previous)
            self.samples.append(item)
            self.last_observation_time = time.monotonic()
            previous = item
            mode = item["locomotion"]
            if mode in ("wade", "swim") and mode not in self.captured:
                # Pause actual movement for an intelligible player-camera screenshot;
                # primary touch remains down. No camera or actor properties are set.
                self.move((0, 0))
                self.capture("tidal-03.png" if mode == "wade" else "tidal-04.png", item)
                self.captured.add(mode)
                # A slow screenshot can consume more than the observation
                # watchdog. Re-read real logs, rather than inventing freshness.
                return self.observe()
        if not self.samples:
            return None
        if time.monotonic() - self.last_observation_time > 10:
            raise RuntimeError("Actual gameplay observations stopped advancing")
        return self.samples[-1]

    def run(self):
        if not ROUTE:
            raise RuntimeError("Authored physical route has not been declared")
        deadline = time.monotonic() + 20
        state = self.observe()
        while state is None and time.monotonic() < deadline:
            self.pause(.1)
            state = self.observe()
        if state is None:
            raise RuntimeError("Game did not produce passive route observations")
        if state["quest_stage"] != 0 or any(state["treasures"]) or state["completed"]:
            raise RuntimeError("Physical route must begin with genuinely fresh progress")
        self.capture("tidal-01.png", state)
        try:
            for point in ROUTE:
                self.current_waypoint = point["name"]
                expected_stage = point.get("stage", self.accepted_stage)
                if expected_stage not in (self.accepted_stage, self.accepted_stage + 1):
                    raise ValueError("Authored route skips a required quest milestone")
                if self.physics_timeout is not None:
                    # Drain passive observations after the preceding screenshot.
                    # Historical startup/preflight frames cannot spend this leg's
                    # physics budget; neither deadline is renewed after this.
                    state = self.observe()
                self.begin_waypoint_budget(point, state)
                while True:
                    self.check_waypoint_budget(state)
                    state = self.observe()
                    if self.physics_timeout is not None:
                        self.check_waypoint_budget(state)
                    if state["quest_stage"] > expected_stage:
                        raise ValueError("Quest advanced beyond the exact current route milestone")
                    approach = point.get("approach", point["target"])
                    if self.milestone_reached(state, point):
                        # Retain shared held keys through ordinary path turns.
                        # Releasing/repressing D within one slow X11 frame lost
                        # the held key in the earlier hosted bay-entry capture.
                        if "stage" in point:
                            self.move((0, 0))
                        if self.physics_timeout is not None:
                            state = self.observe()
                            self.check_waypoint_budget(state)
                        break
                    if self.pending_action is not None:
                        # One real action per milestone. Wait for its actual
                        # acknowledgement; a missing receipt must fail, not
                        # trigger another tap (which could reset completion).
                        self.move((0, 0))
                    elif self.stop_boundary is not None:
                        if self.settled_after_stop(state, point):
                            if not inside_interaction_region(state, point):
                                # Delivery latency/inertia lost actual reach or
                                # availability. Re-approach before the sole action.
                                self.stop_boundary["drifted_sample_id"] = state["sample_id"]
                                self.stop_boundary = None
                                self.move(direction_to(state, approach))
                            else:
                                self.request_action(state, point)
                    elif "stage" in point and inside_interaction_region(state, point):
                        if state["sample_id"] > self.last_action_sample_id:
                            self.stop_for_action(state, point)
                    else:
                        self.move(direction_to(state, approach))
                    if self.physics_timeout is not None:
                        # Count slow input delivery and captures too. An action
                        # callback cannot finish beyond a limit and still pass.
                        state = self.observe()
                        self.check_waypoint_budget(state)
                    self.pause(.1)
                self.update_waypoint_budget(state)["status"] = "completed"
                self.active_budget = None
                self.milestones.append({"name": point["name"], "sample": state})
                if point.get("screenshot"):
                    self.capture(point["screenshot"], state)
            self.move((0, 0))
            self.pause(.4)
            state = self.observe()
            if self.accepted_stage != FINAL_STAGE or self.pending_action is not None or not complete(state):
                raise RuntimeError("Actual physical-input treasure loop was not completed")
            crossing = validate_water_crossing(self.samples)
            self.capture("tidal-05.png", state)
            return {"passed": True, "samples": self.samples, "milestones": self.milestones,
                    "crossing": crossing, "completed_state": state, "physical_actions": self.actions,
                    "physical_stops": self.stops,
                    "budget_policy": self.budget_policy, "waypoint_budgets": self.budgets,
                    "no_demo_no_state_injection": True}
        except Exception as error:
            if self.active_budget is not None:
                budget = self.update_waypoint_budget(self.samples[-1])
                budget["expired_budgets"] = self.expired_waypoint_budgets(budget)
                budget["status"] = "expired" if budget["expired_budgets"] else "failed"
                budget["error"] = str(error)
            raise
        finally:
            self.move((0, 0))
