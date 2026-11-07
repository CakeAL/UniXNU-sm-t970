"""Exercise the actual board bit-bang transport against an I2C wire-state model."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODEL = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>
struct IOMemoryMap {
    bool sda=true, scl=true, slave=true, stuck=false, nack=false, collision=false;
    enum { Idle, Write, Read } mode=Idle;
    unsigned bits=0, value=0, index=0, ack=0, starts=0, stops=0;
    bool address=true;
    std::vector<unsigned> tx, masterAcks;
    uint8_t rx[2]={0x80,0xd4};
    void start() { ++starts; mode=Write; bits=value=ack=0; address=true; slave=true; }
    void rise() {
        if (mode==Write) {
            if (bits<8) {
                value=(value<<1)|unsigned(sda); ++bits;
                slave=!(collision && sda);
            } else { slave=nack; ack=1; }
        } else if (mode==Read) {
            if(bits<8) { slave=bool((rx[index]>>(7-bits))&1); ++bits; }
            else { masterAcks.push_back(unsigned(sda)); slave=true; ack=2; }
        }
    }
    void fall() {
        if (ack==1) {
            tx.push_back(value);
            if (address && (value&1)) { mode=Read; index=0; }
            address=false; bits=value=0;
        } else if (ack==2) {
            if (sda) mode=Idle;
            else ++index;
            bits=0;
        }
        ack=0; slave=true;
    }
};
static uint32_t read(IOMemoryMap &m,unsigned offset) {
    assert(offset==4 || offset==0x1004);
    return offset==4 ? unsigned(m.sda && m.slave) : unsigned(m.scl && !m.stuck);
}
static void writeMasked(IOMemoryMap &m,unsigned offset,uint32_t mask,uint32_t value) {
    assert(mask==(1u<<9) && (offset==0 || offset==0x1000));
    bool high=!(value&mask);
    if(offset==0) {
        bool old=m.sda; m.sda=high;
        if(m.scl && old!=high) {
            if(!high) m.start();
            else { ++m.stops; m.mode=IOMemoryMap::Idle; m.slave=true; }
        }
    } else {
        bool old=m.scl; m.scl=high;
        if(old!=high && !m.stuck) { if(high)m.rise();else m.fall(); }
    }
}
static void IODelay(unsigned) {}
'''
CASES = r'''
int main() {
    for(uint8_t address : {uint8_t(0x49),uint8_t(0x36),uint8_t(0x66),uint8_t(0x69)}) {
        IOMemoryMap m;
        ProbeBus bus(m,address);
        uint8_t reg=9, bytes[2]={};
        assert(bus.transfer(&reg,1,bytes,2));
        assert(bytes[0]==0x80 && bytes[1]==0xd4 && bus.bytesRead==2 && bus.stopped);
        assert(m.tx==std::vector<unsigned>({unsigned(address<<1),9,unsigned((address<<1)|1)}));
        assert(m.masterAcks==std::vector<unsigned>({0,1}));
        assert(m.starts==2 && m.stops==1 && m.sda && m.scl);
    }
    IOMemoryMap touch;
    ProbeBus defaultTouch(touch);
    uint8_t scan[]={0xa0,0,1};
    assert(defaultTouch.transfer(scan,3));
    assert(touch.tx==std::vector<unsigned>({0x92,0xa0,0,1}));
    IOMemoryMap nack; nack.nack=true;
    ProbeBus rejected(nack,0x36); uint8_t reg=9;
    assert(!rejected.transfer(&reg,1) && !strcmp(rejected.fault,"nack") && rejected.stopped);
    IOMemoryMap stuck; stuck.stuck=true;
    ProbeBus timeout(stuck,0x36);
    assert(!timeout.transfer(&reg,1) && !strcmp(timeout.fault,"scl-low"));
    IOMemoryMap arb; arb.collision=true;
    ProbeBus lost(arb,0x36);
    assert(!lost.transfer(&reg,1) && !strcmp(lost.fault,"arbitration") && arb.stops==0);
}
'''


class GpioI2c(unittest.TestCase):
    def test_wire_protocol(self):
        source = (ROOT / 'package/T970Touch/BusSnapshot.h').read_text()
        body = source[source.index('class ProbeBus {'):source.index('// SEC fts1ba90a FIFO')]
        with tempfile.TemporaryDirectory() as tmp:
            cpp, exe = Path(tmp) / 'wire.cpp', Path(tmp) / 'wire'
            cpp.write_text(MODEL + body + CASES)
            subprocess.run(['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
