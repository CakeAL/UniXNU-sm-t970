#!/usr/bin/env python3
"""Review a packed 73 GiB seed and a proposed T970 persistence window, without writes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

PAGE = 4096
PART_FIRST, PART_LAST = 37292800, 62458623
FIRST, LAST = 42816256, 62065402
PAGES = 73 * 1024**3 // PAGE
SEED_ID = 'd4372c71be216bed6f8278026fb6bd08d52fa7565fed0276a9be8fffac8b2cb9'
PACKED_HASH = 'ca1543d1986cb1de5dd8ef6a3f01f48609e2a65a18bbf3f88f04b2d189031dcf'
POLICIES = ((PART_FIRST + 5505024, PART_FIRST + 5505024 + 11593 - 1),
            (PART_FIRST + 5516624, PART_FIRST + 5516624 + 6301 - 1))


def check_window(first, pages, partition=(PART_FIRST, PART_LAST)):
    bitmap = (pages + PAGE * 8 - 1) // (PAGE * 8)
    blocks = 1 + bitmap + pages
    end = first + blocks - 1
    if partition != (PART_FIRST, PART_LAST) or first != FIRST or pages != PAGES:
        raise ValueError('unexpected geometry')
    if not (partition[0] <= first <= end <= LAST < 62065403 <= partition[1]):
        raise ValueError('outside reviewed Data extent')
    if any(first <= hi and lo <= end for lo, hi in POLICIES):
        raise ValueError('overlaps root policy')
    return dict(first_lba=first, last_lba=end, blocks=blocks, bitmap_blocks=bitmap,
                logical_bytes=pages * PAGE, unused_extent_blocks=LAST-end)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('seed', type=Path)
    p.add_argument('--unixnu', type=Path, default=Path(__file__).resolve().parents[2] / 'UniXNU')
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location('packed_ramdisk', a.unixnu / 'drivers/DarwinBoot/Test/packed_ramdisk.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    seed, first = mod.inspect(a.seed)
    if seed.get('sha256') != SEED_ID or seed.get('encoded_sha256') != PACKED_HASH or seed.get('bytes') != PAGES * PAGE:
        raise SystemExit('seed identity or geometry mismatch')
    if first[32:36] != b'NXSB' or int.from_bytes(first[36:40], 'little') != PAGE or int.from_bytes(first[40:48], 'little') != PAGES:
        raise SystemExit('APFS superblock mismatch')
    print(json.dumps(dict(seed=seed, proposed_window=check_window(FIRST, PAGES),
                          note='Host geometry review only; not installed or device tested.'), indent=2))

if __name__ == '__main__':
    main()
