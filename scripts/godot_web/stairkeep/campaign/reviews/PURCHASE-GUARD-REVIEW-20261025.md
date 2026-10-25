# Purchase guard 独立只读 review

范围：`scripts/purchase_guard.gd`、`tests/test_purchase_guard.gd`，并只读追踪正式 campaign snapshot/clone/buy/restore 与 solver receipt。已复核预算修复后的冻结源码。未执行 Godot，未改冻结五源、数据、模拟或被评代码。以下是静态审查，不代替根端完整 suite。

## 具体发现与修复确认

1. **[P1，源码修复已确认，运行待验] 完整测试用不存在的 offer 验证末段 known_winning。** 原 `_late_known_winning_query()` 的 approach 与 preview 均使用 `f19_shop/edge`。实际冻结数据中 `f19_shop` 是 `supply7`，只有 `flask`（48金币、180HP、限2次），所以完整 suite 会在此失败；`--cases-only` 会跳过而掩盖这项覆盖缺失。已向 root/game_rules 报告。后续只读确认两处均改成 `f19_shop/flask`，未改数据；blade此前买过一次，还剩一次可供真实 counterfactual 查询与取消。须跑默认完整 suite，不能用 cases-only 代替。

2. **[P2，源码修复已确认，运行待验] 原查询预算缺少实用上限和累计额度。** 原实现接受 2,000,000,000 毫秒/节点，pending ticket上限不能限制单次求解或 preview→cancel 循环。新源码已在调用solver之前拒绝超出每次 expanded5000、states20000、msec30000、navigation100000 的请求；导航0仍代表完整BFS，其他三个预算不能为0。默认值5000/20000/15000/0明确返回。每实例默认16次solver调用、累计实际solver wall time120000毫秒，constructor只能下缩；实际调用前计数，调用外包计时，effective msec钳到剩余额度。cancel、提交和修改公开stats均不退款或恢复额度，额度拒绝返回unknown且不发token。

   同步solver本身不可抢占：初始化或一次合作式步骤可越过本次effective时间。新代码明确保留实际超额时间，将当次known_winning/known_losing保守降为unknown，累计耗尽后拒绝后续查询；因此这是**每实例合作式额度**，不是硬实时抢占或全局调度器。该边界有源码说明，不能对外改写为「每次绝不超过30秒」。

后续源码确认的 SHA256：

| 文件 | 审查快照 |
|---|---|
| purchase_guard.gd（预算修复后） | `37f81040d17f4bbaef220ffa807d922d5653e57325821d674b333df4d9be9c55` |
| test_purchase_guard.gd（flask与预算测试修复后） | `cb65f3fae60fd850541c005cc29073c0c2c918462fccb69682a1190c0cd90519` |

前版审查快照为guard `c66e7c5c366220dad0625584779b61632f436859f8bb02cbb1adaf5f962488b3`、test `4677b2d5bc226b2d04ce26e6ec17c4fbb0d219e984f8db2d75667d32ab406be4`。本次只读确认修改限于新的guard预算层与其测试，未要求修改原经济或冻结源。

## 主路径核对

- **Exact binding：** 预览比较完整原始/克隆快照；拟购之后的 solver 初态必须等于拟购完整快照，receipt绑定state/content/variant/rules，报告还核对solver/navigation源与active data。求解后确认clone和原campaign均未被改；提交再次核对同一game instance、完整before snapshot及全部来源绑定。
- **默认 known_losing：** token先销毁；未确认分支在调用真实 `buy()` 前返回，原campaign完整快照不变。确认后才执行原购买，且不自动扣生命、标死亡或推进重生seed。
- **Unknown：** 不完整/不匹配的报告降为unknown，回复明确不提供安全保证；unknown提交沿原buy语义，不把有限查询当成可赢或必败证明。
- **One use / tamper / stale：** 公共票据多次deep-copy，不以客户端改写classification、offer或after_snapshot为授权；不接受字典冒充token；String token绑定guard私有pending表。commit/cancel/stale/default-block均消费token，移动产生的完整历史变化会使预览过期。Crypto token熵不消耗布局43次draw或重生序列。
- **恢复：** guard异常回滚尝试完整restore并回读比较，失败明确报告rollback_ok；没有按差额退款/补血/补钥匙。测试恢复完整entry checkpoint后对照经济、已清对象、库存和位置，再走原blade全程预算；历史失败保留，不把它当新增资源。
- **边界：** 测试报告明确为backend facade，21层UI尚未接入；不得据此声称真实购买提示、浏览器输入或用户恢复体验已验收。

## 需要保留的验收边界

现有测试源码包括公共视图篡改、非String伪token、跨guard token、默认block、确认已知败局、unknown提交、取消与消费、真实移动产生stale、checkpoint恢复，以及完整获胜后缀。新增预算测试包括2e9/超硬上限/非导航0在solver前被拒、constructor升限拒绝、缺省effective值、单query限额耗尽、公开嵌套stats篡改不续额，以及1毫秒累计额度在真实solver计时后拒绝下一次调用。尚未看到source-change、commit-mismatch回滚故障及伪造/缺失receipt字段的独立负向测试；它们不能被正常路径通过代替。

**实际运行状态：未跑最新完整guard suite。** 复核时根端4个headless模拟worker占满协调额度；最终默认完整guard实跑已排队，严格等空槽后由根端原授权路径执行。本文不把源码测试条目写成已实测通过，也不以`--cases-only`替代完整恢复/末段known_winning流程。

来源hash读取磁盘文件；本轮应坚持冻结源码并用新headless进程执行。尚未证明支持运行中热改脚本时「已加载bytecode和磁盘源码」的一致绑定，不能将该场景写成已覆盖。

## 随后的实际执行记录

以上「未跑」描述的是该次只读复核时的状态。根端在原模拟释放owned slot后，于2026-10-25 00:24 UTC使用新Godot 4.7.2 headless进程执行了最新完整suite：75项检查全部通过，四个生产前缀均默认拦截，显式接受后仍得到完整unsatisfiable；完整checkpoint恢复后真实通关21层，末段flask known_winning预览也通过，stderr为空。guard/test仍为上表修复后的两个hash。

这份后续记录来自根端实际运行与报告回读，不将先前静态审查改写为独立运行见证。完整结果见[实际报告](../evidence/purchase-guard.json.gz)。正常路径通过不补足上文未覆盖的故障注入或热改脚本场景，亦不证明26个随机晚期败局已逐个恢复。
