# Relic Courier: asset and source notices

Generated models, authored game work, controller code, font and sound effects
have separate rights. The repository's code license does not relicense the
generated models, upstream media or their trademarks.

## Hyper3D models and reference inputs

The model set comes from paid Hyper3D Rodin, Agentic, Bang and Texture API
workflows. Inputs include original text descriptions, original geometric
blockouts rendered for this case, and approved original ImageGen single-view
concepts for the courier and mechanical guardian. The courier concept received
a white-background cleanup preserving its design. No third-party character,
franchise or restricted model library was supplied as a reference input.

The earlier chest texture reference was a Hyper3D-generated render from an
original task-authored text prompt. It was not a manually painted or native
blockout image. The [hero acquisition receipt](diagnosis/hero-acquisition.public.json)
and [asset diagnosis](ASSET-DIAGNOSIS.md) distinguish inputs, immutable provider
outputs and later derivatives. Concept images are not gameplay captures.

The [Hyper3D Terms of Service](https://hyper3d.ai/legal/terms), checked on
2026-10-24, govern output use together with applicable agreements and rights.
Section 5(b) addresses Rodin output use subject to the Agreements, applicable
law and third-party terms. Section 6.3 restricts competing AI models/services and
requires recipients of permitted transfers to be notified of applicable
restrictions. The [copyright license](https://hyper3d.ai/legal/copyright-license)
and any applicable account agreement remain relevant. Generated models are not
offered here as MIT or CC0 assets. This case does not guarantee copyrightability,
uniqueness, exclusivity or absence of third-party rights.

## Authored derivatives and game work

Recorded Blender derivatives include mesh conversion, texture preparation,
the repaired shrine, column UVs/baked stone maps, character skeletons/weights
and animation clips. The interactive chest separates its lid and adds interior
surfaces while retaining the generated exterior and source material images.
The courier's five clips and guardian's four clips, skinning and chest interior
are authored additions, not provider-supplied animation or a new model purchase.
The original character images, UVs, mesh and material bindings are retained in
the recorded rig derivatives. The closed chest's real lid split and pivot are
authored geometry work; opening is driven by Godot rather than a provider clip.

Godot stage geometry, triplanar materials, lighting, collision proxies, AI,
gameplay rules, interface, persistence and VFX are authored work. Keep model
provenance and the native source's `notices/ASSET-RIGHTS.md` with redistributed
project files. Publication of a source archive does not grant additional model
rights.

## Controller adaptation

The movement controller adapts the axis, model rotation and `move_and_slide`
flow from [Kenney's Starter Kit 3D Platformer](https://github.com/KenneyNL/Starter-Kit-3D-Platformer).
That code retains MIT. Its source acquisition hash and full MIT notice are in
the game's `notices/` directory. No Kenney visual model or texture art is bundled.

## Font

Relic Sans is a renamed subset of Noto Sans CJK SC under SIL Open Font License
1.1. The game's `ui/` directory contains the complete OFL notice, upstream URL,
source/derivative hashes and glyph coverage receipt. The subset is not an
official Google or Noto product.

## Audio and engine

The game includes six unmodified effects from [Kenney RPG Audio](https://kenney.nl/assets/rpg-audio),
licensed CC0-1.0. Their exact source members, hashes and roles are in
`game/audio/AUDIO-SOURCES.json`; the complete notice is
`game/notices/KENNEY-RPG-AUDIO.txt`. These effects serve lid opening, confirmed
hits, pickup, equip, footsteps and melee swings. Native effects, Master-bus mute
and captured engine audio have separate runtime checks; source/license and
signal verification do not establish subjective listening acceptance.

Godot retains MIT and its third-party notices. Native authoring and standalone
play are separate configurations: the standalone project does not require the
DCC adapter used for typed authoring checks.

Hyper3D, Godot, Kenney and Noto names identify sources and tools. This independent
case does not claim endorsement by their owners.
