"""SM8250 GPU ARC resource parser and read-only report wiring."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GpuArc(unittest.TestCase):
    def test_parse_and_refusals(self):
        source = (ROOT / 'package/T970Gpu/ArcResources.h').read_text()
        body = source[source.index('struct ArcResource {'):source.index('// Read-only: the ARC block')]
        model = r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
static void put16(uint8_t *p, unsigned v) { p[0]=v; p[1]=v>>8; }
static void put32(uint8_t *p, unsigned v) { put16(p,v); put16(p+2,v>>16); }
static void putId(uint8_t *p, const char *id) { memcpy(p,id,8); }
'''
        cases = r'''
int main() {
    uint8_t db[512] = {};
    put32(db + 4, 0x0c0330db);
    /* Section 0: type 3, entries at 144, data at 192, two entries. */
    put16(db + 8, 3); put16(db + 10, 0); put16(db + 12, 48); put16(db + 14, 2);
    putId(db + 144, "cx.lvl\0\0");
    put32(db + 144 + 16, 0x30000); put16(db + 144 + 20, 8); put16(db + 144 + 22, 0);
    putId(db + 168, "mx.lvl\0\0");
    put32(db + 168 + 16, 0x38000); put16(db + 168 + 20, 6); put16(db + 168 + 22, 8);
    put16(db + 192 + 0, 0); put16(db + 192 + 2, 16);
    put16(db + 192 + 4, 32); put16(db + 192 + 6, 48);
    put16(db + 200 + 0, 0); put16(db + 200 + 2, 32); put16(db + 200 + 4, 48);

    ArcResource cx, mx;
    assert(parseArc(db, sizeof(db), "cx.lvl\0", cx));
    assert(cx.valid && cx.address == 0x30000 && cx.levels == 4 && cx.minSvs == 3 &&
           cx.first == 0 && cx.last == 48 && cx.level[2] == 32 && cx.level[3] == 48);
    char list[64];
    formatArcLevels(cx, list, sizeof(list));
    assert(!strcmp(list, "0,16,32,48"));
    assert(parseArc(db, sizeof(db), "mx.lvl\0", mx));
    assert(mx.valid && mx.address == 0x38000 && mx.levels == 3 && mx.minSvs == 2);

    uint8_t bad[512];
    memcpy(bad, db, sizeof(bad));
    put32(bad + 4, 0);
    ArcResource r;
    assert(!parseArc(bad, sizeof(bad), "cx.lvl\0", r));

    memcpy(bad, db, sizeof(bad));
    putId(bad + 168, "cx.lvl\0\0"); /* duplicate id must be refused */
    assert(!parseArc(bad, sizeof(bad), "cx.lvl\0", r));

    memcpy(bad, db, sizeof(bad));
    put16(bad + 192 + 4, 8); /* levels must increase strictly */
    assert(!parseArc(bad, sizeof(bad), "cx.lvl\0", r));

    memcpy(bad, db, sizeof(bad));
    put32(bad + 144 + 16, 0x30002); /* ARC address must be dword aligned */
    assert(!parseArc(bad, sizeof(bad), "cx.lvl\0", r));
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp, exe = Path(tmp) / 'arc.cpp', Path(tmp) / 'arc'
            cpp.write_text(model + body + cases)
            subprocess.run(['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_gpll0_hz(self):
        source = (ROOT / 'package/T970Gpu/ClockSnapshot.h').read_text()
        body = source[source.index('static inline uint64_t gpll0Hz'):source.index('static void reportClock')]
        cases = r"""
#include <cassert>
#include <cstdint>
int main() {
    assert(gpll0Hz(30, 0) == 576000000ull);
    assert(gpll0Hz(30, 0x8000) == 585600000ull);
    assert(gpll0Hz(31, 0) == 595200000ull);
    assert(gpll0Hz(0, 0xffff) == 19199707ull);
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            cpp, exe = Path(tmp) / 'clk.cpp', Path(tmp) / 'clk'
            cpp.write_text('#include <cstdint>\n' + body + cases)
            subprocess.run(['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_report_is_read_only_and_integrated(self):
        header = (ROOT / 'package/T970Gpu/ArcResources.h').read_text()
        self.assertIn('mapMmio(0x80860000, 0x20000)', header)
        self.assertIn('GPU arc db=%x cx=%x lv=%u [%s] min=%u mx=%x lv=%u [%s] min=%u', header)
        self.assertNotIn('writeMasked', header)
        display = (ROOT / 'package/T970Display/DisplayRegistration.cpp').read_text()
        self.assertEqual(display.count('reportGpu(out + used,'), 2)
        self.assertIn('if (mode != 5 && mode != 7) t970_gpu::reportArc(out, length);', display)
        self.assertIn('t970_gpu::reportClock(', display)
        self.assertIn('PE_parse_boot_argn("t970-gpu-w"', display)

    def test_gpu_branch_gate_write_is_restored(self):
        clock = (ROOT / 'package/T970Gpu/ClockSnapshot.h').read_text()
        self.assertIn('mapMmio(0x100000, 0x80000, writeGate ? 0 : kIOMapReadOnly)', clock)
        self.assertIn('writeMasked(*gcc, 0x52000, divGate, divGate);', clock)
        self.assertIn('writeMasked(*gcc, 0x52000, divGate, branch & divGate);', clock)
        self.assertIn('restore=%u', clock)


if __name__ == '__main__':
    unittest.main()
