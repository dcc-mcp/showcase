# Partial camera checkpoint / 未完成的镜头制作检查点

**Partial stage evidence, not a completed six-second film or final-quality approval.**
The delivered [native excerpt](crate-excerpt.mp4) contains only wide frames 1–50:
960×540, 24 fps, 2.083 seconds, intentionally silent. All 55 completed wide
frames are retained locally and hashed in [the checkpoint](checkpoint.json).
The planned 144-frame film was not completed. Repeated host exits with status
`-9` stopped production; their cause remains unestablished. Rendering retries
were ended. The existing historical artwork is retained unchanged.

**仅为真实阶段证据，不是六秒完成片，也未达到本轮高品质最终验收。**
交付片段只使用全景第 1–50 帧：960×540、24 fps、约 2.083 秒，有意静音。
已完成的 55 个全景帧均保留本地，并逐帧记录哈希。原计划 144 帧未完成；
宿主多次以 `-9` 退出，原因未确定，已停止渲染重试。现有历史作品保持不变。

## Source and rights / 来源与许可

- Original author / 原作者: Long Hao / loonghao
- Pinned source / 固定来源: [crate.blend at 38623dd](https://github.com/dcc-mcp/dcc-mcp-substance3d-designer/blob/38623dd51721a958b8dc5d2e8957e991908333ac/docs/showcase/crate-lookdev/crate.blend)
- Input bytes / 输入字节: 77,739,815
- SHA-256: 39f113b549bfea986d064be128a242f21b288775ccc0be81784c14c01e4e9716
- Preserved license / 保留许可: [upstream MIT](../LICENSE.source.txt)

New camera work, scripts and rendered derivatives retain the source attribution
and MIT notice. No additional artwork, audio, HDRI or add-on code is downloaded
for the new images. The historical generated reference is not used to synthesize
these frames. The old project ZIP remains the historical source archive, not a
complete download of this new camera attempt. New native files remain local;
the pinned input and replay recipe reconstruct the camera setup.

新镜头、脚本和渲染衍生物保留源作者与 MIT 声明。本次没有为新画面下载其他美术、
音频、HDRI 或扩展代码，没有使用历史生成参考图合成这些帧。旧 ZIP 仍是历史
源工程，不是本次新镜头尝试的完整下载。新工程保留本地，公开固定输入与镜头重放脚本。

## Measured environment / 实测环境

- Blender 4.5.14 LTS, build 62c1db4208e8
- dcc-mcp-blender 0.2.16; dcc-mcp-core 0.20.42
- Cycles CPU, 12 samples, OpenImageDenoise, render threads fixed at 2
- Task requested / accepted configuration: gpt-6-astra / ultra
- Historical host record: Blender 5.2.0 LTS, kept separately

Opening this particular scene does not establish general backward compatibility.
The model configuration is not independent backend identity attestation;
historical unknown attribution stays unknown. This pass did not remodel the
crate, rebuild Designer graphs or recompute SBS materials.

本工程成功打开不代表普遍向后兼容。模型配置记录不是独立后端身份鉴证，历史
未知归属不补填。本次没有重做木箱模型、Designer 图或 SBS 材质计算。

## What actually passed / 已完成的真实验证

- Both new shot scenes were saved and reopened through real MCP calls: 187
  objects, 179 meshes, 7 materials; six keyed values read back per animated rig/camera.
- A geometry-only GLB was exported and imported into an empty scene: 179 meshes,
  no exported materials or animation, with identical sampled bounds for two boards.
- The final public replay client was exercised against a dedicated real MCP host;
  saved/reopened camera matrices and render settings were compared with production.
  That smoke does not rerender the incomplete film.
- Every one of the delivered 50 frames was decoded; timestamps, dimensions, frame
  rate and source hashes were checked. This is technical acceptance of the excerpt,
  not approval of the unfinished full-film target.

- 通过真实 MCP 保存并重开两份新镜头工程：187 对象、179 网格、7 材质，每个动画
  相机或转台读回 6 个关键帧值。
- 实际导出仅几何 GLB 并导入空场景：179 网格，不导出材质或动画，两处木板包围盒
  采样一致。这不代表完整材质或所有几何的等价验证。
- 最终公开重放客户端在专用真实 MCP 宿主上执行，保存重开后比较相机矩阵与渲染
  设置；该测试不重渲未完成的影片。
- 交付片段的 50 帧均完整解码，核对时序、尺寸、帧率和源哈希；这是片段技术验收，
  不是未完成整片的最终品质验收。

See [native verification](native-verification.json), [minimal operation summary](mcp-operation-summary.json),
[excerpt verification](crate-excerpt.verification.json), and [stage review](visual-review.json).
详见以上原生验证、最小操作摘要、片段解码与阶段审阅记录。完整调用回执仅保留本地，不公开会话与宿主运行元数据。

## Reuse and replay / 复用与重放

[Official examples and free extensions](references.json) were evaluated before
production. Installed camera, objects, animation, render and scene skills were
sufficient; no new extension was installed. During production, the MCP Python
fallback only set resource options absent from typed tools. Replay acceptance
also samples camera matrices and detailed render state through MCP Python because
the typed keyframe summary does not return these values.

制作前核对了官方案例和免费扩展，已有相机、对象、动画、渲染与场景 skills 足够，
没有安装新扩展。制作时的 MCP Python fallback 只设置 typed 工具未提供的资源参数；
重放验收另用它读取 typed 关键帧摘要未提供的矩阵与详细渲染状态。

Use a dedicated Blender 4.5.14 MCP host with automatic scene scripts disabled.
Launch future renders with `OIDN_NUM_THREADS=2`. `MCP_URL` is the discovered
loopback endpoint, `SOURCE_BLEND` the verified input, and `CASE_DIR` a fresh output
directory. The client refuses an unexpected input hash and existing native outputs.
Opening the input replaces that dedicated host's current scene.

请使用禁用工程自动脚本的专用 Blender 4.5.14 MCP 宿主；后续渲染以
`OIDN_NUM_THREADS=2` 启动。`MCP_URL` 为该宿主发现的本机端点，`SOURCE_BLEND`
为核对过的源文件，`CASE_DIR` 为新输出目录。客户端拒绝未知输入哈希和覆盖已有
新工程。打开输入会替换该专用宿主当前场景。

```sh
python replay.py --mcp-url "$MCP_URL" --source "$SOURCE_BLEND" --output "$CASE_DIR" --confirm-dedicated-host
python replay.py --mcp-url "$MCP_URL" --source "$SOURCE_BLEND" --output "$CASE_DIR" --confirm-dedicated-host --shot wide --start 1 --end 5
```

The recipe defines the **uncompleted target**: wide frames 1–96 followed by detail
frames 1–48. The wide rig keys −16° at frame 1 and +28° at frame 97; the complete
planned wide sequence would cover about 44°. The delivered 50-frame excerpt covers
about 22.5°. Detail camera keys are at frames 1 and 49. All render batches are at
most five frames. Do not interpret the available recipe as proof those missing
frames were rendered.

脚本定义的是**未完成目标**：全景 1–96 帧后接近景 1–48 帧。全景转台第 1 帧
为 −16°，第 97 帧为 +28°，完整计划绕拍约 44°；实际交付的 50 帧片段覆盖约
22.5°。近景相机关键帧在第 1、49 帧。每批最多五帧；有重放脚本不代表缺失帧
已经被渲染。

Encode the exact partial delivery with FFmpeg and Pillow:
使用 FFmpeg 与 Pillow 编码本次实际部分交付：

```sh
python compose.py --wide-prefix 50 "$CASE_DIR/frames" "$CASE_DIR/crate-excerpt.mp4"
```

Without `--wide-prefix`, the encoder requires all 144 distinct native frames and
refuses an incomplete sequence. There is no frame interpolation, repeated still
hold, or padded duration. Wide frames 1–2 reuse actual qualification renders
byte-for-byte. Reproduction promises source, operations and settings, not identical
bytes across different software or hardware.

不带 `--wide-prefix` 时，编码器要求全部 144 个不同原生帧，缺失则拒绝编码。
没有插帧、重复静帧或补足时长。全景第 1–2 帧直接复用真实预检渲染的原字节。
复用指源文件、操作和设置，不承诺跨软硬件字节一致。

## Resource boundary / 资源与质量边界

The published excerpt uses frames 1–50, before the explicit OIDN thread override.
Only the additional local checkpoint frames 51–55 use that override. Same-frame
calibration differed by at most 2/255 per channel and was not pixel-identical.
Two earlier detail renders remain previews, not a completed detail sequence.
The 12-sample denoising softens fine grain. See [the interruption record](adapter-feedback.md):
no proven OOM cause or demonstrated memory reduction is claimed. The full-film
quality gate remains unmet, and this supplement is a Draft checkpoint.

公开片段使用显式 OIDN 线程限制之前的第 1–50 帧；只有额外本地检查点帧
51–55 使用该限制。同帧校准最大通道差 2/255，非逐像素一致。较早的两张近景
渲染只是预览，不是完整近景序列。12 样本去噪会柔化细木纹。退出原因和内存
改善均未被证明；整片品质门槛仍未达到，本补充仅是 Draft 检查点。
