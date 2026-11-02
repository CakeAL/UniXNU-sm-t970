#!/usr/bin/env python3
"""Observe genuine main plus Data and RAM watchdog policy state; terminal, no reset."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import argparse
import json
import subprocess

SOURCE_SHA256 = '39d7cfe12e77cb7d5b8f9a54488c9abb94222051d3d333219d9afb9f75c3b510'
NORMAL_SHA256 = '7ad48eaeebac57cc6d2e693abeffe6f20afcbc1b02a383c03958d91bca31110a'
SITE = 0xfffffff0076f8874
CALLEE = 0xfffffff007719d94
MARKER = 0xfffffff007b614b4
GAP = 0xfffffff00740548c
CAPACITY = 116
MESSAGE_VA = 0xfffffff007405540
DATA_STATUS = 0xfffffff007a70f60
POLICY_STATUS = 0xfffffff007a70f88
POLICY_STAGE = 0xfffffff007b09f08
MESSAGE = b'main=%u e=%d D=%d W=%d S=%d\0'


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
  sub sp, sp, #48
  stp x9, x0, [sp]
  adrp x10, data_status
  ldr w10, [x10, :lo12:data_status]
  adrp x11, policy_status
  ldr w11, [x11, :lo12:policy_status]
  stp x10, x11, [sp, #16]
  adrp x12, policy_stage
  ldr w12, [x12, :lo12:policy_stage]
  str x12, [sp, #32]
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
    if any(names.get(k) != v for k, v in {'_sysctl_handle_int': CALLEE, '_initproc_spawned': MARKER,
            '_native_owner_data_status': DATA_STATUS, '_native_t970_watchdog_policy_status': POLICY_STATUS,
            '_native_t970_watchdog_policy_stage': POLICY_STAGE}.items()):
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
    if struct.unpack_from('<I', raw, m.file_offset(names['_panic']))[0] != m.branch(names['_panic'], 0xfffffff0074055c0):
        raise ValueError('Qualified panic renderer changed')
    with tempfile.TemporaryDirectory() as tmp:
        code = m.assemble(assembly(), GAP, {'callee': CALLEE, 'marker': MARKER,
            'message': MESSAGE_VA, 'panic': names['_panic'], 'data_status': DATA_STATUS,
            'policy_status': POLICY_STATUS, 'policy_stage': POLICY_STAGE}, Path(tmp))
    if len(code) > CAPACITY or len(MESSAGE) > 32:
        raise ValueError('Main-marker diagnostic exceeds padding')
    patched = bytearray(raw); patched[start:end] = code.ljust(CAPACITY, b'\0')
    patched[text:text + 32] = MESSAGE.ljust(32, b'\0')
    struct.pack_into('<I', patched, m.file_offset(SITE), m.branch(SITE, GAP))
    output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(patched)
    return {'tail_branch_site': hex(SITE), 'original_handler': hex(CALLEE),
            'marker_address': hex(MARKER), 'code_address': hex(GAP), 'code_bytes': len(code),
            'code_sha256': hashlib.sha256(code).hexdigest(), 'message': MESSAGE.rstrip(b'\0').decode(),
            'marker_written_by_probe': False, 'data_or_policy_written_by_probe': False,
            'observed_globals': {'D': hex(DATA_STATUS), 'W': hex(POLICY_STATUS), 'S': hex(POLICY_STAGE)}, 'original_handler_arguments_unchanged': True,
            'pass_through_frame_and_lr_restored': True, 'reset_probe': False,
            'limits': 'Terminates only after original sysctl handler leaves genuine initproc_spawned=1. D=Data error, W=policy error, S=policy stage; 0/0/4 proves kernel completed policy installation. Does not prove launchd accepted the override or later service startup. No output alone does not localize a stall.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    device = Path(__file__).resolve().parents[1]
    framework = device.parent / 'UniXNU'
    base = device / 'out/data-bringup/watchdog-policy-verified/boot-partition.img'
    source = device / 'out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data/kernel/kernel.macho'
    raw = base.read_bytes()
    if hashlib.sha256(raw).hexdigest() != '2387e904a86fb48ca64aeabe4a91568721d97e18a34fc47f5f3e484e257b44cb':
        raise ValueError('Require qualified policy BOOT2387e904')
    if args.output.exists():
        raise ValueError('Choose a new output directory')
    args.output.mkdir(parents=True)
    kernel_size = struct.unpack_from('<I', raw, 8)[0]
    ramdisk_size = struct.unpack_from('<I', raw, 16)[0]
    page, version = struct.unpack_from('<II', raw, 36)
    if (page, version, len(raw)) != (4096, 2, 71303168):
        raise ValueError('Unexpected qualified BOOT geometry')
    start = page + ((kernel_size + page - 1) // page) * page
    image = args.output / 'payload.img'
    image.write_bytes(raw[start:start + ramdisk_size])
    names = ('kernel.macho', 'kernel.macho.adt', 'kernel.macho.trustcache', 'scratch-data.img')
    originals = {}
    for name in names:
        path = args.output / name
        subprocess.run(['mcopy', '-i', str(image), '::/EFI/UniXNU/Payloads/' + name, str(path)], check=True)
        originals[name] = path.read_bytes()
    config = subprocess.check_output(['mtype', '-i', str(image), '::/EFI/UniXNU/unixnu.toml'])
    output = args.output / 'diagnostic/kernel.macho'
    probe = patch_copy(source, args.output / 'kernel.macho', output, framework)
    subprocess.run(['mcopy', '-o', '-i', str(image), str(output), '::/EFI/UniXNU/Payloads/kernel.macho'], check=True)
    independent = args.output / 'independent'
    independent.mkdir()
    for name in names:
        path = independent / name
        subprocess.run(['mcopy', '-i', str(image), '::/EFI/UniXNU/Payloads/' + name, str(path)], check=True)
        if path.read_bytes() != (output.read_bytes() if name == 'kernel.macho' else originals[name]):
            raise ValueError('FAT verification failed: ' + name)
    if config != subprocess.check_output(['mtype', '-i', str(image), '::/EFI/UniXNU/unixnu.toml']):
        raise ValueError('Configuration changed')
    payload = image.read_bytes()
    if len(payload) != ramdisk_size:
        raise ValueError('Payload resized')
    result = bytearray(raw)
    result[start:start + ramdisk_size] = payload
    if result[:start] != raw[:start] or result[start + ramdisk_size:] != raw[start + ramdisk_size:]:
        raise ValueError('Header/firmware/DTB/tail changed')
    (args.output / 'boot-partition.img').write_bytes(result)
    report = dict(base_boot_sha256=hashlib.sha256(raw).hexdigest(), boot_sha256=hashlib.sha256(result).hexdigest(),
                  boot_bytes=len(result), diagnostic_kernel_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  probe=probe, adt_trust_seed_config_unchanged=True, header_fd_dtb_tail_unchanged=True,
                  terminal_diagnostic=True, reset_probe=False, hardware_result_pending=True)
    (args.output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
