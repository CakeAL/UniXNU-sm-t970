# UniXNU — Samsung Galaxy Tab S7+ Wi-Fi (SM-T970)

设备代号 `gts7xlwifi`，SoC `SM8250`。目标系统为 iPadOS 17.7.11（21H461）。
本仓库按官方 `examples/device` 建立，保留设备的硬件输入、板级配置和适配记录。

## 仓库位置与职责

两个仓库并列放置；构建命令在主仓库执行：

```text
vsc/
├── UniXNU/                 # 构建工具、组件目录、ARM64 与 OS profile
└── UniXNU-sm-t970/         # 本设备配置、DTS、固件清单、package 与记录
```

- `board.toml` / `feeds.toml`：格式 2 配置、所选组件与固定的 SM8250 来源。
- `configs/sm-t970_defconfig`：本阶段的内核选项。
- `dts/`：板级 CPU 启用状态、候选连续 RAM 窗口和采集到的静态保留区。
- `package/`：后续板级服务；当前保留模板的空目录。
- `proprietary-files.txt`：43 个原厂 GPU、无线、蓝牙和音频资产的来源与哈希；当前单核阶段不消费这些资产。
- [porting.toml](porting.toml)：唯一的设备适配记录，包含 13 个部分。
- [evidence/README.md](evidence/README.md)：ADB 原始输入与采集方法。

## 当前阶段

最小单核平台配置选择 `ArmDTPlatform`、`ArmCpu`、`SoftwareAES`、`XnuPrelink`、
`DarwinBoot`。SM8250 来源固定到 `166235ec2480ff0992627b7aafa15c65ce6b4efa`；
本阶段核对的 UniXNU 主仓库版本是 `04b4e558bcded5213c2d802984862dc062f28257`。
共享控制器代码仍归 SoC 和组件仓库，设备仓库只提供板级输入。

第 2 步的来源、精确版本、组件复用范围和待完成事项见
[共享支持选择](docs/shared-support.md)。`feeds.toml` 已明确固定五个组件的提交；
选型快照同时固定主仓库版本和架构／OS profile 哈希。

第 3 步的七项核查见[设备仓库清单](docs/device-repository-checklist.md)。
目录结构及本地记录要求已满足，固件路径、完整硬件交接和示例标记收尾仍待完成。

只启用 CPU0，UFS、GPU、显示、触控及其他板级外设尚未接入。
DTS 使用 Android 实测的 `0x180000000 + 0x100000000` 连续内存段进行主机转换检查；
它尚未与 T970 的 UEFI 可分配内存和固件所有权核对。
`board.example = true` 因而保留，官方工具会拒绝构建内核/镜像。
T970 的 UEFI 配置、启动方法与固件路径仍待确定。

主机上的配置解析、DTS 编译和 ADT 检查已通过；报告见
[evidence/platform-bootstrap](evidence/platform-bootstrap/README.md)。这些检查不代表
XNU 编译或设备启动成功。

## 主机检查

需要 Python 3.11+、git、dtc 和所选依赖。下面用本机可用的 `python3.14`：

```sh
cd ../UniXNU
python3.14 ./unixnu defconfig sm-t970_defconfig -D ../UniXNU-sm-t970
python3.14 ./unixnu fetch sm8250 ArmDTPlatform ArmCpu SoftwareAES XnuPrelink DarwinBoot -D ../UniXNU-sm-t970
python3.14 ./unixnu status --json -D ../UniXNU-sm-t970
python3.14 ./unixnu tree -D ../UniXNU-sm-t970
python3.14 ../UniXNU-sm-t970/scripts/check-platform.py --unixnu .
python3.14 scripts/porting-record.py check --device ../UniXNU-sm-t970
```

`fetch` 明确指定本阶段依赖；编译内核还需要其他 Apple 参考源码与 ABI 输入。
主仓库的 `fetch/tree` 也会处理其 submodule。采集工具和平台检查脚本分别在本仓库
`scripts/` 下；平台检查结果写入被忽略的 `out/platform-check/`。
生成的 `host-check.adt` 使用人工测试身份，只供主机检查，不能用于启动。
真实 payload 的身份通过本机配置传入，不提交设备标识。

本机 GitHub Git 端点连接失败时，本阶段从官方 API/codeload 获取固定提交，
逐一验证完整源码树和提交对象的 Git 哈希后放入正常依赖缓存，没有更换源码版本。
临时使用 `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=submodule.active
GIT_CONFIG_VALUE_0=__no_module_submodules__` 限制无关 submodule 更新；该设置仅作用于
对应命令，没有写入 Git 配置。普通网络环境可直接执行上面的命令。

## 下一项实机工作

先确定 T970 UEFI 固件及恢复路径，取得固件内存图和帧缓冲交接参数，再移除
`board.example`。以单核内核日志为第一个硬件里程碑，之后才启用 SMP 与外设。
本阶段没有刷写、分区调整、重启或任何设备驱动寄存器操作。

- [移植步骤](https://unixnu.com/zh/porting/steps)
- [设备仓库](https://unixnu.com/zh/porting/device-repository)
- [驱动适配](https://unixnu.com/zh/porting/drivers)
- [平台与内存](https://unixnu.com/zh/porting/platform)
- [设备树](https://unixnu.com/zh/porting/device-tree)
- [适配记录格式](https://unixnu.com/zh/porting/records)
