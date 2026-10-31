# 恢复 follow-up 独立只读 review

审查方式：读取新early/late/helper源码、原队列、根端三份历史smoke及最新8份全量JSONL/summary；用Python标准库核对journal SHA、逐例完整状态、账本与精确队列分区。没有启动Godot/GUI，没有修改被评代码、稳定五源、guard、数据或原baseline。

## 源码快照

| 文件 | SHA256 |
|---|---|
| tests/replay_early_purchase_guard.gd（矛盾分类拒绝修复后） | `2467f66f423bda5f014c9c5a78971f3d18193db76d3d98f93d30a466d32dec50` |
| tests/replay_late_checkpoint_recovery.gd（覆盖预检修复后） | `bd735004625d142f4b40369d00392d4fddee54b6994e319f083767778a518611` |
| tests/recovery_followup_helpers.gd | `914173add2e8233e431bc13bc36b256e5a6e13b54ca6e7fea63c9c8564adb751` |
| recovery-followup-input.json | `45b905d9157585ba8a06df612c9a727ad5bbe3ee7c89c4e4bae0253f94c567d0` |

## 两项具体校验缺口

1. **[P2，源码修复及最新全early独立读审已确认] 同状态相互矛盾的complete结果原未被拒绝。** 原c4d版在第一份完整`known_losing`之后，fresh确认query除`known_losing`外也允许`unknown`或`known_winning`继续。新2467版仅允许再次known_losing并明确接受，或诚实的有界unknown；同绑定的complete winning现会令该case报错并保留前后报告。预算变化可合理造成unknown，但不能解释complete winning与complete unsat互相矛盾。三份旧smoke没有触发该分支，其既有结果未因此被改写；最新2467正式批次现已覆盖全部1,336例，第二次实际查询均为known_losing。本review未新增故意返回矛盾结果的引擎负例。

2. **[P2，源码修复及最新26例引擎记录已确认] Late原全26标记只基于数量，缺少队列唯一性预检。** 原b1版只检查`late_cases`是Array，`all_26_complete`只要求offset0/requested26/请求完成。新bd版在选择shard之前pin原queue/classification SHA，核exact26唯一整数index、late cohort、失败阶段21、精确原分类index集合（含599），并比对raw verification/trace中的18项稳定身份字段。footer现要求actual completed唯一集合等于selected集合、每结果passed及每个initial实际获胜；全26标记还必须等于exact26集合。**实际45b905队列已由本review只读确认：26个唯一late、均stage21、包含599；1,336个唯一early，两个集合不相交。** 本review额外独立读52个bound raw lines核line SHA，对1,404个稳定字段比较为0差异。最新bd正向26例运行已按下节全部复核；本review没有另跑篡改/重复队列负例。

## 实际已运行证据

根端提供的以下journal都与各自summary声明的SHA相符，measurement_completed均为所请求子集完成，errors均为空。Early报告绑定原c4d版`c4d189be58ebe08f19ddcafdbe12920c9a0810203112cc43e281d7cc94cc0ded`，late报告绑定原b1版`b1b9977a63141436fcbe7419d066ee64265249b916bcc10f462a2a9661f206b7`；不能将这些旧报告冒认最新控制修复版的引擎运行：

| journal basename | 已实测范围 | 观察 |
|---|---|---|
| early-guard-benchmark-10.jsonl | 10个首店case，18,397ms | 10个默认known-loss拦截、整状态不变；显式接受原购买后复现原terminal；10个完整初始checkpoint恢复。没有在此benchmark执行10条获胜后缀。 |
| early-guard-win-smoke-1.jsonl | case4，3,650ms | 43个原actions实际/shadow整快照相等；默认拦截不变；完整恢复后实际323个blade事件通关，HP138/ATK153/DEF47/gold946，seed相同。该case包含在前述10例内，不可合计成11个独立case。 |
| late-recovery-smoke-1.jsonl | case24，10,935ms | 原始完整前缀经实际Campaign重放，采集1/4/7/10/13/16/19七个checkpoint；19候选最后为unknown，16通过resource policy实际获胜；独立初始checkpoint完整blade也获胜。 |

Late的`nearest_verified=16`是按当前有限尝试找到的最近**已验证**胜利入口，既不证明19无解，也不证明16是数学上的最近可赢入口。`unknown_id_order_not_executable`、某条policy走到dead-end、solver超预算均未被写成checkpoint unsat。

这些是根端已有引擎运行，review者只读复核。这三份smoke本身不覆盖完整1,336或26；后续最新26例的独立证据另列如下，旧smoke没有被重写。

## 最新late全26独立源读审

任务工作区`output/recovery-aggregate-late-26/summary.json`的late精确覆盖为26/26，4份根端journal均绑定最新bd脚本、914 helper和同一45b905原queue。独立核对结果：

| 核对项 | 结果 |
|---|---:|
| 完整journal字节数、SHA与各自summary SHA | 4份一致 |
| exact原case index集合、无重复/无遗漏 | 26 |
| 原始/候选/初始赢路等receipt行号、offset、length、line SHA | 367条一致 |
| 完整恢复expected树与actual树（含明确历史例外） | 71份一致 |
| 初始blade事件、资源/每店库存/cleared数量及最终对象集合 | 8,398事件一致 |
| 初始路线实际动作 / preview-deduction比较 | 43,989 / 1,742 |
| 候选入口实际获胜后缀动作 | 84,464 |

26例均从实际捕获的候选入口恢复，以`observed_resource_policy`实际获胜；19层10例、16层13例、13层3例。另26例逐个从实际初始checkpoint恢复并完成完整blade，最终HP138/ATK153/DEF47/gold946。候选入口较晚的180次ID-order不可执行、19次policy dead-end和19次solver unknown仍保留，`proven_unsat=0`。

| case | seed | 原终点层 | 最近已验证入口 | 候选路线最终HP |
|---:|---|---:|---:|---:|
| 24 | 015b82f9 | 21 | 16 | 7 |
| 169 | 02433a22 | 21 | 19 | 1 |
| 599 | 04f26220 | 1 | 16 | 68 |
| 1289 | 09410782 | 21 | 13 | 7 |
| 1349 | 09a0e95e | 21 | 19 | 9 |
| 1634 | 0b685a33 | 21 | 16 | 108 |
| 1979 | 0d8face4 | 21 | 19 | 89 |
| 1994 | 0da7a55b | 21 | 19 | 65 |
| 2279 | 0f6f1630 | 21 | 16 | 1 |
| 2479 | 10aeb1b8 | 21 | 16 | 159 |
| 2739 | 124e2f1c | 21 | 16 | 91 |
| 3129 | 14bd6b32 | 21 | 19 | 79 |
| 3354 | 1624fa2b | 21 | 16 | 20 |
| 3379 | 164ced9c | 21 | 19 | 9 |
| 4554 | 1da29f5b | 21 | 19 | 10 |
| 5269 | 2219382e | 21 | 19 | 56 |
| 5704 | 24d05da9 | 21 | 16 | 4 |
| 5854 | 25c0124f | 21 | 16 | 123 |
| 7609 | 30b4a0b2 | 21 | 19 | 19 |
| 7784 | 31cc48c9 | 21 | 16 | 80 |
| 7899 | 32840f04 | 21 | 13 | 58 |
| 8179 | 3443825c | 21 | 16 | 21 |
| 8194 | 345b7ad3 | 21 | 13 | 72 |
| 8574 | 36babbef | 21 | 16 | 75 |
| 8704 | 378a7aa1 | 21 | 16 | 70 |
| 9019 | 3981dc64 | 21 | 19 | 45 |

可复核绑定（路径相对任务工作区）：

- `output/recovery-aggregate-late-26/summary.json`：`1d58d3d41a6ed828d24446f2f01d8c5b63ae2fc003c1cd725795c34474fde2ce`。
- `output/recovery-aggregate-late-26/case-receipts.jsonl.gz`：`d1da531201ed7a4b677598793e5f5cf60e4ac8fca1b05713861703744c2d52e6`。
- 新的26行精简表`output/recovery-aggregate-late-26-v2/late-case-table.json`：`9eeddfb596bb9ec6aa7302814d464590b8cdf03f6ee2bca16dd3cfa087569a61`。另核26行seed/checkpoint/HP与52个实际赢路/初始fallback定位一致。

历史late-only汇总保留`measurement_completed=false`，因为该报告没有纳入early完整队列；其`coverage.late.exact_set_complete=true`。不修改历史报告。下节新的正式完整汇总现已纳入全部early及late，两组精确覆盖均完成。

## 正式全量early 1,336与late 26：最终只读审计

正式产物位于任务工作区`output/recovery-followup-evidence-final/`。根端实际执行、review者只读检查；没有再次启动引擎。汇总`validation_passed=true`、`measurement_completed=true`，8part均为最新2467／bd／914来源；early与late各4part，两个index精确集合无重无漏且互不相交。

| 独立核对项 | 结果 |
|---|---:|
| 8份完整journal字节SHA及manifest长度 | 2,076,867,713字节一致 |
| receipt唯一集合与原45b905队列 | early 1,336；late 26 |
| early默认preview与fresh显式查询均known_losing | 1,336 / 1,336 |
| 默认blocked前后完整状态相等；counterfactual post与shadow真实购买后整快照相等 | 1,336 |
| 显式确认真实购买后复现原terminal | 1,336 |
| early初始完整恢复树（含新增实际failure ID及保留消费历史） | 1,336一致 |
| early实际blade逐事件HP/ATK/DEF/gold/keys、每店购买数及cleared数量 | 431,528事件一致 |
| early记录的实际actions / preview-deduction比较 | 2,260,474 / 89,512 |
| early最终完整cleared集合、购买库存与seed/sequence/attempt | 1,336一致 |
| owner完整退出、exit0／stderr0／source before=after | 8份一致 |

逐例初始恢复仍遵守既有例外：先以真实initial snapshot为完整expected，再把`failure_events_seen`改为实际原历史加本次`assess_failure()`生成的failure ID，保留实际`consumed_loss_ids`。没有删掉字段来凑相等，其他状态逐树一致。每个early完整blade最后均为HP138／ATK153／DEF47／gold946、278个精确cleared对象，原seed／sequence、attempt0不变。末态不是向原败局加资源，而是完整回退后实际执行不同路线。

六种原前缀精确分布为defense-open/flask452、defense-open/ward394、key-available/flask151、key-available/ward139、key-uncollected/flask95、key-uncollected/ward105；未拾取钥匙的200例没有被误写成已消耗。Late正式receipt与4份manifest和此前本review已独立核过的26-case版本完全相同；另核26个最终case summary locator字节SHA一致。19层10／16层13／13层3的已验证入口，以及180次ID-order不可执行、19次policy dead-end、19次solver unknown全部保留，`proven_unsat=0`。

正式汇总分开列出1,336个默认拦截、1,336个显式原策略仍败、1,336个完整初始回档再blade实际胜；加26个late独立初始赢路后共1,362个完整初始恢复及通关。**当前购买前态的实际winning suffix执行数为0**，初始回档不能证明被保留prestate有赢路，post-unsat不能单独证明这次购买造成loss。最近已验证checkpoint也不能改称数学最近可赢入口。

可复核绑定：

| 正式文件 | SHA256 |
|---|---|
| summary.json | `998332094d7592a69597cccfcfde1256ddf2aa4cd57934d89936462aacd86cac` |
| case-receipts.jsonl.gz | `2443137a5ff96b4f101d7fec6f546a256b9e62b9ba9d70f6fff20b71365409a4` |
| journal-manifest.json | `b2990acb696e5fd9b573d7751cf55b87e5327300d9a2a79c1deb857f1374d6da` |

另只读核根端`output/recovery-aggregator-selftest-cli.json`为20项通过；这是聚合器CLI正负例结果，不能算作20个新增游戏通关或UI测试。controller记录8native worker已退出、最大并发4、BelowNormal、源不变；本review没有重启worker或重跑原10k baseline。

本地当前来源与正式summary的以下8个SHA逐字节一致，保留游戏与数据未变的边界：

| 来源 | SHA256 |
|---|---|
| data/levels21.json | `b11c41ed50566f0fcfc7c50f59641c987d29b249435ff08487ab17fd580550d1` |
| scripts/base_rules.gd | `e89070d800c3a7769c4440b6eec8ed4702afaa45ef0055e78c67959b310c0495` |
| scripts/campaign_variant.gd | `a97ab52f46c57a73dc579d786d02446c4786b3ba232cd5de89a41a9174eaacf3` |
| scripts/campaign_navigation.gd | `e91370300b3f9f16bc0074b9c1d9f99eee029a09e8167dcadf0bd97b7ddd7717` |
| tests/simulate_campaign.gd | `c28df0e6d1954baf916ae3076289ba432c562be5ff2bdd80ccd21d28ffaaf908` |
| scripts/campaign_rules.gd | `664e867f797744d3753af5bb726e39089e119c638070e91f602e4c9172e61e0b` |
| scripts/campaign_save_v2.gd | `4afc87f30b6d811413c4dd87ef25bdd5b4302f03018056ae6da8c96b19dcc49d` |
| scripts/purchase_guard.gd | `37f81040d17f4bbaef220ffa807d922d5653e57325821d674b333df4d9be9c55` |

## 玩家恢复文案的预算约束

world_art独立预算报告`output/early-purchase-budget-independent-review.json`绑定SHA `89c4034e43931ad56d0b8a20af52adb48277deec1d5a57ed2c769105f471d239`。本review核其1,336行预算分母与82个不足28金币的子集一致，并另读82条原raw byte/line SHA及JSON before/after预算：均为`defense_door_open/flask`、购买前24金币、入口16金币未捡、没有既往购买。

因此默认block只能保持原24金币，不能提示「立即买28金币edge」。文案已收紧为先核未取金币/合法路线，或使用已验证的完整checkpoint回档。≤40金币总宽松上界、flask后≤16/ward后≤12，以及无edge时ATK≤26<门卫DEF28，可支持局部门槛解释；仍不是每个完整prestate有赢路的引擎证明。恢复后从初始blade前缀实际买edge，与原拦截点是否立即可买是不同观察。

## 状态、资源与动作路径核对

- Helper的唯一`planner.state = core.duplicate(true)`用于新建、隔离的BaseRules规划副本，先经冻结validator验证；它不对active Campaign注入状态。实际收益、战斗、门、购物和楼梯均通过`Navigation.execute(actual_game, path)`调用真实API。
- Early实际初始化两份相同seed的Campaign，原动作逐步执行并比较完整快照。guard查询的counterfactual post快照还与实际shadow购买后快照比较；默认拦截分支不会偷偷接上原策略，只有fresh ticket + 明确true确认后才重新走原败局控制分支。
- Early取消坏拟购后实际购买edge，再从真实恢复状态完成blade；每事件对照资源、精确cleared集合、每店购买次数和seed绑定，不是重置几个预算字段。
- Late原始动作实际通过Campaign，从而由`_capture_chapter_entry()`生成checkpoint。恢复使用实际`restore_checkpoint()`，expected完整快照只按契约替换保留的两份历史列表及checkpoint前缀，整树比较，不删字段或赠资源。
- 每个late候选从原失败分支的独立clone恢复。作者后缀仅按实际已清ID/已买次数跳过相应事件，不可执行则unknown；不会为照合canonical账本强行补买、补钥匙或填数值。
- 初始checkpoint的完整blade独立实跑；晚期某候选获胜不会替代这项最低恢复证据。没有调用respawn或暗换seed，楼梯目标与当前变体数据一致。
- Helper校验冻结文件、原raw文件完整哈希、engine identity，以及具体locator的字节范围和line SHA。它是证据读取/隔离规划辅助，不是另一个战斗公式。

## 结论边界

本轮未发现activeGame状态注入、资源增发、库存暗补或换seed的具体路径。两项QA证据校验缺口在最新源码已收紧；最新early1,336和late26实际记录现均已独立核对。静态修复与新批次都不能改写旧smoke或原baseline。

初始镜像存在赢路、post-purchase unsat、当前policy失败和某个checkpoint赢路是不同结论。特别是guard post-unsat不单独证明购买造成失败；若要作该因果结论，还需同一购买前实际状态的赢路证人。

正式全量现已核对1,336个early精确index与每case实际winning=true，并与26个late精确集合闭合；候选入口的unknown仍保留，历史smoke／late-only报告的measurement_completed只代表各自范围。UI提示、浏览器输入、玩家恢复体验和人工时长仍未验收。新50层目标与D4运行时接入均未实现，21层这些结果只作为独立回归fixture，不能冒认50层成品或原版规则验证。
