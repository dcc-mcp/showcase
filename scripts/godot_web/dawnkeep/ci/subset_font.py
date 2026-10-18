#!/usr/bin/env python3
"""Rebuild the renamed OFL subset from an installed official Noto CJK collection."""
import argparse, hashlib, json
from pathlib import Path
from fontTools.ttLib import TTCollection
from fontTools import subset
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--font',type=Path,required=True)
p.add_argument('--game',type=Path,required=True)
a=p.parse_args()
text=''.join(x.read_text() for x in sorted(a.game.glob('*.gd')))+'中文EN▲▼◀▶♪×0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
font=TTCollection(a.font).fonts[2]
options=subset.Options();options.name_IDs=['*'];options.name_legacy=True;options.name_languages=['*']
selector=subset.Subsetter(options=options);selector.populate(text=text);selector.subset(font)
names={1:'Dawnkeep Sans',3:'DawnkeepSans-Regular-20261018',4:'Dawnkeep Sans Regular',6:'DawnkeepSans-Regular',16:'Dawnkeep Sans',17:'Regular'}
for record in font['name'].names:
 if record.nameID in names:record.string=names[record.nameID].encode(record.getEncoding())
output=a.game/'ui/dawnkeep-sans.otf';font.save(output)
manifest={'source':'https://github.com/notofonts/noto-cjk','source_filename':a.font.name,'source_sha256':hashlib.sha256(a.font.read_bytes()).hexdigest(),'collection_font_index':2,'family':'Dawnkeep Sans','license':'SIL OFL 1.1','output':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size,'text_codepoint_count':len(set(text))}
(output.parent/'FONT-SOURCE.json').write_text(json.dumps(manifest,indent=2)+'\n')
