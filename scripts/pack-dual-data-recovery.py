#!/usr/bin/env python3
"""Repack the verified SM-T970 dual-system RECOVERY with a guarded Data kernel."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile
import tomllib

BASE_SHA = "5c9355fa81ac394b1d001593b5d59d1e961293afeff0f7da1eb6776476958056"
FAT_PREFIX = "::/EFI/UniXNU/"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


GPU_PROBES = {
    33: b"GPU cb1ctx %s/%s tlb=",
    34: b"GPU streams %s free=",
}


def pack(base, kernel, mode, *, gpu_probe=None, shutdown=False, pen=False, haptics=False, usb=False, gpu_addon=False):
    require(hashlib.sha256(base).hexdigest() == BASE_SHA, "Expected the verified dual-system RECOVERY")
    require(all(marker in kernel for marker in (
        b"T970 Data probe:", b"T970 Data persistence not active", b"store header is foreign")),
        "Kernel lacks the guarded T970 persistence path")
    if gpu_probe is not None:
        require(mode == 2, "The GPU probe uses the verified persistent Data configuration")
        require(gpu_probe in GPU_PROBES and GPU_PROBES[gpu_probe] in kernel,
                "Kernel lacks the selected T970 GPU probe")
    if shutdown:
        require(mode == 2 and gpu_probe is None, "Shutdown verification requires standalone persistent mode")
        require(b"T970PlatformPower: shutdown failsafe armed" in kernel,
                "Kernel lacks the T970 shutdown failsafe")
    if pen:
        require(mode == 2 and gpu_probe is None, "S Pen requires standalone persistent mode")
        require(b"T970 pen: original IOHIDEventDriver attached" in kernel,
                "Kernel lacks the T970 Pencil HID service")
    if haptics:
        require(mode == 2 and gpu_probe is None, "Haptics requires standalone persistent mode")
        require(b"t970-haptics" in kernel, "Kernel lacks the T970 haptics service")
    if usb:
        require(mode == 2 and gpu_probe is None, "USB requires standalone persistent mode")
        require(b"T970 USB: MUIC route=" in kernel and b"com.apple.driver.AppleUSBDeviceMux" in kernel,
                "Kernel lacks the shared MUIC route or Apple USB device stack")

    shim_size, ramdisk_size, second_size, page, version = (
        struct.unpack_from("<I", base, offset)[0] for offset in (8, 16, 24, 36, 40))
    require((second_size, page, version) == (0, 4096, 2), "Unexpected Android boot layout")
    dtbo_size, dtbo_at, _, dtb_size = struct.unpack_from("<IQII", base, 1632)
    ramdisk_at = page + ((shim_size + page - 1) // page) * page
    ramdisk_end = ramdisk_at + ramdisk_size
    dtb_at = dtbo_at + ((dtbo_size + page - 1) // page) * page

    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        fat = work / "payload.img"
        fat.write_bytes(base[ramdisk_at:ramdisk_end])
        mcopy = ["mcopy", "-o", "-i", str(fat)]

        def read(name):
            return subprocess.check_output([*mcopy, FAT_PREFIX + name, "-"])

        preserved = {name: read(name) for name in (
            "Payloads/kernel.macho.adt", "Payloads/kernel.macho.trustcache", "Payloads/scratch-data.img")}
        seed = preserved["Payloads/scratch-data.img"]
        require(struct.unpack_from("<8sIIQ", seed) == (b"DBRDISK1", 1, 4096, 512 << 20),
                "Expected the original 512 MiB Data seed")
        config = read("unixnu.toml").decode()
        require(config.count("sheng-data-persist=0") == 1, "Unexpected baseline Data mode")
        config = config.replace("sheng-data-persist=0", f"sheng-data-persist={mode}")
        if mode == 1:
            require(config.count("t970-data-space=1") == 1, "Expected the baseline Data report argument")
            config = config.replace("t970-data-space=1", "t970-data-probe=1")
        if gpu_probe is not None:
            require("t970-gpu-p=" not in config and config.count("t970-data-space=1") == 1,
                    "Unexpected baseline GPU arguments")
            config = config.replace("t970-data-space=1", f"t970-gpu-p={gpu_probe}")
        if shutdown:
            require(config.count("t970-data-space=1") == 1 and "t970-shutdown-wait=" not in config,
                    "Unexpected baseline shutdown arguments")
            config = config.replace("t970-data-space=1", "t970-shutdown-wait=10")
        if pen:
            require("t970-pen=" not in config and config.count("t970-setup-report-touch=1") == 1,
                    "Expected the verified HID boot arguments")
            config = config.replace("t970-setup-report-touch=1", "t970-pen=14359")
        if haptics:
            require("t970-haptics=" not in config and config.count("t970-memory-report=1") == 1,
                    "Expected the verified diagnostics arguments")
            config = config.replace("t970-memory-report=1", "t970-haptics=3")
        if usb:
            require("t970-usb=" not in config and config.count("t970-ui-stack=10") == 1,
                    "Expected the verified diagnostics arguments")
            config = config.replace("t970-ui-stack=10", "t970-usb=37")
        entries = [entry for entry in tomllib.loads(config)["entry"] if entry["type"] == "xnu"]
        require(len(entries) == 1, "Expected one XNU entry")
        command_line = entries[0]["args"]
        if gpu_addon and "gpu-addon=1" not in command_line.split():
            command_line = command_line.rstrip() + " gpu-addon=1 fb-gpu=1"
            config = config.replace(entries[0]["args"], command_line)
        require(len(command_line.encode()) <= 1000 and "t970-ufs-unixnu=1" in command_line.split(),
                "Invalid XNU arguments")
        require(not any(arg.startswith(("sheng-data-reset", "sheng-log=", "ufsrw="))
                        for arg in command_line.split()), "Conflicting storage argument")
        for name, content in (("unixnu.toml", config.encode()), ("Payloads/kernel.macho", kernel)):
            source = work / Path(name).name
            source.write_bytes(content)
            subprocess.run([*mcopy, str(source), FAT_PREFIX + name], check=True)
            require(read(name) == content, f"FAT readback differs for {name}")
        require(all(read(name) == content for name, content in preserved.items()),
                "ADT, trust cache or Data seed changed")
        payload = fat.read_bytes()
    require(len(payload) == ramdisk_size, "FAT size changed")

    boot_id = hashlib.sha1()
    for component in (base[page:page + shim_size], payload, b"",
                      base[dtbo_at:dtbo_at + dtbo_size], base[dtb_at:dtb_at + dtb_size]):
        boot_id.update(component)
        boot_id.update(struct.pack("<I", len(component)))
    header = bytearray(base[:page])
    header[576:608] = boot_id.digest().ljust(32, b"\0")
    return bytes(header) + base[page:ramdisk_at] + payload + base[ramdisk_end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True, help="prelinked kernel with the panic screen")
    parser.add_argument("--mode", type=int, choices=(1, 2), required=True, help="1 probes read-only, 2 persists Data")
    gpu = parser.add_mutually_exclusive_group()
    gpu.add_argument("--gpu-cb1", dest="gpu_probe", action="store_const", const=33,
                     help="enable the CB1 activation probe in mode 2")
    gpu.add_argument("--gpu-streams", dest="gpu_probe", action="store_const", const=34,
                     help="enable the GPU stream slot survey in mode 2")
    parser.add_argument("--shutdown", action="store_true", help="enable the post-unmount shutdown failsafe in mode 2")
    parser.add_argument("--pen", action="store_true", help="enable the independent Pencil HID in mode 2")
    parser.add_argument("--haptics", action="store_true", help="enable haptics and one boot pulse in mode 2")
    parser.add_argument("--usb", action="store_true", help="enable DWC3 high-speed device mode in mode 2")
    parser.add_argument("--gpu-addon", action="store_true", help="use the addon embedded in the kernel image (mode 2)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    recovery = pack(args.base.read_bytes(), args.kernel.read_bytes(), args.mode,
                    gpu_probe=args.gpu_probe, shutdown=args.shutdown, pen=args.pen, haptics=args.haptics, usb=args.usb, gpu_addon=args.gpu_addon)
    with args.output.open("xb") as output:
        output.write(recovery)
    print(f"RECOVERY mode={args.mode} sha256={hashlib.sha256(recovery).hexdigest()} {args.output}")


if __name__ == "__main__":
    main()
