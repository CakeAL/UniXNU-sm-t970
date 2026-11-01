#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <map>
#include <vector>
#include <utility>
#include "T970NopTest.h"
struct Port {
  std::map<unsigned,uint32_t> sm, hc;
  std::vector<std::pair<unsigned,uint32_t>> writes;
  unsigned mode=0, commands=0;
  Port() {
    sm[0]=0x2d0406; sm[0x20]=0x4c017e57; sm[0x24]=0x6000004a; sm[0x28]=0x5111;
    for(unsigned i=0;i<87;++i) sm[0xc00+4*i]=0x200ff;
    sm[0x810]=0x84020820; sm[0xc10]=4; sm[0x808]=0x4e0; sm[0x80c]=0xe0;
    sm[0x1000]=0x100ff;sm[0x1800]=1;sm[0x80000]=0xe0;sm[0x80058]=0x400;
    sm[0x1010]=0x1f000;sm[0x1810]=1;sm[0x84000]=0xe0;sm[0x84058]=0x400;
    hc[0x34]=1;hc[0x30]=0x10f;hc[0x20]=0x400;hc[0x60]=hc[0x80]=1;
  }
  uint32_t smmuRead(unsigned off){return sm[off];}
  void smmuWrite(unsigned off,uint32_t value){
    assert(hc[0x60]==0 && hc[0x80]==0 && hc[0x24]==0);
    assert(off==0x954||off==0x958||off==0xd54||off==0xd58);
    if(off>=0xc00){assert(sm[off-0x400]==0 && value==0);}
    else assert(sm[off+0x400]==0);
    writes.emplace_back(off,value);
    if(mode==2 && off==0xd54)return;
    sm[off]=value;
    if(mode==3 && off==0xd54)sm[0x810]^=1;
    if(mode==4)sm[0x48]=1;
  }
  uint32_t hcRead(unsigned off){return hc[off];}
  void hcWrite(unsigned off,uint32_t value){
    // No broad status ack, reset, UIC command, task doorbell or cancellation.
    assert(off==0x24||off==0x60||off==0x80||off==0x50||off==0x54);
    hc[off]=value;
    if(mode==6 && off==0x60 && value==1)sm[0x80058]|=2;
  }
  bool wait(unsigned off,uint32_t mask,uint32_t value){return mode!=1 && (hc[off]&mask)==value;}
  bool submitted(){return commands!=0;}
  bool nop(){++commands;assert(sm[0x954]==0x800000e0&&sm[0x958]==0x800004e0);return mode!=5;}
};
int main(){
  t970_ufs::Clocks c;c.mapped=true;c.gdsc=0x80000000;c.axi=c.ahb=1;
  t970_ufs::Controller h;h.state=1;
  for(unsigned mode=0;mode<9;++mode){
    Port p;p.mode=mode;
    auto before=t970_smmu::collect([&](unsigned o){return p.smmuRead(o);},0x100000);
    if(mode==7)p.hc[0x58]=1;
    auto r=t970_nop::run(p,before,c,h,mode!=8,0xc47d2000);
    assert(p.commands<=1);
    if(mode==0)assert(r.stage==6 && r.success && r.protectedUnchanged && p.commands==1);
    if(mode==5)assert(r.stage==5 && !r.success && p.commands==1);
    if(mode!=0 && mode!=5)assert(!r.submitted && p.commands==0);
    if(mode==7||mode==8)assert(p.writes.empty());
    assert(p.sm[0x1000]==0x100ff && p.sm[0x1800]==1 && p.sm[0x80000]==0xe0);
    assert(p.hc[0x20]==0x400); // Existing evidence is not cleared by takeover.
  }
  puts("PASS: NOP route gates, queue refusal and one-shot failure retention");
}
