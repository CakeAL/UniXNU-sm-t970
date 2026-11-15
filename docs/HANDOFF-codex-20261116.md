# SM-T970 交接（2026-11-16 凌晨，wholesale 分支）

承接 `docs/HANDOFF-codex-20261115b.md`。那份的验收清单、危险规则（只写 RECOVERY、iPadOS
userdata 区间、证据只收文本、无设备观测不得声称可用）**全部仍然有效**。

本文件记录今天从"能进桌面"推进到"GPU 合成 + 扬声器 + 振动 + USB 设备模式"之后，
**当前卡住的那一件事**（桌面小部件白屏 / 设置页花屏）的全部事实、已排除的假设和下一步实验，
以及其余驱动的状态。写给人接手，不需要重新摸索环境。

---

## 0. 环境（与 15 日相比有两处变化）

- 设备仓库 `/Users/cakeal/vsc/UniXNU-sm-t970`，分支 `gts7xlwifi-wholesale`，当前基线 `1361c29`。
  框架 `/Users/cakeal/vsc/UniXNU`。参考项目 `/Users/cakeal/vsc/gts7xlwifi-upstream`（非 git，= 上游 `main` `88b34f9`）。
- **`/tmp/py314` 已不存在**。用 `/opt/homebrew/opt/python@3.14/libexec/bin`（这里的 `python3` 才是 3.14；
  `/opt/homebrew/bin/python3` 是别的版本，`import tomllib` 会失败，构建脚本会在 `build-arm-driver.py` 处炸掉）。
- 新增依赖（今天为了重编 Metal 插件装的）：`brew install shaderc glslang`（`glslc`、`glslangValidator`）。

内核重建（四个环境变量缺一不可）：

```sh
cd /Users/cakeal/vsc/UniXNU
export PATH=/opt/homebrew/opt/python@3.14/libexec/bin:/opt/homebrew/bin:$PATH
UNIXNU_UEFI=/Users/cakeal/vsc/UniXNU-sm-t970/.cache/uefi-source/Mu-Silicium \
T970_DEVICE_DIR=/Users/cakeal/vsc/UniXNU-sm-t970/kits \
T970_QCA_BLUETOOTH_DIR=/Users/cakeal/vsc/UniXNU/drivers/QcaBluetooth \
T970_ATH12K_WIFI_DIR=/Users/cakeal/vsc/UniXNU/drivers/Ath12kWifi \
python3 ./unixnu defconfig gts7xlwifi_defconfig -D ../UniXNU-sm-t970
# 同上环境再跑：python3 ./unixnu build kernel -D ../UniXNU-sm-t970
```

**必须显式 `defconfig`**：只 `build kernel` 不会重生成 `.config`，`# CONFIG_XNU_NATIVE_ADRENO is not set`
会保留（profile 先写 "not set"，board 的 `=y` 必须最后落盘才生效）。产物
`/Users/cakeal/vsc/UniXNU/out/sm-t970/ipados-17.7.11-21H461/gts7xlwifi/kernel/kernel.macho`
（`out/sm-t970/ipados-17.7.11-21H461/sm-t970/...` 是旧零散移植内核，别拿错）。

打镜像 / 刷机：

```sh
cd /Users/cakeal/vsc/UniXNU-sm-t970
python3.14 scripts/build-boot-progress-page.py --mode 2 --large-data-seed \
  --data-ramdisk out/dual-system/overlay-inspection-20261115/reference-fresh-73g.dbr \
  --kernel-arg build-tag=<tag> --kernel-arg ... --drop-kernel-arg ... \
  --owner-trust-cache out/trust-bundle-<tag>/owner-trust.bundle \
  --kernel /Users/cakeal/vsc/UniXNU/out/sm-t970/ipados-17.7.11-21H461/gts7xlwifi/kernel/kernel.macho \
  --output out/dual-system/wholesale-inputs-20261115/boot-progress-page/page-<tag>

nohup sh scripts/flash-recovery-when-detected.sh <img> <sha256> 3600 > /tmp/flash-<tag>.log 2>&1 &
```

打包器硬约束（`scripts/pack-wholesale-recovery.py`，违反时报 `Unsafe storage or memory switch`）：
命令行必须带 `data-fua=1`、`native-ufs-root=1`；不得带 `t970-dram-end`/`memory-outside`/`data-reset`/`sheng-log`；
payload 内容 ≤ `0.95 × size_mib`，`size_mib=72` → **71,722,598 B**；payload 里
`Payloads/kernel.macho.trustcache` 与 `scratch-data.img` 默认必须与底座镜像逐字节相同，
换 trust bundle 必须显式 `--trust-cache <bundle>`（`build-boot-progress-page.py --owner-trust-cache` 已打通）。

heimdall 的三个坑（今天都踩过）：
1. `Failed to detect compatible download-mode device` 紧跟 `heimdall detect` 成功 → 直接重试一次即可。
2. 一次会话**只能写一个分区**（`--CACHE` 成功后再写 `--RECOVERY` 必挂）。
3. 会话被中断后设备留半开协议状态（`Failed to send handshake! Protocol initialisation failed!`），
   `heimdall` 自己清不掉，**只能长按电源强制关机后重进 Download Mode**。

---

## 1. 已经设备验证可用的功能（含镜像哈希，可直接引用）

| 功能 | 镜像 | 关键参数 | 证据 |
| --- | --- | --- | --- |
| 进桌面 / 触控 / 亮度 / 关机键 / 音量键 | `79d024fb…`、`3c96d2fe…` | 大 Data 种子 | `evidence/storage/large-data-y-20261115/` |
| S Pen 当 Apple Pencil | `79d024fb912dec2c25e1730ed78817488b8606fb3541ae5ffe24207fbb781bf2` | `t970-pen=7` | `evidence/input/pen-79d024fb-20261115/` |
| Data 跨重启持久（搬动图标后仍在） | 同上 | `t970-large-data=1 t970-large-init=1 sheng-data-persist=2` | `evidence/storage/data-persist-79d024fb-20261115/` |
| GPU 合成（Metal 插件接管每一帧） | `3f488107fdf08a615773369ec51d2a73672ca16c689ea069e369d49a2b2890db` | `pipa-gpu=12 gpu-addon=1 fb-gpu=1` + 正确 trust bundle | `evidence/gpu/a650-b-20261115/` |
| 直接扫描 `dpu-scanout=2`（滑动变顺） | `95169672ac5a3fd94fc8164913127a5429506d248db98ffcbd52c6b1639bfa8e` | 追加 `dpu-scanout=2 wallpaper-freeze=1` | 同上 |
| 扬声器（ADSP + T970Audio HAL） | `9f1cabb1cea8fa6507a1c09be2f022573f2b957dbf882d3aaad7f5a16eb198dc` | `t970-adsp=2 t970-audio=32`，addon 带 `firmware/adsp/adsp.mbn` | `evidence/audio/speaker-9f1cabb1-20261116/` |
| 振动 | 同上 | `t970-haptics=3`（**必须带值**，裸写 `t970-haptics` 等于关闭） | `evidence/input/haptics-9f1cabb1-20261116/` |
| USB 设备模式（Mac 认成 iPad） | `6c0b77a4f7da3b001f72b39dfa22d93ab6827fe491c4f89d22f3208d45c80f69` | `t970-usb=37 t970-qud-retry=1 t970-qud-resume=1` | `evidence/diagnostics/usb-device-mode-20261116/` |

### 1.1 GPU 合成的两个必须项（今天查清的）

- **trust bundle 是唯一的门槛**：第一版镜像 `c5f88b11…` 里 `SWAP … gpu offers=0`（插件根本没被加载），
  换成正确 CDHash 的 bundle 后 `offers=2871 done=2871`。根因是 `scripts/build-t970-trust-bundle.py`
  读 SuperBlob 的 BlobIndex 数组偏移写错（应为 **12**，`magic u32 + length u32 + count u32`；旧代码用 8，
  于是对 SuperBlob 整体求哈希）。现已修正，并与 `codesign -d -vvv` 逐个核对。
- **`t970_usb_start()` 曾经没有任何调用者**：本移植链接的是 `package/T970Power/BatteryService.cpp`，
  而参考移植在 `package/T970Battery.cpp:456-461` 里启动 USB。已在 `BatteryService.cpp:317` 补上调用
  （`extern "C" void t970_usb_start(void);`），`T970UsbProbe.cpp:55` 的 MUIC 等待从 600×100 ms 放到 1800×100 ms。
  验证方法：`llvm-objdump` 里 `t970_battery_start` 内出现 `bl … <_t970_usb_start>`。

---

## 2. 当前卡住的问题：桌面小部件白屏 + 设置页花屏

**现象**（多张设备照片）：桌面壁纸、图标、菜单栏、应用图标都正常；**只有小部件区域是白色圆角矩形**，
右侧同样有一块白；设置页打开时内容花/缺，等一会儿才刷出部分内容。

**这不是 GPU 引入的**。最早那批只有 CPU 拷贝、Metal 插件根本没加载的镜像（`c5f88b11…`，
`gpu offers=0`）桌面照片里白块就已经在了。所以问题在合成器/图层的渲染或呈现路径上，
不在 GPU 驱动启用与否。

### 2.1 已排除的假设（都在设备上做过对照，不要重复）

| 假设 | 实验镜像 | 结果 |
| --- | --- | --- |
| `dpu-scanout=2` 直接扫描导致 | `1f01649e…`（去掉 scanout，其余不变） | 小部件仍白；去掉后启动页恢复可见 |
| `wallpaper-freeze=1` 冻结海报层导致 | `e431e7e3…`（去掉 freeze） | 仍白 |
| UBWC / CB 压缩 surface 被当线性读 | `ce99c443…` / `a182394f…`（`pipa-turnip-debug=noubwc,nocb`） | 仍白 |
| 参考项目的 XR10 规则（Poster 系进程保留 10-bit 宽色域） | `0f9ac357…`（见 §2.2） | 仍白 |
| 12 条签名文本补丁没生效（应强制 BGRA8） | 同上镜像的诊断行 | **`FIX parsed=12 applied=12`，补丁全部生效** |

诊断行 `FIX parsed=%u applied=%u` 是今天新加的（`package/BootProgress.c`，读
`cs_text_fixup_parsed/applied`）。`applied < parsed` 才说明 shared cache 与补丁记录的原字节不匹配。

### 2.2 今天动过但**没解决问题**的一处（保留，别当成功）

参考项目 `docs/host-patches/adreno-metal-main/0001-gts7xlwifi-local-changes-next2.next11.patch` 把
`supportsExtendedXR10Formats` 对所有进程回答 0；上游/框架源码只对"名字不含 Poster 的进程"回答 0，
于是 `CollectionsPoster` 之类仍拿到 XR10。我已按参考改成无条件 0，并**重编了整个 Metal 插件**：

- 补丁记录在 `patches/adreno-metal/xr10-withheld-everywhere.patch`，直接改的是框架
  `/Users/cakeal/vsc/UniXNU/drivers/AdrenoMetal/NativeBridgeMetalFrontend.mm:4971`。
- 重编步骤（机器上原本没有 Mesa/Turnip 树，全按 pin 重拉）：
  `git clone --filter=blob:none` Mesa `https://chromium.googlesource.com/external/gitlab.freedesktop.org/mesa/mesa`，
  `git sparse-checkout set include src/freedreno/vulkan src/vulkan`，checkout pin `85fda3b36405bcaea8bffc64aa4f2651dc90770d`；
  `git clone --depth 1 --branch development https://github.com/steelbrain/metal2vulkan .cache/gpu-reference/metal2vulkan`
  再 `git fetch --depth 1 origin 555b13d57e09bff70996a88cff64f1275256d5cf && git checkout`；
  `brew install shaderc glslang`；然后把**已发布的** `libvulkan_freedreno.dylib` 放进
  `build/mesa-tu-ios/src/freedreno/vulkan/`（`build-adreno-metal-plugin.py` 会 copy+strip+self-bind，
  对已签名库会报 `no chained fixups`，所以这一步要手工做：拷原库 → `codesign --force --sign - --pagesize 4096
  --identifier org.blu-sharky.turnip` → 写 Info.plist → 签 bundle；`adrenoprobed` 也用原已签名二进制）。
- 结果：新插件 CDHash `4490c306601dd01d9c0539f71c86b43687a89dbc`（Turnip 仍是 `8a4d6e6c…`），
  trust bundle `out/trust-bundle-xr10-20261116/owner-trust.bundle`（61,480 B，sha `46689a1a…`），
  镜像 `0f9ac3574e699c5be1d83f951a1b7d53f0353c721d8b8241884787e93fb7ff63` 已刷入并验证**白屏依旧**。

结论：XR10 不是这个白屏的原因（参考移植遇到的是"整屏条纹/拖影"，不是"只有小部件白"）。

### 2.3 下一步最有价值的实验（按信息量排序）

1. **在 Data 上把插件彻底移除后再看一次**。`/private/var/ngpu` 是持久的，镜像撤掉 addon 后插件仍在。
   删掉 `addons/NativeAdrenoMetal.bundle`、`publish`、`daemon` 三处重启，确认"没有 Metal 插件时小部件是否也白"。
   如果照样白 → 与插件无关，往 CoreAnimation/图层的呈现路径查；如果有颜色 → 插件内 surface 取样路径（alpha/预乘/格式）有问题。
2. **拿参考项目的同机照片对照**。参考移植 (`gts7xlwifi-upstream`) 的桌面小部件是否正常？如果他们正常，
   逐项 diff `board.toml [payload] text_fixups`、`[adt.product.*]`、`artwork-display-gamut`（我们是 `sRGB`，
   与参考一致）以外的东西，特别是 `[payload.adt]` 里我们精简掉的产品键。
3. **查白屏区域到底是"内容为空"还是"内容为白"**：在诊断页上加一行，把 `IOSurface` 的
   `pixelFormat`/`bytesPerElement`（合成器提交的 surface 描述）打出来。如果小部件那层是 8bpp/双平面，
   就是格式选择问题（和参考 `int-089` 记录同一类）；如果就是 4bpp BGRA8，就是内容本身被画成白。
4. **`iconservicesagent` / `ChronoKit` 系进程的退出码**：今天多张照片里都有 `iconservicesagent`
   `sig=11`（早期）或 `status=9 sig=9`（后期，AMFI 杀）以及 `bluetoothd status=100`。
   白屏小部件的内容由这些进程渲染，进程被杀干净也会表现为白块。`lite=1` 会通过 `disabled.plist`
   关掉一批 daemon（`package/BootWatchdogPolicy.c:24-34`），确认小部件进程没被 `lite` 关掉。

---

## 3. 其余驱动的状态

- **Wi-Fi / 蓝牙**：内核侧参数（`t970-wifi=6 t970-wifi-svc=1 t970-bt=257`）与用户态都在
  `addon-all.bin` 里（`wifi-bin/unixnu-wpa_supplicant`、`bt-bin/BlueTool`、`bt-bin/bluetoothd`、
  `wifi-xpc/launchd.plist` + `.sig`）。**卡点**：`t970-wifi-svc=1` 需要在启动时把
  `/private/var/ngpu/wifi-xpc` 挂到 `/System/Library/xpc`（`kern_exec.c` 里 `t970_wifi_xpc_written`
  那次启动会推迟到下一次启动），而**真正执行挂载的那次启动卡在了 loader handoff 彩条页**
  （镜像 `27a6059c…`，照片证据在对话里；参考移植记录同类失败："combo11/13a/14/15 在 cache 刚被改写后挂载，
  然后 PID 1 卡在一个永不完成的 UFS 写"）。现在设备跑的是不含 `t970-wifi-svc=1` 的 `0f9ac357…`，
  所以 supplicant 和被打补丁的蓝牙 daemon 都没加载，`bluetoothd status=100` 退出就是这个原因。
  下一步要么改成"下一次启动再写、再下一次挂载"的两段式，要么在挂载前等待写完成。
- **USB 配对**：设备模式通了（`05ac:12ab`，`usbmuxd` 里能看到），但 Mac 侧
  `python3 scripts/mac-usb-check.py` 显示 **udid 全是 `f`**、`lockdownd: no answer: timed out`，
  Mac 弹窗里出现"缺少值。"。说明设备没上报序列号。可用真机序列号 `R52N71CDBNM`（来自
  `out/dual-system/firmware-inputs-20261114/device-apnhlos-20261115/readback.json`）。
  待查：序列号应该由 ADT `/chosen` 的哪一段给出（参考 `board.toml` 里**没有**显式写序列号）。
- **传感器 / SLPI**：需要 `slpi` 固件。设备回读目前只有 `adsp.*` 与 `a650_zap.*`，
  需要补一次 `/vendor/firmware_mnt/image/slpi*` 的读取。参数 `t970-sensors=243` 已在命令行里。
- **摄像头**：参数 `t970-camera=513` 还没上过命令行，也未验证。
- **性能**：`0f9ac357…` 的诊断行 `GPU last: cache_ms=299 MB=4706 per_sub_us=0`
  —— 一秒窗口内做了 **4.7 GB / 299 ms** 的 CPU cache maintenance，这是卡顿的量化来源（
  参考移植对同结构记录的是一帧 ~4.4 ms 渲染 + 3 ms 拷贝）。`FB copy_us mean≈21000`（19 MiB / 21 ms）
  说明当前没有走直接扫描。

---

## 4. 命令行现状（`0f9ac357…`，959 字节 / 上限 1000）

```
kt_fixed_zones=120 smp=1 armcpu-spi-ipi=1 armcpu-spi-ipi-base=544 armcpu-self-ipi=1
boot-progress=2 pmgr=2 native-ufs-root=1 native-ufs-stream=0xe0 native-ufs-stream2=0x4e0
sheng-data-persist=2 data-fua=1 offline-mobile-graphics-load=1 offline-legacy-pm=1
offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-validate=1 offline-legacy-phase=4
offline-legacy-transfer=1 offline-legacy-cpu-present=1 vsync=60 lite=1
disable-jobs=com.apple.liveactivitiesd,com.apple.cryptexd,com.apple.routined disable-watchdogd=1
aks=1 offline-hid-input=1 offline-key-events=1 cpufreq=4 cpufreq-cap=2000 qcom-usb-debug=1
qcom-usb-ctl=1 t970-fb-wc=1 native-touch=1 touch-hid=1 t970-touch-xform=5 t970-battery=1
pipa-gpu=12 pipa-turnip-debug=noubwc,nocb gpu-addon=1 fb-gpu=1 t970-large-data=1
t970-large-init=1 t970-pen=7 t970-wifi=6 t970-bt=257 t970-adsp=2 t970-audio=32
t970-haptics=3 t970-sensors=243 t970-usb=37 t970-qud-retry=1 t970-qud-resume=1
build-tag=xr10-off-a
```

参考移植实测行（912 字节）在 `gts7xlwifi-upstream/docs/menu/unixnu.toml`，差异清单：

- 我们用 `boot-progress=2`（持续显示；`3` 会在显示驱动接管后撤掉，白屏就看不到诊断行）。
- 我们**没有** `wallpaper-freeze=1` / `dpu-scanout=2`（这两项已证明与白屏无关，是性能项，等 §2 解决后再加回）。
- 我们**没有** `t970-fb-src-wb=1`（两边代码都没有解析器，纯惰性；为省字节删掉）。
- 我们多出 `t970-pen/audio/haptics/sensors/usb/qud-*`。

参数语义（今天从代码确认，别再猜）：`pipa-gpu=<N>` 是**阶段上限**（≤12），不是位图；
`fb-gpu` 只有等于 1 才生效；`dpu-scanout>=2` 才启用直接扫描；`wallpaper-freeze` 是精确字符串；
`pipa-turnip-debug` 默认就是 `nocb`（即 UBWC 默认开）；`data-fua` / `t970-fb-src-wb` 没有任何解析器。

---

## 5. 记录与提交

- `porting.toml` 已按区更新：`gpu`（driver + trust bundle）、`audio`（ADSP + HAL，implemented）、
  `input`（S Pen、振动）、`storage`（Data 持久）、`diagnostics`（USB 设备模式、白屏/扫描页消失）、
  `packaging`（第二卷实验，已判定不可行）。
  **插入 TOML 数组的条目漏掉行尾逗号会报 `Unclosed array`**，今天踩过两次；`device evidence` 必须有 `command` 字段。
  `python3.14 /Users/cakeal/vsc/UniXNU/scripts/porting-record.py check --device .` 必须通过。
- 设备证据目录（JSON，纯文本）：`evidence/gpu/a650-a|b-20261115/`、`evidence/audio/`、
  `evidence/input/pen-*|haptics-*`、`evidence/storage/data-persist-*`、`evidence/diagnostics/usb-device-mode-*|display-scanout-*`、
  `evidence/packaging/second-volume-probe-20261115/`。
- 图片/镜像都在忽略目录 `out/dual-system/wholesale-inputs-20261115/boot-progress-page/page-*/`。

## 6. 一句话总结

已把"能进桌面"推进到"GPU 合成 + 直接扫描 + 扬声器 + 振动 + USB 设备模式"，
并清掉了两个真实缺陷（trust bundle CDHash 偏移错、`t970_usb_start()` 无调用者）。
**当前唯一挡路的是小部件白屏/设置页花屏**：扫描、冻结、UBWC、XR10、文本补丁五条假设都已用设备对照排除，
证据指向合成器提交的 surface 或小部件渲染进程本身；§2.3 的四个实验是下一步。
