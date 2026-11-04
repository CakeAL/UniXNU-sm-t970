#!/usr/bin/env python3
"""Change only the v32 terminal report deadline from 125 to 150 seconds."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tomllib

device = Path(__file__).resolve().parents[3]
outputs = device / 'out/data-bringup'
base = outputs / 'vsync-stages-v32/boot-partition.img'
out = outputs / 'bundle-late-v33'
prior = json.loads((device / 'evidence/display/vsync-stages-v32/preparation.json').read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
raw = base.read_bytes()
assert sha(raw) == prior['boot_sha256'] and raw[:8] == b'ANDROID!' and len(raw) == 71303168
assert struct.unpack_from('<II', raw, 36) == (4096, 2)
kernel_size = struct.unpack_from('<I', raw, 8)[0]
payload_size = struct.unpack_from('<I', raw, 16)[0]
start = 4096 + (kernel_size + 4095) // 4096 * 4096
end = start + payload_size
assert 0 < start < end <= len(raw)
out.mkdir()
payload = out / 'payload.img'
payload.write_bytes(raw[start:end])
prefix = '::/EFI/UniXNU/'


def get(name):
    return subprocess.check_output(['mtype', '-i', str(payload), prefix + name])


text = get('unixnu.toml').decode()
config = tomllib.loads(text)
entry = next(item for item in config['entry'] if item['id'] == 'xnu')
before = 't970-runtime-report=125'
after = 't970-runtime-report=150'
assert entry['args'].split().count(before) == 1 and text.count(before) == 1
updated = text.replace(before, after)
entry['args'] = ' '.join(after if arg == before else arg for arg in entry['args'].split())
assert tomllib.loads(updated) == config
immutable = {name: digest for name, digest in prior['unchanged_payload_sha256'].items() if name != 'unixnu.toml'}
immutable['Payloads/kernel.macho'] = prior['payload_kernel_sha256']
assert all(sha(get(name)) == digest for name, digest in immutable.items())
path = out / 'unixnu.toml'
path.write_text(updated)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(path), prefix + 'unixnu.toml'], check=True)
packed = raw[:start] + payload.read_bytes() + raw[end:]
assert len(packed) == len(raw) and packed[:start] == raw[:start] and packed[end:] == raw[end:]
image = out / 'boot-partition.img'
image.write_bytes(packed)
payload.write_bytes(image.read_bytes()[start:end])
assert get('unixnu.toml').decode() == updated
assert all(sha(get(name)) == digest for name, digest in immutable.items())
report = dict(base_boot_sha256=sha(raw), boot_sha256=sha(packed), boot_bytes=len(packed),
              changed_argument={'from': before, 'to': after}, unchanged_payload_sha256=immutable,
              target_seconds=150, cpus_requested=8, owned_bytes=805306368,
              final_boot_fat_roundtrip=True, header_fd_dtb_tail_unchanged=True,
              terminal_runtime_report=True, uploaded=False, hardware_result_pending=True)
(out / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: target150 BOOT ' + report['boot_sha256'])
