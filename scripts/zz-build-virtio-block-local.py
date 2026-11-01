#!/usr/bin/env python3
"""Compile the framework VirtioMmioBlock driver with the verified-block symbols.

The board needs native_verified_block_root_authorized for the owner root trust
switch, and that symbol only exists when the driver is compiled with
NATIVE_VERIFIED_BLOCK. The packaged component build omits the define, so the
archive is produced here instead.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'build/xnu').is_dir():
    FW = ROOT.parent / 'UniXNU'
    ROOT = sorted(FW.glob('out/*/*/*/tree'))[-1]
else:
    FW = ROOT.parent / 'UniXNU'
    if not (FW / 'kits/VerifiedRoot').is_dir():
        FW = next(p for p in ROOT.parents if (p / 'kits/VerifiedRoot').is_dir())
out = ROOT / 'build/virtio-block-local'
out.mkdir(parents=True, exist_ok=True)
for stale in out.glob('*.o'):
    stale.unlink()
package = ROOT / 'drivers/VirtioMmioBlock'
identifier = 'VirtioMmioBlock'
recipe = ROOT / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json'
record = json.loads(recipe.read_text().strip().rstrip(','))
objects = []
for source in (package / 'NativeVirtioBlock.cpp',):
    obj = out / (source.stem + '.o')
    command, i = [], 0
    arguments = record['arguments']
    while i < len(arguments):
        arg = arguments[i]
        if arg == record['file']:
            command.append(str(source))
        elif arg == '-o':
            command += ['-o', str(obj)]
            i += 1
        elif arg == '-Xclang' and arguments[i + 1].startswith('-W'):
            i += 1
        elif arg in ('-MF', '-MJ'):
            i += 1
        elif arg not in ('-MD', '-MP') and not arg.startswith('-Werror'):
            command.append(arg)
        i += 1
    command += ['-I', str(ROOT / 'build/storage-abi/include'), '-I', str(FW / 'kits/VerifiedRoot/include'),
                '-DNATIVE_VERIFIED_BLOCK=1', '-Wno-error']
    result = subprocess.run(command, cwd=record['directory'], capture_output=True, text=True)
    (out / (source.stem + '.local.log')).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.stderr[-4000:])
    objects.append(obj)
archive = out / ('lib' + identifier + '.a')
archive.unlink(missing_ok=True)
subprocess.run(['xcrun', 'ar', 'rcs', archive] + [str(o) for o in objects], check=True)
print('VirtioMmioBlock local archive:', archive)
