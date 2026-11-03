#!/usr/bin/env python3
"""Change only the key-state image's EFI allocation request from512 to768 MiB."""
from pathlib import Path
import hashlib
import importlib.util
import json
import struct
import subprocess

device = Path(__file__).resolve().parents[3]
source = device / 'out/data-bringup/key-state-cpu8/boot-partition.img'
out = device / 'out/data-bringup/key-state-memory768'
assert not out.exists(), 'Preserve previous outputs'
sha = lambda b: hashlib.sha256(b).hexdigest()
raw = source.read_bytes()
assert sha(raw) == 'b9cc7afbeb2cf06a76fa7f430b4c6201c9b2c66447800c7492af414b8a253a13'
assert raw[:8] == b'ANDROID!' and len(raw) == 71303168
page, version = struct.unpack_from('<II', raw, 36)
assert (page, version) == (4096, 2)
kernel_size = struct.unpack_from('<I', raw, 8)[0]
size = struct.unpack_from('<I', raw, 16)[0]
start = page + (kernel_size + page - 1) // page * page
assert size == 58720256
unchanged = {name:(device/name).read_bytes() for name in ('board.toml','dts/sm-t970.dts','dts/sm-t970-reserved.dtsi')}
out.mkdir()
payload = out / 'payload.img'
payload.write_bytes(raw[start:start + size])
def get(name):
    return subprocess.check_output(['mtype','-i',str(payload),'::/EFI/UniXNU/'+name])
names = ['unixnu.toml'] + ['Payloads/'+name for name in ('kernel.macho','kernel.macho.adt','kernel.macho.trustcache','scratch-data.img')]
original = {n:get(n) for n in names}
adt = original['Payloads/kernel.macho.adt']
changed = bytearray(adt)
positions = []
def walk(offset, parent, root=False):
    count, children = struct.unpack_from('<II', adt, offset)
    offset += 8
    props = {}
    for _ in range(count):
        key, length = struct.unpack_from('<32sI', adt, offset)
        key = key.split(b'\0',1)[0].decode()
        offset += 36
        assert key not in props and offset+length <= len(adt)
        props[key] = (offset, adt[offset:offset+length])
        offset += (length+3)&~3
    name = props['name'][1].rstrip(b'\0').decode()
    path = '' if root else parent+'/'+name
    if 'darwinboot-memory-size' in props:
        at, old = props['darwinboot-memory-size']
        assert path == '/chosen' and old == struct.pack('<Q',0x20000000)
        changed[at:at+8] = struct.pack('<Q',0x30000000)
        positions.append(at)
    for _ in range(children):
        offset = walk(offset,path)
    return offset
assert walk(0,'',True) == len(adt) and len(positions) == 1
spec = importlib.util.spec_from_file_location('platform_check',device/'scripts/check-platform.py')
platform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platform)
before, after = platform.decode_adt(adt), platform.decode_adt(bytes(changed))
assert before['/chosen']['dram-base'] == struct.pack('<Q',0x80000000)
assert before['/chosen']['dram-size'] == struct.pack('<Q',0x80000000)
before['/chosen']['darwinboot-memory-size'] = struct.pack('<Q',0x30000000)
assert before == after, 'Unexpected topology, DRAM envelope, reservation or identity change'
path = out / 'kernel.macho.adt'
path.write_bytes(changed)
subprocess.run(['mcopy','-o','-i',str(payload),str(path),'::/EFI/UniXNU/Payloads/kernel.macho.adt'],check=True)
packed = bytearray(raw)
packed[start:start+size] = payload.read_bytes()
assert len(packed) == len(raw) and packed[:start] == raw[:start] and packed[start+size:] == raw[start+size:]
target = out/'boot-partition.img'
target.write_bytes(packed)
payload.write_bytes(target.read_bytes()[start:start+size])
for name, data in original.items():
    assert get(name) == (bytes(changed) if name.endswith('.adt') else data), name
assert all((device/name).read_bytes()==data for name,data in unchanged.items())
report = dict(base_boot_sha256=sha(raw),boot_sha256=sha(packed),boot_bytes=len(packed),
              changed_property='/chosen/darwinboot-memory-size',old_owned_bytes=0x20000000,new_owned_bytes=0x30000000,
              unchanged_payload_inputs={n:sha(b) for n,b in original.items() if not n.endswith('.adt')},
              adt_sha256=sha(changed),only_one_adt_property_changed=True,final_boot_fat_roundtrip=True,
              header_fd_dtb_tail_unchanged=True,board_dts_reservations_unchanged=True,
              runtime_allocator='Existing DarwinBoot AllocateWindow: EfiConventionalMemory and AllocatePages only',
              allocation_verified=False,uploaded=False,hardware_result_pending=True,target_wait_seconds=60)
(out/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
