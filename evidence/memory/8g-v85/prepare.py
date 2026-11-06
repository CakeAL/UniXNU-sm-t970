#!/usr/bin/env python3
"""Pack v85: the 8 GiB ADT change plus the kernel with larger bootstrap tables."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

DEVICE = Path(__file__).resolve().parents[3]
TREE = DEVICE / 'out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree'
BASE = DEVICE / 'out/data-bringup/setup-skip-v84/boot-partition.img'
BASE_SHA = '215edec49f9ebf641b2b312f954416eb35e0d4347473b4bf97dd5581857b68cb'
BUILD = DEVICE / 'out/data-bringup/setup-8g-v85-build'
OUTPUT = DEVICE / 'out/data-bringup/setup-8g-v85'
PREFIX = '::/EFI/UniXNU/'
CONFIG = 'unixnu.toml'
KERNEL = 'Payloads/kernel.macho'
ADT = 'Payloads/kernel.macho.adt'
NEW_DRAM_SIZE = 0x200000000
OLD_DRAM_SIZE = 0x80000000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    boot = BASE.read_bytes()
    require(boot[:8] == b'ANDROID!' and digest(boot) == BASE_SHA, 'Expected the exact v84 BOOT')
    kernel_size, = struct.unpack_from('<I', boot, 8)
    payload_size, = struct.unpack_from('<I', boot, 16)
    page, version = struct.unpack_from('<II', boot, 36)
    require((page, version) == (4096, 2), 'Requires Android header v2 and 4096-byte pages')
    start = page + ((kernel_size + page - 1) // page) * page
    end = start + payload_size
    require(start < end < len(boot), 'Invalid ramdisk bounds')

    OUTPUT.mkdir()
    fat = OUTPUT / 'payload.img'
    fat.write_bytes(boot[start:end])

    def read(name):
        return subprocess.check_output(['mcopy', '-i', str(fat), PREFIX + name, '-'])

    config = read(CONFIG)
    seed = read('Payloads/scratch-data.img')
    trust = read('Payloads/kernel.macho.trustcache')
    adt = read(ADT)
    kernel = output_kernel()

    patched_adt = OUTPUT / ADT.split('/')[-1]
    subprocess.run(['python3.14', str(DEVICE / 'scripts/patch-adt-dram-size.py'),
                    '--input', str(write_temp(adt, OUTPUT / 'source.adt')),
                    '--output', str(patched_adt),
                    '--size', str(NEW_DRAM_SIZE), '--expect-old', str(OLD_DRAM_SIZE)], check=True)
    require(struct.pack('<Q', NEW_DRAM_SIZE) in patched_adt.read_bytes(), 'ADT dram-size not written')

    for path, name in ((kernel, KERNEL), (patched_adt, ADT)):
        subprocess.run(['mcopy', '-o', '-i', str(fat), str(path), PREFIX + name], check=True)
    require(read(CONFIG) == config, 'Final BOOT configuration changed')
    require(read('Payloads/scratch-data.img') == seed, 'Final Data seed changed')
    require(read('Payloads/kernel.macho.trustcache') == trust, 'Final trust cache changed')
    require(read(KERNEL) == kernel.read_bytes(), 'Final kernel differs')
    require(read(ADT) == patched_adt.read_bytes(), 'Final ADT differs')

    result = boot[:start] + fat.read_bytes() + boot[end:]
    require(len(result) == len(boot) and result[:start] == boot[:start] and result[end:] == boot[end:],
            'Header, firmware, DTB or partition tail changed')
    require(fat.stat().st_size == payload_size, 'Payload size changed')
    (OUTPUT / 'boot-partition.img').write_bytes(result)

    report = dict(base_boot_sha256=BASE_SHA, boot_sha256=digest(result), boot_bytes=len(result),
                  kernel_sha256=digest(kernel.read_bytes()), kernel_build_sha256=digest((BUILD / 'kernel.macho').read_bytes()),
                  adt_sha256=digest(patched_adt.read_bytes()), source_adt_sha256=digest(adt),
                  dram_size=hex(NEW_DRAM_SIZE), data_seed_sha256=digest(seed), config_sha256=digest(config),
                  trust_cache_sha256=digest(trust), unchanged_header_firmware_dtb_tail=True, uploaded=False)
    (OUTPUT / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


def write_temp(data, path):
    path.write_bytes(data)
    return path


def output_kernel():
    build = BUILD / 'kernel.macho'
    require(build.is_file(), 'Missing built kernel')
    target = OUTPUT / 'kernel.macho'
    shutil.copyfile(build, target)
    env = dict(os.environ, UNIXNU_UEFI=str(DEVICE / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(TREE / 'scripts/patch-xnu-entry-probe.py'),
                    str(target), '--panic-screen', '--no-reset'], env=env, check=True)
    kernel = target.read_bytes()
    require(b'blank/dark=' in kernel and b't970-fb-cached' in kernel and b'Setup touch report scheduling' in kernel,
            'Missing linked display, cache or report markers')
    return target


if __name__ == '__main__':
    main()
