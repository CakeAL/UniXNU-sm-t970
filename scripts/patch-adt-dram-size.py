#!/usr/bin/env python3
"""Rewrite one 8-byte ADT property in place, keeping the rest of the blob byte-identical.

The ADT is the reduced device tree XNU boots from: every node is
`u32 property_count, u32 child_count`, then `char[32] name + u32 size + value`
padded to four bytes, then its children. Only /chosen/dram-size changes, so the
serialized offsets stay valid.
"""
import argparse
import struct
from pathlib import Path


class Layout:
    """Byte offsets of every node and property in one ADT blob."""

    def __init__(self, blob):
        self.blob = blob
        self.nodes = {}
        end = self.walk(0, '', root=True)
        if end != len(blob):
            raise ValueError(f'ADT trailing bytes: {len(blob) - end}')
        if '/' not in self.nodes:
            raise ValueError('ADT has no root node')

    def walk(self, offset, parent, root=False):
        count, children = struct.unpack_from('<II', self.blob, offset)
        offset += 8
        properties = {}
        for _ in range(count):
            key, size = struct.unpack_from('<32sI', self.blob, offset)
            offset += 36
            name = key.split(b'\0', 1)[0].decode()
            if name in properties:
                raise ValueError('Duplicate ADT property: ' + name)
            if offset + size > len(self.blob):
                raise ValueError('Truncated ADT property: ' + name)
            properties[name] = (offset, size)
            offset += (size + 3) & ~3
        if 'name' not in properties:
            raise ValueError('ADT node without a name')
        begin, length = properties['name']
        path = '' if root else parent + '/' + self.blob[begin:begin + length].rstrip(b'\0').decode()
        self.nodes[path or '/'] = properties
        for _ in range(children):
            offset = self.walk(offset, path)
        return offset

    def value(self, path, key):
        begin, size = self.nodes[path][key]
        return self.blob[begin:begin + size]


def patch(blob, new_size, expected_old=0x80000000):
    """Return the blob with /chosen/dram-size replaced; every other byte is unchanged."""
    layout = Layout(blob)
    begin, size = layout.nodes['/chosen']['dram-size']
    if size != 8:
        raise ValueError(f'Unexpected dram-size width: {size}')
    old, = struct.unpack_from('<Q', blob, begin)
    if expected_old is not None and old != expected_old:
        raise ValueError(f'Unexpected dram-size {old:#x}, expected {expected_old:#x}')
    if new_size % 4096 or not 0 < new_size <= 1 << 40:
        raise ValueError(f'Rejected dram-size {new_size:#x}')
    updated = bytearray(blob)
    struct.pack_into('<Q', updated, begin, new_size)
    check = Layout(bytes(updated))
    if check.value('/chosen', 'dram-size') != struct.pack('<Q', new_size):
        raise ValueError('Patched ADT does not read back')
    for path, properties in layout.nodes.items():
        for key, (offset, length) in properties.items():
            if path == '/chosen' and key == 'dram-size':
                continue
            if bytes(updated[offset:offset + length]) != blob[offset:offset + length]:
                raise ValueError(f'Patch changed {path}/{key}')
    return bytes(updated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=lambda value: int(value, 0), required=True)
    parser.add_argument('--expect-old', type=lambda value: int(value, 0), default=0x80000000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refuse to overwrite ' + str(args.output))
    args.output.write_bytes(patch(args.input.read_bytes(), args.size, args.expect_old))
    print(f'{args.input} -> {args.output}: dram-size {args.size:#x}')


if __name__ == '__main__':
    main()
