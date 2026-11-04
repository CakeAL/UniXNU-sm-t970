#!/usr/bin/env python3
"""Make a single-argument, non-terminal comparison of the observed v24 image."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import tomllib

root = Path(__file__).resolve().parents[3]
base = root / 'out/data-bringup/display-novc-memory768-v1/boot-partition.img'
out = root / 'out/data-bringup/display-continuous-v25'
expected = 'bb4d847476d455c0a49d28ffea03492e8e0f2b5fd0f2480ed2eb34dc5604912e'
sha = lambda data: hashlib.sha256(data).hexdigest()
raw = base.read_bytes()
assert sha(raw) == expected and raw[:8] == b'ANDROID!' and len(raw) == 71303168
assert not out.exists(), 'Preserve any earlier output'
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

names = ['Payloads/' + n for n in
         ('kernel.macho', 'kernel.macho.adt', 'kernel.macho.trustcache', 'scratch-data.img')]
original = {n: get(n) for n in names}
text = get('unixnu.toml').decode()
config = tomllib.loads(text)
entry = next(e for e in config['entry'] if e['id'] == 'xnu')
args = entry['args'].split()
removed = 't970-runtime-report=125'
assert args.count(removed) == 1 and 'offline-legacy-cpu-present=1' in args
updated_args = ' '.join(a for a in args if a != removed)
old_line = 'args = "' + entry['args'] + '"'
new_line = 'args = "' + updated_args + '"'
assert text.count(old_line) == 1
updated = text.replace(old_line, new_line, 1)
entry['args'] = updated_args
assert tomllib.loads(updated) == config
config_path = out / 'unixnu.toml'
config_path.write_text(updated)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(config_path),
                '::/EFI/UniXNU/unixnu.toml'], check=True)
packed = bytearray(raw)
packed[start:start + ramdisk_size] = payload.read_bytes()
assert len(packed) == len(raw) and packed[:start] == raw[:start] and packed[start + ramdisk_size:] == raw[start + ramdisk_size:]
image = out / 'boot-partition.img'
image.write_bytes(packed)
payload.write_bytes(image.read_bytes()[start:start + ramdisk_size])
assert get('unixnu.toml').decode() == updated
assert all(get(n) == data for n, data in original.items())
report = {'base_boot_sha256': sha(raw), 'boot_sha256': sha(packed),
          'boot_bytes': len(packed), 'removed_arguments': [removed],
          'args': updated_args, 'owned_bytes': 0x30000000, 'cpus_requested': 8,
          'unchanged_payload_inputs': {n: sha(data) for n, data in original.items()},
          'final_boot_fat_roundtrip': True, 'header_fd_dtb_tail_unchanged': True,
          'terminal_runtime_report': False, 'process_exit_panic_retained': True,
          'uploaded': False, 'hardware_result_pending': True}
(out / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
