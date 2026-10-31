# Step 5: hardware description and firmware inputs

Device commit `7b71e1e9ad1dd16a70e31e2fe536dd09c340200f`, framework `194aae294c1107e791f4f74b2be371a391ac6bc4`.
Both trees were clean when the commands ran.

- `result.json`: the Step 5 checker. Firmware FDT `86c14aa305a6...`
  (837154 bytes, 4533 nodes,
  0 reserved-memory map entries) and the
  board DTS build (`321dbc88450b...`,
  56 nodes, 11240-byte ADT) are
  distinct inputs. It also checks the ADT resources, the DSC/FDF modules and the
  pinned base configuration for DiskIo/FAT/Unicode collation.
- `dtb-info.json`: sanitized capture report. The full FDT stays in ignored
  storage because `/chosen` carries boot arguments, a KASLR seed and initrd
  addresses; two captures were byte-identical.
- `firmware.log`: the normal `unixnu build firmware` run; `platform.log` and
  `check.log` are the platform and Step 5 checkers, both PASS.
- `modules.json`: all eight required modules are in the built FV (92 files):
  UniXNU, UniXNUDxe, RamDiskDxe, DarwinBoot, AdvancedLogDxe, DiskIoDxe, FAT and
  EnglishDxe.
- `boot.json` / `pack.log`: a firmware-only Android v2 image (3993600 bytes,
  separate DTB, empty ramdisk). `fd_sha256` and `dtb_sha256` match the built FD
  and the captured firmware FDT.

`unixnu payload` was probed at this commit: it stops only at
`kernel/kernel.macho` ("run unixnu build kernel"), so the hardware-description
side of the payload is satisfied and the missing XNU build is the next input.

Limits: the ADT uses artificial identity 1; no payload/initrd exists and no
kernel was built. Nothing was written to the tablet or booted. The firmware FD
digest changes between builds (EDK embeds build metadata); the module set and
the packed image's field agreement are what this record checks.

Two firmware inputs, two purposes: `dts/sm-t970.dts` -> `kernel.macho.adt`
(XNU hardware description); the captured firmware FDT -> `bootimg --dtb`
(bootloader handoff). They are not interchangeable.
