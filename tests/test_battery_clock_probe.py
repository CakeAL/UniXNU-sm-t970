"""The actual battery clock observer must restore HWCG and refuse missing owners."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BatteryClock(unittest.TestCase):
    def test_restore_and_gating(self):
        source = (ROOT / 'package/T970Power/BusSnapshot.h').read_text()
        body = source[source.index('static void reportClockProbe('):source.index('static void reportBus(')]
        before = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
struct IOMemoryMap { bool engine=false, canRun=true; uint32_t votes=0, slave=2; };
static IOMemoryMap *active;
static unsigned writes=0, reads=0;
namespace t970_touch {
struct EngineSnapshot { const char *state="off"; uint32_t firmware=0,fifoOff=0,status=0; };
struct Map { IOMemoryMap v{true,true,0,0}; explicit operator bool()const{return true;}
    IOMemoryMap &operator*(){return v;} };
static Map mapMmio(uint64_t base,uint64_t size) { assert(base==0x980000 && size==0x4000); return {}; }
static uint32_t read(IOMemoryMap &m,unsigned offset) {
    if(m.engine) {
        assert(!(active->slave&2) && active->canRun); ++reads;
        active->slave|=0x1000; /* unrelated owner changes another bit */
        assert(offset==0x68 || offset==0x64 || offset==0x40);
        return offset==0x68?0x203:0;
    }
    if(offset==0x52008)return m.votes;
    if(offset==0x1700c)return 0x4220;
    if(offset==0x17004)return 0;
    assert(offset==0x17008);
    return m.slave | ((m.slave&2 || !m.canRun)?0x80000000:0);
}
static void writeMasked(IOMemoryMap &m,unsigned offset,uint32_t mask,uint32_t value) {
    assert(!m.engine && offset==0x17008 && mask==2);
    m.slave=(m.slave&~mask)|(value&mask); ++writes;
}
}
static void IODelay(unsigned us){assert(us==1);}
'''
        after = r'''
int main() {
    char out[256];
    IOMemoryMap m; active=&m;
    reportClockProbe(m,out,sizeof out);
    assert(strstr(out,"refused") && writes==0 && reads==0 && m.slave==2);
    m.votes=(1<<10)|(1<<6)|(1<<7); m.canRun=false;
    reportClockProbe(m,out,sizeof out);
    assert(strstr(out,"restore=1 SE=off") && writes==2 && reads==0 && m.slave==2);
    writes=0; m.canRun=true;
    reportClockProbe(m,out,sizeof out);
    assert(strstr(out,"restore=1 SE=read fw=203 fifoOff=0 st=0"));
    assert(writes==2 && reads==3 && m.slave==0x1002);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp, exe = Path(tmp) / 'clock.cpp', Path(tmp) / 'clock'
            cpp.write_text(before + body + after)
            subprocess.run(['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
