#!/usr/bin/env python3
"""Pack the v104 GPU power snapshot or the v105 CX pulse from its exact baseline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tomllib

DEVICE = Path(__file__).resolve().parents[3]
OUT = DEVICE / 'out/data-bringup'
TREE = OUT / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree'
PREFIX = '::/EFI/UniXNU/'
CONFIG = 'unixnu.toml'
KERNEL = 'Payloads/kernel.macho'
PRESERVED = ('Payloads/kernel.macho.adt', 'Payloads/scratch-data.img', 'Payloads/kernel.macho.trustcache')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cx-pulse', action='store_true', help='Pack v105 from the tested v104 BOOT')
    options = parser.parse_args()
    if options.cx_pulse:
        baseline = 'gpu-power-v104'
        base_sha = '031095d5baf37dae5f3ae7b89e4f1eaffd22683bea218efdf56ffe6e5434f902'
        output = OUT / 'gpu-cx-v105'
        old, new = b't970-gpu-p=1', b't970-gpu-p=2'
        markers = (b'GPU cx pre=', b'ack=%u restore=%u')
    else:
        baseline = 'gpu-clk-write-v103'
        base_sha = '6b1240530b8b702f1ea1083d1f2adb94f2a9ec59203422932a75946399e6ec80'
        output = OUT / 'gpu-power-v104'
        old, new = b't970-gpu-w=1', b't970-gpu-p=1'
        markers = (b'GPU pwr cfg/mem/dvm/axi=', b'cx/hw/gx/ahb/gmu/smmu=')
    build = output.with_name(output.name + '-build')
    boot = (OUT / baseline / 'boot-partition.img').read_bytes()
    require(boot[:8] == b'ANDROID!' and sha(boot) == base_sha, f'Expected the exact {baseline} BOOT')
    kernel_size, = struct.unpack_from('<I', boot, 8)
    payload_size, = struct.unpack_from('<I', boot, 16)
    page, version = struct.unpack_from('<II', boot, 36)
    require((page, version) == (4096, 2), 'Requires Android header v2 and 4096-byte pages')
    start = page + ((kernel_size + page - 1) // page) * page
    end = start + payload_size
    require(start < end < len(boot), 'Invalid ramdisk bounds')
    output.mkdir()
    fat = output / 'payload.img'
    fat.write_bytes(boot[start:end])
    copy = ['mcopy', '-i', str(fat)]

    def read(name):
        return subprocess.check_output([*copy, PREFIX + name, '-'])

    original_config = read(CONFIG)
    old_flag, new_flag = b' ' + old + b' ', b' ' + new + b' '
    require(original_config.count(old_flag) == 1 and new_flag not in original_config, 'Unexpected baseline GPU flag')
    config = original_config.replace(old_flag, new_flag)
    entries = [entry for entry in tomllib.loads(config.decode())['entry'] if entry.get('type') == 'xnu']
    require(len(entries) == 1, 'Expected one XNU entry')
    args = entries[0]['args'].encode()
    require(len(args) <= 1000 and new in args.split() and old not in args.split(),
            'Invalid GPU flag or Loader argument length')
    config_path = output / CONFIG
    config_path.write_bytes(config)
    preserved = {name: sha(read(name)) for name in PRESERVED}

    built = build / 'kernel.macho'
    kernel = output / 'kernel.macho'
    shutil.copyfile(built, kernel)
    env = dict(os.environ, UNIXNU_UEFI=str(DEVICE / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(TREE / 'scripts/patch-xnu-entry-probe.py'),
                    str(kernel), '--panic-screen', '--no-reset'], env=env, check=True)
    payload_kernel = kernel.read_bytes()
    for marker in (*markers, b't970-gpu-p',
                   b'GPU arc db=', b'Battery svc=', b'Memory owned base=', b'blank/dark='):
        require(marker in payload_kernel, f'Missing linked marker {marker!r}')

    for local, name in ((config_path, CONFIG), (kernel, KERNEL)):
        subprocess.run([*copy, '-o', str(local), PREFIX + name], check=True)
    require(read(CONFIG) == config and read(KERNEL) == payload_kernel, 'FAT readback mismatch')
    require({name: sha(read(name)) for name in PRESERVED} == preserved, 'Inherited FAT input changed')
    payload = fat.read_bytes()
    require(len(payload) == payload_size, 'Payload size changed')
    result = boot[:start] + payload + boot[end:]
    (output / 'boot-partition.img').write_bytes(result)

    compile_report = json.loads((build / 'registration/report.json').read_text())
    report = dict(base_boot_sha256=base_sha, boot_sha256=sha(result), boot_bytes=len(result),
                  kernel_build_sha256=sha(built.read_bytes()), kernel_sha256=sha(payload_kernel),
                  config_sha256=sha(config), xnu_args_bytes=len(args), gpu_boot_arg=new.decode(),
                  unchanged_fat_inputs=preserved, unchanged_header_firmware_dtb_tail=True,
                  gpu_soc_revision=compile_report['gpu_soc_revision'],
                  gpu_soc_header_sha256=compile_report['gpu_soc_header_sha256'])
    (output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
