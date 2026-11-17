#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Run the display's actual direct-scanout cadence accounting with a fake clock."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'NativeLegacyDisplay.cpp'
text = source.read_text()
start = text.index('    uint64_t validatedUs(')
end = text.index('    static void latchFired(', start)
methods = text[start:end]

harness = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
static uint64_t native_t970_cadence[10];
static uint64_t native_t970_gap_phase[8];
static void absolutetime_to_nanoseconds(uint64_t ticks,uint64_t *out) {*out=ticks;}
struct OriginalLegacySwapRequest {};
struct Display {
    uint64_t latchStart=0,lastLatchAck=0;
    const OriginalLegacySwapRequest *validated[8]={};
    uint64_t validatedAt[8]={};
#include "methods.inc"
};
int main() {
    Display d;
    OriginalLegacySwapRequest a,b,c;
    d.recordDirectGap(1000000,&a);
    assert(native_t970_cadence[0]==0);

    d.latchStart=1000000;
    d.recordDirectAck(2500000,true);
    assert(native_t970_cadence[4]==1 && native_t970_cadence[5]==1500 && native_t970_cadence[6]==1500);
    assert(native_t970_cadence[7]==0 && d.lastLatchAck==2500000);

    d.validated[0]=&a;d.validatedAt[0]=12500;
    d.recordDirectGap(24500000,&a);
    assert(native_t970_cadence[0]==1 && native_t970_cadence[1]==22000 && native_t970_cadence[2]==22000);
    assert(native_t970_cadence[3]==1);
    assert(native_t970_gap_phase[0]==1 && native_t970_gap_phase[1]==10000 && native_t970_gap_phase[4]==12000);
    assert(native_t970_gap_phase[3]==1 && native_t970_gap_phase[6]==1 && native_t970_gap_phase[7]==0);

    d.latchStart=24500000;
    d.recordDirectAck(28500000,true);
    assert(native_t970_cadence[4]==2 && native_t970_cadence[5]==5500 && native_t970_cadence[6]==4000);
    assert(native_t970_cadence[7]==1 && d.lastLatchAck==28500000);

    d.validated[1]=&b;d.validatedAt[1]=20000;
    d.recordDirectGap(129000000,&b);
    assert(native_t970_cadence[0]==1 && native_t970_cadence[9]==1);
    assert(native_t970_gap_phase[0]==1);

    d.lastLatchAck=30000000;d.validated[2]=&c;d.validatedAt[2]=29000;
    d.recordDirectGap(35000000,&c);
    assert(native_t970_gap_phase[0]==2 && native_t970_gap_phase[7]==1);
    assert(native_t970_gap_phase[1]==10000 && native_t970_gap_phase[4]==17000);

    d.latchStart=129000000;
    d.recordDirectAck(179000000,false);
    assert(native_t970_cadence[8]==1 && d.lastLatchAck==0 && native_t970_cadence[4]==2);
    d.recordDirectGap(180000000,&a);
    assert(native_t970_cadence[0]==2);
    std::puts("PASS: actual display cadence methods split gap/ack and arrival/post-arrival phases");
}
'''

with tempfile.TemporaryDirectory(prefix='gop-cadence-') as directory:
    root = Path(directory)
    (root / 'methods.inc').write_text(methods)
    (root / 'test.cpp').write_text(harness)
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(root / 'test.cpp'), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True)
