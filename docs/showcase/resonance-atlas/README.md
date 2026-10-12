# Resonance Atlas

Three original acoustic vector posters: Phase / locked, Between / waves, After / sound.
Each is an illustrative mathematical schematic, not recorded acoustic data.

## Actual production

9 typed plans -> CLI/Gateway 0.20.42 -> Inkscape adapter source 498982a ->
Inkscape 1.4.4 native inkex effect -> editable SVG, 1587×2116 PNG, live PDF,
outlined SVG. 55 successful real gateway calls include native creation, export,
inspection/reopening and text outline verification.

Native CI proof: https://github.com/dcc-mcp/dcc-mcp-inkscape/actions/runs/38173127868

The adapter fix is an unmerged dependency (#3), not an official released fix.
No new third-party extension was required; the bundled native vector skill was
reused. Inkscape's historical Parametric Curves extension was reviewed for context.

## Film boundary

12 seconds, 1280×720, 24 fps, 288 frames, H.264, intentionally silent. It is a
composited assembly film of actual Inkscape PNG exports, not a screen recording.
Details are proportional crops of the same native image. Pillow composes; FFmpeg
encodes. No AI raster image, stock visual, or external soundtrack is used.

## Reproduce

Run generate_plans.py to create bounded JSON, not SVG. Use the native regression
harness from the exact adapter commit above in an operator-owned display with
private profile/workspace, or the linked review workflow. The harness creates
artwork/resonance-{1,2,3}-{01,02,03}.png alongside SVG and PDF. Run
`python compose_video.py OUTPUT_DIRECTORY --width 1280` against that output.
Only the local composition stage may run without an Inkscape display.

Public records deliberately omit raw host logs, absolute CI paths, process IDs,
and runtime registries. PDF font inspection and text extraction were performed.
Editable SVG and outlined SVG are both supplied; fonts are not bundled.

## Observed limits

- No persistent GUI document binding; this is native batch authoring.
- No acoustic simulation or measured scientific interpretation.
- The runtime validator permits a legacy flat width/height form, while the public
  MCP schema requires the canvas envelope. The initial caller mismatch was fixed
  in the fixture; it is not claimed as a new adapter security defect.
- The reused regression harness assumes text exists in every plan. The persistent
  series identity keeps every assembly stage text-bearing. Text-free generic
  fixtures would need a zero-default count in that harness.
- Model and reasoning-effort attribution is unknown without independent receipt.
