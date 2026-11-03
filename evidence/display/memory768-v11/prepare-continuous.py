#!/usr/bin/env python3
"""Remove only diagnostic boot arguments from the tested768 MiB key-state image."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import tomllib

device = Path(__file__).resolve().parents[3]
source = device/'out/data-bringup/key-state-memory768/boot-partition.img'
out = device/'out/data-bringup/key-state-memory768-continuous'
assert not out.exists(), 'Preserve previous outputs'
sha = lambda data:hashlib.sha256(data).hexdigest()
raw = source.read_bytes()
assert sha(raw) == 'f6fd663660d9f6e70b0c0028197afd229ac2d2aaed71c135952393493c736a40'
assert raw[:8] == b'ANDROID!' and len(raw) == 71303168
page,version = struct.unpack_from('<II',raw,36)
assert (page,version) == (4096,2)
kernel_size = struct.unpack_from('<I',raw,8)[0]
size = struct.unpack_from('<I',raw,16)[0]
start = page+(kernel_size+page-1)//page*page
out.mkdir()
payload = out/'payload.img'
payload.write_bytes(raw[start:start+size])
def get(name):
    return subprocess.check_output(['mtype','-i',str(payload),'::/EFI/UniXNU/'+name])
names = ['Payloads/'+name for name in ('kernel.macho','kernel.macho.adt','kernel.macho.trustcache','scratch-data.img')]
original = {n:get(n) for n in names}
text = get('unixnu.toml').decode()
config = tomllib.loads(text)
entry = next(e for e in config['entry'] if e['id']=='xnu')
remove = {'t970-runtime-report=60','t970-runtime-cache-trace=1',
          'panic_on_error_exit=backboardd,SpringBoard','t970-ui-spawn-calls=1'}
args = entry['args'].split()
assert remove <= set(args) and all(args.count(arg)==1 for arg in remove)
updated_args = ' '.join(arg for arg in args if arg not in remove)
updated = text.replace('args = "'+entry['args']+'"','args = "'+updated_args+'"')
entry['args'] = updated_args
assert tomllib.loads(updated)==config
path = out/'unixnu.toml'
path.write_text(updated)
subprocess.run(['mcopy','-o','-i',str(payload),str(path),'::/EFI/UniXNU/unixnu.toml'],check=True)
packed = bytearray(raw)
packed[start:start+size] = payload.read_bytes()
assert len(packed)==len(raw) and packed[:start]==raw[:start] and packed[start+size:]==raw[start+size:]
target = out/'boot-partition.img'
target.write_bytes(packed)
payload.write_bytes(target.read_bytes()[start:start+size])
assert get('unixnu.toml').decode()==updated
assert all(get(n)==data for n,data in original.items())
report = dict(base_boot_sha256=sha(raw),boot_sha256=sha(packed),boot_bytes=len(packed),
              removed_arguments=sorted(remove),args=updated_args,owned_bytes=0x30000000,
              unchanged_payload_inputs={n:sha(data) for n,data in original.items()},
              final_boot_fat_roundtrip=True,header_fd_dtb_tail_unchanged=True,
              terminal_runtime_report=False,uploaded=False,hardware_result_pending=True)
(out/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
