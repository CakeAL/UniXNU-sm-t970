#!/usr/bin/env python3
"""Display the real mapping return code through a reviewed panic-renderer copy."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile

SOURCE_SHA256 = 'e46326182b42f76791d00ad3671fbf77e00fda522ec2be5805e5aed0e1ba7a08'
NORMAL_SHA256 = '0b04a7823d5fa57ee0397133379f951bf9709dc5f6d32bd3039ff1a0c593451a'
CALL_SITE = 0xfffffff00778fa00
CALLEE = 0xfffffff0073ab774
GAP = 0xfffffff0073fd48c
CAPACITY = 116


def assembly():
    # Darwin ARM64 variadic arguments are on the caller's stack. The qualified
    # panic renderer takes that exact SP; do not pass the integer in X1.
    return '''.text
.global _start
_start:
  bl callee
  mov w0, w0
  sub sp, sp, #16
  str x0, [sp]
  adr x0, message
  bl panic
1:
  wfe
  b 1b
message:
  .asciz "diagnostic: dyld shared map kr=%d"
  .balign 4
'''


def patch_copy(source, normal, output, unixnu):
    source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError('Require reviewed source kernel')
    raw = normal.read_bytes()
    if hashlib.sha256(raw).hexdigest() != NORMAL_SHA256:
        raise ValueError('Require reviewed normal panic-renderer kernel')
    if output.exists() or output.resolve() in (source.resolve(), normal.resolve()):
        raise ValueError('Choose a new diagnostic copy')
    spec = importlib.util.spec_from_file_location('shared_map_patch', unixnu / 'scripts/patch-xnu-entry-probe.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_segments(raw)
    # Derive entry/MMU addresses from the uninstrumented source. The qualified
    # normal copy already branches around the original SCTLR entry sequence.
    names = module.rebase(source, source_bytes)
    site, callee = module.find_call(raw, module.kernel_symbols(source),
                                   '__shared_region_map_and_slide', '_vm_shared_region_map_file', 1)
    if (site, callee) != (CALL_SITE, CALLEE) or module.ENTRY_VA + 4 != GAP or module.CAVES[1] != GAP + CAPACITY:
        raise ValueError('Reviewed mapping call or entry padding changed')
    start = module.file_offset(GAP)
    end = module.file_offset(GAP + CAPACITY - 1) + 1
    if end - start != CAPACITY or any(raw[start:end]):
        raise ValueError('Entry padding is not empty')
    panic = names['_panic']
    word = struct.unpack_from('<I', raw, module.file_offset(panic))[0]
    if word != module.branch(panic, 0xfffffff0073fd5c0):
        raise ValueError('Reviewed panic renderer entry changed')
    with tempfile.TemporaryDirectory() as tmp:
        code = module.assemble(assembly(), GAP, {'callee': callee, 'panic': panic}, Path(tmp))
    if len(code) > CAPACITY:
        raise ValueError('Mapping-result stub exceeds padding')
    patched = bytearray(raw)
    patched[start:end] = code.ljust(CAPACITY, b'\0')
    struct.pack_into('<I', patched, module.file_offset(site), module.branch(site, GAP))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched)
    return {'normal_kernel_sha256': NORMAL_SHA256, 'checked_call_site': hex(site),
            'callee': hex(callee), 'code_address': hex(GAP), 'code_bytes': len(code),
            'code_sha256': hashlib.sha256(code).hexdigest(), 'panic_address': hex(panic),
            'message': 'diagnostic: dyld shared map kr=%d', 'darwin_stack_argument': True,
            'calls_original_callee': True, 'reset_probe': False,
            'limits': 'Deliberate terminal diagnostic panic after mapping returns. kr=0 means KERN_SUCCESS for this call, not launchd main or later userland. No display does not alone locate failure.'}
