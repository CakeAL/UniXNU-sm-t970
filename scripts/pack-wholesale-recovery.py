#!/usr/bin/env python3
"""Install a standard UniXNU FAT payload in the known SM-T970 Recovery wrapper."""
import argparse
import hashlib
import struct
import subprocess
import tempfile
import tomllib
from pathlib import Path

PAGE = 4096
BASE_SHA256 = "33efcec0915129321995cd4de57a3223f7fd41e36c8f73205f07fa97e7aeaeba"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def align(size):
    return (size + PAGE - 1) // PAGE * PAGE


def fat_read(path, name):
    return subprocess.check_output(["mcopy", "-i", path, "::/EFI/UniXNU/" + name, "-"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.base.read_bytes()
    require(hashlib.sha256(base).hexdigest() == BASE_SHA256, "Expected the tested persistent Recovery wrapper")
    payload = args.payload.read_bytes()
    require(len(payload) % PAGE == 0, "FAT image must be page aligned")
    shim_size, _, old_fat_size = struct.unpack_from("<III", base, 8)
    require((struct.unpack_from("<I", base, 36)[0], struct.unpack_from("<I", base, 40)[0]) == (PAGE, 2),
            "Expected the Samsung Android v2 Recovery wrapper")
    fat_at = PAGE + align(shim_size)
    dtbo_size, old_dtbo_at, _, dtb_size = struct.unpack_from("<IQII", base, 1632)
    require(old_dtbo_at == fat_at + align(old_fat_size), "Unexpected Recovery component positions")
    dtb_at = old_dtbo_at + align(dtbo_size)
    end = dtb_at + align(dtb_size)

    with tempfile.TemporaryDirectory() as temporary:
        old_fat = Path(temporary) / "base-fat.img"
        old_fat.write_bytes(base[fat_at:fat_at + old_fat_size])
        for name in ("Payloads/scratch-data.img", "Payloads/kernel.macho.trustcache"):
            require(fat_read(args.payload, name) == fat_read(old_fat, name), f"Changed Recovery input: {name}")

    config = tomllib.loads(fat_read(args.payload, "unixnu.toml").decode())
    boot_entries = [entry for entry in config["entry"] if entry["type"] == "xnu"]
    require(len(boot_entries) == 1, "Expected one XNU boot entry")
    command_line = boot_entries[0]["args"]
    words = set(command_line.split())
    require(len(command_line.encode()) <= 1000 and {"sheng-data-persist=2", "data-fua=1", "native-ufs-root=1"} <= words and
            not any(word.split("=", 1)[0] in {"ufsrw", "t970-ufs-data", "log", "sheng-log", "data-reset",
                                             "sheng-data-reset", "t970-dram-end", "memory-outside"}
                    for word in words), "Unsafe storage or memory switch")

    dtbo = base[old_dtbo_at:old_dtbo_at + dtbo_size]
    dtb = base[dtb_at:dtb_at + dtb_size]
    boot_id = hashlib.sha1()
    for part in (base[PAGE:PAGE + shim_size], payload, b"", dtbo, dtb):
        boot_id.update(part)
        boot_id.update(struct.pack("<I", len(part)))
    header = bytearray(base[:PAGE])
    struct.pack_into("<I", header, 16, len(payload))
    struct.pack_into("<Q", header, 1636, fat_at + len(payload))
    header[576:608] = boot_id.digest().ljust(32, b"\0")
    image = bytes(header) + base[PAGE:fat_at] + payload + base[old_dtbo_at:end]
    require(len(image) <= len(base), "Image exceeds measured RECOVERY capacity")
    image = image.ljust(len(base), b"\0")
    with args.output.open("xb") as stream:
        stream.write(image)
    require(args.output.read_bytes() == image, "Recovery image differs on readback")
    print(f"{len(image)} bytes SHA-256 {hashlib.sha256(image).hexdigest()}")


if __name__ == "__main__":
    main()
