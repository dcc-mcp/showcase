# Desert Relay: bounded production recipe / 有界制作方案

Status: preproduction only. The native portion has not run.
状态：仅预制，原生制作尚未执行。

## Shot / 镜头

Keep the NPS Racetrack excerpt from 13 to 21 seconds at its original 30 fps.
The dry lake, mountain silhouette and real ground texture remain the visual
anchor. A distant, eroded observatory ring rises near the horizon; a small
bronze sword embedded in the foreground leads the eye toward it. The sky stays
restrained, with pale cirrus. Use a quiet opening hold, a slight warm glint and
atmospheric drift in the middle, then a settled ending. Intentional silence.
This is an original proposed composition, not an existing successful render.

保留 NPS Racetrack 的 13–21 秒原速段，以真实干湖、山脊与地面纹理为视觉基底。
远处加入风蚀圆环天文遗迹，前景半埋铜剑引导视线；天空保持淡色薄云。
镜头前段安静，中段仅有轻微暖色反光与空气层变化，末段回稳，计划静音。
这是待执行的原创构图方案，不是已经完成的渲染。

## Before native production / 原生制作前

1. Obtain a new, task-owned Nuke 16.1v2 session and a valid entitlement covering
   this promotional/public output. Standard Nuke is sufficient for the proposed
   Read/Roto/Transform/Grade/Merge workflow; NukeX-only camera solving is not
   required by this plan. This is a requirement, not a measured license claim.
2. Obtain a separate, task-owned Blender session. Check actual version and
   compatibility before the prepared script executes. No installation or
   shared-runtime mutation is part of this recipe.
3. Read the live Core production-reuse contract and discover actual Nuke/Blender
   tools, schemas, adapter versions and application identity. The canonical
   Core source was read during planning; the deployed gateway build is unknown.
4. Preserve sanitized request/response values and actual file hashes. An
   execution return containing a backend failure remains a failure.

执行前需独占且有效许可的 Nuke 16.1v2、新的独占 Blender 会话，并验证版本、
动态工具 schema 与真实实例身份。不使用旧回归实例、不安装或修改共享 runtime。
当前只核过 Core 官方源契约，尚无部署 gateway 的生产能力证明。

## Plate and camera / 实拍与机位

The included plate is 1280×720, BT.709, 30 fps, 240 decoded frames. It was
re-encoded at H.264 CRF16; the original source remains separately hashed.
An offline ground-feature similarity fit measured a maximum 0.7394 px
translation and 0.01025° rotation. This supports a locked-camera first test;
it is not a native Nuke tracking pass or a 3D camera solve.

The native test must inspect first, middle and last frame plus any suspected
drift. Recheck mountains and foreground separately. If locked placement drifts,
use Nuke's actually discovered tracker and inspect residuals. Do not invent lens
distortion or focal length from an unknown camera. The long-lens Blender camera
is an artistic starting point, requiring horizon, projected ground and scale
comparison against the plate. Do not apply an unmeasured undistortion.

原片与裁剪均保留哈希；离线漂移分析只支持静机位首测。原生验收须逐区对比远山、
地面与插入物，需要时进行真实 Nuke 跟踪，不从未知摄影信息虚构焦距或畸变标定。

## 3D prop / 三维道具

Use only `assets/bronze-edge.glb`, the independently extracted KayKit CC0 sword.
The historical Hyper3D chest/column/arch/shrine are excluded while source
redistribution rights remain unresolved; no new Hyper3D request is authorized.
The future Blender script uses original scene assembly and lighting around
that cleared asset. Save an editable `.blend`, reopen it, and compare its
object/dependency readback before rendering.

Start with one 640×360 CPU test frame, at most four render threads. Match the
high camera-left warm key, subdued fill, ground perspective and contact.
Inspect contact shadow direction/softness and the burial/holdout edge. Then
render 1280×720 scene-linear EXR beauty, a white-unshadowed contact-shadow
factor, depth and normals. Inspect actual available outputs rather than
assuming a socket name. A static hold is allowed and must be recorded as such.
An animated 3D object requires a genuinely rendered sequence and new checks.

先做低清单帧，检查比例、入土遮挡、接触影方向与软度，再输出实际可用 EXR passes。
静态道具允许明确 hold；如果展示三维运动，则必须真实渲染连续帧并重新验收。

## Nuke composite / Nuke 主合成

- Read plate as its actual BT.709 encoding, generated PNGs as the verified PNG
  interpretation, and Blender EXRs as the recorded scene-linear space. Choose
  exact colorspace enum values from the assigned host. Check a known unchanged
  patch through the round trip; unknown transforms block final rendering.
- Preserve the plate's mountain/ground silhouette with a measured Roto mask.
  Sky replacement and distant-ruin placement use independent branches.
- Inspect the raw RGBA ruins against light/dark backgrounds, Unpremult before
  color work, correct the red/yellow edge contamination, then premultiply again.
  Record the actual cleanup parameters and view before/after pixels.
- Place the CG sword and its contact-shadow factor in matched screen space;
  multiply the ground shadow, merge beauty, then restore plate holdouts across
  the burial/contact edge. Check the alpha convention and unshadowed white.
- Match local exposure, color, blur and grain with restrained controls. Keep
  artificial atmospheric drift separate from real plate movement. Keying is
  not assumed for this non-green-screen plate; Roto is the intended tool.
- Save the native `.nk`, reopen it from an extracted portable package, and
  confirm no missing Read dependency. Rebuild separately in a blank task scene.

色彩转换、遮罩、前后景遮挡与素材边缘修复都须在真正的 Nuke 中检查。
构建器对未校验的 mask、placement、tracking、passes 与色彩枚举会拒绝成片生成。

## Deliver and review / 交付验收

Render the final 240-frame shot plus a synchronized before/after and a labeled
breakdown. Encode H.264 at width 1280 and preserve frame timing. Decode every
frame; view the entire clip and inspect transitions, edge crawl, color seams,
shadow sliding and clipping. Review silence/no audio intentionally. Measure
bytes, dimensions, duration and hashes from the delivered files.

The source package must include the `.nk`, editable `.blend`, actual render
passes, cleared input layers, exact source notices and actual sanitized MCP
call records. Re-extract and reopen the delivered package. Separate source
reopening, empty-scene rebuilding, technical checks and visual review.

成片、前后对照、breakdown、可重开工程与实测调用记录全部完成后，才进入官网候选
验收。当前未交付上述原生输出，不以静态素材或离线分析冒充实时互动。
