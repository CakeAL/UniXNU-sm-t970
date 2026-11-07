"""Board GPIO ownership/restore and read-only gauge transaction plan."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GaugeProbe(unittest.TestCase):
    def test_gpio_restore_and_register_plan(self):
        source = (ROOT / 'package/T970Power/GaugeProbe.h').read_text()
        body = source[source.index('static void reportGauge('):source.rfind('\n}')]
        model = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "package/T970Power/Max77705Measurements.h"
struct IOMemoryMap { uint32_t cfg[2]={7,7}, io[2]={3,3}; };
static IOMemoryMap pins;
static unsigned writes=0, transfers=0;
static bool nack=false, unknown=false;
namespace t970_touch {
struct Map { explicit operator bool()const{return true;} IOMemoryMap &operator*(){return pins;} };
static Map mapMmio(uint64_t base,uint64_t size,unsigned options) {
    assert(base==0xf91c000 && size==0x2000 && options==0);return {};
}
static uint32_t read(IOMemoryMap &m,unsigned offset) {
    assert(offset==0 || offset==4 || offset==0x1000 || offset==0x1004);
    unsigned pin=offset/0x1000;return (offset&4)?m.io[pin]:m.cfg[pin];
}
static void writeMasked(IOMemoryMap &m,unsigned offset,uint32_t mask,uint32_t value) {
    assert(offset==0 || offset==4 || offset==0x1000 || offset==0x1004);
    assert(mask==((offset&4)?2u:0x23cu));
    auto &v=(offset&4)?m.io[offset/0x1000]:m.cfg[offset/0x1000];
    v=(v&~mask)|(value&mask);++writes;
}
class ProbeBus {
    unsigned address;
public:
    const char *fault="none";
    ProbeBus(IOMemoryMap &,uint8_t a):address(a){}
    bool transfer(const uint8_t *command,unsigned count,uint8_t *data,unsigned size) {
        assert(count==1 && size>0); /* No PMIC configuration writes. */
        assert(pins.cfg[0]==3 && pins.cfg[1]==3 && pins.io[0]==1 && pins.io[1]==1);
        ++transfers;
        if(address==0x66) { assert(*command==0 && size==2);data[0]=unknown?0:0x15;data[1]=2;return true; }
        if(address==0x69) { assert(*command==0xb2 && size==3);data[0]=0x40;data[1]=0x60;data[2]=3;return true; }
        assert(address==0x36 && size==2);
        if(nack){fault="nack";return false;}
        uint16_t value;
        switch(*command) {
        case 0:value=0;break; case 6:value=0x6400;break;case 9:value=0xd480;break;
        case 10:value=0xfe00;break;case 8:value=0x1980;break;case 5:case 16:value=0xfc4;break;
        default:assert(false);return false;
        }
        data[0]=value&255;data[1]=value>>8;return true;
    }
};
}
static void IODelay(unsigned us){assert(us==100);}
'''
        cases = r'''
int main() {
    char text[512];
    pins.cfg[0]=6;
    reportGauge(text,sizeof text);
    assert(strstr(text,"refused pins=6/7") && writes==0 && transfers==0);
    pins={};
    reportGauge(text,sizeof text);
    assert(strstr(text,"id=15/02 valid=7f"));
    assert(strstr(text,"soc100=10000 uV=4250000 uA=-400000 mC=25500 cap=10090/10090"));
    assert(strstr(text,"chg=1:40/60/03 restore=1 done/none"));
    assert(transfers==9 && pins.cfg[0]==7 && pins.cfg[1]==7 && pins.io[0]==3 && pins.io[1]==3);
    nack=true;transfers=0;
    reportGauge(text,sizeof text);
    assert(strstr(text,"valid=0") && strstr(text,"restore=1 gauge-read/nack"));
    assert(transfers==2 && pins.cfg[0]==7 && pins.cfg[1]==7 && pins.io[0]==3 && pins.io[1]==3);
    nack=false;unknown=true;transfers=0;
    reportGauge(text,sizeof text);
    assert(transfers==1 && strstr(text,"restore=1 pmic-id/none"));
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp, exe = Path(tmp) / 'gauge.cpp', Path(tmp) / 'gauge'
            cpp.write_text(model + body + cases)
            subprocess.run(['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-I', str(ROOT),
                            str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
