"""Execute real assembled status-probe instructions with a simulated counter."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

try:
    import unicorn
    from unicorn import arm64_const as regs
except ImportError:
    unicorn = None

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('exec_status', ROOT / 'scripts/exec-return-status-probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class InputTests(unittest.TestCase):
    def test_unknown_source_is_preserved_and_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / 'source', Path(tmp) / 'copy'
            src.write_bytes(b'unknown')
            with self.assertRaises(ValueError):
                probe.patch_copy(src, out, ROOT.parent / 'UniXNU')
            self.assertEqual(src.read_bytes(), b'unknown')
            self.assertFalse(out.exists())


@unittest.skipUnless(unicorn, 'Use the isolated probe-test environment for ARM64 execution')
class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('shared_status_test', ROOT.parent / 'UniXNU/scripts/patch-xnu-entry-probe.py')
        shared = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shared)
        with tempfile.TemporaryDirectory() as tmp:
            cls.code = shared.assemble(probe.assembly(), 0x400000, {'callee': 0x401000}, Path(tmp))
        if len(cls.code) > probe.CAPACITY:
            raise AssertionError('Probe exceeds checked padding')

    def run_status(self, status, seconds):
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
        uc.mem_map(0x400000, 0x2000)
        uc.mem_write(0x400000, self.code)
        uc.reg_write(regs.UC_ARM64_REG_X0, 0x123456789)
        uc.reg_write(regs.UC_ARM64_REG_X1, 0x23456789a)
        uc.reg_write(regs.UC_ARM64_REG_X2, 0x3456789ab)
        observed = {'calls': 0, 'reads': 0, 'reset': False, 'writes': 0}

        def instruction(machine, address, size, unused):
            if address == 0x401000:
                self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X0), 0x123456789)
                self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X1), 0x23456789a)
                self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X2), 0x3456789ab)
                observed['calls'] += 1
                machine.reg_write(regs.UC_ARM64_REG_W0, status)
                machine.reg_write(regs.UC_ARM64_REG_PC, machine.reg_read(regs.UC_ARM64_REG_X30))
                return
            word = struct.unpack('<I', machine.mem_read(address, 4))[0]
            if word == 0xd53be021:
                machine.reg_write(regs.UC_ARM64_REG_X1, observed['reads'] * 19200000)
                observed['reads'] += 1
                machine.reg_write(regs.UC_ARM64_REG_PC, address + 4)
            elif word == 0xd4000003:
                self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X0), 0x84000009)
                observed['reset'] = True
                machine.emu_stop()

        def write(*unused):
            observed['writes'] += 1

        uc.hook_add(unicorn.UC_HOOK_CODE, instruction)
        uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
        uc.emu_start(0x400000, 0x400000 + len(self.code), count=10000)
        self.assertTrue(observed['reset'])
        self.assertEqual(observed['calls'], 1)
        self.assertEqual(observed['reads'] - 1, seconds)
        self.assertEqual(observed['writes'], 0)

    def test_zero_return(self):
        self.run_status(0, 6)

    def test_nonzero_errors(self):
        for error in (2, 12, 13, 0xffffffff):
            with self.subTest(error=error):
                self.run_status(error, 16)
