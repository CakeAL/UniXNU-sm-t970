"""Execute the real trace predicate, pass-through and terminal stack arguments."""
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
spec = importlib.util.spec_from_file_location('postmap', ROOT / 'scripts/post-map-syscall-probe.py')
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)


@unittest.skipUnless(unicorn, 'Use isolated probe-test environment')
class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('postmap_shared', ROOT.parent / 'UniXNU/scripts/patch-xnu-entry-probe.py')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            cls.code = m.assemble(probe.assembly(), 0x400000, {'callee': 0x401000,
                'panic': 0x402000, 'continuation': 0x403000, 'message': 0x400100,
                'signature': 0x400118, 'trace_count': 0x500000, 'trace_rows': 0x501004}, Path(tmp))
        if len(cls.code) > probe.CAPACITY:
            raise AssertionError('Stub exceeds padding')

    def run_case(self, pid, count, prefix, terminal, code=74, error=0):
        u = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
        u.mem_map(0x400000, 0x4000); u.mem_map(0x500000, 0x2000); u.mem_map(0x600000, 0x4000)
        u.mem_write(0x400000, self.code); u.mem_write(0x400100, probe.DATA)
        u.mem_write(0x500000, struct.pack('<I', count))
        if count:
            u.mem_write(0x501004 + ((count - 1) % 24) * 128, prefix)
        before = bytes(u.mem_read(0x500000, 0x2000))
        args = [0x123456789, (1 << 32) | code, (1 << 32) | error, 0x3456789ab]
        for register, value in zip([regs.UC_ARM64_REG_X0, regs.UC_ARM64_REG_X1, regs.UC_ARM64_REG_X2, regs.UC_ARM64_REG_X3], args):
            u.reg_write(register, value)
        u.reg_write(regs.UC_ARM64_REG_X24, pid); u.reg_write(regs.UC_ARM64_REG_SP, 0x604000)
        seen = {'callback': 0, 'panic': False, 'continued': False, 'writes': []}

        def hook(machine, address, size, unused):
            if address == 0x401000:
                self.assertEqual([machine.reg_read(r) for r in [regs.UC_ARM64_REG_X0, regs.UC_ARM64_REG_X1, regs.UC_ARM64_REG_X2, regs.UC_ARM64_REG_X3]], args)
                self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X30), 0x403000)
                self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_SP), 0x604000)
                seen['callback'] += 1; machine.reg_write(regs.UC_ARM64_REG_PC, 0x403000)
            elif address == 0x403000:
                seen['continued'] = True; machine.emu_stop()
            elif address == 0x402000:
                sp = machine.reg_read(regs.UC_ARM64_REG_SP)
                self.assertEqual(sp, 0x603ff0)
                self.assertEqual(struct.unpack('<QQ', machine.mem_read(sp, 16)), tuple(args[1:3]))
                self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X0), 0x400100)
                seen['panic'] = True; machine.emu_stop()

        def write(machine, access, address, size, value, unused):
            seen['writes'].append((address, size))

        u.hook_add(unicorn.UC_HOOK_CODE, hook); u.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
        u.emu_start(0x400000, 0x400000 + len(self.code), count=100)
        self.assertEqual(seen['panic'], terminal); self.assertEqual(seen['continued'], not terminal)
        self.assertEqual(seen['callback'], 0 if terminal else 1)
        self.assertEqual(bytes(u.mem_read(0x500000, 0x2000)), before)
        self.assertEqual(seen['writes'], [(0x603ff0, 8), (0x603ff8, 8)] if terminal else [])

    def test_successful_mapping_predicate_and_ring_wrap(self):
        for count in (1, 24, 25, 0xffffffff):
            for error in (0, 13):
                with self.subTest(count=count, error=error):
                    self.run_case(1, count, b'sc536 e0', True, error=error)

    def test_passthrough_without_matching_prior_success(self):
        for pid, count, prefix in [(2, 1, b'sc536 e0'), (1, 0, b''),
                                   (1, 1, b'sc536 e1'), (1, 1, b'sc294 e0')]:
            with self.subTest(pid=pid, count=count, prefix=prefix):
                self.run_case(pid, count, prefix, False)


class InputTests(unittest.TestCase):
    def test_unknown_kernel_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, normal, out = (Path(tmp) / x for x in ('source', 'normal', 'output'))
            src.write_bytes(b'unknown'); normal.write_bytes(b'unknown')
            with self.assertRaises(ValueError):
                probe.patch_copy(src, normal, out, ROOT.parent / 'UniXNU')
            self.assertFalse(out.exists())
