"""Bounded off-route actual-input probes; all game observations are read-only."""
from __future__ import annotations
import math
import time
from gameplay import direction_to, validate_state
from observers import finite_vector


def validate_chart_contact(samples, side):
    if side not in (-1, 1) or len(samples) < 4:
        raise ValueError("Chart probe needs a declared side and advancing observations")
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
        active = .46 <= distance <= .9 and (x-1.3)*side > .35 and inward > .5
        if current and state["physics_frame"]-current[-1]["physics_frame"] > 30:
            runs.append(current);current=[]
        if active:
            current.append(state)
        elif current:
            runs.append(current);current=[]
    if current:runs.append(current)
    contact = max(runs,key=lambda run:run[-1]["physics_frame"]-run[0]["physics_frame"],default=[])
    if len(contact)<4 or contact[-1]["physics_frame"]-contact[0]["physics_frame"]<60:
        raise ValueError("Pedestal probe did not sustain real inward input against the expected side")
    if math.dist(contact[0]["position"], contact[-1]["position"]) > .20:
        raise ValueError("Pedestal contact was not a stable physical stop")
    return {"side": "east" if side == 1 else "west", "contact_samples": len(contact),
            "contact_physics_frames": contact[-1]["physics_frame"] - contact[0]["physics_frame"],
            "minimum_center_distance": min(math.hypot(s["position"][0]-1.3,s["position"][2]-7.8) for s in samples)}


def run_chart_exploration(read_states, move, pause, snapshot, timeout=35, evidence=None):
    """Walk around both sides and push into the pedestal; no interact calls."""
    samples, receipts, path = [], [], []
    evidence = {} if evidence is None else evidence
    evidence.update({"schema":1,"passed":False,"route":"actual X11 keyboard off-route chart encirclement and opposing contact probes; no interaction or state setters",
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
            samples.append(state); previous = state; last_advance = time.monotonic()
        if not samples or time.monotonic() - last_advance > 10:
            raise RuntimeError("Off-route gameplay observations unavailable or stale")
        return samples[-1]

    def navigate(target):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            state=observe()
            if math.hypot(state["position"][0]-target[0],state["position"][2]-target[1]) < .45:
                move((0,0));path.append({"target":target,"actual":state});return
            move(direction_to(state,target));pause(.05)
        raise TimeoutError("Off-route physical waypoint not reached: "+str(target))

    def push(side):
        start=observe(); boundary=start["sample_id"]; deadline=time.monotonic()+timeout
        contact_start=None
        while time.monotonic()<deadline:
            state=observe()
            distance=math.hypot(state["position"][0]-1.3,state["position"][2]-7.8)
            if distance < .46:
                raise ValueError("Actual input entered the visible chart pedestal")
            if .46<=distance<=.9 and (state["position"][0]-1.3)*side>.35:
                if contact_start is None:contact_start=state["physics_frame"]
                if state["physics_frame"]-contact_start>=120:
                    move((0,0))
                    selected=[s for s in samples if s["sample_id"]>boundary]
                    receipt=validate_chart_contact(selected,side)
                    receipt["observations"]=selected;receipts.append(receipt)
                    snapshot("native-chart-blocker-"+("east" if side==1 else "west")+".png")
                    return
            else:contact_start=None
            move(direction_to(state,[1.3,7.8]));pause(.05)
        raise TimeoutError("Actual chart collision contact never stabilized")

    try:
        for target in ([2.8,9.2],[2.8,7.8]):navigate(target)
        push(1)
        for target in ([2.8,7.8],[2.8,6.4],[-.2,6.4],[-.2,7.8]):navigate(target)
        push(-1)
        for target in ([-.2,7.8],[-.2,9.5],[1.3,10.0]):navigate(target)
        move((0,0))
        evidence["passed"]=True
        return evidence
    except Exception as error:
        evidence["blocker"]=str(error)
        raise
    finally:
        move((0,0))
