# DPU-driven vblank for `NativeLegacyDisplay` — findings and implementation plan

Research only; the only file written is this one. Tagging: **[read]** = opened at the cited
line, **[device]** = a device observation recorded in this repo, **[inferred]** = not provable
from local sources, must be confirmed by read-back before use.

Bases: `A = 0xae01000` is the display driver's MDP map (`drivers/GopFramebuffer/NativeLegacyDisplay.cpp:341`,
`withRange(0xae01000,0x84000)` = MDP `0xae00000` + `qcom,sde-off` 0x1000); `B = 0xae00000` is
the base of the board's read-only DPU probes (`package/BacklightProbe.cpp:428,481`). A register
at `B+X` is driver offset `X-0x1000`.

> **Working-tree state:** `NativeLegacyDisplay.cpp` (uncommitted) already contains a **frame-counter
> polled** hardware vblank — boot arg `t970-hw-vsync`: `hwVsyncProbe()` `:618-650`, `hwVsyncTick()`
> `:653-681`, constants `:296-297`, armed from `startVsync()` `:696`, torn down in `stopVsync()`
> `:702-707`. So answer (c) is **already implemented**; the interrupt path in (a)/(b) is not.
> Line numbers are the working copy as read; the file is under active edit, so re-grep the anchors
> (`kHwIntfFrameCount`, `hwVsyncProbe`, `hwVsyncTick`) before patching.

## (a) Is the GIC exposed to IOKit? No — and a kext cannot reach SPI 83 through IOKit at all

1. **No GIC driver exists in the kernel tree.** `find -iname '*gic*'` over
   `/Users/cakeal/vsc/UniXNU/out/feeds/xnu-b7545ced` returns nothing; grepping `iokit/ osfmk/
   pexpert/` for `gic` finds no interrupt-controller implementation. The only interrupt-controller
   kext in the prelinked kernelcache is Apple's AIC, `com.apple.driver.AppleInterruptController`
   (`IONameMatch = "aic,1"`, `IOProviderClass = AppleARMIODevice`), which cannot drive a
   Qualcomm GICv3. `AppleARMIODevice` exists only as that kext's provider class; nothing in
   Mu-Silicium or in this port publishes such a nub (grep over
   `.cache/uefi-source/Mu-Silicium` for `AppleARMIODevice`/`mdss`/`Mdp` finds none, and the
   board's display DXE is a prebuilt binary, `Platforms/Samsung/gts7xlwifiPkg/Drivers/DisplayDxe/DisplayDxe.efi`).
2. **The only registered IOKit controllers are CPU-scoped.** `IOCPUInterruptController`
   registers itself as `IOPlatformInterruptController` (`iokit/Kernel/IOCPU.cpp:591-598`) and
   stamps that name only onto **CPU** nubs (`:604-630`); `PassthruInterruptController` is the same
   name (`iokit/Kernel/PassthruInterruptController.cpp:44-51`). Neither serves device SPIs.
3. **DT nubs get no interrupt resources.** `IODTPlatformExpert::createNub` builds a plain
   `IOPlatformDevice` and `getNubResources` resolves only `reg` → device memory
   (`iokit/Kernel/IOPlatformExpert.cpp:1740-1749`). `IOService::resolveInterrupt` needs
   `IOInterruptControllers` + `IOInterruptSpecifiers` on the nub
   (`iokit/Kernel/IOService.cpp:8519-8585`); without them `registerInterrupt` returns
   `kIOReturnNoInterrupt` (`:8625-8638`). If a mapping *were* attempted, `lookUpInterruptController`
   **sleeps** until a controller of that name registers (`IOPlatformExpert.cpp:446-465`) — a boot hang.
4. **ArmCpu owns the vector.** It installs its handler with `ml_install_interrupt_handler`
   (`drivers/ArmCpu/ArmCpu.cpp:584`), reads `ICC_IAR1_EL1` itself (`:610-618`), dispatches timer 27,
   SGI 0, the IPI SPIs, then its own SPI table by architectural INTID (`:653-666`), then
   `ICC_EOIR1_EL1`. A GIC `IOInterruptController` added later would never receive the hardware IRQ;
   it could only forward into `ArmCpu` — i.e. it would be a pass-through, not a controller.
5. **One more DT-side blocker** (matters for any ADT-based design): the phandle lookup uses
   `AAPL,phandle` (`iokit/Kernel/IODeviceTreeSupport.cpp:169`, `AddPHandle` `:507-517`,
   `IOInterruptController%08X` at `:583-601`), but the built ADT carries only `phandle`
   (`/arm-io/intc` properties in the built `kernel.macho.adt`), because the generator emits only
   whitelisted keys (`/Users/cakeal/vsc/UniXNU/scripts/unixnu/devicetree.py:205-255`). The MDSS
   node exists only in the Linux firmware FDT (`/tmp/fw.dts:21884-21921`, decompiled from the captured
   `out/firmware-inputs/firmware.dtb`), which XNU never parses
   (`docs/firmware.md`, "两个设备树输入"). `scripts/check-platform.py:220` also requires `/arm-io/intc`
   to be the only exported node today.

**The mechanism that does exist (already used on this board):**

```c
IOReturn armcpu_spi_attach(uint32_t intid, bool edge, void (*handler)(void *),
                           void *context, uint32_t *readback, uint64_t *router);
```
`drivers/ArmCpu/ArmCpu.cpp:886-917`: sets IGROUPR group 1, priority 0xa0, level/edge, IROUTER to
boot affinity, ISENABLER; the handler runs **in primary context, before EOI**, and must clear the
level source (`:202-204`). Unhandled SPIs are counted and ICENABLERed (`:662-666`). No mask API in
this copy (the shared `UniXNU/drivers/ArmCpu/ArmCpu.cpp:1087,1112` has `armcpu_spi_share`/`_mask`;
the board copy is what the build links —
`out/sm-t970/.../gts7xlwifi/tree/drivers/ArmCpu -> ../../../UniXNU-sm-t970/drivers/ArmCpu`), so
masking must use `GICD_ICENABLER` `0x17a00188` bit 19.

**Source numbering: INTID = SPI + 32.** Precedent `kIrq = 133 + 32`
(`drivers/QcomDwc3/QcomDwc3Sm8250.cpp:49,311`). MDP is **SPI 83** (`/tmp/fw.dts:21893`,
`interrupts = <0 0x53 4>`), so the call is `armcpu_spi_attach(115, false, ...)`.

## (b) Smallest honest path

| # | Option | Verdict |
|---|---|---|
| iii | Call `armcpu_spi_attach(115,…)` from the display driver and defer to the work loop | **Recommended.** Exactly what `QcomDwc3Nub` does: it overrides the IOService interrupt verbs and forwards to `armcpu_spi_attach` (`drivers/QcomDwc3/QcomDwc3Sm8250.cpp:284-336`) |
| iii-b | Same but with a real `IOFilterInterruptEventSource`: the *provider nub* answers `getInterruptType`/`registerInterrupt`/`enable`/`disable`/`unregister` (GICD mask/unmask), so the action runs on the work loop (`iokit/Kernel/IOInterruptEventSource.cpp:80-160,252-262`). The nub is already board-owned (`package/LegacyDisplayProbe.cpp:1135-1147`) | Good second step, no XNU patch |
| i | Port `iokit/Examples/drvGenericInterruptController/GenericInterruptController.cpp:103` as a board GIC controller + ADT publish | **Insufficient alone** — ArmCpu still acks the IRQ, so it must forward into `armcpu_spi_attach` anyway (= iii-b with more code) |
| ii | XNU patch to `createNub`/`IODTPlatformExpert` to build the two properties from ADT `interrupts` | Insufficient alone (no controller to register) *and* blocked by the missing `AAPL,phandle` (§a.5) |

Firmware/ADT change is **not** required for iii/iii-b: the display provider is a locally built
`IOPlatformDevice` with memory only (`package/LegacyDisplayProbe.cpp:1135-1147`), independent of
`dts/sm-t970.dts`.

### SDE registers for an interrupt vblank (all relative to `A` unless noted)

| Register | `A`-offset | Absolute | Confidence |
|---|---|---|---|
| CTL0 base; `CTL_FLUSH` = +0x18, already driven by this driver | 0x1000 / 0x1018 | 0xae02000 / 0xae02018 | **[read]** `NativeLegacyDisplay.cpp:364,404,545`; flush bits self-clearing on device |
| `INTF_TIMING_ENGINE_EN` (+0x000), engine-enabled test bit 31 | 0x6a000+ | 0xae6b000 | **[read]** `NativeLegacyDisplay.cpp:296-297,630-635` (scan picks the INTF whose word has bit 31) |
| `INTF_FRAME_LINE_COUNT_EN` (+0x0A8), this driver writes 0x3 | 0x6a800+0xa8 | 0xae6b8a8 | **[read]** `:297,639`; matches `INTF_FRAME_COUNT`/`LINE_COUNT` pair semantics **[inferred]** |
| `INTF_FRAME_COUNT` (+0x0AC) | 0x6a800+0xac | 0xae6b8ac | **[device]** `package/BacklightProbe.cpp:414-419,474,495-510` (polled at 250 µs, moves at 30.1 Hz); also `NativeLegacyDisplay.cpp:657` |
| `INTF_LINE_COUNT` (+0x0B0) | 0x6a800+0xb0 | 0xae6b8b0 | **[read]** `:297,649`; **[device]** `BacklightProbe.cpp:414-419` |
| `INTF_STATUS` (+0x26C), `INTF_TEAR_*` 0x280-0x2B8 (`AUTOREFRESH_CONFIG` 0x2B4, `INT_COUNT_VAL` 0x298 = frame<<16\|line, `RD_PTR_IRQ` 0x2A4) | 0x6a800+ | 0xae6ba6c… | **[device]** `BacklightProbe.cpp:414-419,456-473` |
| INTF interrupt group, candidate 1: `+0x10/0x14/0x18` (EN/STATUS/CLEAR) | 0x6a810/14/18 | 0xae6b810/14/18 | **[inferred]** Linux DPU `MDP_INTR_*` convention |
| INTF interrupt group, candidate 2: `+0x1C0/0x1C4/0x1C8/0x1CC` (EN/STATUS/CLEAR/SET) | 0x6a9c0/c4/c8/cc | 0xae6b9c0… | **[inferred]** `sde_hw_intf.h INTF_INTR_*` |
| Bit meanings (`FRAME_DONE` BIT(0), `VSYNC` BIT(1)) | — | — | **[inferred]** — do not trust before read-back |

SPI 83 is **level-high**: an asserted line whose handler never clears the source re-enters
`ArmCpu::interrupt` (`:620-680`) until the 1 000 000-entry panic (only with
`armcpu-diagnostics=1`, `:631`), otherwise forever. Never set an enable bit before the matching
STATUS/CLEAR pair is proven on hardware.

### Steps (interrupt path, after (c) which is already in the tree)

1. **Read-only probe, one device run.** Keep the existing `hwVsyncProbe()` map (`:624-628`); add a
   read of `0x010/0x014/0x018` and `0x6a810/14/18` and `0x6a9c0/c4/c8` into spare observation
   words (`native_legacy_direct[]` `:62`, `native_t970_cadence[]` `:68`), plus one boot-log row
   with `armcpu_spi_unhandled`/`armcpu_spi_unhandled_id` (`ArmCpu.cpp:211-212`, currently unreferenced
   in `package/BootLog.c`). Write nothing. Answers: which INTF group is live, whether a status bit
   toggles at the panel rate with enables untouched, and whether SPI 115 is already pending
   (`unhandled_id == 0x73` ⇒ the bootloader left an MDP interrupt enabled and ArmCpu masked it).
2. **Enable exactly one bit.** Set it in the chosen EN register, clear it in the matching CLEAR
   register, then `armcpu_spi_attach(115,false,handler,this,&readback,&router)`. The handler must
   only: read STATUS, write CLEAR, bump a counter, store `mach_absolute_time()`. Liveness evidence:
   the `gSpi[].count` increment (`ArmCpu.cpp:660`, readable through `armcpu_spi_count` `:918`) and the
   readback word. Any anomaly → `GICD_ICENABLER`
   (`0x17a00188`, bit 19) and stay on the polled path.
3. **Do not notify from the handler** (primary context). Defer with
   `IOTimerEventSource::wakeAtTime` on the existing `hwVsyncTimer`, which is interrupt-safe
   (`iokit/Kernel/IOTimerEventSource.cpp:546-585` → `thread_call_enter_delayed`,
   `osfmk/kern/thread_call.c:1230`), or add the five nub verbs and use
   `IOFilterInterruptEventSource`. `native_legacy_vsync_notify` must keep running on the work loop
   (`:610`, `:668-673`).
4. **Retire the poll** only when the interrupt count equals frame count over minutes
   (`hwFrames`/`hwNotify`, `:674-679`), with no gap > 1.5× the frame period and
   `armcpu_spi_unhandled` not moving.

## (c) Polled fallback — already implemented, and it is the honest baseline

`hwVsyncProbe()`/`hwVsyncTick()` (`NativeLegacyDisplay.cpp:618-681`) read `INTF+0x0AC` every
`t970-hw-vsync-poll` µs (default 500), and every change is one panel frame; the interval is
smoothed and handed to `native_legacy_vsync_notify`. Recognition of a *real* boundary is the
window `2 ms < Δ < 50 ms` (`:661-666`) plus an 8-sample mean (`:662`); add "two consecutive Δ
within ±20 %" if false edges are seen. Boot args: `vsync=<Hz>` is still required to install the
timers (`:120-121,685-686`); `t970-hw-vsync=0` is the control run.

Hardware grounding: v93 measured `INTF1` at **30.1 Hz** with every ping-pong register 0, and v94
read `INTF_TEAR_AUTOREFRESH_CONFIG = 0x80000002` = autorefresh on, one update per second TE pulse,
panel TE 60 Hz (`BacklightProbe.cpp:456-473`). Writing `0x80000001` (already done by
`t970_dpu_set_refresh`, `:474-485`) makes the interface update on every TE, i.e. a 60 Hz boundary;
that is the single change that would double the notify rate without any interrupt.

## Blockers and risks

- **Level-line storm / boot hang** if an enable is set without a proven clear (`ArmCpu.cpp:620-680`);
  mitigated by step 1 being read-only and by the GICD mask.
- **Unknown INTF interrupt layout and bit numbers** (two candidate groups above): only step 1
  resolves them. Everything else in this document is read from the repo or device-measured.
- **Panel is command mode** (`dsi_cmd_mode`, TE pin, TE check enabled: `/tmp/fw.dts:25512-25516`),
  so the boundary is the TE/autorefresh event that `INTF_FRAME_COUNT` counts — there is no
  video-mode timing generator to take a vsync from.
- **No sharing**: a second consumer of SPI 83 gets `kIOReturnExclusiveAccess` (`ArmCpu.cpp:894`).
