import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from resource_budget import ADDITIONAL,LEGACY_GZIP,LEGACY_RAW,validate
class PublicationBudget(unittest.TestCase):
    def baseline(self):return {'legacy':[LEGACY_RAW,LEGACY_GZIP],**{slug:list(bounds) for slug,bounds in ADDITIONAL.items()}}
    def test_declared_ceilings_remain_case_specific(self):
        mib=1024*1024
        self.assertEqual((LEGACY_RAW,LEGACY_GZIP),(40*mib,11*mib))
        self.assertEqual(ADDITIONAL['dawnkeep-defense'],(6*mib,5*mib))
        self.assertEqual(ADDITIONAL['hyper3d-relic-room'],(40*mib,40*mib))
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
    def test_hyper3d_case_has_independent_bounds(self):
        for channel in (0,1):
            groups=self.baseline();groups['hyper3d-relic-room'][channel]+=1
            with self.assertRaisesRegex(ValueError,'hyper3d-relic-room'):validate(groups)
if __name__=='__main__':unittest.main()
