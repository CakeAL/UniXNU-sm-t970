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
    parser.add_argument('--keys', action='store_true', help='Link the opt-in T970 PMIC key observer')
    parser.add_argument('--gpu-soc', type=Path, help='Pinned SM8250 checkout for the GPU power snapshot')
    parser.add_argument('--refresh-hid', action='store_true', help='Recompile the audited HID wrapper with the setup baseline')
    parser.add_argument('--gop-fork', action='store_true',
                        help='Link the audited GopFramebuffer fork object (scanout and source cache options)')
    variants = parser.add_mutually_exclusive_group()
    variants.add_argument('--touch-hid', action='store_true')
    variants.add_argument('--setup-probe', action='store_true')
    args = parser.parse_args()
    if args.refresh_hid and not (args.setup_probe or args.touch_hid):
        parser.error('--refresh-hid requires --setup-probe or --touch-hid')
    build = args.output.resolve()
    kernel = WORK / 'kernel/kernel.macho'
    if sha(kernel) != BASE_KERNEL_SHA or sha(LIVE / ARCHIVE) != BASE_ARCHIVE_SHA:
        raise ValueError('Expected the v55 kernel and display archive')
    archive_source = LIVE
    if args.setup_probe:
        archive_source = OUT / 'touch-hid-v76-build'
        v76 = json.loads((DEVICE / 'evidence/input/touch-hid-v76/preparation.json').read_text())
        if sha(archive_source / 'kernel.macho') != v76['kernel_sha256']:
            raise ValueError('Expected the device-tested v76 kernel')
        if sha(archive_source / 'touch-hid/TouchHid.late.o') != v76['build']['hid_object_sha256']:
            raise ValueError('Expected the device-tested v76 HID object')
    report = json.loads((archive_source / REPORT).read_text())
    if sha(archive_source / ARCHIVE) != report['archive_sha256']:
        raise ValueError('Source archive does not match its report')
    build.mkdir()
    registration = build / 'registration'
    gop_object = OUT / 'display-object-cf3b429/NativeLegacyDisplay.o'
    approved = DEVICE / 'evidence/display/abi21h461/object-check.json'
    if args.gop_fork:
        gop_object = OUT / 'display-object-fbcache/NativeLegacyDisplay.o'
        approved = DEVICE / 'evidence/display/gop-fb-cache/object-check.json'
    registration_command = ['python3.14', str(DEVICE / 'scripts/build-display-registration.py'),
                            '--tree', str(WORK / 'tree'),
                            '--gop-object', str(gop_object),
                            '--approved', str(approved),
                            '--output', str(registration)]
    if args.touch_hid or args.setup_probe:
        registration_command.append('--touch-hid')
    if args.gpu_soc:
        registration_command.extend(['--gpu-soc', str(args.gpu_soc)])
    subprocess.run(registration_command, check=True)
    replacement = registration / MEMBER
    source = DEVICE / 'package/T970Display/DisplayRegistration.cpp'
    report['source_sha256'][str(source)] = sha(source)
    report['registration_object_sha256'] = sha(replacement)
    replacements = {MEMBER: replacement}
    if args.gop_fork:
        late = build / 'NativeLegacyDisplay.late.o'
        subprocess.run(['/opt/homebrew/opt/llvm/bin/llvm-objcopy',
                        '--remove-section=__DATA,__mod_init_func',
                        '--globalize-symbol=__GLOBAL__sub_I_NativeLegacyDisplay.cpp',
                        str(gop_object), str(late)], check=True)
        replacements['NativeLegacyDisplay.late.o'] = late
        report['gop_object_sha256'] = sha(gop_object)
    if args.setup_probe:
        ui = build / 'ui-wait'
        subprocess.run(['python3.14', str(DEVICE / 'scripts/build-ui-wait-snapshot.py'),
                        '--tree', str(WORK / 'tree'), '--output', str(ui)], check=True)
        replacements['UiWaitSnapshot.o'] = ui / 'UiWaitSnapshot.o'
        sampler = json.loads((ui / 'report.json').read_text())
        report['source_sha256'][str(source.with_name('UiWaitSnapshot.c'))] = sampler['source_sha256']
        report['ui_wait'] = sampler

    archive = build / ARCHIVE
    shutil.copy2(archive_source / ARCHIVE, archive)
    members = ar('-t', archive).decode().splitlines()
    if any(members.count(member) != 1 for member in replacements):
        raise ValueError('Expected unique archive members to replace')
    ar('-r', archive, *(str(path) for path in replacements.values()))
    after = ar('-t', archive).decode().splitlines()
    if len(after) != len(members) or set(after) != set(members):
        raise ValueError('Archive layout changed')
    for member in members:
        if member.startswith('__.SYMDEF'):
            continue
        expected = (replacements[member].read_bytes() if member in replacements
                    else ar('-p', archive_source / ARCHIVE, member))
        if ar('-p', archive, member) != expected:
            raise ValueError('Unexpected archive change: ' + member)
    if args.touch_hid or args.setup_probe:
        hid = (archive_source if args.setup_probe and not args.refresh_hid else build) / 'touch-hid'
        hid_command = ['python3.14', str(DEVICE / 'scripts/build-touch-hid.py'),
                       '--registration', str(registration), '--output', str(hid)]
        if args.touch_hid or args.refresh_hid:
            subprocess.run(hid_command, check=True)
            ar('-r', archive, str(hid / 'TouchHid.late.o'), str(hid / 'touch-hid-bindings.o'))
        for path in (DEVICE / 'package/T970Touch').glob('*'):
            if path.suffix in ('.h', '.cpp'):
                report['source_sha256'][str(path)] = sha(path)
    report['archive_sha256'] = sha(archive)
    if args.keys:
        keys = build / 'keys'
        subprocess.run(['python3.14', str(DEVICE / 'scripts/build-key-probe.py'),
                        '--registration', str(registration), '--output', str(keys)], check=True)
        ar('-r', archive, str(keys / 'KeyProbe.o'))
        report['keys'] = json.loads((keys / 'report.json').read_text())
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
        if args.touch_hid or args.setup_probe:
            subprocess.run([*hid_command, '--verify', str(kernel)], check=True)
        for target in targets[2:]:
            shutil.copy2(target, build / target.name)
    finally:
        for target in targets:
            shutil.copy2(saved / target.name, target)
    print(sha(build / 'kernel.macho'))


if __name__ == '__main__':
    main()
