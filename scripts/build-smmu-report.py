#!/usr/bin/env python3
"""Prepare and independently check a bounded SMMU diagnostic BOOT; never flash."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tomllib


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    device = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unixnu', type=Path, default=device.parent / 'UniXNU')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['smmu', 'handoff', 'smr-id', 'fields'], default='smmu')
    parser.add_argument('--kernel-build', type=Path, default=device / 'out/step7/ufs-readonly-kernel-final.json')
    options = parser.parse_args()
    framework, output = options.unixnu.resolve(), options.output.resolve()
    require(not output.exists(), 'Choose a new output directory')
    require(subprocess.run(['git', '-C', str(device), 'check-ignore', str(output / 'boot.img')],
                           capture_output=True).returncode == 0, 'Output must be Git-ignored')
    kernel_build = json.loads(options.kernel_build.read_text())
    require(kernel_build.get('exit_code') == 0 and kernel_build.get('source_inputs_unchanged_during_build'),
            'Require a successful kernel build with stable source inputs')
    if options.mode in ['handoff', 'smr-id', 'fields']:
        for name in ['package/ShengUfs/GccUfs.h', 'package/ShengUfs/T970UfsHandoff.h',
                     'package/ShengUfs/T970SmmuReport.h', 'package/ShengUfs/NativeUfs.cpp']:
            require(name in kernel_build['source_inputs_sha256'], 'Missing diagnostic input hash: ' + name)
    if options.mode in ['smr-id', 'fields']:
        require('package/ShengUfs/T970SmrIdTest.h' in kernel_build['source_inputs_sha256'],
                'Missing bounded SMR test input hash')
    if options.mode == 'fields':
        require('package/ShengUfs/T970SmmuFields.h' in kernel_build['source_inputs_sha256'],
                'Missing field qualification input hash')
    for name, digest in kernel_build['source_inputs_sha256'].items():
        require(sha(device / name) == digest, 'Kernel input changed: ' + name)
    sys.path.insert(0, str(framework / 'scripts'))
    from unixnu.cli import parser as cli_parser
    from unixnu.config import Context
    from unixnu import feeds, tree, payload, bootimg
    ctx = Context(cli_parser().parse_args(['build', 'payload', '-D', str(device)]))
    ctx.uefi = ctx.option('uefi', 'UNIXNU_UEFI')
    dtb = Path(ctx.option('dtb', 'UNIXNU_DTB'))
    fd = device / 'out/step7/ufs-readonly-inputs/SILICIUM_UEFI.fd'
    require(sha(fd) == '515105d758a9d61078dffce5012db0754a71cec351a1bb34b30ee791196b5690',
            'Use the pinned pre-UFS-dispatch firmware')
    require(sha(dtb) == '86c14aa305a6cf5db46665f4095d28aadcb1ea5ce9d213cd711641a07504ed1d',
            'Firmware DTB changed')
    kernel = ctx.work / 'kernel/kernel.macho'
    require(sha(kernel) == kernel_build['kernel_sha256'], 'Kernel differs from final build')
    mode_arg = {'handoff': 't970-ufs-handoff=1', 'smmu': 't970-smmu-report=1',
                'smr-id': 't970-smr-id-test=1', 'fields': 't970-smmu-fields=1'}[options.mode]
    arguments = ['-v', 'cpus=1', 't970-novc', 'sheng-pmgr=2', mode_arg]
    spec = ctx.board['payload']
    require(spec['kernel_args'] == arguments and spec.get('panic_screen') is True and
            not any(key.startswith('entry_probe_reset_') for key in spec),
            'Diagnostic arguments or panic-screen policy changed')
    # Local defaults become CLI overrides in Context. This fixed diagnostic must
    # use exactly the reviewed board line, including its order and no additions.
    ctx.args.kernel_arg = []
    before = {path: sha(path) for path in (device / 'board.toml', kernel, fd, dtb)}
    tree.assemble(ctx, feeds.resolve(ctx))
    output.mkdir(parents=True)
    ctx.work, ctx.logs = output, output / 'logs'
    image = payload.build(ctx, kernel=kernel)
    boot = bootimg.build(ctx, ctx.uefi, fd, dtb, ramdisk=image, output=output / 'boot.img')
    independent = output / 'independent'
    independent.mkdir()
    env = dict(os.environ, MTOOLS_SKIP_CHECK='1')
    for source, name in [('::/EFI/UniXNU/Payloads/kernel.macho', 'kernel.macho'),
                         ('::/EFI/UniXNU/unixnu.toml', 'unixnu.toml')]:
        subprocess.run(['mcopy', '-i', str(image), source, str(independent / name)],
                       check=True, capture_output=True, env=env)
    config = tomllib.loads((independent / 'unixnu.toml').read_text())
    entries = [entry for entry in config['entry'] if entry['type'] == 'xnu']
    require(len(entries) == 1 and entries[0]['args'] == ' '.join(arguments),
            'Packed FAT command line differs from reviewed arguments')
    payload_report = json.loads((output / 'payload/payload.json').read_text())
    require(sha(independent / 'kernel.macho') == payload_report['payload_kernel_sha256'],
            'Packed FAT kernel differs from the reported patched copy')
    data = boot.read_bytes()
    require(data[:8] == b'ANDROID!' and struct.unpack_from('<I', data, 40)[0] == 2,
            'BOOT must use Android header v2')
    page = struct.unpack_from('<I', data, 36)[0]
    kernel_size = struct.unpack_from('<I', data, 8)[0]
    require(kernel_size == 112 + fd.stat().st_size and
            hashlib.sha256(data[page + 112:page + kernel_size]).hexdigest() == sha(fd),
            'Packed firmware differs from pinned FD')
    gpt = json.loads((device / 'evidence/adb-2026-11-01/gpt.json').read_text())
    sizes = [p['size_bytes'] for lun in gpt.values() for p in lun['partitions'] if p['name'] == 'boot']
    require(len(sizes) == 1 and len(data) <= sizes[0], 'Image exceeds measured BOOT capacity')
    require(all(sha(path) == digest for path, digest in before.items()), 'Source input changed during packing')
    report = {'device_revision': subprocess.check_output(['git', '-C', str(device), 'rev-parse', 'HEAD'], text=True).strip(),
              'framework_revision': subprocess.check_output(['git', '-C', str(framework), 'rev-parse', 'HEAD'], text=True).strip(),
              'command': shlex.join(['python3.14', 'scripts/build-smmu-report.py', *sys.argv[1:]]),
              'kernel_sha256': sha(kernel), 'payload_kernel_sha256': payload_report['payload_kernel_sha256'],
              'firmware_sha256': sha(fd), 'firmware_dtb_sha256': sha(dtb),
              'payload_sha256': sha(image), 'boot_sha256': sha(boot), 'boot_bytes': len(data),
              'boot_partition_bytes': sizes[0], 'kernel_args': arguments,
              'independent_fat_check': True, 'independent_fd_check': True,
              'mode': options.mode, 'hardware_tested': False, 'flash_performed': False}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
