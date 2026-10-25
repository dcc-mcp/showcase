"""Proposed D4 geometry helper: no engine, save, RNG or rule integration.

Integer cell coordinates use x right/y down; rot90 is clockwise. A floor uses
ONE fixed transform for its grid and all spatial entities. A stair target uses
the destination floor's transform. IDs, stats, budgets and stair up/down stay
unchanged. Historical metadata is retained as source annotation, not new proof.

Proposed additions (not frozen-runtime schema): events, hidden_events,
checkpoints, restore_points are stable-ID entity lists. Spatial fields are pos,
cells, path, rect {min,max}, facing (north/east/south/west), direction_vector,
direction_condition {mode: approach|facing, vector: cardinal unit vector}, and
nested trigger/triggers. Semantic payloads use IDs/flags, never undeclared
coordinates. Unsupported entity fields/kinds fail closed and need an adapter.

Actual-outcome symmetry dedup can exclude the previous layout even if another
transform name produces it. Fully symmetric content can have no changed choice.
This does not select a seed/respawn policy, create levels or add strategy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any


class D4(str, Enum):
    IDENTITY = "identity"
    ROT90 = "rot90"
    ROT180 = "rot180"
    ROT270 = "rot270"
    MIRROR_X = "mirror_x"
    MIRROR_X_ROT90 = "mirror_x_rot90"
    MIRROR_X_ROT180 = "mirror_x_rot180"
    MIRROR_X_ROT270 = "mirror_x_rot270"


ELEMENTS = tuple(D4)
_MATRIX = {
    D4.IDENTITY: (1, 0, 0, 1), D4.ROT90: (0, -1, 1, 0),
    D4.ROT180: (-1, 0, 0, -1), D4.ROT270: (0, 1, -1, 0),
    D4.MIRROR_X: (-1, 0, 0, 1), D4.MIRROR_X_ROT90: (0, -1, -1, 0),
    D4.MIRROR_X_ROT180: (1, 0, 0, -1), D4.MIRROR_X_ROT270: (0, 1, 1, 0),
}
_DIRECTION = {"north": (0, -1), "east": (1, 0),
              "south": (0, 1), "west": (-1, 0)}
_KINDS = {"key", "door", "enemy", "potion", "atk", "def", "gold", "shop",
          "stairs", "npc", "event", "hidden_event", "checkpoint", "restore_point"}
_ENTITY_FIELDS = {
    "id", "kind", "pos", "type", "amount", "victory", "direction", "target",
    "name", "facing", "direction_vector", "direction_condition", "cells", "path",
    "rect", "trigger", "triggers", "requires", "effects", "dialogue", "hidden",
    "event_id", "checkpoint_id", "appearance",
}
_SPATIAL_FIELDS = {"pos", "cells", "path", "rect", "facing",
                   "direction_vector", "direction_condition", "trigger", "triggers"}
_TRIGGER_FIELDS = _SPATIAL_FIELDS | {"requires", "effects", "event_id", "mode"}
_SEMANTIC_SPATIAL_KEYS = _SPATIAL_FIELDS | {
    "position", "cell", "location", "area", "bounds", "heading", "orientation",
    "rotation", "vector", "direction", "target", "target_pos", "destination",
    "floor", "coords", "coordinates",
    "points", "vertices", "waypoints", "trigger_cells", "interactive_areas",
    "markers", "regions", "radius", "range", "offset", "offsets", "anchor", "anchors",
}
_ENTITY_LISTS = ("objects", "events", "hidden_events", "checkpoints", "restore_points")
_NOVELTY_OMIT_FIELDS = {"id", "object_id", "target_id", "event_id", "checkpoint_id",
                        "name", "label", "dialogue"}
_ROOT_FIELDS = {
    "schema_version", "content_id", "title", "title_note", "build_recipe",
    "rules_assumptions", "initial_player", "variant_spawn_candidates", "enemies",
    "shops", "floors", "provenance", "validated_routes", "witness_routes",
    "resource_bounds", "validation_summary", "canonical_payload_sha256",
}
_FLOOR_FIELDS = {
    "id", "name", "group", "theme", "palette", "design_intent", "grid", "spawn",
    "objects", "topology", "safe_start_candidates", "events", "hidden_events",
    "checkpoints", "restore_points",
}
_TOPOLOGY_FIELDS = {"recipe", "selector", "room_centers", "edges", "main_path",
                    "choice_rooms", "bonus_leaves"}
_EFFECT_KINDS = {"open", "reveal", "set_flag", "grant_key", "checkpoint"}
_EFFECT_FIELDS = {"kind", "target_id", "flag", "key", "amount", "value"}


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer, excluding bool")
    return value


def _size(width: int, height: int) -> None:
    if _integer(width, "width") < 1 or _integer(height, "height") < 1:
        raise ValueError("grid dimensions must be positive")


def vector(value: Sequence[int], transform: D4 | str) -> tuple[int, int]:
    """Map a displacement without a coordinate translation."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("vector must contain exactly two integers")
    x, y = (_integer(value[0], "x"), _integer(value[1], "y"))
    a, b, c, d = _MATRIX[D4(transform)]
    return a * x + b * y, c * x + d * y


def dimensions(width: int, height: int, transform: D4 | str) -> tuple[int, int]:
    _size(width, height)
    a, b, c, d = _MATRIX[D4(transform)]
    return abs(a) * width + abs(b) * height, abs(c) * width + abs(d) * height


def point(value: Sequence[int], width: int, height: int,
          transform: D4 | str) -> tuple[int, int]:
    _size(width, height)
    x, y = vector(value, D4.IDENTITY)
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"point {(x, y)} is outside {width}x{height}")
    a, b, c, d = _MATRIX[D4(transform)]
    tx = min(0, a * (width - 1)) + min(0, b * (height - 1))
    ty = min(0, c * (width - 1)) + min(0, d * (height - 1))
    return a * x + b * y - tx, c * x + d * y - ty


def compose(after: D4 | str, before: D4 | str) -> D4:
    """Return after(before(p)); dimensions follow the first transform."""
    a, b, c, d = _MATRIX[D4(after)]
    e, f, g, h = _MATRIX[D4(before)]
    product = (a * e + b * g, a * f + b * h,
               c * e + d * g, c * f + d * h)
    return next(item for item, matrix in _MATRIX.items() if matrix == product)


def inverse(transform: D4 | str) -> D4:
    item = D4(transform)
    return next(other for other in ELEMENTS
                if compose(other, item) is D4.IDENTITY)


def direction(name: str, transform: D4 | str) -> str:
    """Only compass names; upstairs/downstairs are not spatial vectors."""
    if name not in _DIRECTION:
        raise ValueError("spatial direction must be north/east/south/west")
    mapped = vector(_DIRECTION[name], transform)
    return next(label for label, value in _DIRECTION.items() if value == mapped)


def _grid_size(rows: Sequence[str]) -> tuple[int, int]:
    if not isinstance(rows, (list, tuple)) or not rows or not all(
            isinstance(row, str) and row for row in rows):
        raise ValueError("grid must contain nonempty string rows")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("grid rows must have equal widths")
    return width, len(rows)


def grid(rows: Sequence[str], transform: D4 | str) -> list[str]:
    width, height = _grid_size(rows)
    out_width, out_height = dimensions(width, height, transform)
    result = [[""] * out_width for _ in range(out_height)]
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            nx, ny = point((x, y), width, height, transform)
            result[ny][nx] = cell
    return ["".join(row) for row in result]


def _semantic(value: Any) -> None:
    if isinstance(value, Mapping):
        if _SEMANTIC_SPATIAL_KEYS.intersection(value):
            raise ValueError("semantic payload contains undeclared spatial data")
        for child in value.values():
            _semantic(child)
    elif isinstance(value, list):
        for child in value:
            _semantic(child)


def _spatial_fields(item: dict[str, Any], width: int, height: int,
                    transform: D4, *, trigger: bool = False) -> None:
    unknown = set(item) - (_TRIGGER_FIELDS if trigger else _ENTITY_FIELDS)
    if unknown:
        raise ValueError(f"unsupported proposed spatial/entity fields: {sorted(unknown)}")
    if "pos" in item:
        item["pos"] = list(point(item["pos"], width, height, transform))
    for key in ("cells", "path"):
        if key in item:
            if not isinstance(item[key], list):
                raise ValueError(f"{key} must be a list of cells")
            item[key] = [list(point(cell, width, height, transform))
                         for cell in item[key]]
    if "rect" in item:
        rect = item["rect"]
        if not isinstance(rect, dict) or set(rect) != {"min", "max"}:
            raise ValueError("rect must contain min and max cells")
        if any(rect["min"][axis] > rect["max"][axis] for axis in (0, 1)):
            raise ValueError("rect min must precede max on each axis")
        low = point(rect["min"], width, height, transform)
        high = point(rect["max"], width, height, transform)
        item["rect"] = {"min": [min(low[0], high[0]), min(low[1], high[1])],
                        "max": [max(low[0], high[0]), max(low[1], high[1])]}
    if "facing" in item:
        item["facing"] = direction(item["facing"], transform)
    if "direction_vector" in item:
        item["direction_vector"] = list(vector(item["direction_vector"], transform))
    if "direction_condition" in item:
        condition = item["direction_condition"]
        if (not isinstance(condition, dict) or set(condition) != {"mode", "vector"}
                or condition["mode"] not in {"approach", "facing"}):
            raise ValueError("direction condition requires explicit mode and vector")
        mapped = vector(condition["vector"], transform)
        if mapped not in _DIRECTION.values():
            raise ValueError("direction condition must use a cardinal unit vector")
        condition["vector"] = list(mapped)
    if "trigger" in item:
        if not isinstance(item["trigger"], dict):
            raise ValueError("trigger must be an explicit spatial dictionary")
        _spatial_fields(item["trigger"], width, height, transform, trigger=True)
    if "triggers" in item:
        if not isinstance(item["triggers"], list):
            raise ValueError("triggers must be explicit spatial dictionaries")
        for child in item["triggers"]:
            if not isinstance(child, dict):
                raise ValueError("trigger must be a dictionary")
            _spatial_fields(child, width, height, transform, trigger=True)
    if trigger and "mode" in item and item["mode"] not in {"enter", "leave", "step", "interact"}:
        raise ValueError("trigger mode needs an explicit non-chiral supported operation")
    if "effects" in item:
        if not isinstance(item["effects"], list):
            raise ValueError("effects must be explicit supported ID/flag operations")
        for effect in item["effects"]:
            if (not isinstance(effect, dict) or set(effect) - _EFFECT_FIELDS
                    or effect.get("kind") not in _EFFECT_KINDS):
                raise ValueError("effect needs an explicit non-spatial ID/flag adapter")
            kind = effect["kind"]
            if kind in {"open", "reveal", "checkpoint"}:
                if (set(effect) != {"kind", "target_id"}
                        or not isinstance(effect["target_id"], str) or not effect["target_id"]):
                    raise ValueError("ID effect requires exactly one nonempty target_id string")
            elif kind == "set_flag":
                if (set(effect) != {"kind", "flag", "value"}
                        or not isinstance(effect["flag"], str) or not effect["flag"]
                        or type(effect["value"]) is not bool):
                    raise ValueError("set_flag requires a nonempty flag and boolean value")
            elif kind == "grant_key":
                if (set(effect) != {"kind", "key", "amount"}
                        or not isinstance(effect["key"], str) or not effect["key"]
                        or type(effect["amount"]) is not int or effect["amount"] <= 0):
                    raise ValueError("grant_key requires a nonempty key and positive integer amount")
    if "requires" in item:
        requirement = item["requires"]
        if (not isinstance(requirement, dict)
                or set(requirement) - {"flag", "event_id", "object_id", "value"}
                or len(set(requirement) & {"flag", "event_id", "object_id"}) != 1
                or any(not isinstance(requirement[key], str) or not requirement[key]
                       for key in set(requirement) & {"flag", "event_id", "object_id"})
                or ("value" in requirement and type(requirement["value"]) is not bool)):
            raise ValueError("requires needs one explicit stable ID/flag condition")
    for key in set(item) - _SPATIAL_FIELDS - {"target"}:
        _semantic(item[key])
    if "direction" in item and item.get("kind") != "stairs":
        raise ValueError("use explicit facing/direction_vector for spatial direction")
    if "target" in item and item.get("kind") != "stairs":
        raise ValueError("non-stair targets need an explicit spatial adapter")
    if item.get("kind") == "stairs" and item.get("direction") not in {"up", "down"}:
        raise ValueError("stair direction must retain its up/down floor meaning")


def _catalog(layout: Mapping[str, Any]) -> tuple[dict[int, dict[str, Any]],
                                              dict[str, tuple[int, dict[str, Any]]]]:
    if not isinstance(layout, Mapping) or set(layout) - _ROOT_FIELDS:
        raise ValueError("unknown root field needs an explicit spatial adapter")
    if not isinstance(layout.get("floors"), list) or not layout["floors"]:
        raise ValueError("layout must contain floors")
    floors: dict[int, dict[str, Any]] = {}
    entities: dict[str, tuple[int, dict[str, Any]]] = {}
    for floor in layout["floors"]:
        if not isinstance(floor, dict):
            raise ValueError("floor must be a dictionary")
        if set(floor) - _FLOOR_FIELDS:
            raise ValueError("unknown floor field needs an explicit spatial adapter")
        if ("topology" in floor and
                (not isinstance(floor["topology"], dict)
                 or set(floor["topology"]) - _TOPOLOGY_FIELDS)):
            raise ValueError("unknown topology field needs an explicit spatial adapter")
        floor_id = _integer(floor["id"], "floor id")
        if floor_id < 1 or floor_id in floors:
            raise ValueError("floor IDs must be unique positive integers")
        floors[floor_id] = floor
        width, height = _grid_size(floor["grid"])
        if "spawn" in floor:
            sx, sy = point(floor["spawn"], width, height, D4.IDENTITY)
            if floor["grid"][sy][sx] == "#":
                raise ValueError("spawn must not be a wall")
        occupied: set[tuple[int, int]] = set()
        for field in _ENTITY_LISTS:
            if not isinstance(floor.get(field, []), list):
                raise ValueError(f"{field} must be a list")
            for item in floor.get(field, []):
                if not isinstance(item, dict):
                    raise ValueError("entity must be a dictionary")
                stable_id = item.get("id")
                if not isinstance(stable_id, str) or not stable_id or stable_id in entities:
                    raise ValueError("all entity IDs must be unique nonempty strings")
                if item.get("kind") not in _KINDS:
                    raise ValueError("unknown entity kind needs an explicit spatial adapter")
                # All public entries, including previous-layout fingerprints,
                # use the same fail-closed adapter without mutating the input.
                _spatial_fields(deepcopy(item), width, height, D4.IDENTITY)
                x, y = point(item["pos"], width, height, D4.IDENTITY)
                if field == "objects":
                    if (x, y) in occupied or floor["grid"][y][x] == "#":
                        raise ValueError("main objects require unique non-wall cells")
                    occupied.add((x, y))
                entities[stable_id] = floor_id, item
    first = layout["floors"][0]
    if ("variant_spawn_candidates" in layout and "safe_start_candidates" in first
            and layout["variant_spawn_candidates"] != first["safe_start_candidates"]):
        raise ValueError("first-floor safe-start aliases must agree in canonical order")
    for source_floor, item in entities.values():
        if item.get("kind") != "stairs":
            continue
        target = item.get("target")
        if not isinstance(target, dict) or set(target) != {"floor", "pos", "object_id"}:
            raise ValueError("stairs require destination floor, pos and stable object_id")
        destination = _integer(target["floor"], "target floor")
        found = entities.get(target["object_id"])
        if (destination not in floors or found is None or found[0] != destination
                or found[1].get("kind") != "stairs"
                or target["pos"] != found[1]["pos"]):
            raise ValueError("stair destination coordinates and stable ID must agree")
        reverse = found[1].get("target", {})
        if (reverse.get("floor") != source_floor or reverse.get("object_id") != item["id"]
                or reverse.get("pos") != item["pos"]):
            raise ValueError("this proposal requires reciprocal stair IDs and landing cells")
        if ((item.get("direction") == "up" and destination <= source_floor)
                or (item.get("direction") == "down" and destination >= source_floor)):
            raise ValueError("stair up/down must agree with its destination floor")
    return floors, entities


def transform_layout(layout: Mapping[str, Any],
                     transforms: D4 | str | Mapping[int, D4 | str]) -> dict[str, Any]:
    """Deep-copy a complete layout; never write a file or set active game state."""
    floors, _ = _catalog(layout)
    if isinstance(transforms, Mapping):
        if (any(type(key) is not int for key in transforms)
                or set(transforms) != set(floors)):
            raise ValueError("supply one fixed transform for every exact floor ID")
        choices = {floor_id: D4(transforms[floor_id]) for floor_id in floors}
    else:
        choices = {floor_id: D4(transforms) for floor_id in floors}
    sizes = {floor_id: _grid_size(floor["grid"]) for floor_id, floor in floors.items()}
    result = deepcopy(dict(layout))
    for floor in result["floors"]:
        floor_id = floor["id"]
        width, height = sizes[floor_id]
        choice = choices[floor_id]
        floor["grid"] = grid(floor["grid"], choice)
        if "spawn" in floor:
            floor["spawn"] = list(point(floor["spawn"], width, height, choice))
        if "safe_start_candidates" in floor:
            floor["safe_start_candidates"] = [
                list(point(cell, width, height, choice))
                for cell in floor["safe_start_candidates"]]
        if "topology" in floor and "room_centers" in floor["topology"]:
            floor["topology"]["room_centers"] = {
                room_id: list(point(cell, width, height, choice))
                for room_id, cell in floor["topology"]["room_centers"].items()}
        for field in _ENTITY_LISTS:
            for item in floor.get(field, []):
                _spatial_fields(item, width, height, choice)
                if item.get("kind") == "stairs":
                    target = item["target"]
                    target_width, target_height = sizes[target["floor"]]
                    target["pos"] = list(point(target["pos"], target_width,
                                               target_height, choices[target["floor"]]))
    if "variant_spawn_candidates" in result:
        first_id = result["floors"][0]["id"]
        width, height = sizes[first_id]
        result["variant_spawn_candidates"] = [
            list(point(cell, width, height, choices[first_id]))
            for cell in result["variant_spawn_candidates"]]
    _catalog(result)
    return result


def _without_identity(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _without_identity(child) for key, child in value.items()
                if key not in _NOVELTY_OMIT_FIELDS}
    if isinstance(value, list):
        return [_without_identity(child) for child in value]
    return value


def _encounter_projection(entity: Mapping[str, Any], layout: Mapping[str, Any]) -> Any:
    """Resolve opaque monster/shop aliases; no graph-isomorphism or runtime claim."""
    result = _without_identity(entity)
    if entity.get("kind") == "enemy":
        definition = layout.get("enemies", {}).get(entity.get("type"))
        if (not isinstance(definition, dict)
                or set(definition) - {"name", "hp", "atk", "def", "gold", "appearance"}
                or not {"hp", "atk", "def", "gold"} <= set(definition)):
            raise ValueError("enemy projection requires explicit stats/optional appearance")
        result.pop("type", None)
        result["encounter"] = _without_identity(definition)
    elif entity.get("kind") == "shop":
        definition = layout.get("shops", {}).get(entity.get("type"))
        if (not isinstance(definition, dict) or set(definition) - {"name", "offers"}
                or not isinstance(definition.get("offers"), list)):
            raise ValueError("shop projection requires explicit offers")
        offers = []
        for offer in definition["offers"]:
            if (not isinstance(offer, dict)
                    or set(offer) - {"id", "label", "cost", "kind", "amount", "limit"}):
                raise ValueError("shop offer projection needs an explicit adapter")
            offers.append(_without_identity(offer))
        result.pop("type", None)
        result["offers"] = sorted(offers, key=_json)
    elif entity.get("kind") == "npc" and "type" in entity:
        raise ValueError("opaque NPC type requires an explicit encounter adapter")
    return result


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def spatial_fingerprint(layout: Mapping[str, Any]) -> str:
    """Conservative spatial occupancy key, not a semantic-equivalence proof.

    Stable-ID spelling, text labels, room recipes and historical evidence are excluded.
    Entity multiplicity/kind/amount, declared appearance, numeric enemy stats,
    shop terms, key/door colours, trigger geometry and facing remain. Enemy/shop
    opaque type aliases are resolved before comparison; text is not novelty.
    Excluding reference IDs is conservative: it may reject an available novelty,
    but cannot claim novelty solely from swapping identical IDs/text labels.
    Different ID/event bindings may collapse here; this key must NEVER authorize
    state substitution, save loading, event equivalence or gameplay proofs.
    Hidden event
    differences are spatial differences, not evidence that a player sees them.
    """
    _catalog(layout)
    rows = []
    for floor in layout["floors"]:
        item = {"floor": floor["id"], "grid": floor["grid"], "spawn": floor.get("spawn")}
        for field in _ENTITY_LISTS:
            entities = [_encounter_projection(entity, layout)
                        for entity in floor.get(field, [])]
            item[field] = sorted(entities, key=_json)
        rows.append(item)
    return sha256(_json(sorted(rows, key=lambda floor: floor["floor"])).encode()).hexdigest()


@dataclass(frozen=True)
class LayoutChoices:
    representatives: tuple[D4, ...]
    equivalence_groups: tuple[tuple[D4, ...], ...]
    previous_fingerprint: str | None
    spatial_change_possible: bool


def distinct_layout_choices(layout: Mapping[str, Any], *,
                            previous_layout: Mapping[str, Any] | None = None) -> LayoutChoices:
    """Deduplicate actual content; caller owns any seed/attempt selection.

    Without a previous layout the representatives include the unchanged outcome;
    spatial_change_possible still compares against the input. With a previous
    layout, every equivalent outcome is excluded, whatever its enum name.
    """
    previous = None if previous_layout is None else spatial_fingerprint(previous_layout)
    comparison = spatial_fingerprint(layout) if previous is None else previous
    groups: dict[str, list[D4]] = {}
    for transform in ELEMENTS:
        fingerprint = spatial_fingerprint(transform_layout(layout, transform))
        groups.setdefault(fingerprint, []).append(transform)
    representatives = tuple(group[0] for fingerprint, group in groups.items()
                            if fingerprint != previous)
    return LayoutChoices(representatives, tuple(tuple(group) for group in groups.values()),
                         previous, any(fingerprint != comparison for fingerprint in groups))
