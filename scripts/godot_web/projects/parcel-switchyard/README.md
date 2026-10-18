# Parcel Switchyard: additive Web adapter

`parcel_game.gd` is byte-identical to the original case at PR #23 head
`943ee722deeec46d64890370fd813498eeebb01c`. `web.gd` inherits its order
sequence, six-parcel capacity, 3.5-second travel time, dispatch and scoring.
The original native project, source ZIP, PCK, screenshots, movie and MCP
receipts are retained under `docs/showcase/parcel-switchyard/` unchanged.

The adapter adds a 720 × 1320 portrait presentation, route/send/auto/pause/reset
controls, live desktop/phone reflow, and a read-only state report. Portrait
primary labels use at least 36 logical units; every actionable native rectangle
is at least 128 × 128 units. Small numbers on decorative moving parcels are
not primary labels. At a 320-pixel viewport with the shell's 12-pixel margins,
the expected minima are 14.8 CSS-pixel primary text and 46.0-pixel targets;
real-browser measurements remain an acceptance requirement.

The browser uses the existing Showcase tap/pan normalization: completed real
finger taps become canvas mouse input; drags scroll without issuing commands.
Native `InputEventScreenTouch` support is also implemented and separately
covered by synthetic engine-event regressions. Neither is a physical-device
acceptance claim. Keyboard 1/2/3 selects, Space sends, A toggles auto, P pauses,
and R starts a fresh shift. The game remains intentionally silent. Reload and
exit clear the session; persistence is not promised.

This adaptation was authored directly as GDScript and exported by the pinned
Godot CLI. Historical DCC-MCP receipts do not cover these new files. See the
pipeline README and `play/parcel-switchyard/export-provenance.json` for exact
source/output hashes, test scope and unresolved browser/visual review.

Rights remain as recorded in the original case; no new blanket license is
introduced. The retained original `LICENSES.md` describes the historical native
package. The optional Web distribution references the existing separately
licensed Godot runtime and its complete third-party notices in `play/runtime/`.

The Web adapter localizes inherited desktop drawing and the new phone controls
into English and Simplified Chinese. Chinese rendering uses the renamed OFL
Parcel Interface subset; complete notices and provenance are included. The same
subset is an explicit fallback for missing English symbols such as arrows,
while the original Latin face and its metrics are preserved.
The export explicitly includes its translation table and font notices, and the
exported PCK is reopened with Chinese enabled for all 118 headless regressions.
