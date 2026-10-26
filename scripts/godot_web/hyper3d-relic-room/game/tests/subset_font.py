"""Rebuild the renamed OFL font and assert coverage of all GDScript UI text."""
import hashlib
import json
from pathlib import Path
import sys
from fontTools import subset
from fontTools.ttLib import TTFont

project = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1])
text = ''.join(path.read_text(encoding='utf-8') for path in sorted((project / 'scripts').glob('*.gd')))
text += ''.join(chr(value) for value in range(32, 127)) + '●○↑←↓→中文EN'
font = TTFont(source)
font.recalcTimestamp = False
options = subset.Options()
options.name_IDs = ['*']
options.name_legacy = True
options.name_languages = ['*']
selector = subset.Subsetter(options=options)
selector.populate(text=text)
selector.subset(font)
names = {1: 'Relic Sans', 3: 'RelicSans-Regular-20261024', 4: 'Relic Sans Regular',
         6: 'RelicSans-Regular', 16: 'Relic Sans', 17: 'Regular'}
for record in font['name'].names:
    if record.nameID in names:
        record.string = names[record.nameID].encode(record.getEncoding())
output = project / 'ui' / 'relic-sans.otf'
font.save(output)
cmap = font.getBestCmap()
required = {ord(char) for char in text if not char.isspace()}
missing = required - set(cmap)
assert not missing, 'Missing characters: %s' % sorted(missing)
receipt = {'source': 'https://github.com/notofonts/noto-cjk/blob/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf',
           'source_filename': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
           'family': 'Relic Sans', 'license': 'SIL OFL 1.1', 'output': output.name,
           'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'bytes': output.stat().st_size,
           'required_codepoints': len(required), 'missing_codepoints': []}
(output.parent / 'FONT-SOURCE.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt))
