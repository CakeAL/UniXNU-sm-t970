#!/usr/bin/env python3
"""Reproduce the trust-cache bundle the payload step accepts.

The payload accepts only bundles whose SHA-256 is listed in the OS profile's
[payload] trust_cache_sha256. The accepted bundle is the two-module original
static+system bundle: the framework's build-original-system-trust.py needs the
DER payload of StaticTrustCache and the IPSW at UniXNU/refer/.

This script takes the StaticTrustCache member extracted by "unixnu ipsw fetch",
writes the framework's expected static-trustcache.bin, runs the framework
builder, and checks the result against the profile allow-list. Host only.
"""
import argparse
import hashlib
import plistlib
import subprocess
import sys
from pathlib import Path
import tomllib

DEVICE = Path(__file__).resolve().parents[1]


def der(data, at):
    tag, size = data[at], data[at + 1]
    at += 2
    if size & 128:
        count = size & 127
        size = int.from_bytes(data[at:at + count], 'big')
        at += count
    return tag, data[at:at + size], at + size


def payload(path):
    tag, sequence, end = der(path.read_bytes(), 0)
    fields, cursor = [], 0
    while cursor < len(sequence):
        kind, value, cursor = der(sequence, cursor)
        fields.append((kind, value))
    if tag != 0x30 or end != path.stat().st_size or [k for k, _ in fields] != [0x16, 0x16, 0x16, 4]:
        raise SystemExit(f'{path}: not the expected IM4P wrapper')
    return fields[3][1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unixnu', type=Path, default=DEVICE.parent / 'UniXNU')
    parser.add_argument('--static-trustcache', type=Path,
                        help='the .dmg.trustcache member from unixnu ipsw fetch')
    parser.add_argument('--output', type=Path, help='static-trustcache.bin destination')
    args = parser.parse_args()
    unixnu = args.unixnu.resolve()
    config = tomllib.loads((unixnu / 'unixnu.local.toml').read_text())['build']
    build = tomllib.loads((unixnu / 'profiles/os/ipados-17.7.11-21H461/profile.toml').read_text())
    accepted = build['payload']['trust_cache_sha256']
    ipsw = Path(config['ipsw']).expanduser()
    if not ipsw.is_absolute():
        ipsw = (unixnu / ipsw).resolve()
    with ipsw.open('rb') as _:
        pass
    member = args.static_trustcache
    if member is None:
        with __import__('zipfile').ZipFile(ipsw) as archive:
            manifest = plistlib.loads(archive.read('BuildManifest.plist'))
            identity = next(i for i in manifest['BuildIdentities'] if i['Info']['DeviceClass'] == 'j120ap')
            entry = identity['Manifest']['StaticTrustCache']['Info']['Path']
            target = unixnu / 'out/ipsw' / manifest['ProductBuildVersion'] / Path(entry).name
        member = target
    static = payload(member)
    if (len(static) < 24 or (len(static) - 24) % 24 or
            int.from_bytes(static[:4], 'little') != 2):
        raise SystemExit(f'{member}: not a version-2 trust module')
    output = args.output or unixnu / '.cache/firmware/target-volumes/static-trustcache.bin'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(static)
    print(f'static module: {len(static)} bytes sha256 {hashlib.sha256(static).hexdigest()}')
    refer = unixnu / 'refer' / ipsw.name
    if not refer.exists():
        raise SystemExit(f'link the IPSW at {refer} (build-original-system-trust.py expects it)')
    result = subprocess.run([sys.executable, str(unixnu / 'scripts/build-original-system-trust.py')],
                            cwd=unixnu, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stderr or result.stdout)
    bundle = unixnu / 'build/original-static-system-trust/original-static-system.bundle'
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    if digest not in accepted:
        raise SystemExit(f'bundle {digest} is not accepted by the OS profile: {accepted}')
    print(f'bundle {bundle} sha256 {digest} is accepted')
    print('set trust_cache = "' + str(bundle.relative_to(unixnu)) + '" in unixnu.local.toml')


if __name__ == '__main__':
    main()
