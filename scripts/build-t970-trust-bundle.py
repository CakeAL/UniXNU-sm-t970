#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Build the owner trust bundle for this tablet's GPU addon.

The addon (package/T970GpuAddon/gpu.addon, scripts/make-gpu-addon.py output) carries three signed, ad-hoc binaries the
kernel mounts under /private/var/ngpu and the userspace then loads: the NativeAdrenoMetal plugin (compositing), its Turnip
Vulkan driver and adrenoprobed. AMFI refuses all three unless their CDHashes are in the boot image's trust cache, and the
original Apple bundle (build/original-static-system-trust/original-static-system.bundle) has only Apple's two modules.

The bundle keeps the same structure DarwinBoot's ValidTrustCaches accepts: a header of one u32 module count and that many
u32 module offsets, then the modules -- here one owner module (the addon CDHashes, version 2, SHA-256 entries) followed by
both original Apple modules byte for byte. Identical in layout to UniXNU's scripts/make-owner-trust-bundle.py; the owner
module only ever adds CDHashes, so nothing Apple rejected before is accepted after.

Usage: scripts/build-t970-trust-bundle.py [--addon FILE] [--original FILE] [--output DIR]
"""
import argparse
import hashlib
import json
import struct
import sys
import uuid
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_SHA256 = '7416ca4f8377146626bb284e2133c76bee6cb4e3ee0af5d648b186235a7323a7'
DEFAULT_ORIGINAL = Path('/Users/cakeal/vsc/UniXNU/build/original-static-system-trust/original-static-system.bundle')
# What the addon must contain: the plugin whose bundle identifier the kernel's Metal device publishes, the Vulkan driver
# and the daemon the addon's launchd plists start. Names are the addon container's paths (NGPUADD2).
ADDON_BINARIES = (
    'addons/NativeAdrenoMetal.bundle/NativeAdrenoMetal',
    'addons/NativeAdrenoMetal.bundle/libvulkan_freedreno.dylib',
    'bin/adrenoprobed',
    # The wireless addon (scripts/build-t970-wifi-service.py, build-t970-bluetool.py): the supplicant the Wi-Fi service runs,
    # BlueTool and the bluetoothd the BT session's launchd job runs. Missing from a GPU-only addon and simply skipped there.
    'wifi-bin/unixnu-wpa_supplicant',
    'bt-bin/BlueTool',
    'bt-bin/bluetoothd',
)


def addon_files(data):
    """Unpack the NGPUADD2 container: u32 name length, u32 mode, u64 size, u64 packed size, name, then the data."""
    if data[:8] != b'NGPUADD2':
        raise SystemExit('not a GPU addon (scripts/make-gpu-addon.py writes the NGPUADD2 header)')
    count, _, total = struct.unpack_from('<IIQ', data, 8)
    if total != len(data):
        raise SystemExit('the addon header length disagrees with the file')
    files, at = {}, 24
    for _ in range(count):
        name_length, _, size, packed = struct.unpack_from('<IIQQ', data, at)
        name = data[at + 24:at + 24 + name_length - 1].decode()
        at += 24 + (name_length + 7) // 8 * 8
        blob = data[at:at + packed]
        at += (packed + 7) // 8 * 8
        files[name] = zlib.decompress(blob) if packed else blob
        if len(files[name]) != size:
            raise SystemExit(f'{name}: unpacked length differs from the header')
    return files


def code_directory(macho):
    """The CodeDirectory blob of an LC_CODE_SIGNATURE SuperBlob, whose SHA-256 is what AMFI compares CDHashes against."""
    magic, = struct.unpack_from('<I', macho, 0)
    if magic not in (0xfeedfacf, 0xfeedface):
        raise SystemExit('not a Mach-O image')
    header = 32 if magic == 0xfeedfacf else 28
    commands = struct.unpack_from('<I', macho, 16)[0]
    at = header
    for _ in range(commands):
        command, size = struct.unpack_from('<II', macho, at)
        if command == 0x1d:  # LC_CODE_SIGNATURE
            data_offset, data_size = struct.unpack_from('<II', macho, at + 8)
            blob = macho[data_offset:data_offset + data_size]
            super_magic, entries = struct.unpack_from('>II', blob, 0)
            if super_magic != 0xfade0cc0:
                raise SystemExit('the signature is not a SuperBlob')
            # SuperBlob = magic, length, count, then the BlobIndex array: the entries start at 12, not 8.
            for index in range(entries):
                kind, offset = struct.unpack_from('>II', blob, 12 + 8 * index)
                if kind == 0:  # CSSLOT_CODEDIRECTORY
                    directory = blob[offset:]
                    return directory[:struct.unpack_from('>I', directory, 4)[0]]
        at += size
    raise SystemExit('the image carries no CodeDirectory')


def valid_like_the_loader(data):
    """The structural checks of DarwinBoot's ValidTrustCaches, so a bundle it would refuse never leaves this script."""
    count = struct.unpack_from('<I', data)[0]
    if not 0 < count <= 128:
        return False
    for index in range(count):
        start = struct.unpack_from('<I', data, 4 + 4 * index)[0]
        end = struct.unpack_from('<I', data, 8 + 4 * index)[0] if index + 1 < count else len(data)
        if start < 4 + 4 * count or start & 3 or end > len(data) or end - start < 24 or struct.unpack_from('<I', data, start)[0] != 2:
            return False
        entries = struct.unpack_from('<I', data, start + 20)[0]
        if end - start != 24 + entries * 24:
            return False
        for entry in range(entries):
            at = start + 24 + entry * 24
            if not 1 <= data[at + 20] <= 4 or (entry and data[at - 24:at - 4] >= data[at:at + 20]):
                return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addon', type=Path, action='append', default=[],
                        help='NGPUADD2 container whose Mach-O files join the owner module (repeatable); default '
                             'package/T970GpuAddon/gpu.addon')
    parser.add_argument('--also-cdhash', action='append', default=[],
                        help='an extra 40-hex CDHash to trust (a component built by its own recipe)')
    parser.add_argument('--original', type=Path, default=DEFAULT_ORIGINAL)
    parser.add_argument('--output', type=Path, default=ROOT / 'out/trust-bundle-20261115')
    args = parser.parse_args()
    original = args.original.read_bytes()
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        raise SystemExit(f'{args.original} is not the unchanged original bundle (sha256 misplaced)')
    modules = struct.unpack_from('<I', original)[0]
    if modules != 2:
        raise SystemExit('the original bundle no longer holds exactly Apple\'s two modules')
    offsets = struct.unpack_from('<2I', original, 4)
    originals = [original[offsets[0]:offsets[1]], original[offsets[1]:]]
    addons = args.addon or [ROOT / 'package/T970GpuAddon/gpu.addon']
    cdhashes = {}
    for addon in addons:
        files = addon_files(addon.read_bytes())
        for name in [n for n in ADDON_BINARIES if n in files]:
            directory = code_directory(files[name])
            cdhashes[f'{addon.name}:{name}'] = hashlib.sha256(directory).hexdigest()[:40]
    for value in args.also_cdhash:
        if len(value) != 40 or any(c not in '0123456789abcdef' for c in value):
            raise SystemExit(f'{value} is not a 40-hex CDHash')
        cdhashes[f'--also-cdhash:{value}'] = value
    if not cdhashes:
        raise SystemExit('no CDHash found: name the addons that carry the binaries')
    hashes = sorted({bytes.fromhex(value) for value in cdhashes.values()})
    if len(hashes) != len(cdhashes):
        raise SystemExit('two addon binaries share a CDHash')
    identifier = uuid.uuid5(uuid.NAMESPACE_URL, 'org.blu-sharky.adreno-metal:' + ''.join(value.hex() for value in hashes))
    own = struct.pack('<I16sI', 2, identifier.bytes, len(hashes)) + b''.join(value + bytes([2, 0, 0, 0]) for value in hashes)
    parts = [own, *originals]
    starts, cursor = [], 4 + 4 * len(parts)
    for part in parts:
        starts.append(cursor)
        cursor += len(part)
    bundle = struct.pack(f'<{len(parts) + 1}I', len(parts), *starts) + b''.join(parts)
    if not valid_like_the_loader(bundle):
        raise SystemExit('the bundle would be refused by the boot loader')
    if bundle[-len(originals[0]) - len(originals[1]):] != b''.join(originals):
        raise SystemExit('the original Apple modules did not survive byte for byte')
    args.output.mkdir(parents=True, exist_ok=True)
    out = args.output / 'owner-trust.bundle'
    out.write_bytes(bundle)
    report = {
        'addons': [{'path': str(a), 'sha256': hashlib.sha256(a.read_bytes()).hexdigest(), 'bytes': a.stat().st_size}
                   for a in addons],
        'original_bundle_sha256': ORIGINAL_SHA256, 'original_modules_unchanged': True, 'modules': len(parts),
        'own_cdhashes': {name: value for name, value in cdhashes.items()},
        'bundle': str(out), 'bundle_sha256': hashlib.sha256(bundle).hexdigest(), 'bundle_bytes': len(bundle),
        'apple_trust_chain_verified': False,
        'hardware_tested': False,
        'purpose': 'owner trust for this tablet\'s GPU addon: NativeAdrenoMetal, Turnip and adrenoprobed',
    }
    (args.output / 'owner-trust.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(parts)} trust modules, {len(hashes)} owner CDHashes, {len(bundle)} bytes, '
          f'SHA-256 {report["bundle_sha256"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
