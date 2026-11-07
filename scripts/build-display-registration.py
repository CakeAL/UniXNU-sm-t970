#!/usr/bin/env python3
"""Compile T970 board callbacks and audit the actual GOP object imports. No linking/flashing."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

DEVICE = Path(__file__).resolve().parents[1]
SMMU_REVISION = '8bb168ad058c28d5c04f179ba407875eacba7ef3'
SMMU_UNITS = ('ArmSmmu4K', 'ArmSmmu4KContext', 'ArmSmmu4KProgram',
              'ArmSmmu4KAudit', 'ArmSmmu4KTableMemory', 'ArmSmmu4KMmio')
FIRMWARE_REVISION = '20ad3d7aca14bd46aecab6335c780f5413fa054b'
FIRMWARE_UNITS = ('AdrenoFirmware', 'A650GmuRegions')
GMU_SHA256 = 'df79fa8482fcc7587bb239b9c9e2b24bce4729893b990fe3f82b30da8175b01c'


def stage_units(kit, repository, revision, units, prefix=''):
    for unit in units:
        for extension in ('.h', '.c'):
            name = unit + extension
            (kit / name).write_bytes(subprocess.check_output(
                ['git', '-C', str(repository), 'show', f'{revision}:{prefix}{name}']))


def compile_units(compiler, kit, units, log):
    commands = []
    for unit in units:
        command = [compiler, '--target=arm64-apple-ios17.0.0', '-mkernel',
                   '-ffreestanding', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-c', str(kit / (unit + '.c')), '-o', str(kit / (unit + '.o'))]
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        commands.append(command)
    (kit / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, required=True)
    p.add_argument('--gop-object', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--touch-hid', action='store_true')
    p.add_argument('--gpu-soc', type=Path, help='Pinned SM8250 checkout for the GPU power snapshot')
    p.add_argument('--arm-smmu4k', type=Path, help='ArmSmmu4K Git repository for the GMU table probe')
    p.add_argument('--gmu-firmware', type=Path, help='a650_gmu.bin matching the T970 firmware inventory')
    p.add_argument('--approved', type=Path,
                   default=DEVICE / 'evidence/display/abi21h461/object-check.json')
    a = p.parse_args()
    if a.arm_smmu4k and not a.gpu_soc:
        p.error('--arm-smmu4k requires --gpu-soc')
    if a.gmu_firmware and not a.arm_smmu4k:
        p.error('--gmu-firmware requires --arm-smmu4k')
    if a.gmu_firmware:
        firmware = a.gmu_firmware.read_bytes()
        if len(firmware) != 41548 or hashlib.sha256(firmware).hexdigest() != GMU_SHA256:
            raise ValueError('a650_gmu.bin does not match the stock T970 firmware pin')
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
    with (out / 'compile.log').open('w') as log:
        if a.arm_smmu4k:
            smmu_kit = out / 'ArmSmmu4K'
            smmu_kit.mkdir()
            stage_units(smmu_kit, a.arm_smmu4k, SMMU_REVISION, SMMU_UNITS)
            compile_units(command[0], smmu_kit, SMMU_UNITS, log)
            command.extend(['-DT970_GPU_GMU_TABLES=1', '-I', str(smmu_kit)])
        if a.gmu_firmware:
            fw_kit = out / 'AdrenoFirmware'
            fw_kit.mkdir()
            stage_units(fw_kit, DEVICE.parent / 'UniXNU/kits/AdrenoFirmware',
                        FIRMWARE_REVISION, ('AdrenoFirmware',))
            stage_units(fw_kit, a.gpu_soc, pin, ('A650GmuRegions',), 'kits/Sm8250Platform/')
            compile_units(command[0], fw_kit, FIRMWARE_UNITS, log)
            rows = ['    ' + ', '.join(f'0x{byte:02x}' for byte in firmware[i:i + 16]) + ','
                    for i in range(0, len(firmware), 16)]
            (fw_kit / 'T970A650Firmware.h').write_text(
                'static const uint8_t t970GmuFirmware[] = {\n' + '\n'.join(rows) + '\n};\n')
            command.extend(['-DT970_GPU_GMU_FIRMWARE=1', '-I', str(fw_kit)])
        (out / 'command.json').write_text(json.dumps(command, indent=2)+'\n')
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
    if a.arm_smmu4k:
        report['arm_smmu4k'] = {
            'revision': SMMU_REVISION,
            'objects': {unit + '.o': sha(smmu_kit / (unit + '.o')) for unit in SMMU_UNITS},
            'probe_sha256': sha(DEVICE / 'package/T970Gpu/GmuTables.h'),
        }
    if a.gmu_firmware:
        report['adreno_firmware'] = {
            'revision': FIRMWARE_REVISION, 'sm8250_revision': pin, 'gmu_sha256': GMU_SHA256,
            'objects': {unit + '.o': sha(fw_kit / (unit + '.o')) for unit in FIRMWARE_UNITS},
            'probe_sha256': sha(DEVICE / 'package/T970Gpu/GmuFirmware.h'),
        }
    (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: board callbacks compiled; nine native_legacy original-family aliases remain')

if __name__ == '__main__':
    main()
