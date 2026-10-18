#!/usr/bin/env python3
"""Reproduce the renamed OFL subset from the hash-pinned system Noto collection."""
import argparse,hashlib,json
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools import subset
ROOT=Path(__file__).resolve().parents[3]
PROJECT=ROOT/'scripts/godot_web/projects/parcel-switchyard'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
 record=json.loads((PROJECT/'font-provenance.json').read_text())
 if hashlib.sha256(a.source.read_bytes()).hexdigest()!=record['source_sha256']:raise SystemExit('Pinned Noto source hash mismatch')
 translations=json.loads((PROJECT/'translations.json').read_text())
 text=''.join(translations)+''.join(translations.values())+''.join(chr(i) for i in range(32,127))+'×→↗•'
 font=TTFont(a.source,fontNumber=record['collection_index']);options=subset.Options();options.name_IDs=['*'];options.name_languages=['*']
 selection=subset.Subsetter(options=options);selection.populate(text=text);selection.subset(font)
 for name in font['name'].names:
  if name.nameID in [1,2,3,4,6,16,17]:name.string=('Regular' if name.nameID in [2,17] else 'Parcel Interface' if name.nameID in [1,4,16] else 'ParcelInterface-Regular').encode(name.getEncoding())
 cff=font['CFF '].cff;cff.fontNames=['ParcelInterface-Regular'];top=cff.topDictIndex[0];top.FamilyName='Parcel Interface';top.FullName='Parcel Interface Regular'
 font.save(PROJECT/'parcel-interface.otf')
 record['subset_sha256']=hashlib.sha256((PROJECT/'parcel-interface.otf').read_bytes()).hexdigest()
 (PROJECT/'font-provenance.json').write_text(json.dumps(record,indent=2)+'\n')
 print(record['subset_sha256'])
if __name__=='__main__':main()
