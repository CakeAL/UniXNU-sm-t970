# T970 GPU（Adreno 650）移植方案

目标：在 SM-T970 / SM8250 / Adreno650v3 上，把现有 XNU GPU 驱动的
**NativeAdreno ABI v1** 核心与一个 SM8250 后端接通，实现 GMU 启动、
CP 提交、GPU 内存映射和最小绘图；Metal/DPU 留到后续阶段。

## 参考项目

| 项目 | 硬件 / OS | 可复用内容 | 限制 |
| --- | --- | --- | --- |
| [unixnu-adreno6xx](https://github.com/RigoLigoRLC/unixnu-adreno6xx)（T733，MIT） | SM7325 / A642L，iPadOS 17.7.11 | NativeAdreno ABI v1、ring、提交、fence、BO/内存、调度、IOKit user client、发布层；与本机同为 17.7.11 ABI | power/GMU/SMMU/CP/hwinit 是 SM7325/A660 专用 |
| [lmi-uefi-touch-gpu](https://github.com/Fsasdddd/lmi-uefi-touch-gpu)（MIT） | SM8250 / A650，iOS 16.5 | SM8250 ARC/RPMh/时钟、GMU 冷启动与 HFI、ZAP/SCM、CP、SMMU/context、tile/desktop；与本机同 SoC/GPU | 内核基线是 HackiOS 16.5，不是 UniXNU 17.7.11；板级数值是 lmi |
| [UniXNU Adreno740](https://github.com/UniXNU/Adreno740) | SM8550 / A740 | NativeAdreno 当前组件结构、构建/发布方式 | A740 寄存器、固件、Metal 插件均不适用 |
| [UniXNU-umi](https://github.com/reAAAq/UniXNU-umi) | SM8250，iPadOS 17.7.11 | 同 SoC + 同 OS profile 的板级/ABI 经验 | GPU 未实现（纯 CPU 呈现） |

## 复用划分

**可直接复用（A6xx 通用，按 ABI 调整）**

- `NativeAdrenoABI.h`、`NativeAdrenoRing.*`、`NativeAdrenoSubmit.*`、
  `NativeAdrenoMemory.*`、`NativeAdrenoScheduler.*`、`NativeAdrenoUserClient.*`、
  `NativeAdrenoPublish.*`、`NativeAdrenoVm.*`（需去掉 A642L 的 `0x06030500` 硬编码）；
- B0/队列/围栏/IOKit 传输和诊断计数。

**必须新写 / 重映射（SM8250 A650 后端）**

- 生成枚举与 chip ID：新增 `A650`（DT `qcom,chipid = 0x06050002`；GMU HFI SFR 值按
  lmi 的 `0x06050200` 先核对）；
- 电源/时钟：GPUCC（`0x3d90000`）、CX/GX GDSC（`0x3d9106c`/`0x3d91508`）、
  ARC `cx.lvl`/`mx.lvl`、RPMh 投票、OPP（305–670 MHz，7 档）；
- GMU：`a650_gmu.bin`（41548 B）、GMU 窗口 `0x3d6a000+0x30000`、HFI 队列/版本、
  `a650_sqe.fw`（31632 B）；
- ZAP：`a650_zap` 分片签名镜像、PAS/SCM 认证；
- SMMU：T970 apps SMMU 的 GPU SID/上下文，按本机 SMMU 只读证据确定；
- CP/hwinit/RBBM：A650 的启动表和中断位；
- 显示：当前是 GOP + CPU 拷贝；GPU 画面要经 DPU scanout（lmi 的异步 DPU 可参考）。

## 阶段与验收

| 阶段 | 内容 | 设备证据 |
| --- | --- | --- |
| 0 | 资源/固件/候选源对照（v99 起） | 报告 `GPU arc` 行、DT/固件哈希 |
| 1 | GPUCC/GDSC/供电/TSENS 资格确认 | 只读时钟/电源快照，无挂死 |
| 2 | GMU 冷启动 + HFI 版本回读 | `FW_INIT`/HFI 响应 |
| 3 | ZAP 认证 + secure mode 退出 | 认证结果 |
| 4 | SMMU/GPU VA + CP ring/fence | GPU 内存写入回读 |
| 5 | tile/GL 探针 | 已知像素精确匹配 |
| 6 | 桌面/DPU + 17.7.11 Metal ABI | 系统合成上屏 |

## 当前起点（v99）

`package/T970Gpu/ArcResources.h` 只读解析 ARC cmd-db（`0x80860000+0x20000`，
触摸/RSC 路径已映射过该块），报告新增 `GPU arc db= cx= lv= min= mx= ...`。
它验证 GPU 的 CX/MX 电压档资源路径，不请求 RPMh、不写寄存器。

下一步：把 ARC 读数与 T970 DT 的 OPP/电源域对照，再做 GPUCC/GDSC 的
只读资格确认（先确认时钟/电源状态，再读 GPU 窗口），然后进入 GMU 启动。

## 风险

- GPU/GMU 窗口在未上电时 MMIO 读可能挂死，必须先做时钟/电源资格；
- `a650_gmu.bin`/`a650_zap` 是专有固件，仓库只有哈希，需从本机 stock 自带；
- 17.7.11 的 Metal/GPU 用户态 ABI 与 lmi 的 16.5 RedwoodGPU 路径不同，后半程需重新审计；
- 参考项目本身也不是成品（lmi 整体 INCOMPLETE；T733 GPU 有回归记录）。
