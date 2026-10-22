"""Bounded PNG decoding to canonical RGBA, using only the Python standard library."""
import binascii
import hashlib
import struct
import zlib
from pathlib import Path


def decode_png(path):
    data = Path(path).read_bytes()
    if not (8 <= len(data) <= 32 * 1024**2 and data[:8] == b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Invalid or oversized PNG')
    pos, chunks, idat, palette, transparency = 8, [], bytearray(), None, b''
    width = height = depth = kind = interlace = None
    ended = False
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError('Truncated PNG chunk')
        size = struct.unpack('>I', data[pos:pos+4])[0]
        tag = data[pos+4:pos+8]
        end = pos + 12 + size
        if end > len(data):
            raise ValueError('Truncated PNG payload')
        payload = data[pos+8:pos+8+size]
        crc = struct.unpack('>I', data[pos+8+size:end])[0]
        if binascii.crc32(tag + payload) & 0xffffffff != crc:
            raise ValueError('PNG CRC mismatch')
        chunks.append(tag.decode('ascii'))
        if tag == b'IHDR':
            if width is not None or len(payload) != 13 or len(chunks) != 1:
                raise ValueError('Invalid IHDR')
            width, height, depth, kind, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            if not (0 < width <= 4096 and 0 < height <= 4096 and width * height <= 8_000_000):
                raise ValueError('PNG dimensions out of bound')
            if depth != 8 or kind not in (0, 2, 3, 4, 6) or compression or filtering or interlace:
                raise ValueError('Decoder requires noninterlaced 8-bit PNG')
        elif tag == b'IDAT':
            idat.extend(payload)
        elif tag == b'PLTE':
            if len(payload) % 3 or not 3 <= len(payload) <= 768:
                raise ValueError('Invalid palette')
            palette = [tuple(payload[i:i+3]) for i in range(0, len(payload), 3)]
        elif tag == b'tRNS':
            transparency = payload
        elif tag == b'IEND':
            if size or end != len(data):
                raise ValueError('Invalid PNG ending')
            ended = True
            break
        elif not tag[0] & 32:
            raise ValueError('Unknown critical PNG chunk')
        pos = end
    if not ended or width is None or not idat:
        raise ValueError('Incomplete PNG')
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[kind]
    stride = width * channels
    expected = (stride + 1) * height
    inflater = zlib.decompressobj()
    raw = inflater.decompress(bytes(idat), expected + 1)
    if len(raw) != expected or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError('Unexpected PNG decoded length')
    rgba = bytearray()
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        mode, row = raw[offset], bytearray(raw[offset+1:offset+1+stride])
        offset += stride + 1
        if mode > 4:
            raise ValueError('Unknown PNG filter')
        for i in range(stride):
            left = row[i-channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i-channels] if i >= channels else 0
            predictor = 0
            if mode == 1:
                predictor = left
            elif mode == 2:
                predictor = up
            elif mode == 3:
                predictor = (left + up) // 2
            elif mode == 4:
                p = left + up - upper_left
                a, b, c = abs(p-left), abs(p-up), abs(p-upper_left)
                predictor = left if a <= b and a <= c else (up if b <= c else upper_left)
            row[i] = (row[i] + predictor) & 255
        for i in range(0, stride, channels):
            pixel = row[i:i+channels]
            if kind == 6:
                rgba.extend(pixel)
            elif kind == 2:
                transparent = len(transparency) == 6 and tuple(pixel) == struct.unpack('>HHH', transparency)
                rgba.extend((*pixel, 0 if transparent else 255))
            elif kind == 0:
                transparent = len(transparency) == 2 and pixel[0] == struct.unpack('>H', transparency)[0]
                rgba.extend((pixel[0], pixel[0], pixel[0], 0 if transparent else 255))
            elif kind == 4:
                rgba.extend((pixel[0], pixel[0], pixel[0], pixel[1]))
            else:
                if palette is None or pixel[0] >= len(palette):
                    raise ValueError('Missing PNG palette entry')
                rgba.extend((*palette[pixel[0]], transparency[pixel[0]] if pixel[0] < len(transparency) else 255))
        previous = row
    return width, height, bytes(rgba)


def crop_rgba(decoded, x, y, width, height):
    w, h, pixels = decoded
    if not (0 <= x <= w-width and 0 <= y <= h-height):
        raise ValueError('Crop outside decoded image')
    return b''.join(pixels[((y+j)*w+x)*4:((y+j)*w+x+width)*4] for j in range(height))


def rgba_sha(decoded):
    return hashlib.sha256(decoded[2]).hexdigest()
