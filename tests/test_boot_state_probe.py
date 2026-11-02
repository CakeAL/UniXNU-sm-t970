"""Run the real tail-call wrapper with preserved arguments, frame and main state."""
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
spec = importlib.util.spec_from_file_location('main_probe', ROOT / 'scripts/boot-state-probe.py')
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)


@unittest.skipUnless(unicorn, 'Use isolated probe-test environment')
class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('main_shared', ROOT.parent / 'UniXNU/scripts/patch-xnu-entry-probe.py')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            cls.code = m.assemble(probe.assembly(), 0x400000, {'callee': 0x401000,
                'panic': 0x402000, 'marker': 0x500000, 'message': 0x400100, 'data_status': 0x500004, 'policy_status': 0x500008, 'policy_stage': 0x50000c}, Path(tmp))
        if len(cls.code) > probe.CAPACITY:
            raise AssertionError('Stub exceeds padding')

    def run_case(self, marker_after, error, data=0, policy=0, stage=4):
        u = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
        u.mem_map(0x400000, 0x4000); u.mem_map(0x500000, 0x1000); u.mem_map(0x600000, 0x4000)
        u.mem_write(0x400000, self.code); u.mem_write(0x400100, probe.MESSAGE)
        states = (data & 0xffffffff, policy & 0xffffffff, stage & 0xffffffff)
        u.mem_write(0x500004, struct.pack('<III', *states))
        args = [0x123456789, 0x23456789a, 0, 0x3456789ab]
        for r, value in zip([regs.UC_ARM64_REG_X0, regs.UC_ARM64_REG_X1, regs.UC_ARM64_REG_X2, regs.UC_ARM64_REG_X3], args):
            u.reg_write(r, value)
        u.reg_write(regs.UC_ARM64_REG_X29, 0x603000); u.reg_write(regs.UC_ARM64_REG_X30, 0x403000)
        u.reg_write(regs.UC_ARM64_REG_SP, 0x604000)
        seen = {'handler': 0, 'panic': False, 'return': False, 'writes': []}
        returned = (1 << 32) | error

        def hook(machine, address, size, unused):
            if address == 0x401000:
                self.assertEqual([machine.reg_read(r) for r in [regs.UC_ARM64_REG_X0, regs.UC_ARM64_REG_X1, regs.UC_ARM64_REG_X2, regs.UC_ARM64_REG_X3]], args)
                seen['handler'] += 1
                machine.mem_write(0x500000, struct.pack('<I', marker_after))
                machine.reg_write(regs.UC_ARM64_REG_X0, returned)
                machine.reg_write(regs.UC_ARM64_REG_PC, machine.reg_read(regs.UC_ARM64_REG_X30))
            elif address in (0x402000, 0x403000):
                self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X29), 0x603000)
                if address == 0x402000:
                    self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_SP), 0x603fd0)
                    self.assertEqual(struct.unpack('<QQQQQ', machine.mem_read(0x603fd0, 40)), (1, returned, *states))
                    self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X0), 0x400100)
                    seen['panic'] = True
                else:
                    self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_SP), 0x604000)
                    self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X0), returned)
                    seen['return'] = True
                machine.emu_stop()

        def write(machine, access, address, size, value, unused):
            seen['writes'].append((address, size))

        u.hook_add(unicorn.UC_HOOK_CODE, hook); u.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
        u.emu_start(0x400000, 0x400000 + len(self.code), count=100)
        self.assertEqual(seen['handler'], 1); self.assertEqual(seen['panic'], marker_after == 1)
        self.assertEqual(seen['return'], marker_after != 1)
        self.assertTrue(all(0x603fd0 <= address < 0x604000 for address, size in seen['writes']))
        self.assertEqual(struct.unpack('<I', u.mem_read(0x500000, 4))[0], marker_after)
        self.assertEqual(struct.unpack('<III', u.mem_read(0x500004, 12)), states)

    def test_real_setter_result_and_unchanged_marker(self):
        for marker in (0, 1, 2):
            for error in (0, 1, 14):
                for data, policy, stage in ((0, 0, 4), (13, -1, 2), (0, 5, 3)):
                    with self.subTest(marker=marker, error=error, data=data, policy=policy, stage=stage):
                        self.run_case(marker, error, data, policy, stage)


class InputTests(unittest.TestCase):
    def test_unknown_kernel_refused_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, normal, out = (Path(tmp) / x for x in ('source', 'normal', 'output'))
            source.write_bytes(b'unknown'); normal.write_bytes(b'unknown')
            with self.assertRaises(ValueError):
                probe.patch_copy(source, normal, out, ROOT.parent / 'UniXNU')
            self.assertFalse(out.exists())
