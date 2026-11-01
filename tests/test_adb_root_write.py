import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('root_write', ROOT / 'scripts/write-root-image-adb.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WriteTests(unittest.TestCase):
    def test_stream_write_readback_and_refusal(self):
        for mode in ('ok', 'source', 'readiness', 'write_error', 'corrupt', 'flush_error'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory); image = root / 'image'; target = root / 'target'
                data = b'fixture block' * 8192
                image.write_bytes(data)
                calls = []

                class Process:
                    def __init__(self, cmd, **kwargs):
                        calls.append(cmd)
                        self.writing = 'shell' in cmd
                        if self.writing:
                            self.stdin = target.open('wb')
                        else:
                            self.stdout = io.BytesIO(target.read_bytes() + (b'bad' if mode == 'corrupt' else b''))
                    def wait(self, timeout=None):
                        return 1 if mode == 'write_error' and self.writing else 0
                    def terminate(self):
                        pass

                def ready(*args, **kwargs):
                    if mode == 'readiness' or (mode == 'flush_error' and 'blockdev --flushbufs' in args[0][-1]):
                        raise subprocess.CalledProcessError(1, args[0])
                    return subprocess.CompletedProcess(args[0], 0)

                arguments = ['write-root-image-adb.py', '--serial', 'fixture', '--image', str(image),
                             '--output', str(root / 'receipt'), '--write']
                expected = 'wrong' if mode == 'source' else hashlib.sha256(data).hexdigest()
                with mock.patch.object(MODULE, 'EXPECTED', expected), mock.patch.object(MODULE, 'IMAGE_BYTES', len(data)), \
                     mock.patch.object(sys, 'argv', arguments), mock.patch.object(MODULE.subprocess, 'run', ready), \
                     mock.patch.object(MODULE.subprocess, 'Popen', Process), contextlib.redirect_stdout(io.StringIO()):
                    if mode == 'ok':
                        MODULE.main()
                        self.assertEqual(target.read_bytes(), data)
                        self.assertTrue(json.loads((root/'receipt/receipt.json').read_text())['verified'])
                    else:
                        with self.assertRaises((ValueError, RuntimeError, subprocess.CalledProcessError)):
                            MODULE.main()
                if mode in ('source', 'readiness'):
                    self.assertEqual(calls, [])
                if mode in ('write_error', 'flush_error'):
                    self.assertEqual(len(calls), 1)
                if mode == 'ok':
                    self.assertIn('iflag=count_bytes', calls[1][-1])
                    self.assertIn('2>/dev/null', calls[1][-1])
