# 同型号移植的执行顺序

目标是把 `rui12366B/UniXNU-gts7xlwifi` 的驱动与用户态服务逐个接到本仓库，

> 上游同型号仓库不进入本仓库，副本位于 `../gts7xlwifi-upstream`（默认由
> `GTS7XLWIFI_UPSTREAM` 指定）。需要复用的驱动按组件复制到 `package/`，
> 复制后的文件归本仓库维护。

直到本机实机达到该项目的功能集合。参考源码快照在 `reference/gts7xlwifi/`，
导入边界与已有证据见 [gts7xlwifi-import](gts7xlwifi-import.md)。

## 当前实机范围

8 核 SMP、桌面可用、侧键与锁屏唤醒、电池与充电、Data 持久化均已在实机确认；
`out/dual-system/all-in-one-20261114/recovery-all-in-one.img`
（SHA-256 `34434b0b227d520dbf32c30edf9176a8a4cabe391632bad6d1468f6f601df9a0`）
把 S Pen、振动、USB 设备模式和关机失败保护合并到同一镜像，
2026-11-14 20:25 只上传 RECOVERY 成功，开机结果待设备回报。

## 差异清单

参考 `package/` 有 62 个文件在本仓库没有同名实现。按依赖关系分组：

| 组 | 参考文件 | 依赖 |
| --- | --- | --- |
| 无线基础设施 | `QcomGlink.c` `QcomQmp.c` `QcomRpmh.c` `QcomScm.h` `QcomSmem.c` `QcomSmp2p.c` `T970Apr.c` `T970Ssc.c` | 无，可先行 |
| Wi-Fi | `T970Ath11k.c` `T970WifiNet.cpp` `T970WifiProbe.cpp` `MhiBoot.h` | PCIe0 供电/PHY/复位/BAR/MSI，需先训练链路 |
| 音频 | `T970Audio.cpp` `T970AudioService.cpp` `T970AudioAbi.h` `T970Adsp.cpp` `AdspFirmware.c` `ShengAdsp.h` `QcomMdt.c` | QMI/GLINK、ADSP 固件与用户态 HAL |
| 蓝牙 | `T970Bluetooth.cpp` | 无线基础设施与 BlueTool 服务缓存 |
| 相机与传感器 | `T970Camera.cpp` `T970CameraService.cpp` `T970Sensors.cpp` `T970Ssc.c` | SSC/SLPI 协处理器 |
| 触控与输入 | `T970FtsTouch.cpp` `HidInputProbe.cpp` `ButtonsCore.h` `ButtonProbe.cpp` | 已自实现的触摸 HID 路径需与 FTS 驱动对齐 |
| 显示与亮度 | `BacklightCore.h` `BacklightProbe.cpp` `LegacyDisplayProbe.cpp` | DSI 交接与 S6TUUM3 命令 |
| 调频与电源 | `CpuFreqProbe.cpp` `T970Rpmh.inc` `BootWatchdogPolicy.c` | RPMh 与 PMGR |
| 诊断 | `Boot*.c` `BootFaultProbe.c` `LinkStubs.c` | 仅构建桩 |

## 顺序

1. 无线基础设施（GLINK/QMP/RPMh/SMEM/SMP2P/APR/SSC）：无 PCIe 依赖，
   是音频、蓝牙、传感器的共同底座，先做可编译 + 只读探测。
2. 音频：ADSP 固件装入与 HAL，先扬声器再麦克风。
3. 蓝牙：复用 2 的 ADSP 与无线基础设施，接 BlueTool 服务缓存。
4. 触控/亮度/调频：与现有 HID、GOP 路径对齐后逐项实机验收。
5. Wi-Fi：必须先完成 PCIe0 训练（供电、PHY、复位、BAR、MSI、DMA），
   再接 ath11k/MHI/QMI 与 21H461 网络 ABI。
6. GPU：Metal addon 需要三件事同时具备——内核侧 addon 挂载补丁、
   FAT 扩容把 `Payloads/kernel.macho.gpuaddon` 放进 Recovery、
   ADT `chosen/memory-map` 的 `GpuAddon` 属性。当前三项都未完成，
   且参考版约 6.4 MiB 的无线 addon 与本机 FAT 剩余 3.4 MiB 冲突。

## 已知阻塞

- Recovery FAT 固定大小，运行版需要扩容并把 DTBO/DTB 后移，同时重算 header
  与 boot id；`scripts/pack-dual-data-recovery.py` 尚不支持。
- 参考的 `t970-wifi-service-mount.patch` 在本机 `bsd/kern/kern_exec.c` 处冲突，
  需要手工重贴后才能挂载服务缓存。
- 每项都必须按镜像哈希做实机验收，主机构建结果不能代替设备结果。
