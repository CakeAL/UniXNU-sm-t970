#!/usr/bin/env python3
"""Repack a device-tested Recovery with exactly one command-line argument changed.

The base image's payload members are compared before and after the edit so an
argument experiment cannot silently carry a kernel, ADT, trust cache or Data
seed change. The packed Recovery is read back and its payload compared again.
"""

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
PRESERVED = (
    "Payloads/kernel.macho",
    "Payloads/kernel.macho.adt",
    "Payloads/kernel.macho.trustcache",
    "Payloads/scratch-data.img",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fat_read(image: Path, name: str) -> bytes:
    return subprocess.check_output(["mcopy", "-i", str(image), FAT_PREFIX + name, "-"])


def xnu_args(config: bytes) -> str:
    parsed = tomllib.loads(config.decode())
    entries = [entry["args"] for entry in parsed["entry"] if entry["type"] == "xnu"]
    if len(entries) != 1:
        raise RuntimeError(f"expected one XNU entry, found {len(entries)}")
    return entries[0]


def apply_edit(args: str, unset: list[str], set_pairs: list[str]) -> str:
    words = args.split()
    for word in unset:
        if words.count(word) != 1:
            raise RuntimeError(f"argument to remove is not present exactly once: {word}")
        words.remove(word)
    for pair in set_pairs:
        if "=" not in pair:
            raise RuntimeError(f"--set expects key=value, got {pair}")
        key = pair.split("=", 1)[0] + "="
        matches = [w for w in words if w.startswith(key)]
        if len(matches) > 1:
            raise RuntimeError(f"argument {key} appears more than once")
        if matches:
            words[words.index(matches[0])] = pair
        else:
            words.append(pair)
    return " ".join(words)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--base-boot-sha256", required=True)
    parser.add_argument("--unset", action="append", default=[])
    parser.add_argument("--set", dest="set_pairs", action="append", default=[])
    parser.add_argument("--expect", action="append", default=[])
    parser.add_argument(
        "--wrapper",
        type=Path,
        default=Path("out/dual-system/data-persistence-20261111/recovery-persistent.img"),
    )
    parser.add_argument(
        "--trust",
        type=Path,
        default=Path("out/main7-direct-ready-20261117/trust/owner-trust.bundle"),
    )
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    base = (repo / args.base).resolve()
    output = (repo / args.output).resolve()
    source_boot = base / "boot.img"
    source_payload = base / "payload.img"

    if sha256(source_boot.read_bytes()) != args.base_boot_sha256:
        raise RuntimeError("base Recovery hash does not match the device-tested image")
    output.mkdir(parents=True, exist_ok=True)
    payload = output / "payload.img"
    boot = output / "boot.img"
    menu = output / "unixnu.toml"
    if payload.exists() or boot.exists():
        raise RuntimeError(f"refusing to overwrite an existing image in {output}")

    before = {name: fat_read(source_payload, name) for name in PRESERVED}
    config = fat_read(source_payload, "unixnu.toml")
    old_args = xnu_args(config)
    new_args = apply_edit(old_args, args.unset, args.set_pairs)

    old_words, new_words = old_args.split(), new_args.split()
    allowed_added = set(args.set_pairs)
    allowed_removed = set(args.unset)
    if (set(new_words) - set(old_words)) - allowed_added:
        raise RuntimeError(
            f"unexpected added arguments: {(set(new_words) - set(old_words)) - allowed_added}"
        )
    if (set(old_words) - set(new_words)) - allowed_removed:
        raise RuntimeError(
            f"unexpected removed arguments: {(set(old_words) - set(new_words)) - allowed_removed}"
        )
    if new_args == old_args:
        raise RuntimeError("the edit changed nothing")
    if len(new_args.encode()) > 1000:
        raise RuntimeError("command line exceeds the firmware limit")
    for required in args.expect:
        if required not in new_words:
            raise RuntimeError(f"expected argument missing: {required}")

    updated = config.decode().replace(old_args, new_args, 1)
    if xnu_args(updated.encode()) != new_args:
        raise RuntimeError("menu edit did not round-trip")

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
            str((repo / args.wrapper).resolve()),
            "--payload",
            str(payload),
            "--output",
            str(boot),
            "--large-data-seed",
            "--trust-cache",
            str((repo / args.trust).resolve()),
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
                "build_tag": args.tag,
                "baseline_boot_sha256": args.base_boot_sha256,
                "boot_image": str(boot.relative_to(repo)),
                "boot_image_sha256": sha256(result),
                "boot_bytes": len(result),
                "payload_sha256": sha256(payload_bytes),
                "kernel_sha256": sha256(after["Payloads/kernel.macho"]),
                "adt_sha256": sha256(after["Payloads/kernel.macho.adt"]),
                "trust_cache_sha256": sha256(after["Payloads/kernel.macho.trustcache"]),
                "data_seed_sha256": sha256(after["Payloads/scratch-data.img"]),
                "command_line_bytes": len(new_args.encode()),
                "arguments_removed": sorted(set(old_words) - set(new_words)),
                "arguments_added": sorted(set(new_words) - set(old_words)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
