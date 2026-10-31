# Step 7: kernel, payload, boot image and Odin preparation

Device commit `7a71f6f36f90de36dc04679500e2ea94257bfa88`, framework `194aae294c1107e791f4f74b2be371a391ac6bc4`.

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `kernel/kernel.macho` | 51908608 | `b3f9ab34199b726105ea1a3bb7a86af0734d632e55c989b2bdb254bb85f48f0e` |
| `payload/payload.img` | 58720256 | `a87d42da70987f70ed81f8ab25ffd530322e69a0b50df60423c426b2bd0a52e0` |
| `boot.img` | 62713856 | `d61f416aad5e5a029edee52674de909ad32030603cf993695db0c75328651388` |
| `SILICIUM_UEFI.fd` | 3145728 | `4691d86c4c1604ca28f1b97428d930724c270debaa02ed03f3d22f1a68fed7ba` |
| firmware FDT | 837154 | `86c14aa305a6cf5db46665f4095d28aadcb1ea5ce9d213cd711641a07504ed1d` |

`boot.json` reports header v2, `ramdisk_bytes` 58720256, separate
DTB and the hashes above; `payload.json` records the kernel, generated ADT and
the accepted trust-cache bundle (`7416ca4f8377...`).
`kernel.log` is the XNU build log, `firmware.log` the firmware build and
`pack.log` the `bootimg` run.

Inputs: the IPSW stays outside the repository; `kernelcache.decompressed` is
`f18b4df86540...` and matches the OS profile pin. The
trust-cache bundle is the two original Apple modules, rebuilt by
`scripts/prepare-trust-cache.py` from the StaticTrustCache DER payload and
Cryptex1,SystemTrustCache; its SHA-256 is in the profile allow-list. The platform
seed is the local test value `0x534d543937303031`; no Data seed.

Patch set: 60 patches. `zzz-boot-progress.patch` is omitted because it patches
the `XNU_SHENG_PMGR` block that only `sheng-platform-power.patch` provides;
`patches/xnu/os-series` keeps the two required XnuPrelink ABI patches.

## Flash preparation

The measured boot partition is 71303168 bytes (68 MiB),
so `[payload] size_mib` is 56 and the image is 62713856 bytes.
Odin AP tars are generated in ignored storage: `boot-unixnu.tar` (test) and
`boot-stock.tar` (restore to the dumped Magisk boot). Flashing steps and expected
observations are in `docs/bring-up.md`.

No device boot was attempted. The tablet still runs Android 12; the boot, dtbo
and vbmeta dumps used for restore stay in ignored storage.
