"""Negative fixtures for off-route observers, not real-input acceptance."""
import math
import unittest
from unittest.mock import Mock, patch
from exploration import chart_approach_ray, hold_chart_contact, validate_chart_contact, run_chart_exploration


def sample(index, angle=0):
    radial=[math.cos(angle),math.sin(angle)]
    return {"schema":1,"sample_id":index+1,"physics_frame":60+index*20,"demo":False,
            "position":[1.3+radial[0]*.65,.53,7.8+radial[1]*.65],"locomotion":"walk","water_depth":0.0,
            "camera_right":[1,0],"camera_forward":[0,-1],"action_rect":[1100,620,100,40],
            "quest_stage":0,"treasures":[False,False],"completed":False,"language":"en",
            "movement_input":[-radial[0],-radial[1]],"velocity":[0,0,0],"interaction_available":True,
            "interaction_reason":"ready"}


class ExplorationTests(unittest.TestCase):
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
        self.assertAlmostEqual(math.hypot(first["target"][0]-1.3, first["target"][1]-7.8), 1.8)
        with self.assertRaises(ValueError):
            chart_approach_ray(state, [0, 0])

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
        self.assertEqual(moves,[(0,0)])  # Only the finally release, no steering.
        self.assertEqual(images,[])
        self.assertFalse(evidence["passed"])

    def test_old_contact_cannot_substitute_for_current_contact(self):
        samples=[sample(i) for i in range(7)]
        samples[-1]['movement_input']=[0,0]
        with self.assertRaises(ValueError):validate_chart_contact(samples)

if __name__=='__main__':unittest.main()
