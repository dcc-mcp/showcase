"""Exact saved candidate regressions, no native execution or replay."""
import hashlib
import json
import pathlib
import unittest
from conversion_contract import audit_candidate
ROOT=pathlib.Path(__file__).resolve().parent

def digest(data):return hashlib.sha256(data).hexdigest()

class Resume(unittest.TestCase):
    def test_exact_saved_candidate_fixtures(self):
        pins=json.loads((ROOT/'original-evidence-pins.json').read_text())
        for path in (ROOT/'fixtures').glob('*.tscn'):
            expected=pins['files']['convert/project/kenney-preflight/candidates/'+path.name]
            data=path.read_bytes()
            self.assertEqual(len(data),expected['bytes'])
            self.assertEqual(digest(data),expected['sha256'])
            audit_candidate(data,expected['sha256'])
        self.assertEqual(len(list((ROOT/'fixtures').glob('*.tscn'))),4)
    def test_uid_is_only_allowed_in_exact_header(self):
        data=(ROOT/'fixtures/shore-rock-a.tscn').read_bytes()
        mutations=[
            data+b'\nresource_name = "uid://external"\n',
            data+b'\nmesh = ExtResource("x")\n',
            data+b'\n[ext_resource type="PackedScene" path="uid://external" id="x"]\n',
            data.replace(b'format=4 uid=',b'format=3 uid=',1),
            data.replace(b'uid://chjd0av3filv4',b'res://outside.tscn',1),
            data.replace(b'format=4 uid=',b'format=4 extra=1 uid=',1),
            data+b'\nvisible = false\n',
        ]
        for changed in mutations:
            with self.subTest(changed=changed[-100:]),self.assertRaises(ValueError):audit_candidate(changed,digest(changed))
    def test_remaining_only_entrypoint(self):
        source=(ROOT/'run_reopen.py').read_text()
        self.assertIn("for phase in ('reopen',):",source)
        self.assertNotIn("('--phase', 'convert')",source)
        self.assertIn("['--resume-artifact',str(args.artifact)]",source)
        self.assertNotIn("'--archive'",source)

if __name__=='__main__':unittest.main()
