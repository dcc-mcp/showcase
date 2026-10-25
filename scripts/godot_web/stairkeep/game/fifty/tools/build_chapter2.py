"""Build NEW original chapter 2 plus a deep copy of frozen authored floors 1-10.

SPDX-License-Identifier: MIT
Only six chapter2 deliverables are owned by this build. No runtime, old content,
old builder, evidence, slot or archive is changed. PlanningReplay is reused as a
non-authoritative design calculator; actual Godot API replay belongs to root.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, deque
from pathlib import Path

from build_content import PlanningReplay, adjacent, cells, packed
from chapter2_catalogue import resolve_layout, validate_catalogue


ROOT = Path(__file__).resolve().parents[1]
OLD_SHA = "3703b2cbc43d2297d42d335ad85ebac3f464d9f6c68d536d75a990e9bdd75fd5"
CONTENT_ID = "stairkeep-fifty-chapter2/v1"
NAMES = [
    ("断泉转轮", "Dry Spring Wheel"), ("潮尺关庭", "Tide Gauge Court"),
    ("墨印回湾", "Ink Seal Reach"), ("双封档库", "Double-Sealed Archive"),
    ("孤钥闸心", "Lone-Key Sluice"), ("折光缆台", "Refraction Cable Deck"),
    ("悬桥回声", "Echo Causeway"), ("双潮印室", "Twin-Tide Seal Room"),
    ("侧风水栈", "Crosswind Water Depot"), ("回港镜台", "Return Beacon Mirror"),
]
MANIFEST = {
    "schema_version": 1, "content_id": CONTENT_ID, "target_floors": 50,
    "authored_floors": list(range(1, 21)), "not_authored_floors": list(range(21, 51)),
    "checkpoint_floors": [1, 5, 11, 15], "default_mode": None,
    "scope": "Original fixed authored floors 1-20, not a completed fifty-floor game.",
    "completion_kind": "slice_complete_not_campaign_victory",
    "modes": {"classic": "Explicit new-seed complete restart.", "practice": "Explicit restoration of a complete captured checkpoint."},
    "legacy_save_migration": False,
}


def make_content():
    source = ROOT / "data/content.json"
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != OLD_SHA:
        raise ValueError("Frozen chapter-1 source bytes changed; refuse to silently rebuild against another fixture")
    old = json.loads(raw)
    data = copy.deepcopy(old)
    data.update({"content_id": CONTENT_ID, "title": "阶塔 · 潮痕信塔 · 回港章", "title_en": "Stairkeep: Tide-Mark Signal — Return Chapter", "title_note": "临时名可改。原创制作1–20层；21–50层未制作。", "manifest": copy.deepcopy(MANIFEST), "build_recipe": "chapter2-fixed-original/v1", "completion": {"slice_goal_object_id": "f20_signal", "campaign_victory_authored": False}})
    data.pop("validated_routes", None)
    data["rules_assumptions"] = [a for a in old["rules_assumptions"] if not a.startswith("floor 10 is a slice milestone")]
    data["rules_assumptions"] += ["floor 10 is a chapter milestone; floor 20 is the authored slice milestone; neither is fifty-floor campaign victory", "one logical four-neighbor layer per floor; no stacked height physics"]
    data["provenance"] = {"layout": "Floors 1-9 copied unchanged from the frozen original slice; floor 10 has only the necessary bridge/milestone adaptation; floors 11-20 newly authored.", "chapter1_source_sha256": OLD_SHA, "story_and_dialogue": "New original chapter-2 Chinese and English writing, no copied commercial dialogue", "numeric_design": "New finite key/resource design", "license": "MIT, repository LICENSE", "external_maps_copied": False, "external_assets_downloaded": False, "reference_version_rules_claimed": False}
    # The original file is untouched. A one-cell bridge is necessary because the
    # old signal sat in a one-cell dead end. All other old encounters stay fixed.
    floor10 = data["floors"][9]
    row = list(floor10["grid"][1]); assert row[8] == "#"; row[8] = "."; floor10["grid"][1] = "".join(row)
    signal = next(o for o in floor10["objects"] if o["id"] == "f10_signal")
    signal.pop("slice_goal", None)
    floor10["objects"].append({"id": "f10_up", "kind": "stairs", "name": "回港章桥梯", "name_en": "Stair to the Return Chapter", "direction": "up", "pos": [8, 1], "target": {"floor": 11, "pos": resolve_layout(11)["markers"]["V"], "object_id": "f11_down"}})
    data["events"]["ev_signal"]["text"] = "第一道信号已经照向塔外。现在可沿桥梯继续探索第11–20层；第21–50层尚未制作。此处只是首章里程碑。"
    data["events"]["ev_signal"]["text_en"] = "The first signal reaches the outside. The bridge now continues through authored floors 11-20; floors 21-50 are not made. This is the first-chapter milestone, not the tower's end."
    new_flags = ["c2_met_surveyor", "c2_scale_read", "c2_ink_found", "c2_first_blue_claimed", "c2_register_read", "c2_f11_cache_taken", "c2_f15_cache_taken", "c2_met_rigger", "c2_rigger_supplied", "c2_sigil_found", "c2_second_blue_claimed", "c2_mirror_plan_read", "c2_edge_cache_taken", "c2_reserve_cache_taken", "c2_mirror_aligned", "c2_beacon_lit"]
    for flag in new_flags: data["flags"][flag] = False
    topology = validate_catalogue()
    for number in range(11, 21):
        layout = resolve_layout(number); markers = layout["markers"]; p = f"f{number:02d}_"; j = number - 10
        floor = {"id": number, "name": NAMES[j - 1][0], "name_en": NAMES[j - 1][1], "topology": layout["topology"], "width": len(layout["grid"][0]), "height": len(layout["grid"]), "spawn": markers["S"], "grid": ["".join("#" if c == "#" else "." for c in row) for row in layout["grid"]], "authored": True, "objects": []}
        def add(marker, suffix, kind, name, name_en, **fields):
            item = {"id": p + suffix, "kind": kind, "pos": markers[marker].copy(), "name": name, "name_en": name_en, **fields}
            floor["objects"].append(item); return item
        add("h", "water", "potion", "回港清水", "Return-Route Water", amount=80 if number == 11 else 100)
        add("i", "blade", "atk", "校准刃片", "Calibrated Edge", amount=3)
        add("g", "coins", "gold", "路修工钱", "Maintenance Pay", amount=12)
        if "K" in markers: add("K", "yellow_key", "key", "关庭黄钥匙", "Forward-Gate Yellow Key", type="yellow", amount=1)
        scout_type, guard_type = p + "watcher", p + "warden"
        data["enemies"][scout_type] = {"name": "回港巡者", "name_en": "Return-Route Watcher", "hp": 65 + 6 * j, "atk": 34 + 2 * j, "def": 24 + j, "gold": 22 + 2 * j}
        guard_hp = {18: 180, 19: 200, 20: 213}.get(number, 95 + 9 * j)
        data["enemies"][guard_type] = {"name": "关庭守卫", "name_en": "Court Warden", "hp": guard_hp, "atk": 38 + 2 * j, "def": 28 + j, "gold": 30 + 3 * j}
        add("e", "scout", "enemy", "巡者", "Watcher", type=scout_type)
        add("G", "guard", "enemy", "前行守卫", "Forward Warden", type=guard_type)
        add("V", "down", "stairs", "下行梯", "Stair Down", direction="down", target={"floor": number - 1, "pos": [8, 1] if number == 11 else resolve_layout(number - 1)["markers"]["U"], "object_id": f"f{number-1:02d}_up"})
        if number < 20:
            add("U", "up", "stairs", "上行梯", "Stair Up", direction="up", target={"floor": number + 1, "pos": resolve_layout(number + 1)["markers"]["V"], "object_id": f"f{number+1:02d}_down"})
        else:
            add("U", "signal", "event", "回港镜台", "Return Beacon", event_ids=["ev_c2_signal"], slice_goal=True)
        if "H" in markers:
            add("H", "main_gate", "door", "前行黄闸", "Forward Yellow Sluice", type="yellow", description="前行需要一把黄钥匙。支匣消耗同一种钥匙，并不返还钥匙。")
        if "B" in markers:
            add("B", "blue_gate", "door", "回访蓝闸", "Return-Visit Blue Sluice", type="blue")
        if "A" in markers:
            add("A", "side_gate", "door", "补给支闸" if number in [11, 15] else "选取支闸", "Supply Side Gate" if number in [11, 15] else "Choice Side Gate", type="yellow")
            reward_id = {11: "ev_c2_f11_cache", 15: "ev_c2_f15_cache", 17: "ev_c2_edge_cache", 19: "ev_c2_reserve_cache"}[number]
            add("a", "side_cache", "event", "有限补给匣", "Finite Supply Cache", event_ids=[reward_id])
        if number == 11: add("N", "surveyor", "npc", "测量员砾舟", "Surveyor Lizhou", facing="south", event_ids=["ev_c2_first_blue", "ev_c2_surveyor_intro"])
        if number == 16: add("N", "rigger", "npc", "缆师绮线", "Rigger Qixian", facing="east", event_ids=["ev_c2_second_blue", "ev_c2_rigger_supply", "ev_c2_rigger_intro"])
        if "q" in markers:
            suffix, name, en, event_id = {12: ("scale", "潮尺", "Tide Gauge", "ev_c2_scale"), 13: ("ink_seal", "墨印", "Ink Seal", "ev_c2_ink"), 14: ("register", "外柜路簿", "Outer Route Register", "ev_c2_register"), 17: ("mirror_plan", "镜向图", "Mirror Plan", "ev_c2_plan"), 18: ("tide_seal", "双潮印", "Twin-Tide Seal", "ev_c2_sigil"), 20: ("alignment", "镜台校准器", "Beacon Alignment", "ev_c2_alignment")}[number]
            add("q", suffix, "event", name, en, event_ids=[event_id])
        if "M" in markers:
            shop_type = p + "workshop"
            add("M", "shop", "shop", "回港修补台", "Return-Route Workshop", type=shop_type)
            data["shops"][shop_type] = {"name": "回港修补台", "name_en": "Return-Route Workshop", "offers": [{"id": "edge", "label": "精修刀刃", "kind": "atk", "amount": 8, "cost": 160, "limit": 1}, {"id": "ward", "label": "加固关甲", "kind": "def", "amount": 5, "cost": 140, "limit": 1}, {"id": "flask", "label": "远程清水包", "kind": "potion", "amount": 120, "cost": 110, "limit": 1}]}
        floor["objects"].sort(key=lambda x: (x["pos"][1], x["pos"][0], x["id"]))
        data["floors"].append(floor)
    def cond(flag, val=True): return {"kind": "flag", "flag": flag, "value": val}
    def setflag(flag): return {"kind": "set_flag", "flag": flag, "value": True}
    def grant(stat, amount): return {"kind": "grant", "stat": stat, "amount": amount}
    def key(color): return {"kind": "grant_key", "color": color, "amount": 1}
    def event(id, floor, obj, conditions, effects, text, text_en):
        data["events"][id] = {"floor": floor, "trigger": {"kind": "interact", "object_id": obj}, "conditions": conditions, "effects": effects, "once": True, "text": text, "text_en": text_en}
    event("ev_c2_first_blue", 11, "f11_surveyor", [cond("c2_scale_read"), cond("c2_ink_found"), cond("c2_first_blue_claimed", False)], [key("blue"), setflag("c2_first_blue_claimed")], "潮尺数值与墨印合上了。给你一把蓝钥匙，开第14层回访蓝闸。这次交换只有一次；黄钥匙仍要留给前行黄闸。", "The gauge and ink seal agree. Take one blue key for the return-visit sluice on F14. This exchange happens once; keep yellow keys for the forward gates.")
    event("ev_c2_surveyor_intro", 11, "f11_surveyor", [cond("c2_met_surveyor", False), cond("c2_first_blue_claimed", False)], [setflag("c2_met_surveyor")], "我是砾舟。读第12层潮尺、取第13层墨印，再来换蓝钥匙。本层黄钥匙要开下一层的前行闸；支匣只有补给，没有替代钥匙。现在开支匣，会把前行钥匙花掉。", "I am Lizhou. Read the F12 gauge and bring the F13 ink seal back for a blue key. This floor's yellow key is needed by the forward gate on F12. The side cache contains supplies, not a replacement key; opening it now spends the key needed to continue.")
    event("ev_c2_scale", 12, "f12_scale", [cond("c2_scale_read", False)], [setflag("c2_scale_read")], "潮尺留下的刻度需要第13层墨印校验。把两条证据带回第11层砾舟处；前行黄闸仍须实付一把钥匙。", "The gauge reading needs the F13 ink seal. Bring both findings back to Lizhou on F11. The forward yellow gate still costs one real key.")
    event("ev_c2_ink", 13, "f13_ink_seal", [cond("c2_ink_found", False)], [setflag("c2_ink_found")], "你取下未褪色的墨印。它不是钥匙；第11层的测量员能用它和潮尺读数完成交换。", "You recover the unfaded ink seal. It is not a key. The surveyor on F11 can exchange the seal together with the gauge reading.")
    event("ev_c2_register", 14, "f14_register", [cond("c2_register_read", False)], [setflag("c2_register_read"), grant("atk", 3), grant("def", 3), grant("hp", 80)], "外柜路簿写着第16层绮线的补给安排。你取走登记过的工具和清水：攻击+3、防御+3、生命+80。蓝闸是上行通道，与这个外柜各自保留状态。", "The outer register records Qixian's supplies on F16. Collect the listed tools and water: +3 ATK, +3 DEF, +80 HP. The blue sluice is the way upward; it and this outer counter keep their own persistent state.")
    event("ev_c2_f11_cache", 11, "f11_side_cache", [cond("c2_f11_cache_taken", False)], [setflag("c2_f11_cache_taken"), grant("hp", 90), grant("gold", 30)], "补给匣交付生命+90、金币+30。匣里没有黄钥匙；第12层前行闸仍需一把黄钥匙。", "The cache grants +90 HP and +30 gold. It contains no yellow key; the forward gate on F12 still needs one.")
    event("ev_c2_f15_cache", 15, "f15_side_cache", [cond("c2_f15_cache_taken", False)], [setflag("c2_f15_cache_taken"), grant("hp", 110), grant("gold", 40)], "应急匣交付生命+110、金币+40，没有返还钥匙。本层黄钥匙与前行闸共用；后面的钥匙源位于闸后。", "The emergency cache grants +110 HP and +40 gold, without returning the key. It shares this floor's key with the forward gate. Later key sources are beyond that gate.")
    event("ev_c2_second_blue", 16, "f16_rigger", [cond("c2_sigil_found"), cond("c2_rigger_supplied"), cond("c2_second_blue_claimed", False)], [key("blue"), setflag("c2_second_blue_claimed")], "双潮印对应的是第19层蓝闸。给你一把蓝钥匙，无法重复领取；第20层前行黄闸仍需要另外保留的黄钥匙。", "The twin-tide seal matches the blue sluice on F19. Take one blue key, once only. The forward yellow gate on F20 still needs a separately reserved yellow key.")
    event("ev_c2_rigger_supply", 16, "f16_rigger", [cond("c2_register_read"), cond("c2_rigger_supplied", False)], [key("yellow"), grant("hp", 40), setflag("c2_rigger_supplied")], "按路簿交付额外黄钥匙一把、生命+40。这把额外钥匙可在第17层刃匣与第19层储备匣之间选一；其余前行钥匙别挪作支路。第18层找到双潮印，再来换第19层蓝钥匙。", "The register authorizes one extra yellow key and +40 HP. This extra key can choose the F17 edge cache or the F19 reserve cache. Do not spend the other forward-gate keys on side rooms. Bring the F18 twin-tide seal back for the F19 blue key.")
    event("ev_c2_rigger_intro", 16, "f16_rigger", [cond("c2_met_rigger", False), cond("c2_rigger_supplied", False)], [setflag("c2_met_rigger")], "我是绮线。先读第14层外柜路簿，才能领取额外钥匙和清水；它仍在可回访的楼层。", "I am Qixian. Read the outer register on F14 before collecting the extra key and water. That earlier floor remains available to revisit.")
    event("ev_c2_plan", 17, "f17_mirror_plan", [cond("c2_mirror_plan_read", False)], [setflag("c2_mirror_plan_read")], "镜向图标出回港信号的校准次序。你记下它，供第20层校准器使用。此处只是一层四邻平面回廊，不是可重叠通行的桥。", "The mirror plan records the beacon's calibration order. Keep it for the alignment instrument on F20. The causeway is one ordinary four-neighbor floor; it has no stacked crossing cells.")
    event("ev_c2_edge_cache", 17, "f17_side_cache", [cond("c2_edge_cache_taken", False)], [setflag("c2_edge_cache_taken"), grant("atk", 5)], "刃匣交付攻击+5。这花掉一把黄钥匙；若使用的是额外那把，后面的前行钥匙预算仍可保留，但第19层储备匣就不能兼得。", "The edge cache grants +5 ATK for one yellow key. Spending the extra key keeps the later forward-gate budget intact, but leaves no spare key for the F19 reserve cache.")
    event("ev_c2_sigil", 18, "f18_tide_seal", [cond("c2_sigil_found", False)], [setflag("c2_sigil_found")], "你取得双潮印。回第16层交给绮线，才能获得第19层蓝钥匙；印本身不打开门。", "You recover the twin-tide seal. Return it to Qixian on F16 for the blue key to F19. The seal itself does not open a door.")
    event("ev_c2_reserve_cache", 19, "f19_side_cache", [cond("c2_reserve_cache_taken", False)], [setflag("c2_reserve_cache_taken"), grant("hp", 80), grant("def", 2)], "储备匣交付生命+80、防御+2。它消耗一把黄钥匙；第20层前行闸仍须留下最后一把。", "The reserve cache grants +80 HP and +2 DEF for one yellow key. Keep the final yellow key for the forward gate on F20.")
    event("ev_c2_alignment", 20, "f20_alignment", [cond("c2_mirror_plan_read"), cond("c2_sigil_found"), cond("c2_mirror_aligned", False)], [setflag("c2_mirror_aligned")], "镜向图与双潮印都已齐备。校准器记住本局的设置；打开前行闸后，才可点亮回港镜台。", "The mirror plan and twin-tide seal are both recorded. The instrument stores this run's alignment. The return beacon can be lit after opening the forward gate.")
    event("ev_c2_signal", 20, "f20_signal", [cond("c2_mirror_aligned"), {"kind": "cleared", "object_id": "f20_guard", "value": True}, {"kind": "cleared", "object_id": "f20_main_gate", "value": True}], [setflag("c2_beacon_lit")], "第二道信号接通回港航线。原创1–20层切片完成，仍可回访与保存；第21–50层尚未制作，这不是整塔通关。", "The second signal reconnects the return route. The authored 1-20 slice is complete and remains open to revisit and save. Floors 21-50 are not made; the fifty-floor campaign is not complete.")
    data["journal_entries"] = [
        {"id": "chapter1_copper", "floor": 1, "text": "F3缺角铜签带回F1，换取首章档案蓝钥匙。", "text_en": "Bring the F3 copper tag back to F1 for the first-chapter archive's blue key.", "status_flag": "copper_redeemed"},
        {"id": "chapter1_keeper", "floor": 7, "text": "读F5档案，去F7领取守灯人一次补给。", "text_en": "Read the F5 archive, then collect the lightkeeper's one-time supplies on F7.", "status_flag": "keeper_supplied"},
        {"id": "c2_first_blue", "floor": 11, "text": "读F12潮尺、取F13墨印，回F11换蓝钥匙。", "text_en": "Read the F12 gauge, take the F13 ink seal, and return to F11 for the blue key.", "status_flag": "c2_first_blue_claimed"},
        {"id": "c2_register", "floor": 14, "text": "读F14外柜路簿，再找F16绮线领一次额外黄钥匙。", "text_en": "Read the F14 outer register, then collect Qixian's one extra yellow key on F16.", "status_flag": "c2_rigger_supplied"},
        {"id": "c2_second_blue", "floor": 16, "text": "F18双潮印带回F16，换F19蓝钥匙。", "text_en": "Bring the F18 twin-tide seal back to F16 for the F19 blue key.", "status_flag": "c2_second_blue_claimed"},
        {"id": "c2_beacon", "floor": 20, "text": "保存最后一把黄钥匙，校准并点亮F20镜台。", "text_en": "Reserve the last yellow key, align the instrument and light the F20 beacon.", "status_flag": "c2_beacon_lit"},
    ]
    assert data["floors"][:9] == old["floors"][:9]
    return data, topology, old


def chapter_events(style):
    result = ["f10_up"]
    for n in range(11, 21):
        p = f"f{n:02d}_"
        result += [p + "water", p + "blade", p + "coins"]
        if n in [11, 15, 17, 19]: result.append(p + "yellow_key")
        result.append(p + "scout")
        if n == 11: result.append("f11_surveyor")
        if n == 12: result.append("f12_scale")
        if n == 13: result.append("f13_ink_seal")
        if n == 14: result.append("f14_register")
        if n == 16:
            result += ["f16_rigger", "buy:f16_shop/edge", "buy:f16_shop/ward"]
        if n == 17:
            result.append("f17_mirror_plan")
            if style == "keen": result += ["f17_side_gate", "f17_side_cache"]
        if n == 18: result.append("f18_tide_seal")
        if n == 19:
            result += ["buy:f19_shop/edge", "buy:f19_shop/ward"]
            if style == "reserve": result += ["f19_side_gate", "f19_side_cache"]
        if n == 20: result.append("f20_alignment")
        result.append(p + "guard")
        if n in [12, 15, 18, 20]: result.append(p + "main_gate")
        if n in [14, 19]: result.append(p + "blue_gate")
        if n == 13: result += ["f13_down", "f12_down", "f11_surveyor", "f11_up", "f12_up"]
        if n == 18: result += ["f18_down", "f17_down", "f16_rigger", "f16_up", "f17_up"]
        result.append(p + ("up" if n < 20 else "signal"))
    return result


def world(replay):
    return {"core_state": copy.deepcopy(replay.state), "flags": copy.deepcopy(replay.flags), "completed_events": replay.completed.copy(), "slice_complete": replay.slice_complete}


def replay_events(data, events):
    run = PlanningReplay(data); ledger = []; checkpoints = {1: {"prefix_length": 0, "world": world(run)}}
    for event in events:
        ledger.append(run.apply(event))
        floor = run.state["floor"] + 1
        if floor in MANIFEST["checkpoint_floors"] and floor not in checkpoints:
            checkpoints[floor] = {"prefix_length": len(ledger), "world": world(run)}
    return run, ledger, checkpoints


def yellow_cut_proof(data, run, gate_id):
    """Complete structural overapprox: all non-yellow obstacles are passable.

    Ignoring HP, enemies, blue doors, NPC blocking and event conditions can only
    add reachable cells/sources. Zero reachable yellow sources in this larger
    graph proves the zero-key prefix cannot cross its remaining yellow cut.
    """
    if run.state["keys"].get("yellow", 0) != 0: raise ValueError("Cut proof requires zero yellow keys")
    objects = {(f["id"], *o["pos"]): o for f in data["floors"] for o in f["objects"]}
    by_id = {o["id"]: (f["id"], o) for f in data["floors"] for o in f["objects"]}
    for event in data["events"].values():
        if any(e["kind"] == "clear_object" for e in event["effects"]):
            raise ValueError("This structural certificate does not handle a door-clearing event")
    start = (run.state["floor"] + 1, *run.state["pos"]); queue = deque([start]); seen = {start}
    blocked = {p for p, o in objects.items() if o["kind"] == "door" and o["type"] == "yellow" and o["id"] not in run.state["cleared"]}
    while queue:
        f, x, y = queue.popleft()
        candidates = [(f, *p) for p in adjacent((x, y))]
        obj = objects.get((f, x, y), {})
        if obj.get("kind") == "stairs": candidates.append((obj["target"]["floor"], *obj["target"]["pos"]))
        for point in candidates:
            floor, cx, cy = point
            if point in seen or point in blocked or floor < 1 or floor > len(data["floors"]): continue
            grid = data["floors"][floor - 1]["grid"]
            if cy < 0 or cy >= len(grid) or cx < 0 or cx >= len(grid[cy]) or grid[cy][cx] == "#": continue
            seen.add(point); queue.append(point)
    remaining_pickups = []; reachable_pickups = []; potential_events = []; shops = []
    for pos, obj in objects.items():
        if obj["kind"] == "key" and obj["type"] == "yellow" and obj["id"] not in run.state["cleared"]:
            remaining_pickups.append(obj["id"])
            if pos in seen: reachable_pickups.append(obj["id"])
        if obj["kind"] == "shop" and (pos in seen or any((pos[0], *p) in seen for p in adjacent(pos[1:]))):
            for offer in data["shops"][obj["type"]]["offers"]:
                if offer["kind"] in ["key", "grant_key"]: shops.append(obj["id"] + "/" + offer["id"])
    for id, event in data["events"].items():
        if id in run.completed or not any(e["kind"] == "grant_key" and e["color"] == "yellow" for e in event["effects"]): continue
        trigger = event["trigger"]
        if trigger["kind"] == "interact":
            floor, obj = by_id[trigger["object_id"]]
            if (floor, *obj["pos"]) in seen or any((floor, *p) in seen for p in adjacent(obj["pos"])): potential_events.append(id)
        elif any((event["floor"], *p) in seen for p in trigger["cells"]): potential_events.append(id)
    floor, gate = by_id[gate_id]
    exit_id = f"f{floor:02d}_up" if floor < 20 else "f20_signal"
    _, exit_obj = by_id[exit_id]
    adjacent_to_gate = any((floor, *p) in seen for p in adjacent(gate["pos"]))
    exit_unreachable = (floor, *exit_obj["pos"]) not in seen
    goal_floor, goal = by_id["f20_signal"]
    goal_unreachable = (goal_floor, *goal["pos"]) not in seen and not any((goal_floor, *p) in seen for p in adjacent(goal["pos"]))
    proven = not reachable_pickups and not potential_events and not shops and adjacent_to_gate and exit_unreachable and goal_unreachable
    if not proven: raise ValueError(f"Bad prefix is not a proven yellow-key cut: {gate_id}")
    return {"classification": "known_yellow_key_cut_in_design_model", "complete_relaxed_graph": True, "queue_exhausted": True, "nodes": len(seen), "reachable_floor_ids": sorted({p[0] for p in seen}), "per_floor_reachable_cells": {str(f): sum(p[0] == f for p in seen) for f in sorted({p[0] for p in seen})}, "ordinary_enemy_costs_ignored": True, "blue_doors_and_npcs_relaxed_open": True, "event_conditions_relaxed_true": True, "yellow_keys": 0, "remaining_yellow_pickup_ids": sorted(remaining_pickups), "reachable_yellow_pickup_ids": reachable_pickups, "reachable_unclaimed_yellow_event_ids": potential_events, "reachable_yellow_shop_offers": shops, "forward_cut_gate": gate_id, "cut_gate_reachable_from_this_side": adjacent_to_gate, "gate_floor_exit_unreachable": exit_unreachable, "goal_object_id": "f20_signal", "goal_and_approach_unreachable": goal_unreachable, "engine_reproduced": False, "scope": "Complete graph overapproximation proves a zero-yellow-key cut for this exact planning prefix. It is not a generic combat/resource solver and not a runtime failure event."}


def add_routes_and_scenarios(data, old):
    prefix = next(r for r in old["validated_routes"] if r["name"] == "blade")["events"]
    routes = []; checkpoint_sets = {}
    for style in ["keen", "reserve"]:
        events = prefix + chapter_events(style)
        run, ledger, checkpoints = replay_events(data, events)
        assert run.slice_complete and not run.state["won"] and run.state["keys"] == {"yellow": 0, "blue": 0}
        routes.append({"name": style, "policy": "首章刃路，额外钥匙选F17攻击匣" if style == "keen" else "首章刃路，额外钥匙留给F19生命/护甲匣", "events": events, "ledger": ledger, "final": run.resources() | {"won": False}, "slice_complete": True, "final_flags": copy.deepcopy(run.flags), "completed_events": run.completed.copy(), "final_purchases": copy.deepcopy(run.state["purchases"]), "final_cleared": sorted(run.state["cleared"]), "design_calculation": {"engine_tested": False, "scope": "Reused non-authoritative Python design arithmetic/BFS, root actual API replay required.", "ordinary_combats": run.combats, "planned_walk_steps": run.paths, "minimum_hp": run.minimum_hp}})
        checkpoint_sets[style] = checkpoints
    data["validated_routes"] = routes
    scenarios = []
    route = routes[0]
    for floor in [11, 15]:
        cp = checkpoint_sets["keen"][floor]; pre = route["events"][:cp["prefix_length"]]
        p = f"f{floor:02d}_"
        bad_suffix = [p + "water", p + "blade", p + "coins", p + "yellow_key", p + "scout"]
        if floor == 11: bad_suffix.append("f11_surveyor")
        bad_suffix += [p + "side_gate", p + "side_cache", p + "guard"]
        if floor == 11: bad_suffix += ["f11_up", "f12_water", "f12_blade", "f12_coins", "f12_scout", "f12_scale", "f12_guard"]
        bad, bad_ledger, _ = replay_events(data, pre + bad_suffix)
        gate = "f12_main_gate" if floor == 11 else "f15_main_gate"
        proof = yellow_cut_proof(data, bad, gate)
        # Rebuild the actual same-prefix planning world, then continue its legal
        # authored suffix; no partial refund or resource setter is simulated.
        good, _, _ = replay_events(data, pre + route["events"][cp["prefix_length"]:])
        scenarios.append({"id": f"bad_early_side_gate_f{floor}", "name": f"F{floor} spends its forward key on an early side cache", "goal_object_id": "f20_signal", "checkpoint_id": f"entry_{floor:02d}", "checkpoint_floor": floor, "mode": "practice_checkpoint", "requested_seed": "00000001", "prefix_events": pre, "bad_suffix_events": bad_suffix, "bad_ledger": bad_ledger[len(pre):], "canonical_checkpoint_world": cp["world"], "canonical_bad_world": world(bad), "failed_interaction": {"object_id": gate, "expected_action": "door_locked", "gameplay_state_unchanged": True}, "key_cut_proof": proof, "restore_contract": {"complete_checkpoint_required": True, "same_seed_and_layout": True, "later_gains_and_consumption_both_rollback": True, "runtime_failure_if_marked": "explicit_give_up_is_abandoned_not_unsat", "resources_injected": False}, "recovery_route": "keen", "recovery_suffix_events": route["events"][cp["prefix_length"]:], "expected_recovered_final": good.resources() | {"won": False, "slice_complete": True}, "engine_tested": False})
    return scenarios, checkpoint_sets


def audit(data, old, topology, scenarios, checkpoint_sets):
    assert data["floors"][:9] == old["floors"][:9]
    assert data["initial_player"] == old["initial_player"]
    for id, enemy in old["enemies"].items(): assert data["enemies"][id] == enemy
    for id, shop in old["shops"].items(): assert data["shops"][id] == shop
    for id, event in old["events"].items():
        if id != "ev_signal": assert data["events"][id] == event
        else:
            for field in ["floor", "trigger", "conditions", "effects", "once"]: assert data["events"][id][field] == event[field]
    original10 = old["floors"][9]; combined10 = data["floors"][9]
    assert [(x, y) for y, row in enumerate(original10["grid"]) for x, char in enumerate(row) if char != combined10["grid"][y][x]] == [(8, 1)]
    assert len(combined10["objects"]) == len(original10["objects"]) + 1
    for original in original10["objects"]:
        expected = copy.deepcopy(original)
        if original["id"] == "f10_signal": expected.pop("slice_goal", None)
        assert next(o for o in combined10["objects"] if o["id"] == original["id"]) == expected
    assert len(data["floors"]) == 20 and [f["id"] for f in data["floors"]] == list(range(1, 21))
    by_id = {}; count = Counter()
    for f in data["floors"]:
        occupied = set()
        for o in f["objects"]:
            assert o["id"] not in by_id and tuple(o["pos"]) not in occupied and tuple(o["pos"]) in cells(f["grid"])
            assert not o.get("victory", False)
            by_id[o["id"]] = (f["id"], o); occupied.add(tuple(o["pos"])); count[o["kind"]] += 1
    for floor, o in by_id.values():
        if o["kind"] == "stairs":
            dest_floor, other = by_id[o["target"]["object_id"]]
            assert dest_floor == o["target"]["floor"] and other["pos"] == o["target"]["pos"]
            assert other["target"] == {"floor": floor, "pos": o["pos"], "object_id": o["id"]}
    assert [id for id, (_, o) in by_id.items() if o.get("slice_goal")] == ["f20_signal"]
    for event_id, event in data["events"].items():
        assert event["once"] is True
        if event["trigger"]["kind"] == "interact":
            floor, o = by_id[event["trigger"]["object_id"]]
            assert floor == event["floor"] and event_id in o["event_ids"]
    upper = Counter()
    for stat in ["hp", "atk", "def", "gold"]: upper[stat] += data["initial_player"][stat]
    for _, o in by_id.values():
        if o["kind"] == "enemy": upper["gold"] += data["enemies"][o["type"]]["gold"]
        elif o["kind"] in ["potion", "atk", "def", "gold", "key"]: upper[("key:" + o["type"]) if o["kind"] == "key" else ("hp" if o["kind"] == "potion" else o["kind"])] += o["amount"]
    for e in data["events"].values():
        for effect in e["effects"]:
            if effect["kind"] == "grant": upper[effect["stat"]] += effect["amount"]
            if effect["kind"] == "grant_key": upper["key:" + effect["color"]] += effect["amount"]
    for shop in data["shops"].values():
        for offer in shop["offers"]: upper["hp" if offer["kind"] == "potion" else offer["kind"]] += offer["amount"] * offer["limit"]
    return {"scope": "New chapter2 build-time static geometry/key-cut and planning evidence only. No Godot/native/GUI run.", "engine_tested": False, "chapter1_frozen_source_sha256": OLD_SHA, "floors_1_to_9_deep_equal": True, "floor10_bridge_edits": ["grid[1][8] wall to floor", "f10_signal no longer slice_goal", "ev_signal milestone copy updated without resource-effect changes", "new f10_up at [8,1]"], "target_floors": 50, "authored_floor_count": 20, "unmade_floor_count": 30, "checkpoint_floors": [1, 5, 11, 15], "new_topology_checks": topology, "object_count": len(by_id), "object_kinds": dict(sorted(count.items())), "all_stairs_bidirectional": True, "loose_independent_resource_upper_envelope": dict(sorted(upper.items())), "upper_envelope_note": "Not jointly attainable: finite keys cannot open every optional door, and finite shop stock still costs gold.", "new_yellow_budget": {"fixed_pickups": ["f11_yellow_key", "f15_yellow_key", "f17_yellow_key", "f19_yellow_key"], "one_time_event": "ev_c2_rigger_supply", "total": 5, "mandatory_main_gates": ["f12_main_gate", "f15_main_gate", "f18_main_gate", "f20_main_gate"], "safe_optional_choices": ["f17_side_gate", "f19_side_gate"], "spare_keys": 1}, "new_blue_budget": {"one_time_events": ["ev_c2_first_blue", "ev_c2_second_blue"], "total": 2, "mandatory_blue_gates": ["f14_blue_gate", "f19_blue_gate"]}, "routes": [{"name": r["name"], "events": len(r["events"]), "final": r["final"], **r["design_calculation"]} for r in data["validated_routes"]], "checkpoint_planning_worlds": {str(k): v for k, v in checkpoint_sets["keen"].items()}, "recovery_scenarios": scenarios}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare the three existing NEW chapter2 data files in memory; write nothing.")
    args = parser.parse_args()
    data, topology, old = make_content()
    scenarios, checkpoints = add_routes_and_scenarios(data, old)
    budget = audit(data, old, topology, scenarios, checkpoints)
    raw_content = packed(data)
    budget["content_file_sha256"] = hashlib.sha256(raw_content).hexdigest()
    payloads = {"chapter2-content.json": raw_content, "chapter2-manifest.json": packed(MANIFEST), "chapter2-budget.json": packed(budget)}
    for name, raw in payloads.items():
        path = ROOT / "data" / name
        if args.check:
            if not path.exists() or path.read_bytes() != raw: raise SystemExit("Reproducibility mismatch: " + name)
        else: path.write_bytes(raw)
    print(json.dumps({"build_check": "passed", "engine_tested": False, "outputs": {n: {"sha256": hashlib.sha256(v).hexdigest(), "bytes": len(v)} for n, v in payloads.items()}, "routes": budget["routes"], "key_cut_scenarios": [{"id": s["id"], "classification": s["key_cut_proof"]["classification"]} for s in scenarios]}, ensure_ascii=False))


if __name__ == "__main__": main()
