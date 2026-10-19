# Dawnkeep acceptance observation contract

This is read-only observation from actual Godot runtime output, never an input
bridge. Tests send X11/XTest keyboard/mouse, Chromium keyboard/mouse, or
Chromium emulated touch. They must not call gameplay methods, inject state,
set variables, change browser storage, or invoke a scripted demonstration.

Main prints `DAWNKEEP_FRAME_READY {"schema":1}` only after a real
`RenderingServer.frame_post_draw`. At 4 Hz main prints `DAWNKEEP_STATE `
followed by JSON, with these fields (the full gameplay snapshot can add more):

- `schema: 1`, monotonically increasing positive `sample_id` and `physics_frame`
- `language: "en" | "zh"`; `paused: bool`; `phase`: actual gameplay phase
- `wave: int`, `gold: number`, `core_hp: number`
- `hero: {position: [x,y,z], level: int, xp: number}`
- `towers: array`; `enemies: array`
- `music: {unlocked: bool, muted: bool, playing: bool, peak_db: number}`
  Peak is measured on a dedicated actual audio bus, rather than inferred from
  player.playing. Runtime must not report sound when the stream is silent.
- `ui: {controls: {KEY: {x: number,y: number,w: number,h: number,enabled: bool}}}`
  Coordinates are viewport pixels for actual currently visible controls.
  Keys: `language`, `mute`, `pause`, `restart`, `start_wave`, `skill_1`,
  `skill_2`, `skill_3`, `equipment`, `build`, `upgrade`, `sell`.
  Optional `start` is clicked if present in an initial menu. Optional `resume`
  returns from a pause menu. Optional `confirm_restart` is used only if shown.
  Missing/hidden controls are omitted. Disabled controls are still described.
- `ui.minimap: {x,y,w,h}` describes the public, clickable minimap. Its linear
  world bounds are x [-17,17] and z [-11,11]. Tests click this visible map;
  observation never invokes the underlying move command.
- Optional `ui.pads`: array of `{id, x,y}` projected clickable support pads.
- Optional `ui.labels`: actual current rendered text, used for localization QA.

Keyboard contract: WASD/arrows move the hero; L switches EN/ZH; M toggles
music; Escape pauses/resumes; Q/E/R are hero abilities; Space starts a wave.
Restart uses the visible restart control and confirm_restart button; optional
Backspace may open the same confirmation.
Only the visible buttons are essential for core acceptance; movement requires
actual keys on desktop and actual terrain taps or a visible touch move control
on the emulated touch route. Native tests never claim physical-touch coverage.

The Web shell is layered around the official Godot export, not a replacement
engine/game. It provides `#dawnkeep-web-quit`, `#dawnkeep-web-restart`,
`#dawnkeep-web-fullscreen`, and `#dawnkeep-web-retry`. It reports lifecycle JSON
with `DAWNKEEP_WEB_...` prefixes. A trusted quit calls the official
`Engine.requestQuit()` and the actual onExit callback; restart creates a fresh
engine process via page reload. Loading retry is tested by failing an actual
PCK network request then pressing the visible Retry button.

## Evidence boundaries

Preview runs are short real rendered screenshot/input gates, not completion,
full audiovisual, full gameplay-balance, physical-phone, or deployed-site
acceptance. Full desktop runs require all eight waves, actual victory, a fresh natural AFK
defeat, and restart after both terminal states. Portrait remains a scoped
two-wave run. Full runs add skills/equipment/repeated and
invalid input, pause/resume/restart, desktop+portrait and EN+ZH, audio bus energy,
Web loading/retry/quit/restart/fullscreen, actual recordings and decode checks.
Listening to the final delivered soundtrack is a separate required review.
