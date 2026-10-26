# Native Max UI evidence

Actual captures:2; wireframe captures:0. DCC-CUA1.12.2 exact-window capture and one background UIA tab action passed. [Evidence](ui-verification.json).

The scene capture shows native Scene Explorer, camera viewport and command panel. The second capture verifies selection of the Modify tab through UIA, without foreground focus. No object is selected; this is not modifier-stack verification.

Still open: housing Lathe128segments, blade Extrude0.45mm, wireframe, frame1/72 comparison, material/light/camera controls, and real video playback. Scene Explorer object rows were not exposed in the observed UIA tree. Foreground activation was refused in an earlier raw-input preparation step; no input was sent then. This is not a general screenshot failure.

Crops remove top toolbars containing private project paths and bottom status strips; no repaint or compositing. Raw captures and target binding receipts remain private. The scoped CUA task stopped with no pending cleanup. Source file retained unchanged.

PrintWindow-specific behavior was not tested. Capture, background semantic input and foreground physical input require separate capability/readiness reporting. These images do not establish normal MZP installation, MCP transport, full-film stability or engineering collision clearance.

中文：已补2张真实Max界面图及后台UIA切换Modify页签的操作后证据；线框、对象修改器参数、关键帧对比和实际播放仍未验收。截图成功、语义操作成功、前台激活被拒分别记录，不扩大结论。原图私有留存，公开图仅裁剪与缩放编码，原工程不覆写。
