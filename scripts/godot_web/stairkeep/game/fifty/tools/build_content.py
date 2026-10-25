"""Build original fixed floors 1-10; never generate runtime enemy placement.

SPDX-License-Identifier: MIT
The small planning replay below calculates authored budgets only. It is not a
game combat authority. Godot BaseRules must independently replay every witness.
No Godot process, download, package installation or external asset is invoked.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, deque
from pathlib import Path

from layout_catalogue import resolve_layout, validate_catalogue


ROOT = Path(__file__).resolve().parents[1]
CONTENT_ID = "stairkeep-fifty-slice/v1"
TITLES = [
    "归潮门厅", "绳桥库", "回声索室", "双庭水闸", "盐封档案",
    "绕潮盘道", "守灯人廊", "三径蓄池", "四翼校准室", "无火信台",
]
THEMES = [
    "湿石与测绘铜线", "旧绳、钟架与铁梯", "两股回声绕过断墙", "两庭残水与平行闸桥",
    "盐白封蜡与蓝色档案匣", "绕柱潮线与返程短廊", "低垂的灯与同伴的布结",
    "三道干渠汇向蓄池", "四翼刻度与封存石像", "无焰信台与朝外的铜镜",
]
# Original per-floor alternatives: atk / branch gold / def / branch health.
# A single yellow key chooses an immediate branch; later keys may fund revisits.
BRANCHES = [
    (3, 12, 2, 35), (2, 20, 3, 20), (4, 6, 1, 60), (2, 14, 3, 20), (3, 8, 2, 35),
    (4, 6, 1, 50), (2, 18, 3, 20), (3, 14, 2, 35), (5, 5, 1, 50), (2, 18, 3, 20),
]
MANIFEST = {
    "schema_version": 1,
    "content_id": CONTENT_ID,
    "target_floors": 50,
    "authored_floors": list(range(1, 11)),
    "not_authored_floors": list(range(11, 51)),
    "scope": "Original authored floors 1-10 only. Floors 11-50 are not made.",
    "completion_kind": "slice_complete_not_campaign_victory",
    "default_mode": None,
    "modes": {
        "classic": "Explicit choice: new runSeed and complete state reset on a new run.",
        "practice": "Explicit choice: restore a complete captured checkpoint, no retained future gains.",
    },
    "legacy_save_migration": False,
}


def packed(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def cells(grid):
    return {(x, y) for y, row in enumerate(grid) for x, char in enumerate(row) if char != "#"}


def adjacent(p):
    x, y = p
    return [(x, y - 1), (x - 1, y), (x + 1, y), (x, y + 1)]


def reachable(grid, start, blocked=()):
    allowed = cells(grid) - set(blocked)
    if tuple(start) not in allowed:
        return set()
    seen = {tuple(start)}
    queue = deque(seen)
    while queue:
        for nxt in adjacent(queue.popleft()):
            if nxt in allowed and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def extra_position(layout, excluded, preserve, sealed=False):
    """Build-time fixed placement; canonical JSON retains the explicit result."""
    markers, grid = layout["markers"], layout["grid"]
    start = markers["S"]
    gates = {tuple(markers[k]) for k in "GADB" if k in markers}
    allowed = reachable(grid, start, gates)
    required = {tuple(markers[k]) for k in preserve if k in markers}
    occupied = {tuple(v) for v in markers.values()} | set(excluded)
    options = []
    for point in sorted(allowed - occupied, key=lambda p: (p[1], p[0])):
        # A sealed optional sentinel may never cut off a named interaction.
        blocked = {point} if sealed else gates | {point}
        test_required = {tuple(v) for v in markers.values()} - {point} if sealed else required
        if test_required <= reachable(grid, start, blocked):
            options.append(point)
    if not options:
        raise ValueError(f"No non-destructive fixed encounter cell on floor {layout['id']}")
    # Select one fixed cell far enough from spawn to allow reading the first UI.
    return list(max(options, key=lambda p: (abs(p[0] - start[0]) + abs(p[1] - start[1]), -p[1], -p[0])))


def make_content():
    topology = validate_catalogue()
    data = {
        "schema_version": 1,
        "content_id": CONTENT_ID,
        "title": "阶塔 · 潮痕信塔",
        "title_note": "临时名，可改。目标50层；现仅原创制作1–10层，11–50层未制作。",
        "manifest": copy.deepcopy(MANIFEST),
        "build_recipe": "fifty-original-fixed-layouts/v1",
        "initial_player": {"hp": 180, "atk": 14, "def": 5, "gold": 0, "keys": {"yellow": 0, "blue": 0}},
        "flags": {key: False for key in ["met_mapper", "copper_found", "copper_redeemed", "archive_read", "met_keeper", "keeper_supplied", "relay_lit"]},
        "events": {}, "enemies": {}, "shops": {}, "floors": [],
        "completion": {"slice_goal_object_id": "f10_signal", "campaign_victory_authored": False},
        "rules_assumptions": ["hero-first ordinary deterministic combat", "finite fixed resources and shop stock", "no walking damage", "all geometry and encounters fixed at build time", "NPC and event rewards once only", "floor 10 is a slice milestone, not 50-floor victory"],
        "provenance": {"layout": "new original fixed ASCII geometry", "story_and_dialogue": "new original Chinese writing", "numeric_design": "new original finite-budget design", "license": "MIT, repository LICENSE", "external_maps_copied": False, "external_assets_downloaded": False, "reference_version_rules_claimed": False},
    }
    for number in range(1, 11):
        layout = resolve_layout(number)
        marks = layout["markers"]
        prefix = f"f{number:02d}_"
        floor = {
            "id": number, "name": TITLES[number - 1], "visual_theme": THEMES[number - 1],
            "topology": layout["topology"], "width": len(layout["grid"][0]), "height": len(layout["grid"]),
            "spawn": marks["S"], "grid": ["".join("#" if c == "#" else "." for c in row) for row in layout["grid"]],
            "objects": [], "authored": True,
        }
        if number == 1:
            floor["safe_start_candidates"] = [[7, 12], [6, 13], [7, 13], [8, 13]]
        def add(marker, suffix, kind, **fields):
            item = {"id": prefix + suffix, "kind": kind, "pos": list(marks[marker]), **fields}
            floor["objects"].append(item)
            return item
        add("i", "core_atk", "atk", amount=1, name="整修刃片")
        add("h", "core_potion", "potion", amount=24, name="清水包")
        add("K", "choice_key", "key", type="yellow", amount=1, name="黄铜钥匙")
        add("A", "attack_door", "door", type="yellow", name="刃路门")
        attack_amount, branch_gold, defense_amount, branch_health = BRANCHES[number - 1]
        add("a", "attack_gem", "atk", amount=attack_amount, name="磨刃石")
        add("$", "attack_gold", "gold", amount=branch_gold, name="工具匣余钱")
        add("D", "defense_door", "door", type="yellow", name="护路门")
        add("d", "defense_gem", "def", amount=defense_amount, name="叠甲片")
        add("p", "defense_potion", "potion", amount=branch_health, name="备用清水包")
        guard_type = prefix + "gatekeeper"
        scout_type = prefix + "watcher"
        data["enemies"][guard_type] = {"name": ["积潮门卫", "绳库重卫", "索室守卫", "闸桥看守", "封蜡卫", "盘道重卫", "暗灯门卫", "渠口重卫", "刻度守卫", "信台守卫"][number - 1], "hp": 32 + 11 * number, "atk": 12 + 3 * number, "def": 5 + 2 * number, "gold": 12 + 3 * number}
        data["enemies"][scout_type] = {"name": ["苔面巡者", "挂绳巡者", "回声巡者", "湿闸巡者", "盐尘巡者", "绕柱巡者", "残灯巡者", "干渠巡者", "校准巡者", "铜镜巡者"][number - 1], "hp": 22 + 5 * number, "atk": 10 + 2 * number, "def": 2 + number, "gold": 18}
        add("G", "guard", "enemy", type=guard_type)
        excluded = {tuple(v) for v in floor.get("safe_start_candidates", [])}
        scout_pos = extra_position(layout, excluded, "SihK")
        floor["objects"].append({"id": prefix + "scout", "kind": "enemy", "type": scout_type, "pos": scout_pos})
        if number > 1:
            add("V", "down", "stairs", direction="down", target={"floor": number - 1, "pos": resolve_layout(number - 1)["markers"]["U"], "object_id": f"f{number-1:02d}_up"})
        if number < 10:
            add("U", "up", "stairs", direction="up", target={"floor": number + 1, "pos": resolve_layout(number + 1)["markers"]["V"], "object_id": f"f{number+1:02d}_down"})
        else:
            add("U", "signal", "event", event_ids=["ev_signal"], slice_goal=True, name="无火信台")
        if number in [2, 5, 8]:
            shop_type = prefix + "supplies"
            add("M", "shop", "shop", type=shop_type, name="修补摊")
            data["shops"][shop_type] = {"name": "有限修补摊", "offers": [
                {"id": "edge", "label": "整修刀刃", "kind": "atk", "amount": 6, "cost": 48, "limit": 1},
                {"id": "ward", "label": "加固护具", "kind": "def", "amount": 4, "cost": 36, "limit": 1},
                {"id": "flask", "label": "封存清水", "kind": "potion", "amount": 90, "cost": 24, "limit": 1},
            ]}
        if number == 1:
            add("N", "mapper", "npc", name="测绘员岚绘", facing="west", event_ids=["ev_mapper_exchange", "ev_mapper_intro"])
        if number == 3:
            add("q", "copper", "event", name="缺角铜签", event_ids=["ev_copper"])
        if number == 5:
            add("B", "archive_door", "door", name="盐封档案门", type="blue")
            add("z", "archive", "event", name="回潮档案匣", event_ids=["ev_archive"])
        if number == 7:
            add("N", "keeper", "npc", name="守灯人弥安", facing="north", event_ids=["ev_keeper_supply", "ev_keeper_intro"])
        if number == 9:
            sentinel_pos = extra_position(layout, {tuple(scout_pos)}, "", sealed=True)
            data["enemies"]["sealed_sentinel"] = {"name": "封存校准像", "hp": 999, "atk": 99, "def": 999, "gold": 0}
            floor["objects"].append({"id": "f09_sealed_sentinel", "kind": "enemy", "type": "sealed_sentinel", "pos": sentinel_pos, "bestiary_note": "不能穿透。旁路始终开放；不必挑战。"})
        floor["objects"].sort(key=lambda o: (o["pos"][1], o["pos"][0], o["id"]))
        data["floors"].append(floor)
    def event(key, number, object_id, conditions, effects, text):
        data["events"][key] = {"floor": number, "trigger": {"kind": "interact", "object_id": object_id}, "conditions": conditions, "effects": effects, "once": True, "text": text}
    def flag(key, value):
        return {"kind": "flag", "flag": key, "value": value}
    def set_flag(key):
        return {"kind": "set_flag", "flag": key, "value": True}
    event("ev_mapper_exchange", 1, "f01_mapper", [flag("copper_found", True), flag("copper_redeemed", False)], [{"kind": "grant_key", "color": "blue", "amount": 1}, set_flag("copper_redeemed")], "这枚缺角正好接上我的旧图。蓝钥匙归你：第五层的盐封档案门后，留着入塔队的行程。铜签我收好了，这次交换只有一把钥匙。")
    event("ev_mapper_intro", 1, "f01_mapper", [flag("met_mapper", False), flag("copper_redeemed", False)], [set_flag("met_mapper")], "我是岚绘。第三层索室有一枚缺角铜签；带回来，我用档案门的蓝钥匙换它。黄钥匙每层只够先开一条支路：刃路给攻击和余钱，护路给防御和清水。门不会自己关回去。")
    event("ev_copper", 3, "f03_copper", [flag("copper_found", False)], [set_flag("copper_found")], "铜签背面刻着半道潮线，和岚绘旧图上的缺口相合。带回第一层，或先继续探索；它不会自动变成钥匙。")
    event("ev_archive", 5, "f05_archive", [flag("archive_read", False)], [set_flag("archive_read"), {"kind": "grant", "stat": "atk", "amount": 3}, {"kind": "grant", "stat": "def", "amount": 2}, {"kind": "grant", "stat": "hp", "amount": 45}], "档案没有写下失踪者的结局，只留了一句：‘灯未熄，去第七层问守灯人。’匣中工具与水仍可用。你记下路线，取走这份一次性补给。")
    event("ev_keeper_supply", 7, "f07_keeper", [flag("archive_read", True), flag("keeper_supplied", False)], [set_flag("keeper_supplied"), {"kind": "grant", "stat": "hp", "amount": 60}, {"kind": "grant", "stat": "gold", "amount": 12}], "你看过那份档案了。留下布结的人还在往上走；这袋水和修补钱原本为他留着，现在交给你。第十层信台能向塔外报平安，这不是整座塔的终点。")
    event("ev_keeper_intro", 7, "f07_keeper", [flag("met_keeper", False), flag("keeper_supplied", False)], [set_flag("met_keeper")], "我叫弥安。第五层的档案匣能说明那枚布结；若你还没看过，回去找找。我的补给只会交付一次。")
    event("ev_signal", 10, "f10_signal", [{"kind": "cleared", "object_id": "f10_guard", "value": True}], [set_flag("relay_lit")], "你把铜镜转向塔外，潮痕组成第一道清楚的信号。首十层的道路已经接通。更高的四十层尚未制作；当前切片完成，你仍可回访、查看预算或保存这局。")
    return data, topology


class PlanningReplay:
    """Finite authored-budget arithmetic/BFS; never loaded by the runtime."""
    def __init__(self, data):
        self.data = data
        self.state = copy.deepcopy(data["initial_player"])
        self.state.update({"won": False, "floor": 0, "pos": data["floors"][0]["spawn"].copy(), "cleared": [], "purchases": {}})
        self.flags = copy.deepcopy(data["flags"])
        self.completed = []
        self.slice_complete = False
        self.locations = {o["id"]: (index, o) for index, f in enumerate(data["floors"]) for o in f["objects"]}
        self.paths = 0
        self.combats = 0
        self.minimum_hp = self.state["hp"]

    def _live(self, obj):
        if obj["id"] in self.state["cleared"]:
            return False
        return not (obj["kind"] == "event" and all(e in self.completed for e in obj["event_ids"]))

    def _path(self, obj, adjacent_only=False):
        floor = self.data["floors"][self.state["floor"]]
        occupied = {tuple(o["pos"]): o for o in floor["objects"] if self._live(o)}
        target = tuple(obj["pos"])
        goals = set(adjacent(target)) if adjacent_only else {target}
        allowed = cells(floor["grid"])
        start = tuple(self.state["pos"])
        queue = deque([start]); parents = {start: None}; end = None
        while queue:
            point = queue.popleft()
            if point in goals:
                end = point; break
            for nxt in adjacent(point):
                if nxt not in allowed or nxt in parents:
                    continue
                obstacle = occupied.get(nxt)
                if obstacle and nxt != target and obstacle["kind"] != "shop":
                    continue
                if nxt == target and adjacent_only:
                    continue
                parents[nxt] = point; queue.append(nxt)
        if end is None:
            raise ValueError(f"No legal authored path to {obj['id']} from floor {self.state['floor']+1} {start}")
        path = []
        while end != start:
            path.append(list(end)); end = parents[end]
        path.reverse()
        if path:
            self.state["pos"] = path[-1]
        self.paths += len(path)
        return path

    def _conditions(self, event):
        for condition in event["conditions"]:
            actual = self.flags[condition["flag"]] if condition["kind"] == "flag" else condition["object_id"] in self.state["cleared"]
            if actual != condition["value"]:
                return False
        return True

    def apply(self, identifier):
        before = self.resources()
        damage = None; selected = None
        if identifier.startswith("buy:"):
            shop_id, offer_id = identifier[4:].split("/")
            index, obj = self.locations[shop_id]
            if index != self.state["floor"]:
                raise ValueError("Shop is on another floor")
            path = self._path(obj, adjacent_only=True)
            offer = next(o for o in self.data["shops"][obj["type"]]["offers"] if o["id"] == offer_id)
            stock_key = shop_id + "/" + offer_id
            if self.state["purchases"].get(stock_key, 0) >= offer["limit"] or self.state["gold"] < offer["cost"]:
                raise ValueError(f"Unaffordable or sold out {identifier}: {self.state['gold']}")
            self.state["gold"] -= offer["cost"]
            stat = "hp" if offer["kind"] == "potion" else offer["kind"]
            self.state[stat] += offer["amount"]
            self.state["purchases"][stock_key] = self.state["purchases"].get(stock_key, 0) + 1
        else:
            index, obj = self.locations[identifier]
            if index != self.state["floor"]:
                raise ValueError(f"Event {identifier} is on another floor")
            kind = obj["kind"]
            path = self._path(obj, adjacent_only=kind in ["npc", "event"])
            if kind == "stairs":
                self.state["floor"] = obj["target"]["floor"] - 1
                self.state["pos"] = obj["target"]["pos"].copy()
            elif kind in ["npc", "event"]:
                candidates = [e for e in obj["event_ids"] if e not in self.completed and self._conditions(self.data["events"][e])]
                if not candidates:
                    raise ValueError(f"No eligible NPC/event branch at {identifier}")
                selected = candidates[0]
                for effect in self.data["events"][selected]["effects"]:
                    if effect["kind"] == "set_flag":
                        self.flags[effect["flag"]] = effect["value"]
                    elif effect["kind"] == "grant":
                        self.state[effect["stat"]] += effect["amount"]
                    elif effect["kind"] == "grant_key":
                        color = effect["color"]
                        self.state["keys"][color] += effect["amount"]
                    else:
                        raise ValueError("Unsupported planning event effect")
                self.completed.append(selected)
                if kind == "event":
                    self.state["pos"] = obj["pos"].copy()
                if obj.get("slice_goal", False):
                    self.slice_complete = True
            else:
                if not self._live(obj):
                    raise ValueError(f"Witness repeats a cleared object {identifier}")
                if kind == "enemy":
                    enemy = self.data["enemies"][obj["type"]]
                    hit = self.state["atk"] - enemy["def"]
                    if hit <= 0:
                        raise ValueError(f"Attack cannot penetrate {identifier}")
                    rounds = (enemy["hp"] + hit - 1) // hit
                    damage = (rounds - 1) * max(0, enemy["atk"] - self.state["def"])
                    if self.state["hp"] <= damage:
                        raise ValueError(f"Lethal authored budget {identifier}: {self.state['hp']} <= {damage}")
                    self.state["hp"] -= damage
                    self.state["gold"] += enemy["gold"]
                    self.combats += 1
                elif kind == "door":
                    if self.state["keys"][obj["type"]] < 1:
                        raise ValueError(f"Missing key for {identifier}")
                    self.state["keys"][obj["type"]] -= 1
                elif kind == "key":
                    self.state["keys"][obj["type"]] += obj["amount"]
                else:
                    self.state["hp" if kind == "potion" else kind] += obj["amount"]
                self.state["cleared"].append(identifier)
        self.minimum_hp = min(self.minimum_hp, self.state["hp"])
        row = {"event": identifier, "before": before, "state": self.resources(), "floor": self.state["floor"] + 1, "pos": self.state["pos"].copy(), "flags": copy.deepcopy(self.flags), "completed_events": self.completed.copy(), "slice_complete": self.slice_complete, "purchases": copy.deepcopy(self.state["purchases"]), "cleared_count": len(self.state["cleared"]), "planned_walk_steps": len(path)}
        if damage is not None:
            row["damage"] = damage
        if selected is not None:
            row["selected_event_id"] = selected
        return row

    def resources(self):
        return {k: copy.deepcopy(self.state[k]) for k in ["hp", "atk", "def", "gold", "keys"]}


def route_events(style):
    result = []
    for n in range(1, 11):
        p = f"f{n:02d}_"
        result += [p + "core_potion", p + "core_atk", p + "choice_key", p + "scout"]
        if n == 1:
            result.append("f01_mapper")
        if style == "blade":
            result += [p + "attack_door", p + "attack_gold", p + "attack_gem"]
        else:
            result += [p + "defense_door", p + "defense_gem", p + "defense_potion"]
        if n in [2, 5, 8]:
            if style == "blade":
                result += ["buy:" + p + "shop/ward", "buy:" + p + "shop/flask"]
            else:
                result += ["buy:" + p + "shop/edge"]
        if n == 3:
            result.append("f03_copper")
        if n == 5:
            result += ["f05_archive_door", "f05_archive"]
        if n == 7:
            result.append("f07_keeper")
        result.append(p + "guard")
        if n == 3:
            result += ["f03_down", "f02_down", "f01_mapper", "f01_up", "f02_up"]
        result.append(p + ("up" if n < 10 else "signal"))
    return result


def add_witnesses(data):
    routes = []
    for name, policy in [("blade", "每层刃路，三店护具与清水；早取攻击换较少回击，额外金币用于有限治疗。"), ("bulwark", "每层护路，三店整修刀刃；用钥匙换防御和药水，把金币留给突破攻击门槛。")]:
        replay = PlanningReplay(data)
        events = route_events("blade" if name == "blade" else "bulwark")
        ledger = [replay.apply(event) for event in events]
        if not replay.slice_complete or replay.state["won"]:
            raise ValueError("Witness must finish the authored slice without campaign victory")
        final = replay.resources() | {"won": False}
        routes.append({"name": name, "policy": policy, "events": events, "ledger": ledger, "final": final, "slice_complete": True, "final_flags": copy.deepcopy(replay.flags), "completed_events": replay.completed.copy(), "final_purchases": copy.deepcopy(replay.state["purchases"]), "final_cleared": sorted(replay.state["cleared"]), "design_calculation": {"scope": "Non-authoritative Python build-time resource/path planning. Actual Godot witness replay still required.", "engine_tested": False, "ordinary_combats": replay.combats, "planned_walk_steps": replay.paths, "minimum_hp": replay.minimum_hp}})
    data["validated_routes"] = routes


def static_checks(data):
    ids = {}; counts = Counter(); all_grants = Counter()
    for floor in data["floors"]:
        points = set()
        for obj in floor["objects"]:
            assert obj["id"] not in ids and tuple(obj["pos"]) not in points
            assert tuple(obj["pos"]) in cells(floor["grid"])
            ids[obj["id"]] = (floor["id"], obj); points.add(tuple(obj["pos"])); counts[obj["kind"]] += 1
            assert not obj.get("victory", False)
            if obj["kind"] in ["atk", "def", "potion", "gold", "key"]:
                all_grants[("key:" + obj["type"]) if obj["kind"] == "key" else ("hp" if obj["kind"] == "potion" else obj["kind"])] += obj["amount"]
            if obj["kind"] == "enemy":
                all_grants["gold"] += data["enemies"][obj["type"]]["gold"]
    for floor in data["floors"]:
        for obj in floor["objects"]:
            if obj["kind"] == "stairs":
                target_floor, other = ids[obj["target"]["object_id"]]
                assert target_floor == obj["target"]["floor"] and other["pos"] == obj["target"]["pos"]
                assert other["target"]["object_id"] == obj["id"] and other["target"]["floor"] == floor["id"] and other["target"]["pos"] == obj["pos"]
    for key, event in data["events"].items():
        assert event["once"] is True and event["trigger"]["kind"] == "interact"
        floor_id, obj = ids[event["trigger"]["object_id"]]
        assert floor_id == event["floor"] and key in obj["event_ids"]
        for effect in event["effects"]:
            if effect["kind"] == "grant": all_grants[effect["stat"]] += effect["amount"]
            if effect["kind"] == "grant_key": all_grants["key:" + effect["color"]] += effect["amount"]
    for shop in data["shops"].values():
        for offer in shop["offers"]:
            assert offer["limit"] == 1 and offer["cost"] > 0
            all_grants["hp" if offer["kind"] == "potion" else offer["kind"]] += offer["amount"] * offer["limit"]
    for key, val in data["initial_player"].items():
        if isinstance(val, int): all_grants[key] += val
    return {"scope": "Lightweight build-time static checks and planning only; no engine run.", "authored_floor_count": 10, "target_floor_count": 50, "not_authored_floor_count": 40, "unique_object_count": len(ids), "object_counts": dict(sorted(counts.items())), "loose_resource_upper_envelope": dict(sorted(all_grants.items())), "upper_envelope_note": "Conservative independent maxima, not a jointly attainable character: 10 yellow keys cannot open all 20 yellow branch doors; shop affordability and stock still apply.", "all_stairs_bidirectional": True, "campaign_victory_present": False, "witnesses": [{"name": r["name"], "events": len(r["events"]), "final": r["final"], "minimum_hp": r["design_calculation"]["minimum_hp"], "ordinary_combats": r["design_calculation"]["ordinary_combats"], "planned_walk_steps": r["design_calculation"]["planned_walk_steps"], "engine_tested": False} for r in data["validated_routes"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="rebuild in memory and compare existing bytes; do not write")
    args = parser.parse_args()
    data, topology = make_content()
    add_witnesses(data)
    report = static_checks(data)
    report["topology_checks"] = topology
    payloads = {"manifest.json": packed(MANIFEST), "content.json": packed(data), "design-budget.json": packed(report)}
    if args.check:
        for name, raw in payloads.items():
            if not (ROOT / "data" / name).exists() or (ROOT / "data" / name).read_bytes() != raw:
                raise SystemExit(f"Reproducibility mismatch: {name}")
    else:
        (ROOT / "data").mkdir(parents=True, exist_ok=True)
        for name, raw in payloads.items():
            (ROOT / "data" / name).write_bytes(raw)
    print(json.dumps({"build_check": "passed", "engine_tested": False, "outputs": {name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in payloads.items()}, "witnesses": report["witnesses"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
