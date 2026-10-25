# First-chapter native preview

Existing project: `res://project.godot`; independent current scene:
`res://fifty/view/preview.tscn`. The default `res://main.tscn` remains the old
three-floor entry. No existing scene, asset, rule source or project setting was
changed by this view contribution.

`preview.gd` composes the new `FiftyRuntime` and `FiftySave`. `world.gd` extends
the existing isometric renderer, retaining its official MIT TileSet and Kenney
CC0 textures. It adds NPC/event markers, respects runtime visibility and keeps
cost badges readable when fitting a larger board. All combat costs come from
the runtime's `combat()` method; there is no presentation combat formula.

The title screen has no selected mode. Native buttons explicitly choose Classic
or Practice, then start or load that mode. Changing mode or starting another run
requires a visible replacement confirmation; a fresh candidate runtime is only
adopted after validation. Load follows the same candidate/commit pattern, so a
failed or incompatible load leaves the current runtime untouched. Saved slots
use only FiftySave's new mode-isolated slot `first-chapter`.

After Classic fails in the current open session, the Load button is disabled.
Both `_load_slot` and `_do_load_slot` enforce the same guard before constructing
a candidate, so that helper path cannot bypass the rule. Same-mode recovery
uses `restart_classic` with the current failure ID; Practice uses the complete
checkpoint API. Explicitly changing mode remains a separately confirmed new
tower. No death tombstone, slot deletion or cross-session anti-rollback system
is added: closing/reopening may still resume an earlier manual save. This is a
current-session recovery policy and makes no permanent-death claim.

Inspect, Bestiary and Clues are real native tabs. NPC/event dialogue and journal
entries preserve the authored content's original Chinese text; no CJK font has
been added or validated. UI control labels are English. Return-visit status uses
the actual `copper_found`, `copper_redeemed`, `archive_read`, `keeper_supplied`
flags. The chapter end remains revisitable and saveable. No UI can enter floors
11–50; the persistent scope label says that they are not yet built.

Pickup inspection displays the authored amount and resource, including key
color and quantity. NPC/event inspection displays only the first currently
eligible unclaimed event's typed finite grants, matching the runtime's authored
selection order. Amounts come from `item.amount` and `available_events.effects`,
not a second reward formula or hardcoded chapter budget. Ineligible or already
claimed interactions show no gain and cannot be claimed through that button.

`view_status()` exposes title-screen selection/disabled state for the
coordinator's headless checks. Static delimiter/source inspection alone is not
Godot parsing or scene instantiation. This author did not launch Godot, a GUI,
browser or capture. The coordinator runs import/instance checks separately.
Rendered native pixels and real input remain blocked by the current GUI stop;
Web persistence and browser interaction are not accepted by this contribution.

The design basis is `../VISUAL-DIRECTION.md` and the existing concept image,
not a newly generated illustration. At 1280×800 the native Container hierarchy
reserves a map region and a 350px notebook. Smaller-window layout, long text,
focus, held input, save/reload, mode confirmation, every floor's readability and
Chinese/Web glyph coverage still need an authorized actual-window review.
