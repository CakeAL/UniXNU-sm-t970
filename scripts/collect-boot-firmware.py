#!/usr/bin/env python3
"""Read SM-T970 XBL and boot headers; record FFS hashes and platform inputs.

Optional extracted binaries stay in a caller-specified ignored directory. This
does not execute firmware, write any device node, or obtain a UEFI runtime map.
Only the observed FV/FFS/gzip section formats are supported; other layouts fail.
"""
import argparse
import csv
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import uuid
from zoneinfo import ZoneInfo

from adb_readonly import read


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sections(data):
    cursor = 0
    while cursor + 4 <= len(data):
        size = int.from_bytes(data[cursor:cursor + 3], "little")
        if size < 4 or size == 0xffffff or cursor + size > len(data):
            raise ValueError("Unsupported/truncated FFS section")
        yield data[cursor + 3], data[cursor + 4:cursor + size]
        cursor = (cursor + size + 3) & ~3


def volumes(data):
    """Walk validated FV headers; embedded sections are visited separately."""
    cursor = 0
    while True:
        signature = data.find(b"_FVH", cursor)
        if signature < 0:
            return
        start = signature - 40
        cursor = signature + 4
        if start < 0 or start + 56 > len(data):
            continue
        length = struct.unpack_from("<Q", data, start + 32)[0]
        header = struct.unpack_from("<H", data, start + 48)[0]
        if header < 56 or header % 2 or length < header or start + length > len(data):
            continue
        if sum(struct.unpack_from(f"<{header // 2}H", data, start)) & 0xffff:
            raise ValueError("FV header checksum mismatch")
        yield start, length, header
        cursor = start + length


def files(data, origin="xbl"):
    for start, length, header in volumes(data):
        cursor, end = start + ((header + 7) & ~7), start + length
        while cursor + 24 <= end:
            raw = data[cursor:cursor + 24]
            if raw == b"\xff" * 24:
                break
            size = int.from_bytes(raw[20:23], "little")
            if size < 24 or size == 0xffffff or cursor + size > end:
                raise ValueError("Unsupported/truncated FFS file")
            kind = raw[18]
            if kind != 0xf0:  # FV padding is not a section stream.
                # IntegrityCheck.File and State do not participate in header checksum.
                if (sum(raw) - raw[17] - raw[23]) & 0xff:
                    raise ValueError("FFS header checksum mismatch")
                body = data[cursor + 24:cursor + size]
                entry = {"guid": str(uuid.UUID(bytes_le=raw[:16])), "type": kind,
                         "origin": origin, "offset": cursor, "size": size,
                         "ffs_sha256": sha(data[cursor:cursor + size]),
                         "name": "", "sections": []}
                payloads = {}
                for index, (section_type, payload) in enumerate(sections(body)):
                    if section_type == 0x15:
                        entry["name"] = payload.decode("utf-16le").rstrip("\0")
                    entry["sections"].append({"type": section_type, "size": len(payload),
                                              "sha256": sha(payload)})
                    payloads[index] = payload
                yield entry, payloads
                if kind == 0xb:
                    for index, section in enumerate(entry["sections"]):
                        if section["type"] != 2:
                            raise ValueError("Unsupported encapsulated FV section")
                        payload = payloads[index]
                        guid = str(uuid.UUID(bytes_le=payload[:16]))
                        offset, attributes = struct.unpack_from("<HH", payload, 16)
                        if guid != "1d301fe9-be79-4353-91c2-d23bc959ae0c" or offset != 24 or attributes != 1:
                            raise ValueError("Unsupported guided decompression")
                        decompressed = gzip.decompress(payload[offset - 4:])
                        if len(decompressed) > 32 * 1024 * 1024:
                            raise ValueError("Unexpected decompressed volume size")
                        yield from files(decompressed, origin + "/gzip-fv")
            cursor = (cursor + size + 7) & ~7


def platform_config(payload):
    text = payload.rstrip(b"\0").decode("ascii")
    section, regions, parameters = "", [], {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            section = line.strip("[]")
        elif section in ("MemoryMap", "RegisterMap"):
            fields = next(csv.reader([line], skipinitialspace=True))
            if len(fields) != 8:
                raise ValueError("Unexpected memory descriptor")
            regions.append(dict(zip(["base", "size", "name", "hob", "resource", "attributes", "type", "cache"],
                                    [int(fields[0], 0), int(fields[1], 0), *[s.strip() for s in fields[2:]]])))
        elif "=" in line:
            key, value = map(str.strip, line.split("=", 1))
            # Retain numeric platform constants; paths/default apps are not used.
            if re.fullmatch(r"0x[0-9a-fA-F]+|[0-9]+", value):
                parameters[key] = int(value, 0)
    return {"regions": regions, "numeric_parameters": parameters}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract-dir", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite a capture")
    if args.extract_dir:
        ignored = subprocess.run(["git", "check-ignore", "--", str(args.extract_dir / "probe")], capture_output=True)
        if ignored.returncode:
            parser.error("--extract-dir must be Git-ignored to keep proprietary binaries local")
        if args.extract_dir.exists():
            parser.error("Extraction directory already exists")
    identity = read("getprop ro.product.model; getprop ro.product.device; getprop ro.bootloader").decode().splitlines()
    if identity[:2] != ["SM-T970", "gts7xlwifi"]:
        raise ValueError("Wrong device")
    record = {"captured_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "device": dict(zip(["model", "codename", "bootloader"], identity)),
              "partitions": {}, "files": [], "platform_config": None,
              "limits": ["XBL configuration is stock firmware input, not a runtime GetMemoryMap observation.",
                         "Android boot partition is Magisk-modified; header/packing observations are not a pristine image claim.",
                         "Extracted DXE binaries are not yet tested in Mu-Silicium."]}
    for name in ["xbl", "xbl_config", "abl"]:
        command = "cat /dev/block/by-name/" + name
        data = read(command)
        if len(data) > 16 * 1024 * 1024:
            raise ValueError("Unexpected firmware partition size")
        record["partitions"][name] = {"command": command, "size": len(data), "sha256": sha(data)}
        if name != "xbl":
            continue
        for entry, payloads in files(data):
            record["files"].append(entry)
            for index, section in enumerate(entry["sections"]):
                if entry["name"] == "uefiplat.cfg" and section["type"] == 0x19:
                    if record["platform_config"] is not None:
                        raise ValueError("Ambiguous platform config")
                    record["platform_config"] = platform_config(payloads[index])
                if args.extract_dir and section["type"] in (0x10, 0x13, 0x19):
                    suffix = {0x10: "efi", 0x13: "depex", 0x19: "raw"}[section["type"]]
                    path = args.extract_dir / entry["guid"] / (str(index) + "." + suffix)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payloads[index])
    if not record["platform_config"]:
        raise ValueError("No validated stock platform configuration found")
    record["boot_headers"] = {}
    for name in ["boot", "recovery"]:
        header = read("dd if=/dev/block/by-name/" + name + " bs=4096 count=1 2>/dev/null")
        if header[:8] != b"ANDROID!":
            raise ValueError("Unsupported boot image")
        keys = ["kernel_size", "kernel_addr", "ramdisk_size", "ramdisk_addr", "second_size",
                "second_addr", "tags_addr", "page_size", "header_version", "os_version"]
        fields = dict(zip(keys, struct.unpack_from("<10I", header, 8)))
        if fields["header_version"] != 2:
            raise ValueError("Expected Android header v2")
        fields.update(zip(["recovery_dtbo_size", "recovery_dtbo_offset", "header_size", "dtb_size", "dtb_addr"],
                          struct.unpack_from("<IQIIQ", header, 1632)))
        record["boot_headers"][name] = fields
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Saved {len(record['files'])} FFS records and {len(record['platform_config']['regions'])} stock regions")


if __name__ == "__main__":
    main()
