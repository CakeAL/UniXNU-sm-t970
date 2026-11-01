# 三星与 SM8250 UFS 参考核查（2026-11-01）

本页是公开源码／维护者记录的对照，不是这些设备在 T970 上的验证。
T970 本轮原始画面见 `evidence/storage/readonly-smmu/screen.txt`，镜像及观察已按哈希绑定。

## 参考设备

| 设备 | 已公开的结果 | 对 T970 有用的内容 |
| --- | --- | --- |
| Samsung SM-T733，SM7325 | 48f 交付记录报告 300788 次 UFS 请求、零失败、两种超时均为零；系统卷及持久 Data 已运行 | Samsung 固件集成、受约束的 SMMU 接管、诊断与请求队列 |
| Xiaomi Mi 10 / umi，SM8250 | 维护者报告 OS/SystemOS 根卷、launchd、持久 Data、Hello/Setup；完成设置与桌面仍未验证 | 同 SoC 的时钟偏移、双 stream 规划、DMA 所有权检查、阶段化诊断 |
| Xiaomi Mi 10 Ultra / cas，SM8250 | README 记录 CPU0 到 VM／早期平台初始化，UFS 根卷仍在工作列表 | 说明同 SoC 仓库的存在不等于已通过存储验证 |

原始记录：[T733 48f](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/dcc9e7f65fb19a8c05514a782dd9759fd7102a43/docs/archive/FORMAT2_2026-10-25.md)、
[umi README](https://github.com/reAAAq/UniXNU-umi/blob/3eb72578597d2ca16471b172d45eddc096a34a04/README.md)、
[umi 验证边界](https://github.com/reAAAq/UniXNU-umi/blob/3eb72578597d2ca16471b172d45eddc096a34a04/docs/validation.json)、
[cas README](https://github.com/ht94911/UniXNU-cas/blob/5cba1411b76170abf027e312afee15669b9541d9/README.md)。

## 它们也经历过硬件诊断

T733 的 `NativeUfs::adoptAndRead` 保留了 2026-10-17 的硬件记录：首次命令使用
内核分配的 DMA 缓冲后设备复位。这个实验函数曾借固件请求列表做定位，并明确警告
页面可能也由内核持有；不能直接移植该实验手段。其正式接管规划检查现有 stream、
共享 context、翻译启用状态及写回值。

来源：[T733 NativeUfs.cpp](https://github.com/RigoLigoRLC/unixnu-nativeufs/blob/06b3a102e78c3129b4645416a52ac23f5523f3cb/NativeUfs.cpp#L410)、
[SmmuTakeover.h](https://github.com/RigoLigoRLC/unixnu-nativeufs/blob/06b3a102e78c3129b4645416a52ac23f5523f3cb/SmmuTakeover.h)。

umi 的探针保留了分阶段观测，host 适配先检查供电／时钟，校验 DMA 落在实际拥有的
内存内，停止请求队列后重新规划并校验两条 stream。它的 `0xe0/0x4e0` 是 umi 的
板级输入，不构成 T970 的 SID 证据；同理 T733 记录的 `0x80` 不能直接套用。

来源：[umi 阶段探针](https://github.com/reAAAq/UniXNU-umi/blob/3eb72578597d2ca16471b172d45eddc096a34a04/package/UmiUfsProbe.cpp)、
[host 适配](https://github.com/reAAAq/UniXNU-umi/blob/3eb72578597d2ca16471b172d45eddc096a34a04/package/UmiNativeUfsHost.inc)、
[双 stream 规划](https://github.com/reAAAq/UniXNU-umi/blob/3eb72578597d2ca16471b172d45eddc096a34a04/package/UmiSmmuTakeover.h)。

## 固件前提不同

T733 有公开的配套 Mu-Silicium fork。固定固件 `d511b74…` 的
`Include/Vendor.inc` 引入 ClockDxe、ScmDxeLA 和 `PatchedBinaries/UFSDxe.inf`。
这些依赖需要设备自己的厂商输入，不能只复制内核驱动就假定获得相同的交接状态。
当前公开目录未包含这个 UFSDxe 包装文件本身，不能声称已取得可复现的全部二进制。

来源：[T733 固件 Vendor.inc](https://github.com/RigoLigoRLC/unixnu-mu-silicium/blob/d511b74f971099e89356b4324dcf1d98c2cee029/Platforms/Samsung/gts7fewifiPkg/Include/Vendor.inc)。
本轮 T970 故意使用不 dispatch UfsDxe 的已测 FD；umi 固定的继承状态／RAM 载荷
固件路径也不同于 T733 的厂商 UFS 路径。不能将某个路径视为所有设备的必要条件。

## 本地代码的具体差异

T970 的原厂 DT 使用 kona GCC。三星设备内核的 `gcc-kona.c`、Linux v6.12 的
`gcc-sm8250.c` 与 umi 的 host 代码对以下偏移一致：

| GCC 时钟 | 本地继承的 SM8550 常量 | SM8250 参考 |
| --- | --- | --- |
| UFS PHY AXI | `0x77018` | `0x77010` |
| UFS PHY AHB | `0x77024` | `0x77018` |
| UniPro core | `0x77068` | `0x7705c` |
| ICE core | `0x77074` | `0x77064` |
| PHY AUX | `0x770b0` | `0x7709c` |

来源：[三星 gcc-kona.c](https://github.com/LineageOS/android_kernel_samsung_sm8250/blob/ad129ac77e9d871770d61f7bd219a836d7f35b74/drivers/clk/qcom/gcc-kona.c)、
[Linux gcc-sm8250.c](https://github.com/torvalds/linux/blob/v6.12/drivers/clk/qcom/gcc-sm8250.c)。
本地 `package/ShengUfs/GccUfs.h` 仍是 SM8550 诊断表，UEFI `BoardInit.c` 也保留了
其中四项旧宏。不过当前 `BoardInit.c` 已跳过 GCC 写入，这些宏没有被它引用；
不能据此认定已证实某次复位原因。只读 SMMU 镜像不执行这两处时钟操作。
本次只记录差异，没有更改默认 SID、启动传输或刷写新固件。

## 对下一步的约束

1. 先修正并验证 SM8250 时钟诊断表，以同 SoC 的 umi 适配作为主要对照；T733 用于核对固件和 Samsung 集成。
2. 一次采集有界的完整 stream 表及 UFS 供电／时钟状态。只有确认寄存器可访问的前提满足后才读取 HCI 与队列状态。
3. 核实 T970 实际路由及 DMA 所有权，再选择固件初始化或独占 context 接管；不扫描改写活动 SMR。
4. 按已知块读取、根卷、持久 Data 顺序验证。本轮寄存器可读和候选未匹配，不代表 SMR 可写、PHY 已就绪或 DMA 已通过。
