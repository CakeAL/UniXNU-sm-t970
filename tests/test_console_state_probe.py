"""Execute the actual assembled AArch64 state probe with a simulated counter."""
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
spec = importlib.util.spec_from_file_location('console_probe', ROOT / 'scripts/console-state-probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class InputTests(unittest.TestCase):
    def test_unknown_kernel_is_not_patched(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'source', Path(tmp) / 'output'
            source.write_bytes(b'unknown kernel')
            with self.assertRaises(ValueError):
                probe.patch_copy(source, output, ROOT.parent / 'UniXNU')
            self.assertEqual(source.read_bytes(), b'unknown kernel')
            self.assertFalse(output.exists())


@unittest.skipUnless(unicorn, 'Install unicorn in an isolated test environment for ARM64 execution tests')
class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shared = ROOT.parent / 'UniXNU/scripts/patch-xnu-entry-probe.py'
        spec = importlib.util.spec_from_file_location('shared_probe_test', shared)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            cls.code = module.assemble(probe.assembly(), 0x400000,
                                       {'gc_initialized': 0x500000, 'pe_putc': 0x501000}, Path(tmp))
        if len(cls.code) > probe.CAPACITY:
            raise AssertionError('Probe does not fit checked padding')

    def run_state(self, initialized, pointer, expected_seconds):
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
        uc.mem_map(0x400000, 0x1000)
        uc.mem_map(0x500000, 0x2000)
        uc.mem_write(0x400000, self.code)
        uc.mem_write(0x500000, bytes([initialized]))
        uc.mem_write(0x501000, struct.pack('<Q', pointer))
        before = bytes(uc.mem_read(0x500000, 0x2000))
        observed = {'counter_reads': 0, 'reset': False, 'writes': 0}

        def instruction(machine, address, size, unused):
            word = struct.unpack('<I', machine.mem_read(address, 4))[0]
            if word == 0xd53be021:  # MRS X1, CNTPCT_EL0
                machine.reg_write(arm64_const.UC_ARM64_REG_X1, observed['counter_reads'] * 19200000)
                observed['counter_reads'] += 1
                machine.reg_write(arm64_const.UC_ARM64_REG_PC, address + 4)
            elif word == 0xd4000003:  # SMC #0
                self.assertEqual(machine.reg_read(arm64_const.UC_ARM64_REG_X0), 0x84000009)
                observed['reset'] = True
                machine.emu_stop()

        def memory_write(*unused):
            observed['writes'] += 1

        uc.hook_add(unicorn.UC_HOOK_CODE, instruction)
        uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, memory_write)
        uc.emu_start(0x400000, 0x400000 + len(self.code), count=10000)
        self.assertTrue(observed['reset'])
        self.assertEqual(observed['counter_reads'] - 1, expected_seconds)
        self.assertEqual(observed['writes'], 0)
        self.assertEqual(bytes(uc.mem_read(0x500000, 0x2000)), before)

    def test_all_four_runtime_states(self):
        for initialized, pointer, seconds in [(0, 0, 4), (1, 0, 14), (0, 0x1234, 24), (1, 0x1234, 34)]:
            with self.subTest(initialized=initialized, pointer=pointer):
                self.run_state(initialized, pointer, seconds)

    def test_boolean_mask_and_full_width_pointer(self):
        self.run_state(2, 0x100000000, 24)


if __name__ == '__main__':
    unittest.main()
