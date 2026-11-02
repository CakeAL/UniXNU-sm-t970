import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('owner_manifest_inputs',
    Path(__file__).resolve().parents[1] / 'scripts/build-owner-root-manifests.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OwnerManifestInputs(unittest.TestCase):
    def test_shngroot_digest_starts_at_entry_byte56(self):
        head = bytearray(4096)
        digest = hashlib.sha256(b'original window').digest()
        struct.pack_into('<8sIIQ', head, 0, b'SHNGROOT', 1, 1, 8192)
        struct.pack_into('<32sQQII32s40s', head, 24, b'OS', 4096, 4096, 512, 1, digest, bytes(40))
        head[4064:] = hashlib.sha256(head[:4064]).digest()
        size, entries = MODULE.parse_root_header(head)
        self.assertEqual(size, 8192)
        self.assertEqual(entries[0]['digest'], digest.hex())
        head[25] ^= 1
        with self.assertRaisesRegex(SystemExit, 'header digest mismatch'):
            MODULE.parse_root_header(head)

    def test_raw_window_matches_declared_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'raw.img'
            body = b'a' * 4096
            path.write_bytes(bytes(4096) + body)
            source = MODULE.RawImage(path)
            try:
                digest = hashlib.sha256(body).hexdigest()
                self.assertEqual(MODULE.check_window_digest(source, {
                    'name': 'SystemOS', 'offset': 4096, 'size': 4096, 'digest': digest}), digest)
            finally:
                source.handle.close()

    def test_rejects_old_sparse_source_header_at_window_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.sparse'
            bad = b'SHNGROOT' + bytes(4096 - 8)
            path.write_bytes(struct.pack('<IHHHHIIII', 0xED26FF3A, 1, 0, 28, 12, 4096, 2, 1, 0)
                + struct.pack('<HHII', MODULE.RAW, 0, 2, 12 + 8192) + bytes(4096) + bad)
            source = MODULE.Segments([path])
            try:
                with self.assertRaisesRegex(SystemExit, 'SystemOS: input digest mismatch'):
                    MODULE.check_window_digest(source, {'name': 'SystemOS', 'offset': 4096,
                        'size': 4096, 'digest': hashlib.sha256(b'a' * 4096).hexdigest()})
            finally:
                for handle in source.handles.values():
                    handle.close()

    def test_digest_crosses_raw_and_fill_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'valid.sparse'
            body = b'b' * 4096
            path.write_bytes(struct.pack('<IHHHHIIII', 0xED26FF3A, 1, 0, 28, 12, 4096, 2, 2, 0)
                + struct.pack('<HHII', MODULE.RAW, 0, 1, 12 + 4096) + body
                + struct.pack('<HHII', MODULE.FILL, 0, 1, 16) + bytes(4))
            source = MODULE.Segments([path])
            try:
                expected = hashlib.sha256(body + bytes(4096)).hexdigest()
                self.assertEqual(MODULE.check_window_digest(source, {
                    'name': 'OS', 'offset': 0, 'size': 8192, 'digest': expected}), expected)
            finally:
                for handle in source.handles.values():
                    handle.close()

    def test_short_raw_input_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'short.img'
            path.write_bytes(bytes(4096))
            source = MODULE.RawImage(path)
            try:
                with self.assertRaisesRegex(SystemExit, 'incomplete input coverage'):
                    MODULE.check_window_digest(source, {
                        'name': 'OS', 'offset': 0, 'size': 8192, 'digest': '0' * 64})
            finally:
                source.handle.close()


if __name__ == '__main__':
    unittest.main()
