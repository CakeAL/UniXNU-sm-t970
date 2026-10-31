# Step 4 build-configuration resolution

Device commit `8055073ce9a05fa60624decae4b8c74b1a544746`, framework `194aae294c1107e791f4f74b2be371a391ac6bc4`. Both trees were
clean when `unixnu defconfig`, `unixnu fetch`, `unixnu status --json` and
`unixnu tree` ran, followed by the committed checker.

- `result.json`: configuration layers, profile paths, component and archive
  lists, patch counts per series (arch 56, SoC 2, OS 3, board 0), 19 modules,
  the nine `unixnu.lock` sources, tree link targets and input hashes.
- `status.json`: full `unixnu status --json` snapshot at this commit.
- `tree.json` / `tree.txt`: assembled-tree inventory (drivers, kits, refer,
  patches, scripts) and the raw `tree` command output.
- `check.log`: checker output, ending in both PASS lines.

What the checker proves, independently of the framework's own resolution:

1. The configuration layers are applied in the documented order
   (arch, SoC, OS, device) and the prelink kernelcache hash matches the OS
   profile.
2. The four patch series resolve to exactly the 61 patches and order that
   `status` reports, with no duplicates.
3. Every selected component and each of the 19 modules matches its pin in
   `feeds.toml`/`unixnu.lock`; driver, kit and fetch checkouts are clean.
4. `out/<device>/<profile>/<config>/tree/` links drivers, kits and refer to
   those pinned sources, `kits/sm-t970` to this repository's `package/`,
   `patches/xnu` to the board series, and copies framework/SoC/device scripts.
   SoC sources are intentionally absent from `tree/refer`; the framework skips
   `kind = "soc"` there and consumes `ctx.soc.path` directly.

Limits: this is resolution and assembly only. Nothing was compiled, packed or
booted, and `unixnu.local.toml` (kernelcache, trust cache, Data seed, unique
chip id) does not exist yet, so `build_config` is empty by design.
