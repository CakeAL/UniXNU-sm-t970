# SM-T970 交接（2026-11-15 晚，wholesale 分支）

目标：在 Galaxy Tab S7+（SM-T970 / gts7xlwifi / SM8250）上，用参考移植
`https://github.com/rui12366B/UniXNU-gts7xlwifi` 的整包（wholesale）内核与板级包，
跑到 iPadOS 17.7.11 桌面，并逐项完成 `docs/HANDOFF-codex-20261115.md` §1 的验收清单
（八核 4+3+1、~6.7 GiB、UFS + 持久 Data、GPU 合成、触控/按键、亮度、扬声器/麦克风、振动、
关机断电、充电、Wi-Fi、蓝牙、S Pen、USB 被 Finder 认成 iPad）。

本文件只补充**今天新增的事实与工具**；§1 清单和验收标准见前一份 handoff，仍然有效。

## 0. 环境与命令

- 设备仓库：`/Users/cakeal/vsc/UniXNU-sm-t970`，分支 `gts7xlwifi-wholesale`。
  `main`（`18f6bd6`）保留着仍能进桌面的旧零散移植，可随时回退比较。
- 框架：`/Users/cakeal/vsc/UniXNU`（HEAD `0e9e1e8`）。参考项目副本：`/Users/cakeal/vsc/gts7xlwifi-upstream`
  （与上游 `main` `88b34f9` 逐字相同，已核对）。
- 本机 Python 3.14；`PATH` 需含 `/tmp/py314`。
- 内核重建（四个环境变量缺一不可，否则 archive-21 报 `T970Bluetooth.cpp needs UniXNU/QcaBluetooth`）：

```sh
cd /Users/cakeal/vsc/UniXNU
PATH=/tmp/py314:$PATH \
UNIXNU_UEFI=/Users/cakeal/vsc/UniXNU-sm-t970/.cache/uefi-source/Mu-Silicium \
T970_DEVICE_DIR=/Users/cakeal/vsc/UniXNU-sm-t970/kits \
T970_QCA_BLUETOOTH_DIR=/Users/cakeal/vsc/UniXNU/drivers/QcaBluetooth \
T970_ATH12K_WIFI_DIR=/Users/cakeal/vsc/UniXNU/drivers/Ath12kWifi \
python3.14 ./unixnu build kernel -D ../UniXNU-sm-t970
```

  产物：`/Users/cakeal/vsc/UniXNU/out/sm-t970/ipados-17.7.11-21H461/gts7xlwifi/kernel/kernel.macho`。
  **注意** `/Users/cakeal/vsc/UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/kernel/kernel.macho`
  是旧零散移植内核（`95e88a24…`，无启动页钩子），别拿错。

- 打屏上启动页镜像（命令行可控、去掉探针参数、按 SM-T970 Recovery 外壳打包）：

```sh
cd /Users/cakeal/vsc/UniXNU-sm-t970
python3.14 scripts/build-boot-progress-page.py \
  --mode 2 --kernel-arg build-tag=<tag> \
  --kernel-arg t970-apfs-seed=1 --kernel-arg t970-ufs-data=1 --kernel-arg ufsrw=1 \
  --kernel-arg t970-pid1=1 --kernel-arg native-ufs-stream2=0x4e0 \
  --drop-kernel-arg panic_on_crash_disabled \
  --kernel <kernel.macho> --output out/dual-system/wholesale-inputs-20261115/boot-progress-page/<new-dir>
```

  输出恒为 86888448 B。脚本会：克隆 board payload 规格、替换 KernelArgs（丢掉本地 `-v cpus=1`
  和 board 的 `boot-progress=3`）、清掉 `entry_probe_reset_*`、用 `scripts/pack-wholesale-recovery.py`
  把 payload 打进 `out/dual-system/data-persistence-20261111/recovery-persistent.img`（保留其
  firmware/shim/DTB 与 `scratch-data.img`）。

- 自动刷写（用户已授权：识别到 Download Mode 就写，只写 RECOVERY）：

```sh
nohup sh scripts/flash-recovery-when-detected.sh <img> <sha256> 5400 > /tmp/flash-<tag>.log 2>&1 &
```

  必须出现 `RECOVERY upload successful`；`Failed to send handshake` 通常是平板正在开机、退出了
  Download Mode，重挂即可。

## 1. 硬规则

- 只允许写 `--RECOVERY`。绝不写 BOOT / userdata / GPT。
- iPadOS 拿到的是 userdata 里的 **LBA 37,292,800–62,458,623（96 GiB）**；之前的
  LBA 2,969,600–37,292,799 属于 One UI，绝不能写。
- 证据只留文本（JSON/日志），不要再存 jpg。
- 任何功能都不能在没有实机观察 + 镜像 sha256 的情况下声称可用。

## 2. 现在能确认的事实（附证据）

| 环节 | 状态 | 证据 |
| --- | --- | --- |
| 固件 → 内核 → MMU | 通 | 启动页能画出来 |
| 八核 4+3+1、PSCI/SMP | **通** | 页面 `SMP req=1 run=7 cond=1 boot=0 \| c1..c7=step7` |
| UFS root（SystemOS） | 通 | `SystemOS mount enter/returned` |
| Data 改为 UFS 上的 APFS 容器 | 已接上 | `RAMDISK capacityMiB=0`（RAM 种子退场），`PID1 data volume enter` |
| **Data 挂载** | **失败** | `PID1 data error NONZERO` → `PID1 data ENOENT` |
| 显示交接 | 从未发生 | `DISPLAY stage=10 PM=2 calls=7 callbacks=1 guard=0 owned=0` |
| launchd | 从未启动 | `PID1 nprocs=1 … nothing was spawned` |

`ml_wait_max_cpus` 不是卡点：复位探针那天得出的结论是假象——`ml_wait_max_cpus` 只被
`bsd/kern/mcache.c:191`、`uipc_mbuf.c:2373`、`kern_mib.c:1326` 调用，不在 `bsd_init`。

## 3. 今天的关键坑（都踩过，别再踩）

1. **`boot-progress=3` 永远不绑帧缓冲**（`package/BootProgress.c:915` `if (!enabled || enabled==3 || !take()) return;`）。
   默认值就是 3，所以「没有启动页」不是故障；要用 2。
2. **panic 被静默吞掉**：命令行里的 `panic_on_crash_disabled=1` 会让 panic 不显示。整晚的
   「安静停住」其实是 4 秒时就 panic 了。诊断版本一律 `--drop-kernel-arg panic_on_crash_disabled`。
3. **`-v` 会打断显示交接**：参考项目的 board.toml 注释写明 DarwinBoot 在命令行含 `-v` 时把
   `Boot_Video.v_display` 置 0（文本控制台），`NativeLegacyDisplay` 因此不是主显示，
   `isMainDisplay()` 为假，backboardd 永远不 present。`/Users/cakeal/vsc/UniXNU/unixnu.local.toml`
   里仍有 `kernel_args = ["-v", "cpus=1"]`——打包脚本会替换掉，但手工 `unixnu build payload` 会带上。
4. **`kern_exec` 里等不到设备**：`waitForMatchingService`/`IOSleep` 在那个时刻立即返回（没有可用的
   时钟等待），所以「轮询 20 秒」实际上几十微秒就结束了。不要在 `native_owner_data_prepare` 里等。
5. **kext 里的 `boot_progress_*` 弱引用解析不到**，用它会静默跳过；要跨 kext 给页面送信息，用
   导出的全局变量（`t970_data_diag` 那组）而不是 stage 字符串。
6. **双流 UFS 在我们固件上不存在**：参考固件预置了 SMMU S2CR（stream `0x0e0`/`0x4e0`），我们的
   Mu-Silicium FD 没有（`smr=0 s2cr=0`）。已把 `requireDualStreamReuse()` 从 panic 改为记日志
   （commit `3b43e1b`），上下文交给 `smmuBypassStream()` 自己在有 DMA 窗口后配置。
7. 栈转储不要裸扫：沿 `sp` 往上扫 2048 字会越过内核栈底触发 data abort（`esr=0x96000007`）。
   被换出的线程只有 `arm_kernel_saved_state`（`kstackptr+80/88/96` 是 FP/LR/SP）可信；帧链
   （`[fp]`/`[fp+8]`）在我们这颗内核上反而取不到活帧（`bt: -`）。

## 4. 当前进行中的实验

最新镜像 **`8a9aff0678901a6d1cfa6ecacff85dca9bf0f2fb0dce9546d20313497c373811`**（`[ufsdata-l]`，
内核 `65af0864…7f34`），在 `package/BootProgress.c` 的 pid1 区多打一行：

```
data diag=<n> media=<m> uuid=<u>
```

含义（`drivers/ShengUfs/NativeUfs.cpp` 的 `t970_ufs_data_volume` 失败分支里赋值）：

- `diag=1 media=0` → 我们发布的块设备**根本没有变成 IOMedia**（发布链路断在 IOStorageFamily）；
- `diag=2 media=1 uuid=0` → 媒体有，但 APFS 没在上面建出卷（要查 APFS 探测条件/卷角色）；
- `diag=3 media=1 uuid=1` → 卷存在，是查找逻辑（UUID 匹配 / 祖先判断）写错了。

拿到这一行就能直接定位，不必再试。

## 5. 下一步（按顺序）

1. 读 `[ufsdata-l]` 的 `data diag=` 行，按上表三选一修：
   - 1 → 在 `t970PublishData()` 之后确认 `IOBlockStorageDevice` 是否被 `IOBlockStorageDriver`
     接管、是否缺 `Content`/分区类型属性；对照 `IOStorageFamily` 的媒体创建条件。
   - 2 → 让 APFS 认这块设备（内容提示/角色），或改为在更晚的时机（有 IOKit 匹配线程之后）挂载。
   - 3 → 修 `t970DataVolumeOnce()` 的 UUID/祖先判断。
2. Data 通了之后确认 `PID1 nprocs>1`、`stage:` 继续往后走；此时再谈 `DISPLAY owned` 与 launchd。
3. 显示：等 backboardd 起来后看 `DISPLAY owned` 是否变 1；同时核对命令行确实没有 `-v`。
4. 再按 §1 清单推进 GPU/触控/音频/Wi-Fi 等驱动（参考项目对应的补丁与参数见
   `docs/wholesale-vs-reference.md`）。

## 6. 相关文件

- `scripts/build-boot-progress-page.py`：屏上启动页镜像构建（`--mode`、`--kernel-arg`、`--drop-kernel-arg`）。
- `scripts/flash-recovery-when-detected.sh`：检测到 Download Mode 就刷 RECOVERY。
- `scripts/pack-wholesale-recovery.py`：把 payload 打进 SM-T970 Recovery 外壳（Base `33efcec0…`）。
- `scripts/addr2sym.py`：把启动页上的无 slide 地址翻成符号（用未 strip 的
  `tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped.noctf`）。
- `drivers/ShengUfs/NativeUfs.cpp`：`t970ApfsSeed()`（写 33 个 APFS 元数据块）、`t970PublishData()`
  （发布 93.69 GB whole-userdata 设备）、`t970_ufs_data_volume()`（按卷 UUID 找 IOMedia）。
- `drivers/ShengUfs/T970ApfsSeed.h`：33 块索引 + 数据（主机上用 `newfs_apfs` 建出的空容器，只有 132 KiB 非零）。
- `patches/xnu/t970-ufs-data-mount.patch`：把 owner Data 的来源从 RAM 种子改为 UFS APFS 卷
  （卷 UUID `4F1C34B9-BBE3-4803-92AC-1503AEF26540`），已进 `patches/xnu/series`。
- `patches/xnu/t970-pid1-stages.patch`：`exec_mach_imgact` / `load_machfile` / Data 卷 / data_error 的阶段标记。
- `package/BootProgress.c`：屏上启动页、`pid1_dump`、`DISPLAY/`SMP`/`MEM` 各诊断行。
- `docs/wholesale-vs-reference.md`：与参考项目的逐项差异（固件、内存契约、存储、参数、补丁集）。
