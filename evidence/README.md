# SM-T970 input inventory

`adb-2026-11-01/` contains a read-only capture from the connected SM-T970,
gts7xlwifi, SM8250, on 2026-11-01 (Asia/Shanghai). Android reports build
T970ZCU2CVK1 and runs with existing Magisk root. The boot image is not assumed
to be pristine factory firmware. This inventory does not verify UniXNU support.

Reproduce into a new directory with Python 3.9+ and `adb`/`dtc` on PATH:

```sh
python3 scripts/collect-adb-inventory.py --root --output evidence/<new-capture>
```

- `capture.json`: commands, timestamps, exit codes, evidence SHA256 values and
  parsed Android boot/recovery header fields. No complete boot images were read.
- `live-device-tree.dts`: live Android FDT decoded by dtc. `/chosen` and
  identifying properties are omitted. The original FDT is not saved; its hash
  is recorded. This DTS is not a flashable UEFI or XNU hardware description.
- `display_boot.txt`: only display-selection tokens from the Android command
  line, used to distinguish the active panel from other DT candidates.
- `gpt.json`: primary GPT partition names and byte ranges for LUNs 0-3, with
  validated header/entry-array CRC32. Disk and partition GUIDs are omitted.
  GPT LBAs use 4096-byte blocks here; Linux block sysfs start/size uses 512-byte
  units. No partition contents or backup GPT copies were inspected.
- Other `.txt` files: bounded hardware queries, with the original command,
  output, stderr and final exit code. Review stderr even when the final command
  returns zero. In particular, `network.txt` exits 1 for missing optional
  firmware paths while retaining the successful PCI and firmware-directory data.
- `../log.txt`: the user's earlier Android identity and meminfo transcript.
- `ipsw-21H461-manifest.json`: selected fields from the local IPSW's
  BuildManifest.plist, its SHA256 and archive size. This is manifest inspection,
  not verification of the complete archive or device compatibility.

No device-node writes, firmware loading, input injection, network tests,
repartitioning, flashing or reboots were performed. Serial numbers, network
addresses, full command lines and user logs are not collected. Input unique
IDs are omitted. No raw proprietary firmware is copied into this directory.

The record cites the ADB observations as `device` evidence. Their collection
script and input snapshots are archived at device commit
`54fafba28ae100130a1d21bf0936983ab632c782`. This identifies the collection
source, not a booted XNU kernel. The script and IPSW excerpt also provide
source references. These Android snapshots do not verify an implemented port.

The format-2 board configuration and CPU/memory DTS wiring now exist, with
implementation scope and remaining UEFI/DMA constraints recorded in
`porting.toml`. Platform host checks are kept separate from device boot claims.

See [platform-bootstrap/README.md](platform-bootstrap/README.md) for the committed
configuration host checks and their exact source revision.
