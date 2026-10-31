# 首次启动构建（第 7 步）

本页最初记录主机构建链；后续设备测试已推进到早期引导线程，最新状态见
[交接更新](handoff.md)与 `evidence/bring-up/runtime/`。下列产物表保留原始提交的构建结果。
证据在 [evidence/bring-up](../evidence/bring-up/README.md)。

## 本地输入

IPSW 按文档放在**仓库外**（`../ipsw/`），组件提取到 `out/ipsw/21H461/`。
`unixnu.local.toml` 只在本机存在，关键字段：

```toml
[build]
device = "../UniXNU-sm-t970"
uefi = "../UniXNU-sm-t970/.cache/uefi-source/Mu-Silicium"
dtb = "../UniXNU-sm-t970/out/firmware-inputs/firmware.dtb"
ipsw = "../ipsw/iPad_Pro_HFR_17.7.11_21H461_Restore.ipsw"
kernelcache = "out/ipsw/21H461/kernelcache.decompressed"
trust_cache = "build/original-static-system-trust/original-static-system.bundle"
unique_chip_id = "0x534d543937303031"
jobs = 10
target = "DEBUG"
kernel_args = ["-v", "cpus=1"]
```

- `kernelcache.decompressed` 的 SHA256 是 `f18b4df865405f2a287b84977d7aca745e056d656d9fc9df1662970ce2969de7`，
  与 OS profile 的固定值一致。
- 平台种子 `0x534d543937303031` 是本地测试值（ASCII `SMT97001`），不是从设备恢复的身份。
- 没有 Data seed；存储驱动尚未移植，首轮不测试可写 Data。

### 信任缓存包

payload 只接受 OS profile `[payload] trust_cache_sha256` 列出的 bundle，而不是 Apple 原始
`.trustcache` 文件。可复现步骤：

```sh
python3.14 scripts/prepare-trust-cache.py
```

脚本从 `unixnu ipsw fetch` 提取的 `StaticTrustCache` 成员中取出 DER 内层（59496 字节，
SHA256 `da88460e…`），写入框架期望的 `static-trustcache.bin`，调用
`build-original-system-trust.py` 与 `Cryptex1,SystemTrustCache` 合成两模块 bundle，
并核对结果为 profile 接受的 `7416ca4f…`。

## 补丁差异

本板应用 60 个补丁（arch 56、SoC 2、OS 层 2、板级 0）。OS profile 的
`zzz-boot-progress.patch` **被省略**：它修改 `bsd_init.c` 中由 `XNU_SHENG_PMGR` 保护的块，
而该符号来自 sheng 的 `sheng-platform-power.patch`，本板不应用。设备仓库用
[patches/xnu/os-series](../patches/xnu/os-series) 保留两个必需的 XnuPrelink ABI 补丁。
省略的只是启动进度诊断，不影响功能；真正需要时再加 sheng PMGR 移植。

## 构建结果

| 产物 | 大小 | SHA256 |
| --- | --- | --- |
| `kernel/kernel.macho` | 51908608 | `b3f9ab34199b726105ea1a3bb7a86af0734d632e55c989b2bdb254bb85f48f0e` |
| `payload/payload.img` | 58720256 | `a87d42da70987f70ed81f8ab25ffd530322e69a0b50df60423c426b2bd0a52e0` |
| `boot.img` | 62713856 | `d61f416aad5e5a029edee52674de909ad32030603cf993695db0c75328651388` |
| `SILICIUM_UEFI.fd` | 3145728 | `4691d86c4c1604ca28f1b97428d930724c270debaa02ed03f3d22f1a68fed7ba` |

顺序：`ipsw fetch` → `build kernel` → `build package` → `build payload` →
`build firmware` → `bootimg`。内核首次构建会先用 bootstrap 通过编译记录，
随后归档、正式链接并预链接。

## 验证

- `boot.json`：header v2、`ramdisk_bytes` 58720256、separate DTB，`dtb_sha256` 等于采集的
  固件 FDT（`86c14aa3…`），`fd_sha256` 等于本次构建的 FD。
- `payload.json`：`kernel_sha256` 等于 `kernel.macho`，包含生成的 ADT 与已接受的
  trust cache（`7416ca4f…`）。
- 镜像内含 BootShim + 3 MiB FD + 56 MiB payload，`kernel_address 0x8000`、
  `tags 0x1e00000`、DTB 独立放置。

## 刷入测试（Odin）

T970 的 boot 分区实测 **71303168 字节（68 MiB）**。payload 必须收进这个上限，
`board.toml [payload] size_mib` 因此从 192 改为 56：内核 51.9 MB 加 ADT 与 trust cache
约 52 MB，镜像 62713856 字节，余量约 8 MB。再大的 payload 需要另找存放分区。

已生成 Odin 用的 AP 包（`out/step7/odin/`，被忽略目录）：

| 文件 | 用途 |
| --- | --- |
| `boot-unixnu.tar` / `.tar.md5` | 本次测试镜像 |
| `boot-stock.tar` / `.tar.md5` | 刷回当前 Magisk 25.2 状态 |

步骤：

1. 平板关机，按住 **Vol Down + Power** 并接 USB，出现警告后按 **Vol Up** 进入下载模式。
2. 打开 Odin（Mac 版），只保留 `F. Reset Time`（`Auto Reboot` 可选），AP 选择 `boot-unixnu.tar`。
3. 确认 ID:COM 出现设备后 Start；通过 Odin 日志 `PASS` 或设备自动重启判断完成。
4. 预期：首先出现 UEFI/UniXNU 菜单（可用 **Tools → Advanced Logger** 扫码抓固件日志）；
   选择启动项后 DarwinBoot 交接内核；因没有 UFS 驱动与 Data seed，最终应停在 root mount 或
   panic 屏幕，这是本阶段的预期停止点。
5. 记录屏幕照片、菜单项、最后一条日志；如无显示或卡死，长按 Power 强制重启。

恢复：同一流程刷 `boot-stock.tar`，或按需刷官方固件（`HOME_CSC` 保数据）。

## 设备侧

本节原始构建快照当时未刷写。后续 ds 已执行 BOOT 测试；交接报告设备进入菜单并交接
内核。不能再把“平板仍运行 Android”当作当前状态，当前 BOOT 据交接由测试镜像占用。
恢复镜像已从设备只读导出到 `out/device-backup/`：`boot.img`（68 MB，Magisk 25.2 补丁版）、
`dtbo.img`（10 MB）、`vbmeta.img`（64 KB），可用 Odin 刷回。

SM-T970 没有 fastboot，测试路径是 Odin 刷 boot（Android v2 格式，与 Magisk 补丁镜像同一种刷法）。
由于没有 UFS 驱动与 Data seed，首次测试预计在内核交接后停在 root mount，不会写存储。

## 下一步

1. 需要机主确认后，用 Odin 单次刷入 `boot.img`，按[启动验证顺序](../evidence/bring-up/README.md)
   记录固件、菜单、加载器和内核观测。
2. 按[存储分析](storage.md)移植 SM8250 UFS 驱动，才能越过 root mount。


## 当前定位方法

一次只改变一个检查点，默认板级配置不保存复位探针。例：

```sh
PATH=$PWD/.cache/bin:/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
python3.14 scripts/build-entry-probe.py --target _idle_thread_create --delay 6 --output out/step7/probes/idle-return
```

新目录中保存独立 payload、boot.img、日志和 probe.json；原始 kernel.macho 与 board.toml
不变。`--before` 表示到达调用点时立即复位，不使用延时；默认表示调用返回后再等待 6 秒。
没有复位只能记作“检查点未观察到”，不能直接证明被测函数内部阻塞。

### 控制台状态诊断

已确认 `vcattach` 中 `gc_enable` 调用前可达、返回后探针未触发。
`--console-state` 在同一位置只读 `_gc_initialized` 的低位及 `_PE_putc` 是否非空，
不调用 `gc_enable`，不修改这两个变量，以延时编码后 PSCI 复位：

| 到达检查点后的延时 | gc_initialized 低位 | PE_putc |
| --- | --- | --- |
| 约 4 秒 | 0 | NULL |
| 约 14 秒 | 1 | NULL |
| 约 24 秒 | 0 | 非空 |
| 约 34 秒 | 1 | 非空 |

```sh
PATH=$PWD/.cache/bin:/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
python3.14 scripts/build-entry-probe.py --target _gc_enable --function _vcattach \
  --before --console-state --output out/step7/probes/console-state
```

从色条出现后计时并观察至少 45 秒，记录实测秒数；色条到检查点还有执行时间，
模糊的时间或未复位不能解码成状态。该模式覆盖普通 `--before` 的立即复位语义。
它固定到已审阅的内核 SHA256，核对符号、调用与空白区；未知内核直接拒绝。
`scripts/console-state-probe.py` 编码的 AArch64 指令可在主机隔离环境用 Unicorn 测试：

```sh
PATH=/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
.cache/probe-test-venv/bin/python -m unittest discover -s tests -v
```

测试覆盖四种状态、64 位非空指针及只读行为；模拟计数器不是实机计时或 PSCI 验证。
该探针不捕获异常，也不提供文本日志。XNU 日志需已适配 UART／原生 USB、屏幕诊断，
或明确保留区的写入与重启后读取实现。ADB 和 UEFI Advanced Logger 不会自动获得
ExitBootServices 后的 XNU 输出。

### 恢复控制台初始化

机主报告状态镜像 `670e78ee…` 约 4 秒后复位，支持该检查点上初始化标志低位为 0、
`PE_putc` 为 NULL。旧实验补丁同时跳过了 `PE_create_console` 和
`PE_init_printf(FALSE)`；后续 `vcattach` 仍会走屏幕启用路径，因此这个绕过不完整。

替换补丁 `t970-console-bootstrap.patch` 恢复 `PE_create_console`，并把
`PE_init_printf(FALSE)` 放到它之前，以便建立控制台时已有输出回调。
修复是否能通过原先失败的 `PE_init_printf(TRUE)` 返回点，需要新的独立镜像实机验证。
原内核及构建报告保存在 `out/step7/baseline-console-skip/`（忽略目录）；旧状态探针
固定到该内核哈希，更换内核后拒绝应用是预期行为。

当前 DTS 是 ADT 的低地址包络。它包含固件保留洞，不是 2 GiB 可用内存池；DarwinBoot
单独通过 EFI conventional memory 分配 256 MiB，并把该大小写入 boot_args。检查器会报告
包络中的保留区，但并不把这些地址标记为空闲；每次实际分配仍需运行时日志验证。
