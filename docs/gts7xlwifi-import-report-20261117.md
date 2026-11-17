# 为什么"把人家的驱动加进来"这么费劲

2026-11-17 · 对照对象 `rui12366B/UniXNU-gts7xlwifi`（快照 `.cache/reference-gts7xlwifi-88b34f9`，远端 `88b34f9`）

## 结论

1. **驱动代码早就搬完了，不是"没加"。** 显示、输入、GPU 探针、Wi-Fi/S Pen 这几层与参考仓库逐字节一致，
   内核补丁是参考的超集，实际启动命令行与对方 main7 只差两个可选开关。今天没有一行是因为"驱动没搬"而缺的。
2. **卡住的地方不在对方仓库里。** 缺的是板级契约：固件（两边是两套固件工程，设备上跑的 FD 已实测就是我们自己的
   Mu-Silicium 构建）、固件的内存图（对方 `PlatformMemoryMap.c` 导出 conventional memory 并配 `t970-dram-end`；
   我们的 MemoryMapLib 静态表只给 3.84 GiB 握手窗口；内核 `patches/xnu` 的 arm_init.c:385 已实现
   `t970-dram-end`/`t970-dram-extend`/`t970-dram-holes` 解析，但命令行没传、固件也没导出更大的可用区）、
   以及必须从本机提取的签名固件。**存储/Data 已不再是缺口**：73 GiB APFS Data 卷自 2026-11-15 起在设备上
   跨重启持久（Recovery `79d024fb`，`evidence/storage/data-persist-79d024fb-20261115`），与对方 `ufsrw` 的差别
   是机制（我们是在 unixnu 分区上播种的 APFS Data，对方是 UFS 原生 Data 卷），不是「有没有可写存储」。
   这些在对方仓库里是外部输入，不是代码。
   提取的签名固件。这些在对方仓库里是"外部输入"，不是代码。
3. **"人家好使"只在功能层有据，帧率没有共同口径。** 对方自己的 porting 记录里，显示区的下一步还是
   "Measure frame pacing with the GPU frame trace"。所以现在这 24.7 ms 不是"他们 16.7、我们 24.7"的对比结果，
   我们一直在没有基线的情况下猜。

## 一、源码对照：已经同字节

逐文件 `diff` 结果（去掉行尾差异后逐字节比较）：

| 范围 | 结果 |
| --- | --- |
| `drivers/ArmCpu/`、`drivers/ShengHidInput/`、`hal/` | 完全一致 |
| `package/GpuProbe.cpp`、`T970FtsTouch.cpp`、`T970Pen.cpp`、`T970WifiStack.cpp` | 完全一致 |
| `drivers/GopFramebuffer/` | 仅 `NativeGOPPresenter.cpp`、`NativeLegacyDisplay.cpp` 两个文件不同，差异是我们自己加的埋点（PHASE deliver/after、空闲回 boot memory） |
| `drivers/Adreno650/` | 仅 `NativeAdrenoAccelerator.cpp` 不同，且本仓库编译时关闭 |
| `dts/gts7xlwifi.dts` | 一致；本地另有 `sm-t970.dts`、`sm-t970-peripherals.dtsi`、`sm-t970-reserved.dtsi` |
| `patches/xnu/` | `comm -23` 检查：参考的补丁文件本地**一个都不缺**，本地另加 48 个诊断补丁（`t970-smp-*`、`t970-ui-*` 等），`series` 顺序不同 |

设备上实际生效的命令行（从 `out/main7-direct-ready-20261117/boot.img` 的 `::/EFI/UniXNU/unixnu.toml` 读出，994 字节）
已包含 `gpu-addon=1`、`tu-debug=noubwc,nocb`、`pipa-gpu=12`、`fb-gpu=1`、`dpu-scanout=2`、`vsync=60`、`cpufreq=4`、
`t970-fb-wc=1`；相对对方 main7 只少 `wallpaper-freeze=1`、`t970-fb-src-wb=1` 两项
（后者是条纹的临时补丁，我们已用 sRGB/BGRA8 修法替代）。**参数层面已经没有"对方开了我们没开"的开关。**

## 二、真正对不上的四件事

### 1. 固件不是同一个构建（已实测确认）

两边 `board.toml` 的 `[firmware]` 段一字不差，指向的是**同一台平板应该有的那份固件**：
`../firmware-t970` 的 Renegade edk2 平台 `Platform/Samsung/sm8250/gts7xlwifi-upstream.dsc`，GCC5 构建，
产物 `GTS7XLWIFI_UPSTREAM.fd`。但那是一行**输入声明**，不是我们实际部署的东西。

实际情况是两套固件工程：

| | 参考 | 本仓库 |
| --- | --- | --- |
| 固件树 | 自己的 `../firmware-t970`（Renegade edk2） | 上游 `Project-Silicium/Mu-Silicium` @ `4bd8ae83` |
| 平台 | `Platform/Samsung/sm8250/gts7xlwifi-upstream.dsc` | 本地 `Platforms/Samsung/gts7xlwifiPkg/gts7xlwifi.dsc`（untracked，由 `scripts/prepare-uefi.py` 把设备 XBL 里提取的厂商 DXE 包装进去） |
| 工具链 | GCC5 | CLANGPDB |
| 产物 | `GTS7XLWIFI_UPSTREAM.fd` | `SILICIUM_UEFI.fd`，sha256 `515105d758a9d61078dffce5012db0754a71cec351a1bb34b30ee791196b5690` |
| 部署方式 | 固件刷一次，之后只更新 ESP 里的 payload | 每次刷 `RECOVERY`，镜像头部 112 字节 shim 后就是整份 FD |

实测确认（本轮）：把 `out/main7-direct-ready-20261117/boot.img` 偏移 4096、长度 3145840 的段取出，
跳过 112 字节 shim，剩下的 FD 逐字节就是 `515105d7…`。**设备上现在跑的是我们的 Mu-Silicium 固件，
不是参考的 `GTS7XLWIFI_UPSTREAM.fd`。**

`firmware-t970` 到底是什么：一份独立的 UEFI 固件仓库（edk2 + Mu-Silicium 风格的平台包），
承担参考那边"UEFI 这一半"的全部内容——`Platform/Samsung/sm8250/gts7xlwifi-upstream.dsc/.fdf`、
`Upstream/gts7xlwifi/Memory/PlatformMemoryMap.c`（conventional memory 与 640 MiB 窗口就定义在这里）、
`LocalPackages/DarwinBootPkg`（`loader = "firmware"` 时装载 XNU 的 DarwinBoot，含 `T970ExportMemoryMap`）、
`menu-t970/`、`GPLDrivers/`、`Common/edk2-platforms`、`tools/build-ipados.sh`、`tools/wrap-raw.py`，
外加配套的 `../board-t970`（测量与分区数据）。它在参考仓库里的地位，等同于我们的
`.cache/uefi-source/Mu-Silicium` + `Platforms/Samsung/gts7xlwifiPkg`。

本地没有这棵树（2026-11-17 复查）：`/Users/cakeal` 与 `/tmp` 下搜不到 `firmware-t970`、`board-t970`、
`gts7xlwifi-upstream.dsc`、`build-ipados.sh`、`wrap-raw.py`、`PlatformMemoryMap.c`、`GTS7XLWIFI_UPSTREAM.fd` 中的任何一个；
我们手里的只有他们的 device repo 快照（`.cache/reference-gts7xlwifi-88b34f9` 与 `/tmp/gts7xlwifi`）。
这一点更早也记过：`docs/wholesale-vs-reference.md:34`。

我们的等价物是另一套，不是空手：上游 Mu-Silicium @ `4bd8ae83` + 本地生成的
`Platforms/Samsung/gts7xlwifiPkg`（由 `.cache/create-t970-firmware.py` / `scripts/prepare-uefi.py` 从上游 `r8qPkg`
的 DXE/APRIORI 列表派生，厂商 DXE 二进制从本机 T970 XBL 提取，剔除 UFS/USB DMA 等不 dispatch 的驱动），
编出 `SILICIUM_UEFI.fd`。差别在于这份 Pkg 里没有 `PlatformMemoryMap.c`、没有固件内的 `DarwinBootPkg`、
没有 UEFI 菜单与按键、没有 UFS handoff / vendor chain / low-FD MMU helper——也就是那三个 define 的落点。

这份差异是怎么来的（本仓库 git 历史）：

- `f1c236f` 按教程做了自己的固件接入：`[firmware] config = "gts7xlwifi"`、
  `dsc = "gts7xlwifiPkg/gts7xlwifi.dsc"`、`fd = "Build/gts7xlwifiPkg/{target}_CLANGPDB/FV/SILICIUM_UEFI.fd"`，
  defines 只有 `DEVICE_MODEL = "sm-t970"`。实际构建日志（`.cache/uefi-source/firmware.log`）也是
  `-p gts7xlwifiPkg/gts7xlwifi.dsc -t CLANGPDB -D FD_BASE=0x9fc00000 -D FD_SIZE=0x300000`，产物即 `SILICIUM_UEFI.fd`。
- `e257999`（"采用上游整包板级配置：archives、patch series、组件与 payload 定义对齐 gts7xlwifi…"）把 `[firmware]` 整段
  换成了参考的：dsc/FD 指向 `firmware-t970` 的 GCC5 产物，defines 换成参考那 10 行，`packages` 换成
  `Common/edk2-platforms`、`GPLDrivers`、`LocalPackages`。payload 参数、archives、patch series 也在同一次提交里对齐。

也就是说：**声明被整包换成了对方的，固件二进制没有（也无法）重建**。所以现在 `unixnu build firmware -D . --uefi <我们的树>`
会直接找不到那个 dsc；而设备里跑的仍是 `515105d7`。这不是"两边天生不同"，是一次配置覆盖留下的双轨状态。

> **2026-11-17 已修复**：`board.toml` 的 `[firmware]` 段已恢复为本仓库自己的 Mu-Silicium 包
> （`config = "gts7xlwifi"`、`gts7xlwifiPkg/gts7xlwifi.dsc`、`SILICIUM_UEFI.fd`、`DEVICE_MODEL = "sm-t970"`），
> 并在注释里保留了参考固件声明的来历、设备上实际运行的 FD `515105d7…`，以及参考固件独有而本包尚无的六项能力。
> 参考那套 Renegade edk2 的声明不再出现在 `board.toml` 中。改动未重建固件、未产生镜像；
> 记录见 `porting.toml` 的 firmware findings 与 evidence。

同一台设备为什么不能直接通用：**板级事实通用，固件的分配策略不通用**。

已经 100% 复用的板级事实：FD base/size（两边都是 `0x9fc00000 + 0x300000`）、display 保留段 `0x9C000000+0x2400000`、
分区几何、vendor DXE 二进制（同一个 XBL）、DTS、内核驱动。这也是 kernel 侧能逐字节一致的原因。

不能通用的部分，是固件"自己怎么花内存、谁负责装载 XNU"。具体到代码：我们的
`package/firmware/Platforms/Samsung/gts7xlwifiPkg/Library/MemoryMapLib/MemoryMapLib.c`（56 行，按本机 XBL 写）
只把 `DXE Heap 0x98900000+0x3300000` 标成 conventional，没有 `0xD0000000..0xFFC00000` 段、也没有
`0x200000000+0x40000000` 的 High RAM 段；参考那份 `PlatformMemoryMap.c` 把 DXE heap 放在 `0xC0000000`，
并额外打开 `0xD0000000..0xFFC00000` 给 DarwinBoot 放 640 MiB 窗口。

`0x98900000` 与 `0xC0000000` 都不是硬件事实，是各自固件的选址决定；一旦这个决定不同，
`[payload.adt]` 的 `owned_memory_size`、`t970-dram-holes`、`dram-end` 就必须跟着不同。所以"简单移植"确实简单，
但它是一对：搬内存图必须连 payload 参数一起搬。现在的状态是搬了参数、没搬文件。

还有一处容易误读的地方：`board.toml` 的 `[firmware.defines]`（`MEMORY_ENABLE`、`LOW_FD_MMU_HELPER_ENABLE`、
`UFS_INHERITED_HANDOFF_ENABLE`、`VENDOR_CHAIN_ENABLE` …）是从参考抄过来的，但我们的平台 DSC 里
**一次都没有引用这些宏**（grep 整个 `gts7xlwifiPkg/` 无命中）。也就是说这些 define 在本仓库是空转的，
真正决定我们固件行为的是那份本地 DSC 与 Mu_Basecore 的库接线。

### 2. 内存契约差一个数量级（这是 payload 配置，不是固件）

| 参数 | 参考 | 本仓库 |
| --- | --- | --- |
| `[payload.adt] owned_memory_size` | `0x28000000`（640 MiB） | `0xf0000000`（3.75 GiB） |
| DRAM 上限 | `t970-dram-end=0x280000000` | 内核解析已实现（arm_init.c:385），命令行未传 |
| 扩展/洞 | `t970-dram-extend`、`t970-dram-holes`、`t970-memory-outside` 生效 | 同上补丁在，但被 `scripts/pack-wholesale-recovery.py` 明文禁用 |

这三行都在 `[payload]`/`[payload.adt]` 里，是我们自己的打包选择，与固件是谁编的无关。
但参考那边的取值不是随便定的，是照它固件的内存图算出来的：`board.toml:216-260` 的注释逐条引用
`firmware-t970 PlatformMemoryMap.c`（`MEMORY_ENABLE=1`，只导出 DXE Heap `0xC0000000+0xDFC0000` 与
High RAM `0x200000000+0x40000000`，640 MiB 窗口铺在 `0xD0000000..0xFFC00000`）和 `DarwinBoot.c T970ExportMemoryMap`
（填 `t970-dram-holes`）。再加上 `loader = "firmware"`——他们的 XNU 由固件里的 DarwinBoot 装载。
**固件与 payload 参数是一对配套件，拆开任何一个都不成立。**但它解释了为什么
不能"整包搬内核"：对方的内存超集是在它那套 payload 配置上成立的自洽解，直接照抄过来，第一次越界就崩。
整包搬内核的实验已经做过，结果卡在 `ml_wait_max_cpus()`。

顺带回答一个常见误解：参考的 README 里确实有完整 build 步骤，但第 2 步就是 `UNIXNU_UEFI=<uefi tree>`——
`<uefi tree>` 和我们的 `.cache/uefi-source/Mu-Silicium` 是同一个位置，`unixnu.lock` 里没有任何 uefi 条目。
他们自己的 `MIGRATION.md` 写着 `UEFI | firmware-t970 | … | separate uefi-gts7xlwifi repo | later`，
即固件树尚未拆出公开。所以能 1:1 复现的是 kernel/payload 的构建配方，不是固件那一半。

### 3. 存储与 Data 是两套完全不同的布局

- 参考：UFS 原生 APFS Data 卷（`t970-ufs-data=1`、`ufsrw=1`，卷 `5915374F-7A58-4BD3-9C6F-0BD63348ACEA`），
  可持久化，`~6.7 GB` 可用内存的日常使用建立在这上面。
- 本仓库：Android BOOT + F2FS userdata + iPadOS `RECOVERY` + 在 unixnu 分区上播种的 73 GiB APFS Data
  （`sheng-data-persist=2`、`data-fua=1`、`t970-large-data=1`、`t970-large-init=1`）。
  **已设备验证持久**：2026-11-15 Recovery `79d024fb` 上移动主屏图标、重启后改动保留，Data 跨重启读写挂载
  （`evidence/storage/data-persist-79d024fb-20261115/owner-observation.json`）。所以「装 App 的存储」这一项
  不再缺；与对方 `ufsrw=1 t970-ufs-data=1` 的差别是卷的来路与 root 可写策略，不是没有可写 Data。

对"能不能开机、能不能装 App、能不能日常用"影响最大的其实是这一层，而不是 GPU 那几个文件。

### 4. 签名固件只能从本机提取

`a650_zap`、`ADSP` 这类要先从平板上 dump 再打包；对方仓库不放二进制。所以"clone 下来照着 build"这条路走不通，
必须在本机做提取和绑定——这一步我们已经做了（`package/firmware/` + `docs/firmware.md`），但它解释了为什么
"照抄对方"不能一键复现。

## 三、对方"好使"的可核对范围

参考 README 的功能清单（八核 4+3+1、~6.7 GB、UFS 持久 Data、Adreno 650 GPU 合成+自恢复、触摸/按键/亮度/扬声器/麦克风/振动/
关机充电、Wi-Fi 上网、蓝牙、S Pen 压感、USB 接 Mac 被识别为 iPad）有据可查——那是它 `porting.toml` 里
`status = "device-verified"` 的部分。

但**帧节奏不在其中**：

```toml
[[area]]
id = "display"
status = "device-verified"
completion = ["Desktop without stripes; swaps retire by direct scanout."]
limits = ["120 Hz and brightness curve are not tuned."]
next_action = ["Measure frame pacing with the GPU frame trace."]
```

"swaps retire by direct scanout"只说明帧**能**从直出路径退掉，不说明每秒 60 帧。对方把测帧节奏列为下一步，
和我们现在的处境是同一件事。

## 四、我们现在的实测

`evidence/display/main7-direct-20261117/report.json`（32 字节 boot.img `33a88fa5…`）：

| 指标 | 值 |
| --- | --- |
| 4 个 2 s 窗口 flush/latch | 37/36、78/79、80/80、81/81 |
| 窗口平均帧间隔 | 32018 / 23995 / 23913 / 22985 µs |
| 合计 | 276 次 latch，0 次 GPU 拷贝回退 |
| 间隔样本 | 272 个，197 个超过 16.7 ms |
| 加权平均 | 24706.5 µs |

判定原文：`DPU direct scanout and USB verified. Sustained 60 FPS is not met.`

更早一次启动的 syslog（`out/pairing-runtime-20261116/syslog-33a88fa5.txt`，91 条 `t970 scanout:` 行）里，
两秒窗口的 flips 在 23–98 之间波动（约 11–49 fps），而 latched 与 flips 始终几乎相等。
**这说明帧不是"60 fps 生产出来后被丢掉"，而是以 20–45 fps 的节奏被生产出来。**
但直出路径里 flip → latch → retire 是串行的，所以还需要拆分确认时间花在生产端还是确认端。

## 五、下一步的最小验证（不需要改打包）

把一帧拆成两段，各一个计数器：

- `gap` = 上一次 latch 确认 → 本次 flip（合成、提交、`gpuWrote` 等的那条 GPU 栅栏）
- `ack` = 本次 flip → CTL flush 位确认（我们的 latch 轮询）

判读：`帧间隔 ≈ gap + ack`。

| 结果 | 含义 | 方向 |
| --- | --- | --- |
| `gap` 大（> 20 ms） | 合成/提交/GPU 栅栏慢 | Metal、Turnip、命令缓冲 |
| `ack` 大（> 3 ms） | flip 之后等不到 CTL 确认 | 我们的 latch 轮询与 flip 路径 |
| 两段都小但间隔大 | 采样/统计口径问题 | 先修测量，再谈优化 |

这套计数器后来已作为 `cadence-a` 实现，实现位置明确：
`drivers/GopFramebuffer/NativeLegacyDisplay.cpp` 的 `flip()` 直出分支 + `latchTick()`，
页面输出走 `package/BootProgress.c` 的一行 `CADENCE`。21H461 内核、prelink、回归测试和 Recovery 回读已通过，
产物为 `out/cadence-a-20261117/boot.img`（SHA-256 `900e487a…`）。实机 58 秒交互采集得到 1796 次 flip/latch、
0 copy fallback、0 CTL timeout；平均间隔 27.083 ms，其中 gap 17.758 ms、ACK 9.697 ms，两者之和与间隔相差约 1.4%。

ACK 等的是实际面板刷新：当前配置 60 Hz，随机相位下平均等待本来就接近 8.3 ms，不能为压数字而提前释放仍可能被扫描的
IOSurface。`cadence-b` 因此不改 retire，只把 gap 再拆为上一次 latch 后的 swap 到达时间，以及 swap 已到达后的
fence/映射/队列时间，同时导出现有 GPU fence wait；其 Recovery `ed73a75e…` 已完成主机构建、prelink、回读和上传，
并已在 21H461 桌面完成 64 秒交互采集。1981 次 flip、1982 次 latch 中没有 copy fallback 或 CTL timeout；
平均帧间隔 26.510 ms。17.165 ms active gap 又分为平均 11.467 ms 的 swap 到达和 5.698 ms 的 post-arrival；
1942 个 active gap 中 1709 个遇到未完成 GPU fence，fence 等待平均 7.592 ms。瓶颈同时存在于上游产帧和 GPU 完成，
不是单独的 DPU latch 或轮询问题。

补充一条源码核对：打包的 AdrenoMetal 插件确实从 `kern.bootargs` 读取 `tu-debug=` 并写入 `TU_DEBUG`；
`pipa-turnip-debug=` 对当前前端无效。当前 `tu-debug=noubwc,nocb` 因而不是“看起来相同但没有被消费”。另一方面，
`ca-triple-buffer=1` 和 `ca-free-wakeup=1` 的现有实现都显式限定 `WindowServer`，本机 iPadOS 渲染服务是
`backboardd`，不能把这两个 macOS 开关当成已生效的对齐项。

## 六、排序建议

1. 保持 `cadence-b` 的显示和 GPU 配置，启用现有 GPU 诊断链，取得 `commit → scheduled → completed`、每个 pass 的硬件时长和提交/退休记录。
2. 将平均 11.467 ms 的 swap-arrival 与 backboardd 的命令缓冲提交节拍关联，区分“上一帧完成回调后才开始下一帧”和 CPU/QuartzCore 自身延迟。
3. 将平均 7.592 ms 的 fence 等待拆为排队、实际 GPU pass 和完成回调；在证实唤醒尾延迟前不改 IRQ，在任何情况下都不提前绕过 CTL 确认。
4. 想验证"换固件有没有用"：本机没有 `../firmware-t970` 这棵树（已确认 `/Users/cakeal/vsc` 下不存在），
   要么拿到它，要么按 `gts7xlwifi-upstream.dsc` + 那组 define 在我们自己的 Mu-Silicium 树上重建一次 FD；
   换 FD 会动启动链和内存布局，必须单独一轮验证，不能与帧率诊断混在一起。
5. 内存/存储/固件这三件事单独排期——它们是"能不能像对方一样日常用"的门槛，不是"卡不卡"的原因，
   两者不该混在同一次改动里。

---

报告最初形成时未执行构建、打包或刷机。后续 `cadence-a` 和 `cadence-b` 均已完成构建、刷机和实机测量；
`board.toml` 与显示驱动的其他既有未提交改动保持原样。
