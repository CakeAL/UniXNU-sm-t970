#!/usr/bin/env python3
"""Repack the qualified normal BOOT with a larger EFI-owned memory request.

Only /chosen/darwinboot-memory-size changes in the ADT. --confirm-main also
inserts the reviewed terminal main observer. This does not declare
physical RAM, change reserved regions, enable storage writes, or flash a device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

from importlib.util import spec_from_file_location, module_from_spec

DEVICE = Path(__file__).resolve().parents[1]
BASE = DEVICE / 'out/step7/probes/policy-release-normal'
BASE_HASH = '73a5738beb948edc90b9d0357663a62a3e672e8a3ee75aaf7bd90aad699ecbba'
KERNEL_HASH = '0b04a7823d5fa57ee0397133379f951bf9709dc5f6d32bd3039ff1a0c593451a'
PARTITION_BYTES = 71303168


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def replace_request(blob, size):
    """Walk the serialized ADT, permitting exactly one reviewed 64-bit value."""
    changed = bytearray(blob)
    found = []

    def node(offset, parent, root=False):
        count, children = struct.unpack_from('<II', blob, offset)
        offset += 8
        props = {}
        for _ in range(count):
            key, length = struct.unpack_from('<32sI', blob, offset)
            offset += 36
            key = key.split(b'\0', 1)[0].decode()
            require(key not in props and offset + length <= len(blob), 'Invalid ADT property')
            props[key] = (offset, blob[offset:offset + length])
            offset += (length + 3) & ~3
        name = props['name'][1].rstrip(b'\0').decode()
        path = '' if root else parent + '/' + name
        if 'darwinboot-memory-size' in props:
            pos, old = props['darwinboot-memory-size']
            require(path == '/chosen' and old == struct.pack('<Q', 0x10000000),
                    'Not the qualified 256 MiB chosen property')
            changed[pos:pos + 8] = struct.pack('<Q', size)
            found.append(pos)
        for _ in range(children):
            offset = node(offset, path)
        return offset

    require(node(0, '', True) == len(blob) and len(found) == 1, 'Invalid ADT/request count')
    return bytes(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mib', type=int, choices=(512, 1024, 2048), default=512)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--confirm-main', action='store_true',
                        help='Use the reviewed terminal main observer to measure runtime pages')
    args = parser.parse_args()
    out = args.output.resolve()
    require(not out.exists(), 'Output must be new; prior images are preserved')
    source = (BASE / 'boot-partition.img').read_bytes()
    require(len(source) == PARTITION_BYTES and digest(source) == BASE_HASH, 'Unqualified source BOOT')
    require(source[:8] == b'ANDROID!', 'Missing Android header')
    kernel_size, = struct.unpack_from('<I', source, 8)
    ramdisk_size, = struct.unpack_from('<I', source, 16)
    page, version = struct.unpack_from('<II', source, 36)
    require(page == 4096 and version == 2, 'Requires qualified header v2/4096')
    ramdisk_offset = page + ((kernel_size + page - 1) // page) * page
    payload = (BASE / 'payload.img').read_bytes()
    require(len(payload) == ramdisk_size and source[ramdisk_offset:ramdisk_offset + ramdisk_size] == payload,
            'Payload differs from qualified BOOT')
    out.mkdir(parents=True)
    image = out / 'payload.img'
    shutil.copyfile(BASE / 'payload.img', image)
    files = ('kernel.macho', 'kernel.macho.adt', 'kernel.macho.trustcache')
    original = {}
    for name in files:
        target = out / name
        subprocess.run(['mcopy', '-i', str(image), '::/EFI/UniXNU/Payloads/' + name, str(target)], check=True)
        original[name] = target.read_bytes()
    require(digest(original['kernel.macho']) == KERNEL_HASH, 'Not the qualified normal kernel')
    adt = replace_request(original['kernel.macho.adt'], args.mib * 1024**2)
    spec = spec_from_file_location('platform_check', DEVICE / 'scripts/check-platform.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    before, after = module.decode_adt(original['kernel.macho.adt']), module.decode_adt(adt)
    before['/chosen']['darwinboot-memory-size'] = struct.pack('<Q', args.mib * 1024**2)
    require(before == after, 'Unexpected ADT change')
    (out / 'kernel.macho.adt').write_bytes(adt)
    subprocess.run(['mcopy', '-o', '-i', str(image), str(out / 'kernel.macho.adt'),
                    '::/EFI/UniXNU/Payloads/kernel.macho.adt'], check=True)
    main_probe = None
    expected_kernel = original['kernel.macho']
    if args.confirm_main:
        probe_spec = spec_from_file_location('main_probe', DEVICE / 'scripts/initproc-main-probe.py')
        probe = module_from_spec(probe_spec)
        probe_spec.loader.exec_module(probe)
        framework = DEVICE.parent / 'UniXNU'
        source_kernel = framework / 'out/sm-t970/ipados-17.7.11-21H461/sm-t970/kernel/kernel.macho'
        patched = out / 'main-kernel.macho'
        main_probe = probe.patch_copy(source_kernel, out / 'kernel.macho', patched, framework)
        expected_kernel = patched.read_bytes()
        subprocess.run(['mcopy', '-o', '-i', str(image), str(patched),
                        '::/EFI/UniXNU/Payloads/kernel.macho'], check=True)
    verify = out / 'independent'
    verify.mkdir()
    for name in files:
        subprocess.run(['mcopy', '-i', str(image), '::/EFI/UniXNU/Payloads/' + name, str(verify / name)], check=True)
        expected = adt if name.endswith('.adt') else expected_kernel if name == 'kernel.macho' else original[name]
        require((verify / name).read_bytes() == expected,
                'Payload round-trip mismatch: ' + name)
    config = subprocess.check_output(['mtype', '-i', str(image), '::/EFI/UniXNU/unixnu.toml'])
    require(config == (BASE / 'unixnu.toml').read_bytes(), 'Command line/config changed')
    new_payload = image.read_bytes()
    require(len(new_payload) == ramdisk_size, 'Payload resized')
    result = bytearray(source)
    result[ramdisk_offset:ramdisk_offset + ramdisk_size] = new_payload
    require(result[:ramdisk_offset] == source[:ramdisk_offset]
            and result[ramdisk_offset + ramdisk_size:] == source[ramdisk_offset + ramdisk_size:],
            'Header, firmware, DTB, or tail changed')
    (out / 'boot-partition.img').write_bytes(result)
    report = dict(source_boot_sha256=BASE_HASH, boot_sha256=digest(result), boot_bytes=len(result),
                  requested_owned_mib=args.mib, adt_sha256=digest(adt), kernel_sha256=digest(expected_kernel),
                  payload_sha256=digest(new_payload), ramdisk_offset=ramdisk_offset,
                  no_terminal_probe=not args.confirm_main, command_line_unchanged=True, firmware_dtb_header_tail_unchanged=True,
                  adt_only_chosen_memory_size_changed=True, board_defaults_unchanged=True,
                  hardware_allocation_verified=False, flashed=False,
                  limitation='EFI must allocate a real conventional-memory run. No Data volume is configured.')
    if main_probe:
        report['initproc_main'] = main_probe
    (out / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
