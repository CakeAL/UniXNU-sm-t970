# 首次启动构建（第 7 步）

本页记录 SM-T970 的内核、payload 与启动镜像在主机上的完整构建链，以及设备侧尚未执行的部分。
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
| `payload/payload.img` | 201326592 | `a4a0bac8487b288aba2a2f2e244709c24761d9829bdd30c5ef4beefc3ee5c551` |
| `boot.img` | 205320192 | `28f3bb9f081420d8f6d6d26d91a12315758f0195e114abef598ca12a86a01f9d` |
| `SILICIUM_UEFI.fd` | 3145728 | `4691d86c4c1604ca28f1b97428d930724c270debaa02ed03f3d22f1a68fed7ba` |

顺序：`ipsw fetch` → `build kernel` → `build package` → `build payload` →
`build firmware` → `bootimg`。内核首次构建会先用 bootstrap 通过编译记录，
随后归档、正式链接并预链接。

## 验证

- `boot.json`：header v2、`ramdisk_bytes` 201326592、separate DTB，`dtb_sha256` 等于采集的
  固件 FDT（`86c14aa3…`），`fd_sha256` 等于本次构建的 FD。
- `payload.json`：`kernel_sha256` 等于 `kernel.macho`，包含生成的 ADT 与已接受的
  trust cache（`7416ca4f…`）。
- 镜像内含 BootShim + 3 MiB FD + 192 MiB payload，`kernel_address 0x8000`、
  `tags 0x1e00000`、DTB 独立放置。

## 设备侧

**没有刷写、没有重启**，平板仍运行 Android 12（`SP2A.220305.013`）。
恢复镜像已从设备只读导出到 `out/device-backup/`：`boot.img`（68 MB，Magisk 25.2 补丁版）、
`dtbo.img`（10 MB）、`vbmeta.img`（64 KB），可用 Odin 刷回。

SM-T970 没有 fastboot，测试路径是 Odin 刷 boot（Android v2 格式，与 Magisk 补丁镜像同一种刷法）。
由于没有 UFS 驱动与 Data seed，首次测试预计在内核交接后停在 root mount，不会写存储。

## 下一步

1. 需要机主确认后，用 Odin 单次刷入 `boot.img`，按[启动验证顺序](../evidence/bring-up/README.md)
   记录固件、菜单、加载器和内核观测。
2. 按[存储分析](storage.md)移植 SM8250 UFS 驱动，才能越过 root mount。
