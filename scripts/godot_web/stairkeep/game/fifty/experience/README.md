# 首章体验修正：源码候选，尚未导出或发布

这轮只修改已交付 1–10 层的显示和输入反馈。原版首章 ZIP 保留；21–30 层工作继续暂停。当前 `http://127.0.0.1:18764/` 仍是原试玩包，不能把本目录当作已经更新的网页。

来源基线是 `../review/firstchapter-source.zip`，SHA256 `544ea650aeed6a57e206526aa5d0fda7df1ed69cd47e521de3715811c893ec42`。参考图仍为仓库 `docs/showcase/stairkeep/concept.jpg`，它是概念图，不是本候选的运行截图。

本轮实际源码修改：

- 地图仅在换层、换局或恢复旧状态时重建；普通移动保留角色和敌人动画相位。点击空地逐格走，点击物件先查看再明确交互，行动期间锁定重复输入。
- 使用原 Kenney 人物的 Idle / Run / Pickup 动作，开门使用同包 Open Door 图片，保留已开门框。购买匹配真实 `purchase` 动作，连续交互重新播放动作，动画不重复执行规则。
- 可走地面统一为暖色石砖；深色矮墙阻挡，柱子减少并避开互动目标。只有前景装饰柱靠近角色时淡出。角色脚下标记、楼梯中文目标、路径反馈与地图图例辅助读图。
- 对高处物件先按实际精灵位置拾取目标，再回退到地格，避免点击门或敌人上半身时选中后方格子。
- 显式附带完整 OFL Noto Sans SC，关闭系统字体回退。HUD、图鉴、楼梯、门、资源、商店、模式、恢复与错误反馈改用中文；价格、余货、距离、金币差额及实际购买前后变化可见。
- 复用已有 CC0 音乐，加入本任务原创简短信号音，提供静音及 20% 默认音量。首手势仅发起播放请求，不声称浏览器已经解锁声音。

`overlay/` 是覆盖到同一首章工程的文件，不是另一款游戏。193 个文件、10,758,907 字节的逐文件清单在 [manifest.json](manifest.json)。唯一覆盖的基线文件是 `fifty/view/preview.gd`；新增 3 个 helper、1 个 SpriteFrames 资源和 188 个素材/来源/诊断文件。规则、经济数据、D4、存档模块及其身份均保留原字节。

## 复现准备

从 `game` 目录运行，下列命令只准备文件；目标目录必须不存在：

```powershell
python -B fifty/experience/prepare.py --baseline fifty/review/firstchapter-source.zip --output <新的输出目录>
python -B fifty/tools/prepare_firstchapter_export.py prepare --project <新的输出目录>/project --templates <已有且已核验的4.7.2模板目录> --repo-license <仓库LICENSE> --output <新的导出准备目录>
```

第二步会包含新增 `assets/experience`、完整字体/动作/音频依赖和外部可读的字体 OFL、音乐 CC0 通知。它沿用既有 Compatibility / GDScript / 单线程 Web 导出流程，不下载软件，不写共享模板缓存，不启动引擎或服务器。

原 Godot console 的 `CreateProcess` 曾被 WinError 5 拒绝。此条件没有解除，本轮没有重试。正常授权恢复后，唯一下一阶段是由原 console 在这份隔离准备目录执行既有 export recipe 的版本、导入、导出；失败即停止，不能换 exe、路径、身份或浏览器通路绕过。

## 已做检查与验收缺口

实际文件准备已成功。静态检查覆盖 659 个码点／539 个汉字，缺字、UTF-8 解码错误和 U+FFFD 均为零；此结果不能证明导出字体已经加载或没有裁切。源级独立复核修正了不适用于 AnimatedSprite2D 的命中 API、购买动作码和连续拾取重播问题。

仍须验证：Godot 解析／导入／导出、真实首屏及原稿对照、移动与遮挡、F1→F2→F3 及返回、钥匙仅扣一次、拾取、购买／售罄／缺钱、战斗预览与实扣、模式与存档恢复、中文字号／重叠、Web 声音解锁与静音。所有画面、声音和真实输入项仍为未验。

UI 只使用项目 DCC-CUA；必须先取得 fresh provider/runtime/PID/HWND 绑定。历史输入拒绝未解除，不重试或换通路。新 Web 候选真正生成并通过有界检查后，交原 server owner 更新同一个 18764 URL，保留原包与存档并避免缓存混用。本目录没有发布、合并或部署授权扩张。

## 许可

原 Godot Isometric MIT 组件和 Kenney CC0 资产沿用原固定来源；新增动作和门帧为同一 CC0 包逐字节复制。字体为 Noto Sans SC / SIL OFL 1.1；音乐为 pauliuw《The Field Of Dreams》/ CC0。完整许可、来源和逐文件 SHA 随对应 `overlay/assets/experience/` 目录保留；没有复制权利保留的 Dawnkeep 代码或音效。
