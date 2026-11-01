#!/usr/bin/env python3
"""Encode one contiguous segment of the userdata image as an Android sparse file.

Chunks outside the segment become DONT_CARE so the bootloader leaves the existing
partition content alone; the encoded file is only as large as the segment, which
keeps each Heimdall upload below its 4 GiB single-file limit.
"""
import argparse
from pathlib import Path
import struct

BLOCK = 4096
CHUNK = 1024 * 1024
SPARSE_MAGIC = 0xED26FF3A
RAW = 0xCAC1
FILL = 0xCAC2
DONT_CARE = 0xCAC3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', type=Path, required=True)
    ap.add_argument('--start-mib', type=int, required=True)
    ap.add_argument('--end-mib', type=int, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    size = a.image.stat().st_size
    if size % BLOCK:
        raise SystemExit('image length must be a multiple of 4096')
    start, end = a.start_mib * CHUNK, min(a.end_mib * CHUNK, size)
    if not (0 <= start < end <= size):
        raise SystemExit('invalid segment')
    chunks = (size + CHUNK - 1) // CHUNK
    zeroes = bytes(CHUNK)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.image.open('rb') as src, a.output.open('wb') as out:
        out.write(struct.pack('<IHHHHIIII', SPARSE_MAGIC, 1, 0, 28, 12, BLOCK, size // BLOCK, chunks, 0))
        pos = 0
        while pos < size:
            length = min(CHUNK, size - pos)
            if start <= pos < end:
                data = src.read(length) if pos == start else None
                if data is None:
                    src.seek(pos)
                    data = src.read(length)
                if len(data) != length:
                    raise SystemExit('short read')
                if data == zeroes[:length]:
                    out.write(struct.pack('<HHII', FILL, 0, length // BLOCK, 16))
                    out.write(bytes(4))
                else:
                    out.write(struct.pack('<HHII', RAW, 0, length // BLOCK, 12 + length))
                    out.write(data)
            else:
                out.write(struct.pack('<HHII', DONT_CARE, 0, length // BLOCK, 12))
            pos += length
    print(f'sparse segment {a.start_mib}..{a.end_mib} MiB -> {a.output} {a.output.stat().st_size} bytes')


if __name__ == '__main__':
    main()
