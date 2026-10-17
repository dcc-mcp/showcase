"""Bounded off-route actual-input probes; all game observations are read-only."""
from __future__ import annotations
import math
import time
from gameplay import direction_to, validate_state
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

    def push(opposite_to=None):
        boundary=observe()["sample_id"];deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            state=observe()
            selected=[s for s in samples if s["sample_id"]>boundary]
            receipt=validate_chart_contact(selected,opposite_to,required=False)
            if receipt is not None:
                # Freeze the reference from actual inward contact, before release.
                receipt["observations"]=selected
                receipt["settled_after_release"]=settle()
                return receipt
            if opposite_to is not None and validate_chart_contact(selected,required=False) is not None:
                evidence.setdefault("opposing_attempts",[]).append({"result":"stable but outside opposite sector","observations":selected})
                settle();return None
            move(direction_to(state,[1.3,7.8]));pause(.05)
        evidence.setdefault("opposing_attempts",[]).append({"result":"contact timeout","opposite_to":opposite_to})
        settle()
        if opposite_to is None:
            raise TimeoutError("Actual first chart collision contact never stabilized")
        return None

    def radial_angle(state):
        return math.atan2(state["position"][2]-7.8,state["position"][0]-1.3)

    def orbit_to(target_angle):
        # Move out first, then around the pedestal in <=45-degree chords. Never
        # ask the player to cross the solid center to obtain the opposite probe.
        angle=radial_angle(observe())
        navigate([1.3+math.cos(angle)*1.8,7.8+math.sin(angle)*1.8],.45)
        angle=radial_angle(observe())
        delta=(target_angle-angle+math.pi)%(2*math.pi)-math.pi
        steps=math.ceil(abs(delta)/(math.pi/4))
        for i in range(1,steps+1):
            a=angle+delta*i/steps
            navigate([1.3+math.cos(a)*1.8,7.8+math.sin(a)*1.8],.45)

    try:
        for target in ([2.8,9.2],[2.8,7.8]):navigate(target)
        first=push();first["name"]="first";receipts.append(first)
        snapshot("native-chart-blocker-first.png")
        reference=list(first["radial_reference"])
        opposite_angle=math.atan2(reference[1],reference[0])+math.pi
        for adjustment in (0,math.radians(20),math.radians(-20)):
            orbit_to(opposite_angle+adjustment)
            second=push(reference)
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
