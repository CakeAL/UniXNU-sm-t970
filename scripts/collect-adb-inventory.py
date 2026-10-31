#!/usr/bin/env python3
"""Collect read-only stock-Android inputs; never flash or write device nodes.

Requires one USB ADB device. --root uses an existing su installation.
Serial numbers, network addresses, user logs and the DT chosen node are excluded.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import zlib
from zoneinfo import ZoneInfo


COMMANDS = {
    "identity": """
id; uname -a; getenforce
for p in ro.product.model ro.product.device ro.soc.model ro.soc.manufacturer ro.board.platform ro.hardware ro.bootloader ro.build.version.release ro.build.version.sdk ro.build.version.security_patch ro.build.fingerprint ro.boot.flash.locked ro.boot.vbmeta.device_state ro.boot.verifiedbootstate ro.boot.warranty_bit ro.boot.bootdevice ro.boot.boot_devices; do
    printf '%s=' "$p"; getprop "$p"
done
""",
    "cpu": """
cat /proc/cpuinfo
getconf PAGE_SIZE
for p in /sys/devices/system/cpu/possible /sys/devices/system/cpu/present /sys/devices/system/cpu/online /sys/devices/system/cpu/cpu[0-9]*/topology/* /sys/devices/system/cpu/cpufreq/policy*/related_cpus /sys/devices/system/cpu/cpufreq/policy*/cpuinfo_max_freq /sys/devices/system/cpu/cpufreq/policy*/scaling_available_frequencies; do
    if [ -f "$p" ]; then printf '\n%s\n' "$p"; cat "$p"; fi
done
cat /proc/interrupts
""",
    "memory": """
cat /proc/meminfo
cat /proc/iomem
ls -l /sys/class/iommu
""",
    "storage": """
ls -l /dev/block/by-name
cat /proc/partitions
for d in /sys/class/block/sd*; do
    printf '\n%s\n' "$d"
    for k in start size partition queue/logical_block_size queue/physical_block_size device/vendor device/model device/rev; do
        if [ -f "$d/$k" ]; then printf '%s=' "$k"; cat "$d/$k"; fi
    done
done
ls -l /sys/class/scsi_device
""",
    "display": """
ls -l /sys/class/drm /sys/class/graphics /sys/class/lcd /sys/class/backlight
for p in /sys/class/drm/card0-DSI-1/status /sys/class/drm/card0-DSI-1/enabled /sys/class/drm/card0-DSI-1/modes /sys/class/drm/card0-DSI-1/dpms /sys/class/lcd/panel/lcd_type /sys/class/backlight/*/max_brightness /sys/class/backlight/*/brightness; do
    if [ -f "$p" ]; then printf '\n%s\n' "$p"; cat "$p"; fi
done
wm size; wm density
""",
    "display_boot": """
tr ' ' '\\n' < /proc/cmdline | grep -E '^(msm_drm[.]dsi_display|mdss_mdp[.]panel)'
""",
    "input": """
cat /proc/bus/input/devices
getevent -lp
for d in /sys/bus/i2c/devices/*-* /sys/bus/spi/devices/*; do
    if [ -d "$d" ]; then
        printf '\n%s\n' "$d"; readlink -f "$d/driver"
        for k in name modalias; do if [ -f "$d/$k" ]; then printf '%s=' "$k"; cat "$d/$k"; fi; done
    fi
done
""",
    "gpu": """
for p in /sys/class/kgsl/kgsl-3d0/gpu_model /sys/class/kgsl/kgsl-3d0/gpu_available_frequencies /sys/class/kgsl/kgsl-3d0/max_gpuclk /sys/class/kgsl/kgsl-3d0/num_pwrlevels /sys/class/kgsl/kgsl-3d0/usesgmem; do
    if [ -f "$p" ]; then printf '\n%s\n' "$p"; cat "$p"; fi
done
ls -l /vendor/firmware/a650* /vendor/firmware/a615_zap*
sha256sum /vendor/firmware/a650_gmu.bin /vendor/firmware/a650_sqe.fw
""",
    "network": """
for d in /sys/bus/pci/devices/*; do
    printf '\n%s\n' "$d"; readlink -f "$d/driver"
    for k in vendor device subsystem_vendor subsystem_device class modalias; do
        if [ -f "$d/$k" ]; then printf '%s=' "$k"; cat "$d/$k"; fi
    done
done
readlink -f /sys/class/net/wlan0/device
ls -l /sys/class/net/wlan0/device/driver
ls -l /vendor/firmware/qca6390 /vendor/firmware/wlan /vendor/firmware_mnt/image/*wlan* /vendor/firmware_mnt/image/*bdwlan* /vendor/firmware_mnt/image/*qca*
""",
    "audio": """
cat /proc/asound/cards
cat /proc/asound/pcm
ls -l /sys/bus/slimbus/devices /sys/bus/platform/devices/*adsp* /sys/bus/platform/devices/*lpass* /sys/bus/i2c/drivers/*cs35* /sys/bus/i2c/drivers/*wcd*
ls -l /vendor/firmware/*cs35* /vendor/firmware_mnt/image/adsp.*
""",
    "power": """
ls -l /sys/class/power_supply
for d in /sys/class/power_supply/*; do
    printf '\n%s\n' "$d"
    for k in type status present capacity voltage_now current_now temp technology charge_full charge_full_design energy_full_design online; do
        if [ -f "$d/$k" ]; then printf '%s=' "$k"; cat "$d/$k"; fi
    done
done
for p in /sys/power/state /sys/power/mem_sleep /sys/class/thermal/thermal_zone*/type; do
    if [ -f "$p" ]; then printf '\n%s\n' "$p"; cat "$p"; fi
done
""",
    "diagnostics": """
id; getenforce
ls -ld /sys/firmware/fdt /sys/firmware/devicetree/base /sys/kernel/debug /sys/fs/pstore
ls -l /sys/fs/pstore
ls -l /dev/block/by-name/boot /dev/block/by-name/recovery /dev/block/by-name/dtbo
""",
}


def redact(text):
    text = re.sub(r"(?m)^U: Uniq=.*$", "U: Uniq=<omitted>", text)
    return re.sub(r"(?m)^\s*unique id:.*$", "  unique id: <omitted>", text)


def sanitize_dts(text):
    # dtc emits each property on one line and uses braces only for nodes.
    output, depth, skip_depth = [], 0, None
    omitted = []
    for line in text.splitlines():
        if skip_depth is None and re.match(r"\s*chosen\s*\{", line):
            skip_depth = depth
            omitted.append("/chosen")
        if skip_depth is not None:
            depth += line.count("{") - line.count("}")
            if depth == skip_depth:
                skip_depth = None
            continue
        match = re.match(r"\s*([A-Za-z0-9_,#.+@-]+)\s*=", line)
        if match and re.search(r"serial.number|serialno|mac.address|(?:rng|kaslr).seed|bd.addr|bt.addr", match[1], re.I):
            omitted.append(match[1])
            continue
        output.append(line)
        depth += line.count("{") - line.count("}")
    if depth != 0 or skip_depth is not None:
        raise ValueError("Unbalanced dtc output during sanitization")
    return "// Sanitized live Android DT; /chosen and identifying properties omitted.\n" + "\n".join(output) + "\n", omitted


def gpt_inventory(read):
    """Read only primary GPT metadata; omit disk/partition GUIDs."""
    disks = {}
    for disk in ("sda", "sdb", "sdc", "sdd"):
        sector_size = int(read("cat /sys/class/block/" + disk + "/queue/logical_block_size",
                               binary=True))
        command = "dd if=/dev/block/" + disk + " bs=" + str(sector_size) + " count=2 2>/dev/null"
        raw = read(command, binary=True)
        header = raw[sector_size:sector_size * 2]
        if header[:8] != b"EFI PART":
            raise ValueError("No primary GPT signature: " + disk)
        header_size, expected_crc = struct.unpack_from("<II", header, 12)
        header_copy = bytearray(header[:header_size])
        header_copy[16:20] = b"\x00" * 4
        if zlib.crc32(header_copy) != expected_crc:
            raise ValueError("GPT header CRC mismatch: " + disk)
        entries_lba, count, entry_size, entries_crc = struct.unpack_from("<QIII", header, 72)
        if entry_size < 128 or count * entry_size > 1024 * 1024:
            raise ValueError("Unexpected GPT entry layout: " + disk)
        blocks = (count * entry_size + sector_size - 1) // sector_size
        command_entries = ("dd if=/dev/block/" + disk + " bs=" + str(sector_size) +
                           " skip=" + str(entries_lba) + " count=" + str(blocks) + " 2>/dev/null")
        table = read(command_entries, binary=True)[:count * entry_size]
        if zlib.crc32(table) != entries_crc:
            raise ValueError("GPT entries CRC mismatch: " + disk)
        partitions = []
        for i in range(count):
            entry = table[i * entry_size:(i + 1) * entry_size]
            if entry[:16] == b"\x00" * 16:
                continue
            first, last = struct.unpack_from("<QQ", entry, 32)
            partitions.append({"index": i + 1, "name": entry[56:128].decode("utf-16le").rstrip("\x00"),
                               "first_lba": first, "last_lba": last,
                               "offset_bytes": first * sector_size,
                               "size_bytes": (last - first + 1) * sector_size})
        disks[disk] = {"logical_block_size": sector_size,
                       "scsi_path": read("readlink -f /sys/class/block/" + disk + "/device",
                                         binary=True).decode().strip(),
                       "primary_header_crc_valid": True, "entry_array_crc_valid": True,
                       "commands": [command, command_entries], "partitions": partitions}
    return disks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", action="store_true", help="use existing su for read access")
    args = parser.parse_args()
    if (args.output / "capture.json").exists():
        parser.error("Output already contains a completed capture; choose a new directory")
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = {"captured_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                "root": args.root, "transport": "adb -d (one USB device; serial omitted)",
                "purpose": "Stock Android inventory only; no UniXNU validation", "commands": {}}

    def read(command, binary=False):
        remote = "su -c " + shlex.quote(command) if args.root else command
        # shell -T preserves binary bytes and gives the remote exit status.
        # exec-out can cause this Magisk su to allocate a PTY and insert CR bytes.
        result = subprocess.run(["adb", "-d", "shell", "-T", remote],
                                capture_output=True, timeout=60)
        if binary:
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace"))
            return result.stdout
        return result

    for name, command in COMMANDS.items():
        command = command.strip()
        result = read(command)
        content = ("$ " + command + "\n\n" + result.stdout.decode(errors="replace") +
                   "\n[stderr]\n" + result.stderr.decode(errors="replace") +
                   "\n[exit_code] " + str(result.returncode) + "\n")
        (args.output / (name + ".txt")).write_text(redact(content))
        metadata["commands"][name] = {"remote_shell": command, "exit_code": result.returncode}
        print(name + ": " + str(result.returncode), flush=True)

    raw = read("cat /sys/firmware/fdt", binary=True)
    if raw[:4] != bytes.fromhex("d00dfeed"):
        raise ValueError("Device did not return a flattened device tree")
    if len(raw) != struct.unpack_from(">I", raw, 4)[0]:
        raise ValueError("Flattened device tree size mismatch")
    dts = subprocess.run(["dtc", "-I", "dtb", "-O", "dts"], input=raw,
                         capture_output=True, check=True).stdout.decode()
    sanitized, omitted = sanitize_dts(dts)
    # Confirm the sanitized tree is still syntactically valid.
    subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", "/dev/null"],
                   input=sanitized.encode(), capture_output=True, check=True)
    (args.output / "live-device-tree.dts").write_text(sanitized)
    metadata["device_tree"] = {"command": "cat /sys/firmware/fdt", "original_size": len(raw),
                               "original_sha256": hashlib.sha256(raw).hexdigest(),
                               "omitted": omitted,
                               "note": "Original DT is not saved; sanitized DTS is not a flashable board DTB."}
    for partition in ("boot", "recovery"):
        command = "dd if=/dev/block/by-name/" + partition + " bs=4096 count=1 2>/dev/null"
        header = read(command, binary=True)
        if header[:8] != b"ANDROID!":
            raise ValueError("Unsupported boot header: " + partition)
        # Android boot header v0-v2 layout, before any cmdline fields.
        fields = struct.unpack_from("<10I", header, 8)
        names = ("kernel_size", "kernel_addr", "ramdisk_size", "ramdisk_addr", "second_size",
                 "second_addr", "tags_addr", "page_size", "header_version", "os_version")
        metadata[partition + "_header"] = dict(zip(names, fields))
        metadata[partition + "_header"]["command"] = command
        metadata[partition + "_header"]["magic"] = "ANDROID!"
    (args.output / "gpt.json").write_text(json.dumps(gpt_inventory(read), indent=2) + "\n")
    metadata["completed_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    metadata["files_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(args.output.iterdir()) if p.is_file()}
    (args.output / "capture.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("Saved " + str(args.output), flush=True)


if __name__ == "__main__":
    main()
