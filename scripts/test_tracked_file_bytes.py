"""The shared matcher accepts only the exact object named by a strict pointer."""
import hashlib
import unittest

from tracked_file_bytes import MAX_LFS_POINTER_BYTES, matches_lfs_content


class LFSContentTests(unittest.TestCase):
    def pointer(self, data):
        return (f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(data).hexdigest()}\nsize {len(data)}\n').encode()

    def test_exact_content_and_empty_object_pass(self):
        for data in [b'original LFS payload', b'']:
            with self.subTest(data=data):
                self.assertTrue(matches_lfs_content(self.pointer(data), len(data), hashlib.sha256(data).hexdigest()))

    def test_size_and_same_size_hash_mismatches_fail(self):
        data = b'original LFS payload'
        for changed in [data + b'!', data[:-1], b'x' * len(data)]:
            with self.subTest(data=changed):
                self.assertFalse(matches_lfs_content(self.pointer(data), len(changed), hashlib.sha256(changed).hexdigest()))
        for size in [True, float(len(data)), -1]:
            with self.subTest(size=size):
                self.assertFalse(matches_lfs_content(self.pointer(data), size, hashlib.sha256(data).hexdigest()))

    def test_pointer_format_is_canonical(self):
        data = b'original LFS payload'
        pointer = self.pointer(data)
        digest = hashlib.sha256(data).hexdigest().encode()
        malformed = [pointer.replace(b'\n', b'\r\n'), pointer.rstrip(b'\n'),
                     pointer + b'extra\n', b'extra\n' + pointer,
                     pointer.replace(b'spec/v1', b'spec/v2'),
                     pointer.replace(b'oid sha256:', b'oid sha1:'),
                     pointer.replace(digest, digest.upper()),
                     pointer.replace(digest, b'g' * 64),
                     pointer.replace(b'size ', b'size 0'),
                     pointer.replace(b'size ', b'size +'),
                     pointer.replace(b'size ', b'size -'),
                     pointer.replace(f'size {len(data)}'.encode(), b'size ' + b'9' * 21)]
        for candidate in malformed:
            with self.subTest(pointer=candidate):
                self.assertFalse(matches_lfs_content(candidate, len(data), digest.decode()))

    def test_nonpointer_and_oversized_input_fail(self):
        for pointer in [b'', b'pointer', b'x' * (MAX_LFS_POINTER_BYTES + 1)]:
            with self.subTest(pointer=pointer):
                self.assertFalse(matches_lfs_content(pointer, 7, hashlib.sha256(b'payload').hexdigest()))


if __name__ == '__main__':
    unittest.main()
