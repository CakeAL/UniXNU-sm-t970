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
- 电源/时钟：GPUCC（`0x3d90000`）、CX/GX GDSC（`0x3d9106c`/`0x3d9100c`）、
  ARC `cx.lvl`/`mx.lvl`、RPMh 投票、OPP（305–670 MHz，7 档）；
- GMU：`a650_gmu.bin`（41548 B）、GMU 窗口 `0x3d6a000+0x30000`、HFI 队列/版本、
  `a650_sqe.fw`（31632 B）；
- ZAP：`a650_zap` 分片签名镜像、PAS/SCM 认证；
- SMMU：T970 apps SMMU 的 GPU SID/上下文，按本机 SMMU 只读证据确定；
- CP/hwinit/RBBM：A650 的启动表和中断位；
- 显示：当前是 GOP + CPU 拷贝；GPU 画面要经 DPU scanout（lmi 的异步 DPU 可参考）。

## 对照 UniXNU 指南

按 [GPU 与 Metal 适配](https://unixnu.com/zh/porting/gpu)的验收项记录。
T970 已确定 A650 与 21H461，原厂 GMU、SQE 和 ZAP 已记录来源与哈希。
电源和时钟的前置实测已完成，v129 验证 GMU 启动，v130 验证 HFI 应答。
GMU 启动依赖 SMMU，因此先做指南第 3 步开头的上下文和流验证，再完成第 2 步的 GMU/HFI 验收。
当前探针使用 ArmSmmu4K 建表、走查及同步。原厂 GMU kernel 使用掩码匹配，
板级探针依原厂设备树和 lmi 处理 SMR/S2CR。后续在固件/HFI 和命令提交路径分别接入
AdrenoFirmware 与 AdrenoPM4，再验收 ring、fence、已知图像和 iPadOS Metal 接口。

## 阶段与验收

| 阶段 | 内容 | 设备证据 |
| --- | --- | --- |
| 0 | 资源/固件/候选源对照（v99 起） | 报告 `GPU arc` 行、DT/固件哈希 |
| 1 | GPUCC/GDSC/供电/TSENS 资格确认 | v104 读到 GPUCC，v105 确认 CX 上电和恢复，v106 确认 XO 分支运行与恢复 |
| 2 | GMU 冷启动 + HFI 版本回读 | [v130 实测通过](../evidence/gpu/hfi-version-v130/device-result.json) |
| 3 | ZAP 认证 + secure mode 退出 | 认证结果 |
| 4 | SMMU/GPU VA + CP ring/fence | GPU 内存写入回读 |
| 5 | tile/GL 探针 | 已知像素精确匹配 |
| 6 | 桌面/DPU + 17.7.11 Metal ABI | 系统合成上屏 |

## 电源与时钟进度

`package/T970Gpu/ArcResources.h` 只读解析 ARC cmd-db（`0x80860000+0x20000`，
触摸/RSC 路径已映射过该块），报告新增 `GPU arc db= cx= lv= min= mx= ...`。
它验证 GPU 的 CX/MX 电压档资源路径，不请求 RPMh、不写寄存器。

v99 首次上机时报告缓冲（896 字节）被前面的 display/UI/Data-space 文本占满，
GPU arc 行没有写入；v100 把 `display_state` 扩到 1280 字节，保持探测与参数不变。

v103 实测 GPLL0 600 MHz，GCC `0x152000` 的 DIV_GATE 置位和恢复均成功。
v104 实测 CFG AHB 为 `0x1`，GPUCC 可读。CX/GX GDSCR 均为 `0x222001`，
CX 硬件状态 `0x5ff4`，各上电位均为 0。内部 AHB、GMU、SMMU 时钟的 CLK_OFF 位为 1。
GX 的 `0x3d91508` 是 clamp 控制，GX GDSCR 位于 `0x3d9100c`。
见 [v103 门控实测](../evidence/gpu/clk-write-v103/device-result.json)和
[v104 GPUCC 实测](../evidence/gpu/power-v104/device-result.json)。

v105 实测 CX 从 `222001/5ff4` 变为 `f8222000/80001fe0`，随后回到原状态。
v106 实测 `rcg=80000000/1 br=1/1/4221 mask=7/7 cx=1/1`，AHB、CXO、CX GMU
三条分支在 CX 期间运行，原分支投票与 CX 均恢复。见
[v105 实测](../evidence/gpu/cx-v105/device-result.json)和
[v106 实测](../evidence/gpu/xo-v106/device-result.json)。

v107 实测 GMU 可读，CM3 仍在 reset、FW_INIT=0，AO 从 `0x1440` 推进到
`0x6b66`，XO 与 CX 恢复。v108 实测 DRV0 `4000000a`、十个 TCS 空闲，hidden
命令、路由、空序列 SRAM 和 PDC `0/100` 均匹配 lmi mode 24 的冷态。
见 [v107 实测](../evidence/gpu/gmu-v107/device-result.json)和
[v108 实测](../evidence/gpu/rsc-v108/device-result.json)。

v109 实测 SDE、五个 RSC SRAM 字、PDC start/enable 全部写入并恢复，`wr=ff restore=ff`。
v110 实测 GPU DRV0 TCS1 依次完成 MX、CX 的 selector 2 请求，两者应答 `0x10101`，
TCS 和控制寄存器恢复。v111 实测 GMU 200 MHz 路径回读 `1/100602/1`、UPDATE 清零，
恢复 XO 和分频门控成功。v112 实测 GPU SMMU 的 ID 和布局与 lmi 一致，六个 SMR
全零，CB0 禁用且读数稳定。v113 实测 CBA2R.VA64 置 1 后触发写后空闲检查，
保留了上游依赖。v114 采用 lmi 的显式 32 位 MMIO 读法，定位到唯一触发项是
CB0 FSR `0x400`。Arm SMMUv2 将 FSR[10:9] 定义为 Format，实际故障位为零。
v115 从故障守卫中排除 Format，并在回读时核对 VA64、原始 FSR 和完整 CB0 状态。
v115 实测 `va64=0/1/0 rb=1 guard=0/0 diff=0`，上游依赖也已恢复。
v116 直接编译 UniXNU 目录固定的 ArmSmmu4K 源码，使用 XNU 分配的物理连续内存
建立并走查 GMU/HFI 页表，实机确认 5 张表、42 个映射页和 2,560 个描述符。
v117 实测 CBAR 切换到 Stage 1 后保持 `0x1f300`，写回零未生效。
VA64 已恢复为零，CBAR 守卫仍触发保留。v118 实机确认 Stage 1 精确保持、其余状态
连续两次匹配，随后释放了上游依赖。v119 实机确认两个 TTBR 的 64 位读、写和恢复。
v120 实机确认翻译关闭时可以安装、走查并撤销 XNU 页表。v121 实机确认在 CM3 复位、无流时
可以完成两次本地 TLB 同步和 CB0 启停。v122 实机确认原厂 DT 的 SID5/mask `0x400`
可发布至 CB0 并撤销。v123 实机确认固定 A650 固件的 ITCM/DTCM 与 RAM 装载和回读，
TCM 恢复无差异，版本字为 `0x20010008`。
v124 复用 T970 的 RSC 路由和 v122 的 SID5，把四队列 HFI 布局随固件发布，
随后释放 CM3 并检查 FW_INIT 和 HFI 就绪。加载后保留 DMA 内存和依赖至重启。
v124 实机在 DDR AXI 时钟关闭时返回。v125 在该范围请求 DDR AXI 时钟，
回读 ENABLE 与 CLK_OFF 后再进入 GMU 首启。
v125 实机把 DDR AXI 从 `80100000` 开到 `00100001` 并释放 CM3，但 `FW_INIT`
未出现；CB0 FSR 由 `0x400` 变为 `0x40000408`，按
[Linux arm-smmu 的 SMMU-500 定义](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/iommu/arm/arm-smmu/arm-smmu.h)
这是 AArch64 格式位加 permission fault（PF）和 stream stalled（SS）。
首个 GMU 总线访问已被翻译但被叶权限拒绝，11 个配置回读和致命位都正常。
v126 在首启轮询中保留该次故障的 FSR/FAR/FSYNR0/SID，并只按故障类型
放宽对应 4 KiB 叶的 AP/XN 位，清理该 ASID 的 TLB、清除故障后重试；
非权限故障、页表走查故障或范围外的页一律不修。
v126 实机在报告线程里踩到栈底保护页：三指探测链的帧和约 12.8 KiB，
加上报告线程自身超过 16 KiB，panic 为 invalid kernel stack pointer。
v127 保留模式 23 的语义，把快照改为写入调用者对象、把固件规划数组移入
BSS，链上帧和降到约 8.3 KiB 后再取首启报告。
v127 实机报告成功，SID5 特权取指在 `0x153e00`、`0x154600` 触发
权限故障，FW_INIT 仍为零。v128 在发布页表前给两页所在的 19 页 GMU
临时 RAM 段加入执行权限，并记录完整的 64 位叶描述符。
v128 实机仍在 HFI 队列和电源日志起始页报告 IND。继承的 S2CR0 将
INSTCFG 设为 3，覆盖了匹配流的读请求属性。v129 在发布 SID5 时将
INSTCFG 设为 0，使用请求原有的属性，再以原始 XN 页表验证 GMU 首启。
见 [Arm SMMUv2 §3.4、§9.6](https://documentation-service.arm.com/static/5f900d34f86e16515cdc08fb)。
v129 实机确认 `s2=1038eb00 fw=100 hfi=1/20000001 rst=0 pf=0`。
v130 实机确认 `FW_VER` 应答 `10401/100201/0/20010008`、
命令游标 `4/4`、中断由 `1` 清为 `0`，验证 GMU 与主机之间的双向 DMA。
下一步验证性能表、带宽表和 `CORE_FW_START`，再进入 GX、ZAP 和 CP。
v131 复用实测通过的 `FW_VER` 传输，按本机原厂 OPP 和 live ARC cmd-db
构建并发送一张 legacy `PERF_TBL`，单独验收性能表应答。
CM3 启动阶段需保留 T970 的 RSC 路由，且核对 A650 的 HFI 队列布局。
锁定的 Sm8250Platform 冷启动序列会写入固定的 hidden 值，集成时需处理与实测路由的差异。
见 [v109 实测](../evidence/gpu/rsc-init-v109/device-result.json)、
[v110 实测](../evidence/gpu/arc-vote-v110/device-result.json)、
[v111 实测](../evidence/gpu/gmu-rate-v111/device-result.json)、
[v112 实测](../evidence/gpu/smmu-v112/device-result.json)、
[v113 实测](../evidence/gpu/cbfmt-v113/device-result.json)、
[v114 实测](../evidence/gpu/cbguard-v114/device-result.json)、
[v115 实测](../evidence/gpu/cbrestore-v115/device-result.json)、
[v116 页表实测](../evidence/gpu/gmu-tables-v116/device-result.json)、
[v117 CBAR 实测](../evidence/gpu/cbbar-v117/device-result.json)、
[v118 释放实测](../evidence/gpu/cbrelease-v118/device-result.json)、
[v119 TTBR 实测](../evidence/gpu/ttbrwidth-v119/device-result.json)、
[v120 页表接入实测](../evidence/gpu/cbroot-v120/device-result.json)、
[v121 启停实测](../evidence/gpu/cbactivate-v121/device-result.json)、
[v122 SID5 实测](../evidence/gpu/sid5-v122/device-result.json)、
[v123 固件装载实测](../evidence/gpu/gmufw-v123/device-result.json)、
[v124 首启探针](../evidence/gpu/gmuboot-v124/README.md)、
[v125 DDR AXI 探针](../evidence/gpu/gmuboot-axi-v125/README.md)、
[v125 首启实测](../evidence/gpu/gmuboot-axi-v125/device-result.json)、
[lmi RSC 实现](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-rsc-init.c)
和 [SM8250 GMU 实现](https://github.com/FFT-infra/UniXNU-sm8250-common/blob/166235ec2480ff0992627b7aafa15c65ce6b4efa/kits/Sm8250Platform/A650Gmu.c)。

## 风险

- GPU/GMU 窗口在未上电时 MMIO 读可能挂死，必须先做时钟/电源资格；
- `a650_gmu.bin`/`a650_zap` 是专有固件，仓库只有哈希，需从本机 stock 自带；
- 17.7.11 的 Metal/GPU 用户态 ABI 与 lmi 的 16.5 RedwoodGPU 路径不同，后半程需重新审计；
- 参考项目本身也不是成品（lmi 整体 INCOMPLETE；T733 GPU 有回归记录）。
