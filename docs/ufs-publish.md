# 根设备发布（t970-ufs-publish）

`t970-ufs-publish=1` 把调查阶段验证过的读取通道接进正式发布路径：先复用固件的 SMMU
handoff 配置做 bring-up，再由 `startRoot` 解析根镜像 manifest、按窗口建立块设备，最后交给
`NativeUfsBlock` 的 owner 校验。发布仍然是 fail-closed：任何一个窗口校验不通过，就一个也
不发布，不挂根。

## 与调查版的区别

| | `t970-ufs-image=1`（调查） | `t970-ufs-publish=1`（本版） |
| --- | --- | --- |
| SMMU | 复用固件 CB0/streams | 同一套，且先逐字段核对 |
| 读取 | `T970ReadTest`/`T970ImageTest` 固定样本 | 正式 `RootWindowRead` 读 manifest/GPT |
| 结束方式 | 读完即 panic，`noPublication=1` | 尝试发布窗口 |
| 块设备 | 不创建 | `NativeUfsBlock`，owner 策略校验 |

## handoff bring-up

`hostBringUpHandoff` 只做三件事：映射 controller 与 SMMU、在 DarwinBoot owned window 内分配
DMA、走和调查版相同的 NOP/上电/TUR 序列。它**不写** SMMU、不写队列寄存器、不写存储。

只要求两件事：`CB0` 仍是活动翻译（`CBAR0=0x100ff`、`CBA2R0=0x1`、`SCTLR0=0xe0`）且
`GFSR=0`；DMA 必须落在 `boot_args` 的 owned window 内。其余状态只记录不判定。

第一版要求固件状态与调查时逐项相同，实机证明这个前提不成立：调查版 `healthy()` 里的
`0x954/0x958`（SID `0xe0`/`0x4e0` 的 park 项）是调查自己的 NOP 测试写进去的，固件并不留下；
`CB0 FSR=0x400` 也是内核之前就存在的旧记录。因此判定改成**故障漂移**：进入时抓一次
`GFSR`/`CB0 FSR` 基线，NOP、上电、TUR 各阶段后必须与基线一致，出现新故障即拒绝。
这和调查版每次读取前后做的比较是同一种判断，不再依赖某个 boot 的寄存器快照。

## handoff bring-up 复刻调查版的准入与 NOP

第一版手写序列在实机卡死（magenta 条后自复位，见下），因此 bring-up 改为**逐字复刻调查版**：

1. 采集 `t970_smmu::collect`、`t970_ufs::collectClocks`、`t970_ufs::collectController`；
2. 同样的准入：`t970_preflight::candidate()`、`canReadController()`、`HCE/HCS`、门铃为零；
3. `t970_preflight::ownsDma()` 保证 DMA 在 owned window；
4. 直接跑调查版的 `t970_nop::run`（含它自己的 `0x60=0` 停队列、`0x50/0x54=dma`、
   `0x60=1` 起队列、SMR/S2CR park、以及一次有界 NOP 和逐项保护状态校验）；
5. `run` 成功后只做上电查询与 TUR，不再重复 NOP。

失败时 panic 会带上 `stage`、`nopStage`（调查版的结果阶段 0–6）、`CB0` 三元组、`smr/s2cr`、
`gfsr/fsr` 和 DMA 地址，正好对应调查版 `Result.stage` 的语义。

## 请求列表必须接管（第一条实机结论）

`t970-ufs-publish=1` 的第一版（BOOT `11a1d635`）停在 magenta 条、没有任何 panic 文本。
magenta 条是内核起来后屏幕上最后的加载器画面（`t970-novc` 下 XNU 本身不出字），所以这代表
**卡死**而不是中止。原因在 handoff 路径少了一步：固件的 UTRLBA 仍指向它自己的请求列表，
`hostNop` 一旦敲响门铃，控制器就按那个缓冲区里的描述符去取命令，机器直接停住，连 panic 都
来不及打印。现在 handoff 路径在取完 DMA 后先 `hostStopQueue` / `hostStartQueue`
把请求列表接管过来（只跳过 SMMU 那一半），再走 NOP/上电/TUR。

调查版之所以没踩到：`t970_nop::run` 自己做了 `hcWrite(0x60,0)` 停队列、写
`0x50/0x54=dma`、`0x60=1` 起队列这几步，看起来像 SMMU 实验，实际是请求列表接管。

## 失败时屏幕上能看到什么

bring-up 被拒绝时 panic 打印 `CB0` 三元组、两个 stream 值、`gfsr/fsr` 和 DMA 地址。
发布中止时打印：

```
T970 UFS publish: publication stopped
stage=<gRootDiagnostic.stage> phase=<..> window=<..> bytes=<..>
userdata=<first>..<last> image=<..> manifest=<status> magic=<..> <..>
windows=<count> prepared=<..> published=<..> policies=<..> verify=<..>
w0 <name> off=<..> size=<..>
...
```

`stage` 直接来自 owner 校验的步骤名。空策略表下会是 `policy count invalid`，`policies=0`。
`w0..w3` 是 manifest 解析出的窗口名、分区内偏移与字节数，用于和 host 侧签名输入核对。

## 当前限制

策略哈希表仍在核心里：OS 6.08 GB 需要约 46.4 MB、SystemOS 3.30 GB 需要约 25.2 MB，
合计约 71.6 MB，加进内核后 BOOT 镜像会超过 71,303,168 字节的分区上限。空策略表可以启动，
但按设计不会发布任何窗口。因此本版预期的实机结果是发布停在 owner 校验，并把窗口几何打印
出来；这两个数就是后续把策略载体移出内核（userdata 固定区 + 运行时 `vr_open`）的输入。

## 实机结果（BOOT `ca021c28`）

调查版序列跑通，发布停在 owner 策略，屏幕原文：

```
T970 UFS publish: publication stopped
stage=policy count invalid phase=1 window=0 bytes=16a408600
userdata=.. image=22f400000 manifest=0 magic=474e4853 544f4f52
windows=2 prepared=0 published=0 policies=0 verify=ffffffff
w0 OS off=100000 size=16a408600
w1 SystemOS off=16a600000 size=c4e00000
```

`magic=SHNGROOT`、`manifest=0`、`windows=2`、`prepared=0 published=0`：正式读取与窗口计划
都成立，且 fail-closed 生效——一个窗口也没发布。窗口几何与 host 侧从镜像首块解出的 manifest
完全一致：

| 窗口 | 偏移 | 字节数 | 4096 块 | 哈希表 |
| --- | --- | --- | --- | --- |
| OS | `0x100000` | 6,077,580,800 | 1,483,785 | 47,481,120 |
| SystemOS | `0x16a600000` | 3,303,014,400 | 806,400 | 25,804,800 |

合计哈希表 73,285,920 字节，加两份 manifest 约 73.3 MB。这就是**下一步签名与载体的输入**：
manifest 放进 userdata 镜像之后的固定区（镜像止于 LBA 5,260,288），启动时经同一 handoff
通道读入并 RSA 校验，再填 `verified_root_policies`；内核体积不变。
```
## 策略载体（out-of-kernel）

`BOOT` 装不下 73,287,008 字节的块哈希表，因此两份 owner manifest 放在 userdata 里，内核只链
owner 公钥锚：

| 内容 | 分区内 LBA | 块数 | 字节 |
| --- | --- | --- | --- |
| OS 包络 | 5,505,024（21 GiB） | 11,593 | 47,481,664 |
| SystemOS 包络 | 5,516,624 | 6,301 | 25,805,344 |

根镜像止于 LBA 5,260,288，两段包络落在其后的空闲区（止于 5,522,925）。内核里
`kOwnerPolicyLbaOS`／`kOwnerPolicyLbaSystemOS` 是这两个常量。

加载顺序（`installOwnerPolicyCarrier`）：读包络头（`VROOT01`、160/4096、`image_bytes` 必须等于
该窗口容量）→ 按 `544 + 32 × block_count` 读满 → `vr_open` 用链入的 owner 公钥做 RSA 校验 →
两条都通过才写 `verified_root_policies`／`verified_root_policy_count`。任一条失败即 panic，一个
窗口也不发布。

`scripts/build-owner-root-manifests.py` 负责 host 侧：从 sparse 段流式读出两个窗口（不落 9.4 GB
文件）、用 `kits/VerifiedRoot/tools/manifest.py` 签名、再用真实 C（`vr_host_open` + 抽样块
`vr_host_block`）验签。卷 UUID 取自设备/镜像事实：OS `04769D26-2CA0-4825-B443-E2E5F88300F2`
（ADT 根匹配），SystemOS `8846FE78-2910-4297-AF97-D59BB6F8FC16`（挂载 cryptex 得到的卷 UUID，
与内核 `XNU_OWNER_CACHE_VOLUME_UUID` 一致）。
