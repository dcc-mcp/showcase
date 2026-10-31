# 首章体验07：地图可读性与商店入口候选，尚未运行验收或发布

这轮延续体验06的中文、动作、声音、输入和网页完整快照存档候选，补充持续的可走地块轮廓，并把商店“前往”和“购买”入口分开写清。原版首章 ZIP、已交付体验01源码包保留；21–30 层工作继续暂停。当前 `http://127.0.0.1:18764/` 仍是原试玩包，不能把本目录当作已经更新的网页。

体验07只改表现层：每个可走格在等距地面上有低对比度菱形边线，深色石墙仍是阻挡体；选中物件时右侧卡、地图路线亮框和底部动作提示共同说明“走哪几格、到达后做什么”。地图图例列出可走地面、墙、楼梯、门、资源和可交互标记。商店卡明确说明 E / 空格只负责前往，商品必须使用对应的独立购买按钮；价格、金币差额、余货和结果提示沿用体验06。新增的静态可读性合同见 [tests/test_readability_contract.py](tests/test_readability_contract.py)。

原稿定位、投影根因、代表F1差异见 [INPUT-AND-F1-REVIEW.md](INPUT-AND-F1-REVIEW.md)。键盘规则见 [KEYBOARD-03.md](KEYBOARD-03.md)，体验04异步焦点修正及真实验收序列见 [FOCUS-04.md](FOCUS-04.md)，历史检查见 [validation-focus-04.json](validation-focus-04.json)。[validation-keyboard-03.json](validation-keyboard-03.json)、[validation-input-f1-02.json](validation-input-f1-02.json) 与 [validation.json](validation.json) 保留体验03／02／01历史检查；这些记录均不覆盖体验05或06。

本轮变更的静态范围、候选哈希和 Hyper3D 未使用原因见 [validation-readability-07.json](validation-readability-07.json)。

体验03实际替换体验02的延迟物理键回读：真实按键进入单意图控制器，持键有界续步，转角保留最新一步，锁定方向后不逐格弹歧义。Esc／GUI和窗口失焦／手动交互清空后续移动。门、战斗和道具先预览，再用新的确认操作执行。70ms只收集初始组合，首次续步240ms、后续180ms，忙碌不补发。同一帧至多一步，规则调用与行动经济不变。实际键盘手感仍未验证。

体验02的F1连续矮墙、门廊、1.6倍近看／整层总览保留；门和楼梯朝向按运行时邻格计算，恢复淡出重建，转角保留Run帧相位。

体验04修正每次动画结束无条件清GUI焦点的问题。仅发起动作的同一有效按钮可以自动归还；路径期间新取得的图鉴／Tab焦点保留，后续路径格也不会把它误当发起按钮。生产控制器本体及玩法规则没有变化。

体验05（`recovery-05`）恢复接续时，首章原存档模块主动阻断 Web 持久化，该版本没有 Web 持久写入与完成回执流程。因此体验05禁用网页的存档／读档按钮，说明刷新或关闭会丢失进度；原生存档行为不变。该版本还修复了方向按钮仅预览物件后归还原按钮焦点的问题，并保留新取得的图鉴／标签焦点。体验06替代其中的 Web 禁用状态；方向按钮修复继续保留。下面各历史 ZIP 与 validation 不覆盖体验05或06。

体验06（`web-save-06`）新增 `web_saves.gd` 与 `indexeddb_source.gd`。网页使用新命名的 IndexedDB 数据库，保存原 `FiftySave.encode_slot` 生成的 v1 完整快照；读取与覆盖前仍调用原 `decode_slot`，不改原生存档模块、版本、规则指纹或关卡数据。写入比较已读取的旧原文，在同一读写事务中拒绝并发覆盖；只有事务提交后重新读取相同原文才显示“已保存”。事务中止、配额不足、访问失败及超时均返回失败；提交是否完成不明确时明确提示“不确定”，不声称旧档未变。操作期间暂停游戏动作，加载先在独立 runtime 校验和导入，成功后才替换当前塔。

兼容迁移只处理原 `user://stairkeep-fifty-save-v1/slots/<mode>/<slot>.json` 中通过当前完整校验的 v1 槽位：新数据库没有该槽位时进行 add-only 复制，原文件和 `.pending` 文件均不删除或改写；有 pending、损坏、未来版本或身份不匹配时拒绝迁移。旧三层、第二／第三章存档根不会被探测。原生槽位与源文件不迁移、不改写。浏览器存档限同一 origin／浏览器配置；浏览器清理站点数据及设备断电不在此次保证范围。

后端依据 [Godot JavaScriptBridge 回调约定](https://docs.godotengine.org/en/stable/classes/class_javascriptbridge.html) 和 [IndexedDB transaction complete](https://developer.mozilla.org/en-US/docs/Web/API/IDBTransaction/complete_event) 实现。没有使用无结果回执的 `force_fs_sync()` 作为保存成功依据。纯逻辑回归可从仓库根运行 `node scripts/godot_web/stairkeep/game/fifty/experience/tests/test_indexeddb_storage.cjs`；它直接提取并执行生产 JS 常量，使用内存事务夹具，**不是实际 IndexedDB、浏览器或 Godot 运行**。Godot 解析、JavaScriptBridge 回调时序、导出、真实页面保存／刷新／重新打开恢复仍未验证。

来源基线是 `../review/firstchapter-source.zip`，SHA256 `544ea650aeed6a57e206526aa5d0fda7df1ed69cd47e521de3715811c893ec42`。参考图仍为仓库 `docs/showcase/stairkeep/concept.jpg`，它是概念图，不是本候选的运行截图。

延续的体验01—04源码修改：

- 地图仅在换层、换局或恢复旧状态时重建；普通移动保留角色和敌人动画相位。点击空地逐格走，点击物件先查看再明确交互；键盘动画期间只保留一个最新意图。
- 使用原 Kenney 人物的 Idle / Run / Pickup 动作，开门使用同包 Open Door 图片，保留已开门框。购买匹配真实 `purchase` 动作，连续交互重新播放动作，动画不重复执行规则。
- 可走地面统一为暖色石砖；深色矮墙阻挡，柱子减少并避开互动目标。只有前景装饰柱靠近角色时淡出。角色脚下标记、楼梯中文目标、路径反馈与地图图例辅助读图。
- 对高处物件先按实际精灵位置拾取目标，再回退到地格，避免点击门或敌人上半身时选中后方格子。
- 显式附带完整 OFL Noto Sans SC，关闭系统字体回退。HUD、图鉴、楼梯、门、资源、商店、模式、恢复与错误反馈改用中文；价格、余货、距离、金币差额及实际购买前后变化可见。
- 复用已有 CC0 音乐，加入本任务原创简短信号音，提供静音及 20% 默认音量。首手势仅发起播放请求，不声称浏览器已经解锁声音。

`overlay/` 是覆盖到同一首章工程的文件，不是另一款游戏。逐字节清单在 [manifest.json](manifest.json)。唯一覆盖的基线文件是 `fifty/view/preview.gd`；规则、经济数据、D4、存档模块及其身份均保留原字节。本目录的 `.gdignore` 防止原工程将待应用的源码副本误导入；准备后的独立工程在正常资源路径加载这轮文件，仍须单独做引擎与实际输入验收。

## 复现准备

从 `game` 目录运行，下列命令只准备文件；目标目录必须不存在：

```powershell
python -B fifty/experience/prepare.py --baseline fifty/review/firstchapter-source.zip --output <新的输出目录>
python -B fifty/tools/prepare_firstchapter_export.py prepare --project <新的输出目录>/project --templates <已有且已核验的4.7.2模板目录> --repo-license <仓库LICENSE> --output <新的导出准备目录>
```

第二步会包含新增 `assets/experience`、完整字体/动作/音频依赖和外部可读的字体 OFL、音乐 CC0 通知。它沿用既有 Compatibility / GDScript / 单线程 Web 导出流程，不下载软件，不写共享模板缓存，不启动引擎或服务器。

原 Godot console 的 `CreateProcess` 曾被 WinError 5 拒绝。此条件没有解除，本轮没有重试。正常授权恢复后，唯一下一阶段是由原 console 在这份隔离准备目录执行既有 export recipe 的版本、导入、导出；失败即停止，不能换 exe、路径、身份或浏览器通路绕过。

## 已做检查与验收缺口

体验06当前来源与检查见 [validation-web-save-06.json](validation-web-save-06.json)。新增28项 Node 事务合同回归通过，原41项输入策略参考与14项静态接线检查通过；207项覆盖文件、65个保留基线文件和显式资源引用已核对。测试只覆盖注明的源码／夹具范围，真实 IndexedDB 和刷新恢复仍为 blocked。

体验04历史源码ZIP、静态接线和字体覆盖结果以 `validation-focus-04.json` 为准；生产GDScript控制器探针和432项真实TileMap几何探针仍只已准备，均未执行。这不能证明体验06的引擎解析、键盘手感、导出字体加载或没有裁切。

体验04源码ZIP为13,163,761B，SHA256 `a308e09df740d73db7646f3b5bc382f552810086ca9b8bbcef841ac20103d82a`。205项overlay、65个保留基线文件、207处静态资源引用通过；字体覆盖671码点／552汉字且缺字为零。41项Python参考和14项静态接线检查通过，均不计为生产GDScript或真实窗口通过。

冻结体验03源码ZIP仍为13,163,694B，SHA256 `b39cf8288a0e55d73a8273aa6320517a04c86a38a239ce9fe63ee30fdde37110`。其205个overlay文件、65个基线文件守恒、207处静态资源引用、671码点／552汉字覆盖、41项Python参考与13项静态接线结果只归属于该版本。

冻结体验02 source ZIP仍为13,159,715B，SHA256 `283d4e97cf3e1bb1a434ee3506640a070bd2bcc9e01fca62286f7daa1cef4b99`，保留为修复前证据。

体验01源码包仍为12,943,025B、SHA256 `5153ae00a454535a362f606b5fc5ed34c44bd2ae791cb3d2ea72a4e2a94efc16`，Library身份保持不变；本轮没有重复上传它。各轮均没有新的可试玩Web包。

仍须验证：Godot 解析／导入／导出、真实首屏及原稿对照、移动与遮挡、F1→F2→F3 及返回、钥匙仅扣一次、拾取、购买／售罄／缺钱、战斗预览与实扣、模式与存档恢复、中文字号／重叠、Web 声音解锁与静音。所有画面、声音和真实输入项仍为未验。

UI只使用项目DCC-CUA；必须先取得fresh provider/runtime/PID/HWND绑定。历史输入拒绝未解除，不重试或换通路。用户已授权真实新版准备好后由原server owner直接更新同一个18764 URL，不再另发链接等待确认；此前必须备份旧包、保留存档/回滚，并核新哈希、完整资源及缓存行为。当前未达到此门禁，不能覆盖旧试玩；没有合并或公网发布。

## 许可

原 Godot Isometric MIT 组件和 Kenney CC0 资产沿用原固定来源；新增动作和门帧为同一 CC0 包逐字节复制。字体为 Noto Sans SC / SIL OFL 1.1；音乐为 pauliuw《The Field Of Dreams》/ CC0。完整许可、来源和逐文件 SHA 随对应 `overlay/assets/experience/` 目录保留；没有复制权利保留的 Dawnkeep 代码或音效。
