# 可复用生产提示词

这是根据本轮实际步骤整理的复用生产说明，不是用户原话逐字稿。关键输入见 `profile.json`，实际响应与验证见 `calls.json` 和 `validation.json`。

只通过 typed DCC-MCP，在独立且确认空场景的 Houdini 宿主制作一件青釉环纹陶瓷器皿。不得改动其他任务场景，不得直接运行 Houdini 资产制作脚本。创建 51 点的半径/高度剖面，连续定义底部、环纹外壁、肩部、口沿和内壁，绕 Y 轴旋转 144 段；建立两级 Subdivide 和顶点法线。保留完整可编辑 SOP 链。

用 Principled Shader 设置青绿色 basecolor=[0.035,0.21,0.18]，禁用点颜色，roughness=0.30、coat=0.35、coatrough=0.24。地面 basecolor=[0.46,0.40,0.32]、roughness=0.65；地面顶面和模型最低点均为 y=0，不使用外部贴图。建立 90 mm 镜头和三块 grid 软箱，保持完整开口、肩部环纹及底部接触阴影可见。

先保存并渲染真实中间图，依据图像有限调整灯光与构图，再输出真实 1200×1500 Mantra 主图，PBR Ray Tracing、4×4 像素采样、最多 16 条次级射线。输出使用 `$HIP/hero.png`，保存工程、等待隔离渲染作业完成并核对文件；随后重开工程，重新读回几何计数、材质、相机和渲染路径。

所有正式 CLI 调用使用 `--require-gateway` 和稳定 `--agent-session-id`。先 inventory、scoped search、load-skill/describe，再按实际 schema 调用。记录实际工具名、请求/响应和失败，不用工具 applied 字段替代实际文件尺寸检查。公开文档用 `CASE_DIR` / `JOB_DIR` 明确脱敏，审计原生工程里的私有元数据，保留作者和 MIT 许可。任何能力缺失都写明，不使用生成图片或历史成图冒充本轮渲染。
