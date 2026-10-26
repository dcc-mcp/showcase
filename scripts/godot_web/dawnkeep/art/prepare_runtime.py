#!/usr/bin/env python3
"""Deterministic stdlib-only KayKit selection/GLB animation assembly.
Run: python prepare_runtime.py
No Blender, reskinning or retargeting: animation channels map by exact node name.
Only writes runtime-selected/ adjacent to this script; never edits a game repo.
"""
from pathlib import Path
import base64, copy, hashlib, json, mimetypes, shutil, struct, urllib.parse

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'runtime-selected'
ADVENTURERS = ROOT/'adventurers-free2.0/KayKit_Adventurers_2.0_FREE'
SKELETONS = ROOT/'skeletons-free1.1/KayKit_Skeletons_1.1_FREE'
FOREST = ROOT/'forest-free/KayKit_Forest_Nature_Pack_1.0_FREE'
ANIM = ROOT/'character-animations-free1.1/KayKit_Character_Animations_1.1'


def read_document(path):
    raw = path.read_bytes()
    binary = None
    if path.suffix.lower() == '.glb':
        magic, version, length = struct.unpack_from('<III', raw)
        assert (magic, version, length) == (0x46546C67, 2, len(raw))
        off = 12
        while off < len(raw):
            n, tag = struct.unpack_from('<II', raw, off)
            data = raw[off+8:off+8+n]
            if tag == 0x4E4F534A:
                doc = json.loads(data)
            elif tag == 0x004E4942:
                binary = data
            off += 8+n
    else:
        doc = json.loads(raw)
    buffers = []
    for b in doc.get('buffers', []):
        data = uri_data(path, b['uri']) if 'uri' in b else binary
        assert data is not None and len(data) >= b['byteLength']
        buffers.append(data[:b['byteLength']])
    return doc, buffers


def uri_data(path, uri):
    if uri.startswith('data:'):
        header, data = uri.split(',', 1)
        return base64.b64decode(data) if ';base64' in header else urllib.parse.unquote_to_bytes(data)
    assert not urllib.parse.urlparse(uri).scheme, 'Only bundled local assets are allowed'
    target = (path.parent/urllib.parse.unquote(uri)).resolve()
    assert target.is_relative_to(ROOT)
    return target.read_bytes()


class Assembly:
    def __init__(self, path):
        self.doc, buffers = read_document(path)
        assert len(buffers) == 1
        self.data = bytearray(buffers[0])
        self.provenance = [str(path.relative_to(ROOT))]
        self.animation_sources = {}

    def push_bytes(self, data, extras=None):
        self.data.extend(b'\0' * ((-len(self.data)) % 4))
        view = {'buffer': 0, 'byteOffset': len(self.data), 'byteLength': len(data)}
        if extras:
            view.update(extras)
        self.data.extend(data)
        views = self.doc.setdefault('bufferViews', [])
        views.append(view)
        return len(views)-1

    def importer(self, doc, buffers):
        view_map, accessor_map = {}, {}
        def view(index):
            if index not in view_map:
                v = doc['bufferViews'][index]
                off = v.get('byteOffset', 0)
                data = buffers[v.get('buffer', 0)][off:off+v['byteLength']]
                assert len(data) == v['byteLength']
                extras = {k: copy.deepcopy(value) for k, value in v.items()
                          if k not in ('buffer','byteOffset','byteLength')}
                view_map[index] = self.push_bytes(data, extras)
            return view_map[index]
        def accessor(index):
            if index not in accessor_map:
                a = copy.deepcopy(doc['accessors'][index])
                if 'bufferView' in a:
                    a['bufferView'] = view(a['bufferView'])
                if 'sparse' in a:
                    for field in ('indices','values'):
                        a['sparse'][field]['bufferView'] = view(a['sparse'][field]['bufferView'])
                values = self.doc.setdefault('accessors', [])
                values.append(a)
                accessor_map[index] = len(values)-1
            return accessor_map[index]
        return view, accessor

    def add_animations(self, source, names):
        doc, buffers = read_document(source)
        _, accessor = self.importer(doc, buffers)
        nodes = {n['name']: i for i, n in enumerate(self.doc['nodes']) if 'name' in n}
        assert len(nodes) == len(self.doc['nodes']), 'Target nodes must have unique names'
        by_name = {a['name']: a for a in doc['animations']}
        existing = {a['name'] for a in self.doc.get('animations', [])}
        for name in names:
            assert name in by_name, (source.name, name)
            assert name not in existing
            anim = copy.deepcopy(by_name[name])
            for sampler in anim['samplers']:
                sampler['input'] = accessor(sampler['input'])
                sampler['output'] = accessor(sampler['output'])
            for channel in anim['channels']:
                target = channel['target']
                old_name = doc['nodes'][target['node']]['name']
                assert old_name in nodes, (name, old_name)
                target['node'] = nodes[old_name]
            self.doc.setdefault('animations', []).append(anim)
            self.animation_sources[name] = str(source.relative_to(ROOT))
        self.provenance.append(str(source.relative_to(ROOT)))

    def attach_static(self, source, bone_name):
        """Append the official accessory in its original local coordinates at a handslot."""
        doc, buffers = read_document(source)
        assert not doc.get('skins') and not doc.get('animations') and not doc.get('extensionsRequired')
        view, accessor = self.importer(doc, buffers)
        image_map = {}
        for i, original in enumerate(doc.get('images', [])):
            image = copy.deepcopy(original)
            if 'uri' in image:
                uri = image.pop('uri')
                image['bufferView'] = self.push_bytes(uri_data(source, uri))
                image.setdefault('mimeType', mimetypes.guess_type(uri)[0] or 'image/png')
            else:
                image['bufferView'] = view(image['bufferView'])
            images = self.doc.setdefault('images', [])
            image_map[i] = len(images)
            images.append(image)
        sampler_offset = len(self.doc.setdefault('samplers', []))
        self.doc['samplers'].extend(copy.deepcopy(doc.get('samplers', [])))
        texture_offset = len(self.doc.setdefault('textures', []))
        for original in doc.get('textures', []):
            texture = copy.deepcopy(original)
            if 'source' in texture:
                texture['source'] = image_map[texture['source']]
            if 'sampler' in texture:
                texture['sampler'] += sampler_offset
            self.doc['textures'].append(texture)
        material_offset = len(self.doc.setdefault('materials', []))
        def remap_texture_info(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key.endswith('Texture') and isinstance(child, dict) and 'index' in child:
                        child['index'] += texture_offset
                    else:
                        remap_texture_info(child)
            elif isinstance(value, list):
                for child in value:
                    remap_texture_info(child)
        for original in doc.get('materials', []):
            material = copy.deepcopy(original)
            remap_texture_info(material)
            self.doc['materials'].append(material)
        mesh_offset = len(self.doc.setdefault('meshes', []))
        for original in doc.get('meshes', []):
            mesh = copy.deepcopy(original)
            for primitive in mesh['primitives']:
                primitive['attributes'] = {k: accessor(v) for k,v in primitive['attributes'].items()}
                if 'indices' in primitive:
                    primitive['indices'] = accessor(primitive['indices'])
                if 'material' in primitive:
                    primitive['material'] += material_offset
                for target in primitive.get('targets', []):
                    for key, value in target.items():
                        target[key] = accessor(value)
            self.doc['meshes'].append(mesh)
        node_offset = len(self.doc['nodes'])
        slot = next(i for i,n in enumerate(self.doc['nodes']) if n.get('name') == bone_name)
        for original in doc['nodes']:
            node = copy.deepcopy(original)
            node['name'] = 'equipment_'+node.get('name', source.stem)
            if 'mesh' in node:
                node['mesh'] += mesh_offset
            if 'children' in node:
                node['children'] = [i+node_offset for i in node['children']]
            self.doc['nodes'].append(node)
        source_roots = doc['scenes'][doc.get('scene', 0)]['nodes']
        self.doc['nodes'][slot].setdefault('children', []).extend(i+node_offset for i in source_roots)
        self.provenance.append(str(source.relative_to(ROOT)))

    def write(self, path):
        self.doc['buffers'] = [{'byteLength': len(self.data)}]
        self.doc.setdefault('asset', {})['generator'] = 'Dawnkeep stdlib exact-name GLB assembly 1.0'
        encoded = json.dumps(self.doc, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        encoded += b' ' * ((-len(encoded)) % 4)
        binary = bytes(self.data)+b'\0'*((-len(self.data)) % 4)
        length = 12+8+len(encoded)+8+len(binary)
        raw = (struct.pack('<III',0x46546C67,2,length)+struct.pack('<II',len(encoded),0x4E4F534A)+encoded
               +struct.pack('<II',len(binary),0x004E4942)+binary)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        # Reload and verify all index ranges / view spans, not only syntactic GLB validity.
        doc, buffers = read_document(path)
        for v in doc['bufferViews']:
            assert v.get('byteOffset',0)+v['byteLength'] <= len(buffers[v.get('buffer',0)])
        for a in doc['accessors']:
            if 'bufferView' in a:
                assert a['bufferView'] < len(doc['bufferViews'])
        for a in doc.get('animations', []):
            for s in a['samplers']:
                assert s['input'] < len(doc['accessors']) and s['output'] < len(doc['accessors'])
            for c in a['channels']:
                assert c['sampler'] < len(a['samplers']) and c['target']['node'] < len(doc['nodes'])
        return {'file': str(path.relative_to(OUT)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                'sources': list(dict.fromkeys(self.provenance)), 'animations': self.animation_sources}


def prepare_characters():
    records = []
    animation_dir = ANIM/'Animations/gltf/Rig_Medium'
    for name in ('Knight','Skeleton_Minion','Skeleton_Warrior','Skeleton_Rogue','Skeleton_Mage'):
        is_knight = name == 'Knight'
        source = (ADVENTURERS/'Characters/gltf' if is_knight else SKELETONS/'characters/gltf')/(name+'.glb')
        assembly = Assembly(source)
        selections = {
            'General': ['Idle_A','Hit_A','Death_A'],
            'MovementBasic': ['Walking_A','Running_A'],
            'CombatMelee': ['Melee_1H_Attack_Chop','Melee_1H_Attack_Slice_Diagonal','Melee_Blocking'],
        }
        if not is_knight:
            selections['Special'] = ['Skeletons_Idle','Skeletons_Walking','Skeletons_Death','Skeletons_Spawn_Ground']
        if name == 'Skeleton_Mage':
            selections['CombatRanged'] = ['Ranged_Magic_Shoot','Ranged_Magic_Spellcasting']
        for category, names in selections.items():
            assembly.add_animations(animation_dir/('Rig_Medium_'+category+'.glb'), names)
        if is_knight:
            records.append(assembly.write(OUT/'characters/Knight_Unarmed.glb'))
            assembly.attach_static(ADVENTURERS/'Assets/gltf/sword_1handed.gltf','handslot.r')
            assembly.attach_static(ADVENTURERS/'Assets/gltf/shield_badge.gltf','handslot.l')
        records.append(assembly.write(OUT/'characters'/(name+'.glb')))
    return records


def copy_forest():
    names = ['Tree_1_A_Color1','Tree_2_A_Color1','Tree_3_A_Color1','Tree_4_B_Color1',
             'Bush_1_A_Color1','Bush_2_A_Color1','Rock_1_A_Color1','Rock_2_A_Color1',
             'Grass_1_A_Color1','Grass_2_A_Color1']
    base = FOREST/'Assets/gltf'
    target = OUT/'forest'
    target.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in names:
        source = base/(name+'.gltf')
        doc = json.loads(source.read_bytes())
        candidates = [source]
        for resource in doc.get('buffers', [])+doc.get('images', []):
            uri = resource.get('uri')
            if uri and not uri.startswith('data:'):
                candidates.append((base/urllib.parse.unquote(uri)).resolve())
        for src in candidates:
            rel = src.relative_to(base)
            dst = target/rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src,dst)
            files[str(dst.relative_to(OUT))] = {'file':str(dst.relative_to(OUT)), 'bytes':dst.stat().st_size,
                'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(), 'source':str(src.relative_to(ROOT))}
    return [files[k] for k in sorted(files)]


def main():
    OUT.mkdir(exist_ok=True)
    characters = prepare_characters()
    forest = copy_forest()
    licenses = OUT/'licenses'
    licenses.mkdir(exist_ok=True)
    for name, base in [('Adventurers-2.0',ADVENTURERS),('Skeletons-1.1',SKELETONS),
                       ('Forest-1.0',FOREST),('Character-Animations-1.1',ANIM)]:
        shutil.copyfile(base/'License.txt', licenses/(name+'.txt'))
    manifest = {'method':'Exact-name animation channel remap; byte-preserving accessor/bufferView import; no re-rigging',
                'license':'CC0-1.0; original license files included',
                'knight_equipment':'Official sword_1handed in handslot.r and shield_badge in handslot.l, original local transforms',
                'characters':characters, 'forest':forest}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for item in characters:
        print(item['file'], item['bytes'], item['sha256'], ', '.join(item['animations']))
    print('Forest:',len(forest),'files (10 models + dependencies)')

if __name__ == '__main__':
    main()
