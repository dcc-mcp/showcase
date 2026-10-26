import io,pathlib,tarfile,tempfile,unittest
from unittest.mock import patch
import prepare_exact_chrome as p
class Response(io.BytesIO):
    status=200
    headers={'Content-Length':'3'}
    def geturl(self):return p.URL
class Contract(unittest.TestCase):
    def test_bad_paths(self):
        for name in ['/opt/google/chrome/x','../x','./opt/google/chrome/../../x','a\\b','a\x00b']:
            with self.assertRaises(ValueError):p.relative_member(name)
        self.assertEqual(str(p.relative_member('./opt/google/chrome/chrome')),'opt/google/chrome/chrome')
    def test_exact_size_and_truncation(self):
        for body,good in [(b'abc',True),(b'ab',False),(b'abcd',False)]:
            with tempfile.TemporaryDirectory() as td,patch.object(p,'PACKAGE_BYTES',3):
                if good:self.assertEqual(p.download(Response(body),pathlib.Path(td)/'p')['bytes'],3)
                else:
                    with self.assertRaises(ValueError):p.download(Response(body),pathlib.Path(td)/'p')
    def test_header_url_rejection_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            response=Response(b'abc');target=pathlib.Path(td)/'p'
            with self.assertRaises(ValueError):p.download(response,target)
            self.assertFalse(target.exists())
    def tar(self,kind='file',duplicate=False):
        b=io.BytesIO()
        with tarfile.open(fileobj=b,mode='w') as t:
            for _ in range(2 if duplicate else 1):
                i=tarfile.TarInfo('opt/google/chrome/chrome');i.mode=0o4755
                if kind=='file':i.size=3;t.addfile(i,io.BytesIO(b'abc'))
                else:i.type=tarfile.SYMTYPE;i.linkname='/outside';t.addfile(i)
        b.seek(0);return b
    def test_no_setuid_and_exact_selected_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);r=p.unpack_tar(self.tar(),root)
            self.assertEqual(r['regular_bytes'],3);binary=root/'opt/google/chrome/chrome';self.assertEqual(binary.read_bytes(),b'abc');self.assertEqual(binary.stat().st_mode&0o7777,0o755)
    def test_links_and_duplicates_rejected(self):
        for kind,duplicate in [('link',False),('file',True)]:
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError):p.unpack_tar(self.tar(kind,duplicate),pathlib.Path(td))
    def test_extracted_size_cap(self):
        with tempfile.TemporaryDirectory() as td,patch.object(p,'MAX_EXTRACTED',2):
            with self.assertRaises(ValueError):p.unpack_tar(self.tar(),pathlib.Path(td))
    def test_hash_checked_before_execution(self):
        source=pathlib.Path(p.__file__).read_text();self.assertLess(source.index("if report['binary_sha256']!=BINARY_SHA"),source.index("result=subprocess.run([str(binary),'--version']"))
    def test_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileExistsError):p.prepare(td)
if __name__=='__main__':unittest.main()
