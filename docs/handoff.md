# SM-T970 移植交接（2026-11-01）

接手者请先读本页，再看 `porting.toml`、`docs/bring-up.md`、`docs/storage.md` 和
`evidence/bring-up/README.md`。

## 当前：SM8250 只读交接快照（实机观察已完成）

- 参数为 `t970-ufs-handoff=1`，预期标题 `T970 UFS handoff RO (no writes)`。
- 修正内核时钟诊断表，删除 SM8550 独立 mem-PHY GDSC 读取；UEFI 原型保持原样且不执行。
- 显示完整、有界的原始 SMR/S2CR 表及正确的 SM8250 GCC 状态；只有 GDSC/AXI/AHB
  通过保守前提检查才只读 HCI／队列。未采样的 HCI 默认零值需结合 HCstate 解读。
- 内核 `147f8d3bc6b8c35990a83f304f5eab1b3654d69ba5b9a1ef1747a5d31602f34a`
  编译、链接、预链接通过，构建期间输入哈希不变。11 项主机测试通过，包括最大表格排版。
- 代码提交 `58bdac8`，仍使用 FD `515105d7…`。成品 BOOT
  `933a5d776edb2500be5c268b93e64f2cfec53fee6e12cebbb39869a8d7050deb`，
  62,713,856 字节，独立 FAT／参数／FD 核验和 DT/ADT 检查通过。
- 2026-11-01 16:24（Asia/Shanghai），检测 Download Mode 后仅刷 BOOT，
  Heimdall exit 0 / `BOOT upload successful`，`--no-reboot`；机主已给出完整画面。
  `evidence/storage/handoff-readonly/` 保存准备与回执，不得沿用旧快照的实机结论。
- 实机读数：GCC 检查通过、HCstate=1，HCE=1、HCS=0x10f、IS=0x400；
  UTRLBA=0x9b296000，两类队列 RSR=1、doorbell=0，END slots=87。
- 唯一有效槽 04：SMR=0x84020820、S2CR=4，与原厂显示 iommus SID 0x820／mask 0x402 对应；
  保留此槽与 CB4。02/03 的 0x4e0／0xe0 仅为无效字段，不能直接当作活动 UFS 路由。
- 本轮原始照片在对话可见，但本机给定路径不存在；已记录可见转录，照片文件哈希留空。
- 下一步拟核查单个无效 SMR 的 ID 字段写入并恢复，保持 VALID=0、S2CR 不变；
  目前尚未执行任何这样的写入，不把已有 HCI ready 状态当作 DMA／根卷通过。
- 范围、格式及复现：[交接快照](ufs-handoff.md)。本轮不进行 UFS 命令、DMA 或 USERDATA 写入。

## 当前接手核查（从 47b113f 继续）

- 当前任务是 UFS／SMMU，而非下面早期控制台定位的历史阶段；根卷挂载失败见
  `evidence/bring-up/runtime/pmgr-bridge/device-result.json`。
- 接手时 `board.toml`、`NativeUfs.cpp`、`SmmuTakeover.h` 有未提交改动，
  已原样保存在 `.cache/handoff-ufs-resume/`。机主确认这组实验尚未刷入。
- 接手的逐槽 SMR 写入探测已撤出新路径；旧参数被拒绝。bank 递增候选从
  ID1.NUMS2CB 的边界开始，不假定 bank 1 可用；该接管算法仍没有实机 DMA 通过证据。
- 本轮 `t970-smmu-report=1` 只读 SMMUv2 原始 ID／控制寄存器与有限候选匹配，
  主动 panic 显示后停止，不进入控制器和根卷路径。候选 SID 不是板级路由确认。
- 旧证据不能证明 SMMU 已永久被 TZ 锁定，也不能证明 SCM 所有路线不可用。
  尤其 SCM 结果标记发生在两个调用之后，不能由一个红块推出第二个调用没返回。
- 本轮固件复用精确哈希 `515105d7…` 的已测试 CPU0/initrd FD，不执行后来的 UFS PHY／SCM 原型。
  原型源码仍保留。复现与原始寄存器定义见 [只读核查](smmu-readonly.md)。
- USERDATA 已有 OS/SystemOS 实验镜像；本轮不再次写入。旧 BOOT 备份只恢复 BOOT，
  不代表恢复 Android 用户数据。最近实际刷入的镜像需以刷写回执和机主反馈为准。
- 以下各节保留不同阶段的交接历史；涉及“无路可走／安全世界掌管”等判断，
  以上述证据边界及新只读测量为准。

## 本轮已准备、刷写并确认只读诊断

- 代码提交：`23d54b9`。9 项主机测试通过，其中 SMMU 模型包含 11 个场景；
  配置检查、CPU0 DT/ADT 与 30 个静态保留区检查通过。
- 源内核 `cca9bbb8…`；加入色条与 panic 显示后的 payload 内核 `c89b24fd…`。
  成品 BOOT `7f729c2a6ee8ee11b6eb5d4ff7ec23171b261854151578e36737d866a62391e2`，
  62,713,856 字节。FAT 中内核及参数、BOOT 中 FD 均已独立提取核验。
- 2026-11-01 15:55（Asia/Shanghai），检测到 Download Mode 后，用本机补丁版 Heimdall
  仅刷 BOOT，exit 0 / `BOOT upload successful`，`--no-reboot`；未再次写 USERDATA。
- 机主已确认标题并提供 `IMG_20261101_155738.jpg`：sCR0=`002d0406`，
  ID0=`4c017e57`，ID1=`6000004a`，ID2=`00005111`，GFSR=0；扫描 87 组，
  74 个 CB，三个候选均未匹配。`0xffffffff` 是无匹配哨兵，不是实际槽号。
  只读路径成立，UFS、DMA 或根卷仍未通过。
- 准备记录、完整哈希、平台检查和刷写回执：`evidence/storage/readonly-smmu/`。
  未通过首次参数核对的打包产物留在忽略目录，未刷写；最终工具固定使用已审阅参数，
  不接受本机默认参数对诊断行的覆盖。

## 公开参考核查与后续方向

- 应机主要求核查 T733 与 SM8250 设备。T733 维护者有大量成功请求记录，
  同时源码保留早期 DMA 复位诊断；umi 报告根卷与 Hello 已运行，采用专门的双 stream 规划。
  这些是对方维护者记录，不是 T970 验证。
- T733 有公开配套固件 fork，不能继续沿用下方历史段落中的“固件不公开”判断。
  它接入厂商 Clock／HALIOMMU／SCM／UFS 依赖；本轮 T970 FD 的交接前提不同。
- 本地 `GccUfs.h` 仍含 SM8550 时钟诊断偏移；三星 `gcc-kona.c`、Linux 与 umi
  共同给出 SM8250 的 AXI=`0x77010`、AHB=`0x77018` 等参考。
  `BoardInit.c` 的旧宏也错位，但当前已经跳过 GCC 写入；不能据此宣称确定复位根因。
- 下一步先审阅并修正 SM8250 诊断输入，再一次采集有界 stream 表和受前提保护的
  电源／HCI／队列状态。不要直接套用 T733 的 `0x80` 或 umi 的双 SID。
- 精确来源与差异：[UFS 参考对照](ufs-reference-comparison.md)。本轮观察后未再刷写。

## 接手后的更新

- 本轮机主确认：最后的 `initialize_screen` 探针一直停留，没有复位。
  已核对代码：它是 **reset-before，立即复位**，不是等待 6 秒；因此不能据此认定
  `initialize_screen` 内部卡住。机主反馈与镜像哈希见
  `evidence/bring-up/runtime/handoff-observation.json`。
- SEC 补丁已在 `ac1ca14` 接入准备工具；固定补丁和四个文件的前／后像哈希，
  干净源码应用、重复执行及保留未知修改的检查均通过，不再依赖缓存的手工修改。
- 重置探针从默认 `board.toml` 移出，用 `scripts/build-entry-probe.py` 隔离生成。
  本项后续调用边界和状态结果属于旧内核 `4131d5b1…`，不能直接套到修复版。
  机主已确认 `idle_thread_create`、`sched_startup` 返回后探针均自动复位；
  `PE_init_iokit` 返回后探针（`9b0f8f68…`）仍停在色条，没有自动复位。
  每轮完整镜像哈希、刷写回执与观察见 `evidence/bring-up/runtime/`。
  `PE_init_iokit` 调用前探针（`458218bd…`）已由机主确认自动复位：
  未通过的路径缩到该调用内部。其内部 `InitIOKit` 调用前探针（`977fd90d…`）
  未复位，第一个调用 `PE_init_printf(TRUE)` 返回后探针（`f89deffa…`）也未复位。
  该二进制中它尾调用 `vcattach`；`vcattach` 中首个无条件调用
  `arm_usimple_lock_init` 返回后探针（`95ff2c91…`）已复位，确认进入并通过锁初始化。
  `vcattach` 内 `gc_enable` 返回后探针（`a914135d…`）未复位，调用前探针
  （`59dc0bb6…`）已复位，范围缩到 `gc_enable` 调用内部。
  `--console-state` 镜像（`670e78ee…`）由机主报告约 4 秒后复位，
  支持 `gc_initialized` 低位为 0、`PE_putc` 为 NULL，详见该轮 `device-result.json`。
  源码显示跳过 `PE_create_console` 也会跳过屏幕回调初始化；这可能影响后续 `gc_enable`，
  已有上述状态时序证据，但仍未确认具体失败指令。
  尚不确定具体失败指令或故障类型，也没有运行时加密 provider 失败证据。
- [相近设备案例](related-bring-up.md)记录了 Surface Duo 2 同阶段的加密 provider 问题，
  以及 SM8250 小米 10 至尊版的验证边界。均不是 T970 根因的证据。
- 修复准备：以 `t970-console-bootstrap.patch` 替换旧绕过补丁，恢复控制台建立，
  并在其前先调用 `PE_init_printf(FALSE)`。旧内核保存在本机忽略目录
  `out/step7/baseline-console-skip/`；新内核 `bfb50a1a…` 已编译、链接、预链接通过，
  最终机器码确认先装输出回调再无条件建立控制台。修复版 `PE_init_printf(TRUE)` 返回后
  镜像（`f759eb80…`）仍未复位。照片中的 UEFI 菜单、DarwinBoot 交接句及固件文字
  是保留像素，没有确认新的 XNU 文本输出；不能断定新内核仍停在旧卡点。
  旧状态探针固定到原内核哈希，更换内核后拒绝运行是预期行为。
- 已用 `--guard-early-faults` 检查更早的 `arm_init` 中 `PE_create_console` 返回：
  正常 6 秒，同步异常／SError／panic／BRK 分别 20／30／40／50 秒后请求复位。
  机主报告 `e18c6ca0…` 60 秒后仍未复位，既未确认正常检查点，也未确认异常分类路径。
  主机测试和活动向量选择核对通过；设备 BRK 正控制尚未完成，不复位仍有多种可能。
- 下一轮加 `--brk-control`：在 `0xfffffff0073f3370`（MMU 开启后、C 初始化前）
  用 `BRK #0` 替换已检查的 `mov x0, #0x300000`。预期约 50 秒后复位，
  控制台建立调用不修改、不执行；先验证诊断通道，再解释负结果。
- BOOT 最近刷入的是 `after-mmu-brk-control` 正控制镜像（`150ed5ff…`），机主确认约 50 秒复位；正控制成立，诊断通道可用。
  原始 BOOT 恢复待完成，后续镜像以 `evidence/bring-up/runtime/*/flash.json` 回执为准。
- 以下为 ds 交接当时的状态、命令和待办，保留作历史基线；当前进展以本节及适配记录为准。

## no-SMMU 实验

保持 SMMU 映射但不写寄存器（`t970-ufs-no-smmu=1`）可以越过 SMMU 相关 panic，但随后停在
magenta 条并自动复位、无控制台输出；与驱动里无超时的 UFS 完成等待一致，即**固件的 stream
映射不覆盖我们的 DMA 缓冲**。内核侧绕过 SMMU 不足以让 UFS 工作。

## SMMU 归属的结论

Linux `arm-smmu.h` 证实 IDR 在 `0x20/0x24/0x28`（原驱动偏移正确）。恢复该模型并扫描全部 128 个 slot 后：

- 固件的 128 条 stream 里没有一条符合“bypass + 单引用 + AArch64”的复用条件；
- 新建 bypass context 的 SMR 写入仍读回 0。

两者合起来说明 **secure world（ABL/TZ）掌握着 stream 寄存器**，非安全世界只能读 IDR。内核侧无法自行配置 SMMU；需要固件为 UFS 留下 bypass stream（alioth/T733 的固件正是这么做的）。

## SMMU 模型的最终判断

- `GFSR`（0x24）写入无效 → SMMU 寄存器**被锁**，不能新建 bypass context；
- 改用 vendored 驱动（IDR `0x0/0x4/0x8`）+ 自动复用所有 exact stream，仍在
  `IDR0 bit30` 的 AArch64 检查失败（`SM8550/alioth 模型 ≠ SM8250 apps_smmu`）；
- 结论：需要**针对 SM8250 的 SMMU 实现**（参考 Linux `arm-smmu-qcom`/SMMU-500 规范，
  重写 SmmuTakeover 的寄存器模型），或让固件按 SM8250 的方式预先配好 UFS stream。

## 下一步的根因（固件不给 UFS 上电）

- 固件 `gts7xlwifi.dsc` 仍写着 `no UFS driver yet. Excluded for bring-up`；
- alioth `ShengUfs` 的 `hostBringUp` 只做控制器映射，**不初始化 PHY/时钟/SMMU**，假设固件已完成；
- T970 上 SMMU 的 SMR 写入不生效（读回 0），IDR 读数在两次启动间变化，说明 **apps_smmu 未被固件上电/配置**；
- 已在 `package/ShengUfs/` 保留 vendor 副本（IDR 偏移改为 0x0/0x4/0x8）和 `zz-build-shengufs-local.py`，但默认 archive 仍只用 `component:ShengUfs`。
- 结论：要过 UFS，需要**固件侧 UFS/PHY/SMMU 上电**（T733 的固件做了这件事，但仓库不公开），或在驱动里补齐 T970 的 PHY/时钟/SMMU 初始化。

## SMMU 诊断（本轮）

`t970-smmu-dump` 在 `arm_init` 末尾转储 apps_smmu：IDR0 `0x002d0405`，固件共配置 **26 个 stream**，
没有 `0x0060`。驱动随后规划 **bank 73 / slot 86** 并写 SMR，写后读回 0（`act=0`）。
这更像 **SMMU 未开时钟/未上电或被 TZ 锁定**，而不是单纯少了 stream id。
下一步：在驱动里先使能 apps_smmu 的 GCC GDSC/时钟，或改用固件已配置的 stream（需从 26 条中确认 UFS 的那条）。

## UFS 进展（userdata 已写入）

- **userdata 已完整写入**：`scripts/encode-userdata-sparse.py` 把 8.7 GiB 镜像切成三段 sparse，
  用 DONT_CARE 跳过非本段内容，每段 <4 GiB，Heimdall 三次 `USERDATA upload successful`。
- 内核 `a981a22d…`（alioth ShengUfs + 空策略 VerifiedRoot，19 KB）能链接、能启动，单 stream
  `0x60` 时在 `NativeUfs.cpp:455` panic：`SMR write off=958 exp=80000060 act=0`，
  即 SMMU 的 stream 写入不生效（固件 SID 不同或 SMMU 被锁）。
- 下一步：确定 ABL 为 T970 配置的 UFS stream id（或确认 SMMU 只能由固件预配），
  再决定改 `native-ufs-stream` 还是做板级 SMMU/ICE 配置。

## UFS 的硬约束（本轮结论）

- 已生成 T970 的 `userdata-root.img`（OS `e5634d04…` @0x100000、SystemOS `b4908cde…` @0x16a600000，
  共 9,382,658,048 字节），并把 `[userdata]` 几何与根卷 UUID 写进 `board.toml`。
- verified-root 路线**装不下**：OS+SystemOS 的块哈希表约 47 MiB 嵌进内核后，`kernel.macho` 为
  125,374,464 字节，实测打包镜像 **138,211,328 字节**，而 BOOT 分区只有 **71,303,168 字节（68 MiB）**。
- 因此 `CONFIG_XNU_NATIVE_UFS` 与 `CONFIG_XNU_VERIFIED_ROOT_PROBE` 保持关闭；下一步需要
  **T970 板级 UFS 发布路径**：复用 alioth 驱动，但不嵌入 verified-root 哈希表，改为直接发布
  userdata 分区/根窗口，适配 68 MiB 启动分区。

## UFS 移植现状（已准备，未启用）

- 已把 `feeds.toml` 的 `ShengUfs` 指向 `FFT-infra/NativeUfs-alioth@ab54059`（SM8250、device-verified），
  驱动源码可编译；`scripts/build-storage-bindings.py` + `scripts/data/native-storage-original-bindings.S`
  解决 `IOBlockStorageDevice`/`IOMedia` 原始符号。
- 完整链接还缺 **VerifiedRoot `vr_*`**：`build-verified-root-probe.py` 需要 OS 卷验证产物
  （`build/verified-root-os/verification.json`），不只是 IPSW。
- 运行还需要 `findRootLayout` 接受的 **sheng userdata manifest**；T970 是 Android GPT，没有该布局。
- 因此 `board.toml` 的组件/archives、`sm-t970_defconfig` 的 `CONFIG_XNU_NATIVE_UFS` 都保持原样
  （可构建状态），接入内容作为后续工作保存。

## 启动链完成（最新）

PMGR 占位（`ShengPlatformPower.cpp` + `build-platform-power.py`，`CONFIG_XNU_SHENG_PMGR=y`、
`sheng-pmgr=2`）编译并通过 ABI 审计后，内核 `d4914c03…` 的实测结果为：

```
Failed to mount root device @IOKitBSDInit.cpp:984
frames fffffff007a13d5c fffffff007925b50 fffffff0076b1d58 fffffff00798d588 fffffff0073f34a4
```

即 **UEFI → 菜单 → DarwinBoot → arm_init → 引导线程 → bsd_init → AMFI/PMGR → IOKit 根卷挂载**
全部走通；失败原因是没有 UFS 驱动。下一步是第 6 步的存储移植（见 `docs/storage.md`），
不再属于启动链问题。设备 BOOT 仍是诊断镜像，原始 BOOT 待恢复。

## AMFI/PMGR 关卡

`bsd_init` 之后的真实失败（内核 `80cc00ad…`，镜像 `041fcf8c…`）：

```
"AMFI: No PMGR?\n" @ConfigurationSettings.cpp:235
```

即未修改的 AMFI 需要 **ApplePMGR provider**。参考 marble-milacy：用板级
`ShengPlatformPower.cpp`（`build-platform-power.py` 生成受保护的 ApplePMGR 占位 nub，
`CONFIG_XNU_SHENG_PMGR=y` + `sheng-pmgr=2`）即可越过；它依赖同一个 21H461
kernelcache（`f18b4df8…`），ABI 地址可复用。此前的“控制台卡死”实际是
`gc_enable` 对未初始化 ticket lock 的 panic（`gc_initialize` 被跳过），已修复。

## 最新里程碑（本轮）

`PE_init_printf(TRUE)` 内部就是 `vcattach()`，跳过 `initialize_screen` 挡不住。新增
`t970-skip-vcattach.patch`，在 `t970-novc` 下把 `PE_putc` 换成丢弃输出的空回调：

- 内核 `d862c992…`：`PE_init_iokit` 返回后探针 `f32a04c0…` 约 6 秒复位（旧内核
  `4131d5b1…` 的同点探针 `9b0f8f68…` 是不复位的）。
- 同一内核：`bsd_init` 调用前探针 `fa16c47d…` **立刻复位**。

结论：**UEFI→菜单→DarwinBoot→arm_init→引导线程→bsd_init 已全部走通**；
`vcattach`/`gc_enable` 自旋是控制台问题，已用诊断旁路绕过（不是正式修复）。
下一关是 `bsd_init` 内的根卷挂载：没有 UFS 驱动，预期 panic 或静默停住。
设备当前 BOOT 是诊断镜像，原始 BOOT 仍待恢复。

## 总体现状

- 第 1–5 步已完成并提交；第 6 步只完成存储（UFS）输入采集与实现判定，驱动未移植；
  第 7 步主机侧构建链全部打通，设备侧已从「UEFI 无法启动」推进到「内核已交接、
  卡在早期控制台/引导线程」。
- 设备现在**可以被刷写**：Heimdall 1.4.2 有握手 bug，已用 PR #478 补丁自建 CLI
  （`.cache/heimdall/build/bin/heimdall`）。SM-T970 没有 fastboot，只能刷 `boot` 分区。
- 恢复镜像：`out/step7/odin/boot-stock.tar`（当前 Magisk 25.2 boot dump）。
  测试镜像：`out/step7/odin/boot-unixnu.tar`（会按下面的构建步骤重新生成）。

## 已确认的设备进展（按时间顺序）

1. 初始固件在 XBL→UEFI 阶段断言：`TzDxe` 内 `QseeComDxe.c` TEE 初始化失败。
   已在 DSC/`Include/DXE.inc`/`Include/APRIORI.inc` 中禁用 `TzDxe`。
2. 下一个断言：`PILDxe`/`PILProxyDxe` 无 UFS 时读分区失败（`usfpil.cfg`）。
   已同样禁用这两个模块。之后进入 **UniXNU 菜单**。
3. 菜单无输入设备（FD 里没有 SimpleTextIn 生产者；`ButtonsDxe` 只发 Qualcomm 按键协议），
   3 秒倒计时自动启动默认项。
4. `UniXNURamDiskDxe` 最初找不到 initrd：上游 Mu-Silicium 的 SEC **没有保存 x0（ABT 传入的
   DTB 指针）**。已给 SEC 打补丁（见 `package/firmware/patches/0001-sec-entry-arg-hob.patch`），
   把 x0 存进 `gSecEntryArg0` 并以 `gSiliciumEntryArgHobGuid` HOB 发布。
   打上后菜单出现 4 项（xnu/Restart/Power off/Tools），payload FAT 正常挂载。
5. DarwinBoot 交接成功（`DARWINBOOT: hand-off to the kernel`，绿条），但内核在开 MMU 前卡住。
   - 蓝条=内核入口（MMU off），粉条=开 MMU 前。
   - 探针 stage 3（`entry_probe_reset_delay=6`）确认 **MMU 成功打开**（6 秒后 PSCI 复位）。
6. 逐点探针（reset after/before）确认以下函数都返回：
   `_arm_vm_init`、`_serial_init`、第一条 `_kprintf`。
7. 用 reset-before 探针定位到 `PE_create_console` **之前**（该调用在 arm_init 尾部），
   随后尝试重置到内核里进一步定位；`PE_create_console` 内 `ml_io_map_wcomb` 返回，
   之后的 `printf` 探针无法区分「未执行/内部卡住」。
8. 为绕过控制台，加了板级内核补丁 `patches/xnu/t970-skip-early-console.patch`：
   默认不调用 `PE_create_console()`/`PE_init_printf()`，只有 boot-arg `t970-console` 才建。
   重建内核后仍然只有三条阶段条、无 panic。
9. 继续在 `_kernel_bootstrap_thread` 内二分：确认到达 `_idle_thread_create`，
   `_bsd_init` **未到达**。
10. 刚刷入的探针是 `_initialize_screen` **之前**（`entry_probe_reset_after="_initialize_screen"`），
    **结果尚未确认**。注意：`initialize_screen` 在引导线程里还会再初始化一次视频控制台，
    与早先的 `PE_create_console` 属同一类路径，是最可疑的卡点。

## 未提交改动（重要）

设备仓库：

- `board.toml`：payload `size_mib=56`（boot 分区 68 MiB）、`panic_screen` 已按需开关、
  当前残留探针配置 `entry_probe_reset_*`（指向 `_initialize_screen`）。
- `dts/sm-t970.dts`：memory 改为低地址包络 `0x80000000+0x80000000`（T733 做法），
  以覆盖 DarwinBoot 实际分配的 `0xC0000000` 窗口。旧的高地址 `0x200000000` 版本不可用。
- `package/firmware/.../gts7xlwifi.dsc`、`Include/DXE.inc`、`Include/APRIORI.inc`：
  禁用 `TzDxe`、`PILDxe`、`PILProxyDxe`。
- `patches/xnu/series` + `patches/xnu/t970-skip-early-console.patch`：跳过早期 Apple 控制台。
- `package/firmware/patches/0001-sec-entry-arg-hob.patch`：SEC x0 HOB 补丁（**尚未接入
  `scripts/prepare-uefi.py`**，目前只存在于 Mu checkout 工作区里）。

Mu-Silicium checkout（`.cache/uefi-source/Mu-Silicium`，勿依赖其工作区状态）：

- 4 个文件被手改：`Silicon/Silicium/SiliciumPkg/Sec/{Sec.c,Sec.inf,AArch64/ModuleEntryPoint.S}`
  和 `SiliciumPkg.dec`。`package/firmware/patches/0001-sec-entry-arg-hob.patch` 是其 diff。
- 重新准备 checkout 后**必须重新应用**该补丁，否则 payload 卷不会挂载。

本机未提交文件：

- `../UniXNU/unixnu.local.toml`：device/uefi/dtb/ipsw/kernelcache/trust_cache/unique_chip_id，
  trust cache 指向 `build/original-static-system-trust/original-static-system.bundle`。
- `../ipsw/iPad_Pro_HFR_17.7.11_21H461_Restore.ipsw`（6.4 GB，仓库外）。
- `.cache/heimdall/`（带 reset 补丁的 Heimdall 源码与二进制）、`.cache/heimdall-plain/`。
- `out/`（kernel/payload/boot.img/odin tar/备份）。

## 构建与刷写命令（可复制）

```sh
# 1. 把 overlay 和 SEC 补丁送进 Mu checkout
python3.14 scripts/prepare-uefi.py --uefi .cache/uefi-source/Mu-Silicium --extract-dir .cache/stock-inputs/extracted

# 2. 固件（需要 LLVM/lld 在 PATH）
PATH=/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
python3.14 ../UniXNU/unixnu build firmware -D . \
  --uefi .cache/uefi-source/Mu-Silicium \
  --edk2 .cache/uefi-source/Mu-Silicium/Mu_Basecore \
  --local-module refer:edk2=.cache/uefi-source/Mu-Silicium/Mu_Basecore

# 3. 内核（归档脚本要 python3 带 tomllib；设备仓库里建了 .cache/bin/python3 -> python3.14）
PATH=$PWD/.cache/bin:/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
python3.14 ../UniXNU/unixnu build kernel -D .

# 4. payload（trust cache / seed 在 unixnu.local.toml）
PATH=$PWD/.cache/bin:$PATH python3.14 ../UniXNU/unixnu build payload -D .

# 5. 启动镜像（boot 分区上限 71303168 字节；当前镜像 62713856）
PATH=/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
python3.14 ../UniXNU/unixnu bootimg -D . --uefi .cache/uefi-source/Mu-Silicium \
  --fd .cache/uefi-source/Mu-Silicium/Build/gts7xlwifiPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd \
  --dtb out/firmware-inputs/firmware.dtb \
  --ramdisk ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/payload/payload.img \
  --output out/step7/boot.img

# 6. 刷写（设备先进 Download Mode：关机后 Vol Down+Power 插 USB，警告后 Vol Up）
.cache/heimdall/build/bin/heimdall flash --BOOT out/step7/boot.img --no-reboot

# 7. 测试后刷回原状
.cache/heimdall/build/bin/heimdall flash --BOOT out/device-backup/boot.img --no-reboot
```

Odin tar 打包（备用）：`tar -cf boot.tar boot.img`，用 OdinMac 1.1.5 的 AP 槽位。

## 关键文件

- 内核镜像：`../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/kernel/kernel.macho`
- payload：`.../payload/payload.img`（56 MiB，含 kernel/ADT/trustcache）
- 固件 FD：`.cache/uefi-source/Mu-Silicium/Build/gts7xlwifiPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd`
- 固件 DTB：`out/firmware-inputs/firmware.dtb`（采集自 `/sys/firmware/fdt`）
- 设备备份：`out/device-backup/{boot,dtbo,vbmeta}.img`（boot sha256 `6f49af2f…`）

## 诊断工具

- 探针：`[payload] entry_probe_reset_delay = 6` + `entry_probe_reset_after/_in/_before`
  生成内核入口色条与定时复位；每次改探针要重建 payload + bootimg 再刷。
- panic 屏：`panic_screen = true`（需要 Mu 的 `FrameBufferSerialPortLib/Font.h`）；与探针
  同时开启会占满 kernel 尾部 padding，二选一。
- 已禁用的调试路径：`TzDxe`/PIL 是固件；`PE_create_console` 跳过是内核补丁。

## 待确认 / 下一步

1. **先确认刚刷的 `initialize_screen` 探针结果**（会/不会重启）。若到达，卡点在
   `vm_commpage_init`/`mac_policy_initmach`/`bsd_init` 之间；若不到达，卡在
   `PE_init_iokit`/`kernel_startup_initialize_upto` 或更早。
2. 控制台是目前最强嫌疑：T733 移植用自绘 framebuffer 控制台（`native-console-debug-output`）
   替代 Apple vc。建议给内核加一个极简的“屏幕 kprintf”（复用 panic 屏的绘制方式），
   或移植 T733 的早期入口/console 补丁，否则永远看不到内核日志。
3. 一旦越过控制台，预期下一个失败是根卷（没有 UFS 驱动），那时回到第 6 步的 UFS 移植，
   参考 umi/alioth 的 NativeUfs fork（双 stream `0x0e0`/`0x4e0`、固件状态接管）。
4. 把 SEC x0 HOB 补丁接入 `prepare-uefi.py`（应用 + 校验），否则干净 checkout 无法复现。
5. 清理 `board.toml` 的探针残留，并提交上面所有未提交改动（含 `docs/handoff.md` 本身），
   更新 `porting.toml` 对应 area 的 findings/evidence。
6. 设备当前 boot 分区被测试镜像占用；交付前刷回 `out/device-backup/boot.img`。

## 参考

- T733（同为三星平板，SM7325）：<https://github.com/RigoLigoRLC/unixnu-sm-t733>
  - `dts/board.dts` 低地址 memory 包络 + `owned_memory_size="auto"`；
  - `patches/t733-xnu/early-entry/*` 早期入口/MMU/framebuffer 映射与阶段标记；
  - `native-console-debug-output.patch` 自绘控制台。
- UniXNU 文档：`porting/uefi-firmware`、`porting/ufs`、`guide/debugging#green-bar`。
