"""Exact water fast-path bounds, not rendered performance or visual proof."""
import math
import random
import unittest
from pathlib import Path


def smoothstep(low, high, value):
    t = min(1., max(0., (value - low) / (high - low)))
    return t*t*(3-2*t)


def reference_height(x, z):
    angle = math.atan2(z/16.5, x/12.)
    coast = 1+.075*math.sin(angle*3+.6)+.055*math.sin(angle*7)+.025*math.cos(angle*11)
    radius = math.hypot(x/12., z/16.5)/coast
    north = 1-smoothstep(-10, 7, z)
    base = 1.45+3.25*north
    shoulder = .65*math.exp(-((x+5)/3.2)**2-((z+1.5)/6.5)**2)
    plateau = (1-smoothstep(-7, -4.5, z))*(1-smoothstep(4.2, 6, abs(x)))
    land = (base+shoulder)*(1-plateau)+4.55*plateau
    cove = 2.9*math.exp(-((x-8)/5.1)**2-((z-5)/4.5)**2)
    return -.60+(1-smoothstep(.83, 1.04, radius))*land-2.7*smoothstep(.98, 1.36, radius)-cove


class WaterFastPathTests(unittest.TestCase):
    def test_conservative_ellipse_only_skips_saturated_depth(self):
        self.assertGreater(2.468, (1.36*(1+.075+.055+.025))**2)
        randomizer = random.Random(81347)
        points = [(randomizer.uniform(-160, 160), randomizer.uniform(-160, 160)) for _ in range(10000)]
        for index in range(2048):
            angle = index*math.tau/2048
            for radius in (math.sqrt(2.468)-1e-7, math.sqrt(2.468), math.sqrt(2.468)+1e-7):
                points.append((12*radius*math.cos(angle), 16.5*radius*math.sin(angle)))
        for x, z in points:
            reference = max(0, -.15-reference_height(x, z))
            fast = 3.15 if (x/12)**2+(z/16.5)**2 >= 2.468 else reference
            if fast != reference:
                self.assertGreaterEqual(reference, 3.15-1e-12)
            self.assertEqual(1-smoothstep(.2, 3, reference), 1-smoothstep(.2, 3, fast))
            self.assertEqual(1-smoothstep(.02, .18, reference), 1-smoothstep(.02, .18, fast))

    def test_fleck_is_unused_beyond_swash_and_alpha_never_writes_prepass(self):
        for depth in (.18, .180001, .2, 1., 3., 100.):
            for fleck in (0., .5, .6, .72, 1.):
                self.assertEqual((1-smoothstep(.02,.18,depth))*smoothstep(.5,.72,fleck)*.23, 0.)
        for index in range(1001):
            shallows = index/1000
            self.assertLess(.94*(1-shallows)+.66*shallows, .99)

    def test_shader_keeps_exact_near_shore_and_no_negative_base_pow(self):
        shader = (Path(__file__).parent.parent/'game/water.gdshader').read_text()
        self.assertIn('if(dot(island_p,island_p)<2.468)', shader)
        self.assertIn('depth=max(0.0,-.15-ground_height(p))', shader)
        self.assertIn('if(depth<.18)', shader)
        self.assertNotIn('depth_prepass_alpha', shader)
        self.assertNotIn('pow(', shader)
        self.assertIn('ALPHA=mix(.94,.66,shallows)', shader)


if __name__ == '__main__':
    unittest.main()
