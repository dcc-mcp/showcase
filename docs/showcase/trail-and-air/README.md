# Trail & Air · 原创步行音频素材

17 个通用音频资源，由 typed DCC-MCP 生成原创确定性声源，再经真实 REAPER 7.82 建立原生项目、逐资源渲染、保存和重开。所有下载 WAV 为48kHz/24-bit PCM，无第三方采样、录音或乐器库。

## 在线试听与下载

[28.6秒试听MP3](Trail-and-Air-audition.mp3)：六个石面脚步、六个草地脚步、8秒环境、8秒音乐、三个交互SFX。网页使用原生音频控件，需要用户点击，不自动播放。试听中两个循环片段用了短淡入淡出；无损交付循环没有改变。

将四个ZIP解压到同一目录，会合并成一个完整的 `Trail-and-Air-UE-Audio` 文件夹：

- [脚步与SFX](Trail-and-Air-OneShots.zip)：12个mono脚步、3个mono交互音效。
- [环境循环](Trail-and-Air-Ambience.zip)：20秒stereo轻微风与叶片质感。
- [轻音乐循环](Trail-and-Air-Music.zip)：19.2秒stereo稀疏调性背景，100BPM / 8bars。
- [原生工程与源码](Trail-and-Air-Source.zip)：原生RPP、合成器代码、typed技能、测试、验证和许可证。先解压音频，再打开根目录的 `Trail-and-Air.rpp`。

[逐文件规格与增益建议](audio-manifest.json)包含帧数、声道、循环起止、随机音高/增益建议、表面类型、峰值/RMS与SHA256。建议游戏增益只是起点，不是已经完成的游戏内混音。

## 实际工具链

- REAPER7.82 Linux x86_64 evaluation，按厂商Linux说明构建NOGDK=1 libSwell；运行的仍是真实宿主。
- dcc-mcp-core0.20.41；CLI/server0.20.42；reapy_boost0.10.201；Python3.12.14。
- [适配器修复PR#3](https://github.com/dcc-mcp/dcc-mcp-reaper/pull/3)，实际commit `867ce6837c916aa7ca89a5cb14deae9869f09d00`。
- `reaper_game_audio__generate_pack`：附加typed技能，在外部适配器进程中做数学合成，并用官方ReaScript API进入真正REAPER项目。
- `reaper_game_audio__render_assets`：逐区域原生离线渲染、格式/帧数检查、部分失败检查记录与禁止覆盖。
- `reaper_stem_session__open_project` / `audit_session`：真实重开与依赖审计。内置适配器仍是只读，不能把附加制作能力算成其原有功能。

正式调用走 inventory → scoped search → load-skill → describe → call，并要求经过Gateway。路径脱敏的[调用记录](mcp-evidence.public.json)保留实际响应；未发布原始机器路径。

## 验证

17 个原生导出全部与原始合成PCM逐样本一致：准确保持mono/stereo、帧数和循环边界。最终加固后再次生成、渲染、重开，全部通过；64项制作技能测试通过。适配器146项host-free测试和精确head的CI通过，另有真实宿主验证。

原生工程已调整到相对 `Audio/` 路径，并再次在真实REAPER中重开保存，17个依赖均可读。交付WAV仅去除BWF/encoder元数据，PCM不变。[信号检查](native-signal-checks.json)和[验证范围](validation.json)明确记录边界。

## 许可与边界

本案例原创音频CC0-1.0，代码MIT；只适用于本案例原创资源，不改变其他案例许可。没有分发REAPER、其他应用二进制、账号或密钥。REAPER是付费软件，60天evaluation不是长期免费，开源或非商业用途不免除其许可。

使用者已确认方向并授权发布。没有记录主观听评，不以零clipping冒充听觉验收。原生项目、代码、素材已公开，但不包含任何游戏项目、场景、图片、录像或其名称。没有宣称Unreal内触发、空间化、衰减、步行动画或完整链路已经验证。下载包是在授权发布前形成的技术快照，其中旧的“待试听/草稿”标记不构成已完成听评的声明。

## Related native MIDI film scores

The same real REAPER/DCC-MCP pipeline now produces individually timed music for [Crystal Freight](https://dcc-mcp.github.io/showcase/cases/crystal-freight-native-film/), [Brass Relay](https://dcc-mcp.github.io/showcase/cases/brass-relay/) and [Orbit Post Office](https://dcc-mcp.github.io/showcase/cases/orbit-post-office/). Each retains the original silent film, adds a separate scored version and offers an editable MIDI/ReaSynth project with source audio and scoped licenses.
