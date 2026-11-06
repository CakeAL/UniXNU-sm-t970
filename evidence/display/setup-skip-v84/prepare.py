#!/usr/bin/env python3
"""Repack the v83 BOOT with the framework's Setup-skip Data seed."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

DEVICE = Path(__file__).resolve().parents[3]
TREE = DEVICE / 'out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree'
TOOL = TREE / 'scripts/seed-data-skip-setup.py'
BASE = DEVICE / 'out/data-bringup/setup-fb-cache-v83/boot-partition.img'
BASE_SHA = 'b739e1ca32ac6a6359611f5b85564048ce96d5804b3a35eb3716c251a52ea9bc'
OUTPUT = DEVICE / 'out/data-bringup/setup-skip-v84'
FAT_PREFIX = '::/EFI/UniXNU/'
SEED = 'Payloads/scratch-data.img'
CONFIG = 'unixnu.toml'
KERNEL = 'Payloads/kernel.macho'
UNCHANGED = (CONFIG, KERNEL, 'Payloads/kernel.macho.adt', 'Payloads/kernel.macho.trustcache')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    boot = BASE.read_bytes()
    require(boot[:8] == b'ANDROID!' and digest(boot) == BASE_SHA, 'Expected the exact v83 BOOT')
    kernel_size, = struct.unpack_from('<I', boot, 8)
    payload_size, = struct.unpack_from('<I', boot, 16)
    page, version = struct.unpack_from('<II', boot, 36)
    require((page, version) == (4096, 2), 'Requires Android header v2 and 4096-byte pages')
    start = page + ((kernel_size + page - 1) // page) * page
    end = start + payload_size
    require(start < end < len(boot), 'Invalid ramdisk bounds')

    output = OUTPUT
    output.mkdir()
    fat = output / 'payload.img'
    fat.write_bytes(boot[start:end])

    def read(name):
        return subprocess.check_output(['mcopy', '-i', str(fat), FAT_PREFIX + name, '-'])

    fixed = {name: digest(read(name)) for name in UNCHANGED}
    config = read(CONFIG)
    seed = output / 'seed.img'
    seed.write_bytes(read(SEED))

    skipped = output / 'seed-skip.dbr'
    subprocess.run(['python3.14', str(TOOL), str(seed), str(skipped), '--no-auto-dim'], check=True)
    require(skipped.is_file(), 'Setup-skip tool produced no seed')
    subprocess.run(['mcopy', '-o', '-i', str(fat), str(skipped), FAT_PREFIX + SEED], check=True)
    require(read(CONFIG) == config, 'Final BOOT configuration changed')
    require(read(SEED) == skipped.read_bytes(), 'Final Data seed differs')
    require(all(digest(read(name)) == value for name, value in fixed.items()), 'Final BOOT changed an input')

    result = boot[:start] + fat.read_bytes() + boot[end:]
    require(len(result) == len(boot) and result[:start] == boot[:start] and result[end:] == boot[end:],
            'Header, firmware, DTB or partition tail changed')
    require(fat.stat().st_size == payload_size, 'Payload size changed')
    (output / 'boot-partition.img').write_bytes(result)

    tool_report = json.loads(skipped.with_suffix('.json').read_text())
    report = dict(base_boot_sha256=BASE_SHA, boot_sha256=digest(result), boot_bytes=len(result),
                  kernel_sha256=fixed[KERNEL], seed_sha256=digest(skipped.read_bytes()),
                  seed_bytes=skipped.stat().st_size, source_seed_sha256=digest(seed.read_bytes()),
                  setup_skipped=tool_report['no_auto_dim'] and True,
                  preferences=tool_report['preferences'], build=tool_report['build'],
                  unchanged_payload_sha256=fixed, unchanged_header_firmware_dtb_tail=True,
                  terminal_runtime_report=False, uploaded=False)
    (output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
