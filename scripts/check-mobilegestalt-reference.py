#!/usr/bin/env python3
"""Check relevant strings in the original cache and property presence in a packed ADT."""
import argparse
import hashlib
import importlib.util
import json
import mmap
from pathlib import Path
import struct

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cache', type=Path, required=True)
parser.add_argument('--adt', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
assert not args.output.exists(), 'Preserve prior results'
device = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('platform', device / 'scripts/check-platform.py')
platform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platform)
adt_data = args.adt.read_bytes()
adt = platform.decode_adt(adt_data)
main = (args.cache / 'dyld_shared_cache_arm64').read_bytes()
assert main[:16].rstrip(b'\0') == b'dyld_v1   arm64'
at, count = struct.unpack_from('<2Q', main, 136)
images = []
for i in range(count):
    _, address, size, path = struct.unpack_from('<16sQ2I', main, at + i * 32)
    images.append((address, size, main[path:main.index(b'\0', path)].decode()))
needles = ('mac-address-wifi0', 'mac-address-bluetooth0', 'IONetworkController', 'marconi-wifi')
found = {name: [] for name in needles}
subcache = args.cache / 'dyld_shared_cache_arm64.11'
with subcache.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
    assert data[:16].rstrip(b'\0') == b'dyld_v1   arm64'
    offset, count = struct.unpack_from('<2I', data, 16)
    mappings = [struct.unpack_from('<3Q2I', data, offset + i * 32) for i in range(count)]
    for name in needles:
        cursor = 0
        while (cursor := data.find(name.encode(), cursor)) >= 0:
            for va, size, file_offset, _, _ in mappings:
                if file_offset <= cursor < file_offset + size:
                    address = va + cursor - file_offset
                    image = next((n for a, length, n in images if a <= address < a + length), None)
                    if image == '/usr/lib/libMobileGestalt.dylib':
                        found[name].append({'unslid_va': hex(address), 'subcache_offset': hex(cursor)})
            cursor += len(name)
for name in needles:
    assert found[name], 'String absent from MobileGestalt image: ' + name
props = {name: [{'node': node, 'length': len(values[name])}
                for node, values in adt.items() if name in values]
         for name in ('mac-address-wifi0', 'mac-address-bluetooth0')}
result = {'cache_uuid': main[88:104].hex(), 'subcache': subcache.name,
          'adt_sha256': hashlib.sha256(adt_data).hexdigest(),
          'image': '/usr/lib/libMobileGestalt.dylib', 'strings': found,
          'adt_property_presence': props,
          'limitation': 'String presence is not an executed call, cross-reference, or proof of the device wait cause.'}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
