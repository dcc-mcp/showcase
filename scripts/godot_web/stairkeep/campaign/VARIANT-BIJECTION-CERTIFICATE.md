# 初始镜像局的路径存在性证书

[`tools/audit_variant_bijections.py`](tools/audit_variant_bijections.py) 是只读的 Python 标准库审计器，不启动引擎，不模拟策略，不计算或复制战斗公式，不修改 canonical 数据、规则、模拟器、旧报告或 journal。它读取完成的 Godot 报告，验证其中每个初始布局与固定 canonical 关卡之间的结构对应，并以四条已经通过真实 Godot 规则回放的赢局记录为存在路径的前提。

证书表示：**在记录的 base-rule 语义与既有赢局证据前提下，所覆盖的每个初始镜像／出生点布局都有对应的赢局路径。** 它不表示所有玩家策略必胜，也不表示某个已经耗尽资源的续局仍可赢。它没有枚举全部 `2^32` 种 seed，没有验收实际 21 层 UI、浏览器、音频、存储或数小时玩家体验。

## 运行

从包含私有验收 `output/` 的工作区运行，或为每个输入传入明确路径。默认读取现有 `campaign-sim-100.json` 作校准及 100 局覆盖，读取 `campaign-witnesses-final.json` 作 canonical 赢局前提：

```text
python stairkeep-campaign/scripts/godot_web/stairkeep/campaign/tools/audit_variant_bijections.py --output output/campaign-bijections-100.json
```

完成的四份 2,500 局分片全部落盘后，使用同一脚本：

```text
python stairkeep-campaign/scripts/godot_web/stairkeep/campaign/tools/audit_variant_bijections.py --reports "output/campaign-shards/shard-*.json" --expected-runs 10000 --output output/campaign-bijections-10000.json --progress
```

`--reports` 的 glob 由脚本展开，不会读取 `*.json.journal.jsonl`、日志或未完成记录。每份输入必须 `measurement_completed=true`，其 requested/completed/实际记录数一致；跨报告索引不得重复。完整覆盖要求索引恰为 `--start-index` 起的 `--expected-runs` 个连续整数。缺少分片、缺索引、重复索引、输入哈希不同或布局哈希不符都不能出具通过证书。脚本不轮询、不把 journal 当正式报告、不把部分覆盖宣传成全覆盖。

`--output` 只创建新文件，拒绝覆盖已有文件；不传它则输出完整证书到 stdout。exit 0 为所请求范围通过，exit 1 为证据／覆盖失败，exit 2 为输出文件未能创建。失败记录仍明确包含错误，不能仅凭文件存在当作通过。

结构定义见 [`variant_bijection_certificate.schema.json`](tools/variant_bijection_certificate.schema.json)。Schema 约束结果形状；真假、来源真实性及字节对应仍须看实际审计和哈希，不能由 schema 替代。运行审计不需要安装 JSON Schema 包。

## 变换规范与检查

审计对应 `campaign_variant.gd` 的 `stairkeep-variant/xorshift32-hv-v1`：uint32 xorshift32 的每层两个 draw 决定 H/V，21 层共 42 draw；第 43 个 draw 模 4 选择首层安全出生点。零 seed 按版本规范归一为 `6d2b79f5`。局绝对索引的布局 seed 推导也与报告逐条比较，策略 RNG 不参与此几何变换。

每层的镜像码为 0=不镜像、1=H、2=V、3=HV。先穷举 **21×4=84 个局部变换**，验证整张矩形格子的双射／自逆、可走格集合、四邻格无向边集合以及全部对象非几何属性。随后每个报告 seed 均从其 43 draw 确定的局部变换组合成实际候选，并核对：

- 全部对象 ID、数量和非几何属性保持。敌人属性、资源数量、门颜色、商店价格与库存、胜利标记以及初始资源均守恒。
- 楼梯自身坐标按所在层镜像；**目标坐标按目的层的镜像**，不能误用来源层。全部 40 条有向链接仍落到正确返回梯并双向互指。
- 首层选中的安全空格到“镜像后的 canonical 出生点”存在明确空格路径。路径不碰任何对象、门、敌人或楼梯，因而不消耗资源、不触发事件。证书保存这条前缀，而不只写一个布尔值。
- 每条记录的 `canonical_hash`、`layout_draw_count`、`layout_seed_after`、`resolved_start` 和独立重建的 `layout_hash` 均与真实 Godot 报告对应。

局部变换的复用是有限结构证明的组成方式：每个 seed 的每层仍指定了具体镜像码，并核查该组合的对象、目标链接、出生前缀及完整布局哈希；没有把 84 个局部案例伪装成 10,000 次引擎重放。

### 既有赢局如何运输

审计先绑定 `campaign-witnesses-final.json` 的原始字节哈希、canonical 原始文件哈希、`base_rules.gd` 哈希及实际 witness replayer 哈希。四条记录必须都通过、最终 `won=true` 且达到 `f21_boss`，事件 ID 序列与 canonical 的四条 witness 完全一致，最终资源值也一致。

在记录的 base-rule 版本下，普通行走无资源损耗，邻接使用曼哈顿距离，战斗与经济只依赖守恒的数值／对象状态。先走空的出生前缀，再把 canonical witness 的每次移动向量按当前层 H/V 反射、保留对象和商购 ID、在楼梯处使用目的层坐标，对应资源／事件序列与胜利结果不变。这是有明确前提的路径运输论证，不是重新实现战斗系统，也不是声称 Python 再次执行了 Godot。

额外的 campaign wrapper、购买保护提示、失败确认或 UI 输入路径仍需各自正式引擎验收。本证书只从绑定的 base-rule 赢局论证逻辑路径存在，不能自动证明所有额外入口均已接通。

## 100 局校准记录

本次 `output/campaign-bijections-100.json` 已通过索引 0–99 的完整校准与覆盖：100 个独立 `layout_hash` 全部与实际 Godot 记录一致；检查 2,100 个楼层变换实例、41,000 个对象实例和 4,000 条楼梯链接。报告保留原模拟的 88 次胜利与 12 次 `dead_end`，没有改写失败策略或赋予补救资源。

冻结审计脚本 SHA-256：`3ee528195dffc38dd3f5a61e4a3f88e1920844fa454643efc99bf43c59f825fe`。证书自身也保存 `auditor_sha256`，后续复核以实际运行证书绑定的字节为准。

独立负例检查确认：篡改一条布局哈希、改错出生点、把 draw 数改成 42 都被拒绝。用 100 条记录要求 101 局时，`campaign-bijections-negative-coverage.json` 返回失败并明确缺少索引 100；这不是“覆盖 101 局”。

旧 100 报告的策略模拟器版本与当前模拟器不同，校准 manifest 如实记录 `simulator_matches_current=false`；canonical 数据、base rules、variant generator 与 navigation 四个相关来源均与当前字节匹配，100 个实际布局哈希也全部对齐。策略模拟器的旧 SHA 保留在输入 manifest 中，没有为匹配结果重写旧报告或修改序列化器。全 10,000 局证书须另读完成的正式分片，不能由 100 局校准推称已覆盖。

## 证书边界

- 既有 Godot receipt 的真实来源是证据前提；脚本检查绑定关系、事件与结果，不独立认证或重跑引擎。
- 结构与资源守恒支持“初始局存在一个赢路”。任意策略可花错资源；当前局是否还有赢路应由实际状态求解器分别处理。
- 仅枚举输入报告中的索引；H/V 的数学性质是一般事实，报告覆盖数量是另一个事实。
- `canonical_payload_sha256`、原始 JSON 文件 SHA 和 Godot `canonical_json` 内容哈希的覆盖字段／序列化不同。它们不能互相替代；脚本使用报告对应的那一种比较。
- 没有 21 层实际画面、人工玩法时长、浏览器或设备验收结论。
