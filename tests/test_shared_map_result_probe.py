"""Execute real return/panic stub instructions and check Darwin vararg ABI."""
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
spec = importlib.util.spec_from_file_location('map_result', ROOT / 'scripts/shared-map-result-probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class InputTests(unittest.TestCase):
    def test_actual_pinned_copy_when_local_inputs_exist(self):
        source = ROOT.parent / 'UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/kernel/kernel.macho'
        normal = ROOT / 'out/step7/probes/ufs-policy-memory/independent/kernel.macho'
        if not source.exists() or not normal.exists():
            self.skipTest('Local qualified diagnostic inputs are unavailable')
        before_source, before_normal = source.read_bytes(), normal.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'kernel.macho'
            result = probe.patch_copy(source, normal, out, ROOT.parent / 'UniXNU')
            patched = out.read_bytes()
            self.assertEqual(len(patched), len(before_normal))
            import sys
            sys.path.insert(0, str(ROOT.parent / 'UniXNU/kits/XnuPrelink'))
            import native_prelink
            meta = native_prelink.macho(before_normal)
            call = native_prelink.backed_offset(meta['segments'], probe.CALL_SITE, 4, len(patched))
            gap = native_prelink.backed_offset(meta['segments'], probe.GAP, probe.CAPACITY, len(patched))
            for lo, hi in ((0, gap), (gap + probe.CAPACITY, call), (call + 4, len(patched))):
                self.assertEqual(patched[lo:hi], before_normal[lo:hi])
            self.assertFalse(result['reset_probe'])
        self.assertEqual(source.read_bytes(), before_source)
        self.assertEqual(normal.read_bytes(), before_normal)

    def test_unknown_source_is_refused_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, normal, out = (Path(tmp) / n for n in ('source', 'normal', 'output'))
            src.write_bytes(b'unknown'); normal.write_bytes(b'unknown')
            with self.assertRaises(ValueError):
                probe.patch_copy(src, normal, out, ROOT.parent / 'UniXNU')
            self.assertFalse(out.exists())
            self.assertEqual(src.read_bytes(), b'unknown')
            self.assertEqual(normal.read_bytes(), b'unknown')


@unittest.skipUnless(unicorn, 'Use isolated probe-test environment for ARM64 execution')
class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('shared_map_test', ROOT.parent / 'UniXNU/scripts/patch-xnu-entry-probe.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            cls.code = module.assemble(probe.assembly(), 0x400000,
                {'callee': 0x401000, 'panic': 0x402000}, Path(tmp))
        if len(cls.code) > probe.CAPACITY:
            raise AssertionError('Stub exceeds reviewed padding')

    def test_return_value_and_stack_abi(self):
        for status in (0, 1, 2, 3, 5, 0xffffffff):
            with self.subTest(status=status):
                uc = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
                uc.mem_map(0x400000, 0x3000); uc.mem_map(0x500000, 0x4000)
                uc.mem_write(0x400000, self.code)
                uc.reg_write(regs.UC_ARM64_REG_SP, 0x503000)
                for register, value in [(regs.UC_ARM64_REG_X0, 0x123456789),
                                        (regs.UC_ARM64_REG_X1, 0x23456789a),
                                        (regs.UC_ARM64_REG_X2, 0x3456789ab)]:
                    uc.reg_write(register, value)
                seen = {'calls': 0, 'panic': False, 'writes': []}

                def instruction(machine, address, size, unused):
                    if address == 0x401000:
                        self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X0), 0x123456789)
                        self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X1), 0x23456789a)
                        self.assertEqual(machine.reg_read(regs.UC_ARM64_REG_X2), 0x3456789ab)
                        seen['calls'] += 1
                        machine.reg_write(regs.UC_ARM64_REG_W0, status)
                        machine.reg_write(regs.UC_ARM64_REG_PC, machine.reg_read(regs.UC_ARM64_REG_X30))
                    elif address == 0x402000:
                        sp = machine.reg_read(regs.UC_ARM64_REG_SP)
                        self.assertEqual(sp, 0x502ff0)
                        self.assertEqual(struct.unpack('<Q', machine.mem_read(sp, 8))[0], status)
                        text = bytes(machine.mem_read(machine.reg_read(regs.UC_ARM64_REG_X0), 40)).split(b'\0')[0]
                        self.assertEqual(text, b'diagnostic: dyld shared map kr=%d')
                        seen['panic'] = True
                        machine.emu_stop()

                def write(machine, access, address, size, value, unused):
                    seen['writes'].append((address, size))

                uc.hook_add(unicorn.UC_HOOK_CODE, instruction)
                uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, write)
                uc.emu_start(0x400000, 0x400000 + len(self.code), count=100)
                self.assertTrue(seen['panic'])
                self.assertEqual(seen['calls'], 1)
                self.assertEqual(seen['writes'], [(0x502ff0, 8)])
