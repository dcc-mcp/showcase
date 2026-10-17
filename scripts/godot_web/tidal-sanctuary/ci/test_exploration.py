"""Negative fixtures for off-route observers, not real-input acceptance."""
import copy
import unittest
from exploration import validate_chart_contact


def sample(index, side=1):
    return {"schema":1,"sample_id":index+1,"physics_frame":60+index*20,"demo":False,
            "position":[1.3+side*.65,.53,7.8],"locomotion":"walk","water_depth":0.0,
            "camera_right":[1,0],"camera_forward":[0,-1],"action_rect":[1100,620,100,40],
            "quest_stage":0,"treasures":[False,False],"completed":False,"language":"en",
            "movement_input":[-side,0],"velocity":[0,0,0],"interaction_available":True,
            "interaction_reason":"ready"}


class ExplorationTests(unittest.TestCase):
    def test_both_sustained_contacts(self):
        for side in (-1,1):
            receipt=validate_chart_contact([sample(i,side) for i in range(7)],side)
            self.assertEqual(receipt["contact_physics_frames"],120)

    def test_reject_penetration_idle_wrong_side_progress_and_stale(self):
        for change in ({"position":[1.3,.53,7.8]}, {"movement_input":[0,0]},
                       {"position":[.65,.53,7.8]}, {"movement_input":[1,0]}, {"movement_input":[0,1]}, {"quest_stage":1},
                       {"sample_id":1,"physics_frame":60}, {"demo":True}):
            samples=[{**sample(i),**change} for i in range(7)]
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_chart_contact(samples,1)

    def test_interrupted_and_sparse_contact_fail(self):
        samples=[sample(i) for i in range(7)]
        for i in (2,4):samples[i]["movement_input"]=[0,0]
        with self.assertRaises(ValueError):validate_chart_contact(samples,1)
        samples=[{**sample(i),"physics_frame":60+i*120} for i in range(7)]
        with self.assertRaises(ValueError):validate_chart_contact(samples,1)

    def test_contact_duration_and_sliding_fail(self):
        with self.assertRaises(ValueError):
            validate_chart_contact([sample(i) for i in range(3)],1)
        samples=[sample(i) for i in range(7)]
        for i,item in enumerate(samples):item["position"][2]+=i*.06
        with self.assertRaisesRegex(ValueError,"stable physical stop"):
            validate_chart_contact(samples,1)

if __name__=='__main__':unittest.main()
