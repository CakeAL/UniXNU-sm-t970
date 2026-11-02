#!/usr/bin/env python3
"""Terminal exec-return status probe for one reviewed SM-T970 kernel copy."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

KERNEL_SHA256 = 'e46326182b42f76791d00ad3671fbf77e00fda522ec2be5805e5aed0e1ba7a08'
CAPACITY = 0x60
CALL_SITE = 0xfffffff0076e90ac
CALLEE = 0xfffffff0076e830c
DELAYS = {'return_zero': 6, 'return_nonzero': 16}


def assembly():
    zero, nonzero = (DELAYS[k] * 19200000 for k in ('return_zero', 'return_nonzero'))
    return f'''.text
.global _start
_start:
  bl callee
  cbz w0, 1f
  movz x2, #{nonzero & 65535}
  movk x2, #{nonzero >> 16}, lsl #16
  b 2f
1:
  movz x2, #{zero & 65535}
  movk x2, #{zero >> 16}, lsl #16
2:
  mrs x1, cntpct_el0
  add x2, x1, x2
3:
  isb
  mrs x1, cntpct_el0
  cmp x1, x2
  b.lo 3b
  movz w0, #9
  movk w0, #0x8400, lsl #16
  mov x1, xzr
  mov x2, xzr
  mov x3, xzr
  smc #0
4:
  wfe
  b 4b
'''


def patch_copy(source, output, unixnu):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != KERNEL_SHA256:
        raise ValueError('Exec-status probe requires the reviewed source kernel')
    if output.exists() or output.resolve() == source.resolve():
        raise ValueError('Choose a new diagnostic copy')
    shared = unixnu / 'scripts/patch-xnu-entry-probe.py'
    spec = importlib.util.spec_from_file_location('shared_exec_probe', shared)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_segments(raw)
    module.rebase(source, raw)
    site, callee = module.find_call(raw, module.kernel_symbols(source),
                                    '_load_init_program_at_path', '___mac_execve', 1)
    if (site, callee) != (CALL_SITE, CALLEE):
        raise ValueError('Reviewed exec call layout changed')
    cave = module.CAVES[4]
    start = module.file_offset(cave)
    end = module.file_offset(cave + CAPACITY - 1) + 1
    if end - start != CAPACITY or cave + CAPACITY > module.PANIC_CAVE_END or any(raw[start:end]):
        raise ValueError('Exec diagnostic padding unavailable')
    with tempfile.TemporaryDirectory() as tmp:
        code = module.assemble(assembly(), cave, {'callee': callee}, Path(tmp))
    if len(code) > CAPACITY:
        raise ValueError('Exec diagnostic exceeds checked padding')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    standard = subprocess.run([sys.executable, str(shared), str(output), '--reset-after',
        '___mac_execve', '--in', '_load_init_program_at_path', '--reset-before'],
        check=True, capture_output=True, text=True)
    patched = bytearray(output.read_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        before = module.assemble(module.RESET_BEFORE, cave, {}, Path(tmp))
    if patched[start:start + len(before)] != before or any(patched[start + len(before):end]):
        raise ValueError('Unexpected temporary before-call contents')
    if struct.unpack_from('<I', patched, module.file_offset(site))[0] != module.branch(site, cave):
        raise ValueError('Unexpected exec diagnostic branch')
    patched[start:end] = code.ljust(CAPACITY, b'\0')
    output.write_bytes(patched)
    return {'checked_call_site': hex(site), 'callee': hex(callee), 'code_address': hex(cave),
            'code_bytes': len(code), 'code_sha256': hashlib.sha256(code).hexdigest(),
            'entry_probe_log': standard.stdout.strip(), 'delays_seconds': DELAYS,
            'encoding': 'Inspect W0 immediately after original ___mac_execve returns: zero6seconds, nonzero16seconds',
            'counter_hz': 19200000, 'calls_original_callee': True,
            'limits': 'Terminal probe; zero return does not prove launchd main, full cache mapping or later userland. No reset alone does not localize failure.'}
