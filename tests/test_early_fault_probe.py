"""Exercise assembled early fault terminals without a physical tablet."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

try:
    import unicorn
    from unicorn import arm64_const
except ImportError:
    unicorn = None

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fault_probe', ROOT / 'scripts/early-fault-probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class InputTests(unittest.TestCase):
    def test_reject_unknown_kernel_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'source', Path(tmp) / 'output'
            source.write_bytes(b'unknown')
            with self.assertRaises(ValueError):
                probe.patch_copy(source, output, ROOT.parent / 'UniXNU', 6)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), b'unknown')


@unittest.skipUnless(unicorn, 'Unicorn is required for ARM64 execution tests')
class ExecutionTests(unittest.TestCase):
    def test_each_fault_terminal(self):
        shared = ROOT.parent / 'UniXNU/scripts/patch-xnu-entry-probe.py'
        spec = importlib.util.spec_from_file_location('shared_fault_test', shared)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            code, entries = probe.assemble_guard(module, 0x400000, Path(tmp))
        self.assertLessEqual(len(code), probe.CAPACITY)
        cases = [('sync_guard', 0x25, 20), ('sync_guard', 0x3c, 50),
                 ('serror_guard', 0, 30), ('panic_guard', 0, 40)]
        for entry, exception_class, seconds in cases:
            with self.subTest(entry=entry, exception_class=exception_class):
                uc = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
                uc.mem_map(0x400000, 0x1000)
                uc.mem_write(0x400000, code)
                seen = {'counter': 0, 'reset': False, 'writes': 0}

                def instruction(machine, address, size, unused):
                    word = struct.unpack('<I', machine.mem_read(address, 4))[0]
                    if address == entries['sync_guard']:
                        machine.reg_write(arm64_const.UC_ARM64_REG_X9, exception_class << 26)
                        machine.reg_write(arm64_const.UC_ARM64_REG_PC, address + 4)
                    elif word == 0xd53be021:  # MRS X1, CNTPCT_EL0
                        machine.reg_write(arm64_const.UC_ARM64_REG_X1, seen['counter'] * 19200000)
                        seen['counter'] += 1
                        machine.reg_write(arm64_const.UC_ARM64_REG_PC, address + 4)
                    elif word == 0xd4000003:  # SMC #0
                        self.assertEqual(machine.reg_read(arm64_const.UC_ARM64_REG_X0), 0x84000009)
                        seen['reset'] = True
                        machine.emu_stop()

                def write(*unused):
                    seen['writes'] += 1

                uc.hook_add(unicorn.UC_HOOK_CODE, instruction)
                uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                uc.emu_start(entries[entry], 0x400000 + len(code), count=10000)
                self.assertTrue(seen['reset'])
                self.assertEqual(seen['counter'] - 1, seconds)
                self.assertEqual(seen['writes'], 0)


if __name__ == '__main__':
    unittest.main()
