"""Bounded off-route actual-input probes; all game observations are read-only."""
from __future__ import annotations
import math
import time
from gameplay import direction_to, keyboard_direction, validate_state
from observers import finite_vector, positive_integer


CHART_CONTRACT = "chart-blocked-normal-v2"
CHART_SOURCE_FILES = ("main.gd", "swim_controller.gd")
CHART_CONTACT_STEPS = 12
CHART_STAGING_BAND = .06
# Godot 4.6.3 grounded movement: six simultaneous contacts per slide result,
# six configured/default max_slides, plus one possible platform-motion result.
# Source: scene/3d/physics/character_body_3d.cpp (_move_and_slide_grounded).
CHART_MAX_COLLISIONS = 6*6 + 1
CHART_REASON = "Chart pedestal is solid; chart is query-only"


def chart_motion_frames(samples, expected_sources, after_frame):
    """Read source-bound, contiguous actual move_and_slide receipts, not positions inferred from a timer."""
    if (not isinstance(expected_sources, dict) or set(expected_sources) != set(CHART_SOURCE_FILES)
            or any(not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
                   for v in expected_sources.values())):
        raise ValueError("Chart motion requires exact independently hashed source bindings")
    if type(after_frame) is not int or after_frame < 0:
        raise ValueError("Chart motion boundary must be an actual nonnegative physics frame")
    frames = {}
    for state in samples:
        envelope = state.get("chart_motion")
        if (not isinstance(envelope, dict) or type(envelope.get("schema")) is not int or envelope["schema"] != 2
                or envelope.get("contract") != CHART_CONTRACT or envelope.get("source_sha256") != expected_sources):
            raise ValueError("Missing or mismatched source-bound chart physics receipt")
        recorded = envelope.get("frames")
        if not isinstance(recorded, list) or not 1 <= len(recorded) <= 32:
            raise ValueError("Chart motion buffer is missing or unbounded")
        last = None
        for frame in recorded:
            if not isinstance(frame, dict):
                raise ValueError("Actual chart physics step must be an object")
            number = positive_integer(frame.get("physics_frame"), "chart physics_frame")
            if last is not None and number != last + 1:
                raise ValueError("Chart motion buffer has stale or missing physics steps")
            last = number
            if number > state["physics_frame"]:
                raise ValueError("Chart receipt is ahead of its observed physics state")
            if number <= after_frame:
                continue
            if number in frames and frames[number] != frame:
                raise ValueError("Chart physics step was reused with conflicting observations")
            frames[number] = frame
        if last != state["physics_frame"]:
            raise ValueError("Chart motion receipt is stale relative to actual state")
        final = recorded[-1]
        for frame_field, state_field in (("after", "position"), ("velocity", "velocity"), ("movement_input", "movement_input")):
            size = 2 if frame_field == "movement_input" else 3
            value = finite_vector(final.get(frame_field), size, frame_field)
            if math.dist(value, state[state_field]) > .002:
                raise ValueError("Chart physics receipt does not match its independently observed state")
    result = [frames[key] for key in sorted(frames)]
    previous = None
    for frame in result:
        number = frame["physics_frame"]
        if number != (previous["physics_frame"] + 1 if previous else after_frame + 1):
            raise ValueError("Chart approach is missing actual physics steps")
        delta = frame.get("delta")
        if type(delta) not in (int, float) or not math.isfinite(delta) or abs(delta - 1/60) > .00001:
            raise ValueError("Chart motion must use actual fixed 60 Hz physics deltas")
        for field in ("before", "after", "requested_velocity", "velocity"):
            finite_vector(frame.get(field), 3, field)
        finite_vector(frame.get("movement_input"), 2, "actual chart movement_input")
        if previous and math.dist(previous["after"], frame["before"]) > .002:
            raise ValueError("Chart actual physics positions are discontinuous")
        if math.dist(frame["before"], frame["after"]) > 8*delta + .02:
            raise ValueError("Chart physics contains an impossible position jump")
        if type(frame.get("max_slides")) is not int or frame["max_slides"] != 6:
            raise ValueError("Chart body max_slides differs from the source-bound configuration")
        collisions = frame.get("collisions")
        if not isinstance(collisions, list) or len(collisions) > CHART_MAX_COLLISIONS:
            raise ValueError("Actual chart collision list is missing or invalid")
        for hit in collisions:
            if not isinstance(hit, dict):
                raise ValueError("Actual chart collision must be an object")
            normal = finite_vector(hit.get("normal"), 3, "actual collision normal")
            finite_vector(hit.get("point"), 3, "actual collision point")
            if not .99 <= math.sqrt(sum(v*v for v in normal)) <= 1.01:
                raise ValueError("Actual collision normal is not normalized")
        previous = frame
    return result


def validate_chart_contact(samples, opposite_to=None, required=True, *, expected_sources=None,
                           after_frame=0, face=1, opposite_normal=None):
    """Prove a real collider blocks inward motion for twelve consecutive steps.

    Tangential sliding is legitimate. Each step must attempt inward motion,
    contact the authored flat face, and lose its inward normal velocity while
    the capsule stays outside. A continuous real approach and source-bound
    KinematicCollision3D receipts exclude idle, missing-collider and stale wins.
    """
    if type(face) is not int or face not in (-1, 1):
        raise ValueError("Chart face must be north or south")
    if opposite_to is not None:
        finite_vector(opposite_to, 2, "opposing radial reference")
        if not .999 <= math.hypot(*opposite_to) <= 1.001:
            raise ValueError("Opposing radial reference must be normalized and nonzero")
        finite_vector(opposite_normal, 3, "actual opposing contact normal")
        if not .999 <= math.sqrt(sum(v*v for v in opposite_normal)) <= 1.001:
            raise ValueError("Actual opposing contact normal must be normalized")
    previous = None
    for state in samples:
        validate_state(state, previous, expected_demo=False)
        if state["quest_stage"] != 0:
            raise ValueError("Exploration must not collect or inject quest progress")
        if math.hypot(state["position"][0]-1.3, state["position"][2]-7.8) < .46:
            raise ValueError("Actual player penetrated the visible chart pedestal")
        previous = state
    if not samples:
        if required:raise ValueError("No actual chart approach observations")
        return None
    frames = chart_motion_frames(samples, expected_sources, after_frame)
    run, candidates = [], []
    approach = 0.
    for frame in frames:
        before, after = frame["before"], frame["after"]
        # Flat Z face is .35 m from center; the production capsule radius is .22.
        # A 5 mm numerical contact tolerance excludes substantive capsule penetration.
        if min(face*(p[2]-7.8) for p in (before, after)) < .565:
            raise ValueError("Actual capsule penetrated or crossed the tested chart face")
        inward = -face*frame["movement_input"][1]
        actual_inward = face*(before[2]-after[2])
        hit = next((hit for hit in frame["collisions"]
            if hit.get("class") == "StaticBody3D" and type(hit.get("interaction_target")) is int
            and hit["interaction_target"] == 0 and hit.get("intent") == "solid"
            and hit.get("reason") == CHART_REASON and isinstance(hit.get("body"), str)
            and hit["body"].startswith("/root/") and "/Solid_" in hit["body"]
            and face*hit["normal"][2] >= .999 and abs(hit["normal"][0]) <= .02 and abs(hit["normal"][1]) <= .02
            and abs(hit["point"][2]-(7.8+face*.35)) <= .015
            and abs(hit["point"][0]-1.3) <= .425), None)
        normal = hit["normal"] if hit else [0, 0, face]
        attempted = -sum(v*n for v,n in zip(frame["requested_velocity"], normal))
        normal_speed = abs(sum(v*n for v,n in zip(frame["velocity"], normal)))
        normal_travel = sum((a-b)*n for a,b,n in zip(before, after, normal))
        if hit is None and inward > .5 and face*(before[2]-7.8) > .65:
            approach += max(0., actual_inward)
        blocked = max(0., attempted*frame["delta"]-normal_travel)
        active = (hit is not None and inward > .5 and attempted > .1 and normal_speed <= .08
                  and abs(normal_travel) <= .003 and approach >= .15)
        radial = [after[0]-1.3, after[2]-7.8]
        distance = math.hypot(*radial)
        radial = [v/distance for v in radial]
        dot = sum(a*b for a,b in zip(radial, opposite_to)) if opposite_to is not None else None
        normal_dot = sum(a*b for a,b in zip(hit["normal"], opposite_normal)) if hit and opposite_normal is not None else None
        if active and opposite_to is not None and (dot > -.8 or normal_dot > -.95):
            active = False
        if active and run and hit["body"] != run[-1]["collision"]["body"]:
            active = False
        if not active:
            run = []
            continue
        run.append({"frame":frame, "collision":hit, "blocked":blocked, "radial":radial, "normal_speed":normal_speed,
                    "opposition_dot":dot, "normal_opposition_dot":normal_dot})
        if len(run) >= CHART_CONTACT_STEPS:
            window = run[-CHART_CONTACT_STEPS:]
            if sum(item["blocked"] for item in window) >= .05:
                candidates.append(window)
    # A buffered window may end between 13-tick state emissions. It must be
    # newly completed in the latest emission, with input still held afterward.
    for contact in reversed(candidates):
        last_frame = contact[-1]["frame"]["physics_frame"]
        if frames[-1]["physics_frame"]-last_frame > 12:
            continue
        tail = [frame for frame in frames if frame["physics_frame"] >= last_frame]
        if any(-face*frame["movement_input"][1] <= .5 for frame in tail):
            continue
        mean = [sum(item["radial"][i] for item in contact)/len(contact) for i in range(2)]
        length = math.hypot(*mean)
        return {"contract":CHART_CONTRACT, "source_sha256":dict(expected_sources),
                "contact_steps":len(contact), "contact_physics_frames":len(contact),
                "first_physics_frame":contact[0]["frame"]["physics_frame"], "last_physics_frame":last_frame,
                "face":face, "actual_normal":contact[-1]["collision"]["normal"],
                "body":contact[-1]["collision"]["body"], "radial_reference":[v/length for v in mean],
                "blocked_inward_distance":sum(item["blocked"] for item in contact),
                "actual_approach_distance":approach,
                "maximum_normal_speed":max(item["normal_speed"] for item in contact),
                "maximum_opposition_dot":max(item["opposition_dot"] for item in contact) if opposite_to is not None else None,
                "maximum_normal_opposition_dot":max(item["normal_opposition_dot"] for item in contact) if opposite_to is not None else None,
                "minimum_face_clearance":min(face*(frame["after"][2]-7.8)-.35 for frame in frames),
                "physics_steps":[item["frame"] for item in contact]}
    if required:
        raise ValueError("No twelve consecutive real chart contacts blocked inward normal motion on the opposing face")
    return None


def validate_chart_physics_controls(receipt, expected_sources):
    """Apply the same gate to actual engine fixtures, including removed colliders.

    The fixture scope stays explicit. Passing this never substitutes for the
    separate native XTest keyboard route.
    """
    controls = [item for item in receipt.get("checks", []) if item.get("check") == "actual_controller_chart_normal_contact"]
    wanted = {(face, mode, offset) for face in (-1, 1) for mode in ("solid", "collider_removed", "idle")
              for offset in ((0.,) if mode == "idle" else (-CHART_STAGING_BAND, 0., CHART_STAGING_BAND))}
    if len(controls) != len(wanted) or {(item.get("face"), item.get("mode"), item.get("lane_offset")) for item in controls} != wanted:
        raise ValueError("Missing actual chart collider-removal or idle negative controls")
    results, positives = [], {}
    for item in controls:
        face, mode = item["face"], item["mode"]
        states = item.get("samples", [])
        if not states:
            raise ValueError("Actual chart physics control has no observations")
        previous = None
        for state in states:
            validate_state(state, previous, expected_demo=False)
            if state["quest_stage"] != 0:
                raise ValueError("Chart control injected progress")
            previous = state
        frames = chart_motion_frames(states, expected_sources, item["after_physics_frame"])
        if mode == "collider_removed":
            if any(hit.get("interaction_target") == 0 for frame in frames for hit in frame["collisions"]):
                raise ValueError("Removed-collider negative still observed the chart collider")
            if min(face*(frame["after"][2]-7.8) for frame in frames) >= .35:
                raise ValueError("Removed-collider control did not actually cross the former face")
            if any(-face*frame["movement_input"][1] <= .5 for frame in frames):
                raise ValueError("Removed-collider control did not hold actual inward input")
        if mode == "idle" and (any(math.hypot(*frame["movement_input"]) > .01 for frame in frames)
                or math.dist(frames[0]["before"], frames[-1]["after"]) > .08):
            raise ValueError("Idle negative control was not actually stationary")
        try:
            result = validate_chart_contact(states, expected_sources=expected_sources,
                after_frame=item["after_physics_frame"], face=face)
        except ValueError as error:
            if mode == "solid":raise
            results.append({"case":item["case"], "rejected":True, "reason":str(error)})
        else:
            if mode != "solid":
                raise ValueError("Actual negative chart physics control incorrectly passed")
            if item["lane_offset"] == 0:positives[face] = (item, result)
            results.append({"case":item["case"], "accepted":True, "contact":result})
    first = positives[1][1]
    second = positives[-1][0]
    validate_chart_contact(second["samples"], first["radial_reference"], expected_sources=expected_sources,
        after_frame=second["after_physics_frame"], face=-1, opposite_normal=first["actual_normal"])
    return {"contract":CHART_CONTRACT, "scope":"actual physics fixtures, not physical-input proof", "controls":results}


def chart_ray_geometry(state, direction):
    """Stage W/S to cross the actual flat north/south face with tangent room."""
    validate_state(state, expected_demo=False)
    direction = finite_vector(list(direction), 2, "chart physical key direction")
    if direction not in ([0, -1], [0, 1]):
        raise ValueError("Chart flat-face approach needs physical W or S")
    forward = state["camera_forward"]
    world = [-v*direction[1] for v in forward]
    length = math.hypot(*world)
    radial = [-axis/length for axis in world]
    face = 1 if radial[1] > 0 else -1
    if abs(radial[1]) < .9:
        raise ValueError("Camera cannot physically approach the intended chart flat face")
    # The largest authored cut is .35*.4*1.8=.252 m, leaving at least .173 m
    # either side of this flat face. Enter 11 cm before center, with a 6 cm
    # cross-track band, to reserve the ensuing ~.19 m tangential travel. Actual
    # physics fixtures test both band endpoints; this target is never proof.
    lane = -.11 if world[0] > 0 else .11
    support = [lane, face*.57]
    cross = support[0]*radial[1]-support[1]*radial[0]
    return {"direction":list(direction), "keys":sorted(keyboard_direction(direction)),
            "face":face, "outward":radial, "cross_track":cross,
            "face_aim":[1.3+support[0],7.8+support[1]],
            "target":[1.3+radial[0]*1.8+radial[1]*cross,
                      7.8+radial[1]*1.8-radial[0]*cross]}


def chart_approach_ray(state, outward):
    outward = finite_vector(outward, 2, "requested chart approach")
    if abs(outward[1]) < abs(outward[0]) or outward[1] == 0:
        raise ValueError("Chart probe requires genuinely opposing north/south flat faces")
    return chart_ray_geometry(state, [0, -1 if outward[1] > 0 else 1])


def settle_chart_movement(observe, move, pause, deadline=None):
    move((0, 0))
    # Keep the boundary after the actual keyup/neutral adapter barrier.
    boundary = observe()
    limit = time.monotonic()+10
    if deadline is not None:
        limit = min(limit, deadline)
    while time.monotonic() < limit:
        state = observe()
        if time.monotonic() >= limit:
            break
        if (state["sample_id"] > boundary["sample_id"] and state["physics_frame"] > boundary["physics_frame"]
                and math.hypot(*state["movement_input"]) <= .01
                and math.hypot(state["velocity"][0], state["velocity"][2]) <= .08):
            return state
        pause(.05)
    raise TimeoutError("Off-route stop did not produce newer neutral settled physics")


def navigate_chart_waypoint(observe, move, pause, target, radius=.45, timeout=35,
                            ray=None, braking=None, evidence=None):
    """Brake real keyboard motion before overshoot; accept only a fresh stop.

    Final contact staging needs alignment across the flat-face held ray,
    not an exact longitudinal point. Its controller-only band stays well outside
    contact; validate_chart_contact remains the sole contact acceptance gate.
    Steering ends at timeout; an in-progress key release and brake may finish
    within ten further seconds (45 seconds total with the default timeout).
    """
    braking = {"seconds": .12} if braking is None else braking
    evidence = {} if evidence is None else evidence
    evidence.update({"target": target, "ray": ray, "brakes": []})
    deadline = time.monotonic()+timeout

    def coordinates(position):
        radial = [position[0]-1.3, position[1]-7.8]
        outward = ray["outward"]
        return (sum(a*b for a, b in zip(radial, outward)),
                radial[0]*outward[1]-radial[1]*outward[0]-ray["cross_track"])

    def arrived(position):
        if ray is None:
            return math.dist(position, target) < radius
        along, across = coordinates(position)
        return 1.2 <= along <= 2.4 and abs(across) <= CHART_STAGING_BAND

    last_decided_sample = None
    try:
        while time.monotonic() < deadline:
            state = observe()
            if state["sample_id"] == last_decided_sample:
                pause(.05)
                continue
            last_decided_sample = state["sample_id"]
            position = [state["position"][0], state["position"][2]]
            velocity = [state["velocity"][0], state["velocity"][2]]
            speed = math.hypot(*velocity)
            predicted = [p+v*braking["seconds"] for p, v in zip(position, velocity)]
            crosses_ray = False
            if ray is not None:
                along, across = coordinates(position)
                stop_along, stop_across = coordinates(predicted)
                crosses_ray = 1.2 <= stop_along <= 2.4 and across*stop_across < 0
            if arrived(position) or (speed > .08 and (arrived(predicted) or crosses_ray)):
                decision = {"observed": state, "predicted_stop": predicted,
                            "coast_seconds": braking["seconds"]}
                evidence["brakes"].append(decision)
                stopped = settle_chart_movement(observe, move, pause, deadline+10)
                decision["settled"] = stopped
                actual = [stopped["position"][0], stopped["position"][2]]
                if ray is not None:
                    ray.update(chart_ray_geometry(stopped, ray["direction"]))
                if speed > .08:
                    # Learn actual key-release latency plus physical deceleration,
                    # rather than assume wall-clock FPS equals simulated physics.
                    coast = sum((a-p)*v for a, p, v in zip(actual, position, velocity))/(speed*speed)
                    braking["seconds"] = min(.25, max(.09, coast))
                if arrived(actual):
                    evidence["actual"] = stopped
                    return stopped
                last_decided_sample = None
                continue
            steering_target = target
            if ray is not None:
                # Correct cross-track error with a realizable perpendicular key
                # direction, leaving harmless along-ray drift room to settle.
                along, across = coordinates(position)
                if abs(across) < .50 and len(evidence["brakes"]) % 2 == 0:
                    # Alternate diagonal and perpendicular corrections after
                    # failed brakes. Their different real eight-way quanta avoid
                    # repeating the same overshoot under bursty native physics.
                    along += abs(across) * (1 if along < 1.8 else -1)
                along = min(2.2, max(1.4, along))
                outward, cross = ray["outward"], ray["cross_track"]
                steering_target = [1.3+outward[0]*along+outward[1]*cross,
                                   7.8+outward[1]*along-outward[0]*cross]
            move(direction_to(state, steering_target))
            pause(.05)
        raise TimeoutError("Off-route physical waypoint not reached: "+str(target))
    finally:
        move((0, 0))


def hold_chart_contact(read_states, move, pause, ray, opposite_to=None, timeout=35, evidence=None,
                       *, expected_sources=None, opposite_normal=None):
    """Hold the shipped W/S key, accepting only measured normal blocking."""
    evidence = {} if evidence is None else evidence
    initial = read_states()[-1]
    validate_state(initial, expected_demo=False)
    boundary = initial["sample_id"]
    deadline = time.monotonic() + timeout
    evidence.update({"ray":ray, "after_sample_id":boundary,
                     "after_physics_frame":initial["physics_frame"], "observations":[]})
    try:
        move(tuple(ray["direction"]))
        while time.monotonic() < deadline:
            selected = [state for state in read_states() if state["sample_id"] > boundary]
            evidence["observations"] = selected
            if selected:
                validate_state(selected[0], initial, expected_demo=False)
            receipt = validate_chart_contact(selected, opposite_to, required=False,
                expected_sources=expected_sources, after_frame=initial["physics_frame"],
                face=ray["face"], opposite_normal=opposite_normal)
            if time.monotonic() >= deadline:
                break
            if receipt is not None:
                evidence["result"] = "accepted actual blocked-normal contact"
                receipt["observations"] = selected
                receipt["held_ray"] = dict(ray)
                return receipt
            if selected and abs(selected[-1]["position"][0]-1.3) > .75 and abs(selected[-1]["position"][2]-7.8) < .9:
                evidence["result"] = "held approach slid beyond the tested flat face before a complete window"
                return None
            pause(.05)
        evidence["result"] = "contact timeout"
        return None
    finally:
        move((0, 0))


def run_chart_exploration(read_states, move, pause, snapshot, timeout=35, evidence=None, *, expected_sources=None):
    """Walk around geometrically opposing contacts; no interact calls."""
    samples, receipts, path = [], [], []
    evidence = {} if evidence is None else evidence
    evidence.update({"schema":3,"contract":CHART_CONTRACT,"source_sha256":expected_sources,"passed":False,"route":"actual X11 keyboard off-route chart encirclement and opposing contact probes; no interaction or state setters",
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
        return settle_chart_movement(observe, move, pause)

    braking = {"seconds": .12}
    def navigate(target,radius=.45,ray=None):
        attempt = {}
        evidence.setdefault("waypoint_attempts", []).append(attempt)
        state = navigate_chart_waypoint(observe, move, pause, target, radius, timeout, ray, braking, attempt)
        path.append({"target":target,"actual":state})

    def push(ray, opposite_to=None, opposite_normal=None):
        def current_samples():
            observe()
            return samples
        attempt = {}
        receipt = hold_chart_contact(current_samples, move, pause, ray, opposite_to, timeout, attempt,
            expected_sources=expected_sources, opposite_normal=opposite_normal)
        settled = settle()
        if receipt is not None:
            receipt["settled_after_release"] = settled
            return receipt
        evidence.setdefault("opposing_attempts", []).append(attempt)
        if opposite_to is None:
            raise TimeoutError("Actual first chart collision did not block inward normal motion: " + attempt["result"])
        return None

    def radial_angle(state):
        return math.atan2(state["position"][2]-7.8,state["position"][0]-1.3)

    def orbit_to(target_angle, final_ray=None):
        # Move out first, then around the pedestal in <=45-degree chords. Never
        # ask the player to cross the solid center to obtain the opposite probe.
        angle=radial_angle(observe())
        navigate([1.3+math.cos(angle)*1.8,7.8+math.sin(angle)*1.8],.45)
        angle=radial_angle(observe())
        delta=(target_angle-angle+math.pi)%(2*math.pi)-math.pi
        steps=math.ceil(abs(delta)/(math.pi/4))
        for i in range(1,steps+1):
            a=angle+delta*i/steps
            navigate([1.3+math.cos(a)*1.8,7.8+math.sin(a)*1.8],ray=final_ray if i==steps else None)
        if steps==0:
            navigate([1.3+math.cos(target_angle)*1.8,7.8+math.sin(target_angle)*1.8],ray=final_ray)

    try:
        first_ray=chart_approach_ray(observe(),[0,1])
        navigate(first_ray["target"],ray=first_ray)
        first=push(first_ray);first["name"]="first";receipts.append(first)
        snapshot("native-chart-blocker-first.png")
        reference=list(first["radial_reference"])
        for attempt_index in range(3):
            ray=chart_approach_ray(observe(),[0,-1])
            orbit_to(math.atan2(ray["outward"][1],ray["outward"][0]),ray)
            second=push(ray,reference,first["actual_normal"])
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
