import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from resource_budget import ADDITIONAL,LEGACY_GZIP,LEGACY_RAW,validate
class PublicationBudget(unittest.TestCase):
    def baseline(self):return {'legacy':[LEGACY_RAW,LEGACY_GZIP],'dawnkeep-defense':list(ADDITIONAL['dawnkeep-defense'])}
    def test_exact_independent_ceilings_pass(self):validate(self.baseline())
    def test_legacy_ceiling_not_relaxed_by_new_game(self):
        for channel in (0,1):
            groups=self.baseline();groups['legacy'][channel]+=1
            with self.assertRaisesRegex(ValueError,'legacy'):validate(groups)
    def test_new_pack_has_separate_bounds(self):
        for channel in (0,1):
            groups=self.baseline();groups['dawnkeep-defense'][channel]+=1
            with self.assertRaisesRegex(ValueError,'dawnkeep-defense'):validate(groups)
    def test_unknown_case_cannot_invent_exemption(self):
        groups=self.baseline();groups['unknown']=[0,0]
        with self.assertRaisesRegex(ValueError,'Unexpected'):validate(groups)
if __name__=='__main__':unittest.main()
