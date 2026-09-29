# From a failed import to a finished turntable — one unattended Blender 5.1.1 run

> **The claim:** a single unattended run took a real Blender 5.1.1 host, built a
> 24‑object mechanical assembly with 5 materials and 4 area lights, and rendered
> a seamless 48‑frame Cycles turntable in 80.23 seconds with zero build errors —
> and the adapter that booted the host **failed to import on the first attempt**.

![turntable](turntable_v2.gif)

Three things separate this from a screenshot:

- **It ran unattended.** 48 frames at 1.57–1.82 s each, 80.23 s total, an empty
  `errors` array. Nobody touched the host between launch and the last frame.
- **Every headline number was recomputed.** Independent measurement of the
  published hero frame gives mean luma 53.8 / std 34.9 against the producing
  run's 53.92 / 34.86. Turntable inter‑frame steps recompute to 2.644–3.920
  against the reported 2.717–4.0098. The numbers are not whatever the job
  happened to log.
- **We publish what broke.** The first `import dcc_mcp_blender` failed. The
  launcher add‑on never loaded at all. Both are recorded below rather than
  edited out, because a showcase that only reports its successes proves nothing.

## What broke, and what that tells you

This is the most useful part of the entry, so it goes near the top.

Blender 5.x runs an isolated interpreter that does not inherit the exported
package path, so on a plain host start the adapter is unimportable. The host
logged the failure and its fix:

```text
BOOT resolved import_failed=ModuleNotFoundError("No module named 'dcc_mcp_blender'")
BOOT add_root=<adapter site-packages> ok=True
BOOT add_root=<core site-packages>      ok=True
BOOT add_root=<adapter addons>          ok=True
BOOT injected dcc_mcp_blender=<adapter>/dcc_mcp_blender/__init__.py
BOOT blender_version=5.1.1
```

Three roots injected, three resolved, second import `ok`. This is a concrete,
reproducible packaging failure with a concrete remedy — not a screenshot.

A second thing stayed broken: `dcc_mcp_blender_launcher` was never installed,
so automatic MCP server startup on host launch was not exercised
(`No module named 'dcc_mcp_blender_launcher'`). It is listed under
*not claimed* rather than quietly omitted.

## The quality bar being met, in three rounds

Luma drift across the cycle — how much the image brightens or darkens as the
camera orbits — is the measurement that decides whether a turntable is watchable.

| Round | Luma drift across the cycle |
| --- | --- |
| First attempt | 10.618 |
| 48‑frame rework | 6.361 |
| **Published here** | **0.007** |

That is a bar being met, not asserted.

## The artifacts

| File | Spec | What it proves |
| --- | --- | --- |
| `hero_v2.jpg` | 1600×900, 52,999 bytes, JPEG q82 | A real Cycles GPU render: mean luma 53.8, std 34.9, 72.92 % of pixels lit, subject centred at uv (0.516, 0.629) |
| `turntable_v2.gif` | 900×506, 48 frames, 12.00 fps, 2,662,913 bytes, loops forever | 48 rendered frames, every inter‑frame step non‑zero, and the loop seam statistically indistinguishable from any other step |
| `contact_sheet_v2.jpg` | 1232×354, 27,860 bytes, 4×2 grid | Eight evenly spaced samples across the rotation, so the motion claim is checkable by eye |
| `showcase_v2.blend` | 100,281 bytes | The source scene. Re‑render it and you regenerate both the hero frame and the turntable |

![hero frame](hero_v2.jpg)

![cycle contact sheet](contact_sheet_v2.jpg)

## How the run was driven

1. **Host launch.** Blender 5.1.1 starts a bootstrap inside its own interpreter.
   The host self‑reports `blender_version=5.1.1` and `python=3.13.9`, so the
   host identity comes from the live process rather than from assumption.
2. **Adapter boot.** It fails, then succeeds — see above. 3 of 3 package roots
   injected. `dcc_mcp_blender` 0.2.4 with `dcc_mcp_core` 0.20.28.
3. **Scene build.** 24 objects (9 body parts, 12 radial bolts, 2 axial pins, 1
   floor), 5 materials, 4 area lights (Key 420, Fill 130, Rim 300, Top 90), an
   85 mm camera with depth of field at (5.054, 3.158, 2.759), rotation
   (74°, 0°, 122°).
4. **Render.** Cycles on GPU: hero at 512 samples with OpenImageDenoise in
   6.01 s; 48 turntable frames at 320 samples each.
5. **Encode.** 48 frames to a 128‑colour palettised GIF.

## Measurements

Every figure below comes from `validation.json` or `manifest.json`.

| Quantity | Value |
| --- | --- |
| Host | Blender 5.1.1, CPython 3.13.9, Windows |
| Adapter | `dcc_mcp_blender` 0.2.4, `dcc_mcp_core` 0.20.28 |
| Renderer | Cycles, GPU |
| Scene | 24 objects, 5 materials, 4 area lights |
| Camera | 85 mm, at (5.054, 3.158, 2.759), rotation (74°, 0°, 122°), DoF on |
| Hero | 1600×900, 512 samples, 6.01 s, mean luma 53.92 / std 34.86 |
| Turntable | 48 frames, 320 samples/frame, 80.23 s total, luma drift 0.007 |

**The turntable is genuinely moving, and it loops cleanly.** Inter‑frame steps
run 2.717–4.0098 with a mean of 3.5239. The last‑to‑first step is 3.1473
(z = −1.0883), inside the normal step range, so the loop seam is not detectable
as a jump. An independent pass over the palettised GIF confirms it: 2.644–3.920
steps, with 8.39–12.41 % of pixels changing between frames and no still frames.

## A recorded deviation: GIF frame timing

The contract caps GIFs at 12 fps. The GIF stores delays in 10 ms units, and
1000 ÷ 12 = 83.33 ms is not representable, so the encoder alternates 80 ms and
90 ms delays to average 83.33 ms. Total cycle time is exactly 4.000 s and the
mean frame rate is exactly 12.00 fps, but 8 of the 48 frames carry an 80 ms
delay and therefore play at 12.5 fps instantaneously.

We are declaring this rather than hiding it. It is a limitation of the GIF
format, not of the render, and re‑encoding at a lower nominal rate would only
trade one artefact for another.

## What this entry does *not* claim

Read this before reading anything above.

- **No MCP tool round trip.** The adapter was booted inside the host, but the
  scene was built and rendered through Blender's Python API. The job issued no
  `tools/call` requests, so the adapter's *tool surface* was not exercised by
  the run that produced these frames.
- **No sustained interactive MCP session.** Long‑lived background hosts are
  reaped between agent tool calls in this environment, so the job ran as a
  single in‑process invocation.
- **`dcc_mcp_blender_launcher` was not installed**, so automatic MCP server
  startup on host launch was never exercised.
- **No cross‑host conservation.** One host, one entry.
- **No geometric ground truth.** No mesh, vertex, UV or shader values were
  measured. Every visual claim rests on the luma statistics above.
- **No aesthetic sign‑off.** Composition is expressed only through the measured
  subject centre, coverage and lit‑area fractions.

Verification level: **host‑level execution with the adapter booted in‑process**.
Not “agent drove the host over MCP end to end”.

## Reproducing

```bash
python scripts/validate_entry.py docs/showcase/blender-mcp-gimbal-turntable
```

The validator checks that the mandatory files exist, that every artifact listed
in `manifest.json` is present with the recorded size and SHA‑256, that there are
no orphan artifacts, and that `validation.json` has the required shape —
including a non‑empty `not_claimed` array. All 19 checks currently pass.
