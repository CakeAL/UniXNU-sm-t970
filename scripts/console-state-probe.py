#!/usr/bin/env python3
"""Read two console states at a previously verified SM-T970 checkpoint.

Diagnostic copies only: this terminates before gc_enable and never writes the
observed variables. Layout is pinned to the reviewed kernel, not a generic ABI.
"""
import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile


KERNEL_SHA256 = '4131d5b15cccc0a6a1697ba19e0cb59a3caced16ac09e6a8ee1823e296956444'
CAPACITY = 0x90
DELAYS = {str(code): 4 + 10 * code for code in range(4)}


def assembly():
    # bit 0: gc_initialized & 1; bit 1: PE_putc != NULL.
    # Immediate constants avoid reading a literal pool during the terminal wait.
    return '''.text
.global _start
_start:
  adrp x8, gc_initialized
  ldrb w8, [x8, :lo12:gc_initialized]
  and w8, w8, #1
  adrp x9, pe_putc
  ldr x9, [x9, :lo12:pe_putc]
  cmp x9, #0
  cset w9, ne
  orr w8, w8, w9, lsl #1
  movz x9, #0xb000
  movk x9, #0x0b71, lsl #16
  mul x2, x8, x9
  movz x9, #0xe000
  movk x9, #0x0493, lsl #16
  add x2, x2, x9
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


def patch_copy(source, output, unixnu):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != KERNEL_SHA256:
        raise ValueError('Console-state probe requires the reviewed SM-T970 kernel hash')
    if output.exists() or output.resolve() == source.resolve():
        raise ValueError('Choose a new diagnostic kernel copy')
    shared = unixnu / 'scripts/patch-xnu-entry-probe.py'
    spec = importlib.util.spec_from_file_location('shared_entry_probe', shared)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_segments(raw)
    names = module.rebase(source, raw)
    expected = {'_gc_initialized': 0xfffffff007b20e00,
                '_PE_putc': 0xfffffff0071f8c38}
    if any(names.get(name) != address for name, address in expected.items()):
        raise ValueError('Console diagnostic symbol layout changed')
    site, callee = module.find_call(raw, module.kernel_symbols(source),
                                    '_vcattach', '_gc_enable', 1)
    if site != 0xfffffff0073c4968 or callee != names['_gc_enable']:
        raise ValueError('Console diagnostic call site changed')
    cave = module.CAVES[4]
    start = module.file_offset(cave)
    end = module.file_offset(cave + CAPACITY - 1) + 1
    if end - start != CAPACITY or cave + CAPACITY > module.PANIC_CAVE_END or any(raw[start:end]):
        raise ValueError('Console diagnostic padding is unavailable')
    with tempfile.TemporaryDirectory() as tmp:
        code = module.assemble(assembly(), cave,
                               {'gc_initialized': expected['_gc_initialized'],
                                'pe_putc': expected['_PE_putc']}, Path(tmp))
    if len(code) > CAPACITY:
        raise ValueError('Console diagnostic exceeds its checked padding')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    standard = subprocess.run([sys.executable, str(shared), str(output), '--reset-after', '_gc_enable',
                               '--in', '_vcattach', '--reset-before'], check=True, capture_output=True, text=True)
    patched = bytearray(output.read_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        before = module.assemble(module.RESET_BEFORE, cave, {}, Path(tmp))
    if patched[start:start + len(before)] != before or any(patched[start + len(before):end]):
        raise ValueError('Unexpected standard before-call probe contents')
    if struct.unpack_from('<I', patched, module.file_offset(site))[0] != module.branch(site, cave):
        raise ValueError('Unexpected console diagnostic branch')
    patched[start:end] = code.ljust(CAPACITY, b'\0')
    output.write_bytes(patched)
    return {'gc_initialized_address': hex(expected['_gc_initialized']),
            'pe_putc_address': hex(expected['_PE_putc']), 'checked_call_site': hex(site),
            'code_address': hex(cave), 'code_bytes': len(code),
            'code_sha256': hashlib.sha256(code).hexdigest(),
            'entry_probe_log': standard.stdout.strip(),
            'encoding': 'code = (gc_initialized & 1) | ((PE_putc != NULL) << 1)',
            'delays_seconds': DELAYS, 'counter_hz': 19200000,
            'writes_observed_state': False, 'executes_gc_enable': False,
            'limits': 'Timing is measured after reaching the checkpoint; this is not text logging or an exception handler.'}
