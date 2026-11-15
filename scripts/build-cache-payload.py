#!/usr/bin/env python3
"""Build a standalone payload FAT for a second volume (the CACHE partition).

  build-cache-payload.py --kernel FILE --data-ramdisk FILE --owner-trust-cache FILE
      [--size-mib N] [--kernel-arg NAME[=VALUE]]... [--drop-kernel-arg PREFIX]...
      --output DIR

The payload inside the Recovery image is a FAT whose content limit is
0.95 * board.toml [payload] size_mib, and Recovery is 82.9 MiB, so an addon that
grows past ~14 MiB no longer fits next to the kernel and the Data seed. This
script builds the same payload with a larger FAT and leaves it as a standalone
file to be written to CACHE (400 MiB, unused by iPadOS): the firmware's ramdisk
volume then carries no unixnu.toml, and UniXNULib falls back to the first
volume that has one, which is this payload.

Nothing here touches a device or the Recovery wrapper; the caller flashes the
result explicitly.
"""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--kernel', required=True, type=Path,
                        help='prelinked kernel Mach-O for the payload')
    parser.add_argument('--data-ramdisk', type=Path,
                        help='preserved Data seed (default: the board build output)')
    parser.add_argument('--owner-trust-cache', type=Path,
                        help='owner trust bundle that replaces the board trust cache')
    parser.add_argument('--size-mib', type=int, default=96,
                        help='FAT size in MiB; stays below the 400 MiB cache partition')
    parser.add_argument('--kernel-arg', action='append', default=[],
                        help='extra kernel argument (repeatable)')
    parser.add_argument('--drop-kernel-arg', action='append', default=[],
                        help='drop board arguments with this prefix (repeatable)')
    parser.add_argument('--unixnu', type=Path, default=Path('/Users/cakeal/vsc/UniXNU'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()

    device = Path(subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', '--show-toplevel'], text=True).strip())
    sys.path.insert(0, str(args.unixnu / 'scripts'))
    from unixnu.cli import parser as cli_parser
    from unixnu.config import Context
    from unixnu import feeds, tree, payload

    kernel = args.kernel.resolve()
    if not kernel.is_file():
        parser.error(f'kernel not found: {kernel}')
    if not (24 <= args.size_mib <= 380):
        parser.error('--size-mib must be 24..380 MiB (the cache partition is 400 MiB)')

    command = ['build', 'payload', '-D', str(device)]
    if args.data_ramdisk:
        command += ['--data-ramdisk', str(args.data_ramdisk.resolve())]
    if args.owner_trust_cache:
        command += ['--owner-trust-cache', str(args.owner_trust_cache.resolve())]
    ctx = Context(cli_parser().parse_args(command))
    ctx.args.kernel_arg = list(args.kernel_arg)
    ctx.uefi = ctx.option('uefi', 'UNIXNU_UEFI')
    dtb = ctx.option('dtb', 'UNIXNU_DTB')
    if ctx.uefi is None or dtb is None:
        parser.error('Set the dedicated uefi and firmware dtb in unixnu.local.toml')

    board_hash = sha(device / 'board.toml')
    kernel_hash = sha(kernel)
    tree.assemble(ctx, feeds.resolve(ctx))
    ctx.board = copy.deepcopy(ctx.board)
    spec = ctx.board['payload']
    for key in list(spec):
        if key.startswith('entry_probe_reset_'):
            del spec[key]
    dropped = []
    for prefix in args.drop_kernel_arg:
        for word in [w for w in spec['kernel_args'] if w.startswith(prefix)]:
            dropped.append(word)
            spec['kernel_args'].remove(word)
    spec['size_mib'] = args.size_mib
    if dropped:
        print('dropped board arguments:', ' '.join(dropped))

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ctx.work = output
    ctx.logs = output / 'logs'
    ctx.logs.mkdir(parents=True, exist_ok=True)
    image = payload.build(ctx, kernel=kernel)
    if sha(device / 'board.toml') != board_hash or sha(kernel) != kernel_hash:
        raise ValueError('Source kernel or board defaults changed during the build')

    report_path = output / 'payload' / 'payload.json'
    report = json.loads(report_path.read_text())
    args_text = json.loads((output / 'payload' / 'payload.json').read_text())
    shipped = output / 'cache-payload.img'
    shipped.write_bytes(Path(image).read_bytes())
    sizes = json.loads((device / 'evidence/adb-2026-11-01/gpt.json').read_text())
    cache_size = [p['size_bytes'] for lun in sizes.values() for p in lun['partitions'] if p['name'] == 'cache']
    if len(cache_size) != 1 or shipped.stat().st_size > cache_size[0]:
        raise ValueError('payload does not fit the measured cache partition')
    summary = {
        'device_revision': subprocess.check_output(['git', '-C', str(device), 'rev-parse', 'HEAD'], text=True).strip(),
        'framework_revision': subprocess.check_output(['git', '-C', str(args.unixnu), 'rev-parse', 'HEAD'], text=True).strip(),
        'kernel_sha256': kernel_hash,
        'payload_sha256': sha(shipped),
        'payload_bytes': shipped.stat().st_size,
        'fat_size_mib': args.size_mib,
        'cache_partition_bytes': cache_size[0],
        'payload_report': str(report_path),
        'kernel_args': report.get('kernel_args') or args_text.get('kernel_args'),
        'owner_trust_cache_sha256': report.get('owner_trust_cache_sha256'),
        'data_ramdisk_sha256': report.get('data_ramdisk_sha256'),
    }
    (output / 'cache-payload.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'{shipped} {summary["payload_bytes"]} bytes SHA-256 {summary["payload_sha256"]}')


if __name__ == '__main__':
    main()
