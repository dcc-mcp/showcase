#!/usr/bin/env python3
"""Fetch only pinned official Web templates; share the CI range-validation code."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from materialize_runtime import RemoteZip,URL
EXPECTED={
 'web_nothreads_release.zip':'1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9',
 'web_nothreads_debug.zip':'4a8a8ef7519637f7898fad25f09d3e466965e99c04e441682e1bc2d97a548922',
 'version.txt':'4855bd38072b77c73c45739cf6a6787d7df790a368b0a437102f352650e6186b'}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=True);record={'url':URL,'files':[]}
    with zipfile.ZipFile(RemoteZip()) as z:
        for name,sha in EXPECTED.items():
            info=z.getinfo('templates/'+name)
            if info.file_size>11*1024*1024 or info.compress_size>11*1024*1024:raise ValueError('Unexpected template member size')
            data=z.read(info)
            if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Official template hash mismatch: '+name)
            (out/name).write_bytes(data)
            record['files'].append({'name':name,'bytes':len(data),'sha256':sha,'crc32':info.CRC})
            print('Verified',name,len(data))
    (out/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
if __name__=='__main__':main()
