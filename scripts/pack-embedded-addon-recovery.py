#!/usr/bin/env python3
"""Repack a verified SM-T970 dual-system RECOVERY with a kernel that carries the
GPU addon inside its own image, growing the FAT ramdisk into the free tail."""
from __future__ import annotations

import argparse, hashlib, re, struct, subprocess, tempfile
from pathlib import Path

PAGE = 4096
LIMIT = 86888448  # RECOVERY partition size from the PIT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--args", action="append", default=[], help="boot argument to add")
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()

    base = a.base.read_bytes()
    kernel = a.kernel.read_bytes()
    shim_size, ramdisk_size = struct.unpack_from("<II", base, 8)
    dtbo_size = struct.unpack_from("<I", base, 1632)[0]
    dtbo_at = struct.unpack_from("<Q", base, 1636)[0]
    dtb_size = struct.unpack_from("<I", base, 1648)[0]
    dtb_at = dtbo_at + ((dtbo_size + PAGE - 1) // PAGE) * PAGE
    ramdisk_at = PAGE + ((shim_size + PAGE - 1) // PAGE) * PAGE
    bps, spc, reserved, fats, root_entries, tot16, _, fat16, tot32 = struct.unpack_from(
        "<HBHBHHBHI", base, ramdisk_at + 11)
    assert b"FAT32" in base[ramdisk_at + 82:ramdisk_at + 90], "no FAT32 ramdisk at the aligned offset"
    ramdisk_size = min((tot32 or tot16) * bps, dtbo_at - ramdisk_at)
    ramdisk_end = ramdisk_at + ramdisk_size

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        fat = work / "fat.img"
        fat.write_bytes(base[ramdisk_at:ramdisk_end])
        names = ("unixnu.toml", "Payloads/kernel.macho.adt",
                 "Payloads/kernel.macho.trustcache", "Payloads/scratch-data.img")

        def read(name: str) -> bytes:
            return subprocess.check_output(
                ["mcopy", "-o", "-i", str(fat), "::/EFI/UniXNU/" + name, "-"])

        preserved = {name: read(name) for name in names}
        config = preserved["unixnu.toml"].decode()
        entry = re.search(r'args = "([^"]*)"', config)
        assert entry, "no XNU arguments"
        words = entry.group(1).split()
        for extra in a.args:
            if extra not in words:
                words.append(extra)
        assert len(" ".join(words).encode()) <= 1023, "boot arguments exceed the limit"
        config = config.replace(entry.group(1), " ".join(words))
        preserved["unixnu.toml"] = config.encode()

        need = len(kernel) + sum(len(v) for v in preserved.values()) + (1 << 20)
        new_size = max(ramdisk_size, -(-need // PAGE) * PAGE)
        assert ramdisk_at + new_size + dtbo_size + dtb_size <= LIMIT, "image exceeds the partition"
        new_fat = work / "fat-new.img"
        subprocess.run(["mformat", "-i", str(new_fat), "-C", "-F", "-T", str(new_size // 512)],
                       check=True)
        for directory in ("::/EFI", "::/EFI/UniXNU", "::/EFI/UniXNU/Payloads"):
            subprocess.run(["mmd", "-i", str(new_fat), directory], check=True)
        tmp_copy = ["mcopy", "-o", "-i", str(new_fat)]
        for name, content in (("unixnu.toml", preserved["unixnu.toml"]), ("Payloads/kernel.macho", kernel)):
            src = work / Path(name).name
            src.write_bytes(content)
            subprocess.run([*tmp_copy, str(src), "::/EFI/UniXNU/" + name], check=True)
            assert subprocess.check_output([*tmp_copy, "::/EFI/UniXNU/" + name, "-"]) == content
        for name in names[1:]:
            src = work / Path(name).name
            src.write_bytes(preserved[name])
            subprocess.run([*tmp_copy, str(src), "::/EFI/UniXNU/" + name], check=True)
            assert subprocess.check_output([*tmp_copy, "::/EFI/UniXNU/" + name, "-"]) == preserved[name]
        payload = new_fat.read_bytes()
        assert len(payload) == new_size

    delta = new_size - ramdisk_size
    dtbo_at_new = dtbo_at + delta
    header = bytearray(base[:PAGE])
    struct.pack_into("<I", header, 16, new_size)
    struct.pack_into("<Q", header, 1636, dtbo_at_new)
    boot_id = hashlib.sha1()
    for part in (base[PAGE:PAGE + shim_size], payload, b"",
                 base[dtbo_at:dtb_at], base[dtb_at:dtb_at + dtb_size]):
        boot_id.update(part)
        boot_id.update(struct.pack("<I", len(part)))
    header[576:608] = boot_id.digest().ljust(32, b"\0")
    image = bytes(header) + base[PAGE:ramdisk_at] + payload + base[dtbo_at:dtb_at] + base[dtb_at:dtb_at + dtb_size]
    assert len(image) <= LIMIT
    with a.output.open("xb") as fh:
        fh.write(image)
    print(f"RECOVERY bytes={len(image)} ramdisk={new_size} sha256={hashlib.sha256(image).hexdigest()} {a.output}")


if __name__ == "__main__":
    main()
