#!/usr/bin/env python3
"""Audit a pinned iPadOS 21H461 MobileGestalt Wi-Fi resolver in its shared cache."""
import argparse
import json
from pathlib import Path
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--cache', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
assert not a.output.exists(), 'Preserve previous results'
main = (a.cache / 'dyld_shared_cache_arm64').read_bytes()
assert main[88:104].hex() == '590d839a82d230f1a17d0cc053420f73', 'Unreviewed shared cache'
text = a.cache / 'dyld_shared_cache_arm64.11'
data = a.cache / 'dyld_shared_cache_arm64.33.dylddata'
text_base, text_file = 0x1a0206000, 0x522000
data_base, data_file = 0x1e7c3b070, 0x1923070

def read_text(va, count):
    with text.open('rb') as stream:
        stream.seek(text_file + va - text_base)
        return stream.read(count)

def cstring(va):
    return read_text(va, 128).split(b'\0', 1)[0].decode()

def cfstring(va):
    with data.open('rb') as stream:
        stream.seek(data_file + va - data_base)
        _, flags, ptr, length = struct.unpack('<4Q', stream.read(32))
    assert flags == 0x7c8 and length < 128
    return read_text(ptr & ((1 << 36) - 1), length).decode()

assert cfstring(0x1e7ca1490) == 'mac-address-wifi0'
names = {va: cstring(va) for va in (0x1a026e13c, 0x1a0277aa9, 0x1a0276cfa,
                                     0x1a0277aae, 0x1a0278ece)}
assert list(names.values()) == ['IODeviceTree:/chosen', 'sdio', 'wlan', 'marconi-wifi', 'IONetworkController']
cs = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
start, end = 0x1a0228284, 0x1a0228314
instructions = {i.address: (i.mnemonic, i.op_str) for i in cs.disasm(read_text(start, end-start), start)}
assert instructions[0x1a02282ac] == ('adrp', 'x0, #0x1a026e000')
assert instructions[0x1a02282b0] == ('add', 'x0, x0, #0x13c')
assert instructions[0x1a02282b4] == ('adrp', 'x1, #0x1e7ca1000')
assert instructions[0x1a02282b8] == ('add', 'x1, x1, #0x490')
assert instructions[0x1a02282c0] == ('bl', '#0x1a02078a4')
assert instructions[0x1a02282c4] == ('cbnz', 'x0, #0x1a02282f8')
for call in (0x1a02282d0, 0x1a02282e0, 0x1a02282f0):
    assert instructions[call] == ('bl', '#0x1a0230794')
assert instructions[0x1a0228308] == ('bl', '#0x1a02307a8')
fallback = {i.address: (i.mnemonic, i.op_str)
            for i in cs.disasm(read_text(0x1a0230800, 12), 0x1a0230800)}
assert fallback[0x1a0230800] == ('adrp', 'x0, #0x1a0278000')
assert fallback[0x1a0230804] == ('add', 'x0, x0, #0xece')
assert fallback[0x1a0230808] == ('bl', '#0x1a6776db4')
result = {
    'cache_uuid': main[88:104].hex(), 'image': '/usr/lib/libMobileGestalt.dylib',
    'resolver_start_unslid': hex(start), 'chosen_path': names[0x1a026e13c],
    'chosen_property_cfstring': cfstring(0x1e7ca1490),
    'chosen_internal_call': '0x1a02078a4', 'success_branch_returns': True,
    'fallback_node_names': ['sdio', 'wlan', 'marconi-wifi'],
    'fallback_function_unslid': '0x1a02307a8', 'fallback_string': names[0x1a0278ece],
    'note': 'An earlier branch can bypass this path. This is a static control-flow audit, not proof of runtime invocation, property type acceptance, timeout semantics, or cause of the device wait.'}
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
