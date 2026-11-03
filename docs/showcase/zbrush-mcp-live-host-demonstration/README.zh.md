# ZBrush 2027 实机演示

本案例**不是**生成的图片、能力清单，也不是「加载了 MCP 技能」的记录。它是一份可机读的
证据账本，记录了一次真实的 ZBrush 2027.0.1 GUI 会话：`dcc-mcp-zbrush` 在真实场景里
真正做了事，并返回了真实工具调用的返回值。

## 实际发生了什么

从干净的进程状态启动一个已签名的 `ZBrush.exe`（ProductVersion `2027, 0, 1, 1`，
Authenticode `Valid`）。一次性用户资源目录通过 ZBrush 启动钩子，在宿主主线程加载了未经
修改的 socket bridge；随后启动连接到该实机 bridge 的 sidecar MCP 服务。整个运行覆盖三层，
最后优雅退出，未残留 ZBrush 进程，也未残留监听端口。

| 层 | 通道 | 真实调用 | 证明内容 |
| --- | --- | --- | --- |
| 0 | 宿主内直接调用 | 5 次 | 真实 `zbrush.commands` SDK 返回值，以及一次真实可逆状态改写 |
| 1 | socket bridge 上的 JSON-RPC | 10 次 | 主线程泵派发真实 SDK 处理器：导入、细分、测量、导出 |
| 2 | `/mcp` 上的 MCP `initialize` / `tools/list` / `tools/call` | 7 次 | 绑定到实机宿主的真实 MCP 服务返回真实工具结果 |

### 第 0 层：真实宿主 VM 内部

`get_session_info`、`get_scene_info`、`list_subtools` 返回真实宿主状态；宿主报告
`zbrush_info(0) = 2027.0009765625`、`zbrush_info(1) = 2`、内嵌 Python `3.11.9`、
149 个公开的 `zbrush.commands` 可调用对象。一次真实 `execute_python` 对
`Draw:DrawSize` 做了读 / 改 / 读 / 还原：`64.0` → `64.05000305175781` → `64.0`，
`changed = true`、`reversible = true`。

`inspect_active_mesh` **如实失败**：
`ValueError: Unable to begin a Script tool editing-session.`。会话默认停在
`SimpleBrush`，不是 `Polymesh3D`，`query_mesh3d` 合理拒绝。该失败被保留，没有隐藏。

### 第 1 层：在真实网格上真正做事

用 `import_to_scene` 导入一个真实四边形立方体（`live_input_cube.obj`，8 顶点 / 6 面）。
随后 `inspect_active_mesh` 返回 8 点、6 面、面积 `24.0`。`refine_active_subtool`
执行了一次真实细分（`subdivision_levels = 1`），下一次 `inspect_active_mesh`
返回 26 点、24 面、面积 `11.936315536499023`。`export_active_subtool_obj` 把改写后的
网格写出为 `live_exported.obj`（26 顶点 / 24 个四边形面）。两个 OBJ 文件都随案例发布，
并附带 SHA-256。

### 第 2 层：真实 MCP 工具返回值

sidecar 回答了真实 MCP `initialize`（`dcc-mcp-zbrush` `0.2.32`，协议
`2025-06-18`）与 `tools/list`（首页 32 个工具，`nextCursor` `3332`）。三次真实
`tools/call` 成功：`list_skills` 返回运行中的技能目录；`load_skill` 注册了
`zbrush_dialog__get_active_dialog` 与 `zbrush_dialog__click_dialog_button`；
`zbrush_dialog__get_active_dialog` 返回 `success: true`、`bridge_state: ready`、
`zbrush_blocked: false` —— 这是一条真实到达实机宿主 bridge 的 MCP 工具返回值。

另外四次 `tools/call` 返回真实的 `isError: true`：`THREAD_AFFINITY_UNAVAILABLE`。
`get_session_info`、`get_scene_info`、`list_subtools`、`execute_python` 声明
`thread_affinity=main`，但 sidecar 模式下 `dcc-mcp-core` 未挂载 `DeferredExecutor`
（`attach_dispatcher` 是空操作，`host_dispatcher_attached=False`），Rust 派发器因此拒绝。
**这是真实、可复现的产品限制，不是演示失败。** 同样的工具在第 1 层的 socket bridge
通道里确实完成了真实工作。修复属于 core sidecar 派发器设计，不在本 showcase 范围内。

## 明确不主张的内容

- 不主张任何视口截图、渲染、转盘或视频。采集了一份不含像素的 GUI 窗口诊断，但结果为
  `proof_passed: false`（`root_overlap`），因此不主张任何宿主媒体。发布的 OBJ 是真实几何，
  不是图片。
- 不主张四个 `affinity: main` 工具在 sidecar 模式下能通过 MCP HTTP 工作。
- 不主张入选画廊、合并、部署或线上页面回读。本案例在同一个 Draft PR 的
  `unlisted-cases.json` 中登记为未列出的 review 案例。
- 不主张独立精确 head 审核、CI 门禁或发布授权已完成。
- 不含私有路径、机器名、回环地址、任务号或凭据。发布账本是私有原始采集的脱敏派生。

## 复现验证

`verify_live_host_evidence.py` 在不重跑 ZBrush 的前提下，复核发布的账本与两个 OBJ
产物：宿主身份、可逆改写、几何变化、产物哈希与几何、MCP 返回计数、已记录的 affinity
限制、生命周期清理以及私有数据扫描。结果写入 `live_host_evidence_result.json`。

```
python verify_live_host_evidence.py
python scripts/validate_entry.py docs/showcase/zbrush-mcp-live-host-demonstration
```

验证器检查的是**已记录的证据**，不重放宿主会话。重跑实机会话需要真实 ZBrush 安装、
一次性用户资源目录以及可运行 GUI 的宿主。

## 环境

| 项 | 值 |
| --- | --- |
| 宿主 | ZBrush 2027.0.1（`2027, 0, 1, 1`） |
| 宿主 Python | 3.11.9（内嵌） |
| Adapter | `dcc-mcp-zbrush` 0.2.32 |
| Core | `dcc-mcp-core` 0.20.52 |
| Sidecar | gateway 端口 0，MCP 与 bridge 分别在回环端口 |
| 验证级别 | `real_host_tool_returns_recorded_and_self_consistency_verified` |
