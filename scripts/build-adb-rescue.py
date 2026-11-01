#!/usr/bin/env python3
"""Build a BOOT-only root ADB rescue from a pinned official recovery. Never flash."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess

EXPECTED = '2f5bbdfccba07af0524d3695f00977d3fcfc2eac994a7491e15cd15462f4bbd8'
BOOT_BYTES = 71303168


def unpack_cpio(blob):
    result = []; offset = 0
    while offset + 110 <= len(blob):
        if blob[offset:offset+6] != b'070701':
            raise ValueError('Only newc archive accepted')
        fields = [int(blob[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        offset += 110
        name_bytes = blob[offset:offset+fields[11]]
        if not name_bytes.endswith(b'\0'):
            raise ValueError('Invalid cpio name')
        name = name_bytes[:-1].decode()
        if name.startswith('/') or '..' in name.split('/'):
            raise ValueError('Unsafe archive path')
        offset = (offset + fields[11] + 3) & ~3
        data = blob[offset:offset+fields[6]]
        if len(data) != fields[6]:
            raise ValueError('Truncated archive')
        offset = (offset + fields[6] + 3) & ~3
        if name == 'TRAILER!!!':
            if any(blob[offset:]):
                raise ValueError('Unexpected trailing archive')
            return result
        result.append((name, fields, data))
    raise ValueError('Missing cpio trailer')


def pack_cpio(entries):
    out = bytearray()
    for name, original, data in entries + [('TRAILER!!!', [0]*13, b'')]:
        fields = original[:]
        name_bytes = name.encode() + b'\0'
        fields[6] = len(data); fields[11] = len(name_bytes); fields[12] = 0
        out += b'070701' + ''.join(f'{value:08x}' for value in fields).encode()
        out += name_bytes; out += bytes(-len(out) % 4)
        out += data; out += bytes(-len(out) % 4)
    out += bytes(-len(out) % 512)
    return bytes(out)


def modify(entries):
    result = []; changes = []
    for name, fields, data in entries:
        if name == 'system/etc/init/hw/init.rc':
            source = data.decode()
            service = 'service recovery /system/bin/recovery\n'
            if source.count(service) != 1:
                raise ValueError('Recovery service layout changed')
            source = source.replace(service, service + '    disabled\n')
            # Do not run recovery UI or process misc/BCB commands. Only USB ADB.
            source += '\non boot\n    setprop sys.usb.controller a600000.dwc3\n    setprop service.adb.root 1\n    setprop sys.usb.config adb\n'
            data = source.encode(); changes.append(name)
        if name == 'prop.default':
            source = data.decode()
            for old, new in [('ro.secure=1', 'ro.secure=0'), ('ro.debuggable=0', 'ro.debuggable=1'),
                             ('ro.adb.secure=1', 'ro.adb.secure=0')]:
                if source.splitlines().count(old) != 1:
                    raise ValueError('Recovery property layout changed: ' + old)
                source = source.replace('\n' + old + '\n', '\n' + new + '\n')
            data = source.encode(); changes.append(name)
        fields = fields[:]; fields[6] = len(data)
        result.append((name, fields, data))
    if len(changes) != 2:
        raise ValueError('Missing rescue inputs')
    return result, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recovery', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.recovery.read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        raise ValueError('Require exact official gts7xlwifi recovery')
    if args.output.exists():
        raise ValueError('Choose a new output')
    root = Path(__file__).resolve().parents[1]
    if subprocess.run(['git', '-C', str(root), 'check-ignore', str(args.output.resolve())], capture_output=True).returncode:
        raise ValueError('Output must be ignored')
    u32 = lambda offset: struct.unpack_from('<I', source, offset)[0]
    page = u32(36)
    if source[:8] != b'ANDROID!' or page != 4096 or u32(40) != 2 or u32(24):
        raise ValueError('Unexpected boot header')
    align = lambda size: (size + page - 1) // page * page
    kernel = source[page:page+u32(8)]
    ram_offset = page + align(u32(8))
    old_ram = source[ram_offset:ram_offset+u32(16)]
    dtbo_offset = struct.unpack_from('<Q', source, 1636)[0]
    dtbo = source[dtbo_offset:dtbo_offset+u32(1632)]
    dtb_offset = dtbo_offset + align(u32(1632))
    dtb = source[dtb_offset:dtb_offset+u32(1648)]
    if len(dtb) != u32(1648) or dtb[:4] != bytes.fromhex('d00dfeed'):
        raise ValueError('Recovery DTB layout changed')
    if kernel[56:60] != b'ARM\x64':
        raise ValueError('Expected raw AArch64 kernel')
    entries = unpack_cpio(gzip.decompress(old_ram))
    updated, changes = modify(entries)
    ramdisk = gzip.compress(pack_cpio(updated), compresslevel=6, mtime=0)
    compressed_kernel = gzip.compress(kernel, compresslevel=6, mtime=0)
    if gzip.decompress(compressed_kernel) != kernel:
        raise ValueError('Kernel compression round-trip failed')
    header = bytearray(source[:page])
    struct.pack_into('<I', header, 8, len(compressed_kernel))
    struct.pack_into('<I', header, 16, len(ramdisk))
    new_dtbo_offset = page + align(len(compressed_kernel)) + align(len(ramdisk))
    struct.pack_into('<Q', header, 1636, new_dtbo_offset)
    cmdline = (source[64:576] + source[608:1632]).split(b'\0')[0]
    cmdline += b' androidboot.mode=recovery'
    if len(cmdline) >= 1536:
        raise ValueError('Command line too long')
    header[64:576] = bytes(512); header[608:1632] = bytes(1024)
    header[64:64+min(len(cmdline),512)] = cmdline[:512]
    if len(cmdline)>512:
        header[608:608+len(cmdline)-512] = cmdline[512:]
    identity = hashlib.sha1()
    for section in (compressed_kernel, ramdisk, b'', dtbo, dtb):
        identity.update(section); identity.update(struct.pack('<I', len(section)))
    header[576:608] = identity.digest() + bytes(12)
    out = bytearray(header)
    for section in (compressed_kernel, ramdisk, dtbo, dtb):
        out += section; out += bytes(-len(out) % page)
    if len(out) > BOOT_BYTES:
        raise ValueError('Rescue does not fit BOOT')
    # Independent decode and archive comparison, including all untouched entries.
    parsed = unpack_cpio(gzip.decompress(out[page+align(len(compressed_kernel)):page+align(len(compressed_kernel))+len(ramdisk)]))
    if parsed != updated:
        raise ValueError('Packed ramdisk differs')
    if out[new_dtbo_offset:new_dtbo_offset+len(dtbo)] != dtbo:
        raise ValueError('Recovery overlay changed')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out)
    report = dict(source_recovery_sha256=EXPECTED, source_kernel_sha256=hashlib.sha256(kernel).hexdigest(),
        boot_sha256=hashlib.sha256(out).hexdigest(), boot_bytes=len(out), boot_partition_bytes=BOOT_BYTES,
        source_dtb_sha256=hashlib.sha256(dtb).hexdigest(), source_dtbo_sha256=hashlib.sha256(dtbo).hexdigest(),
        changed_ramdisk_files=changes, recovery_service_disabled=True, root_adb_usb_only=True,
        header_version=2, kernel_compression='gzip', kernel_roundtrip_verified=True,
        ramdisk_roundtrip_verified=True, recovery_partition_written=False, userdata_written=False,
        hardware_boot_verified=False,
        limitation='BOOT-only rescue candidate: gzip loader path and init/USB startup require device qualification; source official recovery preserved')
    args.output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
