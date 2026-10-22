"""Controller/negative fixtures only; actual physics and OS input have separate gates."""
import copy
import math
import unittest
from pathlib import Path
from unittest.mock import patch
from exploration import (CHART_CONTRACT, CHART_REASON, chart_approach_ray, chart_ray_geometry,
                         hold_chart_contact, navigate_chart_waypoint, validate_chart_contact,
                         validate_chart_physics_controls, run_chart_exploration)
from gameplay import keyboard_direction

SOURCES = {"main.gd":"a"*64, "swim_controller.gd":"b"*64}
BASELINE = 100


def sample(index, angle=0):
    return {"schema":1,"sample_id":index+1,"physics_frame":60+index*20,"demo":False,
            "position":[1.3+math.cos(angle)*.65,.53,7.8+math.sin(angle)*.65],"locomotion":"walk","water_depth":0.0,
            "camera_right":[1,0],"camera_forward":[0,-1],"action_rect":[1100,620,100,40],
            "quest_stage":0,"treasures":[False,False],"completed":False,"language":"en",
            "movement_input":[0,0],"velocity":[0,0,0],"interaction_available":True,"interaction_reason":"ready"}


def motion_frames(face=1, contact_steps=14):
    """Synthetic read-only receipts; they never establish actual gameplay proof."""
    frames = []
    position = [1.3-.41*face,.53,7.8+1.2*face]
    for i in range(20+contact_steps):
        before = list(position)
        contact = i >= 20
        position = [position[0]+.015*face,.53,position[2]-(.0315*face if not contact else 0)]
        hit = {"body":"/root/Tidal/Solid_5100","class":"StaticBody3D","interaction_target":0,
               "intent":"solid","reason":CHART_REASON,"normal":[0,0,face],
               "point":[position[0],.75,7.8+.35*face]}
        frames.append({"physics_frame":BASELINE+i+1,"delta":1/60,"max_slides":6,"before":before,"after":list(position),
                       "requested_velocity":[.9*face,0,-(.5 if contact else 1.89)*face],
                       "velocity":[.9*face,0,0 if contact else -1.89*face],
                       "movement_input":[.2905*face,-.9569*face],"collisions":[hit] if contact else []})
    return frames


def observed(frames):
    result = []
    endpoints = list(range(13,len(frames)+1,13))
    if not endpoints or endpoints[-1] != len(frames):endpoints.append(len(frames))
    for index,end in enumerate(endpoints,1):
        frame = frames[end-1]
        state = sample(index)
        state.update({"physics_frame":frame["physics_frame"],"position":list(frame["after"]),
                      "velocity":list(frame["velocity"]),"movement_input":list(frame["movement_input"]),
                      "chart_motion":{"schema":2,"contract":CHART_CONTRACT,"source_sha256":dict(SOURCES),
                                      "frames":copy.deepcopy(frames[max(0,end-32):end])}})
        result.append(state)
    return result


def validate(frames=None, **kwargs):
    return validate_chart_contact(observed(motion_frames() if frames is None else frames),
        expected_sources=SOURCES, after_frame=BASELINE, **kwargs)


class ContactTests(unittest.TestCase):
    def test_real_contact_contract_allows_tangent_slide_and_opposing_flat_faces(self):
        first = validate()
        self.assertEqual(first["contact_steps"],12)
        self.assertGreater(first["blocked_inward_distance"],.05)
        self.assertGreater(first["actual_approach_distance"],.15)
        self.assertEqual(first["maximum_normal_speed"],0)
        self.assertGreater(first["physics_steps"][-1]["velocity"][0],.8)
        second = validate(motion_frames(-1), face=-1, opposite_to=first["radial_reference"], opposite_normal=first["actual_normal"])
        self.assertLessEqual(second["maximum_opposition_dot"],-.8)
        self.assertEqual(second["maximum_normal_opposition_dot"],-1)

    def test_chart_subcontact_after_terrain_contact_is_not_lost(self):
        frames=motion_frames()
        floor={"body":"/root/Terrain","class":"StaticBody3D","interaction_target":-1,
               "intent":"solid","reason":"terrain","normal":[0,1,0],"point":[1.3,.5,8.37]}
        for frame in frames:frame["collisions"].insert(0,dict(floor))
        self.assertEqual(validate(frames)["contact_steps"],12)
        for frame in frames:frame["collisions"] = [dict(floor)]*36 + frame["collisions"][-1:]
        self.assertEqual(validate(frames)["contact_steps"],12)
        frames[-1]["collisions"].append(dict(floor))
        with self.assertRaisesRegex(ValueError,"collision list"):validate(frames)

    def test_twelve_steps_required_and_buffer_window_can_end_between_emissions(self):
        with self.assertRaises(ValueError):validate(motion_frames(contact_steps=11))
        self.assertEqual(validate(motion_frames(contact_steps=12))["contact_steps"],12)
        frames = motion_frames(contact_steps=17)
        for frame in frames[-5:]:frame["collisions"] = []
        self.assertEqual(validate(frames)["last_physics_frame"],BASELINE+32)

    def test_stale_contact_and_release_after_completed_window_fail(self):
        for tail, idle in ((13,False),(1,True)):
            frames = motion_frames(contact_steps=12+tail)
            for frame in frames[-tail:]:
                frame["collisions"] = []
                if idle:frame["movement_input"] = [0,0]
            with self.subTest(tail=tail), self.assertRaises(ValueError):validate(frames)

    def test_wrong_collider_floor_bevel_opposite_normal_and_identity_fail(self):
        changes = ({"class":"Area3D"},{"interaction_target":1},{"interaction_target":False},
                   {"intent":"query"},{"reason":"other solid"},{"body":"/root/Terrain"},
                   {"normal":[0,1,0]},{"normal":[1,0,0]},{"normal":[0,0,-1]},
                   {"normal":[math.sqrt(.5),0,math.sqrt(.5)]},{"point":[1.3,.75,8.3]})
        for change in changes:
            frames = motion_frames()
            for frame in frames[20:]:frame["collisions"][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate(frames)
        frames = motion_frames()
        for i,frame in enumerate(frames[20:]):frame["collisions"][0]["body"] += str(i)
        with self.assertRaises(ValueError):validate(frames)

    def test_missing_collider_cannot_pass_even_with_stationary_positions(self):
        frames = motion_frames()
        for frame in frames:frame["collisions"] = []
        with self.assertRaises(ValueError):validate(frames)

    def test_idle_released_outward_tangent_only_and_unblocked_motion_fail(self):
        for field,value in (("movement_input",[0,0]),("movement_input",[0,1]),("movement_input",[1,0]),
                            ("requested_velocity",[.9,0,0]),("requested_velocity",[.9,0,-.101]),
                            ("velocity",[.9,0,-.5])):
            frames = motion_frames()
            for frame in frames[20:]:frame[field] = list(value)
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):validate(frames)

    def test_stationary_spawn_at_wall_does_not_replace_actual_approach(self):
        frames = motion_frames()
        for frame in frames:
            frame["before"] = [1.3,.53,8.37]
            frame["after"] = [1.3,.53,8.37]
        with self.assertRaises(ValueError):validate(frames)

    def test_interrupted_input_does_not_accumulate_disjoint_contact_steps(self):
        frames = motion_frames()
        frames[26]["movement_input"] = [0,0]
        with self.assertRaises(ValueError):validate(frames)

    def test_penetration_crossing_and_normal_displacement_fail_even_when_pending(self):
        for shift in (.03,.6,1.2):
            frames = motion_frames()
            for frame in frames:
                frame["before"][2] -= shift
                frame["after"][2] -= shift
            with self.subTest(shift=shift),self.assertRaisesRegex(ValueError,"penetrated|crossed"):
                validate(frames,required=False)
        frames = motion_frames()
        for i,frame in enumerate(frames[20:]):
            frame["before"][2] -= .004*i
            frame["after"][2] -= .004*(i+1)
        with self.assertRaises(ValueError):validate(frames)

    def test_missing_schema_source_binding_receipts_and_state_disagreement_fail(self):
        mutations = [lambda s:s.pop("chart_motion"),
                     lambda s:s["chart_motion"].update(schema=1),
                     lambda s:s["chart_motion"].update(contract="old"),
                     lambda s:s["chart_motion"].update(source_sha256={}),
                     lambda s:s["chart_motion"].update(frames=[]),
                     lambda s:s["position"].__setitem__(0,s["position"][0]+.02),
                     lambda s:s["velocity"].__setitem__(0,0),
                     lambda s:s["movement_input"].__setitem__(0,0)]
        for mutate in mutations:
            states = observed(motion_frames());mutate(states[-1])
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                validate_chart_contact(states,expected_sources=SOURCES,after_frame=BASELINE)
        for binding in (None,{}, {**SOURCES,"main.gd":"bad"}, {**SOURCES,"main.gd":"c"*64}):
            with self.subTest(binding=binding),self.assertRaises(ValueError):
                validate_chart_contact(observed(motion_frames()),expected_sources=binding,after_frame=BASELINE)

    def test_repeated_conflicting_gapped_future_and_stale_physics_fail(self):
        mutations = [lambda s:s[-1]["chart_motion"]["frames"][0]["velocity"].__setitem__(0,4),
                     lambda s:s[-1]["chart_motion"]["frames"].pop(3),
                     lambda s:s[-1]["chart_motion"]["frames"][-1].update(physics_frame=999),
                     lambda s:s[-1]["chart_motion"]["frames"].pop(),
                     lambda s:[state["chart_motion"]["frames"].pop(0) for state in s if state["chart_motion"]["frames"][0]["physics_frame"] == BASELINE+1]]
        for mutate in mutations:
            states = observed(motion_frames());mutate(states)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                validate_chart_contact(states,expected_sources=SOURCES,after_frame=BASELINE)
        states=observed(motion_frames());states.append(copy.deepcopy(states[-1]))
        with self.assertRaises(ValueError):validate_chart_contact(states,expected_sources=SOURCES,after_frame=BASELINE)

    def test_malformed_finite_timing_and_discontinuous_motion_fail(self):
        for field,value in (("delta",.1),("delta",float("nan")),("max_slides",7),("max_slides",True),("before",[1.3,.53,7.8]),
                            ("after",[float("nan"),0,8.37]),("requested_velocity",[True,0,0]),
                            ("movement_input",[0]),("collisions",None)):
            frames=motion_frames();frames[25][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate(frames)
        frames=motion_frames();frames[25]["collisions"][0]["normal"]=[0,0,0]
        with self.assertRaises(ValueError):validate(frames)

    def test_progress_demo_and_teleport_fail_before_pending_contact(self):
        for change in ({"quest_stage":1},{"demo":True},{"position":[1.3,.53,7.8]},
                       {"position":[float("nan"),.53,8.37]},{"sample_id":0}):
            states=observed(motion_frames());states[-1].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_chart_contact(states,required=False,expected_sources=SOURCES,after_frame=BASELINE)

    def test_same_adjacent_and_nonopposed_radial_reference_fail(self):
        for radial,normal in (([0,1],[0,0,1]),([1,0],[1,0,0]),([.8,-.6],[0,0,-1])):
            with self.subTest(radial=radial),self.assertRaises(ValueError):
                validate(opposite_to=radial,opposite_normal=normal)
        for reference in ([0,0],[2,0],[True,0],[float("nan"),0],[1],"east"):
            with self.subTest(reference=reference),self.assertRaises(ValueError):
                validate(opposite_to=reference,opposite_normal=[0,0,-1])

    def test_hold_keeps_one_keyboard_press_and_releases_on_acceptance_or_error(self):
        ray=chart_approach_ray(sample(0),[0,1])
        initial=sample(0);initial.update(physics_frame=BASELINE,position=motion_frames()[0]["before"])
        states=observed(motion_frames())
        for broken in (False,True):
            history=[initial];queue=iter(copy.deepcopy(states));first=[True];clock=[0.];moves=[];evidence={}
            def read():
                if first[0]:first[0]=False
                else:
                    following=next(queue,None)
                    if following:
                        if broken:following["chart_motion"]["source_sha256"]={}
                        history.append(following)
                return list(history)
            def pause(seconds):clock[0]+=seconds
            with patch("exploration.time.monotonic",side_effect=lambda:clock[0]):
                if broken:
                    with self.assertRaises(ValueError):hold_chart_contact(read,moves.append,pause,ray,timeout=1,expected_sources=SOURCES)
                else:
                    result=hold_chart_contact(read,moves.append,pause,ray,timeout=1,evidence=evidence,expected_sources=SOURCES)
                    self.assertEqual(result["contact_steps"],12)
            self.assertEqual(moves,[(0,-1),(0,0)])

    def test_hold_timeout_does_not_extend_budget_and_releases(self):
        state=sample(0);clock=[0.];moves=[];evidence={}
        def pause(seconds):clock[0]+=seconds
        with patch("exploration.time.monotonic",side_effect=lambda:clock[0]):
            self.assertIsNone(hold_chart_contact(lambda:[state],moves.append,pause,chart_approach_ray(state,[0,1]),
                timeout=.2,evidence=evidence,expected_sources=SOURCES))
        self.assertLessEqual(clock[0],.25)
        self.assertEqual(moves,[(0,-1),(0,0)])
        self.assertEqual(evidence["result"],"contact timeout")

    def test_actual_physics_control_inventory_is_mandatory(self):
        for checks in ([],[{"check":"actual_controller_chart_normal_contact","face":1,"mode":"solid"}]):
            with self.assertRaises(ValueError):validate_chart_physics_controls({"checks":checks},SOURCES)

    def test_navigation_penetration_fails_before_any_route_input(self):
        moves=[];images=[];evidence={};initial=sample(0);initial["position"]=[1.3,.53,7.8]
        with self.assertRaisesRegex(ValueError,"navigation penetrated"):
            run_chart_exploration(lambda:[initial],moves.append,lambda _:None,images.append,evidence=evidence,expected_sources=SOURCES)
        self.assertTrue(all(move==(0,0) for move in moves))
        self.assertEqual(images,[])
        self.assertFalse(evidence["passed"])


class ControllerTests(unittest.TestCase):
    def test_passive_native_chart_cadence_and_source_contract_are_bound(self):
        game = Path(__file__).resolve().parents[1] / "game"
        main = (game / "main.gd").read_text()
        controller = (game / "swim_controller.gd").read_text()
        self.assertIn('swim.observe_chart_motion=not OS.has_feature("web") and not demo', main)
        self.assertIn('swim.observe_chart_motion and quest_stage()==0 and flat_distance(player.position,lantern_points[0])<3.0', main)
        self.assertIn('if Engine.get_physics_frames()%4==0:state_clock=0;emit_state()', main)
        self.assertIn('elif state_clock>=.2:state_clock=0;emit_state()', main)
        self.assertIn('if swim.observe_chart_motion:data["chart_motion"]=swim.chart_motion_snapshot()', main)
        self.assertIn('const CHART_MOTION_CONTRACT := "'+CHART_CONTRACT+'"', controller)
        self.assertIn('const CHART_MOTION_LIMIT := 32', controller)
        self.assertIn('for contact_index in range(hit.get_collision_count()):', controller)
        for method in ("get_collider", "get_normal", "get_position"):
            self.assertIn('hit.'+method+'(contact_index)', controller)
        self.assertIn('body.move_and_slide()\n if record_motion:\n  _record_chart_motion(body, before, attempted, desired_move, delta)', controller)
        for source in SOURCES:self.assertIn('FileAccess.get_sha256("res://'+source+'")', controller)

    def run_waypoint(self, observations, ray=None, target=None, timeout=1):
        clock,cursor,moves,evidence=[0.],[0],[],{}
        def pause(seconds):
            clock[0]+=seconds;cursor[0]=min(cursor[0]+1,len(observations)-1)
        with patch("exploration.time.monotonic",side_effect=lambda:clock[0]):
            try:result=navigate_chart_waypoint(lambda:observations[cursor[0]],moves.append,pause,target or ray["target"],
                                               timeout=timeout,ray=ray,evidence=evidence)
            except TimeoutError as error:result=error
        return result,moves,evidence,clock[0]

    def trace_state(self,index,position,velocity,movement=(0,0)):
        state=sample(index)
        state.update(position=[position[0],.53,position[1]],velocity=[velocity[0],0,velocity[1]],movement_input=list(movement),
                     camera_right=[.953733861446381,.300652146339417],camera_forward=[.300652146339417,-.953733861446381])
        return state

    def test_camera_relative_W_and_S_target_opposing_flat_faces(self):
        state=self.trace_state(0,[1.3,10],[0,0]);first=chart_approach_ray(state,[0,1]);second=chart_approach_ray(state,[0,-1])
        self.assertEqual(first["keys"],["w"]);self.assertEqual(second["keys"],["s"])
        self.assertEqual(first["face"],1);self.assertEqual(second["face"],-1)
        self.assertAlmostEqual(first["face_aim"][1],8.37)
        self.assertAlmostEqual(second["face_aim"][1],7.23)
        for ray in (first,second):
            offset=[ray["face_aim"][0]-1.3,ray["face_aim"][1]-7.8]
            self.assertAlmostEqual(offset[0]*ray["outward"][1]-offset[1]*ray["outward"][0],ray["cross_track"])
        self.assertAlmostEqual(first["face_aim"][0]+second["face_aim"][0],2.6)

    def test_geometry_rejects_nonphysical_or_unintended_approaches(self):
        for direction in ([0,0],[.2,1],[2,0],[True,0],[float("nan"),1],[-1,-1]):
            with self.subTest(direction=direction),self.assertRaises(ValueError):chart_ray_geometry(sample(0),direction)
        for outward in ([0,0],[1,0],[1,.5]):
            with self.subTest(outward=outward),self.assertRaises(ValueError):chart_approach_ray(sample(0),outward)

    def test_waypoint_requires_fresh_neutral_stop_after_release(self):
        ray=chart_approach_ray(sample(0),[0,1]);position=ray["target"]
        for observations in ([self.trace_state(1,position,[0,0])],
                             [self.trace_state(i,position,[.2,0]) for i in range(1,20)]):
            result,moves,evidence,elapsed=self.run_waypoint(observations,ray,timeout=.2)
            self.assertIsInstance(result,TimeoutError);self.assertNotIn("actual",evidence)
            self.assertLessEqual(elapsed,.25)
        moving=self.trace_state(1,position,[.2,0]);stopped=self.trace_state(2,position,[0,0])
        ray=chart_approach_ray(moving,[0,1]);moving["position"]=[ray["target"][0],.53,ray["target"][1]];stopped["position"]=moving["position"]
        result,moves,evidence,_=self.run_waypoint([moving,stopped],ray)
        self.assertIs(result,stopped);self.assertEqual(moves,[(0,0),(0,0)])

    def test_waypoint_rejects_cross_track_error_and_released_drift(self):
        state=self.trace_state(0,[1.3,10],[0,0]);ray=chart_approach_ray(state,[0,1])
        position=[ray["target"][0]+.2,ray["target"][1]]
        result,moves,evidence,elapsed=self.run_waypoint([self.trace_state(i,position,[0,0]) for i in range(1,20)],ray,timeout=.2)
        self.assertIsInstance(result,TimeoutError);self.assertNotIn("actual",evidence)
        target=[2.8,9.2]
        result,_,evidence,_=self.run_waypoint([self.trace_state(1,[2.48,9.39],[2.94,-1.46]),
                                            self.trace_state(2,[3.3,9.2],[0,0])],target=target,timeout=.2)
        self.assertIsInstance(result,TimeoutError);self.assertNotIn("actual",evidence)

    def test_no_ray_precision_keeps_exact_radius_and_fresh_neutral_contract(self):
        target=[2.6,6.4]
        for kind in ("stale", "moving", "drift"):
            clock,cursor,moves,evidence=[0.],[0],[],{}
            first=self.trace_state(1,target,[0,0])
            later=self.trace_state(2,target,[0,0])
            if kind == "stale":later=first
            if kind == "moving":later["movement_input"]=[1,0]
            if kind == "drift":later["position"][0]+=.21
            observations=[first,later]
            def pause(seconds):
                clock[0]+=seconds;cursor[0]=1
            with self.subTest(kind=kind), patch("exploration.time.monotonic",side_effect=lambda:clock[0]):
                with self.assertRaises(TimeoutError):
                    navigate_chart_waypoint(lambda:observations[cursor[0]],moves.append,pause,
                        target,radius=.2,timeout=.2,ray=None,evidence=evidence)
            self.assertNotIn("actual",evidence)
            self.assertEqual(moves[-1],(0,0))
            self.assertLessEqual(clock[0],.25)
        clock,cursor,moves,evidence=[0.],[0],[],{}
        observations=[self.trace_state(1,target,[0,0]),self.trace_state(2,target,[0,0])]
        def pause(seconds):
            clock[0]+=seconds;cursor[0]=1
        with patch("exploration.time.monotonic",side_effect=lambda:clock[0]):
            actual=navigate_chart_waypoint(lambda:observations[cursor[0]],moves.append,pause,
                target,radius=.2,timeout=.2,ray=None,evidence=evidence)
        self.assertIs(actual,observations[1])
        self.assertIs(evidence["actual"],actual)

    def test_synthetic_low_fps_keyboard_and_coast_controller_stays_within_budget(self):
        # A controller fixture only: 13 physics ticks per .625 wall seconds,
        # delayed eight-way keys, and the production walk damping equation.
        # This does not simulate the collider or establish real native input.
        state = self.trace_state(8, [1.3, 10.0], [0, 0])
        ray = chart_approach_ray(state, [0, 1])
        clock, physics, next_tick = [0.], [0], [.625/13]
        position, velocity, active = [1.3, 10.0], [0., 0.], [0., 0.]
        command, pending, moves = [set()], [], []
        right, forward = state["camera_right"], state["camera_forward"]
        def move(direction):
            wanted = keyboard_direction(direction)
            if wanted != command[0]:
                command[0] = wanted
                x = int("d" in wanted)-int("a" in wanted)
                y = int("s" in wanted)-int("w" in wanted)
                world = [right[i]*x-forward[i]*y for i in range(2)]
                length = math.hypot(*world)
                pending.append((physics[0]+4, [v/length for v in world] if length else [0., 0.]))
                moves.append(wanted)
        def pause(seconds):
            nonlocal state
            until = clock[0]+seconds
            while next_tick[0] <= until:
                physics[0] += 1
                while pending and pending[0][0] <= physics[0]:
                    active[:] = pending.pop(0)[1]
                for i in range(2):
                    velocity[i] += (active[i]*3.3-velocity[i])*(1-math.exp(-10/60))
                    position[i] += velocity[i]/60
                if physics[0] % 13 == 0:
                    state = self.trace_state(8+physics[0]//13, position, velocity, active)
                next_tick[0] += .625/13
            clock[0] = until
        with patch("exploration.time.monotonic", side_effect=lambda: clock[0]):
            result = navigate_chart_waypoint(lambda: state, move, pause, ray["target"], ray=ray)
        radial = [result["position"][0]-1.3, result["position"][2]-7.8]
        self.assertLessEqual(abs(radial[0]*ray["outward"][1]-radial[1]*ray["outward"][0]-ray["cross_track"]), .08)
        self.assertLessEqual(math.hypot(result["velocity"][0], result["velocity"][2]), .08)
        self.assertEqual(result["movement_input"], [0, 0])
        self.assertTrue(moves[0])
        self.assertEqual(moves[-1], set())
        self.assertLess(clock[0], 35)

    def test_synthetic_burst_physics_and_camera_staging_stays_within_budget(self):
        # Controller-only fixture matching the failed trace's coarse sampling:
        # eight physics ticks per draw, four ticks per native chart sample, actual
        # key-release barrier, follow-camera damping and walking acceleration.
        # No collider is simulated; this is not physical gameplay acceptance.
        for draw_seconds in (.35, .625, .8):
            with self.subTest(draw_seconds=draw_seconds):
                state = self.trace_state(8, [1.3, 10.0], [0, 0])
                ray = chart_approach_ray(state, [0, 1])
                clock, physics, next_draw = [0.], [104], [draw_seconds]
                position, velocity = [1.3, 10.0], [0., 0.]
                camera = [position[0]-3.4, position[1]+10.]
                right, forward = state["camera_right"], state["camera_forward"]
                command, moves = [set()], []
                def pause(seconds):
                    nonlocal state, right, forward
                    until = clock[0]+seconds
                    while next_draw[0] <= until:
                        for _ in range(8):
                            physics[0] += 1
                            x = int("d" in command[0])-int("a" in command[0])
                            y = int("s" in command[0])-int("w" in command[0])
                            world = [right[i]*x-forward[i]*y for i in range(2)]
                            length = math.hypot(*world)
                            world = [v/length for v in world] if length else [0., 0.]
                            for i, offset in enumerate((-3.4, 10.)):
                                velocity[i] += (world[i]*3.3-velocity[i])*(1-math.exp(-10/60))
                                position[i] += velocity[i]/60
                                camera[i] += (position[i]+offset-camera[i])*(1-math.exp(-4.5/60))
                            basis = [position[0]-camera[0], position[1]-1.2-camera[1]]
                            length = math.hypot(*basis)
                            forward = [v/length for v in basis]
                            right = [-forward[1], forward[0]]
                            if physics[0] % 4 == 0:
                                state = self.trace_state(physics[0]//4, position, velocity, world)
                                state.update({"camera_right": right, "camera_forward": forward,
                                              "physics_frame": physics[0]})
                        next_draw[0] += draw_seconds
                    clock[0] = until
                def move(direction):
                    wanted = keyboard_direction(direction)
                    if wanted != command[0]:
                        command[0] = wanted
                        moves.append(wanted)
                        if not wanted:
                            boundary = state["sample_id"]
                            deadline = clock[0]+10
                            while (state["sample_id"] <= boundary or math.hypot(*state["movement_input"]) > .001):
                                if clock[0] >= deadline:
                                    raise TimeoutError("fixture keyup barrier")
                                pause(.05)
                with patch("exploration.time.monotonic", side_effect=lambda: clock[0]):
                    result = navigate_chart_waypoint(lambda: state, move, pause, ray["target"], ray=ray)
                radial = [result["position"][0]-1.3, result["position"][2]-7.8]
                error = radial[0]*ray["outward"][1]-radial[1]*ray["outward"][0]-ray["cross_track"]
                self.assertLessEqual(abs(error), .06)
                self.assertLessEqual(math.hypot(result["velocity"][0], result["velocity"][2]), .08)
                self.assertEqual(result["movement_input"], [0, 0])
                self.assertTrue(moves)
                self.assertEqual(moves[-1], set())
                self.assertLess(clock[0], 35)


if __name__ == "__main__":unittest.main()
