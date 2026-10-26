# Showcase 提交规范

本文件是本仓库的提交指南。先读 [AGENTS.md](AGENTS.md)、[制作 Skill](skills/dcc-showcase-production/SKILL.md)、[案例契约](docs/showcase/CONTRACT.md) 和[双语规则](docs/LOCALIZATION.md)。沿用已有格式，不另建发布系统。

## 1. 开始制作前记录身份与版本

记录实际使用的模型、宿主、适配器、Core、渲染器与后期工具。版本来自实际运行环境的读取结果，不来自仓库最新版、安装目录名或记忆。多软件制作逐个记录，制作与后续审阅分别记录。

| 必填项 | 填写要求 |
| --- | --- |
| 模型 | 实际接受的任务配置中的完整模型 ID；不能只写 Codex、ChatGPT、Agent 或“最新模型” |
| 推理强度 | 实际配置值，独立于模型名称记录；不得猜测 |
| 宿主 | 产品全名和实际版本/build，例如 `Blender 4.5.13 LTS`、`Autodesk Maya 2025`、`Autodesk 3ds Max 2024.2.14` |
| DCC-MCP 适配器 | 完整包名和实际版本，例如 `dcc-mcp-blender 0.2.22`；只写 `Adapter 0.2.22` 不合规范 |
| Core / Server / CLI | 分别写完整名称和实际版本，例如 `dcc-mcp-core 0.20.46`；不同组件不得共用一个未经核实的版本 |
| 渲染与后期 | 实际产品、版本、关键参数、种子和色彩转换；例如 Cycles、Arnold/Noice、dcc-media-enhance 的实际版本 |
| 源码候选 | 包版本、完整 commit SHA、未发布/未合并状态；不得把候选称作已安装的正式发行版 |

`Maya 2025` 是宿主版本，`dcc-mcp-maya` 的包版本必须另行读取。`dcc-mcp-blender` 与 `dcc-mcp-maya` 也不能统称为同一个“DCC-MCP 版本”。

将版本写入 `collection.json` 的 `environment` 行，网页与 Agent/Data 会展示这些行。下面仅演示已有案例的格式，**不能复制成另一个案例的事实**：

```json
"environment": [
  {"label": "Blender", "value": "Blender 4.5.13 LTS · Cycles CPU"},
  {"label": "Adapter / 适配器", "value": "dcc-mcp-blender 0.2.22"},
  {"label": "Core / 核心", "value": "dcc-mcp-core 0.20.46"},
  {"label": "Server", "value": "Unknown — retained production records do not record the server version"}
]
```

保留可核对的原始读取结果，在公开记录中使用脱敏的依据和哈希。可选的 `production-evidence.json.environment` 已有 `role/component/version/evidence` 格式；需要结构化证据时复用它，不再维护另一套版本清单。

## 2. 模型归属必须分阶段

使用既有 `model_attribution`，必填字段为 `stage_id`、`stage`、`model`、`reasoning_effort`、`record_status`、`basis`、`scope`。

- 必须覆盖 `planning`、`creation`、`code`、`reference`、`post_production`，以及至少一个 `review` / `review_visual` / `review_technical`。
- 核对过实际接受的配置记录，才可使用 `configured` 并填写真实模型 ID、推理强度及依据。配置身份不等于后端模型身份认证。
- 历史记录缺失时，使用 `unknown`，且模型、推理强度均填 `Unknown`，在 `basis` 写明缺失原因。只知道部分信息时，在依据中保留已知部分，不能编造另一部分。
- 当前审阅者的模型不能回填历史制作模型；没有模型调用的阶段也不能虚构一次调用。后续补作使用已有 `supplement_*` 阶段，保留原记录。
- 不提交私有任务 ID、原始敏感提示词、账户、密钥、内部路径或未脱敏日志。

## 3. 案例材料与验收范围

每个 `docs/showcase/<slug>/` 至少包含 `README.md`、`manifest.json`、`validation.json`。报告需说明目标、输入/可复用提示、实际工具、制作步骤、成果、环境、权利、复现方式和限制。

保留真实主图、影片及原生界面证据，逐项记录是否实际执行过：MCP 调用、原生保存重开、导出回导、配方重建、画面审阅、实际播放、交互、双语页面和隐私检查。技术解码通过不能代替视觉或播放验收。失败、未测、阻塞分别记录，不因上架而改成通过。

校验记录用 `not_run` 表示未执行，并在 `observed` 写明原因；不能把延期或未执行写成 `fail`。实际失败保留 `expected` 和 `observed`。不同证据格式沿用各自的状态规范，不批量改写历史结果。

未完成的案例可以按用户授权的有限范围展示，但标题、摘要、检查和限制必须显著说明状态，例如“制作实录，视觉待改进”。这种收录不表示作品已经全面验收。

原生工程必须先做公开副本的依赖、隐私和权利检查，再保存重开。未清理的工程和私有日志继续留在公开库存之外。UI 操作遵循项目 DCC-CUA 路由及实际目标绑定；截图不得合成或涂改，裁剪需声明。

`manifest.json` 必须覆盖实际公开文件的最终字节、大小和 SHA-256；修改报告或媒体后重算。保留原始文件与历史失败，不用新产出冒充旧记录。

## 4. 每个案例必须明确是否进入首页

合并证据目录不会自动创建首页卡片。完整案例必须且只能选择一种状态：

1. **进入首页**：在 `collection.json.cases` 增加同一 slug 的完整记录，填写实际模型/软件版本、封面、成果、检查、限制、资源和来源。补齐 `locales/en/cases/<slug>.json`；英文源文案还须按双语规则补中文翻译。
2. **暂不展示**：在根目录 `unlisted-cases.json` 登记 slug、`review` 或 `unlisted` 状态，以及具体原因。不要把暂不展示写成已上线。

构建会拒绝没有收录决定、两处重复登记、已失效的暂不展示记录和不安全路径，并列出明确暂不展示的案例及原因。不能通过自动扫描并发布所有目录来解决遗漏；私有或未选择的文件仍不得进入站点。

首页收录不需要新增 slug 来保存同一作品的修订。用 `revision_notes` 写实际日期、版本和变更，并更新文件哈希。

## 5. 提交前运行仓库检查

使用 Python 3.12，在仓库根目录执行：

```sh
python scripts/validate_entry.py docs/showcase/<slug>
python scripts/test_publication_intent.py
python scripts/publication_intent.py
python scripts/test_validate_collection.py
python scripts/validate_collection.py
python scripts/test_localization.py
python scripts/test_playable.py
python scripts/test_build_site.py
python scripts/godot_web/materialize_runtime.py
python scripts/build_site.py
```

按变更运行相关媒体、Agent/Data 与交互检查。检查生成站点的首页、英文和中文详情页、封面、影片、资源链接及版本/模型信息；不要只检查证据目录存在。实际浏览器播放和输入须保留单独证据，未运行则如实记录。

## 6. PR、合并与上线回读

- 同一案例复用已有分支/PR；使用简洁英文 Conventional Commit，提交者为 `loonghao <hal.long@outlook.com>`。
- PR 写明“进入首页”或“仅归档”，列出 slug、英中 URL、版本/模型记录依据、验证范围与未完成项。
- 核对当前 head 的检查和评审，按用户授权合并。PR 检查通过、合并、Pages 部署成功、线上展示是分别验证的步骤。
- 部署后读取实际首页和两种语言详情页，确认卡片、资源及展示数据都存在；报告实际 URL、部署 commit 与仍未验证的部分。部署失败或案例不可见时，不能宣称已上线。

提交完成的最低交接信息：**案例 slug、收录决定、完整模型记录、具体宿主/适配器/组件版本、实际检查结果、PR/commit、部署状态、英中页面地址和剩余限制**。
