# Step 7: kernel, payload and boot image

Device commit `0d8fb9d0a14630f878a173241059f7687aa6b134`, framework `194aae294c1107e791f4f74b2be371a391ac6bc4`.

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `kernel/kernel.macho` | 51908608 | `b3f9ab34199b726105ea1a3bb7a86af0734d632e55c989b2bdb254bb85f48f0e` |
| `payload/payload.img` | 201326592 | `a4a0bac8487b288aba2a2f2e244709c24761d9829bdd30c5ef4beefc3ee5c551` |
| `boot.img` | 205320192 | `28f3bb9f081420d8f6d6d26d91a12315758f0195e114abef598ca12a86a01f9d` |
| `SILICIUM_UEFI.fd` | 3145728 | `4691d86c4c1604ca28f1b97428d930724c270debaa02ed03f3d22f1a68fed7ba` |
| firmware FDT | 837154 | `86c14aa305a6cf5db46665f4095d28aadcb1ea5ce9d213cd711641a07504ed1d` |

`boot.json` reports header v2, `ramdisk_bytes` 201326592, separate
DTB and the hashes above; `payload.json` records the kernel, generated ADT and
the accepted trust-cache bundle (`7416ca4f8377...`).
`kernel.log` is the XNU build log, `firmware.log` the normal firmware build and
`pack.log` the `bootimg` run.

Inputs: the IPSW stays outside the repository; `kernelcache.decompressed` is
`f18b4df86540...` and matches the OS profile pin. The
trust-cache bundle is the two original Apple modules, rebuilt by
`scripts/prepare-trust-cache.py` (static module from the DER payload of
StaticTrustCache, system module from Cryptex1,SystemTrustCache) and accepted by
the profile allow-list. The platform seed is the local test value
`0x534d543937303031`; no Data seed is used.

Patch set: 60 patches. The OS profile's `zzz-boot-progress.patch` is omitted
because it patches the `XNU_SHENG_PMGR` block that only
`sheng-platform-power.patch` provides; `patches/xnu/os-series` keeps the two
required XnuPrelink ABI patches instead.

No device boot was attempted. The boot partition, dtbo and vbmeta dumps used for
restore stay in ignored storage; the tablet still runs Android 12.
