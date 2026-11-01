# UniXNU — Samsung Galaxy Tab S7+ Wi-Fi (SM-T970)

设备代号 `gts7xlwifi`，SM8250-AB（Snapdragon 865+），目标 iPadOS 17.7.11（21H461）。
本仓库按官方 `examples/device` 建立，保存板级配置、实机输入、固件接入和适配记录。

## 当前结果

交接中的设备记录已到达 `bsd_init`／根卷挂载，当前回到第 6 步的 **UFS／SMMU 适配**。
已有 USERDATA 根镜像写入回执，但 UFS DMA 与根卷挂载尚未通过；用户态、SMP 和外设仍未完成。
本轮先做[只读 SMMU 核查](docs/smmu-readonly.md)，报告原始寄存器与候选 SID，
实机已确认读到 87 组匹配配置、74 个 context bank，三个候选 SID 均未匹配。
未提交 UFS 命令或挂载根卷；已按[同类设备对照](docs/ufs-reference-comparison.md)修正时钟诊断，
[完整只读交接快照](docs/ufs-handoff.md)已确认 HCI ready、队列 doorbell 为零，
唯一有效 stream 与显示对应。已实机确认[无效 SMR 的 ID 字段](docs/smr-id-test.md)可写且恢复成功；
[合并核查 VALID、S2CR](docs/smmu-fields.md)已确认接受及恢复；
[零命令预检](docs/ufs-preflight.md)已确认实际内存归属；
[单次 NOP 测试](docs/ufs-nop.md)已完成一次命令／响应 DMA 往返；
SCSI 数据传输、存储读取和持续稳定性尚未验证。

两个仓库并列放置，普通构建命令在主仓库执行：

```text
vsc/
├── UniXNU/                 # 构建工具、组件目录、ARM64 与 OS profile
└── UniXNU-sm-t970/         # 本设备输入、DTS、固件 overlay、package 和记录
```

- `board.toml`：格式 2，`name/kit=sm-t970`，SM8250 和 iPadOS profile，完整五组件选择。
- `feeds.toml` / `unixnu.lock`：固定 SoC 和组件来源；固件及嵌套子模块固定在 `package/firmware/inputs.json`。
- `configs/sm-t970_defconfig` / `patches/xnu/series`：设备配置、控制台初始化顺序修复及继承的配置／补丁。
- `dts/`：诊断用低地址 DRAM 包络、30 个静态保留区、CPU0 及禁用的板级外设资源。
- `package/firmware/`：T970 配置、DSC/FDF、内存／配置库、44 个厂商模块包装和 UniXNU 接入。
- `proprietary-files.txt`：130 份资产的来源与 SHA256；二进制留在本机忽略目录。
- 固件日志导出器已接入（`AdvancedLogDxe` → **Tools → Advanced Logger**）；
  主机证据见[验证记录](evidence/firmware-log-exporter/README.md)，屏幕菜单与二维码尚未验证。
- [porting.toml](porting.toml)：13 个部分的适配范围、实现和验证证据。

显式组件为 `ArmDTPlatform`、`ArmCpu`、`SoftwareAES`、`XnuPrelink`、`DarwinBoot`；
archive 还接入了设备内 UFS 实验副本、空策略 VerifiedRoot 与 PMGR 占位实现。
这些构建输入不等于功能验证通过；GPU、触控、音频、无线尚未适配。

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
- [存储（UFS）适配分析](docs/storage.md)：板级输入、ShengUfs 不适用判断与后续工作
- [提交后的主机构建与打包证据](evidence/device-repository/README.md)
- [共享支持选择与精确版本](docs/shared-support.md)
- [原厂 ADB 与固件来源证据](evidence/README.md)
- [移植步骤](https://unixnu.com/zh/porting/steps)、[驱动适配](https://unixnu.com/zh/porting/drivers)

交接已包含 BOOT 刷写测试历史；当前机主反馈与下一轮定位见 [交接更新](docs/handoff.md)。
原始恢复镜像、固件 FDT 和每轮测试镜像保留在本机忽略目录。已有 USERDATA 根镜像写入历史，存储读取与持久 Data 尚未验证。
