#!/usr/bin/env python3
"""Relink the qualified v55 kernel with the board's new display counters."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

DEVICE = Path(__file__).resolve().parents[3]
OUT = DEVICE / 'out/data-bringup'
WORK = OUT / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data'
LIVE = WORK / 'tree/build/native-legacy-display'
BUILD = OUT / 'hello-black-v64-build'
ARCHIVE = 'libNativeLegacyDisplay.late.a'
REPORT = 'build-report.json'
MEMBER = 'DisplayRegistration.o'
BASE_KERNEL_SHA = '136e024bdc12b6c8b120ed40e7993fe21ac257b666767481a94d38b39099bd64'
BASE_ARCHIVE_SHA = 'af327ff1b15c902159616f47fabaa53c9a8aa16e8dfc831b59ff61d5a9dddbcd'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ar(option, archive, *args):
    return subprocess.check_output(['xcrun', 'ar', option, str(archive), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BUILD)
    parser.add_argument('--cached-headers', action='store_true')
    parser.add_argument('--touch-hid', action='store_true')
    args = parser.parse_args()
    build = args.output.resolve()
    kernel = WORK / 'kernel/kernel.macho'
    if sha(kernel) != BASE_KERNEL_SHA or sha(LIVE / ARCHIVE) != BASE_ARCHIVE_SHA:
        raise ValueError('Expected the v55 kernel and display archive')
    build.mkdir()
    registration = build / 'registration'
    registration_command = ['python3.14', str(DEVICE / 'scripts/build-display-registration.py'),
                            '--tree', str(WORK / 'tree'),
                            '--gop-object', str(OUT / 'display-object-cf3b429/NativeLegacyDisplay.o'),
                            '--output', str(registration)]
    if args.touch_hid:
        registration_command.append('--touch-hid')
    subprocess.run(registration_command, check=True)
    replacement = registration / MEMBER
    report = json.loads((LIVE / REPORT).read_text())
    source = DEVICE / 'package/T970Display/DisplayRegistration.cpp'
    report['source_sha256'][str(source)] = sha(source)
    report['registration_object_sha256'] = sha(replacement)

    archive = build / ARCHIVE
    shutil.copy2(LIVE / ARCHIVE, archive)
    members = ar('-t', archive).decode().splitlines()
    if members.count(MEMBER) != 1:
        raise ValueError('Expected one board registration archive member')
    ar('-r', archive, str(replacement))
    if members != ar('-t', archive).decode().splitlines():
        raise ValueError('Archive layout changed')
    for member in members:
        if member.startswith('__.SYMDEF'):
            continue
        expected = replacement.read_bytes() if member == MEMBER else ar('-p', LIVE / ARCHIVE, member)
        if ar('-p', archive, member) != expected:
            raise ValueError('Unexpected archive change: ' + member)
    if args.touch_hid:
        hid = build / 'touch-hid'
        hid_command = ['python3.14', str(DEVICE / 'scripts/build-touch-hid.py'),
                       '--registration', str(registration), '--output', str(hid)]
        subprocess.run(hid_command, check=True)
        ar('-r', archive, str(hid / 'TouchHid.late.o'), str(hid / 'touch-hid-bindings.o'))
        for path in (DEVICE / 'package/T970Touch').glob('*'):
            if path.suffix in ('.h', '.cpp'):
                report['source_sha256'][str(path)] = sha(path)
    report['archive_sha256'] = sha(archive)
    (build / REPORT).write_text(json.dumps(report, indent=2) + '\n')

    saved = build / 'baseline'
    saved.mkdir()
    targets = (LIVE / ARCHIVE, LIVE / REPORT, kernel, kernel.with_suffix('.json'))
    for target in targets:
        shutil.copy2(target, saved / target.name)
    env = dict(os.environ)
    env['PATH'] = str(DEVICE / '.cache/bin') + ':/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:' + env['PATH']
    launcher = DEVICE.parent / 'UniXNU/unixnu'
    if args.cached_headers:
        launcher = DEVICE / '.cache/run-kernel-with-cached-headers.py'
    command = ['python3.14', str(launcher), 'build', 'kernel',
               '-D', '.', '--out', str(OUT), '--local-module', 'driver:ArmCpu=' + str(DEVICE / '.cache/armcpu-sgi-asm')]
    try:
        for name in (ARCHIVE, REPORT):
            shutil.copy2(build / name, LIVE / name)
        with (build / 'kernel.log').open('w') as log:
            subprocess.run(command, cwd=DEVICE, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        if b'blank/dark=' not in kernel.read_bytes():
            raise ValueError('Display counters absent from prelinked kernel')
        if args.touch_hid:
            subprocess.run([*hid_command, '--verify', str(kernel)], check=True)
        for target in targets[2:]:
            shutil.copy2(target, build / target.name)
    finally:
        for target in targets:
            shutil.copy2(saved / target.name, target)
    print(sha(build / 'kernel.macho'))


if __name__ == '__main__':
    main()
