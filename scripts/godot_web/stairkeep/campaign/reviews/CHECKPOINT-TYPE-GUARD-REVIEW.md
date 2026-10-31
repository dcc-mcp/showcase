# Nested checkpoint type guard: source correction, native regression pending

Static review of PR54 head `91c7cadae2660bbe4031269bdd459c0868286d84`
found that the legacy 21-floor laboratory called `is_empty()` on a saved child
`checkpoints` value before requiring it to be an Array. A malformed integer,
null or Dictionary could therefore raise a script error instead of returning
the documented load rejection.

The restore candidate now checks the child Dictionary and its history Array
before querying emptiness. The existing isolated candidate/commit path is
retained. Three prepared negative cases require rejection and byte-equivalent
active snapshots; their valid entry-checkpoint precondition is also checked.

This correction is confined to the legacy `campaign/` laboratory. The playable
first-chapter `game/fifty/` runtime and its frozen experience03 source package do
not import it. No map, economy, combat, first-chapter save format or user slot
was changed. Original 10,000-run results and all 1,362 counterexamples remain
historical evidence bound to their original sources.

The laboratory fingerprints its actual rule sources. This patch changes that
fingerprint; old laboratory snapshots still require the matching old source.
No implicit migration or re-signing is added. Old sources and all evidence are
preserved in Git, rather than relabeling prior measurements as this patch's.

Static inspection and `git diff --check` passed. The new negative cases have
**not run**: the original installed Godot console remains blocked at
CreateProcess with WinError5. No retry, executable copy, identity/host change,
CUA/Host launch or browser action was attempted. A normal future run must check
the complete `tests/test_campaign.gd` result plus zero script errors; repository
CI alone is not execution of this separate laboratory project.

Review also distinguished a pre-existing laboratory API limit: save import
checks resource ranges and hash bindings but does not replay all ordinary
actions to prove resource provenance. An in-range edit is not a claimed
anti-tamper rejection. `LIFECYCLE-API.md` now states that boundary explicitly.
The separate first-chapter Fifty loader does use deterministic action replay.
Adding laboratory replay across attempts/checkpoint prefixes would be a larger
change requiring a separately validated design; this patch makes no such claim.
