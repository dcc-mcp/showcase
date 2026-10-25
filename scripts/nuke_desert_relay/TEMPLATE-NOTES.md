# Deferred Nuke graph build / 延后宿主构建

This is an unexecuted builder with an explicit **Nuke 16.1v2 or 17.0v3** target,
using standard nodes. Both targets remain planned and unvalidated; adding the
17.0v3 target does not establish a Nuke 17 host run or pixel acceptance. It is
not a `.nk` deliverable, licensed-host test, rendered film, tracking solution,
or typed MCP success. No NukeX, CameraTracker, plugin, install, or network call
is requested. The graph builder never renders.

这是尚未在宿主执行的构建脚本，不代表已生成可重开 `.nk`、成片、跟踪结果或
MCP 验收。宿主窗口与许可必须由协调者另行确认；配置中的 `verified` 不能代替授权。

The production Skill and entry contract remain authoritative:
[production](../../skills/dcc-showcase-production/references/production.md),
[contract](../../docs/showcase/CONTRACT.md).

## Safe offline check

```powershell
python scripts/nuke_desert_relay/build_nuke.py --preflight --config scripts/nuke_desert_relay/build-config.json
```

Exit `2` with `status: blocked` is expected until all required assets and reviewed
calibration exist. Exit `0` means only that local prerequisites are present and
hashed. It does not import `nuke` or establish application compatibility.

After a fresh exact host grant and license verification, discover the actual
official Nuke scripting capability and inspect its current schema. Its trusted
runtime wrapper must verify the current coordinator grant and inject these
keyword arguments into `build(config_path, ...)`: `runtime_session_id`,
`expected_owner_id`, `expected_grant_id`, `expected_process_id`, and
`expected_window_handle`. Do not derive them from the config, copy them from an
old receipt, or invent/replay a tool slug from this document. The plain CLI
`--build` route is disabled, and unbound function calls fail before importing
`nuke`.

The private local config's `host_grant` must have `state: "granted"`, `grant_id`,
`owner_id`, `runtime_session_id`, integer `process_id` and `window_handle`, exact
`nuke_version` equal to the config's explicit allowlisted `target_nuke_version`,
explicit `starts_at_utc` and `ends_at_utc` ISO timestamps,
and `allowed_actions` containing `build_graph` and `save_native`. Keep that file
outside committed/public inventories; never put actual identities in a template.
The grant and externally injected bindings must match exactly. Missing/unknown
targets, target/grant mismatches and observed-version/grant mismatches are rejected;
no version-prefix matching or automatic fallback is allowed. The executing PID,
Nuke version, current UTC interval and live native HWND's owning PID are checked
before Root/node mutation and checked again before saving. A config change stops
the save. A config is not permission: the official wrapper must obtain fresh,
unrevoked coordinator authorization rather than treating this local guard as a
grant service. This builder currently requires a Windows GUI HWND and does not
silently switch to headless execution.

The builder also refuses a nonempty graph except for a default Viewer. It does
not clear an existing scene. A direct script run is not typed MCP coverage.

## Configuration contract

All paths are relative to the config directory; paths outside that directory are
rejected. Every input, mask curve script, and motion evidence file needs its exact
SHA-256. `verified: false` and absent files remain blockers. `native_output` must
be a single `.nk` basename in the config root, without directories. This keeps
the saved Root's project directory aligned with relative asset paths. Existing
native files are never overwritten; choose a versioned basename.

```json
{
  "schema_version": 1,
  "target_nuke_version": "17.0v3",
  "frame": {"width": 1280, "height": 720, "fps": 30, "first": 1, "last": 240},
  "inputs": {
    "plate": {"path": "assets/plate-8s.mp4", "sha256": "fill-with-observed-hash"},
    "sky": {"path": "assets/ai-sky.png", "sha256": "fill-with-observed-hash"},
    "ruins": {"path": "assets/ai-distant-ruins-clean.png", "sha256": "fill-with-cleaned-layer-hash"}
  },
  "plate_check": {"verified": false, "sha256": "fill-with-observed-clip-hash", "width": 1280, "height": 720, "fps": 30, "frames": 240},
  "colorspaces": {"plate": "rec709", "sky": "sRGB", "ruins": "sRGB", "cg": "linear", "output": "rec709"},
  "color_pipeline_verified": false,
  "ruins_edge_cleanup_verified": false,
  "ruins_edge_cleanup": {
    "verified": false,
    "raw_input": {"path": "assets/ai-distant-ruins.png", "sha256": "retain-original-raw-hash"},
    "cleaned_input": {"path": "assets/ai-distant-ruins-clean.png", "sha256": "fill-with-cleaned-layer-hash"},
    "method": "Record the actual cleanup after it occurs",
    "evidence": {"path": "calibration/ruins-edge-review.json", "sha256": "fill-after-actual-pixel-review"}
  },
  "masks": {
    "sky": {"verified": false, "first": 1, "last": 240, "coordinate_system": "nuke-bottom-left", "curves_script": {"path": "calibration/sky.curves", "sha256": "fill-after-native-Roto-export"}},
    "holdout": {"verified": false, "first": 1, "last": 240, "coordinate_system": "nuke-bottom-left", "curves_script": {"path": "calibration/holdout.curves", "sha256": "fill-after-native-Roto-export"}}
  },
  "motion": {"mode": "lockoff", "verified": false, "max_residual_px": null, "evidence": {"path": "calibration/motion.json", "sha256": "fill-after-measurement"}},
  "cg": {"mode": "still", "beauty": {"path": "renders/prop-beauty.0001.exr", "sha256": "fill-after-render"}, "shadow": {"path": "renders/contact-shadow.0001.exr", "sha256": "fill-after-render"}, "linear_verified": false, "alpha_verified": false, "premultiplied": true, "shadow_white_is_unshadowed": true, "shadow_alpha_association": "premultiplied-factor", "shadow_alpha_association_verified": false},
  "placement": {
    "sky": {"verified": false, "translate": [0, 0], "scale": 1, "rotate": 0, "center": [640, 360]},
    "ruins": {"verified": false, "translate": [0, 0], "scale": 1, "rotate": 0, "center": [640, 360]},
    "prop": {"verified": false, "translate": [0, 0], "scale": 1, "rotate": 0, "center": [640, 360]}
  },
  "grade": {"multiply": [1, 1, 1], "prop_gain_amplitude": 0.015},
  "native_output": "nuke-desert-relay-v001.nk"
}
```

The sample colorspace names are proposed Nuke-native enum values, **not observed
installed names**. Build checks the actual enum and fails when a name is absent;
there is no fallback to another color interpretation or an unknown OCIO config.
Verify plate Rec.709 transfer versus a monitor-only BT.709 tag, sRGB generated
images, scene-linear EXR, read premultiplication and Rec.709 display output in the
granted host before changing `color_pipeline_verified`.

The raw generated ruin has an observed colored-edge failure. Color management
verification alone cannot clear it. Preserve the raw input and its original
hash, create a distinct cleaned RGBA layer, inspect the actual edge on light and
dark backgrounds, and supply a hashed cleanup review. That JSON must contain
`status: "passed"`, `scope: "rgba-edge-cleanup"`, the exact `raw_sha256` and
`cleaned_sha256`, and `reviewed_backgrounds` containing `light` and `dark`.
`inputs.ruins` must equal the distinct `cleaned_input` record; it cannot silently
point back to the failed raw layer. Both `ruins_edge_cleanup_verified` and the
cleanup record's `verified` remain false until the actual repair and review.
Those declarations and hashes are prerequisite evidence, not an automatic
judgment of pixel quality. Retain the original failure beside the later result.

For animated CG set `cg.mode` to `sequence`. Each CG media record then requires
`pattern: "renders/prop-beauty.%04d.exr"` (or shadow pattern) and `files`, an ordered
array of 240 `{path, sha256}` records for frames 1 through 240. A missing sequence
never silently becomes a still. `still` explicitly holds one actual EXR through
the whole shot and records `static_3d_insert: true`; no continuous 3D animation is
claimed. The small optional prop gain animation is a Nuke grade, not 3D lighting
interaction. Temporal source footage remains the original real plate sequence.

`lockoff` requires a measured maximum residual no greater than 0.5 px over the
selected plate. Larger motion requires `similarity`, verified perspective/parallax
suitability, and exactly 240 `{frame, tx, ty, rotation, scale}` samples in Nuke
pixel/bottom-left conventions. OpenCV analysis alone does not verify native Nuke
tracking or camera solving. This script deliberately does not apply guessed lens
distortion or turn a similarity transform into a 3D camera solve.

Create and inspect the sky and foreground holdout with editable native Nuke Roto
shapes, then export each trusted `curves` knob's `toScript()` bytes, hash them, and
supply those files. Build imports them with `fromScript()`. No placeholder sky
polygon, fabricated solved mask, or empty unverified mask passes preflight. A
legitimately empty holdout still needs a checked native curve script and the same
frame-range evidence. Follow privacy review for any curve expressions.

## Graph and review outputs

The graph reads the plate, sky and edge-reviewed premultiplied RGBA ruin; applies reviewed
placement/motion; merges the sky through its Roto; adds the distant ruin; multiplies
the white-neutral RGB contact-shadow pass; overs the premultiplied CG beauty;
restores original plate pixels through the foreground holdout; and applies a
documented final RGB grade. The holdout preserves genuine foreground occlusion.

The contact-shadow input must be a verified coverage-premultiplied factor:
`A_rgb=a*f`, where `a` is coverage and `f=1` is unshadowed. The builder transforms
that pass, then overs it onto a root-format opaque white RGBA Constant to produce
`F_rgb=A_rgb+(1-a)`. The resulting factor is bounded to the white B input's full
format. Contact-shadow multiply writes RGB only, preserving the incoming plate
composite's alpha. This prevents transparent black outside a transformed pass
from multiplying the plate to black, and preserves partial-coverage edges.
`shadow_alpha_association_verified` remains false until the actual exported pass
and Nuke readback establish this convention; this is not a claim that an untested
Blender shadow-catcher output already meets it.

The independent counterexample uses an allowed 0.5 placement scale: the pass
occupies `[320,180,960,540]` in the 1280×720 frame. At `(100,100)`, default
Transform black-outside yields zero RGBA; a direct multiply destroys the original
pixel. White backing makes the factor one there. This is documented node algebra,
not a rendered Nuke comparison. The official [Transform reference](https://learn.foundry.com/nuke/content/reference_guide/transform_nodes/transform.html)
and [Merge reference](https://learn.foundry.com/nuke/content/reference_guide/merge_nodes/merge.html)
define the boundary and merge operations used in that check. The MatchMove center
was already explicit; this change does not claim a diagnosed coordinate failure.

Named standard-node Write branches are prepared for linear EXR, Rec.709 PNG,
1280×360 before/after and 1280×720 six-stage breakdown. The breakdown input order
is plate, sky, ruin, contact shadow, prop, final. Render them only after inspecting
the graph and the actual host/tool state. Encoding, continuous-frame inspection,
intentional-silence review and playback remain later steps.

The builder saves `build-readback.json` only after the graph was saved; it records
native/config hashes, frame contract and static insert scope. It explicitly keeps
render, save/reopen and privacy unverified. A saved `.nk` may contain the host's
absolute Root name or metadata. It is a **private candidate** until sanitized,
reopened from the package location and checked for missing dependencies and pixel
agreement. Source/export reopen and blank-graph rebuilding are separate checks.

Compatibility boundary: the official Nuke 16.1 Python documentation URLs checked
on 2026-10-24 were inaccessible through the available web reader. APIs and exact
knob enums for both candidate versions remain untested assumptions until the granted in-host run;
a syntax/preflight check does not certify them.
