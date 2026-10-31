# 第 2 步：选择共享支持

当前选择面向 **SM-T970 单核平台起步阶段**，结果是固定来源和明确的待完成事项。
它不表示这些组件已在 T970 上运行，也不表示 UEFI 或外设适配已经完成。

## 配置层与精确版本

| 层 | 来源与版本 | 本设备采用的范围 |
| --- | --- | --- |
| ARM64 与构建工具 | `UniXNU/UniXNU`，`04b4e558bcded5213c2d802984862dc062f28257` | `profiles/arch/arm64`，4 KiB 页配置、通用归档配方和补丁 |
| SoC | `FFT-infra/UniXNU-sm8250-common`，`166235ec2480ff0992627b7aafa15c65ce6b4efa` | SM8250 DTSI、CPU affinity、GICv3、19.2 MHz 定时器和两项 CPU 补丁 |
| OS | 同一 UniXNU 提交中的 `profiles/os/ipados-17.7.11-21H461` | 复用现有 iPadOS profile，不建立新 OS profile |
| XNU | `apple-oss-distributions/xnu`，`d8b80295118ef25ac3a784134bcf95cd8e88109f` | XNU 10063.141.1／Darwin 23.6.0；尚未编译 |
| 设备 | 本仓库的 `board.toml`、DTS、固件清单与适配记录 | 只启用 CPU0；内存和外设连接取自设备证据 |
| UEFI | 尚未选定可用于 T970 的实现 | 已核对的上游候选及缺口见下文；不编造 DSC、FD 或设备配置路径 |

SoC 和五个选中组件的完整 Git URL／提交写入 `feeds.toml`。主仓库必须使用上表的
已核对版本；其组件目录提供元数据和配方。现有源码 checkout 可以优先于 feed，
因此平台检查会核对设备 feed、组件目录和实际 checkout 的提交，并拒绝不一致。

该 SoC 提交的 `soc.toml` 实际只声明 SoC 元数据；虽然其 README 提到选择平台组件，
本设备明确在 `board.toml` 中列出完整五组件集合，不依赖这段 README 描述。

`evidence/shared-support/selection.json` 保存本次选型快照，包括主仓库提交、架构／OS
profile 的 SHA256 和组件版本。平台检查会拒绝主仓库版本或这些 profile 的漂移；
以后有意更新来源时，需要重新审核并同步更新这份快照。

## 已选组件

| 组件 | 固定提交 | 匹配依据及接入阶段 |
| --- | --- | --- |
| `ArmDTPlatform` | `417ff95d6a6e8607ddea9309ec45c3bfd4a67c60` | ARM64 ADT 平台专家；匹配 `IOPlatformExpertDevice`／`device-tree`，发布必需节点；内核归档 |
| `ArmCpu` | `9066b53bbc82e92a98ec44a11dd50fd13eaf1a1b` | 实测 GICv3、架构定时器和 SoC affinity；通过 `IOPlatformDevice` CPU nub 启动；内核归档 |
| `SoftwareAES` | `4a45326da5c2cd6fe6813d79ee43db20805628af` | 目录声明支持所选 iPadOS ABI；实现 `IOAESAccelerator` 软件 AES；私有布局和实际预链接仍待验证 |
| `XnuPrelink` | `f876e3ee62e18fc06653dd75ed7dafcfb3950ac0` | 采用 OS profile 的 kernelcache、root bundles、slide 与补丁；预链接工具 |
| `DarwinBoot` | `3325e352d7df68a9f9ad74832ed94a6acbbd7390` | ARM64 UEFI 加载器；接收 Mach-O、ADT 和 sidecar；尚未加入 T970 固件 |

目录中这五项的 `dependencies` 均为空，因此当前组件集合依赖闭合。归档沿用 ARM64
完整列表，三个内核组件分别由 `component:ArmDTPlatform`、`component:ArmCpu`、
`component:SoftwareAES` 接入。DarwinBoot 属固件阶段，XnuPrelink 属预链接阶段，
不能把配置选择理解为已经生成这些阶段的产物。

## OS、固件协议与 ABI 边界

复用现有 profile 的输入为 iPadOS 17.7.11／21H461、`iPad7,1`／`j120ap`，
DriverKit 头文件 tag 为 `xnu-10063.121.3`，TrustCache 头文件 tag 为
`xnu-8796.101.5`。本地 IPSW 的版本与构建号已从 BuildManifest 核对。

profile 固定解压后 kernelcache 的 SHA256 为
`f18b4df865405f2a287b84977d7aca745e056d656d9fc9df1662970ce2969de7`。
目前尚未提取并校验这个 kernelcache，也没有完成组件的私有 ABI 审计、编译和预链接。
Data seed、trust cache、根卷策略和真实平台身份输入仍待准备。

SoC 中的 A650 GMU 操作使用 `A650Gmu*`、HFI 及板级 IO／电源回调；它不是完整的
A650 渲染后端。T970 的 GMU／SQE 固件已记录哈希，AOP command DB、OPP／带宽、
安全固件选择和 SMMU 所有权还未核对，因此不启用 GPU。

## UEFI 候选核对

核对上游 [Project-Silicium/Mu-Silicium](https://github.com/Project-Silicium/Mu-Silicium/tree/4bd8ae83bf37de41777f19e0777db70f59383a6d)
的固定提交 `4bd8ae83bf37de41777f19e0777db70f59383a6d`：

- `Silicon/Qualcomm/KonaPkg` 存在，可作为 SoC 固件支持的参考。
- `Platforms/Samsung` 中有 `r8qPkg` 等平台，没有 `gts7xlwifi`／T970 平台目录。
- `Resources/Configs` 中有 `r8q.toml`，没有 T970 对应配置。
- `r8qPkg/r8q.dsc` 描述 Galaxy S20 FE、1080×2400 framebuffer，引用 KonaPkg；
  `Resources/Configs/r8q.toml` 使用 Android boot header v1。T970 实测为 v2，
  且面板模式为 2800×1752，因此不能直接采用这些板级参数。

这只是对上述上游固定提交的检查，不代表所有第三方分支都没有 T970 移植。
候选不写入设备构建 feed，也不冒充已选定的 `uefi-sm-t970`。
目录证据见 `evidence/shared-support/uefi-candidate.json`。

## 暂不选择的实现与待完成工作

| 能力 | 候选范围与当前决定 | 下一项工作 |
| --- | --- | --- |
| DMA | `ArmSmmu4K` 需要实例、stream、context 和读回所有权 | 对照 T970 SMMU 与固件状态后再选择 |
| UFS／根卷 | 目录中的 `ShengUfs` 声明 SM8550／sheng 时钟、SMMU 和分区依赖 | 审核 SM8250 控制器、PHY、时钟、电源和实际分区策略；不沿用 sheng 布局 |
| RAM／VirtIO 块设备 | `RamBlock`、`VirtioMmioBlock`、`VerifiedRoot` 取决于存储与信任方案 | 先确定根卷和 Data 的传输、持久化及 owner policy |
| 显示 | `GopFramebuffer` 需要真实 GOP、帧缓冲与电源回调 | 在 T970 UEFI 下测地址、stride、格式和亮度连接 |
| 触控／笔 | `ShengNovatekTouch`／`QcomGeniSpi` 面向 Novatek／SPI；T970 为 STM FTS／I2C 与 Wacom | 审核对应 I2C 控制器和两种传感器协议；另行实现 HID 接入 |
| GPU／Metal | `Adreno740` 是 A740 后端，`AdrenoMetal` 依赖它 | 补齐 A650 后端、电源、DMA、同步和所选 OS ABI 后再接前端 |
| Wi-Fi | `Ath12kWifi` 声明的硬件输入未覆盖当前尚有命名差异的 T970 endpoint | 核实 PCI 17cb:1101、实际固件和驱动系列，再做组件选择 |
| 音频／电源 | 板级 DSP、CS35L41、MAX77705／PCA9468 输入尚未形成可用接口 | 核对固件、路由、单位和电源所有者，不复制其他板的服务 |
| 固件平台 | 上游有 Kona／r8q 参考，但没有本次已核对的 T970 实现 | 建立／查明 T970 启动与恢复路径、内存图、面板初始化及日志通道 |

这些待办属于后续硬件或 ABI 工作，不要求在第 2 步声称已实现。
当前 `board.example=true` 和单核、外设禁用状态保持原样。

## 复核入口

在兄弟目录的 UniXNU 主仓库执行 `python3.14 ./unixnu status --json -D ../UniXNU-sm-t970`，
再运行本设备 `scripts/check-platform.py` 检查实际提交、OS ABI 声明和 DT／ADT 输入。
主机验证只确认所选配置范围，不确认设备驱动、固件协议或系统用户态已能工作。

本步主机检查已通过，精确的检查提交和输入哈希见
`evidence/shared-support/result.json`；配置解析结果与候选证据一同归档在
`evidence/shared-support/`。官方记录检查器通过全部 13 个部分。
