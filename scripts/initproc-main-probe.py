#!/usr/bin/env python3
"""Observe the genuine kern.initproc_spawned marker after its original handler."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile

SOURCE_SHA256 = 'e46326182b42f76791d00ad3671fbf77e00fda522ec2be5805e5aed0e1ba7a08'
NORMAL_SHA256 = '0b04a7823d5fa57ee0397133379f951bf9709dc5f6d32bd3039ff1a0c593451a'
SITE = 0xfffffff0076ee220
CALLEE = 0xfffffff00770f740
MARKER = 0xfffffff007b554ac
GAP = 0xfffffff0073fd48c
CAPACITY = 116
MESSAGE_VA = 0xfffffff0073fd540
MESSAGE = b'launchd main marker=%u err=%x\0'


def assembly():
    return '''.text
.global _start
_start:
  stp x29, x30, [sp, #-16]!
  mov x29, sp
  bl callee
  ldp x29, x30, [sp], #16
  adrp x9, marker
  ldr w9, [x9, :lo12:marker]
  cmp w9, #1
  b.eq report
  ret
report:
  sub sp, sp, #16
  stp x9, x0, [sp]
  adr x0, message
  bl panic
1:
  wfe
  b 1b
'''


def patch_copy(source, normal, output, unixnu):
    original, raw = source.read_bytes(), normal.read_bytes()
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256 or hashlib.sha256(raw).hexdigest() != NORMAL_SHA256:
        raise ValueError('Require both reviewed kernels')
    if output.exists() or output.resolve() in (source.resolve(), normal.resolve()):
        raise ValueError('Choose a new diagnostic copy')
    spec = importlib.util.spec_from_file_location('main_patch', unixnu / 'scripts/patch-xnu-entry-probe.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.load_segments(raw); names = m.rebase(source, original)
    if names['_sysctl_handle_int'] != CALLEE or names['_initproc_spawned'] != MARKER:
        raise ValueError('Reviewed main-marker ABI changed')
    if struct.unpack_from('<I', raw, m.file_offset(SITE))[0] != m.branch(SITE, CALLEE):
        raise ValueError('Reviewed sysctl tail branch changed')
    start, end = m.file_offset(GAP), m.file_offset(GAP + CAPACITY - 1) + 1
    text = m.file_offset(MESSAGE_VA)
    if m.ENTRY_VA + 4 != GAP or m.CAVES[1] != GAP + CAPACITY or MESSAGE_VA != m.CAVES[1] + 64:
        raise ValueError('Reviewed padding layout changed')
    if any(raw[start:end]) or any(raw[text:text + 32]):
        raise ValueError('Padding must be empty')
    if struct.unpack_from('<I', raw, text - 4)[0] != m.branch(MESSAGE_VA - 4, m.START_FIRST_CPU):
        raise ValueError('Message must follow nonreturning blue-marker branch')
    if struct.unpack_from('<I', raw, m.file_offset(names['_panic']))[0] != m.branch(names['_panic'], 0xfffffff0073fd5c0):
        raise ValueError('Qualified panic renderer changed')
    with tempfile.TemporaryDirectory() as tmp:
        code = m.assemble(assembly(), GAP, {'callee': CALLEE, 'marker': MARKER,
            'message': MESSAGE_VA, 'panic': names['_panic']}, Path(tmp))
    if len(code) > CAPACITY or len(MESSAGE) > 32:
        raise ValueError('Main-marker diagnostic exceeds padding')
    patched = bytearray(raw); patched[start:end] = code.ljust(CAPACITY, b'\0')
    patched[text:text + 32] = MESSAGE.ljust(32, b'\0')
    struct.pack_into('<I', patched, m.file_offset(SITE), m.branch(SITE, GAP))
    output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(patched)
    return {'tail_branch_site': hex(SITE), 'original_handler': hex(CALLEE),
            'marker_address': hex(MARKER), 'code_address': hex(GAP), 'code_bytes': len(code),
            'code_sha256': hashlib.sha256(code).hexdigest(), 'message': MESSAGE.rstrip(b'\0').decode(),
            'marker_written_by_probe': False, 'original_handler_arguments_unchanged': True,
            'pass_through_frame_and_lr_restored': True, 'reset_probe': False,
            'limits': 'Terminates only after original sysctl handler leaves genuine initproc_spawned=1. That marks launchd main, not service startup or a desktop. No output alone does not localize a stall.'}
