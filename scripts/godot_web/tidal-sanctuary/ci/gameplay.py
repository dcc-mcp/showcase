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
    {"name": "return both treasures to the ring", "target": [0.0, -11.7], "stage": 4},
]
FINAL_STAGE = 4
STATE_PREFIX = "TIDAL_STATE"
INTERACTION_RADIUS = 1.55


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
    def __init__(self, read_states, move, interact, pause, snapshot, timeout=75):
        self.read_states, self.move, self.interact = read_states, move, interact
        self.pause, self.snapshot, self.timeout = pause, snapshot, timeout
        self.samples, self.milestones, self.captured = [], [], set()
        self.last_action = 0
        self.last_action_sample_id = 0
        self.last_observation_time = time.monotonic()
        self.pending_action = None
        self.actions = []
        self.accepted_stage = 0
        self.capture_seconds = 0.0

    def capture(self, name, state):
        started = time.monotonic()
        self.snapshot(name, state)
        self.capture_seconds += time.monotonic() - started

    def milestone_reached(self, state, point):
        if "stage" not in point:
            return math.hypot(state["position"][0] - point["target"][0],
                              state["position"][2] - point["target"][1]) <= point.get("radius", .8)
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

    def request_action(self, state, point):
        """Record the physical callback request, never grant progress by itself."""
        validate_progress(state)
        target_stage = point.get("stage")
        if target_stage != self.accepted_stage + 1 or state["quest_stage"] != self.accepted_stage:
            raise ValueError("Physical action does not match the next exact quest milestone")
        distance = math.hypot(state["position"][0] - point["target"][0], state["position"][2] - point["target"][1])
        if distance > point.get("radius", .8):
            raise ValueError("Physical action was requested away from its authored waypoint")
        action = {"from_stage": self.accepted_stage, "target_stage": target_stage,
                  "after_sample_id": state["sample_id"], "after_physics_frame": state["physics_frame"],
                  "target": list(point["target"]), "position": list(state["position"]),
                  "waypoint": point["name"], "requested_at": time.monotonic(), "callback_returned": False}
        self.actions.append(action)
        self.pending_action = action
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
                expected_stage = point.get("stage", self.accepted_stage)
                if expected_stage not in (self.accepted_stage, self.accepted_stage + 1):
                    raise ValueError("Authored route skips a required quest milestone")
                deadline = time.monotonic() + self.timeout
                captures_before = self.capture_seconds
                reached = False
                while time.monotonic() - (self.capture_seconds - captures_before) < deadline:
                    state = self.observe()
                    if state["quest_stage"] > expected_stage:
                        raise ValueError("Quest advanced beyond the exact current route milestone")
                    target = point["target"]
                    distance = math.hypot(state["position"][0] - target[0], state["position"][2] - target[1])
                    if self.milestone_reached(state, point):
                        # Retain shared held keys through ordinary path turns.
                        # Releasing/repressing D within one slow X11 frame lost
                        # the held key in the earlier hosted bay-entry capture.
                        if "stage" in point:
                            self.move((0, 0))
                        reached = True
                        break
                    if self.pending_action is not None:
                        # One real action per milestone. Wait for its actual
                        # acknowledgement; a missing receipt must fail, not
                        # trigger another tap (which could reset completion).
                        self.move((0, 0))
                    elif distance <= point.get("radius", .8):
                        self.move((0, 0))
                        if state["sample_id"] > self.last_action_sample_id:
                            self.request_action(state, point)
                    else:
                        self.move(direction_to(state, target))
                    self.pause(.1)
                if not reached:
                    raise RuntimeError("Physical route could not reach/complete " + point["name"] + ": " + str(state))
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
                    "no_demo_no_state_injection": True}
        finally:
            self.move((0, 0))
