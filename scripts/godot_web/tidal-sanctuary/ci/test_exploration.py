"""Negative fixtures for off-route observers, not real-input acceptance."""
import math
import unittest
from unittest.mock import Mock, patch
from exploration import (chart_approach_ray, chart_ray_geometry, hold_chart_contact, navigate_chart_waypoint,
                         validate_chart_contact, run_chart_exploration)
from gameplay import keyboard_direction


def sample(index, angle=0):
    radial=[math.cos(angle),math.sin(angle)]
    return {"schema":1,"sample_id":index+1,"physics_frame":60+index*20,"demo":False,
            "position":[1.3+radial[0]*.65,.53,7.8+radial[1]*.65],"locomotion":"walk","water_depth":0.0,
            "camera_right":[1,0],"camera_forward":[0,-1],"action_rect":[1100,620,100,40],
            "quest_stage":0,"treasures":[False,False],"completed":False,"language":"en",
            "movement_input":[-radial[0],-radial[1]],"velocity":[0,0,0],"interaction_available":True,
            "interaction_reason":"ready"}


class ExplorationTests(unittest.TestCase):
    def run_waypoint(self, observations, ray=None, target=None, timeout=1):
        clock, cursor, moves, evidence = [0.], [0], [], {}
        braking = {"seconds": .12}
        def observe():
            return observations[cursor[0]]
        def pause(seconds):
            clock[0] += seconds
            cursor[0] = min(cursor[0]+1, len(observations)-1)
        with patch("exploration.time.monotonic", side_effect=lambda: clock[0]):
            try:
                result = navigate_chart_waypoint(observe, moves.append, pause,
                    target or ray["target"], timeout=timeout, ray=ray, braking=braking, evidence=evidence)
            except TimeoutError as error:
                result = error
        return result, moves, evidence, clock[0], braking

    def trace_state(self, index, position, velocity, movement=(0, 0)):
        state = sample(index)
        state.update({"position": [position[0], .53, position[1]],
                      "velocity": [velocity[0], 0, velocity[1]], "movement_input": list(movement),
                      "camera_right": [.953733861446381, .300652146339417],
                      "camera_forward": [.300652146339417, -.953733861446381]})
        return state

    def test_actual_centerline_stop_cannot_stage_the_bevel_contact(self):
        # Exact a08ccc3 native samples 8-11. The old center ray accepted sample
        # 11, then A+W missed the southeast bevel and slid along the south face.
        initial = self.trace_state(8, [2.844210386, 9.208654404], [.053894073, -.026708052])
        approaching = self.trace_state(9, [2.4632, 9.4087], [-2.565, 1.385], [-.876, .482])
        coasting = self.trace_state(10, [2.134875059, 9.585264206], [-.508321941, .277584285])
        stopped = self.trace_state(11, [2.094228983, 9.604900360], [-.058232784, .031799734])
        stopped["camera_right"] = [.959165692329407, .282844960689545]
        stopped["camera_forward"] = [.282844960689545, -.959165692329407]
        ray = chart_approach_ray(initial, [1, 1])
        result, moves, evidence, elapsed, _ = self.run_waypoint([initial, approaching, coasting, stopped], ray)
        self.assertIsInstance(result, TimeoutError)
        self.assertEqual(keyboard_direction(moves[0]), {"a", "s"})
        self.assertIs(evidence["brakes"][0]["observed"], approaching)
        self.assertIs(evidence["brakes"][0]["settled"], stopped)
        self.assertNotIn("actual", evidence)
        self.assertLessEqual(elapsed, 1.05)
        self.assertEqual(ray["direction"], [-1, -1])
        # Staging refreshes the real camera basis without changing held keys.
        expected = chart_ray_geometry(stopped, [-1, -1])
        self.assertEqual(ray, expected)

    def test_bevel_ray_matches_actual_stable_contact_not_failed_center_line(self):
        # Retained ad1865e real stop: repeated A+W produces zero velocity at
        # (1.6914,8.3315). Geometry guides input; it is not new gameplay proof.
        state = self.trace_state(17, [1.691409707, 8.331536293], [0, 0])
        state["camera_right"] = [.956888139247894, .290456622838974]
        state["camera_forward"] = [.290456622838974, -.956888198852539]
        ray = chart_approach_ray(state, [1, 1])
        def error(position):
            radial = [position[0]-1.3, position[1]-7.8]
            return radial[0]*ray["outward"][1]-radial[1]*ray["outward"][0]-ray["cross_track"]
        self.assertLess(abs(error([1.691409707, 8.331536293])), .02)
        self.assertGreater(abs(error([2.094228983, 9.604900360])), .20)
        self.assertGreater(ray["cross_track"], .08)
        opposite = chart_approach_ray(state, [-1, -1])
        self.assertLess(abs((.873088956-1.3)*opposite["outward"][1]
                            -(7.260665894-7.8)*opposite["outward"][0]-opposite["cross_track"]), .05)

    def test_aligned_fresh_stop_still_allows_longitudinal_staging_room(self):
        ray = chart_approach_ray(self.trace_state(1, [3., 9.], [0, 0]), [1, 1])
        outward, cross = ray["outward"], ray["cross_track"]
        position = [1.3+outward[0]*2.2+outward[1]*cross,
                    7.8+outward[1]*2.2-outward[0]*cross]
        moving = self.trace_state(1, position, [-.2*outward[0], -.2*outward[1]])
        stopped = self.trace_state(2, position, [0, 0])
        result, moves, evidence, _, _ = self.run_waypoint([moving, stopped], ray)
        self.assertIs(result, stopped)
        self.assertGreater(math.dist(position, ray["target"]), .25)
        self.assertEqual(moves, [(0, 0), (0, 0)])
        self.assertIs(evidence["brakes"][0]["settled"], stopped)

    def test_waypoint_rejects_stale_neutral_and_idle_but_moving_stops(self):
        ray = chart_approach_ray(self.trace_state(0, [3., 9.], [0, 0]), [1, 0])
        for observations in ([self.trace_state(1, ray["target"], [0, 0])],
                [self.trace_state(i, ray["target"], [.2, 0]) for i in range(1, 20)]):
            with self.subTest(observations=len(observations)):
                result, moves, evidence, elapsed, _ = self.run_waypoint(observations, ray, timeout=.2)
                self.assertIsInstance(result, TimeoutError)
                self.assertNotIn("actual", evidence)
                self.assertLessEqual(elapsed, .25)  # No extra ten-second settle budget.
                self.assertTrue(all(move == (0, 0) for move in moves))

    def test_waypoint_settle_boundary_remains_after_actual_release_barrier(self):
        ray = chart_approach_ray(sample(0), [1, 0])
        before = self.trace_state(1, ray["target"], [.3, 0], [-1, 0])
        release_receipt = self.trace_state(2, ray["target"], [0, 0])
        latest, clock = [before], [0.]
        def move(_):
            latest[0] = release_receipt
        def pause(seconds):
            clock[0] += seconds
        with patch("exploration.time.monotonic", side_effect=lambda: clock[0]), self.assertRaises(TimeoutError):
            navigate_chart_waypoint(lambda: latest[0], move, pause, ray["target"], ray=ray, timeout=.2)
        # A newer settled sample after the keyup barrier is still required;
        # its own receipt cannot stand in for that later observation.
        self.assertLessEqual(clock[0], .25)

    def test_waypoint_rejects_wrong_ray_cross_track_and_outside_staging_band(self):
        ray = chart_approach_ray(sample(0), [1, 0])
        for position in ([-.5, 7.8], [3.1, 8.01], [2.4, 7.8], [3.8, 7.8]):
            observations = [self.trace_state(i, position, [0, 0]) for i in range(1, 20)]
            with self.subTest(position=position):
                result, moves, evidence, elapsed, _ = self.run_waypoint(observations, ray, timeout=.2)
                self.assertIsInstance(result, TimeoutError)
                self.assertNotIn("actual", evidence)
                self.assertTrue(any(move != (0, 0) for move in moves))
                self.assertLessEqual(elapsed, .25)

    def test_regular_waypoint_keeps_arrival_disk_and_checks_released_drift(self):
        target = [2.8, 9.2]
        moving = self.trace_state(1, [2.48, 9.39], [2.94, -1.46], [.897, -.441])
        drifted = self.trace_state(2, [3.3, 9.2], [0, 0])
        result, moves, evidence, _, _ = self.run_waypoint([moving, drifted], target=target, timeout=.2)
        self.assertIsInstance(result, TimeoutError)
        self.assertEqual(moves[0], (0, 0))
        self.assertNotIn("actual", evidence)

    def test_synthetic_low_fps_keyboard_and_coast_controller_stays_within_budget(self):
        # A controller fixture only: 13 physics ticks per .625 wall seconds,
        # delayed eight-way keys, and the production walk damping equation.
        # This does not simulate the collider or establish real native input.
        state = self.trace_state(8, [2.844210386, 9.208654404], [0, 0])
        ray = chart_approach_ray(state, [1, 1])
        clock, physics, next_tick = [0.], [0], [.625/13]
        position, velocity, active = [2.844210386, 9.208654404], [0., 0.], [0., 0.]
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
        self.assertEqual(moves[0], {"a", "s"})
        self.assertEqual(moves[-1], set())
        self.assertLess(clock[0], 35)

    def test_synthetic_burst_physics_and_camera_staging_stays_within_budget(self):
        # Controller-only fixture matching the failed trace's coarse sampling:
        # eight physics ticks per draw, 13 ticks per passive sample, actual
        # key-release barrier, follow-camera damping and walking acceleration.
        # No collider is simulated; this is not physical gameplay acceptance.
        for draw_seconds in (.35, .625, .8):
            with self.subTest(draw_seconds=draw_seconds):
                state = self.trace_state(8, [2.844210386, 9.208654404], [0, 0])
                ray = chart_approach_ray(state, [1, 1])
                clock, physics, next_draw = [0.], [104], [draw_seconds]
                position, velocity = [2.844210386, 9.208654404], [0., 0.]
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
                            if physics[0] % 13 == 0:
                                state = self.trace_state(physics[0]//13, position, velocity, world)
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
                self.assertLessEqual(abs(error), .08)
                self.assertLessEqual(math.hypot(result["velocity"][0], result["velocity"][2]), .08)
                self.assertEqual(result["movement_input"], [0, 0])
                self.assertTrue(any(len(keys) == 1 for keys in moves))  # Fine lateral correction.
                self.assertEqual(moves[-1], set())
                self.assertLess(clock[0], 35)

    def run_held_probe(self, observations, ray, opposite_to=None, baseline_angle=None):
        angle = math.atan2(ray["outward"][1], ray["outward"][0]) if baseline_angle is None else baseline_angle
        initial = sample(0, angle)
        initial["position"] = [1.3+math.cos(angle)*1.8, .53, 7.8+math.sin(angle)*1.8]
        initial["movement_input"] = [0, 0]
        history = [initial]
        queued = iter(observations)
        first = True
        clock = [0.]
        def read():
            nonlocal first
            if first:
                first = False
            else:
                following = next(queued, None)
                if following is not None:
                    history.append(following)
            return list(history)
        def pause(seconds):
            clock[0] += seconds
        moves, evidence = [], {}
        with patch("exploration.time.monotonic", side_effect=lambda: clock[0]):
            result = hold_chart_contact(read, moves.append, pause, ray, opposite_to, timeout=1, evidence=evidence)
        return result, moves, evidence

    def test_camera_axes_select_real_diagonal_and_opposite_keys(self):
        state = sample(0)
        angle = .295
        state["camera_right"] = [math.cos(angle), math.sin(angle)]
        state["camera_forward"] = [math.sin(angle), -math.cos(angle)]
        first = chart_approach_ray(state, [1, 1])
        self.assertEqual(first["keys"], ["a", "w"])
        self.assertEqual(first["direction"], [-1, -1])
        self.assertAlmostEqual(first["outward"][0], (math.cos(angle)-math.sin(angle))/math.sqrt(2))
        self.assertAlmostEqual(first["outward"][1], (math.sin(angle)+math.cos(angle))/math.sqrt(2))
        opposite = chart_approach_ray(state, [-axis for axis in first["outward"]])
        self.assertEqual(opposite["keys"], ["d", "s"])
        self.assertAlmostEqual(sum(a*b for a,b in zip(first["outward"], opposite["outward"])), -1)
        radial = [first["target"][0]-1.3, first["target"][1]-7.8]
        self.assertAlmostEqual(sum(a*b for a, b in zip(radial, first["outward"])), 1.8)
        self.assertAlmostEqual(radial[0]*first["outward"][1]-radial[1]*first["outward"][0], first["cross_track"])
        for axis, center in enumerate((1.3, 7.8)):
            self.assertAlmostEqual(opposite["bevel_aim"][axis], 2*center-first["bevel_aim"][axis])
        with self.assertRaises(ValueError):
            chart_approach_ray(state, [0, 0])

    def test_geometry_rejects_nonphysical_key_combinations(self):
        for direction in ([0, 0], [.2, 1], [2, 0], [True, 0], [float("nan"), 1]):
            with self.subTest(direction=direction), self.assertRaises(ValueError):
                chart_ray_geometry(sample(0), direction)

    def test_actual_failed_face_slide_still_fails_held_contact(self):
        ray = chart_approach_ray(self.trace_state(8, [2.844210386, 9.208654404], [0, 0]), [1, 1])
        observations = [
            self.trace_state(12, [1.8999, 9.2571], [-1.386, -2.494], [-.487, -.873]),
            self.trace_state(13, [1.5708, 8.6641], [-1.608, -2.823], [-.499, -.867]),
            self.trace_state(14, [1.1972, 8.3708], [-1.651, 0], [-.501, -.865]),
        ]
        receipt, moves, evidence = self.run_held_probe(observations, ray)
        self.assertIsNone(receipt)
        self.assertEqual(evidence["result"], "held contact left the intended opposite sector")
        self.assertEqual(moves, [(-1, -1), (0, 0)])

    def test_held_probe_keeps_one_diagonal_press_across_camera_changes(self):
        ray = chart_approach_ray(sample(0), [1, 1])
        observations = [sample(i, math.pi/4) for i in range(1, 5)]
        for i, state in enumerate(observations):
            angle = .03*(i % 2)
            state["camera_right"] = [math.cos(angle), math.sin(angle)]
            state["camera_forward"] = [math.sin(angle), -math.cos(angle)]
            state["movement_input"] = [(math.sin(angle)-math.cos(angle))/math.sqrt(2),
                                        -(math.sin(angle)+math.cos(angle))/math.sqrt(2)]
        receipt, moves, evidence = self.run_held_probe(observations, ray)
        self.assertEqual(moves, [(-1, -1), (0, 0)])
        self.assertEqual(receipt["contact_physics_frames"], 60)
        self.assertEqual(receipt["contact_samples"], 4)
        self.assertEqual(receipt["held_ray"], ray)
        self.assertEqual(evidence["result"], "accepted held contact")

    def test_held_probe_rejects_same_side_and_leaving_opposed_sector(self):
        ray = chart_approach_ray(sample(0), [1, 0])
        for angles in ([math.pi]*4, [0, 0, math.pi]):
            observations = [sample(i, angle) for i, angle in enumerate(angles, 1)]
            receipt, moves, evidence = self.run_held_probe(observations, ray, [-1, 0])
            self.assertIsNone(receipt)
            self.assertEqual(moves, [(-1, 0), (0, 0)])
            self.assertIn("sector", evidence["result"])
            self.assertLess(len(evidence["observations"]), 4)

    def test_held_probe_rejects_sliding_in_sector_without_extending_contact_budget(self):
        ray = chart_approach_ray(sample(0), [1, 0])
        observations = [sample(i, angle) for i, angle in enumerate((-.2, -.07, .07, .2), 1)]
        receipt, moves, evidence = self.run_held_probe(observations, ray, [-1, 0])
        self.assertIsNone(receipt)
        self.assertEqual(moves, [(-1, 0), (0, 0)])
        self.assertEqual(evidence["result"], "held contact slid instead of stopping")
        self.assertEqual(evidence["observations"][-1]["physics_frame"]-evidence["observations"][0]["physics_frame"], 60)

    def test_held_probe_never_accepts_short_stale_or_missing_contact(self):
        ray = chart_approach_ray(sample(0), [1, 0])
        for observations in ([], [sample(i) for i in range(1, 4)]):
            receipt, moves, evidence = self.run_held_probe(observations, ray, [-1, 0])
            self.assertIsNone(receipt)
            self.assertEqual(moves, [(-1, 0), (0, 0)])
            self.assertEqual(evidence["result"], "contact timeout")

    def test_held_probe_releases_keys_on_invalid_physics(self):
        ray = chart_approach_ray(sample(0), [1, 0])
        initial = sample(0)
        initial["position"] = [3.1, .53, 7.8]
        invalid = {**sample(1), "position": [1.3, .53, 7.8]}
        moves = []
        with self.assertRaisesRegex(ValueError, "penetrated"):
            hold_chart_contact(Mock(side_effect=[[initial], [initial, invalid]]), moves.append, Mock(), ray)
        self.assertEqual(moves, [(-1, 0), (0, 0)])

    def test_both_sustained_contacts_at_oblique_angles(self):
        first=validate_chart_contact([sample(i,2.25) for i in range(7)])
        second=validate_chart_contact([sample(i,2.25+math.pi) for i in range(7)],first['radial_reference'])
        self.assertEqual(first["contact_physics_frames"],60)
        self.assertEqual(second["contact_physics_frames"],60)
        self.assertAlmostEqual(second["maximum_opposition_dot"],-1)

    def test_reject_penetration_idle_progress_and_stale(self):
        for change in ({"position":[1.3,.53,7.8]}, {"movement_input":[0,0]},
                       {"movement_input":[1,0]}, {"movement_input":[0,1]}, {"quest_stage":1},
                       {"sample_id":1,"physics_frame":60}, {"demo":True}):
            samples=[{**sample(i),**change} for i in range(7)]
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_chart_contact(samples)

    def test_pending_does_not_hide_invalid_or_penetrating_samples(self):
        for change in ({"position":[1.3,.53,7.8]}, {"demo":True}, {"quest_stage":1},
                       {"position":[float('nan'),.53,7.8]}, {"sample_id":0}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_chart_contact([{**sample(0),**change}],required=False)
        self.assertIsNone(validate_chart_contact([sample(0)],required=False))

    def test_interrupted_and_sparse_contact_fail(self):
        samples=[sample(i) for i in range(7)]
        for i in (2,4):samples[i]["movement_input"]=[0,0]
        with self.assertRaises(ValueError):validate_chart_contact(samples)
        samples=[{**sample(i),"physics_frame":60+i*120} for i in range(7)]
        with self.assertRaises(ValueError):validate_chart_contact(samples)

    def test_contact_accepts_approach_prefix_before_stable_trailing_second(self):
        samples=[sample(i) for i in range(7)]
        for item,x in zip(samples,(2.18,2.10,2.01)):
            item["position"][0]=x
        receipt=validate_chart_contact(samples)
        self.assertEqual(receipt["contact_physics_frames"],60)
        self.assertEqual(receipt["contact_samples"],4)

    def test_contact_rejects_slide_and_return_with_matching_endpoints(self):
        samples=[sample(i) for i in range(7)]
        samples[-3]["position"][2]+=.25
        samples[-2]["position"][2]+=.25
        with self.assertRaisesRegex(ValueError,"stable physical stop"):
            validate_chart_contact(samples)

    def test_contact_duration_and_sliding_fail(self):
        with self.assertRaises(ValueError):
            validate_chart_contact([sample(i) for i in range(3)])
        samples=[sample(i) for i in range(7)]
        for i,item in enumerate(samples):item["position"][2]+=i*.09
        with self.assertRaisesRegex(ValueError,"stable physical stop"):
            validate_chart_contact(samples)

    def test_second_rejects_same_adjacent_and_outside_opposition_boundary(self):
        for angle in (0, math.pi/2, math.acos(-.799)):
            with self.subTest(angle=angle),self.assertRaisesRegex(ValueError,'continuously opposite'):
                validate_chart_contact([sample(i,angle) for i in range(7)],[1,0])
        receipt=validate_chart_contact([sample(i,math.acos(-.801)) for i in range(7)],[1,0])
        self.assertLessEqual(receipt['maximum_opposition_dot'],-.8)

    def test_every_second_window_sample_must_be_opposite(self):
        samples=[sample(i,math.acos(-.81)) for i in range(7)]
        samples[-2]=sample(5,math.acos(-.79))
        with self.assertRaisesRegex(ValueError,'continuously opposite'):
            validate_chart_contact(samples,[1,0])
        samples=[sample(i,0) for i in range(7)];samples[-1]=sample(6,math.pi)
        with self.assertRaises(ValueError):validate_chart_contact(samples,[1,0])

    def test_invalid_opposition_reference_fails(self):
        for reference in ([0,0],[2,0],[float('nan'),0],[True,0],[1],"east"):
            with self.subTest(reference=reference),self.assertRaises(ValueError):
                validate_chart_contact([sample(i) for i in range(7)],reference)

    def test_navigation_penetration_fails_before_any_route_input(self):
        moves=[];images=[];evidence={}
        initial=sample(0);initial["position"]=[1.3,.53,7.8]
        with self.assertRaisesRegex(ValueError,"navigation penetrated"):
            run_chart_exploration(lambda:[initial],moves.append,lambda _:None,images.append,evidence=evidence)
        self.assertEqual(moves,[(0,0),(0,0)])  # Controller and route finally releases, no steering.
        self.assertEqual(images,[])
        self.assertFalse(evidence["passed"])

    def test_old_contact_cannot_substitute_for_current_contact(self):
        samples=[sample(i) for i in range(7)]
        samples[-1]['movement_input']=[0,0]
        with self.assertRaises(ValueError):validate_chart_contact(samples)

if __name__=='__main__':unittest.main()
