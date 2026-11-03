#!/usr/bin/env python3
"""Repack the recorded v9 image with only its report deadline changed; no upload."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tomllib

device = Path(__file__).resolve().parents[3]
source = device / 'out/data-bringup/ui-call-cpu8/boot-partition.img'
out = device / 'out/data-bringup/ui-call-runtime120'
assert not out.exists(), 'Preserve earlier outputs'
sha = lambda b: hashlib.sha256(b).hexdigest()
raw = source.read_bytes()
assert sha(raw) == '455310477633ec07c43bd030f024711945ef2d74d7e34925e3ab05f4963ac932'
assert raw[:8] == b'ANDROID!' and len(raw) == 71303168
page, version = struct.unpack_from('<II', raw, 36)
assert (page, version) == (4096, 2)
kernel_size = struct.unpack_from('<I', raw, 8)[0]
size = struct.unpack_from('<I', raw, 16)[0]
start = page + (kernel_size + page - 1) // page * page
assert size == 58720256
board = (device / 'board.toml').read_bytes()
out.mkdir()
payload = out / 'payload.img'
payload.write_bytes(raw[start:start + size])

def get(path):
    return subprocess.check_output(['mtype', '-i', str(payload), '::/EFI/UniXNU/' + path])

names = ['Payloads/' + n for n in ('kernel.macho', 'kernel.macho.adt',
         'kernel.macho.trustcache', 'scratch-data.img')]
originals = {n: get(n) for n in names}
text = get('unixnu.toml').decode()
conf = tomllib.loads(text)
entry = next(e for e in conf['entry'] if e['id'] == 'xnu')
assert conf['boot']['default'] == 'xnu'
assert entry['args'].split().count('t970-runtime-report=60') == 1
assert 't970-runtime-report=120' not in text
updated = text.replace('t970-runtime-report=60', 't970-runtime-report=120')
expected = tomllib.loads(text)
next(e for e in expected['entry'] if e['id'] == 'xnu')['args'] = entry['args'].replace(
    't970-runtime-report=60', 't970-runtime-report=120')
assert tomllib.loads(updated) == expected
config = out / 'unixnu.toml'
config.write_text(updated)
subprocess.run(['mcopy', '-o', '-i', str(payload), str(config),
                '::/EFI/UniXNU/unixnu.toml'], check=True)
packed = bytearray(raw)
packed[start:start + size] = payload.read_bytes()
assert len(packed) == len(raw)
assert packed[:start] == raw[:start] and packed[start + size:] == raw[start + size:]
target = out / 'boot-partition.img'
target.write_bytes(packed)
# Re-extract the FAT from the final BOOT, then check actual configuration and inputs.
payload.write_bytes(target.read_bytes()[start:start + size])
assert get('unixnu.toml').decode() == updated
assert all(get(n) == b for n, b in originals.items())
assert (device / 'board.toml').read_bytes() == board
report = dict(base_boot_sha256=sha(raw), boot_sha256=sha(packed),
              boot_bytes=len(packed), changed_argument='t970-runtime-report=60 -> 120',
              target_wait_seconds=120, cpus_requested=8,
              unchanged_payload_inputs={n: sha(b) for n, b in originals.items()},
              final_boot_fat_roundtrip=True, header_fd_dtb_tail_unchanged=True,
              board_default_unchanged=True, uploaded=False, hardware_result_pending=True)
(out / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
