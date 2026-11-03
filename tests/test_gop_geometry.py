"""Exercise the actual board geometry helper with host clang++."""
from pathlib import Path
import subprocess
import tempfile
import unittest

class Geometry(unittest.TestCase):
    def test_measured_mode_and_rejections(self):
        header = Path(__file__).resolve().parents[1] / 'package/T970Display'
        code = r'''#include "T970GopGeometry.h"
#include <assert.h>
int main() {
    uint64_t v[] = {0x9c000000ULL,2800,1752,11200,32,0};
    auto valid = [&]() { return t970GopGeometry(v[0],v[1],v[2],v[3],v[4],v[5]); };
    assert(valid());
    for(unsigned i=0;i<6;++i) {
        uint64_t saved=v[i];
        v[i]=~uint64_t(0); assert(!valid());
        v[i]=saved+1; assert(!valid());
        if(saved) { v[i]=0; assert(!valid()); }
        v[i]=saved;
    }
    assert(valid());
}
'''
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'test.cpp'; source.write_text(code)
            binary=Path(d)/'test'
            subprocess.run(['xcrun','clang++','-std=c++17','-Wall','-Wextra','-Werror',
                            '-I',str(header),str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
