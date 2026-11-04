#!/usr/bin/env python3
"""Replace only the prelinked kernel in the observed v31 BOOT FAT image."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

device = Path(__file__).resolve().parents[3]
out = device / 'out/data-bringup'
v31 = out / 'data-space-v31-memory768-v1'
v32 = out / 'vsync-stages-v32'
work = out / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data'
v31_kernel = out / 'pre-vsync-stages-v32/kernel.macho'
kernel = work / 'kernel/kernel.macho'
expected = json.loads((device / 'evidence/storage/data-space-v31/preparation.json').read_text())
marker = b'vsync start/arm/idle/late/refresh='


def sha(data):
    return hashlib.sha256(data).hexdigest()


def enable_screen(path):
    env = dict(os.environ, UNIXNU_UEFI=str(device / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(work / 'tree/scripts/patch-xnu-entry-probe.py'),
                    str(path), '--panic-screen', '--no-reset'], env=env, check=True)


raw = (v31 / 'boot-partition.img').read_bytes()
assert sha(raw) == expected['boot_sha256'] and raw[:8] == b'ANDROID!' and len(raw) == 71303168
assert sha(v31_kernel.read_bytes()) == expected['kernel_sha256']
assert marker in kernel.read_bytes(), 'Missing linked v32 display report'
page, version = struct.unpack_from('<II', raw, 36)
assert (page, version) == (4096, 2)
kernel_size = struct.unpack_from('<I', raw, 8)[0]
payload_size = struct.unpack_from('<I', raw, 16)[0]
start = page + (kernel_size + page - 1) // page * page
end = start + payload_size
assert 0 < start < end <= len(raw)
v32.mkdir()
payload = v32 / 'payload.img'
payload.write_bytes(raw[start:end])
kernel_entry = 'Payloads/kernel.macho'
prefix = '::/EFI/UniXNU/'


def get(name):
    return subprocess.check_output(['mtype', '-i', str(payload), prefix + name])


original_kernel = get(kernel_entry)
assert sha(original_kernel) == expected['payload_kernel_sha256']
baseline_check = v32 / 'v31-panic-screen-check.macho'
shutil.copyfile(v31_kernel, baseline_check)
enable_screen(baseline_check)
assert baseline_check.read_bytes() == original_kernel
replacement = v32 / 'kernel.macho'
shutil.copyfile(kernel, replacement)
enable_screen(replacement)
assert marker in replacement.read_bytes()
immutable = {n: sha(get(n)) for n in ('unixnu.toml', 'Payloads/kernel.macho.adt',
                                      'Payloads/kernel.macho.trustcache', 'Payloads/scratch-data.img')}
subprocess.run(['mcopy', '-o', '-i', str(payload), str(replacement), prefix + kernel_entry], check=True)
packed = raw[:start] + payload.read_bytes() + raw[end:]
assert len(packed) == len(raw)
image = v32 / 'boot-partition.img'
image.write_bytes(packed)
payload.write_bytes(image.read_bytes()[start:end])
assert get(kernel_entry) == replacement.read_bytes()
assert all(sha(get(name)) == digest for name, digest in immutable.items())
report = dict(base_boot_sha256=sha(raw), boot_sha256=sha(packed), boot_bytes=len(packed),
              kernel_sha256=sha(kernel.read_bytes()), payload_kernel_sha256=sha(get(kernel_entry)),
              unchanged_payload_sha256=immutable, original_panic_screen_reproduced=True,
              final_boot_fat_roundtrip=True, header_fd_dtb_tail_unchanged=True,
              target_seconds=125, cpus_requested=8, owned_bytes=805306368,
              terminal_runtime_report=True, uploaded=False, hardware_result_pending=True)
(v32 / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: vsync stages BOOT ' + report['boot_sha256'])
