# 软件 vsync 事件诊断

v31 在 125 秒报告有 2 次成功 swap/copy/retire 和 0 次软件 vsync 通知。GopFramebuffer `cf3b429` 的 work-loop timer 仅在有通知客户端时 arm。板级回调现在累计组件已有的六类事件，终止报告首行显示 `vsync start/arm/idle/late/refresh`，下一行 `vsync` 保留通知次数。各计数独立采样。refresh 记录刷新属性查询，start 记录 timer 成功挂到 work loop，arm 记录首次布置 deadline，idle 表示 tick 发现通知队列为空，late 表示 deadline 已错过并重置节拍。通知计数记录调用原版 sender 后的事件。

用 `scripts/build-display-registration.py` 按现有 XNU 配方编译板级对象，使用已审计的 `display-object-cf3b429/NativeLegacyDisplay.o` 进行接口核对。在 v31 late archive 副本以 `xcrun ar -r` 替换 `DisplayRegistration.o`，逐项比对其他成员的字节，更新 build-report 中的 archive、对象和板级源码哈希。原内核、归档和报告位于忽略目录 `out/data-bringup/pre-vsync-stages-v32/`。构建树换入新归档及报告后，以原命令重建内核和 prelink。

```sh
python3.14 -m unittest discover -s tests -p test_display_state.py
python3.14 ../UniXNU/unixnu build kernel -D . --out out/data-bringup \
  --local-module "driver:ArmCpu=$PWD/.cache/armcpu-sgi-asm"
python3.14 evidence/display/vsync-stages-v32/prepare.py
```

ASan 格式化检查、实际板级对象编译、归档成员对照、内核预链接和最终 FAT 回读通过。打包前复现了 v31 的 panic-screen 内核字节，随后对新内核应用相同补丁。v32 保留 v31 的启动参数、ADT、trust cache、Data seed、固件及外层 DTB。镜像仍为 8 核、768 MiB 请求、125 秒主动终止报告。平台总检查在 DT/ADT 检查之前因 UniXNU HEAD 与历史审阅版本不同而退出。

从最终 FAT 回读内核中的原版通知函数，逐字节比对 21H461 原始 kernelcache 的完整函数（404 字节）。两处一致。原版发送循环以 `ldr x8, [x8, #0x15d8]` 读取队列头，与组件 `vsyncWanted()` 使用的 5592 偏移一致。证据见 `sender-audit.json`。

BOOT `6b692880cc0c9afb2e8aaaaf65dd8ac4bdc4f38c57c5c316a495620f3d3a2485` 位于忽略目录 `out/data-bringup/vsync-stages-v32/boot-partition.img`。机主授权直接刷 BOOT，Heimdall 已完成 BOOT 上传并请求重启，退出码 0。设备哈希未读回，屏幕采样见下文，见 `upload.json`、`flash.log`。start=0 指向 timer 初始化路径，start>0 且 arm=0 指向注册到 kick 的路径，arm>0 且 idle/notify 均为零时核查 tick 执行。若已有通知，比较帧数和用户态阶段，通知计数本身只覆盖 sender 调用路径。

## 实机结果

18:00:21 机主截图显示 start/arm/idle/late/refresh 为 1/0/0/0/0，notify=0。timer 已挂入 work loop，采样前未观测到 arm。组件只在高于 60 Hz 时记录 refresh 事件，因此本轮 60 Hz 下 refresh=0 符合源码。尚未采到 selector 72 调用或返回值。同期 open7、swap/transfer/copy/retire 各 3 次。Data 仍有约 308.4 MiB 可用。

原始 ARM64 共享缓存符号显示 BB 在 Objective-C 注册映射及 NSBundle 加载，SB 在 SpringBoardUIServices 的生物识别资源初始化链。对原版 backboardd 的低 12 位返回地址候选做反汇编，找到符合 v31/v32 共同栈形态的 `[NSBundle load]`，其参数路径来自 `System/Library/AccessibilityBundles/BackBoard.axbundle`。两个主程序 slide 均为推算。一次栈和跨启动的重复位置只表明应继续跟踪该加载阶段。见 `symbols.json` 与 `backboard-bundle-audit.json`。
