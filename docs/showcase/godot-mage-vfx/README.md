# Mage casting and reusable Godot VFX

An editable Godot casting study using a Hyper3D mage, six portable effects and
native event-driven sound. **Draft: human audiovisual review and reference
fidelity remain unverified.** This is a scripted in-host demonstration.

![Native Godot spell contact](hero.jpg)

- [Natural-speed film with audio](demo.mp4): 1280x720, 30 fps, 480 frames;
  16-second video / 16.021-second container including AAC padding.
- [Native project ZIP](godot-mage-vfx.zip): 32 files; 18,756-triangle mage,
  20-joint local rig, embedded PBR maps and six reusable presets.
- [Shader manual](https://github.com/dcc-mcp/dcc-mcp-godot/blob/3422a8ebb87950c9ae9fce49ce7e0fb1f82b4837/docs/shader-manual.md),
  [source PR](https://github.com/dcc-mcp/dcc-mcp-godot/pull/97),
  [media evidence](public-media-evidence.json), [validation](validation.json),
  [manifest](manifest.json), [rights](LICENSES.md).

## Reproduce

Unzip, open project.godot in Godot 4.7.2, allow GLB import, and run the default
mage scene. Space casts; Q/E choose example combinations; 1/2/3 select palette.
These bindings are implemented but ordinary keyboard acceptance is not claimed.
The procedural character remains an alternative scene. See the included guides
for animation sockets, optional sound streams, lifecycle and gameplay contracts.

Reusable brief: combine the existing six native presets with an authorized
rigged mage; synchronize charge, release and actual contact with visual/audio
cues; retain editable resources and verify hit, miss and cleanup separately.

The local rig and Idle/Cast clip drive a copied finite animation timeline:
release at .90 animation seconds, recovery through 1.85. A miss has no contact
cue. The game owns damage, buffs, costs and input/combination windows. Original
short PCM cues can be replaced through three exported AudioStream properties.

[capture_public.gd](capture_public.gd) is the exact native Movie Maker observer.
It asserts imported_skeletal, the 20-joint rig and RightCastSocket, seeds particles
at 12345 and uses fixed capture framing. Capture each single 4 s, combo 5.5 s and
gallery 6.5 s at 30 fps after 1 s prewarm; trim the same prewarm from audio and video.
Two hard cuts and a final .4s fade join these native shots; no speed changes,
AI frames or post-added spell sounds. The capture helper replaces only the HUD.

## Actual verification and limits

Godot 4.7.2.stable.official.ed1daf0bf ran Forward+. The source candidate is
3422a8ebb87950c9ae9fce49ce7e0fb1f82b4837, based on package 0.9.12; Core and Server were 0.20.48.
FFmpeg 8.1.1-full_build-www.gyan.dev encoded the film. Agent model/effort records
are Unknown for all historical stages; they are not inferred from the output.

Fresh ZIP import, both mage routes, six presets and native repeated-cast tests
passed: seven releases, six contacts, one miss and transient cleanup. Custom
sound resources survived save/exit/separate-process reopen. Windows debug export
and a 300-frame headless executable launch passed; that does not establish
windowed rendering or input. The video fully decoded, and 54 unique sampled
frames were reviewed by the model. Audio peak was -20.74 dBFS, with zero clipped
samples; listening quality was not reviewed. At 10.667–10.767 s impact spokes
cross a readable gallery label. Human natural-speed audiovisual review remains
pending. The full circle-reference player was unavailable, so its dynamics,
exposure and lighting have not been matched frame by frame.

The local MCP fixture has an ownership-receipt conflict; no successful current
local bridge call is claimed. Target-device CPU/GPU budgets, Web, physical phones,
ordinary input and live bilingual player behavior are untested. This Draft PR
selects the case for the collection if later accepted; it is not a deployment.
