#!/usr/bin/env python3
"""Prepare a cadence-b-equivalent Recovery with the existing GPU trace enabled."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tomllib


FAT_PREFIX = "::/EFI/UniXNU/"
BASE_SHA256 = "ed73a75e491c618801110d0847302f0454b9390445cdf2b6ff3805a1f7ae8c8f"
PRESERVED = (
    "Payloads/kernel.macho",
    "Payloads/kernel.macho.adt",
    "Payloads/kernel.macho.trustcache",
    "Payloads/scratch-data.img",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fat_read(image: Path, name: str) -> bytes:
    return subprocess.check_output(
        ["mcopy", "-i", str(image), FAT_PREFIX + name, "-"]
    )


def xnu_args(config: bytes) -> str:
    parsed = tomllib.loads(config.decode())
    entries = [entry["args"] for entry in parsed["entry"] if entry["type"] == "xnu"]
    if len(entries) != 1:
        raise RuntimeError(f"expected one XNU entry, found {len(entries)}")
    return entries[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("out/cadence-b-20261117"))
    parser.add_argument("--output", type=Path, default=Path("out/gpu-timeline-a-20261117"))
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    base = (repo / args.base).resolve()
    output = (repo / args.output).resolve()
    source_boot = base / "boot.img"
    source_payload = base / "payload.img"
    wrapper = repo / "out/dual-system/data-persistence-20261111/recovery-persistent.img"
    trust = repo / "out/main7-direct-ready-20261117/trust/owner-trust.bundle"

    if sha256(source_boot.read_bytes()) != BASE_SHA256:
        raise RuntimeError("cadence-b boot image hash does not match the device-tested baseline")
    output.mkdir(parents=True, exist_ok=True)
    payload = output / "payload.img"
    boot = output / "boot.img"
    menu = output / "unixnu.toml"
    if payload.exists() or boot.exists():
        raise RuntimeError(f"refusing to overwrite an existing image in {output}")

    before = {name: fat_read(source_payload, name) for name in PRESERVED}
    config = fat_read(source_payload, "unixnu.toml")
    old_args = xnu_args(config)
    old_words = old_args.split()
    if old_words.count("log-gpu=1") != 1 or "gpu-trace=1" in old_words:
        raise RuntimeError("unexpected cadence-b GPU diagnostic arguments")

    updated = config.decode().replace(" log-gpu=1 ", " gpu-trace=1 ", 1)
    new_args = xnu_args(updated.encode())
    new_words = new_args.split()
    if set(new_words) - set(old_words) != {"gpu-trace=1"}:
        raise RuntimeError("unexpected added command-line arguments")
    if set(old_words) - set(new_words) != {"log-gpu=1"}:
        raise RuntimeError("unexpected removed command-line arguments")
    if len(new_args.encode()) > 1000:
        raise RuntimeError("command line exceeds the firmware limit")
    for required in ("dpu-scanout=2", "tu-debug=noubwc,nocb", "fb-gpu=1", "vsync=60"):
        if required not in new_words:
            raise RuntimeError(f"required baseline argument disappeared: {required}")

    shutil.copyfile(source_payload, payload)
    menu.write_text(updated)
    subprocess.run(
        ["mcopy", "-o", "-i", str(payload), str(menu), FAT_PREFIX + "unixnu.toml"],
        check=True,
    )
    if fat_read(payload, "unixnu.toml") != updated.encode():
        raise RuntimeError("FAT command-line readback failed")
    after = {name: fat_read(payload, name) for name in PRESERVED}
    if before != after:
        raise RuntimeError("a preserved payload member changed")

    subprocess.run(
        [
            "python3.14",
            str(repo / "scripts/pack-wholesale-recovery.py"),
            "--base",
            str(wrapper),
            "--payload",
            str(payload),
            "--output",
            str(boot),
            "--large-data-seed",
            "--trust-cache",
            str(trust),
        ],
        check=True,
    )

    result = boot.read_bytes()
    shim_size = struct.unpack_from("<I", result, 8)[0]
    fat_start = 4096 + (shim_size + 4095) // 4096 * 4096
    payload_bytes = payload.read_bytes()
    if result[fat_start : fat_start + len(payload_bytes)] != payload_bytes:
        raise RuntimeError("packed Recovery payload readback failed")
    if len(result) != 86888448:
        raise RuntimeError(f"unexpected Recovery size: {len(result)}")

    print(
        json.dumps(
            {
                "build_tag": "gpu-timeline-a",
                "baseline_boot_sha256": BASE_SHA256,
                "boot_image": str(boot.relative_to(repo)),
                "boot_image_sha256": sha256(result),
                "boot_bytes": len(result),
                "payload_sha256": sha256(payload_bytes),
                "kernel_sha256": sha256(after["Payloads/kernel.macho"]),
                "adt_sha256": sha256(after["Payloads/kernel.macho.adt"]),
                "trust_cache_sha256": sha256(after["Payloads/kernel.macho.trustcache"]),
                "data_seed_sha256": sha256(after["Payloads/scratch-data.img"]),
                "command_line_bytes": len(new_args.encode()),
                "argument_removed": "log-gpu=1",
                "argument_added": "gpu-trace=1",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
