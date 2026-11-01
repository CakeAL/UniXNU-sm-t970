import pathlib
import struct
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SparseTests(unittest.TestCase):
    def test_nonzero_segment_reads_its_own_first_chunk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source = root / 'source.img'
            source.write_bytes(b'A' * 1048576 + b'B' * 1048576 + bytes(1048576))
            for start in (0, 1, 2):
                output = root / f'{start}.sparse'
                subprocess.run(['python3.14', str(ROOT / 'scripts/encode-userdata-sparse.py'),
                                '--image', str(source), '--start-mib', str(start),
                                '--end-mib', str(start + 1), '--output', str(output)],
                               check=True, capture_output=True)
                raw = output.read_bytes()
                self.assertEqual(struct.unpack_from('<I', raw)[0], 0xED26FF3A)
                pos = 28
                for index in range(3):
                    kind, _, blocks, size = struct.unpack_from('<HHII', raw, pos)
                    self.assertEqual(blocks, 256)
                    payload = raw[pos + 12:pos + size]
                    if index != start:
                        self.assertEqual((kind, payload), (0xCAC3, b''))
                    elif start == 2:
                        self.assertEqual((kind, payload), (0xCAC2, bytes(4)))
                    else:
                        self.assertEqual(kind, 0xCAC1)
                        self.assertEqual(payload, bytes([65 + start]) * 1048576)
                    pos += size
                self.assertEqual(pos, len(raw))
