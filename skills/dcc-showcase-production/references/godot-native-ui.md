# Godot native UI: author, inspect, then exercise

Use this reference for native Godot menus, HUDs and dialogs in a showcase. Keep
game controls in the Godot scene; a Web wrapper or an image of a menu cannot
replace them. Dawnkeep's engine/export baseline is **4.6.3**; the links below
target the **4.6** manual. Record the actual executable and export-template
versions during production. This reference does not authorize an engine upgrade.

## Reuse the installed capabilities honestly

Read-only inspection on 2026-10-19 found package metadata `dcc-mcp-godot 0.9.6`
and the following skill manifests and host implementations. This is a dated
installed-source inventory, not a live-host test or a claim about every 0.9.6
installation. Rediscover with the existing `dcc-mcp` search/describe/load/call
workflow before use; preserve the returned schema, result and host readback.

| Existing skill | Available building blocks | Important limit |
| --- | --- | --- |
| `godot-scene` | `inspect_scene`, `create_node`, `set_property`, `save_scene` | The tree inspection is bounded to eight levels. Stored/editor state is not running-game layout. |
| `godot-node` | `add_node`, `update_property`, `get_node_properties`, `set_anchor_preset`, signal and resource operations | The property inspector selects storage properties. The anchor handler calls `Control.set_anchors_preset`, not `set_anchors_and_offsets_preset`; inspect/set offsets separately. |
| `godot-theme-ui` | `create_theme`, `set_theme_color`, `set_theme_constant`, `set_theme_font_size`, `set_theme_stylebox`, `get_theme_info` | Theme creation/set/list, not complete CRUD. `get_theme_info` returns item names for one type, not values or resolved inheritance. The StyleBox setter creates a new `StyleBoxFlat`. |
| `godot-analysis` | `analyze_scene_complexity`, `analyze_signal_flow`, `find_unused_resources`, `get_project_statistics` | Counts, signal connections and reference candidates; no overlap, clipping, focus or responsive-layout audit. Dynamic resource references can be missed. |
| `godot-runtime` | Paged game tree/properties, `find_ui_elements`, captures and monitoring | UI discovery filters with `is_visible_in_tree()` and returns `global_position` plus local `size`; it does not return a clipping/occlusion verdict or settled-layout guarantee. |
| `godot-input`, `godot-testing-qa` | Injected input, scenarios, state/text assertions and screenshot comparisons | Instrumented checks need their exact scope stated. The separate `click_button_by_text` runtime helper emits `pressed` directly; it does not test pointer hit routing. |

The inspected Theme surface has no dedicated font-resource/icon setter,
type-variation editor, item removal or resolved-value audit. Generic resource
operations may help only if their discovered schema and readback support the
specific edit. Do not pass a `res://` string to a Resource-typed property and
assume it was loaded: the inspected node coercion does not load resource paths.
Use a verified resource-assignment route or the authorized native editor/project
workflow; record direct scripting separately from typed MCP coverage.

For `create_theme`, choose an unused path or inspect an existing resource first;
the inspected handler saves a new Theme at the supplied path. Creating a Theme
does not attach it to a Control. Confirm both assignment and persistence after
save/reopen. Do not assume all capability mutations are undoable because the
scene skill uses undo/redo: the inspected anchor and Theme handlers differ.

## Build an adaptable native hierarchy

Start with the screens and transitions that actually exist: title/start,
gameplay HUD, pause/settings, defeat/retry and victory/replay. For each, choose
the important action, reading order, smallest supported viewport and longest
supported-language strings. Make a reusable scene for repeated panels/buttons
when it reduces drift; keep the gameplay state outside presentation-only nodes.

A useful HUD starting shape is `CanvasLayer > Control (full rect) >
MarginContainer > VBoxContainer`, with separate status, expanding content and
action rows. A modal can be a separate full-rect overlay containing a centered
panel. This is a starting pattern, not a required tree for every case.

- Use anchors and offsets for a root or deliberately free-positioned child of a
  plain Control. A full-rect anchor preset alone is not proof of zero offsets.
  Verify the four anchors, four offsets and resulting size after resizing.
  [Size and anchors](https://docs.godotengine.org/en/4.6/tutorials/ui/size_and_anchors.html)
- Let Containers own their direct Control children's layout. Use HBox/VBox for
  rows/columns, MarginContainer for padding, PanelContainer for framed sections,
  GridContainer for a chosen column count, and ScrollContainer for genuinely
  overflowing content. Use size flags and stretch ratios for space allocation;
  `custom_minimum_size` is a floor, not a fixed or maximum size. Do not repeatedly
  overwrite child position/size to fight a Container's next sort.
  [Using Containers](https://docs.godotengine.org/en/4.6/tutorials/ui/gui_containers.html)
- Define a narrow-layout policy rather than shrinking every label indefinitely:
  wrap prose, shorten secondary copy with an available full explanation, switch
  to fewer grid columns, or stack action groups. Keep essential health, current
  objective and retry/continue actions visible. Check the actual combined
  minimum sizes when a layout refuses to shrink; inspect fonts, text and panel
  margins before adding hard-coded offsets.
- Plan world-space versus HUD-space explicitly. Do not compare their raw
  rectangles or move HUD controls with the gameplay camera. Decorative overlays
  should not intercept actions; intentional modal backdrops should block the
  background. Inspect the real mouse-filter chain instead of fixing a pointer
  failure by emitting a signal directly.

## Theme once, review every state

Attach a shared project Theme at the intended UI root and keep the Control chain
continuous for inheritance. Use named type variations for recurring semantic
roles when the verified authoring route supports them; reserve per-node overrides
for actual exceptions. Inspect an unexpected local override before changing the
shared resource. [GUI skinning](https://docs.godotengine.org/en/4.6/tutorials/ui/gui_skinning.html)

For this game's design, specify a small palette, a few text sizes, spacing and
panel/button treatments. Populate normal, hover, pressed, disabled and keyboard
focus states, keeping a visible focus cue. Theme font size is not the font
resource: verify glyph coverage, readability and redistribution rights separately.
Use StyleBox content margins intentionally; padding changes can change minimum
sizes. Duplicate a shared StyleBox before a one-off edit that must not affect
other controls. Read resolved `get_theme_*` values in an authorized native check
when inheritance is in doubt; a list of item names cannot settle it.
[Theme API](https://docs.godotengine.org/en/4.6/classes/class_theme.html)

Preview the actual screen as well as the default Theme preview. Reload a scene
preview after editing its source, then review it again in the running game.
Record screenshots of interactive states, not only a pristine menu with no focus.
[Theme editor](https://docs.godotengine.org/en/4.6/tutorials/ui/gui_using_theme_editor.html)

## Focus and input are part of layout

Give the first relevant enabled control focus when a screen opens, using deferred
`grab_focus` when appropriate. Set deliberate directional neighbors and next/
previous order for complex screens; repair links when controls disappear. Restore
focus on closing a dialog or returning to a menu. Keep built-in `ui_*` navigation
separate from gameplay bindings. Test Tab/Shift-Tab, arrows or controller, confirm,
cancel and visible focus through pause, retry and repeated screen transitions.
[Keyboard/controller navigation](https://docs.godotengine.org/en/4.6/tutorials/ui/gui_navigation.html)

Use real pointer/touch input to verify blocked background clicks, hover, release
and activation on the intended target. Test keyboard-only operation independently.
State-changing shortcuts and direct `pressed` emissions can exercise logic, but
cannot prove focus order, hit rectangles, event propagation or touch usability.

## Validate the settled runtime layout

1. **Record the state and coordinate system.** Include scene/UI state, engine and
   adapter versions, logical viewport, window or browser canvas dimensions,
   stretch mode/aspect/scale, locale and the inspected frame. Record browser CSS
   size and device-pixel ratio for Web evidence. A desktop screenshot dimension
   is not the logical Godot viewport.
2. **Allow layout to settle.** Containers queue sorting. Adding controls,
   changing text/Theme, showing panels and resizing can trigger further nested
   sorts. Do not measure synchronously in `_ready()` or immediately after a
   mutation and call it final. A `sort_children` signal or one deferred callback
   alone does not prove the whole hierarchy settled. As a project QA strategy,
   sample geometry on later process frames until consecutive samples agree
   within a declared tolerance, with a bounded timeout; capture pixels after
   rendering when a renderer is available. Record frames waited and stability.
   A timeout is an unsettled result, never a pass. This strategy is not a new
   MCP tool or a universal fixed-frame guarantee.
   [Container sorting](https://docs.godotengine.org/en/4.6/classes/class_container.html)
3. **Check effective visibility.** Record both local `visible` and
   `is_visible_in_tree()` for relevant controls. A locally visible child of a
   hidden screen is not an on-screen overlap. Tree visibility still does not
   prove pixels are drawn: check clipping, cull/layer settings, alpha, covering
   controls and viewport intersection. Hidden-state geometry can be inspected
   separately; do not mix it into active-screen collision findings.
   [CanvasItem visibility](https://docs.godotengine.org/en/4.6/classes/class_canvasitem.html#class-canvasitem-method-is-visible-in-tree)
4. **Measure comparable rectangles.** Use `get_global_rect()` for ordinary
   unrotated UI in the same canvas; local `position`/`size` pairs from different
   parents are not comparable. Canvas-relative rectangles are not screen/CSS
   pixels. Non-default rotation/skew makes the simple rectangle unreliable;
   transform corners into one viewport space when required. Account for scale,
   CanvasLayers, viewport transforms and pixel-snapping tolerance. Check
   intentional containment/overlays separately from unwanted sibling overlap.
   [Control geometry](https://docs.godotengine.org/en/4.6/classes/class_control.html#class-control-method-get-global-rect)
5. **Inspect content and interaction.** Capture visible bounds, combined minimum
   size, relevant text, focus owner/order, disabled state and clipping context
   where the available route supports them. Follow runtime pagination to the end;
   an incomplete traversal cannot prove absence. Inspect actual rendered text
   for clipping, wrapping, truncation and missing glyphs. Then exercise real
   input and observe the intended state transition, with logs.

Test the intended base size, the smallest supported size, a narrow/portrait
viewport if supported, and a wide viewport; also resize while a modal and the
largest-content state are open. Choose stretch deliberately: `canvas_items`
renders 2D at target resolution; `viewport` renders the base viewport then
scales it. Aspect policy and layout reflow solve different problems. Record
unsupported dimensions honestly instead of claiming universal responsiveness.
[Multiple resolutions](https://docs.godotengine.org/en/4.6/tutorials/rendering/multiple_resolutions.html)

Keep static scene inspection, headless geometry checks, rendered native review,
native real input, exported Web browser input and physical-device review as
separate evidence scopes. Bind screenshots, geometry observations and input
results to the exact saved/exported bytes. For each tested state/size/locale,
record the expectation, observation and `passed`, `failed`, `not-tested` or
`blocked` status. Follow [Acceptance](acceptance.md) for the delivery gate.

## Close gaps without another runtime

The missing reusable capability is a **bounded, read-only settled UI audit**,
not another Theme writer. Until a real implementation is discovered, use
authorized project QA/native inspection and disclose its route. A future adapter
proposal should reuse its existing paging and main-thread budget contracts and
return state/frame, visibility, common-space bounds, minimum sizes, clipping
context and focus information with explicit omissions. It must distinguish
observations from visual/input acceptance and test hidden ancestors, nested
sorting, transformed controls, pagination and resize timing. This reference
does not register or claim that capability exists.

If implementation is separately authorized, patch the owning adapter source,
test it and replay the real host regression under [Production](production.md).
Do not edit a Python installation in place, add a parallel tool namespace, or
use a broad runtime script call to conceal a missing typed operation. Missing
host access remains `blocked`; documentation validation is not a Godot run.

### Inventory provenance

The inventory above inspected the installed package's `skills/*/SKILL.md`,
`tools.yaml`, Python dispatchers and the host files under
`godot_addon/addons/dcc_mcp_godot/`. The following SHA-256 values identify the
inspected bytes without exposing an environment-specific installation path:

| Package-relative source | SHA-256 |
| --- | --- |
| `skills/godot-theme-ui/tools.yaml` | `e628cc979baf77c154a20b0707f5a0c132f4ad4b2138341a57ec23b81faa93ea` |
| `skills/godot-scene/tools.yaml` | `7516be2e89af4c528766d6d7b3abcf4362393aa29eab9614e637fa48b23099b7` |
| `skills/godot-analysis/tools.yaml` | `7730b27d880d3410104489e2c6823909f51f75353cc386ead403a2c8be04fd85` |
| `godot_addon/addons/dcc_mcp_godot/capabilities.gd` | `01a5cb2f4cfe879c3d4729bea45c34d726b99a48238660b2aecf7a4d8dae7c5e` |
| `godot_addon/addons/dcc_mcp_godot/runtime_peer.gd` | `10d421815552aac58d047b780b96ee42555de7170766a29a68de068a5216f603` |
