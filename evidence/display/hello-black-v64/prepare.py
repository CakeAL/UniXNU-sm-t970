#!/usr/bin/env python3
"""Pack the v63 black-screen capture with a 240-second terminal report."""
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
BUILD = OUT / 'hello-black-v64-build'
BASE = OUT / 'owned-window-2g-continuous-v63/boot-partition.img'
BASE_REPORT = DEVICE / 'evidence/display/owned-window-2g-continuous-v63/preparation.json'
OUTPUT = OUT / 'hello-black-v64'
TREE = OUT / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree'
PREFIX = '::/EFI/UniXNU/'
CONFIG = 'unixnu.toml'
KERNEL = 'Payloads/kernel.macho'
REPORT_ARG = 't970-runtime-report=240'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    baseline = json.loads(BASE_REPORT.read_text())
    source = BASE.read_bytes()
    require(source[:8] == b'ANDROID!' and digest(source) == baseline['boot_sha256'],
            'Expected the exact uploaded v63 BOOT')
    kernel_size, = struct.unpack_from('<I', source, 8)
    payload_size, = struct.unpack_from('<I', source, 16)
    page, version = struct.unpack_from('<II', source, 36)
    require((page, version) == (4096, 2), 'Requires Android header v2 and 4096-byte pages')
    start = page + ((kernel_size + page - 1) // page) * page
    end = start + payload_size
    require(start < end < len(source), 'Invalid ramdisk bounds')
    OUTPUT.mkdir()
    payload = OUTPUT / 'payload.img'
    payload.write_bytes(source[start:end])

    def read_fat(name):
        return subprocess.check_output(['mcopy', '-i', str(payload), PREFIX + name, '-'])

    config = read_fat(CONFIG)
    require(digest(config) == baseline['config_sha256'], 'Unexpected source boot configuration')
    expected = tomllib.loads(config.decode())
    xnu = [entry for entry in expected['entry'] if entry['type'] == 'xnu']
    require(len(xnu) == 1 and 't970-runtime-report' not in xnu[0]['args'],
            'Expected one continuous XNU entry')
    line = ('args = "' + xnu[0]['args'] + '"').encode()
    require(config.count(line) == 1, 'Ambiguous XNU entry')
    xnu[0]['args'] += ' ' + REPORT_ARG
    updated = config.replace(line, ('args = "' + xnu[0]['args'] + '"').encode())
    require(tomllib.loads(updated.decode()) == expected, 'Unexpected boot configuration difference')
    config_path = OUTPUT / CONFIG
    config_path.write_bytes(updated)

    replacement = OUTPUT / 'kernel.macho'
    shutil.copyfile(BUILD / 'kernel.macho', replacement)
    require(b'blank/dark=' in replacement.read_bytes(), 'Missing linked frame counters')
    env = dict(os.environ, UNIXNU_UEFI=str(DEVICE / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(TREE / 'scripts/patch-xnu-entry-probe.py'),
                    str(replacement), '--panic-screen', '--no-reset'], env=env, check=True)
    for name, path in ((CONFIG, config_path), (KERNEL, replacement)):
        subprocess.run(['mcopy', '-o', '-i', str(payload), str(path), PREFIX + name], check=True)
    require(payload.stat().st_size == payload_size, 'Payload size changed')
    boot = OUTPUT / 'boot-partition.img'
    boot.write_bytes(source[:start] + payload.read_bytes() + source[end:])
    result = boot.read_bytes()
    require(result[:start] == source[:start] and result[end:] == source[end:],
            'Header, firmware, DTB or partition tail changed')
    payload.write_bytes(result[start:end])
    require(read_fat(CONFIG) == updated and read_fat(KERNEL) == replacement.read_bytes(),
            'Final BOOT config or kernel differs')
    unchanged = {name: sha for name, sha in baseline['unchanged_payload_sha256'].items() if name != KERNEL}
    for name, sha in unchanged.items():
        require(digest(read_fat(name)) == sha, 'Unexpected final BOOT input: ' + name)
    report = dict(base_boot_sha256=baseline['boot_sha256'], boot_sha256=digest(result),
                  boot_bytes=len(result), kernel_sha256=digest((BUILD / 'kernel.macho').read_bytes()),
                  payload_kernel_sha256=digest(read_fat(KERNEL)), added_argument=REPORT_ARG,
                  unchanged_payload_sha256=unchanged, unchanged_header_firmware_dtb_tail=True,
                  terminal_runtime_report=True, uploaded=False)
    (OUTPUT / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
