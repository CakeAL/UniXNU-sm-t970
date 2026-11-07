# SM-T733 提交与功能核查

核查日期：2026-11-07。对象为
[RigoLigoRLC/unixnu-sm-t733 的 unixnu-sm-t733 分支](https://github.com/RigoLigoRLC/unixnu-sm-t733/commits/unixnu-sm-t733/)。
读取该分支 145 条提交、相关提交 diff、固定版本源码和有日期的运行记录。
核查时 HEAD 为 `4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab`，提交时间
2026-11-04 23:31:24（UTC+8）。这是远端记录审阅，没有在 T733 上独立复测。

## 已实现的范围

| 功能 | 远端记录支持的结论 | 实测边界 |
| --- | --- | --- |
| 启动、桌面、触屏 | UEFI/UniXNU/XNU 启动，Setup 后进入桌面；FT8203 触屏和中断可用 | 设置及首次打开界面仍有延迟记录 |
| CPU、调频、温度 | 八核、4+3+1 三个调度簇、perfcontrol、三域 EPSS 和 27 路 TSENS；实际频率与硬件周期一致 | 实际过温触发及冷却解除未完成验证；CPU idle/上下线和整机休眠未完成 |
| 内存 | 46b 报告 XNU 内存 4548722688 字节，约 4.236 GiB | 不是全部 6 GiB；实时 EFI 保留区和连续分配影响可用量 |
| UFS 与 Data | 原生 UFS，96 GiB Data 可写并跨重启保留；FUA/flush、并发和任务 abort | 控制器完整复位、独立冷初始化和恢复仍有缺口 |
| 电源、音量键 | SPMI v5/PDC 中断、去抖、三键 HID 完整 DOWN/UP | 不能由 HID 事件推断音频播放已实现 |
| 电池 | SM5714 测量接入 IOPMPowerSource；电量、电压、电流、充满及插拔状态更新 | 充电策略、输入限流、USB-PD 和完整温控尚未接管 |
| 亮度、锁屏、唤醒、关机 | 46l 有用户确认；源码有 DSI 命令、MAX77816、亮度和触屏局部电源协调 | 不等于系统 suspend/resume；后续 GPU 阶段继续修改关机资源清理，不能把早期结果扩展成所有版本均已验证 |
| USB 调试、网络 | CDC 日志/命令/线程栈；ECM 的 Mac en9 与设备 unet0 建链；原生 debugserver 附加 SpringBoard、全线程回溯及 detach | ECM 是 USB 网络；原生首次配对、完整 Xcode 服务、USB host 和部分端点恢复尚未完成 |
| MSC 更新 | 通过 UEFI MSC 写完整 512 MiB 启动 FAT 并 sync，保留系统卷及 Data | BOT reset/失败传输恢复仍有缺口 |
| GPU、Vulkan、Metal、显示 | Adreno 642L/GMU/SMMU、Turnip 离屏回读、系统 Metal 合成、DPU 扫描均有实机记录 | 不是完整 Metal family 认证；颜色和卡顿尚有待确认的问题 |

非 GPU 项目的主要依据为固定版本的
[DRIVERS.md](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab/docs/DRIVERS.md)、
[porting.toml](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab/porting.toml)、
[DisplayPower.cpp](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab/package/T733Display/DisplayPower.cpp) 和
[T733Battery.cpp](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab/package/T733Battery.cpp)。
DRIVERS 的更新日期停在 10 月 27 日，部分亮度待办与 46l 用户确认互相滞后；
porting 的 GPU 条目也落后于后续运行记录，故不能直接照抄勾选状态。

## README 之后的主要提交

| 时间／提交 | 实际进展 |
| --- | --- |
| 10 月 26–28 日，50–63 系列 | Vulkan 离屏、系统 Metal/DPU、BO 复用、硬件一致性、异步任务/timeline、显示读占用与 fence；过程中有回归和修复 |
| [7101c0f](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/7101c0f328b130805ddeb1b885d07d19b018f5e3) | 64a 实机 GPU 时间线：20 秒、886 样本、276 jobs，无丢失及复位 |
| [8e109a1](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/8e109a1a65a03815a48f797b5cfc6441d4c0bec4)、[203964a](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/203964aad591e564f22acd4c95d99839f8c9f90c) | USB Ethernet DMA 合批、GPU 记录流式采集和文件导出；不是无线网络 |
| [a5e3501](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/a5e35015bdace0946ac944969c8180586e36ed38)、[71d2a05](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/71d2a05e4fbe5408c473e12419fcc0e75ef42807) | 阻塞内核栈、任务分页、UFS 请求及 zone 扩展诊断 |
| [bcbfef0](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/bcbfef07179fc55e54a6ac3520ba86202254c55f) | 图形客户端退出清理和卸载文件系统前释放显示资源；提交本身不是新的关机实测证明 |
| [6cc3c2c](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/6cc3c2c28e27b8e78e73b9edb8b0e0cba0a21a38) | GPU 315/450/550 MHz、匹配 DDR 投票和温控上限；随后有 60 秒实机调档采集 |
| [0553707](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/055370743efeeabf962d39812b01bb71f5508ba5) | 72c 消除不必要的 memoryless pass 分段，有匹配 GPU 阶段测量；不能换算成全局 FPS 提升 |
| [e430f3d](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/e430f3d1dee37aabd538b9a49edd012b4c48b706) | 74e 恢复系统 GPU 渲染：150 提交完成、fault/timeout 为 0，367 次显示完成成功；用户仍报告红蓝异常和卡顿 |
| [4379151](https://github.com/RigoLigoRLC/unixnu-sm-t733/commit/4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab) | 76b 同步上游，九阶段构建及 MSC 部署；启动发布 Metal，SB/BB 运行，1247 显示完成、failed/errors=0、1200 DPU flips；可见颜色与交互仍等用户观察 |

最新详见 [76b 运行记录](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab/docs/GPU_UPSTREAM_REBASE_76_2026-11-04.md)。
GPU DVFS 实测见 [71 记录](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab/docs/GPU_DVFS_71_2026-10-31.md)，
同步及 pass 分段见 [72 记录](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/4379151e85f4a3bc5fd6011b4e79fe7d8be5a3ab/docs/GPU_SYNC_CAPTURE_72_2026-10-31.md)。
这些采集记录明确有部分 producer/metadata 丢失；所报收益仅适用于完整保留的匹配阶段。

Apple3 扩展在独立 `unixnu-sm-t733-apple3` 分支，包含参数编码、ICB、细分曲面、
深度 resolve、PVRTC GPU 解码等源码实施记录。构建通过、接口存在、supportsFamily
返回值均不能证明完整能力表通过；76b 主分支更新也没有把 Apple3 分支认定为实测完成。

## 尚未实现及 T970 的采用范围

未找到 Wi-Fi、Bluetooth、S Pen、系统音频、麦克风或整机 suspend/resume 已完成的
提交及实机证据。驱动清单仍将它们列为后续任务；USB ECM 不能算作 Wi-Fi 完成。

T970 保持内存、侧键、电池、亮度和 Wi-Fi 的当前目标，GPU 仍暂缓。
以本次核查补充 USB CDC/ECM/LLDB、持久 Data、正常关机、MSC 日常更新、
CPU 调频和温度管理的后续验收目标；每项仍需 T970 自身的镜像和实机记录。

可借鉴 IOPMPowerSource 属性发布、显示电源协调、HID、USB 调试协议及 UFS/Data
生命周期。先检查组件接口和各文件许可，再决定复用边界。SM7325 的地址、时钟、
中断和器件配置不能直接用于 SM8250。尤其是：

- T733 电池 SM5714，T970 电池 MAX77705；可参考系统服务层，寄存器协议不同。
- T733 无线 WCN6750/ICNSS2，T970 QCA6390/PCIe/MHI/ath11k；两者都不能由 ECM 替代。
- T733 面板电源使用 MAX77816；T970 S6TUUM3 亮度命令、映射及继承状态需独立核对。
- T733 约 4.236 GiB 的读数不能证明 T970 能管理全部 8 GB；后者仍要取得真实 EFI 所有权及保留区证据。

本次只保存参考核查，没有引入 T733 驱动、改变硬件配置或刷入镜像。
