# 回港章：原创11–20层与完整1–20见证

本章只交付六个新增文件：`data/chapter2-content.json`、`data/chapter2-manifest.json`、`data/chapter2-budget.json`、`tools/build_chapter2.py`、`tools/chapter2_catalogue.py`和本文。目标仍为50层；现组合内容明确制作1–20层，21–50层未制作，无空壳楼层。F10只保留首章信号里程碑，F20完成当前切片，`core.won=false`，不宣称50层通关。

所有11–20层地图、数值、中文／英文对白、NPC和线索均为新原创，按仓库MIT许可交付。没有复制商业魔塔关卡／对白，没有素材下载、网络访问、安装或新project.godot。复用现有普通战斗、typed事件、四邻格、资产、库存和完整checkpoint能力。本文件及预算是轻量Python设计证据；**尚未代表Godot实际运行、GUI、浏览器、玩家时长或全seed验收**。

## 冻结首章如何组合

构建器读取并校验原`data/content.json` SHA256：`3703b2cbc43d2297d42d335ad85ebac3f464d9f6c68d536d75a990e9bdd75fd5`，深拷贝后才在新文件中组合。原v1文件、旧builder/catalogue、旧存档、review、证据和ZIP均不写入。

- F1–F9整层数据完全相等；原初始角色、敌人数值、商店、旧事件资源效果也相等。
- 组合内F10只把`grid[1][8]`由墙改为空地，增加`f10_up`于`[8,1]`，与F11 `f11_down`互指。
- 原`f10_signal`仍在`[7,1]`，事件仍设`relay_lit`且不改资源效果；只去掉`slice_goal`并更新章末文字，明确可以继续11–20。
- 新content_id=`stairkeep-fifty-chapter2/v1`，唯一完成对象为`f20_signal`。manifest为authored1–20／not_authored21–50／checkpoint_floors `[1,5,11,15]`／default_mode null／legacy_save_migration false。

新profile必须显式选classic或practice；不能迁移原3层、21层或首章v1存档。Classic新局整体重置并使用新runSeed；practice只恢复真实捕获的完整checkpoint，同seed／同布局，后续收益和消耗一起撤回。此内容文件不提供单项退款、补钥匙、补血或补库存的恢复捷径。

## 十层实际结构与目标

十张新图均为显式17×17固定行。与前十层、彼此之间，去掉标签后都不构成D4复制。主守卫G、黄闸H或蓝闸B是上行口的割点；可选门A只控制自己的奖励支室。所有关卡都是**单一平面的四邻格**；桥、缆台和回声是美术／叙事意象，不存在同坐标上下叠桥或未实现高度物理。

每层都有固定清水、ATK+3、金币+12、一名可绕行巡者和一名主路守卫。见证选择战斗两者；所有敌人都按普通先手公式结算，没有新增特殊伤害公式、Boss周期或随机刷怪。

| 层／英文名 | 空间节奏（空格／独立环） | 可实际执行的目标／交互 | 本层有限资源取舍 |
|---|---|---|---|
| 11 断泉转轮 / Dry Spring Wheel | 转轮环道与单侧窄匣，68／3 | 与`f11_surveyor`砾舟交谈；拿本层黄钥匙继续F12，日后携两条线索回访换蓝钥匙。 | 主水80、ATK3、金12、黄1。提前开A只得HP90／金30，会失去F12前行钥匙。 |
| 12 潮尺关庭 / Tide Gauge Court | 多环关庭与串行闸颈，72／5 | 读取`f12_scale`，打开`f12_main_gate`，将读数带回F11。 | 主水100、ATK3、金12，无钥匙；主闸消耗F11黄1。 |
| 13 墨印回湾 / Ink Seal Reach | 回湾交织网络，90／9 | 取得`f13_ink_seal`；沿双向楼梯回F11，潮尺+墨印共同换蓝1，再返回F13继续。 | 主水100、ATK3、金12，无新增钥匙；不把印记直接当钥匙。 |
| 14 双封档库 / Double-Sealed Archive | 外柜环路与蓝闸前庭，69／4 | 阅读`f14_register`，取得ATK3／DEF3／HP80；用蓝钥匙开`f14_blue_gate`上行。 | 外柜在主闸前，阅读与开门分别保持状态；外柜flag授权F16补给。 |
| 15 孤钥闸心 / Lone-Key Sluice | 回环闸心与独立应急匣，86／9 | 取得黄1，打开`f15_main_gate`。本层是完整practice checkpoint。 | 前行闸和应急匣共享唯一当前钥匙；应急匣HP110／金40，不返还钥匙。 |
| 16 折光缆台 / Refraction Cable Deck | 多回路缆台，82／11 | 凭F14路簿与`f16_rigger`绮线交谈，领取一次黄1／HP40；在有限修补台采购。 | 这把额外黄钥匙可选F17攻击匣或F19储备匣，不能两者兼得。绮线还要求F18双潮印换第二把蓝钥匙。 |
| 17 悬桥回声 / Echo Causeway | 单层桥形回廊，78／7 | 读`f17_mirror_plan`，为F20校准记录条件；拿黄1。 | 可花额外黄1开刃匣得ATK5；若不花，留给F19储备匣。 |
| 18 双潮印室 / Twin-Tide Seal Room | 多环印室与关颈，80／9 | 拿`f18_tide_seal`并开黄主闸；回F16绮线换蓝1，再回来上行。 | 本层无黄源，消耗先前保留黄1；交印不刷新怪、物或商店。 |
| 19 侧风水栈 / Crosswind Water Depot | 横向水栈环路，84／7 | 拿黄1、在第二修补台采购，用F16换得的蓝1开主蓝闸。 | 若F17没开刃匣，可用额外黄1开储备匣得HP80／DEF2；必须留最后黄1给F20。 |
| 20 回港镜台 / Return Beacon Mirror | 终端多环镜庭，101／10 | `f20_alignment`核F17镜向图与F18印记；击败普通守卫，开黄主闸，交互`f20_signal`。 | 无新增钥匙；消耗F19保留黄1。完成的是1–20切片，允许回访，未制作21层入口。 |

每层新对象有`name_en`，NPC／event同时有中文`text`与原创`text_en`。线索只引用楼层、对象身份和颜色，不把绝对东／西条件藏在对白中。`journal_entries`六行只读metadata保留首章两条回访，并列出新四条线索；status_flag均为已声明的boolean，不增加规则或自动奖励。

## 稀缺钥匙总账

首章blade前缀已经消耗10黄与1蓝，进入F11时钥匙库存为0。新章预算如下：

| 颜色 | 全部新来源 | 必需消耗 | 可选余量 |
|---|---|---|---|
| 黄 | F11、F15、F17、F19固定各1；F16绮线一次授1，共5 | F12／F15／F18／F20前行主闸各1，共4 | 1把，在F17攻击匣与F19储备匣之间选择。 |
| 蓝 | F11潮尺+墨印交换1；F16双潮印交换1，共2 | F14／F19主蓝闸各1，共2 | 0；没有商店蓝钥匙。 |

F11与F15的早开支匣不是免费收益，它们先花了到下一段必须保留的钥匙；F16额外黄源在F15主闸之后，无法从错误分支获得。对白与门名说明这一点，坏选择仍保留给实际回档反例，不暗改资源挽救它。

全部钥匙与事件均有限、once；无钥匙商店，无随机补给，无怪物重生。F11交换要求潮尺与墨印两flag；F16先按路簿供给，之后才可凭双潮印换蓝。奖励分支优先于intro，已兑换／已领取之后不会再出现过时的初见任务或第二次授钥。

## 完整F1→F20 macro witness

两条路线都从F1开始，前106事件完全沿冻结首章`blade`的稳定ID序列，再执行`f10_up`进入新章；不是把F10末资源直接塞给新run。主路线在`validated_routes`中提供完整明确事件序列及逐事件资源、flags、completed_events、purchases、cleared_count和选中event ID。

- F13首次到达后：`f13_down → f12_down → f11_surveyor → f11_up → f12_up → f13_up`，实际带回线索取得第一蓝钥匙。
- F18首次取得印记并开主闸后：`f18_down → f17_down → f16_rigger → f16_up → f17_up → f18_up`，实际取得第二蓝钥匙。
- F16和F19各实买edge、ward一次，两个checkpoint之后确实存在购物、flags、事件与世界变化；不会用空库存差异测试冒充恢复覆盖。

新店两家，offer均每店库存1：edge花160金得ATK8，ward花140金得DEF5，flask花110金得HP120。见证不买flask，余库存可供玩家另作选择；首章商店价格与库存保持不变。

| 规划路线 | 黄余量用途 | 事件／普通战斗 | 计划走格 | 末HP／ATK／DEF／金币 | 最低HP |
|---|---|---:|---:|---|---:|
| keen | F17攻击匣ATK5 | 201／40 | 1277 | 227／111／32／733 | 36 |
| reserve | F19储备匣HP80／DEF2 | 201／40 | 1255 | 244／106／34／733 | 36 |

两者均末钥匙黄0／蓝0、slice_complete true、won false。F17攻击会减少后面若干回击，储备路线有更多生命与防御；并非仅换名字的同一预算。最低36生命出现在新章早段，不能省略F14外柜或跳过路线中的资源步骤后还沿用同一预算。

可复核的预算恒等式：

| 项目 | keen | reserve |
|---|---|---|
| HP来源−战损 | 首章来源795 + 新主水980 + F14外柜80 + F16供给40 − 全程1668 = **227** | 同左再加F19储备80 − 全程1731 = **244** |
| ATK | 首章57 + 新主路30 + F14外柜3 + 两店16 + F17匣5 = **111** | 不取F17匣 = **106** |
| DEF | 首章19 + F14外柜3 + 两店10 = **32** | 再加F19匣2 = **34** |
| 金币 | 首章末418 + 新巡者330 + 新守卫465 + 新拾取120 − 新采购600 = **733** | 相同 |

组合共237个唯一对象、38楼梯、31门、41敌（含原F9不可穿透但非必经的封存像）、5家有限商店。松弛独立资源上包络为HP2760／ATK129／DEF55／金币1583／黄15／蓝3；它计入互斥支匣及全部库存，是宽松上界，不能当作可同时取得的角色、退款额度或恢复补给。

## F11／F15坏选择与完整恢复

`chapter2-budget.json.recovery_scenarios`保存每个场景的完整F1前缀、坏选择后缀、canonical checkpoint world、坏世界、预期锁门拒绝、完整恢复后缀与证明。位置是canonical设计坐标，实际seed1需按runtime D4映射并由正式API走到；不能用JSON位置注入activeGame。

| 场景 | 真实入口前缀／坏后缀 | checkpoint资源HP／ATK／DEF／金 | 坏选择后资源 | 被切断的主闸 | 同入口可赢后缀 |
|---|---:|---|---|---|---:|
| bad_early_side_gate_f11 | 107／16事件 | 77／57／19／418，黄0蓝0 | 143／63／19／591，黄0蓝0 | F12 `f12_main_gate` | keen后94事件 |
| bad_early_side_gate_f15 | 143／8事件 | 98／72／22／724，黄0蓝0 | 186／75／22／853，黄0蓝0 | F15 `f15_main_gate` | keen后58事件 |

坏状态生命和金币更多，仍不能前行；不能仅凭HP／金币做dominance合并而忽略钥匙与世界门状态。

已执行的轻量证明是完整跨层松弛BFS：

1. 起于确切坏前缀世界，黄钥匙库存必须为0；已开黄门保持可走，未开黄门阻挡。
2. 放行**一切非黄障碍**：忽略敌人生命成本、蓝门、NPC阻挡和事件条件，扩大可达集合；因此不能因某敌暂不可胜而漏掉潜在授钥路径。
3. 从全部可达楼层逐项检查未捡黄钥匙、所有未完成的可能授黄事件（即使当前条件未满足也纳入）、以及可授／售钥商品。当前内容没有`clear_object`事件；构建证明遇到此effect会拒绝，而不是漏算。
4. F11坏局穷尽727节点、可达F1–F12；F15坏局穷尽968节点、可达F1–F15。两者可达黄拾取／授黄event／黄shop均为0，F20目标及其相邻格均不可达，主闸后本层出口也不可达。

这支持当前typed动作集下的**known yellow-key cut设计结论**，不是有限策略没找到路，也不是把HP solver的unknown写成unsat。它仍须由根端从F1实际重放坏前缀、确认锁门拒绝全状态不变，并独立对实际state再算一次。Python证书中的`engine_reproduced=false`保留来源边界。

practice实际恢复必须使用真`entry_11`／`entry_15`快照：

- CP11恢复后库存黄钥匙仍为0，F11钥匙拾取重新变为未取；不是直接发一把钥匙。已拿的匣水／钱、已开的侧门、cache flag、后续战斗奖励和全部后续库存一起回退。
- CP15同理回到98HP／72ATK／22DEF／724金、钥匙0，F15钥匙未取；F16／F19购物必须撤回，不能保留收益又补回库存。
- 同seed、同布局；checkpoint timeline截到目标。runtime按其既有契约保留恢复／失败审计历史，不能把历史字段删除来凑整份快照字节相等。
- 若为测试先结束坏局，当前API的`give_up(true)`应记录**abandoned**；钥匙切割证明不把它改成combat_death或伪造runtime自动unsat。
- 从完整恢复的真实世界执行94／58事件后缀才计获胜。单项改钥匙／金币、重建角色但保留世界、换seed、复制末预算均不计恢复。

## 复现、数据契约及待验边界

在原`game/fifty/`运行已装Python标准库：

```text
python -B tools/build_chapter2.py
python -B tools/build_chapter2.py --check
```

构建只输出三份新的chapter2数据文件；`--check`只在内存重建并比较bytes。它复用原规划器，不新增runtime战斗公式。当前构建与同字节检查通过，旧文件hash保持不变。尝试追加独立子agent审查时遇到team thread limit，未启动该审查；不把自身检查冒称新的独立review。测试owner另行实现实际API与独立key-cut QA，native只由根端统一执行。

新事件沿既有interact／flag／cleared／set_flag／grant／grant_key／once合同，没有未支持的新effect。root journal_entries只提供`{id,floor,text,text_en,status_flag}`只读显示；root completion仍单一`slice_goal_object_id='f20_signal'`。宏路线中的`ledger.state`是应精确比对的资源；`floor/pos/planned_walk_steps`是canonical规划元数据，NPC相邻落点可因合法寻路不同而变化，不能未执行同一路径却强配坐标。

最终内容SHA256为`a02704a4b9a9e871cca23054980e8f9dc45827ee58e8326ed19f5fbbc3953d58`；manifest为`dfa59c01c80cf278027f54eef682c39d5f3125b3e09e8df1d9fd0eb9591e0f6e`；预算为`41b871e5702881c09ca78a73d5d6d444b6c443677994dd0b0e69221922f2d6be`。

仍待根端实际验：F1 seed1完整路线、F10桥接／F20仅slice完成、全部preview=实扣、双向楼层与NPC一次性、两坏前缀key-cut、F11／F15完整恢复及失败拒绝、跨profile旧save不迁移。GUI权限边界不重试；新原生／Web画面、HTTP浏览器、人工输入、导出和真实时长分别验收，不用静态预算外推。
