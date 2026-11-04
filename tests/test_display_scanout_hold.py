"""Verify that the diagnostic can close admission while a CPU copy drains."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class DisplayScanoutHold(unittest.TestCase):
    def test_drain_and_foreign_completion(self):
        source = (Path(__file__).resolve().parents[1] / 'package/T970Display/DisplayRegistration.cpp').read_text()
        functions = source[source.index('static bool reserveScanout'):source.index('extern "C" bool native_legacy_prepare_scanout')]
        program = r'''
#include <cassert>
using thread_t = int *;
#define THREAD_NULL nullptr
static bool reportTracksScanout;
static bool reportOwnsScanout;
static thread_t scanoutWriter;
''' + functions + r'''
int main() {
    int writer = 0, other = 0;
    assert(native_t970_display_hold() == -1);
    reportTracksScanout = true;
    assert(reserveScanout(&writer));
    assert(reserveScanout(&writer)); // surface path checks twice
    assert(!reserveScanout(&other));
    releaseScanout(&other); // rejected transfer cannot clear the active writer
    assert(native_t970_display_hold() == 1);
    assert(!reserveScanout(&other));
    assert(!reserveScanout(&writer)); // a later check sees the closed admission
    releaseScanout(&writer);
    assert(native_t970_display_hold() == 0);
    assert(!reserveScanout(&writer)); // admission stays closed after draining
}
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'hold.cpp').write_text(program)
            subprocess.run(['xcrun', 'clang++', '-Wall', '-Wextra', '-Werror',
                            str(path / 'hold.cpp'), '-o', str(path / 'hold')], check=True)
            subprocess.run([str(path / 'hold')], check=True)
