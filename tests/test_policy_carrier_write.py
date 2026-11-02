import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('policy_carrier_writer',
    Path(__file__).resolve().parents[1] / 'scripts/write-policy-carrier-adb.py')
WRITER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WRITER)


class PolicyCarrierWrite(unittest.TestCase):
    def run_writer(self, backups_and_reads, fail_write=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'source.json'
            report.write_text(json.dumps({'input_window_digests_verified': True,
                'windows': [{'name': 'OS'}, {'name': 'SystemOS'}]}))
            output = root / 'receipt'
            args = ['writer', '--serial', 'test-device', '--source-report', str(report),
                    '--expected-old-os', 'a' * 64, '--expected-old-systemos', 'b' * 64,
                    '--write', '--output', str(output)]
            def remote(*args, **kwargs):
                denied = fail_write and args[-1].startswith('dd ')
                return SimpleNamespace(returncode=int(denied), stdout='', stderr='')
            with mock.patch.object(sys, 'argv', args), \
                 mock.patch.object(WRITER, 'validate_envelope', side_effect=[(4096, 'c' * 64), (4096, 'd' * 64)]), \
                 mock.patch.object(WRITER.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
                 mock.patch.object(WRITER, 'device_sha', side_effect=backups_and_reads) as reads, \
                 mock.patch.object(WRITER, 'sh', side_effect=remote) as writes, \
                 contextlib.redirect_stdout(io.StringIO()):
                error = None
                try:
                    WRITER.main()
                except RuntimeError as caught:
                    error = str(caught)
                receipt = json.loads((output / 'receipt.json').read_text())
                return receipt, error, reads.call_args_list, writes.call_args_list

    def test_first_backup_mismatch_prevents_all_remote_writes(self):
        receipt, error, reads, writes = self.run_writer(['e' * 64])
        self.assertIn('nothing may be written', error)
        self.assertFalse(writes)
        self.assertEqual(len(reads), 1)
        self.assertFalse(any(e['write_attempted'] for e in receipt['envelopes']))

    def test_both_backups_checked_before_first_write(self):
        receipt, error, reads, writes = self.run_writer(['a' * 64, 'e' * 64])
        self.assertIn('nothing may be written', error)
        self.assertFalse(writes)
        self.assertEqual(len(reads), 2)
        self.assertFalse(any(e['write_attempted'] for e in receipt['envelopes']))

    def test_write_or_flush_failure_stops_before_second_envelope(self):
        receipt, error, reads, writes = self.run_writer(['a' * 64, 'b' * 64], fail_write=True)
        self.assertIn('no automatic retry', error)
        self.assertEqual(len(reads), 2)
        self.assertEqual(len(writes), 2)  # one push, one failed write/flush
        self.assertTrue(receipt['envelopes'][0]['write_attempted'])
        self.assertFalse(receipt['envelopes'][1]['write_attempted'])
        command = writes[-1].args[-1]
        self.assertIn('&& sync && blockdev --flushbufs', command)
        self.assertNotIn('|| true', command)

    def test_exact_readback_required_for_success(self):
        receipt, error, reads, writes = self.run_writer(['a' * 64, 'b' * 64, 'c' * 64, 'd' * 64])
        self.assertIsNone(error)
        self.assertTrue(receipt['all_verified'])
        self.assertEqual(len(reads), 4)
        self.assertEqual(len(writes), 6)

    def test_readback_mismatch_stops_before_second_envelope(self):
        receipt, error, reads, writes = self.run_writer(['a' * 64, 'b' * 64, 'e' * 64])
        self.assertIn('readback mismatch', error)
        self.assertFalse(receipt['all_verified'])
        self.assertFalse(receipt['envelopes'][1]['write_attempted'])
        self.assertEqual(len(writes), 2)


if __name__ == '__main__':
    unittest.main()
