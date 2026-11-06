"""Actual ADT patcher: one 8-byte property changes, every other byte stays."""
import importlib.util
from pathlib import Path
import struct
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/patch-adt-dram-size.py'
spec = importlib.util.spec_from_file_location('adt_patch', SCRIPT)
adt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adt)


def encode_node(properties, children=()):
    out = struct.pack('<II', len(properties), len(children))
    for name, value in properties:
        out += name.encode().ljust(32, b'\0') + struct.pack('<I', len(value))
        out += value + b'\0' * ((4 - len(value) % 4) % 4)
    for child in children:
        out += child
    return out


def sample(size=0x80000000):
    chosen = encode_node([('name', b'chosen\0'),
                          ('dram-base', struct.pack('<Q', 0x80000000)),
                          ('dram-size', struct.pack('<Q', size))])
    return encode_node([('name', b'device-tree\0')], [chosen])


class DramSize(unittest.TestCase):
    def test_patch_changes_only_dram_size(self):
        blob = sample()
        out = adt.patch(blob, 0x200000000)
        self.assertEqual(adt.Layout(out).value('/chosen', 'dram-size'), struct.pack('<Q', 0x200000000))
        self.assertEqual(adt.Layout(out).value('/chosen', 'dram-base'), struct.pack('<Q', 0x80000000))
        self.assertEqual(adt.Layout(out).value('/chosen', 'name'), b'chosen\0')
        self.assertEqual(len(out), len(blob))
        changed = [i for i, (a, b) in enumerate(zip(blob, out)) if a != b]
        begin, _ = adt.Layout(blob).nodes['/chosen']['dram-size']
        self.assertTrue(set(changed) <= set(range(begin, begin + 8)))

    def test_rejects_unexpected_old_value(self):
        with self.assertRaises(ValueError):
            adt.patch(sample(0x40000000), 0x200000000)

    def test_rejects_unaligned_size(self):
        with self.assertRaises(ValueError):
            adt.patch(sample(), 0x100000001)

    def test_rejects_trailing_bytes(self):
        with self.assertRaises(ValueError):
            adt.Layout(sample() + b'\0')

    def test_layout_reports_nodes(self):
        layout = adt.Layout(sample())
        self.assertEqual(set(layout.nodes), {'/', '/chosen'})


if __name__ == '__main__':
    unittest.main()
