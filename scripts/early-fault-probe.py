#!/usr/bin/env python3
"""Bounded fault classification for one pre-interrupt SM-T970 checkpoint.

This is a destructive-to-execution diagnostic COPY, never a normal kernel:
synchronous faults/SError/panic terminate instead of executing their handlers.
IRQ/FIQ and reserved vector slots are preserved byte-for-byte.
"""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


KERNEL_SHA256 = 'bfb50a1a009f4dd08d54cb94d6187d768c7a5ef976427abd235756874f38473c'
DELAYS = {'synchronous': 20, 'SError': 30, 'panic': 40, 'BRK': 50}
CAPACITY = 0x100


def assembly():
    return '''.text
.global _start, sync_guard, serror_guard, panic_guard
_start:
sync_guard:
  mrs x9, esr_el1
  lsr x9, x9, #26
  cmp x9, #0x3c
  mov w8, #20
  mov w10, #50
  csel w8, w10, w8, eq
  b terminal
serror_guard:
  mov w8, #30
  b terminal
panic_guard:
  mov w8, #40
terminal:
  msr daifset, #15
  movz x9, #0xf800
  movk x9, #0x0124, lsl #16
  mul x2, x8, x9
  mrs x1, cntpct_el0
  add x2, x1, x2
1:
  isb
  mrs x1, cntpct_el0
  cmp x1, x2
  b.lo 1b
  movz w0, #0x0009
  movk w0, #0x8400, lsl #16
  mov x1, xzr
  mov x2, xzr
  mov x3, xzr
  smc #0
2:
  wfe
  b 2b
'''


def assemble_guard(module, address, work):
    code = module.assemble(assembly(), address, {}, work)
    nm = shutil.which('llvm-nm') or '/opt/homebrew/opt/llvm/bin/llvm-nm'
    entries = {}
    for line in subprocess.check_output([nm, '-n', str(work / 'cave.elf')], text=True).splitlines():
        parts = line.split()
        if len(parts) == 3:
            entries[parts[2]] = int(parts[0], 16)
    return code, {name: entries[name] for name in ('sync_guard', 'serror_guard', 'panic_guard')}


def selected_vectors(module, data, names):
    base = names['_ExceptionVectorsBase']
    # Validate the actual bootstrap ADRP/ADD and conversion to KVA before MSR
    # VBAR_EL1. Checking only LowExceptionVectorBase would guard the wrong table.
    matches = []
    for va in range(names['_start_first_cpu'], names['_start_first_cpu'] + 0x2000, 4):
        words = struct.unpack_from('<5I', data, module.file_offset(va))
        adrp, add, convert, subtract, msr = words
        if adrp & 0x9f00001f != 0x90000000 or add & 0xffc003ff != 0x91000000:
            continue
        immediate = ((adrp >> 5) & 0x7ffff) << 2 | ((adrp >> 29) & 3)
        if immediate & (1 << 20):
            immediate -= 1 << 21
        target = (va & ~0xfff) + (immediate << 12) + ((add >> 10) & 0xfff)
        if target == base and (convert, subtract, msr) == (0x8b160000, 0xcb170000, 0xd518c000):
            matches.append(va)
    if len(matches) != 1:
        raise ValueError('Require one audited active-vector selection in bootstrap')
    for slot in range(12):
        word = struct.unpack_from('<I', data, module.file_offset(base + slot * 0x80))[0]
        if word >> 26 != 0b000101:
            raise ValueError('Unexpected active exception vector entry')
    return base, matches[0]


def patch_copy(source, output, unixnu, delay):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != KERNEL_SHA256:
        raise ValueError('Early fault probe requires the reviewed repaired SM-T970 kernel')
    if output.exists() or output.resolve() == source.resolve() or not 1 <= delay <= 8:
        raise ValueError('Use a new copy and a normal delay of 1..8 seconds')
    shared = unixnu / 'scripts/patch-xnu-entry-probe.py'
    spec = importlib.util.spec_from_file_location('shared_early_probe', shared)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_segments(raw)
    names = module.rebase(source, raw)
    vectors, selection = selected_vectors(module, raw, names)
    site, _ = module.find_call(raw, module.kernel_symbols(source), '_arm_init', '_PE_create_console', 1)
    guard = module.CAVES[4] + module.CAVE_SIZE
    start = module.file_offset(guard)
    end = module.file_offset(guard + CAPACITY - 1) + 1
    if end - start != CAPACITY or guard + CAPACITY > module.PANIC_CAVE_END or any(raw[start:end]):
        raise ValueError('Early fault diagnostic padding is unavailable')
    with tempfile.TemporaryDirectory() as tmp:
        code, entries = assemble_guard(module, guard, Path(tmp))
    if len(code) > CAPACITY:
        raise ValueError('Early fault diagnostic exceeds its checked padding')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    standard = subprocess.run([sys.executable, str(shared), str(output), '--reset-after', '_PE_create_console',
                               '--in', '_arm_init', '--reset-delay', str(delay)],
                              check=True, capture_output=True, text=True)
    data = bytearray(output.read_bytes())
    if any(data[start:end]):
        raise ValueError('Standard probe overlaps early fault diagnostic padding')
    data[start:end] = code.ljust(CAPACITY, b'\0')
    changes = []
    for slot in (0, 3, 4, 7, 8, 11):
        va = vectors + slot * 0x80
        target = entries['sync_guard' if slot % 4 == 0 else 'serror_guard']
        struct.pack_into('<I', data, module.file_offset(va), module.branch(va, target))
        changes.append(hex(va))
    for name in ('_panic', '_panic_trap_to_debugger'):
        va = names[name]
        struct.pack_into('<I', data, module.file_offset(va), module.branch(va, entries['panic_guard']))
        changes.append(hex(va))
    for slot in (1, 2, 5, 6, 9, 10, 12, 13, 14, 15):
        at = module.file_offset(vectors + slot * 0x80)
        if data[at:at + 0x80] != raw[at:at + 0x80]:
            raise ValueError('IRQ/FIQ or reserved vector slot was modified')
    output.write_bytes(data)
    return {'active_vectors_address': hex(vectors), 'bootstrap_selection': hex(selection),
            'guard_address': hex(guard), 'guard_bytes': len(code),
            'guard_sha256': hashlib.sha256(code).hexdigest(),
            'entries': {key: hex(value) for key, value in entries.items()},
            'modified_entries': changes, 'IRQ_FIQ_and_reserved_slots_preserved': True,
            'normal_return_delay_seconds': delay, 'fault_delays_seconds': DELAYS,
            'entry_probe_log': standard.stdout.strip(), 'counter_hz': 19200000,
            'limits': 'Pre-interrupt diagnostic only. No device BRK control yet, no register/text capture, and no recovery from a plain spin loop or inaccessible diagnostic code.'}
