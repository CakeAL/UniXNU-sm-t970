#!/usr/bin/env python3
"""Hash target firmware compiled into this SM-T970 boot kernel, without saving it.

The Android image header bounds the read to the kernel field. AArch64 RELATIVE
relocations identify name/data pointers in builtin_fw entries. Three independent
names must yield one consistent image base and a compact 24-byte entry table.
"""
import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib
from zoneinfo import ZoneInfo

from adb_readonly import read


NAMES = ["tsp_stm/fts1ba90a_gts7xl.bin", "epen/w9021_gts7xl.bin", "keyboard_stm/stm32_gts7l.bin"]


def inspect(image):
    if image[56:60] != b"ARM\x64":
        raise ValueError("Not an AArch64 Image")
    relocations = []
    for match in re.finditer(rb"(?=(.{8}\x03\x04\x00\x00\x00\x00\x00\x00.{8}))", image, re.S):
        if match.start() % 8 == 0:
            target, kind, addend = struct.unpack("<QQQ", match[1])
            if target >= 0xffff000000000000 and addend >= 0xffff000000000000:
                relocations.append((target, addend))
    lookup = dict(relocations)
    if any(lookup[target] != addend for target, addend in relocations):
        raise ValueError("Ambiguous relocation targets")
    candidates = defaultdict(dict)
    for name in NAMES:
        positions = [m.start() for m in re.finditer(re.escape(name.encode() + b"\0"), image)]
        for position in positions:
            for target, addend in relocations:
                base = addend - position
                offset = target - base
                if base % 4096 or base < 0xffff000000000000 or not 0 <= offset <= len(image) - 24:
                    continue
                data_offset = lookup.get(target + 8, 0) - base
                size = struct.unpack_from("<Q", image, offset + 16)[0]
                if not 0 < size < 4 * 1024 * 1024 or not 0 <= data_offset <= len(image) - size:
                    continue
                if name in candidates[base]:
                    raise ValueError("Ambiguous builtin entry for " + name)
                candidates[base][name] = {"name": name, "table_offset": offset,
                                          "data_offset": data_offset, "size": size,
                                          "sha256": hashlib.sha256(image[data_offset:data_offset + size]).hexdigest()}
    complete = [(base, entries) for base, entries in candidates.items() if set(entries) == set(NAMES)]
    if len(complete) != 1:
        raise ValueError("Could not identify a unique builtin firmware table")
    base, entries = complete[0]
    offsets = sorted(entry["table_offset"] for entry in entries.values())
    if offsets[-1] - offsets[0] > 4096 or any((offset - offsets[0]) % 24 for offset in offsets):
        raise ValueError("Inconsistent builtin entry layout")
    return {"inferred_link_base": hex(base), "relative_relocations": len(relocations),
            "layout": "builtin_fw: name pointer, data pointer, u64 length; 24 bytes",
            "files": list(entries.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing capture")
    identity = read("getprop ro.product.model; getprop ro.product.device; getprop ro.bootloader").decode().splitlines()
    if identity[:2] != ["SM-T970", "gts7xlwifi"]:
        raise ValueError("Wrong device")
    header_command = "dd if=/dev/block/by-name/boot bs=4096 count=1 2>/dev/null"
    header = read(header_command)
    size = struct.unpack_from("<I", header, 8)[0]
    page, version = struct.unpack_from("<II", header, 36)
    if header[:8] != b"ANDROID!" or page != 4096 or version != 2 or not 0 < size < 256 * 1024 * 1024:
        raise ValueError("Unexpected Android boot layout")
    command = f"dd if=/dev/block/by-name/boot bs=4096 skip=1 count={(size + 4095) // 4096} 2>/dev/null"
    raw = read(command)[:size]
    if len(raw) != size:
        raise ValueError("Truncated kernel read")
    compression = "gzip" if raw[:2] == b"\x1f\x8b" else "none"
    image = zlib.decompress(raw, 16 + zlib.MAX_WBITS) if compression == "gzip" else raw
    result = inspect(image)
    result.update(captured_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                  device=dict(zip(["model", "codename", "bootloader"], identity)),
                  commands=[header_command, command], header_version=version,
                  kernel_compression=compression, kernel_field_bytes=size,
                  kernel_field_sha256=hashlib.sha256(raw).hexdigest(),
                  image_sha256=hashlib.sha256(image).hexdigest(),
                  scope="Firmware bytes in the current Magisk-modified boot kernel, not a UniXNU input-driver test")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Hashed {len(result['files'])} builtin assets; unique relocation-consistent image base")


if __name__ == "__main__":
    main()
