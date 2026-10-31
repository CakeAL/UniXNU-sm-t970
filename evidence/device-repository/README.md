# Step 3 host verification

All seven local device-repository input requirements are complete for the
CPU0/initrd platform scope. Device source:
`18d3a77cd98f47ee42aa1f95d6584d22c3a13a18`.
Framework: `194aae294c1107e791f4f74b2be371a391ac6bc4`.
Both source trees were committed and clean when these commands ran.

- `result.json`: source revisions, input hashes, exact commands, exit statuses,
  manifest coverage, firmware/packing checks and explicit hardware-test limits.
- `platform.json` / `platform.log`: all reviewed source pins, 61 patches, 8
  archives, CPU0/GIC/timer/ADT, 30 static reservations, 13 dynamic-pool windows,
  45 stock XBL regions and 7 disabled controller resource sets.
- `firmware.log`: the normal `unixnu build firmware` invocation. It produces
  `Build/gts7xlwifiPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd`, exactly 3145728 bytes.
  Its digest is in result.json and boot.json.
- `modules.json`: FV/FFS inspection of the real `FVMAIN.Fv` confirms UniXNU,
  UniXNUDxe, UniXNURamDiskDxe, DarwinBoot, DiskIo, FAT and Unicode collation
  (7 required modules among 91 FV files). The traversal reuses the FV/FFS
  header checks from scripts/collect-boot-firmware.py and compares GUIDs from
  the pinned source INFs.
- `boot.json` / `pack.log`: the normal `unixnu bootimg` command builds and
  unpacks a 3993600-byte Android v2 image with an uncompressed shim/FD and a
  separate firmware DTB. Its ramdisk is empty: it is a firmware check image,
  without an XNU kernel, Apple OS payload or configured XNU boot entry.

The platform window is 0x200000000+0x80000000 (2 GiB), contained in a measured
DRAM bank. The earlier whole-bank candidate intersected the stock camera CMA
allocation window; the expanded check detected this and the window was narrowed.
Static-source non-overlap does not verify a new UEFI runtime allocation map.

The shared packer has 8 passing unittest cases covering legacy/v2 layouts,
compression choices, empty ramdisk, corrupted fields/data, and upstream shim
image-size normalization. The 130-entry manifest was compared against all three
captured source collections with no missing, extra or mismatched digests.

The original firmware DTB, FD, compiled FV and packed image remain in ignored
local storage. The firmware DTB contains /chosen identity/boot inputs and is
not committed. Logs replace absolute workspace roots with ${DEVICE}/${UNIXNU}.
Hashes describe the exact checked inputs, not a promise that every vendor binary
or build timestamp is reproducible on every host.

No new firmware was executed on the tablet; no kernel build, flash, reboot,
partition modification or device-register operation was performed. Actual UEFI
launch, GOP/stride/format, initrd discovery, runtime memory, XNU handoff, SMP and
peripheral functionality are separate future milestones in porting.toml.
