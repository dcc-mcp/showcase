# Production findings / 制作中发现的问题

These observations come from actual Blender 4.5.14 LTS calls with
`dcc-mcp-blender 0.2.16` and Core `0.20.42`. They are bounded observations, not
claims about every adapter or host version. The movie keeps the installed
adapter unchanged during production.

以下来自 Blender 4.5.14 LTS、`dcc-mcp-blender 0.2.16` 与 Core `0.20.42` 的
真实调用，不代表所有版本。本片制作期间未热替换适配器。

## 1. Parenting reported failure after applying the change

`parent_object(child_name="Camera_Reference", parent_name="Film_Orbit_Rig")`
returned `isError: true`, `success: false`, and a maximum world-transform delta
of `1.430511474609375e-6`. The response itself says that parenting had already
been updated. A subsequent `get_object_info` confirmed the new parent.
Typed `move_object` and `rotate_object` reapplied the original camera pose,
followed by another readback. Production did not change the adapter tolerance.

A failure response after mutation can cause a caller to repeat an already
applied operation. A robust fix should consider transform magnitude,
absolute/relative floating-point tolerance, and the semantics of partial
application. It should still reject singular or genuinely changed transforms.
The original incident did not capture complete before/after world matrices;
its reported delta and object-state readbacks must not be presented as a
complete matrix-level proof. The [minimal operation summary](mcp-operation-summary.json) records selected
request parameters and numerical outcomes. Complete receipts remain private.

`parent_object` 返回失败时，父子关系实际已改变；返回的世界矩阵最大偏差为
`1.430511474609375e-6`，后续读回确认了新父对象。本次用 typed 位移、旋转
恢复原相机姿态并再次核验，没有直接放宽 epsilon。此类“已变更却返回失败”
可能诱发重复操作。修复应同时检查变换量级、绝对与相对容差及部分成功语义，
并保留对奇异矩阵和真正变换错误的拒绝。原事件没有完整前后世界矩阵，
因此不能把这组回执描述为完整矩阵证明。

## 2. Denoiser option unavailable on this host

A `set_render_denoise` call that included `use_gpu=false` failed with
“Not exposed by this Blender build: scene.cycles.use_denoising_use_gpu.
Nothing was changed.” Retrying with only `enabled=true` and
`denoiser="OPENIMAGEDENOISE"` succeeded. The film does not depend on the
unsupported parameter. Host capability mapping should be checked before
advertising that optional setting as available.

带 `use_gpu=false` 的去噪设置请求明确失败，提示当前宿主没有对应属性且未改动。
移除该非必要参数，仅启用 OpenImageDenoise 后成功。影片不依赖这个不支持的
参数；工具应依据实际宿主能力映射可用设置。

## 3. Partial rendering and bounded recovery / 部分渲染与有界恢复

Production selected Cycles CPU after actual preview comparisons. Each native
frame was saved independently. Repeated host exits with status `-9` interrupted
production. Their cause was not established; the record does not prove an
out-of-memory kill, a fixed host lifetime, or an adapter defect.

The [OIDN documentation](https://www.openimagedenoise.org/documentation.html)
describes `OIDN_NUM_THREADS`. A controlled rerender of existing frame 50 with
that setting at 2 used unchanged textures, samples and resolution. Its maximum
RGB channel difference was 2/255, so it was not pixel-identical. The comparison
does not demonstrate lower peak memory or establish the earlier failure cause.

The published excerpt retains original frames 1–50. Only additional local
checkpoint frames 51–55 use the explicit OIDN thread setting. Frame 56 failed
again and all rendering retries ended. No detail sequence was completed; earlier
real detail renders remain previews. No Workbench or EEVEE frame, interpolation,
held still, or padded duration was substituted into the delivered excerpt.

本次根据真实预览选择 Cycles CPU，每帧独立保存。制作被多次 `-9` 宿主退出中断，
原因未确定；不能据此断言 OOM、固定宿主时限或适配器故障。

依据 OIDN 官方文档，仅将线程设置为 2，对已有第 50 帧另行校准；纹理、样本、
分辨率不变。最大 RGB 通道差为 2/255，因此并非逐像素一致，也未证明内存峰值
降低或失败原因。

公开片段保留原第 1–50 帧；额外本地检查点第 51–55 帧才使用显式 OIDN 两线程。
第 56 帧再次失败后已结束全部渲染重试。没有完成近景序列；较早近景渲染仅为
预览。交付片段未混入 Workbench/EEVEE 帧、插帧、重复静帧或补足时长。
