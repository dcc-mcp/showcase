"""Inspect the portable GLB without running embedded content."""
import json,struct,sys,hashlib
from pathlib import Path
p=Path(sys.argv[1]);d=p.read_bytes();n=struct.unpack_from('<I',d,12)[0];j=json.loads(d[20:20+n]);offset=20+n;length=struct.unpack_from('<I',d,offset)[0];binary=d[offset+8:offset+8+length]
def acc(i):
 a=j['accessors'][i];v=j['bufferViews'][a['bufferView']];components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']];fmt={5126:'f',5123:'H',5125:'I'}[a['componentType']];size=struct.calcsize(fmt);stride=v.get('byteStride',size*components);off=v.get('byteOffset',0)+a.get('byteOffset',0)
 return [struct.unpack_from('<'+fmt*components,binary,off+k*stride) for k in range(a['count'])]
report={'file':p.name,'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest(),'glb_version':struct.unpack_from('<I',d,4)[0],'skins':len(j.get('skins',[])),'bones':len(j['skins'][0]['joints']),'meshes':len(j.get('meshes',[])),'material_count':len(j.get('materials',[])),'triangles':sum(j['accessors'][prim['indices']]['count']//3 for mesh in j['meshes'] for prim in mesh['primitives']),'embedded_images':len([im for im in j.get('images',[]) if 'bufferView' in im]),'external_uris':[ob['uri'] for arr in ['images','buffers'] for ob in j.get(arr,[]) if 'uri'in ob],'animations':{},'roots':[j['nodes'][i] for i in j['scenes'][0]['nodes']],'internal_path_strings':any(s in d for s in [b'/workspace/',b'asset-research',b'/home/agent'])}
for anim in j['animations']:
 item={'channels':len(anim['channels']),'start_seconds':min(acc(s['input'])[0][0] for s in anim['samplers']),'end_seconds':max(acc(s['input'])[-1][0] for s in anim['samplers']),'root_motion':[]}
 for ch in anim['channels']:
  node=j['nodes'][ch['target']['node']]
  if node.get('name')=='root' and ch['target']['path']=='translation':
   values=acc(anim['samplers'][ch['sampler']]['output']);item['root_motion']={'first':values[0],'last':values[-1],'delta':[b-a for a,b in zip(values[0],values[-1])]}
 report['animations'][anim['name']]=item
if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
