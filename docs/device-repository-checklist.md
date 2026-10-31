# 第 3 步：设备仓库核查

核查依据：UniXNU `04b4e558bcded5213c2d802984862dc062f28257` 中
`docs/zh/porting/steps.md` 第 3 步的七项要求和设备仓库完成清单。
本次检查的设备配置基线为 `6d3012ab3fbbbb3d4517d1a4ed4ccb87b795a028`。

**结论：设备仓库已建立，七项要求尚未全部完成。** 下表区分本地结构完成与仍缺的设备输入。

| 项 | 当前结果 | 已有证据及缺项 |
| --- | --- | --- |
| 1. `board.toml` | 部分完成 | `name/kit=sm-t970`、SM8250 来源、iPadOS profile、DTS 入口和五组件集合均已填写。完整继承 ARM64 的 8 条归档配方。`firmware.config`、`firmware.dsc`、`firmware.fd` 尚缺真实 T970 输入。 |
| 2. `feeds.toml` | 已完成当前选型 | SoC URL／完整提交已固定，另外固定五个组件。`board.soc=SM8250`、`board.soc_source=sm8250` 和 DTS 的 `sm8250.dtsi` include 一致。 |
| 3. 名称、路径、配置与补丁 | 已完成 | `sm-t970_defconfig` 与 `device:dts/sm-t970.dts` 均指向实际文件。三个配置片段和 arch／soc／os／device 四个 series 均存在，解析出 61 个补丁。 |
| 4. DTS 硬件描述 | 部分完成 | 已填写实测候选 RAM 窗口、CPU0 启用状态及 30 个静态保留区；GIC／定时器沿用核对后的 SoC 输入。UEFI 可分配内存、动态保留区和固件所有权未确认。板级外设仍禁用，未建立完整连接与 DMA／电源策略。 |
| 5. `proprietary-files.txt` | 原厂文件清单已扩展，仍有缺项 | 已通过 ADB 记录 43 个 GPU／Wi-Fi／蓝牙／音频资产的实际路径、大小和 SHA256。触控、笔和键盘的 DTS 固件名在五个文件系统根目录中未找到；无线板型数据的实际选择和 UEFI 厂商 DXE 集合仍待落实。当前单核阶段没有消费这些外设固件。 |
| 6. 记录、文档及模板文件 | 本地文件要求已完成 | `porting.toml` 身份与 `board.toml` 一致，覆盖当前五组件及其依赖。README、AGENTS、记录工作流、忽略规则、`local.toml.example`、`package/.gitkeep` 均已保留并受版本控制。官方记录检查器通过 13 个部分。此项不表示远端 CI、发布和硬件验证已经完成。 |
| 7. 移除 `board.example=true` | 条件尚未满足，保留 | 前述固件路径和实际内存交接输入未齐全，因此暂不移除。实际调用 `build kernel` 和 `bootimg` 均以 exit 1 拒绝示例配置，未进入构建或打包。 |

## 核对范围

- 官方模板全部 13 个文件均有对应的设备文件，重命名映射为
  `configs/example_defconfig` → `configs/sm-t970_defconfig`、
  `dts/board.dts` → `dts/sm-t970.dts`。
- 实际配置文件中没有遗留 `REQUIRED_` 值或 SM8550 板型输入，RAM 也不是零范围。
  输入缺失通过省略固件路径、适配记录中的限制和 `example` 标记明确表达。
- 当前组件集合为 `ArmDTPlatform`、`ArmCpu`、`SoftwareAES`、`XnuPrelink`、
  `DarwinBoot`。选型快照、feed、目录及实际源码版本已在第 2 步核对。
- 空的板级 patch series 和 `package/.gitkeep` 是有效模板结构，不代表已经实现了
  板级服务。未来启用外设时必须补齐实际代码、归档、初始化和 ABI 输入。
- 本机覆盖文件、缓存和生成目录处于忽略范围，没有为通过核查改写硬件参数。

## 可复核命令

从设备仓库执行：

```sh
python3.14 ../UniXNU/unixnu status --json -D .
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

当前配置下，以下命令**预期失败**，应输出 `EXAMPLE device repository`：

```sh
python3.14 ../UniXNU/unixnu build kernel -D .
python3.14 ../UniXNU/unixnu bootimg -D .
```

这些拒绝只验证当前配置标记生效，没有执行内核编译、固件打包或设备操作。

## 收尾条件

第 3 步完全完成前，需要确定真实的 T970 UEFI 配置／DSC／FD 路径，落实可用的
RAM／保留区交接方案，并按实际启用的组件补齐所需板级与固件输入。
之后重新检查记录、配置和补丁／归档选择，再移除 `board.example=true`。
未启用的外设仍可作为明确的后续适配项，不需要为了清空待办而虚构实现。

第 4 步的配置解析可以继续独立核查；其通过不能替代这里尚缺的固件和硬件输入。
