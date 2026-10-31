# First chapter audio

The bundled `field-of-dreams.ogg` is the existing house Vorbis derivative of
**The Field Of Dreams** by **pauliuw**, under CC0 1.0. The
[original source page](https://opengameart.org/content/the-field-of-dreams)
was checked on 2026-10-25. Its byte-for-byte SHA256 matches the house provenance:
`438e56482edc68ee6d86913fac2c14e5574afd71514771e8ff25d0f0053ab956`.
No audio recording was downloaded or altered for this candidate.

The existing **Determined Pursuit** by **Emma_MA** was also verified CC0 at its
[source page](https://opengameart.org/content/determined-pursuit-epic-orchestra-loop),
but its intense battle character is not selected for quiet route planning.
It is not copied into this candidate. Credits, original and derivative hashes,
and both audit decisions are retained in `SOURCE.json`.

The small `fifty/view/experience_audio.gd` Node uses the existing native
`AudioStreamPlayer` pattern without adding a framework or changing global audio
buses. It creates new bounded short feedback cues for pickup, door, purchase,
stairs, blocked action and combat. Dawnkeep's excluded original sound generator
and generated feedback were not copied.

The presenter adds the Node, calls `unlock_from_gesture()` from its first actual
button/input handler, then calls `play_feedback(kind)` after the authoritative
rule result. Feedback never changes rules or repeats an action. `set_muted(bool)`
and `set_volume(float)` control both music and effects. Default linear volume is
0.2, with an additional -8 dB music trim. No playback is requested before the
gesture call; unmuting does not unlock audio.

`unlocked` records an application request, not proof of a resumed browser audio
context. Godot parsing, actual audio output, first-gesture Web unlock, live
mute/volume input, subjective listening and the full 84.64-second loop seam
remain untested by this worker. No browser or Godot process was started.
