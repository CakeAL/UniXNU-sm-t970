#!/usr/bin/env python3
"""Pack a RECOVERY whose FAT carries Payloads/kernel.macho.gpuaddon and whose ADT
declares the matching 16-byte GpuAddon property, exactly as DarwinBoot expects."""
from __future__ import annotations

import argparse, hashlib, re, struct, subprocess, tempfile
from pathlib import Path

PAGE = 4096
LIMIT = 86888448


def node_entry(blob: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<II", blob, offset)


def find_node(blob: bytes, path: str) -> tuple[int, int]:
    """Return (properties_begin, child_begin) for a path like '/chosen/memory-map'."""
    hit: list[tuple[int, int]] = []

    def walk(offset: int, prefix: str) -> int:
        count, children = node_entry(blob, offset)
        cursor = offset + 8
        props = {}
        for _ in range(count):
            key, size = struct.unpack_from("<32sI", blob, cursor)
            cursor += 36
            props[key.split(b"\0", 1)[0].decode()] = (cursor, size)
            cursor += (size + 3) & ~3
        begin, length = props["name"]
        name = blob[begin:begin + length].rstrip(b"\0").decode()
        here = "/" if not prefix else prefix.rstrip("/") + "/" + name
        if here == path:
            hit.append((offset, cursor))
            return cursor
        for _ in range(children):
            cursor = walk(cursor, here)
        return cursor
    walk(0, "")
    if not hit:
        raise SystemExit(f"ADT has no {path}")
    return hit[0]


def add_property(blob: bytes, path: str, key: str, value: bytes) -> bytes:
    node_at, prop_end = find_node(blob, path)
    count, children = node_entry(blob, node_at)
    record = key.encode().ljust(32, b"\0") + struct.pack("<I", len(value)) + value
    record += b"\0" * ((-len(value)) % 4)
    out = bytearray(blob)
    struct.pack_into("<I", out, node_at, count + 1)
    return bytes(out[:prop_end]) + record + bytes(out[prop_end:])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--addon", type=Path, required=True)
    parser.add_argument("--args", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()

    base = a.base.read_bytes()
    addon = a.addon.read_bytes()
    assert addon[:8] == b"NGPUADD2" and struct.unpack_from("<Q", addon, 16)[0] == len(addon)
    shim = struct.unpack_from("<I", base, 8)[0]
    dtbo_at = struct.unpack_from("<Q", base, 1636)[0]
    ramdisk_at = PAGE + ((shim + PAGE - 1) // PAGE) * PAGE
    ramdisk_size = dtbo_at - ramdisk_at
    assert ramdisk_size > (16 << 20), "unexpected ramdisk extent"
    dtbo_size = struct.unpack_from("<I", base, 1632)[0]
    dtb_size = struct.unpack_from("<I", base, 1648)[0]
    dtb_at = dtbo_at + ((dtbo_size + PAGE - 1) // PAGE) * PAGE

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        fat = work / "fat.img"
        fat.write_bytes(base[ramdisk_at:ramdisk_at + ramdisk_size])

        def read(name: str) -> bytes:
            return subprocess.check_output(["mcopy", "-i", str(fat), "::/EFI/UniXNU/" + name, "-"])

        kernel = read("Payloads/kernel.macho")
        adt = add_property(read("Payloads/kernel.macho.adt"), "/chosen/memory-map", "GpuAddon", b"\0" * 16)
        trust = read("Payloads/kernel.macho.trustcache")
        seed = read("Payloads/scratch-data.img")
        config = read("unixnu.toml").decode()
        entry = re.search(r'args = "([^"]*)"', config).group(1)
        words = entry.split()
        for extra in a.args:
            if extra not in words:
                words.append(extra)
        config = config.replace(entry, " ".join(words))
        assert len(" ".join(words).encode()) <= 1023

        need = (len(kernel) + len(adt) + len(trust) + len(seed) + len(addon) + len(config)
                + 2 * 1024 * 1024)
        new_size = max(ramdisk_size, -(-need // PAGE) * PAGE)
        assert ramdisk_at + new_size + dtbo_size + dtb_size <= LIMIT
        new_fat = work / "fat-new.img"
        subprocess.run(["mformat", "-i", str(new_fat), "-C", "-F", "-T", str(new_size // 512)], check=True)
        for d in ("::/EFI", "::/EFI/UniXNU", "::/EFI/UniXNU/Payloads"):
            subprocess.run(["mmd", "-i", str(new_fat), d], check=True)
        files = {"unixnu.toml": config.encode(), "Payloads/kernel.macho": kernel,
                 "Payloads/kernel.macho.adt": adt,
                 "Payloads/kernel.macho.trustcache": trust,
                 "Payloads/scratch-data.img": seed,
                 "Payloads/kernel.macho.gpuaddon": addon}
        for name, content in files.items():
            src = work / Path(name).name
            src.write_bytes(content)
            subprocess.run(["mcopy", "-o", "-i", str(new_fat), str(src), "::/EFI/UniXNU/" + name], check=True)
            assert subprocess.check_output(["mcopy", "-i", str(new_fat), "::/EFI/UniXNU/" + name, "-"]) == content
        payload = new_fat.read_bytes()
        assert len(payload) == new_size

    dtbo_at_new = dtbo_at + new_size - ramdisk_size
    header = bytearray(base[:PAGE])
    struct.pack_into("<I", header, 16, new_size)
    struct.pack_into("<Q", header, 1636, dtbo_at_new)
    boot_id = hashlib.sha1()
    for part in (base[PAGE:ramdisk_at], payload, b"",
                 base[dtbo_at:dtb_at], base[dtb_at:dtb_at + dtb_size]):
        boot_id.update(part)
        boot_id.update(struct.pack("<I", len(part)))
    header[576:608] = boot_id.digest().ljust(32, b"\0")
    image = bytes(header) + base[PAGE:ramdisk_at] + payload + base[dtbo_at:dtb_at] + base[dtb_at:dtb_at + dtb_size]
    assert len(image) <= LIMIT
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("xb") as fh:
        fh.write(image)
    print(f"RECOVERY bytes={len(image)} ramdisk={new_size} sha256={hashlib.sha256(image).hexdigest()} {a.output}")


if __name__ == "__main__":
    main()
