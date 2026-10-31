# Device agent guide

This repository owns the board DTS, peripheral wiring, component selections,
firmware inputs, partition layout, and packaging.

## Read first

Read this README and the following UniXNU documentation before changing the port:

| Task | Required reading |
| --- | --- |
| Every port | [Porting](https://unixnu.com/porting/), [device repository](https://unixnu.com/porting/device-repository), [component catalog](https://unixnu.com/reference/components), UniXNU `components.toml` |
| Hardware | [Device tree](https://unixnu.com/porting/device-tree), [matching](https://unixnu.com/drivers/device-tree-matching), selected SoC README, AGENTS, soc.toml and DTSI |
| Component | Its site page, README, catalog build command, dependencies and source |
| Kernel | [Source and patches](https://unixnu.com/xnu/source-and-patches), [patch reference](https://unixnu.com/xnu/patch-reference), selected OS profile |
| Images | [Prelink](https://unixnu.com/concepts/prelink), [payload](https://unixnu.com/concepts/payload), [UEFI](https://unixnu.com/porting/uefi-firmware) |
| Verification | [Building](https://unixnu.com/building), [bring-up](https://unixnu.com/porting/bring-up) |
| Migration | [Migration](https://unixnu.com/porting/migration) |

## Work

Search the catalog and inspect existing component interfaces before adding code.
Match hardware scope, OS ABI, and board dependencies. Shared SoC resources and
operations belong in the selected SoC repository. Reusable drivers and libraries
belong in their component repositories. Use canonical component IDs and preserve
runtime identifiers recorded in the catalog.

Replace every `REQUIRED_` value, set the board name and firmware paths, and select
the complete dependency set. Verify memory ranges, CPU affinities, interrupts,
firmware hashes, and partition geometry from board evidence. Set `example = false`
after completing the inputs. Pin the SoC commit and inspect resolved profiles.

Run from UniXNU, replacing the device path and defconfig:

```sh
./unixnu defconfig sm-t970_defconfig -D ../UniXNU-sm-t970
./unixnu fetch
./unixnu status --json
./unixnu tree
./unixnu build kernel
./unixnu build package
./unixnu build firmware --uefi ../uefi-sm-t970
./unixnu build payload --unique-chip-id <hex> --trust-cache <bundle> --data-ramdisk <seed>
./unixnu bootimg --uefi ../uefi-sm-t970 --dtb <firmware.dtb>
```

For a Mu-Silicium initrd payload, include `UniXNURamDiskDxe`, DiskIoDxe and
FAT support in the firmware DSC and FDF. Follow
[required firmware integration](https://unixnu.com/porting/uefi-firmware#required-integration)
before building the firmware and boot image.

Record commands, revisions, output paths, results, and unresolved inputs.
Report hardware boot, storage, display, input, and GPU results separately.
Finish both new ports and migrations with the same
[repository checklist](https://unixnu.com/porting/device-repository#completion).
Follow [publication](https://unixnu.com/porting/device-repository#publish), add
the `unixnu` GitHub topic, and update the device revision in UniXNU's
`devices.toml`. Keep this README concise.

## Porting record

Read the device's `porting.toml` and the
[record guide](https://unixnu.com/porting/records) before implementation.
For storage, also read the [UFS guide](https://unixnu.com/porting/ufs).
Update each affected area's findings or evidence with its code change.
The documentation site renders this same record. Follow its schema and
completion levels for both maintainer and agent work.

## Local builds and boot diagnosis

Copy `unixnu.example.toml` to `unixnu.local.toml` in the main checkout and fill
in device inputs using the [configuration reference](https://unixnu.com/reference/configuration#local-build-inputs).
Read [boot arguments](https://unixnu.com/xnu/boot-arguments#apply-arguments)
before changing the command line. Rebuild the payload and boot image after
argument changes. Use the [green-bar diagnosis](https://unixnu.com/guide/debugging#green-bar)
for stalls at loader handoff. Record the last confirmed stage and relevant logs.

## Hardware adaptation

Follow [Port a device](https://unixnu.com/porting/) in order. Read the
[driver adaptation checklist](https://unixnu.com/porting/drivers) before selecting
components. Follow each subsystem guide for board inputs, implementation paths,
archive integration and expected results. Include board-package services such as
brightness, buttons, Wi-Fi, DSP, battery and CPU frequency in the porting record.

## SM-T970 current scope

Use Python 3.11+ (python3.14 on this host). Preserve the existing evidence and
its revisions. The current DTS enables CPU0 only and uses the handed-off low
DRAM envelope for diagnosis. Its reserved holes are not free RAM; DarwinBoot
allocates the separate 256 MiB owned window from EFI conventional memory.
The completed repository inputs no longer
carry board.example: this permits host builds and does not certify boot readiness.
Track runtime UEFI allocation, GOP and actual launch results separately in the
record; do not mark them device-verified from a host build. Do not enable UFS,
GPU, touch or audio from a template: their board interfaces remain unimplemented.
Run scripts/check-platform.py with the sibling UniXNU checkout for DT/ADT checks.
Firmware overlay and exact binary hashes live in package/firmware; read
docs/firmware.md before preparing a dedicated pinned Mu-Silicium checkout.
Use its Mu_Basecore and the exact nested submodules in inputs.json. Target boot
packing uses header v2, an uncompressed shim/FD and a separate firmware DTB.
Hardware DTB/host-check ADT are not the stock firmware DTB. Keep private firmware
DTBs, extracted binaries, identity seeds and generated images in ignored storage.
The staged vendor UFS/USB DMA dispatch remains absent from the CPU0 initrd image.
Build/pack checks do not authorize overwriting a tablet partition.
Do not leave a reset probe in board.toml. Use scripts/build-entry-probe.py for
one checkpoint per ignored output directory; reset-before is immediate, while
an after-return probe waits its configured delay. Preserve source kernel and
prior images, and bind every device observation to its image hash.
Commit coherent groups of completed diagnostic work, as requested by the
maintainer. Keep image preparation, upload receipts and their observations
together; do not create a separate commit for every small probe action.
