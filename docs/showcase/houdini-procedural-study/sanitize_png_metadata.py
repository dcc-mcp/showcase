"""MCP automation fallback: remove only named PNG text metadata, never pixels.

Executed through houdini_automation__run_python_file with args containing
{source, target} records. Standalone import does not read or write files.
Uses only the Python standard library; preserves every IDAT byte.
"""
from pathlib import Path
import hashlib,struct,zlib

SIGNATURE=b'\x89PNG\r\n\x1a\n'
def digest(data): return hashlib.sha256(data).hexdigest()

def parse(data):
    if not data.startswith(SIGNATURE): raise ValueError('Invalid PNG signature')
    chunks=[];offset=8
    while offset<len(data):
        if offset+12>len(data): raise ValueError('Truncated chunk')
        size=struct.unpack('>I',data[offset:offset+4])[0]
        end=offset+12+size
        if end>len(data): raise ValueError('Truncated payload')
        kind=data[offset+4:offset+8];body=data[offset+8:offset+8+size]
        crc=struct.unpack('>I',data[offset+8+size:end])[0]
        if zlib.crc32(kind+body)&0xffffffff!=crc: raise ValueError('CRC mismatch')
        chunks.append((kind,body,data[offset:end]));offset=end
        if kind==b'IEND': break
    if offset!=len(data) or chunks[-1][0]!=b'IEND': raise ValueError('Invalid PNG ending')
    return chunks

def rgba_hash(chunks):
    header=next(body for kind,body,_ in chunks if kind==b'IHDR')
    width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',header)
    if depth!=8 or color not in (2,6) or compression or filtering or interlace:
        raise ValueError('Only verified non-interlaced 8-bit RGB/RGBA is supported')
    bpp=4 if color==6 else 3;stride=width*bpp
    stream=zlib.decompress(b''.join(body for kind,body,_ in chunks if kind==b'IDAT'))
    if len(stream)!=height*(stride+1): raise ValueError('Unexpected decoded length')
    previous=bytearray(stride);sha=hashlib.sha256()
    for row_index in range(height):
        start=row_index*(stride+1);mode=stream[start];row=bytearray(stream[start+1:start+1+stride])
        if mode>4: raise ValueError('Invalid row filter')
        for x in range(stride):
            left=row[x-bpp] if x>=bpp else 0;up=previous[x];upper_left=previous[x-bpp] if x>=bpp else 0
            if mode==1: add=left
            elif mode==2: add=up
            elif mode==3: add=(left+up)//2
            elif mode==4:
                predicted=left+up-upper_left
                distances=(abs(predicted-left),abs(predicted-up),abs(predicted-upper_left))
                add=(left,up,upper_left)[distances.index(min(distances))]
            else: add=0
            row[x]=(row[x]+add)&255
        if bpp==4: sha.update(row)
        else:
            for x in range(0,stride,3): sha.update(row[x:x+3]+b'\xff')
        previous=row
    return {'width':width,'height':height,'decoded_rgba_sha256':sha.hexdigest()}

def sanitize(source,target,remove_keywords=('Artist',)):
    source=Path(source);target=Path(target)
    if source.resolve()==target.resolve(): raise ValueError('Separate public copy required')
    raw=source.read_bytes();before=parse(raw);kept=[];removed=[]
    for kind,body,chunk in before:
        keyword=body.split(b'\x00',1)[0].decode('latin1') if kind in (b'tEXt',b'iTXt',b'zTXt') else None
        if keyword in remove_keywords: removed.append({'chunk':kind.decode(),'keyword':keyword})
        else: kept.append(chunk)
    public=SIGNATURE+b''.join(kept);after=parse(public)
    original_idat=b''.join(body for kind,body,_ in before if kind==b'IDAT')
    public_idat=b''.join(body for kind,body,_ in after if kind==b'IDAT')
    if original_idat!=public_idat: raise ValueError('IDAT changed')
    original_pixels=rgba_hash(before);public_pixels=rgba_hash(after)
    if original_pixels!=public_pixels: raise ValueError('Decoded pixels changed')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(public)
    if target.read_bytes()!=public: raise ValueError('Written public file mismatch')
    return {'source_file':source.name,'public_file':target.name,'source_bytes':len(raw),'public_bytes':len(public),'source_sha256':digest(raw),'public_sha256':digest(public),'idat_sha256':digest(original_idat),'idat_unchanged':True,'crc_validation':'pass','removed_metadata':removed,**original_pixels}

if 'args' in globals():
    result={'operation':'PNG metadata-only publication via DCC-MCP automation fallback','pixel_editing':False,'outputs':[sanitize(item['source'],item['target']) for item in args]}
