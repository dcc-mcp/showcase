"""Deterministic original input data, not a DCC operation or a physics solver."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil

ROOT = Path(__file__).parent / 'field-refinement-v2'
ROOT.mkdir(exist_ok=False)
assert shutil.disk_usage(ROOT).free > 1024**3
dimensions = [81,65,97]
spacing = [.05,.05,.025]
origin = [-2,-1.6,0]
travel, delay = array('d'), array('d')
for iz in range(dimensions[2]):
    z = origin[2] + iz*spacing[2]
    for iy in range(dimensions[1]):
        y = origin[1] + iy*spacing[1]
        for ix in range(dimensions[0]):
            x = origin[0] + ix*spacing[0]
            q = ((x-.2)/.9)**2 + ((y+.1)/.65)**2 + ((z-1.2)/.30)**2
            d = 220*math.exp(-q)
            delay.append(float(format(d,'.10g')))
            travel.append(float(format(.6+.4*z+.025*(x*x+y*y)-d/1000,'.10g')))
assert len(travel) == 510705
target = ROOT/'synthetic-lens-refined.vti'
with target.open('x') as out:
    out.write('<?xml version="1.0"?>\n<VTKFile type="ImageData" version="0.1" byte_order="LittleEndian">\n')
    out.write('<ImageData WholeExtent="0 80 0 64 0 96" Origin="-2 -1.6 0" Spacing="0.05 0.05 0.025">\n')
    out.write('<Piece Extent="0 80 0 64 0 96"><PointData Scalars="SyntheticTime_s">\n')
    for name, values in [('SyntheticTime_s',travel),('SyntheticDelay_ms',delay)]:
        out.write('<DataArray type="Float64" Name="'+name+'" NumberOfComponents="1" format="ascii">\n')
        out.write(' '.join(format(v,'.10g') for v in values)+'\n</DataArray>\n')
    out.write('</PointData><CellData/></Piece></ImageData></VTKFile>\n')
assert target.stat().st_size < 32*1024**2
metrics={'kind':'ORIGINAL_ANALYTIC_INPUT_GENERATION_NOT_NATIVE_PROOF',
    'dimensions':dimensions,'spacing':spacing,'origin':origin,'points':510705,'cells':491520,
    'bounds':[-2,2,-1.6,1.6,0,2.4],
    'why_refined':'Doubled x/y and quadrupled depth sampling relative to coarse pilot, keeping the same original analytic function and physical extent.',
    'formula_q':'q=((x-0.2)/0.9)^2+((y+0.1)/0.65)^2+((z-1.2)/0.30)^2',
    'formula_delay':'SyntheticDelay_ms=220*exp(-q)',
    'formula_time':'SyntheticTime_s=0.6+0.4*z+0.025*(x*x+y*y)-SyntheticDelay_ms/1000',
    'units':'Illustrative km; z positive down. Illustrative seconds/milliseconds.',
    'disclosure':'Synthetic analytic scalar illustration. No measured seismic data. No PDE or physics validation.',
    'array_ranges':{'SyntheticTime_s':[min(travel),max(travel)],'SyntheticDelay_ms':[min(delay),max(delay)]},
    'central_indices':{'x':44,'y':30,'z':48},
    'expected_central_slice_geometry':{'SectionX':{'points':6305,'triangles':12288},'SectionY':{'points':7857,'triangles':15360},'SectionZ':{'points':5265,'triangles':10240}},
    'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
    'native_ranges_and_counts_verified':False,'old_input_preserved':True,
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT/'input-manifest.json').write_text(json.dumps(metrics,indent=2)+'\n')
print(json.dumps(metrics))
