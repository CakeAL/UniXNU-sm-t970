#!/usr/bin/env python3
"""Compile the board-local ShengUfs copy against the current kernel ABI.

The copy in package/ShengUfs carries T970's SMMU register offsets; it replaces
the alioth component archive for this board.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'build/xnu').is_dir():
    FW = ROOT.parent / 'UniXNU'
    ROOT = sorted(FW.glob('out/*/*/*/tree'))[-1]
out = ROOT / 'build/sheng-ufs'
out.mkdir(parents=True, exist_ok=True)
package = ROOT / 'kits/sm-t970/ShengUfs'
recipe = ROOT / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json'
record = json.loads(recipe.read_text().strip().rstrip(','))
objects = []
for source in (package / 'NativeUfs.cpp', package / 'NativeUfsBsdRootCore.cpp'):
    obj = out / (source.stem + '.local.o')
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
    command += ['-I', str(package), '-I', str(ROOT / 'build/storage-abi/include'),
                '-I', str(ROOT / 'kits/VerifiedRoot/include'), '-I', str(ROOT / 'drivers/VirtioMmioBlock'), '-DNATIVE_VERIFIED_BLOCK=1', '-Wno-error']
    result = subprocess.run(command, cwd=record['directory'], capture_output=True, text=True)
    (out / (source.stem + '.local.log')).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.stderr[-4000:])
    objects.append(obj)
archive = out / 'libShengUfs.a'
archive.unlink(missing_ok=True)
subprocess.run(['xcrun', 'ar', 'rcs', archive] + [str(o) for o in objects], check=True)
print('ShengUfs local archive:', archive)
