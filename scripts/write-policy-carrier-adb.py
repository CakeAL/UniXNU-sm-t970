#!/usr/bin/env python3
"""Write and verify the two owner policy envelopes in the userdata carrier region.

Uses the qualified recovery ADB channel: the files are pushed, written at their exact 4096-byte
LBA with dd conv=fsync, the block cache is dropped, and the whole range is read back and compared
by SHA-256. Nothing outside the two envelope ranges is written.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OS_LBA = 5505024
SYSTEMOS_LBA = 5516624
BLOCK = 4096


def sh(*args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def device_sha(serial, node, lba, blocks, length):
    with subprocess.Popen(['adb', '-s', serial, 'shell',
                           f'dd if={node} bs={BLOCK} skip={lba} count={blocks} 2>/dev/null'],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as pipeline:
        sha = hashlib.sha256()
        remaining = length
        while remaining > 0:
            chunk = pipeline.stdout.read(min(1 << 20, remaining))
            if not chunk:
                break
            sha.update(chunk)
            remaining -= len(chunk)
        if remaining:
            raise SystemExit('short device readback')
        if pipeline.wait():
            raise SystemExit('device readback failed')
    return sha.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--os', type=Path, default=Path('out/step7/owner-manifests/OS/manifest.bin'))
    parser.add_argument('--systemos', type=Path, default=Path('out/step7/owner-manifests/SystemOS/manifest.bin'))
    parser.add_argument('--node', default='/dev/block/sda36')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--write', action='store_true')
    options = parser.parse_args()
    if options.output.exists():
        raise SystemExit('Choose a new output directory')
    options.output.mkdir(parents=True)
    plans = [('OS', options.os, OS_LBA), ('SystemOS', options.systemos, SYSTEMOS_LBA)]
    report = {'serial': options.serial, 'node': options.node, 'write': options.write, 'envelopes': []}
    for name, path, lba in plans:
        blocks = (path.stat().st_size + BLOCK - 1) // BLOCK
        entry = {'name': name, 'lba': lba, 'blocks': blocks, 'bytes': path.stat().st_size,
                 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'remote': f'/tmp/unixnu-policy-{name}.bin'}
        if options.write:
            pushed = sh('adb', '-s', options.serial, 'push', str(path), entry['remote'])
            if pushed.returncode:
                raise SystemExit(pushed.stderr[-800:])
            wrote = sh('adb', '-s', options.serial, 'shell',
                       f'dd if={entry["remote"]} of={options.node} bs={BLOCK} seek={lba} '
                       f'count={blocks} conv=fsync 2>&1; sync; blockdev --flushbufs {options.node} || true')
            entry['write_output'] = wrote.stdout.strip()[-400:]
            if wrote.returncode:
                raise SystemExit(wrote.stderr[-800:])
        entry['readback_sha256'] = device_sha(options.serial, options.node, lba, blocks, entry['bytes'])
        entry['verified'] = entry['readback_sha256'] == entry['sha256']
        report['envelopes'].append(entry)
        if options.write:
            sh('adb', '-s', options.serial, 'shell', f'rm -f {entry["remote"]}')
    report['all_verified'] = all(e['verified'] for e in report['envelopes'])
    (options.output / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not report['all_verified']:
        sys.exit(1)


if __name__ == '__main__':
    main()
