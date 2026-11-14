# 板级包整体搬迁方案（gts7xlwifi → sm-t970）

状态：方案，未开始执行。上游源码只作参考与拷贝来源，不进入本仓库提交历史。

## 1. 目标

把上游同型号项目的**整个板级层**（不只是一批驱动）搬到本仓库的构建里，
保留我们现有的分区布局、Data 持久化与打包脚本，产出一个可刷入的 RECOVERY：

- 屏幕上有启动报告（不再是看不见日志的绿条）；
- 触控失败时报出 `TOUCH start=/step=/crc=/hdr=`；
- 亮度、按键、CPU 调频、电池、USB、音频、Wi-Fi/蓝牙、GPU 都走他们验证过的顺序与参数；
- 每个子系统单独可验收、可回滚。

## 2. 为什么现在问题多

上游的 `package/` 是 66 个文件的板级层，我们只有 10 个简化实现。缺的是
"把驱动按正确顺序启动并显示状态"的那一层，所以每补一个驱动就暴露一个新现象：

| 现象 | 根因 |
| --- | --- |
| 绿条不动 | 缺 `BootProgress` 报告，失败点不可见 |
| 卡苹果 logo | 显示晚探测在 IOSurface/framebuffer 检查处退出，无回退路径 |
| 无触控 | 触控控制器启动挂在显示路径之后；HID 发布器失败会阻断核心 |
| panic 屏不显示 | 显示链路未就绪时 panic 无法渲染 |

## 3. 搬迁范围

### 3.1 板级流程与诊断（先搬，最先产生价值）

| 上游文件 | 作用 |
| --- | --- |
| `BootProgress.c` / `BootProgress*.h` | framebuffer 上画启动报告与状态行 |
| `BootLog.c` / `BootDiagExport.c` | 启动日志行、诊断导出 |
| `BootFaultProbe.c` / `BootWatchdogPolicy.c` / `BootReset.c` | 启动故障与复位策略 |
| `LegacyDisplayProbe.cpp` | 显示晚探测、触控/Wi-Fi/音频的启动顺序与诊断输出 |
| `LinkStubs.c` | 弱符号兜底（`native_pmap_user_mappings` 等） |

### 3.2 输入与人机接口

`HidInputProbe.cpp`（含 `ShengHidInput` 组件依赖）、`T970FtsTouch.cpp`（我们已有同一份）、
`T970Pen.cpp`（已有）、`ButtonProbe.cpp` / `ButtonsCore.h`、`BacklightProbe.cpp` / `BacklightCore.h`。

### 3.3 电源、时钟、电池

`CpuFreqProbe.cpp`、`ShengPlatformPower.cpp`（已有）、`T970Battery.cpp`（已有）、`KeyStoreProbe.cpp`。

### 3.4 无线与音频

`T970WifiProbe.cpp`、`T970WifiNet.cpp`、`T970WifiStack.cpp`、`T970Ath11k.c`、`ath11k-compat/`、
`T970Bluetooth.cpp`、`T970Audio.cpp` / `T970AudioService.cpp` / `T970Adsp.cpp` / `AdspFirmware.c`、
`T970Sensors.cpp`、`T970Camera.cpp` / `T970CameraService.cpp`（后期）。

### 3.5 公共基础

`QcomGlink/QcomMdt/QcomQmp/QcomRpmh/QcomScm/QcomSmem/QcomSmp2p`、`T970Apr/T970Ssc`、
`T970Rpmh.inc`、`MhiBoot.h/.inc`、`ShengAdsp.h`、`T970AudioAbi.h`（多数已在 `package/T970Dsp/`）。

### 3.6 已有等价物的替换决策

| 我们的 | 处理 |
| --- | --- |
| `package/T970Display/DisplayRegistration.cpp` | 由 `LegacyDisplayProbe.cpp` 取代，保留为回退 |
| `package/T970Touch/TouchBridge.cpp` | 由 `HidInputProbe.cpp` + `ShengHidInput` 取代 |
| `package/T970Touch/TouchHid.cpp` | 保留（Pen 仍用），触控改走上游发布器 |
| `scripts/build-display-registration.py` | 扩展为统一板级构建入口（见 §4） |

## 4. 构建改造

1. 以 `scripts/build-gop-legacy-display.py` 为蓝本新建 `scripts/build-board-package.py`：
   按上游 archive 清单把 66 个文件编成板级归档 `libT970Board.a`，含 GOP presenter 与原始绑定。
2. `board.toml` / `.config` 增加 `component:ShengHidInput`、`CONFIG_XNU_NATIVE_ADRENO`（后期），
   以及上游 boot args（`native-touch=1`、`t970-touch-xform=5`、`t970-wifi=4`、`t970-battery=1` 等）。
3. 内核补丁：以现有 44 条序列为基线，补 `t970-qcom-usb-debug-console.patch`
   （唯一冲突点在 `pexpert/arm/pe_kprintf.c`，手工 rebase）与 `t970-qcom-usb-debug-worker.patch`。
4. 打包沿用 `scripts/pack-dual-data-recovery.py`，新增 `--args-extra` 以便注入启动参数。

## 5. 里程碑与验收

| 里程碑 | 内容 | 验收 |
| --- | --- | --- |
| M1 | BootProgress/BootLog/BootDiagExport + LinkStubs 进归档并启动 | 屏幕上出现启动报告行；能读到 `TOUCH ...` 行 |
| M2 | LegacyDisplayProbe + HidInputProbe（含 ShengHidInput） | 触控可用；失败时屏幕直接给步骤号 |
| M3 | 电源/亮度/按键/CPU/电池 | 亮度可调、按键可用、调频生效 |
| M4 | USB 调试控制台 + 音频 | Mac 串口可读日志；扬声器/麦克风出音 |
| M5 | Wi-Fi/蓝牙/GPU（含 addon 与 zap 固件） | Safari 上网、蓝牙可开、合成流畅 |

每个里程碑刷一次机，失败按下表回滚到上一里程碑镜像。

## 6. 风险与回滚

- 每次刷写前记录镜像 sha256 与回滚镜像；已刷镜像清单见 `evidence/input/`。
- 回滚基线：`out/dual-system/port-all-v3-20261114/recovery-port-all-v3.img`（能进桌面、无触控）。
- 不触碰 Android 分区、GPT 与 iPadOS 持久化 Data。
- 上游源码放在 `/Users/cakeal/vsc/gts7xlwifi-upstream`，仓库只提交拷贝后的自有文件与记录。

## 7. 首轮执行顺序

1. 拷 `BootProgress.c`/`BootLog.c`/`BootDiagExport.c`/`BootFaultProbe.c`/`BootProgressStubs.c`/`LinkStubs.c`
   与头文件，编入板级归档，从显示晚探测启动；
2. 刷机，确认屏幕出现启动报告；
3. 再拷 `LegacyDisplayProbe.cpp` 与 `HidInputProbe.cpp`，同时拉 `ShengHidInput` 组件；
4. 刷机验证触控；之后再进入 M3。
