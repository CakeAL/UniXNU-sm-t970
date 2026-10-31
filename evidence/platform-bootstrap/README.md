# Single-core platform host check

Device configuration and checker revision: `5cab8f372a491af149ce27df02d918f6ac8cddba`.
UniXNU revision: `04b4e558bcded5213c2d802984862dc062f28257`.

Run from the device repository using Python 3.11+:

```sh
python3.14 scripts/check-platform.py --unixnu ../UniXNU
```

- `result.json` records the checked source commits, input SHA256 values,
  single-core bindings, 30 static reservations and 61 ordered patches.
- `status.json` is the resolved UniXNU configuration. Local absolute paths are
  replaced by `{device}` and `{unixnu}`; no configuration values are changed.
- `dtc.txt` retains three naming warnings inherited from the Android static
  reservations. No measured `reg` value was changed to suppress them.
- `source-snapshots.json` records official API/codeload source acquisition:
  each complete Git tree and imported commit object hash matched the pinned
  upstream object. This was needed because this host's github.com Git endpoint
  timed out. The original upstream commit IDs were preserved.

The checker compared all eight declared CPU affinities with the Android DT,
then verified that only CPU0 is enabled in the output; GIC registers/stride and
19.2 MHz timebase match, and the ADT preserves the required platform nodes and
little-endian address properties. All 30 static reservation `reg` properties
match the input snapshot and do not overlap the chosen high RAM bank.

The high RAM bank is only a candidate for the required contiguous handoff.
UEFI allocatable memory, dynamic reservations and firmware ownership have not
been established. `board.example=true` remains set. The generated host-check
ADT uses artificial identity 1 and is not committed or suitable for booting.
No XNU compilation, prelink, UEFI image, hardware driver operation or device
boot was performed. These are host checks, not `device-verified` milestones.
