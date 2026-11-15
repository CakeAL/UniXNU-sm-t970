#!/usr/bin/env python3
"""Pack the tested firmware alone into a Recovery image (second-volume bootstrap).

  build-bootstrap-image.py [--base FILE] --output DIR

The Recovery image normally carries the payload FAT as its ramdisk, and that FAT
is capped at 0.95 * [payload] size_mib inside an 82.9 MiB partition, which is
what a GPU addon that has grown past ~14 MiB runs into. This builder keeps the
tested wrapper's header, firmware (kernel component), dtbo and device tree and
sets the ramdisk size to zero, so the firmware's own volume scan
(UniXNULib: the volume it booted from first, then every other volume that has
EFI/UniXNU/unixnu.toml) has to find the payload on the tablet's storage -- the
CACHE partition, written from scripts/build-cache-payload.py.

On its own this image boots the firmware menu with no XNU entry; pair it with
that payload. Everything it ships comes from the tested wrapper, so the only
reviewed inputs are its hash and the ramdisk decision.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = 4096
# The tested persistent Recovery wrapper (docs/HANDOFF-codex-20261115b.md).
BASE = ROOT / 'out/dual-system/data-persistence-20261111/recovery-persistent.img'
BASE_SHA256 = '33efcec0915129321995cd4de57a3223f7fd41e36c8f73205f07fa97e7aeaeba'


def align(size):
    return (size + PAGE - 1) // PAGE * PAGE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--base', type=Path, default=BASE, help='tested Recovery wrapper to keep')
    parser.add_argument('--ramdisk', type=Path,
                        help='small FAT to keep the boot image a normal Samsung layout '
                             '(it must not contain EFI/UniXNU/unixnu.toml, or the firmware '
                             'would boot from it instead of the second volume)')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()

    base = args.base.read_bytes()
    if hashlib.sha256(base).hexdigest() != BASE_SHA256:
        raise SystemExit('Expected the tested persistent Recovery wrapper')
    shim_size, _, old_fat_size = struct.unpack_from('<III', base, 8)
    page, version = struct.unpack_from('<II', base, 36)
    if (page, version) != (PAGE, 2):
        raise SystemExit('Expected the Samsung Android v2 Recovery wrapper')
    fat_at = PAGE + align(shim_size)
    dtbo_size, old_dtbo_at, _, dtb_size = struct.unpack_from('<IQII', base, 1632)
    if old_dtbo_at != fat_at + align(old_fat_size):
        raise SystemExit('Unexpected Recovery component positions')
    dtb_at = old_dtbo_at + align(dtbo_size)
    end = dtb_at + align(dtb_size)

    kernel = base[PAGE:PAGE + shim_size]
    ramdisk = args.ramdisk.read_bytes() if args.ramdisk else b''
    if args.ramdisk and len(ramdisk) % PAGE:
        raise SystemExit('ramdisk must be page aligned')
    dtbo = base[old_dtbo_at:old_dtbo_at + dtbo_size]
    dtb = base[dtb_at:dtb_at + dtb_size]

    header = bytearray(base[:PAGE])
    struct.pack_into('<I', header, 16, len(ramdisk))
    new_dtbo_at = PAGE + align(shim_size) + align(len(ramdisk))
    struct.pack_into('<Q', header, 1636, new_dtbo_at)
    boot_id = hashlib.sha1()
    for part in (kernel, ramdisk, b'', dtbo, dtb):
        boot_id.update(part)
        boot_id.update(struct.pack('<I', len(part)))
    header[576:608] = boot_id.digest().ljust(32, b'\0')

    image = bytes(header) + kernel + ramdisk + dtbo + dtb
    image = image.ljust(align(len(image)), b'\0')
    if len(image) > len(base):
        raise SystemExit('Bootstrap image exceeds the measured Recovery capacity')
    image = image.ljust(len(base), b'\0')

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'boot.img'
    path.write_bytes(image)
    report = {
        'base': str(args.base), 'base_sha256': BASE_SHA256,
        'firmware_sha256': hashlib.sha256(kernel).hexdigest(), 'firmware_bytes': len(kernel),
        'dtbo_sha256': hashlib.sha256(dtbo).hexdigest(),
        'dtb_sha256': hashlib.sha256(dtb).hexdigest(),
        'ramdisk_bytes': len(ramdisk),
        'ramdisk_sha256': hashlib.sha256(ramdisk).hexdigest() if ramdisk else None,
        'image_sha256': hashlib.sha256(image).hexdigest(), 'image_bytes': len(image),
        'recovery_partition_bytes': len(base),
        'component_offsets': {'kernel': PAGE, 'ramdisk': PAGE + align(shim_size),
                              'dtbo': new_dtbo_at, 'dtb': new_dtbo_at + align(dtbo_size)},
    }
    (output / 'image.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{path} {len(image)} bytes SHA-256 {report["image_sha256"]}')
    print(f'firmware {report["firmware_sha256"]} (ramdisk 0, dtbo at {new_dtbo_at})')


if __name__ == '__main__':
    main()
