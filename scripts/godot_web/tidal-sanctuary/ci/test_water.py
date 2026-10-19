"""Water arithmetic regressions, not shader execution or rendered/audio proof."""
import math
import random
import struct
import unittest
from pathlib import Path


def f32(value):
    """Round every model operation to binary32 without a NumPy dependency."""
    return struct.unpack('!f', struct.pack('!f', value))[0]


def adjacent_f32(value, direction):
    value = f32(value)
    if value == 0:
        return struct.unpack('!f', struct.pack('!I', 1 if direction > 0 else 0x80000001))[0]
    bits = struct.unpack('!I', struct.pack('!f', value))[0]
    bits += 1 if (value > 0) == (direction > 0) else -1
    return struct.unpack('!f', struct.pack('!I', bits))[0]


def hash32(point):
    # The CPU's sin is not a GPU oracle. Identical lattice inputs guarantee
    # identical shader hash calls, independently of that implementation.
    dot = f32(f32(point[0]*f32(127.1))+f32(point[1]*f32(311.7)))
    value = f32(f32(math.sin(dot))*f32(43758.5453))
    return f32(value-math.floor(value))


def mix32(a, b, weight):
    return f32(f32(a*f32(1-weight))+f32(b*weight))


def interpolate32(point, corners):
    fractions = [f32(axis-math.floor(axis)) for axis in point]
    x, z = [f32(f32(axis*axis)*f32(3-f32(2*axis))) for axis in fractions]
    return mix32(mix32(corners[0], corners[1], x), mix32(corners[2], corners[3], x), z)


def reference_noise32(point):
    cell = tuple(float(math.floor(axis)) for axis in point)
    keys = [(f32(cell[0]+x), f32(cell[1]+z)) for x, z in ((0, 0), (1, 0), (0, 1), (1, 1))]
    return interpolate32(point, [hash32(key) for key in keys]), keys


def octave_coordinates32(point, time, scale, rates):
    """Original five sample coordinates: offset, scale, then time drift."""
    drift = tuple(f32(time*f32(rate)) for rate in rates)
    points = [point,
              (f32(point[0]+f32(.15)), f32(point[1]+0)),
              (f32(point[0]-f32(.15)), f32(point[1]-0)),
              (f32(point[0]+0), f32(point[1]+f32(.15))),
              (f32(point[0]-0), f32(point[1]-f32(.15)))]
    return [tuple(f32(f32(axis*f32(scale))+shift) for axis, shift in zip(p, drift)) for p in points]


def cached_octave32(points):
    origin = tuple(float(math.floor(min(p[axis] for p in points))) for axis in (0, 1))
    # GLSL matrices are indexed [column][row], hence [x][z].
    keys = [[(f32(origin[0]+x), f32(origin[1]+z)) for z in range(3)] for x in range(3)]
    lattice = [[hash32(key) for key in column] for column in keys]
    values, used_keys = [], []
    for p in points:
        cell = tuple(int(f32(math.floor(axis)-base)) for axis, base in zip(p, origin))
        if not all(index in (0, 1) for index in cell):
            raise AssertionError(f'Noise stencil exceeds its 3x3 lattice: {points}')
        corners = [(cell[0]+x, cell[1]+z) for x, z in ((0, 0), (1, 0), (0, 1), (1, 1))]
        values.append(interpolate32(p, [lattice[x][z] for x, z in corners]))
        used_keys.append([keys[x][z] for x, z in corners])
    return values, used_keys, sum(map(len, lattice))


def ripple_and_slopes32(low, high):
    ripples = [f32(f32(f32(a-f32(.5))*f32(.045))+f32(f32(b-f32(.5))*f32(.016)))
               for a, b in zip(low, high)]
    return ripples[0], f32(f32(ripples[1]-ripples[2])/f32(.3)), f32(f32(ripples[3]-ripples[4])/f32(.3))


def function_body(shader, name):
    start = shader.index('{', shader.index(name+'('))
    depth = 1
    for end in range(start+1, len(shader)):
        depth += (shader[end] == '{') - (shader[end] == '}')
        if depth == 0:
            return ''.join(shader[start+1:end].split())
    raise AssertionError(f'Unclosed shader function {name}')


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
    def assert_stencil_matches(self, point, time):
        point, time = tuple(map(f32, point)), f32(time)
        reference, cached = [], []
        hash_count = 0
        for scale, rates in ((.95, (.15, .06)), (2.3, (-.07, .11))):
            points = octave_coordinates32(point, time, scale, rates)
            original = [reference_noise32(p) for p in points]
            values, keys, count = cached_octave32(points)
            self.assertEqual(keys, [item[1] for item in original])
            self.assertEqual(values, [item[0] for item in original])
            reference.append([item[0] for item in original])
            cached.append(values)
            hash_count += count
        self.assertEqual(hash_count, 18)  # Original: five samples * two octaves * four corners = 40.
        self.assertEqual(ripple_and_slopes32(*reference), ripple_and_slopes32(*cached))

    def test_cached_stencil_matches_original_across_whole_water_and_time_range(self):
        randomizer = random.Random(97183)
        for _ in range(512):
            self.assert_stencil_matches((randomizer.uniform(-160, 160), randomizer.uniform(-160, 160)),
                                        randomizer.uniform(0, 3600))
        # Actual plane endpoints/grid rows, including the shader TIME rollover.
        for index in range(102):
            position = -160+320*index/101
            for time in (0., 32., 3600.):
                self.assert_stencil_matches((position, -160), time)
                self.assert_stencil_matches((160, position), time)
        self.assert_stencil_matches((-0., 0.), 0.)

    def test_cached_stencil_keeps_corners_at_lattice_and_offset_boundaries(self):
        for scale, rates in ((.95, (.15, .06)), (2.3, (-.07, .11))):
            for time in (0., .5, 31.999, 32., 3599.9, 3600.):
                drift = [f32(f32(time)*f32(rate)) for rate in rates]
                for cell in (-2, -1, 0, 1, 2):
                    for offset in (-.15, 0., .15):
                        # Put each original stencil point near an integer cell,
                        # including both sides of negative-coordinate boundaries.
                        point = [f32((math.floor(shift)+cell-shift)/f32(scale)+offset) for shift in drift]
                        for x in (adjacent_f32(point[0], -1), point[0], adjacent_f32(point[0], 1)):
                            for z in (adjacent_f32(point[1], -1), point[1], adjacent_f32(point[1], 1)):
                                self.assert_stencil_matches((x, z), time)

    def test_shader_uses_same_coordinates_interpolation_and_finite_differences(self):
        shader = (Path(__file__).parent.parent/'game/water.gdshader').read_text()
        self.assertEqual(function_body(shader, 'hash'), 'returnfract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);')
        stencil = function_body(shader, 'noise_stencil')
        self.assertIn('center=p*scale+drift;', stencil)
        for name, offset in (('positive_x', '+vec2(.15,0)'), ('negative_x', '-vec2(.15,0)'),
                             ('positive_z', '+vec2(0,.15)'), ('negative_z', '-vec2(0,.15)')):
            self.assertIn(f'{name}=(p{offset})*scale+drift;', stencil)
        self.assertIn('origin=floor(min(min(min(center,positive_x),negative_x),min(positive_z,negative_z)));', stencil)
        self.assertIn('mat3lattice=mat3(vec3(hash(origin),hash(origin+vec2(0,1)),hash(origin+vec2(0,2))),'
                      'vec3(hash(origin+vec2(1,0)),hash(origin+vec2(1,1)),hash(origin+vec2(1,2))),'
                      'vec3(hash(origin+vec2(2,0)),hash(origin+vec2(2,1)),hash(origin+vec2(2,2))));', stencil)
        self.assertEqual(stencil.count('hash('), 9)
        self.assertEqual(stencil.count('cached_noise2('), 5)
        self.assertIn('center_x=vec3(cached_noise2(center,origin,lattice),cached_noise2(positive_x,origin,lattice),'
                      'cached_noise2(negative_x,origin,lattice));', stencil)
        self.assertIn('z=vec2(cached_noise2(positive_z,origin,lattice),cached_noise2(negative_z,origin,lattice));', stencil)
        self.assertEqual(function_body(shader, 'cached_noise2'),
                         'ivec2cell=ivec2(floor(p)-origin);vec2f=fract(p);f=f*f*(3.0-2.0*f);'
                         'returnmix(mix(lattice[cell.x][cell.y],lattice[cell.x+1][cell.y],f.x),'
                         'mix(lattice[cell.x][cell.y+1],lattice[cell.x+1][cell.y+1],f.x),f.y);')
        vertex = function_body(shader, 'vertex')
        self.assertEqual(vertex.count('noise_stencil('), 2)
        self.assertIn('noise_stencil(world_position.xz,.95,vec2(TIME*.15,TIME*.06),low_center_x,low_z);', vertex)
        self.assertIn('noise_stencil(world_position.xz,2.3,vec2(-TIME*.07,TIME*.11),high_center_x,high_z);', vertex)
        self.assertIn('vec3center_x=(low_center_x-vec3(.5))*.045+(high_center_x-vec3(.5))*.016;', vertex)
        self.assertIn('vec2z=(low_z-vec2(.5))*.045+(high_z-vec2(.5))*.016;', vertex)
        self.assertIn('VERTEX.y+=center_x.x;', vertex)
        self.assertIn('floatdx=(center_x.y-center_x.z)/.3;', vertex)
        self.assertIn('floatdz=(z.x-z.y)/.3;', vertex)
        self.assertIn('NORMAL=normalize(vec3(-dx,1.0,-dz));', vertex)

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
