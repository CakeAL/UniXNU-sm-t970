#!/usr/bin/env python3
"""Write and verify the two owner policy envelopes in the userdata carrier region.

Uses the qualified recovery ADB channel: the files are pushed, written at their exact 4096-byte
LBA with dd conv=fsync, the block cache is dropped, and the whole range is read back and compared
by SHA-256. Nothing outside the two envelope ranges is written.
"""
import argparse
import contextlib
import struct
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OS_LBA = 5505024
SYSTEMOS_LBA = 5516624
BLOCK = 4096
ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IMAGES = {
    "OS": (6077580800, "e5634d04a8ac35f024845f583394e0a35deb26a04cb0c00286a8674e25a9a4f2"),
    "SystemOS": (3303014400, "b4908cde41d23e6bc05e6af51a2c9eeb00cf0f863a6a18b1600c96a3fd70414f"),
}
EXPECTED_KEY_HASH = "4d5cb682a66bc56f07a17ec4015d0da2a100cf065df05d5a278bcf5646df49f4"


def sh(*args, **kwargs):
    kwargs.setdefault("timeout", 120)
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def device_sha(serial, node, lba, blocks, length, backup=None):
    with subprocess.Popen(['adb', '-s', serial, 'shell', '-T',
                           f'dd if={node} bs={BLOCK} skip={lba} count={blocks} 2>/dev/null'],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as pipeline, \
         (backup.open("wb") if backup else contextlib.nullcontext(None)) as saved:
        sha = hashlib.sha256()
        remaining = length
        while remaining > 0:
            chunk = pipeline.stdout.read(min(1 << 20, remaining))
            if not chunk:
                break
            sha.update(chunk)
            if saved:
                saved.write(chunk)
            remaining -= len(chunk)
        if remaining:
            raise SystemExit('short device readback')
        if pipeline.wait(timeout=60):
            raise SystemExit('device readback failed')
    return sha.hexdigest()


def validate_envelope(name, path, record):
    data = path.read_bytes()
    size, expected_digest = EXPECTED_IMAGES[name]
    blocks = (size + BLOCK - 1) // BLOCK
    if (len(data) != 544 + blocks * 32 or data[:8] != b'VROOT01\0' or
            struct.unpack_from('<4I', data, 8) != (1, 160, BLOCK, 0) or
            struct.unpack_from('<QQ', data, 24) != (size, blocks) or
            data[56:88].hex() != expected_digest or
            data[120:152].hex() != EXPECTED_KEY_HASH or
            hashlib.sha256(data[544:]).digest() != data[88:120]):
        raise ValueError(name + ': wrong envelope geometry, original image digest, key or hash table')
    digest = hashlib.sha256(data).hexdigest()
    if (record.get('envelope_sha256') != digest or
            record.get('verified_blocks') != blocks or
            record.get('image_sha256') != expected_digest or
            not record.get('signature_verified_by_openssl')):
        raise ValueError(name + ': require the exact fully C-verified source report')
    return len(data), digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--os', type=Path, default=Path('out/step7/owner-manifests/OS/manifest.bin'))
    parser.add_argument('--systemos', type=Path, default=Path('out/step7/owner-manifests/SystemOS/manifest.bin'))
    parser.add_argument('--node', default='/dev/block/sda36')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--source-report', type=Path, required=True)
    parser.add_argument('--expected-old-os', required=True)
    parser.add_argument('--expected-old-systemos', required=True)
    options = parser.parse_args()
    if options.node != '/dev/block/sda36':
        raise SystemExit('Only the captured SM-T970 userdata node is supported')
    if options.output.exists():
        raise SystemExit('Choose a new output directory')
    if subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '--quiet',
                       str((options.output / 'backup.bin').resolve())]).returncode:
        raise SystemExit('Policy backups require Git-ignored output storage')
    source = json.loads(options.source_report.read_text())
    if not source.get('input_window_digests_verified'):
        raise SystemExit('Source windows were not checked against SHNGROOT')
    records = {entry['name']: entry for entry in source['windows']}
    plans = [('OS', options.os, OS_LBA, options.expected_old_os),
             ('SystemOS', options.systemos, SYSTEMOS_LBA, options.expected_old_systemos)]
    report = {'node': options.node, 'write': options.write, 'envelopes': [],
              'source_report': str(options.source_report), 'all_verified': False,
              'scope': 'Two fixed owner-envelope ranges only; backup both old ranges before any write'}
    for name, path, lba, expected_old in plans:
        length, digest = validate_envelope(name, path, records[name])
        if len(expected_old) != 64 or any(c not in '0123456789abcdef' for c in expected_old):
            raise ValueError('Require exact previous envelope SHA256')
        report['envelopes'].append({'name': name, 'lba': lba,
            'blocks': (length + BLOCK - 1) // BLOCK, 'bytes': length, 'sha256': digest,
            'expected_old_sha256': expected_old, 'backup': str(options.output / (name + '-before.bin')),
            'remote': '/tmp/unixnu-policy-' + name + '.bin', 'write_attempted': False})
    options.output.mkdir(parents=True)
    receipt = options.output / 'receipt.json'
    def save():
        receipt.write_text(json.dumps(report, indent=2) + '\n')
    save()
    try:
        subprocess.run([sys.executable, str(ROOT / 'scripts/check-recovery-storage.py'),
            '--serial', options.serial, '--output', str(options.output / 'readiness.json')], check=True)
        if options.write:
            for entry in report['envelopes']:
                entry['backup_sha256'] = device_sha(options.serial, options.node, entry['lba'],
                    entry['blocks'], entry['bytes'], Path(entry['backup']))
                save()
                if entry['backup_sha256'] != entry['expected_old_sha256']:
                    raise RuntimeError('Previous carrier differs; nothing may be written')
        for (name, path, _, _), entry in zip(plans, report['envelopes']):
            if options.write:
                pushed = sh('adb', '-s', options.serial, 'push', str(path), entry['remote'])
                if pushed.returncode:
                    raise RuntimeError(pushed.stderr[-800:])
                entry['write_attempted'] = True
                save()
                command = (f'dd if={entry["remote"]} of={options.node} bs={BLOCK} seek={entry["lba"]} '
                           f'count={entry["blocks"]} conv=fsync && sync && '
                           f'blockdev --flushbufs {options.node}')
                wrote = sh('adb', '-s', options.serial, 'shell', '-T', command)
                entry['write_output'] = (wrote.stdout + wrote.stderr)[-800:]
                entry['write_exit_code'] = wrote.returncode
                save()
                if wrote.returncode:
                    raise RuntimeError('Write/sync/cache flush failed; no automatic retry')
            entry['readback_sha256'] = device_sha(options.serial, options.node, entry['lba'],
                                                  entry['blocks'], entry['bytes'])
            entry['verified'] = entry['readback_sha256'] == entry['sha256']
            save()
            if not entry['verified']:
                raise RuntimeError('Envelope readback mismatch; no automatic retry')
            if options.write:
                sh('adb', '-s', options.serial, 'shell', '-T', 'rm -f ' + entry['remote'])
        report['all_verified'] = all(entry['verified'] for entry in report['envelopes'])
        save()
    except BaseException as error:
        report['error'] = str(error)
        save()
        raise
    print(json.dumps(report, indent=2))
    if not report['all_verified']:
        sys.exit(1)


if __name__ == '__main__':
    main()
