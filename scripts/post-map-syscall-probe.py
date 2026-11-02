#!/usr/bin/env python3
"""Observe a later PID1 syscall after the existing trace recorded sc536 e0."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile

SOURCE_SHA256 = 'e46326182b42f76791d00ad3671fbf77e00fda522ec2be5805e5aed0e1ba7a08'
NORMAL_SHA256 = '0b04a7823d5fa57ee0397133379f951bf9709dc5f6d32bd3039ff1a0c593451a'
CALL_SITE = 0xfffffff00783b4b4
CALLEE = 0xfffffff00783b590
GAP = 0xfffffff0073fd48c
CAPACITY = 116
MESSAGE_VA = 0xfffffff0073fd540
MESSAGE = b'postmap sc=%u err=%x\0'
DATA = MESSAGE.ljust(24, b'\0') + b'sc536 e0'


def assembly():
    return '''.text
.global _start
_start:
  cmp w24, #1
  b.ne pass
  adrp x9, trace_count
  ldr w9, [x9, :lo12:trace_count]
  cbz w9, pass
  sub w9, w9, #1
  mov w10, #24
  udiv w11, w9, w10
  msub w9, w11, w10, w9
  adrp x10, trace_rows
  add x10, x10, :lo12:trace_rows
  add x11, x10, x9, lsl #7
  ldr w9, [x11]
  ldr w11, [x11, #4]
  orr x9, x9, x11, lsl #32
  ldr x10, signature
  cmp x9, x10
  b.eq report
pass:
  adrp x30, continuation
  add x30, x30, :lo12:continuation
  b callee
report:
  sub sp, sp, #16
  stp x1, x2, [sp]
  adr x0, message
  bl panic
1:
  wfe
  b 1b
'''


def patch_copy(source, normal, output, unixnu):
    original, raw = source.read_bytes(), normal.read_bytes()
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256 or hashlib.sha256(raw).hexdigest() != NORMAL_SHA256:
        raise ValueError('Require both reviewed source and normal panic kernel')
    if output.exists() or output.resolve() in (source.resolve(), normal.resolve()):
        raise ValueError('Choose a new diagnostic copy')
    spec = importlib.util.spec_from_file_location('postmap_patch', unixnu / 'scripts/patch-xnu-entry-probe.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.load_segments(raw); names = m.rebase(source, original)
    site, callee = m.find_call(raw, m.kernel_symbols(source), '_unix_syscall', '_native_t970_cache_syscall_note', 1)
    if (site, callee) != (CALL_SITE, CALLEE) or m.ENTRY_VA + 4 != GAP or m.CAVES[1] != GAP + CAPACITY:
        raise ValueError('Reviewed callback/entry layout changed')
    if names['_native_t970_cache_count'] != 0xfffffff007b5a8c0 or names['_native_t970_cache_rows'] != 0xfffffff007b5a8c4:
        raise ValueError('Reviewed24x128 trace layout changed')
    start, end = m.file_offset(GAP), m.file_offset(GAP + CAPACITY - 1) + 1
    text = m.file_offset(MESSAGE_VA)
    if any(raw[start:end]) or any(raw[text:text + 32]) or MESSAGE_VA != m.CAVES[1] + 64:
        raise ValueError('Reviewed nonexecuted padding is not empty')
    if struct.unpack_from('<I', raw, text - 4)[0] != m.branch(MESSAGE_VA - 4, m.START_FIRST_CPU):
        raise ValueError('Blue marker must branch away before message data')
    if struct.unpack_from('<I', raw, m.file_offset(names['_panic']))[0] != m.branch(names['_panic'], 0xfffffff0073fd5c0):
        raise ValueError('Qualified panic renderer changed')
    symbols = {'callee': callee, 'continuation': site + 4, 'panic': names['_panic'],
               'message': MESSAGE_VA, 'signature': MESSAGE_VA + 24,
               'trace_count': names['_native_t970_cache_count'], 'trace_rows': names['_native_t970_cache_rows']}
    with tempfile.TemporaryDirectory() as tmp:
        code = m.assemble(assembly(), GAP, symbols, Path(tmp))
    if len(code) > CAPACITY:
        raise ValueError('Post-map stub exceeds padding')
    patched = bytearray(raw); patched[start:end] = code.ljust(CAPACITY, b'\0')
    patched[text:text + 32] = DATA
    struct.pack_into('<I', patched, m.file_offset(site), m.branch(site, GAP))
    output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(patched)
    return {'checked_call_site': hex(site), 'code_address': hex(GAP), 'code_bytes': len(code),
            'code_sha256': hashlib.sha256(code).hexdigest(), 'message_address': hex(MESSAGE_VA),
            'message': MESSAGE.rstrip(b'\0').decode(), 'predicate': 'W24 PID=1 and last existing tracked row starts sc536 e0',
            'trace_reads_only': True, 'passthrough_original_callback_and_lr': True, 'reset_probe': False,
            'limits': 'Shows a later PID1 BSD call result only when prior successful cache syscall536 was recorded. Does not prove launchd main. No message alone does not locate a stall.'}
