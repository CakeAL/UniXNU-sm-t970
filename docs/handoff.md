# SM-T970 移植交接（2026-11-01）

接手者请先读本页，再看 `porting.toml`、`docs/bring-up.md`、`docs/storage.md` 和
`evidence/bring-up/README.md`。

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
