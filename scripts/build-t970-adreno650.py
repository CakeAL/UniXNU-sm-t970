#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Build the gts7xlwifi A650 driver and staged accelerator for iPadOS 21H461."""
import argparse
import hashlib
import json, os, re, shutil, subprocess, sys
from pathlib import Path

parser = argparse.ArgumentParser(description='Build the reference SM-T970 A650 kernel archive')
parser.add_argument('--tree', type=Path, required=True, help='prepared 21H461 XNU build tree')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--firmware', type=Path, required=True)
parser.add_argument('--metal-source', type=Path, required=True, help='AdrenoMetal component directory')
parser.add_argument('--addon', type=Path, help='locally built GPU userspace addon')
parser.add_argument('--host-check', action='store_true', help='compile with GMU/SQE only and stop before archive packaging')
args = parser.parse_args()
ROOT = args.tree.resolve()
c_recipe = json.loads((ROOT / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/bsd/DEVELOPMENT/bsd_init.o.json').read_text().strip().rstrip(','))
cxx_recipe = json.loads((ROOT / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json').read_text().strip().rstrip(','))
# scripts/build-xnu-4k-baseline.sh links CONFIG_XNU_NATIVE_ADRENO from
# build/adreno740/libAdreno740.a -- the A740 name is hard-coded there, not taken from
# CONFIG_XNU_NATIVE_ADRENO_ARCHIVE -- so the A650 archive is produced under that name.
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
DEVICE = Path(__file__).resolve().parents[1]
PACKAGE = DEVICE / 'package/T970Adreno650'
driver = PACKAGE / 'Adreno650'
def write_synced(path, text):
    """Write, flush and fsync a generated build input before anything reads it.

    On this shared mount a plain write is still in flight when the compiler opens the file,
    which shows up as clang's MemoryBuffer assertion rather than as a compile error."""
    with path.open('w') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())

KITS = PACKAGE
metal = args.metal_source.resolve()
if not (metal / 'OriginalAcceleratorABI.h').is_file():
    sys.exit('AdrenoMetal OriginalAcceleratorABI.h is missing')
sources = sorted(KITS.joinpath('ArmSmmu4K').glob('ArmSmmu4K*.c')) + [KITS / 'AdrenoPM4' / 'AdrenoPM4.c']
# The HFI kit and the A650 cold start that uses it.
sources += [KITS / 'AdrenoFirmware' / (name + '.c') for name in ('AdrenoFirmware', 'AdrenoHfi', 'AdrenoHfiStartup', 'AdrenoHfiVotes')]
sources += [KITS / 'pipa' / 'A650Gmu.c']
# The GPU half of NativeAdreno and the GMU's SMMU context. Left out: sheng's GMU platform nodes and service
# (NativeAdrenoService.cpp, NativeAdrenoGmuService/Platform/Config) and the accelerator.
sources += [driver / (name + '.cpp') for name in (
    'NativeAdrenoGpuContext', 'NativeAdrenoSmmuContext', 'NativeAdrenoSmmuMemory',
    'NativeAdrenoMemory', 'NativeAdrenoCpu', 'NativeAdrenoVm', 'NativeAdrenoRing', 'NativeAdrenoSubmit', 'NativeAdrenoTimer',
    'NativeAdrenoUserClient', 'NativeAdrenoPublish', 'NativeAdrenoCpInit', 'NativeAdrenoIrq', 'NativeAdrenoPreempt',
    'NativeAdrenoGmuContext', 'NativeAdrenoGmuMemory')]
# The board probe and its firmware: both are package files. The probe exports
# native_gpu_probe(), which the late display probe calls; the firmware object defines the
# three arrays it weak-imports.
firmware_source = args.firmware.resolve()
if not firmware_source.is_file():
    sys.exit(f'Generated firmware source is missing: {firmware_source}')
firmware_symbols = ('gmu', 'sqe') if args.host_check else ('gmu', 'sqe', 'zap')
firmware_text = firmware_source.read_text()
for image in firmware_symbols:
    if not re.search(rf'const uint32_t native_gpu_{image}_firmware_size = [1-9][0-9]*;', firmware_text):
        sys.exit(f'Generated firmware source is missing the {image} image')
sources += [PACKAGE / 'GpuProbe.cpp', firmware_source]
objects = []
for source in sources:
    recipe = c_recipe if source.suffix == '.c' else cxx_recipe
    obj = out / (source.stem + ('.kit.o' if source.suffix == '.c' else '.o'))
    command, i = [], 0
    while i < len(recipe['arguments']):
        value = recipe['arguments'][i]
        if value == recipe['file']:
            command.append(str(source))
        elif value == '-o':
            command += ['-o', str(obj)]
            i += 1
        elif value in ('-MF', '-MJ'):
            i += 1
        elif value == '-Xclang' and recipe['arguments'][i + 1].startswith('-W'):
            i += 1
        elif not value.startswith('-W') and value not in ('-MD', '-MP'):
            command.append(value)
        i += 1
    command += ['-I', str(ROOT / 'kits/AdrenoPM4'), '-I', str(ROOT / 'kits/ArmSmmu4K'), '-I', str(ROOT / 'kits/AdrenoFirmware'),
                '-I', str(KITS / 'pipa'), '-I', str(KITS / 'AdrenoFirmware'), '-I', str(KITS / 'AdrenoPM4'), '-I', str(KITS / 'ArmSmmu4K'), '-I', str(ROOT / '.cache/xnu-work/osfmk'),
                '-I', str(driver), '-I', str(PACKAGE), '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-Wno-incompatible-sysroot', '-Wno-c99-designator',
                # alioth_pcie.c leaves struct fields implicit on purpose (the ios-sweet tree
                # compiled it without -Werror); the kernel's record turns that into an error.
                '-Wno-missing-field-initializers',
                '-Wno-reorder-init-list', '-Wno-deprecated-enum-enum-conversion',
                '-Wno-unnecessary-virtual-specifier']
    # Mode 12: the staged AGXAccelerator registers the IOAcceleratorES service that the original
    # Metal discovery needs (IOAcceleratorES -> MetalPluginName -> NSBundle -> the plugin).
    if source.name == 'GpuProbe.cpp':
        command.append('-DPIPA_GPU_ACCELERATOR=1')
    result = subprocess.run(command, cwd=recipe['directory'], capture_output=True, text=True)
    if result.returncode:
        sys.exit(str(source) + ':\n' + result.stderr[-2500:])
    objects.append(obj)
# gts7xlwifi: the GPU addon embedded in the kernel (package/T970GpuAddon.S), when the device repository holds one.
ADDON = args.addon.resolve() if args.addon else None
if ADDON:
    addon_obj = out / 'T970GpuAddon.o'
    subprocess.run([c_recipe['arguments'][0], '-c', '--target=arm64-apple-ios17.0', '-DT970_GPU_ADDON="%s"' % ADDON,
                    '-o', str(addon_obj), str(PACKAGE / 'T970GpuAddon.S')], check=True)
    objects.append(addon_obj)
    print('PASS: GPU addon embedded (%d bytes)' % ADDON.stat().st_size)
archive = out / 'libAdreno740.a'

# Mode 12's staged accelerator, the job scripts/build-adreno740-accelerator.py does for the A740
# checkout. The class derives from the original IOAcceleratorES, which this kernel does not
# build, so its three base symbols are bound to the addresses the audited record names
# (scripts/data/ioaccelerator-base-abi.json), and its initializer registration is stripped from
# __mod_init_func so the board probe can run it after IOGPUFamily has loaded. build-xnu links
# only libAdreno740.a, so it rides in the same archive.
plan = json.loads((ROOT / 'scripts/data/ioaccelerator-base-abi.json').read_text())
bindings = {
    '__ZN15IOAcceleratorESC2EPK11OSMetaClass': int(plan['protected_compatible_constructor_aliases'][0], 16),
    '__ZN15IOAcceleratorESD2Ev': int(plan['nondeleting_destructor'], 16),
    '__ZN15IOAcceleratorES10gMetaClassE': int(plan['metaclass'], 16),
}
compiler = cxx_recipe['arguments'][0]
llvm_bin = Path(compiler).parent
accel_obj = out / 'NativeAdrenoAccelerator.o'
command, i = [], 0
while i < len(cxx_recipe['arguments']):
    value = cxx_recipe['arguments'][i]
    if value == cxx_recipe['file']:
        command.append(str(driver / 'NativeAdrenoAccelerator.cpp'))
    elif value == '-o':
        command += ['-o', str(accel_obj)]
        i += 1
    elif value in ('-MF', '-MJ'):
        i += 1
    elif value == '-Xclang' and cxx_recipe['arguments'][i + 1].startswith('-W'):
        i += 1
    elif not value.startswith('-W') and value not in ('-MD', '-MP'):
        command.append(value)
    i += 1
command += ['-I', str(ROOT / '.cache/xnu-work/osfmk'), '-I', str(metal), '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
            '-Wno-unnecessary-virtual-specifier', '-Wno-c99-designator', '-Wno-reorder-init-list',
            '-Wno-deprecated-enum-enum-conversion', '-Wno-overloaded-virtual']
result = subprocess.run(command, cwd=cxx_recipe['directory'], capture_output=True, text=True)
if result.returncode:
    sys.exit('NativeAdrenoAccelerator.cpp:\n' + result.stderr[-2500:])
asm = out / 'original-bindings.S'
write_synced(asm, ''.join('.globl %s\n.set %s, %#x\n' % (name, name, address) for name, address in sorted(bindings.items())))
bind_obj = out / 'original-bindings.o'
subprocess.run([compiler, '-c', '--target=arm64-apple-ios17.0', '-o', str(bind_obj), str(asm)], check=True)
late = out / 'NativeAdrenoAccelerator.late.o'


def tool(name):
    found = shutil.which(name) or str(llvm_bin / name)
    if not Path(found).exists():
        sys.exit('missing ' + name + ' (the accelerator needs the LLVM binutils)')
    return found


subprocess.run([tool('llvm-objcopy'), '--remove-section=__DATA,__mod_init_func',
                '--globalize-symbol=__GLOBAL__sub_I_NativeAdrenoAccelerator.cpp', str(accel_obj), str(late)], check=True)
if args.host_check:
    print(f'PASS: compiled {len(objects) + 2} A650/IOAcceleratorES objects. No deployment archive generated.')
    sys.exit(0)
subprocess.run([tool('llvm-ar'), 'rcs', str(archive), *objects, str(late), str(bind_obj)], check=True)
print('PASS: staged accelerator appended, IOAcceleratorES bound to %s'
      % ', '.join('%#x' % address for _, address in sorted(bindings.items())))

# Every NativeAdreno or kit symbol the objects use must be defined by them; the rest is the kernel's.
nm = subprocess.run([shutil.which('llvm-nm') or 'nm', '-gP', archive], capture_output=True, text=True, check=True).stdout.splitlines()
defined = {f.split()[0] for f in nm if len(f.split()) > 1 and f.split()[1] in 'TSDBC'}
undefined = {f.split()[0] for f in nm if len(f.split()) > 1 and f.split()[1] == 'U'}
missing = sorted(s for s in undefined - defined if re.search(r'NativeAdreno|native_adreno|ArmSmmu4K|AdrenoPM4|AdrenoHfi|AdrenoFirmware|A650Gmu|Sheng', s))
if missing:
    sys.exit('NativeAdreno symbols used but not built here: ' + ', '.join(missing))
required = ('_NativeAdrenoGpuContextBringup', '_NativeAdrenoGpuContextBuffers', '_NativeAdrenoGpuContextVm', '_native_adreno_publish',
            '_ArmSmmu4KAttachStreams', '_AdrenoPM4Type7', '_NativeAdrenoGmuContextBringupRoutes', '_NativeAdrenoGmuContextPayloads',
            '_A650GmuColdStart', '_A650GmuBuildStartup', '_native_adreno_accelerator_allocate')
absent = [s for s in required if s not in defined]
if absent:
    sys.exit('Required definitions absent: ' + ', '.join(absent))
print('PASS: archive verified with %d objects' % len(objects))
print('SHA-256:', hashlib.sha256(archive.read_bytes()).hexdigest())
