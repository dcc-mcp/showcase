"""Native CPU composition inspection; not a gameplay screenshot or MCP claim."""
import bpy,math,random,json
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(HERE/'dawnkeep-original.blend'))
ASSETS=HERE.parent/'game/assets/kaykit';rng=random.Random(18026)
for name in ['watchwood_tree','moonfern']:
 for o in list(bpy.data.collections[name].objects):bpy.data.objects.remove(o,do_unlink=True)
def pos(x,z,y=0):return Vector((x,-z,y))
def add_asset(file,p,scale=1,angle=0,clip=None):
 before=set(bpy.context.scene.objects);old_actions=set(bpy.data.actions)
 bpy.ops.import_scene.gltf(filepath=str((HERE.parent/'game/assets'/file) if file.startswith('original/') else (ASSETS/file)))
 imported=[o for o in bpy.context.scene.objects if o not in before]
 root=bpy.data.objects.new('Preview_'+Path(file).stem,None);bpy.context.collection.objects.link(root)
 for o in imported:
  if not o.parent:o.parent=root
 root.location=p;root.scale=Vector((scale,)*3);root.rotation_euler.z=angle
 if clip:
  arm=next(o for o in imported if o.type=='ARMATURE');actions=[a for a in bpy.data.actions if a not in old_actions]
  action=next(a for a in actions if a.name==clip or a.name.startswith(clip+'.') or a.name.startswith(clip+'_'))
  arm.animation_data_create();arm.animation_data.action=action
  for track in arm.animation_data.nla_tracks:track.mute=True
 return imported
# Same framing idea and same runtime source assets; sample battle arrangement.
for i,k in enumerate(['sunbow','ember','frost','storm']):
 old=pos(-5+i*4,7);new=pos(*[(-5,-7),(-5,-1),(5,-1),(10,2)][i])
 for o in bpy.data.collections['tower_'+k].objects:o.location+=new-old
for i,(x,z) in enumerate([(-15.4,-9.5),(-11.5,-10.1),(-7.7,-10.1),(-3.5,-9.8),(.2,-10.4),(5.5,-9.7),(9,-9.2),(12.3,-7.5),(15,-4.5),(-16,-3.7),(-16,.2),(-15.8,4.5)]):
 add_asset('forest/Tree_4_B_Color1.gltf' if i%3==1 else 'original/watchwood_tree.glb',pos(x,z),rng.uniform(.56,.7) if i%3==1 else rng.uniform(.8,1.0),rng.uniform(0,math.tau))
for i,(x,z) in enumerate([(-14,-9),(-9.4,-9.1),(-5.2,-9.6),(3,-10),(8.8,-8.6),(12.6,-6.3),(15.3,-1),(15.4,7.7),(12.8,9.4),(7,9.5),(1.4,9.5),(-5,9.3),(-10,10.1),(-14.2,10),(-15.2,2.4),(-12.3,-.6),(3,3.8),(1.5,-6.7)]):
 add_asset('original/moonfern.glb' if i%2==0 else 'forest/Bush_1_A_Color1.gltf',pos(x,z),rng.uniform(1.1,1.7) if i%2==0 else rng.uniform(2.1,3),rng.uniform(0,math.tau))
 for j in range(3):add_asset('forest/Grass_1_A_Color1.gltf',pos(x+rng.uniform(-1,1),z+rng.uniform(-1,1)),rng.uniform(.6,1.0),rng.uniform(0,math.tau))
hero=add_asset('characters/Knight.glb',pos(-6,0),1.06,.6,'Melee_1H_Attack_Chop')
for o in hero:
 if o.type=='MESH' and 'Cape' in o.name:
  m=bpy.data.materials.new('Original_orange_livery');m.diffuse_color=(.61,.14,.045,1);o.data.materials.clear();o.data.materials.append(m)
for i,(x,z) in enumerate([(-8,-3),(-8,-5),(-8,-7),(-10,-7),(-11,4),(-11,7)]):add_asset('characters/'+['Skeleton_Minion.glb','Skeleton_Warrior.glb','Skeleton_Rogue.glb'][i%3],pos(x,z),.9,.5,'Skeletons_Walking')
scene=bpy.context.scene;scene.frame_set(12)
scene.cycles.samples=24;scene.render.threads_mode='FIXED';scene.render.threads=2
scene.render.filepath=str(HERE/'evidence/native-composition.png');bpy.ops.render.render(write_still=True)
print('DAWNKEEP_NATIVE_COMPOSITION_RENDERED')
