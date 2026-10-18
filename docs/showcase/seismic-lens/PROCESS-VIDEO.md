# Seismic Lens: real GIMP layer demonstration

[Video](seismic-lens-native-layers.mp4) · [Poster](seismic-lens-native-poster.png) · [Measurements](native-process-video.json) · [Complete original source](editable-source.zip) · [Rights](LICENSES.md)

## What was actually recorded

One continuous eight-second capture of the task-owned GIMP 3.0.4 window. Typed DCC-MCP calls reveal the existing `01 SectionX`, `02 SectionY`, `03 SectionZ`, `04 Delay80` and `05 Delay150` groups. The canvas, layer dock, visibility icons and application menus are real software pixels. No still-image pan, synthetic interface, generated art, frame interpolation or composited panel was used. The output is intentionally silent.

The five panels and nineteen editable text layers are the original work. This is a new inspection/process demonstration, not a replay of its creation or a new ParaView computation. Read the formulas and scientific limits in the original master; the small video is a view of the editing structure, not a replacement for the full-resolution image.

## Bounded reproduction

1. Download the unchanged source archive and verify SHA256 `6e6aaf6197ccc0c7ad245bb6f4a7e8fbbb16255b4de99a17b24019f521d0b439`. Extract its `gimp/native/gimp/seismic-lens-master.xcf`. The original XCF SHA256 is `8efc1515de37d6e917d0b55bdfa24a8c9faae087f2cbe63b60d0f1aa1c7c09e5`.
2. Use a dedicated GIMP profile/window and the official GIMP adapter. This recording used Core 0.20.43, adapter 0.5.0 based on `fa19b03f76df95968b1183d2ad95851cbe6001ec`, with the installer-only readiness fix in [Draft PR22](https://github.com/dcc-mcp/dcc-mcp-gimp/pull/22), commit `17458b808d351acd861a1d9c92b973eeddbbb069`. It was unmerged when recorded. Keep task listeners loopback-only; no remote gateway or new persistent credential is needed. Do not change a shared profile.
3. Run the official context-bound install/verify path. Require `directly_usable=true`, including authenticated bridge and exact host identity. Discover/load `gimp-session`, then call typed `open_image`, `inspect_image` and `list_layers`. Await each actual Core job; a pending response is not completion. Resolve image/layer IDs from this session instead of reusing recorded IDs.
4. Save to a new XCF path, close it, reopen that copy and export PNG. Compare the original and copy hashes, the thirty-layer tree and nineteen text layers, and all RGBA pixels. Open the exported PNG in GIMP, export it again, and compare decoded pixels. In this run the XCF was byte-identical and all PNG pixel comparisons passed; PNG container metadata/bytes are not claimed identical.
5. In the copy's real native view, show the layer dock and fit the complete canvas. Disable the active-layer boundary overlay for clarity. Set the five groups' `visible` properties to false using `gimp_session__set_layer_properties`; keep all artwork and text unchanged. Start continuous capture of only the selected GIMP window after verifying its window PID belongs to the task. Never capture a shared desktop or another application's notification.
6. Reveal X, Y, Z, 80 ms and 150 ms at approximately 1.0, 2.2, 3.4, 4.6 and 5.8 seconds after capture starts, using the same typed property tool. Await every result. The evidence records actual request/completion times; they are not exact display-frame timestamps. Hold the complete plate to the end. The original file is never overwritten.
7. Record eight seconds at 15 fps. This run used FFmpeg X11 window capture and single-threaded libx264, CRF 19, `fast`, `yuv420p` and `+faststart`, with no cuts or retiming. Verify complete decode, duration and all frame timestamps. Inspect the whole sequence and all changes, then test the served video's native controls, play/pause/resume/seek and downloads in both website languages. Display/encoder differences mean a re-recording is not expected to have identical video bytes.

The final clip has 120 decodable frames, including intentional holds. Ninety-eight distinct decoded frame hashes do not independently prove continuity; that conclusion also depends on the single capture process, window identity and actual MCP receipts. Long layer names are partly clipped by the dock width, while the full composition remains in frame.

## Failures and limits retained

Unchanged GIMP verification initially selected only per-DCC sidecars, excluding its real GUI adapter. The older Core HTTP probe also omitted the Streamable HTTP Accept media type and received HTTP 406. The separate readiness fix was replayed against the real host until artifact/import/readiness and identity verification passed. No registry role was fabricated. Private raw diagnostics are retained; public code/tests and this selected summary exclude machine paths, process identities and endpoints.

A two-second capture smoke preceded the final clip. A native UI accessibility request timed out during optional layer-dock collapsing; the software remained live and the final recording was made only after fresh window inspection. That failed UI request is not represented as a completed editing operation.

Only Linux GIMP 3.0.4 was exercised natively. No new ParaView production run, cross-platform qualification, deployed-site acceptance, audio listening test or independent model-certified review is claimed. The two website languages share the same original artwork and video.

## Attribution and rights

Actual model and reasoning effort for this new capture/review are Unknown. `gpt-6-astra` / `ultra` was the requested configuration; no auditable accepted runtime receipt was available. The original historical attribution is unchanged. New media remains rights reserved under [LICENSES.md](LICENSES.md); no additional MIT/CC0 or font/application redistribution grant is made.

Before recording, the official GIMP artist-workflow articles and plugin/API guidance listed in the measured evidence were checked. The 2026 articles archive 2017 interviews, not a newly observed 2026 trend. No external artwork, music or footage was reused.
