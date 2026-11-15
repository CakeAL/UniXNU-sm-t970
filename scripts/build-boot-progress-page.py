#!/usr/bin/env python3
"""Build one isolated image that keeps the on-screen boot page bound.

Only the `boot-progress` argument differs from the board line: 2 binds the frame
buffer that the video console publishes and keeps drawing the stage rows, so the
panel shows the kernel's last stage and every console line before a stall. No
reset probe is added: the image stops where the kernel stops, which is the point.

No USB/device command is executed. Output stays in ignored storage.
"""
import argparse
import copy
import hashlib
import json
import importlib.util
import shlex
import struct
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack(device, base, payload_image, output, work):
    """Install the built FAT payload in the tested Recovery wrapper."""
    packer = device / 'scripts/pack-wholesale-recovery.py'
    spec = importlib.util.spec_from_file_location('pack_wholesale', packer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if sha(base) != module.BASE_SHA256:
        raise SystemExit('Expected the tested persistent Recovery wrapper')
    raw = base.read_bytes()
    shim_size, _, fat_size = struct.unpack_from('<III', raw, 8)
    fat_at = module.PAGE + module.align(shim_size)
    base_fat = work / 'base-fat.img'
    base_fat.write_bytes(raw[fat_at:fat_at + fat_size])
    # The persistent Data seed and the trust cache are inputs of the wrapper, not
    # of this build: keep them byte for byte so Data stays the same volume.
    seed = work / 'base-scratch-data.img'
    subprocess.run(['mcopy', '-i', str(base_fat), '::/EFI/UniXNU/Payloads/scratch-data.img', str(seed)], check=True)
    subprocess.run(['mcopy', '-o', '-i', str(payload_image), str(seed),
                    '::/EFI/UniXNU/Payloads/scratch-data.img'], check=True)
    subprocess.run([sys.executable, str(packer), '--base', str(base), '--payload', str(payload_image),
                    '--output', str(output)], check=True)
    return output


def main():
    device = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unixnu', type=Path, default=device.parent / 'UniXNU')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--out-root', type=Path,
                        help='framework output root kept inside this repository (default: the existing one)')
    parser.add_argument('--kernel', type=Path,
                        help='prelinked kernel Mach-O (default: <out-root>/sm-t970/kernel/kernel.macho)')
    parser.add_argument('--base', type=Path,
                        default=device / 'out/dual-system/data-persistence-20261111/recovery-persistent.img',
                        help='tested persistent Recovery wrapper carrying the firmware and the Data seed')
    parser.add_argument('--data-ramdisk', type=Path,
                        default=device / 'out/step7/data-seed-512/data-512.dbr',
                        help='persistent Data seed (the existing DBRDISK1 image)')
    parser.add_argument('--mode', type=int, default=2, choices=(1, 2, 3),
                        help='1 keeps the page until the system takes the panel; 2 keeps drawing')
    parser.add_argument('--kernel-arg', action='append', default=[],
                        help='extra diagnostic override added to the board arguments')
    parser.add_argument('--drop-kernel-arg', action='append', default=[],
                        help='board argument prefix removed for this image only')
    args = parser.parse_args()
    output = args.output.resolve()
    ignored = subprocess.run(['git', '-C', str(device), 'check-ignore', str(output / 'image.json')],
                             capture_output=True)
    if output.exists() or ignored.returncode:
        parser.error('Choose a new Git-ignored output directory')
    sys.path.insert(0, str(args.unixnu.resolve() / 'scripts'))
    from unixnu.cli import parser as cli_parser
    from unixnu.config import Context
    from unixnu import feeds, tree, payload
    command = ['build', 'payload', '-D', str(device)]
    if args.out_root:
        command += ['--out', str(args.out_root.resolve())]
    command += ['--data-ramdisk', str(args.data_ramdisk.resolve())]
    ctx = Context(cli_parser().parse_args(command))
    # The board line keeps every other argument; the page is a command-line
    # choice of the same BootProgress component, so nothing is rebuilt.
    ctx.args.kernel_arg = [f'boot-progress={args.mode}', *args.kernel_arg]
    ctx.uefi = ctx.option('uefi', 'UNIXNU_UEFI')
    dtb = ctx.option('dtb', 'UNIXNU_DTB')
    if ctx.uefi is None or dtb is None:
        parser.error('Set the dedicated uefi and firmware dtb in unixnu.local.toml')
    kernel = (args.kernel or ctx.work / 'kernel/kernel.macho').resolve()
    if not kernel.is_file():
        parser.error('Build the source kernel first')
    base = args.base.resolve()
    if not base.is_file():
        parser.error('Point --base at the tested persistent Recovery wrapper')
    board_hash = sha(device / 'board.toml')
    kernel_hash = sha(kernel)
    tree.assemble(ctx, feeds.resolve(ctx))
    ctx.board = copy.deepcopy(ctx.board)
    spec = ctx.board['payload']
    # No checkpoint: the page itself is the instrument.
    for key in list(spec):
        if key.startswith('entry_probe_reset_'):
            del spec[key]
    dropped = []
    for prefix in args.drop_kernel_arg:
        kept = [word for word in spec['kernel_args'] if not word.startswith(prefix)]
        dropped += [word for word in spec['kernel_args'] if word.startswith(prefix)]
        spec['kernel_args'] = kept
    if dropped:
        print('dropped board arguments:', ' '.join(dropped))
    output.mkdir(parents=True)
    ctx.work = output
    ctx.logs = output / 'logs'
    ctx.logs.mkdir(parents=True, exist_ok=True)
    image = payload.build(ctx, kernel=kernel)
    # The tested wrapper already carries the firmware, the shim, the device tree
    # and the persistent Data seed; only the FAT payload is replaced.
    boot = pack(device, base, image, output / 'boot.img', output)
    gpt = json.loads((device / 'evidence/adb-2026-11-01/gpt.json').read_text())
    sizes = [p['size_bytes'] for lun in gpt.values() for p in lun['partitions'] if p['name'] == 'recovery']
    if len(sizes) != 1 or boot.stat().st_size != sizes[0]:
        raise ValueError('Image does not match the measured Recovery partition')
    if sha(device / 'board.toml') != board_hash or sha(kernel) != kernel_hash:
        raise ValueError('Source kernel or board defaults changed during the build')
    report = {
        'device_revision': subprocess.check_output(['git', '-C', str(device), 'rev-parse', 'HEAD'],
                                                   text=True).strip(),
        'framework_revision': subprocess.check_output(['git', '-C', str(args.unixnu), 'rev-parse', 'HEAD'],
                                                      text=True).strip(),
        'instruments': {'boot_progress_mode': args.mode,
                        'stage_bars': True,
                        'panic_screen': bool(spec.get('panic_screen')),
                        'kernel_args_override': ctx.args.kernel_arg,
                        'kernel_args_dropped': dropped},
        'board_sha256': board_hash, 'source_kernel_sha256': kernel_hash,
        'base_recovery_sha256': sha(base), 'firmware_config_dtb_sha256': sha(dtb),
        'image_sha256': sha(boot), 'image_bytes': boot.stat().st_size,
        'recovery_partition_bytes': sizes[0], 'hardware_tested': False,
        'note': 'Enables the boot page only; no flash or reboot performed',
        'partition': 'RECOVERY',
        'build_command': shlex.join(['python3.14', 'scripts/build-boot-progress-page.py', *sys.argv[1:]]),
    }
    (output / 'image.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared boot page image:', output / 'boot.img')


if __name__ == '__main__':
    main()
