"""Bounded off-route actual-input probes; all game observations are read-only."""
from __future__ import annotations
import math
import time
from gameplay import direction_to, keyboard_direction, validate_state
from observers import finite_vector


def validate_chart_contact(samples, opposite_to=None, required=True):
    """Require an observed stable stop, optionally geometrically opposite a prior one.

    No contact yet may be pending; malformed, injected or penetrating samples
    always fail, even when the live controller requests required=False.
    """
    if opposite_to is not None:
        finite_vector(opposite_to, 2, "opposing radial reference")
        if not .999 <= math.hypot(*opposite_to) <= 1.001:
            raise ValueError("Opposing radial reference must be normalized and nonzero")
    previous = None
    for state in samples:
        validate_state(state, previous, expected_demo=False)
        if state["quest_stage"] != 0:
            raise ValueError("Exploration must not collect or inject quest progress")
        if math.hypot(state["position"][0] - 1.3, state["position"][2] - 7.8) < .46:
            raise ValueError("Actual player penetrated the visible chart pedestal")
        previous = state
    runs, current = [], []
    for state in samples:
        x, _, z = state["position"]
        distance = math.hypot(x-1.3,z-7.8)
        movement = finite_vector(state.get("movement_input"), 2, "movement_input")
        inward = (movement[0]*(1.3-x)+movement[1]*(7.8-z))/distance if distance else 0
        active = .46 <= distance <= .9 and inward > .5
        if current and state["physics_frame"]-current[-1]["physics_frame"] > 30:
            runs.append(current);current=[]
        if active:
            current.append(state)
        elif current:
            runs.append(current);current=[]
    if current:runs.append(current)
    reason = "Pedestal probe did not sustain real inward input"
    for contact in runs[-1:]:
        if contact[-1] is not samples[-1]:
            continue
        if len(contact)<4 or contact[-1]["physics_frame"]-contact[0]["physics_frame"]<60:
            continue
        # Ignore the approach prefix, but require total spread, not just matching
        # endpoints: sliding away and returning is not a stable physical stop.
        cutoff=contact[-1]["physics_frame"]-60
        start=max(i for i,item in enumerate(contact) if item["physics_frame"]<=cutoff)
        contact=contact[start:]
        if len(contact)<4 or max(math.dist(a["position"],b["position"]) for a in contact for b in contact) > .20:
            reason = "Pedestal contact was not a stable physical stop"
            continue
        radial=[]
        for state in contact:
            x,z=state["position"][0]-1.3,state["position"][2]-7.8
            length=math.hypot(x,z)
            radial.append([x/length,z/length])
        dots = [sum(a*b for a,b in zip(axis,opposite_to)) for axis in radial] if opposite_to is not None else []
        if dots and max(dots)>-.8:
            reason = "Second pedestal contact was not continuously opposite the first"
            continue
        mean=[sum(axis[i] for axis in radial)/len(radial) for i in range(2)]
        length=math.hypot(*mean)
        reference=[v/length for v in mean]
        return {"contact_samples":len(contact),"radial_reference":reference,
                "contact_physics_frames":contact[-1]["physics_frame"]-contact[0]["physics_frame"],
                "maximum_opposition_dot":max(dots) if dots else None,
                "minimum_center_distance":min(math.hypot(s["position"][0]-1.3,s["position"][2]-7.8) for s in samples)}
    if required:
        raise ValueError(reason)
    return None


def chart_approach_ray(state, outward):
    """Choose an actual eight-way key ray using the observed camera basis."""
    validate_state(state, expected_demo=False)
    outward = finite_vector(outward, 2, "requested chart approach")
    length = math.hypot(*outward)
    if length <= 1e-9:
        raise ValueError("Chart approach needs a nonzero outward direction")
    requested = [axis / length for axis in outward]
    right, forward = state["camera_right"], state["camera_forward"]
    candidates = []
    for x, y in ((-1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1), (-1, 1), (1, -1)):
        world = [right[i] * x - forward[i] * y for i in range(2)]
        world_length = math.hypot(*world)
        radial = [-axis / world_length for axis in world]
        candidates.append((sum(a*b for a, b in zip(radial, requested)), (x, y), radial))
    _, direction, radial = max(candidates, key=lambda candidate: candidate[0])
    return {"direction": list(direction), "keys": sorted(keyboard_direction(direction)),
            "outward": radial, "target": [1.3 + radial[0]*1.8, 7.8 + radial[1]*1.8]}


def hold_chart_contact(read_states, move, pause, ray, opposite_to=None, timeout=35, evidence=None):
    """Hold one physical key combination; never chase the center along a bevel."""
    evidence = {} if evidence is None else evidence
    initial = read_states()[-1]
    validate_state(initial, expected_demo=False)
    boundary = initial["sample_id"]
    deadline = time.monotonic() + timeout
    evidence.update({"ray": ray, "after_sample_id": boundary, "observations": []})
    try:
        move(tuple(ray["direction"]))
        while time.monotonic() < deadline:
            states = read_states()
            selected = [state for state in states if state["sample_id"] > boundary]
            evidence["observations"] = selected
            if selected:
                validate_state(selected[0], initial, expected_demo=False)
            # Validate malformed, penetrating or injected observations even when
            # a contact is still pending. The original contact gates are unchanged.
            receipt = validate_chart_contact(selected, opposite_to, required=False)
            if time.monotonic() >= deadline:
                break
            contact = []
            stopped_once = False
            for state in selected:
                x, _, z = state["position"]
                radial = [x-1.3, z-7.8]
                distance = math.hypot(*radial)
                if distance > .9:
                    contact = []
                    stopped_once = False
                    continue
                radial = [axis/distance for axis in radial]
                if (sum(a*b for a, b in zip(radial, ray["outward"])) < .8
                        or (opposite_to is not None and sum(a*b for a, b in zip(radial, opposite_to)) > -.8)):
                    evidence["result"] = "held contact left the intended opposite sector"
                    return None
                inward = -sum(a*b for a, b in zip(state["movement_input"], radial))
                if inward <= .5 or (contact and state["physics_frame"]-contact[-1]["physics_frame"] > 30):
                    contact = []
                    stopped_once = False
                if inward > .5:
                    # Do not mistake the approach prefix for a failed stable
                    # stop. Only an observed stop followed by renewed sliding
                    # ends an attempt early; acceptance still uses the original
                    # complete contact validator above.
                    stopped_once |= math.hypot(state["velocity"][0], state["velocity"][2]) <= .08
                    if stopped_once:
                        contact.append(state)
            if contact and contact[-1]["physics_frame"]-contact[0]["physics_frame"] >= 60:
                cutoff = contact[-1]["physics_frame"]-60
                start = max(i for i, state in enumerate(contact) if state["physics_frame"] <= cutoff)
                trailing = contact[start:]
                if max(math.dist(a["position"], b["position"]) for a in trailing for b in trailing) > .20:
                    evidence["result"] = "held contact slid instead of stopping"
                    return None
            if receipt is not None:
                evidence["result"] = "accepted held contact"
                receipt["observations"] = selected
                receipt["held_ray"] = ray
                return receipt
            pause(.05)
        evidence["result"] = "contact timeout"
        return None
    finally:
        move((0, 0))


def run_chart_exploration(read_states, move, pause, snapshot, timeout=35, evidence=None):
    """Walk around geometrically opposing contacts; no interact calls."""
    samples, receipts, path = [], [], []
    evidence = {} if evidence is None else evidence
    evidence.update({"schema":2,"passed":False,"route":"actual X11 keyboard off-route chart encirclement and opposing contact probes; no interaction or state setters",
                     "contacts":receipts,"waypoints":path,"samples":samples})
    last_advance = time.monotonic()

    def observe():
        nonlocal last_advance
        previous = samples[-1] if samples else None
        for state in read_states():
            if previous and state.get("sample_id",0) <= previous["sample_id"]:
                continue
            validate_state(state, previous, expected_demo=False)
            if state["quest_stage"] != 0:
                raise ValueError("Off-route chart probe requires genuinely fresh progress")
            if math.hypot(state["position"][0]-1.3,state["position"][2]-7.8)<.46:
                raise ValueError("Off-route navigation penetrated the visible chart pedestal")
            samples.append(state); previous = state; last_advance = time.monotonic()
        if not samples or time.monotonic() - last_advance > 10:
            raise RuntimeError("Off-route gameplay observations unavailable or stale")
        return samples[-1]

    def settle():
        move((0,0))
        boundary=observe()
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            state=observe()
            if (state["sample_id"]>boundary["sample_id"] and state["physics_frame"]>boundary["physics_frame"]
                and math.hypot(*state["movement_input"])<=.01
                and math.hypot(state["velocity"][0],state["velocity"][2])<=.08):
                return state
            pause(.05)
        raise TimeoutError("Off-route stop did not produce newer neutral settled physics")

    def navigate(target,radius=.45):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            state=observe()
            if math.hypot(state["position"][0]-target[0],state["position"][2]-target[1]) < radius:
                state=settle()
                if math.hypot(state["position"][0]-target[0],state["position"][2]-target[1]) < radius:
                    path.append({"target":target,"actual":state});return
                # Real release latency may drift beyond the arrival disk. Continue
                # physically approaching inside the same bounded waypoint budget.
                continue
            move(direction_to(state,target));pause(.05)
        raise TimeoutError("Off-route physical waypoint not reached: "+str(target))

    def push(ray, opposite_to=None):
        def current_samples():
            observe()
            return samples
        attempt = {}
        receipt = hold_chart_contact(current_samples, move, pause, ray, opposite_to, timeout, attempt)
        settled = settle()
        if receipt is not None:
            receipt["settled_after_release"] = settled
            return receipt
        evidence.setdefault("opposing_attempts", []).append(attempt)
        if opposite_to is None:
            raise TimeoutError("Actual first chart collision contact never stabilized: " + attempt["result"])
        return None

    def radial_angle(state):
        return math.atan2(state["position"][2]-7.8,state["position"][0]-1.3)

    def orbit_to(target_angle, final_radius=.45):
        # Move out first, then around the pedestal in <=45-degree chords. Never
        # ask the player to cross the solid center to obtain the opposite probe.
        angle=radial_angle(observe())
        navigate([1.3+math.cos(angle)*1.8,7.8+math.sin(angle)*1.8],.45)
        angle=radial_angle(observe())
        delta=(target_angle-angle+math.pi)%(2*math.pi)-math.pi
        steps=math.ceil(abs(delta)/(math.pi/4))
        for i in range(1,steps+1):
            a=angle+delta*i/steps
            navigate([1.3+math.cos(a)*1.8,7.8+math.sin(a)*1.8],final_radius if i==steps else .45)
        if steps==0:
            navigate([1.3+math.cos(target_angle)*1.8,7.8+math.sin(target_angle)*1.8],final_radius)

    try:
        navigate([2.8,9.2])
        # Approach the southeast corner along a realizable keyboard diagonal,
        # rather than chase the center from the east and slide around its bevel.
        first_ray=chart_approach_ray(observe(),[1,1])
        navigate(first_ray["target"],.25)
        first=push(first_ray);first["name"]="first";receipts.append(first)
        snapshot("native-chart-blocker-first.png")
        reference=list(first["radial_reference"])
        opposite_angle=math.atan2(reference[1],reference[0])+math.pi
        for adjustment in (0,math.radians(20),math.radians(-20)):
            angle=opposite_angle+adjustment
            ray=chart_approach_ray(observe(),[math.cos(angle),math.sin(angle)])
            orbit_to(math.atan2(ray["outward"][1],ray["outward"][0]),.25)
            second=push(ray,reference)
            if second is not None:
                second["name"]="opposed";receipts.append(second)
                snapshot("native-chart-blocker-opposed.png")
                break
        else:
            raise TimeoutError("No continuously opposite chart contact after three physical approaches")
        orbit_to(math.pi/2)
        navigate([1.3,10.0])
        settle()
        evidence["passed"]=True
        return evidence
    except Exception as error:
        evidence["blocker"]=str(error)
        raise
    finally:
        move((0,0))
