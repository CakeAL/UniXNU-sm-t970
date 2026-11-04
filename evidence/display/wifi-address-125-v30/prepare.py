#!/usr/bin/env python3
"""Add one synthetic Wi-Fi ADT property to a preserved diagnostic BOOT image."""
from pathlib import Path
import hashlib
import importlib.util
import json
import secrets
import struct
import subprocess

root = Path(__file__).resolve().parents[3]
base = root / 'out/data-bringup/display-novc-memory768-v1/boot-partition.img'
out = root / 'out/data-bringup/wifi-address-125-v30'
expected = 'bb4d847476d455c0a49d28ffea03492e8e0f2b5fd0f2480ed2eb34dc5604912e'
sha = lambda data: hashlib.sha256(data).hexdigest()
raw = base.read_bytes()
assert sha(raw) == expected and raw[:8] == b'ANDROID!' and len(raw) == 71303168
assert not out.exists(), 'Preserve earlier outputs'
page, version = struct.unpack_from('<II', raw, 36)
assert (page, version) == (4096, 2)
kernel_size = struct.unpack_from('<I', raw, 8)[0]
ramdisk_size = struct.unpack_from('<I', raw, 16)[0]
start = page + (kernel_size + page - 1) // page * page
assert 0 < start < start + ramdisk_size <= len(raw)
out.mkdir()
payload = out / 'payload.img'
payload.write_bytes(raw[start:start + ramdisk_size])

def get(name):
    return subprocess.check_output(['mtype', '-i', str(payload), '::/EFI/UniXNU/' + name])

names = ['unixnu.toml'] + ['Payloads/' + name for name in
    ('kernel.macho', 'kernel.macho.adt', 'kernel.macho.trustcache', 'scratch-data.img')]
original = {name: get(name) for name in names}
adt = original['Payloads/kernel.macho.adt']
spec = importlib.util.spec_from_file_location('platform', root / 'scripts/check-platform.py')
platform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platform)
before = platform.decode_adt(adt)
key = 'mac-address-wifi0'
assert '/chosen' in before and all(key not in props for props in before.values())
address = bytearray(secrets.token_bytes(6))
address[0] = (address[0] | 2) & 0xfe  # Locally administered, unicast; not a hardware MAC.
(out / 'synthetic-wifi-address.bin').write_bytes(address)

def locate(offset, parent, is_root=False):
    node_offset = offset
    count, children = struct.unpack_from('<II', adt, offset)
    offset += 8
    props = {}
    for _ in range(count):
        raw_key, length = struct.unpack_from('<32sI', adt, offset)
        offset += 36
        name = raw_key.split(b'\0', 1)[0].decode()
        assert name not in props and offset + length <= len(adt)
        props[name] = adt[offset:offset + length]
        offset += (length + 3) & ~3
    name = props['name'].rstrip(b'\0').decode()
    path = '' if is_root else parent + '/' + name
    if path == '/chosen':
        matches.append((node_offset, count, offset))
    for _ in range(children):
        offset = locate(offset, path)
    return offset

matches = []
assert locate(0, '', True) == len(adt) and len(matches) == 1
node_offset, count, insert_at = matches[0]
prop = struct.pack('<32sI', key.encode(), len(address)) + bytes(address) + bytes(2)
changed = bytearray(adt[:insert_at] + prop + adt[insert_at:])
struct.pack_into('<I', changed, node_offset, count + 1)
after = platform.decode_adt(bytes(changed))
expected_tree = {path: dict(values) for path, values in before.items()}
expected_tree['/chosen'][key] = bytes(address)
assert after == expected_tree
adt_path = out / 'kernel.macho.adt'
adt_path.write_bytes(changed)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(adt_path),
                '::/EFI/UniXNU/Payloads/kernel.macho.adt'], check=True)
packed = bytearray(raw)
new_payload = payload.read_bytes()
assert len(new_payload) == ramdisk_size
packed[start:start + ramdisk_size] = new_payload
assert len(packed) == len(raw) and packed[:start] == raw[:start] and packed[start + ramdisk_size:] == raw[start + ramdisk_size:]
image = out / 'boot-partition.img'
image.write_bytes(packed)
payload.write_bytes(image.read_bytes()[start:start + ramdisk_size])
assert all(get(name) == (bytes(changed) if name.endswith('.adt') else content)
           for name, content in original.items())
report = {'base_boot_sha256': sha(raw), 'boot_sha256': sha(packed), 'boot_bytes': len(packed),
          'base_adt_sha256': sha(adt), 'adt_sha256': sha(changed),
          'adt_only_added': '/chosen/mac-address-wifi0', 'address_bytes': len(address),
          'address_policy': 'random locally administered unicast; diagnostic only, not board identity',
          'unchanged_inputs': {name: sha(content) for name, content in original.items() if not name.endswith('.adt')},
          'config_unchanged': True, 'final_boot_fat_roundtrip': True,
          'header_fd_dtb_tail_unchanged': True, 'target_seconds': 125,
          'terminal_runtime_report': True, 'board_defaults_unchanged': True,
          'wifi_functionality_verified': False, 'uploaded': False, 'hardware_result_pending': True}
(out / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
