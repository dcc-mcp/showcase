"""Source-bound chart bypass evidence; no game mutation or synthetic positions."""
import math
from observers import finite_vector, positive_integer

SOURCE_SHA256 = {
    "main.gd": "e598bccc733437acb58a323bb583db8f6f2a5b44ba74281878584906dde55cd8",
    "swim_controller.gd": "bec8a89fb56b854a82d7d0651518f1eef0cc2e5325be74ab42e0e941aa6f73ff",
}
# Exact source: center(1.3,7.8), beveled block(.85,.7,.7), capsule radius .22.
# Every bevel vertex is within the original half-box. Add .15 m clearance.
PHYSICAL = (.655, 1.945, 7.23, 8.37)  # Original half-box plus actual capsule, no extra margin.
FORBIDDEN = (.505, 2.095, 7.08, 8.52)
REGIONS = {"southeast": (2.35, 3.25, 8.7, 9.3), "northeast": (2.35, 3.25, 6.2, 6.8)}


def inside_region(position, bounds):
    x, z = finite_vector(position, 2, "actual corridor XZ")
    return bounds[0] <= x <= bounds[1] and bounds[2] <= z <= bounds[3]


def segment_enters_box(a, b, box=FORBIDDEN):
    a = finite_vector(a, 2, "actual segment start")
    b = finite_vector(b, 2, "actual segment end")
    low, high = 0., 1.
    for axis, bounds in enumerate((box[:2], box[2:])):
        delta = b[axis]-a[axis]
        if abs(delta) < 1e-12:
            if not bounds[0] <= a[axis] <= bounds[1]:
                return False
        else:
            t0, t1 = sorted(((bounds[0]-a[axis])/delta, (bounds[1]-a[axis])/delta))
            low, high = max(low, t0), min(high, t1)
            if low > high:
                return False
    return True  # Touching the extra-clearance boundary is not a clear segment.


def xz(state):
    position = finite_vector(state.get("position"), 3, "actual corridor position")
    return [position[0], position[2]]


class ChartCorridor:
    def __init__(self, entry, sources=None):
        if sources is not None and sources != SOURCE_SHA256:
            raise ValueError("Chart corridor geometry source hashes changed")
        self.native = sources is not None
        self.sources = sources
        self.last = entry
        self.arrivals = []
        self.finished = False
        if entry["quest_stage"] != 1 or xz(entry)[1] <= PHYSICAL[3]:
            raise ValueError("Chart bypass requires actual post-map entry south of physical collider plus capsule")
        self.escaping = xz(entry)[1] <= FORBIDDEN[3]
        self.receipt = {"contract": "chart-safe-corridor-v1", "source_sha256": dict(SOURCE_SHA256),
                        "physical_plinth_capsule_xz": PHYSICAL, "inflated_plinth_xz": FORBIDDEN, "capsule_radius": .22, "extra_clearance": .15,
                        "regions": REGIONS, "entry": {k: entry[k] for k in ("sample_id", "physics_frame", "position")},
                        "scope": "native contiguous actual physics segments from accepted map sample to B exit inside 3m chart observation domain" if self.native else
                                 "browser sparse actual samples from accepted map sample to B exit; not every-physics trajectory proof",
                        "after_B": "ordinary actual functional route and collision/interaction gates; no every-physics corridor claim",
                        "entry_escape": {"required": self.escaping, "direction": "monotonic +Z away from south physical face",
                                         "target": [xz(entry)[0], 9.0], "completed_at_sample": None if self.escaping else entry["sample_id"]},
                        "physics_segments": 0, "samples": 0, "arrivals": self.arrivals}

    def observe(self, state):
        if self.finished:
            return
        number = positive_integer(state.get("sample_id"), "corridor sample")
        frame = positive_integer(state.get("physics_frame"), "corridor physics frame")
        if number <= self.last["sample_id"] or frame <= self.last["physics_frame"]:
            raise ValueError("Corridor samples must be new and ordered")
        if not self.escaping and inside_region(xz(state), FORBIDDEN):
            raise ValueError("Actual player entered inflated chart clearance box")
        if inside_region(xz(state), REGIONS["northeast"]) and not self.arrivals:
            raise ValueError("Actual northeast region preceded southeast arrival")
        if self.native:
            # Existing validator checks exact source binding, frame order/gaps,
            # duplicate/conflicting frames, finite values and final state match.
            from exploration import chart_motion_frames
            frames = chart_motion_frames([state], self.sources, self.last["physics_frame"])
            if not frames or math.dist(frames[0]["before"], self.last["position"]) > .002:
                raise ValueError("Corridor physics is disconnected from preceding actual state")
            for item in frames:
                a, b = item["before"], item["after"]
                self.check_segment([a[0], a[2]], [b[0], b[2]], number)
            self.receipt["physics_segments"] += len(frames)
        else:
            # Sparse browser samples only; not an every-physics trajectory claim.
            self.check_segment(xz(self.last), xz(state), number)
        self.receipt["samples"] += 1
        self.last = state
        if state["quest_stage"] != 1:
            raise ValueError("Unexpected progress before chart bypass B exit")

    def check_segment(self, a, b, sample):
        if self.escaping:
            if b[1] < a[1] or segment_enters_box(a, b, PHYSICAL):
                raise ValueError("Entry escape must be monotonic away from actual physical obstacle")
            if b[1] > FORBIDDEN[3]:
                self.escaping = False
                self.receipt["entry_escape"]["completed_at_sample"] = sample
        elif segment_enters_box(a, b):
            raise ValueError("Actual physics segment crosses chart clearance box")

    def arrive(self, region, state):
        if self.escaping:
            raise ValueError("Bypass arrival cannot precede completed outward entry escape")
        order = ["southeast", "northeast"]
        if len(self.arrivals) >= 2 or region != order[len(self.arrivals)]:
            raise ValueError("Chart bypass region order must be southeast then northeast")
        if state["sample_id"] != self.last["sample_id"] or state["sample_id"] <= self.receipt["entry"]["sample_id"]:
            raise ValueError("Region arrival is not the latest actual sample")
        if self.arrivals and state["sample_id"] <= self.arrivals[-1]["sample_id"]:
            raise ValueError("Region arrival reused a sample")
        if not inside_region(xz(state), REGIONS[region]):
            raise ValueError("Actual sample is outside named bypass region")
        self.arrivals.append({"region": region, "sample_id": state["sample_id"],
                              "physics_frame": state["physics_frame"], "position": state["position"]})
        if region == "northeast":
            if math.dist(xz(state), [1.3, 7.8]) >= 3.0:
                raise ValueError("Chart bypass B exit is outside native observation domain")
            self.finished = True
            self.receipt["finished_at_sample"] = state["sample_id"]
            self.receipt["proof_end"] = "observed northeast B exit, not cache arrival"
