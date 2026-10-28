# Godot Shader and spell VFX preview companion

This self-contained kit uses a procedural character. The 15-second rendered
mage preview is separate and pending human motion, picture and listening review.
The Hyper3D model/PBR and fitted animation asset are not redistributed here.

## Open, reproduce and edit

1. Extract the archive, import project.godot in Godot 4.7.2 and run the main scene.
2. Open mage_spells/combat_vfx_gallery.tscn to inspect mesh fire, particle fire,
   slash, impact, aura and projectile. Copy the complete folder and shader files.
3. On the casting root disable auto_cast for deliberate casts. Space casts,
   Q/E run examples and 1/2/3 change palettes. Real input was not tested here.
4. For your own authorized character, set mage_scene, a Cast animation and
   RightCastSocket. Preserve imported poses; bind release to the animation event
   and impact to actual collision. Runtime fallback is used if the contract fails.
5. Save project/scene edits, exit and reopen before exporting. Engine process
   checks are distinct from windowed input, Web export and target-device tests.

| Parameter | Meaning / demonstrated setting |
| --- | --- |
| tint | Palette shared by shader, particles and lights |
| radius | Aura size; separate Surface, RuneOrbit and InnerSeal layers |
| duration | Slash/impact lifetime; early stop must fade without brightening |
| auto_free | Cleanup ownership for transient effects |
| speed / lifetime | Projectile travel and miss cleanup |
| sound_gain_db | Scene default -4 dB; preview close cameras use -8 dB |
| auto_cast | Automatic demonstration versus deliberate input |
| mage_scene | Authorized imported rig; procedural fallback in this public kit |

The release event is 0.90 s in the 1.85 s casting timeline. Layered aura geometry
reveals and rotates independently; it is not a complex animated shadow projector.
Damage, buffs and authoritative hits remain gameplay responsibilities.

## Preview shots and versions

| Shot | Film interval | View |
| --- | --- | --- |
| Sigil, gather and release | 0-4 s | Close elevated camera, FOV 48 degrees |
| Flight and contact | 4-9.5 s | Wide view, FOV 49 degrees |
| Layers and decay | 9.5-15 s | Close elevated camera, FOV 52 degrees |

Godot 4.7.2.stable.official.ed1daf0bf / Forward+ produced 450 frames at 30 fps.
The film uses native audio and hard cuts; video/audio prewarm is trimmed equally.
No AI frames, post-added spell cues or playback-rate changes are used.
Skills godot-shader/godot-vfx ship with dcc-mcp-godot 0.9.12 source candidate
304e036575349b0b7f54f6c46d8a4be7667c6e4d; no independent Skill release is claimed.
The project/API target is 4.4; the actually tested host is 4.7.2.

![Native release](manual-images/godot-layered-release.jpg)
![Native contact](manual-images/godot-layered-contact.jpg)
![Native layered sigil](manual-images/godot-layered-sigil.jpg)

The close release ring approaches the lower caption at 12.667 s; this preview
is not a final quality pass. Full motion-reference footage was unavailable.
Fixed-rate Movie Maker rendering is not measured realtime FPS or GPU budget.
Native headless lifecycle/save/reopen/export checks do not prove MCP readiness,
normal keyboard/mouse, Web game execution, physical phones or human listening.

## Rights

Original kit software, effects and documentation use LICENSE (MIT). The rendered
mage is attributed to Hyper3D Rodin Gen-2.5; source redistribution permission is
not established, so model/PBR/retargeted character bytes are excluded. Motion
comes from Kay Lousberg's CC0 source; attribution does not turn Hyper3D output
into CC0 or MIT. No tutorial film or third-party texture database is included.
