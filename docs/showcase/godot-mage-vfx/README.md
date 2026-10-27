# Ritual mage casting and reusable Godot VFX

![Native Godot layered sigil](hero.jpg)

A Hyper3D mage drives three-layer auras, projectile contact and spatial magic
sound in an editable Godot study. The 15-second film is 1280x720 at 30 fps
(450 frames); it is a fixed-rate native Movie Maker capture, not a realtime
performance benchmark. **Draft: final listening and independent quality review
remain pending.**

[Film](demo.mp4) · [36-file native ZIP](godot-mage-vfx.zip) ·
[Shader manual](https://github.com/dcc-mcp/dcc-mcp-godot/blob/5998d429542022ab5c34da46e3ce70e0eabb5494/docs/shader-manual.md) ·
[Capture helper](capture_public.gd) · [Validation](validation.json) ·
[Media evidence](public-media-evidence.json) · [Manifest](manifest.json) ·
[Rights](LICENSES.md) · [Source PR](https://github.com/dcc-mcp/dcc-mcp-godot/pull/97)

## Reproduce and reuse

Extract the ZIP, import project.godot in Godot 4.7.2, then run its main scene.
The 4.4 project marker is an intended minimum, not a tested host. Disable
auto_cast for deliberate casts; Space casts, Q/E run examples, 1/2/3 select
palette. Physical-input acceptance is unverified. The alternative procedural
mage and six-preset gallery remain in the project. Copy complete effect folders
with their scripts/shaders. MANUAL.md includes local screenshots for offline use.

Reusable brief: attach an authorized rigged character, use animation-keyed
release and contact-keyed impact, keep damage/buffs in game code, and verify
misses, early stop, repeated play and cleanup. Surface, RuneOrbit and InnerSeal
have separate masks, heights, rotation, reveal envelopes and small inclinations.
Forty soft motes circulate around them. Hips, spine, shoulders and wrists add
support motion where the imported rig provides those bones. The source GLB
is unchanged. A procedural stone platform and columns, sky/fog and camera moves
replace the earlier plain stage. The platform top meets the character ground
reference; the contact core is shorter and smaller. Local aura light
is unshadowed; the arena key light casts shadows, not animated rune projections.

The native default mix layers low rumble and air for charge, a rush for release,
and a short crack/body/tail for contact. The user rejected the initial beep-like
mix and requested a softer subsequent version. Default sound_gain_db is now
-4 dB, 6 dB below that second candidate; optional AudioStream overrides remain.
The user subsequently requested a complete motion/picture revision. Final
audiovisual approval of this revised candidate is pending. The decoded final mix measures -29.22 dBFS
mean and -6.16 dBFS peak, with no clipped samples.

## Production and verification

Godot 4.7.2.stable.official.ed1daf0bf / Forward+ rendered the footage.
dcc-mcp-godot 0.9.12 is an editable unreleased candidate at 5998d429542022ab5c34da46e3ce70e0eabb5494.
Retained component records: Core/Server 0.20.48; FFmpeg 8.1.1-full_build-www.gyan.dev.
Historical model/effort attribution remains Unknown. No later model label is
used to fill missing production history.

The capture helper fixes cameras and particle seeds and asserts the imported
20-joint rig and RightCastSocket. Three separate performances are joined by
hard cuts: single 4 s, combo 5.5 s, detail 5.5 s. The same 1 s prewarm is removed
from picture and sound. No retiming, AI frames, final fade or post-added cues.
The close shots crop the distant target; the wide shot shows full contact.

The exact final ZIP passed fresh import, main entry, both character routes,
six presets, seven releases/six contacts/one miss and cleanup checks. Custom
audio and gain survived save/exit/separate-process reopen. Windows debug export
and a 300-frame headless EXE launch passed. All 450 film frames decoded and a
model reviewed 51 sampled frames; this is not independent human review.

## Boundaries

The reference's complete motion was unavailable; this is a research prototype,
not a high-fidelity recreation. No real-input, Web game, phone, concurrent-load
or realtime-FPS acceptance is claimed. The existing MCP fixture has an ownership
conflict; native CLI checks do not establish current MCP calls. The Draft is not
merged or deployed, and live bilingual player behavior remains unverified.
Hyper3D mesh/PBR provenance and software MIT rights are recorded separately.
No authenticated provider-account entitlement receipt was obtained.
