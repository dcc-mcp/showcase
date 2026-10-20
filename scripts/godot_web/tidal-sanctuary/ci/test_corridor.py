"""Bounded analytic/controller fixtures, never claims of actual hosted motion."""
import copy
import hashlib
import math
import unittest
from pathlib import Path
from corridor import ChartCorridor, FORBIDDEN, REGIONS, SOURCE_SHA256, inside_region, segment_enters_box
from exploration import CHART_CONTRACT

def state(n=1, frame=10, p=(1.3, 1., 9.), stage=1):
    return dict(sample_id=n,physics_frame=frame,position=list(p),quest_stage=stage,
                velocity=[0.,0.,0.],movement_input=[0.,0.])

def native_next(previous):
    s=state(previous['sample_id']+1,previous['physics_frame']+1,previous['position'])
    f=dict(physics_frame=s['physics_frame'],delta=1/60,before=previous['position'][:],after=s['position'][:],
           requested_velocity=[0.,0.,0.],velocity=[0.,0.,0.],movement_input=[0.,0.],max_slides=6,collisions=[])
    s['chart_motion']=dict(schema=2,contract=CHART_CONTRACT,source_sha256=dict(SOURCE_SHA256),frames=[f])
    return s

class CorridorTests(unittest.TestCase):
    def test_source_hashes_and_geometry_are_bound(self):
        game=Path(__file__).resolve().parents[1]/'game'
        for name,digest in SOURCE_SHA256.items():
            self.assertEqual(hashlib.sha256((game/name).read_bytes()).hexdigest(),digest)
        main=(game/'main.gd').read_text()
        self.assertIn('Vector3(.85,.7,.7)',main)
        self.assertIn('shape.radius=.22',main)
        self.assertEqual(FORBIDDEN,(.505,2.095,7.08,8.52))
    def test_whole_regions_and_convex_connections_clear_plinth(self):
        corners=lambda r:[[x,z] for x in r[:2] for z in r[2:]]
        for a in corners(REGIONS['southeast']):
            self.assertFalse(inside_region(a,FORBIDDEN))
            self.assertFalse(segment_enters_box([1.3,9],a))
            for b in corners(REGIONS['northeast']):self.assertFalse(segment_enters_box(a,b))
        for b in corners(REGIONS['northeast']):self.assertFalse(segment_enters_box(b,[-3.8,3.4]))
    def test_safe_endpoints_can_cross_and_tangent_is_not_clear(self):
        self.assertTrue(segment_enters_box([-1,9.5],[3.5,6]))
        self.assertTrue(segment_enters_box([2.095,6],[2.095,9]))
        self.assertTrue(inside_region([1.3,7.8],FORBIDDEN))
    def test_nonfinite_geometry_rejected(self):
        for p in ([float('nan'),8],[2,float('inf')],[True,8],[1]):
            with self.subTest(p=p),self.assertRaises(ValueError):inside_region(p,FORBIDDEN)
    def test_entry_must_be_actual_post_map_south(self):
        for s in (state(stage=0),state(p=(1.3,1,8.52)),state(p=(1.3,1,7.8))):
            with self.assertRaises(ValueError):ChartCorridor(s)
    def test_source_change_fails_closed(self):
        with self.assertRaises(ValueError):ChartCorridor(state(),{**SOURCE_SHA256,'main.gd':'0'*64})
    def test_browser_order_and_freshness(self):
        c=ChartCorridor(state());a=state(2,11,(2.6,1,9));c.observe(a)
        with self.assertRaises(ValueError):c.arrive('northeast',a)
        c.arrive('southeast',a)
        with self.assertRaises(ValueError):c.arrive('southeast',a)
        b=state(3,12,(2.6,1,6.4));c.observe(b);c.arrive('northeast',b)
        c.observe(state(4,13,(-3.8,1,3.4),2))
        self.assertTrue(c.finished);self.assertEqual(c.receipt['physics_segments'],0)
        self.assertIn('sparse',c.receipt['scope'])
    def test_actual_northeast_before_southeast_fails(self):
        c=ChartCorridor(state())
        with self.assertRaisesRegex(ValueError,"preceded southeast"):
            c.observe(state(2,11,(2.6,1,6.4)))

    def test_cache_without_both_regions_fails(self):
        c=ChartCorridor(state())
        with self.assertRaises(ValueError):c.observe(state(2,11,(-3.8,1,3.4),2))
    def test_stale_reordered_or_outside_arrival_fails(self):
        for s in (state(),state(2,9),state(0,11)):
            with self.assertRaises(ValueError):ChartCorridor(state()).observe(s)
        c=ChartCorridor(state());s=state(2,11,(2.34,1,9));c.observe(s)
        with self.assertRaises(ValueError):c.arrive('southeast',s)
        with self.assertRaises(ValueError):c.arrive('southeast',state())
    def test_native_contiguous_actual_segment(self):
        c=ChartCorridor(state(),SOURCE_SHA256);s=native_next(state());c.observe(s)
        self.assertEqual(c.receipt['physics_segments'],1)
    def test_native_missing_gap_duplicate_order_and_source_fail(self):
        for kind in ('missing','gap','duplicate','reverse','source','nan','disconnected'):
            c=ChartCorridor(state(),SOURCE_SHA256);s=native_next(state());f=s['chart_motion']['frames'][0]
            if kind=='missing':del s['chart_motion']
            elif kind=='gap':s['physics_frame']+=1;f['physics_frame']+=1
            elif kind=='duplicate':s['chart_motion']['frames'].append(copy.deepcopy(f))
            elif kind=='reverse':s['chart_motion']['frames']=[{**f,'physics_frame':12},f]
            elif kind=='source':s['chart_motion']['source_sha256']['main.gd']='0'*64
            elif kind=='nan':f['before'][0]=float('nan')
            else:f['before'][0]+=.01
            with self.subTest(kind=kind),self.assertRaises(ValueError):c.observe(s)
    def test_native_three_metre_domain_ends_proof_at_B_not_cache(self):
        initial=state();c=ChartCorridor(initial,SOURCE_SHA256);previous=initial
        def move_to(target):
            nonlocal previous
            start=previous['position'][:]
            steps=math.ceil(math.dist(start,target)/.08)
            for n in range(1,steps+1):
                current=native_next(previous)
                current['position']=[a+(b-a)*n/steps for a,b in zip(start,target)]
                current['chart_motion']['frames'][0]['after']=current['position'][:]
                # Match production's pre-move recording radius and clear outside.
                if math.hypot(previous['position'][0]-1.3,previous['position'][2]-7.8)>=3:
                    current['chart_motion']['frames']=[]
                c.observe(current);previous=current
        move_to([2.6,1,9]);c.arrive('southeast',previous)
        move_to([2.6,1,6.4]);c.arrive('northeast',previous)
        end=c.receipt['finished_at_sample'];count=c.receipt['physics_segments']
        move_to([-3.8,1,3.4])
        self.assertEqual(previous['chart_motion']['frames'],[])
        self.assertEqual(c.receipt['finished_at_sample'],end)
        self.assertEqual(c.receipt['physics_segments'],count)
        self.assertIn('not cache',c.receipt['proof_end'])
        self.assertIn('no every-physics',c.receipt['after_B'])
    def test_missing_native_domain_before_B_still_rejected(self):
        c=ChartCorridor(state(),SOURCE_SHA256);s=native_next(state())
        s['chart_motion']['frames']=[]
        with self.assertRaisesRegex(ValueError,'missing or unbounded'):c.observe(s)

    def test_native_segment_crossing_forbidden_box_fails(self):
        # Small real-sized step crosses the inflated boundary, not a teleport.
        initial=state(p=(2.1,1,8.53));c=ChartCorridor(initial,SOURCE_SHA256)
        s=native_next(initial);s['position']=[2.09,1,8.51];s['chart_motion']['frames'][0]['after']=s['position'][:]
        with self.assertRaises(ValueError):c.observe(s)

if __name__=='__main__':unittest.main()
