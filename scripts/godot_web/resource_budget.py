"""Keep the original engine/demo ceiling and separately bound promoted 3D assets."""
import gzip
from pathlib import Path
LEGACY_RAW = 40 * 1024 * 1024
LEGACY_GZIP = 11 * 1024 * 1024
# Dawnkeep adds a measured 5.1 MiB pack with licensed 3D art and two music tracks.
# It reuses the existing engine. This does not expand the legacy demos' budget.
ADDITIONAL = {'dawnkeep-defense': (6 * 1024 * 1024, 5 * 1024 * 1024)}

def measure(root, assets):
    groups = {'legacy': [0, 0], **{slug: [0, 0] for slug in ADDITIONAL}}
    for path in assets:
        group = next((slug for slug in ADDITIONAL if path.startswith('play/' + slug + '/')), 'legacy')
        data = (Path(root) / path).read_bytes()
        groups[group][0] += len(data)
        groups[group][1] += len(gzip.compress(data, mtime=0))
    return groups

def validate(groups):
    limits = {'legacy': (LEGACY_RAW, LEGACY_GZIP), **ADDITIONAL}
    if set(groups) != set(limits): raise ValueError('Unexpected resource-budget group')
    for name, (raw, compressed) in groups.items():
        if raw > limits[name][0] or compressed > limits[name][1]:
            raise ValueError(f'{name} playable resource budget exceeded: {raw} raw / {compressed} gzip')
    return groups
