#!/usr/bin/env python3
"""Link the owner public anchor and the table filled by ShengUfs at boot."""
import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tree', type=Path, default=Path('.'))
parser.add_argument('--output', type=Path, default=Path('build/verified-root-empty'))
args = parser.parse_args()
ROOT = args.tree.resolve()
FW = next(p for p in (ROOT, *ROOT.parents) if (p / 'kits/VerifiedRoot').is_dir()
          and (p / 'build/verified-root-host/keys/owner-public.pem').is_file())
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
recipe = ROOT / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/bsd/DEVELOPMENT/bsd_init.o.json'
record = json.loads(recipe.read_text().strip().rstrip(','))
objects = []
for source in (FW / 'kits/VerifiedRoot/src/verified_root.c', FW / 'kits/VerifiedRoot/adapters/xnu_crypto.c'):
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
        elif arg not in ('-MD', '-MP'):
            command.append(arg)
        i += 1
    command += ['-I' + str(FW / 'kits/VerifiedRoot/include'), '-Werror', '-Wno-missing-include-dirs']
    result = subprocess.run(command, cwd=record['directory'], capture_output=True, text=True)
    (out / (source.stem + '.log')).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.stderr[-3000:])
    objects.append(obj)
# The policy table starts empty and is filled at boot from the signed envelopes on unixnu (see
# scripts/build-owner-root-manifests.py): 73,287,008 bytes of block hashes cannot fit the RECOVERY
# partition, so the kernel links only the owner public-key anchor and authenticates each envelope
# with vr_open. The table and its count therefore live in .data, not .text.
spec = importlib.util.spec_from_file_location('verified_manifest', FW / 'kits/VerifiedRoot/tools/manifest.py')
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
anchor = manifest.public_anchor(FW / 'build/verified-root-host/keys/owner-public.pem')
assert len(anchor) == 395, 'Unexpected owner key anchor length'
assembly = out / 'empty-policies.S'
assembly.write_text('.data\n.balign 8\n'
                    '.globl _verified_root_policies\n_verified_root_policies:\n  .space 64\n'
                    '.globl _verified_root_policy_count\n_verified_root_policy_count:\n  .quad 0\n'
                    '.globl _verified_root_key\n_verified_root_key:\n  .byte '
                    + ','.join(str(b) for b in anchor) + '\n'
                    # The virtio personality still references the single-manifest form; this board
                    # publishes through the UFS policy table instead, so the symbols stay empty and
                    # that path remains fail-closed.
                    '.data\n.balign 8\n'
                    '.globl _verified_root_manifest\n_verified_root_manifest:\n  .quad 0\n'
                    '.globl _verified_root_manifest_bytes\n_verified_root_manifest_bytes:\n  .quad 0\n'
                    '.text\n'
                    '.globl _native_verified_policy_count_set\n'
                    '_native_verified_policy_count_set:\n'
                    '  adrp x1, _verified_root_policy_count@PAGE\n'
                    '  add x1, x1, _verified_root_policy_count@PAGEOFF\n'
                    '  str x0, [x1]\n'
                    '  ret\n'
                    '.globl _native_verified_root_probe\n_native_verified_root_probe:\n  ret\n'
                    '.globl _native_verified_root_checkpoint\n_native_verified_root_checkpoint:\n  ret\n')
asm_obj = out / 'empty-policies.o'
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
subprocess.run(['xcrun', 'clang', '-target', 'arm64-apple-ios17.0', '-isysroot', sdk, '-c',
                assembly, '-o', asm_obj], check=True)
objects.append(asm_obj)
archive = out / 'libVerifiedRootProbe.a'
archive.unlink(missing_ok=True)
subprocess.run(['xcrun', 'ar', 'rcs', archive] + [str(o) for o in objects], check=True)
print('VerifiedRoot empty-policy archive:', archive)
