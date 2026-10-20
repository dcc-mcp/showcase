---
name: reaper-game-audio
description: Generate an original generic game-audio kit and validate individually rendered native REAPER assets.
license: MIT
metadata:
  dcc-mcp:
    dcc: reaper
    version: "0.1.0"
    tags: [audio, game, footsteps, ambience, loops, export]
    tools: tools.yaml
---
# Original game audio through REAPER

`generate_pack` synthesizes original deterministic source WAVs in the external adapter process, imports a real native REAPER asset-atlas session, creates individual regions, and saves a native RPP. `render_assets` exports those regions with REAPER's native renderer. Synthesis is mathematical source generation, not a bundled REAPER instrument or recorded field audio.

Requires an empty clean REAPER project, the external reapy transport, Python 3.9+ and NumPy. Destinations must be new. All source audio is original CC0; code MIT. No third-party samples or instruments are used. No private game project is needed or inspected.

The metadata separates unity authoring/import gain from recommended game-playback attenuation. Mono footsteps and SFX are suitable for positional playback; stereo ambience/music loops are intended as subtle non-spatial beds. Loop endpoints are sample-frame boundaries. Actual listening review is required before production use or public showcase approval.
