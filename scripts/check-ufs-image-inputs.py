#!/usr/bin/env python3
"""Verify sample expectations against the exact previously uploaded source image; no device I/O."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads((root / 'evidence/storage/ufs-image/expectations.json').read_text())
    receipt = json.loads((root / 'evidence/bring-up/runtime/userdata-sparse/flash.json').read_text())
    h = hashlib.sha256()
    with args.image.open('rb') as source:
        while chunk := source.read(8 * 1024 * 1024):
            h.update(chunk)
    if h.hexdigest() != spec['source_image_sha256'] or h.hexdigest() != receipt['image_sha256']:
        raise ValueError('Source image does not match the prior USERDATA receipt')
    header = (root / 'package/ShengUfs/T970ImageTest.h').read_text()
    with args.image.open('rb') as source:
        for row in spec['samples']:
            offset = (row['lba'] - 2969600) * 4096
            size = row['blocks'] * 4096
            if offset < 0 or offset + size > args.image.stat().st_size:
                raise ValueError('Sample out of image bounds')
            source.seek(offset)
            if hashlib.sha256(source.read(size)).hexdigest() != row['sha256']:
                raise ValueError('Sample digest mismatch: ' + row['name'])
            octets = ', '.join('0x' + row['sha256'][j:j+2] for j in range(0, 64, 2))
            literal = '"' + row['name'] + '", ' + str(row['lba']) + ', ' + str(row['blocks']) + ', {' + octets + '}'
            if literal not in header:
                raise ValueError('Kernel expectation differs: ' + row['name'])
    args.output.write_text(json.dumps(dict(source_image_sha256=h.hexdigest(),
        matches_prior_flash_source=True, samples_verified=len(spec['samples']),
        kernel_expectations_match=True, device_verified=False), indent=2) + '\n')
    print('PASS: exact prior source image and all seven kernel sample expectations')


if __name__ == '__main__':
    main()
