# Native Godot layered spell casting - review preview

![Native layered sigil and release](hero.jpg)

A 15-second native Godot preview connects layered palm/ground sigils, charge,
release, collision and decay, with event-driven magic audio. It has 450 frames
at 1280x720 / 30 fps. **Preview: human motion, picture and listening acceptance
remain pending; the prior film failed visual acceptance.** This is a new preview,
not an accepted final film or Web game.

[Watch preview](demo.mp4) | [Public procedural source kit](godot-mage-vfx.zip) |
[Self-contained manual](MANUAL.md) | [Capture recipe](capture_public.gd) |
[Validation](validation.json) | [Media evidence](public-media-evidence.json) |
[Manifest](manifest.json) | [Rights](LICENSES.md)

## Reproduce and tune

Extract the public kit and open project.godot in Godot 4.7.2. The 34-file kit uses
an original procedural mage; it contains no Hyper3D mesh, PBR or retargeted
character. The full 38-file mage project is retained locally with a separate
hash/validation receipt. The public character does not reproduce the rendered
mage performance. Open MANUAL.md for offline screenshots, parameters and steps.
Use your own authorized model with mage_scene, a Cast clip and RightCastSocket.
Copy complete scripts/shaders; keep damage, authoritative hits and movement in
game code. Disable auto_cast for deliberate Space/Q/E and palette1/2/3 tests.
Normal keyboard/mouse acceptance was not performed here.

The Surface, RuneOrbit and InnerSeal layers have separate masks and reveal/stop
lifecycle. Tune tint, radius, duration and auto_free; tune projectile speed and
lifetime. Cast release occurs at0.90 s in the1.85 s event timeline. Scene cue gain
is -4 dB. Close capture views use -8 dB because spatial audio becomes louder near
the mage. Local aura lights are unshadowed; the arena key light casts shadows.

## Native production and evidence

Godot4.7.2.stable.official.ed1daf0bf / Forward+ made every frame and sound cue.
The script/Skills source is dcc-mcp-godot0.9.12 candidate at
304e036575349b0b7f54f6c46d8a4be7667c6e4d; adapter PR97 remains Draft.
Skills godot-vfx/godot-shader are bundled with this source, not independently
released. Historical Core/Server0.20.48 and FFmpeg8.1.1 records remain scoped to
retained production history. Current native execution is direct script, not a
successful MCP tool-call or application-UI claim. Model/effort history is Unknown.

Three natural-animation-speed native performances are joined by hard cuts at
4.0 and9.5 seconds. The single view shows sigil/gather/release, the wide view
shows flight/contact, and the detail view shows layers/decay. The wide segment
was reused unchanged from this same run; only close camera framing/native gain
were corrected. Equal picture/audio prewarm is trimmed. No AI frames, retiming,
post-added spell cues or final fades are used. The exact local mage archive
passed save/exit/separate-process reopen, six presets and Windows debug export
with a300-frame headless EXE launch. Public kit checks are recorded separately.

Full450-frame decoding passed;51 samples and full-size frame380 were viewed.
Mix mean -28.8234 dBFS, peak -7.7633 dBFS; zero clipped samples. Metrics do not
replace listening. The outer release ring approaches the lower caption at
12.667 s. This limitation remains visible in the review preview.

The capture helper targets the locally retained mage_motion_study scene and its
authorized imported rig, which are excluded from the public kit. It now exits
after the requested frame reaches Movie Maker. A separate four-second capture
without --quit-after retained all120 picture frames plus30 prewarm frames and
exited; the published15-second preview was not rerendered for this helper fix.

## Boundaries

The intended project target is4.4; the tested host is4.7.2. Fixed-rate capture
is not measured realtime FPS, GPU budget or game-scale performance. No Web game,
physical-phone, normal input or deployed-player acceptance is claimed. Existing
MCP ownership_conflict is unresolved. Full reference motion was unavailable;
this preview does not claim a faithful reconstruction or final human approval.
The page has on-demand native playback/pause and explicit fallback links; static
and CI fixture checks are distinct from actual deployed playback. Crate50-frame
CI previously reported1 dropped frame; its failure and unchanged gate remain.
