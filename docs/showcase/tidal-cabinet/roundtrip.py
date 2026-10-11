import FreeCAD as A, Part, json
from pathlib import Path
out=Path(__file__).resolve().parent
d=A.openDocument(str(out/'tidal.FCStd'));names=json.loads((out/'visible.json').read_text());objs=[d.getObject(n) for n in names]
# Native expression behavior is tested, then restored before the final save.
before=d.RightCheek.Placement.Base.x
d.Dimensions.set('B1','1140 mm');d.recompute();after=d.RightCheek.Placement.Base.x
d.Dimensions.set('B1','1080 mm');d.recompute()
# A reversible presentation copy leaves the master assembly untouched.
e=A.newDocument('TidalExploded')
for i,o in enumerate(objs):
 c=e.addObject('Part::Feature',o.Name);c.Shape=o.Shape.copy()
 shift=A.Vector()
 if 'Drawer' in o.Name:shift=A.Vector(0,-200,0)
 elif 'Shutter' in o.Name:shift=A.Vector(-150,-140,0)
 elif o.Name in ['Crown','ServiceTray']:shift=A.Vector(0,0,160)
 elif o.Name=='LeftCheek':shift=A.Vector(-170,0,0)
 elif o.Name=='RightCheek':shift=A.Vector(170,0,0)
 c.Placement.Base=c.Placement.Base+shift
 e.recompute()
 assert abs(c.Shape.BoundBox.XMin-o.Shape.BoundBox.XMin-shift.x)<1e-6
 assert abs(c.Shape.BoundBox.YMin-o.Shape.BoundBox.YMin-shift.y)<1e-6
 assert abs(c.Shape.BoundBox.ZMin-o.Shape.BoundBox.ZMin-shift.z)<1e-6
e.CreatedBy='DCC-MCP showcase';e.LastModifiedBy='DCC-MCP showcase';e.saveAs(str(out/'tidal-exploded.FCStd'));A.closeDocument(e.Name)
compound=Part.makeCompound([o.Shape for o in objs]);compound.exportStep(str(out/'tidal.step'))
s=Part.Shape();s.read(str(out/'tidal.step'))
def measure(s):
 b=s.BoundBox
 return {'solids':len(s.Solids),'volume_mm3':s.Volume,'bbox_min_mm':[b.XMin,b.YMin,b.ZMin],'bbox_max_mm':[b.XMax,b.YMax,b.ZMax]}
v={'source':measure(compound),'step_reimport':measure(s),'expression_test':{'before_mm':before,'changed_mm':after,'restored_mm':d.RightCheek.Placement.Base.x},'sketch':{'fully_constrained':d.TrayProfile.FullyConstrained,'constraints':d.TrayProfile.ConstraintCount},'all_shapes_valid':all(o.Shape.isValid() for o in objs)}
v['volume_relative_error']=abs(s.Volume-compound.Volume)/compound.Volume
(out/'roundtrip.json').write_text(json.dumps(v,indent=2))
print(json.dumps(v))
A.closeDocument(d.Name)
