# UniXNU — Samsung Galaxy Tab S7+ Wi-Fi (SM-T970)

设备代号 `gts7xlwifi`，SM8250-AB（Snapdragon 865+），目标 iPadOS 17.7.11（21H461）。
本仓库按官方 `examples/device` 建立，保存板级配置、实机输入、固件接入和适配记录。

## 当前结果

第 3 步的设备仓库输入已补齐，范围为 **CPU0／initrd 平台引导**。
配置、来源、补丁、归档和 DTS／ADT 可在主机检查，T970 UEFI 候选已实际编译。
`board.example` 已移除，允许主机构建；这不表示新 UEFI、XNU 或 iPadOS 已在平板启动。
实机启动、GOP／内存交接、SMP 和外设功能仍按 `porting.toml` 分别记录验证等级。

两个仓库并列放置，普通构建命令在主仓库执行：

```text
vsc/
├── UniXNU/                 # 构建工具、组件目录、ARM64 与 OS profile
└── UniXNU-sm-t970/         # 本设备输入、DTS、固件 overlay、package 和记录
```

- `board.toml`：格式 2，`name/kit=sm-t970`，SM8250 和 iPadOS profile，完整五组件选择。
- `feeds.toml` / `unixnu.lock`：固定 SoC 和组件来源；固件及嵌套子模块固定在 `package/firmware/inputs.json`。
- `configs/sm-t970_defconfig` / `patches/xnu/series`：设备配置与空的板级补丁序列；继承配置和 61 个补丁已核对。
- `dts/`：实测连续高内存段、30 个静态保留区、CPU0 及禁用的板级外设资源。
- `package/firmware/`：T970 配置、DSC/FDF、内存／配置库、44 个厂商模块包装和 UniXNU 接入。
- `proprietary-files.txt`：130 份资产的来源与 SHA256；二进制留在本机忽略目录。
- 固件日志导出器已接入（`AdvancedLogDxe` → **Tools → Advanced Logger**）；
  主机证据见[验证记录](evidence/firmware-log-exporter/README.md)，屏幕菜单与二维码尚未验证。
- [porting.toml](porting.toml)：13 个部分的适配范围、实现和验证证据。

当前选择 `ArmDTPlatform`、`ArmCpu`、`SoftwareAES`、`XnuPrelink`、`DarwinBoot`；
UFS、GPU、触控、音频、无线等 XNU 外设组件未启用。DTS 不替代尚未实现的时钟、
电源、DMA／SMMU 和 OS ABI 接口。

## 检查与构建

需要 Python 3.11+（本机 `python3.14`）、git、dtc、LLVM/lld、Xcode 或对应 Linux 工具链。
主仓库固定为 `194aae294c1107e791f4f74b2be371a391ac6bc4`，SoC 固定为
`166235ec2480ff0992627b7aafa15c65ce6b4efa`。历史第 2 步快照仍保留其原始版本。

```sh
cd ../UniXNU
python3.14 ./unixnu defconfig sm-t970_defconfig -D ../UniXNU-sm-t970
python3.14 ./unixnu fetch sm8250 ArmDTPlatform ArmCpu SoftwareAES XnuPrelink DarwinBoot -D ../UniXNU-sm-t970
python3.14 ./unixnu status --json -D ../UniXNU-sm-t970
python3.14 ./unixnu tree -D ../UniXNU-sm-t970
python3.14 ../UniXNU-sm-t970/scripts/check-platform.py --unixnu .
python3.14 ../UniXNU-sm-t970/scripts/check-build-config.py --unixnu .
python3.14 ../UniXNU-sm-t970/scripts/check-hardware-description.py --unixnu .
python3.14 scripts/porting-record.py check --device ../UniXNU-sm-t970
```

`check-build-config.py` 核对第 4 步的解析结果：配置层顺序、profile、组件与补丁顺序、
19 个模块和 `unixnu.lock` 的固定版本，以及 `out/.../tree/` 到这些源码的链接。

详细的固件获取、提取、固定子模块、准备和构建命令见[固件输入与构建](docs/firmware.md)。
不要使用其他设备的配置或二进制替代 T970 输入。固件 FDT 与 XNU 硬件 DTB 是不同输入。
主机检查 ADT 使用人工身份 `1`，不能用于启动；真实身份在本机配置传入。
XNU 内核和完整 payload 构建还需 Apple 原始 kernelcache、信任与 Data 输入。

## 记录

- [第 3 步七项验收](docs/device-repository-checklist.md)
- [提交后的主机构建与打包证据](evidence/device-repository/README.md)
- [共享支持选择与精确版本](docs/shared-support.md)
- [原厂 ADB 与固件来源证据](evidence/README.md)
- [移植步骤](https://unixnu.com/zh/porting/steps)、[驱动适配](https://unixnu.com/zh/porting/drivers)

本阶段仅进行 ADB 读取和主机构建／打包，没有重启、刷写、分区调整或设备寄存器操作。
