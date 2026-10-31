#!/usr/bin/env python3
"""Inventory stock firmware using read-only ADB; save metadata, never binaries.

The allowlist excludes persist, EFS, calibration partitions and user data.
An observed asset is not a selected or validated UniXNU driver dependency.
"""
import argparse
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import shlex
from zoneinfo import ZoneInfo

from adb_readonly import read


FAMILIES = {
    "gpu": ["/vendor/firmware/a650_*", "/vendor/firmware_mnt/image/a650_zap.*"],
    "wifi": ["/vendor/firmware/qca6390/*",
             "/vendor/firmware/wlan/qca_cld/WCNSS_qcom_cfg.ini"],
    "bluetooth": ["/vendor/firmware/htbtfw20.tlv", "/vendor/firmware/htnv20.bin"],
    "audio": ["/vendor/firmware/cs35l40-spk-dsp1-*",
              "/vendor/firmware_mnt/image/adsp.*",
              "/vendor/firmware_mnt/image/adspr.jsn",
              "/vendor/firmware_mnt/image/adspua.jsn"],
}
INPUT_NAMES = ["tsp_stm/fts1ba90a_gts7xl.bin", "epen/w9021_gts7xl.bin",
               "keyboard_stm/stm32_gts7l.bin"]
SEARCH_ROOTS = ["/vendor/firmware", "/vendor/firmware_mnt/image", "/odm/firmware",
                "/system/etc/firmware", "/lib/firmware"]


def collect():
    identity = read("getprop ro.product.model; getprop ro.product.device; getprop ro.bootloader").decode().splitlines()
    if identity[:2] != ["SM-T970", "gts7xlwifi"]:
        raise ValueError("Expected SM-T970/gts7xlwifi, received " + repr(identity[:2]))
    files, commands = [], []
    for family, patterns in FAMILIES.items():
        # Patterns are repository constants, not device/user-provided shell input.
        command = "for f in " + " ".join(patterns) + "; do " + (
            'if [ -f "$f" ]; then sha256sum "$f"; stat -c "%s" "$f"; fi; done')
        commands.append(command)
        lines = read(command).decode().splitlines()
        if len(lines) % 2:
            raise ValueError("Incomplete hash/size response for " + family)
        for offset in range(0, len(lines), 2):
            digest, path = lines[offset].split(None, 1)
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("Invalid firmware digest")
            files.append({"family": family, "source": path.strip(), "sha256": digest,
                          "size": int(lines[offset + 1]), "selected": False,
                          "consumer": "future " + family + " adaptation; stock asset only"})
    probes = []
    for name in INPUT_NAMES:
        candidates = [root + "/" + name for root in SEARCH_ROOTS]
        command = "for f in " + " ".join(map(shlex.quote, candidates)) + "; do " + (
            'if [ -f "$f" ]; then sha256sum "$f"; fi; done')
        commands.append(command)
        output = read(command).decode().strip()
        probes.append({"firmware_name": name, "searched": candidates,
                       "found": output.splitlines(),
                       "conclusion": "not found in searched filesystem paths" if not output else "filesystem asset found"})
    config = gzip.decompress(read("cat /proc/config.gz"))
    selected_config = [line for line in config.decode().splitlines()
                       if re.match(r"(?:# )?CONFIG_(?:FW_LOADER|EXTRA_FIRMWARE|TOUCHSCREEN.*|WACOM.*|SEC.*TSP.*)(?:=| )", line)]
    return {"captured_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "device": dict(zip(["model", "codename", "bootloader"], identity)),
            "transport": "adb -d shell -T su -c (serial omitted)",
            "scope": "Stock filesystem firmware metadata; not a UniXNU boot result or a complete UEFI binary inventory",
            "commands": commands, "files": sorted(files, key=lambda f: f["source"]),
            "input_firmware_probes": probes,
            "kernel_config": {"command": "cat /proc/config.gz", "uncompressed_sha256": hashlib.sha256(config).hexdigest(),
                              "selected_lines": selected_config},
            "uefi_interfaces": {path: bool(read("if [ -d " + path + " ]; then echo yes; fi").strip())
                                for path in ["/sys/firmware/efi", "/sys/firmware/memmap"]},
            "limits": ["Missing input firmware may be built into the kernel; absence in these paths does not establish that.",
                       "Board-data variants are inventoried without choosing the loaded variant.",
                       "No proprietary binaries or personal calibration data are saved."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to replace an existing capture")
    record = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Saved {len(record['files'])} stock assets and {len(record['input_firmware_probes'])} input-firmware probes to {args.output}")


if __name__ == "__main__":
    main()
