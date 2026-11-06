#!/usr/bin/env python3
"""Pack a display, power, or touch-bus bring-up diagnostic."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--pm-watchdog', action='store_true', help='Start from the v66 sleep control')
    modes.add_argument('--touch-bus', action='store_true', help='Start from the v69 continuous display image')
    modes.add_argument('--touch-clock', action='store_true', help='Probe SE5 with a temporary clock vote')
    modes.add_argument('--touch-id', action='store_true', help='Try one GPIO open-drain touch identity read')
    modes.add_argument('--touch-rails', action='store_true', help='Read the touch rail resources and RSC state')
    modes.add_argument('--touch-power', action='store_true', help='Vote the qualified rails, then try one identity read')
    modes.add_argument('--touch-events', action='store_true', help='Sample the powered touch FIFO for 20 seconds')
    args = parser.parse_args()
    base, base_report, build, output = BASE, BASE_REPORT, BUILD, OUTPUT
    arguments = [REPORT_ARG]
    if args.pm_watchdog:
        base = OUT / 'sleep-disabled-v66/boot-partition.img'
        base_report = DEVICE / 'evidence/display/sleep-disabled-v66/preparation.json'
        build = OUT / 'pm-watchdog-v67-build'
        output = OUT / 'pm-watchdog-v67'
        arguments.append('t970-pm-watchdog-detail=1')
    touch_modes = (
        (args.touch_bus, 'touch-bus-v70', 1, b'Touch RO vote='),
        (args.touch_clock, 'touch-clock-v71', 2, b'Touch CLK vote='),
        (args.touch_id, 'touch-id-v72', 3, b'Touch ID idle='),
        (args.touch_rails, 'touch-rails-v73', 4, b'Touch RAIL db='),
        (args.touch_power, 'touch-power-v74', 5, b'Touch PWR A='),
        (args.touch_events, 'touch-events-v75', 6, b'Touch FIFO '),
    )
    touch = next((entry for entry in touch_modes if entry[0]), None)
    if touch:
        _, name, mode, marker = touch
        base = OUT / 'springboard-dim-continuous-v69/boot-partition.img'
        base_report = DEVICE / 'evidence/display/springboard-dim-continuous-v69/preparation.json'
        build = OUT / (name + '-build')
        output = OUT / name
        arguments = ['t970-runtime-report=75', f't970-touch-bus-report={mode}']
    baseline = json.loads(base_report.read_text())
    source = base.read_bytes()
    require(source[:8] == b'ANDROID!' and digest(source) == baseline['boot_sha256'],
            'Expected the exact uploaded source BOOT')
    kernel_size, = struct.unpack_from('<I', source, 8)
    payload_size, = struct.unpack_from('<I', source, 16)
    page, version = struct.unpack_from('<II', source, 36)
    require((page, version) == (4096, 2), 'Requires Android header v2 and 4096-byte pages')
    start = page + ((kernel_size + page - 1) // page) * page
    end = start + payload_size
    require(start < end < len(source), 'Invalid ramdisk bounds')
    output.mkdir()
    payload = output / 'payload.img'
    payload.write_bytes(source[start:end])

    def read_fat(name):
        return subprocess.check_output(['mcopy', '-i', str(payload), PREFIX + name, '-'])

    config = read_fat(CONFIG)
    config_sha = baseline['unchanged_payload_sha256'][CONFIG] if args.pm_watchdog else baseline['config_sha256']
    require(digest(config) == config_sha, 'Unexpected source boot configuration')
    expected = tomllib.loads(config.decode())
    xnu = [entry for entry in expected['entry'] if entry['type'] == 'xnu']
    require(len(xnu) == 1 and 't970-runtime-report' not in xnu[0]['args'],
            'Expected one continuous XNU entry')
    line = ('args = "' + xnu[0]['args'] + '"').encode()
    require(config.count(line) == 1, 'Ambiguous XNU entry')
    xnu[0]['args'] += ' ' + ' '.join(arguments)
    updated = config.replace(line, ('args = "' + xnu[0]['args'] + '"').encode())
    require(tomllib.loads(updated.decode()) == expected, 'Unexpected boot configuration difference')
    config_path = output / CONFIG
    config_path.write_bytes(updated)

    replacement = output / 'kernel.macho'
    shutil.copyfile(build / 'kernel.macho', replacement)
    kernel = replacement.read_bytes()
    require(b'blank/dark=' in kernel, 'Missing linked frame counters')
    if args.pm_watchdog:
        require(b'T970 PM timeout state=' in kernel, 'Missing linked PM watchdog details')
    if touch:
        require(marker in kernel, 'Missing linked touch report')
    env = dict(os.environ, UNIXNU_UEFI=str(DEVICE / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(TREE / 'scripts/patch-xnu-entry-probe.py'),
                    str(replacement), '--panic-screen', '--no-reset'], env=env, check=True)
    for name, path in ((CONFIG, config_path), (KERNEL, replacement)):
        subprocess.run(['mcopy', '-o', '-i', str(payload), str(path), PREFIX + name], check=True)
    require(payload.stat().st_size == payload_size, 'Payload size changed')
    boot = output / 'boot-partition.img'
    boot.write_bytes(source[:start] + payload.read_bytes() + source[end:])
    result = boot.read_bytes()
    require(result[:start] == source[:start] and result[end:] == source[end:],
            'Header, firmware, DTB or partition tail changed')
    payload.write_bytes(result[start:end])
    require(read_fat(CONFIG) == updated and read_fat(KERNEL) == replacement.read_bytes(),
            'Final BOOT config or kernel differs')
    unchanged = {name: sha for name, sha in baseline['unchanged_payload_sha256'].items()
                 if name not in (CONFIG, KERNEL)}
    if args.pm_watchdog:
        unchanged[KERNEL + '.adt'] = baseline['adt_sha256']
    for name, sha in unchanged.items():
        require(digest(read_fat(name)) == sha, 'Unexpected final BOOT input: ' + name)
    report = dict(base_boot_sha256=baseline['boot_sha256'], boot_sha256=digest(result),
                  boot_bytes=len(result), kernel_sha256=digest(kernel),
                  payload_kernel_sha256=digest(read_fat(KERNEL)), added_arguments=arguments,
                  unchanged_payload_sha256=unchanged, unchanged_header_firmware_dtb_tail=True,
                  terminal_runtime_report=True, uploaded=False)
    (output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
