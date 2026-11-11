# 双系统 Data 与启动、显示耗时

## Data

实机已验证的 Recovery `5c9355fa…` 使用 `sheng-data-persist=0`。每次启动从同一份 512 MiB APFS 种子重建 Data。设置、应用数据和运行时缓存的改动随 RAM 一起丢失。

本轮使用既有 [RamBlock 持久化接口](https://unixnu.com/drivers/ram-block)，把变化的页写入独立 `unixnu` 分区内的固定窗口。保留现有 OS、SystemOS、签名载体和 APFS 种子。参考项目用 `SHNGEXT1` 描述 Android F2FS 文件的物理区段。本机已有连续的 `unixnu` GPT 分区，持久化路径按 GPT 和物理窗口直接寻址。

| 对象 | LUN 0 起止 LBA（4 KiB） |
| --- | --- |
| Android `userdata` | 2969600–37292799 |
| iPadOS `unixnu` | 37292800–62458623 |
| Data 页覆盖层 | 62065403–62196479 |

覆盖层为一个头块、四个位图块和 131072 个页块。存储入口要求明确的 `t970-ufs-unixnu=1`、实测分区边界、已知根镜像大小、512 MiB 种子和尾部 1 GiB 保留区，并在打开窗口前重新校验 GPT。未知、损坏或不同种子的头会被拒绝。Data 请求写入模式时，启动还会检查覆盖层确实打开，避免把 RAM Data 当成已持久化。

真机先使用模式 1 检查 GPT、窗口和头，再用模式 2 启动、修改设置并重启核验。刷写目标为 `RECOVERY`，通过物理按键进入。512 MiB 是本次验证的 Data 容量，96 GiB 是整个 `unixnu` 的分区容量。

2026-11-11 从框架 `404572cfc431f0b259cd190a99ad5b2c881a074a` 与设备 `5c37b6e` 工作树构建。现有 XNU 源码和按 Git blob 哈希验证的缓存头参与编译，链接后用 `unixnu build prelink` 产出内核 `481703e5…`。常规构建中的 dSYM 步骤被当前沙箱拒绝。用 `patch-xnu-entry-probe.py --panic-screen --no-reset` 给内核副本添加报告，再用 `scripts/pack-dual-data-recovery.py` 打包两个模式并回读 FAT。主机边界与头校验测试通过，RamBlock 的覆盖层及直通 I/O 自检通过。设备仓库单测运行 76 项，跳过 11 项。输出与日志位于 `out/dual-system/data-persistence-20261111`。

- 只读探测 `fba0a116ff37e5640c83e9e1bd63bdf0644eb2ba8a32f6c00f8b7fc6a4412c87`。Heimdall 只上传 `RECOVERY` 并成功结束。实机屏幕照片显示 `ok=1 header=0`、`LBA=62065403 blocks=131077`，头块为空。
- 持久化镜像 `33efcec0915129321995cd4de57a3223f7fd41e36c8f73205f07fa97e7aeaeba`。探测通过后，Heimdall 只上传 `RECOVERY` 并成功结束。用户观察到首次进入桌面约 4 分钟。设备桌面未找到「文件」，跨重启测试改用本机名称或键盘设置。

从已读回验证的根镜像 `fd43ee70…` 只读检查 OS 的 APFS 目录。`/Applications` 没有 `Files.app`，`/System/Library/AppPlaceholders/Files.app` 有图标和 `Info.plist`，标识符为 `com.apple.DocumentsApp`，包中缺少 plist 所列的 `Files` 可执行文件。该镜像的 OS 卷只提供占位包，完整应用由 [App Store](https://apps.apple.com/us/app/files/id1232058109) 提供。

用户报告 iPadOS 的系统关机停在转圈。用物理按键强制重启后，第二次约 4 分钟进入桌面，先前修改的设置仍在。UFS 覆盖层使用 FUA 提交已发出的块写入，应用或 APFS 尚未提交的修改仍可能在强制重启时丢失。用户随后确认 One UI 能正常启动。iPadOS 正常关机仍待排查。

## 启动

同一持久化 Recovery 的两次开机都约 4 分钟到桌面，保留 Data 后暂未观察到明显提速。v62 显示发布到首帧复制完成相隔 93.587 秒。v84 的首帧在内核计时约 129.340 秒出现。旧 v54、v55 报告了约 530 万次块读取，关闭预取后累计读取耗时依然约 684 秒。这些历史构建使用了各自的配置和计时起点。历史报告也观察到 LaunchServices 锁争用，单个栈样本无法分配开机时间。下一轮需要在同一 Recovery 上记录 launchd、Data 挂载、显示发布、首帧和系统可交互的时间。相关记录见 [v62](../evidence/display/owned-window-2g-v62/device-result.json)、[v84](../evidence/display/setup-skip-v84/device-result.json) 和 [v55](../evidence/display/prefetch-off-v55/device-result.json)。

## 帧呈现

v84 的 `copy us last/max` 为 42.531/49.297 毫秒。计时从显示驱动拿到可用帧并准备好 scanout 后开始，到像素拷贝后的内存屏障结束。2800×1752×4 字节约 18.7 MiB，每帧都全量拷贝时，43 毫秒约等于每秒 23 次拷贝的上限。v82 到 v83 的源映射与 framebuffer 缓存属性调整曾把最近一次拷贝从 326.897 毫秒降到 46.419 毫秒。现有差分复制每帧仍扫描整个源帧，曾在实机上没有测到加速。相关记录见 [拷贝计时回调](../package/T970Display/DisplayRegistration.cpp) 和 [缓存对照](../evidence/display/setup-fb-cache-v83/device-result.json)。

可在刚进桌面和静置约一小时后重复相同的连续滚动，分别采集 swap 间隔、copy 耗时和每次拷贝字节数。出帧更密而拷贝耗时相近时，继续查软件合成和后台服务。拷贝耗时也缩短时，再查时钟、内存带宽和并发 I/O。当前证据支持保留已验证的缓存映射，再测量合成到提交的耗时，并以实际更新区域评估减少拷贝字节数的收益。A650 仍处于 [GPU bring-up](gpu-port-plan.md)，本轮没有可用于证明着色器编译的运行时数据。

用户报告持久化 Recovery `33efcec0…` 下设置页加载慢，设置和负一屏均出现花屏。该镜像沿用向正在扫描的 GOP framebuffer 逐行写入的 CPU 路径，`sheng-vsync=60` 是软件定时器，与面板的垂直消隐未同步。转场时出现、静止后消失的条带符合扫描撕裂。若静止时仍异常，或系统截图也录入异常，需要检查合成帧和复制前后的像素。尚无照片或截图可以确定本次花屏的类型。
