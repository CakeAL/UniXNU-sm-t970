# 第 3 步：设备仓库七项验收

范围为 SM-T970 的 **CPU0／initrd 平台引导输入**。第 3 步要求建立具体设备仓库，
后续 XNU／iPadOS 实机启动与外设实现分别使用适配记录的完成等级；不相互替代。

原始审计基线 `6d3012ab3fbbbb3d4517d1a4ed4ccb87b795a028` 确实缺少固件接入和清单输入。
本次已经补齐下表文件，移除示例标记，并进入提交后的主机复核；最终检查结果单独归档。

| 项 | 已完成的仓库内容 | 后续独立验证 |
| --- | --- | --- |
| 1. `board.toml` | 设备名／kit、SM8250、OS profile、DTS 和固件 config／DSC／FD 均有具体输入。五组件及 8 条继承归档配方完整；T970 DSC/FDF 与配置存在并已编译出 3 MiB FD。 | UEFI 实机入口、GOP 与内存交接。 |
| 2. `feeds.toml` | SoC URL／完整提交和五组件固定版本已填写，`board.soc`、`soc_source`、DTS include 一致；固件及嵌套子模块提交另有精确清单。 | 发布后的远端可获取性及 CI。 |
| 3. 名称、配置和补丁 | `sm-t970_defconfig`、`device:dts/sm-t970.dts` 与真实文件一致；三个配置片段和四层 series 解析出 61 个补丁。 | XNU 编译和预链接。 |
| 4. DTS | 实测高 RAM 中排除相机 CMA 窗口后的 2 GiB 子区间、30 个静态保留区、CPU0 和禁用外设输入已填写。检查原厂动态池分配窗口和 XBL 区域与高 RAM 不相交；对照实机 DT 核对七组控制器范围和 IRQ。 | 实际 UEFI 分配、DMA 所有权；外设启用前的时钟／电源／ABI 实现。 |
| 5. 固件清单 | 共 130 项来源与 SHA256：43 份文件系统资产、3 份本机内核 builtin 固件、84 份候选 UEFI 的 PE32／DEPEX／RAW 输入。触控／笔／键盘已通过重定位表解析补齐。 | 未启用的无线 board-data 变体选择、驱动消费接口和加载验证。 |
| 6. 记录及模板文件 | 身份一致，13 个部分覆盖五组件及依赖，归属路径指向实际文件；README、AGENTS、工作流、忽略规则和 `local.toml.example` 保留。package 具有实际固件代码／配方。 | 远端 CI、公开发布和设备页面同步。 |
| 7. 示例标记 | 必要占位输入已经替换，已移除 `board.example = true`，允许正常主机构建／打包。 | 该标记不代表固件或 iPadOS 已通过实机验证。 |

所有未启用的外设仍为 `planned`。禁止仅通过填入其他板型的寄存器／固件或提高记录等级
清空待办。设备仓库输入完成与整个移植完成是不同结果。

## 核对范围

- 官方模板全部 13 个文件均有对应的受版本控制文件。重命名映射为
  `configs/example_defconfig` → `configs/sm-t970_defconfig`，
  `dts/board.dts` → `dts/sm-t970.dts`。
- 实际配置没有 `REQUIRED_`、零 RAM 或 SM8550 输入。真实设备身份种子和生成文件留在
  本机配置／忽略目录；主机测试用身份 `1`，不作为启动输入。
- 当前组件：`ArmDTPlatform`、`ArmCpu`、`SoftwareAES`、`XnuPrelink`、`DarwinBoot`。
  SoC／组件／架构／OS 输入继续按选型快照核对。
- 主仓库从原审计提交推进到 `194aae294c1107e791f4f74b2be371a391ac6bc4`，仅增加
  经过测试的 raw kernel／Android v2 独立 DTB 打包支持；组件与内核补丁选择不变。
- 空板级 XNU series 仍有效。板级 package 现在提供实际 T970 固件 overlay；未声明已有
  XNU 存储、输入、GPU、网络、音频或电源服务。

## 复核命令

从设备仓库执行：

```sh
python3.14 ../UniXNU/unixnu defconfig sm-t970_defconfig -D .
python3.14 ../UniXNU/unixnu status --json -D .
python3.14 scripts/check-platform.py --unixnu ../UniXNU
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

固件构建／提取和独立 FDT 要求见[固件说明](firmware.md)。实际构建报告应记录设备提交、
主仓库和固件版本、输入哈希、FD 大小及镜像回读结果。不要把后续缺少 kernelcache／
信任／Data 等负载输入的错误误判成模板仓库标记仍未解除。

## 为什么之前没有完成

之前的工作停在模板结构、两份 GPU 固件和只覆盖静态保留区的主机检查，没有继续使用
已授权的 ADB 去补齐本可取得的输入，也没有建立 T970 固件 overlay。该阶段确实未完成。
此外，旧设备说明把“解除示例标记”绑到后续实机验证，比创建仓库步骤要求更强，混淆了
配置完整性与硬件验证等级。这次补齐真实来源和实现，允许主机构建，保留真实验证限制。
