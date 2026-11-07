#!/usr/bin/env python3
"""Compile T970 board callbacks and audit the actual GOP object imports. No linking/flashing."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

DEVICE = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, required=True)
    p.add_argument('--gop-object', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--touch-hid', action='store_true')
    p.add_argument('--gpu-soc', type=Path, help='Pinned SM8250 checkout for the GPU power snapshot')
    p.add_argument('--approved', type=Path,
                   default=DEVICE / 'evidence/display/abi21h461/object-check.json')
    a = p.parse_args()
    approved = json.loads(a.approved.read_text())
    if hashlib.sha256(a.gop_object.read_bytes()).hexdigest() != approved['object_sha256']:
        raise ValueError('Use the previously audited cf3b429 GOP object')
    if a.gpu_soc:
        pin = tomllib.loads((DEVICE / 'unixnu.lock').read_text())['source']['sm8250']['commit']
        gpu_kit = a.gpu_soc.resolve() / 'kits/Sm8250Platform'
        gpu_header = gpu_kit / 'A650GmuPower.h'
        pinned_header = subprocess.check_output(
            ['git', '-C', str(a.gpu_soc), 'show', f'{pin}:kits/Sm8250Platform/A650GmuPower.h'])
        if gpu_header.read_bytes() != pinned_header:
            raise ValueError('SM8250 GPU power header differs from the device lock')
    tree, out = a.tree.resolve(), a.output.resolve()
    if out.exists():
        raise ValueError('Preserve previous outputs')
    out.mkdir(parents=True)
    source = DEVICE / 'package/T970Display/DisplayRegistration.cpp'
    recipe = tree / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json'
    r = json.loads(recipe.read_text().strip().rstrip(','))
    command, i = [], 0
    arguments = r['arguments']
    obj = out / 'DisplayRegistration.o'
    while i < len(arguments):
        v = arguments[i]
        if v == r['file']:
            command.append(str(source))
        elif v == '-o':
            command.extend(['-o', str(obj)])
            i += 1
        elif v in ('-MF', '-MJ'):
            i += 1
        elif v == '-Xclang' and arguments[i+1].startswith('-W'):
            i += 1
        elif v not in ('-MD', '-MP') and not v.startswith('-W'):
            command.append(v)
        i += 1
    command.extend(['-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-Wno-c99-designator', '-Wno-reorder-init-list',
                    '-Wno-deprecated-enum-enum-conversion',
                    '-Wno-unnecessary-virtual-specifier', '-Wno-missing-include-dirs',
                    '-I', str(tree / '.cache/xnu-work/osfmk')])
    if a.touch_hid:
        command.append('-DT970_TOUCH_HID=1')
    if a.gpu_soc:
        command.extend(['-DT970_GPU_POWER_SNAPSHOT=1', '-I', str(gpu_kit)])
    (out / 'command.json').write_text(json.dumps(command, indent=2)+'\n')
    with (out / 'compile.log').open('w') as log:
        subprocess.run(command, cwd=r['directory'], stdout=log, stderr=subprocess.STDOUT, check=True)
    undefined = set(subprocess.check_output(['xcrun', 'nm', '-u', str(a.gop_object)], text=True).split())
    defined = {line.split()[-1] for line in subprocess.check_output(
        ['xcrun', 'nm', '-gU', str(obj)], text=True).splitlines() if line.split()}
    hooks = {s for s in undefined if s.startswith('_native_legacy_')}
    aliases = {'_native_legacy_surface_'+s for s in ('allocation','descriptor','format','height','planes','stride','width')}
    aliases |= {'_native_legacy_vsync_notify', '_native_legacy_set_refresh_properties'}
    missing = hooks - defined
    if missing != aliases:
        raise ValueError('Unexpected unresolved board callbacks: '+str(sorted(missing)))
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(source_sha256=sha(source), geometry_header_sha256=sha(source.with_name('T970GopGeometry.h')),
                  compile_recipe_sha256=sha(recipe), object_sha256=sha(obj),
                  gop_object_sha256=sha(a.gop_object), board_callbacks_resolved=sorted(hooks & defined),
                  pending_original_aliases=sorted(missing), compiled=True, linked=False,
                  runtime_display_verified=False)
    if a.gpu_soc:
        report['gpu_soc_revision'] = pin
        report['gpu_soc_header_sha256'] = sha(gpu_header)
    (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: board callbacks compiled; nine native_legacy original-family aliases remain')

if __name__ == '__main__':
    main()
