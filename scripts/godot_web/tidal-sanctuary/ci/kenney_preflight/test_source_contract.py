import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from source_contract import read_sources

class SourceTests(unittest.TestCase):
    def fixture(self, root, entries):
        path=Path(root)/'source.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name,data in entries:z.writestr(name,data)
        plan={'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
              'assets':[{'source_file':'rock.glb','output':'rock.tscn','source_bytes':4,
                         'source_sha256':hashlib.sha256(b'glTF').hexdigest()}]}
        return path,plan
    def test_exact_unique_member_not_filesystem_extraction(self):
        with tempfile.TemporaryDirectory() as root:
            p,plan=self.fixture(root,[('Models/rock.glb',b'glTF')])
            actual=read_sources(p,plan)
            self.assertEqual(actual['rock.tscn']['bytes'],b'glTF')
            self.assertEqual(list(Path(root).iterdir()),[p])
    def test_wrong_archive_digest(self):
        with tempfile.TemporaryDirectory() as root:
            p,plan=self.fixture(root,[('rock.glb',b'glTF')]);plan['archive_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'archive SHA'):read_sources(p,plan)
    def test_ambiguous_missing_unsafe_size_and_byte_mismatch(self):
        cases=[([('a/rock.glb',b'glTF'),('b/rock.glb',b'glTF')],'ambiguous'),
               ([('other.glb',b'glTF')],'missing'),([('../rock.glb',b'glTF')],'Unsafe'),
               ([('/rock.glb',b'glTF')],'Unsafe'),([('a\\rock.glb',b'glTF')],'Unsafe'),
               ([('rock.glb',b'glTFextra')],'byte count'),([('rock.glb',b'FAIL')],'GLB SHA')]
        for entries,reason in cases:
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as root:
                p,plan=self.fixture(root,entries)
                with self.assertRaisesRegex(ValueError,reason):read_sources(p,plan)
    def test_duplicate_planned_output_fails(self):
        with tempfile.TemporaryDirectory() as root:
            p,plan=self.fixture(root,[('rock.glb',b'glTF')]);plan['assets']*=2
            with self.assertRaisesRegex(ValueError,'Duplicate output'):read_sources(p,plan)

if __name__=='__main__':unittest.main()
