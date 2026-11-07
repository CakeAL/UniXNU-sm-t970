"""V126 GMU boot fault forensics: FSR decoding, leaf repair, boot report."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / 'package/T970Gpu/GmuBoot.h'


def boot_source():
    return BOOT.read_text()


def repair_piece():
    source = boot_source()
    return source[source.index('// Linux arm-smmu documents'):source.index('static bool prepareGmuBootHfi')]


class FaultForensics(unittest.TestCase):
    def test_fsr_classes_and_descriptor_repair(self):
        body = repair_piece()
        model = r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstring>
namespace t970_gpu {
'''
        cases = r'''
} // namespace t970_gpu
using namespace t970_gpu;

int main() {
    /* FORMAT=2 alone is not a fault; the 0x408 pair is PF with stall. */
    assert(gmuFaultClass(0x00000000u) == gmuFaultNone);
    assert(gmuFaultClass(0x00000400u) == gmuFaultNone);
    assert(gmuFaultClass(0x40000000u) == gmuFaultNone);
    assert(gmuFaultClass(0x40000408u) == gmuFaultPermission);
    assert(gmuFaultClass(0x00000402u) == gmuFaultTranslation);
    assert(gmuFaultClass(0x00000410u) == gmuFaultExternal);
    assert(gmuFaultClass(0x00000420u) == gmuFaultOther);
    assert(gmuFaultClass(0x00000008u) == gmuFaultPermission);

    /* A stale read-only, privileged, execute-never leaf seen by an
     * unprivileged read: AF forced, AP[2] cleared, AP[1] set, XN kept. */
    const uint64_t xn = (UINT64_C(3) << 53);
    const uint64_t leaf = 0x0000000050000083u | xn; /* AF=0, AP=10, XN=11 */
    uint64_t fixed = gmuRepairDescriptor(leaf, 0u);
    assert((fixed & gmuPteAddress) == 0x0000000050000000u);
    assert((fixed & (1ull << 10)) != 0);   /* AF */
    assert((fixed & (1ull << 7)) == 0);    /* writable */
    assert((fixed & (1ull << 6)) != 0);    /* unprivileged */
    assert((fixed & xn) == xn);            /* data repair keeps execute-never */
    assert(fixed != leaf);

    /* Privileged write: AP[1] clear. Instruction fetch: both XN clear. */
    fixed = gmuRepairDescriptor(leaf, (1u << 5));
    assert((fixed & (1ull << 7)) == 0 && (fixed & (1ull << 6)) == 0);
    fixed = gmuRepairDescriptor(leaf, (1u << 5) | (1u << 6));
    assert((fixed & xn) == 0);
    fixed = gmuRepairDescriptor(leaf, (1u << 6));
    assert((fixed & xn) == 0 && (fixed & (1ull << 6)) != 0);

    /* An already wide-open leaf asks for no change: the caller must refuse. */
    const uint64_t open = 0x0000000050000403u; /* AF=1, AP=00, XN=00 */
    assert(gmuRepairDescriptor(open, (1u << 5)) == open);

    /* Walk the ArmSmmu4K 4 KiB layout: root at +0 slots level 2, start
     * level 1, six index bits in TTBR0's low region. */
    static uint64_t pool[3 * 512];
    memset(pool, 0, sizeof(pool));
    const GmuTableShape shape = {pool, 0x40000000u, sizeof(pool), 36u, 1u};
    uint64_t *level2 = reinterpret_cast<uint64_t *>(reinterpret_cast<uint8_t *>(pool) + 0x1000);
    uint64_t *level3 = reinterpret_cast<uint64_t *>(reinterpret_cast<uint8_t *>(pool) + 0x2000);
    const uint64_t iova = 0x60001000u;
    pool[(iova >> 30) & 0x3f] = (0x40001000u) | 3u;
    level2[(iova >> 21) & 0x1ff] = (0x40002000u) | 3u;
    level3[(iova >> 12) & 0x1ff] = 0x0000000050000707u;
    uint64_t *found = gmuLeafDescriptor(shape, iova);
    assert(found == &level3[(iova >> 12) & 0x1ff]);
    assert(*found == 0x0000000050000707u);
    /* The walk returns the leaf slot; the caller still refuses a non-leaf
     * word before it compares the physical address. */
    uint64_t *empty = gmuLeafDescriptor(shape, iova + 0x1000);
    assert(empty != nullptr && (*empty & 3) != 3);
    assert(gmuLeafDescriptor(shape, iova | 0x10) == nullptr);
    assert(gmuLeafDescriptor(shape, UINT64_C(1) << 36) == nullptr);
    assert(gmuLeafDescriptor(shape, 0) == nullptr);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp, exe = Path(tmp) / 'fault.cpp', Path(tmp) / 'fault'
            cpp.write_text(model + body + cases.replace('privilegedRead()', '(1u << 5)'))
            subprocess.run(['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_boot_report_carries_the_fault(self):
        source = boot_source()
        self.assertIn('static constexpr unsigned maxFaults = 3;', source)
        self.assertIn('GmuFault fault[maxFaults] = {};', source)
        self.assertIn('f.far = read(smmu, cbFar) | (static_cast<uint64_t>(read(smmu, cbFar + 4)) << 32);',
                      source)
        self.assertIn('if (gmuFaultClass(fsr) != gmuFaultPermission) return stop(\'t\');', source)
        self.assertIn('if (f.fsynr & (1u << 10)) return stop(\'t\');', source)
        self.assertIn('write(smmu, cbFsr, fsr);', source)
        self.assertIn('write(smmu, cbResume, 0);', source)
        self.assertIn('f.resumed = true;', source)

    def test_report_and_mode_wiring(self):
        report = (ROOT / 'package/T970Gpu/RscSnapshot.h').read_text()
        self.assertIn('if (isBootMode(power)) {', report)
        self.assertIn('"\\nGPU pf%u fsr=%x far=%x/%x syn=%x sid=%x pte=%x/%x fix=%c%c rs=%u"', report)
        smmu = (ROOT / 'package/T970Gpu/SmmuSnapshot.h').read_text()
        self.assertIn('constexpr unsigned cbBootRepairMode = 23;', smmu)
        self.assertIn('startGmuBoot(gmu, smmu, *bootTables, result.boot, power == cbBootRepairMode,', smmu)
        clock = (ROOT / 'package/T970Gpu/ClockSnapshot.h').read_text()
        self.assertIn('static char firstReport[512];', clock)
        self.assertIn('if (power == cbFirmwareMode || isBootMode(power)) return power;', clock)


if __name__ == '__main__':
    unittest.main()
