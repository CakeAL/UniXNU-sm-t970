# 整包（gts7xlwifi-upstream）与本案的差异对照

日期：2026-11-15。对象：`/Users/cakeal/vsc/gts7xlwifi-upstream`（同机型上游参考）对
本仓库（`gts7xlwifi-wholesale` 分支，参考整包导入之后）。框架：
`/Users/cakeal/vsc/UniXNU` @ `0e9e1e8`。

目的：整包内核在 `ml_wait_max_cpus()` 等待从未发布的副核，屏幕上只有进内核时的品红条。
本文只回答一个问题：**参考项目与本案在内核之外的哪些输入不同**，因为内核代码已经逐字相同。

## 1. 已经逐字相同、可以排除的部分

| 项 | 证据 |
| --- | --- |
| 设备树 | `diff gts7xlwifi-upstream/dts/gts7xlwifi.dts UniXNU-sm-t970/dts/gts7xlwifi.dts` 无输出 |
| `ArmCpu` 驱动 | `diff -rq` 参考 `drivers/ArmCpu` 与本案同目录无输出；两边都不是框架目录里的版本（框架 `UniXNU/drivers/ArmCpu/ArmCpu.cpp` 与之不同） |
| 18 个板级内核补丁 | 两边 `patches/xnu/series` 列出的文件与内容一致（`t970-three-clusters.patch`、`t970-dram-extend/holes`、`t970-memory-outside`、`t970-ufs-data-mount` 等） |
| SMP 相关启动参数 | 两边都是 `smp=1 armcpu-spi-ipi=1 armcpu-spi-ipi-base=544 armcpu-self-ipi=1`；参考 `porting.toml` cpu 段 `configuration` 逐项相同 |
| 调度簇 | 两边都是 `unixnu,cluster-type` + `die-cluster-id` 0/1/2（4+3+1），`t970-three-clusters.patch` 相同 |

参考 `porting.toml` 的 cpu 段是 `status = "device-verified"`，`completion = ["Seven secondary
cores reach step 7; …"]`，即对方八核是实机验证过的；因此差异不在这些文件里。

## 2. 真正的差异

### 2.1 固件二进制（最大差异）

- 参考 `board.toml` 的 `[firmware]`：`config = "gts7xlwifi-upstream"`、
  `dsc = "Platform/Samsung/sm8250/gts7xlwifi-upstream.dsc"`、
  `fd = "Build/Gts7xlwifiUpstream/{target}_GCC5/FV/GTS7XLWIFI_UPSTREAM.fd"`，
  注释写明由 `../firmware-t970/tools/build-ipados.sh` 构建（Renegade edk2、GCC5）。
- 本案从未重建固件：镜像 `recovery-persistent.img` 里内嵌的 FD 仍是旧的
  Mu-Silicium CLANGPDB 构建，sha256 `515105d758a9d61078dffce5012db0754a71cec351a1bb34b30ee791196b5690`
  （与 `out/step7/ufs-readonly-inputs/SILICIUM_UEFI.fd` 一致），不是 `GTS7XLWIFI_UPSTREAM.fd`。
- 本机没有 `firmware-t970` 源码，也没有那个 `.dsc`／`Resources/Configs/gts7xlwifi-upstream.toml`，
  所以这条差异**目前无法在本机消除**。

### 2.2 内存契约（owned window 与 DRAM 上限）

| 项 | 参考 | 本案 |
| --- | --- | --- |
| `[payload.adt] owned_memory_size` | `0x28000000`（640 MiB） | `0xf0000000`（3.75 GiB） |
| DRAM 上限参数 | `t970-dram-end=0x280000000` | 无（`dram_size = "0x200000000"` 只写 ADT） |
| 高内存 | 固件打开 `0xD0000000..0xFFC00000`，DarwinBoot 首选放这里 | 注释自述「参考的高内存扩展需要配套 UEFI hole export」 |
| `log=1` 持久日志 | 有 | 无 |

参考 `board.toml` 明确记录：该固件只有两段 conventional memory（`0xC0000000+0xDFC0000` 与
`0x200000000+0x40000000`），4 GiB 与 1.5 GiB 的窗口都返回 “Out of Resources”，只有 640 MiB
能落在 `0xD0000000` 起的那段；窗口放不下时 DarwinBoot 退到高段 1 GiB。
本案要 3.75 GiB，与这段实测不相容。

另外 `scripts/pack-wholesale-recovery.py` 明文禁用 `t970-dram-end` 与 `memory-outside`
（它也禁用 `ufsrw`、`t970-ufs-data`、`log`、`sheng-log` 等），所以**当前打包路径根本无法表达
参考的内存参数**——这是本案为了「复用已实测的 Recovery 固件」刻意做的取舍。

### 2.3 存储与 Data 布局（本案的硬约束，不是缺陷）

- 参考：root 在 sda39 的 SHNGROOT 镜像，Data 是 UFS 上的 APFS 卷
  （`t970-ufs-data=1 ufsrw=1`，卷 `5915374F-7A58-4BD3-9C6F-0BD63348ACEA`）。
- 本案：保留「Android BOOT / F2FS userdata / iPadOS RECOVERY / unixnu」双系统布局，
  root 读 unixnu 分区（`native-ufs-root=1`），Data 用打包的 RAM 种子
  （`packed_data_ramdisk = true`、`persistent_data = true`、`sheng-data-persist=2`、
  `RamBlock` 归档、卷 `C25160D3-B586-4C11-9D3A-42CB2741227C`）。
- 因此本案多出 `component:RamBlock` 与 `build-storage-bindings.py --object … NativeRamBlock.o`，
  参考没有。

### 2.4 其他次要差异

- GPU：参考归档 `build-adreno650.py` 并带 `pipa-gpu=12 gpu-addon=1 fb-gpu=1 dpu-scanout=2` 等；
  本案因本机没有 `a650_zap` 固件而注释掉该归档，参数也不含这些（`HANDOFF` 的 M5）。
- root 认证：参考用已签名的 owner root policies（`build-root-policy-archive.py`）；
  本案没有这些签名件，改用 `build-verified-root-empty.py`。
- `feeds.toml`：参考把 `ArmCpu`／`ShengUfs`／`ShengHidInput`／`GopFramebuffer`／
  `QcomXnuUsbDebug` 都写成 `local = "drivers/…"`，本案写 git pin；但实际装配出来的树
  链接的仍是本仓库的 `drivers/ArmCpu`（与参考同字节），结论不受影响。
- `cpufreq`：参考 `cpufreq=3`，本案 `cpufreq=4`（参考 `porting.toml` 写的是 4）。

## 3. 结论：本案卡在哪

1. 内核侧 SMP 代码、DTS、ArmCpu、调度簇补丁与参考逐字相同，**不是代码分歧**。
2. 卡点仍是 `ml_wait_max_cpus()`：副核从未发布。此前旧非整包树上的每核记录显示
   副核走到标记 9（已写 SCTLR、已 ISB，准备跳高地址）后不再出现标记 10
   （`docs/smp-bringup.md`「高地址跳转观察」），即副核没有进入内核的高地址。
3. 参考与本案在内核之外的两处差异正好都指向这段：**固件二进制**与**内存契约**
   （owned window 基地与 DRAM 上限）。副核的 bootstrap/trampoline 页、页表与
   入口地址都由这两者决定。
4. 因此下一次实验应当先确认「副核到底走到哪一步」，再决定是否改成参考的内存契约；
   在没有屏上日志之前改参数属于盲试。

## 4. 仍未回答的既有问题

`ArmCpu::probe` 是否真的匹配到 CPU 节点：`before-armcpu-gic-map` 探针（主核
`ArmCpu::mapGic` 调用前）**没有**复位，而同一次启动里 `ml_wait_max_cpus` 的
`lck_mtx_sleep` 前探针**快速复位**。两者顺序冲突（正常顺序里 ArmCpu 的 start/GIC
映射在等待之前），说明要么该探针站点没被走到、要么 ARM CPU 服务根本没匹配。
`armcpu-probe-cpu-node` 探针正是为此准备，但刷入后一直没有设备观察记录
（`evidence/input/wholesale-recovery-20261115/armcpu-probe-cpu-node.json` 仍是
`device_boot: "awaiting observation"`）。
