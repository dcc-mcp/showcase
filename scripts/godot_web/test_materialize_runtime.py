import io,unittest
from unittest.mock import patch
import materialize_runtime as module

class Response(io.BytesIO):
    def __init__(self,data=b'',status=200,headers=None):
        super().__init__(data);self.status=status;self.headers=headers or {}

class RangeContractTests(unittest.TestCase):
    def perform(self,response):
        with patch.object(module.urllib.request,'urlopen',side_effect=[Response(headers={'Content-Length':'100'}),response]):
            archive=module.RemoteZip();archive.seek(10);return archive.read(4)
    def test_exact_partial_response(self):
        self.assertEqual(self.perform(Response(b'abcd',206,{'Content-Range':'bytes 10-13/100'})),b'abcd')
    def test_unexpected_full_archive_rejected(self):
        with self.assertRaisesRegex(ValueError,'honor HTTP range'):self.perform(Response(b'abcd',200))
    def test_wrong_content_range_rejected(self):
        with self.assertRaisesRegex(ValueError,'Content-Range'):self.perform(Response(b'abcd',206,{'Content-Range':'bytes 0-3/100'}))
    def test_truncated_response_rejected(self):
        with self.assertRaisesRegex(ValueError,'Truncated'):self.perform(Response(b'abc',206,{'Content-Range':'bytes 10-13/100'}))
    def test_excess_response_rejected(self):
        with self.assertRaisesRegex(ValueError,'Truncated'):self.perform(Response(b'abcde',206,{'Content-Range':'bytes 10-13/100'}))
    def test_oversized_archive_rejected(self):
        with patch.object(module.urllib.request,'urlopen',return_value=Response(headers={'Content-Length':'3000000000'})):
            with self.assertRaisesRegex(ValueError,'size'):module.RemoteZip()

if __name__=='__main__':unittest.main()
