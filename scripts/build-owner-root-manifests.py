#!/usr/bin/env python3
"""Sign the OS and SystemOS root windows as owner policy envelopes.

The kernel cannot carry these manifests: 73,285,920 bytes of block hashes would push the packed
BOOT image past the 71,303,168-byte partition. They are written to a fixed userdata region after
the root image instead, and the kernel links only the owner public key and authenticates each
envelope with vr_open before any window may be published.

Use the exact raw deployment image when available. Legacy sparse inputs are accepted only if
every complete window digest agrees with SHNGROOT before signing; stale segments are refused.
"""
import argparse
import hashlib
import importlib.util
import json
import struct
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT.parent / 'UniXNU'
BLOCK = 4096
RAW, FILL, DONT_CARE = 0xCAC1, 0xCAC2, 0xCAC3
POLICY_UUID = {
    'OS': uuid.UUID('04769D26-2CA0-4825-B443-E2E5F88300F2'),
    'SystemOS': uuid.UUID('8846FE78-2910-4297-AF97-D59BB6F8FC16'),
}


def require(ok, message):
    if not ok:
        raise SystemExit(message)


class Segments:
    """Random access to whole-image bytes stored across Android sparse segments."""

    def __init__(self, paths):
        self.chunks = []
        self.handles = {}
        for path in paths:
            with path.open('rb') as handle:
                magic, _, _, file_header, chunk_header, block, blocks, chunks, _ = struct.unpack(
                    '<IHHHHIIII', handle.read(28))
                require(magic == 0xED26FF3A and file_header == 28 and chunk_header == 12 and block == BLOCK,
                        f'{path}: not an Android sparse image with 4096-byte blocks')
                position, offset = 0, 28
                for _ in range(chunks):
                    handle.seek(offset)
                    kind, _, count, total = struct.unpack('<HHII', handle.read(12))
                    length = count * BLOCK
                    require(kind in (RAW, FILL, DONT_CARE), f'{path}: unknown chunk type {kind:#x}')
                    if kind != DONT_CARE:
                        self.chunks.append((position, position + length, path, offset + 12, kind, length))
                    offset += total
                    position += length
        self.chunks.sort()

    def _handle(self, path):
        handle = self.handles.get(path)
        if handle is None:
            handle = path.open('rb')
            self.handles[path] = handle
        return handle

    def read_at(self, offset, count):
        lo, hi = 0, len(self.chunks)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.chunks[mid][1] <= offset:
                lo = mid + 1
            else:
                hi = mid
        if lo >= len(self.chunks):
            return b''
        start, end, path, data_at, kind, length = self.chunks[lo]
        if not start <= offset < end:
            return b''
        take = min(count, end - offset)
        if kind == FILL:
            handle = self._handle(path)
            handle.seek(data_at)
            fill = handle.read(4)
            return fill * (take // 4) + fill[:take % 4]
        handle = self._handle(path)
        handle.seek(data_at + (offset - start))
        data = handle.read(take)
        require(len(data) == take, f'{path}: short read at image offset {offset}')
        return data


class RawImage:
    """Read the exact complete raw SHNGROOT image used by deployment/readback."""

    def __init__(self, path):
        self.handle = path.open('rb')
        self.size = path.stat().st_size

    def read_at(self, offset, count):
        require(offset >= 0 and count >= 0, 'Negative raw-image range')
        self.handle.seek(offset)
        return self.handle.read(count)


def parse_root_header(head):
    require(len(head) == BLOCK and head[:8] == b'SHNGROOT', 'The image does not start with the SHNGROOT manifest')
    require(hashlib.sha256(head[:4064]).digest() == head[4064:], 'SHNGROOT header digest mismatch')
    version, windows = struct.unpack_from('<II', head, 8)
    image_bytes, = struct.unpack_from('<Q', head, 16)
    require(version == 1 and 0 < windows <= 4, 'Unsupported root manifest header')
    entries = []
    for index in range(windows):
        base = 24 + 128 * index
        name = head[base:base + 32].split(b'\0')[0].decode()
        offset, size = struct.unpack_from('<QQ', head, base + 32)
        digest = head[base + 56:base + 88]
        entries.append({'name': name, 'offset': offset, 'size': size, 'digest': digest.hex()})
    return image_bytes, entries


def check_window_digest(source, entry):
    """Refuse stale or corrupted sources before signing any envelope."""
    digest = hashlib.sha256()
    position, remaining = entry['offset'], entry['size']
    while remaining:
        data = source.read_at(position, min(4 * 1024 * 1024, remaining))
        require(data and len(data) <= remaining,
                f"{entry['name']}: incomplete input coverage at {position}")
        digest.update(data)
        position += len(data)
        remaining -= len(data)
    actual = digest.hexdigest()
    require(actual == entry['digest'],
            f"{entry['name']}: input digest mismatch: expected {entry['digest']}, got {actual}")
    return actual


class SparseStream:
    """Sequential, buffered reader over one window of the image."""

    BLOCK_BUFFER = 4 * 1024 * 1024

    def __init__(self, segments, start, size):
        self.segments = segments
        self.position = start
        self.remaining = size
        self.buffer = b''
        self.buffer_at = start

    def read(self, count):
        count = min(count, self.remaining)
        if count <= 0:
            return b''
        if not (self.buffer_at <= self.position and self.position + count <= self.buffer_at + len(self.buffer)):
            want = min(max(count, self.BLOCK_BUFFER), self.remaining)
            self.buffer = self.segments.read_at(self.position, want)
            require(self.buffer, f'Sparse coverage ends at image offset {self.position}')
            self.buffer_at = self.position
        delta = self.position - self.buffer_at
        data = self.buffer[delta:delta + count]
        require(len(data) == count, 'Short buffered read')
        self.position += count
        self.remaining -= count
        return data


def verify_host(verifier, output, segments, entries, windows, public_key, all_blocks=False):
    """Authenticate each envelope with the real C code and compare sampled blocks with the image."""
    if not verifier.is_file():
        for window in windows:
            window['host_verification'] = 'verifier library unavailable'
        return windows
    import ctypes

    class View(ctypes.Structure):
        _fields_ = [('hashes', ctypes.c_void_p), ('image_bytes', ctypes.c_uint64), ('block_count', ctypes.c_uint64),
                    ('generation', ctypes.c_uint64), ('volume_uuid', ctypes.c_uint8 * 16),
                    ('image_sha256', ctypes.c_uint8 * 32)]

    native = ctypes.CDLL(str(verifier))
    native.vr_host_open.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_uint64,
                                    ctypes.POINTER(View)]
    native.vr_host_block.argtypes = [ctypes.POINTER(View), ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t]

    for window, entry in zip(windows, entries):
        envelope = (output / entry['name'] / 'manifest.bin').read_bytes()
        anchor = (output / entry['name'] / 'trusted-key.bin').read_bytes()
        view = View()
        require(not native.vr_host_open(envelope, len(envelope), anchor, 1, ctypes.byref(view)),
                f"{entry['name']}: host signature/volume authentication failed")
        require(view.image_bytes == entry['size'] and view.block_count == window['block_count'],
                f"{entry['name']}: host view geometry differs")
        require(str(uuid.UUID(bytes=bytes(view.volume_uuid))).upper() == window['volume_uuid'],
                f"{entry['name']}: host volume UUID differs")
        count = view.block_count
        indices = range(count) if all_blocks else sorted({0, 1, count // 4, count // 2, count - 2, count - 1})
        for index in indices:
            at = entry['offset'] + index * BLOCK
            data = segments.read_at(at, min(BLOCK, entry['size'] - index * BLOCK))
            require(data, f"{entry['name']}: sampled block {index} is outside the sparse coverage")
            require(not native.vr_host_block(ctypes.byref(view), index, data, len(data)),
                    f"{entry['name']}: sampled block {index} failed authentication")
        window['host_verification'] = 'vr_host_open plus %d %s blocks authenticated' % (len(indices), 'complete' if all_blocks else 'sampled')
        if all_blocks:
            window['verified_blocks'] = count
        else:
            window['sampled_blocks'] = indices
    return windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--segments', type=Path, nargs='+')
    inputs.add_argument('--image', type=Path, help='exact complete raw SHNGROOT deployment image')
    parser.add_argument('--verify-all-blocks', action='store_true', help='authenticate every input block with the real C verifier')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--generation', type=int, default=1)
    parser.add_argument('--private-key', type=Path, default=FW / 'build/verified-root-host/keys/owner.pem')
    parser.add_argument('--public-key', type=Path, default=FW / 'build/verified-root-host/keys/owner-public.pem')
    parser.add_argument('--host-verifier', type=Path, default=FW / 'build/verified-root-host/verified-root.dylib')
    options = parser.parse_args()
    output = options.output.resolve()
    require(not output.exists(), 'Choose a new output directory')
    require(options.private_key.is_file() and options.public_key.is_file(), 'Owner key pair is missing')
    require(not options.verify_all_blocks or options.host_verifier.is_file(),
            'Full block verification requires the real C verifier')

    segments = RawImage(options.image) if options.image else Segments(options.segments)
    head = segments.read_at(0, BLOCK)
    image_bytes, entries = parse_root_header(head)
    if options.image:
        require(segments.size == image_bytes, 'Raw image length differs from SHNGROOT declaration')
    require(sum(e['size'] for e in entries) <= image_bytes, 'Windows exceed the image')
    previous_end = BLOCK
    for entry in sorted(entries, key=lambda e: e['offset']):
        require(entry['offset'] >= previous_end and entry['size'] > 0 and
                entry['offset'] % BLOCK == 0 and entry['offset'] <= image_bytes and
                entry['size'] <= image_bytes - entry['offset'], 'Invalid or overlapping root window')
        previous_end = entry['offset'] + entry['size']
        check_window_digest(segments, entry)

    spec = importlib.util.spec_from_file_location('verified_manifest', FW / 'kits/VerifiedRoot/tools/manifest.py')
    manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest)

    output.mkdir(parents=True)
    report = {'segments': [str(p) for p in options.segments] if options.segments else [],
              'raw_image': str(options.image) if options.image else None,
              'input_window_digests_verified': True, 'image_bytes': image_bytes,
              'generation': options.generation, 'windows': []}
    for entry in entries:
        require(entry['name'] in POLICY_UUID, f"No policy UUID for window {entry['name']}")
        stream = SparseStream(segments, entry['offset'], entry['size'])
        record = manifest.make(stream, entry['size'], options.private_key, options.public_key,
                               POLICY_UUID[entry['name']], options.generation, output / entry['name'])
        envelope = output / entry['name'] / 'manifest.bin'
        require(record['image_sha256'] == entry['digest'], f"{entry['name']}: source changed during signing")
        bytes_in_envelope = envelope.stat().st_size
        require(bytes_in_envelope == 544 + 32 * record['block_count'], 'Unexpected envelope length')
        report['windows'].append({
            'name': entry['name'], 'offset': entry['offset'], 'size': entry['size'],
            'block_count': record['block_count'], 'volume_uuid': record['volume_uuid'],
            'image_sha256': record['image_sha256'], 'hash_table_sha256': record['hash_table_sha256'],
            'trusted_key_sha256': record['trusted_key_sha256'],
            'envelope_bytes': bytes_in_envelope,
            'envelope_blocks': (bytes_in_envelope + BLOCK - 1) // BLOCK,
            'envelope_sha256': hashlib.sha256(envelope.read_bytes()).hexdigest(),
            'signature_verified_by_openssl': record['signature_verified_by_openssl'],
        })
    report['windows'] = verify_host(options.host_verifier, output, segments, entries, report['windows'],
                                    options.public_key, options.verify_all_blocks)
    report['total_envelope_bytes'] = sum(w['envelope_bytes'] for w in report['windows'])
    (output / 'root-manifests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
