#!/usr/bin/env python3
"""Pack the v34 kernel and enable its explicit terminal display hold."""
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
v33 = out / 'bundle-late-v33'
v34 = out / 'display-hold-v34'
work = out / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data'
v33_kernel = out / 'pre-display-hold-v34/kernel.macho'
kernel = work / 'kernel/kernel.macho'
expected = json.loads((device / 'evidence/display/bundle-late-v33/preparation.json').read_text())
marker = b'FB hold=%d publish/first-copy ms='


def sha(data):
    return hashlib.sha256(data).hexdigest()


def enable_screen(path):
    env = dict(os.environ, UNIXNU_UEFI=str(device / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(work / 'tree/scripts/patch-xnu-entry-probe.py'),
                    str(path), '--panic-screen', '--no-reset'], env=env, check=True)


raw = (v33 / 'boot-partition.img').read_bytes()
assert sha(raw) == expected['boot_sha256'] and raw[:8] == b'ANDROID!' and len(raw) == 71303168
v32_prep = json.loads((device / 'evidence/display/vsync-stages-v32/preparation.json').read_text())
assert sha(v33_kernel.read_bytes()) == v32_prep['kernel_sha256']
assert marker in kernel.read_bytes(), 'Missing linked v34 display report'
page, version = struct.unpack_from('<II', raw, 36)
assert (page, version) == (4096, 2)
kernel_size = struct.unpack_from('<I', raw, 8)[0]
payload_size = struct.unpack_from('<I', raw, 16)[0]
start = page + (kernel_size + page - 1) // page * page
end = start + payload_size
assert 0 < start < end <= len(raw)
v34.mkdir()
payload = v34 / 'payload.img'
payload.write_bytes(raw[start:end])
kernel_entry = 'Payloads/kernel.macho'
prefix = '::/EFI/UniXNU/'


def get(name):
    return subprocess.check_output(['mtype', '-i', str(payload), prefix + name])


original_kernel = get(kernel_entry)
assert sha(original_kernel) == expected['unchanged_payload_sha256'][kernel_entry]
baseline_check = v34 / 'v33-panic-screen-check.macho'
shutil.copyfile(v33_kernel, baseline_check)
enable_screen(baseline_check)
assert baseline_check.read_bytes() == original_kernel
replacement = v34 / 'kernel.macho'
shutil.copyfile(kernel, replacement)
enable_screen(replacement)
assert marker in replacement.read_bytes()
immutable = {n: digest for n, digest in expected['unchanged_payload_sha256'].items() if n != kernel_entry}
assert all(sha(get(name)) == digest for name, digest in immutable.items())
old_config = get('unixnu.toml').decode()
config = tomllib.loads(old_config)
entry = next(item for item in config['entry'] if item['id'] == 'xnu')
assert 't970-runtime-report=150' in entry['args'].split() and 't970-display-hold=1' not in entry['args'].split()
args_line = 'args = "' + entry['args'] + '"'
assert old_config.count(args_line) == 1
entry['args'] += ' t970-display-hold=1'
updated = old_config.replace(args_line, 'args = "' + entry['args'] + '"')
assert tomllib.loads(updated) == config
config_path = v34 / 'unixnu.toml'
config_path.write_text(updated)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(config_path), prefix + 'unixnu.toml'], check=True)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(replacement), prefix + kernel_entry], check=True)
packed = raw[:start] + payload.read_bytes() + raw[end:]
assert len(packed) == len(raw)
image = v34 / 'boot-partition.img'
image.write_bytes(packed)
payload.write_bytes(image.read_bytes()[start:end])
assert get(kernel_entry) == replacement.read_bytes()
assert get('unixnu.toml').decode() == updated
assert all(sha(get(name)) == digest for name, digest in immutable.items())
report = dict(base_boot_sha256=sha(raw), boot_sha256=sha(packed), boot_bytes=len(packed),
              kernel_sha256=sha(kernel.read_bytes()), payload_kernel_sha256=sha(get(kernel_entry)),
              unchanged_payload_sha256=immutable, original_panic_screen_reproduced=True,
              final_boot_fat_roundtrip=True, header_fd_dtb_tail_unchanged=True,
              added_argument='t970-display-hold=1', target_seconds=150, cpus_requested=8, owned_bytes=805306368,
              terminal_runtime_report=True, uploaded=False, hardware_result_pending=True)
(v34 / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: display hold BOOT ' + report['boot_sha256'])
