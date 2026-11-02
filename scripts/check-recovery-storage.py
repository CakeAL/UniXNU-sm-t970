#!/usr/bin/env python3
"""Read-only SM-T970 root ADB storage readiness check. Never writes a device."""
import argparse
import json
import shlex
import subprocess
from pathlib import Path

EXPECTED_BYTES = 243668070400


def validate(model, identity, target, size, logical, mounts, device_mm, product=''):
    reasons = []
    stock_identity = model.strip().upper() == 'SM-T970'
    twrp_identity = (model.strip() == 'SAMSUNG_gts7xlwifi' and
                     product.strip() == 'gts7xlwifi')
    if not (stock_identity or twrp_identity):
        reasons.append('Require SM-T970 or exact gts7xlwifi TWRP model/product pair')
    if 'uid=0(' not in identity:
        reasons.append('A root shell is required')
    if target.strip() != '/dev/block/sda36':
        reasons.append('userdata does not resolve to captured sda36')
    if size.strip() != str(EXPECTED_BYTES):
        reasons.append('Partition size differs from captured GPT')
    if logical.strip() != '4096':
        reasons.append('Logical block size differs from captured target')
    # Fail on mounts using either the canonical block path or common aliases.
    # major:minor also catches aliases absent from the mount source spelling.
    if not device_mm.strip() or not all(part.isdigit() for part in device_mm.strip().split(':')) or device_mm.count(':') != 1:
        reasons.append('Invalid runtime userdata major:minor')
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) >= 5 and (fields[2] == device_mm.strip() or fields[4] in ('/data', '/metadata')):
            reasons.append('Data or metadata is mounted; use a quiescent recovery')
            break
        if any(name in line for name in ('/dev/block/sda36', '/dev/block/by-name/userdata', '/dev/block/bootdevice/by-name/userdata')):
            reasons.append('userdata appears in mount information')
            break
    return reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--su', action='store_true', help='Use the existing Android su instead of direct recovery root')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    def read(command):
        remote = 'su -c ' + shlex.quote(command) if args.su else command
        result = subprocess.run(['adb', '-s', args.serial, 'shell', '-T', remote],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'ADB read failed')
        return result.stdout.strip()

    state = subprocess.run(['adb', '-s', args.serial, 'get-state'], capture_output=True, text=True, timeout=10)
    if state.returncode or state.stdout.strip() not in ('device', 'recovery'):
        raise SystemExit('Selected ADB device is not available with a shell')
    values = dict(model=read('getprop ro.product.model'), product=read('getprop ro.product.device'), identity=read('id'),
                  target=read('readlink -f /dev/block/by-name/userdata'),
                  size=read('blockdev --getsize64 /dev/block/by-name/userdata'),
                  logical=read('blockdev --getss /dev/block/by-name/userdata'),
                  mounts=read('cat /proc/self/mountinfo'),
                  device_mm=read('cat /sys/class/block/sda36/dev'))
    reasons = validate(**values)
    report = dict(scope='Read-only environment check; not authorization to write',
                  ready=not reasons, reasons=reasons, observations=values, device_written=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: root ADB identity, partition geometry and quiescent mounts' if not reasons else '\n'.join(reasons))
    raise SystemExit(bool(reasons))


if __name__ == '__main__':
    main()
