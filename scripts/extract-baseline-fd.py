#!/usr/bin/env python3
"""Recover the exact tested CPU0/initrd FD from its preserved private boot image."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot', type=Path, default=ROOT / 'out/step7/probes/after-mmu-brk-control/boot.img')
    parser.add_argument('--output', type=Path, default=ROOT / 'out/step7/ufs-readonly-inputs/SILICIUM_UEFI.fd')
    args = parser.parse_args()
    report = json.loads((ROOT / 'evidence/bring-up/runtime/after-mmu-brk-control/boot.json').read_text())
    blob = args.boot.read_bytes()
    if hashlib.sha256(blob).hexdigest() != report['image_sha256']:
        parser.error('Boot image does not match the preserved tested baseline')
    kernel_size, page, version = (struct.unpack_from('<I', blob, offset)[0] for offset in (8, 36, 40))
    if blob[:8] != b'ANDROID!' or page != 4096 or version != 2 or page + kernel_size > len(blob):
        parser.error('Unexpected baseline Android v2 layout')
    firmware = blob[page + report['shim_bytes']:page + kernel_size]
    if len(firmware) != 0x300000 or hashlib.sha256(firmware).hexdigest() != report['fd_sha256']:
        parser.error('Firmware does not match the pinned baseline')
    if subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-q', str(args.output.resolve())]).returncode:
        parser.error('Firmware output must remain in ignored storage')
    if args.output.exists() and args.output.read_bytes() != firmware:
        parser.error('Refusing to replace an unrelated firmware output')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(firmware)
    source = {'source_boot_sha256': report['image_sha256'],
              'source_boot_revision': 'fc4828781445ebab36819d6cdad8a2eddde82435',
              'fd_sha256': report['fd_sha256'], 'fd_bytes': len(firmware),
              'kernel_page_offset': page, 'shim_bytes': report['shim_bytes'],
              'note': 'Exact tested CPU0/initrd FD; no UfsDxe dispatch or later PlatformUfsLib SCM/PHY experiment.'}
    (args.output.parent / 'firmware-source.json').write_text(json.dumps(source, indent=2) + '\n')
    print('Verified baseline FD:', source['fd_sha256'])


if __name__ == '__main__':
    main()
