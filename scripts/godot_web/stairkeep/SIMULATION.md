# Production-rule exploration

Run from the native project with the exact installed Godot version used for the
slice. The script opens no window or browser:

```text
godot --headless --path game --script res://tests/simulate.gd -- --runs=10000 --seed=20261025 --output=user://stairkeep-simulation.json
```

The harness uses `rules.gd` for every move, stair transfer, purchase, battle
preview and health deduction. It searches the complete currently reachable
navigation component across floors, using cleared tiles, shops and stair
transfers; uncollected resources, gates and enemies are decision frontiers.
Every candidate is then executed through the production rule API. Combat
arithmetic is not copied into the harness.

Five policies rotate by run index. Resource, attack, defense and cautious
policies assign explicit preferences with bounded seeded tie perturbations;
randomized selects uniformly among all currently legal candidates. A run seed
is `master_seed + run_index * 104729`. The report records engine, rule and data
hashes, seeds, policy counts, distinct decision sequences, health/gold ranges,
real navigation count and every preview-versus-deduction comparison. The first
example for each policy/outcome retains its complete decision and budget trace.

A reported `dead_end` means exhaustive navigation BFS found no legal
resource-changing action in that particular state: no reachable collectible,
winnable encounter, unlockable gate or affordable in-stock purchase. Since
ordinary navigation cannot change resources, moving elsewhere cannot repair
that state under the delivered rule set. The retained state and sequence are a
reproducible counterexample. Resetting, editing saves, or future death/respawn
mechanics are outside this classification.

This is not an exhaustive search of every reachable resource state, a universal
proof against soft locks, a browser input test, a subjective difficulty review,
or evidence of hours of play. Simulation outcomes are measurements only after
the exact script has actually run. The later 21-floor campaign and controlled
mirror/respawn variants require separate content and runs.
