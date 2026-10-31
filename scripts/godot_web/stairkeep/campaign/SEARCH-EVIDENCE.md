# Separate initial solvability from a failed continuation

The frozen three-floor game uses a fixed canonical map. Its simulation seed
drives the policy selector; it does not generate enemy placements or a new map.
The old 10,000-run report and its source files were not rewritten.

The new `game/tests/classify_slice.gd` inherits the frozen `frontier-v1` harness
and replays only the 2,000 randomized-policy runs, using the original run-index,
policy-assignment and seed formulas. The coordinator's Godot 4.7.2 run reproduced
1,980 wins and 20 dead ends exactly; its first failure also matched the old
retained sample. The separate `slice-failure-classification.json` records all 20
seeds, final full states, complete decision/action traces, reachable navigation
nodes and edges, blocked object previews, and shop stock/cost checks. All 20
initial states were separately replayed to victory through one of the four
canonical witnesses using the production rule API. The report binds the old
report, data, rule, harness and new classifier SHA-256 values.

These are two different conclusions. Each initial state has a winning route.
Each reached failure state has no legal resource-changing action after complete
clear/shop/stair navigation BFS, so ordinary navigation cannot recover that
particular continuation. This is policy resource exhaustion, not evidence that
the initial generated map was unsatisfiable. The retained report is evidence for
those exact 20 continuations, not a universal proof over all resource states.

## Campaign search interface

`campaign/tests/campaign_solver.gd` can run as a headless script or be called as
`CampaignSolver.solve(game, configuration)` without constructing another tree.
It returns exactly one of:

- `witness`: a winning sequence was found and then continuously replayed from
  the input snapshot through actual `move`, `use_stairs` and `buy` calls.
- `unsatisfiable`: every ordinary-action successor was exhausted under the
  declared dominance contract, or the input is already frozen by the rule
  object's explicit failure-mode gate. These proof scopes are stated separately.
- `unknown`: a time/state/navigation budget stopped search, a schema was
  unsupported, or an actual core action contradicted the frontier model.

Unknown is never converted to a loss. Conclusive receipts bind the exact input
state hash and canonical/transformed/rule hashes expected by the campaign rule
object. Reset, respawn and explicit unsafe challenges are outside this query: it
asks whether the *current run* has an ordinary winning suffix.

`CampaignNavigation.frontier()` is shared by the wrapper and solver. Complete
means its clear/shop/stair BFS queue was exhausted without unsupported objects,
invalid destinations or a node-budget cutoff. Its proof contains visited nodes,
navigation edges, all adjacent resource boundaries and reasons, and reachable
shop offers. Combat costs come from the rule object's `combat()` method. The
helper also matches the base API's first-adjacent-shop dispatch order.

The search signature retains rule/content/variant/seed/attempt/failure/story
metadata, every non-resource core field, exact floor/position, cleared IDs as a
set, purchases and key-color schema. It omits only five audited fields:
`decision_index`, `decision_log_hash`, `decision_log`, `checkpoint_id` and
`checkpoints`. `_perform()` does not consult these fields to gate or calculate
ordinary actions; they append past audit information or serve the explicitly
excluded save/checkpoint/respawn operations. All other current and future
metadata remains exact by default. Only current HP, attack, defense, gold and
key quantities form the dominance vector. A state dominates another only under
an identical signature and when every vector component is at least as large.
Monotonicity is scoped to the current base combat/cost semantics and ordinary
actions; changing those semantics requires revisiting this contract.

`prepare(game)` optionally caches read-only floor/object indexes bound to the
sealed transformed dictionary's identity. A new variant cannot reuse a stale
identity. `frontier_local(game, horizon, ...)` shares the same BFS implementation
but limits its policy horizon and always returns `complete=false`. A policy may
choose an action from that horizon; if it finds none, it must call the global
frontier before declaring a terminal state. Local exhaustion is never a loss
proof. The default `frontier()` continues to search globally.

`test_solver.gd -- --production-shop-regression --witness-report=<actual-canonical-replay.json>
--output=<new-report.json>` adds separately labelled real first-floor shop
queries. It binds the existing four winning canonical witnesses by data/base
hash, then navigates from a real initial state to each `ward`/`flask` purchase,
both with the yellow key retained and with the defense room already chosen.
Each immediate purchase state is queried by the exact solver. A second actual
continuation collects the remaining reachable resources and retains a full
global frontier proof. The test does not preselect the result: a verified
witness corrects any assumed failure, a conclusive unsatisfiable result proves
that continuation lost, and a budget-limited unknown remains unknown.

Search branches use isolated, already bound clones and real core actions.
External input and the independent winning replay use strict snapshot restore.
The solver does not regenerate all 21 floors for each branch, does not expose a
state setter, and releases expanded authority clones. A benchmark should start
with 10 and 100 campaign runs before estimating the 10,000-run cost. No headless
count is claimed as real keyboard/browser input or as hours of player testing.

Example commands (the runner creates a new report, never overwrites the old one):

```text
godot --headless --path game --script res://tests/classify_slice.gd -- --report=<frozen-report.json> --output=<new-classification.json>
godot --headless --path campaign --script res://tests/campaign_solver.gd -- --seed=20261025 --max-expanded=5000 --max-states=20000 --max-ms=15000 --output=<new-solver-report.json>
```

The coordinator ran the expanded first-shop regression on Godot 4.7.2: all 31
checks passed. The four exact production prefixes were all proven
`unsatisfiable` for an ordinary winning suffix. With the yellow key retained,
the ward and flask cases each exhausted 14 states and pruned three dominated
states; after choosing the defense room they each exhausted one state. The
actual resource-collection continuations also ended with complete global
frontiers and no legal resource action. The new
`campaign-shop-regression.json` binds these results to the tested source/data
hashes and the four initial canonical winning witnesses. This evidence does not
claim the whole initial campaign is unsatisfiable.

The independent topology cross-check found 29 cells optimistically reachable
before crossing the first guard, with no reachable stair or attack-room gate
and gem. Free attack before that guard or the shop's attack upgrade is bounded
by 26, against guard defense 28; all pre-guard gold sources sum to at most 40.
These bounds support inspection, while the actual action/solver reports carry
the outcome proof. Later source or economy changes require another bound run.

The first 10 campaign policy runs completed as a benchmark. The 100-run
benchmark and any later 10,000-run measurement remain separate stages; no old
or smaller report is promoted as evidence for a larger run.
