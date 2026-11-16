# 同型号 SM-T970 功能移植

来源为 [UniXNU-gts7xlwifi `88b34f9`](https://github.com/rui12366B/UniXNU-gts7xlwifi/tree/88b34f97100a01aab4ea6b86dc9c748b2114c382)，与本机同为 SM8250、A650、iPadOS 17.7.11 / 21H461。下载快照 SHA-256 `44a463fcdc9a3d6acec80b31f50b524f146ea6df443b040699f42d69365e32af`。GPU 代码保留 [FFT-infra/Adreno650 来源](https://github.com/FFT-infra/Adreno650/tree/914d006ab46c99dde801da9c3ff9b52f0777b27e)和原许可。参考版通过 `62be7bc54266f0a731796ee71395963abccc0687` 加各组件补丁构建，本机验证使用 `404572cfc431f0b259cd190a99ad5b2c881a074a` 的现有 21H461 构建树。

> 上游同型号仓库不进入本仓库，副本位于 `../gts7xlwifi-upstream`（默认由
> `GTS7XLWIFI_UPSTREAM` 指定）。需要复用的驱动按组件复制到 `package/`，
> 复制后的文件归本仓库维护。


对方复用了 alioth 的 A650、UFS 和 USB 调试、pipa 的 GMU/HFI、sheng 的 Wi-Fi/Metal 路径，以及 T733 的显示格式和调度经验。T733 的同版 iPadOS 已实测 1247 次显示完成，DPU flip 达到 1200。相同 21H461 允许复用原版 `IOAcceleratorES`、HID 和 HAL 绑定。同型号仓库的 `periph15`、`combo26` 和 `main7` 记录了多轮实机迭代，包括 XR10 花屏、GPU 错误恢复和首次 addon 写入。公开时间线无法量化双方投入工时。[同型号实机记录](../reference/gts7xlwifi/porting.toml) · [T733 GPU 验证](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/main/docs/GPU_UPSTREAM_REBASE_76_2026-11-04.md)

| 功能 | 导入位置及本机验证 |
| --- | --- |
| A650、Metal、显示 | 使用真实 21H461 编译配方编译了 34 个 A650/IOAcceleratorES 构建单元。Metal 桥、带参考 BO 延迟回收修复的 Turnip、Metal 插件和探针守护程序已构建并打包。GPU 内核完整链接、同机签名 ZAP、显示接线和实机加速仍待完成 |
| 扬声器、麦克风、振动 | 音频 HAL 已签名并通过严格校验。扬声器、麦克风的内核驱动及 ADSP 已链接。放大器固件三件与实机库存哈希一致，ADSP 签名镜像仍需提取。振动已链接进 Recovery，启用独立 `T970Haptics` 服务及一次 150 ms 启动脉冲，实机待验证 |
| 充电、关机 | 本机 Recovery 继续启用已实测的电池及充电服务。PSCI 关机已接入 PMGR 和 21H461 XNU，回退只在没有可写卷挂载时启用。独立及合并 Recovery 均通过主机回读，待验证实机关机 |
| Wi-Fi、密码保存、蓝牙 | QCA6390 的 ath11k、MHI、QMI、mac80211 和蓝牙 UART.SK 已链接并预链接到 21H461。MinsOS 的七个 Wi-Fi 文件与同型号参考清单一致，两份蓝牙固件与此前实机清单的哈希不同。使用原版 21H461 launchd 缓存生成签名的 wpa_supplicant、BlueTool、bluetoothd 和合并无线 addon。服务挂载、KeyStore 和实机连接待验证 |
| S Pen | Wacom I²C 驱动与独立的键盘优先 Pencil HID 已链接到 21H461。复用上游的 usage 0x0D/0x20、压力缩放和 `AccurateMaxDigitizerPressureValue`。预链接复核了 207 个原版 IOHIDDevice 槽位，实际匹配、坐标和 Notes 压感待上机 |
| USB / Finder | AppleUSBXDCI 和 AppleUSBDeviceMux 已预链接，QcomDwc3 通过 267 个槽位布局和 102 个原版绑定检查并链接进 Recovery。MAX77705 MUIC 由现有电池线程操作，确认 D+/D− 路由和恢复 SE0 GPIO 后才启动 USB。Finder 实机待验证 |
| 传感器 | SLPI/GLINK/SSC 和板级启动回调俱已链接。SLPI 固件与服务启动待验证，真实运动数据仍待上游和本机验证 |

板级源码、用户态配方和参考配置在 [reference/gts7xlwifi](../reference/gts7xlwifi)。这些参考配置包含另一套 Windows 分区、日志窗口和挂载布局。实机包应沿用本仓库的 Android `BOOT`、F2FS `userdata`、iPadOS `RECOVERY` 和专用 `unixnu` 设备几何。ZAP 的 MDT 和 b01 必须来自同一签名组，两种已知组合见生成脚本。完整 addon 挂载需要确认 512 MiB 持久化 Data 的剩余空间。Apple、Qualcomm、Samsung 的二进制仍按参考清单从本机提取并留在忽略目录。

主机输出位于 `out/dual-system/gpu-reference-20261114`。Wi-Fi 头文件来自 [Ath12kWifi `5f7f5a8`](https://github.com/UniXNU/Ath12kWifi/tree/5f7f5a8a9f02f7ab45ed10a2f226e348c519a838)，蓝牙头文件来自 [QcaBluetooth `986d631`](https://github.com/UniXNU/QcaBluetooth/tree/986d6319d1d2819b27ed2c9786776f10bf63cc76)。

```sh
python3.14 scripts/gen-t970-adreno650-firmware.py \
  --inputs "$T970_GPU_INPUTS" --output "$T970_BUILD/GpuFirmwareA650.c" --host-check
python3.14 scripts/build-t970-adreno650.py \
  --tree "$T970_XNU_TREE" --output "$T970_BUILD/gpu-objects" \
  --firmware "$T970_BUILD/GpuFirmwareA650.c" \
  --metal-source ../UniXNU/drivers/AdrenoMetal --host-check
python3.14 reference/gts7xlwifi/scripts/build-t970-audio-hal.py "$T970_BUILD/audio-hal"
python3.14 -m unittest discover -s tests
```

主机验证生成两个 86,888,448 字节的 Recovery。独立关机镜像的 SHA-256 为 `755c53f32cd06139a9ccfe229f40f7a3a8c591f4ffd1e9d6eded350018aabce3`，位于 `out/dual-system/shutdown-20261114/recovery-shutdown.img`。关机加 Pencil 镜像的 SHA-256 为 `5aeca0c4a0322ab0e9f83b5a2316395b7d964ef303b46c0f8bb27bcd4fedba06`，位于 `out/dual-system/pen-20261114/recovery-pen.img`。

用 `scripts/pack-dual-data-recovery.py --mode 2 --shutdown` 打包独立关机候选，加 `--pen` 启用 Pencil 候选。为满足 1000 字节命令行上限，关机替换 Data 空间诊断参数，Pencil 替换 Setup 触控诊断参数。独立解包确认两份镜像的固件、两个 DT、分区尾、ADT、trust cache 和 Data seed 与持久化基线逐字节相同，仅替换 FAT 的内核和配置。常规构建在链接成功后生成 dSYM 时遇到沙盒的 `/dev/fd` 拒绝，Recovery 使用已链接的内核独立预链接。

`scripts/build-display-registration.py --haptics` 构建共享 DRV2 RPMh 和振动对象。与现有触控投票使用同一把锁。再加 `--haptics` 打包时，启动参数 `t970-haptics=3` 取代内存状态诊断参数。合并镜像 `out/dual-system/haptics-20261114/recovery-peripherals.img` 独立回读通过，SHA-256 为 `7c378fab6844dc7bde090dc19eafd51c9b133674c43a9965de3b86d24f7c618a`。

离线固件、用户态服务和无线 addon 输出在 `out/dual-system/firmware-inputs-20261114`。使用 MinsOS 的 `vendor.transfer.list` 和 Brotli 数据还原 EROFS，使用 `dump.erofs --cat` 提取指定文件。GMU/SQE 与原实机清单一致，签名 ZAP 和 DSP 段在单独的 modem 固件分区。

用 `--usb-device` 编译 USB 启动回调，再与通过 ABI 审计的 QcomDwc3 归档链接。`--usb` 打包启用 USB 2.0 设备模式和 J120 用户态标识，取代 UI 堆栈诊断参数。与上一份 Recovery 独立回读比较后，新增 USB 的镜像 SHA-256 为 `c5e1456ad05ed1093158b1cde04bf886967db9f844bad9ab71e4bac0cc4237b3`，位于 `out/dual-system/usb-20261114/recovery-usb.img`。USB 构建证据位于同目录的 `objects-final/build-report.json`。

模式 35 的实验在转用同型号驱动时暂停。模式 34 镜像保留作为已经上机的回退包。2026-11-14 使用修复版 Heimdall 读回 PIT，并在新会话仅向 `RECOVERY` 上传 USB 合并候选。回执确认上传成功，设备分区读回和启动观察另行记录。[上传回执](../evidence/input/dual-peripherals-20261114/upload.json)

`scripts/build-display-registration.py --wireless` 加入无线启动回调。Wi-Fi 移除参考版自己的 MUIC 和 USB 调试接管，避免与本机电池线程竞争 SE0。无线内核已通过预链接和原版 HID 地址检查，并打出无线未启用的 Recovery。合并无线 addon 约 6.4 MiB，现有 Recovery FAT 在无线内核加入后剩余约 1.9 MiB，运行版需要扩充 FAT、保留专用 `unixnu` 持久化布局并接入 launchd 缓存。

`scripts/build-display-registration.py --dsp` 构建 ADSP、SLPI、APR 和音频服务对象及 Xcode 的两个 128 位除法 helper。初始化首先登记音频服务，然后启动 ADSP 和 SLPI，关机复用真实的音频停止回调。预链接和 HID 检查通过，镜像 `out/dual-system/dsp-20261114/recovery-dsp-disabled.img` 的 SHA-256 是 `d9aa10ced26d64bc5a5e6ca856ac24da41f75a8fa9555879a44ace8cbe9b83a6`。扬声器、麦克风和 SLPI 保持关闭，待签名固件及用户态接入完成后实测。

Metal 构建在参考 UniXNU `62be7bc` 上运行。AdrenoMetal 为 `83b667824cb88c89473480cdf0c2c7276cd3ffc8`，metal2vulkan 为 `555b13d57e09bff70996a88cff64f1275256d5cf`，Mesa 为 `85fda3b36405bcaea8bffc64aa4f2651dc90770d`。先应用参考目录内的 Mesa patch series，再应用同型号 host patches 0002 和 0003 中的 BO 延迟回收修复。参考 0003 同时处理 iOS 17 Turnip 的 classic dyld binding。插件、Turnip 和探针分别通过严格签名检查，测试着色器通过 SPIR-V 校验。独立 Metal addon 位于 `out/dual-system/firmware-inputs-20261114/addon-metal.bin`，SHA-256 为 `fb32130db66e4a3dfcb0bdb4d030aa6381159e70945837b6a685a84484104ca4`。此处尚未移入参考的显示像素格式修复，也没有实机帧率、花屏或启动耗时数据。

## 触控接线与内核重建阻塞（2026-11-14 夜）

从同型号仓库取回 STM fts1ba90a 触控核心后，本仓库自己的 HID 发布器已经可用：
`package/T970Touch/TouchHid.cpp` 导出 `t970_touch_hid_start()` 与
`t970_touch_hid_frame(const T970TouchFrame&)`，`T970FtsTouch.cpp` 导出
`touchProbeStart()`、`native_touch_set_sink()` 与 `native_touch_*` 序列锁。
`package/T970Touch/TouchBridge.cpp` 把两者接起来（晚探测里由
`t970_touch_bridge_start()` 启动，带 `t970-touch-hid=1` 开关），
`scripts/build-touch-core.py` 用树内内核 C++ 编译记录产出
`T970FtsTouch.o`、`TouchBridge.o` 与带外设宏的 `DisplayRegistration.o`。

阻塞点不在驱动，而在整树内核重建：`.cache/xnu-work` 被重置后，
当前 Xcode 27.2 SDK 不再提供 xnu 需要的 `usr/local/libexec/availability.pl`、
`usr/local/include/kernel` 私有头与 `CodeSignature/Entitlements.h`，
主机上也没有可回退的 iPhoneOS 26.x SDK，因此全量重编在
`make_symbol_aliasing.sh`、`libkern/os/log.c`、`bsd/net/necp_client.c` 处失败。
旧的 887 个对象文件仍在 `build/xnu/ios-obj`，但补丁源已重写，无法安全复用。

结论：触控源码与接线已在本仓库完成并提交；要让平板真正拿到触控，
需要先用 26.x SDK（或补回上述 SDK 文件）重建一次内核，再走
`relink → prelink → pack-dual-data-recovery.py → Heimdall` 刷 RECOVERY。

## 同型号参考与实刷配置对照（2026-11-16）

对照对象是远端 `main` 的 `88b34f9`、其中公开的 `periph15` 启动菜单，以及本机实刷的 `peripheral-followup-a`（RECOVERY `980f9fc9`）。参考 README 还汇总了更晚的 main7、combo25 等结果，公开菜单中的启动参数只是其中一个早期构建。 [参考菜单](https://github.com/rui12366B/UniXNU-gts7xlwifi/blob/88b34f97100a01aab4ea6b86dc9c748b2114c382/docs/menu/unixnu.toml) · [参考运行记录](https://github.com/rui12366B/UniXNU-gts7xlwifi/blob/88b34f97100a01aab4ea6b86dc9c748b2114c382/porting.toml)

| 项目 | 同型号参考 | 当前实刷和结论 |
| --- | --- | --- |
| 系统与构建 | 21H461、UniXNU `62be7bc` 加三组 host carries；AppleKeyStoreState `8c70daf`，AdrenoMetal carries 目标 `9045eb0` | 21H461、UniXNU `945ad8d`。已从独立工作树构建相同 KeyStore；本机用参考 Metal carries 重建过插件，运行时文件留在本机 Data。参考未发布实际签名 addon，因此只能比对源码、配方和本机构建哈希。 |
| Wi-Fi | 菜单是 `t970-wifi=4`。实际 WPA2、DHCP、DNS、TCP 来自 `t970-wifi=6 t970-wifi-svc=1` 的后续运行。 | 已用阶段 6 并挂载签名服务缓存。PCIe worker、ath11k 接线、缓存挂载补丁与参考文件逐字节相同；Apple80211 代码只多关联计数。最新本机截图扫到 41 条，输入密码失败后 `JOIN` 未出现，先查无线守护进程向 Apple80211 提交请求的阶段。 |
| 蓝牙 | `t970-bt=257`、BlueTool、21H461 的 HCI 兼容补丁；公开日志证明守护进程建立传输、Settings 开关可用。 | 同参数、同兼容补丁，板级驱动只多 HCI 计数。最新实机有 10 个 Inquiry 类事件和 1699 个 LE 广播事件；用户可配对，连接与 Settings 发现仍失败。本机 addon 的两个蓝牙固件哈希与此前 Android 库存不同。 |
| USB | main7b `t970-usb=5`，记录覆盖 USB 枚举和 Finder 识别。 | 本机 `37=5+32` 还提供 J120 的 MobileGestalt 芯片/板 ID。启用 `t970-fsid=1` 后已出现平板信任框；Mac 在配对期间记录 `kAMDPasswordProtectedError`。补入 sheng 配对方案中的 `aks-sls=3`，让 KeyStore 如实报告移植系统无密码。 |
| 显示与壁纸 | periph15 的两条入口分别用直扫和 GPU 复制。参考 board 默认还带 `wallpaper-freeze=1`，公开菜单两条入口均未带这个选项。 | 两边的显示主驱动逐字节相同；本机现用 GPU 复制和实时横幅，直扫此前未消除白块或掉帧。参考的 12 条 BGRA 文本修补已加载。壁纸消失需要单独观察 Poster 进程与桌面输出，截图没有建立与点击信任的因果关系。 |
| Data、内存、日志 | 从 UEFI 的 ESP 启动；用 `t970-ufs-data=1 ufsrw=1` 挂载原 Windows 分区上的 APFS，使用 `t970-dram-end=0x280000000`，日志写参考机的备用分区。 | 本机从 Android RECOVERY 封装启动；持久 Data 由 `sheng-data-persist=2 data-fua=1` 和本机专用 `unixnu` 窗口承载。参考 Data、DRAM 和日志开关绑定了另一套分区及 UEFI 内存布局。 |

`pairing-state-a` 继续使用上一版的同一预链接内核、嵌入 addon、信任缓存和 Data 种子。独立回读确认启动参数只增加 `aks-sls=3` 并更新版本标签。 [回读报告](../evidence/diagnostics/pairing-state-20261116/report.json) · [sheng 配对配置](https://unixnu.com/porting/usb)

## 配对后的实机日志（2026-11-16）

- `pairing-state-a` 已通过 Mac 的 MobileDevice 配对验证，并能读取崩溃报告和系统日志。Wi‑Fi 手动加入到达 `wifid`，随后 IO80211 返回 `-3903`，采样中未提交类型 20 的关联请求。对照 21H461 的 `wifid` 确认类型 422（6 GHz 模式）的返回值不会阻断后续关联。新版再次复现。两次均由设置的「其他网络」入口提交，记录的是 WPA 信息元素，未报告 RSN。用扫描列表里的已知 WPA2-Personal（AES）网络验证同型号参考的关联路径。
- 蓝牙被动 LE 扫描已启动，固件送回了广播。用户仍报告设置中搜不到设备、配对后连不上。Recovery `3fbc958c` 新增 `BTCON`。刷入后的 USB 日志已确认该配对设备建成经典 ACL、启用 AES-CCM 加密并成功连接 GATT；同一设备的 PAN 网络共享连接返回 305（PAN 客户端日志 3471）。设置列表里的完整发现以及其他服务仍待验证。
- PosterBoard 在 PosterKit 的 `configuredPropertiesForPoster:` 遇到空配置断言。它找到了系统墙纸 7570，同时报告默认 `CollectionsPoster` 扩展初始化失败（`-2220`）。21H461 原版 OS 内有签名扩展及对应 LaunchServices 种子条目，新一轮启动还记录了该扩展的容器和旧版回退扩展同样返回 `-2220`。继续查扩展查询和激活，因为容器存在时 PosterBoard 仍取不到配置。 [配对后实测](../evidence/diagnostics/pairing-state-20261116/report.json) · [蓝牙诊断镜像](../evidence/diagnostics/wireless-runtime-probe-20261116/report.json)
