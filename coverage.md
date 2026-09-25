# Coverage matrix

The gallery proves one proposition at a time. This matrix is the ledger that says how much of
the DCC-MCP surface those propositions actually cover, and what is still unproven.

Two axes: **host** (the adapter that ran it) and **skill** (the marketplace package that
supplied the capability). One verified sample fills one cell.

- Marketplace catalog: **41 skills** across **19 DCC values**
- Declared `(skill, DCC)` pairs: **170**
- Pairs reachable with the four hosts installed on this machine: **94**
- Skills sampleable here: **32** — 29 declare a host installed here, plus 3 host-neutral (`any`)
- Skills with no locally runnable host yet: **9**

32 sampleable + 9 blocked = 41 skills.

## Where the 170 declared pairs land

The two counts above are about skills and about pairs this machine can act on. Neither is the
same as "every pair the catalog declares", so the four buckets below reconcile the full 170.

| Bucket | Pairs | Enumerated in this ledger |
| --- | --- | --- |
| Skill declares a host installed here | 94 | yes — one ⬜ per pair in the matrix below |
| Host-neutral, declared as `any` | 3 | yes — see *Host-neutral skills* |
| Blocked skills, all of their declared hosts | 25 | yes — see *Blocked: host not installed here* |
| Sampleable skill against a host **not** installed here | 48 | **no** — see the note below |

The 48 are pairs that a skill sampleable here declares against some other host — for example
`dcc-asset-kenney` declaring `godot`, `unity`, `unreal` and `zbrush`, or `dcc-asset-polyhaven`
declaring `photoshop`. No proposition on this machine can close them, so they are not drawn as
cells. They are still real declared support, and they are the raw material for the gap this
project feeds back upstream.

So this file is a ledger of what the sampling machine can act on, not a full transcription of
the catalog: 122 of the 170 declared pairs are enumerated here.

Source of truth: [`marketplace.json`](https://github.com/dcc-mcp/marketplace/blob/main/marketplace.json)
at catalog version `1.15.1`. Regenerate this file — and the Coverage section of `README.md`,
which links here instead of repeating these counts — when the catalog moves.

## Legend

| Mark | Meaning |
| --- | --- |
| ✅ | Published in the gallery |
| 🟡 | Artifact drafted internally, awaiting release approval |
| ⬜ | Declared support, not yet sampled — open cell |
| ⛔ | Host not installed on this machine — the adapter repository exists, but the app is not here |

## Host axis

`Adapter repository` and `Host installed here` are separate questions. The first is whether a
`dcc-mcp` adapter exists for that DCC at all; the second is whether the DCC application itself
is installed on the machine that produces these samples. A ⛔ row is the second one failing,
not the first.

| DCC | Skills declared | Adapter repository | Host installed here | Cells openable now |
| --- | --- | --- | --- | --- |
| `maya` | 26 | [`dcc-mcp-maya`](https://github.com/dcc-mcp/dcc-mcp-maya) | yes | yes |
| `houdini` | 25 | [`dcc-mcp-houdini`](https://github.com/dcc-mcp/dcc-mcp-houdini) | yes | yes |
| `blender` | 23 | [`dcc-mcp-blender`](https://github.com/dcc-mcp/dcc-mcp-blender) | yes | yes |
| `3dsmax` | 20 | [`dcc-mcp-3dsmax`](https://github.com/dcc-mcp/dcc-mcp-3dsmax) | yes | yes |
| `unreal` | 15 | [`dcc-mcp-unreal`](https://github.com/dcc-mcp/dcc-mcp-unreal) | no | no — ⛔ |
| `godot` | 9 | [`dcc-mcp-godot`](https://github.com/dcc-mcp/dcc-mcp-godot) | no | no — ⛔ |
| `unity` | 7 | [`dcc-mcp-unity`](https://github.com/dcc-mcp/dcc-mcp-unity) | no | no — ⛔ |
| `nuke` | 5 | [`dcc-mcp-nuke`](https://github.com/dcc-mcp/dcc-mcp-nuke) | no | no — ⛔ |
| `substance3d_designer` | 5 | [`dcc-mcp-substance3d-designer`](https://github.com/dcc-mcp/dcc-mcp-substance3d-designer) | no | no — ⛔ |
| `substance3d_painter` | 5 | [`dcc-mcp-substance3d-painter`](https://github.com/dcc-mcp/dcc-mcp-substance3d-painter) | no | no — ⛔ |
| `katana` | 5 | [`dcc-mcp-katana`](https://github.com/dcc-mcp/dcc-mcp-katana) | no | no — ⛔ |
| `substance` | 4 | **none** | no | no — ⛔ |
| `mari` | 4 | [`dcc-mcp-mari`](https://github.com/dcc-mcp/dcc-mcp-mari) | no | no — ⛔ |
| `photoshop` | 4 | [`dcc-mcp-photoshop`](https://github.com/dcc-mcp/dcc-mcp-photoshop) | no | no — ⛔ |
| `after-effects` | 4 | [`dcc-mcp-aftereffects`](https://github.com/dcc-mcp/dcc-mcp-aftereffects) | no | no — ⛔ |
| `premiere` | 4 | [`dcc-mcp-premiere`](https://github.com/dcc-mcp/dcc-mcp-premiere) | no | no — ⛔ |
| `any` | 3 | n/a — host-neutral | n/a | yes — any host installed here |
| `zbrush` | 1 | [`dcc-mcp-zbrush`](https://github.com/dcc-mcp/dcc-mcp-zbrush) | no | no — ⛔ |
| `marmoset` | 1 | [`dcc-mcp-marmoset`](https://github.com/dcc-mcp/dcc-mcp-marmoset) | no | no — ⛔ |

## Hosts with no adapter repository

Exactly one declared DCC value has no adapter repository in the `dcc-mcp` organisation:
`substance`, declared by 4 skills. That is the only true capability gap this matrix can
report — everything else marked ⛔ is an install problem on the sampling machine, not missing
work upstream.

No skill is currently blocked by it: all 4 skills that declare `substance` also declare a host
that is installed here, so none of them sit in the blocked table below.

## Skill × locally runnable host

29 of 41 skills declare at least one of the four hosts that resolve here.
Every ⬜ below is a cell a single proposition can close.

| Skill | Category | maya | blender | houdini | 3dsmax | Catalog image |
| --- | --- | --- | --- | --- | --- | --- |
| `dcc-mcp-maya-mgear` | Skills | ⬜ | — | — | — | yes |
| `dcc-mcp-maya-advancedskeleton` | Skills | ⬜ | — | — | — | yes |
| `dcc-mcp-maya-procedural-architecture` | Skills | ⬜ | — | — | — | yes |
| `dcc-ui-qt-inspector` | Infrastructure | ⬜ | — | ⬜ | — | yes |
| `dcc-ui-qt-actions` | Infrastructure | ⬜ | — | ⬜ | — | yes |
| `dcc-ui-workflow-memory` | Infrastructure | ⬜ | — | ⬜ | — | yes |
| `dcc-ai-hunyuan3d` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-ai-tripo3d` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-polyhaven` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-blender-extensions` | Asset Providers | — | ⬜ | — | — | yes |
| `dcc-asset-ambientcg` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-nasa3d` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-smithsonian3d` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-kenney` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-quaternius` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-pirate-nation` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-objaverse` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-gltf-sample-assets` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-sketchfab` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-google-scanned-objects` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-ai-openai-image` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-texture-pipeline` | Infrastructure | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-materialx` | Skills | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-lookdev-turntable` | Skills | ⬜ | ⬜ | ⬜ | ⬜ | **empty** |
| `dcc-modeling-spec` | Skills | ⬜ | ⬜ | ⬜ | ⬜ | **empty** |
| `dcc-pipeline-publish` | Studio | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-game-icons` | Asset Providers | ⬜ | ⬜ | ⬜ | ⬜ | yes |
| `dcc-asset-openstreetmap-city` | Asset Providers | — | ⬜ | ⬜ | — | yes |
| `dcc-asset-overture-city` | Asset Providers | — | ⬜ | ⬜ | — | yes |

The 94 ⬜ in this table are the declared pairs counted at the top: 26 maya + 25 houdini +
23 blender + 20 3dsmax.

## Host-neutral skills

3 skills declare `dcc: ["any"]` — no host constraint at all. `any` is a statement that the
skill works anywhere, not a host we lack, so these are not blocked: any one of the four hosts
installed here can carry the sample today.

Host-neutral is not the same as verified. Until a proposition actually runs one, all three are
still open cells.

| Skill | Category | Declared hosts | Sampleable on | Catalog image |
| --- | --- | --- | --- | --- |
| `dcc-asset-itchio` | Asset Providers | `any` | any host installed here | yes |
| `dcc-asset-poly-pizza` | Asset Providers | `any` | any host installed here | **empty** |
| `dcc-mcp-cache-inspector` | Skills | `any` | any host installed here | yes |

## Blocked: host not installed here

9 skills declare only hosts that are not installed on this machine. Every host in this table
has an adapter repository in the `dcc-mcp` organisation, so none of these is a missing adapter
and none is an upstream gap to file — the only thing standing between them and a sample is
installing the host application here.

| Skill | Category | Declared hosts | Adapter repositories |
| --- | --- | --- | --- |
| `dcc-asset-godot-store` | Asset Providers | `godot` | [`dcc-mcp-godot`](https://github.com/dcc-mcp/dcc-mcp-godot) |
| `dcc-game-release-package` | Studio | `godot`, `unreal`, `unity` | [`dcc-mcp-godot`](https://github.com/dcc-mcp/dcc-mcp-godot), [`dcc-mcp-unreal`](https://github.com/dcc-mcp/dcc-mcp-unreal), [`dcc-mcp-unity`](https://github.com/dcc-mcp/dcc-mcp-unity) |
| `dcc-game-itchio-publish` | Studio | `godot`, `unreal`, `unity` | [`dcc-mcp-godot`](https://github.com/dcc-mcp/dcc-mcp-godot), [`dcc-mcp-unreal`](https://github.com/dcc-mcp/dcc-mcp-unreal), [`dcc-mcp-unity`](https://github.com/dcc-mcp/dcc-mcp-unity) |
| `dcc-game-runtime-acceptance` | Studio | `godot`, `unreal`, `unity` | [`dcc-mcp-godot`](https://github.com/dcc-mcp/dcc-mcp-godot), [`dcc-mcp-unreal`](https://github.com/dcc-mcp/dcc-mcp-unreal), [`dcc-mcp-unity`](https://github.com/dcc-mcp/dcc-mcp-unity) |
| `dcc-game-pv-capture` | Studio | `godot`, `unreal`, `unity` | [`dcc-mcp-godot`](https://github.com/dcc-mcp/dcc-mcp-godot), [`dcc-mcp-unreal`](https://github.com/dcc-mcp/dcc-mcp-unreal), [`dcc-mcp-unity`](https://github.com/dcc-mcp/dcc-mcp-unity) |
| `dcc-asset-pexels-video` | Asset Providers | `after-effects`, `premiere` | [`dcc-mcp-aftereffects`](https://github.com/dcc-mcp/dcc-mcp-aftereffects), [`dcc-mcp-premiere`](https://github.com/dcc-mcp/dcc-mcp-premiere) |
| `dcc-asset-mixkit-free-media` | Asset Providers | `after-effects`, `premiere` | [`dcc-mcp-aftereffects`](https://github.com/dcc-mcp/dcc-mcp-aftereffects), [`dcc-mcp-premiere`](https://github.com/dcc-mcp/dcc-mcp-premiere) |
| `dcc-asset-google-fonts` | Asset Providers | `godot`, `unreal`, `unity`, `photoshop`, `after-effects`, `premiere` | [`dcc-mcp-godot`](https://github.com/dcc-mcp/dcc-mcp-godot), [`dcc-mcp-unreal`](https://github.com/dcc-mcp/dcc-mcp-unreal), [`dcc-mcp-unity`](https://github.com/dcc-mcp/dcc-mcp-unity), [`dcc-mcp-photoshop`](https://github.com/dcc-mcp/dcc-mcp-photoshop), [`dcc-mcp-aftereffects`](https://github.com/dcc-mcp/dcc-mcp-aftereffects), [`dcc-mcp-premiere`](https://github.com/dcc-mcp/dcc-mcp-premiere) |
| `dcc-plugin-github-releases` | Skills | `after-effects`, `premiere` | [`dcc-mcp-aftereffects`](https://github.com/dcc-mcp/dcc-mcp-aftereffects), [`dcc-mcp-premiere`](https://github.com/dcc-mcp/dcc-mcp-premiere) |

## Catalog images still empty

6 of 41 catalog entries carry no `showcase` image:

- `dcc-asset-poly-pizza`
- `dcc-lookdev-turntable`
- `dcc-modeling-spec`
- `dcc-game-release-package`
- `dcc-game-runtime-acceptance`
- `dcc-game-pv-capture`

## Combinations, not single samples

A proposition that chains one marketplace skill through several hosts, or chains several
skills inside one host, closes multiple cells per run. That is the preferred shape: the
parallel budget is small, so each proposition has to buy more than one cell.

Chains proven so far and chains queued live in the gallery table and the proposition backlog.
