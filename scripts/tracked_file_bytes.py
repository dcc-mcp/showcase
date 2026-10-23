"""Match hydrated content only against a canonical committed Git LFS pointer.

Callers own Git-object provenance, observed size/digest, bounded reads and
file type/mode checks. This matcher performs no IO or content hashing and
never invokes Git attributes or clean filters.
"""
import re


MAX_LFS_POINTER_BYTES = 256
_LFS_POINTER = re.compile(
    rb'version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize (0|[1-9][0-9]{0,19})\n')


def matches_lfs_content(pointer: bytes, size: int, sha256: str) -> bool:
    if len(pointer) > MAX_LFS_POINTER_BYTES or type(size) is not int:
        return False
    match = _LFS_POINTER.fullmatch(pointer)
    return bool(match and size == int(match[2]) and sha256 == match[1].decode('ascii'))
