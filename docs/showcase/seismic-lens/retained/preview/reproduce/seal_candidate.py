"""Bind a reviewed local candidate and its installed wheel; never launches GIMP."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'source'
BASE='ea9270a82bd0821993f0c611d9cad2d36e06405d'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def row(path):
    data=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)), 'bytes':len(data), 'sha256':sha(data)}

def main():
    plugin_sha=sha((SOURCE/'bridge/gimp-plugin/dcc_mcp_gimp.py').read_bytes())
    binding=ROOT/'reproduce/binding.py'
    import re
    binding.write_text(re.sub(r"PLUGIN_SHA = '[^']*'", "PLUGIN_SHA = '"+plugin_sha+"'", binding.read_text()))
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=SOURCE,text=True).strip()
    base_tree=subprocess.check_output(['git','rev-parse',BASE+'^{tree}'],cwd=SOURCE,text=True).strip()
    names=subprocess.check_output(['git','ls-files','-z'],cwd=SOURCE).decode().split('\0')
    source_files=[]
    for name in names:
        if name:
            path=SOURCE/name
            item=row(path);item['path']=name;source_files.append(item)
    wheel=ROOT/'dist/dcc_mcp_gimp-0.4.1-py3-none-any.whl'
    installed=[]
    with zipfile.ZipFile(wheel) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith('dcc_mcp_gimp/'):
                data=archive.read(name)
                installed.append({'path':name.removeprefix('dcc_mcp_gimp/'),
                                  'bytes':len(data),'sha256':sha(data)})
    receipt={'schema':'gimp-preview-candidate-binding-v1',
             'base_commit':BASE,'base_tree':base_tree,
             'candidate_commit':commit,'candidate_tree':tree,
             'native_validation':'NOT_EXECUTED',
             'wheel':row(wheel),'installed_files':installed,'source_files':source_files,
             'input_files':[row(p) for p in sorted((ROOT/'inputs').iterdir()) if p.is_file()],
             'recipe_files':[row(p) for p in sorted((ROOT/'reproduce').glob('*.py'))]}
    (ROOT/'candidate-binding.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'candidate_commit':commit,'candidate_tree':tree,
                      'base_commit':BASE,'wheel_sha256':receipt['wheel']['sha256'],
                      'plugin_sha256':plugin_sha,'binding_sha256':sha((ROOT/'candidate-binding.json').read_bytes()),
                      'installed_files':len(installed),'source_files':len(source_files)},indent=2))

if __name__=='__main__':main()
