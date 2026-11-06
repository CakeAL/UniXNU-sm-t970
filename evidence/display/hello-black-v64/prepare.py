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
    modes.add_argument('--touch-hid', action='store_true', help='Enable continuous touchscreen HID delivery')
    modes.add_argument('--setup-probe', action='store_true', help='Sample the language transition with v76 HID')
    modes.add_argument('--setup-copy-diff', action='store_true', help='Enable differential copies on the exact v77 kernel')
    modes.add_argument('--setup-lifecycle', action='store_true', help='Capture Setup lifecycle and the LaunchServices owner')
    modes.add_argument('--setup-exit', action='store_true', help='Report the reason behind early UI process termination')
    modes.add_argument('--setup-relaunch', action='store_true', help='Allow the 21H461 language-change relaunch')
    modes.add_argument('--setup-transfer', action='store_true', help='Capture Setup on a three-finger hold')
    modes.add_argument('--setup-fb-cache', action='store_true', help='Map the scanout write-combined and the source cacheable')
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
        (args.touch_hid, 'touch-hid-v76', None, b'T970 touch: FTS scanning'),
    )
    touch = next((entry for entry in touch_modes if entry[0]), None)
    if touch:
        _, name, mode, marker = touch
        base = OUT / 'springboard-dim-continuous-v69/boot-partition.img'
        base_report = DEVICE / 'evidence/display/springboard-dim-continuous-v69/preparation.json'
        build = OUT / (name + '-build')
        output = OUT / name
        arguments = (['t970-touch-hid=1'] if args.touch_hid else
                     ['t970-runtime-report=75', f't970-touch-bus-report={mode}'])
    if args.setup_probe:
        base = OUT / 'touch-hid-v76/boot-partition.img'
        base_report = DEVICE / 'evidence/input/touch-hid-v76/preparation.json'
        build = OUT / 'setup-language-v77-build'
        output = OUT / 'setup-language-v77'
        arguments = ['t970-setup-probe=1', 't970-runtime-report=360']
    if args.setup_copy_diff or args.setup_lifecycle or args.setup_exit:
        base = OUT / 'setup-language-v77/boot-partition.img'
        base_report = DEVICE / 'evidence/display/setup-language-v77/preparation.json'
        if args.setup_copy_diff:
            output = OUT / 'setup-copy-diff-v78'
            arguments = ['sheng-fb-diff=1']
        elif args.setup_exit:
            build = OUT / 'setup-exit-v80-build'
            output = OUT / 'setup-exit-v80'
            arguments = ['t970-setup-life=1', 't970-ui-exit-reason=1']
        else:
            build = OUT / 'setup-lifecycle-v79-build'
            output = OUT / 'setup-lifecycle-v79'
            arguments = ['t970-setup-life=1']
    if args.setup_relaunch:
        base = OUT / 'setup-exit-v80/boot-partition.img'
        base_report = DEVICE / 'evidence/display/setup-exit-v80/preparation.json'
        build = OUT / 'setup-relaunch-v81-build'
        output = OUT / 'setup-relaunch-v81'
        arguments = ['t970-allow-sb-relaunch=1']
    if args.setup_transfer:
        base = OUT / 'setup-relaunch-v81/boot-partition.img'
        base_report = DEVICE / 'evidence/display/setup-relaunch-v81/preparation.json'
        build = OUT / 'setup-transfer-v82-build'
        output = OUT / 'setup-transfer-v82'
        arguments = ['t970-setup-report-touch=1']
    if args.setup_fb_cache:
        base = OUT / 'setup-transfer-v82/boot-partition.img'
        base_report = DEVICE / 'evidence/display/setup-transfer-v82/preparation.json'
        build = OUT / 'setup-fb-cache-v83-build'
        output = OUT / 'setup-fb-cache-v83'
        arguments = ['t970-fb-wc=1', 't970-fb-cached=1']
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
    if (args.setup_probe or args.setup_copy_diff or args.setup_lifecycle or
            args.setup_exit or args.setup_relaunch or args.setup_transfer or args.setup_fb_cache):
        config_sha = digest((base.parent / CONFIG).read_bytes())
    else:
        config_sha = baseline['unchanged_payload_sha256'][CONFIG] if args.pm_watchdog else baseline['config_sha256']
    require(digest(config) == config_sha, 'Unexpected source boot configuration')
    expected = tomllib.loads(config.decode())
    xnu = [entry for entry in expected['entry'] if entry['type'] == 'xnu']
    require(len(xnu) == 1, 'Expected one XNU entry')
    if args.setup_relaunch:
        boot_args = xnu[0]['args'].split()
        require(set(baseline['added_arguments']) <= set(boot_args) and
                boot_args.count('t970-runtime-report=360') == 1 and
                'panic_on_error_exit=backboardd,SpringBoard' in boot_args,
                'Expected the v80 timed exit diagnostic')
    elif args.setup_copy_diff or args.setup_lifecycle or args.setup_exit:
        boot_args = xnu[0]['args'].split()
        require(set(baseline['added_arguments']) <= set(boot_args) and
                not any(arg.startswith('sheng-fb-diff=') for arg in boot_args),
                'Expected the v77 Setup report with plain copies')
    else:
        require('t970-runtime-report' not in xnu[0]['args'], 'Expected continuous startup')
    if args.setup_transfer:
        require({'t970-allow-sb-relaunch=1', 't970-touch-hid=1', 't970-setup-life=1',
                 't970-ui-stack=10'} <= set(xnu[0]['args'].split()), 'Expected the v81 Setup baseline')
    if args.setup_fb_cache:
        require({'t970-allow-sb-relaunch=1', 't970-touch-hid=1', 't970-setup-life=1',
                 't970-ui-stack=10', 't970-setup-report-touch=1'} <= set(xnu[0]['args'].split()),
                'Expected the v82 transfer baseline')
    if args.setup_probe:
        require({'t970-touch-hid=1', 't970-ui-stack=10', 't970-ui-wait=1'} <= set(xnu[0]['args'].split()),
                'Expected v76 HID and compact UI sampler')
    line = ('args = "' + xnu[0]['args'] + '"').encode()
    require(config.count(line) == 1, 'Ambiguous XNU entry')
    if args.setup_relaunch:
        xnu[0]['args'] = xnu[0]['args'].replace(' t970-runtime-report=360', '')
    xnu[0]['args'] += ' ' + ' '.join(arguments)
    require(len(xnu[0]['args'].encode()) < 1024, 'Boot arguments exceed DarwinBoot capacity')
    updated = config.replace(line, ('args = "' + xnu[0]['args'] + '"').encode())
    require(tomllib.loads(updated.decode()) == expected, 'Unexpected boot configuration difference')
    config_path = output / CONFIG
    config_path.write_bytes(updated)

    replacement = output / 'kernel.macho'
    if args.setup_copy_diff:
        kernel = read_fat(KERNEL)
        require(digest(kernel) == baseline['payload_kernel_sha256'], 'Expected the exact packed v77 kernel')
        replacement.write_bytes(kernel)
        kernel_sha = baseline['kernel_sha256']
    else:
        shutil.copyfile(build / 'kernel.macho', replacement)
        kernel = replacement.read_bytes()
        kernel_sha = digest(kernel)
    require(b'blank/dark=' in kernel, 'Missing linked frame counters')
    if args.pm_watchdog:
        require(b'T970 PM timeout state=' in kernel, 'Missing linked PM watchdog details')
    if touch:
        require(marker in kernel, 'Missing linked touch report')
    if args.setup_probe:
        require(all(marker in kernel for marker in (b'Setup down ms=', b'Setup r0=', b'T970 touch: FTS scanning')),
                'Missing linked Setup or HID markers')
    if args.setup_lifecycle or args.setup_exit:
        require(all(marker in kernel for marker in (b'Setup life exec=', b' owner=%llx seen=%u',
                                                    b'Setup down ms=', b'T970 touch: FTS scanning')),
                'Missing linked Setup lifecycle, owner, display or HID markers')
    if args.setup_exit:
        require(b'T970 UI exit ' in kernel, 'Missing linked UI exit reason capture')
    if args.setup_relaunch:
        require(all(marker in kernel for marker in (b't970-allow-sb-relaunch', b'T970 UI exit ',
                                                    b'T970 touch: FTS scanning')),
                'Missing linked relaunch, exit reason or HID path')
    if args.setup_transfer:
        require(all(marker in kernel for marker in (b't970-setup-report-touch', b'Setup touch report scheduling',
                                                    b'accountsd', b'Setup life exec=')),
                'Missing linked manual Setup report or account sampler')
    if args.setup_fb_cache:
        require(all(marker in kernel for marker in (b't970-fb-wc', b't970-fb-cached', b'Setup touch report scheduling',
                                                    b'accountsd')),
                'Missing linked scanout or source cache options')
    files = [(CONFIG, config_path)]
    if not args.setup_copy_diff:
        env = dict(os.environ, UNIXNU_UEFI=str(DEVICE / '.cache/uefi-source/Mu-Silicium'))
        subprocess.run(['python3.14', str(TREE / 'scripts/patch-xnu-entry-probe.py'),
                        str(replacement), '--panic-screen', '--no-reset'], env=env, check=True)
        files.append((KERNEL, replacement))
    for name, path in files:
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
                  boot_bytes=len(result), kernel_sha256=kernel_sha,
                  payload_kernel_sha256=digest(read_fat(KERNEL)), added_arguments=arguments,
                  unchanged_payload_sha256=unchanged, unchanged_header_firmware_dtb_tail=True,
                  terminal_runtime_report=not (args.touch_hid or args.setup_relaunch or args.setup_transfer or
                                               args.setup_fb_cache),
                  uploaded=False)
    if args.setup_relaunch:
        report['removed_arguments'] = ['t970-runtime-report=360']
    if args.setup_transfer:
        report['manual_terminal_report'] = True
    if args.setup_fb_cache:
        report['manual_terminal_report'] = True
        report['framebuffer_cache_options'] = True
    (output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
