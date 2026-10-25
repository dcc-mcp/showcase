# Experimental purchase protection backend

`scripts/purchase_guard.gd` is an optional logic prototype around the existing
campaign purchase API. It changes no enemy, route, price, reward, shop stock,
campaign rule source, layout RNG, respawn sequence or original simulation.
The historical unguarded baseline and its failure traces remain valid.

The 21-floor UI is **not connected** to this prototype. A returned warning is
not evidence that a player has seen a prompt. Rendered/browser/input acceptance
and the interaction cost of an in-game implementation remain separate work.
Actual headless outcomes belong to the generated test report, not this file.

## Three-valued purchase preview

```gdscript
var guard = preload("res://scripts/purchase_guard.gd").new(campaign)
var preview = guard.preview("f01_shop/ward", {
    "max_expanded": 500, "max_states": 2000, "max_msec": 30000
})
var result = guard.commit(preview.token) # confirmed defaults to false
```

The player must already stand at the actual shop. A qualified `shop/offer`
must match the first adjacent shop selected by the frozen authoritative
`buy()` method. The preview clones the complete campaign, executes the actual
purchase in that isolated clone, and reuses the existing static
`tests/campaign_solver.gd` solver. This dependency is deliberate for an
experimental module; it does not create another solver or production framework.

- `known_losing` requires an exhaustive, exact-state/version/source-bound
  unsatisfiable result. Default commit is blocked with the entire original
  campaign unchanged. A fresh preview may be committed with
  `confirmed=true` to deliberately accept that same real losing purchase.
- `known_winning` requires a continuously replayed winning suffix from the
  exact post-purchase state. This proves existence of one continuation,
  not that all later spending or encounter orders are safe.
- `unknown` includes exhausted budgets and unverified answers. It is never
  called safe. Commit preserves the original purchase semantics and returns
  an explicit lack of a safety guarantee rather than silently vetoing play.

The preview returns both complete snapshots, source/state bindings and the
solver report. The original campaign and the solver's query input must remain
unchanged during analysis. An explicit accepted loss does not automatically
freeze the campaign or advance a seed; its ordinary continuation remains the
original game's behavior. A separately bound proof can still be displayed or
recorded by the existing failure API.

## Per-instance computation limits

The facade supplies explicit defaults and rejects requests above its hard
per-query bounds. Unsupported or out-of-range limits do not invoke the solver
and are never called a safe or losing answer.

| Limit | Default | Hard maximum |
| --- | ---: | ---: |
| `max_expanded` | 5,000 | 5,000 |
| `max_states` | 20,000 | 20,000 |
| `max_msec` | 15,000 | 30,000 |
| `navigation_max_nodes` | 0 | 100,000 |

Non-navigation limits must be positive. Navigation zero means a complete BFS
over the finite content graph; a positive node bound can instead produce an
incomplete frontier and therefore an unknown solver result.

Each instance permits at most **16 actual solver calls** and **120,000 ms of
measured cumulative solver wall time**. The optional second constructor
argument may only reduce `max_queries` or `max_total_msec`; raising these bounds
or supplying an invalid instance configuration is rejected. Cancelling or
consuming tickets does not refill either quota. `query_stats()` returns a deep
copy, so editing the reported accounting cannot alter the internal limit.

The effective per-query time is capped by the remaining total budget and is
reported alongside the requested values. Timing is cooperative around the
actual synchronous solver call, including its initialization: the current call
can finish past its remaining time, after which no further solver
call is permitted. Quota refusals return unknown, not safety or loss. This is
an instance-local backend budget, not global scheduling, cross-instance rate
limiting, a hard process preemption guarantee or an accepted UI latency.

## One-use capabilities

Tokens are generated with independent cryptographic entropy and stored only in
the guard instance's private ticket registry. Returned dictionaries are deep
copies. Editing their classification, offer, resources or proof cannot alter
what commit executes. A token from another instance, a caller-created
dictionary or an invented string is not accepted.

Every valid commit attempt consumes its token, including a default losing
block or stale-state rejection; cancel also consumes it. A confirmation after
a block therefore obtains a fresh preview. Repeated tokens are rejected.
The entire current snapshot and actual source fingerprints must still match
the stored pre-purchase binding. State changes require another preview.

An allowed commit executes the original `buy()` exactly once and compares the
complete result with its private counterfactual snapshot. An unexpected
mismatch reports an explicit complete rollback attempt and whether it succeeded;
it never presents a partial commit as success.

## Reproducible test

Use the authorized existing Godot executable with isolated native user data:

```text
godot --headless --path campaign --script res://tests/test_purchase_guard.gd -- --output=user://purchase-guard-report.json
```

The default suite constructs the four real first-shop prefixes (yellow key
unspent or defense room already chosen, then ward or flask). Each purchase is
analyzed, blocked by default, explicitly accepted in a fresh query and proved
unsatisfiable again in the actual resulting state. It also checks public-view
tampering, forged/cross-instance/stale/repeated tokens, cancel and a genuinely
budget-limited unknown without a false safety claim.
Hard per-query bounds, attempts to raise constructor limits, one-query quota
exhaustion, public accounting tampering and an actually measured reduced total
time quota are checked separately. None of these tests asks for the rejected
multi-billion-unit budgets to be executed.

One accepted wrong purchase is recorded as a proven loss and recovered through
the full chapter-entry checkpoint. The recovered expedition then cancels a
bad offer, actually purchases edge and replays every remaining authored blade
event through the real APIs to floor-21 victory. Resources, object identities,
shop stock and seed bindings are checked against the authored ledger. Before
the final boss, a real return to the floor-19 supply shop permits a short
verified winning-purchase counterfactual for `f19_shop/flask`. This shop has
only that offer: 48 gold for 180 HP, limit two. Blade has used one, so one
remains. The preview is cancelled so the actual blade economy remains exact.

`--cases-only` is an optional short run of the guard cases. Its report explicitly
omits the full winning recovery workflow and must not be presented as the
complete suite. Stdout is compact; `--output=` retains full snapshots, exact
bindings, actual paths, solver evidence and the final campaign state.

This detects post-purchase states conclusively proved to have no ordinary
winning continuation. It does not prove the purchase caused that loss when
the pre-purchase state was already unwinnable. It does not eliminate every losing strategy, guarantee
an answer within a UI latency budget, add rescue resources, prove browser
behavior or replace the pending game interface and actual-player review.

## Recorded full run

The final fresh Godot 4.7.2 headless run passed all 75 checks in 25,079 ms,
with no stderr output. All four production purchase prefixes were blocked by
default; explicitly accepting them still produced complete unsatisfiable
results (14, 14, 1 and 1 expanded states). The recovery workflow reached actual
floor-21 victory with HP 138, ATK 153, DEF 47 and gold 946, matching the authored
blade budget. The remaining floor-19 flask had a verified winning suffix and
was cancelled before the actual final fight.

The report is [purchase-guard.json.gz](evidence/purchase-guard.json.gz).
It binds guard SHA-256 `37f81040d17f4bbaef220ffa807d922d5653e57325821d674b333df4d9be9c55`
and test SHA-256 `cb65f3fae60fd850541c005cc29073c0c2c918462fccb69682a1190c0cd90519`.
This is a separate mitigation experiment; the unguarded 10,000-run baseline
and all its losing outcomes remain intact. The interface has not been connected.
