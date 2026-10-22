---
name: reaper-stem-session
description: Build, save, reopen, audit and render a native REAPER session from a licensed stem manifest.
license: MIT
metadata:
  dcc-mcp:
    dcc: reaper
    version: "0.1.0"
    tags: [audio, stems, render, project]
    tools: tools.yaml
---
# REAPER Stem Session
Use the external REAPER transport with a running real host. All native project operations call REAPER's official ReaScript API through reapy_boost. This added production skill is separate from the adapter's built-in read-only inspection tools.

1. Review the stem manifest and licenses. Every media path must resolve inside its manifest directory.
2. create_session accepts only an empty active project and refuses existing destination files.
3. save_project writes a native RPP. Reopen only after saving; open_project refuses a dirty active project.
4. audit_session measures the live state and dependency paths.
5. render_master invokes REAPER's native offline renderer, refuses overwrite, and checks a nonempty WAV exists. Physical audio playback is not required.

Use original or redistribution-cleared stems. Never package REAPER binaries, license keys or configuration files with outputs.
