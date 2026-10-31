# SM-T970 存储（UFS）适配分析

第 6 步按依赖顺序先处理存储。本页记录实测输入、目录中唯一存储实现的适配性判断，
以及继续实现所需的工作；`porting.toml` 的存储部分仍为 `planned`，没有启用任何驱动。

## 已采集的板级输入

完整机器可读版本见 [board-inputs.json](../evidence/storage/board-inputs.json)，由
`scripts/collect-storage-inputs.py` 从实机 DT、GPT 快照和 Qualcomm kona 头文件生成。

| 项目 | 值 |
| --- | --- |
| 控制器 | `qcom,ufshc`，`0x1d84000+0x3000`，ICE `0x1d90000+0x8000`，中断 `<0 0x109 4>` |
| PHY | `qcom,ufs-phy-qmp-v4`，`0x1d87000+0xe000`，双向各 2 lane |
| 时钟 | GCC `UFS_PHY_AXI_CLK`(167)、`AGGRE_UFS_PHY_AXI_CLK`(6)、`UFS_PHY_AHB_CLK`(166)、`UFS_PHY_UNIPRO_CORE_CLK`(179)、`UFS_PHY_ICE_CORE_CLK`(170)、TX/RX symbol 时钟；`ref_clk` 为 RPMH `RPMH_CXO_CLK`(0) |
| 复位 | GCC `GCC_UFS_PHY_BCR`(33)，名为 `core_reset` |
| 供电 | `vdd-hba`→`qcom,gdsc@177004`；`vcc`→pm8150-l17；`vccq`/`vddp-ref-clk`→pm8150-l6；`vccq2`→pm8150-s4；`vccq-parent`→pm8150a-s8；PHY `vdda-phy`→pm8150-l5、`vdda-pll`→pm8150-l9 |
| SMMU | 实测 UFS 节点**没有** `iommus` 属性 |
| 布局 | 4 个 LUN、逻辑块 4096、GPT CRC 均通过；`userdata` 起始 LBA 2969600 |

时钟/复位 ID 与 `include/dt-bindings/clock/qcom,gcc-kona.h`、`qcom,rpmh.h`
（LineageOS sm8250 内核 `lineage-24.0`）逐项核对；采集器记录头文件 SHA256。

## ShengUfs 是否可用：暂不可用

目录中唯一的存储驱动是 [ShengUfs](https://github.com/UniXNU/ShengUfs)，目录声明
`hardware = ["SM8550 UFS controller"]`。对照实测输入：

| 对比项 | ShengUfs（SM8550） | SM-T970 | 结果 |
| --- | --- | --- | --- |
| 控制器 | `0x1d84000+0x3000` | 同 | 匹配 |
| PHY | `0x1d80000+0x2000` | `0x1d87000+0xe000` | **不匹配** |
| 时钟策略 | SM8550 常量 | UFS_PHY 组 + ICE 时钟 | 需重写 |
| SMMU | 固定 apps-SMMU stream `0x60` | DT 无 `iommus`，所有权未知 | **未确定** |
| ICE | SM8550 方案 | `0x1d90000+0x8000` | 需实现或证明可关闭 |
| userdata | LBA 3094592..64007162（sheng） | 从 2969600 起 | 必须按本机 GPT 重算 |

同时确认目录中没有现成的 SM8250/kona UFS 实现：共享 SoC 仓库只有禁用的
`ufshc@1d84000`／`phy@1d87000` 节点，`UniXNU-pipa`（同为 SM8250）只有
`package/SmmuBypass.h`，没有 UFS 或存储驱动。

因此**不选择 ShengUfs**；把它的 SM8550 常量直接套到 T970 会写错 PHY 窗口、时钟与
SMMU 所有权。存储部分保持 `planned`。

## 继续实现所需工作

1. 把控制器初始化移植为 `qcom,ufshc` + QMP PHY v4（`0x1d87000+0xe000`）的序列，
   使用上表的时钟/复位 ID；或明确记录固件状态接管的依据。
2. 确定 SMMU 归属：从固件或原厂内核读取 UFS 的 stream/context，而不是沿用 sheng `0x60`。
3. 处理 ICE `0x1d90000+0x8000`，或证明可保持关闭并记录依据。
4. 按本机 GPT 重算 userdata/根卷窗口，不使用 sheng 的 LBA。
5. 提供存储 ABI 输入、archive 配方与根卷策略，然后构建内核。

## 验证计划

| 阶段 | 当前 | 需要的观察 |
| --- | --- | --- |
| 硬件清单 | 已完成（本页 + JSON） | 每项有来源与责任方 |
| 控制器访问 | 未开始 | 寄存器可读，时钟/链路状态符合初始化方式 |
| DMA 与命令 | 未开始 | 缓冲区可达，完成与失败均被处理 |
| 块读取 | 未开始 | 容量与已知块匹配 LUN／逻辑块大小 |
| 根卷 | 未开始 | GPT 与根卷窗口正确，挂载并启动用户态 |
| 持久化 | 未开始 | 写入限于 Data 区域，重启后保留 |

## 下一步

存储不再是从零开始：以 umi 的 NativeUfs（双 stream `0x0e0`/`0x4e0`、固件接管）为基，
在 `feeds.toml` 固定 T970 fork 后先做只读探测，再按本机 userdata 窗口发布根卷。
显示与触摸同样有可复用起点：umi 用 CPU framebuffer 显示，并用 ST FTS 驱动触摸，
与 T970 的 `stm,fts_touch` 同族。不要直接复用其他板型的 userdata 参数或镜像。
