#!/usr/bin/env python3
"""Rebuild a GPU addon from the shipped blob, replacing only the plugin bundle files.

The addon carries plugin, daemon, Wi-Fi/Bluetooth firmware, wallpaper and WiFi artifacts; the
plugin bundle is the only part an AdrenoMetal rebuild changes. Everything else is copied
byte-for-byte from the baseline blob so the experiment keeps one variable.
"""
import hashlib, struct, sys, zlib
from pathlib import Path

BASELINE = Path('/Users/cakeal/vsc/UniXNU-sm-t970/out/poster-assets-20261117/complete.addon')
BUNDLE = Path('/Users/cakeal/vsc/UniXNU/build/adreno-metal-plugin/NativeAdrenoMetal.bundle')
PREFIX = 'addons/NativeAdrenoMetal.bundle/'


def pad(b):
    return b + bytes(-len(b) % 8)


def main():
    stage = Path(sys.argv[1])
    raw = BASELINE.read_bytes()
    assert raw[:8] == b'NGPUADD2'
    count, _, _ = struct.unpack_from('<IIQ', raw, 8)
    off, files = 24, []
    for _ in range(count):
        plen, mode, size, csize = struct.unpack_from('<IIQQ', raw, off)
        off += 24
        pb = raw[off:off + plen]; off += len(pad(pb))
        cb = raw[off:off + csize]; off += len(pad(cb))
        files.append([pb.rstrip(b'\0').decode(), mode, zlib.decompress(cb)])
    replaced = 0
    for f in files:
        if f[0].startswith(PREFIX):
            src = BUNDLE / f[0][len(PREFIX):]
            if src.is_file():
                f[2] = src.read_bytes(); replaced += 1
    body = b''
    for path, mode, data in files:
        enc = path.encode() + b'\0'
        packed = zlib.compress(data, 9)
        body += struct.pack('<IIQQ', len(enc), mode, len(data), len(packed)) + pad(enc) + pad(packed)
    blob = b'NGPUADD2' + struct.pack('<IIQ', len(files), 0, 24 + len(body)) + body
    (stage / 'complete.addon').write_bytes(blob)
    print(f'replaced {replaced} bundle files, addon {len(blob)} bytes, sha256 {hashlib.sha256(blob).hexdigest()}')


if __name__ == '__main__':
    main()
