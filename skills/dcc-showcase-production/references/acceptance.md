# Acceptance: inspect what the audience will receive

## Native and audiovisual review

Inspect the actual final pixels and intermediate/native views at useful scale.
Check composition, legibility, materials, geometry, lighting, camera/framing,
artifacts and consistency with the concept. Record concrete defects and the
frames/views inspected. Independent visual and technical review have separate
scopes; model/effort labels never substitute for looking at the work.

Decode the entire delivered video, measure duration, dimensions, frame count,
codec and audio streams, and inspect start/middle/end plus transitions and any
suspect intervals. Verify the production frame sequence/timing, not only a few
thumbnails. Duplicate frames can be intentional holds; a unique-frame count
cannot prove native continuity or quality. Listen to the actual mix across its
whole duration for rhythm, clipping, distracting loops, abrupt cuts and sync.
If playback/listening was not possible, keep that stage `not-tested` or `blocked`.

The checker can run local `ffprobe` and full `ffmpeg` decode with
`--decode-video` (default one decoder thread; `--threads 1..8` is explicit).
It never downloads external assets, launches a host, or declares
continuity/listening/visual review passed. Keep independently observed results
bound to the exact delivered media hash, not an earlier encode.

## Godot and other interactive work

For native Godot menus/HUDs, use the [Native UI acceptance workflow](godot-native-ui.md#validate-the-settled-runtime-layout)
for effective visibility, common-coordinate rectangles, deferred Container
sorting, focus, and responsive evidence. An editor property dump is insufficient.

A scripted demonstration is not real input acceptance. In the actual engine,
exercise real keyboard/mouse and relevant touch input: main action, invalid
moves, undo/reset/restart, repeated actions, save/reload and resizing. Observe
state changes, visuals and logs. Record which input route was used; engine unit
tests and injected state changes remain separate from user interaction.

For Godot showcases deliver a Web playable when the intended case permits it.
Use this repository's `scripts/godot_web/README.md`, export/runtime manifest and
browser tests; do not substitute a visual imitation. Verify the native source,
exported Web build and packaged source match their recorded hashes. Test real
browser input, loading/retry, pause/resume, reset, fullscreen/exit, desktop/mobile
layout, audio unlock/mute, Back/Forward and all supported language controls.
A mobile viewport/emulated touch run is not a physical-device test. Record
those scopes separately, along with browser engine/version. A screenshot,
HTTP 200, exported PCK or JavaScript game clone is not a Godot Web
acceptance pass. Unsupported exports or inaccessible browser/native runs remain
explicit blockers. Browser success does not prove the native input path.

## Public delivery

Use `docs/showcase/CONTRACT.md` and existing validators unchanged for old cases:

```bash
python scripts/validate_entry.py docs/showcase/<slug>
python scripts/test_validate_collection.py
python scripts/validate_collection.py
python scripts/test_localization.py
python scripts/test_playable.py
python scripts/test_build_site.py
python scripts/build_site.py
```

Run other affected repository tests and the documented browser-preview workflow.
The builder only permits `_site` or `_site-*` under the checkout root. For a
read-only review, make an isolated snapshot first and build inside it; do not
loosen that guard to use an arbitrary output path. For a reviewed commit:

```bash
mkdir -p <temporary-directory>/review
git archive <reviewed-commit> | tar -x -C <temporary-directory>/review
cd <temporary-directory>/review
python scripts/godot_web/materialize_runtime.py
python scripts/build_site.py --out _site-review
```

If required bytes/tools cannot be obtained under current permissions, report
the build/browser stage blocked; don't substitute a different unreviewed build.
Test the
actual served detail page and gallery on desktop/mobile: search/filter/empty,
keyboard focus, Back/Forward, resource downloads/hash, video play/pause/resume/
seek and advancing decoded frames. Preview CI and local browser evidence do not
establish deployed-site behavior. Claim live playback only after checking the
actual public URL under the task's authorization.

Read `docs/LOCALIZATION.md`, `locales/config.json` and the builder's current
locale list; cover every supported locale, including UI, captions, alt text,
limitations, rights, model unknowns, errors and playable controls. Preserve stable
IDs, original evidence, source language, hashes and technical identifiers.

Review all selected public files, archives, visible pixels, metadata and native
project dependencies for secrets, private paths, personal data, internal asset
names/URLs and unrelated content. Hash the sanitized public bytes separately
from private originals. Keep internal competing-tool benchmarks outside selected
publication inventory and public source packages. Never distribute internal
Unreal projects or restricted asset libraries; use authorized derivatives and
safe recipes only when their rights have been checked. A hash scan alone cannot
certify privacy or licensing.

Deliver the case's scope, verified stages, unresolved stages, reproducible source,
review attribution, licenses and links. If contribution is authorized, search for
an existing matching Draft PR and reuse it. Check remote head and its CI; report
unrun checks. No merge/deployment follows from creating or approving a draft.
