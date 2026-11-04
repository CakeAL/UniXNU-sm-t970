#!/usr/bin/env python3
"""Read the initial APFS seed's host-side space without mounting it writable."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seed', type=Path, required=True)
parser.add_argument('--expected-sha256', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
assert not args.output.exists(), 'Preserve prior result'
with args.seed.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
assert digest == args.expected_sha256, 'Unreviewed seed'
attachment = plistlib.loads(subprocess.check_output([
    'hdiutil', 'attach', '-imagekey', 'diskimage-class=CRawDiskImage', '-readonly',
    '-nobrowse', '-nomount', '-plist', str(args.seed)]))
devices = [x['dev-entry'] for x in attachment['system-entities']
           if x.get('dev-entry') and not x.get('content-hint')]
assert len(devices) == 1, 'Unexpected image device list'
device = devices[0]
try:
    listing = plistlib.loads(subprocess.check_output(['diskutil', 'apfs', 'list', '-plist']))
    candidates = [c for c in listing.get('Containers', [])
                  if any(('/dev/' + str(s.get('DeviceIdentifier', ''))) == device or
                         ('/dev/' + str(s.get('DeviceIdentifier', ''))).startswith(device + 's')
                         for s in c.get('PhysicalStores', []))]
    assert len(candidates) == 1, 'Expected exactly one APFS container'
    container = candidates[0]
    total, free = container['CapacityCeiling'], container['CapacityFree']
    assert isinstance(total, int) and isinstance(free, int) and 0 <= free <= total
    report = {'seed_sha256': digest, 'attached_read_only': True, 'capacity_bytes': total,
              'free_bytes': free, 'volume_count': len(container.get('Volumes', [])),
              'limitation': 'Initial host seed only; runtime writes and Data free space are not measured.'}
finally:
    subprocess.run(['hdiutil', 'detach', device], check=True, stdout=subprocess.DEVNULL)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
