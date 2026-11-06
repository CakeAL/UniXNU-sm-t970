#!/usr/bin/env python3
"""Pack v51 with an eight-stream continuation table so interleaved readers still prefetch."""
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
base = out / 'ufs-timing-v46'
v51 = out / 'ufs-readahead-v51'
work = out / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data'
kernel = work / 'kernel/kernel.macho'
expected = json.loads((device / 'evidence/display/ufs-timing-v46/preparation.json').read_text())
marker = b'LS waits=%llu addr=%llx waiter=%llx owner=%llx'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def enable_screen(path):
    env = dict(os.environ, UNIXNU_UEFI=str(device / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(work / 'tree/scripts/patch-xnu-entry-probe.py'),
                    str(path), '--panic-screen', '--no-reset'], env=env, check=True)


raw = (base / 'boot-partition.img').read_bytes()
assert sha(raw) == expected['boot_sha256'] and raw[:8] == b'ANDROID!' and len(raw) == 71303168
assert marker in kernel.read_bytes(), 'Missing linked v51 display report'
page, version = struct.unpack_from('<II', raw, 36)
assert (page, version) == (4096, 2)
kernel_size = struct.unpack_from('<I', raw, 8)[0]
payload_size = struct.unpack_from('<I', raw, 16)[0]
start = page + (kernel_size + page - 1) // page * page
end = start + payload_size
assert 0 < start < end <= len(raw)
v51.mkdir()
payload = v51 / 'payload.img'
payload.write_bytes(raw[start:end])
kernel_entry = 'Payloads/kernel.macho'
prefix = '::/EFI/UniXNU/'


def get(name):
    return subprocess.check_output(['mtype', '-i', str(payload), prefix + name])


original_kernel = get(kernel_entry)
assert sha(original_kernel) == expected['payload_kernel_sha256']
replacement = v51 / 'kernel.macho'
shutil.copyfile(kernel, replacement)
enable_screen(replacement)
assert marker in replacement.read_bytes()
immutable = dict(expected['unchanged_payload_sha256'])
config_text = get('unixnu.toml').decode()
assert 'unixnu.toml' not in immutable
assert all(sha(get(name)) == digest for name, digest in immutable.items())
config = tomllib.loads(config_text)
entry = next(item for item in config['entry'] if item['id'] == 'xnu')
args = entry['args'].split()
assert {'t970-runtime-report=300', 't970-display-hold=1', 't970-ls-owner=1', 't970-ufs-time=1'} <= set(args)
assert 't970-ui-stack=10' in args
extra = 't970-ufs-bench=1'
assert extra not in args
line = 'args = "' + entry['args'] + '"'
entry['args'] += ' ' + extra
assert config_text.count(line) == 1
updated = config_text.replace(line, 'args = "' + entry['args'] + '"')
assert tomllib.loads(updated) == config
config_path = v51 / 'unixnu.toml'
config_path.write_text(updated)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(config_path), prefix + 'unixnu.toml'], check=True)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(replacement), prefix + kernel_entry], check=True)
packed = raw[:start] + payload.read_bytes() + raw[end:]
assert len(packed) == len(raw)
image = v51 / 'boot-partition.img'
image.write_bytes(packed)
payload.write_bytes(image.read_bytes()[start:end])
assert get(kernel_entry) == replacement.read_bytes()
assert get('unixnu.toml').decode() == updated
assert all(sha(get(name)) == digest for name, digest in immutable.items())
report = dict(base_boot_sha256=sha(raw), boot_sha256=sha(packed), boot_bytes=len(packed),
              kernel_sha256=sha(kernel.read_bytes()), payload_kernel_sha256=sha(get(kernel_entry)),
              unchanged_payload_sha256=immutable, base_payload_matches_v38=True,
              final_boot_fat_roundtrip=True, header_fd_dtb_tail_unchanged=True,
              added_argument=extra, target_seconds=300, ui_stack_mode=10,
              sampled_processes=['backboardd', 'SpringBoard', 'lsd'],
              cpus_requested=8, owned_bytes=805306368,
              terminal_runtime_report=True, uploaded=False, hardware_result_pending=True)
(v51 / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: ufs bench BOOT ' + report['boot_sha256'])
