#!/usr/bin/env python3
"""Build original, fixed 21-floor content. No runtime random placement or downloads.

The curated room-tree selectors, object roles and integer stat tables below are
the source recipe. The output JSON contains every wall, object and position
explicitly. Python's budget ledger is an independent design calculation; actual
acceptance must replay these witnesses through the production Godot rules.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path


CONTENT_ID = "stairkeep-campaign-21/v1"
BUILD_VERSION = "original-room-trees-1"
CENTERS = {n: (2 + 4 * (n % 3), 2 + 4 * (n // 3)) for n in range(9)}
LATTICE_EDGES = sorted([(i, i + 1) for i in range(9) if i % 3 < 2]
                       + [(i, i + 3) for i in range(6)])
# (main-path node count, pre-exit optional leaf count, sorted-tree selector).
# All 21 literal selections are unique. This is build-time enumeration of a
# small fixed graph catalog, not RNG or runtime generation.
CURATION = [
    (5, 2, 0), (5, 3, 0), (5, 4, 0),
    (5, 3, 1), (5, 2, 10), (5, 4, 1),
    (7, 2, 0), (7, 2, 1), (5, 3, 10),
    (5, 4, 2), (5, 2, 20), (7, 2, 2),
    (7, 2, 3), (5, 3, 20), (5, 2, 30),
    (5, 3, 25), (7, 2, 4), (5, 4, 3),
    (5, 3, 30), (7, 2, 5), (5, 2, 40),
]
GROUPS = [
    ("苔门", "moss", "石青、苔绿、暖铜", "钥匙与先手预览；第一处高防门槛与锻炉。"),
    ("雨井", "rainwell", "湿石、青白、旧木", "跨三层携带蓝钥匙；黄金与永久属性的支线收益。"),
    ("铜炉", "copper", "锻铜、黑铁、琥珀", "长主路与有守卫的攻击房；铸甲减少多次回击。"),
    ("镜藏", "archive", "银灰、深紫、星光", "分叉档案室与可回访锻炉；固定楼梯检验层状态。"),
    ("霜桥", "frost", "霜白、冷蓝、淡金", "窄桥主路与有守卫的攻击房；攻击/防御两种成本。"),
    ("余烬", "ember", "暗红、炭黑、白热", "后置锻炉在18层；16–17层先使用既有投资。"),
    ("星冠", "crown", "靛蓝、淡红、星银", "19层仅有限补给；21层最终监守是唯一胜利触发。"),
]
FORGE_FLOORS = [1, 4, 7, 10, 13, 18]
POLICIES = {
    "blade": {"label": "锋刃路线", "branch": "attack", "armor": True, "heals": 2, "side": "all"},
    "bulwark": {"label": "铸甲路线", "branch": "defense", "armor": True, "heals": 2, "side": "none"},
    "balanced": {"label": "交替投资路线", "branch": "alternate", "armor": True, "heals": 2, "side": "odd"},
    "frugal": {"label": "节制锋刃路线（省镜藏铸甲）", "branch": "attack", "armor": True, "heals": 2, "side": "none", "skip_ward_floors": [10]},
}


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def graph_catalog() -> dict[tuple[int, int], list[dict]]:
    catalog: dict[tuple[int, int], list[dict]] = {}
    for edges in itertools.combinations(LATTICE_EDGES, 8):
        adjacency = {n: [] for n in range(9)}
        for a, b in edges:
            adjacency[a].append(b)
            adjacency[b].append(a)
        parent, queue = {6: None}, deque([6])
        while queue:
            node = queue.popleft()
            for n in adjacency[node]:
                if n not in parent:
                    parent[n] = node
                    queue.append(n)
        if len(parent) != 9:
            continue
        path, node = [], 2
        while node is not None:
            path.append(node)
            node = parent[node]
        path.reverse()
        leaves = [n for n in range(9) if len(adjacency[n]) == 1 and n not in path]
        pre_exit_leaves = []
        for leaf in leaves:
            ancestor = parent[leaf]
            while ancestor not in path:
                ancestor = parent[ancestor]
            if ancestor != 2:
                pre_exit_leaves.append(leaf)
        if len(pre_exit_leaves) < 2:
            continue
        key = (len(path), len(pre_exit_leaves))
        catalog.setdefault(key, []).append({
            "edges": [list(e) for e in edges], "parent": parent,
            "path": path, "leaves": leaves, "pre_exit_leaves": pre_exit_leaves,
        })
    return catalog


def midpoint(a: int, b: int) -> list[int]:
    return [(CENTERS[a][0] + CENTERS[b][0]) // 2, (CENTERS[a][1] + CENTERS[b][1]) // 2]


def add(a: tuple[int, int] | list[int], b: tuple[int, int] | list[int], scale: int = 1) -> list[int]:
    return [a[0] + b[0] * scale, a[1] + b[1] * scale]


def obj(identifier: str, kind: str, pos: list[int] | tuple[int, int], **fields: object) -> dict:
    return {"id": identifier, "kind": kind, "pos": list(pos), **fields}


def make_shop(group: int, supply: bool = False) -> dict:
    if supply:
        return {"name": "星冠补给站", "offers": [
            {"id": "flask", "label": "封存补给", "cost": 48, "kind": "potion", "amount": 180, "limit": 2}
        ]}
    return {"name": GROUPS[group - 1][0] + "锻炉", "offers": [
        {"id": "edge", "label": "磨刃", "cost": 28 + 6 * (group - 1), "kind": "atk", "amount": 4, "limit": 1},
        {"id": "ward", "label": "铸甲", "cost": 28 + 6 * (group - 1), "kind": "def", "amount": 3, "limit": 1},
        {"id": "flask", "label": "补给", "cost": 24 + 4 * (group - 1), "kind": "potion", "amount": 160, "limit": 2},
    ]}


def make_floor(number: int, graph: dict, enemies: dict) -> dict:
    prefix, group = f"f{number:02d}", (number - 1) // 3 + 1
    name, theme, palette, intent = GROUPS[group - 1]
    grid = [["#"] * 13 for _ in range(13)]
    for cx, cy in CENTERS.values():
        for y in range(cy - 1, cy + 2):
            for x in range(cx - 1, cx + 2):
                grid[y][x] = "."
    for a, b in graph["edges"]:
        x, y = midpoint(a, b)
        grid[y][x] = "."
    objects = [
        obj(prefix + "_core_atk", "atk", [1, 9], amount=2),
        obj(prefix + "_core_def", "def", [2, 9], amount=1),
        obj(prefix + "_entry_gold", "gold", [3, 9], amount=16),
        obj(prefix + "_choice_key", "key", [1, 10], type="yellow", amount=1),
    ]
    if (number - 1) % 3 == 0:
        objects.append(obj(prefix + "_chapter_key", "key", [1, 11], type="blue", amount=1))
    if number > 1:
        objects.append(obj(prefix + "_down", "stairs", CENTERS[6], direction="down",
                           target={"floor": number - 1, "pos": list(CENTERS[2]), "object_id": f"f{number - 1:02d}_up"}))
    if number < 21:
        objects.append(obj(prefix + "_up", "stairs", CENTERS[2], direction="up",
                           target={"floor": number + 1, "pos": list(CENTERS[6]), "object_id": f"f{number + 1:02d}_down"}))
    path = graph["path"]
    first_type, second_type = prefix + "_scout", prefix + "_guard"
    enemies[first_type] = {"name": name + "巡卫", "hp": 36 + 5 * number, "atk": 14 + 4 * number, "def": 5 + 3 * number, "gold": 14}
    enemies[second_type] = {"name": name + "重卫", "hp": 45 + 6 * number, "atk": 17 + 4 * number, "def": 7 + 3 * number, "gold": 16}
    if number == 1:
        enemies[second_type] = {"name": "石甲门卫", "hp": 12, "atk": 20, "def": 28, "gold": 16}
    objects += [
        obj(prefix + "_scout", "enemy", midpoint(path[0], path[1]), type=first_type),
        obj(prefix + "_guard", "enemy", midpoint(path[1], path[2]), type=second_type),
        obj(prefix + "_trail_potion", "potion", add(CENTERS[path[1]], [1, 1]), amount=45),
    ]
    if number in FORGE_FLOORS or number == 19:
        objects.append(obj(prefix + "_shop", "shop", add(CENTERS[path[1]], [-1, -1]),
                           type="supply7" if number == 19 else f"forge{group}"))
    if number % 3 == 0:
        objects.append(obj(prefix + "_chapter_door", "door", midpoint(path[-3], path[-2]), type="blue"))
        boss_type = prefix + "_boss"
        enemies[boss_type] = {"name": name + "监守", "hp": 70 + 9 * number, "atk": 21 + 4 * number, "def": 10 + 3 * number, "gold": 30}
        if number == 21:
            enemies[boss_type] = {"name": "星冠塔心监守", "hp": 420, "atk": 116, "def": 78, "gold": 70}
        objects.append(obj(prefix + "_boss", "enemy", midpoint(path[-2], path[-1]), type=boss_type, victory=number == 21))
    # Different fixed tree leaves supply independent, single-entry choice rooms.
    attack_leaf, defense_leaf = graph["pre_exit_leaves"][:2]
    branch_metadata = {}
    for branch, leaf in [("attack", attack_leaf), ("defense", defense_leaf)]:
        parent = graph["parent"][leaf]
        center, pc = CENTERS[leaf], CENTERS[parent]
        direction = [(center[0] - pc[0]) // 4, (center[1] - pc[1]) // 4]
        tangent = [-direction[1], direction[0]]
        branch_metadata[branch] = leaf
        objects.append(obj(prefix + "_" + branch + "_door", "door", midpoint(leaf, parent), type="yellow"))
        if branch == "attack":
            guarded = group in [3, 5]
            gem_pos = add(center, direction) if guarded else list(center)
            if guarded:
                for sign in [-1, 1]:
                    x, y = add(center, tangent, sign)
                    grid[y][x] = "#"
                guard_type = prefix + "_blade_guard"
                enemies[guard_type] = {"name": name + "藏刃守卫", "hp": 25 + 4 * number, "atk": 17 + 4 * number, "def": 8 + 3 * number, "gold": 12}
                objects.append(obj(prefix + "_blade_guard", "enemy", center, type=guard_type))
            objects.append(obj(prefix + "_attack_gem", "atk", gem_pos, amount=3))
            objects.append(obj(prefix + "_attack_gold", "gold", add(gem_pos, tangent), amount=10))
        else:
            objects.append(obj(prefix + "_defense_gem", "def", center, amount=2))
            objects.append(obj(prefix + "_defense_potion", "potion", add(center, tangent), amount=20))
            objects.append(obj(prefix + "_defense_gold", "gold", add(center, direction), amount=10))
    bonus_leaves = [n for n in graph["leaves"] if n not in [attack_leaf, defense_leaf]]
    if bonus_leaves:
        leaf = bonus_leaves[0]
        parent = graph["parent"][leaf]
        center, pc = CENTERS[leaf], CENTERS[parent]
        direction = [(center[0] - pc[0]) // 4, (center[1] - pc[1]) // 4]
        tangent = [-direction[1], direction[0]]
        bonus_type = prefix + "_cache_guard"
        enemies[bonus_type] = {"name": name + "藏箱守卫", "hp": 44 + 5 * number, "atk": 20 + 4 * number, "def": 9 + 3 * number, "gold": 18}
        objects += [
            obj(prefix + "_cache_guard", "enemy", midpoint(leaf, parent), type=bonus_type),
            obj(prefix + "_cache_potion", "potion", center, amount=35),
            obj(prefix + "_cache_gold", "gold", add(center, tangent), amount=12),
        ]
    if len(bonus_leaves) > 1:
        objects.append(obj(prefix + "_open_cache", "gold", CENTERS[bonus_leaves[1]], amount=12))
    if number == 21:
        enemies["sealed_sentinel"] = {"name": "封印哨兵", "hp": 500, "atk": 180, "def": 999, "gold": 0}
        objects.append(obj(prefix + "_sealed_sentinel", "enemy", add(CENTERS[path[1]], [-1, 1]), type="sealed_sentinel"))
    return {
        "id": number, "name": f"{number:02d} · {name} · {['启程', '取舍', '兑现'][(number - 1) % 3]}",
        "group": group, "theme": theme, "palette": palette, "design_intent": intent,
        "grid": ["".join(row) for row in grid], "spawn": list(CENTERS[6]),
        "objects": sorted(objects, key=lambda o: o["id"]),
        "topology": {"recipe": BUILD_VERSION, "selector": list(CURATION[number - 1]),
                     "room_centers": {str(k): list(v) for k, v in CENTERS.items()},
                     "edges": graph["edges"], "main_path": path,
                     "choice_rooms": branch_metadata, "bonus_leaves": bonus_leaves},
    }


def calculate_budget(data: dict, name: str, events: list[str]) -> dict:
    state = deepcopy(data["initial_player"])
    objects = {o["id"]: o for f in data["floors"] for o in f["objects"]}
    cleared, purchases, ledger = set(), {}, []
    won = False
    for event in events:
        row = {"event": event}
        if event.startswith("buy:"):
            shop_id, choice = event[4:].split("/")
            offer = next(o for o in data["shops"][objects[shop_id]["type"]]["offers"] if o["id"] == choice)
            assert purchases.get(event, 0) < offer["limit"], (name, event, "stock")
            assert state["gold"] >= offer["cost"], (name, event, "gold", state)
            purchases[event] = purchases.get(event, 0) + 1
            state["gold"] -= offer["cost"]
            state["hp" if offer["kind"] == "potion" else offer["kind"]] += offer["amount"]
        else:
            item = objects[event]
            kind = item["kind"]
            if kind != "stairs":
                assert event not in cleared, (name, event, "duplicate")
                cleared.add(event)
            if kind == "enemy":
                enemy = data["enemies"][item["type"]]
                hit = state["atk"] - enemy["def"]
                assert hit > 0, (name, event, "armor", state, enemy)
                rounds = (enemy["hp"] + hit - 1) // hit
                damage = (rounds - 1) * max(0, enemy["atk"] - state["def"])
                assert state["hp"] > damage, (name, event, "hp", state, enemy, damage)
                state["hp"] -= damage
                state["gold"] += enemy["gold"]
                won = bool(item.get("victory", False))
                row.update(damage=damage, rounds=rounds)
            elif kind == "door":
                assert state["keys"][item["type"]] > 0, (name, event, "key", state)
                state["keys"][item["type"]] -= 1
            elif kind == "key":
                state["keys"][item["type"]] += item["amount"]
            elif kind in ["potion", "atk", "def", "gold"]:
                state["hp" if kind == "potion" else kind] += item["amount"]
        row["state"] = deepcopy(state)
        ledger.append(row)
    assert won, (name, "not_won")
    return {"name": name, "policy": POLICIES[name]["label"], "events": events,
            "ledger": ledger, "final": {**deepcopy(state), "won": won},
            "design_calculation": "integer budget only; production Godot replay required"}


def route_events(data: dict, name: str) -> list[str]:
    policy, events = POLICIES[name], []
    scheduled_heals = {f + 1: (f, policy["heals"]) for f in FORGE_FLOORS}
    scheduled_heals[20] = (19, 1)
    for floor in data["floors"]:
        number, prefix = floor["id"], f"f{floor['id']:02d}"
        ids = {o["id"] for o in floor["objects"]}
        # DEF is adjacent to the empty arrival component; it opens the approach
        # to the corner ATK pickup without silently collecting another object.
        events += [prefix + "_core_def", prefix + "_core_atk", prefix + "_entry_gold", prefix + "_choice_key"]
        if prefix + "_chapter_key" in ids:
            events.append(prefix + "_chapter_key")
        events += [prefix + "_scout", prefix + "_trail_potion"]
        if number in FORGE_FLOORS:
            events.append("buy:" + prefix + "_shop/edge")
        events.append(prefix + "_guard")
        if number % 3 == 0:
            events.append(prefix + "_chapter_door")
        branch = policy["branch"]
        if branch == "alternate":
            branch = "attack" if number % 2 else "defense"
        events.append(prefix + "_" + branch + "_door")
        if branch == "attack":
            if prefix + "_blade_guard" in ids:
                events.append(prefix + "_blade_guard")
            events += [prefix + "_attack_gem", prefix + "_attack_gold"]
        else:
            events += [prefix + "_defense_gem", prefix + "_defense_potion", prefix + "_defense_gold"]
        if number in FORGE_FLOORS and policy["armor"] and number not in policy.get("skip_ward_floors", []):
            events.append("buy:" + prefix + "_shop/ward")
        if number in scheduled_heals:
            shop_floor, count = scheduled_heals[number]
            events += [f"buy:f{shop_floor:02d}_shop/flask"] * count
        if number % 3 == 0:
            events.append(prefix + "_boss")
        side = policy["side"] == "all" or policy["side"] == "odd" and number % 2
        if side and number != 21 and prefix + "_cache_guard" in ids:
            events += [prefix + "_cache_guard", prefix + "_cache_potion", prefix + "_cache_gold"]
        if side and number != 21 and prefix + "_open_cache" in ids:
            events.append(prefix + "_open_cache")
        if number < 21:
            events.append(prefix + "_up")
    return events


def reachable(grid: list[str], start: list[int], blocked: set[tuple[int, int]]) -> set[tuple[int, int]]:
    queue, visited = deque([tuple(start)]), {tuple(start)}
    while queue:
        x, y = queue.popleft()
        for nx, ny in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            if not (0 <= ny < len(grid) and 0 <= nx < len(grid[ny])) or grid[ny][nx] == "#":
                continue
            if (nx, ny) not in visited and (nx, ny) not in blocked:
                visited.add((nx, ny)); queue.append((nx, ny))
    return visited


def validate(data: dict) -> None:
    ids, topologies = set(), set()
    by_id = {o["id"]: (f, o) for f in data["floors"] for o in f["objects"]}
    victories = []
    for floor in data["floors"]:
        assert len(floor["grid"]) == 13 and all(len(r) == 13 for r in floor["grid"])
        topology = tuple(tuple(e) for e in floor["topology"]["edges"])
        assert topology not in topologies, (floor["id"], "repeated_topology")
        topologies.add(topology)
        cells = set()
        for item in floor["objects"]:
            assert item["id"] not in ids, item["id"]
            ids.add(item["id"])
            x, y = item["pos"]
            assert floor["grid"][y][x] == ".", (item["id"], "wall")
            assert (x, y) not in cells, (item["id"], "overlap")
            cells.add((x, y))
            if item.get("victory"):
                victories.append((floor["id"], item["id"]))
            if item["kind"] == "stairs":
                target_floor, target = by_id[item["target"]["object_id"]]
                assert target_floor["id"] == item["target"]["floor"]
                assert target["pos"] == item["target"]["pos"]
                assert target["target"]["object_id"] == item["id"]
        # Every authored room remains connected when objects are considered
        # interactable; a guarded blade vault has a traversable enemy center.
        assert len(reachable(floor["grid"], floor["spawn"], set())) == sum(r.count(".") for r in floor["grid"])
    assert victories == [(21, "f21_boss")]
    first = data["floors"][0]
    blockers = {tuple(o["pos"]) for o in first["objects"]}
    component = reachable(first["grid"], first["spawn"], blockers)
    candidates = data["variant_spawn_candidates"]
    assert candidates == first["safe_start_candidates"], "legacy root alias must match the floor-owned source"
    assert candidates == sorted(candidates, key=lambda p: (p[1], p[0])) and len(candidates) == 4
    for candidate in candidates:
        assert tuple(candidate) not in blockers and tuple(candidate) in component
        assert all(abs(candidate[0] - o["pos"][0]) + abs(candidate[1] - o["pos"][1]) > 1
                   for o in first["objects"] if o["kind"] == "enemy")
    data["validation_summary"] = {
        "floor_count": 21, "distinct_fixed_topologies": len(topologies), "object_count": len(ids),
        "unique_ids_and_positions": True, "all_floor_cells_connected_without_object_blockers": True,
        "stairs_bidirectional": True, "only_final_boss_victory": True, "safe_spawn_candidates": 4,
        "budget_witness_count": len(data["validated_routes"]), "runtime_random_placement": False,
        "production_rules_replay": "not-tested by this builder", "browser_play": "not-tested",
    }


def resource_bounds(data: dict) -> dict:
    source = {"hp": 0, "atk": 0, "def": 0, "gold": 0, "keys": {"yellow": 0, "blue": 0}}
    counts = Counter()
    for floor in data["floors"]:
        for item in floor["objects"]:
            kind = item["kind"]; counts[kind] += 1
            if kind in ["potion", "atk", "def", "gold"]:
                source["hp" if kind == "potion" else kind] += item["amount"]
            elif kind == "key":
                source["keys"][item["type"]] += item["amount"]
            elif kind == "enemy":
                source["gold"] += data["enemies"][item["type"]]["gold"]
            elif kind == "shop":
                for offer in data["shops"][item["type"]]["offers"]:
                    source["hp" if offer["kind"] == "potion" else offer["kind"]] += offer["amount"] * offer["limit"]
    upper = {k: data["initial_player"][k] + source[k] for k in ["hp", "atk", "def", "gold"]}
    upper["keys"] = deepcopy(source["keys"])
    return {"meaning": "loose componentwise bounds, ignoring costs and mutually exclusive yellow doors; not a jointly reachable maximum",
            "finite_sources": source, "state_component_upper_bounds": upper, "object_kind_counts": dict(sorted(counts.items())),
            "infinite_farming": False, "shop_restock": False}


def build() -> dict:
    catalog, enemies = graph_catalog(), {}
    floors = [make_floor(n, deepcopy(catalog[tuple(selection[:2])][selection[2]]), enemies)
              for n, selection in enumerate(CURATION, 1)]
    floors[0]["safe_start_candidates"] = [[2, 10], [3, 10], [2, 11], [3, 11]]
    data = {
        "schema_version": 1, "content_id": CONTENT_ID, "title": "阶塔 · 星冠21层", "title_note": "临时名，可改名。独立战役，保留原三层切片。",
        "build_recipe": BUILD_VERSION, "rules_assumptions": ["hero-first deterministic combat", "finite pickup and shop stock", "no walking damage", "no runtime random placement"],
        "initial_player": {"hp": 260, "atk": 24, "def": 8, "gold": 0, "keys": {"yellow": 0, "blue": 0}},
        "variant_spawn_candidates": deepcopy(floors[0]["safe_start_candidates"]),
        "enemies": enemies, "shops": {**{f"forge{g}": make_shop(g) for g in range(1, 7)}, "supply7": make_shop(7, True)},
        "floors": floors,
        "provenance": {"layout_and_balance": "Original project-authored fixed room trees, positions and integer stat curves; no legacy Mota level copied.",
                       "generator_license": "Repository license applies; standard-library Python only.",
                       "software_downloaded_or_installed_by_builder": False},
    }
    data["validated_routes"] = [calculate_budget(data, name, route_events(data, name)) for name in POLICIES]
    data["witness_routes"] = [{k: deepcopy(route[k]) for k in ["name", "policy", "events", "final"]} for route in data["validated_routes"]]
    data["resource_bounds"] = resource_bounds(data)
    validate(data)
    data["canonical_payload_sha256"] = hashlib.sha256(json_bytes({k: v for k, v in data.items() if k not in ["canonical_payload_sha256", "validated_routes", "witness_routes", "validation_summary"]})).hexdigest()
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "levels21.json")
    parser.add_argument("--check", action="store_true", help="compare generated bytes with the existing output; do not write")
    args = parser.parse_args()
    data = build()
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.check:
        assert args.out.read_bytes() == payload, "canonical output differs from the fixed build recipe"
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(payload)
    print(json.dumps({"path": str(args.out), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                      "validation": data["validation_summary"],
                      "route_finals": [{"name": r["name"], "events": len(r["events"]), **r["final"]} for r in data["validated_routes"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
