#!/usr/bin/env python3
"""Official old Google Chrome package recovery, not system installation/signature attestation."""
import argparse, hashlib, json, os, pathlib, subprocess, tarfile, urllib.request
URL='https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_155.0.8059.39-1_amd64.deb'
PACKAGE_BYTES=143552428
BINARY_SHA='9bfb381296dffe75f3419d07b6cc64525105ed117d1453a4ef3b291cb97d2b58'
VERSION='Google Chrome 155.0.8059.39'
MAX_EXTRACTED=600*1024*1024
MAX_FILES=4096

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise ValueError('Unexpected official package redirect')

def relative_member(name):
    if not isinstance(name,str) or '\\' in name or name.startswith('/') or '\x00' in name:
        raise ValueError('Unsafe archive path')
    parts=name.split('/')
    if '..' in parts: raise ValueError('Archive parent traversal')
    path=pathlib.PurePosixPath(*[p for p in parts if p not in ('','.')])
    return path

def download(response,destination):
    if response.status!=200 or response.geturl()!=URL or response.headers.get('Content-Length')!=str(PACKAGE_BYTES):
        raise ValueError('Official package URL/status/size mismatch')
    sha=hashlib.sha256();count=0
    with destination.open('xb') as out:
        while True:
            b=response.read(min(1048576,PACKAGE_BYTES-count+1))
            if not b:break
            count+=len(b)
            if count>PACKAGE_BYTES:raise ValueError('Official package exceeds exact byte bound')
            sha.update(b);out.write(b)
    if count!=PACKAGE_BYTES:raise ValueError('Official package truncated')
    return {'url':URL,'bytes':count,'sha256':sha.hexdigest(),'publisher_independent_signature_verified':False}

def unpack_tar(raw,root):
    total=0;count=0;seen=set();prefix=pathlib.PurePosixPath('opt/google/chrome')
    with tarfile.open(fileobj=raw,mode='r|') as tar:
        for member in tar:
            path=relative_member(member.name)
            if not path.is_relative_to(prefix):continue
            if path in seen:raise ValueError('Duplicate Chrome archive member')
            seen.add(path);count+=1
            if count>MAX_FILES or member.size<0 or total+member.size>MAX_EXTRACTED:raise ValueError('Chrome extraction bound exceeded')
            target=root/path
            if member.isdir():target.mkdir(parents=True,exist_ok=True);continue
            if not member.isfile():raise ValueError('Chrome subtree link/device rejected')
            target.parent.mkdir(parents=True,exist_ok=True)
            source=tar.extractfile(member)
            if source is None:raise ValueError('Missing regular member')
            with source,target.open('xb') as out:
                remaining=member.size
                while remaining:
                    b=source.read(min(1048576,remaining))
                    if not b:raise ValueError('Truncated extracted member')
                    out.write(b);remaining-=len(b)
            # Ordinary task-owned files only, no uid/gid/setuid/security changes.
            target.chmod(0o755 if member.mode&0o111 else 0o644)
            total+=member.size
    return {'selected_prefix':str(prefix),'members':count,'regular_bytes':total,'not_system_install':True}

def file_sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def prepare(output):
    root=pathlib.Path(output);root.mkdir(parents=True,exist_ok=False)
    report={'passed':False,'scope':'official package recovery; raw package SHA is observed, not independently signed','url':URL}
    proc=None
    try:
        package=root/'official.deb'
        with urllib.request.build_opener(NoRedirect()).open(URL,timeout=30) as response:
            report['package']=download(response,package)
        with (root/'dpkg.log').open('wb') as log:
            proc=subprocess.Popen(['dpkg-deb','--fsys-tarfile',str(package)],stdout=subprocess.PIPE,stderr=log)
            try:
                report['extraction']=unpack_tar(proc.stdout,root/'unpacked');proc.stdout.close()
                if proc.wait(timeout=10)!=0:raise ValueError('dpkg-deb extraction failed')
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)
        binary=root/'unpacked/opt/google/chrome/chrome'
        report['binary_sha256']=file_sha(binary)
        if report['binary_sha256']!=BINARY_SHA:raise ValueError('Original observed Chrome binary SHA mismatch; not executed')
        result=subprocess.run([str(binary),'--version'],check=True,capture_output=True,text=True,timeout=10)
        report['version']=result.stdout.strip()
        if report['version']!=VERSION:raise ValueError('Exact original Chrome version mismatch')
        (root/'browser-path.txt').write_text(str(binary)+'\n');report['passed']=True
    except Exception as e:report['error']=repr(e)
    finally:
        report['dpkg_wait_completed']=proc is None or proc.poll() is not None
        (root/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();raise SystemExit(prepare(a.output))
