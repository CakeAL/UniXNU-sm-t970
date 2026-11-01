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

发布前要求固件留下的状态与调查时逐项一致，任何一项不同即拒绝（`firmware handoff state changed`）：

- `CBAR0=0x100ff`、`CBA2R0=0x1`、`SCTLR0=0xe0`；
- 已有 stream 项：`0x810=0x84020820`、`0xc10=4`、`0x954=0x800000e0`、`0x958=0x800004e0`，
  对应项尾部 `0xd54/0xd58` 为零；
- `GFSR=0`、`CB0 FSR=0`；
- DMA 必须落在 `boot_args` 的 owned window 内。

这组判断和调查版 `healthy()` 用的是同一组寄存器与同一组期望值，不引入新解释。

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
