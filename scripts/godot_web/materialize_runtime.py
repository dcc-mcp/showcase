#!/usr/bin/env python3
"""Materialize pinned official engine bytes into the static site source at build time.

No credentials, Godot editor, third-party hosting or runtime network request is needed.
HTTP ranges avoid fetching the 1.2 GB cross-platform export-template archive.
"""
import argparse,hashlib,io,json,tempfile,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
URL='https://godot-releases.nbg1.your-objectstorage.com/4.6.3-stable/Godot_v4.6.3-stable_export_templates.tpz'
TEMPLATE_SHA='1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9'
MEMBER='templates/web_nothreads_release.zip'

class RemoteZip(io.RawIOBase):
    def __init__(self):
        self.position=0
        with urllib.request.urlopen(urllib.request.Request(URL,method='HEAD'),timeout=60) as response:
            self.size=int(response.headers['Content-Length'])
        if self.size > 2_000_000_000: raise ValueError('Unexpected archive size')
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        self.position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        return self.position
    def read(self,length=-1):
        end=self.size if length<0 else min(self.position+length,self.size)
        if end<=self.position:return b''
        request=urllib.request.Request(URL,headers={'Range':f'bytes={self.position}-{end-1}'})
        with urllib.request.urlopen(request,timeout=180) as response:
            if response.status!=206:raise ValueError('Server did not honor HTTP range; refusing full archive')
            if response.headers.get('Content-Range') != f'bytes {self.position}-{end-1}/{self.size}':raise ValueError('Unexpected Content-Range')
            data=response.read(end-self.position+1)
        if len(data)!=end-self.position:raise ValueError('Truncated range response')
        self.position=end
        return data

def materialize():
    manifest=json.loads((ROOT/'play/manifest.json').read_text())
    expected={x['path']:x for x in manifest['files'] if x['path'].startswith('play/runtime/godot-4.6.3.')}
    names=['godot-4.6.3.js','godot-4.6.3.wasm','godot-4.6.3.audio.worklet.js','godot-4.6.3.audio.position.worklet.js']
    if set(expected) != {'play/runtime/'+name for name in names}:raise ValueError('Expected exactly four named official runtime assets')
    for path in expected:
        dest=ROOT/path
        if not dest.resolve().is_relative_to(ROOT) or any(p.is_symlink() for p in [dest,*dest.parents] if p.is_relative_to(ROOT)):raise ValueError('Runtime paths must stay inside the checkout without symlinks')
    def valid(path,entry):return path.is_file() and path.stat().st_size==entry['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
    if all(valid(ROOT/p,e) for p,e in expected.items()):print('Pinned Godot runtime already verified.');return
    with zipfile.ZipFile(RemoteZip()) as release:
        info=release.getinfo(MEMBER)
        if info.file_size > 11*1024*1024 or info.compress_size > 11*1024*1024:raise ValueError('Unexpected template member size')
        template=release.read(MEMBER) # Zip CRC is checked before the pinned cryptographic hash.
    if hashlib.sha256(template).hexdigest()!=TEMPLATE_SHA:raise ValueError('Official template SHA-256 mismatch')
    with zipfile.ZipFile(io.BytesIO(template)) as z:
        for path,entry in expected.items():
            name=Path(path).name.replace('godot-4.6.3.','godot.',1);data=z.read(name)
            if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Runtime byte mismatch: '+name)
            dest=ROOT/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    print('Materialized four SHA-256-verified Godot runtime files for same-origin Pages hosting.')
if __name__=='__main__':materialize()
