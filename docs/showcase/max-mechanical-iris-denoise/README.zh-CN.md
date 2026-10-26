# 机械光圈：原生可编辑结构与引导式降噪对照

![真实Arnold渲染，Noice参考，缩小展示](hero.jpg)

原生工程含84对象：12叶片、12轴帽、48个独立紧固件，外壳440×440×34mm。1920×1440/AA3主图、帧48–55的8帧短段和AA6参考均来自真实Max渲染。正式media-enhance Core Skill调用Blender OIDN；Autodesk Noice作为独立原生参考。本案例是草稿，未作为完整影片验收或加入线上精选集。

[24fps三路原速](comparison-24fps.mp4) · [6fps慢速审阅](comparison-slow-review-6fps.mp4) · [960×720 OIDN](oidn-24fps.mp4) · [AA6对照](higher-sample-comparison.jpg) · [紧固件](fastener-detail.jpg) · [叶片边缘](blade-detail.jpg) · [连续帧裁剪](eight-frame-detail.jpg) · [配方](recipe.json) · [验证](validation.json) · [文件哈希](manifest.json) · [权利边界](RIGHTS.md) · [English](README.md)

原生Lathe轴矩阵和外壳尺寸经验证；保存重开、FBX重导入在1/24/72/96/144帧的采样矩阵偏差为0。相机修复后，不支持的Target65mm请求会明确拒绝并回滚，Physical相机真实属性读回65mm；原84对象与工程文件哈希未变。现有图像继续使用原工程实际45°FOV，没有改成65mm冒充旧图。

正式入口为Python3.12 Core Skill进程内调用，并非MCP通信验收。Blender5.1.1提供Intel OIDN算法，项目实现有预算和来源记录的编排；Noice7.2.4.1是另一成熟算法，不称自研或新的Maya验收。真实beauty、normal、albedo导出像素与原EXR逐项比较，差值阈值1e-6通过；最终候选消除无名根层enum警告，前后像素在同阈值下相符。

短片列顺序RAW／正式Skill OIDN／Noice，同源960×720线性EXR、同Gamma2.2展示转换。24fps的8帧仅1/3秒；6fps为明确减速4倍的审阅版本。视频为limited BT709矩阵、BT709primaries及gamma22transfer标记，静音为刻意选择。49–55帧真实seed一致为-2082661815；复用的48帧来自旧采样模式，不能把该接缝变化单独归因于算法。

AA6参考用时272.515秒，是更高采样观察而非真值。两后端均减轻可见颗粒；Noice较平顺，OIDN略多细纹理，孔尖角、细金环及紧固件轮廓在已检查静帧中仍可辨。没有据此做无依据质量评分。全部帧解码和连续裁剪检查不等于真实自然速度播放；CUA仍禁用，未补编辑器或线框截图。

复现需使用适配器候选与改写配方，重新发现工具、核原生单位与FOV，保存真实引导EXR，退出渲染进程后再执行正式Skill，并验证完成manifest和原始哈希。原生工程及私有日志仍保留待公开副本清理。完整144帧、换向时序、实际播放、Max界面、正常MZP安装、MCP通信及最终独立评审尚未通过，不合并或部署此草稿。
