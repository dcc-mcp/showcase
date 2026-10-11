"""Tidal Cabinet: original parametric camera-library furniture concept. MIT."""
import FreeCAD as A, Part, Sketcher, MeshPart, json, os
from pathlib import Path
out=Path(__file__).resolve().parent
doc=A.newDocument('TidalCabinet')
p=doc.addObject('Spreadsheet::Sheet','Dimensions')
for row,(key,value) in enumerate([('Width',1080),('Depth',420),('Height',1040),('Panel',24),('Plinth',140),('Reveal',4)],1):
 p.set('A'+str(row),key);p.set('B'+str(row),str(value)+' mm');p.setAlias('B'+str(row),key)
p.setColumnWidth('A',130);p.setColumnWidth('B',95)
colors={}; visible=[]
wood=(0.52,0.29,0.13); teal=(0.07,0.23,0.25); brass=(0.68,0.49,0.20); felt=(0.20,0.24,0.23); dark=(0.07,0.08,0.09)
def box(name,xyz,size,col,expr=None):
 o=doc.addObject('Part::Box',name);o.Length,o.Width,o.Height=size;o.Placement.Base=A.Vector(*xyz)
 for prop,expression in (expr or {}).items():o.setExpression(prop,expression)
 colors[o.Name]=col;visible.append(o);return o
def shape(name,s,col):
 o=doc.addObject('Part::Feature',name);o.Shape=s;colors[o.Name]=col;visible.append(o);return o
def cyl(name,x,y,z,r,h,col):return shape(name,Part.makeCylinder(r,h,A.Vector(x,y,z)),col)
# Structural skeleton: spreadsheet expressions remain natively editable.
box('LeftCheek',(0,0,140),(24,420,900),wood,{'Height':'Dimensions.Height-Dimensions.Plinth','Width':'Dimensions.Depth','Length':'Dimensions.Panel'})
box('RightCheek',(1056,0,140),(24,420,900),wood,{'Placement.Base.x':'Dimensions.Width-Dimensions.Panel','Height':'Dimensions.Height-Dimensions.Plinth','Width':'Dimensions.Depth','Length':'Dimensions.Panel'})
box('Crown',(24,0,1016),(1032,420,24),wood,{'Length':'Dimensions.Width-2*Dimensions.Panel','Width':'Dimensions.Depth','Height':'Dimensions.Panel','Placement.Base.z':'Dimensions.Height-Dimensions.Panel'})
box('Sole',(24,0,140),(1032,420,24),wood,{'Length':'Dimensions.Width-2*Dimensions.Panel','Width':'Dimensions.Depth','Height':'Dimensions.Panel'})
box('Back',(24,402,164),(1032,18,852),teal,{'Length':'Dimensions.Width-2*Dimensions.Panel','Placement.Base.y':'Dimensions.Depth-18 mm','Height':'Dimensions.Height-Dimensions.Plinth-2*Dimensions.Panel'})
box('Partition',(636,25,164),(18,377,852),wood)
for z in [440,700]:box('Shelf'+str(z),(24,30,z),(612,372,18),wood)
for z in [330,496,662,828]:box('DrawerShelf'+str(z),(654,35,z),(402,367,16),wood)
# Four tapered steel legs and brass shoes, plus cross stretcher.
for x in [80,1000]:
 for y in [72,348]:
  shape('TaperedFoot',Part.makeCone(13,20,140,A.Vector(x,y,0)),teal)
  cyl('BrassShoe',x,y,0,13.5,22,brass)
box('Underframe',(65,60,119),(950,300,18),teal)
# Sliding fluted shutter over the left third; rounded vertical ribs catch the light.
box('Shutter',(30,-3,171),(282,20,838),teal)
for i in range(20):
 s=Part.makeCylinder(5.0,820,A.Vector(36+i*14,-4,180))
 shape('ShutterFlute%02d'%i,s,teal)
for z in [168,1009]:box('BrassTrack'+str(z),(26,-6,z),(608,7,3),brass)
shape('ShutterPull',Part.makeBox(8,20,100,A.Vector(289,-24,530)),brass)
# Drawer fronts: recessed horizontal grips and fine fluting.
for n,z in enumerate([171,337,503,669,835]):
 front=Part.makeBox(394,24,158,A.Vector(658,-3,z))
 grip=Part.makeBox(138,12,12,A.Vector(785,-4,z+124))
 front=front.cut(grip)
 shape('DrawerFront%d'%(n+1),front,teal)
 for i in range(28):
  reed=Part.makeCylinder(2.4,139,A.Vector(664+i*14,-3,z+7))
  clearance=Part.makeBox(144,24,18,A.Vector(782,-10,z+121))
  shape('DrawerReed%d_%02d'%(n+1,i),reed.cut(clearance),teal)
 box('DrawerGripLiner%d'%n,(786,6,z+125),(136,2,10),brass)
# Camera and lenses as neutral unbranded packing proxies.
for shelf,z in enumerate([183,477,737]):
 box('FeltMat%d'%shelf,(325,56,z-2),(284,280,4),felt)
 for i,(r,h) in enumerate([(34,93),(39,115),(29,74)]):
  x=359+i*92;y=168+(shelf%2)*22
  cyl('LensBody%d_%d'%(shelf,i),x,y,z,r,h,dark)
  for dz in [8,h*.45,h-12]:cyl('LensRing',x,y,z+dz,r+2,5,brass if dz==8 else dark)
  cyl('LensGlass',x,y,z+h,r-5,2,(0.10,0.25,0.29))
# Fully constrained profile for the removable equipment tray. Native Sketcher + Pad.
body=doc.addObject('PartDesign::Body','ServiceTray');sk=doc.addObject('Sketcher::SketchObject','TrayProfile');body.addObject(sk)
for pt,q in [((0,0),(270,0)),((270,0),(270,200)),((270,200),(0,200)),((0,200),(0,0))]:sk.addGeometry(Part.LineSegment(A.Vector(pt[0],pt[1],0),A.Vector(q[0],q[1],0)),False)
for i in range(4):sk.addConstraint(Sketcher.Constraint('Coincident',i,2,(i+1)%4,1))
for i in [0,2]:sk.addConstraint(Sketcher.Constraint('Horizontal',i))
for i in [1,3]:sk.addConstraint(Sketcher.Constraint('Vertical',i))
sk.addConstraint(Sketcher.Constraint('Coincident',0,1,-1,1));sk.addConstraint(Sketcher.Constraint('Distance',0,270));sk.renameConstraint(sk.ConstraintCount-1,'TrayWidth');sk.addConstraint(Sketcher.Constraint('Distance',1,200));sk.renameConstraint(sk.ConstraintCount-1,'TrayDepth')
pad=body.newObject('PartDesign::Pad','TrayBase');pad.Profile=sk;pad.Length=8;body.Placement.Base=A.Vector(337,78,1008);doc.recompute();colors[body.Name]=wood;visible.append(body)
doc.recompute();doc.Label='TIDAL / camera library';doc.CreatedBy='DCC-MCP showcase';doc.LastModifiedBy='DCC-MCP showcase';doc.Comment='Original concept, not a fabrication or load-bearing certification.'
doc.saveAs(str(out/'tidal.FCStd'))
# Mesh handoff records individual parts and RGB. No invented renderer geometry.
meshes=[]
for o in visible:
 m=MeshPart.meshFromShape(Shape=o.Shape,LinearDeflection=0.25,AngularDeflection=0.2,Relative=False)
 v,f=m.Topology
 meshes.append({'name':o.Name,'rgb':colors[o.Name],'vertices_mm':[[q.x,q.y,q.z] for q in v],'faces':f})
(out/'cad_meshes.json').write_text(json.dumps(meshes))
(out/'visible.json').write_text(json.dumps([o.Name for o in visible]))
(out/'build_metrics.json').write_text(json.dumps({'objects':len(doc.Objects),'visible_parts':len(visible),'sketch_dof':sk.FullyConstrained,'constraint_count':sk.ConstraintCount,'expressions':sum(len(o.ExpressionEngine) for o in doc.Objects),'volume_mm3':sum(o.Shape.Volume for o in visible),'valid':all(o.Shape.isValid() for o in visible)},indent=2))
print('BUILD_COMPLETE')
