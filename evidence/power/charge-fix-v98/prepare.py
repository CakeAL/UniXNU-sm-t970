#!/usr/bin/env python3
"""Pack v98: verify the watchdog kick by preserved bits only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tomllib

DEVICE = Path(__file__).resolve().parents[3]
TREE = DEVICE / 'out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree'
BASE = DEVICE / 'out/data-bringup/charge-restart-v97/boot-partition.img'
BASE_SHA = '96ff33b674e62c4ca18eeb3efed8955d718e22c70c7a4d9d20f5116063a5f979'
BUILD = DEVICE / 'out/data-bringup/charge-fix-v98-build'
OUTPUT = DEVICE / 'out/data-bringup/charge-fix-v98'
PREFIX = '::/EFI/UniXNU/'
CONFIG = 'unixnu.toml'
KERNEL = 'Payloads/kernel.macho'
ADT = 'Payloads/kernel.macho.adt'
DRAM_SIZE = 0x200000000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    boot = BASE.read_bytes()
    require(boot[:8] == b'ANDROID!' and digest(boot) == BASE_SHA, 'Expected the exact v97 BOOT')
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
    require(b't970-battery=1' in config and b't970-battery-ro=3' in config and
            b't970-memory-report=1' in config and b't970-charge=1' in config,
            'Expected v97 charge configuration')
    entries = tomllib.loads(config.decode())['entry']
    for entry in entries:
        if entry.get('type') == 'xnu':
            require(len(entry['args'].encode()) <= 1000, 'Command line exceeds Loader bound')
            require(b't970-charge=1' in entry['args'].encode(), 'Charge action argument missing')
    config_path = OUTPUT / CONFIG
    config_path.write_bytes(config)
    subprocess.run(['mcopy', '-o', '-i', str(fat), str(config_path), PREFIX + CONFIG], check=True)
    seed = read('Payloads/scratch-data.img')
    trust = read('Payloads/kernel.macho.trustcache')
    adt = read(ADT)
    require(struct.pack('<Q', DRAM_SIZE) in adt, 'Expected the v97 ADT')
    kernel = output_kernel()

    subprocess.run(['mcopy', '-o', '-i', str(fat), str(kernel), PREFIX + KERNEL], check=True)
    require(read(CONFIG) == config, 'Final BOOT configuration changed')
    require(read('Payloads/scratch-data.img') == seed, 'Final Data seed changed')
    require(read('Payloads/kernel.macho.trustcache') == trust, 'Final trust cache changed')
    require(read(ADT) == adt, 'Final ADT changed')
    require(read(KERNEL) == kernel.read_bytes(), 'Final kernel differs')

    result = boot[:start] + fat.read_bytes() + boot[end:]
    require(len(result) == len(boot) and result[:start] == boot[:start] and result[end:] == boot[end:],
            'Header, firmware, DTB or partition tail changed')
    require(fat.stat().st_size == payload_size, 'Payload size changed')
    (OUTPUT / 'boot-partition.img').write_bytes(result)

    report = dict(base_boot_sha256=BASE_SHA, boot_sha256=digest(result), boot_bytes=len(result),
                  kernel_sha256=digest(kernel.read_bytes()),
                  kernel_build_sha256=digest((BUILD / 'kernel.macho').read_bytes()),
                  adt_sha256=digest(adt), dram_size=hex(DRAM_SIZE),
                  data_seed_sha256=digest(seed), config_sha256=digest(config),
                  trust_cache_sha256=digest(trust), unchanged_adt_seed_trust=True,
                  unchanged_config=True, battery_service=True,
                  charge_boot_arg='t970-charge=1', guarded_charge_action=True,
                  kick_verification='CNFG_06 bits7:2 only; WDTCLR self-clears',
                  charger_registers_written=['CNFG_09 0xc0', 'CNFG_06 0xbd'],
                  unchanged_header_firmware_dtb_tail=True, uploaded=False)
    (OUTPUT / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


def output_kernel():
    build = BUILD / 'kernel.macho'
    require(build.is_file(), 'Missing built kernel')
    target = OUTPUT / 'kernel.macho'
    shutil.copyfile(build, target)
    env = dict(os.environ, UNIXNU_UEFI=str(DEVICE / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(TREE / 'scripts/patch-xnu-entry-probe.py'),
                    str(target), '--panic-screen', '--no-reset'], env=env, check=True)
    kernel = target.read_bytes()
    for marker in (b'blank/dark=', b't970-fb-cached', b'Setup touch report scheduling',
                   b'Gauge id=', b'Bat present=', b'Battery svc=', b'Charger cfg=',
                   b'T970 battery: charger action result=', b'Memory owned base='):
        require(marker in kernel, f'Missing linked marker {marker!r}')
    return target


if __name__ == '__main__':
    main()
