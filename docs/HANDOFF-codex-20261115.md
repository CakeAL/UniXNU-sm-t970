# Handoff — SM-T970 iPadOS 17.7.11 port, wholesale adoption of the gts7xlwifi board package

Date: 2026-11-15
Device repo: `/Users/cakeal/vsc/UniXNU-sm-t970`
UniXNU framework checkout: `/Users/cakeal/vsc/UniXNU`
Reference port (same tablet model, upstream): `/Users/cakeal/vsc/gts7xlwifi-upstream` (plain directory, **not** a git repo)
Target OS profile: `ipados-17.7.11-21H461`
Hardware: Samsung Galaxy Tab S7+ Wi-Fi, SM-T970 / gts7xlwifi, SM8250, Adreno 650 (a650), UFS, WCN6855-class Wi-Fi/BT, STM FTS touch.

## 1. Goal

Replicate the reference port's feature set on this tablet, keeping the **existing dual-system partition layout**:

- Android `BOOT`, F2FS `userdata`, iPadOS `RECOVERY`, dedicated `unixnu` partition.
- Only `RECOVERY` may ever be written on this tablet. Never `BOOT`, never `userdata`, never GPT.

Acceptance list (from the maintainer, in order of value):

1. 8 cores with 4+3+1 cluster scheduling and load-based DVFS
2. ~6.7 GB usable RAM
3. Native UFS storage with persistent `Data`
4. GPU compositing (Adreno 650) with automatic recovery after GPU errors
5. Touch and hardware keys
6. Brightness, speaker + microphone, haptics
7. Power-off, charging
8. Wi-Fi with signal bars, Safari + Apple News, saved passwords
9. Bluetooth usable
10. S Pen as Apple Pencil (correct orientation, pressure)
11. USB: Mac Finder sees the tablet as an iPad
12. SLPI sensor coprocessor started (auto-rotate and camera are follow-ups)

## 2. Current state — read this first

### Device

- The tablet currently runs `out/dual-system/port-all-v3-20261114/recovery-port-all-v3.img`
  (sha256 `19466bb4cb9531455f91ced8f5b9833deab85c204f1af6172998e13b366b98fe`).
  It boots to the iPadOS home screen. **Touch does not work.** No GPU acceleration.
- It is not bricked and it is not in download mode. Nothing risky is pending on it.
- Flashing tool: `.cache/heimdall/build/bin/heimdall flash --RECOVERY <img> --no-reboot`.
  An Odin session ends after a PIT read; a physical re-plug is required before the next flash.
  A successful upload prints `RECOVERY upload successful`; Heimdall then often reports a
  session-end error, which is expected on this device.

### Repository

- Branch under work: **`gts7xlwifi-wholesale`** (build to be continued here).
- `main` is unchanged and remains the fallback: commit `18f6bd6`.
- Commits on the branch (oldest first):
  - `e257999` adopt the reference 288-line `board.toml` (archives, patch series, components, payload, firmware, ADT), changing only `name`/`kit`/DTS path to `sm-t970`
  - `d4683c3` sync all 103 reference build scripts and their data
  - `a083252` use reference `build-platform-power.py`, `build-storage-bindings.py`, `build-boot-progress.py`; replace the owner-signed root policy archive with `build-verified-root-empty.py`
  - `4b5ff77` add `kits/sm-t970/{LinkStubs.c,BootProgressStubs.c}`
  - `77fc82f` also provide `kits/gts7xlwifi/` because `scripts/build-link-stubs.py` hardcodes that name
  - `f62d4fd` point `build-link-stubs.py` at the `sm-t970` kit
  - `33ee983` temporarily comment out `build-adreno650.py` in `board.toml` (no `a650_zap` firmware on this host)
  - `d1144ab` let `scripts/build-qcom-usb-debug.py` take `T970_DEVICE_DIR`

### What is already proven by host builds

- `python3.14 ./unixnu defconfig sm-t970_defconfig -D ../UniXNU-sm-t970` → OK
- `python3.14 ./unixnu status --json -D ../UniXNU-sm-t970` → OK, all four profiles resolve
  (arch `arm64`, soc `UniXNU-sm8250-common-a7c5a8ff`, os `ipados-17.7.11-21H461`, device repo)
- `python3.14 ./unixnu build package -D ../UniXNU-sm-t970` → OK
- `python3.14 ./unixnu build kernel …` → archives through
  `corecrypto`, `native-namespace`, `ArmDTPlatform`, `ArmCpu`, `SoftwareAES`, `ShengUfs`,
  `AppleKeyStoreState` (arm64 object audit passed), `GopFramebuffer` display pack,
  `QcomXnuUsbDebug`, Bluetooth (`QcaBluetooth` engine), and stops in the Wi-Fi archive (see §5).

## 3. Environment requirements (non-obvious, all learned the hard way)

1. **The `./unixnu` shebang is `#!/usr/bin/env python3` and macOS `python3` is 3.9**, which has no
   `tomllib`. Always invoke `python3.14 ./unixnu …`.
2. The framework spawns helper scripts as bare `python3`. Create a shim and prepend it:
   ```sh
   mkdir -p /tmp/py314 && ln -sf "$(command -v python3.14)" /tmp/py314/python3
   ```
   Use a PATH without spaces (the JetBrains toolbox entry contains a space and breaks `env PATH=…`):
   ```sh
   PATH=/tmp/py314:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
   ```
3. Required environment variables for the current build:
   ```sh
   export PATH=/tmp/py314:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
   export UNIXNU_UEFI=/Users/cakeal/vsc/UniXNU-sm-t970/.cache/uefi-source/Mu-Silicium   # has .../SiliciumPkg/Library/FrameBufferSerialPortLib/Font.h
   export T970_DEVICE_DIR=/Users/cakeal/vsc/UniXNU-sm-t970/kits                            # note: the *kits* dir, the scripts take .parent
   export T970_QCA_BLUETOOTH_DIR=/Users/cakeal/vsc/UniXNU/drivers/QcaBluetooth             # cloned from github.com/UniXNU/QcaBluetooth
   export T970_ATH12K_WIFI_DIR=/Users/cakeal/vsc/UniXNU/drivers/Ath12kWifi                 # cloned from github.com/UniXNU/Ath12kWifi
   ```
4. Build command:
   ```sh
   cd /Users/cakeal/vsc/UniXNU
   python3.14 ./unixnu build kernel -D ../UniXNU-sm-t970
   ```
   The build tree lives at `out/sm-t970/ipados-17.7.11-21H461/sm-t970/tree`; logs at
   `out/sm-t970/ipados-17.7.11-21H461/sm-t970/logs/`.

## 4. What was done to reach this state (and why it matters)

The earlier approach on `main` was piecemeal: copy a driver, hand-link it with a private
`relink.py`, prelink, pack, flash. Every step was verified on the host and every attempt failed on
the device (green bar hang, Apple logo reboot, no touch). The maintainer explicitly rejected this
and asked for a **wholesale replication of the reference project**.

So the current branch replaces the board layer with the reference's own:

- `package/` now holds all 66 reference sources (`BootProgress.c`, `BootLog.c`,
  `LegacyDisplayProbe.cpp`, `HidInputProbe.cpp`, `Qcom*` bus drivers, `CpuFreqProbe`,
  `BacklightProbe`, `ButtonProbe`, Wi-Fi/Bluetooth/audio, `KeyStoreProbe`, etc.) in addition to
  this repo's directory-style implementations (`package/T970Board`, `package/T970Touch`, …).
- `drivers/` gained `Adreno650`, `ShengHidInput`, `QcomDwc3`, `QcomXnuUsbDebug`, `ShengUfs`,
  plus `hal/` and `tools/`.
- `patches/` was overlaid with the reference series.
- `board.toml` is the reference file, so `archives`, `patch_series`, `components`, `payload`,
  `firmware`, `adt` are all theirs. Only identity differs.

**Do not** go back to hand-linking objects into `libNativeLegacyDisplay.late.a`. That path is what
produced the reboot loop.

Recorded dead ends (do not repeat):

- Linking `BootProgress.o`/`BootLog.o`/`BootDiagExport.o` into the old kernel with weak stubs →
  green bar then immediate reboot, twice.
- Linking the fault/reset/watchdog probes (`BootFaultProbe.o`, `BootReset.o`,
  `BootWatchdogPolicy.o`) → same reboot.
- Starting the touch bridge at the top of the display late probe → hang at the Apple logo
  (RPMh windows + `OSKextLoadKextWithIdentifier` before IOKit/PMGR are ready).
- Deleting `.cache/xnu-work` in the old tree → forced a full kernel rebuild that surfaced unrelated
  SDK/config drift. Never delete it.

## 5. Current blocker and suggested fix

### Blocker A — WiFi module source fetch (build stops here)

`archive-22-build-t970-wifi` runs `drivers/Ath12kWifi/tools/fetch-sources.sh`, which runs
`tools/fetch-sources.py` and then:

```
git -C …/drivers/Ath12kWifi/deps/linux sparse-checkout add /drivers/net/wireless/ath/ … 
called process returned with exit status 128
```

Manual workaround that did populate the sources:

```sh
cd /Users/cakeal/vsc/UniXNU/drivers/Ath12kWifi/deps/linux
git sparse-checkout set --no-cone \
  /drivers/net/wireless/ath/ /drivers/bus/mhi/ /include/ /net/qrtr/ /net/mac80211/ \
  /net/wireless/ /net/core/skbuff.c /drivers/soc/qcom/qmi_interface.c \
  /drivers/soc/qcom/qmi_encdec.c /lib/rbtree.c /lib/crypto/arc4.c
```

`drivers/net/wireless/ath/ath11k/pci.c` then exists. But `build-t970-wifi.py` re-invokes
`fetch-sources.sh` on every build and that call still fails. Suggested fixes, in order of preference:

1. Patch `scripts/build-t970-wifi.py` (repo copy, sync it back to the device repo) to skip
   `fetch-sources.sh` when `deps/linux/drivers/net/wireless/ath/ath11k/pci.c` and the other
   sparse-checkout paths already exist.
2. Or patch `tools/fetch-sources.py` to use `git sparse-checkout set --no-cone …` instead of
   repeated `add`, which is what fails on this host's git.
3. Do not vendor the Linux tree into this repository.

### Blocker B — GPU firmware (archive disabled on purpose)

`scripts/build-adreno650.py` requires `a650_gmu.bin`, `a650_sqe.fw` and `a650_zap.mdt/.b0N` under
`.cache/firmware/gpu`, then generates `kits/package/GpuFirmwareA650.c`.
`out/dual-system/firmware-inputs-20261114/vendor.img` (951,066,624 B) contains only
`a650_gmu.bin` and `a650_sqe.fw` — **there is no ZAP blob anywhere on this host**.

- The archive is commented out in `board.toml` (commit `33ee983`). Restore it after the ZAP is
  extracted from the physical tablet (the owner must supply it; the repo must never contain vendor
  binaries).
- GPU is milestone M5; do not block the rest of the port on it.

### Blocker C — owner-signed root policies

The reference `board.toml` lists
`build-root-policy-archive.py --tree . --policies .cache/firmware/root-policies --output …
build/verified-root-os-xnu-bundle`, which needs `.cache/firmware/root-policies/{os,systemos}/`
(`trusted-key.bin` 395 bytes and `manifest.bin`). These signed artifacts are not on this host.
Substituted with `build-verified-root-empty.py --tree . --output build/verified-root-os-xnu-bundle`
(commit `a083252`). Keep the archive name so the link order is unchanged.

## 6. Remaining work, in order

1. Fix Blocker A, then finish `unixnu build kernel` (expect a full XNU link over the reference
   patch series; a fresh tree has never linked here before, so budget an hour and expect
   configuration drift in `osfmk/conf`, `EXPORT_HDRS`, or the SDK include paths — those are
   fixable, see `docs/board-package-migration.md`).
2. `python3.14 ./unixnu build firmware --uefi ../uefi-sm-t970` — Mu-Silicium checkout is already at
   `.cache/uefi-source/Mu-Silicium`; keep the `GopFramebuffer` + `DarwinBoot` pair consistent with
   the reference (its boot args assume `gpu-addon`, `fb-gpu`, `boot-progress`, `pmgr=2`).
3. `python3.14 ./unixnu build payload --unique-chip-id <hex> --trust-cache <bundle> --data-ramdisk <seed>`
   — the persistent `Data` seed stays the existing 512 MiB `DBRDISK1` image; do not recreate it.
4. `python3.14 ./unixnu bootimg --uefi ../uefi-sm-t970 --dtb <firmware.dtb>` or the existing
   `scripts/pack-dual-data-recovery.py` flow, whichever the new payload format requires.
   Note: the current packer pins base sha `5c9355fa…`, boot layout `(0,4096,2)` and the FAT seed;
   the reference payload may need a different packer invocation.
5. Flash **only** `RECOVERY` after the image hash is recorded in `evidence/input/<dir>/flash.json`.
6. Verify on device in this order: home screen → boot report lines → touch → keys/brightness →
   audio/haptics → Wi-Fi/BT → USB/Finder → S Pen → GPU. A GPU failure is not a regression.
7. Record each result in `docs/` and `porting.toml` with the image hash; host builds are never
   "device verified".

## 7. Reference material

- Porting record: `docs/gts7xlwifi-import.md`
- Migration plan and milestone definitions: `docs/board-package-migration.md`
- Boot arguments and green-bar diagnosis: `docs/bring-up.md`
- Firmware overlay: `docs/firmware.md`
- Evidence of flashes so far: `evidence/input/{touch-core-20261114, gpu-addon-20261114,
  boot-report-20261114, boot-report-v2-20261114, restore-port-all-v3-20261115}/`
- Rollback images that are known to boot: `out/dual-system/port-all-v3-20261114/recovery-port-all-v3.img`
  (`19466bb4…`), `out/dual-system/pen-20261114/recovery-pen.img`

## 8. Hard rules

- Never write any partition other than `RECOVERY`.
- Never commit vendor binaries, extracted firmware, trust caches, or identity seeds.
- Never delete `.cache` trees or build outputs that took hours to produce (the XNU work tree in
  particular).
- Do not claim a feature works from a host build; only from a device observation with the image
  hash attached.
- Keep `main` bootable; do the wholesale work on `gts7xlwifi-wholesale`.

## 9. Whole-board follow-up

The reference's tested system is its `main7` configuration, with the separate
host patch set and firmware inputs. The published board defaults alone do not
enable everything listed in its README. The previous flashed Recovery predates
this whole-board build.

Use `gts7xlwifi_defconfig` for the wholesale branch. It selects the reference
display and late touch path and the reference DTS with eight CPUs. The host
DT-to-ADT cluster-ID change comes from the reference's UniXNU patch 0002. The
profile uses the existing 512 MiB packed Data seed and exact `unixnu` GPT range.
The board package reads the two already provisioned owner policies from the
existing carrier; it does not use the upstream Windows partitions or their log
region. Apple sources missing from a freshly cloned work tree were restored
from the local pinned source cache and checked against Git blob IDs.

Build checkpoint: standard `unixnu build kernel` now passes the initial
compilation stage and enters the archive build. A successful bootstrap stops
at the expected unresolved archive symbols. GPU remains gated on the device's
signed `a650_zap` input. The wholesale change has no device observation yet.

The whole-board kernel linked and prelinked at SHA-256 `246bc7f4…`. The
72 MiB payload was rebuilt with a dedicated local build config to exclude old
single-core and verbose arguments. The final image is `recovery-wholesale.img`
(SHA-256 `cbbf85d79a71670b0058f47839c48c2fc493428a1fae14bdd45b2056624be4f4`).
The original Recovery firmware, DTBO, DTB, Data seed and trust cache match on
readback. Heimdall uploaded only RECOVERY, exit 0. This first image uses the
existing 3840 MiB firmware allocation and CPU display. The matching GPU
firmware and the reference UEFI memory-map handoff are still required for the
GPU and 6.7 GiB configuration. See the upload receipt in
`evidence/input/wholesale-recovery-20261115/flash.json`.
