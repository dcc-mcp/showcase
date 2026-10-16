# Original minigames: candidates awaiting acceptance

Signal Garden is a new, original rotating-network puzzle with three authored gardens, native procedural art, original PCM interaction tones, and native English/Chinese layouts. It is separate from Sonic Loom's sequencer, Prism Tide's optical puzzle, and previous courier games.

This directory is a production recipe, not a claim of completed quality acceptance. The candidate workflow creates the actual native scene through discovered DCC-MCP tools, restarts Godot, reopens the saved scene, runs native logic assertions, makes an official single-thread Compatibility Web export, and exercises it through real browser mouse, keyboard and emulated touch. All outputs and complete interaction recordings remain CI artifacts until reviewed. No collection entry or playable publication manifest is changed here.

The first local session connected the native plugin but did not complete gateway readiness. A second bounded session stopped at its 256 MiB process-tree limit (279.3 MiB observed). Neither is recorded as an authoring pass. CI does not share the production renderer's local resource budget.

Original game source, generated tones and procedural art: copyright 2026 dcc-mcp contributors, all rights reserved; this candidate does not grant a new license for those assets. Garden Subset is a renamed subset of Noto Sans CJK SC under SIL OFL; complete source license is FONT-LICENSE.txt. Godot's existing engine notices remain necessary when publishing the shared runtime. No externally sourced game artwork, recordings or level designs are included.

The research record is research.json. Pocket Pulse and Lunar Skipper remain planned; this candidate only creates Signal Garden. Do not advertise the other games as implemented.

Verification limits remain explicit: browser viewport touch simulation is not physical-phone acceptance; sampled audio is not subjective listening; CI staging is not a live public deployment. A green workflow still requires pixel/motion review and parent approval before adding a public case and manifest.

The downloadable CI candidate includes the complete `minigame-site/play` tree, shared runtime, shell, engine/font notices and a `README.txt` with local HTTP serving instructions. Keep that tree intact; opening only `signal-garden/index.html` without its sibling dependencies does not start the game. The native source bundle also includes the font license. The package validator rejects missing runtime, shell or notice files and mismatched PCK bytes. Browser acceptance separately checks both the bottom-row Resume control and the pause overlay's Continue control with actual mouse/emulated-touch input.
