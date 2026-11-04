#!/usr/bin/env python3
"""Pack v37 with the compact thread sampler enabled."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tomllib

device = Path(__file__).resolve().parents[3]
out = device / 'out/data-bringup'
v35 = out / 'scanout-drain-v35'
v37 = out / 'ui-compact-v37'
work = out / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data'
v35_kernel = out / 'pre-ui-compact-v37/kernel.macho'
kernel = work / 'kernel/kernel.macho'
expected = json.loads((device / 'evidence/display/scanout-drain-v35/preparation.json').read_text())
marker = b'FB hold=%d publish/first-copy ms=%llu/%llu src-lit=%ux%u writer=%llx'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def enable_screen(path):
    env = dict(os.environ, UNIXNU_UEFI=str(device / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(work / 'tree/scripts/patch-xnu-entry-probe.py'),
                    str(path), '--panic-screen', '--no-reset'], env=env, check=True)


raw = (v35 / 'boot-partition.img').read_bytes()
assert sha(raw) == expected['boot_sha256'] and raw[:8] == b'ANDROID!' and len(raw) == 71303168
assert sha(v35_kernel.read_bytes()) == expected['kernel_sha256']
assert marker in kernel.read_bytes(), 'Missing linked v37 display report'
page, version = struct.unpack_from('<II', raw, 36)
assert (page, version) == (4096, 2)
kernel_size = struct.unpack_from('<I', raw, 8)[0]
payload_size = struct.unpack_from('<I', raw, 16)[0]
start = page + (kernel_size + page - 1) // page * page
end = start + payload_size
assert 0 < start < end <= len(raw)
v37.mkdir()
payload = v37 / 'payload.img'
payload.write_bytes(raw[start:end])
kernel_entry = 'Payloads/kernel.macho'
prefix = '::/EFI/UniXNU/'


def get(name):
    return subprocess.check_output(['mtype', '-i', str(payload), prefix + name])


original_kernel = get(kernel_entry)
assert sha(original_kernel) == expected['payload_kernel_sha256']
baseline_check = v37 / 'v35-panic-screen-check.macho'
shutil.copyfile(v35_kernel, baseline_check)
enable_screen(baseline_check)
assert baseline_check.read_bytes() == original_kernel
replacement = v37 / 'kernel.macho'
shutil.copyfile(kernel, replacement)
enable_screen(replacement)
assert marker in replacement.read_bytes()
immutable = dict(expected['unchanged_payload_sha256'])
config_text = get('unixnu.toml').decode()
assert sha(config_text.encode()) == immutable.pop('unixnu.toml')
assert all(sha(get(name)) == digest for name, digest in immutable.items())
config = tomllib.loads(config_text)
entry = next(item for item in config['entry'] if item['id'] == 'xnu')
old_arg = 't970-ui-stack=1'
new_arg = 't970-ui-stack=9'
assert entry['args'].split().count(old_arg) == 1 and config_text.count(old_arg) == 1
assert 't970-runtime-report=150' in entry['args'].split() and 't970-display-hold=1' in entry['args'].split()
entry['args'] = ' '.join(new_arg if arg == old_arg else arg for arg in entry['args'].split())
updated = config_text.replace(old_arg, new_arg)
assert tomllib.loads(updated) == config
config_path = v37 / 'unixnu.toml'
config_path.write_text(updated)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(config_path), prefix + 'unixnu.toml'], check=True)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(replacement), prefix + kernel_entry], check=True)
packed = raw[:start] + payload.read_bytes() + raw[end:]
assert len(packed) == len(raw)
image = v37 / 'boot-partition.img'
image.write_bytes(packed)
payload.write_bytes(image.read_bytes()[start:end])
assert get(kernel_entry) == replacement.read_bytes()
assert get('unixnu.toml').decode() == updated
assert all(sha(get(name)) == digest for name, digest in immutable.items())
report = dict(base_boot_sha256=sha(raw), boot_sha256=sha(packed), boot_bytes=len(packed),
              kernel_sha256=sha(kernel.read_bytes()), payload_kernel_sha256=sha(get(kernel_entry)),
              unchanged_payload_sha256=immutable, original_panic_screen_reproduced=True,
              final_boot_fat_roundtrip=True, header_fd_dtb_tail_unchanged=True,
              target_seconds=150, ui_stack_mode=9, cpus_requested=8, owned_bytes=805306368,
              terminal_runtime_report=True, uploaded=False, hardware_result_pending=True)
(v37 / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: compact UI BOOT ' + report['boot_sha256'])
