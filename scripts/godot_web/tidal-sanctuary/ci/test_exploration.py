"""Negative fixtures for off-route observers, not real-input acceptance."""
import math
import unittest
from exploration import validate_chart_contact, run_chart_exploration


def sample(index, angle=0):
    radial=[math.cos(angle),math.sin(angle)]
    return {"schema":1,"sample_id":index+1,"physics_frame":60+index*20,"demo":False,
            "position":[1.3+radial[0]*.65,.53,7.8+radial[1]*.65],"locomotion":"walk","water_depth":0.0,
            "camera_right":[1,0],"camera_forward":[0,-1],"action_rect":[1100,620,100,40],
            "quest_stage":0,"treasures":[False,False],"completed":False,"language":"en",
            "movement_input":[-radial[0],-radial[1]],"velocity":[0,0,0],"interaction_available":True,
            "interaction_reason":"ready"}


class ExplorationTests(unittest.TestCase):
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
