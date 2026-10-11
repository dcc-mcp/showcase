import bpy,json
s=bpy.context.scene
report={'objects':len(s.objects),'meshes':sum(o.type=='MESH' for o in s.objects),'curves':sum(o.type=='CURVE' for o in s.objects),'cameras':[o.name for o in s.objects if o.type=='CAMERA'],'materials':len(bpy.data.materials),'images':[{'name':i.name,'packed':bool(i.packed_file),'size':list(i.size),'filepath':i.filepath} for i in bpy.data.images if i.type!='RENDER_RESULT'],'water_beads':sum(o.name.startswith('Water bead') for o in s.objects),'rivulets':sum(o.name.startswith('Gravity rivulet') for o in s.objects),'render_engine':s.render.engine,'samples':s.cycles.samples,'resolution':[s.render.resolution_x,s.render.resolution_y]}
report['moods']=[]
for f in (1,2):
 s.frame_set(f);report['moods'].append({'frame':f,'lamp_watts':bpy.data.lights['Warm reading pool'].energy,'sky_watts':bpy.data.lights['Sky through rain'].energy})
s.frame_set(1)
print(json.dumps(report))
