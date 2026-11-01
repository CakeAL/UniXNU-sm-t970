#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include "T970TransportPreflight.h"
int main() {
  using namespace t970_preflight;
  assert(ownsDma(0xc0000000,0x10000000,0xc0100000,0x22000,0x22000));
  assert(!ownsDma(0xc0000000,0x10000000,0xbffff000,4096,4096));
  assert(!ownsDma(0xc0000000,0x10000000,0xcffff000,8192,8192));
  assert(!ownsDma(UINT64_MAX-4095,8192,0,4096,4096));
  assert(!ownsDma(0xc0000000,0x10000000,0xc0100001,4096,4096));
  assert(!ownsDma(0xc0000000,0x10000000,0xc0100000,8192,4096));
  t970_smmu::Report r;
  r.id0=0x4c017e57;r.id1=0x6000004a;r.id2=0x5111;r.geometryValid=true;r.scanned=87;r.valid=1;
  r.streams[4]={0x84020820,4,true};r.streams[2].smr=0x4e0;r.streams[3].smr=0xe0;
  r.streams[0x55].s2cr=r.streams[0x56].s2cr=0x200ff;
  assert(candidate(r,0x100ff,1,0xe0));
  assert(!candidate(r,0,0,0x3ab3a706));
  assert(!candidate(r,0x100ff,1,0xe1));
  r.streams[7]={0x80000123,0,true};assert(!candidate(r,0x100ff,1,0xe0));
  r.streams[7]={};r.streams[0x55].smr=1;assert(!candidate(r,0x100ff,1,0xe0));
  puts("PASS: preflight bounds and route refusal cases");
}
