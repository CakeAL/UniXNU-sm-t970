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
